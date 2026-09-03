"""
S3 Raw 데이터를 읽어 도서 정보를 추출하는
AWS Lambda Handler입니다.
"""

from src.data_collection_pipeline.config import RAW_HTML_DIR
from src.data_collection_pipeline.extract import run_extract
from src.data_collection_pipeline.s3_storage import (
    download_raw_html_batch,
    upload_interim_files,
)


def lambda_handler(
    event: dict,
    context: object,
) -> dict[str, object]:
    """
    Extract Lambda 실행 진입점입니다.
    """

    ## -------------------------------------------------------
    ## 1. Event 입력값 확인
    ## -------------------------------------------------------

    batch_id = event.get('batch_id')
    bucket_name = event.get('bucket')
    raw_prefix = event.get('raw_prefix')

    if not batch_id:
        raise ValueError('batch_id가 없습니다.')

    if not bucket_name:
        raise ValueError('bucket 정보가 없습니다.')

    if not raw_prefix:
        raise ValueError('raw_prefix 정보가 없습니다.')

    ## -------------------------------------------------------
    ## 2. S3 Raw HTML 다운로드
    ## -------------------------------------------------------

    raw_batch_dir = download_raw_html_batch(
        bucket_name=bucket_name,
        batch_id=batch_id,
        raw_prefix=raw_prefix,
        destination_dir=RAW_HTML_DIR,
    )

    ## -------------------------------------------------------
    ## 3. HTML Parsing 및 데이터 추출
    ## -------------------------------------------------------

    parsed_csv_files = run_extract(
        raw_batch_dir
    )

    ## -------------------------------------------------------
    ## 4. Extract 결과 S3 업로드
    ## -------------------------------------------------------

    object_keys = upload_interim_files(
        csv_files=parsed_csv_files,
        bucket_name=bucket_name,
        batch_id=batch_id,
    )

    interim_prefix = f'interim/{batch_id}/'

    ## -------------------------------------------------------
    ## 5. 실행 결과 반환
    ## -------------------------------------------------------

    request_id = getattr(
        context,
        'aws_request_id',
        None,
    )

    return {
        'stage': 'extract',
        'status': 'SUCCEEDED',
        'batch_id': batch_id,
        'bucket': bucket_name,
        'raw_prefix': raw_prefix,
        'interim_prefix': interim_prefix,
        'object_count': len(object_keys),
        'request_id': request_id,
    }