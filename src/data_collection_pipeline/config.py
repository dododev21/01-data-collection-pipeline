"""
정적 크롤링 데이터 수집 파이프라인의 공통 설정 모듈입니다.

웹 수집 설정과 프로젝트 데이터 저장 경로를 한곳에서 관리합니다.
각 단계 모듈은 필요한 설정값만 import하여 사용합니다.
"""

import os
from pathlib import Path
from zoneinfo import ZoneInfo

## ===========================================================
## 1. 프로젝트 경로
## ===========================================================

PROJECT_DIR = Path(__file__).resolve().parents[2]

DEFAULT_DATA_DIR = PROJECT_DIR / 'data'
DATA_DIR = Path(os.getenv('DATA_DIR', str(DEFAULT_DATA_DIR)))
RAW_HTML_DIR = DATA_DIR / 'raw' / 'html'
INTERIM_DIR = DATA_DIR / 'interim'
PROCESSED_DIR = DATA_DIR / 'processed'

ENV_FILE = PROJECT_DIR / '.env'


## ===========================================================
## 2. 웹 수집 설정
## ===========================================================

BASE_URL = 'https://books.toscrape.com/catalogue/'
SOURCE_SITE = 'Books to Scrape'

START_PAGE = 1
END_PAGE = 3

CONNECT_TIMEOUT = 5
READ_TIMEOUT = 30

REQUEST_INTERVAL = 0.5

HEADERS = {
    'User-Agent': 'EducationalDataCollector/1.0',
}

## ===========================================================
## 3. 시간대 설정
## ===========================================================

APP_TIMEZONE = ZoneInfo('Asia/Seoul')