"""
Uvicorn server configuration
"""
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv()

# Server configuration
bind_host = os.getenv("HOST", "localhost")
bind_port = int(os.getenv("PORT", "9090"))
reload = False
workers = 1
log_level = "info"
