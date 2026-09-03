"""
Books to Scrape 웹사이트의 정적 페이지를
페이지네이션 방식으로 수집하는 모듈입니다.

웹 요청, 폴더 생성, HTML 저장 기능을 함수로 분리하고,
run_crawling()에서 전체 페이지네이션 수집 작업을 실행합니다.

수집 시작 시각을 이름으로 사용하는 배치 폴더를 생성하고,
같은 실행에서 수집한 HTML 파일을 해당 폴더에 함께 저장합니다.

저장 구조:
    data/raw/html/YYYYMMDD_HHMMSS/
        books_page_001.html
        books_page_002.html
        ...

반환값:
    run_crawling()
        생성된 raw HTML 배치 폴더 경로
"""

import time
from datetime import datetime
from pathlib import Path

import requests

from .config import (
    APP_TIMEZONE,
    BASE_URL,
    CONNECT_TIMEOUT,
    END_PAGE,
    HEADERS,
    PROJECT_DIR,
    RAW_HTML_DIR,
    READ_TIMEOUT,
    REQUEST_INTERVAL,
    START_PAGE,
)

## ===========================================================
## 1. 기본 설정 확인
## ===========================================================

print(f'프로젝트 기준 경로 : {PROJECT_DIR}')
print(f'원본 HTML 기본 저장 경로 : {RAW_HTML_DIR}')


def fetch_html(
    url: str,
    connect_timeout: int = CONNECT_TIMEOUT,
    read_timeout: int = READ_TIMEOUT,
) -> requests.Response:
    """
    지정한 URL에 GET 요청을 보내고 정상 응답 객체를 반환한다.

    Args:
        url:
            요청할 웹페이지 URL

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

    response = requests.get(
        url,
        headers=HEADERS,
        timeout=(connect_timeout, read_timeout),
    )

    ## HTTP 상태 코드가 400번대 또는 500번대이면
    ## requests.exceptions.HTTPError 발생
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


def create_batch_directory(
    directory: Path,
    collected_at: datetime,
) -> Path:
    """
    수집 시작 시각을 이름으로 사용하는 배치 폴더를 생성한다.

    Args:
        directory:
            모든 수집 배치가 저장되는 기본 폴더

        collected_at:
            전체 수집 작업의 시작 시각

    Returns:
        생성된 raw HTML 배치 폴더 경로
    """

    batch_name = collected_at.strftime('%Y%m%d_%H%M%S')
    batch_dir = directory / batch_name

    return ensure_directory(batch_dir)


def save_raw_html(
    content: bytes,
    batch_dir: Path,
    source_page: int,
) -> Path:
    """
    페이지별 원본 HTML 바이트 데이터를 배치 폴더에 저장한다.

    Args:
        content:
            서버에서 받은 원본 응답 본문

        batch_dir:
            원본 HTML을 저장할 수집 배치 폴더

        source_page:
            수집한 웹페이지 번호

    Returns:
        저장이 완료된 HTML 파일 경로
    """

    file_path = batch_dir / f'books_page_{source_page:03d}.html'
    file_path.write_bytes(content)

    return file_path


def run_crawling(
    base_url: str = BASE_URL,
    start_page: int = START_PAGE,
    end_page: int = END_PAGE,
) -> Path:
    """
    지정한 페이지 범위를 수집하고 raw HTML 배치 폴더에 저장한다.

    Args:
        base_url:
            페이지 URL의 공통 부분

        start_page:
            수집 시작 페이지

        end_page:
            수집 종료 페이지

    Returns:
        이번 수집 작업의 raw HTML 배치 폴더 경로

    Raises:
        ValueError:
            시작 페이지 또는 종료 페이지 범위가 올바르지 않은 경우

        requests.exceptions.RequestException:
            웹페이지 요청에 실패한 경우

        OSError:
            배치 폴더 생성이나 HTML 파일 저장에 실패한 경우
    """

    if start_page <= 0 or end_page <= 0:
        raise ValueError('페이지 번호는 1 이상이어야 합니다.')

    if start_page > end_page:
        raise ValueError('시작 페이지는 종료 페이지보다 클 수 없습니다.')

    ## 전체 수집 작업의 시작 시각
    ## 한국 표준시(KST) 기준 (zoneinfo 모듈 활용)
    collected_at = datetime.now(APP_TIMEZONE)

    ## 같은 수집 작업의 HTML을 저장할 배치 폴더 생성
    batch_dir = create_batch_directory(
        directory=RAW_HTML_DIR,
        collected_at=collected_at,
    )

    ## 저장된 HTML 파일 경로 목록
    raw_files: list[Path] = []

    for page in range(start_page, end_page + 1):
        target_url = f'{base_url}page-{page}.html'

        print('=' * 60)
        print(f'{page}페이지 요청 시작')
        print(f'요청 URL : {target_url}')

        response = fetch_html(target_url)

        raw_file = save_raw_html(
            content=response.content,
            batch_dir=batch_dir,
            source_page=page,
        )

        raw_files.append(raw_file)

        print(f'최종 URL : {response.url}')
        print(f'상태 코드 : {response.status_code}')
        print(f"Content-Type : {response.headers.get('Content-Type')}")
        print(f'응답 인코딩 : {response.encoding}')
        print(f'본문 기준 추정 인코딩 : {response.apparent_encoding}')
        print(f'응답 크기 : {len(response.content):,} bytes')
        print(f'수집 시작 시각 : {collected_at:%Y-%m-%d %H:%M:%S}')
        print(f'원본 HTML 저장 경로 : {raw_file}')

        ## 마지막 페이지가 아니면 다음 요청 전 대기
        if page < end_page:
            time.sleep(REQUEST_INTERVAL)

    print()
    print('=' * 60)
    print('웹페이지 수집을 완료했습니다.')
    print('=' * 60)

    print(f'수집 페이지 : {start_page}~{end_page}')
    print(f'수집 페이지 수 : {len(raw_files)}')
    print(f'수집 시작 시각 : {collected_at:%Y-%m-%d %H:%M:%S}')
    print(f'수집 배치명 : {batch_dir.name}')
    print(f'HTML 저장 폴더 : {batch_dir}')

    return batch_dir


if __name__ == '__main__':
    try:
        run_crawling()

    except requests.exceptions.RequestException as error:
        print()
        print('웹페이지 수집에 실패했습니다.')
        print(f'오류 내용 : {error}')

    except (OSError, ValueError) as error:
        print()
        print('원본 HTML 저장 또는 페이지 설정에 실패했습니다.')
        print(f'오류 내용 : {error}')



