-- PH Job Market Analytics Pipeline — Schema
-- Auto-runs on first container init via docker-entrypoint-initdb.d

CREATE TABLE companies (
    company_id      SERIAL PRIMARY KEY,
    name            VARCHAR(255) NOT NULL UNIQUE,
    industry        VARCHAR(100)          -- e.g. 'BPO', 'Banking', 'Tech', 'Telco' — powers Query 4's PARTITION BY
);

CREATE TABLE job_postings (
    job_id              SERIAL PRIMARY KEY,
    title               VARCHAR(255) NOT NULL,
    company_id          INTEGER REFERENCES companies(company_id),
    location            VARCHAR(255),
    salary_monthly_php  NUMERIC(10,2),     -- normalized midpoint during transform; NULL if source omitted it
    level               VARCHAR(20) CHECK (level IN ('entry', 'mid', 'senior', 'unspecified')),
    posted_date         DATE,
    source_url          TEXT UNIQUE,       -- also your dedup key
    raw_description     TEXT,
    scraped_at          TIMESTAMP DEFAULT NOW()
);

CREATE TABLE skills (
    skill_id        SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE   -- canonicalized: always 'SQL', never 'sql' / 'Sql'
);

CREATE TABLE job_skills (
    job_id          INTEGER REFERENCES job_postings(job_id) ON DELETE CASCADE,
    skill_id        INTEGER REFERENCES skills(skill_id) ON DELETE CASCADE,
    PRIMARY KEY (job_id, skill_id)
);

CREATE INDEX idx_job_postings_company ON job_postings(company_id);
CREATE INDEX idx_job_postings_level ON job_postings(level);
CREATE INDEX idx_job_skills_skill ON job_skills(skill_id);
