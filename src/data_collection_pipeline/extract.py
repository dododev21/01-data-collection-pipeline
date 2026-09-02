"""
저장된 원본 HTML을 파싱하는 모듈

이 모듈은 다음 작업을 수행합니다.

1. crawling 단계에서 저장한 원본 HTML을 읽는다.
2. BeautifulSoup으로 도서 데이터를 파싱한다.
3. 파싱 결과를 Pandas DataFrame으로 변환한다.
4. 필수 컬럼, 결측값, 평점, 중복 URL을 검증한다.
5. 중간 csv 파일로 저장한다.
6. 저장 결과를 다시 읽어 행 수를 검증한다.
"""


from pathlib import Path
from urllib.parse import urljoin
from datetime import datetime

import pandas as pd
from bs4 import BeautifulSoup
from bs4.element import Tag


TARGET_URL = 'https://books.toscrape.com'
PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_HTML_DIR = PROJECT_DIR / 'data' / 'raw' / 'html'

RAW_HTML_PATTERN = 'books_home_*.html'

RATING_MAP = {
    'One': 1,
    'Two': 2,
    'Three': 3,
    'Four': 4,
    'Five': 5
}

REQUIRED_COLUMNS = [
    'title', 
    'price_text', 
    'availability_text', 
    'rating_text', 
    'rating',
    'detail_path',
    'detail_url'
]

INTERIM_DIR = PROJECT_DIR / 'data' / 'interim'


def find_latest_raw_html(
    directory: Path = RAW_HTML_DIR,
    pattern: str = RAW_HTML_PATTERN,
) -> Path:
    """
    지정한 폴더에서 파일명 패턴과 일치하는 최신 HTML 파일을 반환한다.

    Args:
        directory:
            원본 HTML 파일이 저장된 폴더

        pattern:
            검색할 파일명 패턴

    Returns:
        파일명 기준으로 마지막에 있는 HTML 파일 경로

    Raises:
        FileNotFoundError:
            폴더가 없거나 패턴에 맞는 HTML 파일이 없는 경우    
    """
    if not directory.exists():
        raise FileNotFoundError(f'원본 HTML 폴더가 없습니다. {directory}')

    html_files = sorted(directory.glob(pattern))

    if not html_files:
        raise FileNotFoundError('파싱할 원본 HTML 파일이 없습니다.')

    return html_files[-1]


def load_raw_html(file_path: Path) -> bytes:
    """
    원본 HTML 파일을 바이트 데이터 읽어 반환한다.

    Args:
        file_path:
            읽을 HTML 파일 경로

    Returns:
        HTML 원본 바이트 데이터

    Raises:
        FileNotFoundError:
            지정한 파일이 존재하지 않는 경우    
    """
    if not file_path.is_file():
        raise FileNotFoundError(f'HTML 파일이 없습니다. {file_path}')

    return file_path.read_bytes()


def get_required_tag(
    parent: Tag,
    selector: str,
    field_name: str
) -> Tag:
    """
    부모 태그에서 필수하위 태그를 찾아 반환한다.

    Args:
        parent:
            검색 기준이 되는 부모 HTML 태그

        selector:
            찾을 CSS 선택자

        field_name
            오류 메시지에 표시할 필드명

    Returns:
        선택자와 일치하는 첫 번째 HTML 태그

    Raises:
       ValueError:
           필수 태그를 찾지 못한 경우    
    """
    tag = parent.select_one(selector)

    if tag is None:
        raise ValueError(
            f'{field_name} 태그를 찾지 못했습니다. '
            f'선택자 : {selector}'
        )

    return tag    


def parse_rating(rating_tag: Tag) -> tuple[str, int]:
    """
    평점 태그의 클래스에서 평점 단어와 숫자 평점을 추출한다.

    Args:
        rating_tag:
            start-rating 클래스가 있는 HTML 태그

    Returns:
        평점 단어와 숫자 평점의 튜플

    Raises:
        ValueError:
            One부터 Five까지의 평점 클래스를 찾지 못한 경우    
    """

    rating_classes = rating_tag.get('class', []) ## class 속성이 없다면, [] 리턴
    rating_text = rating_classes[-1]

    if rating_text is None:
        raise ValueError(f'유효한 평점 클래스를 찾지 못했습니다. : {rating_classes}')

    return (rating_text, RATING_MAP[rating_text])


def parse_book_item(
    product: Tag,
    base_url: str,
) -> dict[str, str | int]:
    """
    도서 상품 HTML 요소 한 개에서 도서 페이지 정보를 추출한다.

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

    book_info = {
        'title': title,
        'price_text': price_tag.get_text(strip=True),
        'availability_text': availability_tag.get_text(strip=True),
        'rating_text': rating_text,
        'rating': rating,
        'detail_path': detail_path,
        'detail_url': urljoin(base_url, detail_path)
    }

    return book_info   


def parse_books(
    html_content: bytes,
    base_url: str = TARGET_URL,
) -> pd.DataFrame:
    """
    원본 HTML에서 한 페이지의 모든 도서를 파싱한다.
    """
    soup = BeautifulSoup(html_content, features="html.parser")
    products = soup.select('article.product_pod')

    if not products:
        raise ValueError(
            '도서 요소를 찾지 못했습니다. '
            '원본 HTML과 CSS 선택자를 확인하세요.'
        )

    books = [
        parse_book_item(product, base_url) 
        for product in products 
    ]

    return pd.DataFrame(books)


def validate_books_dataframe(
        books_df: pd.DataFrame,
) -> int:
    """
    파싱 DataFrame을 검증하고 중복 URL 수 반환한다.
    """

    if books_df.empty:
        raise ValueError('파싱 결과 DataFrame이 비어 있습니다.')

    missing_columns = [
        column 
        for column in REQUIRED_COLUMNS
        if column not in books_df.columns
    ]

    if missing_columns:
        raise ValueError(f'필수 컬럼이 누락되었다. {missing_columns}')


    null_couts = books_df[REQUIRED_COLUMNS].isna().sum()

    if null_couts.sum() > 0:
        raise ValueError(f'필수 데이터에 결측값이 있습니다. {null_couts[null_couts > 0]}')

    invaild_ratings = books_df[~books_df['rating'].between(1, 5)]

    if not invaild_ratings.empty:
        raise ValueError('1부터 5 범위를 벗어난 평점이 있습니다.')
    

    duplicate_count = int(
        books_df['detail_url']
        .duplicated(keep=False)
        .sum()
    )

    return duplicate_count


def save_parsed_csv(
    books_df: pd.DataFrame,
    directory: Path = INTERIM_DIR,
    saved_at: datetime | None = None,
):
    """
    파싱 DataFrame을 중간 csv 파일로 저장한다.
    """

    directory.mkdir(parents=True, exist_ok=True)

    if saved_at is None:
        saved_at = datetime.now()

    timestamp = saved_at.strftime('%Y%m%d_%H%M%S')

    parsed_file = directory / f'books_page_001_parsed_{timestamp}.csv'
    books_df.to_csv(parsed_file, index=False, encoding='utf-8-sig')

    return parsed_file


def verify_saved_csv(
        parsed_file: Path,
        original_df: pd.DataFrame,
) -> pd.DataFrame:
    """
    저장한 csv 파일을 다시 읽고 저장 전후의 행 수를 검증한다.
    """

    saved_books_df = pd.read_csv(parsed_file, dtype=str)

    if len(saved_books_df) != len(original_df):
        raise ValueError('csv 저장 전후의 행 수가 다릅니다.')

    return saved_books_df


def run_extract(raw_html_file: Path | None = None) -> Path:
    """
    원본 HTML 파싱부터 중간 csv 저장까지 실행한다.

    Args:
        raw_html_file:
            파싱할 원본 HTML 파일 경로

            main.py에서 crawling.py 결과를 전달하면 해당 파일을 사용한다.
            값을 전달하지 않고 이 모듈을 직접 실행하면
            data/raw/html 폴더의 최신 파일을 자동으로 찾는다.
    
    Returns:
        저장된 중간 파일 경로
    """

    ## 저장된 원본 HTML의 최신 파일의 경로 리턴
    if raw_html_file is None:
        raw_html_file = find_latest_raw_html()

    ## 저장된 원본 HTML 파일 일기
    html_content = load_raw_html(raw_html_file)

    ## 원본 HTML에서 한 페이지의 도서 정보를 파싱하여 DataFrame 생성
    books_df = parse_books(html_content)

    ## DataFrame을 검증하고 중복 상세 URL 수 반환
    duplicate_count = validate_books_dataframe(books_df)

    ## DataFrame을 중간 csv 파일로 저장
    parsed_file = save_parsed_csv(books_df)

    ## 저장한 csv를 다시 읽고 저장 전후의 행 수 검증
    saved_books_df = verify_saved_csv(parsed_file, books_df)

    print('=' * 60)
    print('정적 웹페이지 파싱 결과')
    print('=' * 60)

    print(f'원본 HTML 파일 : {raw_html_file}')
    print(f'파싱한 도서 수 : {len(books_df)}')
    print(f'도서명 결측 수 : {books_df.title.isna().sum()}')
    print(f'상세 URL 중복 수 : {duplicate_count}')
    print(f'평점 최솟값 : {books_df.rating.min()}')
    print(f'평점 최댓값 : {books_df.rating.max()}')

    return parsed_file


if __name__ == '__main__':
    try:
        run_extract()
    except (FileNotFoundError, OSError, ValueError) as error:
        print(f'웹페이지 추출 작업에 실패했습니다. : {error}')
