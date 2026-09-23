"""가이드 목록 페이지.

글 본문은 전부 content/posts/*.md 에 있고 관리자 화면에서 작성·수정합니다.
분류가 "가이드"인 글은 실무 가이드 칸에, 나머지는 최신 소식 칸에 나옵니다.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from src import site

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

# 사이트맵에 넣을 별도 글 목록. 지금은 전부 content/posts 로 옮겨서 비어 있습니다.
ARTICLES: list[dict[str, str]] = []

# 예전 주소로 들어온 방문자를 새 주소로 넘깁니다.
LEGACY = {
    "guide-cspa.html": "news/2026-09-15-guide-cspa.html",
    "guide-charts.html": "news/2026-09-15-guide-charts.html",
    "guide-e2-cost.html": "news/2026-09-15-guide-e2-cost.html",
    "guide-l1-blanket-cost.html": "news/2026-09-15-guide-l1-blanket-cost.html",
    "guide-fee-faq.html": "news/2026-09-15-guide-fee-faq.html",
}

CSS = """
.art{max-width:72ch;margin-top:26px}
.art .kicker{font-size:12.5px;color:var(--faint);margin-bottom:6px}
.art h1{font-size:26px;line-height:1.3;letter-spacing:-.025em;margin:0 0 12px}
.art .sum{font-size:15px;color:var(--muted);padding-bottom:18px;border-bottom:1px solid var(--rule)}
.art h2{font-size:17px;margin:32px 0 10px;letter-spacing:-.01em}
.art h3{font-size:15px;margin:22px 0 6px}
.art p{margin:0 0 13px}
.art ul,.art ol{padding-left:20px;margin:0 0 13px}
.art li{margin-bottom:5px}
.art table{width:100%;border-collapse:collapse;font-size:14px;margin:14px 0 18px;background:var(--paper)}
.art th{text-align:left;font-size:12.5px;color:var(--faint);font-weight:600;padding:8px 10px;border-bottom:1px solid var(--rule)}
.art td{padding:8px 10px;border-bottom:1px solid var(--hair)}
.art td.n{text-align:right;font-variant-numeric:tabular-nums;font-weight:600;white-space:nowrap}
.art blockquote{margin:16px 0;padding:12px 16px;background:var(--paper);
  border-left:3px solid var(--ink);font-size:14px;color:var(--muted)}
.art .tool{display:block;margin:20px 0;padding:14px 16px;background:var(--paper);
  border:1px solid var(--rule);text-decoration:none;border-radius:2px}
.art .tool b{display:block;font-size:14.5px}
.art .tool span{font-size:13px;color:var(--faint)}
.list{margin-top:26px;max-width:74ch}
.list a{display:block;padding:18px 0;border-bottom:1px solid var(--rule);text-decoration:none}
.list a:first-child{border-top:1px solid var(--rule)}
.list b{display:block;font-size:16px;margin-bottom:4px;letter-spacing:-.01em}
.list span{font-size:13.5px;color:var(--muted)}
.list h2{font-size:13px;font-weight:600;color:var(--muted);margin:30px 0 6px}
.list a.news{display:flex;gap:16px;align-items:flex-start}
.list a.news img{width:132px;height:88px;object-fit:cover;border-radius:2px;border:1px solid var(--rule);flex:none}
.list a.news .d{display:block;font-size:12px;color:var(--faint);margin-bottom:3px;font-variant-numeric:tabular-nums}
@media (max-width:640px){.list a.news img{width:96px;height:64px}}
"""


def _item(p: dict[str, Any]) -> str:
    img = f'<img src="{html.escape(p["cover"].lstrip("/"))}" alt="">' if p["cover"] else ""
    return (
        f'<a class="news" href="news/{p["slug"]}.html">{img}'
        f'<div><span class="d">{html.escape(p["category"])} · {p["date"].isoformat()}</span>'
        f'<b>{html.escape(p["title"])}</b><span>{html.escape(p["summary"])}</span></div></a>'
    )


def render_articles(cfg: dict[str, Any]) -> list[Path]:
    from src import posts as posts_mod

    DOCS.mkdir(parents=True, exist_ok=True)
    posts = posts_mod.render_posts(cfg)

    for old, new in LEGACY.items():
        (DOCS / old).write_text(
            f'<!doctype html><meta charset="utf-8"><link rel="canonical" href="{new}">'
            f'<meta http-equiv="refresh" content="0; url={new}"><a href="{new}">{new}</a>\n',
            encoding="utf-8",
        )

    news = [p for p in posts if p["category"] != "가이드"]
    guides = [p for p in posts if p["category"] == "가이드"]
    blocks = ""
    if news:
        blocks += "<h2>최신 소식</h2>" + "".join(_item(p) for p in news[:30])
    if news and guides:
        blocks += site.ad(cfg, "list_mid")
    if guides:
        blocks += "<h2>실무 가이드</h2>" + "".join(_item(p) for p in guides)

    body = f"""
<div class="list">{blocks}</div>
{site.lead_form(cfg)}
{site.ad(cfg, "page_bottom")}
"""
    doc = (
        site.head(cfg, "가이드와 소식", CSS,
                  "미국 비자 수수료와 CSPA 나이 계산에 관한 실무 해설과 최신 소식",
                  path="guides.html")
        + site.header(cfg, "guides.html")
        + body
        + site.footer(cfg)
    )
    path = DOCS / "guides.html"
    path.write_text(doc, encoding="utf-8")
    return [path]
