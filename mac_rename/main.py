from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
import os
from pathlib import Path
import logging
from rich.console import Console
from rich.logging import RichHandler

# Set fixed log level - change this value to adjust logging verbosity
# Options: "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"
LOG_LEVEL = "DEBUG"

# Configure Rich logging
console = Console()
logging.basicConfig(
    level=getattr(logging, LOG_LEVEL),
    format="%(message)s",
    datefmt="[%X]",
    handlers=[RichHandler(console=console, rich_tracebacks=True)]
)
logger = logging.getLogger("mac_rename")

# Create FastAPI app
app = FastAPI(title="RAW-Bracketing Rename", version="1.0.0")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Get the directory of the current file
BASE_DIR = Path(__file__).parent

# Mount static files
static_dir = BASE_DIR / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Import routes
from .api import routes

# Include routers
app.include_router(routes.router)

@app.get("/")
async def root():
    """Serve the main HTML page"""
    html_file = BASE_DIR / "static" / "index.html"
    if html_file.exists():
        return FileResponse(str(html_file))
    return {"message": "Application is running. Navigate to /static/"}

@app.on_event("startup")
async def startup_event():
    """Log startup message"""
    logger.info(f"Starting RAW-Bracketing Rename application with log level: {LOG_LEVEL}")
    logger.info(f"Static files directory: {static_dir}")
    logger.info(f"Application ready at: http://localhost:8000")

if __name__ == "__main__":
    import uvicorn
    logger.debug("Starting uvicorn server")
    uvicorn.run(app, host="127.0.0.1", port=8000)