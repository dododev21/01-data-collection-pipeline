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

from src.data_collection_pipeline import (
        run_crawling, 
        run_extract, 
        run_preprocess,
        run_load
)     

## --------------------------------------
## 프로젝트 경로 설정
## --------------------------------------

## main.py 위치한 폴더를 프로젝트 루트 사용
PROJECT_DIR = Path(__file__).resolve().parent


def main() -> tuple[Path, Path, Path, dict[str, int | str]]:
    """
    웹페이지 수집, HTML 파싱, 데이터 전처리, MySQL에 저장을 순서대로 실행한다.

    Returns:
        다음 파일 경로를 저장한 튜플

        1. raw HTML 배치 폴더 경로
        2. 파싱 csv 파일 경로
        3. 전처리 csv 파일 경로
        4. MySQL 저장 결과 요약
    """

    print('=' * 60)
    print('정적 웹페이지 데이터 수집 파이프라인 시작')
    print('=' * 60)

    ## 1. Crawling ---------------------------------------------
    ## 웹페이지에 요청을 보내고 원본 HTML을 저장
    ## 반환값은 저장된 원본 HTML 파일의 Path 객체
    raw_html_file = run_crawling()

    ## 2. Extract -----------------------------------------------
    ## 원본 HTML 파일 경로를 전달하여 도서 정보를 파싱
    ## 파싱 결과를 중간 csv로 저장하고 해당 파일 경로 반환
    parsed_csv_file = run_extract(raw_html_file)

    ## 3. Preprocess --------------------------------------------
    ## 파싱 csv 파일 경로를 전달하여 데이터를 전처리
    ## 전처리 결과를 최종 csv로 저장하고 해당 파일 경로를 반환
    processed_csv_file = run_preprocess(parsed_csv_file=parsed_csv_file)

    ## 4. Load -----------------------------------------------------
    ## 전처리 csv 파일 경로를 전달하여 MySQL에 저장
    ## 입력 파일명, 데이터베이스명, 입력 행 수, DB 영향 행 수가 포함된
    ##      요약 정보를 반환
    load_summary = run_load(processed_csv_file)

    print()
    print('>' * 60)
    print('정적 웹페이지 데이터 수집 파이프라인 완료')
    print('>' * 60)
    print()
    print(f'✔️  원본 HTML 파일 : {raw_html_file}')
    print(f'✔️  파싱 완료된 csv 파일 : {parsed_csv_file}')
    print(f'✔️  전처리 완료된 csv 파일 : {processed_csv_file}')

    return (raw_html_file, parsed_csv_file, processed_csv_file, load_summary)


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

