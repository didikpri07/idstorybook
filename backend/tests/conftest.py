"""Shared test configuration — loads credentials from .env.test so tokens are not hardcoded."""
import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env.test", override=True)
load_dotenv("/app/frontend/.env", override=False)
