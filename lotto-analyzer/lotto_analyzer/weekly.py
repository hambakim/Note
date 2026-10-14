"""이번 주 구매용 추천 조합 만들기 + 기록 + 지난 추천 결과 확인.

흐름
1. 이전 당첨번호 중복 검사 -> 이전 1등 조합 제외 여부 결정
2. 당첨 가능성이 낮을 것으로 보는 조합(이전 1등 조합, 쏠린 모양)을 지운다
3. 남은 조합 중에서 mix 전략으로 10게임을 뽑는다 (서로 3개 이하로만 겹치게)
4. data/picks.json에 회차별로 기록 -> 토요일 추첨 후 결과 확인에 쓴다
"""

import json
from datetime import date, timedelta
from pathlib import Path

from . import stats
from .generator import Generator

PICKS_PATH = Path(__file__).resolve().parent.parent / "data" / "picks.json"
LABELS = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"


def next_round_info(draws):
    latest = draws[-1]
    d = date.fromisoformat(latest["date"]) + timedelta(days=7)
    return latest["round"] + 1, d


def make_weekly_picks(draws, count=10, max_shared=3, seed=None):
    """이번 주(다음 회차) 추천 조합을 만든다. seed를 안 주면 회차 번호를 써서 다시 돌려도 같은 결과."""
    rnd, draw_date = next_round_info(draws)
    gen = Generator(draws, seed=rnd if seed is None else seed)
    tickets = gen.generate(count=count, max_shared=max_shared)
    removed, remaining = gen.elimination_summary()
    return {
        "round": rnd,
        "draw_date": draw_date.isoformat(),
        "based_on": draws[-1]["round"],
        "tickets": [t.numbers for t in tickets],
        "excluded_past": gen.repeat["unique_combos"] if gen.exclude_past else 0,
        "removed": removed,
        "remaining": remaining,
        "repeat_lines": stats.describe_repeat_check(gen.repeat),
    }


def load_picks(path=PICKS_PATH):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_picks(picks, path=PICKS_PATH):
    """회차 번호를 키로 저장. 같은 회차를 다시 만들면 덮어쓴다."""
    path = Path(path)
    data = load_picks(path)
    data[str(picks["round"])] = {
        "draw_date": picks["draw_date"],
        "based_on": picks["based_on"],
        "tickets": picks["tickets"],
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def rank(ticket, draw):
    hit = len(set(ticket) & set(draw["numbers"]))
    if hit == 6:
        return 1
    if hit == 5:
        return 2 if draw["bonus"] in ticket else 3
    return {4: 4, 3: 5}.get(hit)


def check_results(draws, picks):
    """지난 추천 조합을 실제 당첨번호와 비교. [(회차, 당첨번호, [(조합, 등수), ...]), ...]"""
    by_round = {d["round"]: d for d in draws}
    out = []
    for r, p in sorted(picks.items(), key=lambda kv: int(kv[0])):
        draw = by_round.get(int(r))
        if draw:
            out.append((int(r), draw, [(t, rank(t, draw)) for t in p["tickets"]]))
    return out


def _fmt(nums):
    return " ".join(f"{n:02d}" for n in nums)


def format_message_parts(picks):
    """카카오톡으로 보낼 메시지 [요약, 10게임]. 10게임은 199자라 한 건에 다 들어간다."""
    d = date.fromisoformat(picks["draw_date"])
    header = "\n".join([
        f"[로또 {picks['round']}회 추천 {len(picks['tickets'])}게임]",
        f"추첨 {d.month}/{d.day}(토) · {picks['based_on']}회까지 분석",
        f"전체 8,145,060개 중 이전 1등 {picks['excluded_past']:,}개와 "
        f"쏠린 모양을 지우고 남은 약 {picks['remaining']:,}개에서 골랐어요.",
    ])
    body = "\n".join(f"{label} {_fmt(t)}" for label, t in zip(LABELS, picks["tickets"]))
    return [header, body]


def format_message(picks):
    return "\n\n".join(format_message_parts(picks))


def format_result_message(rnd, draw, results):
    lines = [f"[로또 {rnd}회 결과]", f"당첨 {_fmt(draw['numbers'])} + {draw['bonus']:02d}", ""]
    for label, (t, r) in zip(LABELS, results):
        lines.append(f"{label} {_fmt(t)} {f'{r}등' if r else '-'}")
    return "\n".join(lines)
