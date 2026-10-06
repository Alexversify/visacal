"""영사환율 페이지. docs/consular-rate/index.html

data/consular_rate.json 과 이력 csv 만 읽습니다. 둘 다 없으면 "수집 준비 중"으로 그립니다.
그래프는 외부 라이브러리 없이 인라인 SVG로 만듭니다.
"""

from __future__ import annotations

import datetime as dt
import html
import json
import re
from pathlib import Path
from typing import Any

from src import site
from src.consular_rate import KST, fmt_rate, krw, load_history, load_rate, mrv_fees

ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "consular-rate"
STALE_DAYS = 3
TITLE = "미국 비자 수수료 원화 환율, 주한미국대사관 기준"

CSS = """
h1{font-size:22px;letter-spacing:-.02em;margin:26px 0 6px}
.lede{margin:0 0 22px;max-width:72ch;color:var(--muted);font-size:14px}
.stale{border-left:3px solid var(--warn);background:#fdf2f2;padding:9px 12px;font-size:13.5px;margin:0 0 16px}
.stale[hidden]{display:none}
.tiles{display:grid;grid-template-columns:1.4fr 1fr 1fr 1fr;gap:10px;margin-bottom:28px}
.tile{background:var(--paper);border:1px solid var(--rule);padding:14px 16px;border-radius:2px}
.tile.main{border-color:var(--ink);border-top-width:3px}
.tile .k{font-size:12px;color:var(--faint);margin-bottom:4px}
.tile .v{font-size:16px;font-weight:650;font-variant-numeric:tabular-nums}
.tile.main .v{font-size:26px;font-weight:700;letter-spacing:-.02em}
.tile .s{font-size:12px;color:var(--faint);margin-top:2px}
h2{font-size:15px;margin:30px 0 10px}
.tbl{width:100%;border-collapse:collapse;font-size:13.5px;background:var(--paper);border:1px solid var(--rule)}
.tbl th{text-align:left;font-weight:600;color:var(--faint);font-size:12px;padding:9px 10px;border-bottom:1px solid var(--rule)}
.tbl td{padding:9px 10px;border-bottom:1px solid var(--hair);vertical-align:middle}
.tbl .num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}
.tbl .sub{display:block;font-size:12px;color:var(--faint)}
.tbl input{width:58px;border:1px solid var(--rule);padding:5px 7px;font:inherit;font-size:13.5px;text-align:right;
  border-radius:2px;font-variant-numeric:tabular-nums}
.tbl .ais{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12.5px;color:var(--muted);white-space:nowrap}
.tbl .ais-sm{display:none;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;color:var(--muted);margin-top:3px}
.tbl tfoot td{font-weight:700;border-top:1px solid var(--ink);border-bottom:0}
.wait{color:var(--pend)}
.chart{background:var(--paper);border:1px solid var(--rule);padding:14px 14px 8px;border-radius:2px;position:relative;overflow-x:auto}
.chart svg{display:block;width:100%;max-width:720px;min-width:560px;height:auto;margin:0 auto}
.chart .empty{color:var(--faint);font-size:13.5px;padding:24px 4px}
.tip{position:absolute;pointer-events:none;background:var(--ink);color:#fff;font-size:12.5px;padding:5px 8px;
  border-radius:2px;white-space:nowrap;font-variant-numeric:tabular-nums;transform:translate(-50%,-110%)}
.tip[hidden]{display:none}
.guide{margin-top:34px;max-width:74ch}
.guide p{color:var(--muted);font-size:14px;margin:0 0 10px}
@media (max-width:760px){
  .tiles{grid-template-columns:1fr 1fr}
  .tile.main{grid-column:1/-1}
}
@media (max-width:520px){.tbl .hide-sm{display:none}.tbl .ais-sm{display:block}}
"""

JS = r"""
const R = __RATE__, FEES = __FEES__, HIST = __HIST__;
const $ = id => document.getElementById(id);
const n = v => v.toLocaleString('ko-KR');

// 페이지가 몇 시간에 한 번 다시 만들어지므로 경고는 브라우저 시각으로 한 번 더 판단합니다.
if(R && R.checked_at){
  const late = (Date.now() - Date.parse(R.checked_at)) > __STALE__*86400000;
  $('stale').hidden = !late;
}

function calc(){
  let usdSum = 0, krwSum = 0, people = 0;
  FEES.forEach(f=>{
    const el = $('n-'+f.id), outs = [$('ais-'+f.id), $('ais-sm-'+f.id)];
    const put = t => outs.forEach(o => { o.textContent = t; });
    const c = Math.max(0, Math.min(20, parseInt(el.value,10)||0));
    people += c; usdSum += f.amount*c;
    if(!R || !R.rate){ put(c ? `${c}명 × ${f.amount} USD` : ''); return; }
    const v = Math.round(f.amount*c*R.rate); krwSum += v;
    put(c ? `(${c} @ ${f.amount} USD) x ${R.rate} KRW/USD = ${n(v)}` : '');
  });
  $('sum-usd').textContent = usdSum ? n(usdSum)+' USD' : '';
  $('sum-krw').textContent = (R && R.rate && krwSum) ? n(krwSum)+'원' : '';
  $('sum-n').textContent = people ? people+'명' : '';
}
document.addEventListener('input', e=>{ if(e.target.matches('.tbl input')) calc(); });
calc();

const svg = $('chart-svg');
if(svg && HIST.length){
  const tip = $('tip'), guide = $('chart-guide'), dot = $('chart-dot'), box = svg.parentElement;
  svg.addEventListener('mousemove', e=>{
    const pt = svg.createSVGPoint(); pt.x = e.clientX; pt.y = e.clientY;
    const p = pt.matrixTransform(svg.getScreenCTM().inverse());
    let best = HIST[0];
    HIST.forEach(h=>{ if(Math.abs(h.x-p.x) < Math.abs(best.x-p.x)) best = h; });
    guide.setAttribute('x1',best.x); guide.setAttribute('x2',best.x); guide.style.display='';
    dot.setAttribute('cx',best.x); dot.setAttribute('cy',best.y); dot.style.display='';
    const r = svg.getBoundingClientRect(), b = box.getBoundingClientRect(), s = r.width/svg.viewBox.baseVal.width;
    tip.style.left = (r.left-b.left+best.x*s)+'px'; tip.style.top = (r.top-b.top+best.y*s)+'px';
    tip.textContent = `${best.d} · ${n(best.r)}원`; tip.hidden = false;
  });
  svg.addEventListener('mouseleave', ()=>{ tip.hidden = true; guide.style.display='none'; dot.style.display='none'; });
}
"""

GUIDE = """
<div class="guide">
<h2>알아둘 점</h2>
<p>대사관 비자 신청 수수료는 미화로 정해져 있지만 국내에서는 원화로 결제합니다. 이때 적용되는 환율은 시중 환율이 아니라
국무부가 정하는 영사환율이며, 이 페이지의 값은 AIS 결제 화면에 표시된 환율을 매일 아침 확인한 것입니다.</p>
<p>최종 금액은 결제 화면에 표시되는 금액이 기준입니다. 결제 직전에 환율이 바뀌었을 수 있으니 결제 화면에서 한 번 더 확인하십시오.</p>
<p>낸 수수료는 환불되지 않고 다른 사람에게 넘길 수 없습니다. 영수증은 유효기간 안에 인터뷰 예약에 써야 하므로
예약 일정이 정해진 뒤 결제하는 편이 안전합니다.</p>
</div>
"""


def _parse(ts: str | None) -> dt.datetime | None:
    if not ts:
        return None
    try:
        return dt.datetime.fromisoformat(ts).astimezone(KST)
    except ValueError:
        return None


def rate_badge(data: dict[str, Any] | None = None, href: str = "consular-rate/") -> str:
    """메인 페이지와 관납료 화면 상단에 붙는 한 줄 배지."""
    data = load_rate() if data is None else data
    rate = data.get("rate")
    if rate is None:
        return f'<a class="rate-badge" href="{href}">영사환율 수집 준비 중</a>'
    checked = _parse(data.get("checked_at"))
    today = dt.datetime.now(KST).date()
    if checked and checked.date() == today:
        label = f"오늘 영사환율 1 USD = {fmt_rate(rate)}원"
    else:
        when = checked.strftime("%m-%d") if checked else ""
        label = f"영사환율 1 USD = {fmt_rate(rate)}원 <span>{when} 확인</span>"
    return f'<a class="rate-badge" href="{href}">{label}</a>'


def _chart(history: list[tuple[str, float]]) -> tuple[str, list[dict[str, Any]]]:
    if len(history) < 2:
        return '<div class="empty">기록이 이틀 이상 쌓이면 변동 그래프가 표시됩니다.</div>', []
    w, h = 720, 220
    left, right, top, bottom = 56, 14, 14, 30
    dates = [dt.date.fromisoformat(d) for d, _ in history]
    rates = [r for _, r in history]
    lo, hi = min(rates), max(rates)
    pad = max((hi - lo) * 0.15, 5)
    lo, hi = lo - pad, hi + pad
    span = max((dates[-1] - dates[0]).days, 1)

    def x(d: dt.date) -> float:
        return round(left + (d - dates[0]).days / span * (w - left - right), 1)

    def y(r: float) -> float:
        return round(top + (hi - r) / (hi - lo) * (h - top - bottom), 1)

    # 영사환율은 바뀔 때까지 그대로 유지되므로 계단형으로 그립니다.
    path = [f"M{x(dates[0])},{y(rates[0])}"]
    for d, r in zip(dates[1:], rates[1:]):
        path.append(f"H{x(d)}V{y(r)}")
    grid = []
    for i in range(3):
        v = lo + pad + (hi - lo - 2 * pad) * i / 2
        grid.append(
            f'<line x1="{left}" x2="{w - right}" y1="{y(v)}" y2="{y(v)}" stroke="var(--hair)" stroke-width="1"/>'
            f'<text x="{left - 8}" y="{y(v) + 4}" text-anchor="end" font-size="11" fill="var(--faint)">{fmt_rate(round(v))}</text>'
        )
    ticks = {dates[0], dates[-1]}
    if len(dates) > 2:
        ticks.add(dates[len(dates) // 2])
    xlab = "".join(
        f'<text x="{x(d)}" y="{h - 9}" text-anchor="{"start" if d == dates[0] else "end" if d == dates[-1] else "middle"}" '
        f'font-size="11" fill="var(--faint)">{d.isoformat()}</text>'
        for d in sorted(ticks)
    )
    points = [{"x": x(d), "y": y(r), "d": d.isoformat(), "r": r} for d, r in zip(dates, rates)]
    svg = (
        f'<svg id="chart-svg" viewBox="0 0 {w} {h}" role="img" aria-label="영사환율 변동 그래프, '
        f'{dates[0].isoformat()}부터 {dates[-1].isoformat()}까지">'
        + "".join(grid)
        + f'<line x1="{left}" x2="{w - right}" y1="{h - bottom}" y2="{h - bottom}" stroke="var(--rule)" stroke-width="1"/>'
        + xlab
        + f'<line id="chart-guide" y1="{top}" y2="{h - bottom}" stroke="var(--faint)" stroke-width="1" style="display:none"/>'
        + f'<path d="{"".join(path)}" fill="none" stroke="var(--ink)" stroke-width="2" stroke-linejoin="round"/>'
        + f'<circle id="chart-dot" r="4.5" fill="var(--ink)" stroke="var(--paper)" stroke-width="2" style="display:none"/>'
        + f'<rect x="{left}" y="{top}" width="{w - left - right}" height="{h - top - bottom}" fill="transparent"/>'
        + "</svg>"
    )
    return svg, points


def _changes(history: list[tuple[str, float]]) -> list[tuple[str, float, float | None]]:
    out = []
    prev = None
    for d, r in history:
        if prev is None or r != prev:
            out.append((d, r, prev))
        prev = r
    return list(reversed(out))[:12]


def render_consular(cfg: dict[str, Any] | None = None) -> Path:
    cfg = cfg or site.load_cfg()
    data = load_rate()
    history = load_history()
    fees = mrv_fees()
    rate = data.get("rate")
    checked = _parse(data.get("checked_at"))
    changed = _parse(data.get("changed_at"))
    prev = data.get("previous_rate")

    stale = bool(checked and (dt.datetime.now(KST) - checked) > dt.timedelta(days=STALE_DAYS))
    stale_msg = (
        f"최신 확인 지연. 마지막 확인이 {checked.strftime('%Y-%m-%d')}입니다. 결제 화면의 환율을 직접 확인하십시오."
        if checked
        else ""
    )

    if rate is None:
        tiles = """<div class="tile main"><div class="k">오늘 적용 환율</div><div class="v wait">수집 준비 중</div>
<div class="s">첫 수집이 끝나면 표시됩니다</div></div>"""
    else:
        tiles = (
            f'<div class="tile main"><div class="k">오늘 적용 환율</div><div class="v">1 USD = {fmt_rate(rate)}원</div>'
            f'<div class="s">AIS 결제 화면 기준</div></div>'
            f'<div class="tile"><div class="k">마지막 확인</div><div class="v">{checked.strftime("%Y-%m-%d") if checked else "기록 없음"}</div>'
            f'<div class="s">{checked.strftime("%H:%M KST") if checked else ""}</div></div>'
            f'<div class="tile"><div class="k">마지막 변경일</div><div class="v">{changed.strftime("%Y-%m-%d") if changed else "기록 없음"}</div></div>'
            f'<div class="tile"><div class="k">직전 환율</div><div class="v">{fmt_rate(prev) + "원" if prev else "기록 없음"}</div></div>'
        )

    fee_rows = []
    for f in fees:
        per = f"{krw(f['amount'], rate):,}원" if rate is not None else '<span class="wait">환율 수집 후 표시</span>'
        fid = html.escape(f["fee_id"])
        fee_rows.append(
            f"<tr><td>{html.escape(f['visa'])}<span class=\"sub\">{html.escape(f['item'])}</span><span class=\"ais-sm\" id=\"ais-sm-{fid}\"></span></td>"
            f'<td class="num hide-sm">{f["amount"]:,} USD</td><td class="num">{per}</td>'
            f'<td class="num"><input id="n-{fid}" type="number" min="0" max="20" value="0" inputmode="numeric" aria-label="{html.escape(f["visa"])} 신청 인원"></td>'
            f'<td class="ais hide-sm" id="ais-{fid}"></td></tr>'
        )
    if fee_rows:
        table = f"""<table class="tbl"><thead><tr><th>비자</th><th class="num hide-sm">1인 USD</th><th class="num">1인 원화</th>
<th class="num">인원</th><th class="hide-sm">결제창 계산</th></tr></thead>
<tbody>{''.join(fee_rows)}</tbody>
<tfoot><tr><td>합계 <span id="sum-n"></span></td><td class="num hide-sm" id="sum-usd"></td><td class="num" id="sum-krw"></td><td></td><td class="hide-sm"></td></tr></tfoot></table>"""
    else:
        table = '<p class="lede">원장에 금액이 확정된 대사관 수수료가 없습니다.</p>'

    chart_svg, points = _chart(history)
    change_rows = "".join(
        f'<tr><td>{d}</td><td class="num">{fmt_rate(r)}원</td>'
        f'<td class="num">{"첫 기록" if p is None else ("+" if r > p else "") + fmt_rate(r - p)}</td></tr>'
        for d, r, p in _changes(history)
    )
    changes = (
        f'<table class="tbl"><thead><tr><th>날짜</th><th class="num">환율</th><th class="num">변동</th></tr></thead>'
        f"<tbody>{change_rows}</tbody></table>"
        if change_rows
        else '<p class="lede">아직 기록이 없습니다.</p>'
    )

    body = f"""
<h1>{html.escape(TITLE)}</h1>
<p class="lede">주한미국대사관 비자 신청 수수료를 원화로 낼 때 적용되는 영사환율입니다.
평일 아침 AIS 결제 화면에서 확인한 값이며, 아래 표의 원화 금액은 이 환율로 계산합니다.</p>
<div class="stale" id="stale"{'' if stale else ' hidden'}>{html.escape(stale_msg)}</div>
<div class="tiles">{tiles}</div>

<h2>비자별 1인 원화 금액</h2>
{table}

<h2>환율 변동</h2>
<div class="chart">{chart_svg}<div class="tip" id="tip" hidden></div></div>

<h2>최근 변경 이력</h2>
{changes}
{GUIDE}
{site.ad(cfg, "page_bottom")}
"""
    rate_js = (
        {"rate": rate, "checked_at": data.get("checked_at")} if rate is not None else
        ({"checked_at": data.get("checked_at")} if data.get("checked_at") else None)
    )
    js = (
        JS.replace("__RATE__", json.dumps(rate_js))
        .replace("__FEES__", json.dumps([{"id": f["fee_id"], "amount": f["amount"]} for f in fees]))
        .replace("__HIST__", json.dumps(points))
        .replace("__STALE__", str(STALE_DAYS))
    )
    doc = (
        site.head(cfg, TITLE, CSS, "주한미국대사관 비자 수수료 원화 결제 환율. AIS 결제 화면 기준 영사환율과 비자별 원화 금액, 변동 이력.")
        + site.header(cfg, "")
        + body
        + site.footer(cfg)
    ).replace("</body></html>", f"<script>{js}</script></body></html>")
    # consular-rate/ 하위 페이지라 상대경로 링크를 한 단계 올립니다.
    doc = re.sub(r'href="(?!https?:|mailto:|#|\.\./|/)([a-z\-]+\.html)"', r'href="../\1"', doc)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out = OUT_DIR / "index.html"
    out.write_text(doc, encoding="utf-8")
    return out
