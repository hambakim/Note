"""웹페이지(index.html)가 읽는 요약 데이터 data/web.json 만들기.

웹페이지는 계산을 하지 않고 이 파일만 보여 준다.
그래서 카카오톡으로 받은 10게임과 웹페이지의 10게임이 항상 같다.
"""

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import stats, weekly

WEB_PATH = Path(__file__).resolve().parent.parent / "data" / "web.json"
KST = timezone(timedelta(hours=9))


def build_web_data(draws, picks_history, recent=50):
    freq = stats.number_frequency(draws)
    r_freq = stats.number_frequency(draws[-recent:])
    gap = stats.last_seen_gap(draws)
    hot, cold, _ = stats.hot_cold(draws, size=10)
    rc = stats.repeat_check(draws)
    wp = weekly.make_weekly_picks(draws)
    lo, hi = stats.sum_range(draws)
    total = len(draws)
    odd = stats.shape_distribution(draws, stats.odd_count)
    run = stats.shape_distribution(draws, stats.longest_run)

    results = []
    for rnd, draw, rows in reversed(weekly.check_results(draws, picks_history)[-10:]):
        results.append({
            "round": rnd,
            "date": draw["date"],
            "numbers": draw["numbers"],
            "bonus": draw["bonus"],
            "tickets": [{"numbers": t, "rank": r} for t, r in rows],
        })

    return {
        "updated_at": datetime.now(KST).strftime("%Y-%m-%d %H:%M"),
        "total_draws": total,
        "recent": recent,
        "latest": {k: draws[-1][k] for k in ("round", "date", "numbers", "bonus")},
        "latest_draws": [{k: d[k] for k in ("round", "date", "numbers", "bonus")}
                         for d in reversed(draws[-5:])],
        "frequency": [{"n": n, "count": freq[n], "recent": r_freq[n], "gap": gap[n]}
                      for n in stats.ALL_NUMBERS],
        "hot": sorted(hot),
        "cold": sorted(cold),
        "overdue": [{"n": n, "gap": gap[n]}
                    for n in sorted(stats.ALL_NUMBERS, key=lambda n: (-gap[n], n))[:10]],
        "pairs": [{"pair": list(p), "count": c} for p, c in stats.pair_frequency(draws, top=10)],
        "repeat": {
            "duplicates": [{"numbers": list(c), "rounds": r} for c, r in rc["duplicates"].items()],
            "unique_combos": rc["unique_combos"],
            "p_next_repeat": rc["p_next_repeat"],
            "exclude": rc["exclude"],
            "lines": stats.describe_repeat_check(rc),
        },
        "shape": {
            "sum_range": [lo, hi],
            "odd": [{"k": k, "ratio": odd[k] / total} for k in range(7)],
            "run": [{"k": k, "ratio": run[k] / total} for k in sorted(run)],
        },
        "this_week": {
            "round": wp["round"],
            "draw_date": wp["draw_date"],
            "based_on": wp["based_on"],
            "tickets": wp["tickets"],
            "removed": [{"reason": r, "count": n} for r, n in wp["removed"]],
            "remaining": wp["remaining"],
        },
        "results": results,
    }


def write_web_data(draws, picks_history, path=WEB_PATH):
    data = build_web_data(draws, picks_history)
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return data
