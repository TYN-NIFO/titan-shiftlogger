"""Check model-written SQL before it runs: one read-only SELECT over the allowed relations only.

The database role (titan_chat_ro) is the real wall; this check is the first one, and it gives
a clear reason when it says no.
"""
from __future__ import annotations

import sqlglot
from sqlglot import exp

ALLOWED_RELATIONS = {
    "v_production", "v_downtime", "v_absenteeism", "v_operator_productivity",
    "v_operator_productivity_daily", "machines", "codes", "employees",
}
MAX_LIMIT = 200

# Functions that can sleep, read files, reach other servers or change settings.
_BLOCKED_FUNC_PREFIXES = ("pg_", "lo_", "dblink", "set_config", "current_setting", "query_to_xml",
                          "table_to_xml", "cursor_to_xml", "txid_", "nextval", "setval")
_FORBIDDEN_NODES = tuple(getattr(exp, n) for n in (
    "Insert", "Update", "Delete", "Drop", "Create", "Alter", "Merge", "Command", "Into", "Lock",
    "Grant", "TruncateTable", "Copy", "Set", "Transaction", "Commit", "Rollback", "Use",
) if hasattr(exp, n))


class SQLRejected(ValueError):
    pass


def _func_name(node: exp.Expression) -> str:
    if isinstance(node, exp.Anonymous):
        return str(node.this).lower()
    return (node.sql_name() or "").lower()


def guard(sql: str) -> str:
    """Return the safe SQL to run (with a LIMIT), or raise SQLRejected with a reason."""
    text = (sql or "").strip().rstrip(";").strip()
    if not text:
        raise SQLRejected("empty SQL")
    try:
        statements = [st for st in sqlglot.parse(text, read="postgres") if st is not None]
    except sqlglot.errors.ParseError as e:
        raise SQLRejected(f"SQL does not parse: {str(e).splitlines()[0]}") from e
    if len(statements) != 1:
        raise SQLRejected("only one statement is allowed")
    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.Union, exp.Intersect, exp.Except)):
        raise SQLRejected(f"only SELECT is allowed (got {tree.key.upper()})")

    for node in tree.walk():
        if isinstance(node, _FORBIDDEN_NODES):
            raise SQLRejected(f"{node.key.upper()} is not allowed")
        if isinstance(node, exp.Func):
            name = _func_name(node)
            if name.startswith(_BLOCKED_FUNC_PREFIXES):
                raise SQLRejected(f"function {name}() is not allowed")
    if tree.args.get("locks"):
        raise SQLRejected("row locks are not allowed")

    cte_names = {c.alias_or_name.lower() for c in tree.find_all(exp.CTE)}
    for t in tree.find_all(exp.Table):
        name = (t.name or "").lower()
        schema = (t.db or "").lower()
        if not name:
            raise SQLRejected("table functions are not allowed")
        if schema and schema != "public":
            raise SQLRejected(f"schema {schema} is not allowed")
        if name in cte_names and not schema:
            continue
        if name not in ALLOWED_RELATIONS:
            raise SQLRejected(f"table {name} is not allowed")

    limit = tree.args.get("limit")
    if limit is None:
        tree = tree.limit(MAX_LIMIT) if isinstance(tree, exp.Select) else \
            exp.select("*").from_(tree.subquery("q")).limit(MAX_LIMIT)
    else:
        try:
            n = int(limit.expression.name) if limit.expression is not None else None
        except (TypeError, ValueError):
            n = None
        if n is None or n > MAX_LIMIT:
            limit.set("expression", exp.Literal.number(MAX_LIMIT))
    return tree.sql(dialect="postgres")
