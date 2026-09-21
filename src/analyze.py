"""감지된 변경을 실무 언어로 번역합니다.

원문 alert는 소송 경과가 뒤섞여 있어 그대로 팀에 뿌리면 아무도 안 읽습니다.
'지금 얼마를 내야 하는가'와 '언제부터 바뀌는가'로 환원해서 팀별로 나눕니다.
"""

from __future__ import annotations

import json
import os
from typing import Any

MODEL = "claude-sonnet-5"

SYSTEM = """당신은 한국 법무법인의 미국 이민 수속 실무 총괄이다.
USCIS와 미국 국무부의 수수료 변경 정보를 받아 내부 공지를 작성한다.

규칙:
- 추측하지 않는다. 입력에 없는 금액이나 날짜는 만들어내지 않고 "확인 필요"로 표기한다.
- 소송으로 집행이 정지된 수수료는 "현재 납부 대상 아님"임을 명확히 구분한다.
- 시행 예정인 건은 시행일과 그 전까지 접수분의 처리 기준을 반드시 언급한다.
- 줄표(—)를 쓰지 않는다. 쉼표나 마침표를 쓴다.
- 과장 없이 건조하게 쓴다.

출력은 아래 JSON만 반환한다. 다른 텍스트나 코드펜스를 붙이지 않는다.
{
  "headline": "한 줄 제목",
  "severity": "high | medium | low",
  "processing": "수속팀 공지 본문. 양식별 납부액, 시행일, 접수분 경과 기준, 반려 위험 중심. 3~6문장.",
  "sales": "영업팀 공지 본문. 견적 총액 변동, 고객 안내 문구, 계약 실비 조항 영향 중심. 3~5문장.",
  "ledger_updates": [
    {"fee_id": "기존 원장 ID 또는 신규", "field": "amount|status|effective_date", "new_value": "값", "reason": "근거"}
  ],
  "needs_human_review": true
}"""


def analyze(changes: list[dict[str, Any]], fees: dict[str, Any]) -> dict[str, Any] | None:
    if not changes:
        return None
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return {
            "headline": "변경 감지됨. 자동 분석 미실행(API 키 없음)",
            "severity": "medium",
            "processing": "원문을 직접 확인하십시오.",
            "sales": "원문을 직접 확인하십시오.",
            "ledger_updates": [],
            "needs_human_review": True,
        }

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    payload = {
        "detected_changes": changes,
        "current_ledger": [
            {k: f[k] for k in ("fee_id", "visa", "form", "item", "amount", "status")}
            for f in fees.get("fees", [])
        ],
    }
    msg = client.messages.create(
        model=MODEL,
        max_tokens=2000,
        system=SYSTEM,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )
    text = "".join(b.text for b in msg.content if getattr(b, "type", "") == "text")
    text = text.replace("```json", "").replace("```", "").strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "headline": "변경 감지됨. 분석 응답 파싱 실패",
            "severity": "medium",
            "processing": text[:1500],
            "sales": text[:800],
            "ledger_updates": [],
            "needs_human_review": True,
        }


def apply_ledger_updates(fees: dict[str, Any], analysis: dict[str, Any] | None) -> list[str]:
    """제안된 원장 수정은 status를 '검토필요'로 바꿔 사람이 승인하도록 남깁니다.

    금액을 자동으로 덮어쓰지 않습니다. 잘못된 금액이 견적서로 흘러가는 것이
    알림이 하루 늦는 것보다 훨씬 위험합니다.
    """
    if not analysis:
        return []
    touched = []
    index = {f["fee_id"]: f for f in fees.get("fees", [])}
    for update in analysis.get("ledger_updates", []) or []:
        fee = index.get(update.get("fee_id"))
        if not fee:
            continue
        fee["pending_update"] = {
            "field": update.get("field"),
            "proposed": update.get("new_value"),
            "reason": update.get("reason"),
        }
        fee["status"] = "검토필요"
        touched.append(fee["fee_id"])
    return touched
