"""수수료 원장과 변경 감지.

핵심: 페이지 전체를 해시하지 않습니다. alert 블록, PDF edition, 금액 필드처럼
의미 있는 단위만 지문(fingerprint)으로 만들어 비교합니다. 그래야 오탐이 안 납니다.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
FEES_PATH = ROOT / "data" / "fees.json"
STATE_PATH = ROOT / "data" / "state.json"
CHANGELOG_PATH = ROOT / "data" / "changelog.json"

STATUSES = ["시행중", "시행예정", "집행정지", "검토필요"]


def _load(path: Path, default: Any) -> Any:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _save(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def load_fees() -> dict[str, Any]:
    return _load(FEES_PATH, {"fees": []})


def save_fees(fees: dict[str, Any]) -> None:
    fees["updated_at"] = dt.date.today().isoformat()
    _save(FEES_PATH, fees)


def _fp(text: str) -> str:
    return hashlib.sha256(text.strip().encode("utf-8")).hexdigest()[:16]


def build_state(collected: dict[str, Any]) -> dict[str, Any]:
    """이번 수집 결과를 비교 가능한 지문 집합으로 환산합니다."""
    uscis = collected.get("uscis", {})
    fr = collected.get("federal_register", {})
    pdf = collected.get("pdf", {})

    pdf_amounts = {}
    for row in pdf.get("rows", []):
        if row.get("form") and row.get("amounts"):
            pdf_amounts.setdefault(row["form"], sorted(set(row["amounts"])))

    return {
        "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
        "uscis_edition": uscis.get("edition"),
        "uscis_alerts": {_fp(a): a for a in uscis.get("alerts", [])},
        "fr_docs": {d["key"]: d for d in fr.get("items", []) if d.get("key")},
        "pdf_amounts": pdf_amounts,
    }


def diff_state(old: dict[str, Any], new: dict[str, Any]) -> list[dict[str, Any]]:
    """의미 있는 변화만 골라냅니다. 첫 실행이면 기준선만 잡고 알림은 보내지 않습니다."""
    if not old:
        return []

    changes: list[dict[str, Any]] = []

    if old.get("uscis_edition") != new.get("uscis_edition") and new.get("uscis_edition"):
        changes.append(
            {
                "kind": "G-1055 개정판",
                "severity": "high",
                "detail": f"edition {old.get('uscis_edition')} -> {new.get('uscis_edition')}",
                "url": "https://www.uscis.gov/g-1055",
            }
        )

    old_alerts = old.get("uscis_alerts", {})
    for key, text in new.get("uscis_alerts", {}).items():
        if key not in old_alerts:
            changes.append(
                {
                    "kind": "USCIS 신규 공지",
                    "severity": "high",
                    "detail": text[:900],
                    "url": "https://www.uscis.gov/g-1055",
                }
            )
    for key, text in old_alerts.items():
        if key not in new.get("uscis_alerts", {}):
            changes.append(
                {
                    "kind": "USCIS 공지 내림",
                    "severity": "medium",
                    "detail": f"아래 공지가 페이지에서 사라졌습니다. 집행 재개 여부 확인 필요. {text[:500]}",
                    "url": "https://www.uscis.gov/g-1055",
                }
            )

    old_docs = old.get("fr_docs", {})
    for key, doc in new.get("fr_docs", {}).items():
        if key in old_docs:
            continue
        changes.append(
            {
                "kind": "연방관보 " + ("최종규칙" if doc.get("doc_type") == "Rule" else "규칙안"),
                "severity": "high" if doc.get("upcoming") else "medium",
                "detail": f"{doc.get('title')} / 시행일 {doc.get('effective_on') or '미정'} / 의견마감 {doc.get('comments_close_on') or '-'}",
                "abstract": doc.get("abstract"),
                "url": doc.get("url"),
            }
        )

    old_amounts = old.get("pdf_amounts", {})
    for form, amounts in new.get("pdf_amounts", {}).items():
        before = old_amounts.get(form)
        if before and before != amounts:
            changes.append(
                {
                    "kind": "금액 변동",
                    "severity": "high",
                    "detail": f"{form}: {before} -> {amounts}",
                    "url": "https://www.uscis.gov/g-1055",
                }
            )

    return changes


def load_state() -> dict[str, Any]:
    return _load(STATE_PATH, {})


def save_state(state: dict[str, Any]) -> None:
    _save(STATE_PATH, state)


def append_changelog(changes: list[dict[str, Any]], analysis: dict[str, Any] | None) -> list[dict[str, Any]]:
    log = _load(CHANGELOG_PATH, [])
    log.insert(
        0,
        {
            "date": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
            "changes": changes,
            "analysis": analysis,
        },
    )
    log = log[:200]
    _save(CHANGELOG_PATH, log)
    return log


def load_changelog() -> list[dict[str, Any]]:
    return _load(CHANGELOG_PATH, [])
