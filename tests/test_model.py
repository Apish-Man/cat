import json
import tempfile
import unittest
from datetime import date, datetime
from pathlib import Path
from catmate.catalog import gifts_today
from catmate.model import Companion, Store

class ModelTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.store = Store(self.tmp.name)
        self.m = Companion(self.store)

    def advance(self, seconds, **kwargs):
        events = []
        for _ in range(seconds):
            events.extend(self.m.tick(1, **kwargs))
        return events

    def test_work_rewards_only_complete_minutes_and_keeps_fraction(self):
        self.m.working = True
        self.advance(59)
        self.assertEqual(self.m.d["coins"], 200)
        self.advance(1)
        self.assertEqual(self.m.d["coins"], 202)
        self.assertAlmostEqual(self.m.record()["income"], 35 / 60)
        self.m.working = False
        self.advance(120)
        self.assertEqual(self.m.d["coins"], 202)

    def test_idle_and_suspend_dont_mint_coins(self):
        self.m.working = True
        self.advance(60, idle=True)
        self.m.tick(3600)
        self.assertEqual(self.m.d["coins"], 200)
        self.assertEqual(self.m.record()["seconds"], 0)

    def test_midnight_splits_daily_income(self):
        self.m.working = True
        self.m.tick(2, now=datetime(2026, 11, 18, 0, 0, 1))
        self.assertEqual(self.m.record(date(2026, 11, 17))["seconds"], 1)
        self.assertEqual(self.m.record(date(2026, 11, 18))["seconds"], 1)

    def test_changing_salary_doesnt_revalue_history(self):
        self.m.working = True
        self.advance(60)
        self.m.d["settings"]["salary"] = 70
        self.advance(60)
        self.assertAlmostEqual(self.m.record()["income"], (35 + 70) / 60)

    def test_purchase_unique_and_insufficient_funds_are_atomic(self):
        self.assertTrue(self.m.buy("wand")[0])
        self.assertEqual(self.m.d["coins"], 135)
        self.assertFalse(self.m.buy("wand")[0])
        self.assertEqual(self.m.d["coins"], 135)
        self.assertFalse(self.m.buy("christmas")[0])
        self.assertNotIn("christmas", self.m.d["inventory"])

    def test_food_consumes_inventory_and_cannot_overfeed(self):
        self.m.d["hunger"] = 50
        self.assertTrue(self.m.feed("fish")[0])
        self.assertEqual(self.m.d["inventory"]["fish"], 2)
        self.assertEqual(self.m.d["hunger"], 65)
        self.m.d["hunger"] = 99
        self.assertFalse(self.m.feed("fish")[0])
        self.assertEqual(self.m.d["inventory"]["fish"], 2)

    def test_focus_pause_and_one_time_reward(self):
        self.m.start_focus(1)
        self.m.focus_paused = True
        self.advance(30)
        self.assertEqual(self.m.focus_remaining, 60)
        self.m.focus_paused = False
        events = self.advance(60)
        self.assertEqual(sum(e[0] == "focus" for e in events), 1)
        self.assertEqual(self.m.d["coins"], 250)
        self.advance(60)
        self.assertEqual(self.m.d["coins"], 250)

    def test_pet_cooldown_avoids_bond_spam(self):
        self.m.pet()
        self.m.pet()
        self.assertEqual(self.m.d["bond"], 1)
        self.advance(8)
        self.m.pet()
        self.assertEqual(self.m.d["bond"], 2)

    def test_reminders_repeat_at_selected_interval(self):
        self.m.d["settings"]["water_minutes"] = 1
        self.assertEqual(sum(e[0] == "water" for e in self.advance(120)), 2)

    def test_gifts_cannot_be_claimed_twice(self):
        day = date(2026, 11, 17)
        self.assertTrue(self.m.claim_gift("birthday", day))
        self.assertFalse(self.m.claim_gift("birthday", day))
        self.assertFalse(self.m.claim_gift("christmas", day))
        self.assertIn("newyear", gifts_today(date(2027, 2, 6), "11-17"))

    def test_save_roundtrip_preserves_clothes_but_stops_timer(self):
        self.m.buy("blue")
        self.m.equip("blue")
        self.m.working = True
        self.advance(45)
        self.store.save()
        loaded = Companion(Store(self.tmp.name))
        self.assertEqual(loaded.d["outfit"], "blue")
        self.assertEqual(loaded.d["coin_remainder"], 45)
        self.assertFalse(loaded.working)

    def test_corrupt_file_is_preserved(self):
        self.store.directory.mkdir(exist_ok=True)
        self.store.path.write_text("not json", encoding="utf-8")
        loaded = Store(self.tmp.name)
        self.assertTrue(loaded.recovered)
        self.assertEqual(len(list(Path(self.tmp.name).glob("save.corrupt-*.json"))), 1)

    def test_bad_field_types_are_sanitized(self):
        self.store.path.write_text(json.dumps({"coins": -20, "hunger": "bad", "inventory": {"wand": -2},
                                               "settings": {"size": 20000, "birthday": "13-99"}}), encoding="utf-8")
        loaded = Store(self.tmp.name)
        self.assertEqual(loaded.data["coins"], 0)
        self.assertEqual(loaded.data["hunger"], 78)
        self.assertEqual(loaded.data["settings"]["size"], 420)
        self.assertEqual(loaded.data["settings"]["birthday"], "11-17")

if __name__ == "__main__":
    unittest.main()
