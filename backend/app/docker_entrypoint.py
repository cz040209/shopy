"""Prepare container-only settings, then execute the requested process."""
from __future__ import annotations

import os
import sys
from urllib.parse import quote


def main() -> None:
    if len(sys.argv) < 2:
        raise SystemExit("A command is required")

    user = quote(os.environ.get("POSTGRES_USER", "shopy"), safe="")
    password = quote(os.environ.get("POSTGRES_PASSWORD", "shopy_local_password"), safe="")
    database = quote(os.environ.get("POSTGRES_DB", "shopy"), safe="")
    os.environ["DATABASE_URL"] = (
        f"postgresql+psycopg://{user}:{password}@postgres:5432/{database}"
    )
    os.execvp(sys.argv[1], sys.argv[1:])


if __name__ == "__main__":
    main()
