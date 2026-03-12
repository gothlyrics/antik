from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AntiCrashSession:
    owner_id: int
    guild_id: int
    message_id: int | None = None
    selected_role_id: int | None = None
    selected_action_key: str | None = None
    selected_user_id: int | None = None
    selected_trusted_role_id: int | None = None
    selected_channel_id: int | None = None
    view: str = "main"


class AntiCrashSessionStore:
    def __init__(self) -> None:
        self._sessions: dict[int, AntiCrashSession] = {}

    def create(self, message_id: int, state: AntiCrashSession) -> AntiCrashSession:
        state.message_id = message_id
        self._sessions[message_id] = state
        return state

    def get(self, message_id: int) -> AntiCrashSession | None:
        return self._sessions.get(message_id)

    def delete(self, message_id: int) -> None:
        self._sessions.pop(message_id, None)
