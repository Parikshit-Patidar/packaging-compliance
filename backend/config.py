"""
Configuration & Settings Manager for Legal Metrology System
Stores persistent API keys and environment settings in AppData/PackagingCompliance/config.json.
"""

import os
import json
from typing import Optional

def get_config_dir() -> str:
    base = os.environ.get("LOCALAPPDATA") or os.path.expanduser("~")
    cfg_dir = os.path.join(base, "PackagingCompliance")
    os.makedirs(cfg_dir, exist_ok=True)
    return cfg_dir

def get_config_path() -> str:
    return os.path.join(get_config_dir(), "config.json")

def load_config() -> dict:
    p = get_config_path()
    if os.path.exists(p):
        try:
            with open(p, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_config(data: dict):
    p = get_config_path()
    try:
        curr = load_config()
        curr.update(data)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(curr, f, indent=2)
    except Exception as e:
        print("Failed to save config:", e)

def load_env_file():
    """Automatically loads private .env variables from local directory on startup."""
    candidates = [
        os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"),
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"),
        os.path.join(get_config_dir(), ".env"),
        os.path.join(get_config_dir(), "backend", ".env")
    ]
    for p in candidates:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip('"').strip("'")
                            if v:
                                os.environ[k] = v
            except Exception:
                pass

# Load on module startup
load_env_file()


def get_gemini_api_key() -> Optional[str]:
    # Ensure any changes in local .env are loaded
    load_env_file()
    # 1. Environment variable (from .env or shell)
    env_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if env_key and len(env_key.strip()) > 5:
        return env_key.strip()
    # 2. Persistent config file in AppData / User directory
    cfg = load_config()
    cfg_key = cfg.get("gemini_api_key")
    if cfg_key and len(cfg_key.strip()) > 5:
        return cfg_key.strip()
    return None


def set_gemini_api_key(key: str):
    if key and len(key.strip()) > 5:
        cleaned_key = key.strip()
        save_config({"gemini_api_key": cleaned_key})
        os.environ["GEMINI_API_KEY"] = cleaned_key
        # Sync directly into private backend .env
        env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
        try:
            with open(env_path, "w", encoding="utf-8") as f:
                f.write("# Sovereign Legal Metrology Packaging Compliance Engine - Private Configuration\n")
                f.write(f"GEMINI_API_KEY={cleaned_key}\n")
                f.write("PREFERRED_MODEL=gemini-3.8-flash\n")
                f.write("API_PORT=8000\n")
        except Exception as e:
            print("Failed to sync .env file:", e)

def clear_gemini_api_key():
    p = get_config_path()
    try:
        curr = load_config()
        curr.pop("gemini_api_key", None)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(curr, f, indent=2)
        if "GEMINI_API_KEY" in os.environ:
            del os.environ["GEMINI_API_KEY"]
        if "GOOGLE_API_KEY" in os.environ:
            del os.environ["GOOGLE_API_KEY"]
    except Exception as e:
        print("Failed to clear gemini key:", e)
