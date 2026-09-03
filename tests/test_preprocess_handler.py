## 파일 및 디렉터리 경로 처리를 위한 표준 라이브러리 모듈 로드
from pathlib import Path

## S3 다운로드, 전처리 실행, S3 업로드 등 외부 의존성을 격리하기 위한 Mock 객체 로드
from unittest.mock import Mock

## 테스트 대상인 전처리(Preprocess) Lambda 핸들러 모듈 로드
from handlers import preprocess_handler


def test_preprocess_lambda_handler(monkeypatch):
    """
    S3 Interim 데이터 다운로드, 전처리 로직 실행, S3 Processed 업로드 단계가
    순차적으로 올바르게 연계되어 최종 성공 상태 및 메타데이터를 반환하는지 검증합니다.
    """

    ## 1. 테스트에 사용할 고유 배치 식별자(Batch ID) 정의
    batch_id = '20260830_163041'

    ## 2. S3에서 다운로드된 CSV 파일들이 위치할 가상의 Interim 디렉터리 경로 설정
    interim_batch_dir = Path(
        f'/tmp/data/interim/{batch_id}'
    )

    ## 3. 전처리 비즈니스 로직(run_preprocess) 완료 후 생성될 가상의 최종 CSV 파일 경로 설정
    processed_file = Path(
        '/tmp/data/processed/'
        f'books_pages_001_003_processed_{batch_id}.csv'
    )

    ## 4. download_interim_batch 호출 시 가상 Interim 디렉터리 경로를 반환하도록 Mocking
    mock_download = Mock(
        return_value=interim_batch_dir
    )

    ## 5. run_preprocess 호출 시 가상 Processed 파일 경로를 반환하도록 Mocking
    mock_preprocess = Mock(
        return_value=processed_file
    )

    ## 6. S3 Processed 영역에 저장될 기대 S3 Object Key 정의
    processed_key = (
        f'processed/{batch_id}/'
        f'books_pages_001_003_processed_{batch_id}.csv'
    )

    ## 7. upload_processed_file 호출 시 기대 S3 Key 문자열을 반환하도록 Mocking
    mock_upload = Mock(
        return_value=processed_key
    )

    ## 8. 핸들러 모듈 내부의 실제 S3 다운로드 함수를 Mock 객체로 대체
    monkeypatch.setattr(
        preprocess_handler,
        'download_interim_batch',
        mock_download,
    )

    ## 9. 핸들러 모듈 내부의 실제 전처리 함수를 Mock 객체로 대체
    monkeypatch.setattr(
        preprocess_handler,
        'run_preprocess',
        mock_preprocess,
    )

    ## 10. 핸들러 모듈 내부의 실제 S3 업로드 함수를 Mock 객체로 대체
    monkeypatch.setattr(
        preprocess_handler,
        'upload_processed_file',
        mock_upload,
    )

    ## 11. AWS Lambda 런타임 Context 모의 객체 생성 및 고유 Request ID 설정
    context = Mock()
    context.aws_request_id = 'test-request-id'

    ## 12. 이전 단계(Extract) 또는 Step Functions로부터 전달받는 Lambda 입력 이벤트 정의
    event = {
        'batch_id': batch_id,
        'bucket': 'test-books-bucket',
        'interim_prefix': f'interim/{batch_id}/',
    }

    ## 13. Mocking된 환경에서 Preprocess Lambda 핸들러 함수 실행
    result = preprocess_handler.lambda_handler(
        event,
        context,
    )

    ## 14. 반환된 결과 Payload가 기대하는 파이프라인 스키마 및 메타데이터와 완벽히 일치하는지 종합 검증
    assert result == {
        'stage': 'preprocess',
        'status': 'SUCCEEDED',
        'batch_id': batch_id,
        'bucket': 'test-books-bucket',
        'interim_prefix': f'interim/{batch_id}/',
        'processed_prefix': f'processed/{batch_id}/',
        'processed_key': processed_key,
        'request_id': 'test-request-id',
    }