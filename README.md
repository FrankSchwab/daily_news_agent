# Daily News Agent – DACH & MENA (Banking, Finance & Crypto)

Sammelt täglich relevante Artikel zu Banken, Finanzen und Krypto aus DACH & MENA, scored sie, erstellt einen Markdown- und CSV-Digest und verschickt die CSV per E-Mail. Läuft lokal oder automatisiert via GitHub Actions.

## Highlights
- **Quellen**: etablierte Finanz-/Wirtschaftsmedien + **Regulatoren & Zentralbanken** via Google News RSS (`site:`-Filter).
- **Regionen**: DACH & MENA (automatische Heuristik via TLD).
- **Scoring**: gewichtete Keywords (DE/EN/AR) + Quell- und Regions-Boost.
- **Output**: `out/digest_YYYY-MM-DD.md` & `out/digest_YYYY-MM-DD.csv`.
- **Mail**: Versand via SMTP (z. B. Gmail App-Passwort).

---

## Schnellstart (GitHub Actions)
1. **Repo erstellen** und Dateien aus diesem Ordner pushen.
2. **Secrets setzen**:  
   `Settings → Secrets and variables → Actions → New repository secret`  
   Lege diese Secrets an:
   - `SMTP_HOST` = `smtp.gmail.com`
   - `SMTP_PORT` = `587`
   - `SMTP_USER` = **deine Gmail-Adresse**
   - `SMTP_PASS` = **Gmail App-Passwort** (nicht dein normales Passwort)
   - `MAIL_TO`    = **Empfängeradresse**, z. B. `Frank@FrankSchwab.de`
   - *(optional)* `MAIL_FROM` = Absenderanzeige (Fallback: `SMTP_USER`)
   - *(optional)* `TOP_N` (z. B. `18`)
   - *(optional)* `HOURS_BACK` (z. B. `48`)
3. **Workflow starten**:  
   Tab **Actions → Daily Digest with Email → Run workflow** (Branch `main` auswählen → Start).  
   Nach dem Lauf findest du:
   - eine E-Mail an `MAIL_TO` mit CSV-Anhang,
   - die Artefakte unter **Actions → Lauf → Artifacts → `digest`**.

> **Gmail App-Passwort**: Google-Konto → **Sicherheit** → **App-Passwörter** → App `Mail`, Gerät `Mac/Other` wählen → generiertes 16-stelliges Passwort als `SMTP_PASS` nutzen.

---

## Lokal ausführen
```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# .env anlegen (siehe .env.example) oder Umgebungsvariablen exportieren:
cp .env.example .env
# dann Werte in .env eintragen

python daily_news_agent.py
Outputs landen in ./out/.# daily_news_agent
