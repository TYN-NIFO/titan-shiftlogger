-- 001_schema.sql: tables and indexes. Must match app/db/models.py exactly (models.py is the source of truth).
-- Run by scripts/init_db.py, which drops and recreates everything (idempotent).

DROP VIEW IF EXISTS v_operator_productivity CASCADE;
DROP VIEW IF EXISTS v_operator_productivity_daily CASCADE;
DROP VIEW IF EXISTS v_absenteeism CASCADE;
DROP VIEW IF EXISTS v_downtime CASCADE;
DROP VIEW IF EXISTS v_production CASCADE;

DROP TABLE IF EXISTS chat_log CASCADE;
DROP TABLE IF EXISTS review_log CASCADE;
DROP TABLE IF EXISTS card_rows CASCADE;
DROP TABLE IF EXISTS job_cards CASCADE;
DROP TABLE IF EXISTS codes CASCADE;
DROP TABLE IF EXISTS components CASCADE;
DROP TABLE IF EXISTS machines CASCADE;
DROP TABLE IF EXISTS employees CASCADE;

-- ------------------------------------------------------------------ masters

CREATE TABLE employees (
    emp_no      VARCHAR(12) NOT NULL,
    shift_group VARCHAR(2),
    home_mc_no  VARCHAR(16),
    name        VARCHAR(60),                -- made-up display name, e.g. 'Ravi K.'
    PRIMARY KEY (emp_no)
);

CREATE TABLE machines (
    mc_no        VARCHAR(16) NOT NULL,      -- e.g. 604021.05
    machine_type VARCHAR(16) NOT NULL,      -- Press or CNC
    is_cnc       BOOLEAN NOT NULL,
    name         VARCHAR(60),               -- display name, e.g. 'CNC case milling 1'
    PRIMARY KEY (mc_no)
);

CREATE TABLE components (
    comp_code         VARCHAR(12) NOT NULL,
    description       VARCHAR(120),
    std_rate_per_hour FLOAT NOT NULL,       -- standard accepted qty per productive hour
    PRIMARY KEY (comp_code)
);

CREATE TABLE codes (
    code        VARCHAR(12) NOT NULL,       -- 10804, RW-001, RJ-008
    kind        VARCHAR(12) NOT NULL,       -- production, idle, rework, rejection
    description VARCHAR(200) NOT NULL,
    category    VARCHAR(20),                -- idle only: breakdown, maintenance, tooling, material, utilities, people, other
    PRIMARY KEY (code)
);

-- ------------------------------------------------------------------ cards

CREATE TABLE job_cards (
    id           SERIAL NOT NULL,
    card_ref     VARCHAR(40) NOT NULL,      -- C04, SYN-000123
    source       VARCHAR(12) NOT NULL,      -- photo, synthetic
    status       VARCHAR(16) NOT NULL,      -- processing, needs_review, approved, failed
    image_path   TEXT,
    card_date    DATE,
    mc_no        VARCHAR(16),
    emp_no       VARCHAR(12),
    shift        VARCHAR(2),
    header       JSONB NOT NULL,            -- as written
    total_hours  VARCHAR(10),               -- as written
    flags        JSONB NOT NULL,            -- validate() output
    extracted    JSONB,
    read_model   VARCHAR(80),
    read_seconds FLOAT,
    error        TEXT,
    created_at   TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    approved_at  TIMESTAMP WITH TIME ZONE,
    approved_by  VARCHAR(60),
    PRIMARY KEY (id)
);
CREATE INDEX ix_job_cards_card_ref  ON job_cards (card_ref);
CREATE INDEX ix_job_cards_status    ON job_cards (status);
CREATE INDEX ix_job_cards_card_date ON job_cards (card_date);
CREATE INDEX ix_job_cards_mc_no     ON job_cards (mc_no);
CREATE INDEX ix_job_cards_emp_no    ON job_cards (emp_no);

CREATE TABLE card_rows (
    id          SERIAL NOT NULL,
    card_id     INTEGER NOT NULL,
    row_no      INTEGER NOT NULL,           -- 1-based
    raw         JSONB NOT NULL,             -- the 14 fields as written + "unclear": [...]
    emp_no      VARCHAR(12),
    shift       VARCHAR(2),
    opn_code    VARCHAR(12),
    wo_no       VARCHAR(30),
    comp_code   VARCHAR(12),
    qty_prod    INTEGER,
    qty_accp    INTEGER,
    rej_code    VARCHAR(6),
    rej_qty     INTEGER,
    rework_code VARCHAR(6),
    rework_qty  INTEGER,
    time_from   VARCHAR(8),
    time_to     VARCHAR(8),
    minutes     INTEGER,                    -- paid duration of the row
    PRIMARY KEY (id),
    FOREIGN KEY (card_id) REFERENCES job_cards (id) ON DELETE CASCADE
);
CREATE INDEX ix_card_rows_card_id  ON card_rows (card_id);
CREATE INDEX ix_card_rows_emp_no   ON card_rows (emp_no);
CREATE INDEX ix_card_rows_opn_code ON card_rows (opn_code);

CREATE TABLE review_log (
    id        SERIAL NOT NULL,
    card_id   INTEGER NOT NULL,
    action    VARCHAR(16) NOT NULL,         -- edit, approve
    field     VARCHAR(60),
    old_value TEXT,
    new_value TEXT,
    by        VARCHAR(60) NOT NULL,
    at        TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id),
    FOREIGN KEY (card_id) REFERENCES job_cards (id) ON DELETE CASCADE
);
CREATE INDEX ix_review_log_card_id ON review_log (card_id);

CREATE TABLE chat_log (
    id            SERIAL NOT NULL,
    question      TEXT NOT NULL,
    route         VARCHAR(10),
    sql           TEXT,
    sql_valid     BOOLEAN,
    row_count     INTEGER,
    answer        TEXT,
    view          JSONB,
    numbers_match BOOLEAN,
    error         TEXT,
    ms            INTEGER,
    created_at    TIMESTAMP WITH TIME ZONE DEFAULT now() NOT NULL,
    PRIMARY KEY (id)
);
