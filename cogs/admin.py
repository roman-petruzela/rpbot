import asyncio
import inspect

import discord
from discord.ext import commands

from config_manager import ALLOWED_CHANNEL_IDS, CONFIG, CONTENT, save_config


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def pravidla(self, ctx: commands.Context):
        rules_gif_path = CONTENT.get("rules_gif_path", "")
        rules_text = CONTENT.get("rules_text", "")
        invite_url = CONTENT.get("invite_url", "")
        embed_color = CONTENT.get("embed_color", "")

        await ctx.send(file=discord.File(rules_gif_path))
        await ctx.send(rules_text)
        embed = discord.Embed(
            title="Pozvi své kamarády!",
            description=f"```{invite_url}```",
            color=discord.Color.from_str(embed_color),
        )
        view = discord.ui.View()
        await ctx.send(embed=embed, view=view)

    @commands.command(name="roleall")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def roleall(self, ctx: commands.Context, role: discord.Role):
        guild = ctx.guild
        if guild is None:
            return

        me = guild.me
        if me is None:
            return await ctx.send("Kritická chyba: účet bota nebyl na serveru nalezen.")

        app_role = guild.self_role if hasattr(guild, "self_role") else None
        role_limit = app_role or me.top_role

        if not guild.me.guild_permissions.manage_roles:
            return await ctx.send(
                "Chybí oprávnění: pro tuto akci potřebuji oprávnění 'Spravovat role'."
            )

        if role >= role_limit:
            if app_role is not None:
                return await ctx.send(
                    "Tuto roli nemohu přiřadit, protože je vyšší nebo stejná jako aplikační role bota."
                )
            return await ctx.send(
                "Tuto roli nemohu přiřadit, protože je vyšší nebo stejná jako moje nejvyšší role."
            )

        await ctx.send(
            f"Začínám přidělovat roli **{role.name}** všem členům. Může to chvíli trvat..."
        )

        added = 0
        skipped = 0
        failed = 0

        for member in guild.members:
            if member.bot:
                continue

            if role in member.roles:
                skipped += 1
                continue

            if member.top_role >= me.top_role:
                failed += 1
                continue

            try:
                await member.add_roles(
                    role, reason=f"Bulk role assignment by {ctx.author}"
                )
                added += 1
                await asyncio.sleep(0.2)
            except (discord.Forbidden, discord.HTTPException):
                failed += 1

        await ctx.send(
            f"Hotovo. Přidáno: **{added}**, už měli: **{skipped}**, neúspěšné: **{failed}**."
        )

    @roleall.error
    async def roleall_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.BadArgument):
            await ctx.send("Použití: `!roleall @Role`")
        elif isinstance(error, commands.MaxConcurrencyReached):
            await ctx.send(
                "Příkaz roleall už na tomto serveru běží. Počkej, až doběhne."
            )

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def add_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        if channel.id in ALLOWED_CHANNEL_IDS:
            await ctx.send("Tento kanál už je v seznamu povolených kanálů.")
            return

        ALLOWED_CHANNEL_IDS.add(channel.id)
        save_config()

        await ctx.send(
            f"Kanál **{channel.name}** byl přidán do seznamu povolených kanálů."
        )

    @add_channel.error
    async def add_channel_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Použití: `{ctx.prefix}add_channel #channel`")
        elif isinstance(error, (commands.BadArgument, commands.ChannelNotFound)):
            await ctx.send("Neplatný kanál.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def rem_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        if channel.id not in ALLOWED_CHANNEL_IDS:
            await ctx.send("Tento kanál není v seznamu povolených kanálů.")
            return

        ALLOWED_CHANNEL_IDS.remove(channel.id)
        save_config()

        await ctx.send(
            f"Kanál **{channel.name}** byl odebrán ze seznamu povolených kanálů."
        )

    @rem_channel.error
    async def rem_channel_error(self, ctx: commands.Context, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Použití: `{ctx.prefix}rem_channel #channel`")
        elif isinstance(error, (commands.BadArgument, commands.ChannelNotFound)):
            await ctx.send("Neplatný kanál.")

    @commands.command(name="log")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def set_log_channel(self, ctx: commands.Context, channel: discord.TextChannel | None = None):  # fmt: skip
        target_channel = channel or ctx.channel
        if target_channel is None:
            return

        CONFIG["log_channel_id"] = target_channel.id
        save_config()

        channel_mention = getattr(target_channel, "mention", str(target_channel))
        await ctx.send(f"Logovací kanál byl nastaven na {channel_mention}.")

        send_log = getattr(self.bot, "send_log", None)
        if send_log and inspect.iscoroutinefunction(send_log):
            ctx_mention = getattr(ctx.channel, "mention", str(ctx.channel))
            await send_log(f"Logovací kanál změnil **{ctx.author}** na {ctx_mention}.")

    @set_log_channel.error
    async def set_log_channel_error(self, ctx: commands.Context, error):
        if isinstance(error, (commands.BadArgument, commands.ChannelNotFound)):
            await ctx.send("Neplatný kanál.")


async def setup(bot):
    await bot.add_cog(Admin(bot))
