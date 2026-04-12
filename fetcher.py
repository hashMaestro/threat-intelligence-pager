"""
RSS-Fetcher: Liest konfigurierte Feeds und liefert Einträge der letzten 24 Stunden.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import urlparse

import feedparser
import requests

from config import RSSFeed


@dataclass(frozen=True)
class Article:
    """Ein normalisierter RSS-Artikel für die weitere Verarbeitung."""

    title: str
    link: str
    summary: str
    source_name: str
    published_at: datetime


def _parse_published(entry: dict[str, Any]) -> datetime | None:
    """
    Ermittelt das Veröffentlichungsdatum eines Feed-Eintrags.

    Nutzt bevorzugt strukturierte Felder von feedparser, fällt sonst auf
    RFC-822-Datumsstrings zurück.
    """
    # feedparser liefert time.struct_time oder None
    for key in ("published_parsed", "updated_parsed", "created_parsed"):
        t = entry.get(key)
        if t:
            try:
                return datetime.fromtimestamp(time.mktime(t), tz=timezone.utc)
            except (OverflowError, OSError, ValueError):
                continue

    for key in ("published", "updated", "created"):
        raw = entry.get(key)
        if isinstance(raw, str) and raw.strip():
            try:
                dt = parsedate_to_datetime(raw)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt.astimezone(timezone.utc)
            except (TypeError, ValueError):
                continue

    return None


def _entry_summary(entry: dict[str, Any]) -> str:
    """Kurzbeschreibung aus summary oder content extrahieren."""
    if entry.get("summary"):
        return str(entry["summary"]).strip()
    content = entry.get("content")
    if isinstance(content, list) and content:
        first = content[0]
        if isinstance(first, dict) and first.get("value"):
            return str(first["value"]).strip()
    return ""


def _user_agent() -> str:
    """Erlaubtigen User-Agent für HTTP-Requests (manche Feeds blocken Defaults)."""
    return (
        "ThreatIntelPager/1.0 (+https://github.com/; personal threat intel; "
        "Python feedparser)"
    )


def fetch_feed_entries(
    feed: RSSFeed,
    *,
    timeout_seconds: int = 25,
) -> list[dict[str, Any]]:
    """
    Lädt einen RSS/Atom-Feed per HTTP und parst ihn mit feedparser.

    Raises bei schwerwiegenden Netzwerkfehlern; leere/fehlerhafte Antworten
    werden als leere Liste behandelt.
    """
    headers = {"User-Agent": _user_agent(), "Accept": "application/rss+xml, */*"}
    response = requests.get(feed.url, headers=headers, timeout=timeout_seconds)
    response.raise_for_status()

    # feedparser kann Bytes oder Text verarbeiten
    parsed = feedparser.parse(response.content)
    if getattr(parsed, "bozo", False) and not getattr(parsed, "entries", None):
        # Feed defekt — keine Einträge; Aufrufer kann loggen
        return []

    return list(parsed.entries)


def collect_articles_from_feed(
    feed: RSSFeed,
    *,
    max_age: timedelta | None = None,
) -> list[Article]:
    """
    Liefert Artikel eines einzelnen Feeds, die nicht älter als `max_age` sind.

    Wirft bei Netzwerk-/HTTP-Fehlern — in `main.py` pro Feed mit try/except
    abfangen, damit ein offline Feed nicht den gesamten Lauf stoppt.
    """
    if max_age is None:
        max_age = timedelta(hours=24)

    now = datetime.now(timezone.utc)
    cutoff = now - max_age
    articles: list[Article] = []

    entries = fetch_feed_entries(feed)
    for entry in entries:
        title = (entry.get("title") or "Ohne Titel").strip()
        link = (entry.get("link") or "").strip()
        if not link:
            # Fallback: id kann eine URL sein
            link = (entry.get("id") or "").strip()
        if not link or not _looks_like_http_url(link):
            continue

        published = _parse_published(entry)
        if published is None:
            continue
        if published < cutoff:
            continue

        articles.append(
            Article(
                title=title,
                link=link,
                summary=_entry_summary(entry),
                source_name=feed.name,
                published_at=published,
            )
        )

    articles.sort(key=lambda a: a.published_at, reverse=True)
    return articles


def collect_recent_articles(
    feeds: tuple[RSSFeed, ...],
    *,
    max_age: timedelta | None = None,
) -> list[Article]:
    """
    Sammelt aus allen Feeds (ohne Fehlerbehandlung pro Feed).

    Für robuste Orchestrierung lieber `collect_articles_from_feed` aus `main.py`
    mit try/except pro Quelle aufrufen.
    """
    merged: list[Article] = []
    for feed in feeds:
        merged.extend(collect_articles_from_feed(feed, max_age=max_age))
    merged.sort(key=lambda a: a.published_at, reverse=True)
    return merged


def _looks_like_http_url(value: str) -> bool:
    try:
        p = urlparse(value)
        return p.scheme in ("http", "https") and bool(p.netloc)
    except Exception:
        return False
