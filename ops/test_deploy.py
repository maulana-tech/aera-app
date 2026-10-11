"""Offline deployment check: service activation and rollback, without touching EC2."""
import io
import os
from pathlib import Path
import subprocess
import tarfile
import tempfile
import unittest


class DeploymentTest(unittest.TestCase):
    def exercise(self, fail_health=False, first_release=False):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            root = base / "project"
            units = base / "systemd"
            env = root / "sigap/agent/.env"
            env.parent.mkdir(parents=True)
            env.write_text("SIGAP_DB=/var/lib/sigap/sigap.db\n")
            current = root / "current"
            if not first_release:
                old = root / "releases/old"
                old.mkdir(parents=True)
                current.symlink_to(old)
            overrides = []
            for service in ("agent", "web"):
                override = units / f"sigap-{service}.service.d/10-release.conf"
                override.parent.mkdir(parents=True)
                if not first_release:
                    override.write_text(f"old {service}\n")
                overrides.append(override)
            archive = base / "release.tar.gz"
            with tarfile.open(archive, "w:gz") as bundle:
                for name in ("standalone/server.js", "sigap/agent/api.py",
                             "sigap/agent/requirements.txt"):
                    data = b"# offline fixture\n"
                    member = tarfile.TarInfo(name)
                    member.size = len(data)
                    bundle.addfile(member, io.BytesIO(data))
            script = Path(__file__).with_name("deploy.sh").read_text()
            script = script.replace("[[ $EUID == 0 ]]", "[[ 1 == 1 ]]")
            script = script.replace("/opt/sigap-project", str(root))
            script = script.replace("/etc/systemd/system", str(units))
            script = script.replace("/var/lock/sigap-deploy.lock", str(base / "lock"))
            local_script = base / "deploy.sh"
            local_script.write_text(script)
            binaries = base / "bin"
            binaries.mkdir()
            stubs = {
                "node": "echo 22",
                "runuser": "exit 0",
                "chown": "exit 0",
                "systemctl": 'echo "$*" >> "$TEST_SYSTEMCTL_LOG"',
                "curl": "exit 1" if fail_health else "exit 0",
                "sleep": "exit 0",
            }
            for name, body in stubs.items():
                executable = binaries / name
                executable.write_text("#!/bin/sh\n" + body + "\n")
                executable.chmod(0o755)
            release_id = "a" * 40 + "-1-1"
            result = subprocess.run(
                ["bash", str(local_script), str(archive), release_id],
                env={**os.environ, "PATH": f"{binaries}:{os.environ['PATH']}",
                     "TEST_SYSTEMCTL_LOG": str(base / "systemctl.log")},
                capture_output=True, text=True,
            )
            if fail_health:
                self.assertNotEqual(result.returncode, 0, result.stdout)
                if first_release:
                    self.assertFalse(current.exists())
                    self.assertTrue(all(not path.exists() for path in overrides))
                else:
                    self.assertEqual(current.resolve(), old)
                    self.assertEqual(overrides[0].read_text(), "old agent\n")
                    self.assertEqual(overrides[1].read_text(), "old web\n")
                self.assertEqual((base / "systemctl.log").read_text().count("restart"), 2)
            else:
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(current.resolve(), root / "releases" / release_id)
                self.assertIn("current/standalone", overrides[1].read_text())
            self.assertEqual(env.read_text(), "SIGAP_DB=/var/lib/sigap/sigap.db\n")

    def test_success(self):
        self.exercise()

    def test_rollback(self):
        self.exercise(fail_health=True)

    def test_first_deployment_rollback(self):
        self.exercise(fail_health=True, first_release=True)


if __name__ == "__main__":
    unittest.main()
