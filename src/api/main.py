from fastapi import FastAPI

from api.datasources import router as datasources_router

app = FastAPI(title="Chat-DB", version="0.1.0")
app.include_router(datasources_router)
