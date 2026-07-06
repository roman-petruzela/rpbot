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

## Installation

1. Clone the repository.
2. Create and activate a virtual environment.
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

## Configuration (`config.json`)

The bot uses a single configuration file: `config.json`.

Recommended minimal template:

```json
{
  "command_prefix": "!",
  "auto_role_id": "",
  "allowed_channels": [],
  "ydl_options": {
    "format": "bestaudio[abr<=96]/bestaudio/best",
    "remote_components": ["ejs:github"],
    "js_runtimes": {
      "deno": {},
      "node": {}
    },
    "noplaylist": true,
    "quiet": true
  },
  "ffmpeg_options": {
    "before_options": "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5",
    "options": "-vn -loglevel quiet"
  },
  "ffmpeg_executable": "ffmpeg",
  "voice_trigger_id": null,
  "voice_default_name": "voice - {member.display_name}",
  "log_channel_id": null,
  "ai": {
    "enabled": false,
    "model": "gemini-3.1-flash-lite-preview",
    "fallback_models": ["gemini-2.5-flash"],
    "temperature": 0.7,
    "max_output_tokens": 500,
    "system_prompt": "You are a friendly Discord bot. Keep responses concise and useful.",
    "respond_when_mentioned": true,
    "respond_when_replied": true,
    "history_window_hours": 12,
    "history_message_limit": 50,
    "allowed_channels": [],
    "auto_reply_channels": [],
    "auto_reply_chance": 0.2,
    "min_response_interval_seconds": 6
  }
}
```

### Configuration Notes

- `allowed_channels: []` means commands are allowed in all channels.
- Set `voice_trigger_id` to the voice channel ID that should create temporary rooms.
- Set `log_channel_id` to a text channel for internal bot logs.
- Restrict AI replies with `ai.allowed_channels` if needed.

## Run

```bash
python main.py
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
