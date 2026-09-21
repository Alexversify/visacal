# visacal

visacal.com. 미국 비자 관납료 계산기와 CSPA 나이 계산기입니다.
USCIS G-1055, 연방관보, 국무부 수수료표를 하루 두 번 대조해 금액 변경을 자동 반영하고,
변경이 잡히면 수속팀과 영업팀에 각각 다른 요약을 메일로 보냅니다.

## 왜 이 구조인가

- USCIS 웹사이트는 봇 차단이 걸려 있습니다. 서버에서 `requests`로 긁으면 실패합니다.
  Playwright 실제 브라우저로 접근합니다.
- 페이지 전체 해시 비교는 오탐이 쏟아집니다. alert 블록, G-1055 개정판 날짜,
  PDF 안의 금액 필드만 지문으로 만들어 비교합니다.
- 수수료 변경은 반드시 연방관보 규칙 제정을 거칩니다. 시행일 전에 잡으려면
  Federal Register API가 유일하게 확실한 소스입니다. 공개 API라 키가 필요 없습니다.
- 대사관 수수료(MRV, 상호주의)는 국무부 소관이라 G-1055에 없습니다. 별도 트랙입니다.
- 금액은 자동으로 덮어쓰지 않습니다. 변경이 감지되면 해당 항목 상태가 `검토필요`로
  바뀌고 제안값만 기록됩니다. 잘못된 금액이 견적서로 흘러가는 것이 알림이 하루 늦는
  것보다 위험합니다.

## 설치

1. 새 리포지토리를 만들고 이 폴더 내용을 그대로 올립니다.
2. Settings > Pages 에서 Source를 `Deploy from a branch`, 브랜치 `main`, 폴더 `/docs`로 지정합니다.
3. Settings > Secrets and variables > Actions 에 아래를 등록합니다.

| 종류 | 이름 | 값 |
|---|---|---|
| Secret | `ANTHROPIC_API_KEY` | 변경 내용 분석용. 없으면 원문만 전달됩니다 |
| Secret | `SMTP_HOST` `SMTP_PORT` `SMTP_USER` `SMTP_PASS` `SMTP_FROM` | 메일 발송 계정 |
| Secret | `MAIL_TO_PROCESSING` | 수속팀 수신 주소, 쉼표 구분 |
| Secret | `MAIL_TO_SALES` | 영업팀 수신 주소, 쉼표 구분 |
| Secret | `SLACK_WEBHOOK_URL` | 선택. 있으면 슬랙에도 발송 |
| Variable | `PAGES_URL` | 현황판 주소. 알림 본문에 들어갑니다 |

4. Actions 탭에서 `fee-watch`를 수동 실행합니다. **첫 실행은 기준선만 잡고 알림을 보내지 않습니다.**
   두 번째 실행부터 변경분을 비교합니다.

## 로컬 실행

```bash
pip install -r requirements.txt
python -m playwright install --with-deps chromium
python -m src.main
```

## 파일

```
config/settings.yaml   감시 대상 URL, 키워드, 추적 양식. 소스 추가는 여기만 수정
config/site.yaml       도메인, 애드센스 ID, 전환 동선. 값이 비면 해당 요소가 렌더링되지 않음
data/fees.json         수수료 원장. 현재 유효 금액의 단일 기준점
data/scenarios.json    비자 x 진행경로 x 옵션 정의. 비자를 추가하려면 여기만 수정
data/state.json        직전 수집 지문. 이 파일과 비교해 변경을 판정 (자동 생성)
data/changelog.json    변경 이력 (자동 생성)
docs/index.html        비자별 관납료 견적 화면 (자동 생성)
docs/cspa.html         CSPA 나이 계산기 (자동 생성)
docs/changes.html      원장 전체와 변경 이력 (자동 생성)
docs/privacy.html      개인정보처리방침 (자동 생성)
docs/CNAME ads.txt robots.txt sitemap.xml   도메인과 광고 부속 파일 (자동 생성)
src/sources.py         수집
src/ledger.py          변경 감지
src/analyze.py         팀별 요약 생성
src/notify.py          메일, 슬랙 발송
src/render.py          관납료, 원장 페이지 생성
src/cspa_page.py       CSPA 계산기 생성
src/site.py            공통 헤더, 광고, 전환 동선, 푸터
src/static_pages.py    개인정보처리방침, CNAME, ads.txt, sitemap
```

## 화면 구조

`index.html`은 비자를 고르고 경로와 옵션을 체크하면 납부 명세와 총액이 나옵니다.
G-1055가 양식 번호 기준인 것과 달리 상담 순서 그대로입니다.
금액은 HTML에 박히지 않고 `fees.json`이 통째로 심겨 브라우저에서 계산되므로,
원장만 맞으면 화면은 자동으로 따라옵니다.

비자를 추가하려면 `scenarios.json`에 항목을 넣고 필요한 `fee_id`를 `fees.json`에 만들면 됩니다.
참조가 어긋나면 해당 줄이 화면에서 빠지므로, 추가 후 로컬 실행으로 한 번 확인하십시오.

## 운영 시 확인할 것

- **첫 2주는 알림을 본인만 받으십시오.** 오탐 패턴을 보고 `settings.yaml`의
  `alert_selector`와 키워드를 조정한 뒤 팀 주소를 넣는 편이 낫습니다.
- USCIS가 페이지 구조를 바꾸면 alert 수집이 비게 됩니다. Actions 로그에
  `uscis_g1055: ok`인데 alerts가 0건이면 선택자 점검이 필요합니다.
- `data/fees.json`에서 `amount`가 `null`인 항목은 화면에 "확인 필요"로 뜨고 합계에서 빠집니다.
  값을 넣고 `status`를 `시행중`으로 바꾸면 즉시 반영됩니다.
- `status: 집행정지` 항목은 체크해도 경고가 뜨고 납부 대상이 아님을 표시합니다.
- git 커밋 이력 자체가 감사 로그입니다. 특정 날짜의 수수료 근거가 필요하면
  `git log -p data/fees.json`으로 복원됩니다.

## 다음 단계 후보

- 원장을 구글 시트에 미러링해서 기존 견적 양식과 연결
- 상호주의 수수료 국적별 전체 수집 (현재는 한국만)
- I-907 처리 기간 변경, 접수 센터 변경 감시 추가

## 도메인과 배포

GitHub Pages는 무료 플랜에서 public 레포만 게시됩니다. 광고를 붙이려면 어차피 공개 사이트여야 하므로
이 레포는 public으로 둡니다. 대신 팀 내부 공지 문구는 사이트에 남기지 않습니다.
변경 분석의 전문은 메일로만 나가고, `changelog.json`에는 제목과 심각도만 기록됩니다.

1. 레포 Settings > Pages에서 브랜치 `main`, 폴더 `/docs`
2. `config/site.yaml`의 `domain`을 `visacal.com`으로 두면 빌드가 `docs/CNAME`을 자동 생성합니다
3. 도메인 DNS에 A 레코드 네 개를 GitHub Pages IP로, `www`는 CNAME으로 `<계정>.github.io`
4. Pages 설정에서 Enforce HTTPS 체크

## 광고 수익화

`config/site.yaml`의 `adsense.client_id`와 슬롯 ID를 채우면 광고가 나갑니다.
비어 있으면 광고 태그 자체가 출력되지 않으므로 심사 전에는 그대로 두십시오.

승인 전에 준비해야 할 것이 있습니다.

- **콘텐츠 분량.** 계산기만 있는 사이트는 가치가 낮다는 이유로 반려되는 경우가 많습니다.
  CSPA 페이지 하단 해설처럼 비자별 안내 글이 몇 편 더 필요합니다.
- **개인정보처리방침.** `privacy.html`이 자동 생성되며 광고 쿠키 고지가 포함됩니다.
- **ads.txt.** `client_id`를 넣으면 자동 생성됩니다. 이 파일이 없으면 수익이 제한됩니다.
- **동의 관리.** 유럽과 영국 접속자에게 광고를 노출하면 Google 인증 CMP가 필요합니다.
  한국 트래픽만 대상으로 할 계획이면 당장은 넘어가도 되지만, 유입 국가를 확인하고 판단하십시오.

## 결제

정적 사이트라 서버가 없습니다. `cta.paid_url`에 토스페이먼츠 결제링크나 Stripe Payment Link를 넣으면
버튼이 계산 결과 하단에 붙고 결제는 해당 서비스에서 처리됩니다. 서버나 DB를 만들 필요가 없습니다.
`cta.consult_url`에는 상담 신청 폼 주소를 넣습니다.
