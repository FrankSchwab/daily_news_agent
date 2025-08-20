#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Daily News Agent – DACH & MENA (Banking, Finance, Crypto)
- RSS + Google News RSS (inkl. site:-Filter für Regulatoren & Zentralbanken)
- Keyword-Scoring, Region-Boost, Source-Boost
- Markdown & CSV Output, SMTP-Mail mit CSV-Anhang

ENV / .env:
SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, MAIL_TO, [optional MAIL_FROM, TOP_N, HOURS_BACK]
"""

import os
import re
import csv
import ssl
import sys
import time
import html
import smtplib
import hashlib
import tldextract
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

import feedparser
from dateutil import parser as dtparser
import pytz
from dotenv import load_dotenv

# .env laden (falls vorhanden)
load_dotenv()

# ----------------------------
# Konfiguration
# ----------------------------

BERLIN_TZ = pytz.timezone("Europe/Berlin")

KEYWORDS = {
    # Banking / Finance / Regulation (DE/EN)
    r"\b(Bank(en)?|Banking|Kreditinstitut|Sparkasse|Genossenschaftsbank|Zins(en)?|Einlagen|Kredite|Factoring|Leasing|Zahlungsverkehr|Payment|SEPA|ISO\s*20022|Basel\s*III|Basel\s*IV|MiCA|PSD2|PSD3|Open\s*Banking|Core\s*Banking|FlexCube|Temenos|Avaloq|Aufsicht|Regulierung|BaFin|FINMA|EZB|SNB|OeNB|Bundesbank|ECB|BIS)\b": 3.1,
    # Fintech / Tech
    r"\b(Fintech|FinTech|RegTech|WealthTech|InsurTech|API|Embedded\s*Finance|Bank-as-a-Service|BaaS|Cloud|Kubernetes|Core\s*Upgrade)\b": 2.2,
    # Crypto / Web3
    r"\b(Krypto(w(ährung|aehrung))?|Crypto|Bitcoin|BTC|Ethereum|ETH|Stablecoin(s)?|Tokenisierung|Tokenization|DeFi|Web3|Blockchain|CBDC|Digital(er|e)\s*(Euro|Dirham|Riyal)|Wallet|Custody|MiCA)\b": 3.3,
    # Payments / Fraud / AML
    r"\b(SWIFT|Instant\s*Payments|RT1|TIPS|Apple\s*Pay|Google\s*Pay|Betrug|Fraud|AML|KYC|Sanktions|Sanctions|Screening)\b": 2.0,
    # GCC entities
    r"\b(SAMA|CBUAE|QCB|CBE|CMA|DFSA|ADGM|FSRA|VARA)\b": 2.2,
    # Arabic basics
    r"\b(بنك|تمويل|فينتك|تشفير|بلوكتشين|مدفوعات|مصرف|عملة\s*رقمية)\b": 2.6,
}

NEGATIVE_FILTERS = [
    r"\b(Sport|Fußball|Football|Entertainment|Celebrity|Promi|Horoskop)\b",
    r"\b(Recipe|Kochen|Rezepte)\b",
]

DACH_TLDS = {"de", "at", "ch", "li"}
MENA_TLDS = {"ae","sa","qa","bh","om","kw","eg","jo","lb","ma","tn","dz","ir","iq","ye","ly","ps","sd"}

# Feste RSS-Quellen (stabil)
STATIC_FEEDS = [
    # DACH – Wirtschaft/Finanzen
    {"region": "DACH", "name": "Handelsblatt", "url": "https://www.handelsblatt.com/contentexport/feed/rss"},
    {"region": "DACH", "name": "WirtschaftsWoche", "url": "https://www.wiwo.de/contentexport/feed/rss/schlagzeilen"},
    {"region": "DACH", "name": "FAZ Finanzen", "url": "https://www.faz.net/rss/aktuell/finanzen/"},
    {"region": "DACH", "name": "ARD Börse", "url": "https://www.tagesschau.de/wirtschaft/boerse/index~rss2.xml"},
    {"region": "DACH", "name": "NZZ Wirtschaft", "url": "https://www.nzz.ch/wirtschaft.rss"},
    {"region": "DACH", "name": "Der Standard Wirtschaft", "url": "https://www.derstandard.at/rss/wirtschaft"},
    {"region": "DACH", "name": "Manager Magazin", "url": "https://www.manager-magazin.de/finanzen/index.rss"},
    {"region": "DACH", "name": "SwissInfo Business", "url": "https://www.swissinfo.ch/eng/business/rss"},
    # Global Crypto
    {"region": "GLOBAL", "name": "CoinDesk", "url": "https://www.coindesk.com/arc/outboundfeeds/rss/"},
    {"region": "GLOBAL", "name": "CoinTelegraph", "url": "https://cointelegraph.com/rss"},
    {"region": "GLOBAL", "name": "Bitcoin Magazine", "url": "https://bitcoinmagazine.com/.rss/full/"},
]

# Google News RSS – breit + Regulatoren/Zentralbanken (DACH & MENA) via site: Filter
GOOGLE_NEWS_QUERIES = [
    # DACH allgemein (de)
    {"region": "DACH","name":"Google News DACH (de)",
     "q":"Bank OR Fintech OR Zahlungsverkehr OR Krypto OR Blockchain OR Bitcoin OR Ethereum OR CBDC OR Regulator OR BaFin OR FINMA",
     "hl":"de","gl":"DE","ceid":"DE:de"},

    # Regulatoren/Zentralbanken DACH (de/en)
    {"region":"DACH","name":"DACH Regulators (de)",
     "q":"site:bafin.de OR site:finma.ch OR site:bundesbank.de OR site:snb.ch OR site:oenb.at OR site:ecb.europa.eu",
     "hl":"de","gl":"DE","ceid":"DE:de"},
    {"region":"DACH","name":"DACH Regulators (en)",
     "q":"site:finma.ch OR site:bundesbank.de OR site:snb.ch OR site:oenb.at OR site:ecb.europa.eu",
     "hl":"en","gl":"DE","ceid":"DE:en"},

    # MENA allgemein (en)
    {"region":"MENA","name":"Google News MENA (en)",
     "q":"bank OR fintech OR crypto OR blockchain OR CBDC OR payments OR regulator OR central bank (site:ae OR site:sa OR site:eg OR site:bh OR site:om OR site:qa OR site:kw)",
     "hl":"en","gl":"AE","ceid":"AE:en"},

    # MENA arabisch
    {"region":"MENA","name":"Google News MENA (ar)",
     "q":"بنك OR تمويل OR فينتك OR تشفير OR بلوكتشين OR المدفوعات OR عملة رقمية",
     "hl":"ar","gl":"SA","ceid":"SA:ar"},

    # GCC Regulatoren & Free Zones (en)
    {"region":"MENA","name":"GCC Regulators (en)",
     "q":"site:sama.gov.sa OR site:cbuae.gov.ae OR site:qcb.gov.qa OR site:cbe.org.eg OR site:cma.org.sa OR site:dfsa.ae OR site:adgm.com OR site:vara.ae",
     "hl":"en","gl":"AE","ceid":"AE:en"},
]

BASE_SOURCE_WEIGHTS = {
    "handelsblatt": 1.15,
    "wiwo": 1.1,
    "faz": 1.05,
    "nzz": 1.1,
    "coindesk": 1.05,
    "cointelegraph": 1.0,
    "zawya": 1.05,
    "thenationalnews": 1.0,
    "gulfnews": 1.0,
    "arabnews": 0.95,
    # Regulatoren/ZBs (leichter Boost)
    "bafin.de": 1.12,
    "finma.ch": 1.12,
    "bundesbank.de": 1.12,
    "snb.ch": 1.1,
    "oenb.at": 1.1,
    "ecb.europa.eu": 1.12,
    "bis.org": 1.08,
    "imf.org": 1.05,
    "sama.gov.sa": 1.1,
    "cbuae.gov.ae": 1.1,
    "qcb.gov.qa": 1.08,
    "cbe.org.eg": 1.05,
    "cma.org.sa": 1.05,
    "dfsa.ae": 1.08,
    "adgm.com": 1.06,
    "vara.ae": 1.06,
}

REGION_BOOST = {"DACH": 1.15, "MENA": 1.15, "GLOBAL": 1.00}

HOURS_BACK = int(os.getenv("HOURS_BACK", "48"))
TOP_N = int(os.getenv("TOP_N", "18"))

# ----------------------------
# Utilities
# ----------------------------

def now_berlin():
    return datetime.now(BERLIN_TZ)

def to_berlin(dt):
    if dt.tzinfo is None:
        return BERLIN_TZ.localize(dt)
    return dt.astimezone(BERLIN_TZ)

def guess_region_from_url(url: str) -> str:
    ext = tldextract.extract(url)
    tld = ext.suffix.split(".")[-1] if ext.suffix else ""
    if tld in DACH_TLDS:
        return "DACH"
    if tld in MENA_TLDS:
        return "MENA"
    return "GLOBAL"

def normalize_url(url: str) -> str:
    url = url.strip()
    url = re.sub(r"([?&])(utm_[^=]+=[^&]+)&?", r"\1", url)
    url = re.sub(r"[?&]$", "", url)
    return url

def text_score(text: str) -> float:
    if not text:
        return 0.0
    score = 0.0
    for pattern, weight in KEYWORDS.items():
        hits = re.findall(pattern, text, flags=re.IGNORECASE)
        if hits:
            score += weight * len(hits)
    for neg in NEGATIVE_FILTERS:
        if re.search(neg, text, flags=re.IGNORECASE):
            score -= 2.5
    n = len(text.split())
    if n < 8:
        score -= 0.8
    return score

def source_weight(url: str) -> float:
    host = tldextract.extract(url).registered_domain.lower()
    # exakte Domains zuerst prüfen
    for key, w in BASE_SOURCE_WEIGHTS.items():
        if key == host or key in host:
            return w
    return 1.0

def summarize(teaser: str, max_sent=2) -> str:
    if not teaser:
        return ""
    sents = re.split(r"(?<=[.!?])\s+", teaser.strip())
    return " ".join(sents[:max_sent]).strip()

def parse_date(entry) -> datetime:
    # try string dates
    for k in ("published", "updated", "created"):
        val = entry.get(k)
        if val:
            try:
                return to_berlin(dtparser.parse(val))
            except Exception:
                pass
    # try struct_time
    for k in ("published_parsed", "updated_parsed"):
        val = entry.get(k)
        if val:
            try:
                dt = datetime.fromtimestamp(time.mktime(val), tz=timezone.utc)
                return to_berlin(dt)
            except Exception:
                pass
    return now_berlin()

def build_google_news_url(q: str, hl: str, gl: str, ceid: str) -> str:
    from urllib.parse import quote_plus
    return f"https://news.google.com/rss/search?q={quote_plus(q)}&hl={hl}&gl={gl}&ceid={ceid}"

def load_all_feeds():
    feeds = list(STATIC_FEEDS)
    for q in GOOGLE_NEWS_QUERIES:
        feeds.append({
            "region": q["region"],
            "name": q["name"],
            "url": build_google_news_url(q["q"], q["hl"], q["gl"], q["ceid"])
        })
    return feeds

# ----------------------------
# Fetch & Rank
# ----------------------------

def fetch_entries(feeds):
    cutoff = now_berlin() - timedelta(hours=HOURS_BACK)
    seen = set()
    items = []
    for f in feeds:
        try:
            parsed = feedparser.parse(f["url"])
        except Exception as e:
            print(f"[WARN] Feed nicht lesbar: {f['name']} – {e}", file=sys.stderr)
            continue

        for e in parsed.entries:
            url = normalize_url(e.get("link", "") or "")
            if not url:
                continue

            uid = hashlib.sha1(url.encode("utf-8")).hexdigest()
            if uid in seen:
                continue
            seen.add(uid)

            title = html.unescape(e.get("title", "")).strip()
            summary = html.unescape(e.get("summary", "")).strip()
            published = parse_date(e)
            if published < cutoff:
                continue

            region = f["region"]
            if region == "GLOBAL" or "Google News" in f["name"] or "Regulators" in f["name"]:
                region = guess_region_from_url(url)

            s_text = " ".join([title, summary, f["name"]])
            s = text_score(s_text)
            s *= source_weight(url)
            s *= REGION_BOOST.get(region, 1.0)

            items.append({
                "title": title,
                "summary": summarize(summary),
                "url": url,
                "source": f["name"],
                "host": tldextract.extract(url).registered_domain,
                "region": region,
                "score": round(s, 3),
                "published": published,
            })
    return items

def pick_top(items, top_n=TOP_N):
    by_region = {}
    for it in items:
        by_region.setdefault(it["region"], []).append(it)
    picked = []
    for region, lst in by_region.items():
        lst.sort(key=lambda x: (x["score"], x["published"]), reverse=True)
        picked.extend(lst[:top_n])
    picked.sort(key=lambda x: (x["region"], x["score"], x["published"]), reverse=True)
    return picked

# ----------------------------
# Output
# ----------------------------

def ensure_out_dir():
    out_dir = os.path.join(".", "out")
    os.makedirs(out_dir, exist_ok=True)
    return out_dir

def write_csv(items, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["region", "published", "score", "title", "source", "host", "url", "summary"])
        for it in items:
            w.writerow([
                it["region"],
                it["published"].strftime("%Y-%m-%d %H:%M %Z"),
                it["score"],
                it["title"],
                it["source"],
                it["host"],
                it["url"],
                it["summary"],
            ])

def write_md(items, path, run_dt):
    regions = ["DACH", "MENA", "GLOBAL"]
    grouped = {r: [] for r in regions}
    for it in items:
        grouped.setdefault(it["region"], []).append(it)

    lines = []
    lines.append(f"# Daily Digest – Banking, Finance & Crypto (DACH & MENA)\n")
    lines.append(f"_Stand: {run_dt.strftime('%Y-%m-%d %H:%M %Z')}_\n")
    for r in regions:
        if not grouped.get(r):
            continue
        lines.append(f"\n## {r}\n")
        for it in sorted(grouped[r], key=lambda x: (x["score"], x["published"]), reverse=True):
            dt_str = it["published"].strftime("%Y-%m-%d %H:%M %Z")
            lines.append(
                f"- **[{it['title']}]({it['url']})**  \n"
                f"  {it['summary']}  \n"
                f"  _{it['source']} · {it['host']} · {dt_str} · Score {it['score']}_"
            )
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

# ----------------------------
# Mail
# ----------------------------

def send_email(subject: str, html_body: str, text_body: str, attachments: list):
    host = os.getenv("SMTP_HOST")
    port = int(os.getenv("SMTP_PORT", "587"))
    user = os.getenv("SMTP_USER")
    pwd  = os.getenv("SMTP_PASS")
    to   = os.getenv("MAIL_TO")
    mail_from = os.getenv("MAIL_FROM", user)

    if not all([host, port, user, pwd, to]):
        print("[WARN] E-Mail nicht gesendet – SMTP/Empfänger-ENV Variablen fehlen.", file=sys.stderr)
        return

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = mail_from
    msg["To"] = to

    part1 = MIMEText(text_body, "plain", "utf-8")
    part2 = MIMEText(html_body, "html", "utf-8")
    msg.attach(part1)
    msg.attach(part2)

    for att_path, mime_type in attachments or []:
        try:
            with open(att_path, "rb") as f:
                data = f.read()
            maintype, subtype = mime_type.split("/", 1)
            from email.mime.base import MIMEBase
            from email import encoders
            part = MIMEBase(maintype, subtype)
            part.set_payload(data)
            encoders.encode_base64(part)
            part.add_header("Content-Disposition", f'attachment; filename="{os.path.basename(att_path)}"')
            msg.attach(part)
        except Exception as e:
            print(f"[WARN] Anhang konnte nicht hinzugefügt werden: {att_path} – {e}", file=sys.stderr)

    context = ssl.create_default_context()
    with smtplib.SMTP(host, port) as server:
        server.starttls(context=context)
        server.login(user, pwd)
        server.sendmail(mail_from, [to], msg.as_string())

def html_table(items):
    rows = []
    rows.append('<table border="0" cellpadding="6" cellspacing="0">')
    rows.append("<thead><tr><th align='left'>Region</th><th align='left'>Zeit</th><th align='left'>Titel</th><th align='left'>Quelle</th><th align='left'>Score</th></tr></thead><tbody>")
    for it in items:
        dt_str = it["published"].strftime("%Y-%m-%d %H:%M %Z")
        title = html.escape(it["title"])
        source = html.escape(f"{it['source']} / {it['host']}")
        rows.append(
            f"<tr>"
            f"<td>{it['region']}</td>"
            f"<td>{dt_str}</td>"
            f"<td><a href='{html.escape(it['url'])}'>{title}</a><br><small>{html.escape(it['summary'])}</small></td>"
            f"<td>{source}</td>"
            f"<td>{it['score']}</td>"
            f"</tr>"
        )
    rows.append("</tbody></table>")
    return "\n".join(rows)

# ----------------------------
# Main
# ----------------------------

def main():
    run_dt = now_berlin()
    feeds = load_all_feeds()
    items = fetch_entries(feeds)
    if not items:
        print("Keine Items gefunden.")
        return

    picked = pick_top(items, top_n=TOP_N)
    out_dir = ensure_out_dir()
    date_tag = run_dt.strftime("%Y-%m-%d")
    csv_path = os.path.join(out_dir, f"digest_{date_tag}.csv")
    md_path  = os.path.join(out_dir, f"digest_{date_tag}.md")

    write_csv(picked, csv_path)
    write_md(picked, md_path, run_dt)

    subject = f"Daily Digest – Banking/Finance/Crypto (DACH & MENA) – {run_dt.strftime('%Y-%m-%d')}"
    html_body = f"<p>Hallo,</p><p>hier ist dein täglicher Digest (DACH &amp; MENA).</p>{html_table(picked)}<p>Viele Grüße</p>"
    text_body = "Täglicher Digest im Anhang (CSV) bzw. als Markdown in ./out/.\n"

    send_email(subject, html_body, text_body, attachments=[(csv_path, "text/csv")])

    print(f"Fertig. {len(picked)} Artikel geschrieben nach:\n- {md_path}\n- {csv_path}")

if __name__ == "__main__":
    main()
