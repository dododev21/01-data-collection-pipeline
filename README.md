# Data Collection Pipeline

정적 웹페이지에서 도서 데이터를 수집하고, 로컬 환경과 AWS Lambda 환경에서 단계별로 처리하는 데이터 수집 파이프라인 프로젝트입니다.

현재 프로젝트는 [Books to Scrape](https://books.toscrape.com/)를 대상으로 다음 두 실행 구조를 함께 제공합니다.

- **로컬 파이프라인**: Crawling → Extract → Preprocess → Load → MySQL
- **AWS 파이프라인(현재 구현 범위)**: Crawling Lambda → S3 Raw → Extract Lambda → S3 Interim → Preprocess Lambda → S3 Processed → Load Lambda → Amazon RDS MySQL

또한 `pytest`, `Ruff`, GitHub Actions를 이용하여 코드 품질과 테스트를 자동으로 검증하고, AWS SAM과 CloudFormation을 이용하여 Lambda와 S3 리소스를 배포합니다. Load 단계에서는 AWS Secrets Manager의 RDS 관리형 Secret과 VPC 네트워크 구성을 이용해 Private RDS MySQL에 안전하게 적재합니다.

---

## 1. 프로젝트 목표

이 프로젝트의 주요 목표는 다음과 같습니다.

- 정적 웹페이지의 페이지네이션 데이터를 수집합니다.
- 한 번의 수집 실행을 `batch_id` 기준으로 관리합니다.
- 원본 HTML, 파싱 CSV, 전처리 CSV를 단계별로 분리합니다.
- 로컬 환경에서는 전체 파이프라인을 순차 실행하여 MySQL까지 적재합니다.
- AWS 환경에서는 Lambda별 책임을 분리하고 S3를 단계 간 데이터 저장소로 사용합니다.
- Lambda 간에 대용량 데이터 자체를 전달하지 않고 `bucket`, `prefix`, `batch_id` 같은 메타데이터를 전달합니다.
- 데이터 저장 전 필수 컬럼, 결측값, 중복값, 자료형을 검증합니다.
- `pytest`와 `Ruff`를 이용해 로컬에서 코드와 테스트를 검증합니다.
- GitHub Actions를 이용해 `push`, `pull_request` 시 CI를 자동 실행합니다.
- AWS SAM을 이용해 Lambda, IAM Role, S3 Bucket을 코드로 정의하고 배포합니다.

---

## 2. 전체 구성

### 2.1 로컬 파이프라인

로컬에서는 `main.py`가 전체 파이프라인의 진입점입니다.

```text
Books to Scrape
       ↓
Crawling
       ↓
Raw HTML
       ↓
Extract
       ↓
Parsed CSV
       ↓
Preprocess
       ↓
Processed CSV
       ↓
Load
       ↓
MySQL
```

실행 함수 기준:

```text
run_crawling()
      ↓
run_extract()
      ↓
run_preprocess()
      ↓
run_load()
```

### 2.2 AWS 파이프라인 - 현재 구현 상태

현재 AWS 환경에서는 Crawling, Extract, Preprocess, Load 단계를 각각 Lambda로 분리했습니다.

```text
Books to Scrape
       ↓
Crawling Lambda
       ↓
/tmp/data/raw/html/{batch_id}/
       ↓
Amazon S3
raw/{batch_id}/
       ↓
Extract Lambda
       ↓
/tmp/data/raw/html/{batch_id}/
       ↓
HTML Parsing
       ↓
/tmp/data/interim/{batch_id}/
       ↓
Amazon S3
interim/{batch_id}/
       ↓
Preprocess Lambda
       ↓
/tmp/data/interim/{batch_id}/
       ↓
데이터 통합 / 전처리 / 검증
       ↓
/tmp/data/processed/
       ↓
Amazon S3
processed/{batch_id}/
       ↓
Load Lambda
       ↓
/tmp/data/processed/
       ↓
Processed CSV 검증
       ↓
AWS Secrets Manager
       ↓
Amazon RDS MySQL
       ↓
books 테이블 UPSERT
```

현재 구현 완료 범위:

```text
Crawling Lambda
      ↓
S3 Raw
      ↓
Extract Lambda
      ↓
S3 Interim
      ↓
Preprocess Lambda
      ↓
S3 Processed
      ↓
Load Lambda
      ↓
Amazon RDS MySQL
      ✅ 완료

다음 단계
      ↓
AWS Step Functions
      ↓
EventBridge Scheduler
```

---

## 3. 프로젝트 구조

```text
data-collection-pipeline/
│
├─ .github/
│  └─ workflows/
│     └─ ci.yml
│
├─ events/
│  ├─ crawling-event.json
│  ├─ extract-event.json
│  ├─ preprocess-event.json
│  └─ load-event.json
│
├─ handlers/
│  ├─ __init__.py
│  ├─ crawling_handler.py
│  ├─ extract_handler.py
│  ├─ preprocess_handler.py
│  └─ load_handler.py
│
├─ src/
│  └─ data_collection_pipeline/
│     ├─ __init__.py
│     ├─ config.py
│     ├─ crawling.py
│     ├─ database.py
│     ├─ extract.py
│     ├─ load.py
│     ├─ preprocess.py
│     └─ s3_storage.py
│
├─ tests/
│  ├─ test_crawling_handler.py
│  ├─ test_extract.py
│  ├─ test_extract_handler.py
│  ├─ test_preprocess.py
│  ├─ test_preprocess_handler.py
│  ├─ test_load_handler.py
│  ├─ test_database.py
│  └─ test_s3_storage.py
│
├─ data/                  # 로컬 실행 데이터, Git 제외
├─ docs/                  # 로컬 문서, 현재 Git 제외
├─ notebooks/             # 학습용 Notebook, Git 제외
│
├─ .env                   # 로컬 비밀정보, Git 제외
├─ .env.example
├─ .gitignore
├─ main.py
├─ pyproject.toml
├─ README.md
├─ requirements.txt
├─ requirements-dev.txt
├─ samconfig.toml         # 현재 Git 제외
└─ template.yaml
```

`.aws-sam/`, `.venv/`, `data/`, `.env` 등은 실행 환경 또는 빌드 산출물이므로 Git에서 제외합니다.

---

## 4. 주요 Python 모듈

### 4.1 `config.py`

프로젝트에서 공통으로 사용하는 경로, 웹 수집 설정, 시간대를 관리합니다.

주요 설정:

```text
PROJECT_DIR
DATA_DIR
RAW_HTML_DIR
INTERIM_DIR
PROCESSED_DIR
ENV_FILE
BASE_URL
SOURCE_SITE
START_PAGE
END_PAGE
CONNECT_TIMEOUT
READ_TIMEOUT
REQUEST_INTERVAL
HEADERS
APP_TIMEZONE
```

로컬 환경에서는 기본적으로 프로젝트의 `data/`를 사용합니다.

AWS Lambda에서는 `template.yaml`의 환경변수로 다음 값을 전달합니다.

```text
DATA_DIR=/tmp/data
```

따라서 같은 Python 모듈을 로컬과 Lambda에서 재사용할 수 있습니다.

시간대는 다음 기준을 사용합니다.

```text
Asia/Seoul
```

---

### 4.2 `crawling.py`

Books to Scrape 페이지를 순회하면서 HTTP 요청을 보내고 원본 HTML을 배치 단위로 저장합니다.

주요 역할:

```text
페이지 요청
→ HTTP 응답 검증
→ 배치 디렉터리 생성
→ 페이지별 Raw HTML 저장
```

로컬 출력 예:

```text
data/raw/html/20260830_163041/
├─ books_page_001.html
├─ books_page_002.html
└─ books_page_003.html
```

Lambda에서는 동일한 로직이 `/tmp/data/raw/html/{batch_id}/`에 임시 파일을 생성합니다.

---

### 4.3 `extract.py`

Raw HTML을 읽고 BeautifulSoup으로 필요한 도서 정보를 파싱하여 페이지별 CSV를 생성합니다.

주요 처리:

```text
Raw HTML 탐색
→ HTML 읽기
→ 도서 정보 파싱
→ DataFrame 생성
→ 데이터 검증
→ 페이지별 Parsed CSV 저장
```

로컬 출력 예:

```text
data/interim/20260830_163041/
├─ books_page_001_parsed.csv
├─ books_page_002_parsed.csv
└─ books_page_003_parsed.csv
```

---

### 4.4 `preprocess.py`

페이지별 Parsed CSV를 통합하고 문자열, 가격, 재고 상태, 자료형, 중복 등을 정리합니다.

주요 처리:

```text
페이지별 CSV 탐색
→ 페이지 순서 검증
→ CSV 통합
→ 문자열 정리
→ 가격 변환
→ 재고 상태 변환
→ 자료형 변환
→ book_id 생성
→ 메타데이터 추가
→ 중복 제거
→ 데이터 검증
→ Processed CSV 저장
```

로컬 파이프라인에서는 `run_preprocess()`가 직접 실행되고, AWS 환경에서는 `preprocess_handler.py`가 S3 Interim 데이터를 내려받아 기존 `run_preprocess()`를 재사용합니다.

---

### 4.5 `database.py`

MySQL 연결 설정과 SQLAlchemy Engine 생성을 담당합니다.

로컬에서는 `.env`를 사용하고, AWS Lambda에서는 `DB_SECRET_ARN` 환경변수가 존재하면 AWS Secrets Manager의 RDS 관리형 Secret을 사용합니다.

주요 함수:

```text
load_database_config()
    실행 환경에 따라 DB 연결정보 구성

load_database_config_from_secret()
    Secrets Manager와 Lambda 환경변수로 RDS 연결정보 구성

create_mysql_engine()
    SQLAlchemy + PyMySQL Engine 생성

test_mysql_connection()
    MySQL 연결 및 서버 정보 확인
```

로컬 환경:

```text
.env
├─ DB_HOST
├─ DB_PORT
├─ DB_NAME
├─ DB_USER
└─ DB_PASSWORD
```

AWS Lambda 환경:

```text
Lambda Environment
├─ DB_HOST
├─ DB_PORT
├─ DB_NAME
└─ DB_SECRET_ARN
        ↓
AWS Secrets Manager
├─ username
└─ password
```

---

### 4.6 `load.py`

Processed CSV를 읽고 검증한 뒤 MySQL `books` 테이블에 UPSERT 방식으로 저장합니다.

주요 처리:

```text
Processed CSV 입력
→ 파일명 및 배치 검증
→ DB 저장용 자료형 변환
→ 실행 환경에 맞는 DB 연결정보 구성
→ MySQL 연결
→ books 테이블 생성
→ UPSERT
→ SELECT COUNT(*)로 실제 저장 건수 확인
```

로컬에서는 `.env` 기반 MySQL 연결을 사용하고, AWS Lambda에서는 Secrets Manager 기반 RDS MySQL 연결을 사용합니다. `run_load()`는 로컬과 Lambda에서 동일하게 재사용됩니다.

---

### 4.7 `s3_storage.py`

AWS Lambda 단계에서 사용하는 Amazon S3 입출력 기능을 담당합니다.

현재 구현 함수:

```text
upload_raw_html_batch()
    Crawling 결과 HTML → S3 raw 영역 업로드

download_raw_html_batch()
    S3 raw HTML → Extract Lambda /tmp 다운로드

upload_interim_files()
    Extract 결과 CSV → S3 interim 영역 업로드

download_interim_batch()
    S3 interim CSV → Preprocess Lambda /tmp 다운로드

upload_processed_file()
    Preprocess 결과 CSV → S3 processed 영역 업로드

download_processed_file()
    S3 processed CSV → Load Lambda /tmp 다운로드
```

S3 Object Key 예:

```text
raw/20260830_163041/books_page_001.html
raw/20260830_163041/books_page_002.html
raw/20260830_163041/books_page_003.html

interim/20260830_163041/books_page_001_parsed.csv
interim/20260830_163041/books_page_002_parsed.csv
interim/20260830_163041/books_page_003_parsed.csv

processed/20260830_163041/books_pages_001_003_processed_20260830_163041.csv
```

---

## 5. Lambda Handler

### 5.1 `crawling_handler.py`

Crawling Lambda의 실행 진입점입니다.

입력 Event 예:

```json
{
  "start_page": 1,
  "end_page": 3
}
```

처리 흐름:

```text
Lambda Event
      ↓
start_page / end_page 확인
      ↓
run_crawling()
      ↓
/tmp에 Raw HTML 생성
      ↓
upload_raw_html_batch()
      ↓
S3 raw/{batch_id}/ 저장
```

반환 예:

```json
{
  "stage": "crawling",
  "status": "SUCCEEDED",
  "batch_id": "20260830_163041",
  "start_page": 1,
  "end_page": 3,
  "bucket": "<data-bucket-name>",
  "raw_prefix": "raw/20260830_163041/",
  "object_count": 3,
  "request_id": "..."
}
```

`bucket`, `raw_prefix`, `batch_id`는 다음 Extract 단계가 S3 데이터를 찾기 위한 메타데이터입니다.

---

### 5.2 `extract_handler.py`

Extract Lambda의 실행 진입점입니다.

입력 Event 예:

```json
{
  "batch_id": "20260830_163041",
  "bucket": "<data-bucket-name>",
  "raw_prefix": "raw/20260830_163041/"
}
```

처리 흐름:

```text
Lambda Event
      ↓
batch_id / bucket / raw_prefix 검증
      ↓
S3 Raw HTML 다운로드
      ↓
/tmp/data/raw/html/{batch_id}/
      ↓
run_extract()
      ↓
Parsed CSV 생성
      ↓
S3 interim/{batch_id}/ 업로드
```

반환 예:

```json
{
  "stage": "extract",
  "status": "SUCCEEDED",
  "batch_id": "20260830_163041",
  "bucket": "<data-bucket-name>",
  "raw_prefix": "raw/20260830_163041/",
  "interim_prefix": "interim/20260830_163041/",
  "object_count": 3,
  "request_id": "..."
}
```

향후 Step Functions에서는 이 반환값의 메타데이터를 다음 단계로 전달할 예정입니다.


### 5.3 `preprocess_handler.py`

Preprocess Lambda의 실행 진입점입니다.

입력 Event 예:

```json
{
  "batch_id": "20260901_035140",
  "bucket": "<data-bucket-name>",
  "interim_prefix": "interim/20260901_035140/"
}
```

처리 흐름:

```text
Lambda Event
      ↓
batch_id / bucket / interim_prefix 검증
      ↓
S3 Interim CSV 다운로드
      ↓
/tmp/data/interim/{batch_id}/
      ↓
run_preprocess()
      ↓
Processed CSV 생성
      ↓
S3 processed/{batch_id}/ 업로드
```

반환 예:

```json
{
  "stage": "preprocess",
  "status": "SUCCEEDED",
  "batch_id": "20260901_035140",
  "bucket": "<data-bucket-name>",
  "interim_prefix": "interim/20260901_035140/",
  "processed_prefix": "processed/20260901_035140/",
  "processed_key": "processed/20260901_035140/books_pages_001_003_processed_20260901_035140.csv",
  "request_id": "..."
}
```

`processed_key`는 다음 Load 단계에서 처리할 Processed CSV 객체를 정확하게 지정하기 위한 메타데이터입니다.

### 5.4 `load_handler.py`

Load Lambda의 실행 진입점입니다.

입력 Event 예:

```json
{
  "batch_id": "20260901_035140",
  "bucket": "<data-bucket-name>",
  "processed_key": "processed/20260901_035140/books_pages_001_003_processed_20260901_035140.csv"
}
```

처리 흐름:

```text
Lambda Event
      ↓
batch_id / bucket / processed_key 검증
      ↓
S3 Processed CSV 다운로드
      ↓
/tmp/data/processed/
      ↓
run_load()
      ↓
Secrets Manager 자격 증명 조회
      ↓
Amazon RDS MySQL 연결
      ↓
books 테이블 생성 / UPSERT
      ↓
실제 저장 건수 확인
```

Load 결과에는 `input_count`, `affected_row_count`, `stored_book_count`가 포함됩니다.


---

## 6. S3 데이터 구조

AWS 파이프라인의 데이터 Bucket은 현재 다음 구조를 사용합니다.

```text
DataBucket
│
├─ raw/
│  └─ {batch_id}/
│     ├─ books_page_001.html
│     ├─ books_page_002.html
│     └─ books_page_003.html
│
├─ interim/
│  └─ {batch_id}/
│     ├─ books_page_001_parsed.csv
│     ├─ books_page_002_parsed.csv
│     └─ books_page_003_parsed.csv
│
└─ processed/
   └─ {batch_id}/
      └─ books_pages_001_003_processed_{batch_id}.csv
```

S3 콘솔에서 보이는 `raw/`, `interim/`, `processed/`는 일반 파일시스템의 실제 디렉터리가 아니라 Object Key의 Prefix입니다.

---

## 7. 배치 관리

한 번의 수집 실행은 하나의 `batch_id`로 관리합니다.

형식:

```text
YYYYMMDD_HHMMSS
```

예:

```text
20260830_163041
```

동일한 `batch_id`를 단계별 S3 Prefix에 사용합니다.

```text
raw/20260830_163041/
interim/20260830_163041/
processed/20260830_163041/
```

이를 통해 한 번의 데이터 수집 작업이 다음 단계로 어떻게 처리되었는지 추적할 수 있습니다.

---

## 8. AWS SAM 구성

AWS 리소스는 프로젝트 루트의 `template.yaml`에서 정의합니다.

현재 주요 리소스:

```text
Resources
├─ DataBucket
├─ CrawlingFunction
├─ ExtractFunction
├─ PreprocessFunction
└─ LoadFunction
```

### `DataBucket`

파이프라인의 Raw HTML, Interim CSV, Processed CSV를 저장하는 S3 Bucket입니다.

CloudFormation이 Bucket 이름을 자동 생성하므로 특정 Bucket 이름을 코드에 고정하지 않습니다.

### `CrawlingFunction`

```text
FunctionName: books-pipeline-crawling
Runtime: Python 3.13
Memory: 512 MB
Timeout: 60 sec
DATA_DIR: /tmp/data
```

S3 Raw 데이터를 쓰기 위해 `S3WritePolicy`를 사용합니다.

### `ExtractFunction`

```text
FunctionName: books-pipeline-extract
Runtime: Python 3.13
Memory: 512 MB
Timeout: 60 sec
DATA_DIR: /tmp/data
```

Raw HTML을 읽고 Interim CSV를 저장하기 위해 `S3ReadPolicy`, `S3WritePolicy`를 사용합니다.

### `PreprocessFunction`

```text
FunctionName: books-pipeline-preprocess
Runtime: Python 3.13
Memory: 512 MB
Timeout: 60 sec
DATA_DIR: /tmp/data
```

Interim CSV를 읽고 Processed CSV를 저장하기 위해 `S3ReadPolicy`, `S3WritePolicy`를 사용합니다.

### `LoadFunction`

```text
FunctionName: books-pipeline-load
Runtime: Python 3.13
Memory: 512 MB
Timeout: 60 sec
DATA_DIR: /tmp/data
DB_HOST: <RDS Endpoint>
DB_PORT: 3306
DB_NAME: booksdb
DB_SECRET_ARN: <RDS Managed Secret ARN>
```

Processed CSV를 S3에서 읽고 Amazon RDS MySQL에 적재합니다.

주요 권한 및 설정:

```text
S3ReadPolicy
→ Processed CSV 다운로드

secretsmanager:GetSecretValue
→ RDS 관리형 Secret 조회

AWSLambdaVPCAccessExecutionRole
→ Load Lambda VPC 연결

VpcConfig
→ RDS와 동일 VPC의 Subnet / Security Group 사용
```

계정마다 달라지는 RDS Endpoint, Secret ARN, Subnet ID, Security Group ID는 SAM Parameter로 전달합니다.


---

## 9. Amazon RDS 및 VPC 네트워크 구성

Load Lambda는 Private Amazon RDS MySQL에 접근하기 위해 VPC에 연결합니다.

```text
                         VPC
        ┌──────────────────────────────────┐
        │ Load Lambda                      │
        │ [books-pipeline-lambda-sg]       │
        │        │                         │
        │        ├── TCP 3306 ───────→ RDS│
        │        │                         │
        │        ├── S3 Gateway Endpoint ──┼──→ Amazon S3
        │        │                         │
        │        └── HTTPS 443             │
        │                 ↓                │
        │      Secrets Manager             │
        │      Interface Endpoint          │
        └──────────────────────────────────┘
```

```text
RDS Public Access
→ No

RDS Security Group
→ TCP 3306
→ Source: books-pipeline-lambda-sg

S3 접근
→ Gateway VPC Endpoint

Secrets Manager 접근
→ Interface VPC Endpoint
→ HTTPS 443
```

RDS 마스터 자격 증명은 AWS Secrets Manager에서 관리하며 Lambda 코드에 사용자 이름과 비밀번호를 직접 저장하지 않습니다.

---

## 10. SAM 관리 S3와 데이터 S3의 차이

AWS 계정에는 SAM 배포 후 서로 다른 목적의 S3 Bucket이 보일 수 있습니다.

```text
aws-sam-cli-managed-default-samclisourcebucket-...
```

이 Bucket은 **SAM CLI 배포 아티팩트 저장용**입니다.

```text
로컬 소스
   ↓
sam build
   ↓
Lambda 배포 패키지
   ↓
SAM 관리 S3 Bucket
   ↓
CloudFormation
   ↓
Lambda
```

반면 `DataBucket`은 애플리케이션 데이터 저장용입니다.

```text
Crawling Lambda
      ↓
DataBucket/raw/
      ↓
Extract Lambda
      ↓
DataBucket/interim/
      ↓
Preprocess Lambda
      ↓
DataBucket/processed/
```

두 Bucket의 목적을 구분하여 사용합니다.

---

## 11. 환경 구성

### 10.1 가상환경 생성

프로젝트 루트에서:

```bash
python -m venv .venv
```

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

Git Bash:

```bash
source .venv/Scripts/activate
```

### 10.2 실행 패키지 설치

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

현재 주요 실행 의존성:

```text
requests
pandas
beautifulsoup4
python-dotenv
SQLAlchemy
PyMySQL
```

### 10.3 개발 및 테스트 패키지 설치

```bash
python -m pip install -r requirements-dev.txt
```

추가 개발 의존성:

```text
pytest
ruff
```

### 10.4 `.env` 설정

`.env.example`을 참고하여 로컬 `.env`를 작성합니다.

```env
DB_HOST=
DB_PORT=
DB_NAME=
DB_USER=
DB_PASSWORD=
```

`.env`는 Git에 커밋하지 않습니다.

---

## 12. 로컬 파이프라인 실행

```bash
python main.py
```

실행 흐름:

```text
main.py
  │
  ├─ run_crawling()
  │      ↓
  │   raw_batch_dir
  │
  ├─ run_extract(raw_batch_dir)
  │      ↓
  │   parsed_csv_files
  │
  ├─ run_preprocess(interim_batch_dir)
  │      ↓
  │   processed_csv_file
  │
  └─ run_load(processed_csv_file)
         ↓
      load_summary
```

---

## 13. 테스트와 코드 품질 검사

### pytest

```bash
python -m pytest -v
```

현재 테스트 구성:

```text
test_extract.py
    Extract 관련 파일명/배치 파싱 테스트

test_preprocess.py
    Preprocess 변환 및 파일 경로 테스트

test_crawling_handler.py
    Crawling Lambda Handler 단위 테스트

test_extract_handler.py
    Extract Lambda Handler 단위 테스트

test_preprocess_handler.py
    Preprocess Lambda Handler 단위 테스트

test_load_handler.py
    Load Lambda Handler 입력 검증 및 실행 흐름 테스트

test_database.py
    로컬 .env 및 Secrets Manager 기반 DB 설정 테스트

test_s3_storage.py
    S3 Raw / Interim / Processed 입출력 기능 단위 테스트
```

AWS 호출을 직접 수행하지 않는 테스트에서는 Mock을 사용하여 외부 의존성을 분리합니다.

### Ruff

```bash
python -m ruff check .
```

`pyproject.toml`의 주요 설정:

```text
Python: 3.13
line-length: 100
규칙: E4, E7, E9, F, I, DTZ, RUF
```

---

## 14. GitHub Actions CI

Workflow 위치:

```text
.github/workflows/ci.yml
```

실행 조건:

```text
main branch push
또는
main branch 대상 pull_request
```

현재 CI 흐름:

```text
GitHub Push / Pull Request
        ↓
Checkout Repository
        ↓
Python 3.13 설정
        ↓
requirements-dev.txt 설치
        ↓
Ruff 검사
        ↓
pytest 실행
        ↓
CI 성공 / 실패
```

현재 GitHub Actions는 **CI 코드 검사와 테스트**를 담당합니다. AWS 배포는 아직 `sam deploy`를 이용해 수동으로 수행합니다.

---

## 15. AWS SAM 빌드 및 배포

프로젝트 파일 또는 `template.yaml`을 수정한 뒤 다음 순서로 검증합니다.

```bash
python -m ruff check .
python -m pytest -v
sam validate
sam build
sam deploy
```

역할:

```text
sam validate
→ SAM Template 문법/구조 검증

sam build
→ Lambda 실행 코드와 의존성을 .aws-sam/build에 구성

sam deploy
→ 배포 아티팩트를 S3에 업로드하고 CloudFormation Stack 업데이트
```

현재 Stack 이름:

```text
books-pipeline
```

현재 Region:

```text
ap-northeast-2
```

---

## 16. Lambda 원격 호출

### 16.1 Crawling Lambda

`events/crawling-event.json`:

```json
{
  "start_page": 1,
  "end_page": 3
}
```

호출:

```powershell
sam remote invoke CrawlingFunction `
  --stack-name books-pipeline `
  --event-file events/crawling-event.json
```

정상 실행 후 S3에서 다음 Prefix를 확인합니다.

```text
raw/{batch_id}/
```

### 16.2 Extract Lambda

`events/extract-event.json`은 **직전 Crawling Lambda의 실제 반환값**을 기준으로 작성합니다.

```json
{
  "batch_id": "<actual-batch-id>",
  "bucket": "<actual-data-bucket-name>",
  "raw_prefix": "raw/<actual-batch-id>/"
}
```

호출:

```powershell
sam remote invoke ExtractFunction `
  --stack-name books-pipeline `
  --event-file events/extract-event.json
```

정상 실행 후 S3에서 다음 Prefix를 확인합니다.

```text
interim/{batch_id}/
```

### 16.3 Preprocess Lambda

`events/preprocess-event.json`은 **직전 Extract Lambda의 실제 반환값과 S3 Interim 경로**를 기준으로 작성합니다.

```json
{
  "batch_id": "<actual-batch-id>",
  "bucket": "<actual-data-bucket-name>",
  "interim_prefix": "interim/<actual-batch-id>/"
}
```

호출:

```powershell
sam remote invoke PreprocessFunction `
  --stack-name books-pipeline `
  --event-file events/preprocess-event.json
```

정상 실행 후 S3에서 다음 Prefix와 Processed CSV를 확인합니다.

```text
processed/{batch_id}/
```

### 16.4 Load Lambda

`events/load-event.json`은 **직전 Preprocess Lambda의 실제 반환값**을 기준으로 작성합니다.

```json
{
  "batch_id": "<actual-batch-id>",
  "bucket": "<actual-data-bucket-name>",
  "processed_key": "processed/<actual-batch-id>/<processed-file-name>.csv"
}
```

호출:

```powershell
sam remote invoke LoadFunction `
  --stack-name books-pipeline `
  --event-file events/load-event.json
```

정상 실행 시 `database_name`, `input_count`, `affected_row_count`, `stored_book_count`를 확인합니다.

`sam remote invoke`는 로컬 코드를 실행하는 명령이 아니라, **로컬 SAM CLI를 이용해 AWS에 배포된 Lambda를 원격 호출하는 명령**입니다.

---

## 17. Lambda `/var/task`와 `/tmp`

Lambda 실행 환경에서 주요 경로의 역할은 다음과 같습니다.

```text
/var/task
→ 배포된 Lambda 코드와 패키지가 위치하는 실행 기준 경로

/tmp
→ Lambda 실행 중 파일을 임시 저장할 수 있는 쓰기 가능한 영역
```

현재 Lambda에서는:

```text
DATA_DIR=/tmp/data
```

를 사용합니다.

Crawling Lambda가 `/tmp`에 만든 파일은 다른 Lambda가 직접 접근할 수 없으므로 S3에 업로드합니다.

```text
Crawling Lambda /tmp
        ↓
Amazon S3
        ↓
Extract Lambda /tmp
```

이 구조를 통해 서로 독립적인 Lambda 실행 환경 사이에서 데이터를 전달합니다.

---

## 18. Git 관리 정책

이 프로젝트는 블랙리스트 방식의 `.gitignore`를 사용합니다.

주요 제외 대상:

```text
.env
.env.*
data/
logs/
*.log
docs/
notebooks/

__pycache__/
.pytest_cache/
.ruff_cache/

.venv/
venv/

.vscode/
.idea/

build/
dist/
.aws-sam/
samconfig.toml
```

`.env.example`은 실제 비밀번호가 포함되지 않은 환경설정 예제이므로 Git에서 추적합니다.

---



## 19. 현재 구현 상태

### 완료

```text
[Local]
Crawling
→ Extract
→ Preprocess
→ Load
→ MySQL

[Code Quality / CI]
pytest
→ Ruff
→ GitHub Actions CI

[AWS]
AWS SAM
→ CloudFormation
→ Crawling Lambda
→ S3 Raw 저장
→ Extract Lambda
→ S3 Interim 저장
→ Preprocess Lambda
→ S3 Processed 저장
→ Load Lambda
→ Amazon RDS MySQL
→ Secrets Manager 기반 자격 증명 조회
→ S3 Gateway VPC Endpoint
→ Secrets Manager Interface VPC Endpoint
```

### 다음 구현 단계

```text
AWS Step Functions
      ↓
Crawling Lambda
      ↓
Extract Lambda
      ↓
Preprocess Lambda
      ↓
Load Lambda
```

그 이후에는 EventBridge Scheduler를 연결하여 전체 파이프라인을 정기 실행 구조로 확장할 예정입니다.

```text
EventBridge Scheduler
        ↓
Step Functions
        ↓
Crawling Lambda
        ↓
S3 Raw
        ↓
Extract Lambda
        ↓
S3 Interim
        ↓
Preprocess Lambda
        ↓
S3 Processed
        ↓
Load Lambda
        ↓
RDS MySQL
```

---

## 20. 설계 원칙

- 원본 데이터는 `raw` 영역에 보관합니다.
- 한 번의 수집 실행을 하나의 `batch_id`로 관리합니다.
- 단계 간 대용량 데이터는 S3에 저장합니다.
- Lambda 간에는 `batch_id`, `bucket`, `prefix` 등의 메타데이터를 전달합니다.
- Lambda의 `/tmp`는 임시 작업 공간으로만 사용합니다.
- 각 Lambda Handler는 실행 제어에 집중하고 실제 데이터 처리 로직은 `src/` 모듈을 재사용합니다.
- 공통 설정은 `config.py`에서 관리합니다.
- 데이터베이스 연결 책임은 `database.py`에서 관리합니다.
- 로컬에서는 `.env`, AWS Lambda에서는 Secrets Manager를 사용하여 DB 자격 증명을 분리합니다.
- Amazon RDS는 Public Access를 사용하지 않고 Load Lambda와 동일 VPC에서 접근합니다.
- S3는 Gateway VPC Endpoint, Secrets Manager는 Interface VPC Endpoint를 사용합니다.
- AWS S3 입출력 책임은 `s3_storage.py`에서 관리합니다.
- 테스트에서는 외부 네트워크 및 AWS 의존성을 가능한 한 Mock으로 분리합니다.
- 로컬과 CI에서 동일한 Ruff/pytest 명령을 사용합니다.
- AWS 리소스는 `template.yaml`을 기준으로 재현 가능하게 관리합니다.
