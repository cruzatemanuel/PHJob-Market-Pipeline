-- ============================================================
-- Query 1: Top 10 most demanded skills
-- ============================================================
SELECT s.name AS skill, COUNT(*) AS posting_count
FROM job_skills js
JOIN skills s ON s.skill_id = js.skill_id
GROUP BY s.name
ORDER BY posting_count DESC
LIMIT 10;


-- ============================================================
-- Query 2: Average salary by skill
-- ============================================================
SELECT s.name AS skill,
       ROUND(AVG(jp.salary_monthly_php), 2) AS avg_salary_php,
       COUNT(*) AS postings_with_salary
FROM job_skills js
JOIN skills s ON s.skill_id = js.skill_id
JOIN job_postings jp ON jp.job_id = js.job_id
WHERE jp.salary_monthly_php IS NOT NULL
GROUP BY s.name
ORDER BY avg_salary_php DESC
LIMIT 10;


-- ============================================================
-- Query 3: Top 10 hiring companies for data roles (CTE)
-- ============================================================
WITH data_roles AS (
    SELECT * FROM job_postings
    WHERE title ILIKE '%data%' OR title ILIKE '%analyst%'
       OR title ILIKE '%engineer%' OR title ILIKE '%scientist%'
)
SELECT c.name AS company, COUNT(*) AS data_role_postings
FROM data_roles dr
JOIN companies c ON c.company_id = dr.company_id
GROUP BY c.name
ORDER BY data_role_postings DESC
LIMIT 10;


-- ============================================================
-- Query 4: Salary rank per company within industry (window function)
-- ============================================================
WITH company_avg_salary AS (
    SELECT c.company_id, c.name AS company, c.industry,
           ROUND(AVG(jp.salary_monthly_php), 2) AS avg_salary
    FROM job_postings jp
    JOIN companies c ON c.company_id = jp.company_id
    WHERE jp.salary_monthly_php IS NOT NULL
    GROUP BY c.company_id, c.name, c.industry
)
SELECT company, industry, avg_salary,
       RANK() OVER (PARTITION BY industry ORDER BY avg_salary DESC) AS rank_in_industry
FROM company_avg_salary
ORDER BY industry, rank_in_industry;


-- ============================================================
-- Query 5: Entry-level vs mid-level skill gap (CASE WHEN pivot)
-- ============================================================
SELECT s.name AS skill,
       SUM(CASE WHEN jp.level = 'entry' THEN 1 ELSE 0 END) AS entry_postings,
       SUM(CASE WHEN jp.level = 'mid'   THEN 1 ELSE 0 END) AS mid_postings,
       SUM(CASE WHEN jp.level = 'mid'   THEN 1 ELSE 0 END)
         - SUM(CASE WHEN jp.level = 'entry' THEN 1 ELSE 0 END) AS gap
FROM job_skills js
JOIN skills s ON s.skill_id = js.skill_id
JOIN job_postings jp ON jp.job_id = js.job_id
WHERE jp.level IN ('entry', 'mid')
GROUP BY s.name
ORDER BY gap DESC;
