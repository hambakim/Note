# 경매 매물 알리미 (car-auction)

K3·아반떼 / 2019~2020년식 / 7만km 이하 / 흰색(1순위)·검정(2순위) 경매 매물을 모아 보고,
조건에 맞는 차가 올라오면 카카오톡 '나에게 보내기'로 알려 줍니다.

- **웹페이지: https://hambakim.github.io/Note/car-auction/** (기본 브랜치 `claude/lottery-win-simulator-e9ubtt`에 합친 뒤부터 열림)
- 딜러 경매장(코오롱 등)은 회원 로그인이 필요해서 자동 수집은 하지 않습니다. 고모부께 받은 매물 정보를 직접 넣는 방식입니다.

## 쓰는 순서

1. 웹페이지 아래 **매물 추가**에 차 정보 입력 → 저장 → 바로 "조건 일치 / 색상 다름 / 조건 밖" 판정
2. 카드의 **고모부께 보낼 문자 복사** → 권장 상한까지만 입찰해 달라는 문자를 카톡에 붙여넣기
3. 카톡 알림까지 받고 싶으면 **GitHub에 올리기** → 열린 `data/listings.json` 편집 화면에서 `[` 다음 줄에 붙여넣고 Commit
4. 경매가 끝나면 상태를 낙찰/유찰/패스로 바꿔 두기 (지난 매물 탭으로 이동)

## 파일

| 파일 | 내용 |
|---|---|
| `data/criteria.json` | 조건, 마감일, 연식별 입찰 상한(만원), 감가 규칙 |
| `data/listings.json` | 모두가 보는 매물 목록 |
| `data/notified.json` | 카톡으로 이미 보낸 매물 (자동 기록) |
| `car_alert.py` | 조건 판정 + 카톡 전송 (`--send`) |
| `.github/workflows/car-auction-kakao.yml` | listings.json이 기본 브랜치에 올라오면 자동 실행 / Actions 탭에서 수동 실행(테스트 전송 가능) |

권장 상한 = 연식별 상한 − 골격판금 30만 − 흰색·검정 아님 30만 − 내차피해 2회째부터 1회당 10만 (어림 계산).
아반떼 상한은 비워 두었으니 시세를 보고 `criteria.json` 또는 웹페이지 설정에서 넣어 주세요.

```bash
cd car-auction
python -m unittest discover -s tests   # 테스트
python car_alert.py                    # 보낼 매물 미리 보기 (전송 안 함)
```
