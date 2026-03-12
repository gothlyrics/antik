from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class Config:
    token: str
    client_id: str
    guild_id: int
    database_path: Path


def load_config() -> Config:
    load_dotenv()

    required = ("DISCORD_TOKEN", "DISCORD_CLIENT_ID", "DISCORD_GUILD_ID")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError(
            f"Не заданы обязательные переменные окружения: {', '.join(missing)}"
        )

    return Config(
        token=os.environ["DISCORD_TOKEN"],
        client_id=os.environ["DISCORD_CLIENT_ID"],
        guild_id=int(os.environ["DISCORD_GUILD_ID"]),
        database_path=Path.cwd() / "data" / "anticrash.sqlite",
    )
