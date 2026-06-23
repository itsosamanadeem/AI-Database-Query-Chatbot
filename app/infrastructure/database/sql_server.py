import pandas as pd
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.engine import URL


class SqlServerDatabase:
    def __init__(self, database_url: URL) -> None:
        self.engine = create_engine(database_url)
        self._inspector = None

    @property
    def inspector(self):
        if self._inspector is None:
            self._inspector = inspect(self.engine)
        return self._inspector

    def get_discovered_views(self) -> list[str]:
        views = []

        for schema_name in self.inspector.get_schema_names():
            for view_name in self.inspector.get_view_names(schema=schema_name):
                views.append(f"{schema_name}.{view_name}")

        return views

    def get_view_columns(self, schema: str, view: str):
        return self.inspector.get_columns(view, schema=schema)

    def execute_query(self, query: str):
        with self.engine.connect() as connection:
            return pd.read_sql(text(query), connection)

    def dispose(self) -> None:
        self.engine.dispose()
