"""통계 결과를 사람이 읽기 좋은 Markdown 문서로 만든다 (매주 자동 갱신용)."""

from datetime import datetime, timedelta, timezone

from . import stats
from .generator import Generator

KST = timezone(timedelta(hours=9))


def _fmt(nums):
    return " ".join(f"{n:02d}" for n in nums)


def build_report(draws, recent=50, picks=5, seed=None):
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

    w(f"## 6. 이번 주 추천 조합 (mix 전략, {picks}개)\n")
    w("3번 판단에 따라 이전 1등 조합을 제외한 뒤, 많이 나온 번호 3개 + 덜 나온/오래 안 나온 번호 2개 + 무작위 1개로 만들었습니다.\n")
    for i, t in enumerate(Generator(draws, seed=seed).generate(count=picks), 1):
        w(f"{i}. `{_fmt(t.numbers)}`  (합계 {t.total})")
    w("\n> 로또 추첨은 매 회 독립 시행이라 어떤 조합이든 1등 확률은 8,145,060분의 1로 같습니다. "
      "이 통계는 재미와 번호 고르는 기준용입니다.\n")
    return "\n".join(out)
