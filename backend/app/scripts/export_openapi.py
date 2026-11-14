"""Write the OpenAPI schema to a file (used by `make gen-api` for frontend types).

Usage: python -m app.scripts.export_openapi ../frontend/openapi.json
"""

import json
import sys
from pathlib import Path

from app.main import create_app


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m app.scripts.export_openapi <output.json>")
    out = Path(sys.argv[1])
    out.write_text(json.dumps(create_app().openapi(), indent=2, sort_keys=True) + "\n")
    print(f"OpenAPI schema written to {out}")


if __name__ == "__main__":
    main()
