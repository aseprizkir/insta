"""
utils/config_manager.py
Semua fungsi load/save konfigurasi bot_config.json dan threads_config.json.
Dipisah dari run.py supaya modular.
"""
import os
import json


BOT_CONFIG_PATH = "bot_config.json"
THREADS_CONFIG_PATH = "threads_config.json"


def default_bot_config() -> dict:
    return {
        "telegram_bot_token": "",
        "instagram_cookie": "",
        "openai_api_key": "",
        "openai_base_url": "https://router.bynara.id/v1",
        "openai_model": "mimo-v2.5-pro-free",
        "allowed_users": [],
        "admin_cookies": []
    }


def save_bot_config(data: dict):
    with open(BOT_CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=4)
    try:
        os.chmod(BOT_CONFIG_PATH, 0o600)
    except OSError:
        pass


def load_bot_config() -> dict:
    default = default_bot_config()
    if not os.path.exists(BOT_CONFIG_PATH):
        save_bot_config(default)
        return default
    try:
        with open(BOT_CONFIG_PATH, "r") as f:
            data = json.load(f)
        if isinstance(data, dict):
            default.update(data)
    except Exception:
        save_bot_config(default)
    return default


def default_threads_config() -> dict:
    return {
        "threads_cookie": "",
        "x_ig_app_id": "238260118697367",
        "x_fb_lsd": "",
        "fb_dtsg": "",
        "doc_id_comments": "27459511047022916",
        "doc_id_posts": "26868991796135032",
        "doc_id_follow": "26234294899535416",
        "doc_id_like": "24753372994365040",
        "doc_id_followers": "27390125367306731",
        "doc_id_following": "26565260693147172",
        "doc_id_friendships": "27932967052970549",
        "admin_threads_cookies": []
    }


def save_threads_config(data: dict):
    with open(THREADS_CONFIG_PATH, "w") as f:
        json.dump(data, f, indent=4)
    try:
        os.chmod(THREADS_CONFIG_PATH, 0o600)
    except OSError:
        pass


def load_threads_config() -> dict:
    default = default_threads_config()
    if not os.path.exists(THREADS_CONFIG_PATH):
        save_threads_config(default)
        return default
    try:
        with open(THREADS_CONFIG_PATH, "r") as f:
            data = json.load(f)
        if isinstance(data, dict):
            default.update(data)
    except Exception:
        save_threads_config(default)
    return default
