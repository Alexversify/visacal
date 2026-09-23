# visacal 작업 안내

visacal.com: 미국 비자 관납료 계산기, CSPA 나이 계산기, 이민 수수료 소식. 운영 법무법인 한미.

## 구조
- src/ 파이썬 정적 사이트 생성기. python -m src.main 실행 시 docs/ 를 다시 만든다
  - RUN_MODE=render python -m src.main 은 수집 없이 페이지만 재생성 (로컬 확인은 이걸로)
  - sources.py 수수료 수집, ledger.py 변경 감지, analyze.py 요약, notify.py 메일
  - render.py 관납료·원장 페이지, cspa_page.py CSPA 계산기, articles.py 가이드 목록, posts.py 글 페이지, site.py 공통 레이아웃·광고·문의폼, static_pages.py 개인정보처리방침·sitemap·ads.txt·CNAME
- content/posts/*.md 글. 관리자 화면(admin.visacal.com)이 여기에 커밋한다. 분류 "가이드"는 실무 가이드, 나머지는 최신 소식
  - front matter의 order는 목록 고정 순서. 작은 수가 위로 가고, order가 없는 글은 날짜순으로 뒤에 붙는다
- data/fees.json 수수료 원장, data/scenarios.json 비자별 계산 시나리오
- config/site.yaml 도메인, 애드센스, GA4, 문의폼 설정
  - adsense.slots가 비면 그 자리의 광고는 렌더링되지 않는다. 광고 단위를 만들어 slot 번호를 채워야 노출된다
- auth-worker/ admin.visacal.com Cloudflare Worker. 이 폴더가 바뀌면 Cloudflare가 자동 배포
- docs/ GitHub Pages 배포 폴더. 직접 고치지 말고 생성기를 고친 뒤 재생성

## 배포
- main에 푸시하면 GitHub Actions가 페이지를 재생성하고 커밋, Pages가 1분 안에 반영
- 매시 5분 페이지 재생성(예약 글 공개), 하루 두 번(KST 07:30, 19:30) 수수료 수집
- 작업 후 반드시 RUN_MODE=render python -m src.main 으로 빌드 확인하고 docs/ 도 함께 커밋

## 규칙
- 한국어 문구에 줄표를 쓰지 않는다. 쉼표나 마침표를 쓴다. "아울러"를 쓰지 않는다
- 금액을 추측해서 넣지 않는다. 확인 안 된 금액은 null, status "검토필요"
- .github/workflows/ 변경은 신중히. 스케줄과 RUN_MODE 분기를 깨지 않는다
- 비밀값(토큰, API 키)을 코드나 커밋에 넣지 않는다. Cloudflare·GitHub Secrets에만 둔다
- 디자인 토큰은 site.py 의 TOKENS를 따른다 (잉크 #14243c, Pretendard)
- 애드센스 심사 중에는 URL 구조를 크게 바꾸지 않는다
- 광고 태그를 innerHTML로 넣지 않는다. 스크립트가 실행되지 않아 광고가 비고, 재계산마다 다시 만들면 정책 위반 소지가 있다
- CSPA 나이 산정 기준은 최종행동일 차트가 원칙. 2025-08-15 전 접수된 신분조정 신청만 경과규정으로 접수가능일 차트
