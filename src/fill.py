"""비어 있는 원장 금액을 공식 자료에서 채웁니다.

설계 원칙
1. 이미 값이 있는 항목은 건드리지 않습니다. 사람이 확인해 넣은 값을 기계가 덮지 않습니다.
2. 후보가 하나로 좁혀질 때만 채웁니다. 한 줄에 금액이 여러 개면 비워 둡니다.
   G-1055 표에는 일반 사업장과 소형 사업장 금액이 한 줄에 같이 오는 경우가 있어,
   아무거나 고르면 견적이 틀립니다.
3. 채운 금액에는 근거가 된 원문 줄을 같이 남깁니다. 원장 화면에서 바로 대조할 수 있습니다.
4. status 는 그대로 둡니다. 금액이 들어와도 사람이 확인하기 전까지는 검토 대상입니다.
"""

from __future__ import annotations

import datetime as dt
from typing import Any

# 각 항목의 match 규칙이 가리키는 수집 결과 이름입니다.
SOURCE_KEYS = {
    "uscis_g1055_pdf": "pdf",
    "state_dept": "state_dept",
    "sevis": "sevis",
}


def _rows(collected: dict[str, Any], source: str) -> list[dict[str, Any]]:
    key = SOURCE_KEYS.get(source)
    if not key:
        return []
    return (collected.get(key) or {}).get("rows") or []


def _matches(row: dict[str, Any], rule: dict[str, Any]) -> bool:
    line = (row.get("line") or "").lower()
    form = rule.get("form")
    if form and (row.get("form") or "").upper() != form.upper():
        return False
    for word in rule.get("require") or []:
        if word.lower() not in line:
            return False
    for word in rule.get("exclude") or []:
        if word.lower() in line:
            return False
    return bool(row.get("amounts"))


def candidates(collected: dict[str, Any], rule: dict[str, Any]) -> list[dict[str, Any]]:
    """규칙에 걸리는 원문 줄을 모읍니다."""
    return [row for row in _rows(collected, rule.get("source", "")) if _matches(row, rule)]


def resolve(collected: dict[str, Any], rule: dict[str, Any]) -> tuple[int | None, str, str]:
    """금액 하나와 근거 줄을 고릅니다. 못 고르면 이유를 돌려줍니다."""
    hits = candidates(collected, rule)
    if not hits:
        return None, "", "후보 없음"

    amounts = {amount for row in hits for amount in row["amounts"]}
    if len(amounts) > 1:
        pick = rule.get("pick")
        if pick == "min":
            value = min(amounts)
        elif pick == "max":
            value = max(amounts)
        else:
            return None, "", f"금액 후보가 여러 개입니다 {sorted(amounts)}"
    else:
        value = next(iter(amounts))

    line = next((row["line"] for row in hits if value in row["amounts"]), hits[0]["line"])
    return value, line, "채움"


def fill_missing(fees: dict[str, Any], collected: dict[str, Any]) -> list[dict[str, Any]]:
    """금액이 비어 있는 항목만 채우고, 무엇을 왜 못 채웠는지 함께 돌려줍니다."""
    report: list[dict[str, Any]] = []
    now = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")

    for fee in fees.get("fees", []):
        rule = fee.get("match")
        if not rule:
            continue
        if fee.get("amount") is not None:
            continue

        value, line, why = resolve(collected, rule)
        entry = {"fee_id": fee.get("fee_id"), "result": why, "amount": value}
        if value is None:
            report.append(entry)
            continue

        fee["amount"] = value
        fee["currency"] = fee.get("currency") or "USD"
        # 근거를 남깁니다. 사람이 확인하면 이 블록을 지우고 status 를 바꾸면 됩니다.
        fee["auto_fill"] = {"source": rule.get("source"), "line": line, "at": now}
        report.append(entry)

    return report
