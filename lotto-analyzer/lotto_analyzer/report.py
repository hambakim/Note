"""통계 결과를 사람이 읽기 좋은 Markdown 문서로 만든다 (매주 자동 갱신용)."""

from datetime import datetime, timedelta, timezone

from . import stats
from . import weekly

KST = timezone(timedelta(hours=9))


def _fmt(nums):
    return " ".join(f"{n:02d}" for n in nums)


def build_report(draws, recent=50, picks=10, seed=None):
    if not draws:
        return "# 로또 통계\n\n데이터가 없습니다. `python -m lotto_analyzer update`를 먼저 실행하세요.\n"

    latest = draws[-1]
    freq = stats.number_frequency(draws)
    gap = stats.last_seen_gap(draws)
    hot, cold, _ = stats.hot_cold(draws, size=10)
    r_hot, r_cold, r_freq = stats.hot_cold(draws, recent=recent, size=10)
    lo, hi = stats.sum_range(draws)
    now = datetime.now(KST).strftime("%Y-%m-%d %H:%M")

    out = []
    w = out.append
    w("# 로또 6/45 통계 리포트\n")
    w(f"- 생성 시각: {now} (KST)")
    w(f"- 분석 범위: 1회 ~ {latest['round']}회 (총 {len(draws)}회)")
    w(f"- 최신 회차: **{latest['round']}회 ({latest['date']})** "
      f"`{_fmt(latest['numbers'])}` + 보너스 `{latest['bonus']:02d}`\n")

    w("## 1. 번호별 출현 횟수 (보너스 제외)\n")
    w("| 순위 | 번호 | 횟수 | 최근 %d회 | 미출현 회차 |" % recent)
    w("|---:|---:|---:|---:|---:|")
    ranked = sorted(stats.ALL_NUMBERS, key=lambda n: (-freq[n], n))
    for i, n in enumerate(ranked, 1):
        w(f"| {i} | {n:02d} | {freq[n]} | {r_freq[n]} | {gap[n]} |")
    w("")

    w("## 2. 많이 나온 번호 / 적게 나온 번호\n")
    w(f"- 전체 기간 많이 나온 10개: `{_fmt(sorted(hot))}`")
    w(f"- 전체 기간 적게 나온 10개: `{_fmt(sorted(cold))}`")
    w(f"- 최근 {recent}회 많이 나온 10개: `{_fmt(sorted(r_hot))}`")
    w(f"- 최근 {recent}회 적게 나온 10개: `{_fmt(sorted(r_cold))}`")
    overdue = sorted(stats.ALL_NUMBERS, key=lambda n: -gap[n])[:10]
    w(f"- 가장 오래 안 나온 10개: " + ", ".join(f"{n:02d}({gap[n]}회)" for n in overdue) + "\n")

    w("## 3. 이전 당첨번호가 다시 1등이 된 적이 있나?\n")
    for line in stats.describe_repeat_check(stats.repeat_check(draws)):
        w(f"- {line}")
    w("")

    w("## 4. 자주 함께 나온 번호\n")
    w("| 번호 쌍 | 횟수 |\n|---|---:|")
    for p, c in stats.pair_frequency(draws, top=10):
        w(f"| {_fmt(p)} | {c} |")
    w("")
    w("| 번호 3개 묶음 | 횟수 |\n|---|---:|")
    for t, c in stats.triple_frequency(draws, top=5):
        w(f"| {_fmt(t)} | {c} |")
    w("")

    w("## 5. 당첨 조합의 모양\n")
    total = len(draws)
    odd = stats.shape_distribution(draws, stats.odd_count)
    w("홀수 개수별 비율: " + ", ".join(
        f"{k}개 {odd[k] / total:.1%}" for k in range(7)))
    run = stats.shape_distribution(draws, stats.longest_run)
    w("\n최장 연속번호 길이: " + ", ".join(
        f"{k}연속 {run[k] / total:.1%}" for k in sorted(run)))
    w(f"\n번호 합계 가운데 80% 범위: **{lo} ~ {hi}**\n")

    wp = (weekly.saved_picks_for_next_round(draws) if seed is None else None) \
        or weekly.make_weekly_picks(draws, count=picks, seed=seed)
    w(f"## 6. {wp['round']}회 추천 조합 ({len(wp['tickets'])}게임)\n")
    w("당첨 가능성이 낮을 것으로 보는 조합을 먼저 지우고, 남은 조합 중에서 골랐습니다. "
      "(전체 8,145,060개, 먼저 걸린 조건 기준 추정)\n")
    w("| 지운 조건 | 개수 |\n|---|---:|")
    for reason, n in wp["removed"]:
        w(f"| {reason} | 약 {n:,} |")
    w(f"| **남은 후보** | **약 {wp['remaining']:,}** |\n")
    for label, t in zip(weekly.LABELS, wp["tickets"]):
        w(f"- {label}) `{_fmt(t)}`  (합계 {sum(t)})")
    w("")

    results = weekly.check_results(draws, weekly.load_picks())
    if results:
        w("## 7. 지난 추천 조합 결과\n")
        w("| 회차 | 당첨번호 | 1등 | 2등 | 3등 | 4등 | 5등 |\n|---|---|---:|---:|---:|---:|---:|")
        for rnd, draw, rows in reversed(results[-10:]):
            cnt = [sum(1 for _, r in rows if r == k) for k in range(1, 6)]
            w(f"| {rnd} | `{_fmt(draw['numbers'])}` + {draw['bonus']:02d} | " + " | ".join(map(str, cnt)) + " |")
        w("")

    w("> 로또 추첨은 매 회 독립 시행이라 남은 조합 하나하나의 1등 확률도 8,145,060분의 1입니다. "
      "지우는 조건은 '살 조합을 고르는 기준'이고, 흔한 모양을 피해 당첨 시 나눠 가질 사람을 줄이는 효과가 있습니다.\n")
    return "\n".join(out)
