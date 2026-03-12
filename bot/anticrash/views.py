from __future__ import annotations

from typing import Any

import disnake

from .constants import ACTION_DEFINITIONS, ACTION_SELECT_OPTIONS, ACTIONS_BY_KEY, PUNISHMENT_OPTIONS
from .service import format_policy
from .session_store import AntiCrashSession, AntiCrashSessionStore


def has_manage_access(member: disnake.Member | None, guild: disnake.Guild | None) -> bool:
    if member is None or guild is None:
        return False
    return member.id == guild.owner_id or member.guild_permissions.administrator


def _get_role_summary(guild: disnake.Guild, role_id: int | None) -> str:
    if not role_id:
        return "Роль не выбрана"
    role = guild.get_role(role_id)
    return role.mention if role else f"Не найдена ({role_id})"


def _list_mentions(ids: list[str], formatter, empty_text: str) -> str:
    if not ids:
        return empty_text
    return "\n".join(formatter(entry_id) for entry_id in ids[:15])


def _build_columns(role_config: dict[str, Any] | None) -> list[str]:
    columns = ["", "", ""]
    for index, action in enumerate(ACTION_DEFINITIONS):
        value = format_policy(role_config["limits"][action.key]) if role_config else "Выберите staff-роль"
        line = f"**{action.label}**\n{value}\n"
        columns[index % 3] += f"{line}\n"
    return [column.strip() or "Нет данных." for column in columns]


def _ensure_role_config(repository, session: AntiCrashSession) -> None:
    if session.selected_role_id is not None:
        repository.get_role_config(session.guild_id, session.selected_role_id)


def build_closed_embed() -> disnake.Embed:
    return disnake.Embed(
        title="AntiCrash | Меню закрыто",
        description="Сессия настройки завершена. Откройте `/anticrash_manage`, чтобы начать заново.",
        color=0x6D4C41,
    )


def build_main_embed(guild: disnake.Guild, dashboard_state: dict[str, Any], selected_role_id: int | None) -> disnake.Embed:
    role_config = dashboard_state["groups_by_role"].get(str(selected_role_id)) if selected_role_id else None
    first_column, second_column, third_column = _build_columns(role_config)
    guild_settings = dashboard_state["guild_settings"]

    punishment_label = "Выберите роль"
    if role_config:
        punishment_label = next(
            (option["label"] for option in PUNISHMENT_OPTIONS if option["value"] == role_config["punishment"]),
            "Не задано",
        )

    embed = disnake.Embed(
        title="AntiCrash Staff",
        description="\n".join(
            [
                f"Настройка staff-группы: {_get_role_summary(guild, selected_role_id)}",
                "",
                f"Лог-канал: <#{guild_settings['log_channel_id']}>" if guild_settings["log_channel_id"] else "Лог-канал: Не указан",
                f"Trusted роли: {len(dashboard_state['trusted_role_ids'])}",
                f"Белый лист: {len(dashboard_state['whitelist_user_ids'])}",
                f"Наказание: {punishment_label}",
            ]
        ),
        color=0x2D2F8F,
    )
    embed.add_field(name="Защиты I", value=first_column, inline=True)
    embed.add_field(name="Защиты II", value=second_column, inline=True)
    embed.add_field(name="Защиты III", value=third_column, inline=True)
    embed.set_footer(text="Выберите роль, затем нужную защиту или настройку.")
    return embed


def build_action_embed(
    guild: disnake.Guild,
    selected_role_id: int,
    role_config: dict[str, Any],
    action_key: str,
) -> disnake.Embed:
    action = ACTIONS_BY_KEY[action_key]
    punishment_label = next(
        (option["label"] for option in PUNISHMENT_OPTIONS if option["value"] == role_config["punishment"]),
        "Не задано",
    )
    embed = disnake.Embed(
        title=f"AntiCrash | {action.label}",
        description="\n".join(
            [
                f"Staff-группа: {_get_role_summary(guild, selected_role_id)}",
                "",
                action.description,
                "",
                f"Текущее значение: **{format_policy(role_config['limits'][action_key])}**",
                f"Наказание: **{punishment_label}**",
            ]
        ),
        color=0x3538C7,
    )
    embed.set_footer(text="Используйте кнопки ниже, чтобы запретить действие или задать лимит.")
    return embed


def build_punishment_embed(
    guild: disnake.Guild,
    selected_role_id: int,
    role_config: dict[str, Any],
) -> disnake.Embed:
    punishment_label = next(
        (option["label"] for option in PUNISHMENT_OPTIONS if option["value"] == role_config["punishment"]),
        "Не задано",
    )
    return disnake.Embed(
        title="AntiCrash | Наказание",
        description="\n".join(
            [
                f"Staff-группа: {_get_role_summary(guild, selected_role_id)}",
                "",
                f"Текущее наказание: **{punishment_label}**",
                "",
                "Выберите наказание для этой staff-группы.",
            ]
        ),
        color=0x3949AB,
    )


def build_whitelist_embed(
    dashboard_state: dict[str, Any],
    selected_user_id: int | None,
) -> disnake.Embed:
    return disnake.Embed(
        title="AntiCrash | Белый лист",
        description="\n".join(
            [
                "Пользователи из белого листа не попадают под anticrash-проверки.",
                "",
                f"Текущий выбор: <@{selected_user_id}>"
                if selected_user_id
                else "Текущий выбор: Не выбран",
                "",
                _list_mentions(
                    dashboard_state["whitelist_user_ids"],
                    lambda user_id: f"• <@{user_id}>",
                    "Список пока пуст.",
                ),
            ]
        ),
        color=0x283593,
    )


def build_trusted_roles_embed(
    guild: disnake.Guild,
    dashboard_state: dict[str, Any],
    selected_trusted_role_id: int | None,
) -> disnake.Embed:
    return disnake.Embed(
        title="AntiCrash | Trusted роли",
        description="\n".join(
            [
                "Участники с trusted-ролями не попадают под anticrash-проверки.",
                "",
                f"Текущий выбор: {_get_role_summary(guild, selected_trusted_role_id)}"
                if selected_trusted_role_id
                else "Текущий выбор: Не выбран",
                "",
                _list_mentions(
                    dashboard_state["trusted_role_ids"],
                    lambda role_id: f"• {_get_role_summary(guild, int(role_id))}",
                    "Trusted роли не заданы.",
                ),
            ]
        ),
        color=0x303F9F,
    )


def build_log_channel_embed(
    dashboard_state: dict[str, Any],
    selected_channel_id: int | None,
) -> disnake.Embed:
    current_channel = dashboard_state["guild_settings"]["log_channel_id"]
    return disnake.Embed(
        title="AntiCrash | Лог-канал",
        description="\n".join(
            [
                f"Текущий лог-канал: <#{current_channel}>"
                if current_channel
                else "Текущий лог-канал: Не указан",
                f"Новый выбор: <#{selected_channel_id}>"
                if selected_channel_id
                else "Новый выбор: Не выбран",
                "",
                "Выберите текстовый канал и сохраните настройку.",
            ]
        ),
        color=0x303F9F,
    )


def render_anticrash_panel(
    guild: disnake.Guild,
    repository,
    session_store: AntiCrashSessionStore,
    session: AntiCrashSession,
) -> tuple[disnake.Embed, "AntiCrashView"]:
    _ensure_role_config(repository, session)
    dashboard_state = repository.get_dashboard_state(session.guild_id)

    if session.view == "action" and session.selected_role_id and session.selected_action_key:
        role_config = repository.get_role_config(session.guild_id, session.selected_role_id)
        embed = build_action_embed(
            guild,
            session.selected_role_id,
            role_config,
            session.selected_action_key,
        )
    elif session.view == "punishment" and session.selected_role_id:
        role_config = repository.get_role_config(session.guild_id, session.selected_role_id)
        embed = build_punishment_embed(guild, session.selected_role_id, role_config)
    elif session.view == "whitelist":
        embed = build_whitelist_embed(dashboard_state, session.selected_user_id)
    elif session.view == "trusted_roles":
        embed = build_trusted_roles_embed(
            guild,
            dashboard_state,
            session.selected_trusted_role_id,
        )
    elif session.view == "log_channel":
        embed = build_log_channel_embed(dashboard_state, session.selected_channel_id)
    else:
        embed = build_main_embed(guild, dashboard_state, session.selected_role_id)

    return embed, AntiCrashView(repository, session_store, session, guild)


async def edit_panel(
    inter: disnake.MessageInteraction,
    repository,
    session_store: AntiCrashSessionStore,
    session: AntiCrashSession,
) -> None:
    embed, view = render_anticrash_panel(inter.guild, repository, session_store, session)
    await inter.response.edit_message(embed=embed, view=view)


class AntiCrashView(disnake.ui.View):
    def __init__(
        self,
        repository,
        session_store: AntiCrashSessionStore,
        session: AntiCrashSession,
        guild: disnake.Guild,
    ) -> None:
        super().__init__(timeout=1800)
        self.repository = repository
        self.session_store = session_store
        self.session = session
        self.guild = guild
        self._build_items()

    async def interaction_check(self, inter: disnake.MessageInteraction) -> bool:
        if inter.author.id != self.session.owner_id:
            await inter.response.send_message(
                "Это меню привязано к другому администратору. Откройте собственное `/anticrash_manage`.",
                ephemeral=True,
            )
            return False

        if not has_manage_access(inter.author, inter.guild):
            await inter.response.send_message(
                "У вас больше нет прав для настройки anticrash.",
                ephemeral=True,
            )
            return False

        return True

    async def on_timeout(self) -> None:
        if self.session.message_id is not None:
            self.session_store.delete(self.session.message_id)

    def _build_items(self) -> None:
        self.clear_items()

        if self.session.view == "main":
            self.add_item(StaffRoleSelect(self.repository, self.session_store, self.session))
            self.add_item(EntrySelect(self.repository, self.session_store, self.session))
            self.add_item(ActionButton("back-main", "Вернуться в меню", disnake.ButtonStyle.primary, self.repository, self.session_store, self.session))
            self.add_item(ActionButton("open-whitelist", "Список белого листа", disnake.ButtonStyle.secondary, self.repository, self.session_store, self.session))
            self.add_item(ActionButton("close", "Выход", disnake.ButtonStyle.danger, self.repository, self.session_store, self.session))
            return

        if self.session.view == "action":
            self.add_item(ActionButton("set-forbidden", "Запретить", disnake.ButtonStyle.secondary, self.repository, self.session_store, self.session))
            self.add_item(ActionButton("open-limit-modal", "Установить лимит", disnake.ButtonStyle.success, self.repository, self.session_store, self.session))
            self.add_item(ActionButton("back-main", "Назад", disnake.ButtonStyle.primary, self.repository, self.session_store, self.session))
            self.add_item(ActionButton("close", "Выход", disnake.ButtonStyle.danger, self.repository, self.session_store, self.session))
            return

        if self.session.view == "punishment":
            self.add_item(PunishmentSelect(self.repository, self.session_store, self.session))
            self.add_item(ActionButton("back-main", "Назад", disnake.ButtonStyle.primary, self.repository, self.session_store, self.session))
            self.add_item(ActionButton("close", "Выход", disnake.ButtonStyle.danger, self.repository, self.session_store, self.session))
            return

        if self.session.view == "whitelist":
            self.add_item(WhitelistUserSelect(self.repository, self.session_store, self.session))
            self.add_item(ActionButton("add-whitelist", "Добавить", disnake.ButtonStyle.success, self.repository, self.session_store, self.session))
            self.add_item(ActionButton("remove-whitelist", "Удалить", disnake.ButtonStyle.secondary, self.repository, self.session_store, self.session))
            self.add_item(ActionButton("back-main", "Назад", disnake.ButtonStyle.primary, self.repository, self.session_store, self.session))
            self.add_item(ActionButton("close", "Выход", disnake.ButtonStyle.danger, self.repository, self.session_store, self.session))
            return

        if self.session.view == "trusted_roles":
            self.add_item(TrustedRoleSelect(self.repository, self.session_store, self.session))
            self.add_item(ActionButton("add-trusted-role", "Добавить", disnake.ButtonStyle.success, self.repository, self.session_store, self.session))
            self.add_item(ActionButton("remove-trusted-role", "Удалить", disnake.ButtonStyle.secondary, self.repository, self.session_store, self.session))
            self.add_item(ActionButton("back-main", "Назад", disnake.ButtonStyle.primary, self.repository, self.session_store, self.session))
            self.add_item(ActionButton("close", "Выход", disnake.ButtonStyle.danger, self.repository, self.session_store, self.session))
            return

        if self.session.view == "log_channel":
            self.add_item(LogChannelSelect(self.repository, self.session_store, self.session))
            self.add_item(ActionButton("save-log-channel", "Сохранить", disnake.ButtonStyle.success, self.repository, self.session_store, self.session))
            self.add_item(ActionButton("clear-log-channel", "Очистить", disnake.ButtonStyle.secondary, self.repository, self.session_store, self.session))
            self.add_item(ActionButton("back-main", "Назад", disnake.ButtonStyle.primary, self.repository, self.session_store, self.session))
            self.add_item(ActionButton("close", "Выход", disnake.ButtonStyle.danger, self.repository, self.session_store, self.session))


class StaffRoleSelect(disnake.ui.RoleSelect):
    def __init__(self, repository, session_store: AntiCrashSessionStore, session: AntiCrashSession) -> None:
        super().__init__(
            placeholder="Выберите staff-роль",
            min_values=1,
            max_values=1,
            custom_id="anticrash:select-role",
            row=0,
        )
        self.repository = repository
        self.session_store = session_store
        self.session = session

    async def callback(self, inter: disnake.MessageInteraction) -> None:
        role = self.values[0]
        self.session.selected_role_id = role.id
        self.session.selected_action_key = None
        self.session.view = "main"
        await edit_panel(inter, self.repository, self.session_store, self.session)


class EntrySelect(disnake.ui.StringSelect):
    def __init__(self, repository, session_store: AntiCrashSessionStore, session: AntiCrashSession) -> None:
        options = [
            disnake.SelectOption(
                label=entry["label"],
                value=entry["value"],
                description=entry["description"],
            )
            for entry in ACTION_SELECT_OPTIONS
        ]
        super().__init__(
            placeholder="Выберите функцию или настройку",
            custom_id="anticrash:select-entry",
            options=options,
            row=1,
        )
        self.repository = repository
        self.session_store = session_store
        self.session = session

    async def callback(self, inter: disnake.MessageInteraction) -> None:
        value = self.values[0]

        if value.startswith("action:"):
            if self.session.selected_role_id is None:
                await inter.response.send_message(
                    "Сначала выберите staff-роль в верхнем select menu.",
                    ephemeral=True,
                )
                return
            self.session.selected_action_key = value.replace("action:", "", 1)
            self.session.view = "action"
            await edit_panel(inter, self.repository, self.session_store, self.session)
            return

        if value == "setting:punishment":
            if self.session.selected_role_id is None:
                await inter.response.send_message(
                    "Сначала выберите staff-роль в верхнем select menu.",
                    ephemeral=True,
                )
                return
            self.session.view = "punishment"
            await edit_panel(inter, self.repository, self.session_store, self.session)
            return

        if value == "setting:trusted_roles":
            self.session.view = "trusted_roles"
            await edit_panel(inter, self.repository, self.session_store, self.session)
            return

        if value == "setting:log_channel":
            self.session.view = "log_channel"
            await edit_panel(inter, self.repository, self.session_store, self.session)


class PunishmentSelect(disnake.ui.StringSelect):
    def __init__(self, repository, session_store: AntiCrashSessionStore, session: AntiCrashSession) -> None:
        role_config = repository.get_role_config(session.guild_id, session.selected_role_id)
        options = [
            disnake.SelectOption(
                label=option["label"],
                value=option["value"],
                description=option["description"],
                default=option["value"] == role_config["punishment"],
            )
            for option in PUNISHMENT_OPTIONS
        ]
        super().__init__(
            placeholder="Выберите наказание",
            custom_id="anticrash:select-punishment",
            options=options,
            row=0,
        )
        self.repository = repository
        self.session_store = session_store
        self.session = session

    async def callback(self, inter: disnake.MessageInteraction) -> None:
        if self.session.selected_role_id is None:
            await inter.response.send_message(
                "Сначала выберите staff-роль в верхнем select menu.",
                ephemeral=True,
            )
            return
        self.repository.set_punishment(
            self.session.guild_id,
            self.session.selected_role_id,
            self.values[0],
        )
        await edit_panel(inter, self.repository, self.session_store, self.session)


class WhitelistUserSelect(disnake.ui.UserSelect):
    def __init__(self, repository, session_store: AntiCrashSessionStore, session: AntiCrashSession) -> None:
        super().__init__(
            placeholder="Выберите пользователя",
            min_values=1,
            max_values=1,
            custom_id="anticrash:select-whitelist-user",
            row=0,
        )
        self.repository = repository
        self.session_store = session_store
        self.session = session

    async def callback(self, inter: disnake.MessageInteraction) -> None:
        self.session.selected_user_id = self.values[0].id
        await edit_panel(inter, self.repository, self.session_store, self.session)


class TrustedRoleSelect(disnake.ui.RoleSelect):
    def __init__(self, repository, session_store: AntiCrashSessionStore, session: AntiCrashSession) -> None:
        super().__init__(
            placeholder="Выберите trusted-роль",
            min_values=1,
            max_values=1,
            custom_id="anticrash:select-trusted-role",
            row=0,
        )
        self.repository = repository
        self.session_store = session_store
        self.session = session

    async def callback(self, inter: disnake.MessageInteraction) -> None:
        self.session.selected_trusted_role_id = self.values[0].id
        await edit_panel(inter, self.repository, self.session_store, self.session)


class LogChannelSelect(disnake.ui.ChannelSelect):
    def __init__(self, repository, session_store: AntiCrashSessionStore, session: AntiCrashSession) -> None:
        super().__init__(
            placeholder="Выберите лог-канал",
            min_values=1,
            max_values=1,
            custom_id="anticrash:select-log-channel",
            channel_types=[disnake.ChannelType.text, disnake.ChannelType.news],
            row=0,
        )
        self.repository = repository
        self.session_store = session_store
        self.session = session

    async def callback(self, inter: disnake.MessageInteraction) -> None:
        self.session.selected_channel_id = self.values[0].id
        await edit_panel(inter, self.repository, self.session_store, self.session)


class ActionButton(disnake.ui.Button):
    def __init__(
        self,
        action: str,
        label: str,
        style: disnake.ButtonStyle,
        repository,
        session_store: AntiCrashSessionStore,
        session: AntiCrashSession,
    ) -> None:
        super().__init__(label=label, style=style, custom_id=f"anticrash:{action}")
        self.action = action
        self.repository = repository
        self.session_store = session_store
        self.session = session

    async def callback(self, inter: disnake.MessageInteraction) -> None:
        if self.action == "back-main":
            self.session.view = "main"
            self.session.selected_action_key = None
            self.session.selected_channel_id = None
            self.session.selected_user_id = None
            self.session.selected_trusted_role_id = None
            await edit_panel(inter, self.repository, self.session_store, self.session)
            return

        if self.action == "open-whitelist":
            self.session.view = "whitelist"
            await edit_panel(inter, self.repository, self.session_store, self.session)
            return

        if self.action == "close":
            if self.session.message_id is not None:
                self.session_store.delete(self.session.message_id)
            await inter.response.edit_message(embed=build_closed_embed(), view=None)
            return

        if self.action == "set-forbidden":
            if self.session.selected_role_id is None or self.session.selected_action_key is None:
                await inter.response.send_message(
                    "Сначала выберите staff-роль и функцию.",
                    ephemeral=True,
                )
                return
            self.repository.upsert_limit(
                self.session.guild_id,
                self.session.selected_role_id,
                self.session.selected_action_key,
                "forbidden",
                None,
            )
            await edit_panel(inter, self.repository, self.session_store, self.session)
            return

        if self.action == "open-limit-modal":
            if self.session.selected_role_id is None or self.session.selected_action_key is None:
                await inter.response.send_message(
                    "Сначала выберите staff-роль и функцию.",
                    ephemeral=True,
                )
                return
            await inter.response.send_modal(
                LimitModal(self.repository, self.session_store, self.session)
            )
            return

        if self.action == "add-whitelist":
            if self.session.selected_user_id is None:
                await inter.response.send_message("Сначала выберите пользователя.", ephemeral=True)
                return
            self.repository.add_whitelist_user(self.session.guild_id, self.session.selected_user_id)
            await edit_panel(inter, self.repository, self.session_store, self.session)
            return

        if self.action == "remove-whitelist":
            if self.session.selected_user_id is None:
                await inter.response.send_message("Сначала выберите пользователя.", ephemeral=True)
                return
            self.repository.remove_whitelist_user(self.session.guild_id, self.session.selected_user_id)
            await edit_panel(inter, self.repository, self.session_store, self.session)
            return

        if self.action == "add-trusted-role":
            if self.session.selected_trusted_role_id is None:
                await inter.response.send_message("Сначала выберите trusted-роль.", ephemeral=True)
                return
            self.repository.add_trusted_role(
                self.session.guild_id,
                self.session.selected_trusted_role_id,
            )
            await edit_panel(inter, self.repository, self.session_store, self.session)
            return

        if self.action == "remove-trusted-role":
            if self.session.selected_trusted_role_id is None:
                await inter.response.send_message("Сначала выберите trusted-роль.", ephemeral=True)
                return
            self.repository.remove_trusted_role(
                self.session.guild_id,
                self.session.selected_trusted_role_id,
            )
            await edit_panel(inter, self.repository, self.session_store, self.session)
            return

        if self.action == "save-log-channel":
            if self.session.selected_channel_id is None:
                await inter.response.send_message("Сначала выберите канал.", ephemeral=True)
                return
            self.repository.set_log_channel(
                self.session.guild_id,
                self.session.selected_channel_id,
            )
            await edit_panel(inter, self.repository, self.session_store, self.session)
            return

        if self.action == "clear-log-channel":
            self.repository.clear_log_channel(self.session.guild_id)
            self.session.selected_channel_id = None
            await edit_panel(inter, self.repository, self.session_store, self.session)


class LimitModal(disnake.ui.Modal):
    def __init__(self, repository, session_store: AntiCrashSessionStore, session: AntiCrashSession) -> None:
        self.repository = repository
        self.session_store = session_store
        self.session = session
        action_label = ACTIONS_BY_KEY.get(session.selected_action_key).label if session.selected_action_key else "защиты"
        components = [
            disnake.ui.TextInput(
                label=f"Лимит для: {action_label}",
                custom_id="limit-value",
                placeholder="Например: 3",
                min_length=1,
                max_length=3,
                style=disnake.TextInputStyle.short,
            )
        ]
        super().__init__(
            title="Установить лимит",
            custom_id=f"anticrash:submit-limit:{session.message_id}",
            components=components,
        )

    async def callback(self, inter: disnake.ModalInteraction) -> None:
        raw_value = inter.text_values.get("limit-value", "").strip()
        try:
            limit = int(raw_value)
        except ValueError:
            await inter.response.send_message(
                "Лимит должен быть целым числом от 1 до 999.",
                ephemeral=True,
            )
            return

        if limit < 1 or limit > 999:
            await inter.response.send_message(
                "Лимит должен быть целым числом от 1 до 999.",
                ephemeral=True,
            )
            return

        self.repository.upsert_limit(
            self.session.guild_id,
            self.session.selected_role_id,
            self.session.selected_action_key,
            "limit",
            limit,
        )

        message = None
        if inter.channel and self.session.message_id:
            try:
                message = await inter.channel.fetch_message(self.session.message_id)
            except disnake.HTTPException:
                message = None

        if message and inter.guild:
            embed, view = render_anticrash_panel(
                inter.guild,
                self.repository,
                self.session_store,
                self.session,
            )
            await message.edit(embed=embed, view=view)

        await inter.response.send_message(f"Лимит сохранён: {limit}.", ephemeral=True)
