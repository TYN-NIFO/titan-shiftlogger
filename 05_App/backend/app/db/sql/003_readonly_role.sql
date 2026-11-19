-- 003_readonly_role.sql: the chatbot's read-only role. Re-runnable.
-- titan_chat_ro may SELECT the 5 views + machines, codes, employees. Nothing else.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'titan_chat_ro') THEN
        CREATE ROLE titan_chat_ro LOGIN PASSWORD 'titan_chat_ro';
    ELSE
        ALTER ROLE titan_chat_ro LOGIN PASSWORD 'titan_chat_ro';
    END IF;
END
$$;

ALTER ROLE titan_chat_ro NOSUPERUSER NOCREATEDB NOCREATEROLE;
ALTER ROLE titan_chat_ro SET default_transaction_read_only = on;
ALTER ROLE titan_chat_ro SET statement_timeout = '5s';

DO $$
BEGIN
    EXECUTE 'GRANT CONNECT ON DATABASE ' || quote_ident(current_database()) || ' TO titan_chat_ro';
END
$$;

GRANT USAGE ON SCHEMA public TO titan_chat_ro;
REVOKE CREATE ON SCHEMA public FROM titan_chat_ro;
REVOKE ALL ON ALL TABLES IN SCHEMA public FROM titan_chat_ro;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM titan_chat_ro;

GRANT SELECT ON
    v_production,
    v_downtime,
    v_absenteeism,
    v_operator_productivity,
    v_operator_productivity_daily,
    machines,
    codes,
    employees
TO titan_chat_ro;
