import random
import tempfile
import unittest
from pathlib import Path

from lotto_analyzer import fetch, stats
from lotto_analyzer.generator import Generator


def fake_draws(n=300, seed=1):
    rng = random.Random(seed)
    out = []
    for r in range(1, n + 1):
        nums = rng.sample(range(1, 46), 7)
        out.append({"round": r, "date": "2020-01-01", "numbers": sorted(nums[:6]), "bonus": nums[6]})
    return out


def fake_api(latest):
    """latest 회차까지만 결과가 있는 가짜 API."""
    def get_json(url):
        r = int(url.rsplit("=", 1)[1])
        if r > latest:
            return {"returnValue": "fail"}
        nums = random.Random(r).sample(range(1, 46), 7)
        raw = {"returnValue": "success", "drwNo": r, "drwNoDate": "2020-01-01", "bnusNo": nums[6]}
        raw.update({f"drwtNo{i + 1}": nums[i] for i in range(6)})
        return raw
    return get_json


class FetchTest(unittest.TestCase):
    def test_parse_real_round1(self):
        raw = {"returnValue": "success", "drwNo": 1, "drwNoDate": "2002-12-07", "bnusNo": 16,
               "drwtNo1": 10, "drwtNo2": 23, "drwtNo3": 29, "drwtNo4": 33, "drwtNo5": 37, "drwtNo6": 40}
        d = fetch.parse_draw(raw)
        self.assertEqual(d["numbers"], [10, 23, 29, 33, 37, 40])
        self.assertEqual(d["bonus"], 16)
        self.assertIsNone(fetch.parse_draw({"returnValue": "fail"}))

    def test_incremental_update(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "draws.json"
            added = fetch.update(path, get_json=fake_api(5), delay=0, log=lambda *_: None)
            self.assertEqual([d["round"] for d in added], [1, 2, 3, 4, 5])
            # 다음 주: 6회만 새로 받아야 한다
            added = fetch.update(path, get_json=fake_api(6), delay=0, log=lambda *_: None)
            self.assertEqual([d["round"] for d in added], [6])
            self.assertEqual(len(fetch.load_draws(path)), 6)
            # 아직 추첨 전이면 아무것도 추가 안 됨
            self.assertEqual(fetch.update(path, get_json=fake_api(6), delay=0), [])


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

    def test_bad_input(self):
        gen = Generator(self.draws)
        with self.assertRaises(ValueError):
            gen.generate(include=[1], exclude=[1])
        with self.assertRaises(ValueError):
            gen.generate(include=[46])


if __name__ == "__main__":
    unittest.main()
