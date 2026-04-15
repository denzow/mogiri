import os
from pathlib import Path

import yaml

DATA_DIR = Path(os.environ.get("MOGIRI_DATA_DIR", Path.home() / ".mogiri"))

# Default values
DEFAULTS = {
    "server": {
        "host": "127.0.0.1",
        "port": 8899,
    },
    "log": {
        "retention_days": 30,
        "max_per_job": 100,
    },
}


def load_yaml_config(config_path=None):
    """Load configuration from YAML file, falling back to defaults."""
    if config_path is None:
        config_path = DATA_DIR / "config.yaml"
    else:
        config_path = Path(config_path)

    cfg = {}
    if config_path.exists():
        with open(config_path) as f:
            cfg = yaml.safe_load(f) or {}

    # Merge: defaults <- yaml <- env vars
    merged = {}
    for section, defaults in DEFAULTS.items():
        file_section = cfg.get(section, {}) or {}
        merged[section] = {}
        for key, default in defaults.items():
            merged[section][key] = file_section.get(key, default)

    # Environment variables override everything
    if os.environ.get("MOGIRI_LOG_RETENTION_DAYS"):
        merged["log"]["retention_days"] = int(os.environ["MOGIRI_LOG_RETENTION_DAYS"])
    if os.environ.get("MOGIRI_LOG_MAX_PER_JOB"):
        merged["log"]["max_per_job"] = int(os.environ["MOGIRI_LOG_MAX_PER_JOB"])

    return merged


class Config:
    SQLALCHEMY_DATABASE_URI = f"sqlite:///{DATA_DIR / 'mogiri.db'}"
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"timeout": 30}}
    SECRET_KEY = os.environ.get("MOGIRI_SECRET_KEY", "mogiri-local-dev-key")
    DATA_DIR = DATA_DIR

    @staticmethod
    def from_yaml(config_path=None):
        """Create a config dict with YAML settings merged in."""
        cfg = load_yaml_config(config_path)
        return {
            "SQLALCHEMY_DATABASE_URI": Config.SQLALCHEMY_DATABASE_URI,
            "SQLALCHEMY_ENGINE_OPTIONS": Config.SQLALCHEMY_ENGINE_OPTIONS,
            "SECRET_KEY": Config.SECRET_KEY,
            "DATA_DIR": Config.DATA_DIR,
            "SERVER_HOST": cfg["server"]["host"],
            "SERVER_PORT": cfg["server"]["port"],
            "LOG_RETENTION_DAYS": cfg["log"]["retention_days"],
            "LOG_MAX_PER_JOB": cfg["log"]["max_per_job"],
        }
