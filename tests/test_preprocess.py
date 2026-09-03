from datetime import datetime
from pathlib import Path

import pandas as pd
import pytest

from src.data_collection_pipeline.config import APP_TIMEZONE
from src.data_collection_pipeline.preprocess import (
    build_processed_file_path,
    parse_availability,
    parse_parsed_file_name,
    parse_price,
)


def test_parse_parsed_file_name_returns_page_number():
    file_path = Path('books_page_012_parsed.csv')

    result = parse_parsed_file_name(file_path)

    assert result == 12


def test_parse_parsed_file_name_raises_value_error_for_invalid_name():
    file_path = Path('books_page_12_parsed.csv')

    with pytest.raises(ValueError):
        parse_parsed_file_name(file_path)


def test_parse_price_converts_price_text_to_float64():
    prices = pd.Series(
        ['£51.77', '£23.88'],
        dtype='string',
    )

    result = parse_price(prices)

    assert result.tolist() == [51.77, 23.88]
    assert str(result.dtype) == 'Float64'


@pytest.mark.parametrize(
    ('value', 'expected'),
    [
        ('In stock', True),
        ('  In stock (22 available)  ', True),
        ('Out of stock', False),
        ('Unknown', None),
        (pd.NA, None),
    ],
)
def test_parse_availability(value, expected):
    assert parse_availability(value) is expected


def test_build_processed_file_path_contains_page_range_and_batch_time(tmp_path):
    batch_at = datetime(2026, 8, 21, 15, 30, 45, tzinfo=APP_TIMEZONE)

    result = build_processed_file_path(
        source_pages=[1, 2, 3],
        batch_at=batch_at,
        directory=tmp_path,
    )

    assert result == (
        tmp_path
        / 'books_pages_001_003_processed_20260821_153045.csv'
    )