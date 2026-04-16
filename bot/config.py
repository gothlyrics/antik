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

    required = ("MTQ5NDM5OTUzODYyMDkyMzk3Ng.G3BMJs.hNCTE8EkW1Ojx_WYxlBUwYNAIceay6vkv7BpDc", "1494399538620923976", "1494450549670678821")
    missing = [key for key in required if not os.getenv(key)]
    if missing:
        raise RuntimeError(
            f"Не заданы обязательные переменные окружения: {', '.join(missing)}"
        )

    return Config(
        token=os.environ["MTQ5NDM5OTUzODYyMDkyMzk3Ng.G3BMJs.hNCTE8EkW1Ojx_WYxlBUwYNAIceay6vkv7BpDc"],
        client_id=os.environ["1494399538620923976"],
        guild_id=int(os.environ["1494450549670678821"]),
        database_path=Path.cwd() / "data" / "anticrash.sqlite",
    )
