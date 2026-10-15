import os, stat, subprocess, sys, tempfile, unittest

SCRIPT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "scripts", "oci_public_url.sh")
FAKE_OCI = """#!/usr/bin/env bash
echo "$*" >> "$FAKE_LOG"
case "$*" in
  "os ns get"*) echo myns;;
  "os object put"*) ;;
  "os preauth-request create"*) echo "/p/abc/n/myns/b/navaan/o/tmp/x.mp4";;
  "iam region-subscription list"*) echo "Error: Missing option(s) --tenancy-id." >&2; exit 2;;
  *) ;;
esac
"""
FAKE_CURL = "#!/usr/bin/env bash\necho us-chicago-1\n"


class Url(unittest.TestCase):
    def run_script(self, curl_ok=True, env_region=None):
        d = tempfile.mkdtemp(); log = os.path.join(d, "log")
        for name, body in (("oci", FAKE_OCI), ("curl", FAKE_CURL if curl_ok else "#!/usr/bin/env bash\nexit 7\n")):
            p = os.path.join(d, name); open(p, "w").write(body); os.chmod(p, 0o755)
        f = os.path.join(d, "x.mp4"); open(f, "wb").write(b"x")
        env = dict(os.environ, PATH=d + os.pathsep + os.environ["PATH"], FAKE_LOG=log)
        env.pop("NAVAAN_OCI_REGION", None); env.pop("OCI_CLI_REGION", None)
        if env_region: env["NAVAAN_OCI_REGION"] = env_region
        r = subprocess.run(["bash", SCRIPT, f], capture_output=True, text=True, env=env)
        return r, open(log).read()

    def test_region_from_instance_metadata_without_iam(self):
        r, log = self.run_script()
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip(), "https://objectstorage.us-chicago-1.oraclecloud.com/p/abc/n/myns/b/navaan/o/tmp/x.mp4")
        self.assertNotIn("region-subscription", log)

    def test_env_region_wins(self):
        r, log = self.run_script(env_region="eu-frankfurt-1")
        self.assertIn("objectstorage.eu-frankfurt-1.", r.stdout)

    def test_old_lookup_is_only_the_last_resort(self):
        r, log = self.run_script(curl_ok=False)
        self.assertIn("region-subscription", log)


if __name__ == "__main__":
    unittest.main()
