"""
backend/scripts/hash_password.py — turn a plaintext password into a bcrypt
hash for AUTH_USERS_JSON.

Usage:
    python backend/scripts/hash_password.py
    (prompts for a password, prints the bcrypt hash)

Then add it to AUTH_USERS_JSON, e.g.:
    [{"username": "ade", "password_hash": "$2b$12$...", "role": "admin"}]
"""
import getpass
import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))
from passlib.context import CryptContext  # noqa: E402

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

if __name__ == "__main__":
    pw = getpass.getpass("Password to hash: ")
    confirm = getpass.getpass("Confirm: ")
    if pw != confirm:
        print("Passwords did not match.", file=sys.stderr)
        sys.exit(1)
    print(pwd_context.hash(pw))
