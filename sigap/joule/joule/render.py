"""Fill the capability's two placeholders and write a deployable copy to build/.

The YAML in sigap_capability/ is tracked by git, and the repo is public. The
two values that make it this team's (the BTP destination name and the team's
IAS group UUID) are not, so they live in joule.env (gitignored) and are put in
here, into build/ (gitignored too). Deploy from build/:

    python3 render.py
    cd build && joule deploy -c -n "sigap_assistant_<team>"

A template deployed by mistake fails safe: no destination resolves to
`__SIGAP_DESTINATION__`, and no user is in the group `__TEAM_IAS_GROUP_ID__`,
so every scenario stays invisible.
"""
from __future__ import annotations

import os
import pathlib
import re
import shutil
import sys

HERE = pathlib.Path(__file__).resolve().parent
KEYS = ("SIGAP_DESTINATION", "TEAM_IAS_GROUP_ID")
UUID = re.compile(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$")


def values() -> dict:
    found = {}
    env_file = HERE / "joule.env"
    if env_file.exists():
        for line in env_file.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                found[k.strip()] = v.split(" #", 1)[0].strip().strip("\"'")
    for k in KEYS:                       # the environment wins over the file
        if os.environ.get(k):
            found[k] = os.environ[k]
    return found


def main() -> int:
    v = values()
    missing = [k for k in KEYS if not v.get(k)]
    if missing:
        print(f"set {', '.join(missing)} in {HERE / 'joule.env'} (see joule.env.example)")
        return 1
    if not UUID.match(v["TEAM_IAS_GROUP_ID"]):
        print("TEAM_IAS_GROUP_ID must be the group's UUID, not its display name")
        return 1
    if not re.match(r"^[A-Za-z0-9_\-]+$", v["SIGAP_DESTINATION"]):
        print("SIGAP_DESTINATION must be a BTP destination name: letters, digits, _ and -")
        return 1

    build = HERE / "build"
    if build.exists():
        shutil.rmtree(build)
    build.mkdir()
    shutil.copy(HERE / "da.sapdas.yaml", build / "da.sapdas.yaml")
    shutil.copytree(HERE / "sigap_capability", build / "sigap_capability")
    for f in build.rglob("*.yaml"):
        t = f.read_text()
        for k in KEYS:
            t = t.replace(f"__{k}__", v[k])
        f.write_text(t)
    left = [str(f.relative_to(build)) for f in build.rglob("*.yaml") if "__" in f.read_text()]
    if left:
        print(f"placeholders left in: {', '.join(left)}")
        return 1
    print(f"wrote {build}; deploy from there with: joule deploy -c -n \"sigap_assistant_<team>\"")
    return 0


if __name__ == "__main__":
    sys.exit(main())
