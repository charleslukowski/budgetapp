"""
FastAPI application for OVEC Budget System.
"""

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path

from src.api.routes import (
    summary,
    transactions,
    pages,
    forecasts_api,
    variance_api,
    funding_api,
    exports,
    budget_entry_api,
    scenarios,
)

# Create FastAPI app
app = FastAPI(
    title="OVEC Budget System",
    description="Financial planning and reporting for OVEC power plants",
    version="1.0.0"
)

# CORS middleware for development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (mockups/styles.css)
static_path = Path(__file__).parent.parent.parent / "mockups"
if static_path.exists():
    app.mount("/static", StaticFiles(directory=str(static_path)), name="static")

# Templates
templates_path = Path(__file__).parent.parent.parent / "templates"
templates_path.mkdir(exist_ok=True)
templates = Jinja2Templates(directory=str(templates_path))

# Include routers
app.include_router(summary.router, prefix="/api", tags=["Summary"])
app.include_router(transactions.router, prefix="/api", tags=["Transactions"])
app.include_router(pages.router, tags=["Pages"])
app.include_router(forecasts_api.router, tags=["Forecasts"])
app.include_router(variance_api.router, tags=["Variance"])
app.include_router(funding_api.router, tags=["Funding"])
app.include_router(exports.router, tags=["Exports"])
app.include_router(budget_entry_api.router, tags=["Budget Entry"])
app.include_router(scenarios.router, tags=["Scenarios"])


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "app": "OVEC Budget System"}


@app.get("/health")
async def health():
    """Health check endpoint."""
    from src.db.postgres import test_connection
    db_ok, db_msg = test_connection()
    return {
        "status": "healthy" if db_ok else "unhealthy",
        "database": db_msg
    }
