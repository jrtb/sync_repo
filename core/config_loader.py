from __future__ import annotations

import json
import sys
from pathlib import Path


def load_config(project_root: Path, config_file: str | None) -> dict:
    if config_file:
        config_path = Path(config_file)
    else:
        config_path = project_root / "config" / "aws-config.json"
    try:
        with open(config_path, "r") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ Configuration file not found: {config_path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ Invalid JSON in configuration file: {e}")
        sys.exit(1)


