# AdropHub — 서버비 0원, 30분 자동 갱신

| 파일 | 역할 |
|---|---|
| `index.html` | 화면. `data.json`을 raw.githubusercontent.com에서 직접 읽는다(Netlify 재배포 없음) |
| `data` 브랜치의 `data.json` | `scripts/fetch_data.py`가 만든 최신 데이터 — 110건 / 55KB. 사이트가 raw에서 직접 읽는다 |
| `scripts/fetch_data.py` | RSS 5개 소스 수집 (표준 라이브러리만, 설치 없음) |
| `.github/workflows/update-data.yml` | 30분 cron 워크플로. 결과는 `data` 브랜치에 커밋한다 |

## 켜는 법

1. Actions 탭 → `update-data` → **Run workflow** 로 1회 수동 실행
   - 초록불 + 커밋 `data: refresh ...` 가 생기면 성공
2. https://adrophub.netlify.app/ 을 새로고침 → 헤더가 `🟢 방금 갱신 · 5/5 소스` 인지 확인

## 확인 지점 (끝난 것과 안 끝난 것)

| 확인 | 통과 기준 |
|---|---|
| 데이터가 공개로 읽히나 | `curl -s https://raw.githubusercontent.com/co242424/airdrophub/data/data.json` → `generated_at` 이 30분 안쪽 |
| 화면이 그 데이터를 쓰나 | 페이지 소스에 `rss2json` 없음, 첫 방문에 API 키 모달 없음 |
| 소스 상태가 보이나 | 헤더에 `5/5 소스`, 에어드롭 탭 부제에 5개 소스 이름 |
| 소스 하나가 죽으면 | 헤더 `4/5 소스`, 부제에 `Airdrops.io ✕` 처럼 표시 |
| 30분마다 도나 | Actions 실행 기록이 30분 간격, 커밋이 같은 간격 |

## 왜 Netlify로 재배포하지 않나 (중요)

Netlify 무료 플랜은 2026년 기준 크레딧제다. 무료 300크레딧, **프로덕션 배포 1회 = 15크레딧** → 한 달 20회가 한도다.
30분마다 커밋하면 하루 48회, 반나절이면 크레딧이 바닥난다. 그래서 **사이트는 그대로 두고 data.json만 GitHub raw에서 직접 읽는다**
(`access-control-allow-origin: *`, `cache-control: max-age=300` 확인함). 배포 0회, 서버 0대.

이 저장소는 main에 푸시하면 Netlify가 자동 배포한다(2026-11-23 `index.html` 커밋 → 라이브 반영으로 확인).
그래서 데이터 커밋은 배포가 걸리지 않는 `data` 브랜치에만 쌓고, main은 코드가 바뀔 때만 배포된다.

## 0원 근거

- GitHub Actions: 공개 저장소는 표준 러너 사용료가 무료
- cron 최소 간격 5분 → 30분은 여유. 실행 1회 약 4초(소스 5개, data.json 55KB)
- Netlify: 재배포 안 함(0크레딧), 트래픽은 정적 파일 + 55KB JSON
- DB·프록시·API 키 없음

## 알려진 한계

- 공개 저장소의 예약 워크플로는 **저장소 활동이 60일 없으면 자동 비활성**된다. 커밋이 계속 쌓이니 보통 유지되지만,
  아니면 헤더가 `🟠/🔴 N분 전`으로 먼저 알려준다. 그게 이 화면의 목적이다.
- GitHub cron은 피크 시간에 5~15분 늦게 돌 수 있다. "30분 주기"는 보장이 아니라 목표치다.
- 실제 신선도 = cron 지연 + raw CDN 캐시(최대 5분) → 보통 5~35분.
- Airdrops.io 피드는 갱신이 드물다(마지막 글이 2026-10-02). 그래서 날짜를 숨기지 않고 그대로 보여준다.
- Google News RSS는 피드 고지문에 "개인·비상업용"만 허용이라 넣지 않았다(사이트에 광고 슬롯이 있다).
- DefiLlama `/raises`는 유료 전환(HTTP 402). 무료로 airdrop 데이터를 주지 않는다.

## 롤백

`git revert` 로 파이프라인 커밋들을 되돌리면 이전 `index.html`(SOURCES + rss2json)로 돌아간다. `data` 브랜치는 지워도 main 배포에는 영향이 없다.
