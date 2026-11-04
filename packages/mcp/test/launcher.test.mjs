import { test } from "node:test";
import assert from "node:assert/strict";
import { spawnSync } from "node:child_process";
import { chmodSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const bin = join(here, "..", "bin", "pea-mcp.js");

function run(env) {
  return spawnSync(process.execPath, [bin, "--version"], {
    env: { ...process.env, ...env },
    encoding: "utf8",
  });
}

test("prints its version", () => {
  const result = run({});
  assert.equal(result.status, 0);
  assert.match(result.stdout, /^0\.0\.1/);
});

test("dry run plans uvx by default", () => {
  const result = spawnSync(process.execPath, [bin], {
    env: { ...process.env, PEA_MCP_DRY_RUN: "1" },
    encoding: "utf8",
  });
  assert.equal(result.status, 0);
  const plan = JSON.parse(result.stdout);
  assert.equal(plan.command, "uvx");
  assert.deepEqual(plan.args.slice(0, 3), ["--from", "patristic-ethics", "pea-mcp"]);
});

test("force python uses the module fallback", () => {
  const result = spawnSync(process.execPath, [bin], {
    env: { ...process.env, PEA_MCP_DRY_RUN: "1", PEA_MCP_FORCE_PYTHON: "1" },
    encoding: "utf8",
  });
  assert.equal(result.status, 0);
  const plan = JSON.parse(result.stdout);
  assert.match(plan.command, /python/);
  assert.deepEqual(plan.args.slice(0, 2), ["-m", "patristic_ethics.mcp_server"]);
});

test("missing interpreter prints install help and exits 1", () => {
  const result = spawnSync(process.execPath, [bin], {
    env: {
      ...process.env,
      PEA_MCP_FORCE_PYTHON: "1",
      PEA_PYTHON: "pea-missing-python",
    },
    encoding: "utf8",
  });
  assert.equal(result.status, 1);
  assert.match(result.stderr, /needs uv or Python 3\.11\+/);
});

test("falls back to python when uvx exits nonzero", () => {
  const dir = mkdtempSync(join(tmpdir(), "pea-mcp-"));
  const uvx = join(dir, "uvx");
  const python = join(dir, "python3");
  writeFileSync(uvx, "#!/bin/sh\nif [ \"$1\" = \"--version\" ]; then exit 0; fi\nexit 1\n");
  writeFileSync(python, "#!/bin/sh\necho PYTHON_FALLBACK_REACHED\nexit 0\n");
  chmodSync(uvx, 0o755);
  chmodSync(python, 0o755);

  const result = spawnSync(process.execPath, [bin], {
    env: {
      ...process.env,
      PATH: dir + ":" + process.env.PATH,
      PEA_UVX: "uvx",
      PEA_PYTHON: "python3",
      PEA_MCP_FORCE_PYTHON: "0",
    },
    encoding: "utf8",
  });
  assert.equal(result.status, 0);
  assert.match(result.stdout, /PYTHON_FALLBACK_REACHED/);
});
