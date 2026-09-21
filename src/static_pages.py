"""매 실행마다 같은 내용으로 다시 쓰이는 부속 파일.

CNAME과 ads.txt는 실수로 지우면 도메인이 끊기거나 광고 수익이 정지됩니다.
빌드가 매번 다시 써서 복구되도록 코드 쪽에 둡니다.
"""

from __future__ import annotations

import datetime as dt
import html
from pathlib import Path
from typing import Any

from src import site

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

PRIVACY_CSS = """
.doc{max-width:74ch;margin-top:24px}
.doc h2{font-size:15px;margin:28px 0 8px}
.doc p,.doc li{color:var(--muted);font-size:14px}
.doc ul{padding-left:18px}
"""


def render_privacy(cfg: dict[str, Any]) -> Path:
    s = cfg.get("site", {})
    operator = html.escape(s.get("operator", ""))
    email = html.escape(s.get("contact_email", ""))
    domain = html.escape(s.get("domain", ""))
    has_ads = bool((cfg.get("adsense") or {}).get("client_id"))

    ads_section = (
        """
<h2>광고</h2>
<p>이 사이트는 Google AdSense를 통해 광고를 게재합니다. Google을 포함한 제3자 광고 사업자는
쿠키를 사용해 이용자의 방문 기록을 바탕으로 광고를 제공할 수 있습니다.
이용자는 Google 광고 설정에서 맞춤 광고를 해제할 수 있으며, 브라우저 설정으로 쿠키를 차단할 수 있습니다.</p>
<p>유럽경제지역, 영국, 스위스에서 접속하는 이용자에게 광고를 노출하는 경우
Google이 인증한 동의 관리 플랫폼을 통해 사전 동의를 받아야 합니다.</p>
"""
        if has_ads
        else ""
    )

    body = f"""
<div class="doc">
<p>{operator}는 {domain}에서 제공하는 계산 도구와 관련해 다음과 같이 개인정보를 처리합니다.
시행일 {dt.date.today().isoformat()}.</p>

<h2>수집하지 않는 정보</h2>
<p>관납료 계산기와 CSPA 나이 계산기에 입력하는 생년월일, 사건 날짜, 금액 등 모든 값은
이용자의 브라우저 안에서만 계산되며 서버로 전송되거나 저장되지 않습니다.
운영자는 이용자가 입력한 사건 정보를 열람할 수 없습니다.</p>

<h2>자동으로 수집되는 정보</h2>
<p>사이트 운영과 통계를 위해 접속 로그, 브라우저 종류, 접속 시각 등이 호스팅 사업자에 의해 기록될 수 있습니다.
이 정보는 개인을 식별하는 목적으로 사용되지 않습니다.</p>
{ads_section}
<h2>문의로 제공한 정보</h2>
<p>상담 신청이나 검토 요청을 통해 이름, 연락처, 사건 내용을 제공한 경우
해당 정보는 문의 처리와 수임 검토 목적으로만 사용되며, 목적 달성 후 관계 법령이 정한 기간이 지나면 파기됩니다.</p>

<h2>이용자의 권리</h2>
<p>이용자는 자신의 개인정보에 대해 열람, 정정, 삭제, 처리정지를 요구할 수 있습니다.
요청은 아래 연락처로 접수합니다.</p>

<h2>문의</h2>
<p>{operator} {email}</p>
</div>
"""
    doc = (
        site.head(cfg, "개인정보처리방침", PRIVACY_CSS)
        + site.header(cfg, "privacy.html")
        + body
        + site.footer(cfg)
    )
    out = DOCS / "privacy.html"
    out.write_text(doc, encoding="utf-8")
    return out


def render_all(cfg: dict[str, Any]) -> None:
    DOCS.mkdir(parents=True, exist_ok=True)
    render_privacy(cfg)

    domain = (cfg.get("site") or {}).get("domain") or ""
    client = (cfg.get("adsense") or {}).get("client_id") or ""

    if domain:
        (DOCS / "CNAME").write_text(domain + "\n", encoding="utf-8")
        (DOCS / "robots.txt").write_text(
            f"User-agent: *\nAllow: /\nSitemap: https://{domain}/sitemap.xml\n", encoding="utf-8"
        )
        today = dt.date.today().isoformat()
        from src.articles import ARTICLES

        pages = ["", "cspa.html", "guides.html", "changes.html", "privacy.html"]
        pages += [a["slug"] for a in ARTICLES]
        urls = "".join(
            f"<url><loc>https://{domain}/{page}</loc><lastmod>{today}</lastmod></url>"
            for page in pages
        )
        (DOCS / "sitemap.xml").write_text(
            f'<?xml version="1.0" encoding="UTF-8"?>\n'
            f'<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">{urls}</urlset>\n',
            encoding="utf-8",
        )

    if client:
        pub = client.replace("ca-", "")
        (DOCS / "ads.txt").write_text(
            f"google.com, {pub}, DIRECT, f08c47fec0942fa0\n", encoding="utf-8"
        )
