import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "harness"))

# Hermetic tests: never call OpenAI during pytest
os.environ.pop("OPENAI_API_KEY", None)
os.environ["OPENAI_API_KEY"] = ""


def pytest_configure(config):
    os.environ.pop("OPENAI_API_KEY", None)
