from __future__ import annotations

import unittest

from bot.anticrash.repository import AntiCrashRepository, connect_database
from bot.anticrash.service import (
    detect_mass_mention,
    register_action_hit,
    resolve_strictest_policy,
    should_bypass_protection,
)


class AntiCrashLogicTests(unittest.TestCase):
    def test_resolve_strictest_policy_prefers_forbidden(self) -> None:
        result = resolve_strictest_policy(
            ["role-high", "role-low"],
            {
                "role-high": {
                    "role_id": "role-high",
                    "punishment": "kick",
                    "limits": {"channel_delete": {"mode": "limit", "limit_value": 5}},
                },
                "role-low": {
                    "role_id": "role-low",
                    "punishment": "ban",
                    "limits": {"channel_delete": {"mode": "forbidden", "limit_value": None}},
                },
            },
            "channel_delete",
        )
        self.assertEqual(result["role_id"], "role-low")
        self.assertEqual(result["policy"]["mode"], "forbidden")

    def test_resolve_strictest_policy_uses_smallest_limit(self) -> None:
        result = resolve_strictest_policy(
            ["role-high", "role-low"],
            {
                "role-high": {
                    "role_id": "role-high",
                    "punishment": "kick",
                    "limits": {"channel_create": {"mode": "limit", "limit_value": 7}},
                },
                "role-low": {
                    "role_id": "role-low",
                    "punishment": "remove_roles",
                    "limits": {"channel_create": {"mode": "limit", "limit_value": 3}},
                },
            },
            "channel_create",
        )
        self.assertEqual(result["role_id"], "role-low")
        self.assertEqual(result["policy"]["limit_value"], 3)

    def test_register_action_hit_triggers_after_limit(self) -> None:
        store: dict[str, list[float]] = {}
        key = "guild:user:channel_delete"

        first = register_action_hit(store, key, 2, now=1000, window_seconds=60)
        second = register_action_hit(store, key, 2, now=1001, window_seconds=60)
        third = register_action_hit(store, key, 2, now=1002, window_seconds=60)

        self.assertFalse(first["triggered"])
        self.assertFalse(second["triggered"])
        self.assertTrue(third["triggered"])
        self.assertEqual(third["count"], 3)

    def test_register_action_hit_drops_expired(self) -> None:
        store: dict[str, list[float]] = {}
        key = "guild:user:role_update"

        register_action_hit(store, key, 1, now=1000, window_seconds=60)
        result = register_action_hit(store, key, 1, now=1061, window_seconds=60)

        self.assertFalse(result["triggered"])
        self.assertEqual(result["count"], 1)

    def test_should_bypass_protection_for_whitelist_and_trusted_roles(self) -> None:
        trusted_role = type("Role", (), {"id": 99})()
        member = type("Member", (), {"id": 123, "roles": [trusted_role]})()

        self.assertTrue(
            should_bypass_protection(
                member=member,
                guild_owner_id=1,
                bot_user_id=2,
                whitelist_user_ids=[],
                trusted_role_ids=["99"],
            )
        )
        self.assertTrue(
            should_bypass_protection(
                member=type("Member", (), {"id": 555, "roles": []})(),
                guild_owner_id=1,
                bot_user_id=2,
                whitelist_user_ids=["555"],
                trusted_role_ids=[],
            )
        )

    def test_detect_mass_mention(self) -> None:
        message = type(
            "Message",
            (),
            {
                "mentions": [1, 2, 3],
                "role_mentions": [1, 2],
                "mention_everyone": False,
            },
        )()
        self.assertTrue(detect_mass_mention(message))


class RepositorySmokeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.connection = connect_database(":memory:")
        self.repository = AntiCrashRepository(self.connection)

    def tearDown(self) -> None:
        self.repository.close()

    def test_repository_reads_and_writes_staff_group_limits(self) -> None:
        self.repository.ensure_staff_group(100, 200)
        self.repository.set_punishment(100, 200, "kick")
        self.repository.upsert_limit(100, 200, "channel_delete", "limit", 3)
        self.repository.add_whitelist_user(100, 555)
        self.repository.add_trusted_role(100, 777)
        self.repository.set_log_channel(100, 999)

        role_config = self.repository.get_role_config(100, 200)
        dashboard_state = self.repository.get_dashboard_state(100)

        self.assertEqual(role_config["punishment"], "kick")
        self.assertEqual(role_config["limits"]["channel_delete"]["mode"], "limit")
        self.assertEqual(role_config["limits"]["channel_delete"]["limit_value"], 3)
        self.assertEqual(dashboard_state["guild_settings"]["log_channel_id"], "999")
        self.assertIn("555", dashboard_state["whitelist_user_ids"])
        self.assertIn("777", dashboard_state["trusted_role_ids"])


if __name__ == "__main__":
    unittest.main()
