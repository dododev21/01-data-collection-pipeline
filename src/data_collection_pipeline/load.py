"""
Books to Scrape의 전처리 데이터를 MySQL에 저장하는 모듈입니다.

processed 파일명에서 페이지 범위와 배치 시각을 추출하고,
CSV 내부 source_page와 parsed_at이 같은 배치를 가리키는지 검증합니다.
배치 검증이 완료된 데이터만 MySQL books 테이블에 저장합니다.

입력 구조:
    data/processed/
        books_pages_001_003_processed_YYYYMMDD_HHMMSS.csv

저장 대상:
    MySQL books
"""

## 정규표현식 처리를 위한 표준 모듈
import re

## 날짜 및 시각 처리를 위한 표준 모듈
from datetime import datetime

## MySQL DECIMAL 타입 변환을 위한 Decimal
from decimal import Decimal

## 파일 경로 처리를 위한 Path
from pathlib import Path

## 타입 힌팅을 위한 Any
from typing import Any

## CSV 및 DataFrame 처리를 위한 pandas
import pandas as pd

## SQL 실행을 위한 SQLAlchemy text
from sqlalchemy import text

## SQLAlchemy Engine 타입
from sqlalchemy.engine import Engine

## SQLAlchemy 관련 예외 처리
from sqlalchemy.exc import SQLAlchemyError

## 프로젝트 공통 설정
from .config import APP_TIMEZONE, PROCESSED_DIR

## MySQL 연결 설정 및 Engine 생성 함수
from .database import (
    create_mysql_engine,
    load_database_config,
    test_mysql_connection,
)

## ===========================================================
## 1. Processed CSV 파일 규칙
## ===========================================================

## Processed CSV 검색 패턴
PROCESSED_CSV_PATTERN = 'books_pages_*_processed_*.csv'

## Processed CSV 파일명 검증 정규표현식
PROCESSED_FILE_PATTERN_RE = re.compile(
    r'^books_pages_(\d{3})_(\d{3})_processed_(\d{8}_\d{6})\.csv$'
)


## ===========================================================
## 2. MySQL 저장 컬럼 설정
## ===========================================================

## MySQL books 테이블에 저장할 컬럼
DB_COLUMNS = [
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

## 문자열 정제 대상 컬럼
STRING_COLUMNS = [
    'book_id',
    'title',
    'detail_url',
    'source_site',
    'source_url',
    'source_file',
    'price_text',
    'availability_text',
    'rating_text',
    'detail_path',
]

## NULL을 허용하지 않는 필수 컬럼
NOT_NULL_COLUMNS = DB_COLUMNS


## ===========================================================
## 3. MySQL DDL / DML
## ===========================================================

## books 테이블 생성 SQL
CREATE_BOOKS_TABLE_SQL = text(
    '''
    CREATE TABLE IF NOT EXISTS books (
        book_id VARCHAR(20) PRIMARY KEY,
        title VARCHAR(255) NOT NULL,
        price DECIMAL(10, 2) NOT NULL,
        rating TINYINT UNSIGNED NOT NULL,
        is_available BOOLEAN NOT NULL,
        detail_url VARCHAR(500) NOT NULL,
        source_site VARCHAR(100) NOT NULL,
        source_url VARCHAR(500) NOT NULL,
        source_page INT UNSIGNED NOT NULL,
        parsed_at DATETIME NOT NULL,
        processed_at DATETIME NOT NULL,
        source_file VARCHAR(255) NOT NULL,
        price_text VARCHAR(30) NOT NULL,
        availability_text VARCHAR(50) NOT NULL,
        rating_text VARCHAR(20) NOT NULL,
        detail_path VARCHAR(500) NOT NULL,
        last_checked_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,

        CONSTRAINT uq_books_detail_url UNIQUE (detail_url),
        CONSTRAINT chk_books_price CHECK (price > 0),
        CONSTRAINT chk_books_rating CHECK (rating BETWEEN 1 AND 5)
    )
    ENGINE=InnoDB
    DEFAULT CHARSET=utf8mb4
    COLLATE=utf8mb4_unicode_ci
    '''
)

## books 테이블 INSERT / UPDATE SQL
UPSERT_BOOK_SQL = text(
    '''
    INSERT INTO books (
        book_id,
        title,
        price,
        rating,
        is_available,
        detail_url,
        source_site,
        source_url,
        source_page,
        parsed_at,
        processed_at,
        source_file,
        price_text,
        availability_text,
        rating_text,
        detail_path
    )
    VALUES (
        :book_id,
        :title,
        :price,
        :rating,
        :is_available,
        :detail_url,
        :source_site,
        :source_url,
        :source_page,
        :parsed_at,
        :processed_at,
        :source_file,
        :price_text,
        :availability_text,
        :rating_text,
        :detail_path
    ) AS new
    ON DUPLICATE KEY UPDATE
        updated_at = IF(
            NOT (books.title <=> new.title)
            OR NOT (books.price <=> new.price)
            OR NOT (books.rating <=> new.rating)
            OR NOT (books.is_available <=> new.is_available)
            OR NOT (books.detail_url <=> new.detail_url),
            CURRENT_TIMESTAMP,
            books.updated_at
        ),
        title = new.title,
        price = new.price,
        rating = new.rating,
        is_available = new.is_available,
        detail_url = new.detail_url,
        source_site = new.source_site,
        source_url = new.source_url,
        source_page = new.source_page,
        parsed_at = new.parsed_at,
        processed_at = new.processed_at,
        source_file = new.source_file,
        price_text = new.price_text,
        availability_text = new.availability_text,
        rating_text = new.rating_text,
        detail_path = new.detail_path,
        last_checked_at = CURRENT_TIMESTAMP
    '''
)


## ===========================================================
## 4. Processed CSV 파일명 처리
## ===========================================================

def parse_processed_file_name(file_path: Path) -> tuple[int, int, datetime]:
    """
    processed CSV 파일명에서 페이지 범위와 배치 시각을 추출합니다.

    Args:
        file_path:
            페이지 범위와 배치 시각이 포함된 processed CSV 파일 경로

    Returns:
        시작 페이지, 종료 페이지, 배치 시각의 튜플
    """

    ## 파일명 패턴 검증
    matched = PROCESSED_FILE_PATTERN_RE.fullmatch(file_path.name)

    if matched is None:
        raise ValueError(f'processed CSV 파일명 형식이 올바르지 않습니다. {file_path.name}')

    ## 시작 페이지, 종료 페이지 추출
    start_page = int(matched.group(1))
    end_page = int(matched.group(2))

    ## 파일명의 배치 시각을 프로젝트 표준 시간대로 변환
    batch_at = datetime.strptime(matched.group(3), '%Y%m%d_%H%M%S').replace(
        tzinfo=APP_TIMEZONE
    )

    ## 페이지 범위 검증
    if start_page > end_page:
        raise ValueError(
            f'processed CSV의 페이지 범위가 올바르지 않습니다. {start_page}~{end_page}'
        )

    return (start_page, end_page, batch_at)


def find_latest_processed_csv(
    directory: Path = PROCESSED_DIR,
    pattern: str = PROCESSED_CSV_PATTERN,
) -> Path:
    """
    가장 최근 배치의 processed CSV 파일 경로를 반환합니다.
    """

    ## Processed 디렉터리 존재 여부 확인
    if not directory.is_dir():
        raise FileNotFoundError(f'전처리 데이터 폴더가 없습니다. {directory}')

    ## 파일명에서 추출한 배치 정보 저장
    file_infos: list[tuple[datetime, int, int, Path]] = []

    ## 검색 패턴에 맞는 Processed CSV 탐색
    for file_path in directory.glob(pattern):
        try:
            start_page, end_page, batch_at = parse_processed_file_name(file_path)
        except ValueError:
            continue

        file_infos.append((batch_at, start_page, end_page, file_path))

    ## 사용 가능한 파일이 없는 경우 예외 발생
    if not file_infos:
        raise FileNotFoundError('MySQL에 저장할 processed CSV 파일이 없습니다.')

    ## 배치 시각과 페이지 범위를 기준으로 정렬
    file_infos.sort(key=lambda item: (item[0], item[2], item[1]))

    return file_infos[-1][3]


## ===========================================================
## 5. Processed CSV 로드 및 배치 검증
## ===========================================================

def load_processed_csv(file_path: Path) -> pd.DataFrame:
    """
    processed CSV를 DataFrame으로 읽어 반환합니다.
    """

    ## 파일 존재 여부 검증
    if not file_path.is_file():
        raise FileNotFoundError(f'processed CSV 파일이 없습니다. {file_path}')

    ## Processed CSV 로드
    return pd.read_csv(
        file_path,
        dtype={
            'book_id': 'string',
            'title': 'string',
            'rating': 'Int64',
            'detail_url': 'string',
            'source_site': 'string',
            'source_url': 'string',
            'source_page': 'Int64',
            'source_file': 'string',
            'price_text': 'string',
            'availability_text': 'string',
            'rating_text': 'string',
            'detail_path': 'string',
            'is_available': 'boolean',
        },
        parse_dates=['parsed_at', 'processed_at'],
    )


def validate_processed_batch(
    df: pd.DataFrame,
    start_page: int,
    end_page: int,
    batch_at: datetime,
) -> None:
    """
    processed 파일명의 배치 정보와 CSV 내부 데이터를 비교하여 검증합니다.
    """

    ## 배치 검증 필수 컬럼 확인
    required_columns = {'source_page', 'parsed_at'}
    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(f'배치 검증에 필요한 컬럼이 누락되었습니다. {sorted(missing_columns)}')

    ## CSV 내부 source_page 목록 추출
    source_pages = (
        pd.to_numeric(df['source_page'], errors='coerce')
        .dropna()
        .astype(int)
        .sort_values()
        .unique()
        .tolist()
    )

    ## 파일명 기준 예상 페이지 목록 생성
    expected_pages = list(range(start_page, end_page + 1))

    ## 파일명과 CSV의 페이지 범위 비교
    if source_pages != expected_pages:
        raise ValueError(
            f'processed 파일명과 source_page 범위가 다릅니다. '
            f'파일명 : {expected_pages}, 데이터 : {source_pages}'
        )

    ## CSV 내부 parsed_at 값 확인
    parsed_times = pd.to_datetime(df['parsed_at'], errors='coerce').dropna().unique()

    ## 하나의 배치에는 parsed_at이 하나만 존재해야 함
    if len(parsed_times) != 1:
        raise ValueError('processed CSV의 parsed_at 배치 시각이 하나가 아닙니다.')

    parsed_at = pd.Timestamp(parsed_times[0]).to_pydatetime()

    ## 파일명의 배치 시각과 CSV parsed_at 비교
    if parsed_at != batch_at:
        raise ValueError(
            f'processed 파일명과 parsed_at 배치 시각이 다릅니다. '
            f'파일명 : {batch_at.isoformat()}, 데이터 : {parsed_at.isoformat()}'
        )


## ===========================================================
## 6. DataFrame 저장 전 검증
## ===========================================================

def prepare_and_validate_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    DataFrame을 MySQL 저장용 자료형으로 정리하고 검증합니다.
    """

    ## DB 저장 필수 컬럼 확인
    missing_columns = set(DB_COLUMNS) - set(df.columns)

    if missing_columns:
        raise ValueError(f'DB 저장에 필요한 컬럼이 누락되었습니다. {sorted(missing_columns)}')

    ## DB 저장 대상 컬럼만 복사
    database_df = df[DB_COLUMNS].copy()

    ## 문자열 컬럼 정제
    for column in STRING_COLUMNS:
        database_df[column] = database_df[column].astype('string').str.strip().replace('', pd.NA)

    ## 숫자형 컬럼 변환
    database_df['price'] = pd.to_numeric(database_df['price'], errors='coerce').astype('Float64')
    database_df['rating'] = pd.to_numeric(database_df['rating'], errors='coerce').astype('Int64')
    database_df['source_page'] = pd.to_numeric(
        database_df['source_page'], errors='coerce'
    ).astype('Int64')

    ## 날짜형 컬럼 변환
    database_df['parsed_at'] = pd.to_datetime(database_df['parsed_at'], errors='coerce')
    database_df['processed_at'] = pd.to_datetime(database_df['processed_at'], errors='coerce')

    ## 논리형 컬럼 변환
    database_df['is_available'] = database_df['is_available'].astype('boolean')

    ## 데이터 검증 오류 목록
    errors: list[str] = []

    ## 필수 컬럼 결측값 검증
    null_counts = database_df[NOT_NULL_COLUMNS].isna().sum()
    invalid_nulls = null_counts[null_counts > 0]

    if not invalid_nulls.empty:
        errors.append(f'필수 컬럼 결측 발생:\n{invalid_nulls.to_string()}')

    ## book_id 중복 검증
    if database_df['book_id'].duplicated().any():
        errors.append('중복된 book_id가 존재합니다.')

    ## detail_url 중복 검증
    if database_df['detail_url'].duplicated().any():
        errors.append('중복된 detail_url이 존재합니다.')

    ## 가격 범위 검증
    if (database_df['price'] <= 0).any():
        errors.append('유효하지 않은 가격(<= 0)이 존재합니다.')

    ## 평점 범위 검증
    if (~database_df['rating'].between(1, 5)).any():
        errors.append('유효하지 않은 평점(1~5 범위 벗어남)이 존재합니다.')

    ## 페이지 번호 범위 검증
    if (database_df['source_page'] <= 0).any():
        errors.append('유효하지 않은 페이지 번호(<= 0)가 존재합니다.')

    ## 검증 오류가 존재하면 저장 중단
    if errors:
        raise ValueError('DB 저장 전 데이터 검증 실패\n' + '\n\n'.join(errors))

    return database_df


## ===========================================================
## 7. DataFrame → DB Record 변환
## ===========================================================

def dataframe_to_database_records(df: pd.DataFrame) -> list[dict[str, Any]]:
    """
    DB 저장용 DataFrame을 Python 기본 자료형의 레코드 목록으로 변환합니다.
    """

    ## SQLAlchemy execute()에 전달할 레코드 목록
    records: list[dict[str, Any]] = []

    ## DataFrame 각 행을 Python 기본 자료형으로 변환
    for row in df.to_dict(orient='records'):
        record = {
            'book_id': str(row['book_id']),
            'title': str(row['title']),
            'price': Decimal(str(row['price'])).quantize(Decimal('0.01')),
            'rating': int(row['rating']),
            'is_available': bool(row['is_available']),
            'detail_url': str(row['detail_url']),
            'source_site': str(row['source_site']),
            'source_url': str(row['source_url']),
            'source_page': int(row['source_page']),
            'parsed_at': pd.Timestamp(row['parsed_at']).to_pydatetime(),
            'processed_at': pd.Timestamp(row['processed_at']).to_pydatetime(),
            'source_file': str(row['source_file']),
            'price_text': str(row['price_text']),
            'availability_text': str(row['availability_text']),
            'rating_text': str(row['rating_text']),
            'detail_path': str(row['detail_path']),
        }

        records.append(record)

    return records


## ===========================================================
## 8. MySQL books 테이블 처리
## ===========================================================

def create_books_table(engine: Engine) -> None:
    """
    books 테이블이 없으면 생성합니다.
    """

    ## Transaction 단위로 CREATE TABLE 실행
    with engine.begin() as connection:
        connection.execute(CREATE_BOOKS_TABLE_SQL)


def upsert_books(engine: Engine, records: list[dict[str, Any]]) -> int:
    """
    도서 레코드를 books 테이블에 UPSERT합니다.

    새로운 book_id는 INSERT하고
    기존 book_id는 UPDATE합니다.
    """

    ## 저장할 데이터가 없으면 처리하지 않음
    if not records:
        return 0

    ## Transaction 단위로 UPSERT 실행
    with engine.begin() as connection:
        result = connection.execute(UPSERT_BOOK_SQL, records)

    return int(result.rowcount)


def count_books(engine: Engine) -> int:
    """
    books 테이블에 실제 저장된 전체 도서 수를 조회합니다.

    Args:
        engine:
            MySQL SQLAlchemy Engine

    Returns:
        books 테이블 전체 행 수
    """

    ## books 테이블의 실제 저장 건수 조회
    query = text('SELECT COUNT(*) FROM books')

    ## SELECT COUNT(*) 실행
    with engine.connect() as connection:
        count = connection.execute(query).scalar_one()

    return int(count)


## ===========================================================
## 9. Load Pipeline 실행
## ===========================================================

def run_load(
    processed_csv_file: Path | None = None,
    engine: Engine | None = None,
) -> dict[str, int | str]:
    """
    processed CSV의 배치를 검증한 뒤 MySQL 저장까지 순서대로 실행합니다.

    Args:
        processed_csv_file:
            MySQL에 저장할 processed CSV 파일 경로

            값을 전달하지 않으면 data/processed 폴더에서
            가장 최근 배치 파일을 자동으로 찾습니다.

        engine:
            외부에서 생성한 SQLAlchemy Engine

            값을 전달하지 않으면 실행 환경에 따라
            로컬에서는 .env,
            AWS Lambda에서는 Secrets Manager 기반 설정으로
            새 Engine을 생성합니다.

    Returns:
        입력 파일명, 배치 시각, 데이터베이스명,
        입력 행 수, DB 영향 행 수,
        books 테이블 실제 저장 건수를 반환합니다.
    """

    ## 외부 Engine 전달 여부 확인
    owns_engine = engine is None

    ## 입력 파일이 지정되지 않으면 최신 Processed CSV 탐색
    if processed_csv_file is None:
        processed_csv_file = find_latest_processed_csv()

    ## 파일명에서 페이지 범위와 배치 시각 추출
    start_page, end_page, batch_at = parse_processed_file_name(processed_csv_file)

    ## Processed CSV 로드
    processed_df = load_processed_csv(processed_csv_file)

    ## 파일명과 CSV 내부 배치 정보 검증
    validate_processed_batch(
        df=processed_df,
        start_page=start_page,
        end_page=end_page,
        batch_at=batch_at,
    )

    ## DB 저장용 DataFrame 정제 및 검증
    database_df = prepare_and_validate_dataframe(processed_df)

    ## DataFrame을 SQLAlchemy 저장용 레코드로 변환
    records = dataframe_to_database_records(database_df)

    ## Engine이 외부에서 전달되지 않은 경우 실행 환경에 맞게 생성
    if engine is None:
        database_config = load_database_config()
        engine = create_mysql_engine(database_config)

    try:
        ## MySQL 연결 상태 확인
        connection_info = test_mysql_connection(engine)

        ## books 테이블 생성
        create_books_table(engine)

        ## Processed 데이터를 books 테이블에 UPSERT
        affected_row_count = upsert_books(engine, records)

        ## 실제 books 테이블 저장 건수 조회
        stored_book_count = count_books(engine)

        ## 실행 결과 출력
        print('=' * 70)
        print('전처리 도서 데이터 MySQL 저장 결과')
        print('=' * 70)

        print(f'입력 CSV : {processed_csv_file.name}')
        print(f'배치 시각 : {batch_at:%Y-%m-%d %H:%M:%S}')
        print(f'페이지 범위 : {start_page}~{end_page}')
        print(f'연결 데이터베이스 : {connection_info["database_name"]}')
        print(f'MySQL 버전 : {connection_info["mysql_version"]}')
        print(f'입력 데이터 수 : {len(records)}')
        print(f'DB 드라이버 영향 행 수 : {affected_row_count}')
        print(f'books 테이블 실제 저장 건수 : {stored_book_count}')

        ## Load 단계 실행 결과 반환
        return {
            'input_file': processed_csv_file.name,
            'batch_at': batch_at.strftime('%Y-%m-%d %H:%M:%S'),
            'database_name': connection_info['database_name'],
            'input_count': len(records),
            'affected_row_count': affected_row_count,
            'stored_book_count': stored_book_count,
        }

    finally:
        ## run_load() 내부에서 생성한 Engine만 직접 종료
        if owns_engine:
            engine.dispose()


## ===========================================================
## 10. 로컬 직접 실행
## ===========================================================

if __name__ == '__main__':
    try:
        ## 최신 Processed CSV를 MySQL에 적재
        run_load()

    except SQLAlchemyError as error:
        ## MySQL 처리 오류 출력
        print('MySQL 처리 중 오류가 발생했습니다.')
        print(f'오류 내용 : {error}')
        raise SystemExit(1) from error

    except (FileNotFoundError, OSError, ValueError) as error:
        ## 파일 또는 데이터 검증 오류 출력
        print('파일 처리 또는 데이터 검증에 실패했습니다.')
        print(f'오류 내용 : {error}')
        raise SystemExit(1) from error