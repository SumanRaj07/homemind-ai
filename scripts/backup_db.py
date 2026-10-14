"""Back up the HomeMind AI SQLite database.

Usage:
    python scripts/backup_db.py --dest /path/to/backups
"""

import shutil
from argparse import ArgumentParser
from datetime import UTC, datetime
from pathlib import Path

from homemind.config.settings import get_settings


def main() -> None:
    parser = ArgumentParser(description="Back up the HomeMind AI database.")
    parser.add_argument("--dest", required=True, help="Backup destination directory")
    args = parser.parse_args()

    settings = get_settings()
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    dest_dir = Path(args.dest)
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / f"homemind-{stamp}.db"
    shutil.copy2(settings.db_path, dest)
    print(f"Backed up {settings.db_path} -> {dest}")


if __name__ == "__main__":
    main()
