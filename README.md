# Personal Threat Intelligence Pager

Ein vollautomatisches, headless-ready Threat Intelligence Framework für Blue Teams und Security-Analysten. Das Tool aggregiert kontinuierlich Cybersecurity-Feeds, evaluiert das akute Risiko für spezifische Infrastrukturen dynamisch via LLM (Gemini) und pusht kritische Alerts als strukturierte Payloads auf mobile Endgeräte.

## Disclaimer

Dieses Tool dient der automatisierten Informationsbeschaffung und dem Noise-Filtering. Die KI-generierten Handlungsempfehlungen ersetzen keine manuelle Verifizierung durch einen Security-Analysten vor Eingriffen in produktive Netzwerke.

## Features
- **Smart Feed Ingestion:** Zieht rohe RSS-Daten (CISA, BSI, Vendor-Blogs) und normalisiert die Struktur für die nachfolgende Pipeline.

- **LLM Risk Scoring:** Nutzt einen restriktiven System-Prompt (Gemini Flash), um irrelevante CVEs zu droppen und das akute Risiko für KMU-Infrastrukturen auf einer Skala (1-5) zu bewerten.

- **Stateful Tracking (Anti-Spam):** Ein lokaler Cache-Mechanismus (seen_urls.json) verhindert Alert-Duplikate bei wiederholter Ausführung.

- **Tokenless Push-Triggering:** Pusht Alerts via nativem HTTP POST-Request an ntfy.sh – ohne App-Registrierung oder komplexe Auth-Flows.

- **Zero-Ops Deployment:** Entwickelt für den komplett autonomen Betrieb via CI/CD-Pipelines (GitHub Actions) oder lokale Cronjobs.

## Prerequisites
Eine Python 3.x Umgebung sowie einen einen API-Key für Google AI Studio.

```bash
git clone https://github.com/hashMaestro/threat-intelligence-pager.git
cd threat-intelligence-pager
pip install -r requirements.txt
```

## Usage
**Note**: Der Threshold für Benachrichtigungen wird über die Variable MIN_RISK_STARS definiert. Standardmäßig (Level 3) werden nur relevante Bedrohungen gepusht.

Konfiguration initialisieren:
```bash
cp .env.example .env
# Füge GEMINI_API_KEY und NTFY_TOPIC ein
```
**Manuelle Ausführung (CLI):**
```bash
python3 main.py
```
**Automatisierter Betrieb (GitHub Actions):**
Repository pushen und GEMINI_API_KEY sowie NTFY_TOPIC in den GitHub Repository Secrets hinterlegen. Der Workflow läuft standardmäßig alle 4 Stunden an und persistiert den State (Cache) nach jedem Run automatisch via Git-Commit.
