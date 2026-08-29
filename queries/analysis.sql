-- ==============================================================================
-- PH Job Market Analysis SQL Queries
-- Database Target: PostgreSQL / SQLite
-- Description: Analytical queries for extracting tech demand, compensation trends,
--              work setup distribution, and regional hiring insights in PH.
-- ==============================================================================

-- Query 1: Top 15 Most Demanded Tech & Soft Skills in PH
SELECT 
    s.skill_name,
    s.category,
    COUNT(js.job_id) AS total_job_postings,
    ROUND(COUNT(js.job_id) * 100.0 / (SELECT COUNT(*) FROM jobs), 2) AS market_demand_pct
FROM skills s
JOIN job_skills js ON s.skill_id = js.skill_id
GROUP BY s.skill_id, s.skill_name, s.category
ORDER BY total_job_postings DESC
LIMIT 15;


-- Query 2: Salary Compensation Breakdown by Experience Level
SELECT 
    experience_level,
    COUNT(*) AS total_postings,
    ROUND(AVG(salary_php_equiv), 2) AS avg_monthly_salary_php,
    ROUND(MIN(salary_php_equiv), 2) AS min_monthly_salary_php,
    ROUND(MAX(salary_php_equiv), 2) AS max_monthly_salary_php
FROM jobs
WHERE salary_php_equiv IS NOT NULL
GROUP BY experience_level
ORDER BY avg_monthly_salary_php DESC;


-- Query 3: Remote vs. Hybrid vs. On-site Work Setup & Salary Comparison
SELECT 
    work_setup,
    COUNT(*) AS job_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM jobs), 2) AS setup_share_pct,
    ROUND(AVG(salary_php_equiv), 2) AS avg_monthly_salary_php
FROM jobs
GROUP BY work_setup
ORDER BY job_count DESC;


-- Query 4: Geographic Hiring Distribution across Philippine Regions
SELECT 
    region,
    COUNT(*) AS posting_count,
    ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM jobs), 2) AS regional_share_pct,
    ROUND(AVG(salary_php_equiv), 2) AS avg_monthly_salary_php
FROM jobs
GROUP BY region
ORDER BY posting_count DESC;


-- Query 5: Top Highest-Paying Tech Skills (Minimum 2 Job References)
SELECT 
    s.skill_name,
    s.category,
    COUNT(js.job_id) AS job_sample_size,
    ROUND(AVG(j.salary_php_equiv), 2) AS avg_skill_salary_php
FROM skills s
JOIN job_skills js ON s.skill_id = js.skill_id
JOIN jobs j ON js.job_id = j.job_id
WHERE j.salary_php_equiv IS NOT NULL
GROUP BY s.skill_id, s.skill_name, s.category
HAVING COUNT(js.job_id) >= 2
ORDER BY avg_skill_salary_php DESC
LIMIT 10;


-- Query 6: Top Tech Stack for Remote Work Setup
SELECT 
    s.skill_name,
    COUNT(js.job_id) AS remote_job_count
FROM jobs j
JOIN job_skills js ON j.job_id = js.job_id
JOIN skills s ON js.skill_id = s.skill_id
WHERE j.work_setup = 'Remote'
GROUP BY s.skill_name
ORDER BY remote_job_count DESC
LIMIT 10;


-- Query 7: Top Hiring Companies by Job Volume
SELECT 
    c.name AS company_name,
    c.industry,
    COUNT(j.job_id) AS open_positions,
    ROUND(AVG(j.salary_php_equiv), 2) AS avg_offered_salary_php
FROM companies c
JOIN jobs j ON c.company_id = j.company_id
GROUP BY c.company_id, c.name, c.industry
ORDER BY open_positions DESC
LIMIT 10;
