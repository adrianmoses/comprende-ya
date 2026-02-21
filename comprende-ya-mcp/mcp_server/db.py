"""Async database pool and Apache AGE Cypher query helper."""

from __future__ import annotations

import json
import os
import re
from typing import Any

from psycopg_pool import AsyncConnectionPool


def _db_conninfo() -> str:
    host = os.getenv("AGE_HOST", "localhost")
    port = os.getenv("AGE_PORT", "5455")
    user = os.getenv("AGE_USER", "comprende")
    password = os.getenv("AGE_PASSWORD", "comprende_dev")
    dbname = os.getenv("AGE_DB", "comprende_ya")
    return f"host={host} port={port} user={user} password={password} dbname={dbname}"


async def _configure_connection(conn) -> None:
    """Run on every connection checkout: load AGE and set search_path."""
    await conn.set_autocommit(True)
    await conn.execute("LOAD 'age'")
    await conn.execute('SET search_path = ag_catalog, "$user", public')
    await conn.set_autocommit(False)


def escape_cypher(value: str) -> str:
    """Escape a string for safe interpolation into a Cypher literal."""
    return value.replace("\\", "\\\\").replace("'", "\\'")


async def create_pool(min_size: int = 1, max_size: int = 5) -> AsyncConnectionPool:
    pool = AsyncConnectionPool(
        conninfo=_db_conninfo(),
        min_size=min_size,
        max_size=max_size,
        configure=_configure_connection,
    )
    await pool.open()
    return pool


def _interpolate_params(query: str, params: dict) -> str:
    """Interpolate parameters into a Cypher query string.

    AGE doesn't support parameterized Cypher natively. Escapes backslashes
    then quotes to prevent breakout. Processes keys longest-first to avoid
    partial substitution (e.g. $concept_id before $concept).
    """
    for key in sorted(params, key=len, reverse=True):
        value = params[key]
        if isinstance(value, str):
            escaped = value.replace("\\", "\\\\").replace("'", "\\'")
            query = query.replace(f"${key}", f"'{escaped}'")
        elif value is None:
            query = query.replace(f"${key}", "null")
        else:
            query = query.replace(f"${key}", str(value))
    return query


def _parse_agtype(raw: Any) -> Any:
    """Parse a single agtype value from AGE.

    AGE returns agtype strings with type suffixes like ::vertex, ::edge,
    ::integer, etc. Strip those before JSON parsing.
    """
    if isinstance(raw, str):
        # Strip AGE type suffixes (::vertex, ::edge, ::path, ::integer, etc.)
        cleaned = re.sub(r"::\w+$", "", raw)
        return json.loads(cleaned)
    return raw


async def cypher_query(
    conn,
    graph: str,
    query: str,
    params: dict | None = None,
    columns: list[str] | None = None,
) -> list[Any]:
    """Execute a Cypher query via AGE and return parsed results.

    Args:
        conn: Database connection.
        graph: Graph name.
        query: Cypher query string.
        params: Optional parameter dict for interpolation.
        columns: Column names for multi-column RETURN queries.
            If None, assumes a single 'result' column and returns
            a flat list of parsed values. If provided, each row is
            returned as a list of parsed values.
    """
    if params:
        query = _interpolate_params(query, params)

    if columns:
        col_spec = ", ".join(f"{c} agtype" for c in columns)
    else:
        col_spec = "result agtype"

    sql = f"SELECT * FROM cypher('{graph}', $$ {query} $$) AS ({col_spec})"
    rows = await conn.execute(sql)
    results = []
    for row in await rows.fetchall():
        if columns:
            results.append([_parse_agtype(row[i]) for i in range(len(columns))])
        else:
            results.append(_parse_agtype(row[0]))
    return results
