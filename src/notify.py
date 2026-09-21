"""알림 발송. 수속팀과 영업팀에 서로 다른 본문을 보냅니다."""

from __future__ import annotations

import json
import os
import smtplib
import ssl
from email.message import EmailMessage
from typing import Any

import requests


def _send_mail(to_addrs: list[str], subject: str, body: str) -> None:
    host = os.environ.get("SMTP_HOST")
    user = os.environ.get("SMTP_USER")
    password = os.environ.get("SMTP_PASS")
    if not (host and user and password and to_addrs):
        print(f"[notify] 메일 설정 없음, 건너뜀: {subject}")
        return
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.environ.get("SMTP_FROM", user)
    msg["To"] = ", ".join(to_addrs)
    msg.set_content(body)
    port = int(os.environ.get("SMTP_PORT", "465"))
    context = ssl.create_default_context()
    if port == 465:
        with smtplib.SMTP_SSL(host, port, context=context) as server:
            server.login(user, password)
            server.send_message(msg)
    else:
        with smtplib.SMTP(host, port) as server:
            server.starttls(context=context)
            server.login(user, password)
            server.send_message(msg)
    print(f"[notify] 메일 발송: {to_addrs}")


def _send_slack(text: str) -> None:
    hook = os.environ.get("SLACK_WEBHOOK_URL")
    if not hook:
        return
    requests.post(hook, json={"text": text}, timeout=20)


def _addrs(env_key: str) -> list[str]:
    raw = os.environ.get(env_key, "")
    return [a.strip() for a in raw.split(",") if a.strip()]


def dispatch(analysis: dict[str, Any] | None, changes: list[dict[str, Any]], pages_url: str) -> None:
    if not changes:
        return

    headline = (analysis or {}).get("headline", "미국 이민 수수료 변경 감지")
    severity = (analysis or {}).get("severity", "medium")
    prefix = "[긴급] " if severity == "high" else "[안내] "

    sources = "\n".join(f"- {c['kind']}: {c.get('url', '')}" for c in changes[:8])

    for channel, env_key, label in (
        ("processing", "MAIL_TO_PROCESSING", "수속팀"),
        ("sales", "MAIL_TO_SALES", "영업팀"),
    ):
        body_text = (analysis or {}).get(channel) or json.dumps(changes, ensure_ascii=False, indent=2)[:2000]
        body = (
            f"{headline}\n\n"
            f"{body_text}\n\n"
            f"원문 출처\n{sources}\n\n"
            f"전체 수수료 현황판: {pages_url}\n\n"
            f"이 메일은 G-1055 및 연방관보 자동 감시 결과입니다. 금액 확정 전 원문을 대조하십시오."
        )
        _send_mail(_addrs(env_key), f"{prefix}{label} 미국 수수료 변경 - {headline}", body)

    _send_slack(f"*{prefix}{headline}*\n{(analysis or {}).get('processing', '')}\n{pages_url}")
