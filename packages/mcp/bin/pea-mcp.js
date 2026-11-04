#!/usr/bin/env node
/**
 * Thin stdio launcher for the PEA MCP server.
 *
 * Preferred path: uvx --from patristic-ethics pea-mcp
 * Fallback:      python -m patristic_ethics.mcp_server
 *
 * It never runs pip install silently. If neither uvx nor a usable Python
 * installation exists, it prints one install command and exits 1.
 */
import { spawn, spawnSync } from "node:child_process";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";

const here = dirname(fileURLToPath(import.meta.url));
const pkg = JSON.parse(readFileSync(join(here, "..", "package.json"), "utf8"));
const args = process.argv.slice(2);
const first = args[0];

if (first === "--version" || first === "-v") {
  console.log(pkg.version);
  process.exit(0);
}
if (first === "--help" || first === "-h") {
  console.log(`pea-mcp ${pkg.version}

Usage: npx pea-mcp

The launcher starts the PEA MCP server over stdio. It prefers:
  uvx --from patristic-ethics pea-mcp
and falls back to:
  python -m patristic_ethics.mcp_server

Environment:
  PEA_UVX=uvx            uvx executable
  PEA_PYTHON=python3     Python executable
  PEA_MCP_FORCE_PYTHON=1 skip uvx
  PEA_MCP_DRY_RUN=1      print the resolved command; do not launch
`);
  process.exit(0);
}

const uvx = process.env.PEA_UVX || "uvx";
const python = process.env.PEA_PYTHON || (process.platform === "win32" ? "python" : "python3");
const forcedPython = process.env.PEA_MCP_FORCE_PYTHON === "1";
const dryRun = process.env.PEA_MCP_DRY_RUN === "1";

function exists(command) {
  const result = spawnSync(command, ["--version"], { stdio: "ignore", timeout: 5000 });
  return !result.error;
}

function plan() {
  if (!forcedPython && exists(uvx)) {
    return {
      command: uvx,
      args: ["--from", "patristic-ethics", "pea-mcp", ...args],
    };
  }
  return { command: python, args: ["-m", "patristic_ethics.mcp_server", ...args] };
}

const resolved = plan();
if (dryRun) {
  console.log(JSON.stringify(resolved));
  process.exit(0);
}

function printInstallHelp() {
  console.error(`PEA MCP needs uv or Python 3.11+.

Install uv:
  https://docs.astral.sh/uv/getting-started/installation/

Or install the Python package:
  python3 -m pip install patristic-ethics

Then run:
  npx pea-mcp
`);
}

const canFallback = !forcedPython && resolved.command === uvx;

function launch(plan, allowFallback) {
  const child = spawn(plan.command, plan.args, {
    stdio: "inherit",
    env: process.env,
    shell: false,
  });

  child.on("error", (error) => {
    if (error && error.code === "ENOENT") {
      printInstallHelp();
      process.exit(1);
    }
    console.error(`PEA MCP launcher failed: ${error.message}`);
    process.exit(1);
  });

  for (const signal of ["SIGINT", "SIGTERM", "SIGHUP"]) {
    process.on(signal, () => {
      if (!child.killed) child.kill(signal);
    });
  }

  child.on("exit", (code, signal) => {
    if (signal) process.exit(1);
    if (code !== 0 && allowFallback) {
      launch(
        { command: python, args: ["-m", "patristic_ethics.mcp_server", ...args] },
        false,
      );
      return;
    }
    process.exit(code ?? 1);
  });
}

launch(resolved, canFallback);
