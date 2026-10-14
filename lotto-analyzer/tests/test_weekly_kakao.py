import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from lotto_analyzer import kakao, web, weekly
from test_lotto import fake_draws


class WeeklyTest(unittest.TestCase):
    def setUp(self):
        self.draws = fake_draws(300)

    def test_ten_distinct_spread_tickets(self):
        p = weekly.make_weekly_picks(self.draws)
        self.assertEqual(p["round"], 301)
        self.assertEqual(len(p["tickets"]), 10)
        past = {tuple(d["numbers"]) for d in self.draws}
        for i, a in enumerate(p["tickets"]):
            self.assertNotIn(tuple(a), past)
            for b in p["tickets"][i + 1:]:
                self.assertLessEqual(len(set(a) & set(b)), 3)
        self.assertLess(p["remaining"], 8_145_060)

    def test_same_round_same_picks(self):
        # 금요일 카톡과 리포트가 같은 조합을 보여 주도록 회차 기준으로 고정
        self.assertEqual(weekly.make_weekly_picks(self.draws)["tickets"],
                         weekly.make_weekly_picks(self.draws)["tickets"])

    def test_saturday_picks_are_reused_on_friday(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "picks.json"
            sat = weekly.get_weekly_picks(self.draws, path)      # 토요일: 새로 만들어 고정
            self.assertFalse(sat["saved"])
            # 고정된 번호를 바꿔 놓고 금요일에 불러오면, 다시 만들지 않고 저장된 번호를 써야 한다
            data = json.loads(path.read_text(encoding="utf-8"))
            data["301"]["tickets"][0] = [1, 2, 3, 4, 5, 6]
            path.write_text(json.dumps(data), encoding="utf-8")
            fri = weekly.get_weekly_picks(self.draws, path)
            self.assertTrue(fri["saved"])
            self.assertEqual(fri["tickets"][0], [1, 2, 3, 4, 5, 6])
            self.assertEqual(fri["remaining"], sat["remaining"])
            # 웹페이지도 같은 번호
            self.assertEqual(web.build_web_data(self.draws, {}, picks_path=path)["this_week"]["tickets"][0],
                             [1, 2, 3, 4, 5, 6])
            # --new 로 다시 만들면 원래 번호로
            self.assertEqual(weekly.get_weekly_picks(self.draws, path, regenerate=True)["tickets"], sat["tickets"])

    def test_message_fits_kakao(self):
        msg = weekly.format_message(weekly.make_weekly_picks(self.draws))
        chunks = kakao.split_text(msg)
        self.assertTrue(all(len(c) <= kakao.TEXT_LIMIT for c in chunks))
        self.assertEqual("\n".join(chunks), msg)  # 나눠도 내용이 빠지지 않음
        body = weekly.format_message_parts(weekly.make_weekly_picks(self.draws))[1]
        self.assertLessEqual(len(body), kakao.TEXT_LIMIT)  # 10게임이 한 건에 들어감
        for label in "ABCDEFGHIJ":
            self.assertIn(f"\n{label} ", "\n" + "\n".join(chunks))

    def test_save_and_check_results(self):
        draw = {"round": 5, "numbers": [1, 2, 3, 4, 5, 6], "bonus": 7}
        self.assertEqual(weekly.rank([1, 2, 3, 4, 5, 6], draw), 1)
        self.assertEqual(weekly.rank([1, 2, 3, 4, 5, 7], draw), 2)
        self.assertEqual(weekly.rank([1, 2, 3, 4, 5, 9], draw), 3)
        self.assertEqual(weekly.rank([1, 2, 3, 40, 41, 42], draw), 5)
        self.assertIsNone(weekly.rank([1, 2, 30, 40, 41, 42], draw))
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "picks.json"
            weekly.save_picks({"round": 5, "draw_date": "2020-01-01", "based_on": 4,
                               "tickets": [[1, 2, 3, 4, 5, 7]], "excluded_past": 4,
                               "removed": [], "remaining": 1, "repeat_lines": []}, path)
            res = weekly.check_results([draw], weekly.load_picks(path))
            self.assertEqual(res[0][2], [([1, 2, 3, 4, 5, 7], 2)])


class WebDataTest(unittest.TestCase):
    def test_web_json_matches_weekly_picks(self):
        draws = fake_draws(300)
        picks = weekly.make_weekly_picks(draws)
        history = {"300": {"draw_date": "2020-01-01", "based_on": 299, "tickets": [draws[-1]["numbers"]]}}
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "web.json"
            web.write_web_data(draws, history, path)
            data = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(data["this_week"]["tickets"], picks["tickets"])  # 카톡과 같은 번호
        self.assertEqual(len(data["frequency"]), 45)
        self.assertEqual(data["results"][0]["tickets"][0]["rank"], 1)


class FakeKakao:
    def __init__(self, new_refresh=None):
        self.calls = []
        self.new_refresh = new_refresh

    def __call__(self, url, data, headers=None):
        self.calls.append((url, data, headers))
        if url == kakao.TOKEN_URL:
            res = {"access_token": "AT", "expires_in": 21599}
            if self.new_refresh:
                res["refresh_token"] = self.new_refresh
            return res
        if url == kakao.MEMO_URL:
            assert headers["Authorization"] == "Bearer AT"
            assert len(json.loads(data["template_object"])["text"]) <= 200
            return {"result_code": 0}
        raise AssertionError(url)


@mock.patch.dict(os.environ, {"KAKAO_REST_API_KEY": "KEY", "KAKAO_REFRESH_TOKEN": "RT",
                              "GITHUB_ACTIONS": "true"}, clear=True)
class KakaoTest(unittest.TestCase):
    def test_refresh_then_send_split(self):
        fake = FakeKakao()
        client = kakao.KakaoClient(token_file="/nonexistent/x.json", post=fake)
        parts = weekly.format_message_parts(weekly.make_weekly_picks(fake_draws(300)))
        n = sum(client.send_long_text(p) for p in parts)
        self.assertEqual(n, 2)  # 요약 1건 + 10게임 1건
        self.assertEqual(fake.calls[0][1]["grant_type"], "refresh_token")
        self.assertEqual(sum(1 for c in fake.calls if c[0] == kakao.TOKEN_URL), 1)  # 토큰은 한 번만 갱신
        self.assertIsNone(client.new_refresh_token)

    def test_new_refresh_token_is_reported(self):
        client = kakao.KakaoClient(token_file="/nonexistent/x.json", post=FakeKakao(new_refresh="RT2"))
        client.send_text("hi")
        self.assertEqual(client.new_refresh_token, "RT2")

    def test_login_parses_redirect_url(self):
        fake = FakeKakao(new_refresh="RT0")
        client = kakao.KakaoClient(token_file="/nonexistent/x.json", post=fake)
        client.login("https://localhost/?code=ABC123")
        self.assertEqual(fake.calls[0][1]["code"], "ABC123")
        self.assertIn("scope=talk_message", client.authorize_url())


if __name__ == "__main__":
    unittest.main()
