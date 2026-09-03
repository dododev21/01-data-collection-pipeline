"""
database.py의 로컬 .env 및 AWS Secrets Manager 기반
MySQL 연결 설정 로직을 검증하는 단위 테스트입니다.
"""

## JSON 문자열 생성을 위한 표준 모듈
import json

## Mock 객체 생성을 위한 표준 테스트 도구
from unittest.mock import Mock

## 예외 발생 검증을 위한 pytest
import pytest

## 테스트 대상 데이터베이스 설정 함수
from src.data_collection_pipeline.database import (
    load_database_config,
    load_database_config_from_secret,
)

## ===========================================================
## 1. 테스트 공통 함수
## ===========================================================

def _clear_database_env(monkeypatch) -> None:
    """
    테스트 간 환경변수 간섭을 방지하기 위해
    데이터베이스 관련 환경변수를 제거합니다.
    """

    ## 테스트에 영향을 줄 수 있는 DB 관련 환경변수 제거
    env_names = [
        'DB_SECRET_ARN',
        'DB_HOST',
        'DB_PORT',
        'DB_NAME',
        'DB_USER',
        'DB_PASSWORD',
    ]

    for name in env_names:
        monkeypatch.delenv(name, raising=False)


## ===========================================================
## 2. AWS Secrets Manager 테스트
## ===========================================================

def test_load_database_config_from_secret(monkeypatch):
    """
    RDS 관리형 Secret에서 username/password를 읽고
    나머지 연결정보는 Lambda 환경변수에서 읽는지 확인합니다.
    """

    ## 테스트 간 환경변수 간섭 제거
    _clear_database_env(monkeypatch)

    ## AWS Lambda 환경변수 설정
    monkeypatch.setenv('DB_SECRET_ARN', 'arn:aws:secretsmanager:test')
    monkeypatch.setenv('DB_HOST', 'books-db.example.amazonaws.com')
    monkeypatch.setenv('DB_PORT', '3306')
    monkeypatch.setenv('DB_NAME', 'booksdb')

    ## 실제 AWS Secrets Manager 대신 Mock Client 사용
    mock_secrets_client = Mock()

    ## RDS 관리형 Secret을 가정한 테스트 데이터 설정
    mock_secrets_client.get_secret_value.return_value = {
        'SecretString': json.dumps({
            'username': 'booksadmin',
            'password': 'test-password',
        })
    }

    ## 데이터베이스 설정 조회
    config = load_database_config(secrets_client=mock_secrets_client)

    ## 최종 데이터베이스 연결 설정 검증
    assert config == {
        'host': 'books-db.example.amazonaws.com',
        'port': 3306,
        'database': 'booksdb',
        'username': 'booksadmin',
        'password': 'test-password',
    }

    ## 올바른 Secret ARN으로 Secrets Manager가 호출되었는지 검증
    mock_secrets_client.get_secret_value.assert_called_once_with(
        SecretId='arn:aws:secretsmanager:test'
    )


def test_load_database_config_prefers_secret_values(monkeypatch):
    """
    Secret에 host, port, dbname이 존재하면
    Lambda 환경변수보다 Secret 값을 우선 사용하는지 확인합니다.
    """

    ## 테스트 간 환경변수 간섭 제거
    _clear_database_env(monkeypatch)

    ## Secret 값과 다른 Lambda 환경변수 설정
    monkeypatch.setenv('DB_HOST', 'env-db.example.amazonaws.com')
    monkeypatch.setenv('DB_PORT', '3307')
    monkeypatch.setenv('DB_NAME', 'env_booksdb')

    ## 실제 AWS Secrets Manager 대신 Mock Client 사용
    mock_secrets_client = Mock()

    ## 모든 RDS 연결정보가 포함된 Secret 설정
    mock_secrets_client.get_secret_value.return_value = {
        'SecretString': json.dumps({
            'host': 'secret-db.example.amazonaws.com',
            'port': 3306,
            'dbname': 'booksdb',
            'username': 'booksadmin',
            'password': 'test-password',
        })
    }

    ## Secrets Manager 기반 데이터베이스 설정 조회
    config = load_database_config_from_secret(
        secret_arn='arn:aws:secretsmanager:test',
        secrets_client=mock_secrets_client,
    )

    ## Secret의 연결정보가 우선 사용되는지 검증
    assert config == {
        'host': 'secret-db.example.amazonaws.com',
        'port': 3306,
        'database': 'booksdb',
        'username': 'booksadmin',
        'password': 'test-password',
    }


def test_load_database_config_secret_requires_username(monkeypatch):
    """
    Secret에 username이 없으면 ValueError가 발생하는지 확인합니다.
    """

    ## 테스트 간 환경변수 간섭 제거
    _clear_database_env(monkeypatch)

    ## Secret에 없는 연결정보를 환경변수로 제공
    monkeypatch.setenv('DB_HOST', 'books-db.example.amazonaws.com')
    monkeypatch.setenv('DB_NAME', 'booksdb')

    ## 실제 AWS Secrets Manager 대신 Mock Client 사용
    mock_secrets_client = Mock()

    ## username이 누락된 Secret 설정
    mock_secrets_client.get_secret_value.return_value = {
        'SecretString': json.dumps({
            'password': 'test-password',
        })
    }

    ## username 누락 예외 검증
    with pytest.raises(ValueError, match=r'Secrets Manager에 username이 없습니다\.'):
        load_database_config_from_secret(
            secret_arn='arn:aws:secretsmanager:test',
            secrets_client=mock_secrets_client,
        )


def test_load_database_config_secret_requires_password(monkeypatch):
    """
    Secret에 password가 없으면 ValueError가 발생하는지 확인합니다.
    """

    ## 테스트 간 환경변수 간섭 제거
    _clear_database_env(monkeypatch)

    ## Secret에 없는 연결정보를 환경변수로 제공
    monkeypatch.setenv('DB_HOST', 'books-db.example.amazonaws.com')
    monkeypatch.setenv('DB_NAME', 'booksdb')

    ## 실제 AWS Secrets Manager 대신 Mock Client 사용
    mock_secrets_client = Mock()

    ## password가 누락된 Secret 설정
    mock_secrets_client.get_secret_value.return_value = {
        'SecretString': json.dumps({
            'username': 'booksadmin',
        })
    }

    ## password 누락 예외 검증
    with pytest.raises(ValueError, match=r'Secrets Manager에 password가 없습니다\.'):
        load_database_config_from_secret(
            secret_arn='arn:aws:secretsmanager:test',
            secrets_client=mock_secrets_client,
        )


def test_load_database_config_secret_invalid_json(monkeypatch):
    """
    SecretString이 올바른 JSON 형식이 아니면
    ValueError가 발생하는지 확인합니다.
    """

    ## 테스트 간 환경변수 간섭 제거
    _clear_database_env(monkeypatch)

    ## 실제 AWS Secrets Manager 대신 Mock Client 사용
    mock_secrets_client = Mock()

    ## 잘못된 JSON 문자열 설정
    mock_secrets_client.get_secret_value.return_value = {
        'SecretString': 'invalid-json'
    }

    ## JSON 파싱 예외 검증
    with pytest.raises(ValueError, match=r'올바른 JSON 형식이 아닙니다\.'):
        load_database_config_from_secret(
            secret_arn='arn:aws:secretsmanager:test',
            secrets_client=mock_secrets_client,
        )


## ===========================================================
## 3. 로컬 .env 테스트
## ===========================================================

def test_load_database_config_from_env(monkeypatch, tmp_path):
    """
    DB_SECRET_ARN이 없는 로컬 환경에서는
    .env 파일에서 MySQL 연결정보를 읽는지 확인합니다.
    """

    ## 테스트 간 환경변수 간섭 제거
    _clear_database_env(monkeypatch)

    ## 테스트용 .env 파일 생성
    env_file = tmp_path / '.env'

    env_file.write_text(
        '\n'.join([
            'DB_HOST=localhost',
            'DB_PORT=3306',
            'DB_NAME=booksdb',
            'DB_USER=root',
            'DB_PASSWORD=local-password',
        ]),
        encoding='utf-8',
    )

    ## 로컬 .env 기반 데이터베이스 설정 조회
    config = load_database_config(env_file=env_file)

    ## .env 파일의 연결정보가 정확히 변환되었는지 검증
    assert config == {
        'host': 'localhost',
        'port': 3306,
        'database': 'booksdb',
        'username': 'root',
        'password': 'local-password',
    }


def test_load_database_config_requires_env_file(monkeypatch, tmp_path):
    """
    로컬 실행에서 .env 파일이 없으면
    FileNotFoundError가 발생하는지 확인합니다.
    """

    ## 테스트 간 환경변수 간섭 제거
    _clear_database_env(monkeypatch)

    ## 존재하지 않는 .env 파일 경로 설정
    env_file = tmp_path / '.env'

    ## .env 파일 누락 예외 검증
    with pytest.raises(FileNotFoundError, match=r'.env 파일이 없습니다\.'):
        load_database_config(env_file=env_file)


def test_load_database_config_requires_all_env_values(monkeypatch, tmp_path):
    """
    로컬 .env 파일에 필수 DB 환경변수가 누락되면
    ValueError가 발생하는지 확인합니다.
    """

    ## 테스트 간 환경변수 간섭 제거
    _clear_database_env(monkeypatch)

    ## DB_PASSWORD가 누락된 테스트용 .env 파일 생성
    env_file = tmp_path / '.env'

    env_file.write_text(
        '\n'.join([
            'DB_HOST=localhost',
            'DB_PORT=3306',
            'DB_NAME=booksdb',
            'DB_USER=root',
        ]),
        encoding='utf-8',
    )

    ## 필수 환경변수 누락 예외 검증
    with pytest.raises(ValueError, match=r'필수 환경 변수가 없습니다\.'):
        load_database_config(env_file=env_file)


def test_load_database_config_requires_integer_port(monkeypatch, tmp_path):
    """
    DB_PORT가 정수가 아니면 ValueError가 발생하는지 확인합니다.
    """

    ## 테스트 간 환경변수 간섭 제거
    _clear_database_env(monkeypatch)

    ## 잘못된 포트를 가진 테스트용 .env 파일 생성
    env_file = tmp_path / '.env'

    env_file.write_text(
        '\n'.join([
            'DB_HOST=localhost',
            'DB_PORT=invalid',
            'DB_NAME=booksdb',
            'DB_USER=root',
            'DB_PASSWORD=local-password',
        ]),
        encoding='utf-8',
    )

    ## 잘못된 DB_PORT 예외 검증
    with pytest.raises(ValueError, match=r'DB_PORT는 정수여야 합니다\.'):
        load_database_config(env_file=env_file)


def test_load_database_config_requires_valid_port_range(monkeypatch, tmp_path):
    """
    DB_PORT가 TCP 포트 범위를 벗어나면
    ValueError가 발생하는지 확인합니다.
    """

    ## 테스트 간 환경변수 간섭 제거
    _clear_database_env(monkeypatch)

    ## TCP 포트 범위를 벗어난 테스트용 .env 파일 생성
    env_file = tmp_path / '.env'

    env_file.write_text(
        '\n'.join([
            'DB_HOST=localhost',
            'DB_PORT=70000',
            'DB_NAME=booksdb',
            'DB_USER=root',
            'DB_PASSWORD=local-password',
        ]),
        encoding='utf-8',
    )

    ## DB_PORT 범위 예외 검증
    with pytest.raises(ValueError, match=r'DB_PORT는 1~65535 범위여야 합니다\.'):
        load_database_config(env_file=env_file)