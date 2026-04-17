"""Database backup sample for mogiri jobs.

Runs pg_dump or mysqldump and compresses the output.
Old backups beyond the retention count are automatically removed.

Required environment variables:
  DB_TYPE      - "postgres" or "mysql"
  DB_NAME      - Database name
  DB_HOST      - Database host (default: localhost)

Optional environment variables:
  DB_PORT      - Database port (default: 5432 for postgres, 3306 for mysql)
  DB_USER      - Database user (default: current user)
  DB_PASSWORD  - Database password
  BACKUP_DIR   - Directory to store backups (default: /tmp/mogiri-backups)
  BACKUP_KEEP  - Number of backups to retain (default: 7)
"""

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


def main():
    db_type = os.environ.get("DB_TYPE", "").lower()
    db_name = os.environ.get("DB_NAME", "")
    db_host = os.environ.get("DB_HOST", "localhost")
    db_user = os.environ.get("DB_USER", "")
    db_password = os.environ.get("DB_PASSWORD", "")
    backup_dir = Path(os.environ.get("BACKUP_DIR", "/tmp/mogiri-backups"))
    backup_keep = int(os.environ.get("BACKUP_KEEP", "7"))

    if not db_type or not db_name:
        print("Error: DB_TYPE and DB_NAME are required.", file=sys.stderr)
        sys.exit(1)

    backup_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{db_name}_{timestamp}.sql.gz"
    filepath = backup_dir / filename

    # Build dump command
    env = os.environ.copy()
    if db_type == "postgres":
        port = os.environ.get("DB_PORT", "5432")
        cmd = ["pg_dump", "-h", db_host, "-p", port, db_name]
        if db_user:
            cmd.extend(["-U", db_user])
        if db_password:
            env["PGPASSWORD"] = db_password
    elif db_type == "mysql":
        port = os.environ.get("DB_PORT", "3306")
        cmd = ["mysqldump", "-h", db_host, "-P", port, db_name]
        if db_user:
            cmd.extend(["-u", db_user])
        if db_password:
            cmd.append(f"-p{db_password}")
    else:
        print(f"Error: Unsupported DB_TYPE: {db_type}", file=sys.stderr)
        sys.exit(1)

    # Run dump and compress
    print(f"Backing up {db_type} database '{db_name}' to {filepath}")
    with open(filepath, "wb") as f:
        dump = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        gzip = subprocess.Popen(["gzip"], stdin=dump.stdout, stdout=f, stderr=subprocess.PIPE)
        dump.stdout.close()
        _, gzip_err = gzip.communicate()
        _, dump_err = dump.communicate()

    if dump.returncode != 0:
        print(f"Dump failed: {dump_err.decode()}", file=sys.stderr)
        filepath.unlink(missing_ok=True)
        sys.exit(1)

    size_mb = filepath.stat().st_size / (1024 * 1024)
    print(f"Backup complete: {filepath} ({size_mb:.1f} MB)")

    # Rotate old backups
    backups = sorted(backup_dir.glob(f"{db_name}_*.sql.gz"))
    if len(backups) > backup_keep:
        for old in backups[: len(backups) - backup_keep]:
            old.unlink()
            print(f"Removed old backup: {old.name}")

    print(f"Retained {min(len(backups), backup_keep)} backup(s)")


if __name__ == "__main__":
    main()
