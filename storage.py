"""
Persistenz für bereits verarbeitete Artikel-URLs (Duplikatsfilter).

Die Datei ``seen_urls.json`` liegt im Projektverzeichnis und kann in Git
versioniert werden (z. B. GitHub Actions committet Updates nach jedem Lauf).
"""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Final

logger = logging.getLogger(__name__)

# Projektroot = Verzeichnis dieser Datei (neben main.py)
_SEEN_URLS_FILE: Final[Path] = Path(__file__).resolve().parent / "seen_urls.json"


def load_seen_urls() -> set[str]:
    """
    Liest gespeicherte URLs aus ``seen_urls.json``.

    Gibt ein leeres Set zurück, wenn die Datei fehlt. Bei beschädigtem JSON
    wird gewarnt und ebenfalls ein leeres Set geliefert (CI soll nicht abbrechen).
    """
    if not _SEEN_URLS_FILE.is_file():
        return set()

    try:
        raw = _SEEN_URLS_FILE.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning(
            "seen_urls.json ist kein gültiges JSON (%s) — starte mit leerem Set.",
            exc,
        )
        return set()

    if not isinstance(data, list):
        logger.warning("seen_urls.json: erwartet JSON-Array von URLs — ignoriere.")
        return set()

    return {str(u).strip() for u in data if str(u).strip()}


def save_seen_urls(urls_set: set[str]) -> None:
    """
    Speichert das URL-Set nach ``seen_urls.json`` (sortiert, lesbar für Git-Diffs).
    """
    # Sortierte Liste: stabile, nachvollziehbare Diffs im Repository
    payload = sorted(urls_set)
    text = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    _SEEN_URLS_FILE.write_text(text, encoding="utf-8")
