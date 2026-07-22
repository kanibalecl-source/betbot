"""Create Argon2id dashboard users without storing plaintext passwords."""
from __future__ import annotations

import argparse
import getpass
import json
from pathlib import Path

from password_security import hash_password


def main() -> None:
    parser = argparse.ArgumentParser(description="Create or replace a KANIBAL dashboard user")
    parser.add_argument("username")
    parser.add_argument("--users-file", default="users.json")
    parser.add_argument("--role", default="admin", choices=("admin", "user"))
    args = parser.parse_args()

    username = args.username.strip()
    if not username:
        raise SystemExit("Username must not be empty")
    password = getpass.getpass("New password: ")
    confirmation = getpass.getpass("Repeat password: ")
    if password != confirmation:
        raise SystemExit("Passwords do not match")
    if len(password) < 14:
        raise SystemExit("Password must contain at least 14 characters")

    path = Path(args.users_file).resolve()
    users = {}
    if path.is_file():
        loaded = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(loaded, dict):
            users = loaded
    users[username] = {
        "password_hash": hash_password(password),
        "role": args.role,
        "active": True,
    }
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(users, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)
    print(f"User {username!r} written to {path}")


if __name__ == "__main__":
    main()
