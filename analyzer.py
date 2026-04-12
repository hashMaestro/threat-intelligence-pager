"""
Gemini-Analyse: Bewertet Cybersecurity-Artikel hinsichtlich Relevanz für deutsche KMU.

Nutzt den offiziellen Google Gen AI SDK (``google-genai``), nicht das eingestellte
``google.generativeai``-Paket.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from google import genai
from google.genai import types

from config import GEMINI_MODEL, get_gemini_api_key
from fetcher import Article


# Maschinenlesbare Zeile zur Risikoextraktion (wird für Filter genutzt)
_RISK_LINE_PATTERN = re.compile(
    r"^\s*RISIKO_WERT:\s*([1-5])\s*$",
    re.IGNORECASE | re.MULTILINE,
)

# Ein Client pro Prozess (Verbindungen wiederverwenden)
_client: genai.Client | None = None


def _get_client() -> genai.Client:
    global _client
    if _client is None:
        _client = genai.Client(api_key=get_gemini_api_key())
    return _client


# System-Anweisung: Rolle, Sprache, Output-Struktur
SYSTEM_INSTRUCTION = """\
Du bist ein Senior Cyber Threat Intelligence (CTI) Analyst und Berater für den DACH-Mittelstand (KMU). Deine Aufgabe ist es, rohe Security-Feeds in hochkonzentrierte, handlungsorientierte Executive Summaries zu filtern. 

Fokus: Extreme Prägnanz (BLUF-Prinzip - Bottom Line Up Front), Fokus auf reale Ausnutzbarkeit (In-the-wild) und Passgenauigkeit für typische KMU-Infrastrukturen (Microsoft 365, Standard-Firewalls, VPNs, kein 24/7 SOC).

BEWERTUNGSKRITERIEN FÜR DAS KMU-RISIKO (1-5):
1 = Irrelevant: Nischensysteme, reine Proof-of-Concepts ohne echten Impact.
2 = Gering: Komplexe Angriffsketten, Phishing ohne neue Taktik.
3 = Moderat: Schwachstellen in genutzter Software, aber kein aktiver Exploit. Standard-Patch-Zyklus reicht.
4 = Hoch: Kritische Lücke in KMU-Standardsoftware (z.B. Fortinet, Exchange, M365) MIT aktiven Exploits.
5 = Kritisch: Massen-Exploitation im Gange, Ransomware-Vorstufe, sofortiges Handeln/Isolieren zwingend.

STRIKTE FORMATVORGABE (Keine Begrüßung, keine Erklärungen, exakt dieses Format einhalten):

RISIKO_WERT: [Ziffer 1-5]

## 📌 Executive Summary
[Maximal 3 Sätze. Nenne sofort den Angriffsvektor, die betroffene Technologie und den potenziellen Business Impact.]

## ⚠️ KMU-Risiko
[Visualisierung mit 5 Sternen, z.B. ⭐⭐⭐⭐☆] ([Ziffer]/5) — [Maximal 1 Satz messerscharfe Begründung, warum dieser Wert für ein KMU vergeben wurde.]

## 🛡️ Actionable Intelligence
- [Pragmatische Maßnahme 1 (z.B. "Patch KB12345 ausrollen")]
- [Pragmatische Maßnahme 2 (z.B. "Port 443 am Gateway einschränken")]
- [Pragmatische Maßnahme 3]
- [Pragmatische Maßnahme 4]
"""


@dataclass(frozen=True)
class AnalysisResult:
    """Ergebnis der KI-Analyse inkl. numerischem Risiko für Filterlogik."""

    risk_score: int
    """Integer 1–5; 0 bedeutet „nicht zuverlässig erkannt“."""

    markdown_text: str
    """Bereinigter Text für die Push-Nachricht (ohne die Zeile RISIKO_WERT)."""


def _strip_risk_line(text: str) -> str:
    """Entfernt die erste Zeile RISIKO_WERT für die Anzeige auf dem Gerät."""
    lines = text.strip().splitlines()
    if lines and _RISK_LINE_PATTERN.match(lines[0]):
        lines = lines[1:]
    while lines and not lines[0].strip():
        lines = lines[1:]
    return "\n".join(lines).strip()


def _extract_risk_score(text: str) -> int:
    m = _RISK_LINE_PATTERN.search(text)
    if not m:
        return 0
    return int(m.group(1))


def analyze_article_for_kmu(article: Article) -> AnalysisResult:
    """
    Sendet Artikelmetadaten an Gemini und liefert strukturierte Analyse.

    Raises bei API-Fehlern — vom Aufrufer (main) abfangen.
    """
    client = _get_client()
    user_payload = (
        f"Titel: {article.title}\n"
        f"Quelle: {article.source_name}\n"
        f"Link: {article.link}\n\n"
        f"Kurzbeschreibung / Auszug:\n{article.summary or '(kein Auszug)'}\n"
    )

    response = client.models.generate_content(
        model=GEMINI_MODEL,
        contents=user_payload,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_INSTRUCTION,
        ),
    )

    try:
        raw = (response.text or "").strip()
    except Exception as exc:
        raise ValueError(
            "Gemini lieferte keinen lesbaren Text (Safety-Filter oder Block?)."
        ) from exc
    if not raw:
        raise ValueError("Leere Antwort von Gemini.")

    risk = _extract_risk_score(raw)
    display = _strip_risk_line(raw)

    return AnalysisResult(risk_score=risk, markdown_text=display)
