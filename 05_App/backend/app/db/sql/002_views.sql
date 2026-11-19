-- 002_views.sql: the views the chatbot queries (as the read-only role titan_chat_ro).
-- Approved cards only. Hours are decimal hours = card_rows.minutes / 60.0 (paid time of the row).
-- The machine on a row is the card's M/C No (one operator, one machine, one shift per card).
-- Display names (emp_name, machine_name, component_name) are appended as the LAST columns of each view,
-- so queries written against the original column order keep working. Names are made-up sample data.

-- Production rows: code 10202, also with a letter prefix such as S10202.
CREATE VIEW v_production AS
SELECT jc.card_date,
       COALESCE(r.shift, jc.shift)            AS shift,
       COALESCE(r.emp_no, jc.emp_no)          AS emp_no,
       jc.mc_no,
       m.machine_type,
       COALESCE(m.is_cnc, false)              AS is_cnc,
       r.comp_code,
       COALESCE(r.qty_prod, 0)                AS qty_prod,
       COALESCE(r.qty_accp, 0)                AS qty_accp,
       COALESCE(r.rej_qty, 0)                 AS rej_qty,
       COALESCE(r.rework_qty, 0)              AS rework_qty,
       r.minutes / 60.0                       AS hours,
       e.name                                 AS emp_name,
       m.name                                 AS machine_name,
       cp.description                         AS component_name
FROM card_rows r
JOIN job_cards jc       ON jc.id = r.card_id
LEFT JOIN machines m    ON m.mc_no = jc.mc_no
LEFT JOIN employees e   ON e.emp_no = COALESCE(r.emp_no, jc.emp_no)
LEFT JOIN components cp ON cp.comp_code = r.comp_code
WHERE jc.status = 'approved'
  AND regexp_replace(r.opn_code, '^[A-Z]+', '') IN (SELECT code FROM codes WHERE kind = 'production');

-- Idle / downtime rows except absenteeism (10813), with reason and category from the code sheet.
CREATE VIEW v_downtime AS
SELECT jc.card_date,
       COALESCE(r.shift, jc.shift)            AS shift,
       COALESCE(r.emp_no, jc.emp_no)          AS emp_no,
       jc.mc_no,
       m.machine_type,
       COALESCE(m.is_cnc, false)              AS is_cnc,
       r.opn_code                             AS code,
       c.description                          AS reason,
       COALESCE(c.category, 'other')          AS category,
       r.minutes / 60.0                       AS hours,
       e.name                                 AS emp_name,
       m.name                                 AS machine_name
FROM card_rows r
JOIN job_cards jc     ON jc.id = r.card_id
JOIN codes c          ON c.code = r.opn_code AND c.kind = 'idle'
LEFT JOIN machines m  ON m.mc_no = jc.mc_no
LEFT JOIN employees e ON e.emp_no = COALESCE(r.emp_no, jc.emp_no)
WHERE jc.status = 'approved'
  AND r.opn_code <> '10813';

-- One row per absent shift (code 10813).
CREATE VIEW v_absenteeism AS
SELECT DISTINCT
       jc.card_date,
       COALESCE(r.shift, jc.shift)            AS shift,
       COALESCE(r.emp_no, jc.emp_no)          AS emp_no,
       jc.mc_no,
       e.name                                 AS emp_name,
       m.name                                 AS machine_name
FROM card_rows r
JOIN job_cards jc     ON jc.id = r.card_id
LEFT JOIN machines m  ON m.mc_no = jc.mc_no
LEFT JOIN employees e ON e.emp_no = COALESCE(r.emp_no, jc.emp_no)
WHERE jc.status = 'approved'
  AND r.opn_code = '10813';

-- Per operator per day: productive hours, accepted qty, and the standard qty for those hours.
CREATE VIEW v_operator_productivity_daily AS
SELECT p.card_date,
       p.emp_no,
       p.shift,
       ROUND(SUM(p.hours), 2)                                      AS productive_hours,
       SUM(p.qty_accp)                                             AS qty_accp,
       ROUND(SUM(p.hours * c.std_rate_per_hour::numeric), 1)       AS std_qty,
       p.emp_name
FROM v_production p
LEFT JOIN components c ON c.comp_code = p.comp_code
GROUP BY p.card_date, p.emp_no, p.shift, p.emp_name;

-- Per operator over the whole period. efficiency_pct = 100 * accepted qty / standard qty.
CREATE VIEW v_operator_productivity AS
SELECT p.emp_no,
       p.shift,
       COUNT(DISTINCT p.card_date)                                 AS days_worked,
       ROUND(SUM(p.hours), 1)                                      AS productive_hours,
       SUM(p.qty_accp)                                             AS qty_accp,
       ROUND(SUM(p.hours * c.std_rate_per_hour::numeric), 0)       AS std_qty,
       ROUND(100.0 * SUM(p.qty_accp)
             / NULLIF(SUM(p.hours * c.std_rate_per_hour::numeric), 0), 1) AS efficiency_pct,
       p.emp_name
FROM v_production p
LEFT JOIN components c ON c.comp_code = p.comp_code
GROUP BY p.emp_no, p.shift, p.emp_name;
