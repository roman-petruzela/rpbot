import json
import logging
import os
import tempfile
from pathlib import Path

logger = logging.getLogger("rpbot")
CONFIG_PATH = Path(__file__).parent / "config.json"


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
        command_prefix = "!"
    validated["command_prefix"] = command_prefix

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


def _load_json_file(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data if isinstance(data, dict) else {}


def _load_raw_config() -> dict:
    try:
        return _load_json_file(CONFIG_PATH)
    except Exception as e:
        logger.warning("Nepodařilo se načíst config.json: %s", e)
        return {}


def load_content() -> dict:
    content_path = Path(__file__).parent / "content.json"
    with open(content_path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_config() -> None:
    CONFIG["allowed_channels"] = sorted(list(ALLOWED_CHANNEL_IDS))

    try:
        config_dir = CONFIG_PATH.parent
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=config_dir,
            delete=False,
            prefix="config.",
            suffix=".tmp",
        ) as temp_file:
            temp_path = Path(temp_file.name)
            json.dump(CONFIG, temp_file, indent=4, ensure_ascii=False)
            temp_file.flush()
            os.fsync(temp_file.fileno())
        os.replace(temp_path, CONFIG_PATH)
    except Exception as e:
        logger.error("Nepodařilo se uložit config.json: %s", e)


CONFIG = validate_config(_load_raw_config())
CONTENT = load_content()
ALLOWED_CHANNEL_IDS = parse_channel_ids(CONFIG.get("allowed_channels", []))
