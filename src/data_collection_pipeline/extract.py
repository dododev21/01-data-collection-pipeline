"""
Books to Scrape의 수집 배치 폴더에 저장된 원본 HTML을 파싱하는 모듈입니다.

raw와 interim이 같은 배치 이름을 사용하도록 변경합니다.
원본 HTML 배치 폴더의 이름을 그대로 사용하여 interim 배치 폴더를 만들고,
페이지별 파싱 CSV는 해당 폴더 안에 저장합니다.

입력 구조:
    data/raw/html/YYYYMMDD_HHMMSS/
        books_page_001.html
        books_page_002.html
        ...

출력 구조:
    data/interim/YYYYMMDD_HHMMSS/
        books_page_001_parsed.csv
        books_page_002_parsed.csv
        ...
"""

import re
from datetime import datetime
from pathlib import Path
from urllib.parse import urljoin

import pandas as pd
from bs4 import BeautifulSoup
from bs4.element import Tag

from .config import APP_TIMEZONE, BASE_URL, INTERIM_DIR, RAW_HTML_DIR

BATCH_DIR_PATTERN_RE = re.compile(r'^\d{8}_\d{6}$')
RAW_HTML_PATTERN = 'books_page_*.html'
RAW_FILE_PATTERN_RE = re.compile(r'^books_page_(\d{3})\.html$')

RATING_MAP = {
    'One': 1,
    'Two': 2,
    'Three': 3,
    'Four': 4,
    'Five': 5,
}

REQUIRED_COLUMNS = [
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
]


def parse_batch_directory_name(batch_dir: Path) -> datetime:
    """
    수집 배치 폴더명에서 수집 시각을 추출한다.

    Args:
        batch_dir:
            YYYYMMDD_HHMMSS 형식의 수집 배치 폴더 경로

    Returns:
        배치 폴더명에서 추출한 원본 HTML 수집 시각

    Raises:
        ValueError:
            폴더명이 지정한 형식과 일치하지 않는 경우

    Examples:
        data/raw/html/20260809_224616
    """

    if BATCH_DIR_PATTERN_RE.fullmatch(batch_dir.name) is None:
        raise ValueError(f'수집 배치 폴더명 형식이 올바르지 않습니다. {batch_dir.name}')

    return datetime.strptime(batch_dir.name, '%Y%m%d_%H%M%S').replace(tzinfo=APP_TIMEZONE)


def find_latest_batch_directory(directory: Path = RAW_HTML_DIR) -> Path:
    """
    data/raw/html 폴더에서 가장 최근 수집 배치 폴더를 반환한다.

    Args:
        directory:
            수집 배치 폴더들이 저장된 기본 HTML 폴더

    Returns:
        가장 최근 수집 배치 폴더 경로

    Raises:
        FileNotFoundError:
            기본 HTML 폴더가 없거나 유효한 수집 배치 폴더가 없는 경우
    """

    if not directory.is_dir():
        raise FileNotFoundError(f'원본 HTML 폴더가 없습니다. {directory}')

    batch_directories: list[tuple[datetime, Path]] = []

    for batch_dir in directory.iterdir():
        if not batch_dir.is_dir():
            continue

        try:
            collected_at = parse_batch_directory_name(batch_dir)
        except ValueError:
            continue

        batch_directories.append((collected_at, batch_dir))

    if not batch_directories:
        raise FileNotFoundError('파싱할 원본 HTML 수집 배치 폴더가 없습니다.')

    return max(batch_directories, key=lambda item: item[0])[1]


def parse_raw_file_name(file_path: Path) -> int:
    """
    원본 HTML 파일명에서 페이지 번호를 추출한다.

    Args:
        file_path:
            books_page_NNN.html 형식의 원본 HTML 파일 경로

    Returns:
        원본 HTML의 페이지 번호

    Raises:
        ValueError:
            파일명이 지정한 규칙과 일치하지 않는 경우

    Examples:
        books_page_001.html
    """

    matched = RAW_FILE_PATTERN_RE.fullmatch(file_path.name)

    if matched is None:
        raise ValueError(f'원본 HTML 파일명 형식이 올바르지 않습니다. {file_path.name}')

    return int(matched.group(1))


def find_raw_html_files(batch_dir: Path) -> list[Path]:
    """
    수집 배치 폴더의 HTML 파일을 페이지 순서대로 반환한다.

    페이지 번호가 중복되거나 중간 페이지가 누락된 경우 오류를 발생시킨다.

    Args:
        batch_dir:
            페이지별 원본 HTML 파일이 저장된 수집 배치 폴더

    Returns:
        페이지 번호순으로 정렬된 원본 HTML 파일 경로 목록

    Raises:
        FileNotFoundError:
            배치 폴더가 없거나 파싱할 HTML 파일이 없는 경우

        ValueError:
            페이지 번호가 중복되거나 누락된 경우
    """

    if not batch_dir.is_dir():
        raise FileNotFoundError(f'수집 배치 폴더가 없습니다. {batch_dir}')

    file_infos: list[tuple[int, Path]] = []

    for file_path in batch_dir.glob(RAW_HTML_PATTERN):
        try:
            source_page = parse_raw_file_name(file_path)
        except ValueError:
            continue

        file_infos.append((source_page, file_path))

    if not file_infos:
        raise FileNotFoundError(f'파싱할 원본 HTML 파일이 없습니다. {batch_dir}')

    file_infos.sort(key=lambda item: item[0])
    source_pages = [source_page for source_page, _ in file_infos]

    if len(source_pages) != len(set(source_pages)):
        raise ValueError(f'중복된 페이지 번호가 있습니다. {source_pages}')

    expected_pages = list(range(source_pages[0], source_pages[-1] + 1))

    if source_pages != expected_pages:
        raise ValueError(f'원본 HTML 배치에 누락된 페이지가 있습니다. {source_pages}')

    return [file_path for _, file_path in file_infos]


def load_raw_html(file_path: Path) -> bytes:
    """
    원본 HTML 파일을 바이트 데이터로 읽어 반환한다.

    Args:
        file_path:
            읽을 원본 HTML 파일 경로

    Returns:
        원본 HTML 바이트 데이터

    Raises:
        FileNotFoundError:
            지정한 원본 HTML 파일이 존재하지 않는 경우
    """

    if not file_path.is_file():
        raise FileNotFoundError(f'HTML 파일이 없습니다. {file_path}')

    return file_path.read_bytes()


def get_required_tag(
    parent: Tag,
    selector: str,
    field_name: str,
) -> Tag:
    """
    부모 태그에서 필수 하위 태그를 찾아 반환한다.

    Args:
        parent:
            검색 기준이 되는 부모 HTML 태그

        selector:
            찾을 CSS 선택자

        field_name:
            오류 메시지에 표시할 필드명

    Returns:
        선택자와 일치하는 첫 번째 HTML 태그

    Raises:
        ValueError:
            필수 태그를 찾지 못한 경우
    """

    tag = parent.select_one(selector)

    if tag is None:
        raise ValueError(f'{field_name} 태그를 찾지 못했습니다. 선택자 : {selector}')

    return tag


def parse_rating(rating_tag: Tag) -> tuple[str, int]:
    """
    평점 태그의 클래스에서 평점 단어와 숫자 평점을 추출한다.

    Args:
        rating_tag:
            star-rating 클래스가 있는 HTML 태그

    Returns:
        평점 단어와 숫자 평점의 튜플

    Raises:
        ValueError:
            One부터 Five까지의 평점 클래스를 찾지 못한 경우
    """

    rating_classes = rating_tag.get('class', [])

    rating_text = next(
        (
            class_name
            for class_name in rating_classes
            if class_name in RATING_MAP
        ),
        None,
    )

    if rating_text is None:
        raise ValueError(f'유효한 평점 클래스를 찾지 못했습니다. {rating_classes}')

    return (rating_text, RATING_MAP[rating_text])


def parse_book_item(product: Tag, base_url: str) -> dict[str, str | int]:
    """
    도서 상품 HTML 요소 한 건에서 도서 정보를 추출한다.

    Args:
        product:
            article.product_pod 도서 상품 요소

        base_url:
            상대 URL을 절대 URL로 변환할 기준 URL

    Returns:
        도서 한 건의 파싱 결과 딕셔너리

    Raises:
        ValueError:
            필수 태그나 필수 속성을 찾지 못한 경우
    """

    title_tag = get_required_tag(product, 'h3 a', '도서명')
    price_tag = get_required_tag(product, '.price_color', '가격')
    availability_tag = get_required_tag(product, '.availability', '재고 상태')
    rating_tag = get_required_tag(product, '.star-rating', '평점')

    title = title_tag.get('title')
    detail_path = title_tag.get('href')

    if not title:
        raise ValueError('도서명의 title 속성이 없습니다.')

    if not detail_path:
        raise ValueError('상세 페이지 href 속성이 없습니다.')

    rating_text, rating = parse_rating(rating_tag)

    return {
        'title': title,
        'price_text': price_tag.get_text(strip=True),
        'availability_text': availability_tag.get_text(strip=True),
        'rating_text': rating_text,
        'rating': rating,
        'detail_path': detail_path,
        'detail_url': urljoin(base_url, detail_path),
    }


def parse_books(
    html_content: bytes,
    source_page: int,
    source_url: str,
    source_file: str,
) -> pd.DataFrame:
    """
    한 페이지의 원본 HTML에서 모든 도서 정보를 파싱한다.

    각 도서 정보에 원본 페이지 번호, URL, 파일명을 함께 저장한다.

    Args:
        html_content:
            파싱할 원본 HTML 바이트 데이터

        source_page:
            원본 페이지 번호

        source_url:
            원본 페이지 URL

        source_file:
            원본 HTML 파일명

    Returns:
        한 페이지의 도서 정보가 저장된 DataFrame

    Raises:
        ValueError:
            도서 상품 요소를 찾지 못한 경우
    """

    soup = BeautifulSoup(html_content, 'html.parser')
    products = soup.select('article.product_pod')

    if not products:
        raise ValueError('도서 요소를 찾지 못했습니다. 원본 HTML과 CSS 선택자를 확인하세요.')

    books: list[dict[str, str | int]] = []

    for product in products:
        book_info = parse_book_item(product, source_url)
        book_info['source_page'] = source_page
        book_info['source_url'] = source_url
        book_info['source_file'] = source_file
        books.append(book_info)

    return pd.DataFrame(books)


def validate_books_dataframe(books_df: pd.DataFrame) -> int:
    """
    파싱 결과 DataFrame의 필수 데이터와 값의 범위를 검증한다.

    Args:
        books_df:
            한 페이지의 도서 파싱 결과 DataFrame

    Returns:
        중복된 상세 URL의 개수

    Raises:
        ValueError:
            DataFrame이 비어 있거나 필수 컬럼, 결측값,
            평점, 페이지 번호에 문제가 있는 경우
    """

    if books_df.empty:
        raise ValueError('파싱 결과 DataFrame이 비어 있습니다.')

    missing_columns = [
        column
        for column in REQUIRED_COLUMNS
        if column not in books_df.columns
    ]

    if missing_columns:
        raise ValueError(f'필수 컬럼이 누락되었습니다. {missing_columns}')

    null_counts = books_df[REQUIRED_COLUMNS].isna().sum()
    invalid_nulls = null_counts[null_counts > 0]

    if not invalid_nulls.empty:
        raise ValueError(f'필수 데이터에 결측값이 있습니다.\n{invalid_nulls.to_string()}')

    invalid_ratings = books_df.loc[~books_df['rating'].between(1, 5)]

    if not invalid_ratings.empty:
        raise ValueError('1부터 5 범위를 벗어난 평점이 있습니다.')

    invalid_pages = books_df.loc[books_df['source_page'] <= 0]

    if not invalid_pages.empty:
        raise ValueError('유효하지 않은 페이지 번호가 있습니다.')

    duplicate_count = int(books_df['detail_url'].duplicated().sum())

    return duplicate_count


def create_interim_batch_directory(
    batch_name: str,
    directory: Path = INTERIM_DIR,
) -> Path:
    """
    원본 HTML 배치와 같은 이름의 interim 배치 폴더를 생성한다.

    Args:
        batch_name:
            YYYYMMDD_HHMMSS 형식의 원본 HTML 배치 이름

        directory:
            interim 배치 폴더들이 저장되는 기본 경로

    Returns:
        생성된 interim 배치 폴더 경로

    Raises:
        ValueError:
            배치 이름이 지정한 형식과 일치하지 않는 경우
    """

    if BATCH_DIR_PATTERN_RE.fullmatch(batch_name) is None:
        raise ValueError(f'수집 배치 이름 형식이 올바르지 않습니다. {batch_name}')

    interim_batch_dir = directory / batch_name
    interim_batch_dir.mkdir(parents=True, exist_ok=True)

    return interim_batch_dir


def save_parsed_csv(
    books_df: pd.DataFrame,
    source_page: int,
    interim_batch_dir: Path,
) -> Path:
    """
    한 페이지의 파싱 결과를 interim 배치 폴더 안의 CSV 파일로 저장한다.

    배치 폴더가 수집 시각을 관리하므로
    CSV 파일명에는 페이지 번호와 처리 단계만 포함한다.

    Args:
        books_df:
            한 페이지에서 파싱한 도서 DataFrame

        source_page:
            원본 페이지 번호

        interim_batch_dir:
            파싱 CSV 파일을 저장할 interim 배치 폴더

    Returns:
        저장된 CSV 파일 경로
    """

    parsed_file = interim_batch_dir / f'books_page_{source_page:03d}_parsed.csv'
    books_df.to_csv(parsed_file, index=False, encoding='utf-8-sig')

    return parsed_file


def verify_saved_csv(
    parsed_file: Path,
    original_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    저장한 CSV 파일을 다시 읽고 저장 전후의 행 수를 검증한다.

    Args:
        parsed_file:
            저장한 CSV 파일 경로

        original_df:
            CSV 저장 전 원본 DataFrame

    Returns:
        다시 읽은 CSV DataFrame

    Raises:
        ValueError:
            CSV 저장 전후의 행 수가 다른 경우
    """

    saved_books_df = pd.read_csv(parsed_file, dtype=str)

    if len(saved_books_df) != len(original_df):
        raise ValueError('CSV 저장 전후의 행 수가 다릅니다.')

    return saved_books_df


def run_extract(batch_dir: Path | None = None) -> list[Path]:
    """
    수집 배치의 원본 HTML을 파싱하고 같은 배치 이름의 interim 폴더에 저장한다.

    Args:
        batch_dir:
            파싱할 원본 HTML 수집 배치 폴더

            값을 전달하지 않으면 data/raw/html 폴더에서
            가장 최근 수집 배치 폴더를 자동으로 찾는다.

    Returns:
        페이지별로 저장된 CSV 파일 경로 목록

    Raises:
        ValueError:
            페이지 내 중복 상세 URL이 있는 경우
    """

    if batch_dir is None:
        batch_dir = find_latest_batch_directory()

    collected_at = parse_batch_directory_name(batch_dir)
    raw_html_files = find_raw_html_files(batch_dir)

    ## raw 배치와 같은 이름의 interim 배치 폴더 생성
    interim_batch_dir = create_interim_batch_directory(batch_dir.name)

    parsed_files: list[Path] = []
    total_book_count = 0

    for raw_html_file in raw_html_files:
        source_page = parse_raw_file_name(raw_html_file)
        source_url = f'{BASE_URL}page-{source_page}.html'
        html_content = load_raw_html(raw_html_file)

        books_df = parse_books(
            html_content=html_content,
            source_page=source_page,
            source_url=source_url,
            source_file=raw_html_file.name,
        )

        duplicate_count = validate_books_dataframe(books_df)

        if duplicate_count > 0:
            raise ValueError(
                f'{source_page}페이지에 중복 상세 URL이 있습니다. '
                f'중복 수 : {duplicate_count}'
            )

        parsed_file = save_parsed_csv(
            books_df=books_df,
            source_page=source_page,
            interim_batch_dir=interim_batch_dir,
        )

        verify_saved_csv(parsed_file, books_df)

        parsed_files.append(parsed_file)
        total_book_count += len(books_df)

        print(f'{source_page:03d}페이지 파싱 완료 : {len(books_df)}')
        print(f'저장 파일 : {parsed_file.name}')

    print('=' * 60)
    print('정적 웹페이지 페이지네이션 파싱 완료')
    print('=' * 60)

    print(f'원본 HTML 배치 : {batch_dir.name}')
    print(f'수집 배치 시각 : {collected_at:%Y-%m-%d %H:%M:%S}')
    print(f'파싱 페이지 수 : {len(parsed_files)}')
    print(f'전체 파싱 도서 수 : {total_book_count}')
    print(f'생성된 CSV 수 : {len(parsed_files)}')
    print(f'interim 저장 폴더 : {interim_batch_dir}')

    return parsed_files


if __name__ == '__main__':
    try:
        run_extract()

    except (FileNotFoundError, OSError, ValueError) as error:
        print('웹페이지 파싱 작업에 실패했습니다.')
        print(f'오류 내용 : {error}')

        raise SystemExit(1) from error




