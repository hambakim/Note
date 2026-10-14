"""통계를 바탕으로 조건에 맞는 번호 조합을 무작위로 만든다.

전략(strategy)
- mix    : 많이 나온 번호 N개 + 안 나온(덜 나온) 번호 M개 + 나머지 무작위  (기본)
- hot    : 출현 횟수에 비례하는 가중치로 뽑기
- cold   : 오래 안 나온 번호일수록 가중치를 높여 뽑기
- pair   : 자주 함께 나온 번호 쌍 하나를 넣고, 나머지는 출현 횟수 가중치로 채우기
- random : 완전 무작위 (필터만 적용)

1단계 - 중복 검사: 역대 1등 조합이 다시 1등이 된 적이 있는지 확인한다.
  중복이 없거나 확률이 매우 낮으면(기본 1% 미만) 이전 1등 조합을 후보에서 전부 제외한다.
2단계 - 모양 필터(기본 켜짐): 홀짝 6:0/0:6 제외, 고저 6:0/0:6 제외, 합계가 역대 가운데 80% 범위 밖이면 제외,
3연속 이상 번호 제외, 번호대가 2구간 이하로 몰리면 제외.
"""

import random
from dataclasses import dataclass, field

from . import stats

STRATEGIES = ("mix", "hot", "cold", "pair", "random")


@dataclass
class Filters:
    past_policy: str = "auto"           # auto: 중복 검사 결과로 결정 / exclude: 항상 제외 / allow: 제외 안 함
    repeat_threshold: float = 0.01      # auto일 때 이 확률보다 낮으면 제외
    max_overlap_with_past: int = 6      # 역대 1등과 최대 몇 개까지 겹쳐도 되는지 (6이면 검사 안 함)
    odd_range: tuple = (1, 5)           # 홀수 개수 허용 범위
    low_range: tuple = (1, 5)           # 저번호(1~22) 개수 허용 범위
    sum_coverage: float = 0.8           # 역대 합계 분포 중 가운데 몇 %를 허용할지 (0이면 끔)
    max_run: int = 2                    # 연속번호 최대 길이
    min_decade_spread: int = 3          # 최소 몇 개 번호대에 걸쳐야 하는지


@dataclass
class Ticket:
    numbers: list
    hot: list = field(default_factory=list)
    cold: list = field(default_factory=list)

    @property
    def total(self):
        return sum(self.numbers)


class Generator:
    def __init__(self, draws, recent=None, pool_size=15, filters=None, seed=None):
        """
        draws     : 역대 당첨 기록
        recent    : 최근 N회만 기준으로 hot/cold를 정할 때 (None이면 전체)
        pool_size : hot/cold 후보를 몇 개씩 둘지
        """
        self.draws = draws
        self.filters = filters or Filters()
        self.rng = random.Random(seed)

        target = draws[-recent:] if recent else draws
        self.freq = stats.number_frequency(target)
        self.gap = stats.last_seen_gap(draws)
        self.hot_pool, self.cold_pool, _ = stats.hot_cold(draws, recent=recent, size=pool_size)
        # 덜 나온 번호 + 오래 안 나온 번호를 합쳐 cold 후보를 넓힌다 (hot과 겹치는 번호는 뺌)
        overdue = sorted(stats.ALL_NUMBERS, key=lambda n: (-self.gap[n], n))[:pool_size]
        self.cold_pool = [n for n in dict.fromkeys(self.cold_pool + overdue) if n not in self.hot_pool]
        self.top_pairs = [p for p, _ in stats.pair_frequency(target, top=30)]

        self.past_sets = [frozenset(d["numbers"]) for d in draws]
        self.past_combos = {tuple(d["numbers"]) for d in draws}
        # 1단계: 중복 당첨 검사 -> 이전 1등 조합을 제외할지 결정
        self.repeat = stats.repeat_check(draws, self.filters.repeat_threshold)
        policy = self.filters.past_policy
        self.exclude_past = self.repeat["exclude"] if policy == "auto" else policy == "exclude"
        self.sum_lo, self.sum_hi = (
            stats.sum_range(draws, self.filters.sum_coverage)
            if self.filters.sum_coverage
            else (21, 255)
        )

    # ---------- 조건 검사 ----------

    def reject_reason(self, numbers):
        """조건에 안 맞으면 이유를, 맞으면 None을 돌려준다."""
        f = self.filters
        nums = sorted(numbers)
        if self.exclude_past and tuple(nums) in self.past_combos:
            return "이전 1등 조합과 같음"
        if f.max_overlap_with_past < 6:
            s = set(nums)
            if any(len(s & p) > f.max_overlap_with_past for p in self.past_sets):
                return f"역대 1등과 {f.max_overlap_with_past + 1}개 이상 겹침"
        if not f.odd_range[0] <= stats.odd_count(nums) <= f.odd_range[1]:
            return "홀짝 비율이 한쪽으로 쏠림"
        if not f.low_range[0] <= stats.low_count(nums) <= f.low_range[1]:
            return "고저 비율이 한쪽으로 쏠림"
        if not self.sum_lo <= sum(nums) <= self.sum_hi:
            return f"합계 {sum(nums)}가 범위({self.sum_lo}~{self.sum_hi}) 밖"
        if stats.longest_run(nums) > f.max_run:
            return f"{f.max_run + 1}연속 이상 번호 포함"
        if stats.decade_spread(nums) < f.min_decade_spread:
            return "번호대가 한쪽에 몰림"
        return None

    # ---------- 뽑기 도구 ----------

    def _weighted_pick(self, candidates, weights, k):
        """가중치에 비례해 중복 없이 k개 뽑기."""
        candidates, weights = list(candidates), list(weights)
        picked = []
        for _ in range(min(k, len(candidates))):
            i = self.rng.choices(range(len(candidates)), weights=weights)[0]
            picked.append(candidates.pop(i))
            weights.pop(i)
        return picked

    def _fill(self, chosen, k, pool=None, weight=None):
        pool = [n for n in (pool or stats.ALL_NUMBERS) if n not in chosen]
        if weight is None:
            return chosen + self.rng.sample(pool, min(k, len(pool)))
        return chosen + self._weighted_pick(pool, [weight(n) for n in pool], k)

    def _candidate(self, strategy, n_hot, n_cold, include, exclude):
        chosen = list(include)
        banned = set(exclude) | set(chosen)

        def allowed(pool):
            return [n for n in pool if n not in banned]

        if strategy == "mix":
            room = 6 - len(chosen)
            hot_pool = allowed(self.hot_pool)
            hot = self.rng.sample(hot_pool, min(n_hot, room, len(hot_pool)))
            banned.update(hot)
            cold_pool = allowed(self.cold_pool)
            cold = self.rng.sample(cold_pool, min(n_cold, room - len(hot), len(cold_pool)))
            banned.update(cold)
            chosen += hot + cold
        elif strategy == "pair":
            pairs = [p for p in self.top_pairs if not set(p) & banned]
            if pairs and len(chosen) <= 4:
                chosen += list(self.rng.choice(pairs))
                banned.update(chosen)

        need = 6 - len(chosen)
        if need < 0:
            raise ValueError("고정 번호가 6개를 넘습니다.")
        pool = allowed(stats.ALL_NUMBERS)
        if strategy in ("hot", "pair"):
            chosen = self._fill(chosen, need, pool, weight=lambda n: self.freq[n] + 1)
        elif strategy == "cold":
            chosen = self._fill(chosen, need, pool, weight=lambda n: self.gap[n] + 1)
        else:
            chosen = self._fill(chosen, need, pool)
        return sorted(chosen)

    # ---------- 공개 함수 ----------

    def generate(self, count=5, strategy="mix", n_hot=3, n_cold=2,
                 include=(), exclude=(), max_tries=20000):
        if strategy not in STRATEGIES:
            raise ValueError(f"strategy는 {STRATEGIES} 중 하나여야 합니다.")
        include, exclude = list(dict.fromkeys(include)), set(exclude)
        for n in list(include) + list(exclude):
            if not 1 <= n <= 45:
                raise ValueError(f"번호 {n}은(는) 1~45 범위가 아닙니다.")
        if set(include) & exclude:
            raise ValueError("같은 번호를 포함과 제외에 동시에 넣을 수 없습니다.")
        if len(include) > 6:
            raise ValueError("고정 번호는 최대 6개입니다.")
        if 45 - len(exclude) < 6:
            raise ValueError("제외 번호가 너무 많아 6개를 고를 수 없습니다.")

        tickets, seen = [], set()
        reasons = {}
        for _ in range(max_tries):
            nums = self._candidate(strategy, n_hot, n_cold, include, exclude)
            key = tuple(nums)
            if key in seen:
                continue
            reason = self.reject_reason(nums)
            if reason:
                reasons[reason] = reasons.get(reason, 0) + 1
                continue
            seen.add(key)
            tickets.append(Ticket(
                numbers=nums,
                hot=[n for n in nums if n in self.hot_pool],
                cold=[n for n in nums if n in self.cold_pool],
            ))
            if len(tickets) == count:
                break

        if len(tickets) < count:
            top = sorted(reasons.items(), key=lambda kv: -kv[1])[:3]
            detail = ", ".join(f"{r}({c}회)" for r, c in top)
            raise RuntimeError(
                f"조건에 맞는 조합을 {count}개 만들지 못했습니다({len(tickets)}개 성공). "
                f"조건을 완화해 보세요. 주로 걸린 조건: {detail}"
            )
        return tickets
