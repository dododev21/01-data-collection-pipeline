"""
정적 웹페이지의 원본 HTML을 수집하는 모듈

이 모듈은 다음 작업을 수행한다.

1. 웹페이지에 GET 요청을 보낸다.
2. 정상 응답인지 확인한다.
3. 원본 HTML을 data/raw/html 폴더에 저장한다.
4. 저장한 HTML 파일 경로를 반환한다.
"""


from pathlib import Path
from datetime import datetime

import requests


TARGET_URL = 'https://books.toscrape.com'

CONNECT_TIMEOUT  = 5
READ_TIMEOUT = 30

# PROJECT_DIR = Path('D:/AI/data_analytics/crawling/01-data-collection-pipeline')
PROJECT_DIR = Path(__file__).resolve().parents[2]
RAW_HTML_DIR = PROJECT_DIR / 'data' / 'raw' / 'html'


def fetch_html(
    url: str,
    connect_timeout: int = 5,
    read_timeout: int = 30,
) -> requests.Response:
    """
    지정한 URL에 GET 요청을 보내고 응답 객체를 반환한다.

    Args:
        url:
            요청할 웹페이지 

        connect_timeout:
            서버 연결 제한 시간
            
        read_timeout:
            응답 데이터 대기 제한 시간

    Returns:
        정상 응답을 포함한 requests.Response 객체

    Raises:
        requests.exceptions.RequestException:
            요청 과정에서 오류가 발생한 경우
    """
    headers = {'User-Agent': 'EducationalDataCollector/1.0'}

    response = requests.get(
        TARGET_URL,
        headers=headers,
        timeout=(CONNECT_TIMEOUT, READ_TIMEOUT),
    )

    response.raise_for_status()

    return response
    

def ensure_directory(directory: Path) -> Path:
    """
    지정한 폴더가 없으면 생성하고 폴더 경로를 반환한다.

    Args:
        directory:
            생성하거나 확인할 폴더 경로

    Returns:
        생성 또는 확인이 완료된 폴더 경로    
    """
    directory.mkdir(
        parents=True, 
        exist_ok=True, 
    )

    return directory


def save_raw_html(
    content: bytes,
    directory: Path,
    file_prefix: str,
    collected_at: datetime
) -> Path:
    """
    원본 HTML 바이트 데이터를 시간 정보가 포함된 파일로 저장한다.

    Args:
        content:
            서버에서 받은 원본 응답 본문

        directory:
            원본 HTML을 저장할 폴더
    
        file_prefix:
            파일명 앞부분

        collected_at:
            데이터를 수집한 날짜와 시각

    Returns:
        저장이 완료된 HTML 파일 경로
    """
    save_directory = ensure_directory(directory)
    
    timestamp = collected_at.strftime('%Y%m%d_%H%M%S')
    file_path = save_directory / f'{file_prefix}_{timestamp}.html'
    file_path.write_bytes(content)

    return file_path


def run_crawling(url: str = TARGET_URL) -> Path:
    """
    웹페이지 수집부터 원본 HTML 저장까지 실행한다.

    Args:
        url:
            수집할 웹페이지 url
    
    Returns:
        저장된 원본 HTML 파일 경로

    Raises:
        reqeusts.exceptions.RequestException
            웹페이지 요청에 실패한 경우

        OSError:
            폴더 생성이나 파일 저장에 실패한 경우
    """

    response = fetch_html(url)

    collected_at = datetime.now()
    
    raw_file = save_raw_html(
        content=response.content,
        directory=RAW_HTML_DIR,
        file_prefix='books_home',
        collected_at=collected_at,
    )
    
    print('웹페이지 수집을 완료했습니다.')
    print('=' * 60)
    print(f'요청 URL : {url}')
    print(f'최종 URL : {response.url}')
    print(f'상태 코드 : {response.status_code}')
    print(f'Content-Type : {response.headers.get('Content-Type')}')
    print(f'응답 인코딩 : {response.encoding}')
    print(f'본문 기준 추정 인코딩 : {response.apparent_encoding}')
    print(f'응답 크기 : {len(response.content):,} bytes')
    print(f'수집 시각 : {collected_at: %Y-%m-%d %H:%M:%S}')    
    print(f'원본 HTML 저장 경로 : {raw_file}')    

    return raw_file


if __name__ == '__main__':
    try:
        run_crawling()
    except requests.exceptions.RequestException as error:
        print('웹페이지 수집에 실패했습니다.')
        print(f'오류 내용 : {error}')
    except OSError as error:
        print('원본 HTML 저장에 실패했습니다.')
        print(f'오류 내용 : {error}')

