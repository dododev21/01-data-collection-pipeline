from pathlib import Path
from unittest.mock import Mock

from handlers import crawling_handler


def test_lambda_handler_runs_crawling_and_uploads_to_s3(monkeypatch):
    batch_dir = Path('/tmp/data/raw/html/20260830_153000')

    mock_run_crawling = Mock(return_value=batch_dir)

    mock_upload = Mock(
        return_value=[
            'raw/20260830_153000/books_page_001.html',
            'raw/20260830_153000/books_page_002.html',
            'raw/20260830_153000/books_page_003.html',
        ]
    )

    monkeypatch.setattr(
        crawling_handler,
        'run_crawling',
        mock_run_crawling,
    )

    monkeypatch.setattr(
        crawling_handler,
        'upload_raw_html_batch',
        mock_upload,
    )

    monkeypatch.setenv(
        'DATA_BUCKET_NAME',
        'test-books-bucket',
    )

    context = Mock()
    context.aws_request_id = 'test-request-id'

    event = {
        'start_page': 1,
        'end_page': 3,
    }

    result = crawling_handler.lambda_handler(
        event,
        context,
    )

    mock_run_crawling.assert_called_once_with(
        start_page=1,
        end_page=3,
    )

    mock_upload.assert_called_once_with(
        raw_batch_dir=batch_dir,
        bucket_name='test-books-bucket',
    )

    assert result == {
        'stage': 'crawling',
        'status': 'SUCCEEDED',
        'batch_id': '20260830_153000',
        'start_page': 1,
        'end_page': 3,
        'bucket': 'test-books-bucket',
        'raw_prefix': 'raw/20260830_153000/',
        'object_count': 3,
        'request_id': 'test-request-id',
    }


def test_lambda_handler_uses_default_page_range(monkeypatch):
    batch_dir = Path('/tmp/data/raw/html/20260830_153000')

    mock_run_crawling = Mock(return_value=batch_dir)

    mock_upload = Mock(
        return_value=[
            'raw/20260830_153000/books_page_001.html',
        ]
    )

    monkeypatch.setattr(
        crawling_handler,
        'run_crawling',
        mock_run_crawling,
    )

    monkeypatch.setattr(
        crawling_handler,
        'upload_raw_html_batch',
        mock_upload,
    )

    monkeypatch.setenv(
        'DATA_BUCKET_NAME',
        'test-books-bucket',
    )

    result = crawling_handler.lambda_handler({}, None)

    mock_run_crawling.assert_called_once_with(
        start_page=1,
        end_page=3,
    )

    assert result['batch_id'] == '20260830_153000'
    assert result['bucket'] == 'test-books-bucket'
    assert result['request_id'] is None