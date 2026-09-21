"""CSPA 나이 계산기 페이지.

계산은 전부 브라우저에서 돕니다. 입력한 생년월일과 사건 날짜가 서버로 가지 않습니다.
광고를 붙이는 사이트에서 이건 기능이 아니라 방어선입니다.

적용 규칙
- 우선순위 카테고리: CSPA 나이 = 비자 가용 시점의 실제 나이 - 청원 계류기간
- 비자 가용 시점 = 차트상 우선일이 도래한 날과 청원 승인일 중 나중
- 직계가족(IR): 청원 접수일의 나이로 고정, 계류기간 차감 없음
- 신분취득 노력 요건: 비자 가용일로부터 1년 이내
- 미국 내 신분조정은 접수가능일 차트, 영사수속은 최종행동일 차트를 적용하므로
  두 기준을 나란히 계산해 차이를 드러냅니다
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src import site

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

CSS = """
.lede{margin:20px 0 24px;max-width:72ch;color:var(--muted);font-size:14px}
.cols{display:grid;grid-template-columns:minmax(0,1fr) 400px;gap:34px;align-items:start}
.card{background:var(--paper);border:1px solid var(--rule);padding:18px 20px;margin-bottom:16px;border-radius:2px}
.card h2{font-size:13px;font-weight:600;color:var(--muted);margin:0 0 14px}
.f{display:flex;align-items:center;gap:12px;padding:9px 0;border-bottom:1px solid var(--hair)}
.f:last-child{border-bottom:0}
.f label{flex:1;font-size:14px}
.f label em{display:block;font-style:normal;font-size:12px;color:var(--faint);margin-top:1px}
.f input,.f select{border:1px solid var(--rule);padding:7px 9px;font:inherit;font-size:14px;
  border-radius:2px;background:var(--paper);color:var(--ink);width:172px;
  font-variant-numeric:tabular-nums}
.f input:focus,.f select:focus{outline:2px solid var(--ink);outline-offset:-1px;border-color:var(--ink)}
.f.wide input,.f.wide select{width:100%}
.res{background:var(--paper);border:1px solid var(--ink);border-top-width:3px;
  padding:22px;position:sticky;top:20px;border-radius:2px}
.res h2{font-size:15px;margin:0 0 14px;font-weight:700}
.two{display:grid;grid-template-columns:1fr 1fr;gap:14px}
.box{border:1px solid var(--hair);padding:13px 14px;border-radius:2px}
.box .k{font-size:12px;color:var(--faint);margin-bottom:6px}
.box .age{font-size:27px;font-weight:700;letter-spacing:-.03em;font-variant-numeric:tabular-nums;line-height:1.15}
.box .age small{font-size:14px;font-weight:600;color:var(--muted);margin-left:2px}
.box .verdict{font-size:13px;font-weight:650;margin-top:5px}
.box.safe{border-color:#bcd9c8;background:#f4faf6}
.box.safe .verdict{color:var(--ok)}
.box.risk{border-color:#e6bfc0;background:#fdf4f4}
.box.risk .verdict{color:var(--warn)}
.box.none{color:var(--faint)}
.rows{margin-top:16px;padding-top:12px;border-top:1px solid var(--hair);font-size:13px}
.r{display:flex;align-items:baseline;gap:6px;padding:5px 0}
.r .dots{flex:1;border-bottom:1px dotted var(--rule);transform:translateY(-3px)}
.r .v{font-variant-numeric:tabular-nums;white-space:nowrap;font-weight:600}
.r .k{color:var(--muted)}
.r.key .v{color:var(--ink)}
.r.miss .v{color:var(--pend);font-weight:400}
.warn{margin-top:14px;font-size:12.5px;line-height:1.55}
.warn div{padding:8px 11px;border-left:3px solid var(--pend);background:#fdf9ee;margin-top:6px}
.warn div.stop{border-left-color:var(--warn);background:#fdf2f2}
.guide{margin-top:40px;max-width:74ch}
.guide h3{font-size:15px;margin:26px 0 8px}
.guide p{color:var(--muted);font-size:14px;margin:0 0 10px}
.guide dl{margin:0}
.guide dt{font-weight:650;font-size:14px;margin-top:14px}
.guide dd{margin:3px 0 0;color:var(--muted);font-size:14px}
@media (max-width:860px){
  .cols{grid-template-columns:1fr;gap:20px}
  .res{position:static;order:-1}
  .f{flex-wrap:wrap}
  .f input,.f select{width:100%}
}
"""

JS = r"""
const $ = id => document.getElementById(id);
const D = s => { if(!s) return null; const [y,m,d]=s.split('-').map(Number);
  return (y&&m&&d) ? new Date(Date.UTC(y,m-1,d)) : null; };
const fmt = d => d ? d.toISOString().slice(0,10) : '';
const days = (a,b) => Math.round((a-b)/86400000);
const addDays = (d,n) => new Date(d.getTime()+n*86400000);
const addYears = (d,n) => new Date(Date.UTC(d.getUTCFullYear()+n, d.getUTCMonth(), d.getUTCDate()));
const later = (a,b) => (!a?b : !b?a : (a>b?a:b));

function exactAge(dob, on){
  let y = on.getUTCFullYear()-dob.getUTCFullYear();
  let m = on.getUTCMonth()-dob.getUTCMonth();
  let d = on.getUTCDate()-dob.getUTCDate();
  if(d<0){ m--; d += new Date(Date.UTC(on.getUTCFullYear(), on.getUTCMonth(), 0)).getUTCDate(); }
  if(m<0){ y--; m+=12; }
  return {y,m,d, under21: (y<21)};
}

function read(){
  return {
    cat: $('cat').value,
    dob: D($('dob').value),
    filed: D($('filed').value),
    approved: D($('approved').value),
    dff: D($('dff').value),
    fad: D($('fad').value),
    sought: D($('sought').value)
  };
}

function calcTrack(v, availRaw){
  // 비자 가용 시점은 차트 도래일과 승인일 중 나중입니다. 승인 전에는 비자를 받을 수 없습니다.
  const avail = later(availRaw, v.approved);
  if(!avail) return null;
  const pending = (v.filed && v.approved) ? Math.max(0, days(v.approved, v.filed)) : null;
  if(pending===null) return null;
  const adjusted = addDays(avail, -pending);
  const age = exactAge(v.dob, adjusted);
  const deadline = addDays(addYears(v.dob,21), pending); // 이 날 전에 가용되어야 21세 미만
  const seekBy = addYears(avail, 1);
  return {avail, pending, adjusted, age, deadline, seekBy,
          margin: days(deadline, avail),
          sought: v.sought ? (v.sought <= seekBy) : null};
}

function box(title, t){
  if(!t) return `<div class="box none"><div class="k">${title}</div><div class="age">–</div>
    <div class="verdict">입력 부족</div></div>`;
  const a = t.age;
  const cls = a.under21 ? 'safe' : 'risk';
  const verdict = a.under21 ? '21세 미만, 보호 대상' : '21세 이상, 보호 불가';
  return `<div class="box ${cls}"><div class="k">${title}</div>
    <div class="age">${a.y}<small>세</small> ${a.m}<small>개월</small> ${a.d}<small>일</small></div>
    <div class="verdict">${verdict}</div></div>`;
}

function detail(label, t){
  if(!t) return '';
  const seekNote = t.sought===null ? '' : (t.sought ? ' · 충족' : ' · 기한 초과');
  const seekCls = (t.sought===false) ? ' style="color:var(--warn)"' : '';
  return `<div class="rows">
    <div class="r key"><span class="k">${label} 비자 가용 기준일</span><span class="dots"></span><span class="v">${fmt(t.avail)}</span></div>
    <div class="r"><span class="k">청원 계류기간</span><span class="dots"></span><span class="v">${t.pending}일</span></div>
    <div class="r"><span class="k">나이 산정일, 가용일에서 계류기간 차감</span><span class="dots"></span><span class="v">${fmt(t.adjusted)}</span></div>
    <div class="r key"><span class="k">보호 마감 기준일</span><span class="dots"></span><span class="v">${fmt(t.deadline)}</span></div>
    <div class="r"><span class="k">신분취득 신청 기한</span><span class="dots"></span><span class="v"${seekCls}>${fmt(t.seekBy)}${seekNote}</span></div>
  </div>`;
}

function calc(){
  const v = read();
  const out = $('out');
  const isIR = v.cat === 'IR';

  document.querySelectorAll('.pref-only').forEach(el=>{ el.style.display = isIR ? 'none' : ''; });

  if(!v.dob || !v.filed){
    out.innerHTML = `<h2>계산 결과</h2><div class="two">${box('접수가능일 기준',null)}${box('최종행동일 기준',null)}</div>
      <div class="warn"><div>자녀 생년월일과 청원 접수일을 입력하면 계산됩니다.</div></div>`;
    return;
  }

  if(isIR){
    const age = exactAge(v.dob, v.filed);
    const cls = age.under21 ? 'safe':'risk';
    out.innerHTML = `<h2>계산 결과</h2>
      <div class="box ${cls}"><div class="k">직계가족, 청원 접수일 기준 고정</div>
      <div class="age">${age.y}<small>세</small> ${age.m}<small>개월</small> ${age.d}<small>일</small></div>
      <div class="verdict">${age.under21?'21세 미만, 보호 대상':'21세 이상, 보호 불가'}</div></div>
      <div class="rows">
        <div class="r key"><span class="k">나이 산정일</span><span class="dots"></span><span class="v">${fmt(v.filed)}</span></div>
        <div class="r"><span class="k">21세 도달일</span><span class="dots"></span><span class="v">${fmt(addYears(v.dob,21))}</span></div>
      </div>
      <div class="warn"><div>직계가족은 청원 접수 시점의 나이로 고정되며 계류기간을 차감하지 않습니다.
      청원인이 영주권자에서 시민권자로 바뀐 경우 전환 시점 기준이 달라지므로 별도 검토가 필요합니다.</div></div>
      ${CTA}${AD_SIDE}`;
    return;
  }

  const dff = calcTrack(v, v.dff);
  const fad = calcTrack(v, v.fad);
  const shown = dff || fad;

  const warns = [];
  if(dff && fad && dff.age.under21 !== fad.age.under21){
    warns.push(`<div class="stop">두 차트의 판정이 갈립니다. 미국 내 신분조정은 접수가능일 차트를,
      영사수속은 최종행동일 차트를 적용합니다. 어느 경로로 진행하는지에 따라 결과가 바뀌므로
      경로 선택 자체가 쟁점입니다.</div>`);
  }
  if(v.approved && ((v.dff && v.approved > v.dff) || (v.fad && v.approved > v.fad))){
    warns.push(`<div>우선일 도래보다 청원 승인이 늦어 승인일이 가용 기준일이 되었습니다.</div>`);
  }
  if(shown && shown.sought === false){
    warns.push(`<div class="stop">비자 가용일로부터 1년 내 신분취득 신청 요건을 넘겼습니다.
      예외 사유 해당 여부를 검토해야 합니다.</div>`);
  }
  if(shown && shown.margin < 180 && shown.margin > 0){
    warns.push(`<div>보호 마감까지 ${shown.margin}일 남았습니다. 우선일 퇴보 시 즉시 위험해집니다.</div>`);
  }
  warns.push(`<div>우선일이 도래했다가 퇴보한 이력이 있으면 최초 도래일을 가용일로 씁니다.
    과거 비자불레틴을 확인해 입력하십시오.</div>`);

  out.innerHTML = `<h2>계산 결과</h2>
    <div class="two">${box('접수가능일 기준', dff)}${box('최종행동일 기준', fad)}</div>
    ${detail('접수가능일', dff)}${detail('최종행동일', fad)}
    <div class="warn">${warns.join('')}</div>
    ${CTA}${AD_SIDE}`;
}

document.addEventListener('input', e=>{ if(e.target.closest('.card')) calc(); });
document.addEventListener('change', e=>{ if(e.target.closest('.card')) calc(); });
calc();
"""

GUIDE = """
<div class="guide">
<h3>계산 방식</h3>
<p>우선순위 카테고리의 CSPA 나이는 비자가 가용된 시점의 실제 나이에서 청원이 계류했던 기간을 뺀 값입니다.
비자 가용 시점은 우선일이 차트에 도달한 날과 청원이 승인된 날 중 나중입니다. 승인 전에는 비자를 받을 수 없기 때문입니다.
직계가족은 이 계산을 하지 않고 청원 접수일의 나이로 고정됩니다.</p>

<h3>어느 차트를 쓰는가</h3>
<p>여기가 실무에서 가장 자주 다투는 지점입니다. 미국 내에서 신분조정으로 진행하면 접수가능일 차트를,
해외 영사수속으로 진행하면 최종행동일 차트를 적용합니다. 두 차트의 날짜 차이가 몇 개월에서 몇 년까지 벌어지므로
같은 사건도 경로에 따라 보호 여부가 달라집니다. 이 계산기가 두 기준을 나란히 보여주는 이유입니다.</p>

<h3>날짜 세 개를 같이 보십시오</h3>
<dl>
<dt>비자 가용 기준일</dt>
<dd>나이를 재는 기준점입니다. 이 날이 언제냐에 따라 모든 결과가 바뀝니다.</dd>
<dt>보호 마감 기준일</dt>
<dd>이 날 전에 비자가 가용되어야 CSPA 나이가 21세 미만으로 남습니다.
대기 중인 사건에서 남은 시간을 가늠하는 숫자입니다.</dd>
<dt>신분취득 신청 기한</dt>
<dd>비자 가용일로부터 1년입니다. 나이가 보호되어도 이 기한을 놓치면 혜택을 잃습니다.</dd>
</dl>

<h3>이 계산기가 다루지 못하는 것</h3>
<p>우선일 퇴보 이력, 청원인의 시민권 취득에 따른 카테고리 전환, 카테고리 변경 요청,
난민·망명 파생 신분, 자동 전환 규정은 사건별 판단이 필요합니다.
숫자가 경계선에 가깝다면 계산 결과만으로 판단하지 마십시오.</p>
</div>
"""


def render_cspa(cfg: dict[str, Any] | None = None) -> Path:
    cfg = cfg or site.load_cfg()
    # 광고와 전환 동선은 렌더 시점에 문자열로 주입합니다.
    js = JS.replace("${CTA}", site.cta(cfg).replace("`", "")).replace(
        "${AD_SIDE}", site.ad(cfg, "result_side", "ad ad-side").replace("`", "")
    )

    body = f"""
<p class="lede">청원 접수일, 승인일, 우선일 도래일을 넣으면 CSPA 나이와 판정 근거가 되는 날짜를 계산합니다.
접수가능일 차트와 최종행동일 차트를 나란히 계산하므로 진행 경로에 따른 차이를 바로 확인할 수 있습니다.
입력한 내용은 이 브라우저 안에서만 계산되며 서버로 전송되지 않습니다.</p>

<div class="cols">
  <div>
    <div class="card">
      <h2>사건 정보</h2>
      <div class="f wide"><label for="cat">카테고리</label>
        <select id="cat">
          <option value="F2A">F-2A 영주권자의 미성년 자녀</option>
          <option value="F1">F-1 시민권자의 미혼 성년 자녀</option>
          <option value="F2B">F-2B 영주권자의 미혼 성년 자녀</option>
          <option value="F3">F-3 시민권자의 기혼 자녀</option>
          <option value="F4">F-4 시민권자의 형제자매</option>
          <option value="EB">취업이민 EB-1·2·3</option>
          <option value="EB5">투자이민 EB-5</option>
          <option value="IR">직계가족 IR, 계류기간 차감 없음</option>
        </select></div>
      <div class="f"><label for="dob">자녀 생년월일</label><input type="date" id="dob"></div>
      <div class="f"><label for="filed">청원 접수일<em>I-130, I-140, I-526E 등</em></label><input type="date" id="filed"></div>
      <div class="f pref-only"><label for="approved">청원 승인일</label><input type="date" id="approved"></div>
    </div>

    <div class="card pref-only">
      <h2>비자 가용일</h2>
      <div class="f"><label for="dff">접수가능일 차트 도래일<em>미국 내 신분조정 기준</em></label><input type="date" id="dff"></div>
      <div class="f"><label for="fad">최종행동일 차트 도래일<em>영사수속 기준</em></label><input type="date" id="fad"></div>
      <div class="f"><label for="sought">신분취득 신청일<em>I-485 접수 또는 DS-260 제출일</em></label><input type="date" id="sought"></div>
    </div>
  </div>

  <div class="res" id="out"></div>
</div>

{GUIDE}
{site.lead_form(cfg, "CSPA 나이")}
{site.ad(cfg, "page_bottom")}
"""
    doc = (
        site.head(cfg, "CSPA 나이 계산기", CSS, "미국 이민 CSPA 나이 계산기. 접수가능일과 최종행동일 차트 기준을 함께 계산합니다.")
        + site.header(cfg, "cspa.html")
        + body
        + site.footer(cfg)
    ).replace("</body></html>", f"<script>{js}</script></body></html>")

    DOCS.mkdir(parents=True, exist_ok=True)
    out = DOCS / "cspa.html"
    out.write_text(doc, encoding="utf-8")
    return out
