import asyncio
import logging
import os
import sys
from pathlib import Path
from typing import cast

import discord
from discord.ext import commands
from dotenv import load_dotenv

from config_manager import ALLOWED_CHANNEL_IDS, CONFIG

load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rpbot")

raw_token = os.getenv("DISCORD_TOKEN")
if not raw_token:
    raise ValueError("Token not found in .env file.")
DISCORD_TOKEN = cast(str, raw_token)

COMMAND_PREFIX = CONFIG["command_prefix"]
RESTART_REQUESTED = False

intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)


async def send_log(message: str):
    log_channel_id = CONFIG.get("log_channel_id")
    if not log_channel_id:
        return

    try:
        channel_id = int(log_channel_id)
    except (TypeError, ValueError):
        logger.warning("Invalid log_channel_id in config: %s", log_channel_id)
        return

    channel = bot.get_channel(channel_id)
    if channel is None:
        try:
            channel = await bot.fetch_channel(channel_id)
        except (discord.NotFound, discord.Forbidden, discord.HTTPException):
            logger.warning("Unable to fetch log channel: %s", channel_id)
            return

    if isinstance(channel, (discord.TextChannel, discord.Thread)):
        try:
            await channel.send(message)
        except (discord.Forbidden, discord.HTTPException):
            logger.warning("Unable to send message to log channel: %s", channel_id)


@bot.event
async def on_ready():
    if not bot.user:
        return
    logger.info("Logged in as: %s", bot.user)
    logger.info("Bot ID: %s", bot.user.id)
    logger.info("------")
    await send_log(f"Bot je online jako **{bot.user}** (ID: `{bot.user.id}`).")


@bot.event
async def on_command(ctx):
    await send_log(
        f"Příkaz `{ctx.command}` použil **{ctx.author}** v {ctx.channel.mention}."
    )


@bot.event
async def on_message(message):
    if message.author.bot:
        return

    ctx = await bot.get_context(message)

    if ctx.command and getattr(ctx.command, "cog_name", None) in {"Admin", "AI"}:
        await bot.invoke(ctx)
        return

    if not ALLOWED_CHANNEL_IDS:
        await bot.invoke(ctx)
        return

    temp_voice_channel_ids = getattr(bot, "temp_voice_channel_ids", set())
    if (
        message.channel.id not in ALLOWED_CHANNEL_IDS
        and message.channel.id not in temp_voice_channel_ids
    ):
        return

    await bot.invoke(ctx)


@bot.event
async def on_command_error(ctx, error):
    if isinstance(error, commands.MissingPermissions):
        await ctx.send("Tento příkaz je určen pouze administrátorům.")
        await send_log(
            f"Nedostatečná oprávnění: **{ctx.author}** zkusil `{ctx.command}` v {ctx.channel.mention}."
        )
    elif isinstance(error, commands.NoPrivateMessage):
        await ctx.send("Tento příkaz nelze použít v soukromých zprávách.")
        await send_log(f"Zablokovaný DM příkaz `{ctx.command}` od **{ctx.author}**.")
    elif isinstance(error, commands.ChannelNotFound):
        await ctx.send("Neplatný kanál.")
        await send_log(
            f"Neplatný argument kanálu v `{ctx.command}` od **{ctx.author}**."
        )
    elif isinstance(error, commands.CommandNotFound):
        pass
    else:
        await send_log(
            f"Nezachycená chyba v `{ctx.command}` od **{ctx.author}**: `{error}`"
        )
        raise error


@bot.command(name="status")
async def status(ctx):
    cogs = ", ".join(sorted(bot.cogs.keys())) or "žádné"
    lines = [
        f"Prefix: **{COMMAND_PREFIX}**",
        f"Latency: **{bot.latency * 1000:.0f} ms**",
        f"Servery: **{len(bot.guilds)}**",
        f"Načtené cogy: **{cogs}**",
        f"Allowed channels: **{len(ALLOWED_CHANNEL_IDS)}**",
        f"Message content intent: **{'ano' if bot.intents.message_content else 'ne'}**",
        f"Members intent: **{'ano' if bot.intents.members else 'ne'}**",
    ]
    await ctx.send("\n".join(lines))


async def load_cogs():
    base_dir = Path(__file__).parent / "cogs"
    if not base_dir.exists():
        return

    for file in sorted(base_dir.rglob("*.py")):
        if file.name == "__init__.py" or file.name.startswith("_"):
            continue

        rel = file.relative_to(Path(__file__).parent).with_suffix("")
        module = ".".join(rel.parts)

        try:
            await bot.load_extension(module)
            logger.info("Loaded: %s", module)
        except Exception as e:
            logger.error("Error loading %s: %s", module, e)


async def main():
    async with bot:
        await load_cogs()
        await bot.start(DISCORD_TOKEN)


@bot.command()
@commands.has_permissions(administrator=True)
async def restart(ctx):
    global RESTART_REQUESTED
    RESTART_REQUESTED = True
    await ctx.send("Restartuji bota...")
    await send_log(f"Restart vyžádal **{ctx.author}**.")
    await bot.close()


@bot.command()
@commands.has_permissions(administrator=True)
async def end(ctx):
    await ctx.send("Vypínám bota...")
    await send_log(f"Vypnutí vyžádal **{ctx.author}**.")
    await bot.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot byl ukončen uživatelem.")

    if RESTART_REQUESTED:
        logger.info("Restart requested, restarting bot...")
        os.execv(sys.executable, [sys.executable, *sys.argv])
