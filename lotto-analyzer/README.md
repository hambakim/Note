# 로또 통계 분석기 (lotto-analyzer)

역대 로또 6/45 당첨번호를 모아서 수치화하고, 원하는 조건에 맞춰 번호 조합을 무작위로 만들어 주는 프로그램입니다.
한 주의 흐름:

| 언제 | 무엇을 |
|---|---|
| **토요일 21시** | 당첨번호 수집 → 다음 회차 10게임을 만들어 **고정** → 웹페이지에 바로 표시 |
| 그 주 내내 | 웹페이지에서 고정된 10게임 확인 |
| **금요일 18시** | 고정된 10게임을 **그대로** 카카오톡으로 전송 (새로 뽑지 않음) |
| 다음 토요일 21시 | 결과(몇 등인지) 확인 → 다음 회차 10게임 고정 |

- **웹페이지로 보기: https://hambakim.github.io/Note/lotto-analyzer/** (기본 브랜치에 합친 뒤부터 열림)
- 파이썬 3.9 이상, **표준 라이브러리만 사용** (`pip install` 필요 없음)
- 데이터 출처 (차례로 시도, 번호 검증 후 저장)
  1. 동행복권 공식 API: 한국 IP에서만 동작 (GitHub 서버에서는 막혀 있음)
  2. 네이버 검색 결과("로또 N회 당첨번호"): 토요일 추첨 직후 반영, GitHub 서버에서 동작
  3. [smok95/lotto](https://github.com/smok95/lotto) 공개 JSON: 처음 전체 회차를 한 번에 받을 때 사용

## 할 수 있는 것

| 요구 사항 | 명령 |
|---|---|
| 역대 번호 조회, 매주 새 회차 추가 | `update` (+ GitHub Actions 또는 cron으로 자동 실행) |
| 어느 번호가 제일 많이 나왔는지 | `stats` |
| 똑같은 번호 조합이 당첨된 적이 있는지 | `stats`, `pick`, `report` 모두 맨 먼저 중복 검사 결과를 보여 줌 / `check`(내 조합 확인) |
| 중복이 없거나 확률이 낮으면 이전 당첨번호 전부 제외 | `pick` 1단계 (자동 판단) |
| 자주 나온/안 나온 번호 섞기 | `pick` 2단계 (기본 mix 전략) |
| 자주 같이 나온 번호 조합 활용 | `stats`(번호 쌍 TOP), `pick -s pair` |
| 이번 주 살 10게임 만들기 + 기록 | `weekly` |
| 금요일 18시 카카오톡으로 받기 | `weekly --send` (+ GitHub Actions 또는 PC 예약 실행) |
| 지난주 추천 조합이 몇 등이었는지 | `result`, `REPORT.md` 7번 |
| 한눈에 보는 주간 리포트 | `report` → `REPORT.md` |

## 따라 하기 (처음 한 번)

```bash
cd lotto-analyzer

# 1) 역대 당첨번호 전부 받기 (1회~최신, 1~5분 걸림)
python -m lotto_analyzer update

# 2) 통계 보기
python -m lotto_analyzer stats            # 번호 순서대로
python -m lotto_analyzer stats --sort     # 많이 나온 순서대로
python -m lotto_analyzer stats --recent 50  # 최근 50회만

# 3) 이번 주 살 10게임 만들기
python -m lotto_analyzer weekly
```

`weekly` 출력 예시:

```
[1단계] 이전 당첨번호 중복 검사
  역대 1193회 중 같은 1등 조합이 다시 나온 적: 없음 (0번)
  판단: 중복이 없음 → 이전 1등 조합 1,193개를 후보에서 전부 제외

[2단계] 당첨 가능성이 낮을 것으로 보는 조합 지우기 (전체 8,145,060개)
  - 이전 1등 조합과 같음: 약 1,193개
  - 번호 합계가 역대 가운데 범위 밖: 약 1,280,000개
  - 3연속 이상 번호 포함: 약 290,000개
  - ...
  => 남은 후보 약 6,100,000개

[3단계] 남은 후보에서 10게임 선택 (많이 나온 번호 3 + 덜 나온 번호 2 + 무작위 1, 조합끼리 3개 이하로만 겹침)
A 09 15 22 24 33 40
...
J 03 13 15 16 26 32
```

- 10게임끼리 번호가 4개 이상 겹치지 않게 골라서, 비슷한 조합에 돈을 몰아 쓰지 않습니다 (`--max-shared`로 조절).
- 처음 만든 번호는 `data/picks.json`에 **고정**되고, 같은 회차에 다시 실행하면 새로 뽑지 않고 고정된 번호를 그대로 씁니다. 그래서 웹페이지·카톡·`REPORT.md`의 번호가 항상 같습니다. 꼭 새로 뽑고 싶으면 `weekly --new`.
- 만든 조합은 `data/picks.json`에 기록되고, 토요일 추첨 뒤 `python -m lotto_analyzer result`로 몇 등인지 확인할 수 있습니다.

`pick`은 전략·필터를 바꿔 가며 실험할 때 씁니다.

`pick` 출력 예시 (`python -m lotto_analyzer pick`):

```
[1단계] 이전 당첨번호 중복 검사
  역대 1193회 중 같은 1등 조합이 다시 나온 적: 없음 (0번)
  다음 회차가 이전 1등 조합 1,193개 중 하나와 같을 확률: 0.0146% (약 6,827분의 1)
  판단: 중복이 없음 → 이전 1등 조합 1,193개를 후보에서 전부 제외

[2단계] mix 전략으로 번호 조합 (전체 1193회 기준 / 1193회까지 반영)
  많이 나온 번호 3개 + 덜 나온·오래 안 나온 번호 2개 + 나머지 무작위
  ...
  A) 05 12 18 27 34 43   합 139 | 홀3:짝3 | hot 12,18,34 / cold 27,43
```

## 1단계: 이전 당첨번호 중복 검사 → 제외 여부 자동 판단

번호를 만들기 전에 항상 먼저 아래 순서로 판단합니다.

1. 역대 1등 조합 중 **똑같은 6개 조합이 두 번 이상 1등이 된 적이 있는지** 셉니다.
2. 다음 회차가 이전 1등 조합 중 하나와 똑같을 확률을 계산합니다.
   `이전 1등 조합 수 ÷ 8,145,060` (1,200회 기준 약 0.015%, 6,800분의 1)
3. **중복이 한 번도 없거나, 위 확률이 1% 미만이면 → 이전 1등 조합을 후보에서 전부 제외**합니다.
   제외된 조합은 2단계에서 무작위로 뽑혀도 버리고 다시 뽑습니다.

| 옵션 | 동작 |
|---|---|
| `--past auto` (기본) | 위 판단 결과대로 |
| `--past exclude` | 판단과 상관없이 항상 제외 |
| `--past allow` | 제외하지 않음 |
| `--threshold 0.001` | auto 판단 기준 확률 바꾸기 (기본 0.01 = 1%) |
| `--max-overlap 4` | (선택) 이전 1등과 5개 이상 겹치는 조합까지 제외. 기본은 끔 |

## 번호 만들기 옵션 (`pick`)

### 전략 고르기 `-s`

| 전략 | 방식 |
|---|---|
| `mix` (기본) | 많이 나온 번호 `--hot`개(기본 3) + 덜 나온·오래 안 나온 번호 `--cold`개(기본 2) + 나머지 무작위 |
| `hot` | 많이 나온 번호일수록 잘 뽑히게 (출현 횟수 비례 가중치) |
| `cold` | 오래 안 나온 번호일수록 잘 뽑히게 |
| `pair` | 역대 자주 함께 나온 번호 쌍 TOP 30 중 하나를 넣고 나머지는 hot 가중치 |
| `random` | 완전 무작위 (필터만 적용) |

### 자주 쓰는 조합 예시

```bash
python -m lotto_analyzer pick -n 5                     # 5게임만
python -m lotto_analyzer pick --hot 4 --cold 1         # 많이 나온 번호 비중 높이기
python -m lotto_analyzer pick --hot 0 --cold 4         # 안 나온 번호 위주
python -m lotto_analyzer pick --recent 30              # 최근 30회 흐름 기준으로 hot/cold 판단
python -m lotto_analyzer pick -s pair -n 5             # 자주 함께 나온 번호 쌍 활용
python -m lotto_analyzer pick -i 7 27 -x 1 2 3         # 7, 27은 꼭 넣고 1, 2, 3은 빼기
python -m lotto_analyzer pick --seed 2026              # 같은 시드면 같은 결과 (기록용)
```

### 2단계 모양 필터 (기본으로 켜짐, `--no-filter`로 모두 끄기)

| 필터 | 이유 | 바꾸는 옵션 |
|---|---|---|
| 홀짝 6:0, 0:6 제외 | 역대 비율이 매우 낮음 | `--no-filter` |
| 저번호(1~22)/고번호 6:0, 0:6 제외 | 역대 비율이 매우 낮음 | `--no-filter` |
| 번호 합계가 역대 가운데 80% 밖이면 제외 | 극단적으로 작거나 큰 합계 배제 | `--sum-coverage 0.9`, `0`이면 끔 |
| 3연속 이상 번호 제외 | 역대 약 5% 수준 | `--max-run 3` |
| 번호대가 2구간 이하로 몰리면 제외 | 1~9/10~19/…/40~45 중 3구간 이상 | `--no-filter` |

`--no-filter`는 모양 필터만 끕니다. 1단계의 이전 당첨번호 제외는 그대로 적용됩니다.

조건을 너무 빡빡하게 걸면 "조합을 만들지 못했습니다"와 함께 **어떤 조건에 가장 많이 걸렸는지** 알려 줍니다.

## 내 번호 확인 (`check`)

```bash
python -m lotto_analyzer check 3 11 19 25 33 41
```

역대 모든 회차와 비교해서 1등~5등 기준으로 몇 번 맞았을지 보여 줍니다.

## 매주 토요일 21시 자동 갱신

로또 추첨은 토요일 20시 35분쯤이고, 21시면 결과가 올라와 있습니다. 두 가지 방법 중 하나를 고르세요.

### 방법 A. GitHub Actions (PC를 켜 두지 않아도 됨)

`.github/workflows/lotto-weekly-update.yml`이 이미 들어 있습니다.

- 토요일 21:00 KST 실행, 22:00과 일요일 09:00에 재시도(결과가 늦게 올라온 경우 대비, 이미 받았으면 아무것도 안 함)
- 새 회차를 `data/draws.json`에 추가하고, 다음 회차 10게임을 고정(`data/picks.json`)하고, `REPORT.md`와 웹페이지 데이터(`data/web.json`)를 다시 만들어 커밋합니다.
- **주의 1**: GitHub의 예약 실행(schedule)은 **기본 브랜치에 있는 워크플로만** 동작합니다. 이 브랜치를 기본 브랜치에 합친(merge) 뒤부터 매주 돕니다.
- **주의 2**: 예약 실행은 GitHub 서버 사정으로 몇 분~수십 분 늦어질 수 있습니다.
- **주의 3**: 동행복권 사이트는 해외 IP 접속을 막아서 GitHub 서버에서는 네이버·smok95 출처로 자동 전환됩니다.
- 처음 한 번은 GitHub 저장소 → **Actions** 탭 → `로또 주간 업데이트` → **Run workflow** 로 직접 돌려 전체 데이터를 받아 두면 좋습니다.

### 방법 B. 내 PC에서 예약 실행

**리눅스/맥 (cron)** — `crontab -e`로 아래 줄 추가 (PC 시간대가 KST일 때)

```
0 21 * * 6 cd /경로/Note/lotto-analyzer && (python3 -m lotto_analyzer update && python3 -m lotto_analyzer report) >> update.log 2>&1
```

**윈도우 (작업 스케줄러)** — 관리자 PowerShell에서

```powershell
$action  = New-ScheduledTaskAction -Execute "python" -Argument "-m lotto_analyzer update" -WorkingDirectory "C:\경로\Note\lotto-analyzer"
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Saturday -At 9pm
Register-ScheduledTask -TaskName "LottoWeeklyUpdate" -Action $action -Trigger $trigger
```

## 웹페이지로 보기

**https://hambakim.github.io/Note/lotto-analyzer/** 를 폰이나 PC 브라우저로 열면 됩니다. 로그인은 필요 없습니다.

| 화면 | 내용 |
|---|---|
| 이번 주 추천 10게임 | 카카오톡으로 받는 번호와 같음, **번호 복사** 버튼 |
| 어떤 조합을 지웠나 | 전체 8,145,060개 → 지운 조건별 개수 → 남은 후보, 이전 당첨번호 중복 검사 결과 |
| 지난 추천 결과 | 회차별로 10게임 중 몇 등이 있었는지, 맞은 번호 표시 |
| 최근 당첨번호 | 최근 5회 |
| 번호별 출현 횟수 | 막대그래프 (전체/최근 50회, 번호순/많은 순), 막대를 누르면 자세히, 표로 보기 |
| 많이/적게/오래 안 나온 번호, 자주 함께 나온 번호, 당첨 조합 모양 | 통계 |

동작 방식
- 페이지는 `lotto-analyzer/index.html` 한 파일이고, 계산은 하지 않고 `data/web.json`만 읽어서 보여 줍니다.
- `data/web.json`은 토요일 업데이트와 금요일 카톡 워크플로가 실행될 때마다 새로 만들어져 커밋됩니다. 커밋 후 1~2분 뒤 페이지에 반영됩니다.
- 카톡 설정을 아직 안 했어도 금요일 워크플로가 이번 주 10게임을 웹페이지에 올려 줍니다 (카톡 전송 단계만 실패로 표시됨).
- 홈 화면에 추가해 두면 앱처럼 바로 열 수 있습니다 (안드로이드 크롬: ⋮ → 홈 화면에 추가 / 아이폰 사파리: 공유 → 홈 화면에 추가).

내 PC에서 미리 보기:

```bash
cd lotto-analyzer
python -m lotto_analyzer web          # data/web.json 만들기
python -m http.server 8000            # 브라우저에서 http://localhost:8000 열기
```

## 금요일 18시 카카오톡으로 받기

카카오 공식 API의 **'나에게 보내기'** 기능을 씁니다. 내 카카오톡 **'나와의 채팅'**방에 메시지가 옵니다.
메시지는 2건입니다: ① 요약(회차, 지운 조합 수) ② 10게임 번호.

### 1. 카카오 개발자 앱 만들기 (한 번만, 10분)

카카오 개발자 콘솔은 화면 개편이 잦아서 메뉴 이름이 조금 다를 수 있습니다.

1. https://developers.kakao.com 에 카카오 계정으로 로그인 → **내 애플리케이션** → **애플리케이션 추가하기** (앱 이름 예: `로또알림`)
2. **앱 키**에서 **REST API 키**를 복사해 둡니다.
3. **카카오 로그인** 메뉴에서 **활성화 설정을 ON**, **Redirect URI**에 `https://localhost` 를 등록합니다.
4. **동의항목**에서 **카카오톡 메시지 전송(talk_message)** 을 **선택 동의**로 설정합니다.
5. **보안** 메뉴의 **Client Secret**이 "사용함"이면 코드 값을 복사해 둡니다 (아니면 건너뜀).

### 2. 내 PC에서 로그인해서 refresh_token 받기 (한 번만)

```bash
cd lotto-analyzer
# 윈도우 PowerShell은:  $env:KAKAO_REST_API_KEY="복사한 REST API 키"
export KAKAO_REST_API_KEY="복사한 REST API 키"
# Client Secret을 쓰면:  export KAKAO_CLIENT_SECRET="값"

python -m lotto_analyzer kakao login
```

1. 화면에 나온 주소를 브라우저로 열고 카카오 로그인 → **동의하고 계속하기**
2. "사이트에 연결할 수 없음"이 떠도 정상입니다. **주소창의 주소 전체**를 복사해서:

```bash
python -m lotto_analyzer kakao login "https://localhost/?code=......"
python -m lotto_analyzer kakao test      # 카톡 '나와의 채팅'에 테스트 메시지가 오면 성공
python -m lotto_analyzer weekly --send   # 10게임 바로 받아 보기
```

토큰은 `kakao_token.json`에 저장되며 `.gitignore`에 들어 있어 **저장소에 올라가지 않습니다.** 로그인 결과로 나온 refresh_token 값은 3단계에서 씁니다.

### 3-A. GitHub Actions로 매주 자동 전송 (PC를 꺼 둬도 됨)

`.github/workflows/lotto-friday-kakao.yml`이 금요일 18:00 KST에 `weekly --send`를 실행해 **토요일에 고정된 10게임을 그대로** 보냅니다. (토요일 수집이 실패해 고정된 번호가 없을 때만 새로 만들어 보냅니다.)

GitHub 저장소 → **Settings → Secrets and variables → Actions → New repository secret** 으로 아래를 등록합니다.

| 이름 | 값 |
|---|---|
| `KAKAO_REST_API_KEY` | REST API 키 |
| `KAKAO_REFRESH_TOKEN` | 2단계에서 나온 refresh_token |
| `KAKAO_CLIENT_SECRET` | (Client Secret을 쓰는 경우만) |
| `GH_PAT` | (권장) 아래 설명 참고 |

**GH_PAT가 필요한 이유**: 카카오 refresh_token은 약 2개월 유효하고, 만료 1개월 전부터는 쓸 때마다 새 값으로 바뀝니다.
GH_PAT를 넣어 두면 워크플로가 새 값으로 `KAKAO_REFRESH_TOKEN` 시크릿을 **자동으로 바꿔서 계속 동작**합니다.
없으면 1~2개월마다 2단계 로그인을 다시 하고 시크릿을 직접 바꿔야 합니다 (그때 Actions 화면에 경고가 뜹니다).

GH_PAT 만들기: GitHub 오른쪽 위 프로필 → **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**
→ Repository access: **Only select repositories → Note** → Permissions: **Secrets: Read and write** → 만든 값을 `GH_PAT` 시크릿으로 등록.
(토큰 만료일을 1년 정도로 잡고, 만료되면 새로 만들어 바꿔 주세요.)

확인: **Actions** 탭 → `로또 금요일 카톡 추천` → **Run workflow** 를 눌러 바로 카톡이 오는지 봅니다.

주의
- 예약 실행은 **기본 브랜치에 합친 뒤부터** 동작하고, GitHub 사정으로 **몇 분~수십 분 늦게** 올 수 있습니다. 정확히 18시가 중요하면 3-B를 쓰세요.
- 이 저장소는 공개 저장소라 `data/picks.json`(추천 번호 기록)과 Actions 실행 로그를 다른 사람도 볼 수 있습니다. 토큰은 시크릿이라 보이지 않습니다.

### 3-B. 내 PC에서 예약 전송

PC가 켜져 있어야 합니다. 2단계를 한 PC에서 설정하세요.

```
# 리눅스/맥 crontab -e  (PC 시간대 KST)
0 18 * * 5 cd /경로/Note/lotto-analyzer && (python3 -m lotto_analyzer update; python3 -m lotto_analyzer weekly --send) >> kakao.log 2>&1
```

```powershell
# 윈도우 PowerShell
$action  = New-ScheduledTaskAction -Execute "python" -Argument "-m lotto_analyzer weekly --send" -WorkingDirectory "C:\경로\Note\lotto-analyzer"
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Friday -At 6pm
Register-ScheduledTask -TaskName "LottoFridayKakao" -Action $action -Trigger $trigger
```

PC에서는 새 refresh_token이 나오면 `kakao_token.json`에 자동 저장되므로 따로 할 일이 없습니다.

## API가 막혔을 때: CSV로 넣기

동행복권 사이트에서 회차별 당첨번호를 엑셀로 받은 뒤 아래 형식의 CSV로 저장해서 넣을 수 있습니다.

```
회차,날짜,번호1,번호2,번호3,번호4,번호5,번호6,보너스
1,2002-12-07,10,23,29,33,37,40,16
```

```bash
python -m lotto_analyzer import-csv lotto.csv
```

## 파일 구조

| 파일 | 역할 |
|---|---|
| `lotto_analyzer/fetch.py` | API 조회, 증분 수집, `data/draws.json` 저장 |
| `lotto_analyzer/stats.py` | 중복 당첨 검사·제외 판단(`repeat_check`), 출현 횟수, 미출현 기간, 번호 쌍/3개 묶음, 같은 조합 재등장, 홀짝·합계·연속번호 분포 |
| `lotto_analyzer/generator.py` | 1단계 이전 당첨번호 제외 + 2단계 전략별 번호 생성·모양 필터 |
| `lotto_analyzer/weekly.py` | 이번 주 10게임 만들기, `data/picks.json` 기록, 지난 추천 결과 확인, 카톡 문구 |
| `index.html` | 웹페이지 (`data/web.json`을 읽어 표시) |
| `lotto_analyzer/web.py` | 웹페이지용 `data/web.json` 만들기 |
| `lotto_analyzer/kakao.py` | 카카오 로그인·토큰 갱신·나에게 보내기 |
| `lotto_analyzer/report.py` | `REPORT.md` 생성 |
| `lotto_analyzer/cli.py` | 명령줄 명령 |
| `tests/` | 테스트 (`python -m unittest discover -s tests`) |

## 꼭 알아 둘 점

이 프로그램의 방식은 "**당첨 가능성이 낮을 것으로 보는 조합을 먼저 지우고, 남은 것 중에서 고른다**"입니다.
다만 숫자로 정확히 말하면, 로또는 매 회 독립적으로 추첨하기 때문에 **남은 조합 하나하나의 1등 확률도 8,145,060분의 1로 지우기 전과 같습니다.**
예를 들어 "합계가 너무 작은 조합"이 역대에 드물게 나온 이유는 그런 조합 자체가 전체에서 적기 때문이지, 그 조합 하나가 덜 뽑히기 때문은 아닙니다.
그래서 10게임을 사면 1등 확률은 어떤 방식으로 골라도 10 ÷ 8,145,060 입니다.

그래도 이 방식이 의미 있는 부분:
- **같은 조합 중복 구매 방지**: 10게임이 서로 겹치지 않게 퍼뜨립니다.
- **당첨금을 나눠 가질 가능성 줄이기**: 연속번호, 한쪽에 몰린 번호, 이전 당첨번호 같은 모양은 사람들이 일부러 많이 고릅니다. 이런 조합을 피하면 같은 등수에 당첨됐을 때 나눠 가질 사람이 줄어 받는 금액이 커질 수 있습니다.
- **나만의 기준을 데이터로 기록**: `data/picks.json`과 `result`로 매주 어떤 결과가 나왔는지 쌓아 볼 수 있습니다.
