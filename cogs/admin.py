import asyncio
import inspect
import json
from pathlib import Path

import discord
from discord.ext import commands


class Admin(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.content = getattr(bot, "content", {})

    def _save_config(self):
        config_path = Path(__file__).resolve().parent.parent / "config.json"
        with open(config_path, "w", encoding="utf-8") as config_file:
            json.dump(self.bot.config, config_file, ensure_ascii=False, indent=2)

    # Pravidla atd ------------------------------------------------------

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def pravidla(self, ctx):
        rules_gif_path = self.content.get("rules_gif_path", "")
        rules_text = self.content.get("rules_text", "")
        invite_url = self.content.get("invite_url", "")
        embed_color = self.content.get("embed_color", "")

        await ctx.send(file=discord.File(rules_gif_path))
        await ctx.send(rules_text)
        embed = discord.Embed(
            title="Pozvi své kamarády!",
            description=f"```{invite_url}```",
            color=discord.Color.from_str(embed_color),
        )
        view = discord.ui.View()
        await ctx.send(embed=embed, view=view)

    # role management ------------------------------------------------------

    @commands.command(name="roleall")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def roleall(self, ctx, role: discord.Role):
        guild = ctx.guild
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
    async def roleall_error(self, ctx, error):
        """Error handler pro roleall"""
        if isinstance(error, commands.BadArgument):
            await ctx.send("Použití: `!roleall @Role`")
        elif isinstance(error, commands.MaxConcurrencyReached):
            await ctx.send(
                "Příkaz roleall už na tomto serveru běží. Počkej, až doběhne."
            )

    # config zmeny ------------------------------------------------------

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def add_channel(self, ctx, channel: discord.TextChannel):
        raw_allowed_channels = self.bot.config.get("allowed_channels", [])
        if isinstance(raw_allowed_channels, int):
            raw_allowed_channels = [raw_allowed_channels]

        allowed_channel_ids = [int(channel_id) for channel_id in raw_allowed_channels]

        if channel.id in allowed_channel_ids:
            await ctx.send("Tento kanál už je v seznamu povolených kanálů.")
            return

        allowed_channel_ids.append(channel.id)
        self.bot.config["allowed_channels"] = allowed_channel_ids
        self.bot.allowed_channel_ids = set(allowed_channel_ids)
        self._save_config()

        await ctx.send(
            f"Kanál **{channel.name}** byl přidán do seznamu povolených kanálů."
        )

    @add_channel.error
    async def add_channel_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Použití: `{ctx.prefix}add_channel #channel`")
        elif isinstance(error, (commands.BadArgument, commands.ChannelNotFound)):
            await ctx.send("Neplatný kanál.")

    @commands.command()
    @commands.has_permissions(administrator=True)
    async def rem_channel(self, ctx, channel: discord.TextChannel):
        raw_allowed_channels = self.bot.config.get("allowed_channels", [])
        if isinstance(raw_allowed_channels, int):
            raw_allowed_channels = [raw_allowed_channels]

        allowed_channel_ids = [int(channel_id) for channel_id in raw_allowed_channels]

        if channel.id not in allowed_channel_ids:
            await ctx.send("Tento kanál není v seznamu povolených kanálů.")
            return

        allowed_channel_ids.remove(channel.id)
        self.bot.config["allowed_channels"] = allowed_channel_ids
        self.bot.allowed_channel_ids = set(allowed_channel_ids)
        self._save_config()

        await ctx.send(
            f"Kanál **{channel.name}** byl odebrán ze seznamu povolených kanálů."
        )

    @rem_channel.error
    async def rem_channel_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Použití: `{ctx.prefix}rem_channel #channel`")
        elif isinstance(error, (commands.BadArgument, commands.ChannelNotFound)):
            await ctx.send("Neplatný kanál.")

    # logging ------------------------------------------------------

    @commands.command(name="log")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def set_log_channel(self, ctx, channel: discord.TextChannel | None = None):
        """Nastaví kanál pro bot logy"""
        target_channel = channel or ctx.channel
        self.bot.config["log_channel_id"] = target_channel.id
        self._save_config()

        await ctx.send(f"Logovací kanál byl nastaven na {target_channel.mention}.")

        send_log = getattr(self.bot, "send_log", None)
        if send_log and inspect.iscoroutinefunction(send_log):
            await send_log(
                f"Logovací kanál změnil **{ctx.author}** na {target_channel.mention}."
            )

    @set_log_channel.error
    async def set_log_channel_error(self, ctx, error):
        """Error handler for log"""
        if isinstance(error, (commands.BadArgument, commands.ChannelNotFound)):
            await ctx.send("Neplatný kanál.")

    # dalsi? ------------------------------------------------------


async def setup(bot):
    await bot.add_cog(Admin(bot))
