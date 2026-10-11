"""Run a real PostgreSQL server locally, with no Docker.

Uses the PostgreSQL binaries bundled in the ``pgserver`` wheel and starts them
with ``pg_ctl``, which **daemonises**: the server survives the Python process that
created it, so `init_db`, `uvicorn` and `pytest` can each connect independently.

The data directory (default ``.pgdata``) persists between runs, so records survive
a database restart.

    python -m app.scripts.devdb start     # start (idempotent)
    python -m app.scripts.devdb url       # print DATABASE_URL
    python -m app.scripts.devdb stop      # stop, keeping data
    python -m app.scripts.devdb status
"""

from __future__ import annotations

import argparse
import pathlib
import subprocess
import sys
import tempfile


def _bin_dir() -> pathlib.Path:
    """Locate the bundled PostgreSQL binaries."""
    import pgserver

    pkg_dir = pathlib.Path(pgserver.__file__).parent
    candidates = sorted(pkg_dir.glob("pginstall*"))
    if not candidates:
        raise RuntimeError(f"PostgreSQL binaries not found under {pkg_dir}")
    # pginstall/bin on Windows, pginstall/bin elsewhere.
    return candidates[0] / "bin"


def _exe(name: str) -> str:
    suffix = ".exe" if sys.platform == "win32" else ""
    return str(_bin_dir() / f"{name}{suffix}")


def _data_dir(raw: str) -> pathlib.Path:
    """Resolve the data directory.

    Only the parent is created: ``initdb`` requires the cluster directory itself
    to be absent or empty, so it must not be pre-created here.
    """
    path = pathlib.Path(raw).resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def is_running(data_dir: pathlib.Path) -> bool:
    result = subprocess.run(
        [_exe("pg_ctl"), "-D", str(data_dir), "status"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0


def start(data_dir: pathlib.Path, port: int, log_file: pathlib.Path) -> None:
    if is_running(data_dir):
        print(f"already running on port {port}")
        return
    if not (data_dir / "PG_VERSION").exists():
        print(f"initialising cluster in {data_dir} ...")
        result = subprocess.run(
            [
                _exe("initdb"),
                "-D",
                str(data_dir),
                "-U",
                "postgres",
                "--auth=trust",
                # UTF-8 explicitly: the default cluster encoding follows the host
                # locale (WIN1252 on Windows), which cannot store the JSONB payloads
                # this project writes, since the event copy contains typographic
                # characters such as an em dash.
                "--encoding=UTF8",
                "--locale=C",
            ],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stdout or "", file=sys.stderr)
            print(result.stderr or "", file=sys.stderr)
            raise SystemExit(result.returncode)
    data_dir.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [
            _exe("pg_ctl"),
            "-D",
            str(data_dir),
            "-l",
            str(log_file),
            "-o",
            f'-p {port} -h 127.0.0.1',
            "-w",
            "start",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    print(f"started postgres on 127.0.0.1:{port}")


def stop(data_dir: pathlib.Path) -> None:
    subprocess.run(
        [_exe("pg_ctl"), "-D", str(data_dir), "-m", "fast", "stop"],
        check=False,
        capture_output=True,
        text=True,
    )


def ensure_database(data_dir: pathlib.Path, db: str) -> None:
    """Create the database if it does not exist."""
    exists = subprocess.run(
        [_exe("psql"), "-U", "postgres", "-d", "postgres", "-tAc",
         f"SELECT 1 FROM pg_database WHERE datname='{db}'"],
        capture_output=True,
        text=True,
    )
    if exists.stdout.strip() != "1":
        subprocess.run(
            [_exe("createdb"), "-U", "postgres", db], check=True, capture_output=True, text=True
        )
        print(f"created database {db}")


def database_url(port: int, db: str) -> str:
    return f"postgresql+psycopg://postgres:@127.0.0.1:{port}/{db}"


def main() -> int:
    parser = argparse.ArgumentParser(description="Local PostgreSQL for KAYAN")
    parser.add_argument("action", choices=["start", "stop", "status", "url"], default="start", nargs="?")
    parser.add_argument("--data-dir", default=".pgdata")
    parser.add_argument("--db", default="kayan")
    parser.add_argument("--port", type=int, default=54321)
    args = parser.parse_args()

    data_dir = _data_dir(args.data_dir)
    # The server log lives outside the data directory: on Windows, writing the
    # log inside the cluster while pg_ctl also holds it open causes a sharing
    # violation and startup aborts.
    log_file = pathlib.Path(tempfile.gettempdir()) / "kayan-postgres.log"

    if args.action == "stop":
        stop(data_dir)
        print("stopped (data preserved)")
        return 0

    if args.action == "status":
        print("running" if is_running(data_dir) else "stopped")
        return 0

    start(data_dir, args.port, log_file)
    ensure_database(data_dir, args.db)

    url = database_url(args.port, args.db)
    if args.action == "url":
        print(url)
    else:
        print(f"DATABASE_URL={url}")
        print(f"data dir: {data_dir}")
        print("stop it with: python -m app.scripts.devdb stop")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())