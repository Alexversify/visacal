"""주한미국대사관 영사환율 수집.

AIS(ais.usvisa-info.com) 결제 화면에 표시되는 원화 환율을 그대로 가져옵니다.
대사관 MRV 수수료는 이 환율로 원화 결제되므로 시중 환율로 계산하면 금액이 어긋납니다.

실행: python -m src.consular_rate  (GitHub Actions consular-rate.yml)

공개 레포라는 점이 설계의 전제입니다.
- 결제 화면에는 신청인 정보가 있습니다. 스크린샷은 레포 밖 임시 폴더에만 만들고 실패 메일에 첨부한 뒤 지웁니다.
- Actions 로그와 data/ 파일도 공개됩니다. 화면 본문을 출력하지 않고, 오류 문구에서 URL과 이메일을 지웁니다.

저장
- data/consular_rate.json         rate, checked_at, changed_at, previous_rate (KST ISO)
- data/consular_rate_history.csv  date, rate. 하루 한 줄, 같은 날 재실행 시 덮어씁니다
  수집에 실패한 날은 rate를 비워 둡니다. 같은 날 성공 기록이 있으면 실패로 덮지 않습니다
- data/consular_fee_history.csv   date, fee_id, amount. 성공한 날의 원장 MRV 수수료. 원화 추이 그래프용
수집에 실패하면 json의 기존 값은 그대로 두고 last_error, failed_at 만 기록합니다.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import shutil
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
RATE_JSON = ROOT / "data" / "consular_rate.json"
HISTORY_CSV = ROOT / "data" / "consular_rate_history.csv"
FEE_HISTORY_CSV = ROOT / "data" / "consular_fee_history.csv"
FEES_JSON = ROOT / "data" / "fees.json"

SIGN_IN = "https://ais.usvisa-info.com/ko-kr/niv/users/sign_in"
KST = dt.timezone(dt.timedelta(hours=9))

RATE_PATTERNS = [
    re.compile(r"1\.00\s*USD\s*=\s*([\d,]+(?:\.\d+)?)\s*KRW"),
    re.compile(r"x\s*([\d,]+(?:\.\d+)?)\s*KRW\s*/\s*USD"),
]
# 화면 구조가 바뀌어 엉뚱한 숫자를 잡는 경우를 거릅니다.
RATE_RANGE = (500, 5000)


class RateError(Exception):
    """수집 실패. 메시지는 공개 json과 로그에 남으므로 신청인 정보를 담지 않습니다."""


# ---------------------------------------------------------------- 공용 (페이지 생성에서도 씀)


def now_kst() -> dt.datetime:
    return dt.datetime.now(KST).replace(microsecond=0)


def load_rate() -> dict[str, Any]:
    if not RATE_JSON.exists():
        return {}
    try:
        return json.loads(RATE_JSON.read_text(encoding="utf-8")) or {}
    except json.JSONDecodeError:
        return {}


def load_history_all() -> dict[str, float | None]:
    """날짜별 환율. 수집 실패한 날은 None."""
    if not HISTORY_CSV.exists():
        return {}
    rows: dict[str, float | None] = {}
    with HISTORY_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            d = (row.get("date") or "").strip()
            if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d):
                continue
            raw = (row.get("rate") or "").strip()
            try:
                rows[d] = float(raw) if raw else None
            except ValueError:
                continue
    return dict(sorted(rows.items()))


def load_history() -> list[tuple[str, float]]:
    """성공한 날만."""
    return [(d, r) for d, r in load_history_all().items() if r is not None]


def load_fee_history() -> dict[str, list[tuple[str, float]]]:
    """fee_id 별 [(날짜, USD 금액)]."""
    out: dict[str, list[tuple[str, float]]] = {}
    if not FEE_HISTORY_CSV.exists():
        return out
    with FEE_HISTORY_CSV.open(encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            try:
                out.setdefault(row["fee_id"], []).append((row["date"], float(row["amount"])))
            except (KeyError, TypeError, ValueError):
                continue
    return {k: sorted(v) for k, v in out.items()}


def fmt_rate(rate: float | None) -> str:
    if rate is None:
        return ""
    return f"{rate:,.0f}" if float(rate).is_integer() else f"{rate:,.2f}".rstrip("0").rstrip(".")


def krw(usd: float, rate: float) -> int:
    """결제창과 같은 방식. USD 금액 × 환율을 원 단위로 반올림합니다."""
    return int(round(usd * rate))


def mrv_fees(fees: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """원장의 대사관 MRV 수수료 중 금액이 확정된 신청인 본인 항목.

    동반가족 항목(-DEP)은 1인당 같은 금액이라 표에서 뺍니다. 금액이 null이면 넣지 않습니다.
    """
    if fees is None:
        fees = json.loads(FEES_JSON.read_text(encoding="utf-8"))
    rows = [
        f
        for f in fees.get("fees", [])
        if f.get("fee_id", "").startswith("DOS-MRV")
        and not f["fee_id"].endswith("-DEP")
        and f.get("amount") is not None
        and f.get("currency", "USD") == "USD"
        and f.get("status") == "시행중"
    ]
    return sorted(rows, key=lambda f: f["amount"])


# ---------------------------------------------------------------- 수집


def parse_rate(text: str) -> float:
    for pattern in RATE_PATTERNS:
        m = pattern.search(text)
        if m:
            rate = float(m.group(1).replace(",", ""))
            if not (RATE_RANGE[0] < rate < RATE_RANGE[1]):
                raise RateError(f"환율 값이 정상 범위를 벗어났습니다: {rate}")
            return rate
    raise RateError("결제 화면에서 환율 문구를 찾지 못했습니다. 화면 구조가 바뀌었을 수 있습니다.")


def _sanitize(message: str, secrets: list[str]) -> str:
    out = message
    for s in secrets:
        if s:
            out = out.replace(s, "<비공개>")
    out = re.sub(r"https?://\S+", "<URL>", out)
    out = re.sub(r"[\w.+-]+@[\w-]+\.[\w.]+", "<이메일>", out)
    out = " ".join(out.split())
    return out[:300]


def fetch_rate(email: str, password: str, payment_url: str, shot_dir: Path) -> float:
    from playwright.sync_api import sync_playwright

    from src.sources import UA

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale="ko-KR", user_agent=UA)
        page.set_default_timeout(60_000)
        try:
            page.goto(SIGN_IN, wait_until="domcontentloaded")
            page.fill("#user_email", email)
            page.fill("#user_password", password)
            # iCheck가 원래 체크박스를 숨기므로 클릭 대신 값을 직접 바꾸고 change를 알립니다.
            page.evaluate(
                """() => {
                  const c = document.querySelector('#policy_confirmed');
                  if (!c) return;
                  c.checked = true;
                  c.dispatchEvent(new Event('change', {bubbles: true}));
                }"""
            )
            page.click("input[name='commit']")
            try:
                page.wait_for_url(lambda u: "sign_in" not in u, timeout=60_000)
            except Exception as exc:  # noqa: BLE001
                raise RateError("로그인에 실패했습니다. 계정 정보, 약관 동의, 잠금 여부를 확인하십시오.") from exc

            page.goto(payment_url, wait_until="domcontentloaded")
            try:
                page.wait_for_load_state("networkidle", timeout=30_000)
            except Exception:  # noqa: BLE001
                pass  # 환율 문구는 정적 본문에 있으므로 백그라운드 요청이 남아 있어도 진행합니다.
            if "sign_in" in page.url:
                raise RateError("결제 화면 대신 로그인 화면이 열렸습니다. 세션이 유지되지 않았습니다.")
            return parse_rate(page.inner_text("body"))
        except Exception:
            try:
                page.screenshot(path=str(shot_dir / "ais-error.png"), full_page=True)
            except Exception:  # noqa: BLE001
                pass
            raise
        finally:
            browser.close()


# ---------------------------------------------------------------- 저장


def _write_json(data: dict[str, Any]) -> None:
    RATE_JSON.parent.mkdir(parents=True, exist_ok=True)
    RATE_JSON.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def record_success(rate: float, now: dt.datetime) -> tuple[dict[str, Any], float | None]:
    """저장 후 (새 json, 변경 전 환율)을 돌려줍니다. 변경이 없으면 두 번째 값은 None."""
    prev = load_rate()
    prev_rate = prev.get("rate")
    stamp = now.isoformat()
    if prev_rate is None:
        data = {"rate": rate, "checked_at": stamp, "changed_at": stamp, "previous_rate": None}
        changed_from = None
    elif float(prev_rate) != rate:
        data = {"rate": rate, "checked_at": stamp, "changed_at": stamp, "previous_rate": prev_rate}
        changed_from = float(prev_rate)
    else:
        data = {
            "rate": rate,
            "checked_at": stamp,
            "changed_at": prev.get("changed_at") or stamp,
            "previous_rate": prev.get("previous_rate"),
        }
        changed_from = None
    _write_json(data)

    rows = load_history_all()
    rows[now.date().isoformat()] = rate
    _write_history(rows)
    _record_fees(now.date().isoformat())
    return data, changed_from


def _write_history(rows: dict[str, float | None]) -> None:
    HISTORY_CSV.parent.mkdir(parents=True, exist_ok=True)
    with HISTORY_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "rate"])
        for d in sorted(rows):
            r = rows[d]
            w.writerow([d, "" if r is None else fmt_rate(r).replace(",", "")])


def _record_fees(day: str) -> None:
    """그날 원장에 있던 MRV 수수료를 남깁니다. 지난 날짜의 금액은 만들어 내지 않습니다."""
    hist = load_fee_history()
    for f in mrv_fees():
        rows = [r for r in hist.get(f["fee_id"], []) if r[0] != day]
        rows.append((day, float(f["amount"])))
        hist[f["fee_id"]] = sorted(rows)
    with FEE_HISTORY_CSV.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["date", "fee_id", "amount"])
        for fee_id in sorted(hist):
            for d, amount in hist[fee_id]:
                w.writerow([d, fee_id, fmt_rate(amount).replace(",", "")])


def record_failure(message: str, now: dt.datetime) -> None:
    data = load_rate()
    data["last_error"] = message
    data["failed_at"] = now.isoformat()
    _write_json(data)
    rows = load_history_all()
    day = now.date().isoformat()
    if rows.get(day) is None:  # 같은 날 앞서 성공했다면 그 값을 지킵니다
        rows[day] = None
        _write_history(rows)


# ---------------------------------------------------------------- 알림


def _page_url() -> str:
    from src import site

    domain = (site.load_cfg().get("site") or {}).get("domain") or "visacal.com"
    return f"https://{domain}/consular-rate/"


def _fee_table(rate: float) -> str:
    rows = mrv_fees()
    if not rows:
        return "원장(data/fees.json)에 금액이 확정된 대사관 MRV 수수료가 없어 표를 만들지 못했습니다."
    lines = ["비자 | 1인 USD | 1인 원화"]
    for f in rows:
        lines.append(f"{f['visa']} ({f['item']}) | {f['amount']:,} USD | {krw(f['amount'], rate):,}원")
    return "\n".join(lines)


def notify_success(data: dict[str, Any], changed_from: float | None, now: dt.datetime) -> None:
    from src import notify

    mode = (os.environ.get("NOTIFY_MODE") or "daily").strip().lower()
    if mode == "change" and changed_from is None:
        print("[consular] 환율 변경 없음, change 모드라 메일 생략")
        return
    rate = float(data["rate"])
    subject = f"[영사환율] 1 USD = {fmt_rate(rate)} KRW ({now.date().isoformat()})"
    if changed_from is not None:
        subject += f" 변경: {fmt_rate(changed_from)} → {fmt_rate(rate)}"
    changed_at = (data.get("changed_at") or "")[:10]
    body = (
        f"오늘 AIS 결제창 기준 영사환율은 1 USD = {fmt_rate(rate)} KRW 입니다.\n"
        f"마지막 변경일: {changed_at}"
        + (f", 직전 환율 {fmt_rate(float(data['previous_rate']))} KRW" if data.get("previous_rate") else "")
        + "\n\n"
        f"{_fee_table(rate)}\n\n"
        f"동반가족도 1인당 같은 금액입니다. 결제창에 표시되는 금액이 최종 기준입니다.\n"
        f"현황: {_page_url()}"
    )
    notify._send_mail(notify._addrs("CONSULAR_MAIL_TO"), subject, body)


def notify_failure(message: str, now: dt.datetime, screenshot: Path | None) -> None:
    from src import notify

    subject = f"[영사환율] 수집 실패 ({now.date().isoformat()})"
    body = (
        f"AIS 결제창에서 영사환율을 가져오지 못했습니다.\n\n"
        f"오류: {message}\n\n"
        "사이트에는 마지막으로 확인된 환율이 그대로 표시됩니다. 3일 넘게 실패하면 페이지에 확인 지연 경고가 뜹니다.\n"
        + (
            "첨부한 스크린샷에는 신청인 정보가 담겨 있을 수 있습니다. 외부로 전달하지 마십시오."
            if screenshot
            else "스크린샷은 만들지 못했습니다."
        )
    )
    notify._send_mail(notify._addrs("CONSULAR_MAIL_TO"), subject, body, [screenshot] if screenshot else None)


# ---------------------------------------------------------------- 진입점


def main() -> int:
    email = os.environ.get("AIS_EMAIL", "")
    password = os.environ.get("AIS_PASSWORD", "")
    payment_url = os.environ.get("AIS_PAYMENT_URL", "")
    now = now_kst()

    shot_dir = Path(tempfile.mkdtemp(prefix="ais-"))  # 레포 밖. 커밋되지 않습니다
    try:
        try:
            if not (email and password and payment_url):
                raise RateError("AIS_EMAIL, AIS_PASSWORD, AIS_PAYMENT_URL 시크릿이 설정되지 않았습니다.")
            rate = fetch_rate(email, password, payment_url, shot_dir)
        except Exception as exc:  # noqa: BLE001
            message = _sanitize(str(exc) or exc.__class__.__name__, [email, password, payment_url])
            print(f"[consular] 수집 실패: {message}")
            record_failure(message, now)
            shot = shot_dir / "ais-error.png"
            notify_failure(message, now, shot if shot.exists() else None)
            return 1

        data, changed_from = record_success(rate, now)
        note = f", 변경 {fmt_rate(changed_from)} → {fmt_rate(rate)}" if changed_from is not None else ""
        print(f"[consular] 1 USD = {fmt_rate(rate)} KRW{note}")
        notify_success(data, changed_from, now)
        return 0
    finally:
        shutil.rmtree(shot_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    sys.exit(main())
