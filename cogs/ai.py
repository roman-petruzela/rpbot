# fully vibecoded
import asyncio
import json
import logging
import os
import random
import tempfile
import time
from datetime import timedelta
from pathlib import Path
from typing import Any

import discord
from discord.ext import commands

try:
    from google import genai
except ImportError:
    genai = None

logger = logging.getLogger("rpbot.ai")


class AI(commands.Cog):
    def __init__(self, bot):
        """Inicializace cogu."""
        self.bot = bot
        # Sjednotíme config rovnou do třídy, aby Pyright neřval na self.bot.config
        self.config: dict[str, Any] = getattr(bot, "config", {})

        self._client: Any = None
        # Typově ošetřený slovník pro rate-limity (id_kanalu: timestamp_v_sekundach)
        self._last_response_ts: dict[int, float] = {}

        self._default_ai_config = self._load_ai_config_from_config_file()
        self._ensure_ai_config_defaults()
        self._init_client()

    def _config_path(self) -> Path:
        """Vrátí absolutní cestu ke `config.json`."""
        return Path(__file__).resolve().parent.parent / "config.json"

    def _save_config(self):
        """Uloží konfiguraci atomicky."""
        config_path = self._config_path()
        config_dir = config_path.parent

        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=config_dir,
            delete=False,
            prefix="config.",
            suffix=".tmp",
        ) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(self.config, temp_file, ensure_ascii=False, indent=2)
            temp_file.flush()
            os.fsync(temp_file.fileno())

        os.replace(temp_path, config_path)

    def _load_ai_config_from_config_file(self) -> dict:
        """Načte AI nastavení z `config.json`."""
        config_path = self._config_path()
        try:
            with open(config_path, "r", encoding="utf-8") as config_file:
                data = json.load(config_file)
                ai_defaults = data.get("ai", {})
                return ai_defaults if isinstance(ai_defaults, dict) else {}
        except Exception as exc:
            logger.warning("Unable to load AI config from config.json: %s", exc)
            fallback_ai = self.config.get("ai", {})
            return fallback_ai if isinstance(fallback_ai, dict) else {}

    def _ensure_ai_config_defaults(self):
        """Doplní chybějící klíče v `config['ai']` podle výchozích hodnot."""
        ai_cfg = self.config.setdefault("ai", {})
        for key, value in self._default_ai_config.items():
            ai_cfg.setdefault(key, value)

        if "allowed_channels" not in ai_cfg:
            ai_cfg["allowed_channels"] = []
        if "fallback_models" not in ai_cfg:
            ai_cfg["fallback_models"] = []
        if ai_cfg.get("model") == "gemini-2.5-flash":
            ai_cfg["model"] = "gemini-3.1-flash-lite"

    def _parse_channel_ids(self, raw_channels: Any) -> set[int]:
        """Převede hodnotu (int/list) z configu na množinu validních channel ID."""
        if isinstance(raw_channels, int):
            raw_channels = [raw_channels]

        channel_ids: set[int] = set()
        for channel_id in raw_channels or []:
            try:
                channel_ids.add(int(channel_id))
            except (TypeError, ValueError):
                continue
        return channel_ids

    def _load_api_key(self) -> str | None:
        """Načte API klíč z env proměnných."""
        env_key = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")
        if env_key:
            return env_key.strip()

        return None

    def _init_client(self):
        """Inicializuje klienta pro Google GenAI SDK."""
        if genai is None:
            logger.warning("google-genai package is not installed; AI cog disabled.")
            return

        api_key = self._load_api_key()
        if not api_key:
            logger.warning("No GenAI API key found.")
            return

        try:
            self._client = genai.Client(api_key=api_key)
        except Exception as exc:
            logger.exception("Failed to initialize GenAI client: %s", exc)

    def _is_rate_limited(self, channel_id: int) -> bool:
        """Vrátí `True`, pokud je stále aktivní cooldown pro daný kanál."""
        ai_cfg = self.config.get("ai", {})
        min_interval = float(ai_cfg.get("min_response_interval_seconds", 6))
        now = asyncio.get_running_loop().time()
        last = self._last_response_ts.get(channel_id, 0.0)

        return now - last < min_interval

    def _mark_responded(self, channel_id: int):
        """Označí čas poslední úspěšné odpovědi v kanálu."""
        self._last_response_ts[channel_id] = asyncio.get_running_loop().time()

    def _clean_mention(self, message: discord.Message, text: str) -> str:
        """Odstraní mention bota ze zprávy, aby model dostal čistý vstup."""
        if not self.bot.user:
            return text.strip()

        cleaned = text.replace(f"<@{self.bot.user.id}>", "")
        cleaned = cleaned.replace(f"<@!{self.bot.user.id}>", "")
        return cleaned.strip()

    async def _build_prompt(self, message: discord.Message, user_input: str) -> str:
        """Sestaví prompt z krátké historie a nové zprávy uživatele."""
        ai_cfg = self.config.get("ai", {})
        history_window_hours = max(0.0, float(ai_cfg.get("history_window_hours", 12)))
        history_message_limit = max(1, int(ai_cfg.get("history_message_limit", 50)))
        history_after = discord.utils.utcnow() - timedelta(hours=history_window_hours)

        history_lines = []
        async for item in message.channel.history(
            limit=history_message_limit, after=history_after
        ):
            if item.id == message.id:
                continue

            content = item.clean_content.strip()
            if not content:
                continue

            name = "RPBot" if item.author == self.bot.user else item.author.display_name
            history_lines.append(f"{name}: {content}")

        history_lines.reverse()
        recent_chat = "\n".join(history_lines)

        if recent_chat:
            return (
                f"[Historie chatu pro kontext]\n{recent_chat}\n\n"
                f"[Nová zpráva]\n{message.author.display_name}: {user_input}\n\n"
                "Odpověz přirozeně přímo na tuto Novou zprávu."
            )
        else:
            return f"Uživatel {message.author.display_name} říká: {user_input}"

    def _extract_finish_reason(self, response: Any) -> str:
        """Vytáhne `finish_reason` z odpovědi SDK v bezpečné podobě."""
        candidates = getattr(response, "candidates", None) or []
        if not candidates:
            return "UNKNOWN"

        reason = getattr(candidates[0], "finish_reason", None)
        if reason is None:
            return "UNKNOWN"

        if hasattr(reason, "name"):
            return str(reason.name)

        return str(reason)

    async def _log_finish_reason(
        self,
        *,
        source: str,
        channel: discord.abc.GuildChannel,
        user: discord.abc.User,
        finish_reason: str,
        model_used: str,
    ):
        send_log = getattr(self.bot, "send_log", None)
        if send_log is None:
            return

        configured_model = self.config.get("ai", {}).get("model", "unknown")
        await send_log(
            f"AI odpověď ({source}) v {channel.mention} od **{user}** | nastavený_model=`{configured_model}` | použitý_model=`{model_used}` | finish_reason=`{finish_reason}`"
        )

    async def _log_ai_error(
        self, *, source: str, channel_name: str, user_name: str, error: Exception
    ):
        send_log = getattr(self.bot, "send_log", None)
        if send_log is None:
            return

        await send_log(
            f"AI chyba ({source}) v `{channel_name}` od **{user_name}**: `{error}`"
        )

    def _is_model_not_found_error(self, exc: Exception) -> bool:
        """Heuristika pro detekci 'model neexistuje / není dostupný'."""
        err_text = str(exc).lower()
        markers = (
            "not_found",
            "not found",
            "is not found",
            "404",
            "unknown model",
            "model not found",
        )
        if any(marker in err_text for marker in markers):
            return True

        status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        return str(status_code) == "404"

    def _is_transient_error(self, exc: Exception) -> bool:
        """Rozpozná dočasné chyby, kde dává smysl retry (5xx, timeout, quota)."""
        err_text = str(exc).lower()
        transient_markers = (
            "deadline",
            "timeout",
            "timed out",
            "temporar",
            "unavailable",
            "internal",
            "rate limit",
            "resource exhausted",
            "503",
            "502",
            "500",
            "429",
        )
        if any(marker in err_text for marker in transient_markers):
            return True

        status_code = getattr(exc, "status_code", None) or getattr(exc, "code", None)
        return str(status_code) in {"429", "500", "502", "503", "504"}

    async def _generate_response(self, prompt: str) -> tuple[str, str, str]:
        """Vygeneruje odpověď modelu."""
        if self._client is None:
            raise RuntimeError("GenAI client is not initialized.")

        ai_cfg = self.config.get("ai", {})
        model = ai_cfg.get("model", "gemini-3.1-flash-lite")
        system_prompt = ai_cfg.get("system_prompt", "Jsi pomocník.")
        temperature = float(ai_cfg.get("temperature", 0.7))
        max_tokens = int(ai_cfg.get("max_output_tokens", 800))
        request_timeout = float(ai_cfg.get("request_timeout_seconds", 35))
        max_retries = int(ai_cfg.get("max_retries", 2))
        retry_backoff = float(ai_cfg.get("retry_backoff_seconds", 1.0))

        fallback_models = [
            m for m in ai_cfg.get("fallback_models", []) if isinstance(m, str) and m
        ]
        models_to_try = [model] + [m for m in fallback_models if m != model]

        def _run_call():
            last_exc: Exception | None = None
            used_model = model

            for candidate_model in models_to_try:
                used_model = candidate_model
                for attempt in range(max_retries + 1):
                    try:
                        response = self._client.models.generate_content(
                            model=candidate_model,
                            contents=prompt,
                            config={
                                "system_instruction": system_prompt,
                                "temperature": temperature,
                                "max_output_tokens": max_tokens,
                            },
                        )
                        text = (getattr(response, "text", "") or "").strip()
                        finish_reason = self._extract_finish_reason(response)
                        return text, finish_reason, used_model
                    except Exception as exc:
                        last_exc = exc

                        if self._is_model_not_found_error(exc):
                            break

                        should_retry = (
                            attempt < max_retries and self._is_transient_error(exc)
                        )
                        if should_retry:
                            sleep_seconds = retry_backoff * (2**attempt)
                            time.sleep(max(0.0, sleep_seconds))
                            continue

                        raise

            # Pojistka pro Pyright: pokud vše selže, throw the last exception,
            # nebo obecný error pokud by last_exc zůstalo prázdné
            raise last_exc or RuntimeError(
                "All fallback models failed without a specific error."
            )

        try:
            text, finish_reason, used_model = await asyncio.wait_for(
                asyncio.to_thread(_run_call),
                timeout=request_timeout,
            )
        except asyncio.TimeoutError as exc:
            raise TimeoutError(
                f"AI request timed out after {request_timeout:.1f}s"
            ) from exc

        if used_model != model:
            logger.warning(
                "Configured AI model '%s' unavailable, used fallback '%s'.",
                model,
                used_model,
            )

        return text, finish_reason, used_model

    async def _send_long_message(self, channel: discord.abc.Messageable, text: str):
        """Pošle dlouhý text po částech, aby prošel Discord limitem zprávy."""
        if not text:
            await channel.send("Nepodařilo se vygenerovat odpověď.")
            return

        chunks = [text[i : i + 1900] for i in range(0, len(text), 1900)]
        for chunk in chunks:
            await channel.send(chunk)

    def _message_is_ai_trigger(self, message: discord.Message) -> tuple[bool, str]:
        """Rozhodne, jestli má AI odpovědět, a vrátí i text pro prompt."""
        ai_cfg = self.config.get("ai", {})
        content = (message.content or "").strip()
        if not content:
            return False, ""

        mentioned = self.bot.user and self.bot.user in message.mentions
        if mentioned and ai_cfg.get("respond_when_mentioned", True):
            return True, self._clean_mention(message, content)

        if (
            message.reference
            and ai_cfg.get("respond_when_replied", True)
            and message.reference.resolved
            and isinstance(message.reference.resolved, discord.Message)
            and message.reference.resolved.author == self.bot.user
        ):
            return True, content

        auto_channel_ids = self._parse_channel_ids(
            ai_cfg.get("auto_reply_channels", [])
        )

        if message.channel.id in auto_channel_ids:
            chance = float(ai_cfg.get("auto_reply_chance", 0.2))
            if random.random() <= max(0.0, min(1.0, chance)):
                return True, content

        return False, ""

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        """Hlavní listener pro automatické AI odpovědi na zprávy."""
        # Bot a Webhook ochrana
        if message.author.bot:
            return

        ai_cfg = self.config.get("ai", {})
        if not ai_cfg.get("enabled", False):
            return

        ai_allowed_channel_ids = self._parse_channel_ids(
            ai_cfg.get("allowed_channels", [])
        )
        if ai_allowed_channel_ids and message.channel.id not in ai_allowed_channel_ids:
            return

        if self._client is None:
            return

        ctx = await self.bot.get_context(message)
        if ctx.valid:
            return

        should_answer, user_input = self._message_is_ai_trigger(message)
        if not should_answer:
            return

        if self._is_rate_limited(message.channel.id):
            return

        prompt = await self._build_prompt(message, user_input)

        try:
            async with message.channel.typing():
                answer, finish_reason, used_model = await self._generate_response(
                    prompt
                )
            await self._send_long_message(message.channel, answer)
            self._mark_responded(message.channel.id)
            if isinstance(message.channel, discord.abc.GuildChannel):
                await self._log_finish_reason(
                    source="auto",
                    channel=message.channel,
                    user=message.author,
                    finish_reason=finish_reason,
                    model_used=used_model,
                )
        except Exception as exc:
            logger.exception("AI response generation failed: %s", exc)
            await self._log_ai_error(
                source="auto",
                channel_name=str(message.channel),
                user_name=str(message.author),
                error=exc,
            )

    @commands.command(name="ai_status")
    @commands.has_permissions(administrator=True)
    async def ai_status(self, ctx):
        ai_cfg = self.config.get("ai", {})
        enabled = ai_cfg.get("enabled", False)
        allowed_channels = [str(ch) for ch in ai_cfg.get("allowed_channels", [])]
        auto_channels = [str(ch) for ch in ai_cfg.get("auto_reply_channels", [])]
        status_text = "ZAPNUTO" if enabled else "VYPNUTO"

        await ctx.send(
            f"Stav AI: **{status_text}**\n"
            f"Model: `{ai_cfg.get('model', 'unknown')}`\n"
            f"AI povolené kanály: `{', '.join(allowed_channels) if allowed_channels else 'všechny'}`\n"
            f"Kanály pro náhodnou auto-odpověď: `{', '.join(auto_channels) if auto_channels else 'žádné'}`\n"
            f"Klient připraven: `{self._client is not None}`"
        )

    @commands.command(name="ai_on")
    @commands.has_permissions(administrator=True)
    async def ai_on(self, ctx):
        self.config.setdefault("ai", {})["enabled"] = True
        self._save_config()
        self._init_client()

        if self._client is None:
            await ctx.send(
                "AI jsem zapnul v konfiguraci, ale chybí API klíč nebo knihovna `google-genai`."
            )
            return

        await ctx.send("AI odpovídání je zapnuté.")

    @commands.command(name="ai_off")
    @commands.has_permissions(administrator=True)
    async def ai_off(self, ctx):
        self.config.setdefault("ai", {})["enabled"] = False
        self._save_config()
        await ctx.send("AI odpovídání je vypnuté.")

    @commands.command(name="ai_add_channel")
    @commands.has_permissions(administrator=True)
    async def ai_add_channel(self, ctx, channel: discord.TextChannel):
        ai_cfg = self.config.setdefault("ai", {})
        channel_ids = self._parse_channel_ids(ai_cfg.get("allowed_channels", []))

        if channel.id in channel_ids:
            await ctx.send("Tenhle kanál už je v AI povoleném seznamu.")
            return

        channel_ids.add(channel.id)
        ai_cfg["allowed_channels"] = sorted(channel_ids)
        self._save_config()
        await ctx.send(f"AI je povolené v kanálu {channel.mention}.")

    @commands.command(name="ai_rem_channel")
    @commands.has_permissions(administrator=True)
    async def ai_rem_channel(self, ctx, channel: discord.TextChannel):
        ai_cfg = self.config.setdefault("ai", {})
        channel_ids = self._parse_channel_ids(ai_cfg.get("allowed_channels", []))

        if channel.id not in channel_ids:
            await ctx.send("Tenhle kanál není v AI povoleném seznamu.")
            return

        channel_ids.remove(channel.id)
        ai_cfg["allowed_channels"] = sorted(channel_ids)
        self._save_config()
        await ctx.send(f"AI bylo zakázáno v kanálu {channel.mention}.")

    @commands.command(name="ai")
    async def ai_manual_prompt(self, ctx, *, prompt: str):
        ai_cfg = self.config.get("ai", {})
        if not ai_cfg.get("enabled", False):
            await ctx.send(
                "AI je momentálně vypnuté. Admin může zapnout přes `!ai_on`."
            )
            return

        ai_allowed_channel_ids = self._parse_channel_ids(
            ai_cfg.get("allowed_channels", [])
        )
        if ai_allowed_channel_ids and ctx.channel.id not in ai_allowed_channel_ids:
            await ctx.send("AI v tomto kanálu není povolené.")
            return

        if self._client is None:
            await ctx.send("AI není inicializováno (zkontroluj env `GOOGLE_API_KEY`).")
            return

        full_prompt = await self._build_prompt(ctx.message, prompt)
        try:
            async with ctx.typing():
                answer, finish_reason, used_model = await self._generate_response(
                    full_prompt
                )
            await self._send_long_message(ctx.channel, answer)
            if isinstance(ctx.channel, discord.abc.GuildChannel):
                await self._log_finish_reason(
                    source="command",
                    channel=ctx.channel,
                    user=ctx.author,
                    finish_reason=finish_reason,
                    model_used=used_model,
                )
        except Exception as exc:
            logger.exception("Manual AI prompt failed: %s", exc)
            await self._log_ai_error(
                source="command",
                channel_name=str(ctx.channel),
                user_name=str(ctx.author),
                error=exc,
            )


async def setup(bot):
    await bot.add_cog(AI(bot))
