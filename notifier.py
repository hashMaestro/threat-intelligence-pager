"""
Push-Benachrichtigungen über ntfy.sh (oder kompatible Self-Hosted-Instanz).
"""

from __future__ import annotations

import requests

from config import NTFY_BASE_URL, get_ntfy_topic


def _latin1_safe_header(value: str, max_len: int) -> str:
    """
    HTTP-Header (urllib3/requests) müssen als latin-1 kodierbar sein.

    Umlaute (äöü) bleiben erhalten; Zeichen > U+FF (z. B. Emoji) werden ersetzt,
    damit keine ``UnicodeEncodeError``/latin-1-Fehler beim Senden entstehen.
    """
    clipped = value[:max_len]
    return clipped.encode("latin-1", "replace").decode("latin-1")


def send_ntfy_message(
    body: str,
    *,
    title: str | None = None,
    click_url: str | None = None,
    priority: str = "default",
    tags: str = "warning,mag",
    timeout_seconds: int = 30,
) -> None:
    """
    Sendet eine Nachricht per POST an ntfy.

    :param body: Nachrichtentext; mit Header ``Markdown: yes`` werden \
        gängige Markdown-Elemente gerendert (ntfy unterstützt Emoji nativ im UTF-8-Body).
    :param title: Kurzer Titel in der Benachrichtigung (optional).
    :param click_url: Wenn gesetzt, setzt den ntfy-Header ``Click`` (externe URL beim Tippen).
        Weglassen, damit nur die ntfy-Nachrichtenansicht geöffnet wird; Links gehören in den Body.
    :param priority: ntfy-Priorität: min, low, default, high, urgent.
    :param tags: Kommagetrennte Emoji/Tags (siehe ntfy-Dokumentation).
    :raises requests.HTTPError: bei nicht erfolgreicher HTTP-Antwort.
    """
    topic = get_ntfy_topic()
    url = f"{NTFY_BASE_URL}/{requests.utils.quote(topic, safe='')}"

    headers: dict[str, str] = {
        # UTF-8 explizit — Emoji und Umlaute zuverlässig
        "Content-Type": "text/plain; charset=utf-8",
        "Markdown": "yes",
    }
    if title:
        headers["Title"] = _latin1_safe_header(title, 256)
    if click_url:
        headers["Click"] = _latin1_safe_header(click_url, 2048)
    if priority:
        headers["Priority"] = _latin1_safe_header(priority, 32)
    if tags:
        headers["Tags"] = _latin1_safe_header(tags, 256)

    response = requests.post(
        url,
        data=body.encode("utf-8"),
        headers=headers,
        timeout=timeout_seconds,
    )
    response.raise_for_status()
