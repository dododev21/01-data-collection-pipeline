from pathlib import Path
from typing import Any
import os

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import URL, create_engine, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError


PROJECT_DIR = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_DIR / 'data' / 'processed'
ENV_FILE = PROJECT_DIR / '.env'
PROCESSED_CSV_PATTERN = 'books_*_processed_*.csv'


## ----------------------------------------------
## DB 저장 컬럼
## ----------------------------------------------
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

## books 테이블의 컬럼 모두 NOT NULL
NOT_NULL_COLUMNS = DB_COLUMNS


## ----------------------------------------------
## SQL
## ----------------------------------------------
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
        last_checked_at DATETIME NOT NULL 
            DEFAULT CURRENT_TIMESTAMP,
        created_at DATETIME NOT NULL
            DEFAULT CURRENT_TIMESTAMP,
        updated_at DATETIME NOT NULL
            DEFAULT CURRENT_TIMESTAMP
            ON UPDATE CURRENT_TIMESTAMP,

        CONSTRAINT uq_books_detail_url
            UNIQUE (detail_url),

        CONSTRAINT chk_books_price
            CHECK (price > 0),

        CONSTRAINT chk_books_rating
            CHECK (rating BETWEEN 1 AND 5)
    )
    '''
)

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

REQUIRED_ENV_NAMES = {
    'DB_HOST',
    'DB_PORT',
    'DB_NAME',
    'DB_USER',
    'DB_PASSWORD',
}



def find_latest_processed_csv(
    directory: Path = PROCESSED_DIR,
    pattern: str = PROCESSED_CSV_PATTERN,
):
    """
    파일명 패턴과 일치하는 최신 전처리 csv 경로를 반환한다.

    Args:
        directory:
            전처리 csv 파일이 저장된 폴더

        pattern:
            검색할 파일명 패턴

    Returns:
        파일명 기준으로 가장 마지막에 있는 csv 경로

    Raises:
        FileNotFoundError:
            폴더가 없거나 패턴에 맞는 csv가 없는 경우    
    """

    if not directory.exists():
        raise FileNotFoundError(f'전처리 데이터 폴더가 없습니다. {directory}')

    processed_files = sorted(directory.glob(pattern))

    if not processed_files:
        raise FileNotFoundError(
            'MySQL에 저장할 전처리 csv 파일이 없습니다. '
            '먼저 전처리 단계를 실행하세요'
        )

    return processed_files[-1]   


def load_processed_csv(
    file_path: Path,
) -> pd.DataFrame:
    """
    최신 전처리 csv를 DataFrame으로 불러온다.

    Args:
        file_path:
            최신 전처리 csv 파일 경로

    Returns:
        전처리 데이터가 저장된 DataFrame

    Raises:
        FileNotFoundError:
            지정한 csv 파일이 존재하지 않는 경우    
    """
    if not file_path.is_file():
        raise FileNotFoundError(f'전처리 csv 파일이 없습니다. : {file_path}')

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
        parse_dates=[
            'parsed_at',
            'processed_at',
        ],
    )        


def load_database_config(env_file: Path = ENV_FILE) -> dict[str, str | int]:
    """
    .env 파일에서 MySQL 연결 정보를 읽고 검증한다.
    """
    if not env_file.is_file():
        raise FileNotFoundError(f'.env 파일이 없습니다. {env_file}')

    ## 환경 변수 읽어오기
    load_dotenv(dotenv_path=env_file)

    missing_names = REQUIRED_ENV_NAMES - set(os.environ)

    if missing_names:
        raise ValueError(f'필수 환경 변수가 없습니다. {missing_names}')

    try:
        port = int(os.environ['DB_PORT'])
    except ValueError as error:
        raise ValueError('DB_PORT는 정수여야 합니다.')

    return {
        'host': os.environ.get('DB_HOST'),
        'port': port,
        'database': os.environ.get('DB_NAME'),
        'username': os.environ.get('DB_USER'),
        'password': os.environ.get('DB_PASSWORD')
    }        


def create_mysql_engine(config: dict[str, str | int]) -> Engine:
    """
    MySQL 연결 설정으로 SQLAlchemy Engine을 생성한다.

    Args:
        config:
            load_database_config()가 반환한 연결 설정

    Returns:
        PyMySQL 드라이버를 사용하는 SQLAlchemy Engine

    Notes:
        URL.create()를 사용하므로 비밀번호에 특수문자가 있어도
        연결 URL을 안전하게 구성할 수 있다.
    """

    db_url = URL.create(
        drivername='mysql+pymysql',
        username=config.get('username'),
        password=config.get('password'),
        host=config.get('host'),
        port=config.get('port'),
        database=config.get('database'),
        query={'charset': 'utf8mb4'}       
    )

    return create_engine(db_url, pool_pre_ping=True, pool_recycle=1800)


def prepare_and_validate_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    DataFrame을 MySQL 저장용 자료형으로 정리하고 검증한다.

    Args:
        df:
            전처리가 완료된 도서 DataFrame

    Returns:
        DB 저장용 컬럼과 자료형으로 정리된 DataFrame

    Raises:
        ValueError:
            필수 컬럼이 없거나 결측값, 중복값,
            유효하지 않은 가격·평점·페이지가 있는 경우
    """

    missing_columns = set(DB_COLUMNS) - set(df.columns)

    if missing_columns:
        raise ValueError(
            'DB 저장에 필요한 컬럼이 누락되었습니다. '
            f'{sorted(missing_columns)}'
        )

    database_df = df[DB_COLUMNS].copy()

    for col in STRING_COLUMNS:
        database_df[col] = (
            database_df[col]
            .astype('string')
            .str
            .strip()
            .replace('', pd.NA)
        )

    database_df['price'] = pd.to_numeric(
        database_df['price'], errors='coerce',
    ).astype('Float64')

    database_df['rating'] = pd.to_numeric(
        database_df['rating'], errors='coerce',
    ).astype('Int64')

    database_df['source_page'] = pd.to_numeric(
        database_df['source_page'], errors='coerce',
    ).astype('Int64')

    database_df['parsed_at'] = pd.to_datetime(
        database_df['parsed_at'], errors='coerce',
    )

    database_df['processed_at'] = pd.to_datetime(
        database_df['processed_at'], errors='coerce',
    )

    database_df['is_available'] = (
        database_df['is_available']
        .astype('boolean')
    )

    errors = []
    null_counts = database_df[NOT_NULL_COLUMNS].isna().sum()
    invalid_nulls = null_counts[null_counts > 0]

    if not invalid_nulls.empty:
        errors.append(f'필수 컬럼 결측 발생:\n{invalid_nulls.to_string()}')

    if database_df['book_id'].duplicated().any():
        errors.append('중복된 book_id가 존재합니다.')

    if database_df['detail_url'].duplicated().any():
        errors.append('중복된 detail_url이 존재합니다.')

    if (database_df['price'] <= 0).any():
        errors.append('유효하지 않은 가격(<=0)이 존재합니다.')

    if (~database_df.rating.between(1, 5)).any():
        errors.append('유효하지 않은 평점(1~5 범위 벗어남)이 존재합니다.')

    if errors:
        raise ValueError('DB 저장 전 데이터 검증 실패: \n' + '\n\n'.join(errors))

    return database_df  


def create_books_table(engine: Engine) -> None:
    """
    books 테이블이 없으면 생성한다.
    """

    with engine.begin() as conn:
        conn.execute(CREATE_BOOKS_TABLE_SQL)


def upsert_books(engine: Engine, records: list[dict[str, Any]]) -> int:
    """
    도서 레코드를 books 테이블에 UPSERT한다.

    새로운 book_id는 INSERT하고,
    기존 book_id는 해당 행의 데이터를 UPDATE한다.

    Returns:
        작업한 로우 수
    """

    if not records:
        return 0

    with engine.begin() as conn:
        result = conn.execute(UPSERT_BOOK_SQL, records)

    return int(result.rowcount)


def test_mysql_connection(
    engine: Engine,
) -> dict[str, str]:
    """
    MySQL 연결 상태와 서버 정보를 확인한다.

    Args:
        engine:
            연결을 확인할 SQLAlchemy Engine

    Returns:
        MySQL 버전, 데이터베이스명, 현재 사용자 정보
    """

    query = text(
        '''
        SELECT 
            VERSION() AS ver,
            DATABASE() AS db,
            CURRENT_USER() AS user;
        '''
    )

    with engine.connect() as connection:
        connection_info = (
            connection.execute(query)
            .mappings()
            .one()
        )

    return {
        'mysql_version': str(connection_info['ver']),
        'database_name': str(connection_info['db']),
        'current_user': str(connection_info['user']),
    }


def run_load(
    processed_csv_file: Path | None = None,
    engine: Engine | None = None,
) -> dict[str, int | str]:
    """
    전처리 csv 선택부터 MySQL 저장까지 순서대로 실행한다.

    Args:
        processed_csv_file:
            MySQL에 저장할 전처리 CSV 경로
            전달하지 않으면 data/processed의 최신 파일을 사용한다.

    engine:
        외부에서 생성한 SQLAlchemy Engine
        전달하지 않으면 .env 설정으로 새 Engine을 생성한다.

    Returns:
        입력 파일명, 데이터베이스명, 입력 행 수,
        DB 영향 행 수가 포함된 요약 정보
    """

    owns_engine = engine is None

    if processed_csv_file is None:
        processed_csv_file = find_latest_processed_csv()

    processed_df = load_processed_csv(processed_csv_file)
    database_df = prepare_and_validate_dataframe(processed_df)

    ## pd.NA 및 Pandas dtype을 Python 기본 타입/None으로 치환
    records = (
        database_df
        .astype(object)
        .where(pd.notna(database_df), None)
        .to_dict(orient='records')
    )

    if engine is None:
        database_config = load_database_config()
        engine = create_mysql_engine(database_config)

    try:
        connection_info = test_mysql_connection(engine)  
        create_books_table(engine)
        affected_row_count = upsert_books(engine, records)
        print('=' * 70)
        print('전처리 도서 데이터 MySQL 저장 결과')
        print('=' * 70)
        print(f'입력 CSV : {processed_csv_file.name}')
        print(f'연결 데이터베이스 : {connection_info["database_name"]}')
        print(f'입력 데이터 수 : {len(records)}')
        print(f'DB 드라이버 영향 행 수 : {affected_row_count}')

        return {
            'input_file': processed_csv_file.name,
            'database_name': connection_info['database_name'],
            'input_count': len(records),
            'affected_row_count': affected_row_count
        }
    finally:
        if owns_engine and engine is not None:
            engine.dispose()


if __name__ == '__main__':
    try:
        run_load()
    except SQLAlchemyError as error:
        print('MySQL 처리 중 오류가 발생했습니다.')
        print(f'오류 내용 : {error}')

    except (
        FileNotFoundError,
        OSError,
        ValueError,
    ) as error:
        print('파일 처리 또는 데이터 검증에 실패했습니다.')
        print(f'오류 내용 : {error}')

