"""A new channel's login files (youtube_token_<type>.json, instagram_<type>.env) go to Vault like the first two accounts' do, so the
worker gets them and a restart keeps them. Before, a fixed list left The Aha-lorithm's sign-in in the web container only."""
import importlib.util, os, sys, tempfile, unittest
from unittest import mock

HERE = os.path.dirname(os.path.abspath(__file__))
spec = importlib.util.spec_from_file_location("vault_sync", os.path.join(HERE, "..", "..", "..", "deploy", "vault_sync.py"))
V = importlib.util.module_from_spec(spec); spec.loader.exec_module(V)


class Known(unittest.TestCase):
    def test_account_files_of_any_type_are_credentials_and_nothing_else_is(self):
        for n in ("youtube_token_aha.json", "youtube_token_aha_analytics.json", "instagram_aha.env", "youtube_token.json", "claude.env"): self.assertTrue(V.is_known(n), n)
        for n in ("auth_setup_code", "secrets.status", "youtube_token_../x.json", "notes.txt", "youtube_token_.json"): self.assertFalse(V.is_known(n), n)


class SettingsFiles(unittest.TestCase):
    """NAV-140: a settings file in the config folder (a tmpfs on prod, refilled from Vault) that Vault does not list is lost at every restart; the standing licence statement was."""
    def test_every_settings_file_the_studio_writes_there_is_kept_in_vault(self):
        sys.path.insert(0, os.path.join(HERE, "..", "scripts"))
        import licence_cfg, gate_cfg
        import media_cfg
        for name in (licence_cfg.FILE, gate_cfg.FILE, "media.json", *[k[0] for k in media_cfg.KEYS.values()]): self.assertTrue(V.is_known(name), f"{name} would be lost at the next restart")   # every key file Settings can write (OpenAI, ElevenLabs, dev.to, LinkedIn)

    def test_the_licence_statement_is_pushed_and_comes_back_after_a_restart(self):
        vault = {}
        web, fresh = tempfile.TemporaryDirectory(), tempfile.TemporaryDirectory(); self.addCleanup(web.cleanup); self.addCleanup(fresh.cleanup)
        with open(os.path.join(web.name, "licence.json"), "w") as f: f.write('{"auto": true, "statement": "paid plan"}')
        with mock.patch.multiple(V, store=lambda n, d, m, t: vault.__setitem__(n, (d, m)), names=lambda t: list(vault), fetch=lambda n, t: vault.get(n)):
            with mock.patch.object(V, "DIR", web.name): V.cycle("t", {})
            self.assertIn("licence.json", vault)
            with mock.patch.object(V, "DIR", fresh.name): V.cycle("t", {})   # a new container: an empty config folder
        self.assertEqual(open(os.path.join(fresh.name, "licence.json")).read(), '{"auto": true, "statement": "paid plan"}')


class Cycle(unittest.TestCase):
    def test_a_new_channel_token_is_pushed_from_one_container_and_pulled_by_the_other(self):
        vault = {}
        def store(name, data, mode, token): vault[name] = (data, mode)
        def names(token): return list(vault)
        def fetch(name, token): return vault.get(name)
        web, worker = tempfile.TemporaryDirectory(), tempfile.TemporaryDirectory(); self.addCleanup(web.cleanup); self.addCleanup(worker.cleanup)
        with open(os.path.join(web.name, "youtube_token_aha.json"), "w") as f: f.write('{"refresh_token": "x"}')
        with open(os.path.join(web.name, "auth_setup_code"), "w") as f: f.write("123456")
        with mock.patch.multiple(V, store=store, names=names, fetch=fetch):
            with mock.patch.object(V, "DIR", web.name): V.cycle("t", {})
            self.assertIn("youtube_token_aha.json", vault); self.assertNotIn("auth_setup_code", vault)
            with mock.patch.object(V, "DIR", worker.name): V.cycle("t", {})
        self.assertEqual(open(os.path.join(worker.name, "youtube_token_aha.json")).read(), '{"refresh_token": "x"}')


if __name__ == "__main__":
    unittest.main()
