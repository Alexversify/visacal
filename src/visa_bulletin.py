"""미 국무부 비자 문호(Visa Bulletin) 수집.

`python -m src.visa_bulletin` 으로 실행합니다. 매일 돌지만 새 달 문호가 나왔을 때만 일을 합니다.

수집 순서 (앞에서 성공하면 뒤는 건너뜀)
1. 수동 투입함 content/visa-bulletin/inbox/ 의 .txt/.html (원문 페이지를 저장하거나 복사해 넣은 것)
2. 국무부 원문 페이지. travel.state.gov 는 Cloudflare 보안 확인을 걸어 두어 GitHub 서버에서는 보통 막힙니다.
   막히면 막혔다고 기록만 하고 넘어갑니다. 보안 확인을 우회하지 않습니다
3. 메일함(IMAP). 국무부 Visa Bulletin 메일링을 구독한 메일함에서 원문 메일을 읽습니다

파싱 원칙
- 원문 텍스트에서 표 4개(가족·취업 × 최종조치일·접수가능일)를 찾고, 행마다 값 5개(전 세계, 중국, 인도, 멕시코, 필리핀)를 읽습니다
- 행이 하나라도 빠지거나 값이 5개가 아니면 그 달은 게시하지 않고 실패로 알립니다. 추정으로 채우지 않습니다
- 원문 텍스트는 data/visa_bulletin/raw/ 에 남겨 나중에 대조할 수 있게 합니다

결과
- data/visa_bulletin/YYYY-MM.json 달별 데이터
- 가장 최신 달이 새로 들어오면 6개 언어 요약(LLM, 실패 시 고정 문구), 소식 글(content/posts), 팀 메일
"""

from __future__ import annotations

import datetime as dt
import email
import email.policy
import html as htmlmod
import imaplib
import json
import os
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import vb_i18n as I  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "visa_bulletin"
RAW = DATA / "raw"
INBOX = ROOT / "content" / "visa-bulletin" / "inbox"
POSTS = ROOT / "content" / "posts"
KST = dt.timezone(dt.timedelta(hours=9))

BASE = "https://travel.state.gov/content/travel/en/legal/visa-law0/visa-bulletin"
INDEX_URL = BASE + ".html"
USCIS_CHART_URL = (
    "https://www.uscis.gov/green-card/green-card-processes-and-procedures/"
    "visa-availability-priority-dates/adjustment-of-status-filing-charts-from-the-visa-bulletin"
)
UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
MODEL = "claude-sonnet-5"
MONTHS = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST",
          "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]

# ---------------------------------------------------------------- 텍스트 변환


class _TableText(HTMLParser):
    """HTML을 텍스트로. 표는 칸 사이 탭, 행마다 줄바꿈으로 둡니다."""

    BLOCK = {"p", "div", "br", "h1", "h2", "h3", "h4", "h5", "li", "tr", "table", "section"}

    def __init__(self) -> None:
        super().__init__()
        self.out: list[str] = []
        self.skip = 0

    def handle_starttag(self, tag, attrs):  # noqa: ANN001
        if tag in ("script", "style", "noscript"):
            self.skip += 1
        elif tag in ("td", "th"):
            self.out.append("\t")
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_endtag(self, tag):  # noqa: ANN001
        if tag in ("script", "style", "noscript"):
            self.skip = max(0, self.skip - 1)
        elif tag in self.BLOCK:
            self.out.append("\n")

    def handle_data(self, data):  # noqa: ANN001
        if not self.skip:
            self.out.append(data)


def html_to_text(raw: str) -> str:
    p = _TableText()
    p.feed(raw)
    text = htmlmod.unescape("".join(p.out)).replace("\xa0", " ")
    text = re.sub(r"[ \r\f\v]+", " ", text)
    return re.sub(r"\n\s*\n+", "\n", text)


def looks_blocked(text: str) -> bool:
    t = text[:4000].lower()
    return any(k in t for k in ("just a moment", "cf-chl", "challenge-platform", "verify you are human",
                                "보안 확인", "잠시만 기다리십시오", "attention required"))


# ---------------------------------------------------------------- 파싱

SECTIONS = {
    "fam_final": r"A\.\s*FINAL\s+ACTION\s+DATES\s+FOR\s+FAMILY[\s\-]*SPONSORED",
    "fam_filing": r"B\.\s*DATES\s+FOR\s+FILING\s+(?:OF\s+)?FAMILY[\s\-]*SPONSORED",
    "emp_final": r"A\.\s*FINAL\s+ACTION\s+DATES\s+FOR\s+EMPLOYMENT[\s\-]*BASED",
    "emp_filing": r"B\.\s*DATES\s+FOR\s+FILING\s+(?:OF\s+)?EMPLOYMENT[\s\-]*BASED",
}

# 행 이름. 표 안에서 처음 나오는 것만 씁니다.
ROW_PATTERNS = {
    "F1": r"(?<![A-Z0-9])F1(?![A-Z0-9])",
    "F2A": r"(?<![A-Z0-9])F2A(?![A-Z0-9])",
    "F2B": r"(?<![A-Z0-9])F2B(?![A-Z0-9])",
    "F3": r"(?<![A-Z0-9])F3(?![A-Z0-9])",
    "F4": r"(?<![A-Z0-9])F4(?![A-Z0-9])",
    "EB1": r"(?<![A-Za-z0-9])1st(?![A-Za-z0-9])",
    "EB2": r"(?<![A-Za-z0-9])2nd(?![A-Za-z0-9])",
    "EB3": r"(?<![A-Za-z0-9])3rd(?![A-Za-z0-9])",
    "EW": r"Other\s+Workers",
    "EB4": r"(?<![A-Za-z0-9])4th(?![A-Za-z0-9])",
    "RW": r"Certain\s+Religious\s+Workers",
    "EB5U": r"5th\s+Unreserved",
    "EB5R": r"Rural",
    "EB5H": r"High\s+Unemployment",
    "EB5I": r"Infrastructure",
}
VALUE = re.compile(r"(?<![A-Za-z0-9])(\d{2}[A-Z]{3}\d{2}|C|U)(?![A-Za-z0-9])")
MON3 = {m[:3]: i + 1 for i, m in enumerate(MONTHS)}


class ParseError(ValueError):
    pass


def norm_value(tok: str, bulletin_year: int) -> str:
    if tok in ("C", "U"):
        return tok
    d, mon, yy = int(tok[:2]), MON3.get(tok[2:5]), int(tok[5:])
    if not mon:
        raise ParseError(f"알 수 없는 월 표기: {tok}")
    year = 2000 + yy if 2000 + yy <= bulletin_year + 1 else 1900 + yy
    return dt.date(year, mon, d).isoformat()


def detect_month(text: str) -> tuple[int, int] | None:
    m = re.search(r"VISA\s+BULLETIN\s+FOR\s+([A-Za-z]+)\s+(\d{4})", text, re.I)
    if not m:
        return None
    name = m.group(1).upper()
    if name not in MONTHS:
        return None
    return int(m.group(2)), MONTHS.index(name) + 1


def _segments(text: str) -> dict[str, str]:
    found: list[tuple[int, str]] = []
    for key, pat in SECTIONS.items():
        m = re.search(pat, text, re.I)
        if not m:
            raise ParseError(f"표 제목을 찾지 못함: {key}")
        found.append((m.start(), key))
    found.sort()
    segs = {}
    for i, (pos, key) in enumerate(found):
        end = found[i + 1][0] if i + 1 < len(found) else pos + 9000
        segs[key] = text[pos:end]
    return segs


def _parse_chart(seg: str, rows: list[str], year: int) -> tuple[dict[str, list[str]], int]:
    # 열 순서 확인. 국무부가 열 구성을 바꾸면 여기서 멈춥니다.
    head = seg[:3000].upper()
    order = [head.find(k) for k in ("CHINA", "INDIA", "MEXICO", "PHILIPPINES")]
    if min(order) < 0 or order != sorted(order):
        raise ParseError("열 머리(CHINA, INDIA, MEXICO, PHILIPPINES) 순서가 예상과 다름")
    labels = {k: re.compile(ROW_PATTERNS[k], re.I if k.startswith("E") else 0) for k in rows}
    out: dict[str, list[str]] = {}
    end = 0
    for key, rx in labels.items():
        m = rx.search(seg, max(order))
        if not m:
            raise ParseError(f"행을 찾지 못함: {key}")
        # 다음 행 이름이 나오기 전까지, 최대 400자 안에서 값 5개
        window = seg[m.end(): m.end() + 400]
        stop = len(window)
        for other, orx in labels.items():
            if other == key:
                continue
            om = orx.search(window)
            if om and om.start() > 0:
                stop = min(stop, om.start())
        found = list(VALUE.finditer(window[:stop]))
        if len(found) < 5:
            raise ParseError(f"{key} 행 값이 5개가 아님: {[f.group(1) for f in found]}")
        out[key] = [norm_value(f.group(1), year) for f in found[:5]]
        end = max(end, m.end() + found[4].end())
    return out, end


def parse_bulletin(text: str, month: tuple[int, int] | None = None) -> dict[str, Any]:
    """원문 텍스트 → 표 4개. 실패하면 ParseError."""
    month = month or detect_month(text)
    if not month:
        raise ParseError("문호 연월(VISA BULLETIN FOR ...)을 찾지 못함")
    year = month[0]
    segs = _segments(text)
    charts: dict[str, dict[str, list[str]]] = {}
    notes_parts = []
    for key, rows in (("fam_final", I.FAMILY_ROWS), ("fam_filing", I.FAMILY_ROWS),
                      ("emp_final", I.EMP_ROWS), ("emp_filing", I.EMP_ROWS)):
        charts[key], end = _parse_chart(segs[key], rows, year)
        # 표 바로 뒤 공지(F2A 예외, 소급 예고 등). 요약에만 쓰고 그대로 게시하지 않습니다.
        tail = segs[key][end:].strip()
        if tail:
            notes_parts.append(tail[:3000] if key != "emp_filing" else tail[:6000])
    notes = "\n\n".join(notes_parts)[:9000]
    return {"year": month[0], "month": month[1], "charts": charts, "notes": notes}


# ---------------------------------------------------------------- 변동 비교

def _days(a: str, b: str) -> int:
    return (dt.date.fromisoformat(b) - dt.date.fromisoformat(a)).days


def diff(prev: dict[str, Any] | None, cur: dict[str, Any]) -> list[dict[str, Any]]:
    if not prev:
        return []
    out = []
    for chart, rows in cur["charts"].items():
        for row, vals in rows.items():
            old = (prev.get("charts", {}).get(chart) or {}).get(row)
            if not old:
                continue
            for i, (a, b) in enumerate(zip(old, vals)):
                if a == b:
                    continue
                if b == "C":
                    kind = "to_c"
                elif a == "C":
                    kind = "from_c"
                elif b == "U":
                    kind = "to_u"
                elif a == "U":
                    kind = "from_u"
                else:
                    kind = "adv" if _days(a, b) > 0 else "ret"
                item = {"chart": chart, "row": row, "col": I.COLS[i], "a": a, "b": b, "kind": kind}
                if kind in ("adv", "ret"):
                    item["d"] = abs(_days(a, b))
                out.append(item)
    return out


def change_line(lang: str, c: dict[str, Any]) -> str:
    return I.t(lang, c["kind"], cat=I.SHORT[c["row"]], col=I.t(lang, c["col"]),
               a=c["a"], b=c["b"], d=c.get("d", 0))


# ---------------------------------------------------------------- 저장소


def month_key(y: int, m: int) -> str:
    return f"{y:04d}-{m:02d}"


def load_all() -> list[dict[str, Any]]:
    if not DATA.exists():
        return []
    items = []
    for p in sorted(DATA.glob("????-??.json")):
        try:
            items.append(json.loads(p.read_text(encoding="utf-8")))
        except Exception:  # noqa: BLE001
            continue
    return items


def load(key: str) -> dict[str, Any] | None:
    p = DATA / f"{key}.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def previous(key: str) -> dict[str, Any] | None:
    keys = sorted(p.stem for p in DATA.glob("????-??.json")) if DATA.exists() else []
    older = [k for k in keys if k < key]
    return load(older[-1]) if older else None


def official_url(y: int, m: int) -> str:
    fy = y + 1 if m >= 10 else y
    return f"{BASE}/{fy}/visa-bulletin-for-{MONTHS[m - 1].lower()}-{y}.html"


# ---------------------------------------------------------------- 수집원


def from_inbox() -> list[tuple[str, str, str]]:
    """(원문 텍스트, 출처 설명, 파일 경로) 목록."""
    out = []
    if not INBOX.exists():
        return out
    for p in sorted(INBOX.iterdir()):
        if p.suffix.lower() not in (".txt", ".html", ".htm"):
            continue
        raw = p.read_text(encoding="utf-8", errors="replace")
        text = html_to_text(raw) if p.suffix.lower() != ".txt" or "<table" in raw.lower() else raw
        out.append((text, "manual", str(p)))
    return out


def _http_text(url: str) -> str:
    import requests

    r = requests.get(url, headers={"User-Agent": UA, "Accept-Language": "en-US"}, timeout=40)
    if r.status_code == 404:
        raise FileNotFoundError(url)
    body = html_to_text(r.text)
    if r.status_code >= 400 or looks_blocked(body):
        raise PermissionError(f"보안 확인 또는 차단 (HTTP {r.status_code})")
    return body


def from_official(y: int, m: int) -> str:
    """국무부 원문. 차단되면 PermissionError. 보안 확인을 풀려고 시도하지 않습니다."""
    return _http_text(official_url(y, m))


def from_mailbox(since_days: int = 60) -> list[tuple[str, str]]:
    """국무부 Visa Bulletin 메일. (텍스트, 메일 제목) 목록."""
    user = os.environ.get("VB_IMAP_USER") or ""
    pw = os.environ.get("VB_IMAP_PASS") or ""
    host = os.environ.get("VB_IMAP_HOST") or ""
    if not (user and pw):
        # 발송용 Gmail을 그대로 쓰는 경우
        if "gmail" in (os.environ.get("SMTP_HOST") or "") or (os.environ.get("SMTP_USER") or "").endswith("@gmail.com"):
            user, pw = os.environ.get("SMTP_USER", ""), os.environ.get("SMTP_PASS", "")
            host = host or "imap.gmail.com"
    if not (user and pw):
        return []
    host = host or "imap.gmail.com"
    out = []
    since = (dt.date.today() - dt.timedelta(days=since_days)).strftime("%d-%b-%Y")
    box = imaplib.IMAP4_SSL(host)
    try:
        box.login(user, pw)
        box.select("INBOX", readonly=True)
        _, data = box.search(None, f'(SINCE {since} SUBJECT "Visa Bulletin")')
        for num in (data[0].split() if data and data[0] else [])[-10:]:
            _, msg_data = box.fetch(num, "(RFC822)")
            msg = email.message_from_bytes(msg_data[0][1], policy=email.policy.default)
            sender = str(msg.get("From", "")).lower()
            if "state.gov" not in sender:
                continue
            part = msg.get_body(preferencelist=("plain", "html"))
            if not part:
                continue
            body = part.get_content()
            if part.get_content_type() == "text/html":
                body = html_to_text(body)
            out.append((body, str(msg.get("Subject", ""))))
    finally:
        try:
            box.logout()
        except Exception:  # noqa: BLE001
            pass
    return out


def uscis_charts(y: int, m: int) -> dict[str, str | None]:
    """USCIS가 그달 신분조정에 쓰라고 지정한 차트. 확실히 읽힐 때만 값을 넣습니다."""
    res: dict[str, str | None] = {"family": None, "employment": None}
    try:
        text = _http_text(USCIS_CHART_URL)
    except Exception as exc:  # noqa: BLE001
        print(f"  - USCIS 차트 안내 수집 실패: {exc}")
        return res
    name = f"{MONTHS[m - 1].title()} {y}"
    pos = text.find(name)
    if pos < 0:
        return res
    chunk = text[pos: pos + 2500]
    for key, word in (("family", "Family"), ("employment", "Employment")):
        mm = re.search(word + r"[^\n]{0,400}?(Final Action Dates|Dates for Filing)", chunk, re.I | re.S)
        if mm:
            res[key] = "final" if "final" in mm.group(1).lower() else "filing"
    return res


# ---------------------------------------------------------------- 요약 (6개 언어)

SUMMARY_SYSTEM = """당신은 미국 이민 법무법인의 실무 담당자입니다. 미 국무부 Visa Bulletin의 이번 달 변동을 6개 언어로 요약합니다.

규칙
- 입력에 있는 사실만 씁니다. 다음 달 전망, 추측, 권유를 쓰지 않습니다
- 날짜와 범주 이름은 입력 그대로 씁니다
- 한국어(ko)는 한국 출생 신청자 관점(전 세계 열)을 먼저 다룹니다. 줄표(—, –)를 쓰지 않고, "아울러"를 쓰지 않습니다
- 다른 언어도 같은 내용을 자연스럽게 옮깁니다. 기계 번역투를 피합니다
- headline 40자 안팎(영어 90자 이내), summary 2~3문장, points 3~5개
- 출력은 JSON 하나만: {"ko":{"headline":"","summary":"","points":[]},"en":{...},"zh":{...},"ja":{...},"vi":{...},"es":{...}}
"""


def _fallback_summary(rec: dict[str, Any], changes: list[dict[str, Any]], has_prev: bool) -> dict[str, Any]:
    finals = [c for c in changes if c["chart"].endswith("final")]
    out = {}
    for lang in I.LANGS:
        n = len(finals)
        head = I.t(lang, "headline_auto" if n else "headline_none", y=rec["year"], m=rec["month"], n=n)
        pts = [change_line(lang, c) for c in finals if c["col"] == "row"][:5]
        if not has_prev:
            summ = I.t(lang, "changes_first")
        elif not changes:
            summ = I.t(lang, "changes_none")
        else:
            summ = ""
        out[lang] = {"headline": head, "summary": summ, "points": pts, "auto": False}
    return out


def summarize(rec: dict[str, Any], changes: list[dict[str, Any]], has_prev: bool) -> dict[str, Any]:
    base = _fallback_summary(rec, changes, has_prev)
    try:
        from src import llm

        if not llm.enabled():
            print("  - 요약: LLM 설정 없음, 고정 문구 사용")
            return base
        row = {k: v[0] for ch in ("fam_final", "emp_final") for k, v in rec["charts"][ch].items()}
        payload = {
            "bulletin": month_key(rec["year"], rec["month"]),
            "all_chargeability_final_action": row,
            "changes": changes[:80],
            "notices_excerpt": (rec.get("notes") or "")[:5000],
            "uscis_chart": rec.get("uscis"),
        }
        text = llm.complete(SUMMARY_SYSTEM, json.dumps(payload, ensure_ascii=False), MODEL, timeout=400)
        m = re.search(r"\{.*\}", text, re.S)
        data = json.loads(m.group(0)) if m else {}
        for lang in I.LANGS:
            d = data.get(lang) or {}
            if not (isinstance(d.get("headline"), str) and isinstance(d.get("points"), list)):
                continue
            item = {
                "headline": d["headline"].strip()[:140],
                "summary": str(d.get("summary") or "").strip()[:900],
                "points": [str(p).strip()[:300] for p in d["points"][:6] if str(p).strip()],
                "auto": True,
            }
            if lang == "ko":
                for k in ("headline", "summary"):
                    item[k] = re.sub(r"\s*[—–]\s*", ", ", item[k]).replace("아울러 ", "").replace("아울러", "")
                item["points"] = [re.sub(r"\s*[—–]\s*", ", ", p).replace("아울러", "") for p in item["points"]]
            base[lang] = item
        print("  - 요약: 6개 언어 작성 완료")
    except Exception as exc:  # noqa: BLE001
        print(f"  - 요약 실패, 고정 문구 사용: {str(exc)[:200]}")
    return base


# ---------------------------------------------------------------- 소식 글, 메일


def write_post(rec: dict[str, Any], changes: list[dict[str, Any]], today: dt.date) -> Path:
    key = month_key(rec["year"], rec["month"])
    s = rec["summary"]["ko"]
    finals = [c for c in changes if c["chart"].endswith("final") and c["col"] == "row"]
    lines = "\n".join(f"- {change_line('ko', c)}" for c in finals[:10])
    points = "\n".join(f"- {p}" for p in s.get("points", []))
    body = f"""{s.get('summary') or ''}

## 핵심 내용

{points or '- ' + I.t('ko', 'changes_none')}

## 전 세계(한국 포함) 열 최종조치일 변동

{lines or '- 변동 없음'}

[전체 표, 접수가능일, 6개 언어 버전 보기](/visa-bulletin/{key}/)

원문: [미 국무부 Visa Bulletin]({rec['source_url']})
"""
    title = s.get("headline") or I.t("ko", "title", y=rec["year"], m=rec["month"])
    summary = s.get("summary") or I.t("ko", "desc", y=rec["year"], m=rec["month"])
    front = {
        "title": title,
        "slug": f"visa-bulletin-{key}",
        "date": today.isoformat(),
        "category": "비자 문호",
        "summary": summary.split("\n")[0][:200],
        "cover": "",
        "draft": False,
    }
    import yaml

    POSTS.mkdir(parents=True, exist_ok=True)
    path = POSTS / f"{today.isoformat()}-visa-bulletin-{key}.md"
    path.write_text("---\n" + yaml.safe_dump(front, allow_unicode=True, sort_keys=False) + "---\n\n" + body,
                    encoding="utf-8")
    return path


def _site_url() -> str:
    return (os.environ.get("PAGES_URL") or "https://visacal.com").rstrip("/")


def notify_new(rec: dict[str, Any], changes: list[dict[str, Any]]) -> None:
    from src import notify

    key = month_key(rec["year"], rec["month"])
    s = rec["summary"]["ko"]
    finals = [c for c in changes if c["chart"].endswith("final")]
    body = "\n".join([
        s.get("headline", ""),
        "",
        s.get("summary", ""),
        "",
        *[f"- {p}" for p in s.get("points", [])],
        "",
        "[최종조치일 변동]",
        *([f"- {change_line('ko', c)}" for c in finals] or ["- 변동 없음"]),
        "",
        f"사이트: {_site_url()}/visa-bulletin/{key}/",
        f"원문: {rec['source_url']}",
    ])
    subject = f"[비자 문호] {rec['year']}년 {rec['month']}월 발표: {s.get('headline', '')}"[:150]
    for env in ("MAIL_TO_PROCESSING", "MAIL_TO_SALES"):
        to = [a.strip() for a in (os.environ.get(env) or "").split(",") if a.strip()]
        if to:
            try:
                notify._send_mail(to, subject, body)
            except Exception as exc:  # noqa: BLE001
                print(f"  - 메일 실패({env}): {exc}")


def notify_failure(month: str, reasons: list[str]) -> None:
    """같은 달 실패 알림은 하루 한 번만. data/visa_bulletin/status.json 으로 관리."""
    from src import notify

    st_path = DATA / "status.json"
    st = json.loads(st_path.read_text(encoding="utf-8")) if st_path.exists() else {}
    today = dt.datetime.now(KST).date().isoformat()
    st.update({"pending": month, "last_try": dt.datetime.now(KST).isoformat(timespec="minutes"), "reasons": reasons})
    already = st.get("alerted") == f"{month}:{today}"
    st["alerted"] = f"{month}:{today}"
    DATA.mkdir(parents=True, exist_ok=True)
    st_path.write_text(json.dumps(st, ensure_ascii=False, indent=2), encoding="utf-8")
    if already:
        return
    to = [a.strip() for a in (os.environ.get("VB_ALERT_TO") or os.environ.get("MAIL_TO_PROCESSING") or "").split(",") if a.strip()]
    if to:
        body = (
            f"{month} 비자 문호를 아직 가져오지 못했습니다.\n\n" + "\n".join(f"- {r}" for r in reasons) +
            "\n\n바로 반영하려면 원문 페이지를 열어 전체 선택 후 복사한 텍스트를 "
            "content/visa-bulletin/inbox/ 에 .txt 로 넣으면 다음 실행 때 게시됩니다."
        )
        try:
            notify._send_mail(to, f"[비자 문호] {month} 수집 대기", body)
        except Exception as exc:  # noqa: BLE001
            print(f"  - 실패 알림 메일 실패: {exc}")


# ---------------------------------------------------------------- 실행


def ingest(text: str, source: str, want: str | None = None) -> dict[str, Any]:
    month = tuple(map(int, want.split("-"))) if want else None
    rec = parse_bulletin(text, month)  # type: ignore[arg-type]
    key = month_key(rec["year"], rec["month"])
    if want and key != want:
        raise ParseError(f"원하는 달({want})이 아니라 {key} 문호임")
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"{key}.txt").write_text(text, encoding="utf-8")
    rec.update({
        "key": key,
        "source": source,
        "source_url": official_url(rec["year"], rec["month"]),
        "fetched_at": dt.datetime.now(KST).isoformat(timespec="minutes"),
    })
    return rec


def save(rec: dict[str, Any]) -> None:
    DATA.mkdir(parents=True, exist_ok=True)
    keep = {k: v for k, v in rec.items() if k != "notes"}
    (DATA / f"{rec['key']}.json").write_text(json.dumps(keep, ensure_ascii=False, indent=2), encoding="utf-8")


def publish(rec: dict[str, Any], announce: bool) -> None:
    prev = previous(rec["key"])
    changes = diff(prev, rec)
    rec["changes"] = changes
    rec["prev_key"] = prev["key"] if prev else None
    rec["uscis"] = uscis_charts(rec["year"], rec["month"])
    rec["summary"] = summarize(rec, changes, bool(prev)) if announce else _fallback_summary(rec, changes, bool(prev))
    save(rec)
    print(f"  - {rec['key']} 저장 (출처 {rec['source']}, 변동 {len(changes)}건)")
    if announce:
        today = dt.datetime.now(KST).date()
        print(f"  - 소식 글: {write_post(rec, changes, today).name}")
        notify_new(rec, changes)


def targets(now: dt.datetime) -> list[str]:
    """이번 달과 다음 달. 국무부는 보통 전달 중순에 다음 달 문호를 냅니다."""
    y, m = now.year, now.month
    ny, nm = (y + 1, 1) if m == 12 else (y, m + 1)
    return [month_key(y, m), month_key(ny, nm)]


def main() -> int:
    now = dt.datetime.now(KST)
    have = {r["key"] for r in load_all()}
    latest_before = max(have) if have else ""
    added: list[dict[str, Any]] = []

    # 1. 수동 투입함. 어느 달이든 받습니다 (과거 달 보충 포함)
    for text, source, path in from_inbox():
        try:
            rec = ingest(text, source)
        except ParseError as exc:
            print(f"[inbox] {Path(path).name}: 파싱 실패, 그대로 둠: {exc}")
            continue
        added.append(rec)
        have.add(rec["key"])
        Path(path).unlink()
        print(f"[inbox] {Path(path).name} → {rec['key']}")

    missing = [k for k in targets(now) if k not in have]
    reasons: dict[str, list[str]] = {k: [] for k in missing}

    # 2. 국무부 원문
    for key in list(missing):
        y, m = map(int, key.split("-"))
        try:
            rec = ingest(from_official(y, m), "travel.state.gov", key)
            added.append(rec)
            missing.remove(key)
            print(f"[official] {key} 수집")
        except FileNotFoundError:
            reasons[key].append("국무부 원문 페이지 없음 (아직 미발표)")
        except PermissionError as exc:
            reasons[key].append(f"국무부 사이트 보안 확인으로 자동 접근 불가: {exc}")
        except ParseError as exc:
            reasons[key].append(f"국무부 원문 파싱 실패: {exc}")
        except Exception as exc:  # noqa: BLE001
            reasons[key].append(f"국무부 원문 수집 오류: {str(exc)[:160]}")

    # 3. 메일함
    if missing:
        try:
            mails = from_mailbox()
        except Exception as exc:  # noqa: BLE001
            mails = []
            for k in missing:
                reasons[k].append(f"메일함 접속 실패: {str(exc)[:160]}")
        for text, subject in mails:
            mo = detect_month(subject) or detect_month(text)
            key = month_key(*mo) if mo else ""
            if key not in missing:
                continue
            try:
                added.append(ingest(text, "email", key))
            except ParseError as exc:
                print(f"[mail] '{subject[:60]}' 파싱 실패: {exc}")
                continue
            missing.remove(key)
            print(f"[mail] {key} 수집")
        if not mails:
            for k in missing:
                reasons[k].append("메일함에 국무부 Visa Bulletin 메일 없음 또는 메일함 미설정")

    # 저장, 요약, 게시. 가장 최신이면서 기존보다 새 달만 알립니다.
    added.sort(key=lambda r: r["key"])
    for rec in added:
        announce = rec["key"] > latest_before and rec["key"] == added[-1]["key"]
        publish(rec, announce)

    # 다음 달 문호는 전달 중순 이후에 나오므로 그 전에는 실패로 보지 않습니다.
    nxt = targets(now)[1]
    cur = targets(now)[0]
    if cur in missing:
        notify_failure(cur, reasons[cur])
    elif nxt in missing and now.day >= 20:
        notify_failure(nxt, reasons[nxt])
    if not missing:
        st_path = DATA / "status.json"
        if st_path.exists():
            st_path.unlink()
    for k in missing:
        print(f"[대기] {k}: " + " / ".join(reasons[k]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
