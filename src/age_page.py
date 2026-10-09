"""만 나이 계산기 페이지.

CSPA 계산기와 마찬가지로 계산은 전부 브라우저에서 돕니다.

적용 규칙
- 만 나이: 생일이 지나야 한 살이 늘어납니다. 기준일이 생일 당일이면 늘어난 나이입니다.
- 2월 29일생은 평년에 3월 1일부터 한 살이 늘어납니다. 민법 제160조 기간 계산과 같습니다.
- 연 나이: 기준 연도 - 출생 연도. 병역법, 청소년보호법 등 일부 법령이 씁니다.
- 주소 ?b=YYYYMMDD[&d=YYYYMMDD]로 입력값을 복원합니다. d가 없으면 오늘 기준입니다.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src import site

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

CSS = """
.lede{margin:20px 0 24px;max-width:72ch;color:var(--muted);font-size:14px}
.card{background:var(--paper);border:1px solid var(--rule);padding:18px 20px;border-radius:2px;max-width:640px}
.card h2{font-size:13px;font-weight:600;color:var(--muted);margin:0 0 10px}
.f{display:flex;align-items:center;gap:12px;padding:10px 0;border-bottom:1px solid var(--hair)}
.f label{width:64px;flex:none;font-size:14px;font-weight:600}
.f input{flex:1;min-width:0;border:1px solid var(--rule);padding:8px 10px;font:inherit;font-size:14px;
  border-radius:2px;background:var(--paper);color:var(--ink);font-variant-numeric:tabular-nums}
.f input:focus{outline:2px solid var(--ink);outline-offset:-1px;border-color:var(--ink)}
.f .today{flex:none;width:64px;padding:8px 0}
.f .spacer{flex:none;width:64px}
.btn{border:1px solid var(--ink);background:var(--paper);color:var(--ink);font:inherit;font-size:14px;
  font-weight:600;padding:8px 14px;border-radius:2px;cursor:pointer;white-space:nowrap}
.btn.solid{background:var(--ink);color:#fff}
.btn:hover{opacity:.88}
.acts{display:flex;justify-content:center;gap:8px;padding-top:16px}
.acts .btn{min-width:96px}
.res{max-width:640px;margin-top:16px;background:var(--paper);border:1px solid var(--ink);border-top-width:3px;
  padding:20px 22px;border-radius:2px}
.res[hidden]{display:none}
.res .hd{margin:-20px -22px 14px;padding:14px 22px;background:var(--ground);border-bottom:1px solid var(--hair);
  text-align:center;font-size:15px;line-height:1.6}
.res .hd b{font-variant-numeric:tabular-nums}
.res .err{color:var(--warn);font-size:14px;font-weight:600}
.it{border:1px solid var(--hair);padding:10px 14px;margin-bottom:6px;border-radius:2px;font-size:14.5px;line-height:1.6}
.it b{font-variant-numeric:tabular-nums}
.it.main{border-color:var(--ink);border-left-width:4px;font-size:15.5px}
.it.main b{font-size:17px}
.it .sub{display:block;color:var(--muted);font-size:13.5px}
.it.bm{background:#f3f6fa;color:var(--muted);font-size:13.5px}
.it.bm b{color:var(--ink)}
.marks{margin-top:14px;padding-top:12px;border-top:1px solid var(--hair)}
.marks h3{font-size:13px;font-weight:600;color:var(--muted);margin:0 0 6px}
.m{display:flex;gap:10px;padding:6px 0;font-size:13.5px;line-height:1.5}
.m .t{flex:none;font-size:12px;font-weight:650;padding:1px 7px;border-radius:2px;height:fit-content;
  border:1px solid var(--rule);color:var(--faint);white-space:nowrap}
.m.on .t{border-color:#bcd9c8;background:#f4faf6;color:var(--ok)}
.m .d{color:var(--muted)}
.m.on .d{color:var(--ink)}
.m a{color:inherit}
.guide{margin-top:40px;max-width:74ch}
.guide h3{font-size:15px;margin:26px 0 8px}
.guide p{color:var(--muted);font-size:14px;margin:0 0 10px}
@media (max-width:520px){
  .f label{width:52px}
  .f .today,.f .spacer{width:56px}
}
"""

JS = r"""
const $ = id => document.getElementById(id);
const D = s => { if(!s) return null; const [y,m,d]=s.split('-').map(Number);
  return (y&&m&&d) ? new Date(Date.UTC(y,m-1,d)) : null; };
const fmt = d => d.toISOString().slice(0,10);
const days = (a,b) => Math.round((a-b)/86400000);
const todayStr = () => { const t=new Date();
  return new Date(Date.UTC(t.getFullYear(),t.getMonth(),t.getDate())).toISOString().slice(0,10); };

function exactAge(dob, on){
  let y = on.getUTCFullYear()-dob.getUTCFullYear();
  let m = on.getUTCMonth()-dob.getUTCMonth();
  let d = on.getUTCDate()-dob.getUTCDate();
  if(d<0){ m--; d += new Date(Date.UTC(on.getUTCFullYear(), on.getUTCMonth(), 0)).getUTCDate(); }
  if(m<0){ y--; m+=12; }
  return {y,m,d};
}

// 해당 연도의 생일. 평년의 2월 29일생은 Date.UTC가 3월 1일로 넘겨 줍니다.
const birthdayIn = (dob, year) => new Date(Date.UTC(year, dob.getUTCMonth(), dob.getUTCDate()));

// 미국 이민 실무에서 나이가 기준이 되는 지점들. 해당 나이에 이르면 on 표시됩니다.
const MARKS = [
  {age:14, test:a=>a>=14, t:'만 14세', d:'영주권자 자녀는 만 14세 생일 후 30일 안에 외국인 등록과 지문 날인을 다시 해야 합니다.'},
  {age:18, test:a=>a<18, t:'만 18세 미만', d:'불법체류 기간(unlawful presence)이 누적되지 않습니다.'},
  {age:21, test:a=>a<21, t:'만 21세 미만', d:'동반 자녀로 비자·영주권을 받을 수 있습니다. 21세에 가까우면 <a href="cspa.html">CSPA 나이</a>를 확인하십시오.'},
];

const WD = ['일','월','화','수','목','금','토'];
const ANIMAL = ['쥐','소','호랑이','토끼','용','뱀','말','양','원숭이','닭','개','돼지'];
const GAN = ['갑','을','병','정','무','기','경','신','임','계'], GAN_H = '甲乙丙丁戊己庚辛壬癸';
const JI = ['자','축','인','묘','진','사','오','미','신','유','술','해'], JI_H = '子丑寅卯辰巳午未申酉戌亥';
const ganji = y => { const g=((y-4)%10+10)%10, j=((y-4)%12+12)%12;
  return {animal:ANIMAL[j], ko:GAN[g]+JI[j], hanja:GAN_H[g]+JI_H[j]}; };
const kdate = d => `${d.getUTCFullYear()}년 ${d.getUTCMonth()+1}월 ${d.getUTCDate()}일(${WD[d.getUTCDay()]})`;
const n = x => x.toLocaleString('ko-KR');
const compact = s => s.replaceAll('-','');
const fromCompact = s => /^\d{8}$/.test(s||'') ? `${s.slice(0,4)}-${s.slice(4,6)}-${s.slice(6)}` : '';

// 주소에 출생일을 남겨 북마크하면 바로 오늘 기준 나이가 나오게 합니다.
// 기준일이 오늘이면 주소에 넣지 않아야 나중에 열어도 그날 기준으로 계산됩니다.
function syncUrl(){
  const b=$('dob').value, d=$('on').value;
  const q = new URLSearchParams();
  if(b) q.set('b', compact(b));
  if(b && d && d!==todayStr()) q.set('d', compact(d));
  const qs = q.toString();
  history.replaceState(null, '', location.pathname + (qs?'?'+qs:''));
}

function calc(){
  const out = $('out');
  const dob = D($('dob').value), on = D($('on').value);
  syncUrl();
  if(!dob || !on){ out.hidden = true; return; }
  out.hidden = false;
  if(dob > on){
    out.innerHTML = '<div class="err">출생일이 기준일보다 늦습니다.</div>';
    return;
  }
  const a = exactAge(dob, on);
  const y0 = on.getUTCFullYear();
  let last = birthdayIn(dob, y0);
  if(last > on) last = birthdayIn(dob, y0-1);
  const next = birthdayIn(dob, last.getUTCFullYear()+1);
  const sinceLast = days(on, last), toNext = days(next, on);
  const decimal = (a.y + sinceLast/days(next,last)).toFixed(2);
  const yearAge = y0 - dob.getUTCFullYear();
  const bg = ganji(dob.getUTCFullYear()), og = ganji(y0);
  const earlyYear = dob.getUTCMonth() < 2;
  const at21 = birthdayIn(dob, dob.getUTCFullYear()+21);

  const marks = MARKS.map(k => `<div class="m${k.test(a.y)?' on':''}"><span class="t">${k.t}</span><span class="d">${k.d}</span></div>`).join('');

  out.innerHTML = `<div class="hd">출생일 <b>${kdate(dob)}</b>의<br><b>${kdate(on)}</b> 기준 나이 정보</div>
    <div class="it main"><b>만 나이</b>는 <b>${a.y}세</b>입니다.
      <span class="sub">${sinceLast===0 ? `오늘 만 ${a.y}세가 되었습니다.` : `만 ${a.y}세가 된 지 ${n(sinceLast)}일 지났습니다.`}
      다음 생일 ${kdate(next)}까지 ${n(toNext)}일 남았습니다.</span></div>
    <div class="it"><b>한국 나이</b>(세는 나이)는 <b>${yearAge+1}살</b>입니다.</div>
    <div class="it"><b>연 나이</b>는 <b>${yearAge}세</b>입니다.</div>
    <div class="it"><b>${bg.animal}띠</b>입니다. ${dob.getUTCFullYear()}년은 ${bg.ko}(${bg.hanja})년입니다.
      ${earlyYear ? '<span class="sub">띠는 음력 설을 기준으로 바뀌므로, 설 전에 태어났다면 전년도 띠일 수 있습니다.</span>' : ''}</div>
    <div class="it">태어난 지 <b>${n(days(on,dob))}일</b> 지났습니다.</div>
    <div class="it"><b>${a.y}년 ${a.m}개월 ${a.d}일</b> 살았습니다.</div>
    <div class="it">생후 <b>${n(a.y*12+a.m)}개월</b>입니다.</div>
    <div class="it">소수점으로 계산한 나이는 <b>${decimal}세</b>입니다.</div>
    <div class="it">만 21세가 되는 날은 <b>${kdate(at21)}</b>입니다.</div>
    <div class="it">${y0}년은 <b>${og.animal}띠</b> 해, <b>${og.ko}(${og.hanja})년</b>입니다.</div>
    <div class="it bm">이 페이지를 <b>북마크</b>하거나 <b>홈 화면에 추가</b>하면 언제든 그날 기준 나이를 바로 확인할 수 있습니다.</div>
    <div class="marks"><h3>미국 이민에서 나이가 기준이 되는 지점</h3>${marks}</div>`;
}

$('todayBtn').addEventListener('click', ()=>{ $('on').value = todayStr(); calc(); });
$('calcBtn').addEventListener('click', calc);
$('resetBtn').addEventListener('click', ()=>{ $('dob').value=''; $('on').value=todayStr(); $('out').hidden=true; syncUrl(); $('dob').focus(); });
['dob','on'].forEach(id => { $(id).addEventListener('change', calc);
  $(id).addEventListener('keydown', e=>{ if(e.key==='Enter') calc(); }); });

const q = new URLSearchParams(location.search);
$('dob').value = fromCompact(q.get('b'));
$('on').value = fromCompact(q.get('d')) || todayStr();
if($('dob').value) calc();
"""

GUIDE = """
<div class="guide">
<h3>만 나이 계산 방식</h3>
<p>출생일에 0세로 시작해 생일이 지날 때마다 한 살씩 늘어납니다. 기준일이 생일 당일이면 늘어난 나이로 계산합니다.
2023년 6월부터 법령과 계약서의 나이는 특별한 규정이 없으면 만 나이로 봅니다.
2월 29일생은 평년에는 3월 1일에 한 살이 늘어납니다.</p>

<h3>미국 서류의 나이</h3>
<p>미국 이민 서류의 나이는 모두 만 나이입니다. 다만 동반 자녀 자격을 따지는 21세 기준은
실제 나이가 아니라 청원 계류기간을 뺀 CSPA 나이로 판단하는 경우가 많습니다.
21세 전후라면 <a href="cspa.html">CSPA 나이 계산기</a>로 따로 확인하십시오.</p>
</div>
"""


def render_age(cfg: dict[str, Any] | None = None) -> Path:
    cfg = cfg or site.load_cfg()
    body = f"""
<p class="lede">출생일과 기준일을 넣으면 만 나이, 한국 나이, 연 나이와 띠를 계산합니다. 기준일은 오늘로 채워져 있습니다.
계산하면 주소에 출생일이 붙으므로 그 주소를 북마크하면 열 때마다 그날 기준 나이가 바로 나옵니다.
입력한 내용은 이 브라우저 안에서만 계산되며 서버로 전송되지 않습니다.</p>

<div class="card">
  <h2>생년월일을 입력하십시오</h2>
  <div class="f"><label for="dob">출생일</label><input type="date" id="dob"><span class="spacer"></span></div>
  <div class="f"><label for="on">기준일</label><input type="date" id="on">
    <button type="button" class="btn today" id="todayBtn">오늘</button></div>
  <div class="acts">
    <button type="button" class="btn solid" id="calcBtn">계산</button>
    <button type="button" class="btn" id="resetBtn">초기화</button>
  </div>
</div>

<div class="res" id="out" hidden></div>

{GUIDE}
{site.ad(cfg, "page_bottom")}
"""
    doc = (
        site.head(
            cfg, "만 나이 계산기", CSS,
            "출생일과 기준일로 만 나이를 계산합니다. 한국 나이, 연 나이, 띠, 태어난 날수, 다음 생일까지 함께 보여줍니다.",
            path="age.html",
            jsonld=site.jsonld_tool(
                cfg, "만 나이 계산기",
                "출생일과 기준일로 만 나이와 한국 나이, 연 나이를 계산합니다.", "age.html",
            ),
        )
        + site.header(cfg, "age.html")
        + body
        + site.footer(cfg)
    ).replace("</body></html>", f"<script>{JS}</script></body></html>")

    DOCS.mkdir(parents=True, exist_ok=True)
    out = DOCS / "age.html"
    out.write_text(doc, encoding="utf-8")
    return out
