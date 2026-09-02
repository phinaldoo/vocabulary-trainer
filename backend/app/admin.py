from __future__ import annotations

import argparse
import asyncio

from sqlalchemy import select

from app.config import get_settings
from app.database import create_database
from app.models import User
from app.security import normalize_email


async def set_role(email: str, role: str) -> None:
    settings = get_settings()
    engine, session_factory = create_database(settings)
    try:
        async with session_factory() as db:
            user = await db.scalar(select(User).where(User.email == normalize_email(email)))
            if not user:
                raise RuntimeError("Konto nicht gefunden. Registriere es zuerst in Verba.")
            user.role = role
            await db.commit()
            print(f"{user.email}: Rolle auf {role} gesetzt.")
    finally:
        await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Verba-Administratorrollen verwalten")
    parser.add_argument("action", choices=["promote", "demote"])
    parser.add_argument("email")
    args = parser.parse_args()
    asyncio.run(set_role(args.email, "admin" if args.action == "promote" else "user"))


if __name__ == "__main__":
    main()
