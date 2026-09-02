import json
from pathlib import Path

from app.main import app

OUTPUT = Path(__file__).resolve().parents[1] / "openapi.json"
OUTPUT.write_text(json.dumps(app.openapi(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
print(OUTPUT)
