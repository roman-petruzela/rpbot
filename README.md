# RPBot

A Discord bot written in Python, built on top of `discord.py` with a modular Cog architecture.

## Features

- Server administration (rules, bulk role assignment, allowed text channels, log channel)
- YouTube music playback via `yt-dlp` + `ffmpeg` (queue, skip, pause, persisted queue)
- Fun commands (random, coin flip, quotes, 8ball, audio meme)
- Automatic temporary voice rooms + basic voice moderation
- Optional AI replies via Google GenAI

## Tech Stack

- Python 3.10+
- `discord.py`
- `yt-dlp`
- `ffmpeg` (must be available in PATH)
- `google-genai` (only for AI features)

## Prerequisites & Discord Intents

**Important:** This bot requires **Privileged Intents** to be enabled in the Discord Developer Portal. Before running the bot, navigate to your Bot settings on the developer portal and toggle **ON** the following:
- **Presence Intent**
- **Server Members Intent** (required for `!roleall`)
- **Message Content Intent** (required for prefix commands and AI replies)

Without these intents, the bot will not respond to commands or function properly.

## Installation

1. Clone the repository.

```bash
git clone [https://github.com/roman-petruzela/rpbot.git](https://github.com/roman-petruzela/rpbot.git)
cd rpbot
```

2. Create and activate a virtual environment.
- On Windows (PowerShell / Cmd):
```bash
python -m venv venv
.\venv\Scripts\activate
```
- On Linux / macOS:
```bash
python3 -m venv venv
source venv/bin/activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create a `.env` file in the project root:

```env
DISCORD_TOKEN=your_discord_bot_token
# optional for AI:
# GOOGLE_API_KEY=your_google_api_key
# or
# GEMINI_API_KEY=your_google_api_key
```

5. Create `config.json` in the project root (this file is local and ignored by git).

## Configuration

The bot uses a single configuration file: `config.json`.

### Configuration Notes

- `allowed_channels: []` means commands are allowed in all channels.
- Set `voice_trigger_id` to the voice channel ID that should create temporary rooms.
- Set `log_channel_id` to a text channel for internal bot logs.
- Restrict AI replies with `ai.allowed_channels` if needed.

## Run

- On Windows (PowerShell / Cmd):
```bash
python main.py
```
- On Linux / macOS:
```bash
python3 ./main.py
```

## Commands

The prefix is loaded from `config.json` (`command_prefix`). Examples below use `!`.

### Core

- `!status` — bot runtime info
- `!restart` — restart process (admin)
- `!end` — shut down bot (admin)

### Admin

- `!pravidla` — sends rules from `content.json` (admin)
- `!roleall @Role` — assigns a role to all non-bot members (admin)
- `!add_channel #channel` — adds a text channel to allowlist (admin)
- `!rem_channel #channel` — removes a text channel from allowlist (admin)
- `!log [#channel]` — sets log channel (admin)

### Auto Role

- `!set_auto_role` — shows current auto role
- `!set_auto_role @Role` — sets auto role for new members (admin)

### Music

- `!play <YouTube_URL>` — play or queue a track
- `!queue` — show current queue
- `!nowplaying` / `!np` — show currently playing track
- `!pause` — pause playback
- `!skip` — skip current track
- `!stop` — stop, disconnect, clear queue
- `!music` — music cog status/debug output

### Fun

- `!gragas_jumpscare @member`
- `!pero`
- `!mince`
- `!random [max]` / `!random <min> <max>`
- `!quote add "Text" - @User`
- `!quote random`
- `!8ball <question>`

### Voice

- `!deny @member` — toggle member access to your current voice channel
- `!lock` — lock/unlock current voice channel for `@everyone`

### AI

- `!ai_status` — AI status (admin)
- `!ai_on` / `!ai_off` — enable/disable AI (admin)
- `!ai_add_channel #channel` / `!ai_rem_channel #channel` (admin)
- `!ai <text>` — manual AI prompt

## Project Structure

```text
.
├── main.py
├── config_manager.py
├── content.json
├── cogs/
│   ├── admin.py
│   ├── ai.py
│   ├── auto.py
│   ├── fun.py
│   ├── music.py
│   ├── voice.py
│   └── test.py
└── sources/
    ├── audio/
    ├── pictures/
    └── text/
```

## Runtime Data

- `music_state.json` is generated at runtime and stores the persisted music queue.

## Troubleshooting

- **Bot does not start:** verify `DISCORD_TOKEN` in `.env`.
- **Voice does not work:** verify `ffmpeg` in PATH and that `PyNaCl` is installed.
- **AI does not respond:** verify `GOOGLE_API_KEY`/`GEMINI_API_KEY` and `ai.enabled`.
- **Commands do not work in a channel:** check `allowed_channels` in `config.json`.
