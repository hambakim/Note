"""역대 당첨번호 통계.

여기서 다루는 draws는 fetch.load_draws()가 돌려주는 리스트다.
각 원소: {"round": 1, "date": "2002-12-07", "numbers": [10, 23, 29, 33, 37, 40], "bonus": 16, ...}
"""

from collections import Counter
from itertools import combinations

ALL_NUMBERS = range(1, 46)


def number_frequency(draws, include_bonus=False):
    """번호별 출현 횟수. 한 번도 안 나온 번호도 0으로 들어간다."""
    counter = Counter({n: 0 for n in ALL_NUMBERS})
    for d in draws:
        counter.update(d["numbers"])
        if include_bonus:
            counter[d["bonus"]] += 1
    return counter


def last_seen_gap(draws):
    """번호별로 마지막 출현 후 몇 회째 안 나오고 있는지 (0 = 가장 최근 회차에 나옴)."""
    if not draws:
        return {n: 0 for n in ALL_NUMBERS}
    latest = draws[-1]["round"]
    first = draws[0]["round"]
    last = {}
    for d in draws:
        for n in d["numbers"]:
            last[n] = d["round"]
    # 한 번도 안 나왔으면 전체 기간 내내 안 나온 것으로 본다
    return {n: latest - last.get(n, first - 1) for n in ALL_NUMBERS}


def pair_frequency(draws, top=None):
    """같은 회차에 함께 나온 두 번호 쌍의 횟수."""
    counter = Counter()
    for d in draws:
        counter.update(combinations(d["numbers"], 2))
    return counter.most_common(top)


def triple_frequency(draws, top=None):
    """같은 회차에 함께 나온 세 번호 묶음의 횟수."""
    counter = Counter()
    for d in draws:
        counter.update(combinations(d["numbers"], 3))
    return counter.most_common(top)


def duplicate_winning_combos(draws):
    """같은 6개 조합이 두 번 이상 1등 번호가 된 적이 있는지. {조합: [회차들]}"""
    seen = {}
    for d in draws:
        seen.setdefault(tuple(d["numbers"]), []).append(d["round"])
    return {combo: rounds for combo, rounds in seen.items() if len(rounds) > 1}


def find_combo(draws, combo):
    """내 조합과 역대 당첨번호를 비교해 3개 이상 겹친 회차를 등수별로 돌려준다."""
    combo = set(combo)
    result = {6: [], "5+bonus": [], 5: [], 4: [], 3: []}
    for d in draws:
        hit = len(combo & set(d["numbers"]))
        if hit == 6:
            result[6].append(d["round"])
        elif hit == 5 and d["bonus"] in combo:
            result["5+bonus"].append(d["round"])
        elif hit in (5, 4, 3):
            result[hit].append(d["round"])
    return result


# ---- 조합의 "모양" 통계: 생성기 필터에 쓰인다 ----

def odd_count(numbers):
    return sum(1 for n in numbers if n % 2)


def low_count(numbers):
    """1~22를 저번호로 본다."""
    return sum(1 for n in numbers if n <= 22)


def longest_run(numbers):
    """가장 길게 이어진 연속번호 길이. 예: [3,4,5,20,..] -> 3"""
    nums = sorted(numbers)
    best = run = 1
    for a, b in zip(nums, nums[1:]):
        run = run + 1 if b == a + 1 else 1
        best = max(best, run)
    return best


def decade_spread(numbers):
    """번호대(1~9, 10~19, 20~29, 30~39, 40~45) 중 몇 개 구간에 걸쳐 있는지."""
    return len({n // 10 for n in numbers})


def shape_distribution(draws, key):
    return Counter(key(d["numbers"]) for d in draws)


def sum_range(draws, coverage=0.8):
    """역대 번호 합계 중 가운데 coverage(기본 80%)가 들어가는 범위."""
    sums = sorted(sum(d["numbers"]) for d in draws)
    if not sums:
        return (21, 255)  # 가능한 최소~최대
    cut = (1 - coverage) / 2
    lo = sums[int(len(sums) * cut)]
    hi = sums[min(len(sums) - 1, int(len(sums) * (1 - cut)))]
    return (lo, hi)


def hot_cold(draws, recent=None, size=10):
    """많이 나온 번호(hot)와 적게 나온 번호(cold). recent를 주면 최근 N회만 본다."""
    target = draws[-recent:] if recent else draws
    freq = number_frequency(target)
    ordered = sorted(ALL_NUMBERS, key=lambda n: (-freq[n], n))
    hot = ordered[:size]
    cold = sorted(ALL_NUMBERS, key=lambda n: (freq[n], n))[:size]
    return hot, cold, freq


# ---- 중복 당첨 검사: 이전 당첨조합을 후보에서 뺄지 결정하는 근거 ----

TOTAL_COMBOS = 8_145_060  # 45개 중 6개를 고르는 경우의 수 (45C6)


def repeat_check(draws, threshold=0.01):
    """역대 1등 조합이 중복된 적이 있는지 검사하고, 이전 당첨조합을 제외할지 판단한다.

    - duplicates            : 두 번 이상 나온 조합 {조합: [회차들]}
    - unique_combos         : 지금까지 나온 서로 다른 1등 조합 수
    - p_next_repeat         : 다음 회차가 이전 1등 조합 중 하나와 똑같을 확률 (= 고유 조합 수 / 8,145,060)
    - p_any_repeat_so_far   : 지금까지 회차 수라면 이론상 한 번이라도 중복이 나왔을 확률 (생일 문제)
    - exclude               : 중복이 없거나, p_next_repeat가 threshold(기본 1%)보다 낮으면 True
    """
    dup = duplicate_winning_combos(draws)
    unique = len({tuple(d["numbers"]) for d in draws})
    p_none = 1.0
    for k in range(len(draws)):
        p_none *= 1 - k / TOTAL_COMBOS
    p_next = unique / TOTAL_COMBOS
    return {
        "draws": len(draws),
        "duplicates": dup,
        "unique_combos": unique,
        "p_next_repeat": p_next,
        "p_any_repeat_so_far": 1 - p_none,
        "exclude": not dup or p_next < threshold,
    }


def describe_repeat_check(rc):
    """repeat_check 결과를 사람이 읽을 문장 목록으로."""
    lines = []
    if rc["duplicates"]:
        rounds = "; ".join(f"{' '.join(f'{n:02d}' for n in c)} → {', '.join(map(str, r))}회"
                           for c, r in rc["duplicates"].items())
        lines.append(f"역대 {rc['draws']}회 중 같은 1등 조합이 다시 나온 적: 있음 ({rounds})")
    else:
        lines.append(f"역대 {rc['draws']}회 중 같은 1등 조합이 다시 나온 적: 없음 (0번)")
    lines.append(f"다음 회차가 이전 1등 조합 {rc['unique_combos']:,}개 중 하나와 같을 확률: "
                 f"{rc['p_next_repeat']:.4%} (약 {round(1 / rc['p_next_repeat']):,}분의 1)"
                 if rc["p_next_repeat"] else "이전 1등 조합이 없습니다.")
    if rc["exclude"]:
        why = "중복이 없음" if not rc["duplicates"] else "확률이 매우 낮음"
        lines.append(f"판단: {why} → 이전 1등 조합 {rc['unique_combos']:,}개를 후보에서 전부 제외")
    else:
        lines.append("판단: 중복 확률이 기준보다 높음 → 이전 1등 조합을 제외하지 않음")
    return lines
