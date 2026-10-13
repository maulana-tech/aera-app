"""Exercise SSH transport with stubs; never connect to a server."""
import os
from pathlib import Path
import subprocess
import tempfile
import unittest


class SshDeploymentTest(unittest.TestCase):
    def run_transport(self, fail_deploy=False, host="ec2.example.com", missing_key=False):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            binaries = base / "bin"
            binaries.mkdir()
            log = base / "calls"
            for name, body in {
                "ssh-keygen": "exit 0",
                "scp": 'echo "scp $*" >> "$TEST_LOG"',
                "ssh": '''echo "ssh $*" >> "$TEST_LOG"
case "$*" in
  *mktemp*) echo /tmp/sigap-upload.ABC123 ;;
  *"bash -s"*) cat >/dev/null; exit "$TEST_DEPLOY_EXIT" ;;
esac''',
            }.items():
                binary = binaries / name
                binary.write_text("#!/bin/sh\n" + body + "\n")
                binary.chmod(0o755)
            archive = base / "release.tar.gz"
            archive.write_bytes(b"fake artifact")
            env = {**os.environ, "PATH": f"{binaries}:{os.environ['PATH']}",
                   "TEST_LOG": str(log), "TEST_DEPLOY_EXIT": "7" if fail_deploy else "0",
                   "EC2_HOST": host, "EC2_SSH_KEY": "" if missing_key else "TEST_KEY",
                   "EC2_KNOWN_HOSTS": "sigap-ec2 ssh-ed25519 TEST_HOST_KEY",
                   "RELEASE_ID": "a" * 40 + "-1-1", "TMPDIR": str(base)}
            result = subprocess.run(
                ["bash", str(Path(__file__).with_name("deploy-ssh.sh")), str(archive)],
                env=env, capture_output=True, text=True,
            )
            calls = log.read_text() if log.exists() else ""
            self.assertNotIn("TEST_KEY", result.stdout + result.stderr + calls)
            self.assertFalse(list(base.glob("tmp*")), "temporary SSH credentials must be deleted")
            return result, calls

    def test_success_uses_pinned_host_key(self):
        result, calls = self.run_transport()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("StrictHostKeyChecking=yes", calls)
        self.assertIn("HostKeyAlias=sigap-ec2", calls)
        self.assertIn("sudo -n true", calls)
        self.assertIn("scp ", calls)
        self.assertIn("bash -s", calls)

    def test_remote_failure_is_preserved_and_upload_cleaned(self):
        result, calls = self.run_transport(fail_deploy=True)
        self.assertEqual(result.returncode, 7)
        self.assertIn("rm -rf -- '/tmp/sigap-upload.ABC123'", calls)

    def test_invalid_host_never_connects(self):
        result, calls = self.run_transport(host="host;echo bad")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, "")

    def test_missing_secret_never_connects(self):
        result, calls = self.run_transport(missing_key=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(calls, "")


if __name__ == "__main__":
    unittest.main()
