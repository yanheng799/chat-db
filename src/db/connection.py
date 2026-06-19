from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine


class ConnectionManager:
    def __init__(self) -> None:
        self._engines: dict[str, AsyncEngine] = {}

    def create_engine(self, config: dict) -> AsyncEngine:
        engine_type = config["engine"]
        if engine_type == "postgresql":
            url = (
                f"postgresql+asyncpg://{config['username']}"
                f":{config['password']}@{config['host']}"
                f":{config['port']}/{config['database']}"
            )
            connect_args = {
                "server_settings": {
                    "statement_timeout": "30000",
                    "default_transaction_read_only": "on",
                },
            }
        else:
            url = (
                f"mysql+asyncmy://{config['username']}"
                f":{config['password']}@{config['host']}"
                f":{config['port']}/{config['database']}"
            )
            connect_args = {"init_command": "SET SESSION max_execution_time=30000; SET SESSION TRANSACTION READ ONLY"}

        return create_async_engine(url, pool_size=5, max_overflow=10, connect_args=connect_args)

    def get_or_create(self, datasource_id: str, config: dict) -> AsyncEngine:
        if datasource_id not in self._engines:
            self._engines[datasource_id] = self.create_engine(config)
        return self._engines[datasource_id]

    async def dispose(self, datasource_id: str) -> None:
        engine = self._engines.pop(datasource_id, None)
        if engine is not None:
            await engine.dispose()

    def dispose_sync(self, datasource_id: str) -> None:
        engine = self._engines.pop(datasource_id, None)
        if engine is not None:
            import asyncio

            asyncio.ensure_future(engine.dispose())

    async def dispose_all(self) -> None:
        for engine in self._engines.values():
            await engine.dispose()
        self._engines.clear()

    def engine_count(self) -> int:
        return len(self._engines)
