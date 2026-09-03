from pathlib import Path

import pytest

from src.data_collection_pipeline.config import APP_TIMEZONE
from src.data_collection_pipeline.extract import (
    parse_batch_directory_name,
    parse_raw_file_name,
)


def test_parse_raw_file_name_returns_page_number():
    file_path = Path('books_page_003.html')

    result = parse_raw_file_name(file_path)

    assert result == 3


def test_parse_raw_file_name_raises_value_error_for_invalid_name():
    file_path = Path('books_page_3.html')

    with pytest.raises(ValueError):
        parse_raw_file_name(file_path)


def test_parse_batch_directory_name_returns_datetime():
    batch_dir = Path('20260821_153000')

    result = parse_batch_directory_name(batch_dir)

    assert result.year == 2026
    assert result.month == 8
    assert result.day == 21
    assert result.hour == 15
    assert result.minute == 30
    assert result.second == 0
    assert result.tzinfo == APP_TIMEZONE