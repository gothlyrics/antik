from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any

from .constants import ACTION_DEFINITIONS, DEFAULT_PUNISHMENT, DEFAULT_WINDOW_SECONDS


def connect_database(database_path: str | Path) -> sqlite3.Connection:
    if str(database_path) != ":memory:":
        path = Path(database_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(path)
    else:
        connection = sqlite3.connect(":memory:")

    connection.row_factory = sqlite3.Row
    initialize_schema(connection)
    return connection


def initialize_schema(connection: sqlite3.Connection) -> None:
    connection.executescript(
        """
        CREATE TABLE IF NOT EXISTS guild_settings (
          guild_id TEXT PRIMARY KEY,
          log_channel_id TEXT,
          window_seconds INTEGER NOT NULL DEFAULT 60
        );

        CREATE TABLE IF NOT EXISTS staff_groups (
          guild_id TEXT NOT NULL,
          role_id TEXT NOT NULL,
          punishment TEXT NOT NULL DEFAULT 'remove_roles',
          enabled INTEGER NOT NULL DEFAULT 1,
          PRIMARY KEY (guild_id, role_id)
        );

        CREATE TABLE IF NOT EXISTS group_limits (
          guild_id TEXT NOT NULL,
          role_id TEXT NOT NULL,
          action_key TEXT NOT NULL,
          mode TEXT NOT NULL CHECK(mode IN ('forbidden', 'limit')),
          limit_value INTEGER,
          PRIMARY KEY (guild_id, role_id, action_key)
        );

        CREATE TABLE IF NOT EXISTS whitelist_users (
          guild_id TEXT NOT NULL,
          user_id TEXT NOT NULL,
          PRIMARY KEY (guild_id, user_id)
        );

        CREATE TABLE IF NOT EXISTS trusted_roles (
          guild_id TEXT NOT NULL,
          role_id TEXT NOT NULL,
          PRIMARY KEY (guild_id, role_id)
        );
        """
    )
    connection.commit()


class AntiCrashRepository:
    def __init__(self, connection: sqlite3.Connection) -> None:
        self.connection = connection

    def close(self) -> None:
        self.connection.close()

    def ensure_guild(self, guild_id: int | str) -> None:
        self.connection.execute(
            """
            INSERT INTO guild_settings (guild_id, window_seconds)
            VALUES (?, ?)
            ON CONFLICT(guild_id) DO NOTHING
            """,
            (str(guild_id), DEFAULT_WINDOW_SECONDS),
        )
        self.connection.commit()

    def ensure_staff_group(self, guild_id: int | str, role_id: int | str) -> None:
        self.ensure_guild(guild_id)
        self.connection.execute(
            """
            INSERT INTO staff_groups (guild_id, role_id, punishment, enabled)
            VALUES (?, ?, ?, 1)
            ON CONFLICT(guild_id, role_id) DO NOTHING
            """,
            (str(guild_id), str(role_id), DEFAULT_PUNISHMENT),
        )
        self.connection.commit()

    def get_guild_settings(self, guild_id: int | str) -> dict[str, Any]:
        self.ensure_guild(guild_id)
        row = self.connection.execute(
            """
            SELECT guild_id, log_channel_id, window_seconds
            FROM guild_settings
            WHERE guild_id = ?
            """,
            (str(guild_id),),
        ).fetchone()
        return (
            dict(row)
            if row
            else {
                "guild_id": str(guild_id),
                "log_channel_id": None,
                "window_seconds": DEFAULT_WINDOW_SECONDS,
            }
        )

    def set_log_channel(self, guild_id: int | str, channel_id: int | str) -> None:
        self.ensure_guild(guild_id)
        self.connection.execute(
            """
            UPDATE guild_settings
            SET log_channel_id = ?
            WHERE guild_id = ?
            """,
            (str(channel_id), str(guild_id)),
        )
        self.connection.commit()

    def clear_log_channel(self, guild_id: int | str) -> None:
        self.ensure_guild(guild_id)
        self.connection.execute(
            """
            UPDATE guild_settings
            SET log_channel_id = NULL
            WHERE guild_id = ?
            """,
            (str(guild_id),),
        )
        self.connection.commit()

    def set_punishment(self, guild_id: int | str, role_id: int | str, punishment: str) -> None:
        self.ensure_staff_group(guild_id, role_id)
        self.connection.execute(
            """
            UPDATE staff_groups
            SET punishment = ?
            WHERE guild_id = ? AND role_id = ?
            """,
            (punishment, str(guild_id), str(role_id)),
        )
        self.connection.commit()

    def upsert_limit(
        self,
        guild_id: int | str,
        role_id: int | str,
        action_key: str,
        mode: str,
        limit_value: int | None = None,
    ) -> None:
        self.ensure_staff_group(guild_id, role_id)
        self.connection.execute(
            """
            INSERT INTO group_limits (guild_id, role_id, action_key, mode, limit_value)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(guild_id, role_id, action_key)
            DO UPDATE SET mode = excluded.mode, limit_value = excluded.limit_value
            """,
            (str(guild_id), str(role_id), action_key, mode, limit_value),
        )
        self.connection.commit()

    def add_whitelist_user(self, guild_id: int | str, user_id: int | str) -> None:
        self.ensure_guild(guild_id)
        self.connection.execute(
            """
            INSERT INTO whitelist_users (guild_id, user_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id, user_id) DO NOTHING
            """,
            (str(guild_id), str(user_id)),
        )
        self.connection.commit()

    def remove_whitelist_user(self, guild_id: int | str, user_id: int | str) -> None:
        self.ensure_guild(guild_id)
        self.connection.execute(
            """
            DELETE FROM whitelist_users
            WHERE guild_id = ? AND user_id = ?
            """,
            (str(guild_id), str(user_id)),
        )
        self.connection.commit()

    def add_trusted_role(self, guild_id: int | str, role_id: int | str) -> None:
        self.ensure_guild(guild_id)
        self.connection.execute(
            """
            INSERT INTO trusted_roles (guild_id, role_id)
            VALUES (?, ?)
            ON CONFLICT(guild_id, role_id) DO NOTHING
            """,
            (str(guild_id), str(role_id)),
        )
        self.connection.commit()

    def remove_trusted_role(self, guild_id: int | str, role_id: int | str) -> None:
        self.ensure_guild(guild_id)
        self.connection.execute(
            """
            DELETE FROM trusted_roles
            WHERE guild_id = ? AND role_id = ?
            """,
            (str(guild_id), str(role_id)),
        )
        self.connection.commit()

    def get_role_config(self, guild_id: int | str, role_id: int | str) -> dict[str, Any]:
        self.ensure_staff_group(guild_id, role_id)
        group_row = self.connection.execute(
            """
            SELECT role_id, punishment, enabled
            FROM staff_groups
            WHERE guild_id = ? AND role_id = ?
            """,
            (str(guild_id), str(role_id)),
        ).fetchone()
        limit_rows = self.connection.execute(
            """
            SELECT action_key, mode, limit_value
            FROM group_limits
            WHERE guild_id = ? AND role_id = ?
            """,
            (str(guild_id), str(role_id)),
        ).fetchall()

        limits = {
            action.key: {"mode": "forbidden", "limit_value": None}
            for action in ACTION_DEFINITIONS
        }

        for row in limit_rows:
            limits[row["action_key"]] = {
                "mode": row["mode"],
                "limit_value": row["limit_value"],
            }

        return {
            "role_id": str(role_id),
            "punishment": group_row["punishment"] if group_row else DEFAULT_PUNISHMENT,
            "enabled": bool(group_row["enabled"]) if group_row else True,
            "limits": limits,
        }

    def get_dashboard_state(self, guild_id: int | str) -> dict[str, Any]:
        self.ensure_guild(guild_id)
        guild_settings = self.get_guild_settings(guild_id)
        staff_rows = self.connection.execute(
            """
            SELECT role_id, punishment, enabled
            FROM staff_groups
            WHERE guild_id = ?
            """,
            (str(guild_id),),
        ).fetchall()
        limit_rows = self.connection.execute(
            """
            SELECT role_id, action_key, mode, limit_value
            FROM group_limits
            WHERE guild_id = ?
            """,
            (str(guild_id),),
        ).fetchall()
        whitelist_rows = self.connection.execute(
            """
            SELECT user_id
            FROM whitelist_users
            WHERE guild_id = ?
            """,
            (str(guild_id),),
        ).fetchall()
        trusted_rows = self.connection.execute(
            """
            SELECT role_id
            FROM trusted_roles
            WHERE guild_id = ?
            """,
            (str(guild_id),),
        ).fetchall()

        groups_by_role: dict[str, dict[str, Any]] = {}
        for row in staff_rows:
            groups_by_role[row["role_id"]] = {
                "role_id": row["role_id"],
                "punishment": row["punishment"],
                "enabled": bool(row["enabled"]),
                "limits": {
                    action.key: {"mode": "forbidden", "limit_value": None}
                    for action in ACTION_DEFINITIONS
                },
            }

        for row in limit_rows:
            groups_by_role.setdefault(
                row["role_id"],
                {
                    "role_id": row["role_id"],
                    "punishment": DEFAULT_PUNISHMENT,
                    "enabled": True,
                    "limits": {
                        action.key: {"mode": "forbidden", "limit_value": None}
                        for action in ACTION_DEFINITIONS
                    },
                },
            )
            groups_by_role[row["role_id"]]["limits"][row["action_key"]] = {
                "mode": row["mode"],
                "limit_value": row["limit_value"],
            }

        return {
            "guild_settings": guild_settings,
            "groups_by_role": groups_by_role,
            "whitelist_user_ids": [row["user_id"] for row in whitelist_rows],
            "trusted_role_ids": [row["role_id"] for row in trusted_rows],
        }
