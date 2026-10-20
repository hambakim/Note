"""경매 매물 중 조건(K3·아반떼 / 19~20년식 / 7만km 이하 / 흰색·검정)에 맞는 차를 골라
카카오톡 '나에게 보내기'로 알린다.

웹페이지(index.html)와 같은 판정 규칙을 쓴다. 규칙을 바꾸면 두 곳을 같이 고칠 것.

  python car_alert.py           # 조건에 맞는 새 매물을 화면에만 출력
  python car_alert.py --send    # 카톡으로 보내고 data/notified.json에 기록 (같은 차는 다시 안 보냄)
  python car_alert.py --send --test   # 연결 확인용 테스트 메시지 한 통 (기록 안 남김)

카톡 설정은 lotto-analyzer와 같은 시크릿(KAKAO_REST_API_KEY, KAKAO_REFRESH_TOKEN)을 그대로 쓴다.
"""

import argparse
import json
import os
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
DATA = HERE / "data"
PAGE_URL = "https://hambakim.github.io/Note/car-auction/"

# 경매장마다 색 이름이 달라서 대표 이름으로 묶는다
COLOR_ALIASES = {
    "흰색": ["흰", "화이트", "백색", "white", "펄", "스노우"],
    "검정": ["검정", "검은", "블랙", "흑색", "black"],
}
MODEL_ALIASES = {
    "K3": ["k3"],
    "아반떼": ["아반떼", "avante", "elantra"],
}


def load_json(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def norm_color(color):
    c = (color or "").lower().replace(" ", "")
    for name, keys in COLOR_ALIASES.items():
        if any(k in c for k in keys):
            return name
    return color or ""


def norm_model(model):
    m = (model or "").lower().replace(" ", "")
    for name, keys in MODEL_ALIASES.items():
        if any(k in m for k in keys):
            return name
    return model or ""


def evaluate(item, crit):
    """level: match(조건 일치) / near(색상만 다름) / out(조건 밖)"""
    model = norm_model(item.get("model"))
    year = item.get("year") or 0
    mileage = item.get("mileage")
    color = norm_color(item.get("color"))

    hard_ok = (model in crit["models"]
               and crit["yearMin"] <= year <= crit["yearMax"]
               and mileage is not None and mileage <= crit["mileageMax"])
    if color in crit["colorsPreferred"]:
        color_rank = 1
    elif color in crit["colorsOk"]:
        color_rank = 2
    else:
        color_rank = 0

    if not hard_ok:
        level = "out"
    elif color_rank:
        level = "match"
    else:
        level = "near"

    cap = None
    base = crit["maxBid"].get(f"{model}-{year}")
    if base:
        d = crit["deductions"]
        cap = base
        if item.get("frame"):
            cap -= d["frame"]
        if color_rank == 0:
            cap -= d["otherColor"]
        cap -= max(0, (item.get("myDamage") or 0) - 1) * d["perExtraAccident"]

    return {"level": level, "model": model, "color": color, "colorRank": color_rank, "cap": cap}


def is_closed(item, today=None):
    if item.get("status") in ("낙찰", "유찰", "패스"):
        return True
    when = item.get("auctionDate")
    return bool(when) and when < (today or date.today()).isoformat()


def man(v):
    """만원 단위 숫자를 '1,040만' 형태로"""
    return f"{v:,}만" if v is not None else "-"


def format_message(item, ev):
    rank = "1순위" if ev["colorRank"] == 1 else "2순위"
    price = item.get("currentPrice") or item.get("startPrice")
    lines = [
        f"🚗 조건 일치 매물 ({rank})",
        f"{item.get('year')} {ev['model']} {item.get('trim') or ''}".strip(),
        f"{ev['color']} / {item['mileage']:,}km",
        f"시작가 {man(item.get('startPrice'))}원" + (f" (현재 {man(item['currentPrice'])})" if item.get("currentPrice") else ""),
    ]
    damage = []
    if item.get("frame"):
        damage.append("골격판금")
    if item.get("myDamage"):
        damage.append(f"내차피해 {item['myDamage']}회")
    lines.append("사고: " + (", ".join(damage) if damage else "표시 없음"))
    if ev["cap"]:
        verdict = "입찰 고려" if price and price <= ev["cap"] else "상한 초과"
        lines.append(f"권장 상한 {man(ev['cap'])}원 → {verdict}")
    if item.get("auctionDate"):
        lines.append(f"경매일 {item['auctionDate']} ({item.get('source') or ''})".replace(" ()", ""))
    return "\n".join(lines)


def find_new_matches(listings, crit, notified, today=None):
    out = []
    for item in listings:
        if item["id"] in notified or is_closed(item, today):
            continue
        ev = evaluate(item, crit)
        if ev["level"] == "match":
            out.append((item, ev))
    out.sort(key=lambda p: p[1]["colorRank"])
    return out


def kakao_client():
    """로또 분석기의 카카오 모듈을 같이 쓴다 (같은 시크릿·토큰 파일)."""
    sys.path.insert(0, str(HERE.parent / "lotto-analyzer"))
    from lotto_analyzer.kakao import KakaoClient
    return KakaoClient()


def save_new_token(client):
    """refresh_token이 새로 나오면 워크플로가 시크릿을 갱신하도록 파일로 넘긴다."""
    token_file = os.environ.get("KAKAO_NEW_REFRESH_TOKEN_FILE")
    if token_file and client.new_refresh_token:
        Path(token_file).write_text(client.new_refresh_token, encoding="utf-8")


def main(argv=None):
    ap = argparse.ArgumentParser(description="경매 매물 조건 알림")
    ap.add_argument("--send", action="store_true", help="카카오톡으로 보내기")
    ap.add_argument("--test", action="store_true", help="테스트 메시지 한 통만 (기록 안 남김)")
    args = ap.parse_args(argv)

    if args.test:
        text = ("🚗 경매 매물 알리미 연결 테스트\n"
                "이 메시지가 보이면 카톡 알림 설정 완료!\n"
                "조건 일치 매물이 올라오면 이렇게 알려 드려요.")
        print(text)
        if args.send:
            client = kakao_client()
            client.send_text(text, link=PAGE_URL, button="알리미 열기")
            save_new_token(client)
            print("테스트 메시지 전송 완료")
        return 0

    crit = load_json("criteria.json")
    listings = load_json("listings.json")
    notified = load_json("notified.json")
    matches = find_new_matches(listings, crit, notified)

    if not matches:
        print("새로 알릴 조건 일치 매물 없음")
        return 0

    messages = [format_message(item, ev) for item, ev in matches]
    for m in messages:
        print(m, end="\n\n")
    if not args.send:
        return 0

    client = kakao_client()
    for (item, _), text in zip(matches, messages):
        link = item.get("url") or PAGE_URL
        client.send_long_text(text, link=link, button="매물 보기")
        notified[item["id"]] = date.today().isoformat()
    (DATA / "notified.json").write_text(json.dumps(notified, ensure_ascii=False, indent=1) + "\n",
                                       encoding="utf-8")

    save_new_token(client)
    print(f"카톡 {len(matches)}건 전송")
    return 0


if __name__ == "__main__":
    sys.exit(main())
