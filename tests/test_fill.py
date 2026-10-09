"""금액 채우기 규칙 검증.

네트워크 없이 돌도록 수집 결과를 흉내 낸 자료로 확인합니다.
아래 금액은 규칙이 걸리는지 보려고 만든 예시이며 실제 고시 금액이 아닙니다.
원장에는 들어가지 않습니다. 실제 금액은 정규 수집이 공식 자료에서 채웁니다.
실행: python -m pytest tests -q   또는   python tests/test_fill.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src import fill  # noqa: E402

G1055 = {
    "rows": [
        {"form": "I-129", "amounts": [780], "line": "I-129 | Petition for a Nonimmigrant Worker, H-1B | $780"},
        {"form": "I-129", "amounts": [1385], "line": "I-129 | Petition for a Nonimmigrant Worker, L-1 | $1,385"},
        {"form": "I-129", "amounts": [1055], "line": "I-129 | Petition for a Nonimmigrant Worker, O-1 | $1,055"},
        {"form": "I-129", "amounts": [500], "line": "Fraud Prevention and Detection Fee, H-1B | $500"},
        {"form": "I-129", "amounts": [500], "line": "Fraud Prevention and Detection Fee, L-1 | $500"},
        {"form": None, "amounts": [1500, 750], "line": "ACWIA fee | 26 or more employees $1,500 | 25 or fewer $750"},
        {"form": "I-140", "amounts": [715], "line": "I-140 | Immigrant Petition for Alien Worker | $715"},
        {"form": "I-907", "amounts": [2805], "line": "I-907 | Premium Processing, I-140 | $2,805"},
        {"form": "I-485", "amounts": [1440], "line": "I-485 | Application to Register Permanent Residence | $1,440"},
        {"form": "I-130", "amounts": [675], "line": "I-130 | Petition for Alien Relative, paper filing | $675"},
    ]
}
STATE = {
    "rows": [
        {"amounts": [325], "line": "Immigrant visa application processing fee (per person) $325"},
        {"amounts": [120], "line": "Affidavit of Support review (only when reviewed domestically) $120"},
    ]
}
SEVIS = {"rows": [{"form": "I-901", "amounts": [350], "line": "I-901 SEVIS fee for F-1 students $350"}]}

COLLECTED = {"pdf": G1055, "state_dept": STATE, "sevis": SEVIS}


def ledger(*entries: dict) -> dict:
    return {"fees": list(entries)}


def entry(fee_id: str, match: dict, amount=None) -> dict:
    return {"fee_id": fee_id, "amount": amount, "currency": "USD", "status": "검토필요", "match": match}


def run(name: str, condition: bool) -> bool:
    print(("  통과  " if condition else "  실패  ") + name)
    return condition


def main() -> int:
    ok = True
    real = json.loads((ROOT / "data" / "fees.json").read_text(encoding="utf-8"))
    rules = {f["fee_id"]: f.get("match") for f in real["fees"] if f.get("match")}

    print("원장에 들어 있는 실제 규칙으로 확인")
    fees = ledger(*[entry(fid, rule) for fid, rule in rules.items()])
    report = fill.fill_missing(fees, COLLECTED)
    got = {r["fee_id"]: r["amount"] for r in report}

    expected = {
        "USCIS-I129-H": 780, "USCIS-I129-L": 1385, "USCIS-I129-O": 1055,
        "USCIS-FRAUD-I129-H": 500, "USCIS-FRAUD-I129-L": 500,
        "USCIS-I140": 715, "USCIS-I907-I140": 2805,
        "USCIS-I485": 1440, "USCIS-I130": 675,
        "DOS-IV-DS260": 325, "DOS-AOS-REVIEW": 120, "SEVIS-I901-F": 350,
    }
    for fee_id, want in expected.items():
        ok &= run(f"{fee_id} 가 {want} 로 채워진다", got.get(fee_id) == want)

    ok &= run("ACWIA 는 한 줄에 금액이 둘이라 채우지 않는다", got.get("USCIS-ACWIA") is None)
    ok &= run("자료에 없는 항목은 채우지 않는다", got.get("USCIS-I526E") is None)

    print("\n안전장치")
    kept = ledger(entry("USCIS-I140", rules["USCIS-I140"], amount=999))
    fill.fill_missing(kept, COLLECTED)
    ok &= run("이미 있는 금액은 덮어쓰지 않는다", kept["fees"][0]["amount"] == 999)

    filled = ledger(entry("USCIS-I140", rules["USCIS-I140"]))
    fill.fill_missing(filled, COLLECTED)
    fee = filled["fees"][0]
    ok &= run("채운 금액에 근거 줄이 남는다", "I-140" in (fee.get("auto_fill") or {}).get("line", ""))
    ok &= run("채워도 status 는 검토필요로 남는다", fee["status"] == "검토필요")

    no_rule = ledger({"fee_id": "X", "amount": None, "status": "검토필요"})
    ok &= run("규칙이 없으면 손대지 않는다", fill.fill_missing(no_rule, COLLECTED) == [])

    empty = ledger(entry("USCIS-I140", rules["USCIS-I140"]))
    fill.fill_missing(empty, {"pdf": {"rows": []}})
    ok &= run("수집이 비면 금액이 그대로 비어 있다", empty["fees"][0]["amount"] is None)

    broken = ledger(entry("USCIS-I140", rules["USCIS-I140"]))
    fill.fill_missing(broken, {"pdf": {"error": "타임아웃", "rows": []}})
    ok &= run("수집이 실패해도 예외 없이 지나간다", broken["fees"][0]["amount"] is None)

    print("\n결과:", "모두 통과" if ok else "실패 있음")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
