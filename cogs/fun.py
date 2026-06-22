import random
import discord
from discord.ext import commands
import asyncio
from pathlib import Path

class Fun(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.content = getattr(bot, "content", {})

    def _quotes_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "sources" / "text" / "quotes.txt"

    def _eight_ball_path(self) -> Path:
        return Path(__file__).resolve().parent.parent / "sources" / "text" / "8ball.txt"

    @commands.command()
    async def gragas_jumpscare(self, ctx, member: discord.Member):
        """Easter egg - přehraje Gragas zvuk uživateli ve voice channelu"""
        if not member.voice:
            return await ctx.send(f"**{member.display_name}** není ve voice kanálu.")

        channel = member.voice.channel
        vc = ctx.voice_client

        try:
            if vc is None:
                vc = await channel.connect(timeout=15.0, reconnect=False)
            elif vc.channel != channel:
                await vc.move_to(channel)
        except (discord.ClientException, asyncio.TimeoutError, discord.HTTPException):
            return await ctx.send("Do tohoto voice kanálu se nepodařilo připojit.")

        await asyncio.sleep(1)  # Krátká pauza, aby se bot správně připojil

        gragas_audio_path = self.content.get("gragas_audio_path", "sources/audio/gragas.ogg")
        source = discord.FFmpegPCMAudio(executable="ffmpeg", source=gragas_audio_path)
        
        if vc.is_playing():
            return await ctx.send("V tomto voice kanálu už něco přehrávám.")

        vc.play(source)
        while vc.is_playing():
            await asyncio.sleep(1)
        
        await vc.disconnect()
        
    @commands.command()
    async def pero(self, ctx):
        """Fun command"""
        await ctx.send(f"Tvoje velikost je {random.randint(1, 30)} cm")
        
    @commands.command()
    async def mince(self, ctx):
        vysledek = random.choice(["Orel", "Panna"])
        await ctx.send(f"**{vysledek}**")
        
    @commands.command()
    async def random(self, ctx, cislo1: int = None, cislo2: int = None):
        """Vyber náhodnou možnost ze zadaných"""
        if cislo1 is None and cislo2 is None:
            minimum, maximum = 0, 100
        minimum, maximum = sorted((cislo1, cislo2))

        choice = random.randint(minimum, maximum)
        await ctx.send(f"Padlo číslo: **{choice}**")

    @commands.group(invoke_without_command=True)
    async def quote(self, ctx):
        await ctx.send("Použití: `!quote add \"Hláška\" - @Uživatel` nebo `!quote random`")

    @quote.command(name="add")
    async def quote_add(self, ctx, *, payload: str):
        raw = (payload or "").strip()
        if not raw:
            return await ctx.send("Použití: `!quote add \"Hláška\" - @Uživatel`")

        if " - " in raw:
            quote_text, author_text = raw.split(" - ", 1)
        else:
            quote_text, author_text = raw, ctx.author.mention

        quote_text = quote_text.strip().strip('"').strip()
        author_text = author_text.strip() or ctx.author.mention

        if not quote_text:
            return await ctx.send("Nejdřív napiš samotnou hlášku.")

        quotes_path = self._quotes_path()
        quotes_path.parent.mkdir(parents=True, exist_ok=True)
        with open(quotes_path, "a", encoding="utf-8") as quote_file:
            quote_file.write(f"{quote_text} - {author_text}\n")

        await ctx.send("Hláška uložena.")

    @quote.command(name="random")
    async def quote_random(self, ctx):
        quotes_path = self._quotes_path()
        if not quotes_path.exists():
            return await ctx.send("Zatím není uložená žádná hláška.")

        with open(quotes_path, "r", encoding="utf-8") as quote_file:
            quotes = [line.strip() for line in quote_file.readlines() if line.strip()]

        if not quotes:
            return await ctx.send("Zatím není uložená žádná hláška.")

        await ctx.send(f"Legendy praví: \"{random.choice(quotes)}\"")

    @commands.command(name="8ball")
    async def eight_ball(self, ctx, *, otazka: str):
        if not otazka.strip():
            return await ctx.send("Zeptej se otázku, třeba `!8ball Vyhrajeme dneska?`")

        eight_ball_path = self._eight_ball_path()
        if not eight_ball_path.exists():
            return await ctx.send("Soubor s odpověďmi pro 8ball neexistuje.")

        with open(eight_ball_path, "r", encoding="utf-8") as eight_ball_file:
            answers = [line.strip() for line in eight_ball_file.readlines() if line.strip()]

        if not answers:
            return await ctx.send("Soubor `8ball.txt` je prázdný.")

        await ctx.send(f"Otázka: {otazka}\n8ball: **{random.choice(answers)}**")


async def setup(bot):
    await bot.add_cog(Fun(bot))
