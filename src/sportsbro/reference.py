from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_reference_json(base_dir: Path, name: str) -> dict[str, Any]:
    path = base_dir / "src" / "sportsbro" / "reference" / name
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))
