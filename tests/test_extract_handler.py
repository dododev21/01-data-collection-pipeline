from pathlib import Path
from unittest.mock import Mock

from handlers import extract_handler


def test_extract_lambda_handler(monkeypatch):
    batch_id = '20260830_163500'

    raw_batch_dir = Path(
        f'/tmp/data/raw/html/{batch_id}'
    )

    parsed_csv_files = [
        Path(
            f'/tmp/data/interim/{batch_id}/'
            'books_page_001.csv'
        ),
        Path(
            f'/tmp/data/interim/{batch_id}/'
            'books_page_002.csv'
        ),
    ]

    mock_download = Mock(
        return_value=raw_batch_dir
    )

    mock_extract = Mock(
        return_value=parsed_csv_files
    )

    mock_upload = Mock(
        return_value=[
            f'interim/{batch_id}/books_page_001.csv',
            f'interim/{batch_id}/books_page_002.csv',
        ]
    )

    monkeypatch.setattr(
        extract_handler,
        'download_raw_html_batch',
        mock_download,
    )

    monkeypatch.setattr(
        extract_handler,
        'run_extract',
        mock_extract,
    )

    monkeypatch.setattr(
        extract_handler,
        'upload_interim_files',
        mock_upload,
    )

    context = Mock()
    context.aws_request_id = 'test-request-id'

    event = {
        'batch_id': batch_id,
        'bucket': 'test-books-bucket',
        'raw_prefix': f'raw/{batch_id}/',
    }

    result = extract_handler.lambda_handler(
        event,
        context,
    )

    assert result == {
        'stage': 'extract',
        'status': 'SUCCEEDED',
        'batch_id': batch_id,
        'bucket': 'test-books-bucket',
        'raw_prefix': f'raw/{batch_id}/',
        'interim_prefix': f'interim/{batch_id}/',
        'object_count': 2,
        'request_id': 'test-request-id',
    }