"""Verify operator file access and one-shot review in a disposable namespace.

Run as UID 0 inside a Linux user namespace with a second mapped UID/GID 1000.
The namespace's root represents the operator. This probe uses a disposable
database and credential and performs no external tool action.
"""

import json
import os
from pathlib import Path
import secrets
import subprocess
import sys
from tempfile import TemporaryDirectory

from patristic_ethics.runtime_store import RuntimeStore


def main():
    if os.geteuid() != 0 or Path("/proc/self/uid_map").read_text().split()[:2] == ["0", "0"]:
        sys.exit("Run this probe in a non-root-owned user namespace with two mapped IDs.")

    with TemporaryDirectory(prefix="pea-operator-probe-") as directory:
        root = Path(directory)
        root.chmod(0o755)
        private = root / "private"
        private.mkdir(mode=0o700)
        database = private / "runtime.db"
        database.touch(mode=0o600)
        token_file = private / "operator.token"
        token_file.touch(mode=0o600)
        token_file.write_text(secrets.token_urlsafe(32))

        action = {"tool": "record_fixture", "arguments": {"label": "benign"}}
        context = {"fixture": "operator-isolation"}
        policy = "probe-v1"
        store = RuntimeStore(database)
        review_id = store.open_review("isolated-probe", action, context, policy)
        store.conn.close()

        check_access = """
import os, sys
from pathlib import Path
assert os.geteuid() == os.getegid() == 1000
assert not os.getgroups()
assert "PEA_OPERATOR_TOKEN" not in os.environ
assert Path(sys.argv[1]).is_dir()
for path in sys.argv[2:]:
    assert not os.access(path, os.R_OK | os.W_OK)
    for mode in (os.O_RDONLY, os.O_RDWR):
        try:
            fd = os.open(path, mode)
        except PermissionError:
            continue
        os.close(fd)
        raise AssertionError("agent accessed a protected file")
"""
        agent_env = {k: v for k, v in os.environ.items() if k != "PEA_OPERATOR_TOKEN"}
        subprocess.run(["setpriv", "--reuid", "1000", "--regid", "1000", "--clear-groups",
                        "--no-new-privs", "/usr/bin/python3", "-I", "-c", check_access,
                        str(root), str(database), str(token_file)], env=agent_env, check=True)

        operator_env = {**agent_env, "PEA_OPERATOR_TOKEN": token_file.read_text()}
        result = subprocess.run(
            [sys.executable, "-m", "patristic_ethics.operator", "--db", str(database),
             "resolve", review_id, "approved", "--note", "benign isolated fixture"],
            env=operator_env, capture_output=True, text=True, check=True,
        )
        assert json.loads(result.stdout)["status"] == "approved"

        store = RuntimeStore(database)
        assert store.claim_dispatch(review_id, action, context, policy)
        assert not store.claim_dispatch(review_id, action, context, policy)
        assert store.mark_dispatched(review_id)
        store.conn.close()
        print("PASS: separate IDs; agent denied both protected files; operator approved; one dispatch claim")


if __name__ == "__main__":
    main()
