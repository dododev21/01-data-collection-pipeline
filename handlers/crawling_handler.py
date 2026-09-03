"""
정적 웹페이지 수집 작업을 실행하는 AWS Lambda Handler입니다.

Lambda event에서 수집 페이지 범위를 전달받아
기존 run_crawling()을 실행하고,
생성된 Raw HTML 파일을 Amazon S3에 저장합니다.
"""

import os

from src.data_collection_pipeline.config import END_PAGE, START_PAGE
from src.data_collection_pipeline.crawling import run_crawling
from src.data_collection_pipeline.s3_storage import upload_raw_html_batch


def lambda_handler(event: dict | None, context: object) -> dict[str, object]:
    """
    정적 웹페이지 Crawling Lambda의 실행 진입점입니다.
    """

    if event is None:
        event = {}

    start_page = int(event.get('start_page', START_PAGE))
    end_page = int(event.get('end_page', END_PAGE))

    ## -------------------------------------------------------
    ## 1. Raw HTML Crawling
    ## -------------------------------------------------------

    raw_batch_dir = run_crawling(
        start_page=start_page,
        end_page=end_page,
    )

    batch_id = raw_batch_dir.name

    ## -------------------------------------------------------
    ## 2. S3 Bucket 설정
    ## -------------------------------------------------------

    bucket_name = os.getenv('DATA_BUCKET_NAME')

    if not bucket_name:
        raise RuntimeError(
            'DATA_BUCKET_NAME 환경변수가 설정되지 않았습니다.'
        )

    ## -------------------------------------------------------
    ## 3. Raw HTML S3 업로드
    ## -------------------------------------------------------

    object_keys = upload_raw_html_batch(
        raw_batch_dir=raw_batch_dir,
        bucket_name=bucket_name,
    )

    raw_prefix = f'raw/{batch_id}/'

    ## -------------------------------------------------------
    ## 4. Lambda 실행 정보
    ## -------------------------------------------------------

    request_id = getattr(context, 'aws_request_id', None)

    return {
        'stage': 'crawling',
        'status': 'SUCCEEDED',
        'batch_id': batch_id,
        'start_page': start_page,
        'end_page': end_page,
        'bucket': bucket_name,
        'raw_prefix': raw_prefix,
        'object_count': len(object_keys),
        'request_id': request_id,
    }