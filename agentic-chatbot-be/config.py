"""config.py: one place for filesystem paths imports"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
KNOWLEDGE_BASE_DIR = DATA_DIR / "knowledge_base"
CHROMA_STORE_DIR = DATA_DIR / "chroma_store"

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "mock").lower()
FULFILLMENT_API_URL = os.getenv("FULFILLMENT_API_URL", "http://localhost:8010")