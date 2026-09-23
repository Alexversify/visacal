"""정적 페이지 생성.

docs/index.html   비자를 고르면 납부 명세와 총액이 나오는 견적 화면
docs/changes.html 수수료 원장 전체와 변경 이력

금액을 HTML에 박지 않고 JSON을 심어 브라우저에서 계산합니다.
원장만 정확하면 화면은 항상 따라옵니다.
"""

from __future__ import annotations

import datetime as dt
import html
import json
from pathlib import Path
from typing import Any

from src import site

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"
SCENARIOS = ROOT / "data" / "scenarios.json"

STATUS_COLOR = {
    "시행중": "#1f6b45",
    "시행예정": "#8a6d1f",
    "집행정지": "#9b2226",
    "검토필요": "#6b7688",
}

INDEX_CSS = """
.visas{display:flex;flex-wrap:wrap;gap:7px;margin:22px 0 26px}
.chip{border:1px solid var(--rule);background:var(--paper);padding:7px 14px;
  font:inherit;font-size:14px;cursor:pointer;color:var(--muted);border-radius:2px}
.chip:hover{border-color:var(--muted)}
.chip[aria-pressed="true"]{background:var(--ink);border-color:var(--ink);color:#fff;font-weight:600}
.chip:focus-visible{outline:2px solid var(--ink);outline-offset:2px}
.cols{display:grid;grid-template-columns:minmax(0,1fr) 400px;gap:34px;align-items:start}
.pick h2{font-size:13px;font-weight:600;color:var(--muted);margin:0 0 10px}
.opt{display:flex;gap:10px;align-items:flex-start;padding:11px 0;border-bottom:1px solid var(--hair);cursor:pointer}
.opt:last-child{border-bottom:0}
.opt input{margin:5px 0 0;accent-color:#14243c;flex:none}
.opt .t{flex:1}
.opt .n{font-size:12.5px;color:var(--faint);display:block;margin-top:1px}
.opt.dead .t{color:var(--faint)}
.opt.dead .t b{text-decoration:line-through}
.group{background:var(--paper);border:1px solid var(--rule);padding:16px 18px;margin-bottom:16px;border-radius:2px}
.count{display:flex;align-items:center;gap:8px;margin:0 0 6px;padding-left:26px}
.count button{width:26px;height:26px;border:1px solid var(--rule);background:var(--paper);
  font:inherit;cursor:pointer;line-height:1;color:var(--ink);border-radius:2px}
.count span{min-width:20px;text-align:center;font-variant-numeric:tabular-nums}
.count label{font-size:12.5px;color:var(--muted)}
.bill{background:var(--paper);border:1px solid var(--ink);border-top-width:3px;
  padding:22px 22px 18px;position:sticky;top:20px;border-radius:2px}
.bill h2{font-size:15px;margin:0 0 3px;font-weight:700}
.bill .who{font-size:12.5px;color:var(--faint);margin-bottom:16px}
.li{display:flex;align-items:baseline;gap:6px;padding:7px 0;font-size:14px}
.li .dots{flex:1;border-bottom:1px dotted var(--rule);transform:translateY(-3px)}
.li .v{font-variant-numeric:tabular-nums;white-space:nowrap}
.li.unk .nm,.li.unk .v{color:var(--pend)}
.li .tag{font-size:11.5px;color:var(--faint)}
.sum{margin-top:14px;padding-top:12px;border-top:1px solid var(--ink)}
.sum .li{padding:5px 0}
.total{display:flex;justify-content:space-between;align-items:baseline;
  margin-top:10px;padding-top:11px;border-top:3px double var(--ink)}
.total .l{font-weight:700}
.total .v{font-size:21px;font-weight:700;font-variant-numeric:tabular-nums;letter-spacing:-.02em}
.krw{display:flex;align-items:center;gap:8px;margin-top:14px;padding-top:12px;
  border-top:1px solid var(--hair);font-size:13px;color:var(--muted)}
.krw input{width:78px;border:1px solid var(--rule);padding:4px 7px;font:inherit;font-size:13px;
  text-align:right;font-variant-numeric:tabular-nums;border-radius:2px}
.krw .out{margin-left:auto;font-variant-numeric:tabular-nums;color:var(--ink);font-weight:600}
.flag{margin-top:14px;font-size:12.5px;line-height:1.55}
.flag div{padding:7px 10px;border-left:3px solid var(--pend);background:#fdf9ee;margin-top:6px}
.flag div.stop{border-left-color:var(--warn);background:#fdf2f2}
.note{margin-top:30px;color:var(--faint);font-size:12.5px;max-width:70ch}
@media (max-width:860px){
  .cols{grid-template-columns:1fr;gap:22px}
  .bill{position:static;order:-1}
}
"""

CHANGES_CSS = """
h3{font-size:13px;font-weight:600;color:var(--muted);margin:34px 0 10px;
  padding-bottom:7px;border-bottom:1px solid var(--rule)}
table{width:100%;border-collapse:collapse;font-size:13.5px;background:var(--paper)}
th{text-align:left;font-weight:600;color:var(--faint);font-size:12px;padding:9px 10px;border-bottom:1px solid var(--rule)}
td{padding:9px 10px;border-bottom:1px solid var(--hair);vertical-align:top}
.amt{text-align:right;font-variant-numeric:tabular-nums;font-weight:600;white-space:nowrap}
.st b{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px;vertical-align:1px}
.who{color:var(--faint);font-size:12.5px}
.pend{background:#fdf9ee;border:1px solid #ecdcb4;padding:8px 10px;font-size:12.5px;margin-top:5px}
.log{border-left:2px solid var(--rule);padding-left:18px;margin-top:12px}
.entry{margin-bottom:24px;position:relative}
.entry:before{content:"";position:absolute;left:-23px;top:8px;width:9px;height:9px;border-radius:50%;background:var(--ink)}
.entry .d{font-size:12.5px;color:var(--faint);font-variant-numeric:tabular-nums}
.entry .h{font-weight:650;margin:2px 0 5px}
.entry p{margin:0 0 6px;color:var(--muted);max-width:74ch}
@media (max-width:640px){td:first-child,th:first-child{display:none}}
"""

JS = r"""
const FEES = __FEES__, VISAS = __VISAS__;
const S = {visa: VISAS[0].id, route: VISAS[0].routes[0].id, opts:{}, counts:{}, rate:''};
const fee = id => FEES[id];
const money = (v,c) => (c==='KRW' ? v.toLocaleString('ko-KR')+'원' : '$'+v.toLocaleString('en-US'));
const visa = () => VISAS.find(v=>v.id===S.visa);
const route = () => visa().routes.find(r=>r.id===S.route) || visa().routes[0];

function chips(){
  return VISAS.map(v=>`<button class="chip" aria-pressed="${v.id===S.visa}" data-visa="${v.id}">${v.label}</button>`).join('');
}

function controls(){
  const v = visa(), r = route();
  let h = '';
  if(v.routes.length>1){
    h += '<div class="group"><h2>진행 경로</h2>' + v.routes.map(x=>`
      <label class="opt"><input type="radio" name="route" value="${x.id}" ${x.id===r.id?'checked':''}>
      <span class="t"><b>${x.label}</b></span></label>`).join('') + '</div>';
  }
  if(r.options.length){
    h += '<div class="group"><h2>선택 항목</h2>' + r.options.map(o=>{
      const f = fee(o.fee_id) || {};
      const dead = f.status === '집행정지';
      const price = (f.amount==null) ? '확인 필요' : money(f.amount, f.currency);
      const note = dead ? '현재 납부 대상 아님' : '';
      const on = !!S.opts[o.id];
      let block = `<label class="opt ${dead?'dead':''}"><input type="checkbox" data-opt="${o.id}" ${on?'checked':''}>
        <span class="t"><b>${o.label}</b><span class="n">${price}${note?' · '+note:''}</span></span></label>`;
      if(o.type==='per_person' && on){
        const n = S.counts[o.id]||1;
        block += `<div class="count"><button data-step="-1" data-opt="${o.id}">−</button>
          <span>${n}</span><button data-step="1" data-opt="${o.id}">+</button><label>명</label></div>`;
      }
      return block;
    }).join('') + '</div>';
  }
  return h || '<div class="group"><h2>선택 항목</h2><div class="opt"><span class="t">이 경로에는 선택 항목이 없습니다.</span></div></div>';
}

function lines(){
  const r = route(), out = [];
  r.lines.forEach(id=>{ const f=fee(id); if(f) out.push({f, qty:1, label:f.item}); });
  r.options.forEach(o=>{
    if(!S.opts[o.id]) return;
    const f = fee(o.fee_id); if(!f) return;
    out.push({f, qty: o.type==='per_person' ? (S.counts[o.id]||1) : 1, label:o.label});
  });
  return out;
}

function bill(){
  const items = lines();
  let usd=0, krw=0, unknown=0;
  const rows = items.map(it=>{
    const f = it.f, qty = it.qty;
    if(f.amount==null){ unknown++;
      return `<div class="li unk"><span class="nm">${it.label}</span><span class="dots"></span><span class="v">확인 필요</span></div>`;
    }
    const sub = f.amount*qty;
    if(f.currency==='KRW') krw+=sub; else usd+=sub;
    const q = qty>1 ? `<span class="tag">${money(f.amount,f.currency)} × ${qty}</span>` : '';
    return `<div class="li"><span class="nm">${it.label}</span>${q}<span class="dots"></span><span class="v">${money(sub,f.currency)}</span></div>`;
  }).join('');

  const sub = [];
  if(krw) sub.push(`<div class="li"><span class="nm">원화 항목 소계</span><span class="dots"></span><span class="v">${money(krw,'KRW')}</span></div>`);
  if(unknown) sub.push(`<div class="li unk"><span class="nm">금액 미확인</span><span class="dots"></span><span class="v">${unknown}건</span></div>`);

  const rate = parseFloat(String(S.rate).replace(/,/g,''));
  const conv = (rate>0) ? Math.round(usd*rate)+krw : null;

  const flags = [];
  items.forEach(it=>{
    if(it.f.status==='집행정지') flags.push(`<div class="stop">${it.label}: 법원 명령으로 집행이 정지된 항목입니다. 현재 납부 대상이 아닙니다.</div>`);
    else if(it.f.status==='검토필요') flags.push(`<div>${it.label}: 금액 또는 적용 여부가 확인되지 않았습니다. 견적 전 원문 대조가 필요합니다.</div>`);
  });

  return `<h2>${visa().label}</h2>
    <div class="who">${route().label} · 관납료 기준, 법무 수임료 별도</div>
    ${rows || '<div class="li"><span class="nm">항목 없음</span></div>'}
    ${sub.length?`<div class="sum">${sub.join('')}</div>`:''}
    <div class="total"><span class="l">미화 합계</span><span class="v">$${usd.toLocaleString('en-US')}</span></div>
    <div class="krw"><label for="rate">환율</label>
      <input id="rate" inputmode="decimal" value="${S.rate}" placeholder="1,400">
      <span class="out">${conv!=null ? conv.toLocaleString('ko-KR')+'원' : '원화 환산'}</span></div>
    ${flags.length?`<div class="flag">${[...new Set(flags)].join('')}</div>`:''}`;
}

function draw(keepFocus){
  document.getElementById('visas').innerHTML = chips();
  document.getElementById('controls').innerHTML = controls();
  document.getElementById('bill').innerHTML = bill();
  if(keepFocus){ const el=document.getElementById('rate'); if(el){ el.focus(); el.setSelectionRange(el.value.length,el.value.length); } }
}

document.addEventListener('click', e=>{
  const c = e.target.closest('[data-visa]');
  if(c){ S.visa=c.dataset.visa; S.route=visa().routes[0].id; S.opts={}; S.counts={}; return draw(); }
  const step = e.target.closest('[data-step]');
  if(step){ const k=step.dataset.opt; const n=(S.counts[k]||1)+Number(step.dataset.step);
    S.counts[k]=Math.min(10,Math.max(1,n)); return draw(); }
});
document.addEventListener('change', e=>{
  if(e.target.name==='route'){ S.route=e.target.value; S.opts={}; S.counts={}; return draw(); }
  if(e.target.dataset.opt!=null && e.target.type==='checkbox'){
    S.opts[e.target.dataset.opt]=e.target.checked;
    if(e.target.checked && !S.counts[e.target.dataset.opt]) S.counts[e.target.dataset.opt]=1;
    return draw();
  }
});
document.addEventListener('input', e=>{ if(e.target.id==='rate'){ S.rate=e.target.value; draw(true); } });
draw();
"""


def _checked_kst(state: dict[str, Any]) -> str:
    checked = state.get("checked_at")
    if not checked:
        return "확인 기록 없음"
    return (
        dt.datetime.fromisoformat(checked)
        .astimezone(dt.timezone(dt.timedelta(hours=9)))
        .strftime("마지막 확인 %Y-%m-%d %H:%M KST")
    )


def render_index(fees: dict[str, Any], state: dict[str, Any]) -> Path:
    scenarios = json.loads(SCENARIOS.read_text(encoding="utf-8"))
    index = {
        f["fee_id"]: {
            "amount": f.get("amount"),
            "currency": f.get("currency", "USD"),
            "item": f.get("item", ""),
            "status": f.get("status", ""),
        }
        for f in fees.get("fees", [])
    }
    js = JS.replace("__FEES__", json.dumps(index, ensure_ascii=False)).replace(
        "__VISAS__", json.dumps(scenarios["visas"], ensure_ascii=False)
    )
    cfg = site.load_cfg()
    body = f"""
<div class="visas" id="visas"></div>
<div class="cols">
  <div class="pick" id="controls"></div>
  <div class="bill" id="bill"></div>
</div>
{site.lead_form(cfg, "관납료 문의")}
{site.ad(cfg, "page_bottom")}
<p class="note">주한미국대사관 및 USCIS 납부 기준입니다. 법무 수임료와 공증·번역 실비는 포함하지 않습니다.
금액이 확인되지 않은 항목은 원장에서 채워야 합계에 반영됩니다.</p>
"""
    doc = (
        site.head(
            cfg, "비자별 관납료", INDEX_CSS,
            "미국 비자 종류별 관납료를 진행 경로와 동반가족까지 반영해 계산합니다.",
            path="", jsonld=site.jsonld_site(cfg),
        )
        + site.header(cfg, "index.html", _checked_kst(state))
        + body
        + site.footer(cfg)
    ).replace("</body></html>", f"<script>{js}</script></body></html>")
    DOCS.mkdir(parents=True, exist_ok=True)
    out = DOCS / "index.html"
    out.write_text(doc, encoding="utf-8")
    return out


def render_changes(fees: dict[str, Any], changelog: list[dict[str, Any]], state: dict[str, Any]) -> Path:
    rows = []
    for fee in fees.get("fees", []):
        color = STATUS_COLOR.get(fee.get("status", ""), "#6b7688")
        amount = fee.get("amount")
        currency = fee.get("currency", "USD")
        if amount is None:
            shown = "확인 필요"
        elif currency == "KRW":
            shown = f"{amount:,.0f}원"
        else:
            shown = f"${amount:,.0f}"
        pending = fee.get("pending_update")
        pend = ""
        if pending:
            pend = (
                f'<div class="pend">제안된 수정: {html.escape(str(pending.get("field")))} → '
                f'{html.escape(str(pending.get("proposed")))}. 근거: {html.escape(str(pending.get("reason")))[:200]}. '
                "승인 전까지 반영되지 않습니다.</div>"
            )
        url = fee.get("source_url") or ""
        item = html.escape(fee.get("item", ""))
        item_html = f'<a href="{html.escape(url)}">{item}</a>' if url else item
        rows.append(
            "<tr>"
            f'<td class="who">{html.escape(fee.get("fee_id", ""))}</td>'
            f'<td>{html.escape(fee.get("visa", ""))}</td>'
            f'<td class="who">{html.escape(fee.get("authority", ""))} · {html.escape(fee.get("form", "") or "")}</td>'
            f"<td>{item_html}{pend}</td>"
            f'<td class="amt">{shown}</td>'
            f'<td class="st"><b style="background:{color}"></b>{html.escape(fee.get("status", ""))}</td>'
            "</tr>"
        )

    log_html = []
    for entry in changelog[:15]:
        analysis = entry.get("analysis") or {}
        date = entry.get("date", "")[:16].replace("T", " ")
        title = html.escape(analysis.get("headline", "변경 감지"))
        body = html.escape(analysis.get("processing", "")) or "<br>".join(
            html.escape(f'{c.get("kind", "")}: {c.get("detail", "")}')[:300] for c in entry.get("changes", [])[:4]
        )
        links = " ".join(
            f'<a href="{html.escape(c.get("url", "#"))}">{html.escape(c.get("kind", "출처"))}</a>'
            for c in entry.get("changes", [])[:5]
        )
        log_html.append(
            f'<div class="entry"><div class="d">{html.escape(date)} UTC</div>'
            f'<div class="h">{title}</div><p>{body}</p><div class="d">{links}</div></div>'
        )

    cfg = site.load_cfg()
    body = f"""
<h3>원장</h3>
<table><thead><tr><th>ID</th><th>비자</th><th>납부처</th><th>항목</th>
<th style="text-align:right">금액</th><th>상태</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>
<h3>변경 이력</h3>
<div class="log">{''.join(log_html) or '<div class="entry"><div class="d">기록 없음</div><p>감시 시작 이후 감지된 변경이 없습니다.</p></div>'}</div>
"""
    doc = (
        site.head(cfg, "수수료 원장과 변경 이력", CHANGES_CSS,
                  "미국 이민 수수료의 현재 금액과 변경 이력을 출처와 함께 정리한 원장입니다.",
                  path="changes.html")
        + site.header(cfg, "changes.html", _checked_kst(state))
        + body
        + site.footer(cfg)
    )
    out = DOCS / "changes.html"
    out.write_text(doc, encoding="utf-8")
    return out


def render_static(cfg: dict[str, Any]) -> None:
    """도메인, 광고, 개인정보처리방침처럼 매 실행마다 같은 내용인 파일들."""
    from src import articles, cspa_page, static_pages

    cspa_page.render_cspa(cfg)
    articles.render_articles(cfg)
    static_pages.render_all(cfg)


def render(fees: dict[str, Any], changelog: list[dict[str, Any]], state: dict[str, Any]) -> Path:
    cfg = site.load_cfg()
    render_changes(fees, changelog, state)
    render_static(cfg)
    return render_index(fees, state)
