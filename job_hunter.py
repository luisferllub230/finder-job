#!/usr/bin/env python3
"""
job_hunter.py — Busca empleos remotos de software a diario en varias fuentes
públicas, filtra por perfil/salario/ubicación, puntúa y genera un reporte HTML
solo con las vacantes NUEVAS. Opcionalmente lo envía por email.

Sin dependencias externas (solo librería estándar de Python 3.8+).

Uso:
    python3 job_hunter.py              # corre normal
    python3 job_hunter.py --all        # incluye vacantes ya vistas en el reporte
    python3 job_hunter.py --no-email   # no envía email aunque esté configurado
"""
import html
import json
import os
import re
import smtplib
import sqlite3
import sys
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

BASE = Path(__file__).resolve().parent
CFG = json.loads((BASE / "config.json").read_text(encoding="utf-8"))
UA = "Mozilla/5.0 (job_hunter personal script)"


# ----------------------------------------------------------------- utilidades
def fetch(url, as_json=True):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    with urllib.request.urlopen(req, timeout=40) as r:
        raw = r.read().decode("utf-8", errors="replace")
    return json.loads(raw) if as_json else raw


def fix_mojibake(text):
    """Repara UTF-8 doble-codificado (p. ej. 'Ø§Ù' de RemoteOK)."""
    if re.search(r"[ÃØÙÂ][\x80-\xbf]", text):
        try:
            return text.encode("latin-1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass
    return text


def clean(text):
    text = fix_mojibake(re.sub(r"<[^>]+>", " ", str(text or "")))
    return re.sub(r"\s+", " ", html.unescape(text)).strip()


def has_word(text, word):
    return re.search(r"(?<![a-z0-9])" + re.escape(word.lower()) + r"(?![a-z0-9])", text) is not None


def parse_salary(text, strict=False):
    """Devuelve salario ANUAL mínimo aproximado en USD a partir de texto.

    strict=True (texto libre, p. ej. HN): solo cuenta montos con '$' delante,
    para no confundir "team of 1500" o "24 hours" con un salario.
    """
    if not text:
        return None
    t = str(text).lower().replace(",", "")
    pattern = r"\$\s*(\d+(?:\.\d+)?)\s*([km])?" if strict else r"(\d+(?:\.\d+)?)\s*([km])?"
    vals = []
    for m in re.finditer(pattern, t):
        if m.group(2) == "m":  # "$5M seed round"
            continue
        n = float(m.group(1)) * (1000 if m.group(2) == "k" else 1)
        if n < 5:
            continue
        unit = t[m.end():m.end() + 20]
        if re.search(r"/\s*h|hour|hora", unit):
            n *= 2080
        elif re.search(r"/\s*mo|month|mes", unit):
            n *= 12
        elif not strict and re.search(r"hour|/hr|hora", t):
            n *= 2080
        elif not strict and re.search(r"month|/mo|mes", t):
            n *= 12
        vals.append(n)
    vals = [v for v in vals if v >= 1000]
    return min(vals) if vals else None


def job(source, jid, title, company, url, location="", salary_min=None,
        salary_text="", tags=None, description="", date=""):
    return {
        "id": f"{source}:{jid}", "source": source, "title": clean(title),
        "company": clean(company), "url": url, "location": clean(location),
        "salary_min": salary_min, "salary_text": clean(salary_text),
        "tags": [str(t).lower() for t in (tags or [])],
        "description": clean(description)[:6000], "date": str(date)[:10],
    }


# -------------------------------------------------------------------- fuentes
def src_remotive():
    out = []
    data = fetch("https://remotive.com/api/remote-jobs?category=software-dev")
    for j in data.get("jobs", []):
        sal = j.get("salary") or ""
        out.append(job("remotive", j.get("id"), j.get("title"), j.get("company_name"),
                       j.get("url"), j.get("candidate_required_location"),
                       parse_salary(sal), sal, j.get("tags"), j.get("description"),
                       j.get("publication_date")))
    return out


def src_remoteok():
    out = []
    for j in fetch("https://remoteok.com/api"):
        if not isinstance(j, dict) or "position" not in j:
            continue
        smin = j.get("salary_min") or None
        stxt = f"${smin:,}–${j.get('salary_max', 0):,}/yr" if smin else ""
        out.append(job("remoteok", j.get("id"), j.get("position"), j.get("company"),
                       j.get("apply_url") or j.get("url"), j.get("location"),
                       smin, stxt, j.get("tags"), j.get("description"), j.get("date")))
    return out


def src_himalayas():
    out = []
    for offset in (0, 100, 200):
        data = fetch(f"https://himalayas.app/jobs/api?limit=100&offset={offset}")
        for j in data.get("jobs", []):
            locs = j.get("locationRestrictions") or []
            loc = ", ".join(l if isinstance(l, str) else l.get("name", "") for l in locs) or "Worldwide"
            smin = j.get("minSalary")
            stxt = f"{j.get('currency', 'USD')} {smin:,}–{j.get('maxSalary') or 0:,}/yr" if smin else ""
            out.append(job("himalayas", j.get("guid") or j.get("applicationLink"),
                           j.get("title"), j.get("companyName"),
                           j.get("applicationLink") or j.get("guid"), loc, smin, stxt,
                           j.get("categories"), j.get("description") or j.get("excerpt"),
                           j.get("pubDate")))
    return out


def src_jobicy():
    out = []
    data = fetch("https://jobicy.com/api/v2/remote-jobs?count=100&industry=dev")
    for j in data.get("jobs", []):
        smin = j.get("annualSalaryMin")
        stxt = f"{j.get('salaryCurrency', 'USD')} {smin}–{j.get('annualSalaryMax')}/yr" if smin else ""
        out.append(job("jobicy", j.get("id"), j.get("jobTitle"), j.get("companyName"),
                       j.get("url"), j.get("jobGeo"), float(smin) if smin else None, stxt,
                       j.get("jobIndustry"), j.get("jobDescription") or j.get("jobExcerpt"),
                       j.get("pubDate")))
    return out


def src_arbeitnow():
    out = []
    for page in (1, 2, 3):
        data = fetch(f"https://www.arbeitnow.com/api/job-board-api?page={page}")
        for j in data.get("data", []):
            if not j.get("remote"):
                continue
            out.append(job("arbeitnow", j.get("slug"), j.get("title"), j.get("company_name"),
                           j.get("url"), j.get("location"), None, "", j.get("tags"),
                           j.get("description"), datetime.fromtimestamp(j.get("created_at", 0)).date()))
    return out


def src_weworkremotely():
    out = []
    feeds = ["remote-back-end-programming-jobs", "remote-full-stack-programming-jobs",
             "remote-programming-jobs"]
    for f in feeds:
        root = ET.fromstring(fetch(f"https://weworkremotely.com/categories/{f}.rss", as_json=False))
        for it in root.iter("item"):
            title = it.findtext("title", "")
            company, _, role = title.partition(":")
            out.append(job("weworkremotely", it.findtext("guid") or it.findtext("link"),
                           role or title, company, it.findtext("link"),
                           it.findtext("region", ""), None, "", [],
                           it.findtext("description"), it.findtext("pubDate")))
    return out


def src_hn_whoshiring():
    """Último hilo 'Ask HN: Who is hiring?' — filtrado por REMOTE."""
    out = []
    q = urllib.parse.quote('"Ask HN: Who is hiring"')
    hits = fetch(f"https://hn.algolia.com/api/v1/search_by_date?query={q}&tags=story,author_whoishiring")["hits"]
    if not hits:
        return out
    story = fetch(f"https://hn.algolia.com/api/v1/items/{hits[0]['objectID']}")
    for c in story.get("children", []):
        text = clean(c.get("text"))
        if "remote" not in text.lower():
            continue
        first = text.split("|")
        company = first[0][:80] if first else "HN"
        out.append(job("hn", c.get("id"), " | ".join(x.strip() for x in first[1:3]) or text[:90],
                       company, f"https://news.ycombinator.com/item?id={c.get('id')}",
                       text[:300], parse_salary(text[:600], strict=True), "", [], text, c.get("created_at")))
    return out


SOURCES = [src_remotive, src_remoteok, src_himalayas, src_jobicy, src_arbeitnow,
           src_weworkremotely, src_hn_whoshiring]


# ------------------------------------------------------------ filtro y score
def evaluate(j):
    """Devuelve (score, flags) o None si se descarta."""
    title = j["title"].lower()
    blob = " ".join([title, " ".join(j["tags"]), j["description"].lower()])
    loc = j["location"].lower()
    flags = []

    if any(has_word(title, x) for x in CFG["exclude_title"]):
        return None
    # El rol se decide por título/tags; la descripción menciona "python" o "ERP" en cualquier cosa
    head = " ".join([title, " ".join(j["tags"])])
    if not any(has_word(head, k) for k in CFG["require_any"]):
        return None

    # Ubicación: primero lo explícitamente abierto, luego lo bloqueado
    if not loc:
        flags.append("ubicación no especificada")
    elif any(has_word(loc, a) for a in CFG["location_ok"]):
        pass
    elif any(has_word(loc, b) for b in CFG["location_blocked"]):
        return None
    elif CFG.get("strict_location") and j["source"] != "hn" and loc not in CFG.get("location_generic", []):
        return None  # ciudad/país concreto (Cincinnati, Brazil, Sweden...)
    else:
        flags.append(f"verificar ubicación: {j['location'][:60]}")

    # Salario
    if j["salary_min"] is None and j["salary_text"]:
        j["salary_min"] = parse_salary(j["salary_text"])
    if j["salary_min"] is not None:
        if float(j["salary_min"]) < CFG["min_annual_usd"]:
            return None
    else:
        flags.append("salario no indicado")

    # Años de experiencia exigidos
    yrs = [int(y) for y in re.findall(r"(\d{1,2})\+?\s*(?:years|yrs)", blob)]
    if yrs and max(yrs) > CFG["max_years_required"]:
        flags.append(f"pide {max(yrs)}+ años")

    score = 0
    for k, w in CFG["keywords"].items():
        if has_word(blob, k):
            score += w
        if has_word(title, k):
            score += w  # en el título pesa doble
    if yrs and max(yrs) > CFG["max_years_required"]:
        score -= 4
    if score < CFG["min_score"]:
        return None
    return score, flags


# ------------------------------------------------------------------- reporte
def pitch_for(j):
    return CFG["pitch"].format(company=j["company"] or "team", title=j["title"])


def build_report(rows, errors):
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    cards = []
    for j, score, flags in rows:
        fl = "".join(f'<span class="flag">{html.escape(f)}</span>' for f in flags)
        sal = html.escape(j["salary_text"]) or "—"
        cards.append(f"""
<div class="card">
  <div class="top"><span class="score">{score}</span>
    <a href="{html.escape(j['url'] or '#')}" target="_blank"><b>{html.escape(j['title'])}</b></a></div>
  <div class="meta">{html.escape(j['company'])} · {html.escape(j['location'] or 'n/a')} · {sal} · {j['source']} · {j['date']}</div>
  <div>{fl}</div>
  <details><summary>Mensaje sugerido</summary><pre>{html.escape(pitch_for(j))}</pre></details>
</div>""")
    err = "".join(f"<li>{html.escape(e)}</li>" for e in errors)
    return f"""<!doctype html><html><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Empleos remotos {now}</title>
<style>
body{{font-family:system-ui,sans-serif;max-width:900px;margin:24px auto;padding:0 16px;background:#f6f7f9;color:#1d2330}}
.card{{background:#fff;border:1px solid #e3e6ec;border-radius:10px;padding:12px 14px;margin:10px 0}}
.top{{display:flex;gap:10px;align-items:center}} a{{color:#1f5fbf;text-decoration:none}}
.score{{background:#1d2330;color:#fff;border-radius:6px;padding:2px 8px;font-size:13px}}
.meta{{color:#5b6475;font-size:13px;margin:4px 0}}
.flag{{display:inline-block;background:#fff4dd;color:#8a5a00;border-radius:4px;padding:1px 6px;font-size:12px;margin:2px 4px 2px 0}}
pre{{white-space:pre-wrap;background:#f1f3f6;padding:10px;border-radius:6px;font-size:13px}}
</style></head><body>
<h2>Empleos remotos nuevos — {now}</h2>
<p>{len(rows)} vacantes nuevas, ordenadas por afinidad con tu perfil.</p>
{''.join(cards) or '<p>No hubo vacantes nuevas hoy.</p>'}
{f'<h4>Fuentes con error</h4><ul>{err}</ul>' if err else ''}
</body></html>"""


def build_email(rows, errors):
    """Versión para Gmail: estilos inline (Gmail ignora <style> y <details>)."""
    td = "padding:10px 12px;border-bottom:1px solid #e3e6ec;vertical-align:top"
    trs = []
    for j, score, flags in rows:
        fl = " · ".join(html.escape(f) for f in flags)
        trs.append(f"""<tr>
<td style="{td};width:34px"><span style="background:#1d2330;color:#fff;border-radius:6px;padding:2px 7px;font-size:13px">{score}</span></td>
<td style="{td}"><a href="{html.escape(j['url'] or '#')}" style="color:#1f5fbf;font-weight:bold;text-decoration:none">{html.escape(j['title'])}</a><br>
<span style="color:#5b6475;font-size:13px">{html.escape(j['company'])} · {html.escape(j['location'][:60] or 'n/a')} · {html.escape(j['salary_text']) or 'salario n/d'} · {j['source']}</span>
{f'<br><span style="color:#8a5a00;font-size:12px">⚠ {fl}</span>' if fl else ''}</td></tr>""")
    err = "".join(f"<li>{html.escape(e)}</li>" for e in errors)
    return f"""<div style="font-family:Arial,sans-serif;max-width:720px;color:#1d2330">
<h2 style="margin:0 0 6px">{len(rows)} empleos remotos nuevos</h2>
<p style="color:#5b6475;margin:0 0 12px">Ordenados por afinidad. El reporte adjunto trae el mensaje de postulación sugerido para cada vacante.</p>
<table style="border-collapse:collapse;width:100%">{''.join(trs)}</table>
{f'<p style="color:#a33;font-size:12px">Fuentes con error:</p><ul style="color:#a33;font-size:12px">{err}</ul>' if err else ''}
</div>"""


def send_email(subject, body_html, attachment=None):
    host, user, pwd = (os.getenv(k) for k in ("SMTP_HOST", "SMTP_USER", "SMTP_PASS"))
    to = os.getenv("REPORT_TO") or user
    if not (host and user and pwd):
        return False
    msg = MIMEMultipart("mixed")
    msg["Subject"], msg["From"], msg["To"] = subject, user, to
    msg.attach(MIMEText(body_html, "html", "utf-8"))
    if attachment:
        part = MIMEText(attachment.read_text(encoding="utf-8"), "html", "utf-8")
        part["Content-Disposition"] = f'attachment; filename="{attachment.name}"'
        msg.attach(part)
    with smtplib.SMTP(host, int(os.getenv("SMTP_PORT", "587")), timeout=60) as s:
        s.starttls()
        s.login(user, pwd)
        s.sendmail(user, [to], msg.as_string())
    return True


# ---------------------------------------------------------------------- main
def main():
    show_all = "--all" in sys.argv
    db = sqlite3.connect(BASE / "jobs.db")
    db.execute("""CREATE TABLE IF NOT EXISTS jobs(id TEXT PRIMARY KEY, first_seen TEXT,
                  title TEXT, company TEXT, url TEXT, score INT, status TEXT DEFAULT 'new')""")

    jobs, errors = [], []
    for src in SOURCES:
        try:
            got = src()
            jobs += got
            print(f"[ok] {src.__name__}: {len(got)}")
        except Exception as e:  # una fuente caída no detiene las demás
            errors.append(f"{src.__name__}: {e}")
            print(f"[error] {src.__name__}: {e}")

    seen_urls, rows = set(), []
    for j in jobs:
        key = (j["title"].lower(), j["company"].lower())
        if key in seen_urls:
            continue
        seen_urls.add(key)
        res = evaluate(j)
        if not res:
            continue
        is_new = db.execute("SELECT 1 FROM jobs WHERE id=?", (j["id"],)).fetchone() is None
        if is_new:
            db.execute("INSERT INTO jobs(id,first_seen,title,company,url,score) VALUES(?,?,?,?,?,?)",
                       (j["id"], datetime.now().isoformat(), j["title"], j["company"], j["url"], res[0]))
        if is_new or show_all:
            rows.append((j, res[0], res[1]))
    db.commit()

    rows.sort(key=lambda r: -r[1])
    rows = rows[: CFG["max_results"]]
    report = build_report(rows, errors)
    out_dir = BASE / "reports"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / f"jobs_{datetime.now():%Y-%m-%d}.html"
    path.write_text(report, encoding="utf-8")
    print(f"{len(rows)} vacantes nuevas → {path}")

    failed = len(errors) == len(SOURCES)
    if rows and "--no-email" not in sys.argv:
        try:
            if send_email(f"{len(rows)} empleos remotos nuevos — {datetime.now():%d/%m}",
                          build_email(rows, errors), path):
                print("Reporte enviado por email.")
            else:
                print("[aviso] email no configurado (faltan SMTP_HOST/SMTP_USER/SMTP_PASS)")
        except Exception as e:
            print(f"[error] email: {e}")
            failed = True
    if failed:  # exit != 0 → GitHub Actions avisa del fallo por correo
        sys.exit(1)


if __name__ == "__main__":
    main()
