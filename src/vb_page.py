"""비자 문호 페이지.

docs/visa-bulletin/index.html               최신 달 (한국어) + 지난 달 목록
docs/visa-bulletin/YYYY-MM/index.html       달별 한국어
docs/visa-bulletin/YYYY-MM/<lang>/index.html 달별 다른 언어 (en, zh, ja, vi, es)

표 숫자는 수집한 원문 데이터 그대로, 문구는 vb_i18n 고정 문구, 요약만 자동 작성입니다.
"""

from __future__ import annotations

import html
import re
from pathlib import Path
from typing import Any

from src import site
from src import vb_i18n as I
from src.visa_bulletin import change_line, load_all

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "visa-bulletin"

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
"""

CHARTS = [("fam_final", I.FAMILY_ROWS), ("fam_filing", I.FAMILY_ROWS),
          ("emp_final", I.EMP_ROWS), ("emp_filing", I.EMP_ROWS)]


def _e(s: Any) -> str:
    return html.escape(str(s))


def _cell(lang: str, v: str, old: str | None) -> str:
    cls, arrow, title = "", "", ""
    if old and old != v:
        title = f' title="{_e(old)} → {_e(v)}"'
        if v == "C" or (old not in ("C", "U") and v not in ("C", "U") and v > old) or old == "U":
            cls, arrow = "up", "▲"
        else:
            cls, arrow = "dn", "▼"
    cur = " cur" if v == "C" else ""
    a = f'<span class="ar">{arrow}</span>' if arrow else ""
    return f'<td class="{cls}{cur}"{title}>{_e(v)}{a}</td>'


def _table(lang: str, rec: dict[str, Any], prev: dict[str, Any] | None, chart: str, rows: list[str]) -> str:
    head = "".join(f"<th>{_e(I.t(lang, c))}</th>" for c in I.COLS)
    body = ""
    pc = (prev or {}).get("charts", {}).get(chart, {})
    for r in rows:
        vals = rec["charts"][chart].get(r) or ["", "", "", "", ""]
        olds = pc.get(r) or [None] * 5
        name = I.t(lang, r)
        short = I.SHORT[r]
        rest = name[len(short):].strip() if name.startswith(short) else name
        body += (f'<tr><td class="l"><b>{_e(short)}</b> <span>{_e(rest)}</span></td>'
                 + "".join(_cell(lang, v, o) for v, o in zip(vals, olds)) + "</tr>")
    u = rec.get("uscis") or {}
    kind = "family" if chart.startswith("fam") else "employment"
    tag = ""
    if u.get(kind) and chart.endswith(u[kind]):
        tag = f' <em class="tag">{_e(I.t(lang, "uscis_tag"))}</em>'
    return (f'<h3 id="{chart}">{_e(I.t(lang, chart))}{tag}</h3>'
            f'<div class="tw"><table><thead><tr><th>{_e(I.t(lang, "cat"))}</th>{head}</tr></thead>'
            f"<tbody>{body}</tbody></table></div>")


def _trend(lang: str, recs: list[dict[str, Any]], upto: str) -> str:
    seq = [r for r in recs if r["key"] <= upto][-8:]
    if len(seq) < 2:
        return ""
    head = "".join(f"<th>{_e(r['key'])}</th>" for r in seq)
    body = ""
    for row in I.KEY_ROWS:
        chart = "fam_final" if row.startswith("F") else "emp_final"
        cells, last = "", None
        for r in seq:
            v = (r["charts"][chart].get(row) or [""])[0]
            cells += _cell(lang, v, last)
            last = v
        body += f'<tr><td class="k">{_e(I.SHORT[row])}</td>{cells}</tr>'
    return (f'<h2>{_e(I.t(lang, "trend"))}</h2><div class="tw"><table><thead><tr>'
            f'<th>{_e(I.t(lang, "cat"))}</th>{head}</tr></thead><tbody>{body}</tbody></table></div>')


def _uscis(lang: str, rec: dict[str, Any]) -> str:
    u = rec.get("uscis") or {}

    def w(v: str | None) -> str:
        return I.t(lang, v) if v in ("final", "filing") else I.t(lang, "uscis_unknown")

    return (f'<div><span>{_e(I.t(lang, "uscis"))}</span>'
            f'{_e(I.t(lang, "uscis_fam"))}: {_e(w(u.get("family")))}<br>'
            f'{_e(I.t(lang, "uscis_emp"))}: {_e(w(u.get("employment")))}</div>')


def _langs(rec_key: str, lang: str, depth_prefix: str) -> str:
    out = []
    for lg in I.LANGS:
        href = f"{depth_prefix}visa-bulletin/{rec_key}/" + ("" if lg == "ko" else f"{lg}/")
        cur = ' aria-current="page"' if lg == lang else ""
        out.append(f'<a href="{href}" hreflang="{I.HTML_LANG[lg]}"{cur}>{_e(I.NATIVE[lg])}</a>')
    return f'<nav class="langs" aria-label="{_e(I.t(lang, "lang"))}">{"".join(out)}</nav>'


def _alternates(domain: str, key: str) -> str:
    links = "".join(
        f'<link rel="alternate" hreflang="{I.HTML_LANG[lg]}" href="https://{domain}/visa-bulletin/{key}/'
        f'{"" if lg == "ko" else lg + "/"}">'
        for lg in I.LANGS
    )
    return links + f'<link rel="alternate" hreflang="x-default" href="https://{domain}/visa-bulletin/{key}/en/">'


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


def _href(prefix: str, key: str | None, lang: str) -> str:
    base = f"{prefix}visa-bulletin/" + (f"{key}/" if key else "")
    return base + ("" if lang == "ko" else f"{lang}/")


def _monthly(lang: str, recs: list[dict[str, Any]], prefix: str, current: str) -> str:
    """월별 정리. 연도별로 묶고 달마다 요약 제목과 변동 건수를 보여 줍니다."""
    out, year = "", None
    for r in reversed(recs):
        if r["year"] != year:
            if year is not None:
                out += "</div>"
            year = r["year"]
            out += f'<div class="yr"><div class="yh">{_e(I.t(lang, "year", y=year))}</div>'
        s = (r.get("summary") or {}).get(lang) or {}
        n = len([c for c in r.get("changes") or [] if c["chart"].endswith("final")])
        cnt = I.t(lang, "nchg", n=n) if n else (I.t(lang, "nchg0") if r.get("prev_key") else "")
        cur = ' aria-current="page"' if r["key"] == current else ""
        out += (f'<a class="mo" href="{_href(prefix, r["key"], lang)}"{cur}>'
                f'<span class="mk">{_e(I.t(lang, "month", y=r["year"], m=r["month"]))}</span>'
                f'<span class="mh">{_e(s.get("headline") or I.t(lang, "title", y=r["year"], m=r["month"]))}</span>'
                f'<span class="mc">{_e(cnt)}</span></a>')
    return out + ("</div>" if year is not None else "")


def _month_page(cfg: dict[str, Any], recs: list[dict[str, Any]], rec: dict[str, Any], lang: str,
                prefix: str, is_index: bool = False) -> str:
    y, m, key = rec["year"], rec["month"], rec["key"]
    prev = next((r for r in recs if r["key"] == rec.get("prev_key")), None)
    keys = [r["key"] for r in recs]
    i = keys.index(key)
    before = recs[i - 1] if i > 0 else None
    after = recs[i + 1] if i + 1 < len(recs) else None
    s = (rec.get("summary") or {}).get(lang) or {}
    title = I.t(lang, "title_full", y=y, m=m)
    pts = "".join(f"<li>{_e(p)}</li>" for p in s.get("points") or [])
    summ = (
        f'<div class="sumbox"><b>{_e(s.get("headline") or I.t(lang, "title", y=y, m=m))}</b>'
        + (f"<p>{_e(s['summary'])}</p>" if s.get("summary") else "")
        + (f"<ul>{pts}</ul>" if pts else "")
        + (f'<div class="ai">{_e(I.t(lang, "ai_note"))}</div>' if s.get("auto") else "")
        + "</div>"
    )
    final_tables = _table(lang, rec, prev, "fam_final", I.FAMILY_ROWS) + _table(lang, rec, prev, "emp_final", I.EMP_ROWS)
    filing_tables = _table(lang, rec, prev, "fam_filing", I.FAMILY_ROWS) + _table(lang, rec, prev, "emp_filing", I.EMP_ROWS)
    pager = '<div class="pager">' + (
        f'<a href="{_href(prefix, before["key"], lang)}">← {_e(I.t(lang, "month", y=before["year"], m=before["month"]))}</a>'
        if before else "<span></span>") + (
        f'<a href="{_href(prefix, after["key"], lang)}">{_e(I.t(lang, "month", y=after["year"], m=after["month"]))} →</a>'
        if after else "<span></span>") + "</div>"
    checked = (rec.get("fetched_at") or "").replace("T", " ")[:16]
    contact = site.lead_form(cfg, f"비자 문호 {y}.{m:02d}") if lang == "ko" else (
        f'<p class="notes">{_e(I.t(lang, "contact"))}: '
        f'<a href="mailto:{_e((cfg.get("site") or {}).get("contact_email", ""))}">'
        f'{_e((cfg.get("site") or {}).get("contact_email", ""))}</a></p>'
    )
    body = f"""
<article class="vb">
  <div class="kicker">{_e(I.t(lang, "latest") + " · " if is_index else "")}Visa Bulletin · {_e(key)}</div>
  <h1>{_e(title)}</h1>
  {_langs(key, lang, prefix)}
  <p class="legend">{_e(I.t(lang, "legend"))} {_e(I.t(lang, "col_note"))}</p>
  <div class="grp"><h2>{_e(I.t(lang, "final"))}</h2>{final_tables}</div>
  <div class="grp"><h2>{_e(I.t(lang, "filing"))}</h2>{filing_tables}</div>
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
  <div class="monthly">{_monthly(lang, recs, prefix, key)}</div>
  <p class="disc2">{_e(I.t(lang, "disclaimer"))}</p>
</article>
{contact}
{site.ad(cfg, "page_bottom")}
"""
    domain = (cfg.get("site") or {}).get("domain") or "visacal.com"
    canonical = f'https://{domain}/visa-bulletin/{key}/{"" if lang == "ko" else lang + "/"}'
    head = site.head(cfg, I.t(lang, "title", y=y, m=m), CSS, I.t(lang, "desc", y=y, m=m)).replace(
        "</head>", f'<link rel="canonical" href="{canonical}">{_alternates(domain, key)}</head>', 1)
    doc = head + site.header(cfg, "/visa-bulletin/") + body + site.footer(cfg)
    return _fix(doc, prefix, lang)


def _empty_page(cfg: dict[str, Any]) -> str:
    body = f"""<article class="vb"><h1>{_e(I.t("ko", "index_title"))}</h1>
<p class="lede">{_e(I.t("ko", "index_desc"))}</p><p class="empty">{_e(I.t("ko", "empty"))}</p></article>"""
    doc = site.head(cfg, I.t("ko", "index_title"), CSS, I.t("ko", "index_desc")) + site.header(cfg, "/visa-bulletin/") + body + site.footer(cfg)
    return _fix(doc, "../", "ko")


def badge(prefix: str = "") -> str:
    """메인 화면용 한 줄 링크."""
    recs = load_all()
    if not recs:
        return ""
    r = recs[-1]
    return f'<a class="rate-badge" href="{prefix}visa-bulletin/">비자 문호 {r["year"]}년 {r["month"]}월 발표 보기</a>'


def paths() -> list[str]:
    """sitemap 용 경로."""
    recs = load_all()
    out = (["visa-bulletin/"] + [f"visa-bulletin/{lg}/" for lg in I.LANGS if lg != "ko"]) if recs else []
    for r in recs:
        out += [f"visa-bulletin/{r['key']}/"] + [f"visa-bulletin/{r['key']}/{lg}/" for lg in I.LANGS if lg != "ko"]
    return out


def render(cfg: dict[str, Any]) -> list[Path]:
    recs = load_all()
    written: list[Path] = []
    OUT.mkdir(parents=True, exist_ok=True)
    if not recs:
        p = OUT / "index.html"
        p.write_text(_empty_page(cfg), encoding="utf-8")
        return [p]
    # 상단 메뉴 '비자 문호'는 최신 달로 바로 들어갑니다. 언어별 최신 주소도 따로 둡니다.
    latest = recs[-1]
    for lang in I.LANGS:
        d = OUT if lang == "ko" else OUT / lang
        d.mkdir(parents=True, exist_ok=True)
        p = d / "index.html"
        p.write_text(_month_page(cfg, recs, latest, lang, "../" if lang == "ko" else "../../", is_index=True),
                     encoding="utf-8")
        written.append(p)
    for rec in recs:
        for lang in I.LANGS:
            d = OUT / rec["key"] / ("" if lang == "ko" else lang)
            d.mkdir(parents=True, exist_ok=True)
            prefix = "../../" if lang == "ko" else "../../../"
            f = d / "index.html"
            f.write_text(_month_page(cfg, recs, rec, lang, prefix), encoding="utf-8")
            written.append(f)
    return written
