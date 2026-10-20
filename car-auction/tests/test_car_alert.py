import json
import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import car_alert  # noqa: E402

CRIT = json.loads((car_alert.DATA / "criteria.json").read_text(encoding="utf-8"))


def car(**kw):
    base = {"id": "x", "model": "K3", "year": 2020, "mileage": 50000, "color": "흰색",
            "startPrice": 950, "frame": False, "myDamage": 0, "status": "예정", "auctionDate": ""}
    base.update(kw)
    return base


class EvaluateTest(unittest.TestCase):
    def test_white_k3_matches_first(self):
        ev = car_alert.evaluate(car(color="스노우 화이트 펄"), CRIT)
        self.assertEqual((ev["level"], ev["colorRank"]), ("match", 1))

    def test_black_avante_is_second(self):
        ev = car_alert.evaluate(car(model="더 뉴 아반떼", color="오로라 블랙"), CRIT)
        self.assertEqual((ev["level"], ev["model"], ev["colorRank"]), ("match", "아반떼", 2))

    def test_blue_is_near_and_cap_reduced(self):
        ev = car_alert.evaluate(car(year=2019, color="블루", frame=True, myDamage=1), CRIT)
        self.assertEqual(ev["level"], "near")
        self.assertEqual(ev["cap"], 1000 - 30 - 30)

    def test_out_of_range(self):
        for kw in ({"year": 2015}, {"mileage": 70001}, {"model": "쏘나타"}, {"mileage": None}):
            self.assertEqual(car_alert.evaluate(car(**kw), CRIT)["level"], "out", kw)

    def test_new_matches_skip_notified_and_closed(self):
        items = [car(id="a"), car(id="b"), car(id="c", status="낙찰"),
                 car(id="d", auctionDate="2026-10-01"), car(id="e", color="블랙")]
        found = car_alert.find_new_matches(items, CRIT, {"b": "2026-10-20"}, today=date(2026, 10, 20))
        self.assertEqual([i["id"] for i, _ in found], ["a", "e"])

    def test_message_fits_kakao(self):
        item = car(trim="프레스티지", currentPrice=990, auctionDate="2026-10-28", source="코오롱오토옥션")
        text = car_alert.format_message(item, car_alert.evaluate(item, CRIT))
        self.assertIn("권장 상한 1,080만원 → 입찰 고려", text)
        self.assertLessEqual(len(text), 200)


if __name__ == "__main__":
    unittest.main()
