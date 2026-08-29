-- PH Job Market Pipeline PostgreSQL Schema DDL

-- 1. Companies Table
CREATE TABLE IF NOT EXISTS companies (
    company_id VARCHAR(100) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    industry VARCHAR(100),
    location VARCHAR(150),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 2. Jobs Table
CREATE TABLE IF NOT EXISTS jobs (
    job_id VARCHAR(100) PRIMARY KEY,
    title VARCHAR(255) NOT NULL,
    company_id VARCHAR(100) REFERENCES companies(company_id) ON DELETE SET NULL,
    company_name VARCHAR(255),
    location VARCHAR(150),
    region VARCHAR(100),
    work_setup VARCHAR(50) CHECK (work_setup IN ('Remote', 'Hybrid', 'On-site', 'Unknown')),
    salary_min NUMERIC(12, 2),
    salary_max NUMERIC(12, 2),
    salary_currency VARCHAR(10) DEFAULT 'PHP',
    salary_php_equiv NUMERIC(12, 2),
    experience_level VARCHAR(50) CHECK (experience_level IN ('Entry-level', 'Mid-level', 'Senior', 'Lead/Executive', 'Unspecified')),
    employment_type VARCHAR(50),
    description TEXT,
    source VARCHAR(50),
    posted_date DATE,
    scraped_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- 3. Skills Taxonomy Table
CREATE TABLE IF NOT EXISTS skills (
    skill_id VARCHAR(50) PRIMARY KEY,
    skill_name VARCHAR(100) UNIQUE NOT NULL,
    category VARCHAR(50) NOT NULL
);

-- 4. Job-Skill Junction Table
CREATE TABLE IF NOT EXISTS job_skills (
    job_id VARCHAR(100) REFERENCES jobs(job_id) ON DELETE CASCADE,
    skill_id VARCHAR(50) REFERENCES skills(skill_id) ON DELETE CASCADE,
    PRIMARY KEY (job_id, skill_id)
);

-- 5. Performance Indexes
CREATE INDEX IF NOT EXISTS idx_jobs_posted_date ON jobs(posted_date);
CREATE INDEX IF NOT EXISTS idx_jobs_work_setup ON jobs(work_setup);
CREATE INDEX IF NOT EXISTS idx_jobs_region ON jobs(region);
CREATE INDEX IF NOT EXISTS idx_jobs_company ON jobs(company_id);
CREATE INDEX IF NOT EXISTS idx_job_skills_skill ON job_skills(skill_id);

-- 6. Pre-seeded Skills Taxonomy
INSERT INTO skills (skill_id, skill_name, category) VALUES
    ('sk_python', 'Python', 'Programming'),
    ('sk_javascript', 'JavaScript', 'Programming'),
    ('sk_typescript', 'TypeScript', 'Programming'),
    ('sk_sql', 'SQL', 'Database'),
    ('sk_postgresql', 'PostgreSQL', 'Database'),
    ('sk_mysql', 'MySQL', 'Database'),
    ('sk_react', 'React', 'Framework'),
    ('sk_node', 'Node.js', 'Framework'),
    ('sk_vue', 'Vue.js', 'Framework'),
    ('sk_django', 'Django', 'Framework'),
    ('sk_fastapi', 'FastAPI', 'Framework'),
    ('sk_aws', 'AWS', 'Cloud/DevOps'),
    ('sk_docker', 'Docker', 'Cloud/DevOps'),
    ('sk_kubernetes', 'Kubernetes', 'Cloud/DevOps'),
    ('sk_gcp', 'Google Cloud', 'Cloud/DevOps'),
    ('sk_pandas', 'Pandas', 'Data/AI'),
    ('sk_pyspark', 'PySpark', 'Data/AI'),
    ('sk_tableau', 'Tableau', 'Data/AI'),
    ('sk_powerbi', 'Power BI', 'Data/AI'),
    ('sk_git', 'Git', 'Tool'),
    ('sk_english', 'English Communication', 'Soft Skill')
ON CONFLICT (skill_id) DO NOTHING;
