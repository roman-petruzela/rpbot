import json
from pathlib import Path

import discord
from discord.ext import commands


class Auto(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    def _save_config(self):
        config_path = Path(__file__).resolve().parent.parent / "config.json"
        with open(config_path, "w", encoding="utf-8") as config_file:
            json.dump(self.bot.config, config_file, ensure_ascii=False, indent=2)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        guild = member.guild
        me = guild.me or guild.get_member(self.bot.user.id)
        role_id = int(getattr(self.bot, "config", {}).get("auto_role_id", 0) or 0)

        if me is None or not me.guild_permissions.manage_roles or role_id == 0:
            return

        role = guild.get_role(role_id)
        if role is None:
            return

        if role in member.roles or role >= me.top_role:
            return

        try:
            await member.add_roles(role, reason="Automatic member role assignment")
        except (discord.Forbidden, discord.HTTPException):
            return

    @commands.command(name="set_auto_role")
    @commands.has_permissions(administrator=True)
    @commands.guild_only()
    async def set_auto_role(self, ctx, role: discord.Role | None = None):
        me = ctx.guild.me
        if me is None:
            return await ctx.send("Kritická chyba: účet bota nebyl na serveru nalezen.")

        if role is None:
            role_id = getattr(self.bot, "config", {}).get("auto_role_id", "")
            if role_id == "":
                return await ctx.send("Auto role není nastavená.")

            current_role = ctx.guild.get_role(int(role_id))
            if current_role is None:
                return await ctx.send(
                    f"ID auto role je nastavené na `{role_id}`, ale tato role na serveru nebyla nalezena."
                )

            return await ctx.send(
                f"Aktuální auto role: **{current_role.name}** (`{current_role.id}`)."
            )

        if not me.guild_permissions.manage_roles:
            return await ctx.send(
                "Chybí oprávnění: pro tuto akci potřebuji oprávnění 'Spravovat role'."
            )

        if role >= me.top_role:
            return await ctx.send(
                "Tuto roli nemohu přiřadit, protože je vyšší nebo stejná jako moje nejvyšší role."
            )

        self.bot.config["auto_role_id"] = str(role.id)
        self._save_config()
        await ctx.send(f"Auto role byla nastavena na **{role.name}** (`{role.id}`).")

    @set_auto_role.error  # type: ignore
    async def set_auto_role_error(self, ctx, error):
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(f"Použití: `{ctx.prefix}set_auto_role @Role`")
        elif isinstance(error, commands.BadArgument):
            await ctx.send("Neplatná role.")


async def setup(bot):
    await bot.add_cog(Auto(bot))
