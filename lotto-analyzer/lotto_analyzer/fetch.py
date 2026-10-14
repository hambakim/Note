"""회차별 당첨번호를 받아와 data/draws.json에 저장한다.

출처 (위에서부터 차례로 시도)
1. 동행복권 공식 API  : 한국 IP에서만 잘 됨. GitHub 서버(미국)에서는 막혀 있음
2. 네이버 검색 결과   : "로또 N회 당첨번호" 검색 화면에서 번호를 읽음. 토요일 추첨 직후 반영
3. smok95/lotto     : GitHub에 공개된 당첨번호 JSON. 처음 전체 회차를 한 번에 받을 때 사용

- 처음 실행하면 1회차부터 최신 회차까지 전부 받는다 (smok95 전체 파일 -> 나머지는 회차별).
- 다음부터는 저장된 마지막 회차 다음부터만 받는다(증분 수집).
- 어느 출처에서도 다음 회차가 없으면(아직 추첨 전) 거기서 멈춘다.
"""

import json
import re
import time
import urllib.error
import urllib.parse
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


def http_get_text(url, timeout=10):
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def http_get_json(url, timeout=10):
    body = http_get_text(url, timeout)
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


def valid_draw(d):
    """번호 6개가 1~45 사이에서 서로 다르고, 보너스도 겹치지 않는지 확인."""
    nums = d["numbers"]
    return (len(nums) == 6 and len(set(nums)) == 6 and all(1 <= n <= 45 for n in nums)
            and 1 <= d["bonus"] <= 45 and d["bonus"] not in nums)


# ---------- 출처 1: 동행복권 ----------

def from_dhlottery(rnd, get_text=http_get_text):
    try:
        raw = json.loads(get_text(API_URL.format(rnd), timeout=5))
    except json.JSONDecodeError:
        raise FetchError("동행복권: JSON이 아닌 응답(접속 차단 또는 점검)")
    return parse_draw(raw)


# ---------- 출처 2: 네이버 검색 ----------

NAVER_URL = "https://search.naver.com/search.naver?query={}"


def parse_naver(html, rnd):
    """네이버 검색 결과에서 rnd회 번호를 읽는다. 아직 추첨 전이면 네이버는 최신 회차를 보여 주므로 None."""
    shown = re.search(r"(\d{1,4})회차", html)
    if not shown or int(shown.group(1)) != rnd:
        return None
    box = re.search(r'class="winning_number">(.*?)</div>\s*<div class="bonus_number">(.*?)</div>', html, re.S)
    if not box:
        raise FetchError("네이버: 당첨번호 영역을 찾지 못함 (화면 구조 변경?)")
    nums = [int(x) for x in re.findall(r'class="ball[^"]*">(\d+)<', box.group(1))]
    bonus = re.findall(r'class="ball[^"]*">(\d+)<', box.group(2))
    date = re.search(rf"\b{rnd}회차 \((\d{{4}})\.(\d{{2}})\.(\d{{2}})\.\)", html)
    prize = re.search(r'1등 당첨금 <strong[^>]*>([\d,]+)</strong>원 \(당첨게임 수 (\d+)개\)', html)
    if not bonus or not date:
        raise FetchError("네이버: 보너스 번호나 추첨일을 찾지 못함 (화면 구조 변경?)")
    return {
        "round": rnd,
        "date": "-".join(date.groups()),
        "numbers": sorted(nums),
        "bonus": int(bonus[0]),
        "first_prize_amount": int(prize.group(1).replace(",", "")) if prize else 0,
        "first_prize_winners": int(prize.group(2)) if prize else 0,
    }


def from_naver(rnd, get_text=http_get_text):
    html = get_text(NAVER_URL.format(urllib.parse.quote(f"로또 {rnd}회 당첨번호")), timeout=15)
    return parse_naver(html, rnd)


# ---------- 출처 3: smok95/lotto (GitHub 공개 JSON) ----------

SMOK95_ONE = "https://smok95.github.io/lotto/results/{}.json"
SMOK95_ALL = "https://smok95.github.io/lotto/results/all.json"


def parse_smok95(raw):
    first = (raw.get("divisions") or [{}])[0] or {}
    return {
        "round": raw["draw_no"],
        "date": raw["date"][:10],
        "numbers": sorted(raw["numbers"]),
        "bonus": raw["bonus_no"],
        "first_prize_amount": first.get("prize", 0),
        "first_prize_winners": first.get("winners", 0),
    }


def from_smok95(rnd, get_text=http_get_text):
    try:
        return parse_smok95(json.loads(get_text(SMOK95_ONE.format(rnd), timeout=10)))
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None  # 아직 올라오지 않음
        raise


def smok95_all(get_text=http_get_text):
    return [parse_smok95(r) for r in json.loads(get_text(SMOK95_ALL, timeout=30))]


SOURCES = [("동행복권", from_dhlottery), ("네이버", from_naver), ("smok95", from_smok95)]


def fetch_round(rnd, sources, get_text, dead, log):
    """여러 출처를 차례로 시도. 번호를 찾으면 돌려주고, '아직 추첨 전'이면 None.
    한 출처도 제대로 답하지 못하면(모두 오류) FetchError."""
    errors, answered = [], False
    for name, fn in sources:
        if name in dead:
            continue
        try:
            d = fn(rnd, get_text=get_text)
        except Exception as e:
            errors.append(f"{name}: {e}")
            if name == "동행복권":
                dead.add(name)  # 막혀 있으면 이번 실행에서는 다시 시도하지 않음
            continue
        answered = True
        if d is None:
            continue  # 이 출처에는 아직 없음 -> 다음 출처 확인
        if d["round"] != rnd or not valid_draw(d):
            errors.append(f"{name}: 잘못된 데이터 {d}")
            continue
        d["source"] = name
        return d
    if not answered:
        raise FetchError(f"{rnd}회 조회 실패 - " + " / ".join(errors))
    if errors:
        log("  (일부 출처 실패: " + " / ".join(errors) + ")")
    return None


def update(path=DEFAULT_DATA_PATH, get_text=http_get_text, sources=None, delay=0.3, log=print):
    """새 회차를 받아 저장하고, 새로 추가된 회차 목록을 돌려준다."""
    sources = sources or SOURCES
    draws = load_draws(path)
    have = {d["round"] for d in draws}
    added = []

    # 처음이거나 중간에 빈 회차가 있으면 smok95 전체 파일로 한 번에 채운다 (요청 1번)
    if not draws or len(draws) < draws[-1]["round"]:
        try:
            bulk = [d for d in smok95_all(get_text) if d["round"] not in have and valid_draw(d)]
            for d in bulk:
                d["source"] = "smok95"
            added.extend(bulk)
            have.update(d["round"] for d in bulk)
            log(f"  smok95 전체 파일에서 {len(bulk)}개 회차를 받았습니다.")
        except Exception as e:
            log(f"  smok95 전체 파일 실패({e}), 회차별로 받습니다.")

    # 1회부터 빈 회차가 없는지 확인하며, 마지막 회차 다음부터 회차별로 받는다
    rnd = 1
    while rnd in have:
        rnd += 1
    dead = set()
    while True:
        d = fetch_round(rnd, sources, get_text, dead, log)
        if d is None:
            break  # 아직 추첨하지 않은 회차 -> 최신까지 다 받음
        added.append(d)
        have.add(rnd)
        log(f"  {rnd}회 ({d['date']}) {d['numbers']} + {d['bonus']}  [{d['source']}]")
        if len(added) % 100 == 0:
            save_draws(draws + added, path)  # 중간 저장
        rnd += 1
        while rnd in have:
            rnd += 1
        if delay:
            time.sleep(delay)  # 서버에 부담 주지 않도록 천천히

    if added:
        save_draws(draws + added, path)
    return added
