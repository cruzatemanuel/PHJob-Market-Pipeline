# PH Job Market Analytics Pipeline — Step-by-Step Execution Guide

> **Project Goal**: Build an end-to-end Data Engineering pipeline that retrieves Philippine tech job postings through official APIs, cleans and normalizes raw data, loads it into a PostgreSQL relational data warehouse, performs SQL analytics, and outputs data visualizations.
>
> **Target Duration**: 5 Weeks

---

## 🗂️ Project Architecture & Repository Blueprint

```text
ph-job-market-pipeline/
├── .env.example              # Template for environment configuration
├── .env                      # Secrets & DB credentials (gitignored)
├── .gitignore                # Git exclusions (data/raw/*.json, .env, venv)
├── README.md                 # Project documentation & key analytics findings
├── STEP_BY_STEP_GUIDE.md     # Detailed step-by-step build roadmap
├── docker-compose.yml        # PostgreSQL 16 service definition
├── requirements.txt          # Python dependencies
├── data/
│   └── raw/                  # API JSON snapshots (gitignored)
├── db/
│   └── schema.sql            # DDL for companies, job_postings, skills, job_skills
├── src/
│   ├── scrape.py             # Jooble API client and mock data generator
│   ├── transform_load.py     # Pandas + SQLAlchemy ETL pipeline
│   └── generate_charts.py    # Matplotlib chart generator
├── queries/
│   └── analysis.sql          # 5 Core SQL analytical queries
├── charts/                   # Output PNG charts (top_skills, avg_salary, etc.)
└── tests/
    └── validate_load.py      # Automated data integrity & sanity assertions
```

---

## 🗺️ Master Execution Plan Checklist

- [ ] **Phase 0: Project Setup & Data Source Decision**
  - [ ] Step 0.1: Select Primary Data Source & Plan Fallback
  - [x] Step 0.2: Directory Scaffolding & Initial Git Repo Setup
- [ ] **Phase 1: Foundation (Environment, Docker & Database Schema)**
  - [x] Step 1.1: Create `.gitignore`
  - [x] Step 1.2: Create `.env.example` & `.env`
  - [x] Step 1.3: Define `requirements.txt` & Setup Virtual Environment
  - [ ] Step 1.4: Define `docker-compose.yml` for PostgreSQL 16
  - [ ] Step 1.5: Draft `db/schema.sql` (DDL with constraints & indexes)
  - [ ] Step 1.6: Launch Docker Container & Verify DB Schema Ingestion
  - [ ] Step 1.7: Git Commit & Merge `feature/db-schema`
- [ ] **Phase 2: Extract (Job APIs)**
  - [ ] Step 2.1: Register for the Jooble Philippines API and configure `.env`
  - [x] Step 2.2: Implement `src/scrape.py` with mock mode, Jooble pagination, and defensive API handling
  - [ ] Step 2.3: Define Jooble search scope and API page limits
  - [ ] Step 2.4: Execute Jooble collection and save JSON to `data/raw/`
  - [ ] Step 2.5: Verify Raw Data Integrity
  - [ ] Step 2.6: Git Commit & Merge `feature/scraper`
- [ ] **Phase 3: Transform & Load (ETL Pipeline)**
  - [ ] Step 3.1: Build `src/transform_load.py` (Cleaning & Regex Parsing)
  - [ ] Step 3.2: Configure `INDUSTRY_LOOKUP` for PH Employers
  - [ ] Step 3.3: Ingest Cleaned Data into PostgreSQL
  - [ ] Step 3.4: Create Automated Verification Script (`tests/validate_load.py`)
  - [ ] Step 3.5: Execute Data Verification Suite
  - [ ] Step 3.6: Git Commit & Merge `feature/transform-load`
- [ ] **Phase 4: Analytics & Visualization**
  - [ ] Step 4.1: Write `queries/analysis.sql` (5 Advanced SQL Queries)
  - [ ] Step 4.2: Execute & Validate Queries in DB Client
  - [ ] Step 4.3: Implement `src/generate_charts.py`
  - [ ] Step 4.4: Generate PNG Visualizations in `charts/`
  - [ ] Step 4.5: Git Commit & Merge `feature/analytics-charts`
- [ ] **Phase 5: Documentation, Polish & Release**
  - [ ] Step 5.1: Draft `README.md` with Key Findings & Mermaid Architecture Diagram
  - [ ] Step 5.2: End-to-End Fresh Deployment Verification
  - [ ] Step 5.3: Tag Release `v1.0` & Pin Repo on GitHub

---

## 📌 Phase-by-Phase Detailed Instructions

---

### Phase 0: Project Setup & Data Source Decision

#### Step 0.1: Select Data Source & Define Timebox Strategy
- **Goal**: Register a Jooble Philippines API key and lock the keyword/location scope.
- **Timebox**: 3 days maximum for API setup and a 50-record collection test.
- **Fallback Rule**: If the API key cannot be obtained or the results are insufficient, use the existing manual sample and document the limitation rather than automating an unapproved source.

#### Step 0.2: Initialize Repository & Workspace Folders
- **Command**:
  ```bash
  mkdir -p data/raw db src queries charts tests
  ```
- **Verification**: Run `ls -la` to confirm directory structure matches the blueprint.

---

### Phase 1: Foundation (Environment, Docker & Database Schema)

#### Step 1.1: Create `.gitignore`
- **File**: `.gitignore`
- **Action**: Add rules to exclude `.venv`, `.env`, `data/raw/*.json`, `__pycache__`, and OS files (`.DS_Store`).

#### Step 1.2: Create `.env.example` & `.env`
- **Files**: `.env.example` and `.env`
- **Variables**:
  ```env
  POSTGRES_USER=ph_job_market_user
  POSTGRES_PASSWORD=changeme
  POSTGRES_DB=ph_job_market
  POSTGRES_HOST=localhost
  POSTGRES_PORT=5433
  ```

#### Step 1.3: Define Dependencies & Setup Python Virtual Environment
- **File**: `requirements.txt`
  ```txt
requests==2.32.3
pandas==2.2.3
  SQLAlchemy==2.0.35
  psycopg2-binary==2.9.9
  python-dotenv==1.0.1
  matplotlib==3.9.2
  ```
- **Commands**:
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  pip install -r requirements.txt
  ```

#### Step 1.4: Define Docker Compose Service
- **File**: `docker-compose.yml`
- **Action**: Configure PostgreSQL 16 container, port mapping `5433:5432` (to avoid the local PostgreSQL service on port 5432), volume persistence `pgdata`, and mount `./db/schema.sql` to `/docker-entrypoint-initdb.d/schema.sql`.

#### Step 1.5: Create Database DDL (`db/schema.sql`)
- **File**: `db/schema.sql`
- **Tables**:
  1. `companies` (`company_id`, `name`, `industry`)
  2. `job_postings` (`job_id`, `title`, `company_id`, `location`, `salary_monthly_php`, `level`, `posted_date`, `source_url`, `raw_description`, `scraped_at`)
  3. `skills` (`skill_id`, `name`)
  4. `job_skills` (`job_id`, `skill_id`)
- **Indexes**: `idx_job_postings_company`, `idx_job_postings_level`, `idx_job_skills_skill`.

#### Step 1.6: Spin up Docker & Verify Schema Application
- **Command**:
  ```bash
  docker compose up -d
  ```
- **Verification**: Connect via DB client or psql:
  ```bash
  docker exec -it ph_job_market_db psql -U ph_job_market_user -d ph_job_market -c "\dt"
  ```
  Ensure all 4 tables are present.

#### Step 1.7: Git Commit & Merge Branch
- **Commands**:
  ```bash
  git checkout -b feature/db-schema
  git add .
  git commit -m "feat: setup project structure, docker-compose, and postgres db schema"
  git checkout main
  git merge feature/db-schema
  ```

---

### Phase 2: Data Extraction (Jooble API Integration)

#### Step 2.1: Register and Configure the Jooble Philippines API
- Register at [Jooble API registration](https://ph.jooble.org/api/about), then add the country-specific key to the untracked `.env` file as `JOOBLE_API_KEY`.
- Start with the provided `JOOBLE_KEYWORDS`, `JOOBLE_LOCATIONS`, and page-limit values in `.env.example`.

#### Step 2.2: Implement Scraper Script
- **File**: `src/scrape.py`
- **Key Features**:
  - Official Jooble REST API requests through `requests`
  - Keyword/location search scope and bounded pagination
  - Raw-field normalization for title, company, location, description snippet, salary, source, link, and update date
  - API-error handling that does not expose the key
  - Reproducible mock mode for local development
  - Output written to `data/raw/raw_jobs_YYYY-MM-DDTHHMMSSZ.json`

#### Step 2.3: Define API Search Scope
- Decide the initial keywords, locations, result count, and page cap in `.env`.
- Keep the first live run to 50 records and the default three pages per keyword/location to conserve the free API quota.

#### Step 2.4: Execute Jooble Collection
- **Command**:
  ```bash
  .venv/bin/python src/scrape.py --mode jooble --count 50
  ```

#### Step 2.5: Verify API Data
- Inspect generated JSON file in `data/raw/`.
- Ensure JSON contains valid array of objects with non-empty titles, companies, URLs, and descriptions.

#### Step 2.6: Git Branch & Merge
- **Commands**:
  ```bash
  git checkout -b feature/scraper
  git add src/scrape.py tests/test_scrape.py .env.example requirements.txt README.md
  git commit -m "feat: add Jooble Philippines API job collection"
  git checkout main
  git merge feature/scraper
  ```

---

### Phase 3: Data Transformation & Database Loading

#### Step 3.1: Build ETL Pipeline Script
- **File**: `src/transform_load.py`
- **Key Logic**:
  - `load_raw_files()`: Glob raw JSONs into Pandas DataFrame
  - Deduplication on `source_url`
  - `parse_salary()`: Regex extraction of PHP monthly salary numbers & midpoint calculation
  - `parse_posted_date()`: Relative date string conversion
  - `classify_level()`: Categorize into `entry`, `mid`, `senior`, or `unspecified` based on title/description keywords
  - `extract_skills()`: Standardize and normalize tech skills (SQL, Python, AWS, Docker, Power BI, Excel, etc.)
  - `tag_industry()`: Map company names to industry verticals (BPO, Banking, Telco, Tech)

#### Step 3.2: Configure `INDUSTRY_LOOKUP`
- Review unique companies extracted from raw data and update `INDUSTRY_LOOKUP` in `transform_load.py`.

#### Step 3.3: Execute Ingestion
- **Command**:
  ```bash
  python src/transform_load.py
  ```
- Verify batch insertion into PostgreSQL via SQLAlchemy engine with `ON CONFLICT` deduplication.

#### Step 3.4: Implement Data Integrity Assertions
- **File**: `tests/validate_load.py`
- **Checks**:
  1. `job_postings` count > 0
  2. `skills` count > 0
  3. `job_skills` count > 0
  4. Zero orphaned `job_id` references in `job_skills`
  5. Zero orphaned `skill_id` references in `job_skills`
  6. Zero NULL titles in `job_postings`

#### Step 3.5: Run Validation Suite
- **Command**:
  ```bash
  python tests/validate_load.py
  ```
- **Verification**: Must exit with code 0 and output `6 passed, 0 failed`.

#### Step 3.6: Git Branch & Merge
- **Commands**:
  ```bash
  git checkout -b feature/transform-load
  git add src/transform_load.py tests/validate_load.py
  git commit -m "feat: implement ETL cleaning pipeline and automated validation tests"
  git checkout main
  git merge feature/transform-load
  ```

---

### Phase 4: Analytics & Data Visualization

#### Step 4.1: Write SQL Queries
- **File**: `queries/analysis.sql`
- **Queries**:
  1. **Query 1**: Top 10 most demanded skills (`COUNT(*) GROUP BY skill`)
  2. **Query 2**: Average salary by skill (`AVG(salary_monthly_php)`)
  3. **Query 3**: Top 10 hiring companies for data roles (CTE filtering `%data%`, `%analyst%`, `%engineer%`, `%scientist%`)
  4. **Query 4**: Company salary rank per industry (Window function `RANK() OVER (PARTITION BY industry ORDER BY avg_salary DESC)`)
  5. **Query 5**: Entry-level vs mid-level skill gap (`CASE WHEN` pivot calculating demand delta)

#### Step 4.2: Validate SQL Query Execution
- Run queries in DB client or via `psql`:
  ```bash
  docker exec -i ph_job_market_db psql -U ph_job_market_user -d ph_job_market < queries/analysis.sql
  ```

#### Step 4.3: Implement Chart Generator Script
- **File**: `src/generate_charts.py`
- **Logic**: Use Matplotlib to fetch SQL results into DataFrames and save horizontal bar charts (`top_skills.png`, `avg_salary_by_skill.png`, `top_companies.png`) in `charts/`.

#### Step 4.4: Generate Charts
- **Command**:
  ```bash
  python src/generate_charts.py
  ```
- **Verification**: Check `charts/` directory for 3 high-resolution PNG image files.

#### Step 4.5: Git Branch & Merge
- **Commands**:
  ```bash
  git checkout -b feature/analytics-charts
  git add queries/analysis.sql src/generate_charts.py charts/
  git commit -m "feat: add analytics queries and automated chart generation script"
  git checkout main
  git merge feature/analytics-charts
  ```

---

### Phase 5: Documentation, Polish & Release

#### Step 5.1: Construct `README.md`
- **File**: `README.md`
- **Contents**:
  - Project Title & Summary
  - Executive Key Findings (populated with real numbers from Query 1-5)
  - Mermaid Architecture Diagram
  - Tech Stack List
  - Data Source & Scope
  - Step-by-Step "How to Run" Instructions
  - Data Quality Notes (missing salary percentages, parsing assumptions)
  - License (MIT)

#### Step 5.2: Perform Fresh Clean Test
- Run teardown and full rerun:
  ```bash
  docker compose down -v
  docker compose up -d
  python src/transform_load.py
  python tests/validate_load.py
  python src/generate_charts.py
  ```
- Confirm zero errors on clean environment restart.

#### Step 5.3: Tag & Publish Release
- **Commands**:
  ```bash
  git add README.md
  git commit -m "docs: finalize readme with findings and architecture diagram"
  git tag -a v1.0 -m "PH Tech Job Market Pipeline v1.0 Release"
  git push origin main --tags
  ```

---

## 🛠️ Appendix: Common Troubleshooting Commands

- **Reset Database Volume**:
  ```bash
  docker compose down -v && docker compose up -d
  ```
- **View Container Logs**:
  ```bash
  docker compose logs -f postgres
  ```
- **Check Port Binding Issues (Port 5432)**:
  ```bash
  lsof -i :5432
  ```
