import json
import random
import re
import urllib.error
import urllib.parse
import tempfile
import unittest
from pathlib import Path

from lotto_analyzer import fetch, stats
from lotto_analyzer.generator import Filters, Generator


def fake_draws(n=300, seed=1):
    rng = random.Random(seed)
    out = []
    for r in range(1, n + 1):
        nums = rng.sample(range(1, 46), 7)
        out.append({"round": r, "date": "2020-01-01", "numbers": sorted(nums[:6]), "bonus": nums[6]})
    return out


def fake_api(latest, blocked=("dhlottery",)):
    """latest 회차까지만 결과가 있는 가짜 인터넷. blocked에 든 출처는 접속 실패."""
    def numbers(r):
        nums = random.Random(r).sample(range(1, 46), 7)
        return sorted(nums[:6]), nums[6]

    def get_text(url, timeout=10):
        if "dhlottery" in url:
            if "dhlottery" in blocked:
                raise OSError("timed out")
            r = int(url.rsplit("=", 1)[1])
            if r > latest:
                return json.dumps({"returnValue": "fail"})
            nums, bonus = numbers(r)
            raw = {"returnValue": "success", "drwNo": r, "drwNoDate": "2020-01-01", "bnusNo": bonus}
            raw.update({f"drwtNo{i + 1}": n for i, n in enumerate(nums)})
            return json.dumps(raw)
        if "smok95" in url:
            if "smok95" in blocked:
                raise OSError("down")
            def one(r):
                nums, bonus = numbers(r)
                return {"draw_no": r, "numbers": nums, "bonus_no": bonus,
                        "date": "2020-01-01T00:00:00Z", "divisions": [{"prize": 1, "winners": 1}]}
            if url.endswith("all.json"):
                return json.dumps([one(r) for r in range(1, latest + 1)])
            r = int(url.rsplit("/", 1)[1].split(".")[0])
            if r > latest:
                raise urllib.error.HTTPError(url, 404, "nf", None, None)
            return json.dumps(one(r))
        if "naver" in url:
            if "naver" in blocked:
                raise OSError("down")
            q = urllib.parse.unquote(url.split("query=")[1])
            r = min(int(re.search(r"(\d+)회", q).group(1)), latest)  # 미래 회차면 최신 회차를 보여 줌
            nums, bonus = numbers(r)
            balls = " ".join(f'<span class="ball type1">{n}</span>' for n in nums)
            return (f'<a>{r}회차 (2020.01.01.) </a> <div class="winning_number"> {balls} </div> '
                    f'<div class="bonus_number"> <span class="ball type2">{bonus}</span> </div>')
        raise AssertionError(url)
    return get_text


class FetchTest(unittest.TestCase):
    def test_parse_real_round1(self):
        raw = {"returnValue": "success", "drwNo": 1, "drwNoDate": "2002-12-07", "bnusNo": 16,
               "drwtNo1": 10, "drwtNo2": 23, "drwtNo3": 29, "drwtNo4": 33, "drwtNo5": 37, "drwtNo6": 40}
        d = fetch.parse_draw(raw)
        self.assertEqual(d["numbers"], [10, 23, 29, 33, 37, 40])
        self.assertEqual(d["bonus"], 16)
        self.assertIsNone(fetch.parse_draw({"returnValue": "fail"}))

    def test_incremental_update(self):
        quiet = dict(delay=0, log=lambda *_: None)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draws.json"
            # 처음: smok95 전체 파일로 한 번에
            added = fetch.update(path, get_text=fake_api(5), **quiet)
            self.assertEqual([d["round"] for d in added], [1, 2, 3, 4, 5])
            # 다음 주: 6회만 새로 받아야 한다 (동행복권 막힘 -> 네이버)
            added = fetch.update(path, get_text=fake_api(6), **quiet)
            self.assertEqual([(d["round"], d["source"]) for d in added], [(6, "네이버")])
            self.assertEqual(len(fetch.load_draws(path)), 6)
            # 아직 추첨 전이면 아무것도 추가 안 됨 (네이버는 최신 회차를 보여 주지만 회차가 달라 무시)
            self.assertEqual(fetch.update(path, get_text=fake_api(6), **quiet), [])

    def test_fallback_and_all_sources_down(self):
        quiet = dict(delay=0, log=lambda *_: None)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draws.json"
            fetch.save_draws(fetch.load_draws(path) or [], path)
            added = fetch.update(path, get_text=fake_api(3, blocked=("dhlottery", "naver")), **quiet)
            self.assertEqual(len(added), 3)
            added = fetch.update(path, get_text=fake_api(4, blocked=("dhlottery", "naver")), **quiet)
            self.assertEqual([(d["round"], d["source"]) for d in added], [(4, "smok95")])
            with self.assertRaises(fetch.FetchError):
                fetch.update(path, get_text=fake_api(5, blocked=("dhlottery", "naver", "smok95")), **quiet)

    def test_naver_parse_real_layout(self):
        html = ('<a class="link">1245회차 (2026.10.10.) </a> ... <div class="win_ball"> <div class="winning_number"> '
                '<span class="ball type1">4</span> <span class="ball type1">5</span> <span class="ball type3">25</span> '
                '<span class="ball type3">28</span> <span class="ball type4">32</span> <span class="ball type5">42</span> '
                '</div> <div class="bonus_number"> <span class="ball type2">12</span> </div> </div> '
                '<p class="win_text">1등 당첨금 <strong class="emphasis">3,006,515,775</strong>원 (당첨게임 수 10개)</p>')
        d = fetch.parse_naver(html, 1245)
        self.assertEqual(d["numbers"], [4, 5, 25, 28, 32, 42])
        self.assertEqual(d["bonus"], 12)
        self.assertEqual(d["date"], "2026-10-10")
        self.assertEqual(d["first_prize_winners"], 10)
        self.assertIsNone(fetch.parse_naver(html, 1246))  # 아직 추첨 전


class StatsTest(unittest.TestCase):
    def setUp(self):
        self.draws = [
            {"round": 1, "numbers": [1, 2, 3, 4, 5, 6], "bonus": 7},
            {"round": 2, "numbers": [1, 2, 10, 20, 30, 40], "bonus": 3},
            {"round": 3, "numbers": [1, 2, 3, 4, 5, 6], "bonus": 9},
        ]

    def test_frequency_and_gap(self):
        f = stats.number_frequency(self.draws)
        self.assertEqual(f[1], 3)
        self.assertEqual(f[45], 0)
        gap = stats.last_seen_gap(self.draws)
        self.assertEqual(gap[1], 0)
        self.assertEqual(gap[10], 1)
        self.assertEqual(gap[45], 3)

    def test_duplicates_and_pairs(self):
        self.assertEqual(stats.duplicate_winning_combos(self.draws), {(1, 2, 3, 4, 5, 6): [1, 3]})
        self.assertEqual(stats.pair_frequency(self.draws, top=1)[0], ((1, 2), 3))

    def test_find_combo(self):
        res = stats.find_combo(self.draws, [1, 2, 10, 20, 30, 3])
        self.assertEqual(res["5+bonus"], [2])
        self.assertEqual(res[3], [1, 3])

    def test_repeat_check(self):
        rc = stats.repeat_check(self.draws)
        self.assertEqual(rc["unique_combos"], 2)
        self.assertAlmostEqual(rc["p_next_repeat"], 2 / 8_145_060)
        self.assertTrue(rc["exclude"])  # 중복은 있지만 확률이 매우 낮음
        self.assertFalse(stats.repeat_check(self.draws, threshold=0)["exclude"])

    def test_shapes(self):
        self.assertEqual(stats.longest_run([1, 2, 3, 10, 12, 13]), 3)
        self.assertEqual(stats.odd_count([1, 2, 3, 4, 5, 6]), 3)
        self.assertEqual(stats.decade_spread([1, 2, 10, 20, 30, 40]), 5)


class GeneratorTest(unittest.TestCase):
    def setUp(self):
        self.draws = fake_draws()

    def test_all_strategies_respect_filters(self):
        gen = Generator(self.draws, seed=42)
        past = {tuple(d["numbers"]) for d in self.draws}
        for strategy in ("mix", "hot", "cold", "pair", "random"):
            tickets = gen.generate(count=10, strategy=strategy)
            self.assertEqual(len(tickets), 10)
            for t in tickets:
                self.assertEqual(len(set(t.numbers)), 6)
                self.assertNotIn(tuple(t.numbers), past)
                self.assertIsNone(gen.reject_reason(t.numbers))

    def test_mix_uses_hot_and_cold(self):
        gen = Generator(self.draws, seed=1)
        for t in gen.generate(count=20, strategy="mix", n_hot=3, n_cold=2):
            self.assertGreaterEqual(len(t.hot), 3)
            self.assertGreaterEqual(len(t.cold), 2)

    def test_include_exclude(self):
        gen = Generator(self.draws, seed=3)
        for t in gen.generate(count=10, include=[7, 33], exclude=[1, 2, 3]):
            self.assertIn(7, t.numbers)
            self.assertIn(33, t.numbers)
            self.assertFalse({1, 2, 3} & set(t.numbers))

    def test_rejects_past_winner(self):
        gen = Generator(self.draws)
        self.assertIsNotNone(gen.reject_reason(self.draws[0]["numbers"]))

    def test_no_repeat_excludes_every_past_winner(self):
        gen = Generator(self.draws)
        self.assertFalse(gen.repeat["duplicates"])
        self.assertTrue(gen.exclude_past)
        for d in self.draws:
            self.assertEqual(gen.reject_reason(d["numbers"]), "이전 1등 조합과 같음")

    def test_repeat_with_high_probability_keeps_past(self):
        # 같은 조합이 두 번 나왔고, 확률 기준을 0으로 두면 제외하지 않는다
        draws = self.draws + [dict(self.draws[0], round=301)]
        gen = Generator(draws, filters=Filters(repeat_threshold=0))
        self.assertTrue(gen.repeat["duplicates"])
        self.assertFalse(gen.exclude_past)
        # 기본 기준(1%)에서는 중복이 있어도 확률이 매우 낮아 제외한다
        self.assertTrue(Generator(draws).exclude_past)

    def test_past_policy_override(self):
        self.assertFalse(Generator(self.draws, filters=Filters(past_policy="allow")).exclude_past)

    def test_bad_input(self):
        gen = Generator(self.draws)
        with self.assertRaises(ValueError):
            gen.generate(include=[1], exclude=[1])
        with self.assertRaises(ValueError):
            gen.generate(include=[46])


if __name__ == "__main__":
    unittest.main()
