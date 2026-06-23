from langchain.tools import tool

from app.domain.sql_policy import (
    normalize_sqlserver_view_names,
    validate_read_only_query,
)
from app.infrastructure.ai.prompts import create_query_checker_prompt
from app.infrastructure.database.sql_server import SqlServerDatabase
import json

def create_database_tools(database: SqlServerDatabase, model):
    @tool
    def list_db_views() -> str:
        """List all accessible SQL Server database views with schema names."""
        views = database.get_discovered_views()

        if not views:
            return "No accessible views found."

        return "\n".join(views)

    @tool
    def get_view_schema(view_full_name: str) -> str:
        """
        Get columns for a discovered SQL Server view.
        Input must be like: dbo.v_Revenue
        """
        if "." not in view_full_name:
            return "Invalid view name. Use format: schema.view"

        discovered_views = database.get_discovered_views()

        if view_full_name not in discovered_views:
            return "View not found. Use only one of these views:\n" + "\n".join(
                discovered_views
            )

        schema, view = view_full_name.split(".", 1)
        columns = database.get_view_columns(schema, view)
        result = [f"View: {view_full_name}", "Columns:"]

        for column in columns:
            result.append(f"- {column['name']} ({column['type']})")

        return "\n".join(result)

    @tool
    def sql_db_query_checker(query: str) -> str:
        """
        Double check a Microsoft SQL Server SELECT query before execution.
        Always use this before sql_db_query.
        """
        discovered_views = database.get_discovered_views()
        query = normalize_sqlserver_view_names(query.strip(), discovered_views)
        response = model.invoke(create_query_checker_prompt(query))
        checked_query = response.text.strip()
        return normalize_sqlserver_view_names(checked_query, discovered_views)

    @tool
    def sql_db_query(query: str) -> str:
        """
        Execute a read-only SQL Server SELECT query against discovered database views.
        Automatically fixes wrong SQL Server view quoting like [schema.view].
        """
        discovered_views = database.get_discovered_views()
        query = normalize_sqlserver_view_names(query.strip(), discovered_views)
        validation_error = validate_read_only_query(query, discovered_views)

        if validation_error:
            return validation_error

        try:
            dataframe = database.execute_query(query)

            if dataframe.empty:
                return "No rows returned."

            result = {
                "columns": dataframe.columns.tolist(),
                "rows": dataframe.head(20).fillna("").to_dict(orient="records"),
                "total_returned": min(len(dataframe), 20),
            }

            return json.dumps(result, default=str)
        except Exception as error:
            return f"SQL Error: {str(error)}"

    return [list_db_views, get_view_schema, sql_db_query_checker, sql_db_query]
