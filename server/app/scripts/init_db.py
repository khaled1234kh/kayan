"""Schema initialisation and seeding CLI.

    python -m app.scripts.init_db              # create tables + seed agents
    python -m app.scripts.init_db --demo       # also seed the demo order
    python -m app.scripts.init_db --reset      # drop and recreate (dev only)
"""

from __future__ import annotations

import argparse

from app.core.config import get_settings
from app.db.seed import seed_agents, seed_demo_order
from app.db.session import Base, get_engine, get_session_factory, reset_engine
from app.main import check_database_connection


def main() -> int:
    parser = argparse.ArgumentParser(description="Initialise the KAYAN database")
    parser.add_argument("--demo", action="store_true", help="also seed the demo order")
    parser.add_argument("--reset", action="store_true", help="drop all tables first (dev only)")
    args = parser.parse_args()

    settings = get_settings()
    engine = get_engine()

    if args.reset:
        print("dropping existing tables ...")
        Base.metadata.drop_all(bind=engine)

    print("creating tables ...")
    Base.metadata.create_all(bind=engine)

    print(f"checking connection ({engine.dialect.name}) ...")
    check_database_connection()
    print("connection OK")

    session = get_session_factory()()
    try:
        created = seed_agents(session)
        print(f"agents seeded: {created}")
        if args.demo:
            result = seed_demo_order(session)
            print(f"demo order seeded: {result}")
    finally:
        session.close()

    reset_engine()
    print(f"database ready: {settings.database_url.split('@')[-1] if '@' in settings.database_url else settings.database_url}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())