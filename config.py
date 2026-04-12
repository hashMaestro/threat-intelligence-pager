"""
Konfiguration: Umgebungsvariablen, RSS-Quellen und Schwellenwerte.

Werte können über eine `.env`-Datei (lokal) oder über echte Umgebungsvariablen
(z. B. GitHub Actions Secrets) gesetzt werden.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Final

from dotenv import load_dotenv

# .env laden, falls vorhanden (lokale Entwicklung)
load_dotenv()


@dataclass(frozen=True)
class RSSFeed:
    """Eine RSS-Quelle mit Anzeigenamen und URL."""

    name: str
    url: str


# Beispiel-Feeds: Cybersecurity-Schwerpunkte, teils deutschsprachig / relevant für DE
RSS_FEEDS: Final[tuple[RSSFeed, ...]] = (
    # CERT-Bund (BSI): offizieller Advisory-RSS (alter BSI-SiteGlobals-Link liefert oft 404)
    RSSFeed(
        name="CERT-Bund (Sicherheitshinweise / Advisories)",
        url="https://wid.cert-bund.de/content/public/securityAdvisory/rss",
    ),
    RSSFeed(
        name="The Hacker News",
        url="https://feeds.feedburner.com/TheHackersNews",
    ),
    RSSFeed(
        name="Krebs on Security",
        url="https://krebsonsecurity.com/feed/",
    ),
)

# Mindest-Risiko (1–5), ab dem eine Push-Nachricht gesendet wird
MIN_RISK_STARS: Final[int] = int(os.getenv("MIN_RISK_STARS", "3"))

# Gemini-Modell (siehe Google AI Dokumentation)
GEMINI_MODEL: Final[str] = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

# ntfy-Basis-URL (selbst gehostet möglich)
NTFY_BASE_URL: Final[str] = os.getenv("NTFY_BASE_URL", "https://ntfy.sh").rstrip("/")


def get_gemini_api_key() -> str:
    """Liest den Gemini-API-Schlüssel aus der Umgebung."""
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise ValueError(
            "GEMINI_API_KEY ist nicht gesetzt. "
            "Lege eine .env an oder exportiere die Variable."
        )
    return key


def get_ntfy_topic() -> str:
    """Liest das ntfy-Topic aus der Umgebung."""
    topic = os.getenv("NTFY_TOPIC", "").strip()
    if not topic:
        raise ValueError(
            "NTFY_TOPIC ist nicht gesetzt. "
            "Lege eine .env an oder exportiere die Variable."
        )
    return topic
