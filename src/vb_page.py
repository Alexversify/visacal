"""비자 문호 페이지.

docs/visa-bulletin/index.html                 최신 달 (한국어). 상단 메뉴 '비자 문호'
docs/visa-bulletin/<lang>/index.html          최신 달 (다른 언어)
docs/visa-bulletin/YYYY-MM/index.html         달별 한국어
docs/visa-bulletin/YYYY-MM/<lang>/index.html  달별 다른 언어 (en, zh, ja, vi, es)
docs/visa-bulletin/archive/[<lang>/]          전체 월별 정리 (2001년 12월부터), 연도별 장기 추이

표 숫자는 원문 데이터 그대로, 문구는 vb_i18n 고정 문구입니다.
시기마다 행(EB-5 등)과 열(중국 열 유무, 추가 국가 열)이 다르므로 그 달 데이터에 있는 것만 그립니다.
"""

from __future__ import annotations

import html
import json
import re
from pathlib import Path
from typing import Any

from src import site
from src import vb_i18n as I
from src.visa_bulletin import change_line, load_all

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "visa-bulletin"
INDEX = ROOT / "data" / "visa_bulletin" / "index.json"

CSS = """
.vb{margin-top:24px}
.vb .kicker{font-size:12.5px;color:var(--faint);margin-bottom:6px;font-variant-numeric:tabular-nums}
.vb h1{font-size:26px;line-height:1.3;letter-spacing:-.025em;margin:0 0 10px}
.vb .lede{font-size:15px;color:var(--muted);max-width:72ch;margin:0 0 6px}
.vb h2{font-size:17px;margin:34px 0 10px;letter-spacing:-.01em}
.vb h3{font-size:14px;margin:18px 0 6px;color:var(--muted)}
.langs{display:flex;flex-wrap:wrap;gap:6px;margin:14px 0 4px}
.langs a{font-size:13px;text-decoration:none;padding:4px 10px;border:1px solid var(--rule);border-radius:2px;background:var(--paper)}
.langs a[aria-current]{background:var(--ink);color:#fff;border-color:var(--ink)}
.sumbox{background:var(--paper);border:1px solid var(--rule);border-top:3px solid var(--ink);padding:16px 20px;margin:20px 0;max-width:80ch}
.sumbox b{display:block;font-size:16px;margin-bottom:6px}
.sumbox p{margin:0 0 8px;font-size:14.5px}
.sumbox ul{margin:6px 0 0;padding-left:20px;font-size:14px}
.sumbox li{margin-bottom:4px}
.sumbox .ai{font-size:12px;color:var(--faint);margin-top:8px}
.legend{font-size:12.5px;color:var(--faint);max-width:90ch;margin:10px 0 0;line-height:1.5}
.grp{margin-top:6px}
.grp h2{margin:22px 0 4px;font-size:16px}
.vb h3 .tag{font-style:normal;font-size:11px;font-weight:600;background:var(--ink);color:#fff;padding:2px 7px;border-radius:2px;margin-left:6px;vertical-align:1px}
.tw{overflow-x:auto;-webkit-overflow-scrolling:touch;margin:8px 0 6px;background:var(--paper);border:1px solid var(--rule)}
.vb table{width:100%;border-collapse:collapse;font-size:13px;min-width:600px;table-layout:auto}
.vb th{text-align:left;font-size:11.5px;color:var(--faint);font-weight:600;padding:6px 8px;border-bottom:1px solid var(--rule);white-space:nowrap}
.vb td{padding:4px 8px;border-bottom:1px solid var(--hair);font-variant-numeric:tabular-nums;white-space:nowrap;line-height:1.45}
.vb td.l{white-space:normal;min-width:170px;max-width:300px}
.vb td.l b{font-weight:650;margin-right:2px}
.vb td.l span{color:var(--muted);font-size:12px}
.vb h3{margin:12px 0 4px}
.vb td.k{font-weight:650}
.vb .up{color:var(--ok)} .vb .dn{color:var(--warn)}
.vb .ar{font-size:11px;margin-left:3px}
.vb .cur{font-weight:650}
.notes{font-size:13px;color:var(--muted);max-width:80ch;margin:6px 0 0}
.chg{font-size:14px;padding-left:20px;margin:6px 0 0}
.chg li{margin-bottom:3px;font-variant-numeric:tabular-nums}
.meta{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:10px;margin:18px 0}
.meta div{background:var(--paper);border:1px solid var(--rule);padding:12px 14px;font-size:13.5px}
.meta span{display:block;font-size:12px;color:var(--faint);margin-bottom:3px}
details.more{margin:6px 0 0;font-size:13.5px}
details.more summary{cursor:pointer;color:var(--muted)}
@media (max-width:640px){.vb td.l span{display:none}.vb td.l{min-width:0}.vb table{min-width:0}.vb td,.vb th{padding:4px 6px}}
.pager{display:flex;justify-content:space-between;margin:4px 0 10px;font-size:14px}
.pager a{text-decoration:none;font-weight:600}
.monthly .yr{margin-bottom:14px}
.monthly .yh{font-size:12.5px;font-weight:650;color:var(--muted);margin:10px 0 4px}
.monthly a.mo{display:grid;grid-template-columns:110px 1fr auto;gap:12px;align-items:baseline;padding:10px 12px;
  background:var(--paper);border:1px solid var(--rule);border-top:0;text-decoration:none;font-size:14px}
.monthly .yh + a.mo{border-top:1px solid var(--rule)}
.monthly a.mo[aria-current]{border-left:3px solid var(--ink)}
.monthly .mk{font-weight:650;font-variant-numeric:tabular-nums}
.monthly .mc{font-size:12.5px;color:var(--faint);white-space:nowrap}
@media (max-width:640px){.monthly a.mo{grid-template-columns:1fr}.monthly .mc{white-space:normal}}
.disc2{font-size:12.5px;color:var(--faint);margin-top:26px;max-width:80ch}
.empty{padding:40px 0;color:var(--muted)}
.yrs details{background:var(--paper);border:1px solid var(--rule);margin:0 0 8px}
.yrs summary{cursor:pointer;padding:10px 14px;font-weight:650;font-size:14.5px;display:flex;justify-content:space-between}
.yrs summary span{font-weight:400;color:var(--faint);font-size:12.5px}
.yrs details .monthly{padding:0 10px 10px}
.yrs details a.mo{border-left:0;border-right:0}
.missing{font-size:12.5px;color:var(--faint);margin-top:8px}
.vb td.na{color:var(--faint)}
.vb th.x{color:var(--muted)}
.fix{font-size:12px;color:var(--faint);margin:4px 0 0}
.toarch{display:inline-block;margin-top:10px;font-size:14px;font-weight:600}
"""

DEFAULT_ROWS = {"fam_final": I.FAMILY_ROWS, "fam_filing": I.FAMILY_ROWS,
                "emp_final": I.EMP_ROWS, "emp_filing": I.EMP_ROWS}


def _e(s: Any) -> str:
    return html.escape(str(s))


def _label(lang: str, key: str, rec: dict[str, Any]) -> str:
    if key in I.T[lang] or key in I.T["en"]:
        return I.t(lang, key)
    return (rec.get("labels") or {}).get(key, key)


def _cell(lang: str, v: Any, old: Any) -> str:
    if v is None:
        return f'<td class="na">{_e(I.t(lang, "dash"))}</td>'
    cls, arrow, title = "", "", ""
    if old is not None and old != v:
        title = f' title="{_e(old)} → {_e(v)}"'
        if v == "C" or (old not in ("C", "U") and v not in ("C", "U") and v > old) or old == "U":
            cls, arrow = "up", "▲"
        else:
            cls, arrow = "dn", "▼"
    cur = " cur" if v == "C" else ""
    a = f'<span class="ar">{arrow}</span>' if arrow else ""
    return f'<td class="{cls}{cur}"{title}>{_e(v)}{a}</td>'


def _rows(rec: dict[str, Any], chart: str) -> list[str]:
    have = rec["charts"].get(chart) or {}
    order = (rec.get("order") or {}).get(chart) or [r for r in DEFAULT_ROWS[chart] if r in have]
    return [r for r in order if r in have]


def _table(lang: str, rec: dict[str, Any], prev: dict[str, Any] | None, chart: str) -> str:
    if chart not in rec["charts"]:
        return ""
    ex = (rec.get("extra") or {}).get(chart) or {}
    xcols = ex.get("cols") or []
    pex = ((prev or {}).get("extra") or {}).get(chart) or {}
    # 이 달 표에 한 번도 값이 없는 표준 열(예: 2005년 전 중국 열)은 그리지 않습니다.
    rows = _rows(rec, chart)
    vals_by_row = {r: rec["charts"][chart][r] for r in rows}
    show = [i for i in range(5) if any((vals_by_row[r] or [None] * 5)[i] is not None for r in rows)]
    head = "".join(f"<th>{_e(I.t(lang, I.COLS[i]))}</th>" for i in show) + "".join(
        f'<th class="x">{_e(_label(lang, c, rec))}</th>' for c in xcols)
    body = ""
    pc = (prev or {}).get("charts", {}).get(chart, {})
    for r in rows:
        vals = vals_by_row[r]
        olds = pc.get(r) or [None] * 5
        name = _label(lang, r, rec)
        short = I.SHORT.get(r, "")
        rest = name[len(short):].strip() if short and name.startswith(short) else name
        xv = (ex.get("rows") or {}).get(r) or {}
        xo = (pex.get("rows") or {}).get(r) or {}
        body += (f'<tr><td class="l"><b>{_e(short)}</b> <span>{_e(rest)}</span></td>'
                 + "".join(_cell(lang, vals[i], olds[i]) for i in show)
                 + "".join(_cell(lang, xv.get(c), xo.get(c)) for c in xcols) + "</tr>")
    u = rec.get("uscis") or {}
    kind = "family" if chart.startswith("fam") else "employment"
    tag = ""
    if u.get(kind) and chart.endswith(u[kind]):
        tag = f' <em class="tag">{_e(I.t(lang, "uscis_tag"))}</em>'
    return (f'<h3 id="{chart}">{_e(I.t(lang, chart))}{tag}</h3>'
            f'<div class="tw"><table><thead><tr><th>{_e(I.t(lang, "cat"))}</th>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def _row_val(rec: dict[str, Any], row: str) -> Any:
    chart = "fam_final" if row.startswith("F") else "emp_final"
    rows = rec["charts"].get(chart) or {}
    keys = I.EB5_TREND if row == "EB5U" else [row]
    for k in keys:
        if k in rows:
            return rows[k][0]
    return None


def _trend_table(lang: str, seq: list[dict[str, Any]], head_fmt) -> str:
    head = "".join(f"<th>{_e(head_fmt(r))}</th>" for r in seq)
    body = ""
    for row in I.KEY_ROWS:
        cells, last = "", None
        for r in seq:
            v = _row_val(r, row)
            cells += _cell(lang, v, last)
            last = v if v is not None else last
        body += f'<tr><td class="k">{_e(I.SHORT[row])}</td>{cells}</tr>'
    return (f'<div class="tw"><table><thead><tr><th>{_e(I.t(lang, "cat"))}</th>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def _trend(lang: str, recs: list[dict[str, Any]], upto: str) -> str:
    seq = [r for r in recs if r["key"] <= upto][-8:]
    if len(seq) < 2:
        return ""
    return f'<h2>{_e(I.t(lang, "trend"))}</h2>' + _trend_table(lang, seq, lambda r: r["key"])


def _uscis(lang: str, rec: dict[str, Any]) -> str:
    u = rec.get("uscis") or {}
    old = (rec["year"], rec["month"]) < (2015, 10)

    def w(v: str | None) -> str:
        if old:
            return I.t(lang, "uscis_na")
        return I.t(lang, v) if v in ("final", "filing") else I.t(lang, "uscis_unknown")

    return (f'<div><span>{_e(I.t(lang, "uscis"))}</span>'
            f'{_e(I.t(lang, "uscis_fam"))}: {_e(w(u.get("family")))}<br>'
            f'{_e(I.t(lang, "uscis_emp"))}: {_e(w(u.get("employment")))}</div>')


def _href(prefix: str, key: str | None, lang: str) -> str:
    base = f"{prefix}visa-bulletin/" + (f"{key}/" if key else "")
    return base + ("" if lang == "ko" else f"{lang}/")


def _langs(target: str, lang: str, prefix: str) -> str:
    """target: 'YYYY-MM' 달, 'archive' 전체 정리."""
    out = []
    for lg in I.LANGS:
        href = _href(prefix, target, lg)
        cur = ' aria-current="page"' if lg == lang else ""
        out.append(f'<a href="{href}" hreflang="{I.HTML_LANG[lg]}"{cur}>{_e(I.NATIVE[lg])}</a>')
    return f'<nav class="langs" aria-label="{_e(I.t(lang, "lang"))}">{"".join(out)}</nav>'


def _alternates(domain: str, target: str) -> str:
    links = "".join(
        f'<link rel="alternate" hreflang="{I.HTML_LANG[lg]}" href="https://{domain}/visa-bulletin/{target}/'
        f'{"" if lg == "ko" else lg + "/"}">'
        for lg in I.LANGS
    )
    return links + f'<link rel="alternate" hreflang="x-default" href="https://{domain}/visa-bulletin/{target}/en/">'


def _changes_html(lang: str, rec: dict[str, Any]) -> str:
    ch = rec.get("changes") or []
    if not rec.get("prev_key"):
        return f'<p class="notes">{_e(I.t(lang, "changes_first"))}</p>'
    if not ch:
        return f'<p class="notes">{_e(I.t(lang, "changes_none"))}</p>'
    out = ""
    for label, suffix in (("final_chg", "final"), ("filing_chg", "filing")):
        items = [c for c in ch if c["chart"].endswith(suffix)]
        if not items:
            continue
        main = [c for c in items if c["col"] == "row"]
        rest = [c for c in items if c["col"] != "row"]
        out += f'<h3>{_e(I.t(lang, label))}</h3>'
        if main:
            out += '<ul class="chg">' + "".join(f"<li>{_e(change_line(lang, c))}</li>" for c in main) + "</ul>"
        if rest:
            out += (f'<details class="more"><summary>{_e(I.t(lang, "more_chg", n=len(rest)))}</summary><ul class="chg">'
                    + "".join(f"<li>{_e(change_line(lang, c))}</li>" for c in rest) + "</ul></details>")
    return out


def _fix(doc: str, prefix: str, lang: str) -> str:
    doc = re.sub(r'href="(?!https?:|mailto:|#|\.\./|/)([a-z\-]+\.html)"', rf'href="{prefix}\1"', doc)
    return doc.replace('<html lang="ko">', f'<html lang="{I.HTML_LANG[lang]}">', 1)


def _mo(lang: str, r: dict[str, Any], prefix: str, current: str = "") -> str:
    s = (r.get("summary") or {}).get(lang) or {}
    n = len([c for c in r.get("changes") or [] if c["chart"].endswith("final")])
    cnt = I.t(lang, "nchg", n=n) if n else (I.t(lang, "nchg0") if r.get("prev_key") else "")
    cur = ' aria-current="page"' if r["key"] == current else ""
    return (f'<a class="mo" href="{_href(prefix, r["key"], lang)}"{cur}>'
            f'<span class="mk">{_e(I.t(lang, "month", y=r["year"], m=r["month"]))}</span>'
            f'<span class="mh">{_e(s.get("headline") or I.t(lang, "title", y=r["year"], m=r["month"]))}</span>'
            f'<span class="mc">{_e(cnt)}</span></a>')


def _contact(cfg: dict[str, Any], lang: str, topic: str) -> str:
    if lang == "ko":
        return site.lead_form(cfg, topic)
    mail = _e((cfg.get("site") or {}).get("contact_email", ""))
    return f'<p class="notes">{_e(I.t(lang, "contact"))}: <a href="mailto:{mail}">{mail}</a></p>'


def _doc(cfg: dict[str, Any], lang: str, prefix: str, title: str, desc: str, canonical_path: str,
         alt_target: str, body: str) -> str:
    domain = (cfg.get("site") or {}).get("domain") or "visacal.com"
    canonical = f"https://{domain}/{canonical_path}"
    head = site.head(cfg, title, CSS, desc).replace(
        "</head>", f'<link rel="canonical" href="{canonical}">{_alternates(domain, alt_target)}</head>', 1)
    doc = head + site.header(cfg, "/visa-bulletin/") + body + site.footer(cfg)
    return _fix(doc, prefix, lang)


def _month_page(cfg: dict[str, Any], recs: list[dict[str, Any]], rec: dict[str, Any], lang: str,
                prefix: str, is_index: bool = False) -> str:
    y, m, key = rec["year"], rec["month"], rec["key"]
    prev = next((r for r in recs if r["key"] == rec.get("prev_key")), None)
    keys = [r["key"] for r in recs]
    i = keys.index(key)
    before = recs[i - 1] if i > 0 else None
    after = recs[i + 1] if i + 1 < len(recs) else None
    s = (rec.get("summary") or {}).get(lang) or {}
    pts = "".join(f"<li>{_e(p)}</li>" for p in s.get("points") or [])
    summ = (
        f'<div class="sumbox"><b>{_e(s.get("headline") or I.t(lang, "title", y=y, m=m))}</b>'
        + (f"<p>{_e(s['summary'])}</p>" if s.get("summary") else "")
        + (f"<ul>{pts}</ul>" if pts else "")
        + (f'<div class="ai">{_e(I.t(lang, "ai_note"))}</div>' if s.get("auto") else "")
        + "</div>"
    )
    final_tables = _table(lang, rec, prev, "fam_final") + _table(lang, rec, prev, "emp_final")
    if "fam_filing" in rec["charts"] or "emp_filing" in rec["charts"]:
        filing = _table(lang, rec, prev, "fam_filing") + _table(lang, rec, prev, "emp_filing")
    else:
        filing = f'<p class="notes">{_e(I.t(lang, "no_filing"))}</p>'
    fixes = "".join(f'<p class="fix">{_e(I.t(lang, "fix_note", t=f))}</p>' for f in rec.get("fixes") or [])
    pager = '<div class="pager">' + (
        f'<a href="{_href(prefix, before["key"], lang)}">← {_e(I.t(lang, "month", y=before["year"], m=before["month"]))}</a>'
        if before else "<span></span>") + (
        f'<a href="{_href(prefix, after["key"], lang)}">{_e(I.t(lang, "month", y=after["year"], m=after["month"]))} →</a>'
        if after else "<span></span>") + "</div>"
    same_year = [r for r in recs if r["year"] == y]
    monthly = "".join(_mo(lang, r, prefix, key) for r in reversed(same_year))
    checked = (rec.get("fetched_at") or "").replace("T", " ")[:16]
    body = f"""
<article class="vb">
  <div class="kicker">{_e(I.t(lang, "latest") + " · " if is_index else "")}Visa Bulletin · {_e(key)}</div>
  <h1>{_e(I.t(lang, "title_full", y=y, m=m))}</h1>
  {_langs(key, lang, prefix)}
  <p class="legend">{_e(I.t(lang, "legend"))} {_e(I.t(lang, "col_note"))}</p>
  <div class="grp"><h2>{_e(I.t(lang, "final"))}</h2>{final_tables}</div>
  <div class="grp"><h2>{_e(I.t(lang, "filing"))}</h2>{filing}</div>
  {fixes}
  <div class="meta">
    {_uscis(lang, rec)}
    <div><span>{_e(I.t(lang, "source"))}</span><a href="{_e(rec['source_url'])}" rel="nofollow">{_e(I.t(lang, "source_text"))}</a><br>{_e(I.t(lang, "checked", t=checked))}</div>
  </div>
  {site.ad(cfg, "result_side", "ad")}
  {summ}
  <h2>{_e(I.t(lang, "changes"))}</h2>
  {_changes_html(lang, rec)}
  {_trend(lang, recs, key)}
  <h2 id="monthly">{_e(I.t(lang, "monthly"))}</h2>
  {pager}
  <div class="monthly"><div class="yh">{_e(I.t(lang, "year", y=y))}</div>{monthly}</div>
  <a class="toarch" href="{_href(prefix, "archive", lang)}">{_e(I.t(lang, "all"))} →</a>
  <p class="disc2">{_e(I.t(lang, "disclaimer"))}</p>
</article>
{_contact(cfg, lang, f"비자 문호 {y}.{m:02d}")}
{site.ad(cfg, "page_bottom")}
"""
    return _doc(cfg, lang, prefix, I.t(lang, "title", y=y, m=m), I.t(lang, "desc", y=y, m=m),
                f'visa-bulletin/{key}/{"" if lang == "ko" else lang + "/"}', key, body)


def _archive_page(cfg: dict[str, Any], recs: list[dict[str, Any]], lang: str, prefix: str) -> str:
    years = sorted({r["year"] for r in recs}, reverse=True)
    blocks = ""
    for i, yv in enumerate(years):
        rs = [r for r in recs if r["year"] == yv]
        n = sum(len([c for c in r.get("changes") or [] if c["chart"].endswith("final")]) for r in rs)
        blocks += (f'<details{" open" if i < 2 else ""}><summary>{_e(I.t(lang, "year", y=yv))}'
                   f'<span>{len(rs)} · {_e(I.t(lang, "nchg", n=n))}</span></summary>'
                   f'<div class="monthly">{"".join(_mo(lang, r, prefix) for r in reversed(rs))}</div></details>')
    # 해마다 마지막 발표 기준 장기 추이
    last_of_year = [[r for r in recs if r["year"] == yv][-1] for yv in sorted({r["year"] for r in recs})]
    yearly = _trend_table(lang, last_of_year, lambda r: r["key"])
    idx = json.loads(INDEX.read_text(encoding="utf-8")) if INDEX.exists() else {}
    missing = idx.get("missing") or []
    miss = (f'<p class="missing">{_e(I.t(lang, "missing"))}: {_e(", ".join(missing))}</p>' if missing else "")
    body = f"""
<article class="vb">
  <div class="kicker">Visa Bulletin · {_e(recs[0]["key"])} ~ {_e(recs[-1]["key"])}</div>
  <h1>{_e(I.t(lang, "archive_title"))}</h1>
  <p class="lede">{_e(I.t(lang, "archive_desc"))}</p>
  {_langs("archive", lang, prefix)}
  <div class="yrs" style="margin-top:18px">{blocks}</div>
  {miss}
  {site.ad(cfg, "result_side", "ad")}
  <h2>{_e(I.t(lang, "yearly"))}</h2>
  {yearly}
  <p class="disc2">{_e(I.t(lang, "disclaimer"))}</p>
</article>
{_contact(cfg, lang, "비자 문호")}
{site.ad(cfg, "page_bottom")}
"""
    return _doc(cfg, lang, prefix, I.t(lang, "archive_title"), I.t(lang, "archive_desc"),
                f'visa-bulletin/archive/{"" if lang == "ko" else lang + "/"}', "archive", body)


def _empty_page(cfg: dict[str, Any]) -> str:
    body = f"""<article class="vb"><h1>{_e(I.t("ko", "index_title"))}</h1>
<p class="lede">{_e(I.t("ko", "index_desc"))}</p><p class="empty">{_e(I.t("ko", "empty"))}</p></article>"""
    doc = site.head(cfg, I.t("ko", "index_title"), CSS, I.t("ko", "index_desc")) + site.header(cfg, "/visa-bulletin/") + body + site.footer(cfg)
    return _fix(doc, "../", "ko")


def badge(prefix: str = "") -> str:
    recs = load_all()
    if not recs:
        return ""
    r = recs[-1]
    return f'<a class="rate-badge" href="{prefix}visa-bulletin/">비자 문호 {r["year"]}년 {r["month"]}월 발표 보기</a>'


def paths() -> list[str]:
    """sitemap 용 경로."""
    recs = load_all()
    if not recs:
        return []
    out = ["visa-bulletin/"] + [f"visa-bulletin/{lg}/" for lg in I.LANGS if lg != "ko"]
    out += ["visa-bulletin/archive/"] + [f"visa-bulletin/archive/{lg}/" for lg in I.LANGS if lg != "ko"]
    for r in recs:
        out += [f"visa-bulletin/{r['key']}/"] + [f"visa-bulletin/{r['key']}/{lg}/" for lg in I.LANGS if lg != "ko"]
    return out


def _write(path: Path, doc: str) -> None:
    """내용이 같으면 다시 쓰지 않습니다 (수백 개 페이지의 불필요한 커밋 방지)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists() and path.read_text(encoding="utf-8") == doc:
        return
    path.write_text(doc, encoding="utf-8")


def render(cfg: dict[str, Any]) -> list[Path]:
    recs = load_all()
    written: list[Path] = []
    OUT.mkdir(parents=True, exist_ok=True)
    if not recs:
        p = OUT / "index.html"
        _write(p, _empty_page(cfg))
        return [p]
    latest = recs[-1]
    for lang in I.LANGS:
        sub = "" if lang == "ko" else lang
        p = OUT / sub / "index.html"
        _write(p, _month_page(cfg, recs, latest, lang, "../" if lang == "ko" else "../../", is_index=True))
        a = OUT / "archive" / sub / "index.html"
        _write(a, _archive_page(cfg, recs, lang, "../../" if lang == "ko" else "../../../"))
        written += [p, a]
    for rec in recs:
        for lang in I.LANGS:
            f = OUT / rec["key"] / ("" if lang == "ko" else lang) / "index.html"
            _write(f, _month_page(cfg, recs, rec, lang, "../../" if lang == "ko" else "../../../"))
            written.append(f)
    return written
