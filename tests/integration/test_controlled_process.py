"""Real process transport checks with synthetic hosts, never model inference."""
import json
import os
from pathlib import Path
import selectors
import subprocess
import sys
import time

import pytest

from patristic_ethics.controlled import CONTROLLED_CONFIG

ROOT = Path(__file__).resolve().parents[2]
MARKER = "UNREVIEWED_CANDIDATE_MARKER"

HOST = '''#!{python}
import json, os, pathlib, sys, time
root = pathlib.Path(os.environ["PROBE_DIR"])
if sys.argv[1:3] == ["debug", "config"]:
    print(os.environ["PROBE_CONFIG"])
    sys.exit(0)
(root / "launched").touch()
mode = os.environ["PROBE_MODE"]
marker = "UNREVIEWED_CANDIDATE_MARKER"
if mode == "invalid":
    print(marker, flush=True)
elif mode == "error":
    print(marker, file=sys.stderr, flush=True)
else:
    if pathlib.Path(sys.argv[0]).name == "claude":
        print(json.dumps(dict(type="result", subtype="success", is_error=False, result=marker)), flush=True)
    else:
        print(json.dumps(dict(type="text", sessionID="test-session", part=dict(type="text", text=marker))), flush=True)
(root / "emitted").touch()
deadline = time.monotonic() + 10
while not (root / "release").exists():
    if time.monotonic() > deadline:
        sys.exit(9)
    time.sleep(0.01)
sys.exit(3 if mode == "error" else 0)
'''

# Exercise actual CLI/runner/display code, replacing only semantic assessment.
HARNESS = '''
import sys
from patristic_ethics import controlled, claude_controlled
from patristic_ethics.assess import AssessResult
from patristic_ethics.guidance import GuidanceResult
module = controlled if sys.argv[1] == "opencode" else claude_controlled
original = module.ControlledClient
def assessor(envelope):
    if envelope.stage == "output":
        return AssessResult(action="refuse", guidance=GuidanceResult(text="PEA reviewed refusal"))
    return AssessResult(action="proceed")
def client(**kwargs):
    return original(assessor=assessor, **kwargs)
module.ControlledClient = client
args = ["--prompt", "benign input", "--backend", "fake"]
if sys.argv[1] == "opencode":
    args += ["--model", "test-model"]
sys.exit(module.main(args))
'''


@pytest.mark.parametrize("host", ["opencode", "claude"])
@pytest.mark.parametrize("mode", ["valid", "invalid", "error"])
def test_candidate_never_reaches_display_before_review_or_on_failure(tmp_path, host, mode):
    executable = tmp_path / host
    executable.write_text(HOST.format(python=sys.executable))
    executable.chmod(0o700)
    env = {**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
           "PROBE_DIR": str(tmp_path), "PROBE_MODE": mode,
           "PROBE_CONFIG": json.dumps(CONTROLLED_CONFIG)}
    proc = subprocess.Popen([sys.executable, "-c", HARNESS, host], cwd=ROOT, env=env,
                            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        deadline = time.monotonic() + 10
        while not (tmp_path / "emitted").exists():
            assert proc.poll() is None, "client exited before test host emitted its candidate"
            assert time.monotonic() < deadline, "test host did not emit"
            time.sleep(0.01)
        # Host has flushed candidate/error text but remains alive: neither stream may expose it.
        with selectors.DefaultSelector() as selector:
            selector.register(proc.stdout, selectors.EVENT_READ)
            selector.register(proc.stderr, selectors.EVENT_READ)
            assert not selector.select(timeout=0.1), "client displayed content while host was running"
        (tmp_path / "release").touch()
        stdout, stderr = proc.communicate(timeout=10)
        assert proc.returncode == 0, stderr
        assert MARKER.encode() not in stdout + stderr
        if mode == "valid":
            assert stdout.decode().strip() == "PEA reviewed refusal"
            assert json.loads(stderr)["action"] == "refuse"
        else:
            assert b"response was withheld" in stdout
            assert json.loads(stderr)["action"] == "withhold"
    finally:
        if proc.poll() is None:
            proc.kill()
            proc.communicate()


def test_unsafe_resolved_profile_prevents_host_process_launch(tmp_path):
    executable = tmp_path / "opencode"
    executable.write_text(HOST.format(python=sys.executable))
    executable.chmod(0o700)
    config = json.loads(json.dumps(CONTROLLED_CONFIG))
    config["permission"]["bash"] = "allow"
    env = {**os.environ, "PATH": str(tmp_path) + os.pathsep + os.environ["PATH"],
           "PROBE_DIR": str(tmp_path), "PROBE_MODE": "valid", "PROBE_CONFIG": json.dumps(config)}
    result = subprocess.run([sys.executable, "-c", HARNESS, "opencode"], cwd=ROOT, env=env,
                            capture_output=True, timeout=10)
    assert result.returncode == 0
    assert not (tmp_path / "launched").exists()
    assert b"response was withheld" in result.stdout
    assert json.loads(result.stderr)["failure"] == "OpenCode resolved permissions are not deny-all"
