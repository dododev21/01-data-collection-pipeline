## 단위 테스트 프레임워크인 pytest 로드
## AWS S3 API 호출을 가짜(Mock) 객체로 격리하기 위한 Mock 모듈 로드
from unittest.mock import Mock

import pytest

## S3 스토리지 연동 함수들 로드 (Raw HTML 업로드, Interim CSV 다운로드, Processed CSV 업로드 및 다운로드)
from src.data_collection_pipeline.s3_storage import (
    download_interim_batch,
    download_processed_file,
    upload_processed_file,
    upload_raw_html_batch,
)


def test_upload_raw_html_batch(tmp_path):
    """
    로컬 배치 디렉터리의 Raw HTML 파일들이 S3 Raw 경로(raw/{batch_id}/)로
    누락 없이 정확하게 업로드되는지 검증합니다.
    """
    ## 1. 테스트용 Raw HTML 임시 배치 디렉터리 생성 (pytest tmp_path fixture 활용)
    batch_dir = tmp_path / '20260830_153000'
    batch_dir.mkdir()

    ## 2. 테스트용 HTML 파일 2개 생성 및 더미 데이터 작성
    first_file = batch_dir / 'books_page_001.html'
    second_file = batch_dir / 'books_page_002.html'

    first_file.write_text(
        '<html>page 1</html>',
        encoding='utf-8',
    )

    second_file.write_text(
        '<html>page 2</html>',
        encoding='utf-8',
    )

    ## 3. 실제 AWS 네트워크 통신을 차단하기 위한 Mock S3 Client 생성
    mock_s3_client = Mock()

    ## 4. Raw HTML 배치 업로드 함수 실행
    object_keys = upload_raw_html_batch(
        raw_batch_dir=batch_dir,
        bucket_name='test-books-bucket',
        s3_client=mock_s3_client,
    )

    ## 5. 반환된 S3 Object Key 목록의 경로와 파일명이 표준 규격에 맞는지 검증
    assert object_keys == [
        'raw/20260830_153000/books_page_001.html',
        'raw/20260830_153000/books_page_002.html',
    ]

    ## 6. HTML 파일 2개에 대해 S3 upload_file API가 정확히 2회 호출되었는지 검증
    assert mock_s3_client.upload_file.call_count == 2


def test_download_interim_batch(tmp_path):
    """
    S3 Interim 영역의 CSV 파일 목록을 조회하고, 각 파일을 로컬 대상 디렉터리로
    올바른 경로와 파일명으로 다운로드하는지 검증합니다.
    """
    ## 1. 테스트용 배치 메타데이터 정의
    batch_id = '20260901_035140'
    bucket_name = 'test-books-bucket'
    interim_prefix = f'interim/{batch_id}/'

    ## 2. 실제 AWS S3 대신 사용할 Mock Client 생성
    mock_s3_client = Mock()

    ## 3. S3 list_objects_v2() API 응답 데이터(CSV 파일 3개 목록) 모의 설정
    mock_s3_client.list_objects_v2.return_value = {
        'Contents': [
            {
                'Key': (
                    f'{interim_prefix}'
                    'books_page_001_parsed.csv'
                )
            },
            {
                'Key': (
                    f'{interim_prefix}'
                    'books_page_002_parsed.csv'
                )
            },
            {
                'Key': (
                    f'{interim_prefix}'
                    'books_page_003_parsed.csv'
                )
            },
        ]
    }

    ## 4. S3 Interim CSV 일괄 다운로드 함수 실행
    interim_batch_dir = download_interim_batch(
        bucket_name=bucket_name,
        batch_id=batch_id,
        interim_prefix=interim_prefix,
        destination_dir=tmp_path,
        s3_client=mock_s3_client,
    )

    ## 5. 생성 및 반환된 로컬 목적지 디렉터리 경로 검증
    assert interim_batch_dir == tmp_path / batch_id

    ## 6. S3 목록 조회가 지정된 버킷명과 Prefix로 정확히 1회 호출되었는지 검증
    mock_s3_client.list_objects_v2.assert_called_once_with(
        Bucket=bucket_name,
        Prefix=interim_prefix,
    )

    ## 7. 조회된 3개의 CSV 파일이 각각 개별 다운로드되었는지 총 호출 횟수(3회) 검증
    assert mock_s3_client.download_file.call_count == 3

    ## 8. 첫 번째 CSV 파일의 다운로드 인자(버킷명, S3 Key, 로컬 저장 경로) 일치 검증
    mock_s3_client.download_file.assert_any_call(
        bucket_name,
        (
            f'{interim_prefix}'
            'books_page_001_parsed.csv'
        ),
        str(
            tmp_path
            / batch_id
            / 'books_page_001_parsed.csv'
        ),
    )

    ## 9. 두 번째 CSV 파일의 다운로드 인자 일치 검증
    mock_s3_client.download_file.assert_any_call(
        bucket_name,
        (
            f'{interim_prefix}'
            'books_page_002_parsed.csv'
        ),
        str(
            tmp_path
            / batch_id
            / 'books_page_002_parsed.csv'
        ),
    )

    ## 10. 세 번째 CSV 파일의 다운로드 인자 일치 검증
    mock_s3_client.download_file.assert_any_call(
        bucket_name,
        (
            f'{interim_prefix}'
            'books_page_003_parsed.csv'
        ),
        str(
            tmp_path
            / batch_id
            / 'books_page_003_parsed.csv'
        ),
    )


def test_upload_processed_file(tmp_path):
    """
    최종 정제된 Processed CSV 파일이 S3 Processed 경로(processed/{batch_id}/)로
    단 1회 정확하게 업로드되는지 검증합니다.
    """
    ## 1. 테스트용 배치 메타데이터 정의
    batch_id = '20260901_035140'
    bucket_name = 'test-books-bucket'

    ## 2. 테스트용 전처리 완료 CSV 임시 파일 생성
    processed_file = (
        tmp_path
        / (
            'books_pages_001_003_processed_'
            f'{batch_id}.csv'
        )
    )

    processed_file.write_text(
        'book_id,title\n1,Test Book\n',
        encoding='utf-8',
    )

    ## 3. Mock S3 Client 생성
    mock_s3_client = Mock()

    ## 4. Processed CSV 단일 업로드 함수 실행
    object_key = upload_processed_file(
        processed_file=processed_file,
        bucket_name=bucket_name,
        batch_id=batch_id,
        s3_client=mock_s3_client,
    )

    expected_object_key = (
        f'processed/{batch_id}/'
        f'books_pages_001_003_processed_{batch_id}.csv'
    )

    ## 5. 반환된 S3 Object Key가 기대하는 S3 경로 규격과 일치하는지 검증
    assert object_key == expected_object_key

    ## 6. 올바른 로컬 파일 경로, 버킷명, 대상 S3 Key로 1회 업로드 호출되었는지 검증
    mock_s3_client.upload_file.assert_called_once_with(
        str(processed_file),
        bucket_name,
        expected_object_key,
    )


def test_download_processed_file(tmp_path):
    """
    Load 단계를 위해 S3 Processed 영역의 단일 정제 CSV 파일을 로컬 디렉터리로
    올바르게 다운로드하는지 검증합니다.
    """
    ## 1. 테스트용 S3 메타데이터 정의
    bucket_name = 'test-books-bucket'
    batch_id = '20260901_035140'

    processed_key = (
        f'processed/{batch_id}/'
        f'books_pages_001_003_processed_{batch_id}.csv'
    )

    ## 2. Mock S3 Client 생성
    mock_s3_client = Mock()

    ## 3. Processed CSV 다운로드 함수 실행
    downloaded_file = download_processed_file(
        bucket_name=bucket_name,
        processed_key=processed_key,
        destination_dir=tmp_path,
        s3_client=mock_s3_client,
    )

    expected_file = (
        tmp_path
        / f'books_pages_001_003_processed_{batch_id}.csv'
    )

    ## 4. 반환된 로컬 파일 경로가 목적지 경로와 파일명에 정확히 일치하는지 검증
    assert downloaded_file == expected_file

    ## 5. 올바른 버킷, Key, 로컬 저장 목적지 문자열로 S3 download_file API가 1회 호출되었는지 검증
    mock_s3_client.download_file.assert_called_once_with(
        bucket_name,
        processed_key,
        str(expected_file),
    )


def test_download_processed_file_requires_processed_key(
    tmp_path,
):
    """
    processed_key 파라미터가 비어 있거나 누락된 경우
    명시적인 ValueError 예외가 발생하는지 방어 로직을 검증합니다.
    """
    ## 1. Mock S3 Client 생성
    mock_s3_client = Mock()

    ## 2. 빈 processed_key 전달 시 적절한 에러 메시지와 함께 ValueError가 발생하는지 검증
    with pytest.raises(
        ValueError,
        match=r'processed_key가 지정되지 않았습니다\.',
    ):
        download_processed_file(
            bucket_name='test-books-bucket',
            processed_key='',
            destination_dir=tmp_path,
            s3_client=mock_s3_client,
        )