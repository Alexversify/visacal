"""소스별 수집 모듈.

설계 원칙
1. Federal Register API는 공개 JSON API라 차단이 없습니다. 시행 전 단계를 여기서 잡습니다.
2. USCIS는 봇 차단이 걸려 있어 requests로는 실패합니다. Playwright 실제 브라우저로 접근합니다.
3. 수집 실패는 예외를 던지지 않고 error 필드에 담아 반환합니다. 한 소스가 죽어도 나머지는 돌아야 합니다.
"""

from __future__ import annotations

import datetime as dt
import io
import re
from typing import Any

import requests

FR_API = "https://www.federalregister.gov/api/v1/documents.json"
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/129.0.0.0 Safari/537.36"
)


# ---------------------------------------------------------------- Federal Register


def fetch_federal_register(cfg: dict[str, Any]) -> dict[str, Any]:
    """수수료 관련 규칙 제정 문서를 조회합니다. 시행일이 미래인 건이 '변경 예정'입니다."""
    since = (dt.date.today() - dt.timedelta(days=cfg.get("lookback_days", 14))).isoformat()
    params = [
        ("conditions[publication_date][gte]", since),
        ("conditions[term]", " OR ".join(cfg.get("keywords", ["fee"]))),
        ("order", "newest"),
        ("per_page", "50"),
    ]
    for agency in cfg.get("agencies", []):
        params.append(("conditions[agencies][]", agency))
    for doc_type in cfg.get("types", []):
        params.append(("conditions[type][]", doc_type))
    for field in (
        "document_number",
        "title",
        "type",
        "publication_date",
        "effective_on",
        "comments_close_on",
        "abstract",
        "html_url",
        "agencies",
    ):
        params.append(("fields[]", field))

    try:
        res = requests.get(FR_API, params=params, timeout=30, headers={"User-Agent": UA})
        res.raise_for_status()
        docs = res.json().get("results", []) or []
    except Exception as exc:  # noqa: BLE001
        return {"source": "federal_register", "error": str(exc), "items": []}

    today = dt.date.today()
    items = []
    for doc in docs:
        effective = doc.get("effective_on")
        upcoming = bool(effective and dt.date.fromisoformat(effective) > today)
        items.append(
            {
                "key": doc.get("document_number"),
                "title": doc.get("title"),
                "doc_type": doc.get("type"),
                "published": doc.get("publication_date"),
                "effective_on": effective,
                "comments_close_on": doc.get("comments_close_on"),
                "upcoming": upcoming,
                "abstract": (doc.get("abstract") or "")[:1200],
                "url": doc.get("html_url"),
            }
        )
    return {"source": "federal_register", "error": None, "items": items}


# ---------------------------------------------------------------- USCIS G-1055


def _browser_text(url: str, selector: str | None = None) -> tuple[str, list[str], str]:
    """Playwright로 페이지를 열어 (본문텍스트, 선택자매칭텍스트목록, 최종URL)을 반환합니다."""
    from playwright.sync_api import sync_playwright

    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--disable-blink-features=AutomationControlled"])
        context = browser.new_context(user_agent=UA, locale="en-US", viewport={"width": 1400, "height": 1000})
        page = context.new_page()
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(3000)
        body = page.inner_text("body")
        blocks: list[str] = []
        if selector:
            for el in page.query_selector_all(selector):
                text = (el.inner_text() or "").strip()
                if text:
                    blocks.append(re.sub(r"\s+", " ", text))
        hrefs = [a.get_attribute("href") or "" for a in page.query_selector_all("a")]
        final_url = page.url
        context.close()
        browser.close()
    _browser_text.last_hrefs = hrefs  # type: ignore[attr-defined]
    return body, blocks, final_url


def fetch_uscis_g1055(cfg: dict[str, Any]) -> dict[str, Any]:
    """G-1055 페이지의 alert 블록과 PDF edition date를 수집합니다."""
    url = cfg["g1055_url"]
    try:
        body, blocks, _ = _browser_text(url, cfg.get("alert_selector"))
    except Exception as exc:  # noqa: BLE001
        return {"source": "uscis_g1055", "error": str(exc), "alerts": [], "edition": None, "pdf_url": None}

    # alert 블록 후보에서 중복과 껍데기를 제거합니다.
    alerts: list[str] = []
    for text in blocks:
        if len(text) < 60:
            continue
        if not re.search(r"\balert\b", text, re.I) and not re.search(r"\b(court|fee|edition|rule)\b", text, re.I):
            continue
        if any(text in existing for existing in alerts):
            continue
        alerts = [a for a in alerts if a not in text]
        alerts.append(text)

    edition = None
    match = re.search(r"edition[^.]{0,40}?(\d{2}/\d{2}/\d{2,4})", body, re.I)
    if match:
        edition = match.group(1)

    hrefs = getattr(_browser_text, "last_hrefs", [])
    pat = cfg.get("pdf_link_pattern", "g-1055")
    pdf_url = next(
        (h if h.startswith("http") else f"https://www.uscis.gov{h}" for h in hrefs if pat in h.lower() and h.lower().endswith(".pdf")),
        None,
    )

    return {
        "source": "uscis_g1055",
        "error": None,
        "alerts": alerts[:12],
        "edition": edition,
        "pdf_url": pdf_url,
    }


def fetch_g1055_pdf_fees(pdf_url: str | None) -> dict[str, Any]:
    """G-1055 PDF에서 양식별 금액을 추출합니다. HTML보다 구조가 안정적입니다."""
    if not pdf_url:
        return {"source": "uscis_g1055_pdf", "error": "pdf_url 없음", "rows": []}
    try:
        import pdfplumber

        res = requests.get(pdf_url, timeout=60, headers={"User-Agent": UA})
        res.raise_for_status()
        rows: list[dict[str, Any]] = []
        with pdfplumber.open(io.BytesIO(res.content)) as pdf:
            for page in pdf.pages:
                for table in page.extract_tables() or []:
                    for row in table:
                        cells = [(c or "").replace("\n", " ").strip() for c in row]
                        line = " | ".join(c for c in cells if c)
                        if not re.search(r"\$[\d,]+", line):
                            continue
                        form = re.search(r"\b([A-Z]{1,3}-\d{2,4}[A-Z]?)\b", line)
                        amounts = [int(a.replace(",", "")) for a in re.findall(r"\$([\d,]+)", line)]
                        rows.append(
                            {
                                "form": form.group(1) if form else None,
                                "amounts": amounts,
                                "line": line[:300],
                            }
                        )
        return {"source": "uscis_g1055_pdf", "error": None, "rows": rows}
    except Exception as exc:  # noqa: BLE001
        return {"source": "uscis_g1055_pdf", "error": str(exc), "rows": []}


# ---------------------------------------------------------------- 국무부


def fetch_state_fees(cfg: dict[str, Any]) -> dict[str, Any]:
    """대사관 수수료(MRV, 상호주의)는 국무부 소관이라 별도 트랙으로 봅니다."""
    out: dict[str, Any] = {"source": "state_dept", "error": None, "rows": [], "reciprocity_kr": []}
    try:
        body, _, _ = _browser_text(cfg["fees_url"])
        for line in body.splitlines():
            line = line.strip()
            if not line or not re.search(r"\$\d", line):
                continue
            amounts = [int(a.replace(",", "")) for a in re.findall(r"\$([\d,]+)", line)]
            out["rows"].append({"line": line[:240], "amounts": amounts})
    except Exception as exc:  # noqa: BLE001
        out["error"] = str(exc)
    return out
