# 로또 통계 분석기 (lotto-analyzer)

역대 로또 6/45 당첨번호를 모아서 수치화하고, 원하는 조건에 맞춰 번호 조합을 무작위로 만들어 주는 프로그램입니다.
매주 토요일 저녁 9시에 새 회차를 자동으로 받아 통계를 갱신합니다.

- 파이썬 3.9 이상, **표준 라이브러리만 사용** (`pip install` 필요 없음)
- 데이터 출처: 동행복권 공식 조회 API (`https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo=회차`)

## 할 수 있는 것

| 요구 사항 | 명령 |
|---|---|
| 역대 번호 조회, 매주 새 회차 추가 | `update` (+ GitHub Actions 또는 cron으로 자동 실행) |
| 어느 번호가 제일 많이 나왔는지 | `stats` |
| 똑같은 번호 조합이 당첨된 적이 있는지 | `stats`, `pick`, `report` 모두 맨 먼저 중복 검사 결과를 보여 줌 / `check`(내 조합 확인) |
| 중복이 없거나 확률이 낮으면 이전 당첨번호 전부 제외 | `pick` 1단계 (자동 판단) |
| 자주 나온/안 나온 번호 섞기 | `pick` 2단계 (기본 mix 전략) |
| 자주 같이 나온 번호 조합 활용 | `stats`(번호 쌍 TOP), `pick -s pair` |
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

# 3) 번호 만들기
python -m lotto_analyzer pick
```

`pick` 출력 예시:

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
python -m lotto_analyzer pick -n 10                    # 10게임
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

- 토요일 21:00 KST 실행, 일요일 09:00 KST에 한 번 더 실행(결과가 늦게 올라온 경우 대비)
- 새 회차를 `data/draws.json`에 추가하고 `REPORT.md`를 다시 만들어 커밋합니다.
- **주의 1**: GitHub의 예약 실행(schedule)은 **기본 브랜치에 있는 워크플로만** 동작합니다. 이 브랜치를 기본 브랜치에 합친(merge) 뒤부터 매주 돕니다.
- **주의 2**: 예약 실행은 GitHub 서버 사정으로 몇 분~수십 분 늦어질 수 있습니다.
- **주의 3**: 동행복권 사이트가 해외 IP 접속을 막으면 GitHub 서버(미국)에서 조회가 실패할 수 있습니다. 그럴 땐 방법 B를 쓰세요.
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
| `lotto_analyzer/report.py` | `REPORT.md` 생성 |
| `lotto_analyzer/cli.py` | 명령줄 명령 |
| `tests/test_lotto.py` | 테스트 (`python -m unittest discover -s tests`) |

## 꼭 알아 둘 점

로또는 매 회 독립적으로 추첨하기 때문에 **어떤 조합이든 1등 확률은 8,145,060분의 1로 똑같습니다.**
"많이 나온 번호"가 앞으로도 더 잘 나오거나, "안 나온 번호"가 곧 나올 차례인 것은 아닙니다.
이 프로그램의 통계와 필터는 확률을 높여 주는 게 아니라, **번호를 고르는 나만의 기준을 데이터로 만들어 보는 도구**입니다.
대신 "남들이 많이 고르는 모양(연속번호, 한 줄 찍기 등)을 피하면 당첨 시 나눠 가질 사람이 줄어든다"는 점에서는 필터가 의미가 있습니다.
