"""Tests for the portal's automatic analytics refresh. Run: python3 -W ignore -m unittest test_analytics_auto"""
import datetime, json, os, sys, tempfile, unittest
sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts"))
import analytics_auto as au

UTC = datetime.timezone.utc


class Auto(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.p = os.path.join(self.tmp.name, "analytics_auto.json")
        self._path, self._now = au.path, au._now
        au.path = lambda: self.p
        self.calls = []
        self.fake = {"running": False, "rc": 0, "tail": ""}
        api = au.api
        self._api = (api.start_collect, api.analyze_now, api.start_ask, api._state)
        api.start_collect = lambda acc, pl: self.calls.append(("collect", pl)) or True
        api.analyze_now = lambda acc, db, pl: self.calls.append(("analyze", pl)) or []
        api.start_ask = lambda acc, pl: self.calls.append(("ask", pl)) or True
        api._state = lambda pl: (dict(self.fake), dict(self.fake))
        au.STATE.update(running=False, step="")

    def tearDown(self):
        au.path, au._now = self._path, self._now
        au.api.start_collect, au.api.analyze_now, au.api.start_ask, au.api._state = self._api
        self.tmp.cleanup()

    def at(self, *a):
        t = datetime.datetime(*a, tzinfo=UTC); au._now = lambda: t; return t

    def test_off_by_default_never_due(self):
        s = au.settings()
        self.assertFalse(s["enabled"]); self.assertIsNone(s["next_run"])
        self.assertFalse(au.tick()); self.assertEqual(self.calls, [])

    def test_validation(self):
        with self.assertRaises(ValueError): au.set_settings(True, 5, 9, False)
        with self.assertRaises(ValueError): au.set_settings(True, 7, 24, False)

    def test_first_run_is_next_time_the_hour_comes_round(self):
        self.at(2026, 10, 13, 12)
        s = au.set_settings(True, 7, 9, False)
        local = datetime.datetime.fromisoformat(s["next_run"].replace("Z", "+00:00")).astimezone()
        self.assertEqual(local.hour, 9)
        nr = datetime.datetime.fromisoformat(s["next_run"].replace("Z", "+00:00"))
        self.assertGreater(nr, au._now()); self.assertLessEqual(nr - au._now(), datetime.timedelta(days=1, hours=1))

    def test_after_a_run_next_is_every_days_later(self):
        self.at(2026, 10, 13, 12)
        au.set_settings(True, 7, 9, False)
        c = au.load(); c["last_run"] = "2026-10-13T12:00:00Z"; au._save(c)
        nr = datetime.datetime.fromisoformat(au.settings()["next_run"].replace("Z", "+00:00")).astimezone()
        self.assertEqual(nr.hour, 9)
        last = datetime.datetime(2026, 10, 13, 12, tzinfo=UTC).astimezone().date()
        self.assertEqual(nr.date(), last + datetime.timedelta(days=7))

    def test_tick_runs_when_due_then_not_again(self):
        self.at(2026, 10, 13, 12)
        au.set_settings(True, 1, 9, False)
        self.assertFalse(au.tick())                       # not due yet
        au._now = lambda: datetime.datetime(2026, 10, 15, tzinfo=UTC)   # well past due
        self.assertTrue(au.tick())
        for _ in range(100):
            if not au.STATE["running"] and self.calls: break
            import time; time.sleep(0.05)
        self.assertFalse(au.tick())                       # last_run now set, next one is a day later
        self.assertEqual(au.load()["last_note"], "ok")

    def test_run_once_order_without_ask(self):
        au.run_once()
        self.assertEqual(self.calls, [("collect", "instagram"), ("collect", "youtube"), ("analyze", "instagram"), ("analyze", "youtube")])
        self.assertIsNotNone(au.load()["last_run"])

    def test_run_once_with_ask_and_failed_collect_noted(self):
        self.fake.update(rc=1, tail="boom\nYouTube API error 403 accessNotConfigured")
        note = au.run_once(ask=True)
        self.assertEqual([c for c in self.calls if c[0] == "ask"], [("ask", "instagram"), ("ask", "youtube")])
        self.assertIn("accessNotConfigured", note)
        self.assertEqual(au.load()["last_note"], note)
        self.assertFalse(au.STATE["running"])

    def test_run_once_refuses_while_running(self):
        au.STATE["running"] = True
        self.assertEqual(au.run_once(), "already running"); self.assertEqual(self.calls, [])
        self.assertFalse(au.run_async())


if __name__ == "__main__":
    unittest.main()
