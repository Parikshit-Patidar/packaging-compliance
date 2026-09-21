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

def get_gemini_api_key() -> Optional[str]:
    # 1. Environment variable
    env_key = os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY")
    if env_key and len(env_key.strip()) > 5:
        return env_key.strip()
    # 2. Project root .env file check
    try:
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_file = os.path.join(root, ".env")
        if os.path.exists(env_file):
            with open(env_file, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("GEMINI_API_KEY=") or line.startswith("GOOGLE_API_KEY="):
                        k = line.split("=", 1)[1].strip().strip('"').strip("'")
                        if len(k) > 5:
                            return k
    except Exception:
        pass
    # 3. Persistent config file in AppData / User directory
    cfg = load_config()
    cfg_key = cfg.get("gemini_api_key")
    if cfg_key and len(cfg_key.strip()) > 5:
        return cfg_key.strip()
    return None

def set_gemini_api_key(key: str):
    if key and len(key.strip()) > 5:
        save_config({"gemini_api_key": key.strip()})
        os.environ["GEMINI_API_KEY"] = key.strip()
