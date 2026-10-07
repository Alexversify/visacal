"""진입점. GitHub Actions에서 `python -m src.main` 으로 실행합니다."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import analyze as analyzer
from src import fill, ledger, notify, render, sources

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / "config" / "settings.yaml"


def main() -> int:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8"))
    pages_url = os.environ.get("PAGES_URL", "")

    # 매시간 실행과 글 게시 직후 실행은 페이지만 다시 그립니다.
    # 수수료 수집은 하루 두 번 정규 실행에서만 합니다.
    if os.environ.get("RUN_MODE", "full") == "render":
        print("[render] 페이지만 재생성")
        render.render(ledger.load_fees(), ledger.load_changelog(), ledger.load_state())
        return 0

    print("[1/5] 소스 수집")
    fr = sources.fetch_federal_register(cfg["federal_register"])
    uscis = sources.fetch_uscis_g1055(cfg["uscis"])
    pdf = sources.fetch_g1055_pdf_fees(uscis.get("pdf_url"))
    state_dept = sources.fetch_state_fees(cfg["state_dept"])
    sevis = sources.fetch_sevis_fee(cfg.get("sevis") or {})
    fx = sources.fetch_fx(cfg.get("fx") or {})

    # 환율은 받았을 때만 덮어씁니다. 실패하면 직전 값과 그 날짜가 화면에 남습니다.
    if fx.get("rate"):
        (ROOT / "data" / "fx.json").write_text(
            json.dumps({"rate": fx["rate"], "date": fx["date"], "base": "USD", "quote": "KRW"},
                       ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )

    for result in (fr, uscis, pdf, state_dept, sevis, fx):
        status = result.get("error") or "ok"
        print(f"  - {result['source']}: {status}")

    collected = {"federal_register": fr, "uscis": uscis, "pdf": pdf,
                 "state_dept": state_dept, "sevis": sevis}

    print("[2/5] 변경 감지")
    old_state = ledger.load_state()
    new_state = ledger.build_state(collected)
    first_run = not old_state
    changes = ledger.diff_state(old_state, new_state)
    print(f"  - {'기준선 최초 생성' if first_run else f'변경 {len(changes)}건'}")

    fees = ledger.load_fees()
    analysis = None

    if changes:
        print("[3/5] 분석")
        analysis = analyzer.analyze(changes, fees)
        touched = analyzer.apply_ledger_updates(fees, analysis)
        if touched:
            print(f"  - 원장 검토 대기 표시: {', '.join(touched)}")
        # 공개 사이트에 노출되는 파일이므로 팀 내부 공지 문구는 남기지 않습니다.
        # 전문은 메일로만 나갑니다.
        public = None
        if analysis:
            public = {"headline": analysis.get("headline"), "severity": analysis.get("severity")}
        ledger.append_changelog(changes, public)

        print("[4/5] 알림 발송")
        notify.dispatch(analysis, changes, pages_url)
    else:
        print("[3/5] 분석 생략")
        print("[4/5] 알림 생략")

    print("[5/5] 금액 채우기, 저장 및 렌더링")
    # 비어 있는 금액만 공식 자료에서 채웁니다. 이미 있는 값은 건드리지 않습니다.
    report = fill.fill_missing(fees, collected)
    filled = [r for r in report if r["amount"] is not None]
    if filled:
        print(f"  - 금액 채움 {len(filled)}건: {', '.join(r['fee_id'] for r in filled)}")
    for row in report:
        if row["amount"] is None:
            print(f"  - 미채움 {row['fee_id']}: {row['result']}")

    for fee in fees.get("fees", []):
        fee["last_checked"] = new_state["checked_at"]
    ledger.save_fees(fees)
    ledger.save_state(new_state)
    out = render.render(fees, ledger.load_changelog(), new_state)
    print(f"  - {out}")

    # 수집 원본은 디버깅용으로 남깁니다.
    (ROOT / "data" / "last_raw.json").write_text(
        json.dumps(collected, ensure_ascii=False, indent=2)[:400000], encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
