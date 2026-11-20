"""Runtime configuration, read once from environment variables.

Values come from the process environment, then from a `.env` file in the
current directory (never overriding variables already set). Every knob has a
safe production default; development conveniences (demo data, OpenAPI docs)
must be switched on explicitly.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PACKAGE_DIR = Path(__file__).resolve().parent
DEFAULT_DATA_DIR = Path.home() / ".nian"

# Cities collected automatically so the globe is never empty (YouTube key required).
DEFAULT_CITIES = "Abidjan,Paris,Lagos,Dakar,Montreal,Cairo,Tokyo,London"


def load_dotenv(path: Path | str = ".env") -> None:
    """Minimal .env reader (KEY=VALUE lines, # comments, optional quotes)."""
    p = Path(path)
    if not p.is_file():
        return
    for raw in p.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip().removeprefix("export ").strip()
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(key, value)


load_dotenv()


def _bool(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, default))
    except ValueError:
        return default


def _list(name: str, default: str = "") -> list[str]:
    raw = os.environ.get(name, default)
    return [x.strip() for x in raw.split(",") if x.strip()]


@dataclass(frozen=True)
class Settings:
    env: str = field(default_factory=lambda: os.environ.get("NIAN_ENV", "production"))
    db_path: Path = field(default_factory=lambda: Path(os.environ.get("NIAN_DB_PATH", DEFAULT_DATA_DIR / "nian.db")).expanduser())
    static_dir: Path = PACKAGE_DIR / "static"

    # Collectors (NIAN_YOUTUBE_KEY, or the generic YOUTUBE_API_KEY used by v1)
    youtube_key: str = field(default_factory=lambda: os.environ.get("NIAN_YOUTUBE_KEY") or os.environ.get("YOUTUBE_API_KEY", ""))
    youtube_daily_search_budget: int = field(default_factory=lambda: _int("NIAN_YT_DAILY_SEARCHES", 90))
    default_cities: list[str] = field(default_factory=lambda: _list("NIAN_DEFAULT_CITIES", DEFAULT_CITIES))
    refresh_hours: int = field(default_factory=lambda: _int("NIAN_REFRESH_HOURS", 6))
    geocoder_user_agent: str = field(
        default_factory=lambda: os.environ.get("NIAN_GEOCODER_UA", "nian-map (https://pypi.org/project/nian-map/)")
    )
    demo: bool = field(default_factory=lambda: _bool("NIAN_DEMO"))

    # Security
    api_token: str = field(default_factory=lambda: os.environ.get("NIAN_API_TOKEN", ""))
    allowed_hosts: list[str] = field(default_factory=lambda: _list("NIAN_ALLOWED_HOSTS"))
    search_rate_per_minute: int = field(default_factory=lambda: _int("NIAN_SEARCH_RATE", 6))
    max_sse_clients: int = field(default_factory=lambda: _int("NIAN_MAX_SSE", 200))

    # Data lifecycle
    retention_days: int = field(default_factory=lambda: _int("NIAN_RETENTION_DAYS", 30))
    max_feed_limit: int = 500

    @property
    def debug(self) -> bool:
        return self.env == "development"


settings = Settings()
