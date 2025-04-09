"""
Simple entry point for the Pension Advisor application.
This file serves as a wrapper around main.py to start the application.
"""

import uvicorn
import logging
from main import app

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    logger = logging.getLogger("app")
    logger.info("Starting Pension Advisor application...")
    
    # Run the application
    uvicorn.run(
        "main:app", 
        host="0.0.0.0",
        port=9090,
        reload=True
    )
