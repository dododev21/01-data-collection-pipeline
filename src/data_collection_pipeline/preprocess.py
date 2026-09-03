"""
Books to Scrape의 페이지별 파싱 CSV를 통합하여 전처리하는 모듈입니다.

data/interim/YYYYMMDD_HHMMSS 형태의 배치 폴더를 사용합니다.
가장 최근 interim 배치 폴더를 찾고, 해당 폴더의 페이지별 CSV를 통합하여
가격, 재고 상태, 평점, 도서 식별자와 메타데이터를 정리합니다.

입력 구조:
    data/interim/YYYYMMDD_HHMMSS/
        books_page_001_parsed.csv
        books_page_002_parsed.csv
        ...

출력 구조:
    data/processed/
        books_pages_001_003_processed_YYYYMMDD_HHMMSS.csv
"""

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from .config import APP_TIMEZONE, BASE_URL, INTERIM_DIR, PROCESSED_DIR, SOURCE_SITE

BATCH_DIR_PATTERN_RE = re.compile(r'^\d{8}_\d{6}$')
PARSED_CSV_PATTERN = 'books_page_*_parsed.csv'
PARSED_FILE_PATTERN_RE = re.compile(r'^books_page_(\d{3})_parsed\.csv$')

REQUIRED_INPUT_COLUMNS = {
    'title',
    'price_text',
    'availability_text',
    'rating_text',
    'rating',
    'detail_path',
    'detail_url',
    'source_page',
    'source_url',
    'source_file',
}

STRING_COLUMNS = [
    'title',
    'price_text',
    'availability_text',
    'rating_text',
    'detail_path',
    'detail_url',
    'source_url',
    'source_file',
]

COLUMN_ORDER = [
    'book_id',
    'title',
    'price',
    'rating',
    'is_available',
    'detail_url',
    'source_site',
    'source_url',
    'source_page',
    'parsed_at',
    'processed_at',
    'source_file',
    'price_text',
    'availability_text',
    'rating_text',
    'detail_path',
]


def parse_batch_directory_name(batch_dir: Path) -> datetime:
    """
    interim 배치 폴더명에서 배치 시각을 추출한다.

    Args:
        batch_dir:
            YYYYMMDD_HHMMSS 형식의 interim 배치 폴더 경로

    Returns:
        배치 폴더명에서 추출한 날짜와 시각

    Raises:
        ValueError:
            폴더명이 지정한 형식과 일치하지 않는 경우

    Examples:
        data/interim/20260809_233901
    """

    if BATCH_DIR_PATTERN_RE.fullmatch(batch_dir.name) is None:
        raise ValueError(f'interim 배치 폴더명 형식이 올바르지 않습니다. {batch_dir.name}')

    return datetime.strptime(batch_dir.name, '%Y%m%d_%H%M%S').replace(tzinfo=APP_TIMEZONE)


def find_latest_interim_batch_directory(directory: Path = INTERIM_DIR) -> Path:
    """
    data/interim 폴더에서 가장 최근 배치 폴더를 반환한다.

    Args:
        directory:
            interim 배치 폴더들이 저장된 기본 경로

    Returns:
        가장 최근 interim 배치 폴더 경로

    Raises:
        FileNotFoundError:
            interim 폴더가 없거나 유효한 배치 폴더가 없는 경우
    """

    if not directory.is_dir():
        raise FileNotFoundError(f'interim 폴더가 없습니다. {directory}')

    batch_directories: list[tuple[datetime, Path]] = []

    for batch_dir in directory.iterdir():
        if not batch_dir.is_dir():
            continue

        try:
            batch_at = parse_batch_directory_name(batch_dir)
        except ValueError:
            continue

        batch_directories.append((batch_at, batch_dir))

    if not batch_directories:
        raise FileNotFoundError('전처리할 interim 배치 폴더가 없습니다.')

    return max(batch_directories, key=lambda item: item[0])[1]


def parse_parsed_file_name(file_path: Path) -> int:
    """
    파싱 CSV 파일명에서 페이지 번호를 추출한다.

    Args:
        file_path:
            books_page_NNN_parsed.csv 형식의 파싱 CSV 파일 경로

    Returns:
        파싱 CSV의 페이지 번호

    Raises:
        ValueError:
            파일명이 지정한 규칙과 일치하지 않는 경우

    Examples:
        books_page_001_parsed.csv
    """

    matched = PARSED_FILE_PATTERN_RE.fullmatch(file_path.name)

    if matched is None:
        raise ValueError(f'파싱 CSV 파일명 형식이 올바르지 않습니다. {file_path.name}')

    return int(matched.group(1))


def find_parsed_csv_files(batch_dir: Path) -> tuple[list[Path], list[int]]:
    """
    interim 배치 폴더의 파싱 CSV를 페이지 순서대로 반환한다.

    페이지 번호가 중복되거나 중간 페이지가 누락된 경우 오류를 발생시킨다.

    Args:
        batch_dir:
            페이지별 파싱 CSV가 저장된 interim 배치 폴더

    Returns:
        페이지 순으로 정렬된 CSV 파일 목록과 페이지 번호 목록

    Raises:
        FileNotFoundError:
            배치 폴더가 없거나 파싱 CSV 파일이 없는 경우

        ValueError:
            페이지 번호가 중복되거나 누락된 경우
    """

    if not batch_dir.is_dir():
        raise FileNotFoundError(f'interim 배치 폴더가 없습니다. {batch_dir}')

    file_infos: list[tuple[int, Path]] = []

    for file_path in batch_dir.glob(PARSED_CSV_PATTERN):
        try:
            source_page = parse_parsed_file_name(file_path)
        except ValueError:
            continue

        file_infos.append((source_page, file_path))

    if not file_infos:
        raise FileNotFoundError(f'전처리할 파싱 CSV 파일이 없습니다. {batch_dir}')

    file_infos.sort(key=lambda item: item[0])
    source_pages = [source_page for source_page, _ in file_infos]

    if len(source_pages) != len(set(source_pages)):
        raise ValueError(f'중복된 페이지 번호가 있습니다. {source_pages}')

    expected_pages = list(range(source_pages[0], source_pages[-1] + 1))

    if source_pages != expected_pages:
        raise ValueError(f'파싱 CSV 배치에 누락된 페이지가 있습니다. {source_pages}')

    parsed_csv_files = [file_path for _, file_path in file_infos]

    return (parsed_csv_files, source_pages)


def load_parsed_csv(file_path: Path) -> pd.DataFrame:
    """
    파싱 CSV 파일 한 개를 DataFrame으로 읽어 반환한다.

    Args:
        file_path:
            읽을 파싱 CSV 파일 경로

    Returns:
        파싱 데이터가 저장된 DataFrame

    Raises:
        FileNotFoundError:
            지정한 CSV 파일이 존재하지 않는 경우
    """

    if not file_path.is_file():
        raise FileNotFoundError(f'파싱 CSV 파일이 없습니다. {file_path}')

    return pd.read_csv(file_path, dtype='string')


def validate_input_books(books_df: pd.DataFrame) -> None:
    """
    전처리 입력 DataFrame의 행과 필수 컬럼을 검증한다.

    Args:
        books_df:
            검증할 파싱 DataFrame

    Raises:
        ValueError:
            DataFrame이 비어 있거나 필수 컬럼이 없는 경우
    """

    if books_df.empty:
        raise ValueError('전처리할 파싱 데이터가 비어 있습니다.')

    missing_columns = REQUIRED_INPUT_COLUMNS - set(books_df.columns)

    if missing_columns:
        raise ValueError(f'입력 데이터의 필수 컬럼이 누락되었습니다. {sorted(missing_columns)}')


def load_parsed_csv_files(parsed_csv_files: list[Path]) -> pd.DataFrame:
    """
    페이지별 파싱 CSV를 읽어 하나의 DataFrame으로 통합한다.

    파일명의 페이지 번호와 CSV 내부 source_page 값도 함께 검증한다.

    Args:
        parsed_csv_files:
            페이지 순서대로 정렬된 파싱 CSV 파일 경로 목록

    Returns:
        모든 페이지가 통합된 DataFrame

    Raises:
        ValueError:
            파일명 페이지 번호와 CSV 내부 페이지 번호가 다른 경우
    """

    page_frames: list[pd.DataFrame] = []

    for file_path in parsed_csv_files:
        source_page = parse_parsed_file_name(file_path)
        books_df = load_parsed_csv(file_path)
        validate_input_books(books_df)

        page_values = (
            pd.to_numeric(books_df['source_page'], errors='coerce')
            .dropna()
            .astype(int)
            .unique()
            .tolist()
        )

        if page_values != [source_page]:
            raise ValueError(
                f'파일명 페이지 번호와 CSV 내부 source_page가 다릅니다. '
                f'파일 : {file_path.name}, 값 : {page_values}'
            )

        page_frames.append(books_df)

    return pd.concat(page_frames, ignore_index=True)


def clean_string_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    문자열 컬럼을 Pandas string dtype으로 변환하고 앞뒤 공백을 제거한다.

    빈 문자열은 pd.NA로 변환한다.

    Args:
        df:
            문자열 컬럼을 정리할 DataFrame

    Returns:
        문자열 컬럼이 정리된 새로운 DataFrame
    """

    clean_df = df.copy()

    for column in STRING_COLUMNS:
        clean_df[column] = (
            clean_df[column]
            .astype('string')
            .str.strip()
            .replace('', pd.NA)
        )

    return clean_df


def parse_price(price_series: pd.Series) -> pd.Series:
    """
    가격 문자열에서 숫자를 추출하여 Float64 자료형으로 변환한다.

    Args:
        price_series:
            가격 문자열 Series

    Returns:
        Float64 자료형의 가격 Series
    """

    number_text = price_series.astype('string').str.extract(
        r'(\d+(?:\.\d+)?)',
        expand=False,
    )

    return pd.to_numeric(number_text, errors='coerce').astype('Float64')


def parse_availability(value: object) -> bool | None:
    """
    재고 상태 문자열을 논리값으로 변환한다.

    Args:
        value:
            재고 상태 값

    Returns:
        재고 있음은 True, 재고 없음은 False,
        판단할 수 없는 값은 None
    """

    if pd.isna(value):
        return None

    normalized = str(value).strip().casefold()

    if 'out of stock' in normalized:
        return False

    if 'in stock' in normalized:
        return True

    return None


def preprocess_books(
    books_df: pd.DataFrame,
    batch_at: datetime,
) -> pd.DataFrame:
    """
    통합된 도서 데이터를 분석 가능한 구조로 전처리한다.

    Args:
        books_df:
            모든 페이지가 통합된 파싱 DataFrame

        batch_at:
            interim 배치 폴더명에 포함된 배치 시각

    Returns:
        전처리와 페이지 간 중복 제거가 완료된 DataFrame
    """

    validate_input_books(books_df)

    processed_at = pd.Timestamp.now(tz=APP_TIMEZONE).floor('s')
    processed_df = clean_string_columns(books_df)

    ## 가격 문자열에서 숫자를 추출하여 price 컬럼 생성
    processed_df['price'] = parse_price(processed_df['price_text'])

    ## 재고 문자열을 논리값으로 변환하여 is_available 컬럼 생성
    processed_df['is_available'] = (
        processed_df['availability_text']
        .map(parse_availability)
        .astype('boolean')
    )

    ## rating 컬럼을 정수 자료형으로 변환
    processed_df['rating'] = pd.to_numeric(
        processed_df['rating'],
        errors='coerce',
    ).astype('Int64')

    ## 상세 URL에서 도서 식별자를 추출하여 book_id 컬럼 생성
    processed_df['book_id'] = (
        processed_df['detail_url']
        .str.extract(r'_(\d+)/index\.html$', expand=False)
        .astype('string')
    )

    ## 페이지 번호를 정수 자료형으로 변환
    processed_df['source_page'] = pd.to_numeric(
        processed_df['source_page'],
        errors='coerce',
    ).astype('Int64')

    ## 데이터 출처와 처리 시각 등의 메타데이터 컬럼 추가
    processed_df['source_site'] = SOURCE_SITE
    processed_df['parsed_at'] = pd.Timestamp(batch_at)
    processed_df['processed_at'] = processed_at

    ## detail_url 기준 중복 제거 후 마지막 행 유지
    processed_df = (
        processed_df
        .drop_duplicates(subset=['detail_url'], keep='last')
        .reset_index(drop=True)
    )

    return processed_df[COLUMN_ORDER]


def validate_processed_books(df: pd.DataFrame) -> dict[str, int]:
    """
    전처리된 도서 데이터의 필수 컬럼과 값의 품질을 검증한다.

    Args:
        df:
            검증할 전처리 DataFrame

    Returns:
        행 수, 컬럼 수, 중복 수, 결측값 수를 담은 검증 요약

    Raises:
        ValueError:
            하나 이상의 검증 규칙을 통과하지 못한 경우
    """

    if df.empty:
        raise ValueError('전처리 결과 DataFrame이 비어 있습니다.')

    missing_columns = set(COLUMN_ORDER) - set(df.columns)

    if missing_columns:
        raise ValueError(f'필수 컬럼이 누락되었습니다. {sorted(missing_columns)}')

    null_counts = df[COLUMN_ORDER].isna().sum()
    invalid_nulls = null_counts[null_counts > 0]

    if not invalid_nulls.empty:
        raise ValueError(f'필수 데이터에 결측값이 있습니다.\n{invalid_nulls.to_string()}')

    invalid_price_count = int((df['price'] <= 0).sum())
    invalid_rating_count = int((~df['rating'].between(1, 5)).sum())
    invalid_page_count = int((df['source_page'] <= 0).sum())
    invalid_url_count = int(
        (~df['detail_url'].str.startswith(BASE_URL, na=False)).sum()
    )
    duplicate_url_count = int(df['detail_url'].duplicated(keep=False).sum())
    duplicate_book_id_count = int(df['book_id'].duplicated(keep=False).sum())

    errors: list[str] = []

    if invalid_price_count:
        errors.append(f'유효하지 않은 가격 : {invalid_price_count}건')

    if invalid_rating_count:
        errors.append(f'유효하지 않은 평점 : {invalid_rating_count}건')

    if invalid_page_count:
        errors.append(f'유효하지 않은 페이지 번호 : {invalid_page_count}건')

    if invalid_url_count:
        errors.append(f'유효하지 않은 상세 URL : {invalid_url_count}건')

    if duplicate_url_count:
        errors.append(f'중복 상세 URL : {duplicate_url_count}건')

    if duplicate_book_id_count:
        errors.append(f'중복 book_id : {duplicate_book_id_count}건')

    if errors:
        raise ValueError('전처리 데이터 검증 실패\n' + '\n'.join(errors))

    return {
        'row_count': len(df),
        'column_count': len(df.columns),
        'duplicate_url_count': duplicate_url_count,
        'null_count': int(df.isna().sum().sum()),
    }


def ensure_directory(directory: Path) -> Path:
    """
    지정한 폴더가 없으면 생성하고 폴더 경로를 반환한다.
    """

    directory.mkdir(parents=True, exist_ok=True)

    return directory


def save_csv_atomically(df: pd.DataFrame, file_path: Path) -> Path:
    """
    DataFrame을 임시 CSV에 저장한 뒤 최종 파일로 교체한다.

    Args:
        df:
            저장할 DataFrame

        file_path:
            최종 CSV 파일 경로

    Returns:
        저장된 최종 CSV 파일 경로
    """

    ensure_directory(file_path.parent)
    temp_path = file_path.with_suffix('.tmp.csv')

    try:
        df.to_csv(
            temp_path,
            index=False,
            encoding='utf-8-sig',
            date_format='%Y-%m-%dT%H:%M:%S%z',
        )
        temp_path.replace(file_path)

    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise

    return file_path


def build_processed_file_path(
    source_pages: list[int],
    batch_at: datetime,
    directory: Path = PROCESSED_DIR,
) -> Path:
    """
    페이지 범위와 배치 시각으로 전처리 CSV 파일 경로를 생성한다.

    Args:
        source_pages:
            전처리한 페이지 번호 목록

        batch_at:
            interim 배치 폴더명에서 추출한 배치 시각

        directory:
            전처리 CSV 저장 폴더

    Returns:
        생성된 전처리 CSV 파일 경로
    """

    timestamp = batch_at.strftime('%Y%m%d_%H%M%S')
    file_name = (
        f'books_pages_{source_pages[0]:03d}_{source_pages[-1]:03d}_'
        f'processed_{timestamp}.csv'
    )

    return directory / file_name


def save_processed_csv(
    processed_df: pd.DataFrame,
    source_pages: list[int],
    batch_at: datetime,
) -> Path:
    """
    전처리 DataFrame을 하나의 processed CSV 파일로 저장한다.
    """

    output_file = build_processed_file_path(source_pages, batch_at)

    return save_csv_atomically(processed_df, output_file)


def verify_saved_csv(
    saved_file: Path,
    original_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    저장한 CSV를 다시 읽고 행 수와 컬럼 순서를 검증한다.

    Args:
        saved_file:
            저장한 CSV 파일 경로

        original_df:
            저장 전 전처리 DataFrame

    Returns:
        다시 읽은 CSV DataFrame

    Raises:
        ValueError:
            저장 전후의 행 수 또는 컬럼 순서가 다른 경우
    """

    saved_df = pd.read_csv(saved_file)

    if len(saved_df) != len(original_df):
        raise ValueError('CSV 저장 전후의 행 수가 다릅니다.')

    if list(saved_df.columns) != list(original_df.columns):
        raise ValueError('CSV 저장 전후의 컬럼 순서가 다릅니다.')

    return saved_df


def run_preprocess(interim_batch_dir: Path | None = None) -> Path:
    """
    interim 배치의 CSV를 통합하여 전처리하고 하나의 CSV로 저장한다.

    Args:
        interim_batch_dir:
            전처리할 interim 배치 폴더

            값을 전달하지 않으면 data/interim 폴더에서
            가장 최근 배치 폴더를 자동으로 찾는다.

    Returns:
        저장된 전처리 CSV 파일 경로
    """

    if interim_batch_dir is None:
        interim_batch_dir = find_latest_interim_batch_directory()

    batch_at = parse_batch_directory_name(interim_batch_dir)
    parsed_csv_files, source_pages = find_parsed_csv_files(interim_batch_dir)

    books_df = load_parsed_csv_files(parsed_csv_files)
    processed_df = preprocess_books(books_df, batch_at)
    validation_summary = validate_processed_books(processed_df)

    removed_duplicate_count = len(books_df) - len(processed_df)

    saved_file = save_processed_csv(
        processed_df=processed_df,
        source_pages=source_pages,
        batch_at=batch_at,
    )

    verify_saved_csv(saved_file, processed_df)

    print('=' * 70)
    print('정적 웹페이지 페이지네이션 전처리 완료')
    print('=' * 70)

    print(f'interim 배치 : {interim_batch_dir.name}')
    print(f'입력 페이지 : {source_pages[0]}~{source_pages[-1]}')
    print(f'입력 CSV 수 : {len(parsed_csv_files)}')
    print(f'통합 파싱 데이터 수 : {len(books_df)}')
    print(f'제거된 중복 수 : {removed_duplicate_count}')
    print(f'전처리 데이터 수 : {validation_summary["row_count"]}')
    print(f'배치 시각 : {batch_at:%Y-%m-%d %H:%M:%S}')
    print(f'전처리 CSV 저장 경로 : {saved_file}')

    return saved_file


if __name__ == '__main__':
    try:
        run_preprocess()

    except (FileNotFoundError, OSError, ValueError) as error:
        print('정적 웹페이지 전처리 작업에 실패했습니다.')
        print(f'오류 내용 : {error}')

        raise SystemExit(1) from error




