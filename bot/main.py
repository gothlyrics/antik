from __future__ import annotations

import asyncio

import disnake
from disnake.ext import commands

from bot.anticrash.listeners import register_anticrash_listeners
from bot.anticrash.repository import AntiCrashRepository, connect_database
from bot.anticrash.service import AntiCrashService
from bot.anticrash.session_store import AntiCrashSession, AntiCrashSessionStore
from bot.anticrash.views import has_manage_access, render_anticrash_panel
from bot.config import load_config


async def run_bot() -> None:
    config = load_config()
    connection = connect_database(config.database_path)
    repository = AntiCrashRepository(connection)
    session_store = AntiCrashSessionStore()

    intents = disnake.Intents.default()
    intents.guilds = True
    intents.guild_messages = True
    intents.members = True
    intents.message_content = True
    intents.moderation = True
    intents.webhooks = True

    bot = commands.InteractionBot(
        intents=intents,
        test_guilds=[config.guild_id],
    )

    service = AntiCrashService(bot, repository)
    register_anticrash_listeners(bot, service)

    @bot.event
    async def on_ready() -> None:
        print(f"Бот вошёл как {bot.user} (guild-scoped sync на {config.guild_id})")

    @bot.slash_command(
        name="anticrash_manage",
        description="Открыть меню управления anticrash / antinuke",
        dm_permission=False,
    )
    async def anticrash_manage(inter: disnake.AppCmdInter) -> None:
        if inter.guild is None or not isinstance(inter.author, disnake.Member):
            await inter.response.send_message(
                "Эта команда доступна только внутри сервера.",
                ephemeral=True,
            )
            return

        if not has_manage_access(inter.author, inter.guild):
            await inter.response.send_message(
                "У вас нет доступа к настройке anticrash. Нужен владелец сервера или Administrator.",
                ephemeral=True,
            )
            return

        repository.ensure_guild(inter.guild.id)
        session = AntiCrashSession(owner_id=inter.author.id, guild_id=inter.guild.id)
        embed, view = render_anticrash_panel(inter.guild, repository, session_store, session)
        await inter.response.send_message(embed=embed, view=view)
        message = await inter.original_message()
        session_store.create(message.id, session)

    try:
        await bot.start(config.token)
    finally:
        repository.close()


def main() -> None:
    asyncio.run(run_bot())


if __name__ == "__main__":
    main()
