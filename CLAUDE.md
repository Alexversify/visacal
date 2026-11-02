# visacal 작업 안내

visacal.com: 미국 비자 관납료 계산기, CSPA 나이 계산기, 이민 수수료 소식. 운영 법무법인 한미.

## 구조
- src/ 파이썬 정적 사이트 생성기. python -m src.main 실행 시 docs/ 를 다시 만든다
  - RUN_MODE=render python -m src.main 은 수집 없이 페이지만 재생성 (로컬 확인은 이걸로)
  - sources.py 수수료 수집, ledger.py 변경 감지, analyze.py 요약, notify.py 메일
  - render.py 관납료·원장 페이지, cspa_page.py CSPA 계산기, articles.py 가이드 목록, posts.py 글 페이지, site.py 공통 레이아웃·광고·문의폼, static_pages.py 개인정보처리방침·sitemap·ads.txt·CNAME
  - consular_rate.py 주한미국대사관 영사환율 수집(AIS 결제창, Playwright 로그인). 결과는 data/consular_rate.json, data/consular_rate_history.csv(실패일은 rate 빈칸), data/consular_fee_history.csv. 페이지는 consular_page.py 가 /consular-rate/, consular_history.py 가 /consular-rate/history/ 로 생성
  - visa_bulletin.py 미 국무부 비자 문호(Visa Bulletin) 수집. 순서: 수동 투입함(content/visa-bulletin/inbox/) → 국무부 원문(travel.state.gov, Cloudflare 보안 확인으로 GitHub 서버에서는 보통 막힘, 우회 금지) → 국무부 메일링을 받는 메일함(IMAP). 표 4개 × 행 전부가 읽혀야 저장하고, 하나라도 빠지면 게시하지 않는다. 결과 data/visa_bulletin/YYYY-MM.json, 원문 data/visa_bulletin/raw/. 새 달이면 6개 언어 요약(LLM, 월 1회), content/posts 소식 글, 팀 메일
  - vb_page.py 가 /visa-bulletin/ (최신, 상단 메뉴 "비자 문호"), /visa-bulletin/<en|zh|ja|vi|es>/ (언어별 최신), /visa-bulletin/YYYY-MM/ (한국어), /visa-bulletin/YYYY-MM/<lang>/ 생성. 화면 순서: 표(최종조치일, 접수가능일) → USCIS·출처 → 요약 → 지난달 대비 변동 → 추이 → 월별 정리. 고정 문구는 vb_i18n.py
- content/posts/*.md 글. 관리자 화면(admin.visacal.com)이 여기에 커밋한다. 분류 "가이드"는 실무 가이드, 나머지는 최신 소식
- data/fees.json 수수료 원장, data/scenarios.json 비자별 계산 시나리오
- config/site.yaml 도메인, 애드센스, GA4, 문의폼 설정
- auth-worker/ admin.visacal.com Cloudflare Worker. 이 폴더가 바뀌면 Cloudflare가 자동 배포
- docs/ GitHub Pages 배포 폴더. 직접 고치지 말고 생성기를 고친 뒤 재생성

## 배포
- main에 푸시하면 GitHub Actions가 페이지를 재생성하고 커밋, Pages가 1분 안에 반영
- 매시 5분 페이지 재생성(예약 글 공개), 하루 두 번(KST 07:30, 19:30) 수수료 수집
- .github/workflows/consular-rate.yml 평일 KST 08:30 영사환율 수집, 페이지 재생성까지 직접 하고 data/ docs/ 커밋 (GITHUB_TOKEN 푸시는 fee-watch 를 트리거하지 않음, concurrency 그룹 fee-watch 공유)
- .github/workflows/visa-bulletin.yml 매일 KST 09:40, 18:40 비자 문호 확인. 투입함에 파일이 커밋되면 즉시 실행. 페이지 재생성까지 직접 하고 커밋
- 작업 후 반드시 RUN_MODE=render python -m src.main 으로 빌드 확인하고 docs/ 도 함께 커밋

## 규칙
- 한국어 문구에 줄표를 쓰지 않는다. 쉼표나 마침표를 쓴다. "아울러"를 쓰지 않는다
- 금액을 추측해서 넣지 않는다. 확인 안 된 금액은 null, status "검토필요"
- .github/workflows/ 변경은 신중히. 스케줄과 RUN_MODE 분기를 깨지 않는다
- 비밀값(토큰, API 키)을 코드나 커밋에 넣지 않는다. Cloudflare·GitHub Secrets에만 둔다
- 디자인 토큰은 site.py 의 TOKENS를 따른다 (잉크 #14243c, Pretendard)
- 애드센스 심사 중에는 URL 구조를 크게 바꾸지 않는다
- 비자 문호 표 값은 원문에서 읽은 값만 쓴다. 추정·보간·제3자 사이트 값으로 채우지 않는다. 행 이름과 열 순서는 vb_i18n 고정 문구로 번역하고 LLM은 요약에만 쓴다
- 월 API 상한: src/llm.py가 API 사용액을 data/llm_spend/YYYY-MM/에 기록하고, 이번 달 합계가 `LLM_MONTHLY_CAP_USD`(저장소 변수, 없으면 10달러) 이상이면 그달은 API를 쓰지 않는다. 상한·빈도·실행당 한도(0.5달러)를 올리는 변경은 소유자 승인 없이 하지 않는다
