#!/usr/bin/env bash
# Prepare a separate operator identity and protected runtime database.
# Run as root: sudo bash scripts/setup_operator_isolation.sh
# The token is generated locally and never printed.
set -euo pipefail

OPERATOR_USER="${PEA_OPERATOR_USER:-pea-operator}"
AGENT_USER="${PEA_AGENT_USER:-${SUDO_USER:-$(id -un)}}"
STATE_DIR="${PEA_STATE_DIR:-/var/lib/pea}"
TOKEN_FILE="${PEA_TOKEN_FILE:-/etc/pea/operator.token}"
RUNTIME_DB="${PEA_RUNTIME_DB:-$STATE_DIR/runtime.db}"

if [ "$(id -u)" -ne 0 ]; then
  echo "run this script as root: sudo bash $0" >&2
  exit 1
fi
if [ "$AGENT_USER" = "$OPERATOR_USER" ]; then
  echo "agent and operator users must differ" >&2
  exit 1
fi

if ! id "$OPERATOR_USER" >/dev/null 2>&1; then
  useradd --system --home "$STATE_DIR" --shell /usr/sbin/nologin "$OPERATOR_USER"
fi

install -d -o "$OPERATOR_USER" -g "$OPERATOR_USER" -m 0700 "$STATE_DIR"
install -d -o root -g "$OPERATOR_USER" -m 0750 "$(dirname "$TOKEN_FILE")"

if [ ! -s "$TOKEN_FILE" ]; then
  umask 077
  head -c 32 /dev/urandom | base64 > "$TOKEN_FILE"
fi
chown root:"$OPERATOR_USER" "$TOKEN_FILE"
chmod 0640 "$TOKEN_FILE"

if [ ! -e "$RUNTIME_DB" ]; then
  runuser -u "$OPERATOR_USER" -- touch "$RUNTIME_DB"
fi
chown "$OPERATOR_USER":"$OPERATOR_USER" "$RUNTIME_DB"
chmod 0600 "$RUNTIME_DB"

if id -nG "$AGENT_USER" | tr ' ' '\n' | grep -qx "$OPERATOR_USER"; then
  echo "agent user $AGENT_USER is in the operator group; remove it first" >&2
  exit 1
fi

runuser -u "$AGENT_USER" -- test ! -r "$TOKEN_FILE"
runuser -u "$AGENT_USER" -- test ! -w "$RUNTIME_DB"

echo "OK: operator isolation prepared"
echo "operator user: $OPERATOR_USER"
echo "runtime db:    $RUNTIME_DB (0600, operator-owned)"
echo "token file:    $TOKEN_FILE (0640, root:$OPERATOR_USER; value not printed)"
if id -nG "$AGENT_USER" | tr ' ' '\n' | grep -qx "sudo"; then
  echo "WARNING: agent user $AGENT_USER is in the sudo group." >&2
  echo "Remove that membership or run the agent under a separate non-admin identity." >&2
fi
echo
echo "Operator console example (run as the operator, not the agent):"
echo "  sudo -u $OPERATOR_USER env \\"
echo "    PEA_RUNTIME_DB=$RUNTIME_DB \\"
echo "    PEA_OPERATOR_TOKEN=\"\$(cat $TOKEN_FILE)\" \\"
echo "    $PWD/.venv/bin/python -m patristic_ethics.operator --db $RUNTIME_DB list"
