/**
 * PEA (Patristic Ethics Agent) — native OpenCode adapter plugin (M4a).
 *
 * What this plugin does:
 * - `chat.message`: collects session context automatically, runs the frozen
 *   PEA CLI (`python -m patristic_ethics.cli assess --stdin`) and, on a
 *   refuse/guide/clarify/review action, injects guidance into the user
 *   message as a full TextPart (id/sessionID/messageID/type/text — the
 *   host's zod schema rejects anything less).
 * - `tool.execute.before`: pre-action gate for covered tools. A refuse,
 *   clarify or review action throws an Error, which the host turns into a
 *   blocked tool call (`tool.execute.after` then never fires for it).
 * - `tool.execute.after`: best-effort audit logging only; never throws.
 *
 * Native-mode limits (documented, deliberate):
 * - NO before-display guarantee: `experimental.text.complete` fires AFTER
 *   text deltas are published, so native mode cannot withhold display.
 *   The PEA-owned controlled client (M4b, src/patristic_ethics/
 *   controlled.py) owns that guarantee. DO NOT combine this plugin with
 *   the controlled client profile — the same prompt would be assessed
 *   twice with no shared private call path.
 * - Covered tools only: the gate applies to `tool.execute.before` for host
 *   tools enabled in the profile; uncovered paths (other tools, subagents,
 *   background jobs, interactive continuation) run ungated.
 * - Fail-open on hook failure: any CLI failure or timeout injects nothing
 *   and blocks nothing; the failure is logged (pea_cli_failure). This is
 *   the documented native-mode tradeoff — use M4b when fail-open is
 *   unacceptable.
 *
 * Recursion guard: tool calls whose name starts with "pea" or whose args
 * mention the PEA CLI are skipped — a private adapter path, never an
 * agent-supplied bypass flag.
 *
 * This file never writes to stdout (no console.log anywhere) and never
 * throws out of a hook except the deliberate tool-gate block.
 */

import fs from "fs"
import path from "path"
import type { Plugin } from "@opencode-ai/plugin"

const PEA_PREFIX = "PEA: "
const REFUSE_BOUNDARY =
  "This request has been assessed and refused by the PEA ethics gate."

type Config = {
  enabled: boolean
  cliCmd: string[]
  db: string
  policy?: string
  backend: string
  workdir: string
  timeoutMs: number
  logPath?: string
}

function readConfig(): Config {
  const env = (k: string, d?: string): string | undefined =>
    process.env[k] !== undefined && process.env[k] !== "" ? process.env[k] : d
  const timeoutRaw = parseInt(process.env.PEA_TIMEOUT_MS ?? "", 10)
  return {
    enabled: (env("PEA_ENABLED", "1") ?? "1") !== "0",
    cliCmd: (env("PEA_CLI", "uv run python -m patristic_ethics.cli") ?? "").split(/\s+/).filter(Boolean),
    db: env("PEA_DB", "corpus/units.db") ?? "corpus/units.db",
    policy: env("PEA_POLICY"),
    backend: env("PEA_BACKEND", "fake") ?? "fake",
    workdir: env("PEA_WORKDIR", process.cwd()) ?? process.cwd(),
    timeoutMs: Number.isFinite(timeoutRaw) && timeoutRaw >= 1000 ? timeoutRaw : 20000,
    logPath: env("PEA_LOG"),
  }
}

function now(): string {
  return new Date().toISOString()
}

/** Best-effort audit log (file, when PEA_LOG is set) + host log for failures. */
function logLine(cfg: Config, client: any, line: Record<string, unknown>): void {
  if (cfg.logPath) {
    try {
      fs.mkdirSync(path.dirname(cfg.logPath), { recursive: true })
      fs.appendFileSync(cfg.logPath, JSON.stringify({ ts: now(), ...line }) + "\n")
    } catch {
      // Never crash the host on logging.
    }
  }
  if (line.type === "pea_cli_failure" || line.type === "pea_hook_error") {
    try {
      client?.app?.log?.({
        body: {
          service: "pea-ethics",
          level: "error",
          message: JSON.stringify(line),
        },
      })
    } catch {
      // Best-effort host log only.
    }
  }
}

function partsText(parts: any[]): string {
  try {
    return (parts ?? [])
      .map((p: any) => (typeof p?.text === "string" ? p.text : ""))
      .filter(Boolean)
      .join("\n")
  } catch {
    return ""
  }
}

function firstJsonObject(stdout: string): any | null {
  for (const raw of stdout.split("\n")) {
    const line = raw.trim()
    if (!line.startsWith("{")) continue
    try {
      const obj = JSON.parse(line)
      if (obj && typeof obj === "object") return obj
    } catch {
      // Not a JSON line; keep scanning.
    }
  }
  return null
}

/**
 * Run the frozen PEA CLI: one ContextEnvelope JSON on stdin, one
 * AssessResult JSON line on stdout. Never throws to the host; returns
 * null on any failure (documented fail-open). Never writes to stdout.
 */
async function runCli(cfg: Config, client: any, envelope: any, hook: string): Promise<any | null> {
  const cmd = cfg.cliCmd.concat([
    "assess",
    "--stdin",
    "--backend",
    cfg.backend,
    "--db",
    cfg.db,
  ])
  if (cfg.policy) cmd.push("--policy", cfg.policy)
  const payload = JSON.stringify(envelope)

  let stdout = ""
  let stderr = ""
  let exit: number | null = null
  let timedOut = false

  try {
    const bun: any = (globalThis as any).Bun
    if (bun?.spawn) {
      const proc = bun.spawn(cmd, {
        cwd: cfg.workdir,
        stdin: "pipe",
        stdout: "pipe",
        stderr: "pipe",
      })
      proc.stdin.write(payload)
      proc.stdin.end()
      const timer = setTimeout(() => {
        timedOut = true
        try {
          proc.kill(9)
        } catch {
          // Already exited.
        }
      }, cfg.timeoutMs)
      const outP = new Response(proc.stdout).text()
      const errP = new Response(proc.stderr).text()
      stdout = await outP
      stderr = await errP
      exit = await proc.exited
      clearTimeout(timer)
    } else {
      // Non-Bun fallback (e.g. node-based test harnesses).
      const cp = await import("child_process")
      const r = cp.spawnSync(cmd[0], cmd.slice(1), {
        input: payload,
        cwd: cfg.workdir,
        timeout: cfg.timeoutMs,
        encoding: "utf8",
        killSignal: "SIGKILL",
        maxBuffer: 16 * 1024 * 1024,
      })
      stdout = r.stdout ?? ""
      stderr = r.stderr ?? ""
      exit = r.status
      timedOut = r?.error?.code === "ETIMEDOUT"
    }
  } catch (e: any) {
    logLine(cfg, client, { hook, type: "pea_cli_failure", detail: "spawn failed: " + String(e) })
    return null
  }

  if (timedOut) {
    logLine(cfg, client, { hook, type: "pea_cli_failure", detail: "timeout after " + cfg.timeoutMs + "ms" })
    return null
  }
  if (exit !== 0) {
    logLine(cfg, client, {
      hook,
      type: "pea_cli_failure",
      detail: "exit " + String(exit),
      stderr: stderr.slice(0, 400),
    })
    return null
  }
  const result = firstJsonObject(stdout)
  if (result === null || typeof result.action !== "string") {
    logLine(cfg, client, { hook, type: "pea_cli_failure", detail: "no AssessResult JSON on stdout" })
    return null
  }
  return result
}

/** Map fetched session messages to envelope messages (seq strictly ascending). */
function mapMessages(rows: any[]): any[] {
  const out: any[] = []
  let seq = 1
  for (const row of rows ?? []) {
    const info = row?.info
    if (!info?.id || !info?.role) continue
    const text = partsText(row?.parts)
    if (!text) continue
    const role =
      info.role === "user" || info.role === "assistant" || info.role === "system"
        ? info.role
        : "tool"
    const origin =
      role === "user" ? "user" : role === "assistant" ? "assistant" : role === "system" ? "quote" : "tool"
    out.push({ role, source_id: info.id, seq: seq++, text, origin })
  }
  return out
}

/** Input-stage envelope with automatically collected session history. */
async function buildInputEnvelope(
  sessionID: string,
  requestText: string,
  client: any,
  fallbackTurnID?: string
): Promise<any> {
  const errors: string[] = []
  let messages: any[] = []
  let complete = false
  let turnID = fallbackTurnID ?? ""
  try {
    const res = await client?.session?.messages?.({ path: { id: sessionID } })
    if (Array.isArray(res?.data)) {
      complete = true
      messages = mapMessages(res.data)
      const last = res.data[res.data.length - 1]
      if (last?.info?.id) turnID = last.info.id
    } else {
      errors.push("session fetch returned no data: " + String(res?.error ?? "unknown"))
    }
  } catch (e) {
    errors.push("session fetch failed: " + String(e))
  }
  if (!turnID) turnID = "turn-" + sessionID
  return {
    schema_version: "1",
    host: { name: "opencode", version: "1.18.x", mode: "native" },
    session: { id: sessionID },
    turn: { id: turnID },
    stage: "input",
    request: requestText,
    messages,
    earlier_excerpts: [],
    history: {
      complete,
      omitted_ranges: [],
      collection_errors: errors,
      modalities: messages.length ? ["text"] : [],
    },
    policy_version: "0.1.0-draft",
    corpus_version: "0.1.0-draft",
    language: "en",
  }
}

/** Pre-action envelope for a proposed tool call (history intentionally not collected). */
function buildPreActionEnvelope(sessionID: string, callID: string, tool: string, args: any): any {
  return {
    schema_version: "1",
    host: { name: "opencode", version: "1.18.x", mode: "native" },
    session: { id: sessionID },
    turn: { id: callID || "call-" + sessionID },
    stage: "pre_action",
    request: "Tool call: " + tool,
    messages: [],
    earlier_excerpts: [],
    proposed_action: { tool, arguments: args ?? {} },
    history: { complete: false, omitted_ranges: [], collection_errors: [], modalities: [] },
    policy_version: "0.1.0-draft",
    corpus_version: "0.1.0-draft",
    language: "en",
  }
}

const GATE_ACTIONS = new Set(["refuse", "clarify", "review"])
const INJECT_ACTIONS = new Set(["refuse", "guide", "clarify", "review"])

export const PeaEthics: Plugin = async ({ client }) => {
  const cfg = readConfig()
  return {
    "chat.message": async (input, output) => {
      try {
        if (!cfg.enabled) return
        const requestText = partsText(output?.parts)
        if (!requestText) return
        const sessionID = input?.sessionID ?? ""
        const messageID = input?.messageID ?? output?.message?.id
        const envelope = await buildInputEnvelope(sessionID, requestText, client, messageID)
        const result = await runCli(cfg, client, envelope, "chat.message")
        if (!result) return // fail-open, already logged
        if (INJECT_ACTIONS.has(result.action)) {
          const guidance = typeof result?.guidance?.text === "string" ? result.guidance.text : ""
          const text =
            result.action === "refuse"
              ? PEA_PREFIX + REFUSE_BOUNDARY + "\n" + guidance
              : PEA_PREFIX + guidance
          if (sessionID && messageID && Array.isArray(output?.parts)) {
            output.parts.push({
              id: "prt_pea_" + Date.now() + "_" + Math.random().toString(36).slice(2, 10),
              sessionID: sessionID,
              messageID: messageID,
              type: "text",
              text: text,
            })
            logLine(cfg, client, { hook: "chat.message", sessionID, action: result.action, injected: text })
          } else {
            logLine(cfg, client, { hook: "chat.message", sessionID, action: result.action, injection_skipped: "no messageID" })
          }
          return
        }
        logLine(cfg, client, { hook: "chat.message", sessionID, action: result.action })
      } catch (e) {
        logLine(cfg, client, { hook: "chat.message", type: "pea_hook_error", detail: String(e) })
      }
    },
    "tool.execute.before": async (input, output) => {
      try {
        if (!cfg.enabled) return
        const tool = input?.tool ?? ""
        // Recursion guard: private adapter path only — no agent-supplied
        // bypass flag. Skip PEA's own tools and any attempt to run the
        // PEA CLI itself through a host tool.
        let argsJson = ""
        try {
          argsJson = JSON.stringify(output?.args ?? {})
        } catch {
          argsJson = ""
        }
        if (tool.startsWith("pea") || argsJson.includes("patristic_ethics.cli") || argsJson.includes("pea assess")) {
          logLine(cfg, client, { hook: "tool.execute.before", tool, skipped: "recursion_guard" })
          return
        }
        const sessionID = input?.sessionID ?? ""
        const envelope = buildPreActionEnvelope(sessionID, input?.callID ?? "", tool, output?.args)
        const result = await runCli(cfg, client, envelope, "tool.execute.before")
        if (!result) return // fail-open, already logged
        if (GATE_ACTIONS.has(result.action)) {
          const guidance = typeof result?.guidance?.text === "string" ? result.guidance.text : ""
          logLine(cfg, client, {
            hook: "tool.execute.before",
            sessionID,
            tool,
            action: result.action,
            blocked: true,
          })
          // Throwing an Error is the host-supported way to block the call.
          throw new Error(PEA_PREFIX + result.action + " — " + guidance)
        }
        logLine(cfg, client, { hook: "tool.execute.before", sessionID, tool, action: result.action })
      } catch (e: any) {
        if (e instanceof Error && e.message.startsWith(PEA_PREFIX)) throw e
        logLine(cfg, client, { hook: "tool.execute.before", type: "pea_hook_error", detail: String(e) })
      }
    },
    "tool.execute.after": async (input, output) => {
      try {
        if (!cfg.enabled) return
        logLine(cfg, client, {
          hook: "tool.execute.after",
          sessionID: input?.sessionID ?? "",
          tool: input?.tool ?? "",
          callID: input?.callID ?? "",
          title: output?.title ?? "",
        })
      } catch {
        // Best-effort audit only; never throw.
      }
    },
  }
}

export default PeaEthics