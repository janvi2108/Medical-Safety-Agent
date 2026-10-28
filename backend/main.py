"""
main.py

FastAPI application entry point. Sets up CORS, optional Application
Insights instrumentation, and mounts the API routes.
"""

import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from backend.config import config
from backend.api.routes import router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

if config.APPLICATIONINSIGHTS_CONNECTION_STRING:
    from azure.monitor.opentelemetry import configure_azure_monitor
    configure_azure_monitor(connection_string=config.APPLICATIONINSIGHTS_CONNECTION_STRING)
    logger.info("Application Insights monitoring enabled")

app = FastAPI(
    title="Medication Safety Agent Chain",
    description="Extracts medications from clinical notes and checks interactions against DDInter 2.0.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=config.CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router)


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.main:app", host="0.0.0.0", port=8001, reload=True)
