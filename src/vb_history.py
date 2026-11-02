"""과거 비자 문호 일괄 변환.

`python -m src.vb_history` 로 실행합니다.
입력: data/visa_bulletin/import/tables.json
  국무부 원문 페이지(2001년 12월 ~ 현재)에서 표만 그대로 뽑은 것. 페이지 경로 → {t: 제목, x: 표 텍스트}
  표 텍스트는 표마다 '@직전 제목' 한 줄 뒤에 행을 '|' 로 이어 붙였고, 표 사이는 '\\n#\\n' 입니다.
출력: data/visa_bulletin/YYYY-MM.json (달마다 하나)

시기별 차이를 그대로 다룹니다.
- 2005년 1월 전에는 중국 열이 없고, 2002~2003년 일부 가족 표에는 인도 열도 없습니다. 없는 칸은 null 로 둡니다
- 도미니카공화국(2010~2011), 엘살바도르·과테말라·온두라스(2016~2023), 베트남(2018~2021) 열은 extra 에 따로 둡니다
- 접수가능일 표는 2015년 10월부터. 그 전 달은 최종조치일 표만 있습니다
- EB-5 행 이름은 시기마다 바뀌므로 행 이름 그대로 구분합니다 (vb_i18n.SHORT 참고)

이미 있는 달의 LLM 요약과 USCIS 지정 차트는 보존하고, 표와 변동, 자동 분석은 다시 계산합니다.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import vb_i18n as I  # noqa: E402
from src import visa_bulletin as vb  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "data" / "visa_bulletin" / "import" / "tables.json"
OUT = ROOT / "data" / "visa_bulletin"
KST = dt.timezone(dt.timedelta(hours=9))
MONTHS = [m.lower() for m in vb.MONTHS]
VAL = re.compile(r"^(\d{1,2}[A-Z]{3}\d{2}|C|U)$")
FIXES: list[str] = []


def month_of(path: str) -> tuple[int, int]:
    m = re.search(r"for-([a-z]+)-(\d{4})", path)
    if not m:
        raise ValueError(path)
    return int(m.group(2)), MONTHS.index(m.group(1)) + 1


def col_key(label: str) -> str | None:
    u = re.sub(r"[\s\-]", "", label.upper())
    if re.search(r"CHARGE?AB", u):
        return "row"
    if "CHINA" in u:
        return "china"
    if "INDIA" in u:
        return "india"
    if "MEXICO" in u:
        return "mexico"
    if "PHILIP" in u or "PHILLI" in u:
        return "philippines"
    for k, pat in I.EXTRA_COLS.items():
        if re.search(pat, u):
            return "x:" + k
    return None


def emp_row_key(label: str) -> str | None:
    l = re.sub(r"\s+", " ", label).strip()
    low = l.lower()
    if re.match(r"^1st\b", low):
        return "EB1"
    if re.match(r"^2nd\b", low):
        return "EB2"
    if re.match(r"^3rd\b", low):
        return "EB3"
    if "schedule a" in low:
        return "SCHA"
    if "other worker" in low:
        return "EW"
    if re.match(r"^4th\b", low):
        return "EB4"
    if "religi" in low:
        return "RW"
    if "iraq" in low or "afghan" in low:
        return "SI"
    if "unreserved" in low:
        return "EB5URC" if re.search(r"\(i5 and r5\)", low) else "EB5U"
    if "rural" in low:
        return "EB5R"
    if "high unemployment" in low:
        return "EB5H"
    if "infrastructure" in low:
        return "EB5I"
    if "non-regional" in low:
        return "EB5NRC"
    if "regional center (i5" in low or low.startswith("5th regional center"):
        return "EB5RC"
    if "pilot program" in low and "targeted" not in low:
        return "EB5PP"
    if low.startswith("5th targeted") or ("targeted" in low and "pilot" in low):
        return "EB5"
    if re.search(r"targeted employ", low):
        return "EB5TEA"
    if re.match(r"^5th\b", low):
        return "EB5"
    return None


def parse_table(text: str, year: int) -> dict[str, Any] | None:
    lines = text.split("\n")
    head = lines[0][1:] if lines and lines[0].startswith("@") else ""
    rows = [l.split("|") for l in lines[1:] if l.strip()]
    hdr_i = next((i for i, r in enumerate(rows) if any(re.search(r"charge?ab", re.sub(r"[\s\-]", "", c.lower())) for c in r)), None)
    if hdr_i is None:
        return None
    hdr = rows[hdr_i]
    cols = [col_key(c) for c in hdr]
    blob = " ".join(" ".join(r[:1]) for r in rows).lower() + " " + " ".join(hdr).lower()
    if "employ" in blob:
        kind = "emp"
    elif "family" in blob:
        kind = "fam"
    else:
        return None
    body = [r for r in rows[hdr_i + 1:] if r and any(VAL.match(c.strip().upper().replace("*", "")) for c in r[1:])
            and not re.match(r"^(employment|family|priority)", r[0].strip().lower())]
    out_rows: dict[str, list[Any]] = {}
    extra_rows: dict[str, dict[str, Any]] = {}
    labels: dict[str, str] = {}
    order: list[str] = []
    fam_keys = I.FAMILY_ROWS
    for i, r in enumerate(body):
        label = r[0].strip()
        if kind == "fam":
            if i >= len(fam_keys):
                continue
            key = fam_keys[i]
        else:
            key = emp_row_key(label)
            if not key:
                raise vb.ParseError(f"알 수 없는 취업이민 행: {label!r}")
        std: list[Any] = [None] * 5
        ext: dict[str, Any] = {}
        vals_present = [c for c in r[1:] if c.strip()]
        if len(r) == 2 and len(vals_present) == 1:
            # 한 칸이 모든 열에 걸쳐 있는 행 (예: 2005년 Schedule A Workers 'C')
            r = [r[0]] + [r[1]] * (len(cols) - 1)
        for c_i, cell in enumerate(r[1:], start=1):
            if c_i >= len(cols) or not cols[c_i]:
                continue
            cell = cell.strip()
            if not cell:
                val = None
            else:
                val = vb.norm_value(cell, year)
                raw = cell.upper().replace("*", "").strip()
                if re.match(r"^\d[A-Z]{3}\d{2}$", raw):
                    FIXES.append(f"{year}: {label} '{raw}' → {val}")
            ck = cols[c_i]
            if ck.startswith("x:"):
                ext[ck[2:]] = val
            else:
                std[I.COLS.index(ck)] = val
        if key in out_rows:
            continue
        out_rows[key] = std
        if ext:
            extra_rows[key] = ext
        labels[key] = label
        order.append(key)
    if kind == "fam" and len(out_rows) != 5:
        raise vb.ParseError(f"가족 표 행 수가 5가 아님: {list(out_rows)}")
    filing = "filing" in head.lower() and "final" not in head.lower()
    extra_cols = [c[2:] for c in cols if c and c.startswith("x:")]
    return {"kind": kind, "filing": filing, "rows": out_rows, "extra": extra_rows, "extra_cols": extra_cols,
            "labels": labels, "order": order}


def build(path: str, item: dict[str, Any]) -> dict[str, Any]:
    y, m = month_of(path)
    n_fix = len(FIXES)
    tabs = [t for t in item["x"].split("\n#\n") if t.strip()]
    parsed = [p for p in (parse_table(t, y) for t in tabs) if p]
    fam = [p for p in parsed if p["kind"] == "fam"]
    emp = [p for p in parsed if p["kind"] == "emp"]
    if not fam or not emp:
        raise vb.ParseError("가족 또는 취업 표 없음")

    def pick(lst: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any] | None]:
        finals = [p for p in lst if not p["filing"]]
        filings = [p for p in lst if p["filing"]]
        # 제목으로 구분이 안 되면 순서로 (첫 표 최종조치일, 둘째 표 접수가능일)
        if not filings and len(lst) >= 2 and (y, m) >= (2015, 10):
            return lst[0], lst[1]
        return (finals or lst)[0], (filings[0] if filings and (y, m) >= (2015, 10) else None)

    ff, fl = pick(fam)
    ef, el = pick(emp)
    charts: dict[str, Any] = {"fam_final": ff["rows"], "emp_final": ef["rows"]}
    order = {"fam_final": ff["order"], "emp_final": ef["order"]}
    extra: dict[str, Any] = {}
    labels: dict[str, str] = {}
    for name, p in (("fam_final", ff), ("fam_filing", fl), ("emp_final", ef), ("emp_filing", el)):
        if not p:
            continue
        charts[name] = p["rows"]
        order[name] = p["order"]
        if p["extra_cols"]:
            extra[name] = {"cols": p["extra_cols"], "rows": p["extra"]}
        labels.update(p["labels"])
    return {
        "year": y, "month": m, "key": vb.month_key(y, m),
        "charts": charts, "order": order, "extra": extra, "labels": labels,
        "source": "travel.state.gov",
        "source_url": "https://travel.state.gov" + path,
        "fetched_at": dt.datetime.now(KST).isoformat(timespec="minutes"),
        "title": item.get("t", ""),
        "fixes": [f.split(": ", 1)[1] for f in FIXES[n_fix:]],
    }


def main() -> int:
    data = json.loads(SRC.read_text(encoding="utf-8"))
    recs: list[dict[str, Any]] = []
    fails = []
    for path, item in data.items():
        try:
            recs.append(build(path, item))
        except Exception as exc:  # noqa: BLE001
            fails.append((path, str(exc)))
    recs.sort(key=lambda r: r["key"])
    prev = None
    for rec in recs:
        old = vb.load(rec["key"]) or {}
        changes = vb.diff(prev, rec)
        rec["changes"] = changes
        rec["prev_key"] = prev["key"] if prev else None
        rec["summary"] = vb.analysis(rec, changes, bool(prev))
        # 이미 받아 둔 LLM 요약, USCIS 지정 차트, 원래 수집 시각은 유지
        if (old.get("summary") or {}).get("ko", {}).get("auto"):
            rec["summary"] = old["summary"]
        if old.get("uscis"):
            rec["uscis"] = old["uscis"]
        if old.get("fetched_at"):
            rec["fetched_at"] = old["fetched_at"]
        vb.save(rec)
        prev = rec
    have = {r["key"] for r in recs}
    first = recs[0]["key"]
    y, m = map(int, first.split("-"))
    missing = []
    while vb.month_key(y, m) <= recs[-1]["key"]:
        if vb.month_key(y, m) not in have:
            missing.append(vb.month_key(y, m))
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    (OUT / "index.json").write_text(json.dumps({"first": first, "last": recs[-1]["key"], "count": len(recs),
                                                "missing": missing}, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"변환 {len(recs)}개월, 실패 {len(fails)}, 원문 미게시 {missing}")
    for p, e in fails:
        print("  실패", p, e)
    return 1 if fails else 0


if __name__ == "__main__":
    raise SystemExit(main())
