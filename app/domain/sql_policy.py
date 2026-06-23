import re


BLOCKED_SQL_WORDS = [
    "insert",
    "update",
    "delete",
    "drop",
    "alter",
    "truncate",
    "exec",
    "execute",
    "merge",
    "create",
]


def normalize_sqlserver_view_names(query: str, discovered_views: list[str]) -> str:
    fixed_query = query

    for full_view_name in discovered_views:
        if "." not in full_view_name:
            continue

        schema, view = full_view_name.split(".", 1)
        wrong = f"[{schema}.{view}]"
        correct = f"[{schema}].[{view}]"
        fixed_query = fixed_query.replace(wrong, correct)

    return fixed_query


def query_uses_discovered_view(query: str, discovered_views: list[str]) -> bool:
    query_lower = query.lower()

    for full_view_name in discovered_views:
        schema, view = full_view_name.split(".", 1)
        patterns = [
            full_view_name.lower(),
            f"[{schema.lower()}].[{view.lower()}]",
            f"[{schema.lower()}.{view.lower()}]",
        ]

        if any(pattern in query_lower for pattern in patterns):
            return True

    return False


def validate_read_only_query(query: str, discovered_views: list[str]) -> str | None:
    query_lower = query.lower()

    if not query_lower.startswith("select"):
        return "Only SELECT queries are allowed."

    if any(re.search(rf"\b{word}\b", query_lower) for word in BLOCKED_SQL_WORDS):
        return "Only read-only SELECT queries are allowed."

    if not query_uses_discovered_view(query, discovered_views):
        return "Query must use only discovered views. First call list_db_views."

    return None
