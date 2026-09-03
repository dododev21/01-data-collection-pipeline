"""
S3 Interim 데이터를 전처리하여
S3 Processed 영역에 저장하는 AWS Lambda Handler입니다.
"""

## 환경 설정 모듈에서 임시 디렉터리 기본 경로 로드
from src.data_collection_pipeline.config import INTERIM_DIR

## CSV 데이터 정제 및 결합을 수행하는 전처리 비즈니스 로직 함수 로드
from src.data_collection_pipeline.preprocess import run_preprocess

## S3 버킷과의 입출력(다운로드 및 업로드)을 담당하는 스토리지 함수 로드
from src.data_collection_pipeline.s3_storage import (
    download_interim_batch,
    upload_processed_file,
)


def lambda_handler(
    event: dict,
    context: object,
) -> dict[str, object]:
    """
    Preprocess Lambda 실행 진입점입니다.
    """

    ## -------------------------------------------------------
    ## 1. Event 입력값 확인
    ## -------------------------------------------------------

    ## Step Functions 또는 상위 파이프라인에서 전달받은 필수 메타데이터 파싱
    batch_id = event.get('batch_id')
    bucket_name = event.get('bucket')
    interim_prefix = event.get('interim_prefix')

    ## 파이프라인 추적용 고유 배치 ID 누락 여부 검증
    if not batch_id:
        raise ValueError('batch_id가 없습니다.')

    ## 데이터를 읽고 쓸 대상 S3 버킷 이름 누락 여부 검증
    if not bucket_name:
        raise ValueError('bucket 정보가 없습니다.')

    ## 중간 정제 데이터(CSV)가 위치한 S3 Prefix 누락 여부 검증
    if not interim_prefix:
        raise ValueError('interim_prefix 정보가 없습니다.')

    ## -------------------------------------------------------
    ## 2. S3 Interim CSV 다운로드
    ## -------------------------------------------------------

    ## S3 Interim 영역의 CSV 파일들을 Lambda 로컬 임시 디렉터리(INTERIM_DIR)로 동기화
    interim_batch_dir = download_interim_batch(
        bucket_name=bucket_name,
        batch_id=batch_id,
        interim_prefix=interim_prefix,
        destination_dir=INTERIM_DIR,
    )

    ## -------------------------------------------------------
    ## 3. 데이터 전처리
    ## -------------------------------------------------------

    ## 다운로드된 CSV 파일들을 정제, 결합, 스키마 변환하여 최종 처리된 단일 CSV 파일 생성
    processed_file = run_preprocess(
        interim_batch_dir
    )

    ## -------------------------------------------------------
    ## 4. Processed CSV S3 업로드
    ## -------------------------------------------------------

    ## 전처리가 완료된 최종 결과 파일(CSV)을 S3 Processed 영역으로 업로드
    processed_key = upload_processed_file(
        processed_file=processed_file,
        bucket_name=bucket_name,
        batch_id=batch_id,
    )

    ## 후속 단계(적재 또는 분석 파이프라인)에서 참조할 S3 Processed Prefix 정의
    processed_prefix = f'processed/{batch_id}/'

    ## -------------------------------------------------------
    ## 5. Lambda 실행 결과 반환
    ## -------------------------------------------------------

    ## 런타임 Context 객체에서 AWS 고유 요청 ID 안전 추출 (테스트 환경 호환성 확보)
    request_id = getattr(
        context,
        'aws_request_id',
        None,
    )

    ## Step Functions 상태 머신의 다음 작업(예: DB 적재) 또는 모니터링 시스템에 전달할 결과 Payload 반환
    return {
        'stage': 'preprocess',
        'status': 'SUCCEEDED',
        'batch_id': batch_id,
        'bucket': bucket_name,
        'interim_prefix': interim_prefix,
        'processed_prefix': processed_prefix,
        'processed_key': processed_key,
        'request_id': request_id,
    }