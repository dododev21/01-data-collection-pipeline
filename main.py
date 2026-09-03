"""
정적 웹페이지 데이터 수집 파이프라인 실행 파일

이 파일은 프로젝트의 실행 진입점(entry point)으로,
크롤링, 파싱, 전처리, MySQL에 저장 작업을 순서대로 실행한다.

[사용 모듈]
1. crawling.py
    - 웹페이지에 HTTP 요청을 보낸다.
    - 응답받은 원본 HTML을 파일로 저장한다.

2. extract.py
    - 저장된 원본 HTML 파일을 읽는다.
    - 도서 정보를 파싱하여 중간 csv 파일로 저장한다.

3. preprocess.py
    - 파싱 csv 파이을 읽는다.
    - 문자열, 가격, 평점, 재고 여부 등을 정리한다.
    - 데이터 검증과 중복 제거를 수행한다.
    - 전처리 결과를 최종 csv 파일로 저장한다.

4. load.py
    - 전처리 csv 파일을 읽는다.
    - MySQL 연결 정보를 불러온다.
    - books 테이블 생성한다.
    - 도서 데이터를 UPSERT 방식으로 저장한다.

[실행 흐름]
run_crawling()
-> 원본 HTML 파일 경로 반환

run_extract(raw_html_file)
-> 파싱 csv 파일 경로 반환

run_preprocess(parsed_csv_file)
-> 전처리 csv 파일 경로 반환

run_load(processed_csv_file)
-> MySQL 저장 결과 요약 반환

[실행 결과]
각 단계에서 생성한 파일 경로를 출력하고,
원본 HTML, 파싱 csv, 전처리 csv 경로와
MySQL 저장 결과를 튜플로 반환한다.
"""

from pathlib import Path

import requests
from sqlalchemy.exc import SQLAlchemyError

from src.data_collection_pipeline.crawling import run_crawling
from src.data_collection_pipeline.extract import run_extract
from src.data_collection_pipeline.load import run_load
from src.data_collection_pipeline.preprocess import run_preprocess

## --------------------------------------
## 프로젝트 경로 설정
## --------------------------------------

def main() -> tuple[Path, list[Path], Path, dict[str, int | str]]:
    """
    웹페이지 수집, HTML 파싱, 데이터 전처리, MySQL에 저장을 순서대로 실행한다.

    Returns:
        다음 파일 경로를 저장한 튜플

        1. raw HTML 배치 폴더 경로
        2. 페이지별 parsed csv 파일 경로 목록
        3. 전처리 csv 파일 경로
        4. MySQL 저장 결과 요약
    """

    print('=' * 60)
    print('정적 웹페이지 데이터 수집 파이프라인 시작')
    print('=' * 60)

    ## 1. Crawling ---------------------------------------------
    raw_batch_dir = run_crawling()

    ## 2. Extract -----------------------------------------------
    parsed_csv_files = run_extract(raw_batch_dir)

    ## 3. Preprocess --------------------------------------------
    interim_batch_dir = parsed_csv_files[0].parent
    processed_csv_file = run_preprocess(interim_batch_dir)

    ## 4. Load -----------------------------------------------------
    load_summary = run_load(processed_csv_file)

    print()
    print('>' * 60)
    print('정적 웹페이지 데이터 수집 파이프라인 완료')
    print('>' * 60)
    print()
    print(f'✔️  raw HTML 배치 폴더 : {raw_batch_dir}')
    print(f'✔️  parsed CSV 파일 수 : {len(parsed_csv_files)}')
    print(f'✔️  interim 배치 폴더 : {interim_batch_dir}')
    print(f'✔️  processed csv 파일 : {processed_csv_file}')
    print(f'✔️  MySQL 저장 결과 : {load_summary}')

    return (raw_batch_dir, parsed_csv_files, processed_csv_file, load_summary)


if __name__ == '__main__':
    try:
        main()
    except requests.exceptions.RequestException as error:
        print()
        print('웹페이지 요청 중 오류가 발생했습니다.')
        print(f'오류 내용: {error}')
    except SQLAlchemyError as error:
        print()
        print('MySQL 처리 중 오류가 발생했습니다.')
        print(f'오류 내용 : {error}')
    except (OSError, ValueError) as error:
        print()
        print('파일 처리 또는 데이터 변환 중 오류가 발생했습니다.')
        print(f'오류 내용 : {error}')

