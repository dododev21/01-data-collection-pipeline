from datetime import datetime
from pathlib import Path
import re

import pandas as pd


BASE_URL = 'https://books.toscrape.com/'
SOURCE_SITE = 'Books to Scrape'

PROJECT_DIR = Path(__file__).resolve().parents[2]
INTERIM_DIR = PROJECT_DIR / 'data' / 'interim'
PROCESSED_DIR = PROJECT_DIR / 'data' / 'processed'

PARSED_CSV_PATTERN = 'books_page_001_parsed_*.csv'

REQUIRED_INPUT_COLUMNS = {
    'title',
    'price_text',
    'availability_text',
    'rating_text',
    'rating',
    'detail_path',
    'detail_url',
}

STRING_COLUMNS = [
    'title',
    'price_text',
    'availability_text',
    'rating_text',
    'detail_path',
    'detail_url',
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

REQUIRED_PROCESSED_COLUMNS = set(COLUMN_ORDER)


def find_latest_parsed_csv(
    directory: Path = INTERIM_DIR,
    pattern: str = PARSED_CSV_PATTERN
):
    """
    파일명 패턴과 일치하는 최신 파싱 csv를 반환한다.

    Args:
        directory:
            중간 csv 파일이 저장된 폴더

        pattern:
            검색할 파일명 패턴
    
    Returns:
        파일명 기준으로 가장 마지막에 있는 csv 파일 경로

    Raises:
        FileNotFoundError:
            폴더가 없거나 패턴에 맞는 csv가 없는 경우
    
    """

    if not directory.exists():
        raise FileNotFoundError(f'중간 데이터 폴더가 없습니다. {directory}')

    parsed_files = sorted(directory.glob(pattern))
    # print(parsed_files)

    if not parsed_files:
        raise FileNotFoundError(
            '전처리할 파싱 csv 파일이 없습니다. '
            '먼저 프로젝트 루트에서 main.py를 실행하세요'
        )

    return parsed_files[-1]   

def load_parsed_csv(
    file_path: Path,
) -> pd.DataFrame:
    """
    파싱 csv를 DataFrame으로 읽어 반환한다.

    Args:
        file_path:
            읽을 파싱 csv 파일 경로

    Returns:
        파싱 데이터가 저장된 DataFrame

    Raises:
        FileNotFoundError:
            지정한 csv 파일이 존재하지 않는 경우    
    """
    if not file_path.is_file():
        raise FileNotFoundError(f'파싱 csv 파일이 없습니다. : {file_path}')

    return pd.read_csv(file_path, dtype='string')        

    
def validate_input_books(books_df: pd.DataFrame) -> None:
    """
    전처리 입력 DataFrame의 필수 구조를 검증한다.

    Raises:
        ValueError:
            DataFrame이 비어 있거나 필수 컬럼이 없는 경우
    """

    if books_df.empty:
        raise ValueError('전처리할 파싱 데이터가 비어 있습니다.')

    missing_columns = REQUIRED_INPUT_COLUMNS - set(books_df.columns)
        
    if missing_columns:
        raise ValueError(f'입력 데이터의 필수 컬럼이 누락되었습니다. : {missing_columns}')
        

def clean_string_columns(df: pd.DataFrame) -> pd.DataFrame:
    """
    문자열 컬럼을 Pandas string dtype으로 변환하고 공백을 정리한다.

    빈 문자열은 pd.NA로 변환한다.    
    """
    clean_df = df.copy()

    for column in STRING_COLUMNS:
        clean_df[column] = (
            clean_df[column]
            .astype('string')
            .str
            .strip()
            .replace('', pd.NA)
        )

    return clean_df    

    
def parse_price(price_series: pd.Series) -> pd.Series:
    """
    가격 문자열에서 숫자 부분을 추출하여 Float64로 변환한다.

    숫자로 변환할 수 없는 값은 errors='coerce'에 의해
    결측값으로 처리되며, 이후 검증 단계에서 확인한다.    
    """

    number_text = pd.Series(
        price_series
        .astype('string')
        .str
        .extract(r'(\d+\.\d+)', expand=False)       
    )

    # print(type(number_text))
    # print(number_text.dtype)

    return pd.to_numeric(number_text, errors='coerce').astype('Float64')

    
def parse_availability(value: object) -> bool | None:
    """
    재고 상태 문자열을 True, False 또는 None으로 변환한다.    
    """

    if pd.isna(value):
        return None

    normalized = str(value).strip().casefold()

    if 'out of stock' in normalized:
        return False

    if 'in stock' in normalized:
        return True

    return None

    
def extract_file_timestamp(file_path: Path) -> pd.Timestamp:
    """
    파일명에서 YYYYMMDD_HHMMSS 형식의 시각을 추출한다.

    파일명에서 시각을 찾지 못하면 파일 수정 시각을 사용한다.    
    """
    match = re.search(r'(\d{8}_\d{6})', str(file_path))

    if match:
        file_datetime = datetime.strptime(match.group(1), '%Y%m%d_%H%M%S')
        return pd.Timestamp(file_datetime)

    return pd.Timestamp(datetime.fromtimestamp(file_path.stat().st_mtime))

    
def add_processing_metadata(
    df: pd.DataFrame,
    source_file: Path,
    parsed_at: pd.Timestamp,
    source_url: str = BASE_URL,
    source_page: int = 1,    
):
    """
    전처리 DataFrame에 출처와 처리 시각 메타데이터를 추가한다.

    source_url, source_page, source_file 컬럼이 이미 존재하면
    기존 값을 유지하고 자료형만 정리한다.
    """

    metadata_df = df.copy()

    metadata_df['source_site'] = pd.Series(
        SOURCE_SITE, index=metadata_df.index, dtype='string'
    )

    if 'source_url' not in metadata_df.columns:
        metadata_df['source_url'] = pd.Series(
            source_url, index=metadata_df.index, dtype='string'
        )
    else:
        metadata_df['source_url'] = (
            metadata_df['source_url']
            .astype('string')
            .str
            .strip()
            .replace('', pd.NA)            
        )

    if 'source_page' not in metadata_df.columns:
        metadata_df['source_page'] = pd.Series(
            source_page, 
            index=metadata_df.index, 
            dtype='Int64'
        )
    else:
         metadata_df['source_page'] = (
            pd.to_numeric(
                metadata_df['source_page'],
                errors='coerce',                
            ).astype('Int64')  
        )   

    if 'source_file' not in metadata_df.columns:
        metadata_df['source_file'] = pd.Series(
            source_file.name,
            index=metadata_df.index,
            dtype='string'
        )
    else:
        metadata_df['source_file'] = (
            metadata_df['source_file']
            .astype('string')
            .str
            .strip()
            .replace('', pd.NA)            
        )        

    metadata_df['parsed_at'] = pd.Timestamp(parsed_at)
    metadata_df['processed_at'] = pd.Timestamp.now().floor('s')

    return metadata_df   

    
def preprocessing_books(
    books_df: pd.DataFrame,
    source_file: Path,
    parsed_at: pd.Timestamp | None = None,
    source_url: str = BASE_URL,
    source_page: int = 1,    
) -> pd.DataFrame:
    """
    파싱된 도서 데이터를 분석 가능한 구조로 전처리한다.

    Args:
        books_df:
            파싱된 도서 DataFrame

        source_file:
            입력 파싱 csv 파일 경로

        parsed_at:
            파싱 csv 생성 시각
            전달하지 않으면 파일명에서 추출

        source_url:
            데이터 출처 URL

        source_page:
            기본 출처 페이지 번호
            DataFrame에 soruce_page 컬럼이 있으면 기존 값 유지

    Returns:
        전처리와 중복 제거가 완료된 DataFrame    
    """

    ## 입력 DataFrame의 행과 필수 컬럼 검증
    validate_input_books(books_df)

    ## 문자열 컬럼 정리
    processed_df = clean_string_columns(books_df)

    ## 가격 문자열에서 숫자를 추출하여 price 컬럼 생성
    processed_df['price'] = parse_price(processed_df['price_text'])

    ## is_available 컬럼 추가
    processed_df['is_available'] = (
        processed_df['availability_text']
        .map(parse_availability)
        .astype('boolean')
    )

    ## rating 컬럼을 정수 자료형으로 변환
    processed_df['rating'] = (
        pd.to_numeric(
            processed_df['rating'],
            errors='coerce',
        ).astype('Int64')
    )

    ## book_id 컬럼 추가
    processed_df['book_id'] = (
        processed_df['detail_url']
        .str
        .extract(r'_(\d+)/index\.html$', expand=False)
        .astype('string')
    )

    ## parsed_at이 없으면 파일명에서 파싱 시각 추출
    if parsed_at is None:
        parsed_at = extract_file_timestamp(source_file)

    ## 메타데이터 컬럼 추가
    processed_df = add_processing_metadata(
        df=processed_df,
        source_file=source_file,
        parsed_at=parsed_at,
        source_page=source_page,
    )

    ## detail_url 기준 중복 제거 후 마지막 행 유지
    processed_df = (
        processed_df.drop_duplicates(
            subset=['detail_url'], 
            keep='last',
        )
        .reset_index(drop=True)
    )

    ## 컬럼 순서를 정리한 전처리 DataFrame 반환
    return processed_df[COLUMN_ORDER]

    
def ensure_directory(directory: Path) -> Path:
    """
    폴더가 없으면 생성하고, 폴더 경로를 반환한다.
    """

    directory.mkdir(parents=True, exist_ok=True)

    return directory


def save_csv_atomically(
    df: pd.DataFrame,
    file_path: Path,
) -> Path:
    """
    DataFrame을 임시 csv에 저장한 후, 최종 파일로 교체한다.

    Args:
        df:
            저장할 DataFrame

        file_path:
            최종 csv 파일 경로

    Returns:
        저장된 최종 csv 파일 경로
    """

    ensure_directory(file_path.parent)
    temp_path = file_path.with_suffix('.tmp.csv')

    try:
        df.to_csv(
            temp_path, 
            index=False, 
            encoding='utf-8-sig',
            date_format='%Y-%m-%d %H:%M:%S'
        )
        temp_path.replace(file_path)
    except Exception:
        if temp_path.exists():
            temp_path.unlink()
        raise
            
    return file_path    

    
def validate_processed_books(
    df: pd.DataFrame,
    base_url: str = BASE_URL,
    required_columns: set = REQUIRED_PROCESSED_COLUMNS,
) -> dict[str, int]:
    """
    전처리된 도서 데이터의 품질 규칙을 검증한다.

    Returns:
        검증 요약 정보

    Raises:
        ValueError:
            하나 이상의 검증 규칙을 통과하지 못한 경우    
    """

    errors: list[str] = list()

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        errors.append(f'필수 컬럼 누락 : {sorted(missing_columns)}')

    if not missing_columns and not df.empty:
        required_not_null = [
            'book_id', 
            'title', 
            'price', 
            'rating', 
            'is_available',
            'detail_url',
            'parsed_at',
            'processed_at',
        ]

        null_counts = df[required_not_null].isna().sum()
        invalid_null_counts = null_counts[null_counts > 0]

        if not invalid_null_counts.empty:
            errors.append(f'필수값 결측 :\n{invalid_null_counts.to_string()}')

        invalid_price_count = (df['price'].isna() | (df['price'] <= 0)).sum()

        if invalid_price_count:
            errors.append(f'유효하지 않은 가격 : {invalid_price_count} 건')

        invalid_rating_count = (df['rating'].isna() | ~df['rating'].between(1, 5)).sum()

        if invalid_rating_count:
            errors.append(f'유효하지 않은 평점 : {invalid_rating_count} 건')
        
        invalid_url_count = (
            df['detail_url'].isna() 
            | ~df['detail_url'].fillna('').str.startswith(base_url)
        ).sum()

        if invalid_url_count:
            errors.append(f'유효하지 않은 상세 URL : {invalid_url_count} 건')

        duplicate_url_count = df['detail_url'].duplicated(keep=False).sum()

        if duplicate_url_count:
            errors.append(f'중복 상세 URL : {duplicate_url_count} 건')

    if errors:
        raise ValueError('전처리 데이터 검증 실패\n' + '\n\n'.join(errors))
        
    return {
        'row_count': len(df),
        'column_count': len(df.columns),
        'duplicate_url_count': df['detail_url'].duplicated(keep=False).sum(),
        'null_count': df.isna().sum().sum()
    }

    
def build_processed_file_path(
    parsed_csv_file: Path,
    directory: Path = PROCESSED_DIR,
) -> Path:
    """
    파싱 csv 파일명을 기준으로 전처리 csv 경로를 생성한다.

    예:
        books_page_001_parsed_20260803_124432.csv
        -> books_page_001_processed_20260803_124432.csv
    """

    if '_parsed_' in parsed_csv_file.name:
        processed_file_name = (
             parsed_csv_file
                 .name
                 .replace('_parsed_', '_processed_', 1)   
        )
    else:
        timestamp = extract_file_timestamp(parsed_csv_file).strftime('%Y%m%d_%H%M%S')
        processed_file_name = f'books_page_001_processed_{timestamp}.csv'

    return directory / processed_file_name

    
def save_processed_csv(
    processed_df: pd.DataFrame,
    parsed_csv_file: Path,
    directory: Path = PROCESSED_DIR
) -> Path:
    """
    전처리 DataFrame을 processed 폴더에 원자적으로 저장한다.
    """

    output_file = build_processed_file_path(parsed_csv_file, directory)

    return save_csv_atomically(processed_df, output_file)
    

def verify_saved_csv(
    saved_file: Path,
    original_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    저장한 csv를 다시 읽고 행 수와 컬럼 순서를 검증한다.
    """
    saved_df = pd.read_csv(saved_file)

    if len(saved_df) != len(original_df):
        raise ValueError('csv 저장 전후의 행 수가 다릅니다.')
    
    if list(saved_df.columns) != list(original_df.columns):
        raise ValueError('csv 저장 전후의 컬럼 순서가 다릅니다.')

    return saved_df

    
def run_preprocess(
    parsed_csv_file: Path | None = None
) -> Path:
    """
    파싱 csv 선택부터 전처리 csv 저장까지 순서대로 실행한다.

    Args:
        parsed_csv_file:
            전처리할 파싱 csv 경로
            전달하지 않으면 data/interim의 최신 파일 사용한다.

    Returns:
        저장된 전처리 csv 파일 경로
    """

    ## 입력 파일을 전달하지 않으면, 최신 파싱 csv 경로 선택
    if parsed_csv_file is None:
        parsed_csv_file = find_latest_parsed_csv()

    ## 파싱 csv를 DataFrame으로 불러오기
    books_df = load_parsed_csv(parsed_csv_file)

    ## 파싱 csv 파일명에서 생성 날짜와 시각 추출
    parsed_at = extract_file_timestamp(parsed_csv_file)

    ## 파싱 DataFrame을 분석 가능한 구조로 전처리
    processed_df = preprocessing_books(
        books_df=books_df,
        source_file=parsed_csv_file,
        parsed_at=parsed_at,
    )

    ## 전처리 결과 검증 및 검증 요약 생성
    validation_summary = validate_processed_books(
        processed_df,
    )

    ## 중복 제거로 삭제된 행 수 계산
    removed_duplicate_count = len(books_df) - len(processed_df)

    ## 전처리된 DataFrame을 csv 파일로 저장
    saved_file = save_processed_csv(
        processed_df=processed_df,
        parsed_csv_file=parsed_csv_file,
    )

    ## 저장한 csv를 다시 읽어 행 수와 컬럼 순서 검증
    verify_saved_csv(
        saved_file=saved_file,
        original_df=processed_df,
    )

    print('=' * 70)
    print('정적 웹페이지 전처리 결과')
    print('=' * 70)
    
    print(f'입력 파싱 csv : {parsed_csv_file.name}')
    print(f'파싱 데이터 수 : {len(books_df)}')
    print(f'제거된 중복 수 : {removed_duplicate_count}')
    print(f'가격 변환 실패 수 : {processed_df.price.isna().sum()}')
    print(f'재고 변환 실패 수 : {processed_df.is_available.isna().sum()}')
    print(f'식별자 추출 실패 수 : {processed_df.book_id.isna().sum()}')
    print(f'재고 보유 도서 수 : {processed_df.is_available.sum()}')
    print(f'파싱 csv 생성 시각 : {parsed_at}')
    # print(f'전처리 실행 시각 : {processed_at}')
    print(f'전처리 csv 저장 경로 : {saved_file}')
    # print(f'검증 결과 : {validation_summary}')

    return saved_file   


if __name__ == '__main__':
    try:
        run_preprocess()
    except (FileNotFoundError, OSError, ValueError) as error:
        print('정적웹페이지 전처리 작업에 실패했습니다.')
        print(f'오류 내용 : {error}')