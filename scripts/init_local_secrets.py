"""Create a random local Compose password without printing or overwriting it."""

import secrets
from pathlib import Path


def main() -> None:
    directory = Path(__file__).resolve().parents[1] / ".secrets"
    directory.mkdir(mode=0o700, exist_ok=True)
    try:
        with (directory / "db_password.txt").open("x", encoding="utf-8") as secret:
            secret.write(secrets.token_urlsafe(32))
    except FileExistsError:
        print("Existing database password preserved.")
    else:
        print("Created ignored local database password for Docker Compose.")


if __name__ == "__main__":
    main()
