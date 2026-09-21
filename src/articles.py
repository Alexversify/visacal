"""가이드 페이지.

애드센스는 도구만 있는 사이트를 반려합니다. 검색 유입도 계산기가 아니라
설명 글에서 들어옵니다. 여기 글이 광고 수익과 문의 유입의 실제 입구입니다.

글을 추가하려면 ARTICLES에 항목을 하나 넣으면 됩니다. 목록과 사이트맵에 자동 반영됩니다.
"""

from __future__ import annotations

import html
from pathlib import Path
from typing import Any

from src import site

ROOT = Path(__file__).resolve().parents[1]
DOCS = ROOT / "docs"

CSS = """
.art{max-width:72ch;margin-top:26px}
.art .kicker{font-size:12.5px;color:var(--faint);margin-bottom:6px}
.art h1{font-size:26px;line-height:1.3;letter-spacing:-.025em;margin:0 0 12px}
.art .sum{font-size:15px;color:var(--muted);padding-bottom:18px;border-bottom:1px solid var(--rule)}
.art h2{font-size:17px;margin:32px 0 10px;letter-spacing:-.01em}
.art h3{font-size:15px;margin:22px 0 6px}
.art p{margin:0 0 13px}
.art ul,.art ol{padding-left:20px;margin:0 0 13px}
.art li{margin-bottom:5px}
.art table{width:100%;border-collapse:collapse;font-size:14px;margin:14px 0 18px;background:var(--paper)}
.art th{text-align:left;font-size:12.5px;color:var(--faint);font-weight:600;padding:8px 10px;border-bottom:1px solid var(--rule)}
.art td{padding:8px 10px;border-bottom:1px solid var(--hair)}
.art td.n{text-align:right;font-variant-numeric:tabular-nums;font-weight:600;white-space:nowrap}
.art blockquote{margin:16px 0;padding:12px 16px;background:var(--paper);
  border-left:3px solid var(--ink);font-size:14px;color:var(--muted)}
.art .tool{display:block;margin:20px 0;padding:14px 16px;background:var(--paper);
  border:1px solid var(--rule);text-decoration:none;border-radius:2px}
.art .tool b{display:block;font-size:14.5px}
.art .tool span{font-size:13px;color:var(--faint)}
.list{margin-top:26px;max-width:74ch}
.list a{display:block;padding:18px 0;border-bottom:1px solid var(--rule);text-decoration:none}
.list a:first-child{border-top:1px solid var(--rule)}
.list b{display:block;font-size:16px;margin-bottom:4px;letter-spacing:-.01em}
.list span{font-size:13.5px;color:var(--muted)}
"""

TOOL_CSPA = """<a class="tool" href="cspa.html"><b>CSPA 나이 계산기</b>
<span>접수가능일 차트와 최종행동일 차트를 나란히 계산합니다</span></a>"""
TOOL_FEE = """<a class="tool" href="index.html"><b>비자별 관납료 계산기</b>
<span>진행 경로와 동반가족 수를 반영해 납부 총액을 계산합니다</span></a>"""


ARTICLES: list[dict[str, str]] = [
    {
        "slug": "guide-cspa.html",
        "kicker": "CSPA",
        "title": "CSPA 나이 계산, 무엇을 언제 기준으로 재는가",
        "summary": "자녀가 21세를 넘겨도 이민 대상으로 남을 수 있는지는 실제 나이가 아니라 CSPA 나이로 결정됩니다. 계산 구조와 자주 틀리는 지점을 정리했습니다.",
        "topic": "CSPA 나이",
        "body": """
<p>미국 이민법에서 자녀는 21세 미만이어야 부모의 신청에 함께 포함됩니다. 그런데 우선일 대기가 몇 년씩 걸리는 카테고리에서는
아이가 기다리는 동안 21세를 넘기는 일이 흔합니다. 이런 경우를 구제하기 위해 만든 것이 아동신분보호법(CSPA)입니다.
핵심은 실제 나이가 아닌 별도로 계산한 나이, 이른바 CSPA 나이로 판단한다는 점입니다.</p>

<h2>계산 구조</h2>
<p>우선순위 카테고리에서 CSPA 나이는 두 단계로 나옵니다.</p>
<ol>
<li>비자가 가용된 시점의 실제 나이를 구합니다.</li>
<li>거기서 청원이 심사에 걸려 있던 기간을 뺍니다.</li>
</ol>
<p>청원 계류기간은 승인일에서 접수일을 뺀 일수입니다. 행정 처리가 오래 걸린 책임을 신청인에게 지우지 않는다는 취지입니다.
계류가 길었던 사건일수록 이 차감이 크고, 그만큼 보호 가능성이 올라갑니다.</p>

<h2>비자 가용 시점이 언제인가</h2>
<p>여기가 실무에서 가장 많이 틀립니다. 가용 시점은 두 날짜 중 나중입니다.</p>
<ul>
<li>비자불레틴 차트에서 우선일이 도래한 날</li>
<li>청원이 승인된 날</li>
</ul>
<p>승인되지 않은 청원으로는 비자를 받을 수 없으므로, 차트상 순번이 먼저 와도 승인이 늦으면 승인일이 기준이 됩니다.
반대로 승인이 훨씬 먼저 끝났다면 차트 도래일이 기준입니다.</p>

<h2>직계가족은 계산하지 않는다</h2>
<p>시민권자의 직계가족(IR)은 대기 순번이 없으므로 계류기간 차감도 없습니다.
청원을 접수한 날의 나이로 고정되며, 그날 21세 미만이었다면 이후 심사가 얼마나 길어지든 자녀로 남습니다.
영주권자 청원이 진행 중에 청원인이 시민권을 취득해 카테고리가 바뀌는 경우는 별도 검토가 필요합니다.</p>

<h2>나이가 보호되어도 놓치는 요건</h2>
<p>CSPA 나이가 21세 미만으로 나왔다고 끝이 아닙니다. 비자 가용일로부터 1년 안에 영주권 취득을 위한 신청을 해야 합니다.
미국 내에서는 신분조정 신청, 해외에서는 이민비자 신청서 제출이 이에 해당합니다.
나이 계산에만 집중하다가 이 1년을 넘겨 자격을 잃는 사례가 적지 않습니다.</p>

<blockquote>계산 결과에서 세 개의 날짜를 같이 확인하십시오. 나이를 재는 기준일, 그 전에 비자가 가용되어야 하는 마감 기준일,
그리고 신청 기한 1년입니다. 이 셋 중 하나만 어긋나도 결론이 바뀝니다.</blockquote>

<h2>퇴보가 있었다면</h2>
<p>우선일이 도래했다가 다시 뒤로 밀리는 퇴보는 드물지 않습니다. 이런 경우 최초로 도래한 시점을 가용일로 봅니다.
따라서 과거 비자불레틴을 거슬러 확인해야 하고, 지금 차트만 보고 계산하면 실제보다 나이가 많게 나옵니다.
아래 계산기에 가용일을 직접 입력하도록 만든 이유입니다.</p>
""" + TOOL_CSPA,
    },
    {
        "slug": "guide-charts.html",
        "kicker": "비자불레틴",
        "title": "접수가능일과 최종행동일, 어느 차트를 봐야 하는가",
        "summary": "같은 사건인데 CSPA 판정이 갈린다면 대개 차트를 잘못 골랐기 때문입니다. 두 차트의 용도와 적용 경로를 구분합니다.",
        "topic": "차트 적용",
        "body": """
<p>매달 나오는 비자불레틴에는 카테고리마다 두 개의 날짜가 있습니다. 최종행동일과 접수가능일입니다.
이름만 보면 비슷해 보이지만 용도가 완전히 다르고, 두 날짜의 간격이 몇 개월에서 몇 년까지 벌어집니다.</p>

<h2>두 차트의 용도</h2>
<h3>최종행동일</h3>
<p>실제로 영주권이 승인되고 비자가 발급될 수 있는 순번입니다. 이 날짜가 우선일을 지나야 최종 결정이 납니다.
해외 영사수속에서는 이 차트가 기준입니다.</p>

<h3>접수가능일</h3>
<p>최종 결정은 아직 못 받지만 서류 접수는 시작해도 되는 순번입니다. 최종행동일보다 앞서 있어
실제 승인보다 먼저 접수를 열어주는 장치입니다. 미국 내 신분조정에서는 매달 이 차트 사용이 허용되는지 별도로 공지됩니다.</p>

<h2>CSPA에서 왜 문제가 되는가</h2>
<p>비자가 가용된 시점이 CSPA 나이의 기준점이므로, 어느 차트로 가용 여부를 판단하느냐에 따라 기준일이 달라집니다.
접수가능일이 몇 년 앞서 있는 카테고리라면 그 차트를 쓸 때 나이가 훨씬 어리게 나옵니다.</p>
<p>미국 내에서 신분조정으로 진행하고 해당 월에 접수가능일 차트 사용이 허용된다면 그 차트로 판단합니다.
해외 영사수속으로 진행한다면 최종행동일 차트가 기준입니다.
같은 가족이 일부는 미국 내에서, 일부는 해외에서 진행하는 경우 결과가 갈릴 수 있습니다.</p>

<h2>실무에서 확인할 순서</h2>
<ol>
<li>진행 경로를 먼저 정합니다. 미국 내 신분조정인지 해외 영사수속인지에 따라 볼 차트가 정해집니다.</li>
<li>해당 월 비자불레틴에서 그 카테고리와 출생국의 날짜를 확인합니다.</li>
<li>우선일이 그 날짜를 지난 시점을 찾습니다. 지금이 아니라 처음 지난 시점입니다.</li>
<li>청원 승인일과 비교해 나중인 날을 가용일로 씁니다.</li>
</ol>

<p>경로 선택이 판정을 바꾼다는 것은, 반대로 말하면 선택의 여지가 있는 사건에서는 경로 자체가 전략이라는 뜻입니다.
두 기준을 모두 계산해보고 차이를 확인한 다음 결정하는 편이 안전합니다.</p>
""" + TOOL_CSPA,
    },
    {
        "slug": "guide-e2-cost.html",
        "kicker": "E-2",
        "title": "E-2 비자 관납료, 한국 진행과 미국 내 신분변경 비교",
        "summary": "같은 E-2인데 한국 대사관에서 받는 경우와 미국 안에서 신분을 바꾸는 경우 납부액이 크게 다릅니다. 항목별로 나눠 봅니다.",
        "topic": "E-2 비용",
        "body": """
<p>E-2는 진행 방식이 두 가지입니다. 한국에서 주한미국대사관 인터뷰를 거쳐 비자를 받는 방법과,
이미 미국에 합법 체류 중인 상태에서 신분을 E-2로 변경하는 방법입니다. 절차가 다르니 납부처와 금액도 다릅니다.</p>

<h2>한국에서 진행하는 경우</h2>
<p>국무부 소관입니다. E-2는 조약투자자 비자로 상호주의가 적용되어 국적별로 금액이 다르고,
한국 국적자는 <strong>315달러</strong>입니다. 동반가족은 1인당 같은 금액이 붙습니다.</p>
<table>
<tr><th>항목</th><th>납부처</th><th style="text-align:right">금액</th></tr>
<tr><td>비이민 신청 수수료</td><td>국무부</td><td class="n">$315</td></tr>
<tr><td>동반가족, 1인당</td><td>국무부</td><td class="n">$315</td></tr>
<tr><td>여권 택배 수령</td><td>배송업체</td><td class="n">22,000원</td></tr>
</table>
<p>4인 가족이라면 신청 수수료만 1,260달러입니다. 상담에서 이 부분을 빼놓으면 나중에 금액이 어긋납니다.</p>

<h2>미국 내에서 신분변경하는 경우</h2>
<p>이민국 소관이고 구조가 더 복잡합니다. 청원 수수료에 망명 프로그램 수수료가 따로 붙고,
사업장 규모에 따라 금액이 나뉩니다. 소규모 사업장은 감액된 금액이 적용됩니다.</p>
<table>
<tr><th>항목</th><th>소형 사업장</th><th>일반 사업장</th></tr>
<tr><td>청원 신청 수수료</td><td class="n">$510</td><td class="n">$1,015</td></tr>
<tr><td>망명 프로그램 수수료</td><td class="n">$300</td><td class="n">$600</td></tr>
<tr><td>합계</td><td class="n">$810</td><td class="n">$1,615</td></tr>
</table>
<p>동반가족은 별도 양식으로 신청하며 가족 단위로 <strong>470달러</strong>가 붙습니다.
한국 진행이 1인당 과금인 것과 달리 여기서는 가족 그룹 단위라, 가족이 많을수록 미국 내 진행이 유리해지는 구간이 생깁니다.</p>

<h2>급행 처리</h2>
<p>미국 내 진행에서만 선택할 수 있습니다. 추가로 <strong>2,965달러</strong>를 내면 심사 기간이 크게 단축됩니다.
사업 일정이 걸려 있는 사건에서는 사실상 필수 비용으로 봐야 합니다.</p>

<h2>사업장 규모 판정을 먼저 하십시오</h2>
<p>소형과 일반의 차이가 800달러를 넘습니다. 직원 수와 비영리 여부에 따라 갈리므로
견적을 내기 전에 이 판정을 확정해야 합니다. 여기가 어긋나면 견적 전체가 틀립니다.</p>

<p>위 금액은 관납료만입니다. 법무 수임료, 사업계획서 작성, 번역과 공증은 별도입니다.</p>
""" + TOOL_FEE,
    },
    {
        "slug": "guide-l1-blanket-cost.html",
        "kicker": "L-1",
        "title": "L-1 Blanket 비용 구조와 개별청원과의 차이",
        "summary": "Blanket 승인을 받은 기업은 개별 청원을 건너뛰고 대사관에서 바로 진행합니다. 비용 구조가 달라지는 지점을 짚습니다.",
        "topic": "L-1 비용",
        "body": """
<p>L-1은 주재원 비자입니다. 일정 규모 이상의 기업은 Blanket 승인을 미리 받아두고,
개별 직원을 파견할 때마다 청원을 새로 넣지 않고 대사관에서 바로 비자를 신청할 수 있습니다.
이 차이가 비용 구조를 바꿉니다.</p>

<h2>Blanket으로 대사관에서 진행하는 경우</h2>
<table>
<tr><th>항목</th><th>납부처</th><th style="text-align:right">금액</th></tr>
<tr><td>비이민 신청 수수료, 청원 기반</td><td>국무부</td><td class="n">$205</td></tr>
<tr><td>사기방지 조사 수수료</td><td>국무부</td><td class="n">$500</td></tr>
<tr><td>동반가족, 1인당</td><td>국무부</td><td class="n">$205</td></tr>
</table>
<p>사기방지 조사 수수료는 Blanket 진행에서 신청자가 대사관에 납부합니다.
개별청원에서는 청원 단계에서 고용주가 이민국에 내는 항목이라, 같은 성격의 비용이 다른 단계에 나타납니다.</p>

<h2>대기업에 붙는 추가 수수료</h2>
<p>직원 50명을 넘고 그 중 절반 이상이 H-1B 또는 L 신분인 기업은 별도의 추가 수수료 대상입니다.
금액이 <strong>4,500달러</strong>로 크기 때문에 해당 여부를 먼저 판정해야 합니다.
파견 규모가 큰 기업에서는 이 항목이 전체 비용의 대부분을 차지합니다.</p>

<h2>개별청원으로 가는 경우</h2>
<p>Blanket 승인이 없거나 직책이 Blanket 범위를 벗어나면 개별 청원을 넣습니다.
이민국에 청원 수수료와 망명 프로그램 수수료를 내고, 승인 후 다시 대사관에서 비자 신청 수수료를 냅니다.
단계가 둘로 나뉘므로 총액도 올라가고 기간도 길어집니다.</p>
<p>2026년 9월 개정된 수수료 고지서에는 H-1B와 L 청원에 생체정보 관련 수수료가 추가되었습니다.
연장이 아닌 수정 청원은 제외되는 등 적용 범위에 조건이 있어, 청원 유형을 먼저 확정해야 합니다.</p>

<h2>어느 쪽이 유리한가</h2>
<p>파견 인원이 여러 명이고 직책이 Blanket 범위에 들어간다면 Blanket이 명확히 유리합니다.
한 명을 보내는 경우라면 Blanket 승인 자체를 유지하는 비용까지 감안해 판단해야 합니다.
동반가족 수에 따라서도 총액이 달라지므로 계산기에서 인원을 넣고 비교해보십시오.</p>
""" + TOOL_FEE,
    },
    {
        "slug": "guide-fee-faq.html",
        "kicker": "수수료",
        "title": "미국 비자 수수료, 자주 나오는 질문",
        "summary": "누가 내는가, 환불되는가, 왜 나라마다 금액이 다른가. 상담에서 반복되는 질문을 모았습니다.",
        "topic": "수수료 일반",
        "body": """
<h2>수수료는 환불되나</h2>
<p>거절되어도 환불되지 않습니다. 심사에 대한 대가이지 발급에 대한 대가가 아니기 때문입니다.
재신청하면 다시 전액을 냅니다. 서류가 부족한 상태로 일단 넣어보는 선택이 왜 비싼지 여기서 드러납니다.</p>

<h2>누가 내는가</h2>
<p>항목마다 다릅니다. 취업 관련 청원 수수료 중 일부는 법령상 고용주가 부담해야 하며 직원에게 전가할 수 없습니다.
반면 대사관에서 내는 비자 신청 수수료는 신청자 본인이 냅니다.
계약서에 비용 부담 주체를 적을 때 이 구분을 지키지 않으면 나중에 문제가 됩니다.</p>

<h2>왜 나라마다 금액이 다른가</h2>
<p>조약에 근거한 비자에는 상호주의가 적용됩니다. 상대국이 미국인에게 받는 만큼 미국도 받는 구조입니다.
E-2가 대표적이고, 한국 국적자는 315달러입니다. 같은 E-2라도 국적이 다르면 금액이 달라지므로
다국적 구성원이 있는 사건에서는 국적별로 확인해야 합니다.</p>

<h2>비청원 비자와 청원 기반 비자</h2>
<p>대사관 신청 수수료는 크게 두 갈래입니다. 관광, 상용, 학생처럼 사전 청원이 없는 카테고리는 <strong>185달러</strong>,
H와 L, O처럼 이민국 청원이 선행하는 카테고리는 <strong>205달러</strong>입니다.
여기에 카테고리별 추가 항목이 붙습니다.</p>

<h2>수수료는 얼마나 자주 바뀌나</h2>
<p>금액 변경은 규칙 제정 절차를 거칩니다. 규칙안이 공고되고 의견 수렴을 거쳐 최종 규칙이 나오며, 시행일이 따로 정해집니다.
따라서 시행 전에 미리 알 수 있고, 그 사이에 접수하는 사건은 기존 금액이 적용되는 경우가 많습니다.
반면 소송으로 집행이 정지되는 경우는 예고 없이 상태가 바뀝니다. 최근의 H-1B 관련 대규모 납부 요건이 그 예입니다.</p>

<h2>고지된 금액과 실제 납부액이 다를 때</h2>
<p>수수료 고지서에 나온 금액과 실제 상태가 어긋나는 일이 있습니다. 소송으로 집행이 멈춘 항목이거나,
개정판이 나왔지만 적용 시점이 아직 오지 않은 경우입니다. 이 사이트는 고지서 개정, 관보 규칙, 대사관 수수료표를
하루 두 번 대조해 변경을 반영합니다. 근거와 반영 시각은 원장 페이지에서 확인할 수 있습니다.</p>
""" + TOOL_FEE,
    },
]


def render_articles(cfg: dict[str, Any]) -> list[Path]:
    DOCS.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []

    for art in ARTICLES:
        body = f"""
<article class="art">
  <div class="kicker">{html.escape(art['kicker'])}</div>
  <h1>{html.escape(art['title'])}</h1>
  <div class="sum">{html.escape(art['summary'])}</div>
  {art['body']}
</article>
{site.lead_form(cfg, art.get('topic', ''))}
{site.ad(cfg, "page_bottom")}
"""
        doc = (
            site.head(cfg, art["title"], CSS, art["summary"])
            + site.header(cfg, "guides.html")
            + body
            + site.footer(cfg)
        )
        path = DOCS / art["slug"]
        path.write_text(doc, encoding="utf-8")
        out.append(path)

    items = "".join(
        f'<a href="{a["slug"]}"><b>{html.escape(a["title"])}</b><span>{html.escape(a["summary"])}</span></a>'
        for a in ARTICLES
    )
    body = f"""
<div class="list">{items}</div>
{site.lead_form(cfg)}
{site.ad(cfg, "page_bottom")}
"""
    doc = (
        site.head(cfg, "가이드", CSS, "미국 비자 수수료와 CSPA 나이 계산에 관한 실무 해설")
        + site.header(cfg, "guides.html")
        + body
        + site.footer(cfg)
    )
    path = DOCS / "guides.html"
    path.write_text(doc, encoding="utf-8")
    out.append(path)
    return out
