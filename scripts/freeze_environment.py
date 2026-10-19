"""Freeze the installed dependency closure, excluding unrelated host packages."""
from importlib import metadata
from pathlib import Path
import json
import platform
import sys
import tomllib
from packaging.requirements import Requirement
from packaging.utils import canonicalize_name

project = tomllib.loads(Path("pyproject.toml").read_text())["project"]
pending = [Requirement(r).name for r in project["dependencies"]]
for requirements in project["optional-dependencies"].values():
    pending.extend(Requirement(r).name for r in requirements)
versions = {}
while pending:
    name = canonicalize_name(pending.pop())
    if name in versions:
        continue
    dist = metadata.distribution(name)
    versions[name] = dist.version
    for line in dist.requires or []:
        requirement = Requirement(line)
        if requirement.marker is None or requirement.marker.evaluate({"extra": ""}):
            pending.append(requirement.name)
Path("requirements.lock.txt").write_text("# Installed project dependency closure; Python 3.12 reference run.\n" +
                                         "\n".join(f"{k}=={v}" for k, v in sorted(versions.items())) + "\n")
Path("outputs/environment.json").write_text(json.dumps({"python": sys.version,
    "platform": platform.platform(), "packages": dict(sorted(versions.items()))}, indent=2) + "\n")

