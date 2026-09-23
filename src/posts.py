"""뉴스 포스트.

content/posts/*.md 를 읽어 docs/news/<slug>.html 을 만듭니다.
글은 /admin 의 CMS에서 작성하면 이 폴더에 마크다운으로 커밋되고,
워크플로가 이 모듈을 돌려 페이지로 만듭니다.
"""

from __future__ import annotations

import datetime as dt
import html
import re
from pathlib import Path
from typing import Any

import yaml

from src import site

ROOT = Path(__file__).resolve().parents[1]
POSTS_DIR = ROOT / "content" / "posts"
OUT_DIR = ROOT / "docs" / "news"

CSS = """
.art{max-width:72ch;margin-top:26px}
.art .kicker{font-size:12.5px;color:var(--faint);margin-bottom:6px;font-variant-numeric:tabular-nums}
.art h1{font-size:26px;line-height:1.3;letter-spacing:-.025em;margin:0 0 12px}
.art .sum{font-size:15px;color:var(--muted);padding-bottom:18px;border-bottom:1px solid var(--rule)}
.art .cover{width:100%;height:auto;margin:22px 0 4px;border-radius:2px;border:1px solid var(--rule)}
.art h2{font-size:17px;margin:32px 0 10px;letter-spacing:-.01em}
.art h3{font-size:15px;margin:22px 0 6px}
.art p{margin:0 0 13px}
.art ul,.art ol{padding-left:20px;margin:0 0 13px}
.art li{margin-bottom:5px}
.art img{max-width:100%;height:auto}
.art table{width:100%;border-collapse:collapse;font-size:14px;margin:14px 0 18px;background:var(--paper)}
.art th{text-align:left;font-size:12.5px;color:var(--faint);font-weight:600;padding:8px 10px;border-bottom:1px solid var(--rule)}
.art td{padding:8px 10px;border-bottom:1px solid var(--hair)}
.art blockquote{margin:16px 0;padding:12px 16px;background:var(--paper);border-left:3px solid var(--ink);font-size:14px;color:var(--muted)}
.art .back{display:inline-block;margin-top:28px;font-size:14px}
"""

FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n(.*)$", re.S)


def _slug(path: Path) -> str:
    return re.sub(r"[^a-z0-9\-]+", "-", path.stem.lower()).strip("-") or "post"


def _order(value: Any) -> int | None:
    """목록 고정 순서. 비었거나 숫자가 아니면 순서 지정 없음으로 봅니다."""
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(str(value).strip())
    except ValueError:
        return None


def _img(src: str) -> str:
    """CMS가 넣는 /uploads/... 경로를 페이지 위치 기준으로 맞춥니다."""
    if not src:
        return ""
    if src.startswith("http"):
        return src
    return "../" + src.lstrip("/")


def load_posts() -> list[dict[str, Any]]:
    if not POSTS_DIR.exists():
        return []
    posts = []
    for path in POSTS_DIR.glob("*.md"):
        raw = path.read_text(encoding="utf-8")
        m = FRONT.match(raw)
        meta: dict[str, Any] = yaml.safe_load(m.group(1)) if m else {}
        body = m.group(2) if m else raw
        if meta.get("draft"):
            continue
        # 예약 게시: 한국 시간 기준으로 예정 시각이 지나야 공개
        pub = meta.get("publish_at")
        if pub:
            try:
                when = dt.datetime.fromisoformat(str(pub)[:16])
                if when > dt.datetime.utcnow() + dt.timedelta(hours=9):
                    continue
            except ValueError:
                pass
        date = meta.get("date") or dt.date.today()
        if isinstance(date, (dt.datetime,)):
            date = date.date()
        if isinstance(date, str):
            date = dt.date.fromisoformat(date[:10])
        posts.append(
            {
                "slug": _slug(path),
                "order": _order(meta.get("order")),
                "title": str(meta.get("title") or path.stem),
                "summary": str(meta.get("summary") or ""),
                "category": str(meta.get("category") or "뉴스"),
                "cover": str(meta.get("cover") or ""),
                "date": date,
                "body": body,
            }
        )
    # order 를 지정한 글이 오름차순으로 먼저 오고, 나머지는 최신순으로 뒤따릅니다.
    # glob 순서는 파일시스템에 따라 달라지므로 동점일 때는 slug 로 순서를 고정합니다.
    fixed = [p for p in posts if p["order"] is not None]
    rest = [p for p in posts if p["order"] is None]
    fixed.sort(key=lambda p: (p["order"], p["slug"]))
    rest.sort(key=lambda p: (p["date"], p["slug"]), reverse=True)
    return fixed + rest


def _to_html(md_text: str) -> str:
    import markdown

    out = markdown.markdown(md_text, extensions=["tables", "fenced_code", "sane_lists"])
    # 본문 이미지 경로도 news/ 폴더 기준으로 보정
    return re.sub(r'src="/(uploads/[^"]+)"', r'src="../\1"', out)


def _with_inline_ad(body_html: str, ad_html: str) -> str:
    """본문 중간에 광고를 한 번 넣습니다.

    문단 세 개를 읽은 뒤가 자연스럽고, 짧은 글에는 넣지 않습니다.
    본문과 붙어 보이지 않도록 광고 표기는 site.ad 가 함께 출력합니다.
    """
    if not ad_html:
        return body_html
    ends = [m.end() for m in re.finditer(r"</p>", body_html)]
    if len(ends) < 6:
        return body_html
    cut = ends[2]
    return body_html[:cut] + ad_html + body_html[cut:]


def render_posts(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    posts = load_posts()
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for old in OUT_DIR.glob("*.html"):
        old.unlink()

    for p in posts:
        cover = (
            f'<img class="cover" src="{html.escape(_img(p["cover"]))}" alt="">' if p["cover"] else ""
        )
        body = f"""
<article class="art">
  <div class="kicker">{html.escape(p['category'])} · {p['date'].isoformat()}</div>
  <h1>{html.escape(p['title'])}</h1>
  <div class="sum">{html.escape(p['summary'])}</div>
  {cover}
  {_with_inline_ad(_to_html(p['body']), site.ad(cfg, "in_article"))}
  <a class="back" href="../guides.html">가이드와 소식 전체 보기</a>
</article>
{site.lead_form(cfg, p['title'][:30])}
{site.ad(cfg, "page_bottom")}
"""
        doc = (
            site.head(
                cfg, p["title"], CSS, p["summary"],
                path=f"news/{p['slug']}.html",
                jsonld=site.jsonld_article(
                    cfg, p["title"], p["summary"], f"news/{p['slug']}.html",
                    p["date"].isoformat(), p["cover"],
                ),
                og_type="article",
                image=p["cover"],
            )
            + site.header(cfg, "guides.html")
            + body
            + site.footer(cfg)
        )
        # news/ 하위 페이지라 상대경로 링크를 한 단계 올립니다.
        doc = re.sub(r'href="(?!https?:|mailto:|#|\.\./)([a-z\-]+\.html)"', r'href="../\1"', doc)
        (OUT_DIR / f"{p['slug']}.html").write_text(doc, encoding="utf-8")
    return posts
