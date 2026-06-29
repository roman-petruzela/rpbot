import json
import logging
from pathlib import Path

logger = logging.getLogger("rpbot")


def parse_channel_ids(raw_channels) -> set[int]:
    if isinstance(raw_channels, int):
        raw_channels = [raw_channels]

    channel_ids = set()
    for channel_id in raw_channels or []:
        try:
            channel_ids.add(int(channel_id))
        except (TypeError, ValueError):
            continue

    return channel_ids


def validate_config(config: dict) -> dict:
    validated = dict(config) if isinstance(config, dict) else {}

    command_prefix = validated.get("command_prefix", "!")
    if not isinstance(command_prefix, str) or not command_prefix.strip():
        logger.warning("Invalid command_prefix in config; falling back to '!'.")
        validated["command_prefix"] = "!"

    allowed_channels = validated.get("allowed_channels", [])
    if not isinstance(allowed_channels, (list, int)):
        logger.warning(
            "Invalid allowed_channels in config; falling back to empty list."
        )
        allowed_channels = []
    validated["allowed_channels"] = sorted(parse_channel_ids(allowed_channels))

    for key in ("ydl_options", "ffmpeg_options", "ai"):
        value = validated.get(key)
        if value is not None and not isinstance(value, dict):
            logger.warning("Invalid %s in config; falling back to empty dict.", key)
            validated[key] = {}

    return validated


def _load_raw_config() -> dict:
    config_path = Path(__file__).parent / "config.json"
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_content() -> dict:
    content_path = Path(__file__).parent / "content.json"
    with open(content_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config() -> None:
    config_path = Path(__file__).parent / "config.json"

    CONFIG["allowed_channels"] = sorted(list(ALLOWED_CHANNEL_IDS))

    try:
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(CONFIG, f, indent=4, ensure_ascii=False)
    except Exception as e:
        logger.error("Nepodařilo se uložit config.json: %s", e)


CONFIG = validate_config(_load_raw_config())
CONTENT = load_content()
ALLOWED_CHANNEL_IDS = parse_channel_ids(CONFIG.get("allowed_channels", []))
