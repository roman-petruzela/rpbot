import discord
from discord.ext import commands

class Test(commands.Cog):
    def __init__(self, bot):
        self.bot = bot

    @commands.command()
    async def test(self, ctx):
        await ctx.send("Vše funguje.")
        
    @commands.command()
    async def join(self, ctx):
        await ctx.send("Připojuji se.")
        if not ctx.author.voice:
            return await ctx.send("Musíš být ve voice kanálu.")

        channel = ctx.author.voice.channel
        me = ctx.guild.me
        permissions = channel.permissions_for(me)
        if not permissions.connect:
            return await ctx.send("Nemám oprávnění připojit se do tvého voice kanálu.")
        if not permissions.speak:
            return await ctx.send("Nemám oprávnění mluvit ve tvém voice kanálu.")

        if ctx.voice_client is None:
            await channel.connect()
            await ctx.send("Jsem připojený ve voice.")
            return

        if ctx.voice_client.channel != channel:
            await ctx.voice_client.move_to(channel)
            await ctx.send("Přesunul jsem se do tvého voice kanálu.")
            return

        await ctx.send("Už jsem v tomhle voice kanálu.")

async def setup(bot):
    await bot.add_cog(Test(bot))