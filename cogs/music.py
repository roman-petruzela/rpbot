import discord
from discord.ext import commands
import yt_dlp
import asyncio
import json
from pathlib import Path

class Music(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        self.config = getattr(bot, "config", {})
        self.state_path = Path(__file__).resolve().parent.parent / "music_state.json"
        self.guild_queues = {}
        self.guild_now_playing = {}
        self.guild_text_channels = {}
        self.guild_idle_tasks = {}
        self.guild_alone_tasks = {}
        self._load_music_state()

    def _build_ydl_options(self) -> dict:
        ydl_options = dict(self.config.get("ydl_options", {}))

        remote_components = ydl_options.get("remote_components")
        if isinstance(remote_components, str):
            component = remote_components.strip()
            if component in {"github", "npm"}:
                component = f"ejs:{component}"
            ydl_options["remote_components"] = [component]
        elif isinstance(remote_components, list):
            normalized_components = []
            for component in remote_components:
                if not isinstance(component, str):
                    continue
                clean = component.strip()
                if clean in {"github", "npm"}:
                    clean = f"ejs:{clean}"
                normalized_components.append(clean)
            if normalized_components:
                ydl_options["remote_components"] = normalized_components

        js_runtimes = ydl_options.get("js_runtimes")
        if isinstance(js_runtimes, str):
            runtimes_list = [runtime.strip() for runtime in js_runtimes.split(",") if runtime.strip()]
            ydl_options["js_runtimes"] = {runtime: {} for runtime in runtimes_list}
        elif isinstance(js_runtimes, list):
            ydl_options["js_runtimes"] = {runtime: {} for runtime in js_runtimes if isinstance(runtime, str)}
        elif not isinstance(js_runtimes, dict) or not js_runtimes:
            ydl_options["js_runtimes"] = {"node": {}, "deno": {}}

        return ydl_options

    def _get_guild_queue(self, guild_id: int):
        return self.guild_queues.setdefault(guild_id, [])

    def _serialize_track(self, track: dict) -> dict:
        serialized = {
            "title": track.get("title", "Neznámý název"),
            "source_url": track.get("source_url") or track.get("stream_url", ""),
            "requested_by": track.get("requested_by", "Neznámý uživatel"),
        }
        return serialized

    def _load_music_state(self):
        if not self.state_path.exists():
            return

        try:
            with open(self.state_path, "r", encoding="utf-8") as state_file:
                data = json.load(state_file)
        except Exception as exc:
            print(f"[music] Failed to load state: {exc}")
            return

        raw_queues = data.get("guild_queues", {})
        if isinstance(raw_queues, dict):
            for guild_id, queue in raw_queues.items():
                try:
                    parsed_guild_id = int(guild_id)
                except (TypeError, ValueError):
                    continue

                if not isinstance(queue, list):
                    continue

                cleaned_queue = []
                for track in queue:
                    if not isinstance(track, dict):
                        continue
                    source_url = track.get("source_url") or track.get("stream_url")
                    title = track.get("title", "Neznámý název")
                    requested_by = track.get("requested_by", "Neznámý uživatel")
                    if not isinstance(source_url, str) or not source_url:
                        continue
                    cleaned_queue.append({
                        "title": title,
                        "source_url": source_url,
                        "requested_by": requested_by,
                    })

                if cleaned_queue:
                    self.guild_queues[parsed_guild_id] = cleaned_queue

    def _save_music_state(self):
        payload = {
            "guild_queues": {
                str(guild_id): [self._serialize_track(track) for track in queue]
                for guild_id, queue in self.guild_queues.items()
                if queue
            },
        }

        try:
            tmp_path = self.state_path.with_suffix(".tmp")
            with open(tmp_path, "w", encoding="utf-8") as state_file:
                json.dump(payload, state_file, ensure_ascii=False, indent=2)
            tmp_path.replace(self.state_path)
        except Exception as exc:
            print(f"[music] Failed to save state: {exc}")

    def _cancel_task(self, task: asyncio.Task | None):
        if task and not task.done():
            task.cancel()

    def _cancel_idle_task(self, guild_id: int):
        self._cancel_task(self.guild_idle_tasks.pop(guild_id, None))

    def _cancel_alone_task(self, guild_id: int):
        self._cancel_task(self.guild_alone_tasks.pop(guild_id, None))

    def _is_bot_alone(self, vc: discord.VoiceClient) -> bool:
        if not vc.is_connected() or vc.channel is None:
            return False
        non_bot_members = [member for member in vc.channel.members if not member.bot]
        return len(non_bot_members) == 0

    async def _send_music_log(self, guild_id: int, message: str):
        target = self.guild_text_channels.get(guild_id)
        if target is not None:
            try:
                await target.send(message)
                return
            except (discord.Forbidden, discord.HTTPException):
                pass

        send_log = getattr(self.bot, "send_log", None)
        if callable(send_log):
            await send_log(message)

    def _schedule_idle_disconnect(self, guild_id: int, vc: discord.VoiceClient):
        self._cancel_idle_task(guild_id)

        async def _worker():
            await asyncio.sleep(600)
            if not vc.is_connected():
                return
            if vc.is_playing() or vc.is_paused():
                return
            if self._get_guild_queue(guild_id):
                return

            await vc.disconnect(force=True)
            self.guild_now_playing.pop(guild_id, None)
            await self._send_music_log(guild_id, "Odpojeno z voice po 10 minutách neaktivity.")

        self.guild_idle_tasks[guild_id] = asyncio.create_task(_worker())

    def _schedule_alone_disconnect(self, guild_id: int, vc: discord.VoiceClient):
        self._cancel_alone_task(guild_id)

        async def _worker():
            await asyncio.sleep(60)
            if not vc.is_connected() or vc.channel is None:
                return
            if not self._is_bot_alone(vc):
                return

            voice_cog = self.bot.get_cog("Voice")
            temp_channels = getattr(voice_cog, "temp_channels", set()) if voice_cog else set()
            channel_to_cleanup = vc.channel

            await vc.disconnect(force=True)
            self.guild_now_playing.pop(guild_id, None)

            if channel_to_cleanup.id in temp_channels:
                try:
                    await channel_to_cleanup.delete()
                    temp_channels.remove(channel_to_cleanup.id)
                except (discord.Forbidden, discord.HTTPException):
                    pass

            await self._send_music_log(guild_id, "Odpojeno z voice po 1 minutě bez lidí.")

        self.guild_alone_tasks[guild_id] = asyncio.create_task(_worker())

    def _resolve_ffmpeg_executable(self) -> str:
        configured = self.config.get("ffmpeg_executable")
        if isinstance(configured, str) and configured.strip():
            configured_path = Path(configured.strip())
            if configured_path.exists():
                return str(configured_path)

        project_root = Path(__file__).resolve().parent.parent
        bundled_ffmpeg = project_root / "sources" / "ffmpeg.exe"
        if bundled_ffmpeg.exists():
            return str(bundled_ffmpeg)

        return "ffmpeg"

    def _pick_stream_url(self, info: dict) -> str | None:
        direct_url = info.get("url")
        if isinstance(direct_url, str) and direct_url:
            return direct_url

        formats = info.get("formats") or []
        if not isinstance(formats, list):
            return None

        for fmt in reversed(formats):
            if not isinstance(fmt, dict):
                continue
            if fmt.get("vcodec") != "none":
                continue
            if fmt.get("acodec") in {None, "none"}:
                continue
            url = fmt.get("url")
            if isinstance(url, str) and url:
                return url

        return None

    def _load_track_info(self, url: str, ydl_options: dict) -> tuple[str, str]:
        with yt_dlp.YoutubeDL(ydl_options) as ydl:
            info = ydl.extract_info(url, download=False)
            if isinstance(info, dict) and info.get("entries"):
                entries = [entry for entry in info.get("entries", []) if entry]
                if not entries:
                    raise ValueError("Playlist/query did not return any playable entries")
                info = entries[0]

            if not isinstance(info, dict):
                raise ValueError("yt-dlp returned unexpected info structure")

            stream_url = self._pick_stream_url(info)
            if not stream_url:
                raise ValueError("No playable stream URL was found in extractor output")

            title = info.get("title", "Neznámý název")
            return title, stream_url

    async def _resolve_track_stream(self, track: dict) -> dict:
        if isinstance(track.get("stream_url"), str) and track["stream_url"]:
            return track

        source_url = track.get("source_url")
        if not isinstance(source_url, str) or not source_url:
            raise ValueError("Track is missing source_url")

        ydl_options = self._build_ydl_options()
        title, stream_url = await asyncio.to_thread(self._load_track_info, source_url, ydl_options)

        resolved_track = dict(track)
        resolved_track["title"] = track.get("title") or title
        resolved_track["stream_url"] = stream_url
        resolved_track.setdefault("source_url", source_url)
        return resolved_track

    async def _start_track(self, channel: discord.abc.Messageable, vc: discord.VoiceClient, guild_id: int, track: dict):
        ffmpeg_options = dict(self.config.get("ffmpeg_options", {}))
        
        before_opts = ffmpeg_options.get("before_options", "")
        if "-reconnect" not in before_opts:
            ffmpeg_options["before_options"] = f"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 {before_opts}".strip()
            
        opts = ffmpeg_options.get("options", "")
        if "-vn" not in opts:
            ffmpeg_options["options"] = f"-vn -threads 1 {opts}".strip()

        ffmpeg_executable = self._resolve_ffmpeg_executable()

        try:
            track = await self._resolve_track_stream(track)
            source = discord.FFmpegPCMAudio(
                source=track["stream_url"],
                executable=ffmpeg_executable,
                **ffmpeg_options,
            )

            def _after_playback(error):
                if error:
                    print(f"[play] Playback error: {error}")
                self.bot.loop.call_soon_threadsafe(
                    asyncio.create_task,
                    self._play_next(guild_id=guild_id, channel=channel, vc=vc),
                )

            vc.play(source, after=_after_playback)
            self.guild_now_playing[guild_id] = track
            self._cancel_idle_task(guild_id)
            self._cancel_alone_task(guild_id)
            await channel.send(f"Právě hraje: **{track['title']}**")
            
        except FileNotFoundError:
            if vc.is_connected():
                await vc.disconnect(force=True)
            await channel.send("FFmpeg nebyl na hostiteli nalezen. Nainstaluj FFmpeg a přidej ho do PATH.")
        except Exception as e:
            print(f"[play] Failed to start playback: {e}")
            if vc.is_connected() and not vc.is_playing():
                await vc.disconnect(force=True)
            await channel.send("Nepodařilo se spustit přehrávání.")

    async def _play_next(self, guild_id: int, channel: discord.abc.Messageable, vc: discord.VoiceClient):
        queue = self._get_guild_queue(guild_id)
        if not queue:
            self.guild_now_playing.pop(guild_id, None)
            if vc.is_connected() and not vc.is_playing() and not vc.is_paused():
                self._schedule_idle_disconnect(guild_id, vc)
                if self._is_bot_alone(vc):
                    self._schedule_alone_disconnect(guild_id, vc)
            return

        next_track = queue.pop(0)
        self._save_music_state()
        await self._start_track(channel=channel, vc=vc, guild_id=guild_id, track=next_track)

    @commands.command()
    async def play(self, ctx, url):
        if not ctx.author.voice:
            return await ctx.send("Musíš být ve voice kanálu.")

        channel = ctx.author.voice.channel
        me = ctx.guild.me
        permissions = channel.permissions_for(me)
        if not permissions.connect:
            return await ctx.send("Nemám oprávnění připojit se do tvého voice kanálu.")
        if not permissions.speak:
            return await ctx.send("Nemám oprávnění mluvit ve tvém voice kanálu.")

        ydl_options = self._build_ydl_options()
        self.guild_text_channels[ctx.guild.id] = ctx.channel

        try:
            vc = ctx.voice_client

            if vc is not None and not vc.is_connected():
                try:
                    await vc.disconnect(force=True)
                except Exception:
                    pass
                vc = None

            if vc is None:
                vc = await channel.connect(timeout=30.0, reconnect=True)
            elif vc.channel != channel:
                await vc.move_to(channel)
        except discord.ClientException as e:
            print(f"[play] Voice client error: {e}")
            return await ctx.send("Nepodařilo se připojit do voice kanálu. Zkontroluj, jestli už nejsem připojený, nebo mě restartuj.")
        except RuntimeError as e:
            print(f"[play] Runtime voice error: {e}")
            return await ctx.send("Na hostiteli chybí voice závislosti (nainstaluj PyNaCl).")
        except asyncio.TimeoutError:
            return await ctx.send("Připojení do voice kanálu vypršelo.")
        except Exception as e:
            print(f"[play] Unexpected voice connect error: {e}")
            return await ctx.send("Nepodařilo se připojit do tvého voice kanálu.")

        await ctx.send("Vyhledávám a připravuji audio...")

        try:
            title, url2 = await asyncio.to_thread(self._load_track_info, url, ydl_options)
        except Exception as e:
            print(f"[play] Error while loading video: {e}")
            await ctx.send("Nepodařilo se načíst video.")
            return

        track = {
            "title": title,
            "source_url": url,
            "stream_url": url2,
            "requested_by": str(ctx.author),
        }

        if vc.is_playing() or vc.is_paused():
            queue = self._get_guild_queue(ctx.guild.id)
            queue.append(track)
            self._save_music_state()
            return await ctx.send(f"Přidáno do fronty na pozici **{len(queue)}**: **{title}**")

        await self._start_track(channel=ctx.channel, vc=vc, guild_id=ctx.guild.id, track=track)

    @commands.command()
    async def queue(self, ctx):
        now_playing = self.guild_now_playing.get(ctx.guild.id)
        queue = self._get_guild_queue(ctx.guild.id)

        if not now_playing and not queue:
            return await ctx.send("Fronta je prázdná.")

        lines = []
        if now_playing:
            lines.append(f"Teď hraje: **{now_playing['title']}**")

        if queue:
            lines.append("Další ve frontě:")
            for index, track in enumerate(queue, start=1):
                lines.append(f"{index}. {track['title']}")

        await ctx.send("\n".join(lines))

    @commands.command(aliases=["np"])
    async def nowplaying(self, ctx):
        now_playing = self.guild_now_playing.get(ctx.guild.id)
        if not now_playing:
            return await ctx.send("Momentálně nic nehraje.")

        queue = self._get_guild_queue(ctx.guild.id)
        lines = [
            f"Právě hraje: **{now_playing['title']}**",
            f"Přidáno od: **{now_playing.get('requested_by', 'Neznámý uživatel')}**",
            f"Ve frontě zbývá: **{len(queue)}**",
        ]
        if ctx.voice_client and ctx.voice_client.channel:
            lines.append(f"Voice kanál: **{ctx.voice_client.channel.name}**")

        await ctx.send("\n".join(lines))

    @commands.command()
    async def pause(self, ctx):
        vc = ctx.voice_client
        if vc is None or not vc.is_connected():
            return await ctx.send("Nejsem připojený ve voice kanálu.")

        if vc.is_paused():
            return await ctx.send("Přehrávání už je pozastavené.")

        if not vc.is_playing():
            return await ctx.send("Momentálně nic nehraje.")

        vc.pause()
        await ctx.send("Přehrávání pozastaveno.")

    @commands.command()
    async def stop(self, ctx):
        if ctx.voice_client:
            self._cancel_idle_task(ctx.guild.id)
            self._cancel_alone_task(ctx.guild.id)
            self._get_guild_queue(ctx.guild.id).clear()
            self.guild_now_playing.pop(ctx.guild.id, None)
            self._save_music_state()
            await ctx.voice_client.disconnect()
            await ctx.send("Odpojeno.")
        else:
            await ctx.send("Nejsem připojený ve voice kanálu.")

    @commands.command()
    async def skip(self, ctx):
        if ctx.voice_client and (ctx.voice_client.is_playing() or ctx.voice_client.is_paused()):
            ctx.voice_client.stop()
            await ctx.send("Přeskočeno.")
        else:
            await ctx.send("Momentálně nic nehraje.")

    @commands.command(name="music")
    async def music_status(self, ctx):
        vc = ctx.voice_client
        now_playing = self.guild_now_playing.get(ctx.guild.id)
        queue = self._get_guild_queue(ctx.guild.id)

        lines = []
        lines.append(f"Připojen: {'ano' if vc and vc.is_connected() else 'ne'}")
        if vc and vc.is_connected() and vc.channel:
            lines.append(f"Voice kanál: **{vc.channel.name}**")
        lines.append(f"Právě hraje: **{now_playing['title']}**" if now_playing else "Právě hraje: nic")
        lines.append(f"Ve frontě: **{len(queue)}**")
        lines.append(f"Perzistence fronty: {'ano' if self.state_path.exists() else 'ne'}")

        idle_task = self.guild_idle_tasks.get(ctx.guild.id)
        alone_task = self.guild_alone_tasks.get(ctx.guild.id)
        lines.append(f"Idle odpojení (10 min): {'čeká' if idle_task and not idle_task.done() else 'ne'}")
        lines.append(f"Solo odpojení (1 min): {'čeká' if alone_task and not alone_task.done() else 'ne'}")

        await ctx.send("\n".join(lines))

    @commands.Cog.listener()
    async def on_voice_state_update(self, member, before, after):
        guild = member.guild
        vc = guild.voice_client
        if vc is None or not vc.is_connected() or vc.channel is None:
            self._cancel_idle_task(guild.id)
            self._cancel_alone_task(guild.id)
            return

        # Ignore unrelated channel changes.
        if before.channel != vc.channel and after.channel != vc.channel:
            return

        if self._is_bot_alone(vc):
            self._schedule_alone_disconnect(guild.id, vc)
        else:
            self._cancel_alone_task(guild.id)


async def setup(bot):
    await bot.add_cog(Music(bot))
