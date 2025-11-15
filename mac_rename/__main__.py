import uvicorn
import os
import sys
import logging

if __name__ == '__main__':
    # Get the directory of the current file
    path = os.path.dirname(os.path.abspath(__file__))
    
    # Run FastAPI application with uvicorn
    uvicorn.run(
        "mac_rename.main:app",
        host="127.0.0.1",
        port=8000,
        reload=True,
        log_level="info"
    )