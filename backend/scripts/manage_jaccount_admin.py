from __future__ import annotations

import argparse
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.storage.json_db import set_jaccount_user_role  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description="Manage Siyuan Compass jAccount administrators.")
    parser.add_argument("action", choices=("add", "remove"))
    parser.add_argument("usernames", nargs="+")
    args = parser.parse_args()

    role = "admin" if args.action == "add" else "student"
    for username in args.usernames:
        user = set_jaccount_user_role(username=username, role=role)
        print(f"{user['username']}: {user['role']}")


if __name__ == "__main__":
    main()
