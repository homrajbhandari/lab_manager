#!/usr/bin/env python
"""PostgreSQL backup utility for lab-manager.

Two storage backends are supported:
    * local   — write a .sql.gz file into BACKUP_DIR
    * s3      — upload to S3 (boto3) under BACKUP_S3_BUCKET

The retention policy keeps the most recent N backups (default: 14) per
backend and removes older artefacts.

Intended to be run from cron, a Kubernetes CronJob, or GitHub Actions on a
schedule. The script is safe to run concurrently across hosts — the
filename includes a UTC timestamp, and stale-cleanup is based on name
prefix matching.
"""

from __future__ import annotations

import argparse
import gzip
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


log = logging.getLogger("lab-manager.backup")


def _utc_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _build_filename(stamp: str) -> str:
    return f"lab_manager-{stamp}.sql.gz"


def _parse_database_url(url: str) -> dict[str, str]:
    """Very small postgresql:// URL parser — enough for pg_dump connection args."""
    from urllib.parse import urlparse

    parsed = urlparse(url)
    if parsed.scheme not in {"postgresql", "postgres"}:
        raise ValueError(f"DATABASE_URL must be a postgresql:// URL, got {parsed.scheme!r}")

    return {
        "host":     parsed.hostname or "localhost",
        "port":     str(parsed.port or 5432),
        "user":     parsed.username or "",
        "password": parsed.password or "",
        "dbname":   (parsed.path or "/").lstrip("/") or "lab_manager",
    }


def _dump_pg(url: str, out_path: Path) -> None:
    """Run pg_dump and gzip its stdout into out_path."""
    parts = _parse_database_url(url)

    env = os.environ.copy()
    if parts["password"]:
        env["PGPASSWORD"] = parts["password"]

    cmd = [
        "pg_dump",
        "--host",     parts["host"],
        "--port",     parts["port"],
        "--user",     parts["user"],
        "--dbname",   parts["dbname"],
        "--format",   "plain",
        "--no-owner",
        "--no-privileges",
        "--clean",        # include DROP ... statements
        "--if-exists",
    ]

    log.info("Running pg_dump host=%s db=%s", parts["host"], parts["dbname"])
    with out_path.open("wb") as fh:
        # Two-stage: pg_dump -> gzip -> file. We use a pipeline so we never
        # materialise the full dump in memory.
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        try:
            with gzip.GzipFile(fileobj=fh, mode="wb", compresslevel=6) as gz:
                shutil.copyfileobj(proc.stdout, gz)
        finally:
            proc.stdout.close()  # type: ignore[union-attr]
            rc = proc.wait()
            if rc != 0:
                err = proc.stderr.read().decode("utf-8", errors="replace")
                raise RuntimeError(f"pg_dump failed (rc={rc}): {err}")


def _prune(files: Iterable[Path], keep: int) -> list[Path]:
    """Delete all but the most recent `keep` files. Returns deleted paths."""
    if keep <= 0:
        return []

    sorted_files = sorted(files, key=lambda p: p.name, reverse=True)  # newest first
    victims = sorted_files[keep:]
    for victim in victims:
        try:
            victim.unlink()
            log.info("Pruned old backup %s", victim)
        except FileNotFoundError:
            pass
    return victims


def _backup_local(url: str, backup_dir: Path, keep: int) -> Path:
    backup_dir.mkdir(parents=True, exist_ok=True)
    out = backup_dir / _build_filename(_utc_stamp())
    _dump_pg(url, out)
    _prune(backup_dir.glob("lab_manager-*.sql.gz"), keep=keep)
    return out


def _backup_s3(url: str, bucket: str, prefix: str, keep: int) -> str:
    try:
        import boto3  # type: ignore[import-not-found]
        from botocore.exceptions import BotoCoreError  # type: ignore[import-not-found]
    except ImportError as exc:
        raise SystemExit(
            "boto3 is required for S3 backups — `pip install boto3`"
        ) from exc

    import tempfile

    name = _build_filename(_utc_stamp())
    key = f"{prefix.rstrip('/')}/{name}" if prefix else name

    with tempfile.TemporaryDirectory() as td:
        local = Path(td) / name
        _dump_pg(url, local)

        s3 = boto3.client("s3")
        s3.upload_file(str(local), bucket, key)
        log.info("Uploaded s3://%s/%s", bucket, key)

        # Prune: list the prefix, sort by key, delete the tail.
        paginator = s3.get_paginator("list_objects_v2")
        objects = []
        for page in paginator.paginate(Bucket=bucket, Prefix=(prefix or "")):
            for obj in page.get("Contents", []):
                if obj["Key"].endswith(".sql.gz"):
                    objects.append(obj)

        objects.sort(key=lambda o: o["Key"], reverse=True)
        for stale in objects[keep:]:
            try:
                s3.delete_object(Bucket=bucket, Key=stale["Key"])
                log.info("Pruned s3://%s/%s", bucket, stale["Key"])
            except BotoCoreError as exc:
                log.warning("Failed to prune %s: %s", stale["Key"], exc)

    return f"s3://{bucket}/{key}"


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    parser = argparse.ArgumentParser(description="lab-manager PostgreSQL backup")
    parser.add_argument(
        "--backend",
        choices=["local", "s3"],
        default=os.getenv("BACKUP_BACKEND", "local"),
    )
    parser.add_argument(
        "--keep",
        type=int,
        default=int(os.getenv("BACKUP_KEEP", "14")),
        help="How many recent backups to keep (per backend).",
    )
    parser.add_argument(
        "--output-dir",
        default=os.getenv("BACKUP_DIR", "./backups"),
        help="Local output directory when backend=local.",
    )
    parser.add_argument(
        "--s3-bucket",
        default=os.getenv("BACKUP_S3_BUCKET", ""),
        help="S3 bucket when backend=s3.",
    )
    parser.add_argument(
        "--s3-prefix",
        default=os.getenv("BACKUP_S3_PREFIX", "lab-manager"),
        help="Key prefix when backend=s3.",
    )
    args = parser.parse_args(argv)

    url = os.getenv("DATABASE_URL", "")
    if not url:
        log.error("DATABASE_URL is not set — nothing to back up")
        return 2

    try:
        if args.backend == "local":
            out = _backup_local(url, Path(args.output_dir), keep=args.keep)
            log.info("Backup written: %s", out)
        else:
            if not args.s3_bucket:
                log.error("--s3-bucket / BACKUP_S3_BUCKET required for backend=s3")
                return 2
            uri = _backup_s3(url, args.s3_bucket, args.s3_prefix, keep=args.keep)
            log.info("Backup uploaded: %s", uri)
    except Exception as exc:
        log.exception("Backup failed: %s", exc)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
