from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

import disnake

from .constants import (
    ACTIONS_BY_KEY,
    DEFAULT_PUNISHMENT,
    DEFAULT_WINDOW_SECONDS,
    MASS_MENTION_THRESHOLD,
    PUNISHMENT_OPTIONS,
)


def format_policy(policy: dict[str, Any] | None) -> str:
    if not policy:
        return "Не настроено"
    if policy["mode"] == "forbidden":
        return "Запрещено"
    return f"{policy['limit_value']} / 60 сек."


def resolve_strictest_policy(
    member_role_ids: list[str],
    groups_by_role: dict[str, dict[str, Any]],
    action_key: str,
) -> dict[str, Any] | None:
    applicable: list[dict[str, Any]] = []
    for role_id in member_role_ids:
        group = groups_by_role.get(role_id)
        if not group:
            continue
        applicable.append(
            {
                "role_id": group["role_id"],
                "punishment": group.get("punishment", DEFAULT_PUNISHMENT),
                "policy": group["limits"].get(
                    action_key, {"mode": "forbidden", "limit_value": None}
                ),
            }
        )

    if not applicable:
        return None

    for entry in applicable:
        if entry["policy"]["mode"] == "forbidden":
            return entry

    return min(applicable, key=lambda item: item["policy"]["limit_value"])


def should_bypass_protection(
    *,
    member: disnake.Member | None,
    guild_owner_id: int,
    bot_user_id: int | None,
    whitelist_user_ids: list[str],
    trusted_role_ids: list[str],
) -> bool:
    if member is None:
        return True
    if member.id in {guild_owner_id, bot_user_id}:
        return True
    if str(member.id) in whitelist_user_ids:
        return True
    return any(str(role.id) in trusted_role_ids for role in member.roles)


def register_action_hit(
    counter_store: dict[str, list[float]],
    key: str,
    limit: int,
    *,
    now: float,
    window_seconds: int = DEFAULT_WINDOW_SECONDS,
) -> dict[str, Any]:
    hits = counter_store.get(key, [])
    fresh_hits = [timestamp for timestamp in hits if now - timestamp < window_seconds]
    fresh_hits.append(now)
    counter_store[key] = fresh_hits
    return {
        "count": len(fresh_hits),
        "limit": limit,
        "triggered": len(fresh_hits) > limit,
    }


def detect_mass_mention(message: disnake.Message) -> bool:
    total_mentions = len(message.mentions) + len(message.role_mentions)
    return message.mention_everyone or total_mentions >= MASS_MENTION_THRESHOLD


class AntiCrashService:
    def __init__(self, bot: disnake.Client, repository: Any) -> None:
        self.bot = bot
        self.repository = repository
        self.counter_store: dict[str, list[float]] = defaultdict(list)

    def get_punishment_label(self, value: str | None) -> str:
        for option in PUNISHMENT_OPTIONS:
            if option["value"] == value:
                return option["label"]
        return "Неизвестно"

    async def handle_protected_action(
        self,
        *,
        guild: disnake.Guild,
        executor_id: int | None,
        action_key: str,
        details: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if guild is None or executor_id is None or executor_id == getattr(self.bot.user, "id", None):
            return {"status": "ignored"}

        state = self.repository.get_dashboard_state(guild.id)
        member = guild.get_member(executor_id)
        if member is None:
            try:
                member = await guild.fetch_member(executor_id)
            except disnake.HTTPException:
                member = None

        if should_bypass_protection(
            member=member,
            guild_owner_id=guild.owner_id,
            bot_user_id=getattr(self.bot.user, "id", None),
            whitelist_user_ids=state["whitelist_user_ids"],
            trusted_role_ids=state["trusted_role_ids"],
        ):
            return {"status": "bypassed"}

        details = details or {}
        if member is None:
            await self.send_violation_log(
                guild=guild,
                action_key=action_key,
                policy=None,
                punishment=None,
                executor_tag=f"Не удалось получить участника ({executor_id})",
                result_text="Нарушитель не найден в кэше/гильдии, наказание не применено.",
                details=details,
            )
            return {"status": "member-missing"}

        ordered_role_ids = [
            str(role.id)
            for role in sorted(member.roles, key=lambda role: role.position, reverse=True)
        ]
        matched = resolve_strictest_policy(ordered_role_ids, state["groups_by_role"], action_key)
        if not matched:
            return {"status": "no-policy"}

        if matched["policy"]["mode"] == "limit":
            counter_key = f"{guild.id}:{member.id}:{action_key}"
            counter = register_action_hit(
                self.counter_store,
                counter_key,
                int(matched["policy"]["limit_value"]),
                now=datetime.now(tz=timezone.utc).timestamp(),
            )
            if not counter["triggered"]:
                return {"status": "within-limit", "counter": counter}

        punishment_result = await self.apply_punishment(
            member, matched["punishment"], state["groups_by_role"]
        )
        await self.send_violation_log(
            guild=guild,
            action_key=action_key,
            policy=matched["policy"],
            punishment=matched["punishment"],
            executor_tag=f"{member} ({member.id})",
            result_text=punishment_result["message"],
            details=details,
        )
        return {
            "status": "punished",
            "matched": matched,
            "punishment_result": punishment_result,
        }

    async def handle_mass_mention(self, message: disnake.Message) -> dict[str, Any]:
        if (
            message.guild is None
            or message.author.bot
            or message.author.id == getattr(self.bot.user, "id", None)
        ):
            return {"status": "ignored"}
        if not detect_mass_mention(message):
            return {"status": "ignored"}

        return await self.handle_protected_action(
            guild=message.guild,
            executor_id=message.author.id,
            action_key="mass_mentions",
            details={
                "channel_id": message.channel.id,
                "message_url": message.jump_url,
                "mention_count": len(message.mentions) + len(message.role_mentions),
                "mentions_everyone": message.mention_everyone,
            },
        )

    async def apply_punishment(
        self,
        member: disnake.Member,
        punishment: str,
        groups_by_role: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        reason = "AntiCrash: превышение лимита или запрещённое действие."
        guild = member.guild
        bot_member = guild.me

        if bot_member is None:
            return {
                "success": False,
                "message": "Бот не найден как участник гильдии, наказание не применено.",
            }

        if punishment == "ban":
            if (
                not self._can_moderate_member(bot_member, member)
                or not bot_member.guild_permissions.ban_members
            ):
                return {
                    "success": False,
                    "message": "Бот не может забанить нарушителя из-за прав или иерархии.",
                }
            try:
                await member.ban(reason=reason)
                return {"success": True, "message": "Нарушитель забанен."}
            except disnake.HTTPException as error:
                return {"success": False, "message": f"Наказание не применено: {error}"}

        if punishment == "kick":
            if (
                not self._can_moderate_member(bot_member, member)
                or not bot_member.guild_permissions.kick_members
            ):
                return {
                    "success": False,
                    "message": "Бот не может кикнуть нарушителя из-за прав или иерархии.",
                }
            try:
                await member.kick(reason=reason)
                return {"success": True, "message": "Нарушитель кикнут."}
            except disnake.HTTPException as error:
                return {"success": False, "message": f"Наказание не применено: {error}"}

        protected_role_ids = {int(role_id) for role_id in groups_by_role.keys()}
        removable_roles = [
            role
            for role in member.roles
            if role.id in protected_role_ids
            and role != guild.default_role
            and not role.managed
            and role < bot_member.top_role
        ]

        if not removable_roles:
            return {
                "success": False,
                "message": "Бот не нашёл управляемых staff-ролей для снятия.",
            }

        try:
            await member.remove_roles(*removable_roles, reason=reason)
            return {
                "success": True,
                "message": f"Снято staff-ролей: {len(removable_roles)}.",
            }
        except disnake.HTTPException as error:
            return {"success": False, "message": f"Наказание не применено: {error}"}

    async def send_violation_log(
        self,
        *,
        guild: disnake.Guild,
        action_key: str,
        policy: dict[str, Any] | None,
        punishment: str | None,
        executor_tag: str,
        result_text: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        settings = self.repository.get_guild_settings(guild.id)
        log_channel_id = settings.get("log_channel_id")
        if not log_channel_id:
            return

        log_channel = guild.get_channel(int(log_channel_id))
        if log_channel is None:
            try:
                log_channel = await self.bot.fetch_channel(int(log_channel_id))
            except disnake.HTTPException:
                return
        if not hasattr(log_channel, "send"):
            return

        definition = ACTIONS_BY_KEY.get(action_key)
        details = details or {}
        result_lower = result_text.lower()
        color = 0xFFA726 if "не может" in result_lower or "не применено" in result_lower else 0xFF4D6D
        embed = disnake.Embed(
            title="AntiCrash | Нарушение зафиксировано",
            description=f"Защита сработала на действие **{definition.event_label if definition else action_key}**.",
            color=color,
            timestamp=datetime.now(tz=timezone.utc),
        )
        embed.add_field(name="Нарушитель", value=executor_tag, inline=False)
        embed.add_field(name="Лимит / режим", value=format_policy(policy), inline=True)
        embed.add_field(name="Наказание", value=self.get_punishment_label(punishment), inline=True)
        embed.add_field(
            name="Время",
            value=f"<t:{int(datetime.now(tz=timezone.utc).timestamp())}:F>",
            inline=False,
        )
        embed.add_field(name="Результат", value=result_text, inline=False)
        embed.set_footer(text="Sataki AntiCrash")

        if details.get("message_url"):
            embed.add_field(name="Ссылка на сообщение", value=details["message_url"], inline=False)
        if details.get("target_id"):
            embed.add_field(name="Target ID", value=str(details["target_id"]), inline=True)
        if details.get("channel_id"):
            embed.add_field(name="Канал", value=f"<#{details['channel_id']}>", inline=True)

        try:
            await log_channel.send(embed=embed)
        except disnake.HTTPException:
            return

    @staticmethod
    def _can_moderate_member(bot_member: disnake.Member, target: disnake.Member) -> bool:
        return target.id != target.guild.owner_id and bot_member.top_role > target.top_role
