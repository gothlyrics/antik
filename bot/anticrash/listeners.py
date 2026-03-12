from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Callable

import disnake


AuditMatcher = Callable[[disnake.AuditLogEntry], bool]


class AuditEntryGuard:
    def __init__(self, ttl_seconds: int = 15) -> None:
        self.ttl_seconds = ttl_seconds
        self._entries: dict[int, datetime] = {}

    def remember(self, entry_id: int) -> bool:
        now = datetime.now(tz=timezone.utc)
        expired_before = now - timedelta(seconds=self.ttl_seconds)
        self._entries = {
            key: timestamp
            for key, timestamp in self._entries.items()
            if timestamp >= expired_before
        }
        if entry_id in self._entries:
            return False
        self._entries[entry_id] = now
        return True


async def find_recent_audit_entry(
    guild: disnake.Guild,
    action: disnake.AuditLogAction,
    matcher: AuditMatcher,
    *,
    limit: int = 6,
) -> disnake.AuditLogEntry | None:
    try:
        async for entry in guild.audit_logs(limit=limit, action=action):
            if datetime.now(tz=timezone.utc) - entry.created_at > timedelta(seconds=10):
                continue
            if matcher(entry):
                return entry
    except disnake.HTTPException:
        return None
    return None


def role_became_dangerous(old_role: disnake.Role, new_role: disnake.Role) -> bool:
    return not old_role.permissions.administrator and new_role.permissions.administrator


def register_anticrash_listeners(bot: disnake.Client, service) -> None:
    entry_guard = AuditEntryGuard()

    @bot.listen("on_message")
    async def anticrash_on_message(message: disnake.Message) -> None:
        await service.handle_mass_mention(message)

    @bot.listen("on_guild_channel_create")
    async def anticrash_on_channel_create(channel: disnake.abc.GuildChannel) -> None:
        entry = await find_recent_audit_entry(
            channel.guild,
            disnake.AuditLogAction.channel_create,
            lambda audit_entry: getattr(audit_entry.target, "id", None) == channel.id,
        )
        if not entry or not entry_guard.remember(entry.id):
            return
        await service.handle_protected_action(
            guild=channel.guild,
            executor_id=entry.user.id if entry.user else None,
            action_key="channel_create",
            details={"target_id": channel.id, "channel_id": channel.id},
        )

    @bot.listen("on_guild_channel_delete")
    async def anticrash_on_channel_delete(channel: disnake.abc.GuildChannel) -> None:
        entry = await find_recent_audit_entry(
            channel.guild,
            disnake.AuditLogAction.channel_delete,
            lambda audit_entry: getattr(audit_entry.target, "id", None) == channel.id,
        )
        if not entry or not entry_guard.remember(entry.id):
            return
        await service.handle_protected_action(
            guild=channel.guild,
            executor_id=entry.user.id if entry.user else None,
            action_key="channel_delete",
            details={"target_id": channel.id, "channel_id": channel.id},
        )

    @bot.listen("on_guild_channel_update")
    async def anticrash_on_channel_update(
        _before: disnake.abc.GuildChannel,
        after: disnake.abc.GuildChannel,
    ) -> None:
        entry = await find_recent_audit_entry(
            after.guild,
            disnake.AuditLogAction.channel_update,
            lambda audit_entry: getattr(audit_entry.target, "id", None) == after.id,
        )
        if not entry or not entry_guard.remember(entry.id):
            return
        await service.handle_protected_action(
            guild=after.guild,
            executor_id=entry.user.id if entry.user else None,
            action_key="channel_update",
            details={"target_id": after.id, "channel_id": after.id},
        )

    @bot.listen("on_guild_role_create")
    async def anticrash_on_role_create(role: disnake.Role) -> None:
        entry = await find_recent_audit_entry(
            role.guild,
            disnake.AuditLogAction.role_create,
            lambda audit_entry: getattr(audit_entry.target, "id", None) == role.id,
        )
        if not entry or not entry_guard.remember(entry.id):
            return
        await service.handle_protected_action(
            guild=role.guild,
            executor_id=entry.user.id if entry.user else None,
            action_key="role_create",
            details={"target_id": role.id},
        )

    @bot.listen("on_guild_role_delete")
    async def anticrash_on_role_delete(role: disnake.Role) -> None:
        entry = await find_recent_audit_entry(
            role.guild,
            disnake.AuditLogAction.role_delete,
            lambda audit_entry: getattr(audit_entry.target, "id", None) == role.id,
        )
        if not entry or not entry_guard.remember(entry.id):
            return
        await service.handle_protected_action(
            guild=role.guild,
            executor_id=entry.user.id if entry.user else None,
            action_key="role_delete",
            details={"target_id": role.id},
        )

    @bot.listen("on_guild_role_update")
    async def anticrash_on_role_update(before: disnake.Role, after: disnake.Role) -> None:
        entry = await find_recent_audit_entry(
            after.guild,
            disnake.AuditLogAction.role_update,
            lambda audit_entry: getattr(audit_entry.target, "id", None) == after.id,
        )
        if not entry or not entry_guard.remember(entry.id):
            return
        await service.handle_protected_action(
            guild=after.guild,
            executor_id=entry.user.id if entry.user else None,
            action_key="role_update",
            details={"target_id": after.id},
        )

        if role_became_dangerous(before, after):
            await service.handle_protected_action(
                guild=after.guild,
                executor_id=entry.user.id if entry.user else None,
                action_key="dangerous_permissions",
                details={"target_id": after.id},
            )

    @bot.listen("on_member_join")
    async def anticrash_on_member_join(member: disnake.Member) -> None:
        if not member.bot:
            return
        entry = await find_recent_audit_entry(
            member.guild,
            disnake.AuditLogAction.bot_add,
            lambda audit_entry: getattr(audit_entry.target, "id", None) == member.id,
        )
        if not entry or not entry_guard.remember(entry.id):
            return
        await service.handle_protected_action(
            guild=member.guild,
            executor_id=entry.user.id if entry.user else None,
            action_key="bot_add",
            details={"target_id": member.id},
        )

    @bot.listen("on_member_ban")
    async def anticrash_on_member_ban(guild: disnake.Guild, user: disnake.User) -> None:
        entry = await find_recent_audit_entry(
            guild,
            disnake.AuditLogAction.ban,
            lambda audit_entry: getattr(audit_entry.target, "id", None) == user.id,
        )
        if not entry or not entry_guard.remember(entry.id):
            return
        await service.handle_protected_action(
            guild=guild,
            executor_id=entry.user.id if entry.user else None,
            action_key="member_ban",
            details={"target_id": user.id},
        )

    @bot.listen("on_member_unban")
    async def anticrash_on_member_unban(guild: disnake.Guild, user: disnake.User) -> None:
        entry = await find_recent_audit_entry(
            guild,
            disnake.AuditLogAction.unban,
            lambda audit_entry: getattr(audit_entry.target, "id", None) == user.id,
        )
        if not entry or not entry_guard.remember(entry.id):
            return
        await service.handle_protected_action(
            guild=guild,
            executor_id=entry.user.id if entry.user else None,
            action_key="member_unban",
            details={"target_id": user.id},
        )

    @bot.listen("on_member_remove")
    async def anticrash_on_member_remove(member: disnake.Member) -> None:
        entry = await find_recent_audit_entry(
            member.guild,
            disnake.AuditLogAction.kick,
            lambda audit_entry: getattr(audit_entry.target, "id", None) == member.id,
        )
        if not entry or not entry_guard.remember(entry.id):
            return
        await service.handle_protected_action(
            guild=member.guild,
            executor_id=entry.user.id if entry.user else None,
            action_key="member_kick",
            details={"target_id": member.id},
        )

    @bot.listen("on_member_update")
    async def anticrash_on_member_update(
        before: disnake.Member,
        after: disnake.Member,
    ) -> None:
        added_role_ids = {role.id for role in after.roles} - {role.id for role in before.roles}
        removed_role_ids = {role.id for role in before.roles} - {role.id for role in after.roles}

        if added_role_ids or removed_role_ids:
            entry = await find_recent_audit_entry(
                after.guild,
                disnake.AuditLogAction.member_role_update,
                lambda audit_entry: getattr(audit_entry.target, "id", None) == after.id,
            )
            if entry and entry_guard.remember(entry.id):
                if added_role_ids:
                    await service.handle_protected_action(
                        guild=after.guild,
                        executor_id=entry.user.id if entry.user else None,
                        action_key="role_grant",
                        details={"target_id": after.id},
                    )
                if removed_role_ids:
                    await service.handle_protected_action(
                        guild=after.guild,
                        executor_id=entry.user.id if entry.user else None,
                        action_key="role_remove",
                        details={"target_id": after.id},
                    )

        old_timeout = before.current_timeout
        new_timeout = after.current_timeout
        if new_timeout and new_timeout != old_timeout and new_timeout > datetime.now(tz=timezone.utc):
            entry = await find_recent_audit_entry(
                after.guild,
                disnake.AuditLogAction.member_update,
                lambda audit_entry: getattr(audit_entry.target, "id", None) == after.id,
            )
            if not entry or not entry_guard.remember(entry.id):
                return
            await service.handle_protected_action(
                guild=after.guild,
                executor_id=entry.user.id if entry.user else None,
                action_key="member_timeout",
                details={"target_id": after.id},
            )

    @bot.listen("on_webhooks_update")
    async def anticrash_on_webhooks_update(channel: disnake.abc.GuildChannel) -> None:
        create_entry = await find_recent_audit_entry(
            channel.guild,
            disnake.AuditLogAction.webhook_create,
            lambda audit_entry: getattr(getattr(audit_entry, "extra", None), "channel", None) and audit_entry.extra.channel.id == channel.id,
        )
        if create_entry and entry_guard.remember(create_entry.id):
            await service.handle_protected_action(
                guild=channel.guild,
                executor_id=create_entry.user.id if create_entry.user else None,
                action_key="webhook_create",
                details={"target_id": getattr(create_entry.target, "id", None), "channel_id": channel.id},
            )

        delete_entry = await find_recent_audit_entry(
            channel.guild,
            disnake.AuditLogAction.webhook_delete,
            lambda audit_entry: getattr(getattr(audit_entry, "extra", None), "channel", None) and audit_entry.extra.channel.id == channel.id,
        )
        if delete_entry and entry_guard.remember(delete_entry.id):
            await service.handle_protected_action(
                guild=channel.guild,
                executor_id=delete_entry.user.id if delete_entry.user else None,
                action_key="webhook_delete",
                details={"target_id": getattr(delete_entry.target, "id", None), "channel_id": channel.id},
            )
