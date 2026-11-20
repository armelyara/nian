"""Pydantic schemas: the single source of truth for the feed contract."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, HttpUrl, field_validator

CATEGORIES: dict[str, str] = {
    "Concerts": "#E78D38",
    "Protests": "#D97B22",
    "Incidents": "#e5443b",
    "Tech": "#74A5CC",
    "Other": "#8a9599",
}
Category = Literal["Concerts", "Protests", "Incidents", "Tech", "Other"]
Precision = Literal["exact", "city", "region"]

YOUTUBE_EMBED_PREFIX = "https://www.youtube-nocookie.com/embed/"


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


class FeedItem(BaseModel):
    id: str = Field(max_length=64, pattern=r"^[A-Za-z0-9_\-:]+$")
    source: str = Field(max_length=32)
    city: str = Field(max_length=120)
    lat: float = Field(ge=-90, le=90)
    lon: float = Field(ge=-180, le=180)
    precision: Precision = "city"
    category: Category = "Other"
    text: str = Field(default="", max_length=500)
    author: str = Field(default="", max_length=120)
    url: HttpUrl | None = None
    embed: str | None = None
    video: HttpUrl | None = None
    thumb: HttpUrl | None = None
    ts: datetime = Field(default_factory=utcnow)

    @field_validator("embed")
    @classmethod
    def _only_youtube_embeds(cls, v: str | None) -> str | None:
        # Embeds become iframe src on the client: never accept arbitrary origins.
        if v is not None and not v.startswith(YOUTUBE_EMBED_PREFIX):
            raise ValueError("embed must be a youtube-nocookie embed URL")
        return v

    @field_validator("url", "video", "thumb")
    @classmethod
    def _https_only(cls, v: HttpUrl | None) -> HttpUrl | None:
        if v is not None and v.scheme != "https":
            raise ValueError("only https URLs are accepted")
        return v


class Place(BaseModel):
    name: str
    lat: float
    lon: float


class FeedPage(BaseModel):
    items: list[FeedItem]


class SearchResult(BaseModel):
    items: list[FeedItem]
    place: Place | None = None
    cached: bool = False


class Meta(BaseModel):
    categories: dict[str, str] = CATEGORIES
    search_enabled: bool
    token_required: bool
