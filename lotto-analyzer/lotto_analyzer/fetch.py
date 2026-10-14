"""동행복권 공식 API에서 회차별 당첨번호를 받아와 data/draws.json에 저장한다.

- 처음 실행하면 1회차부터 최신 회차까지 전부 받는다.
- 다음부터는 저장된 마지막 회차 다음부터만 받는다(증분 수집).
- 아직 추첨 전인 회차를 요청하면 API가 returnValue="fail"을 주므로 거기서 멈춘다.
"""

import json
import time
import urllib.request
from pathlib import Path

API_URL = "https://www.dhlottery.co.kr/common.do?method=getLottoNumber&drwNo={}"
DEFAULT_DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "draws.json"

# 브라우저처럼 보이지 않으면 HTML 안내 페이지를 돌려주는 경우가 있어 헤더를 붙인다.
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Referer": "https://www.dhlottery.co.kr/",
}


class FetchError(Exception):
    pass


def http_get_json(url, timeout=10):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8", errors="replace")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        raise FetchError(
            "JSON이 아닌 응답을 받았습니다(점검 중이거나 접속 차단). 앞부분: " + body[:120]
        )


def parse_draw(raw):
    """API 응답 하나를 우리가 쓰는 형태로 바꾼다. 추첨 전 회차면 None."""
    if raw.get("returnValue") != "success":
        return None
    numbers = sorted(raw[f"drwtNo{i}"] for i in range(1, 7))
    return {
        "round": raw["drwNo"],
        "date": raw["drwNoDate"],
        "numbers": numbers,
        "bonus": raw["bnusNo"],
        "first_prize_amount": raw.get("firstWinamnt", 0),
        "first_prize_winners": raw.get("firstPrzwnerCo", 0),
    }


def load_draws(path=DEFAULT_DATA_PATH):
    path = Path(path)
    if not path.exists():
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def save_draws(draws, path=DEFAULT_DATA_PATH):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    draws = sorted(draws, key=lambda d: d["round"])
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(draws, f, ensure_ascii=False, indent=1)
        f.write("\n")
    tmp.replace(path)  # 쓰다가 끊겨도 기존 파일이 깨지지 않게 임시 파일 후 교체


def update(path=DEFAULT_DATA_PATH, get_json=http_get_json, delay=0.2, retries=3, log=print):
    """새 회차를 받아 저장하고, 새로 추가된 회차 목록을 돌려준다."""
    draws = load_draws(path)
    next_round = draws[-1]["round"] + 1 if draws else 1
    added = []

    while True:
        raw = None
        for attempt in range(1, retries + 1):
            try:
                raw = get_json(API_URL.format(next_round))
                break
            except Exception as e:  # 네트워크 오류는 잠깐 쉬었다 재시도
                if attempt == retries:
                    # 받은 데이터까지는 저장하고 오류를 알린다
                    if added:
                        save_draws(draws + added, path)
                    raise FetchError(f"{next_round}회 조회 실패: {e}") from e
                time.sleep(2 ** attempt)

        draw = parse_draw(raw)
        if draw is None:
            break  # 아직 추첨하지 않은 회차 -> 최신까지 다 받음
        added.append(draw)
        if len(added) % 100 == 0:
            log(f"  ... {draw['round']}회까지 받음")
            save_draws(draws + added, path)  # 중간 저장
        next_round += 1
        if delay:
            time.sleep(delay)  # 서버에 부담 주지 않도록 천천히

    if added:
        save_draws(draws + added, path)
    return added
