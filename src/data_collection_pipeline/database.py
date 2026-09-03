"""
MySQL 연결 설정과 SQLAlchemy Engine 생성을 담당하는 모듈입니다.

로컬 환경에서는 .env 파일에서 데이터베이스 접속 정보를 읽습니다.
AWS Lambda 환경에서는 AWS Secrets Manager와 환경변수를 이용하여
Amazon RDS MySQL 접속 정보를 구성합니다.
"""

## JSON 문자열 파싱을 위한 표준 모듈
import json

## OS 환경변수 접근을 위한 표준 모듈
import os

## 파일 경로 처리를 위한 모듈
from pathlib import Path

## 타입 힌팅
from typing import Any

## .env 파일 로드
from dotenv import load_dotenv

## SQLAlchemy 엔진 생성 및 SQL 실행
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine

## 프로젝트 공통 .env 경로
from .config import ENV_FILE

## ===========================================================
## 1. 데이터베이스 환경변수 설정
## ===========================================================

## 로컬 환경에서 반드시 필요한 데이터베이스 환경변수
REQUIRED_LOCAL_ENV_NAMES = {
    'DB_HOST',
    'DB_PORT',
    'DB_NAME',
    'DB_USER',
    'DB_PASSWORD',
}


## ===========================================================
## 2. 공통 유틸리티
## ===========================================================

def _parse_port(port_value: str | int, source_name: str) -> int:
    """
    데이터베이스 포트 값을 정수로 변환하고 유효성을 검증합니다.

    Args:
        port_value:
            문자열 또는 정수 형태의 포트 값

        source_name:
            오류 메시지에 표시할 포트 값 출처

    Returns:
        정수형 포트 번호
    """

    ## 포트 번호를 정수로 변환
    try:
        port = int(port_value)
    except (TypeError, ValueError) as error:
        raise ValueError(f'{source_name}는 정수여야 합니다.') from error

    ## TCP 포트 범위 검증
    if not 1 <= port <= 65535:
        raise ValueError(f'{source_name}는 1~65535 범위여야 합니다.')

    return port


## ===========================================================
## 3. AWS Secrets Manager 설정
## ===========================================================

def _load_secret_value(
    secret_arn: str,
    secrets_client: Any | None = None,
) -> dict[str, Any]:
    """
    AWS Secrets Manager에서 Secret 값을 조회하고 JSON으로 변환합니다.

    Args:
        secret_arn:
            조회할 Secrets Manager Secret ARN

        secrets_client:
            테스트에서 사용할 Secrets Manager Mock Client

    Returns:
        SecretString을 파싱한 딕셔너리
    """

    ## Secret ARN 필수값 검증
    if not secret_arn:
        raise ValueError('DB_SECRET_ARN이 지정되지 않았습니다.')

    ## 실제 AWS 실행 시 boto3 Client 생성
    ## 테스트에서는 Mock Client를 전달할 수 있음
    if secrets_client is None:
        import boto3

        secrets_client = boto3.client('secretsmanager')

    ## Secrets Manager Secret 조회
    response = secrets_client.get_secret_value(SecretId=secret_arn)

    ## SecretString 추출
    secret_string = response.get('SecretString')

    ## SecretString 누락 검증
    if not secret_string:
        raise ValueError('Secrets Manager의 SecretString이 없습니다.')

    ## Secret JSON 문자열 파싱
    try:
        secret = json.loads(secret_string)
    except json.JSONDecodeError as error:
        raise ValueError(
            'Secrets Manager의 SecretString이 올바른 JSON 형식이 아닙니다.'
        ) from error

    ## Secret 데이터 타입 검증
    if not isinstance(secret, dict):
        raise ValueError('Secrets Manager의 Secret 값은 JSON 객체여야 합니다.')

    return secret


def load_database_config_from_secret(
    secret_arn: str,
    secrets_client: Any | None = None,
) -> dict[str, str | int]:
    """
    AWS Secrets Manager와 Lambda 환경변수를 이용하여
    Amazon RDS MySQL 연결 정보를 구성합니다.

    Secret에 값이 존재하면 Secret 값을 우선 사용하고,
    없는 값은 Lambda 환경변수에서 조회합니다.

    Args:
        secret_arn:
            RDS가 관리하는 Secrets Manager Secret ARN

        secrets_client:
            테스트에서 사용할 Secrets Manager Mock Client

    Returns:
        MySQL 연결 설정 딕셔너리
    """

    ## -------------------------------------------------------
    ## 1. Secrets Manager 값 조회
    ## -------------------------------------------------------

    secret = _load_secret_value(secret_arn=secret_arn, secrets_client=secrets_client)

    ## -------------------------------------------------------
    ## 2. 사용자 이름과 비밀번호 조회
    ## -------------------------------------------------------

    ## RDS 관리형 Secret의 사용자 이름과 비밀번호 조회
    username = secret.get('username')
    password = secret.get('password')

    ## 사용자 이름 필수값 검증
    if not username:
        raise ValueError('Secrets Manager에 username이 없습니다.')

    ## 비밀번호 필수값 검증
    if not password:
        raise ValueError('Secrets Manager에 password가 없습니다.')

    ## -------------------------------------------------------
    ## 3. RDS Host 조회
    ## -------------------------------------------------------

    ## Secret의 host를 우선 사용하고 없으면 DB_HOST 환경변수 사용
    host = secret.get('host') or os.environ.get('DB_HOST')

    if not host:
        raise ValueError('DB_HOST가 지정되지 않았습니다.')

    ## -------------------------------------------------------
    ## 4. Database 이름 조회
    ## -------------------------------------------------------

    ## Secret의 dbname을 우선 사용하고 없으면 DB_NAME 환경변수 사용
    database_name = secret.get('dbname') or os.environ.get('DB_NAME')

    if not database_name:
        raise ValueError('DB_NAME이 지정되지 않았습니다.')

    ## -------------------------------------------------------
    ## 5. Port 조회
    ## -------------------------------------------------------

    ## Secret의 port를 우선 사용하고 없으면 DB_PORT 환경변수 사용
    ## 두 값이 모두 없으면 MySQL 기본 포트 3306 사용
    port_value = secret.get('port') or os.environ.get('DB_PORT') or '3306'
    port = _parse_port(port_value=port_value, source_name='DB_PORT')

    ## -------------------------------------------------------
    ## 6. AWS RDS 연결 설정 반환
    ## -------------------------------------------------------

    return {
        'host': str(host),
        'port': port,
        'database': str(database_name),
        'username': str(username),
        'password': str(password),
    }


## ===========================================================
## 4. 데이터베이스 연결 설정
## ===========================================================

def load_database_config(
    env_file: Path = ENV_FILE,
    secrets_client: Any | None = None,
) -> dict[str, str | int]:
    """
    실행 환경에 따라 MySQL 연결 정보를 읽고 검증합니다.

    AWS Lambda:
        DB_SECRET_ARN 환경변수가 존재하면
        AWS Secrets Manager를 사용합니다.

    Local:
        DB_SECRET_ARN이 없으면
        .env 파일을 사용합니다.

    Args:
        env_file:
            로컬 실행 시 사용할 .env 파일 경로

        secrets_client:
            테스트에서 사용할 Secrets Manager Mock Client

    Returns:
        MySQL 연결 설정 딕셔너리
    """

    ## -------------------------------------------------------
    ## 1. AWS Lambda 환경 확인
    ## -------------------------------------------------------

    ## DB_SECRET_ARN 환경변수 확인
    secret_arn = os.environ.get('DB_SECRET_ARN')

    ## Secret ARN이 존재하면 AWS Secrets Manager 사용
    if secret_arn:
        return load_database_config_from_secret(
            secret_arn=secret_arn,
            secrets_client=secrets_client,
        )

    ## -------------------------------------------------------
    ## 2. 로컬 .env 파일 검증
    ## -------------------------------------------------------

    ## 로컬 실행에서는 .env 파일이 반드시 존재해야 함
    if not env_file.is_file():
        raise FileNotFoundError(f'.env 파일이 없습니다. {env_file}')

    ## -------------------------------------------------------
    ## 3. .env 환경변수 로드
    ## -------------------------------------------------------

    ## .env 파일의 키-값을 OS 환경변수로 로드
    load_dotenv(dotenv_path=env_file)

    ## -------------------------------------------------------
    ## 4. 필수 환경변수 검증
    ## -------------------------------------------------------

    ## 누락된 데이터베이스 환경변수 탐색
    missing_names = [
        name
        for name in REQUIRED_LOCAL_ENV_NAMES
        if not os.environ.get(name)
    ]

    ## 필수 환경변수가 누락되면 예외 발생
    if missing_names:
        raise ValueError(f'필수 환경 변수가 없습니다. {sorted(missing_names)}')

    ## -------------------------------------------------------
    ## 5. Port 검증
    ## -------------------------------------------------------

    port = _parse_port(
        port_value=os.environ['DB_PORT'],
        source_name='DB_PORT',
    )

    ## -------------------------------------------------------
    ## 6. 로컬 MySQL 연결 설정 반환
    ## -------------------------------------------------------

    return {
        'host': os.environ['DB_HOST'],
        'port': port,
        'database': os.environ['DB_NAME'],
        'username': os.environ['DB_USER'],
        'password': os.environ['DB_PASSWORD'],
    }


## ===========================================================
## 5. SQLAlchemy Engine 생성
## ===========================================================

def create_mysql_engine(config: dict[str, str | int]) -> Engine:
    """
    MySQL 연결 설정으로 SQLAlchemy Engine을 생성합니다.

    Args:
        config:
            load_database_config()가 반환한
            데이터베이스 연결 설정

    Returns:
        PyMySQL 드라이버를 사용하는 SQLAlchemy Engine
    """

    ## -------------------------------------------------------
    ## 1. SQLAlchemy 연결 URL 생성
    ## -------------------------------------------------------

    ## URL.create()를 사용하여 비밀번호의 특수문자를 안전하게 처리
    db_url = URL.create(
        drivername='mysql+pymysql',
        username=str(config['username']),
        password=str(config['password']),
        host=str(config['host']),
        port=int(config['port']),
        database=str(config['database']),
        query={'charset': 'utf8mb4'},
    )

    ## -------------------------------------------------------
    ## 2. SQLAlchemy Engine 생성
    ## -------------------------------------------------------

    ## pool_pre_ping
    ## 쿼리 실행 전 DB 연결 상태를 확인하여 끊어진 연결을 재생성
    ##
    ## pool_recycle
    ## MySQL wait_timeout 문제를 줄이기 위해 1800초마다 연결 재생성
    return create_engine(
        db_url,
        pool_pre_ping=True,
        pool_recycle=1800,
    )


## ===========================================================
## 6. MySQL 연결 테스트
## ===========================================================

def test_mysql_connection(engine: Engine) -> dict[str, str]:
    """
    MySQL 연결 상태와 서버 정보를 확인합니다.

    Args:
        engine:
            연결을 확인할 SQLAlchemy Engine

    Returns:
        MySQL 버전, 데이터베이스명, 현재 사용자 정보
    """

    ## -------------------------------------------------------
    ## 1. 연결 확인 SQL 정의
    ## -------------------------------------------------------

    query = text(
        """
        SELECT
            VERSION() AS ver,
            DATABASE() AS db,
            CURRENT_USER() AS user
        """
    )

    ## -------------------------------------------------------
    ## 2. MySQL 연결 및 SQL 실행
    ## -------------------------------------------------------

    with engine.connect() as connection:
        connection_info = connection.execute(query).mappings().one()

    ## -------------------------------------------------------
    ## 3. 연결 정보 반환
    ## -------------------------------------------------------

    return {
        'mysql_version': str(connection_info['ver']),
        'database_name': str(connection_info['db']),
        'current_user': str(connection_info['user']),
    }