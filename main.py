"""
Orchestrierung: Feeds laden → Gemini analysieren → relevante Treffer per ntfy versenden.

Lokal: `.env` mit GEMINI_API_KEY und NTFY_TOPIC anlegen.
CI: GitHub Secrets derselben Namen setzen; ``seen_urls.json`` per Workflow committen.
"""

from __future__ import annotations

import logging
import sys
from datetime import timedelta

from config import MIN_RISK_STARS, RSS_FEEDS
from analyzer import AnalysisResult, analyze_article_for_kmu
from fetcher import Article, collect_articles_from_feed
from notifier import send_ntfy_message
from storage import load_seen_urls, save_seen_urls

# Logging nach stderr — in GitHub Actions sichtbar
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("threat_intel_pager")


def _dedupe_articles(articles: list[Article]) -> list[Article]:
    """Entfernt Dubletten nach Link (bevorzugt neueste Reihenfolge beibehalten)."""
    seen: set[str] = set()
    unique: list[Article] = []
    for a in articles:
        if a.link in seen:
            continue
        seen.add(a.link)
        unique.append(a)
    return unique


def _format_push_title(article: Article, result: AnalysisResult) -> str:
    """
    ntfy-Titel als HTTP-Header: nur latin-1-tauglich (keine Emoji — sonst latin-1-Fehler).
    Sterne siehe sichtbar im Nachrichten-Body (_format_push_body).
    """
    stars = min(5, max(0, result.risk_score))
    prefix = f"[KMU-Risiko {stars}/5] " if stars else "[KMU-Risiko ?] "
    return (prefix + article.title)[:240]


def _format_push_body(article: Article, result: AnalysisResult) -> str:
    """Markdown-Body: Kurz-Sterneile, Quelle, Link und Gemini-Text (UTF-8-Body, Emoji ok)."""
    stars = min(5, max(0, result.risk_score))
    stars_line = (
        ("⭐" * stars + "☆" * (5 - stars) + f" ({stars}/5)\n\n") if stars else ""
    )
    header = (
        stars_line
        + f"**Quelle:** {article.source_name}\n"
        + f"**Link:** {article.link}\n\n"
        + "---\n\n"
    )
    return header + result.markdown_text


def run() -> int:
    """Hauptablauf; Exit-Code 0 bei Erfolg (auch wenn einzelne Feeds fehlschlagen)."""
    # Persistenter Duplikatsfilter (wird am Ende in jedem Fall gespeichert)
    seen_urls = load_seen_urls()
    try:
        return _run_inner(seen_urls)
    finally:
        # Auch bei Fehlern/Frühabbruch: aktuellen Stand schreiben (z. B. erfolgreiche Pushes)
        save_seen_urls(seen_urls)
        logger.info("seen_urls.json gespeichert (%d URLs).", len(seen_urls))


def _run_inner(seen_urls: set[str]) -> int:
    """Kerntlogik mit Zugriff auf das gemeinsame seen_urls-Set."""
    all_articles: list[Article] = []

    for feed in RSS_FEEDS:
        try:
            batch = collect_articles_from_feed(feed, max_age=timedelta(hours=24))
            logger.info("Feed OK: %s — %d Artikel (24h)", feed.name, len(batch))
            all_articles.extend(batch)
        except Exception as exc:
            logger.warning("Feed übersprungen (%s): %s", feed.name, exc)

    articles = _dedupe_articles(all_articles)
    if not articles:
        logger.info("Keine Artikel in den letzten 24 Stunden — Ende.")
        return 0

    logger.info("Insgesamt %d eindeutige Artikel nach Duplikat-Filter.", len(articles))

    sent = 0
    for article in articles:
        # Bereits erfolgreich per ntfy gemeldet (oder manuell in JSON) — kein erneutes Gemini/ntfy
        if article.link in seen_urls:
            logger.info("Bereits gesehen, überspringe: %s", article.title[:80])
            continue

        try:
            result = analyze_article_for_kmu(article)
        except Exception as exc:
            logger.warning("Analyse übersprungen (%s): %s", article.link, exc)
            continue

        if result.risk_score == 0:
            logger.warning(
                "Kein RISIKO_WERT erkannt — überspringe Push: %s",
                article.link,
            )
            continue

        if result.risk_score < MIN_RISK_STARS:
            logger.info(
                "Risiko %d unter Schwellwert %d — kein Push: %s",
                result.risk_score,
                MIN_RISK_STARS,
                article.title[:80],
            )
            continue

        title = _format_push_title(article, result)
        body = _format_push_body(article, result)
        try:
            # Kein Click-Header: Tipp öffnet die Nachricht in ntfy, nicht den Artikel im Browser.
            send_ntfy_message(
                body,
                title=title,
                priority="high" if result.risk_score >= 4 else "default",
            )
            sent += 1
            logger.info("Push gesendet: %s", article.title[:80])
            # Nur bei erfolgreichem Versand persistieren — verhindert Doppel-Pushes in CI
            seen_urls.add(article.link)
        except Exception as exc:
            logger.warning("ntfy fehlgeschlagen (%s): %s", article.link, exc)

    logger.info("Fertig — %d Push-Nachricht(en) versendet.", sent)
    return 0


if __name__ == "__main__":
    sys.exit(run())
