import discord
from discord.ext import commands
import asyncio
from pathlib import Path
import json
import os
import sys
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("rpbot")


def parse_channel_ids(raw_channels) -> set[int]:
    if isinstance(raw_channels, int):
        raw_channels = [raw_channels]

    channel_ids = set()
    for channel_id in raw_channels or []:
        try:
            channel_ids.add(int(channel_id))
        except (TypeError, ValueError):
            continue

    return channel_ids


def validate_config(config: dict) -> dict:
    validated = dict(config) if isinstance(config, dict) else {}

    command_prefix = validated.get("command_prefix", "!")
    if not isinstance(command_prefix, str) or not command_prefix.strip():
        logger.warning("Invalid command_prefix in config; falling back to '!'.")
        validated["command_prefix"] = "!"

    allowed_channels = validated.get("allowed_channels", [])
    if not isinstance(allowed_channels, (list, int)):
        logger.warning("Invalid allowed_channels in config; falling back to empty list.")
        allowed_channels = []
    validated["allowed_channels"] = sorted(parse_channel_ids(allowed_channels))

    for key in ("ydl_options", "ffmpeg_options", "ai"):
        value = validated.get(key)
        if value is not None and not isinstance(value, dict):
            logger.warning("Invalid %s in config; falling back to empty dict.", key)
            validated[key] = {}

    return validated

def load_config():
    config_path = Path(__file__).parent / "config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_content():
    content_path = Path(__file__).parent / "content.json"
    with open(content_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_discord_token():
    token_path = Path(__file__).parent / "token"
    if not token_path.exists():
        raise FileNotFoundError("Token file was not found. Create a file named 'token' in the project root.")

    token = token_path.read_text(encoding="utf-8").strip()
    if not token:
        raise ValueError("Token file is empty.")

    return token


CONFIG = validate_config(load_config())
CONTENT = load_content()
DISCORD_TOKEN = load_discord_token()
COMMAND_PREFIX = CONFIG["command_prefix"]
RESTART_REQUESTED = False


intents = discord.Intents.default()
intents.message_content = True
intents.members = True

bot = commands.Bot(command_prefix=COMMAND_PREFIX, intents=intents)
bot.config = CONFIG
bot.content = CONTENT
bot.allowed_channel_ids = parse_channel_ids(CONFIG.get("allowed_channels", []))


async def send_log(message: str):
    log_channel_id = bot.config.get("log_channel_id")
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

bot.send_log = send_log

@bot.event
async def on_ready():
    print(f'Logged in as: {bot.user}')
    print(f'Bot ID: {bot.user.id}')
    print('------')
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

    allowed_channel_ids = bot.allowed_channel_ids
    if not allowed_channel_ids:
        await bot.invoke(ctx)
        return

    temp_voice_channel_ids = getattr(bot, "temp_voice_channel_ids", set())
    if message.channel.id not in allowed_channel_ids and message.channel.id not in temp_voice_channel_ids:
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
    elif isinstance(error, (commands.ChannelNotFound)):
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
        f"Allowed channels: **{len(bot.allowed_channel_ids)}**",
        f"Message content intent: **{'ano' if bot.intents.message_content else 'ne'}**",
        f"Members intent: **{'ano' if bot.intents.members else 'ne'}**",
    ]
    await ctx.send("\n".join(lines))

async def load_cogs():
    base_dir = Path(__file__).parent / "cogs"

    for file in sorted(base_dir.rglob("*.py")):
        if file.name == "__init__.py" or file.name.startswith("_"):
            continue

        rel = file.relative_to(Path(__file__).parent).with_suffix("")
        module = ".".join(rel.parts)

        try:
            await bot.load_extension(module)
            print(f"Loaded: {module}")
        except Exception as e:
            print(f"Error loading {module}: {e}")

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


if __name__ == '__main__':
    asyncio.run(main())
    if RESTART_REQUESTED:
        print("Restart requested, restarting bot...")
        os.execv(sys.executable, [sys.executable, *sys.argv])
