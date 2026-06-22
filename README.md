# rpbot

A lightweight Discord bot written in Python using `discord.py` with a modular Cog-based structure.

## Features
- **Admin commands**: send server rules, bulk-assign roles, manage allowed text channels.
- **Music commands**: play audio from YouTube URLs, stop, and skip.
- **Fun commands**: meme/sound effects and small random commands.
- **AI chat replies (GenAI)**: optional Gemini integration for message replies in chat.

## Project Structure
- `main.py` – bot entry point, config/content loading, event handlers, cog loading.
- `cogs/` – command modules (`admin.py`, `music.py`, `fun.py`, `test.py`).
- `config.json` – command prefix, allowed channels, yt-dlp/ffmpeg options.
- `content.json` – text content and file paths used by commands.
- `token` – Discord bot token (plain text, one line).
- `sources/` – static media files (audio and images).

## Requirements
- Python 3.10+
- `discord.py`
- `yt-dlp`
- `ffmpeg` available in system PATH

## Run
1. Install dependencies (for example): `pip install discord.py yt-dlp`
2. Put your Discord bot token into the `token` file in project root
3. Start the bot: `python main.py`

## AI Setup (Gemini / GenAI)
1. Install all dependencies from file: `pip install -r requirements.txt`
2. Add Gemini API key:
	 - environment variable `GOOGLE_API_KEY` (or `GEMINI_API_KEY`), or
	 - file `genai_token` in project root (one line with API key)
3. Start bot and enable AI command: `!ai_on`

### AI Behavior
- Bot replies when mentioned (`@bot`) and when user replies to bot message.
- AI reacts only in channels listed in `ai.allowed_channels`.
- Optional random auto-reply can be enabled via `ai.auto_reply_channels` and `ai.auto_reply_chance`.
- Status command: `!ai_status`
- Manual generation command: `!ai <text>`

### AI Config Keys (`config.json`)
- `ai.enabled`: global switch for AI replies
- `ai.model`: model name (default `gemini-2.5-flash`)
- `ai.system_prompt`: style/persona of bot responses
- `ai.allowed_channels`: where AI replies are allowed (`[]` = all channels)
- `ai.auto_reply_channels`: channel IDs for random auto replies
- `ai.auto_reply_chance`: 0.0 to 1.0 probability in auto-reply channels
- `ai.history_window_hours`: how many hours back AI can read chat history for context
- `ai.history_message_limit`: max number of history messages loaded into context


## Command List and Usage
Command prefix is loaded from `config.json` (`command_prefix`). In examples below, prefix is `!`.

### Core (`main.py`)
- `!restart`
	Restarts the bot process. Administrator only.
- `!end`
	Shuts the bot down. Administrator only.
- `!status`
	Shows a compact runtime/status overview for debugging.

### Admin (`cogs/admin.py`)
- `!pravidla`
	Sends server rules content from `content.json`. Administrator only.
- `!roleall @Role`
	Bulk-assigns a role to all non-bot members (with role hierarchy checks). Administrator only.
- `!add_channel #channel`
	Adds a text channel to global command allowlist (`allowed_channels`). Administrator only.
- `!rem_channel #channel`
	Removes a text channel from global command allowlist (`allowed_channels`). Administrator only.
- `!log`
	Sets current channel as bot log channel. Administrator only.
- `!log #channel`
	Sets selected channel as bot log channel. Administrator only.

### Auto Role (`cogs/auto.py`)
- `!set_auto_role`
	Shows currently configured auto role.
- `!set_auto_role @Role`
	Sets auto role for new members. Administrator only.

### Music (`cogs/music.py`)
- `!play <YouTube_URL>`
	Joins your voice channel and plays audio from the URL. If something is already playing, song is added to queue.
- `!queue`
	Shows currently playing track and upcoming queue.
- `!nowplaying` / `!np`
	Shows detailed information about the current track.
- `!pause`
	Pauses currently playing song.
- `!stop`
	Stops playback, clears queue, and disconnects bot from voice.
- `!skip`
	Skips currently playing (or paused) audio and continues with next track from queue.

### Music Notes
- The music queue is persisted in `music_state.json` so queued tracks survive a bot restart.

### Fun (`cogs/fun.py`)
- `!gragas_jumpscare @member`
	Joins member's voice channel and plays the configured Gragas sound.
- `!pero`
	Sends a random joke size value.
- `!mince`
	Coin toss (`Orel`/`Panna`).
- `!random`
	Random number from `0` to `100`.
- `!random <max>`
	Random number from `0` to `<max>`.
- `!random <min> <max>`
	Random number between `<min>` and `<max>` (order does not matter).
- `!quote add "Hláška" - @Uživatel`
	Adds quote to `sources/text/quotes.txt`.
- `!quote random`
	Shows random quote from `sources/text/quotes.txt`.
- `!8ball <otázka>`
	Shows random answer from `sources/text/8ball.txt`.

### Voice Moderation (`cogs/voice.py`)
- `!deny @member`
	Toggles member connect permission in your current voice channel.

### AI (`cogs/ai.py`)
- `!ai_status`
	Shows AI status, model, AI allowed channels and auto-reply channels. Administrator only.
- `!ai_on`
	Enables AI in config and initializes AI client. Administrator only.
- `!ai_off`
	Disables AI in config. Administrator only.
- `!ai_add_channel #channel`
	Adds channel to `ai.allowed_channels` (where AI is allowed to respond). Administrator only.
- `!ai_rem_channel #channel`
	Removes channel from `ai.allowed_channels`. Administrator only.
- `!ai <text>`
	Manual AI prompt in chat.

### Test (`cogs/test.py`)
- `!test`
	Basic test response.
- `!join`
	Test command for joining/moving voice channel.