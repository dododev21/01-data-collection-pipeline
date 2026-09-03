"""
데이터 수집 파이프라인에서 사용하는
Amazon S3 저장 기능을 제공하는 모듈입니다.
"""

from pathlib import Path
from typing import Any


def upload_raw_html_batch(
    raw_batch_dir: Path,
    bucket_name: str,
    s3_client: Any | None = None,
) -> list[str]:
    """
    Crawling 단계에서 생성한 HTML 파일을
    Amazon S3 raw 영역에 업로드합니다.

    Args:
        raw_batch_dir:
            Crawling 단계에서 생성된 로컬 임시 배치 폴더

        bucket_name:
            HTML 파일을 저장할 S3 Bucket 이름

        s3_client:
            테스트 등을 위해 외부에서 전달할 수 있는 S3 Client

    Returns:
        S3에 업로드된 Object Key 목록
    """

    ## 1. 대상 S3 버킷 이름 파라미터 유효성 검증
    if not bucket_name:
        raise ValueError('S3 Bucket 이름이 지정되지 않았습니다.')

    ## 2. 로컬의 Raw HTML 소스 디렉터리 존재 여부 검증
    if not raw_batch_dir.exists():
        raise FileNotFoundError(
            f'Raw HTML 배치 폴더가 존재하지 않습니다: {raw_batch_dir}'
        )

    ## Lambda Runtime에는 boto3가 기본으로 제공됨 (외부 주입이 없을 경우 기본 클라이언트 생성)
    if s3_client is None:
        import boto3

        s3_client = boto3.client('s3')

    ## 3. 배치 폴더명을 파싱하여 S3 저장 경로 Prefix 정의 (예: raw/20260827_083000)
    batch_id = raw_batch_dir.name
    raw_prefix = f'raw/{batch_id}'

    ## 4. 로컬 배치 디렉터리 내의 모든 .html 파일을 이름 순으로 정렬하여 탐색
    html_files = sorted(raw_batch_dir.glob('*.html'))

    ## 5. 업로드 대상 파일이 없는 경우 예외 발생 (빈 배치 업로드 방지)
    if not html_files:
        raise FileNotFoundError(
            f'업로드할 HTML 파일이 없습니다: {raw_batch_dir}'
        )

    ## 6. S3 업로드 성공 키들을 추적할 리스트 초기화
    object_keys: list[str] = []

    ## 7. 파일 목록을 순회하며 개별 HTML 파일을 S3로 업로드
    for html_file in html_files:
        object_key = f'{raw_prefix}/{html_file.name}'

        ## S3 버킷에 로컬 파일 업로드 실행
        s3_client.upload_file(
            str(html_file),
            bucket_name,
            object_key,
        )

        object_keys.append(object_key)

        ## 업로드 완료 로그 출력 (CloudWatch 등에서 모니터링 가능)
        print(
            f'S3 업로드 완료 : '
            f's3://{bucket_name}/{object_key}'
        )

    ## 8. 파이프라인의 다음 단계(Extract 등)에서 참조할 S3 Object Key 리스트 반환
    return object_keys


def download_raw_html_batch(
    bucket_name: str,
    batch_id: str,
    raw_prefix: str,
    destination_dir: Path,
    s3_client: Any | None = None,
) -> Path:
    """
    S3 Raw 영역의 HTML 파일을
    Lambda 임시 디렉터리로 다운로드합니다.
    """

    ## 1. 필수 입력 인자 유효성 검증
    if not bucket_name:
        raise ValueError('S3 Bucket 이름이 지정되지 않았습니다.')

    if not batch_id:
        raise ValueError('batch_id가 지정되지 않았습니다.')

    if not raw_prefix:
        raise ValueError('raw_prefix가 지정되지 않았습니다.')

    ## 2. S3 클라이언트 주입 여부 확인 및 초기화
    if s3_client is None:
        import boto3

        s3_client = boto3.client('s3')

    ## 3. 데이터를 저장할 로컬 목적지 배치 폴더 생성 (/tmp/.../batch_id)
    raw_batch_dir = destination_dir / batch_id
    raw_batch_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    ## S3 Prefix에 포함된 객체 목록 조회
    response = s3_client.list_objects_v2(
        Bucket=bucket_name,
        Prefix=raw_prefix,
    )

    ## 4. S3 응답에서 Contents 메타데이터 리스트 추출
    objects = response.get('Contents', [])

    ## 5. 조회된 객체 중 확장자가 .html인 파일만 필터링
    html_objects = [
        obj
        for obj in objects
        if obj['Key'].endswith('.html')
    ]

    ## 6. S3 Prefix 하위에 유효한 HTML 객체가 없는 경우 예외 처리
    if not html_objects:
        raise FileNotFoundError(
            f'S3 Raw 영역에 HTML 파일이 없습니다: '
            f's3://{bucket_name}/{raw_prefix}'
        )

    ## 7. S3에 저장된 HTML 객체들을 로컬 임시 디렉터리로 다운로드
    for obj in html_objects:
        object_key = obj['Key']
        file_name = Path(object_key).name

        local_file = raw_batch_dir / file_name

        s3_client.download_file(
            bucket_name,
            object_key,
            str(local_file),
        )

        ## 다운로드 완료 로그 출력
        print(
            f'S3 다운로드 완료 : '
            f's3://{bucket_name}/{object_key}'
        )

    ## 8. 다운로드가 완료된 로컬 디렉터리 경로 반환
    return raw_batch_dir


def upload_interim_files(
    csv_files: list[Path],
    bucket_name: str,
    batch_id: str,
    s3_client: Any | None = None,
) -> list[str]:
    """
    Extract 단계에서 생성된 CSV 파일을
    S3 Interim 영역에 업로드합니다.
    """

    ## 1. 필수 인자(버킷 이름, 대상 파일 목록) 유효성 검증
    if not bucket_name:
        raise ValueError('S3 Bucket 이름이 지정되지 않았습니다.')

    if not csv_files:
        raise ValueError('업로드할 CSV 파일이 없습니다.')

    ## 2. S3 클라이언트 주입 여부 확인 및 초기화
    if s3_client is None:
        import boto3

        s3_client = boto3.client('s3')

    ## 3. 중간 데이터(Interim) 전용 S3 Prefix 생성 (예: interim/20260827_083000)
    interim_prefix = f'interim/{batch_id}'
    object_keys: list[str] = []

    ## 4. 추출된 CSV 파일 리스트를 순회하며 S3에 업로드
    for csv_file in csv_files:
        object_key = (
            f'{interim_prefix}/{csv_file.name}'
        )

        s3_client.upload_file(
            str(csv_file),
            bucket_name,
            object_key,
        )

        object_keys.append(object_key)

        ## 업로드 완료 로그 출력
        print(
            f'S3 업로드 완료 : '
            f's3://{bucket_name}/{object_key}'
        )

    ## 5. 업로드된 중간 정제 CSV 파일들의 S3 Object Key 목록 반환
    return object_keys


def download_interim_batch(
    bucket_name: str,
    batch_id: str,
    interim_prefix: str,
    destination_dir: Path,
    s3_client: Any | None = None,
) -> Path:
    """
    S3 Interim 영역의 CSV 파일을
    Lambda 임시 디렉터리로 다운로드합니다.
    """

    ## 1. 필수 인자 유효성 검증
    if not bucket_name:
        raise ValueError('S3 Bucket 이름이 지정되지 않았습니다.')

    if not batch_id:
        raise ValueError('batch_id가 지정되지 않았습니다.')

    if not interim_prefix:
        raise ValueError('interim_prefix가 지정되지 않았습니다.')

    ## 2. S3 클라이언트 주입 여부 확인 및 초기화
    if s3_client is None:
        import boto3

        s3_client = boto3.client('s3')

    ## 3. 중간 데이터를 저장할 로컬 목적지 디렉터리 준비
    interim_batch_dir = destination_dir / batch_id
    interim_batch_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    ## 4. S3 Interim Prefix 하위 객체 목록 검색
    response = s3_client.list_objects_v2(
        Bucket=bucket_name,
        Prefix=interim_prefix,
    )

    objects = response.get('Contents', [])

    ## 5. 조회된 객체 중 확장자가 .csv인 파일만 필터링
    csv_objects = [
        obj
        for obj in objects
        if obj['Key'].endswith('.csv')
    ]

    ## 6. S3 Interim 경로에 CSV 파일이 존재하지 않는 경우 예외 처리
    if not csv_objects:
        raise FileNotFoundError(
            f'S3 Interim 영역에 CSV 파일이 없습니다: '
            f's3://{bucket_name}/{interim_prefix}'
        )

    ## 7. S3에 저장된 CSV 객체들을 로컬 디렉터리로 다운로드
    for obj in csv_objects:
        object_key = obj['Key']
        file_name = Path(object_key).name
        local_file = interim_batch_dir / file_name

        s3_client.download_file(
            bucket_name,
            object_key,
            str(local_file),
        )

        ## 다운로드 완료 로그 출력
        print(
            f'S3 다운로드 완료 : '
            f's3://{bucket_name}/{object_key}'
        )

    ## 8. CSV 파일 다운로드가 완료된 로컬 디렉터리 경로 반환
    return interim_batch_dir


def upload_processed_file(
    processed_file: Path,
    bucket_name: str,
    batch_id: str,
    s3_client: Any | None = None,
) -> str:
    """
    전처리가 완료된 CSV 파일을
    S3 Processed 영역에 업로드합니다.
    """

    ## 1. 필수 인자(버킷 이름, 배치 ID) 유효성 검증
    if not bucket_name:
        raise ValueError('S3 Bucket 이름이 지정되지 않았습니다.')

    if not batch_id:
        raise ValueError('batch_id가 지정되지 않았습니다.')

    ## 2. 업로드 대상인 전처리 완료 로컬 CSV 파일 존재 여부 검증
    if not processed_file.exists():
        raise FileNotFoundError(
            f'Processed CSV 파일이 존재하지 않습니다: '
            f'{processed_file}'
        )

    ## 3. S3 클라이언트 주입 여부 확인 및 초기화
    if s3_client is None:
        import boto3

        s3_client = boto3.client('s3')

    ## 4. 최종 정제 데이터(Processed) 전용 S3 Object Key 생성 (예: processed/20260827_083000/data.csv)
    object_key = (
        f'processed/{batch_id}/{processed_file.name}'
    )

    ## 5. S3 Processed 경로로 단일 파일 업로드 실행
    s3_client.upload_file(
        str(processed_file),
        bucket_name,
        object_key,
    )

    ## 6. 업로드 완료 로그 출력
    print(
        f'S3 업로드 완료 : '
        f's3://{bucket_name}/{object_key}'
    )

    ## 7. 저장된 S3 Object Key 반환 (후속 적재 단계 또는 메타데이터 관리용)
    return object_key


def download_processed_file(
    bucket_name: str,
    processed_key: str,
    destination_dir: Path,
    s3_client: Any | None = None,
) -> Path:
    """
    S3 Processed 영역의 CSV 파일을
    Lambda 임시 디렉터리로 다운로드합니다.
    """

    ## 1. 대상 S3 버킷 이름 유효성 검증
    if not bucket_name:
        raise ValueError('S3 Bucket 이름이 지정되지 않았습니다.')

    ## 2. 다운로드할 S3 Processed 객체 키(Object Key) 누락 여부 검증
    if not processed_key:
        raise ValueError('processed_key가 지정되지 않았습니다.')

    ## 3. 대상 객체가 전처리 완료 데이터 형식인 CSV인지 확장자 검증
    if not processed_key.endswith('.csv'):
        raise ValueError(
            f'Processed 객체가 CSV 파일이 아닙니다: {processed_key}'
        )

    ## 4. S3 클라이언트 주입 여부 확인 및 boto3 기본 클라이언트 초기화
    if s3_client is None:
        import boto3

        s3_client = boto3.client('s3')

    ## 5. 다운로드 파일을 저장할 로컬 목적지 디렉터리 생성 (/tmp/...)
    destination_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    ## 6. S3 키에서 순수 파일명을 추출하고 로컬 저장 대상 전체 경로 생성
    file_name = Path(processed_key).name
    local_file = destination_dir / file_name

    ## 7. S3 Processed 객체를 로컬 파일 시스템으로 다운로드 실행
    s3_client.download_file(
        bucket_name,
        processed_key,
        str(local_file),
    )

    ## 8. 다운로드 완료 로그 출력
    print(
        f'S3 다운로드 완료 : '
        f's3://{bucket_name}/{processed_key}'
    )

    ## 9. 최종 다운로드된 로컬 CSV 파일의 Path 객체 반환 (후속 DB 적재 단계에서 활용)
    return local_file





