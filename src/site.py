"""모든 페이지가 공유하는 조각.

광고와 전환 동선은 config/site.yaml 값이 비어 있으면 아예 출력되지 않습니다.
로컬에서는 깨끗한 화면으로 확인하고 배포 시점에만 채우면 됩니다.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[1]
SITE_CFG = ROOT / "config" / "site.yaml"

NAV = [
    ("index.html", "관납료"),
    ("cspa.html", "CSPA 나이"),
    ("guides.html", "가이드"),
    ("changes.html", "원장과 이력"),
]

TOKENS = """
:root{
  --ink:#14243c; --muted:#6b7688; --faint:#98a1b0;
  --rule:#d8dee7; --hair:#e8ecf1; --ground:#eef1f5; --paper:#fff;
  --warn:#9b2226; --pend:#8a6d1f; --ok:#1f6b45;
}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--ground);color:var(--ink);
  font-family:Pretendard,'Apple SD Gothic Neo','Noto Sans KR',system-ui,sans-serif;
  font-size:15px;line-height:1.6}
.wrap{max-width:1020px;margin:0 auto;padding:28px 20px 64px}
a{color:var(--ink)}
.top{display:flex;justify-content:space-between;align-items:baseline;gap:16px;flex-wrap:wrap;
  border-bottom:2px solid var(--ink);padding-bottom:12px}
.brand{font-size:19px;font-weight:700;letter-spacing:-.02em;text-decoration:none}
.brand span{color:var(--faint);font-weight:400;font-size:13px;margin-left:9px;letter-spacing:0}
nav{display:flex;gap:16px;font-size:14px}
nav a{color:var(--muted);text-decoration:none;padding-bottom:2px}
nav a:hover{color:var(--ink)}
nav a[aria-current="page"]{color:var(--ink);font-weight:650;border-bottom:2px solid var(--ink)}
.stamp{color:var(--faint);font-size:12.5px;font-variant-numeric:tabular-nums;margin-top:10px}
.ad{margin:22px 0;min-height:1px}
.ad-label{display:block;font-size:11px;color:var(--faint);letter-spacing:.06em;margin-bottom:4px}
.ad-side{margin:18px 0 0}
.cta{margin-top:16px;padding-top:14px;border-top:1px solid var(--hair)}
.cta a{display:block;text-align:center;text-decoration:none;padding:11px 14px;
  border:1px solid var(--ink);font-size:14px;font-weight:600;border-radius:2px;margin-bottom:8px}
.cta a.solid{background:var(--ink);color:#fff}
.cta .p{font-size:12.5px;color:var(--faint);text-align:center}
footer{margin-top:52px;padding-top:18px;border-top:1px solid var(--rule);
  color:var(--faint);font-size:12.5px;line-height:1.7}
footer a{color:var(--muted)}
.lead-form{background:var(--paper);border:1px solid var(--rule);border-top:3px solid var(--ink);
  padding:20px 22px;margin:34px 0 0;border-radius:2px}
.lead-form h3{font-size:15px;margin:0 0 4px}
.lead-form .sd{font-size:13px;color:var(--faint);margin-bottom:14px}
.lead-form .g{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.lead-form input,.lead-form select,.lead-form textarea{width:100%;border:1px solid var(--rule);
  padding:9px 10px;font:inherit;font-size:14px;border-radius:2px;background:var(--paper);color:var(--ink)}
.lead-form textarea{min-height:82px;resize:vertical;margin-top:10px}
.lead-form button{margin-top:12px;width:100%;background:var(--ink);color:#fff;border:0;
  padding:12px;font:inherit;font-size:14px;font-weight:600;cursor:pointer;border-radius:2px}
.lead-form .fine{font-size:12px;color:var(--faint);margin-top:9px;line-height:1.5}
@media (max-width:640px){.lead-form .g{grid-template-columns:1fr}}
footer .disc{max-width:74ch;margin-bottom:10px}
"""


def load_cfg() -> dict[str, Any]:
    if not SITE_CFG.exists():
        return {"site": {}, "adsense": {"slots": {}}, "cta": {}}
    return yaml.safe_load(SITE_CFG.read_text(encoding="utf-8")) or {}


def canonical_url(cfg: dict[str, Any], path: str = "") -> str:
    """페이지의 정규 주소. path 가 비면 루트입니다."""
    domain = (cfg.get("site") or {}).get("domain") or ""
    if not domain:
        return ""
    return f"https://{domain}/{path.lstrip('/')}"


def head(
    cfg: dict[str, Any],
    title: str,
    css: str,
    description: str = "",
    path: str | None = "",
    jsonld: str = "",
    og_type: str = "website",
    image: str = "",
) -> str:
    site = cfg.get("site", {})
    client = (cfg.get("adsense") or {}).get("client_id") or ""
    # 소유 확인용 메타와 로더를 함께 냅니다. 심사 중에도 메타는 필요합니다.
    ads_script = (
        f'<meta name="google-adsense-account" content="{html.escape(client)}">'
        f'<script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={html.escape(client)}" crossorigin="anonymous"></script>'
        if client
        else ""
    )
    an = cfg.get("analytics") or {}
    ga = an.get("ga4_id") or ""
    ga_script = (
        f'<script async src="https://www.googletagmanager.com/gtag/js?id={html.escape(ga)}"></script>'
        f"<script>window.dataLayer=window.dataLayer||[];function gtag(){{dataLayer.push(arguments);}}"
        f"gtag('js',new Date());gtag('config','{html.escape(ga)}');</script>"
        if ga
        else ""
    )
    verify = an.get("search_console") or ""
    verify_tag = f'<meta name="google-site-verification" content="{html.escape(verify)}">' if verify else ""
    desc = description or site.get("tagline", "")
    full_title = f"{title} · {site.get('title', 'VisaCal')}"
    # path 가 None 이면 정규 주소를 넣지 않습니다. 404 처럼 대표 주소가 없는 페이지입니다.
    url = canonical_url(cfg, path) if path is not None else ""
    canonical_tag = f'<link rel="canonical" href="{html.escape(url)}">' if url else ""

    # 공유 카드. 카카오톡과 슬랙, 검색 미리보기가 같은 값을 읽습니다.
    og = [
        f'<meta property="og:type" content="{html.escape(og_type)}">',
        f'<meta property="og:title" content="{html.escape(full_title)}">',
        f'<meta property="og:description" content="{html.escape(desc)}">',
        f'<meta property="og:site_name" content="{html.escape(site.get("title", "VisaCal"))}">',
        '<meta property="og:locale" content="ko_KR">',
    ]
    if url:
        og.append(f'<meta property="og:url" content="{html.escape(url)}">')
    if image:
        img_url = image if image.startswith("http") else canonical_url(cfg, image)
        og.append(f'<meta property="og:image" content="{html.escape(img_url)}">')
    og.append('<meta name="twitter:card" content="%s">' % ("summary_large_image" if image else "summary"))
    og_tags = "".join(og)

    ld = f'<script type="application/ld+json">{jsonld}</script>' if jsonld else ""

    return f"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html.escape(full_title)}</title>
<meta name="description" content="{html.escape(desc)}">
<meta name="theme-color" content="#14243c">
{canonical_tag}
{og_tags}
<link rel="preconnect" href="https://cdn.jsdelivr.net" crossorigin>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/static/pretendard.min.css">
{verify_tag}
{ld}
{ads_script}{ga_script}
<style>{TOKENS}{css}</style></head><body>"""


def header(cfg: dict[str, Any], active: str, stamp: str = "") -> str:
    site = cfg.get("site", {})
    # 파이썬 3.11 에서는 f-string 안에 역슬래시를 쓸 수 없어 속성 문자열을 밖에 둡니다
    current = ' aria-current="page"'
    links = "".join(
        f'<a href="{href}"{current if href == active else ""}>{html.escape(label)}</a>'
        for href, label in NAV
    )
    stamp_html = f'<div class="stamp">{html.escape(stamp)}</div>' if stamp else ""
    return f"""<div class="wrap">
<div class="top">
  <a class="brand" href="index.html">{html.escape(site.get('title', 'VisaCal'))}<span>{html.escape(site.get('tagline', ''))}</span></a>
  <nav>{links}</nav>
</div>
{stamp_html}"""


def _publisher(cfg: dict[str, Any]) -> dict[str, Any]:
    s = cfg.get("site") or {}
    return {"@type": "Organization", "name": s.get("operator") or s.get("title", "VisaCal"),
            "url": canonical_url(cfg)}


def jsonld_site(cfg: dict[str, Any]) -> str:
    """홈에 넣는 사이트 정보. 검색 결과에 사이트명과 운영 주체를 알립니다."""
    s = cfg.get("site") or {}
    data = {
        "@context": "https://schema.org",
        "@type": "WebSite",
        "name": s.get("title", "VisaCal"),
        "url": canonical_url(cfg),
        "inLanguage": "ko",
        "publisher": _publisher(cfg),
    }
    return json.dumps(data, ensure_ascii=False)


def jsonld_article(cfg: dict[str, Any], title: str, description: str, path: str,
                   published: str, image: str = "") -> str:
    """글 페이지의 구조화 데이터. 발행일과 작성 주체를 명시합니다."""
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": title[:110],
        "description": description,
        "inLanguage": "ko",
        "datePublished": published,
        "dateModified": published,
        "mainEntityOfPage": canonical_url(cfg, path),
        "author": _publisher(cfg),
        "publisher": _publisher(cfg),
    }
    if image:
        data["image"] = image if image.startswith("http") else canonical_url(cfg, image)
    return json.dumps(data, ensure_ascii=False)


def jsonld_tool(cfg: dict[str, Any], name: str, description: str, path: str) -> str:
    """계산기 페이지. 무료 웹 도구라는 점을 명시합니다."""
    data = {
        "@context": "https://schema.org",
        "@type": "WebApplication",
        "name": name,
        "description": description,
        "url": canonical_url(cfg, path),
        "applicationCategory": "BusinessApplication",
        "operatingSystem": "All",
        "inLanguage": "ko",
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "KRW"},
        "publisher": _publisher(cfg),
    }
    return json.dumps(data, ensure_ascii=False)


def ad(cfg: dict[str, Any], slot_key: str, css_class: str = "ad") -> str:
    ads = cfg.get("adsense") or {}
    client = ads.get("client_id") or ""
    slot = (ads.get("slots") or {}).get(slot_key) or ""
    if not (client and slot):
        return ""
    # 광고 표기를 붙여 본문과 구분합니다. 계산 결과로 오인되면 정책 위반입니다.
    return (
        f'<div class="{css_class}"><span class="ad-label">광고</span>'
        f'<ins class="adsbygoogle" style="display:block"'
        f' data-ad-client="{html.escape(client)}" data-ad-slot="{html.escape(slot)}"'
        ' data-ad-format="auto" data-full-width-responsive="true"></ins>'
        "<script>(adsbygoogle=window.adsbygoogle||[]).push({});</script></div>"
    )


def cta(cfg: dict[str, Any]) -> str:
    c = cfg.get("cta") or {}
    parts = []
    if c.get("paid_url"):
        price = f' <span class="p">{html.escape(str(c.get("paid_price", "")))}</span>' if c.get("paid_price") else ""
        parts.append(f'<a class="solid" href="{html.escape(c["paid_url"])}">{html.escape(c.get("paid_label", "정밀검토 신청"))}</a>')
        if price:
            parts.append(f'<div class="p">{html.escape(str(c.get("paid_price", "")))}</div>')
    if c.get("consult_url"):
        parts.append(f'<a href="{html.escape(c["consult_url"])}">{html.escape(c.get("consult_label", "사건 검토 요청"))}</a>')
    if not parts:
        return ""
    return f'<div class="cta">{"".join(parts)}</div>'


def lead_form(cfg: dict[str, Any], topic: str = "") -> str:
    """문의 폼. Formspree 주소가 없으면 메일 링크로 대체합니다.

    광고 수익보다 이쪽이 큽니다. 계산 결과를 보고 불안해진 사람이
    그 자리에서 연락할 수 있어야 합니다.
    """
    c = cfg.get("cta") or {}
    s = cfg.get("site") or {}
    endpoint = c.get("form_endpoint") or ""
    email = s.get("contact_email", "")
    fields = c.get("form_fields") or {}
    f_name = html.escape(fields.get("name", "name"))
    f_contact = html.escape(fields.get("contact", "contact"))
    f_detail = html.escape(fields.get("detail", "detail"))
    is_google = "docs.google.com/forms" in endpoint

    if not endpoint:
        if not email:
            return ""
        subject = f"[VisaCal] {topic} 검토 요청" if topic else "[VisaCal] 검토 요청"
        return f"""<div class="lead-form">
<h3>사건 검토 요청</h3>
<div class="sd">계산 결과가 경계선에 가깝거나 판단이 갈리는 경우, 실제 서류를 보고 확인해야 합니다.</div>
<a href="mailto:{html.escape(email)}?subject={html.escape(subject)}" style="display:block;text-align:center;
  background:#14243c;color:#fff;text-decoration:none;padding:12px;font-weight:600;border-radius:2px">메일로 문의</a>
<div class="fine">{html.escape(s.get('operator',''))} · 회신까지 영업일 기준 1일에서 2일 걸립니다.</div>
</div>"""

    return f"""<div class="lead-form">
<h3>사건 검토 요청</h3>
<div class="sd">계산 결과가 경계선에 가깝거나 판단이 갈리는 경우, 실제 서류를 보고 확인해야 합니다.</div>
<form action="{html.escape(endpoint)}" method="POST"{' target="_blank"' if is_google else ''}>
  {'' if is_google else f'<input type="hidden" name="_subject" value="[VisaCal] {html.escape(topic or "검토 요청")}">'}
  <div class="g">
    <input type="text" name="{f_name}" placeholder="성함" required>
    <input type="text" name="{f_contact}" placeholder="연락처 또는 이메일" required>
  </div>
  <textarea name="{f_detail}" placeholder="비자 종류, 진행 단계, 확인하고 싶은 내용을 적어주십시오." required>{html.escape(("[" + topic + "] ") if topic else "")}</textarea>
  <button type="submit">검토 요청 보내기</button>
</form>
<div class="fine">보내주신 내용은 문의 처리와 수임 검토 목적으로만 사용합니다.
회신까지 영업일 기준 1일에서 2일 걸립니다.</div>
</div>"""


def footer(cfg: dict[str, Any], extra: str = "") -> str:
    site = cfg.get("site", {})
    operator = html.escape(site.get("operator", ""))
    email = html.escape(site.get("contact_email", ""))
    return f"""<footer>
<div class="disc">{extra}이 사이트의 계산 결과는 공개된 정부 자료를 근거로 한 참고용 추정이며 법률 자문이 아닙니다.
실제 신청 전에는 반드시 담당 변호사의 검토를 받으십시오. 계산 결과로 발생한 손해에 대해 책임지지 않습니다.</div>
<div>{operator}{' · ' if operator and email else ''}{email} · <a href="privacy.html">개인정보처리방침</a></div>
</footer>
</div></body></html>"""
