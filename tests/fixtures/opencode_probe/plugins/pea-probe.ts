import fs from "fs"
import path from "path"
import type { Plugin } from "@opencode-ai/plugin"

const OUT_DIR = "/tmp/pea-probe/out"
const LOG = path.join(OUT_DIR, "probe.jsonl")
const BLOCK_SENTINEL = "PEA_PROBE_BLOCK"
const CANARY = "PEA-CANARY-1"

function now(): string {
  return new Date().toISOString()
}

function emit(client: Plugin.Context["client"], line: Record<string, unknown>): void {
  try {
    fs.mkdirSync(OUT_DIR, { recursive: true })
    fs.appendFileSync(LOG, JSON.stringify(line) + "\n")
  } catch {
    // Never crash the host on logging.
  }
  try {
    client?.app?.log({ body: { service: "pea-probe", level: "info", message: JSON.stringify(line) } })
  } catch {
    // Best-effort host log only.
  }
}

function partsText(parts: any[]): string {
  try {
    return (parts ?? [])
      .map((p) => (typeof p?.text === "string" ? p.text : ""))
      .filter(Boolean)
      .join(" ")
  } catch {
    return ""
  }
}

export const PeaProbe: Plugin = async ({ client }) => {
  return {
    "chat.message": (input, output) => {
      emit(client, {
        hook: "chat.message",
        ts: now(),
        sessionID: input?.sessionID,
        mutate: process.env.PEA_PROBE_MUTATE === "1",
        text: partsText(output?.parts),
      })
      try {
        if (process.env.PEA_PROBE_MUTATE === "1" && Array.isArray(output?.parts)) {
          // A part must carry the full TextPart shape; a bare {type,text}
          // object fails the host's zod schema (Missing key at id/sessionID/messageID).
          if (input?.sessionID && (input?.messageID ?? output?.message?.id)) {
            output.parts.push({
              id: "prt_" + Date.now(),
              sessionID: input.sessionID,
              messageID: input?.messageID ?? output?.message?.id,
              type: "text",
              text: CANARY,
            })
            emit(client, { hook: "chat.message", ts: now(), injected: CANARY })
          } else {
            emit(client, { hook: "chat.message", ts: now(), injection_skipped: "no messageID" })
          }
        }
      } catch {
        // Injection is best-effort; never crash the host.
      }
      return output
    },
    "tool.execute.before": (input, output) => {
      let blocked = false
      try {
        blocked = JSON.stringify(output?.args ?? {}).includes(BLOCK_SENTINEL)
      } catch {
        blocked = false
      }
      emit(client, {
        hook: "tool.execute.before",
        ts: now(),
        sessionID: input?.sessionID,
        tool: input?.tool,
        callID: input?.callID,
        blocked,
      })
      if (blocked) throw new Error("PEA_PROBE_BLOCKED")
      return output
    },
    "tool.execute.after": (input, output) => {
      emit(client, {
        hook: "tool.execute.after",
        ts: now(),
        sessionID: input?.sessionID,
        tool: input?.tool,
        callID: input?.callID,
      })
      return output
    },
    event: ({ event }) => {
      // Keep the log small: only the type, no payload (no secrets).
      emit(client, { hook: "event", ts: now(), type: event?.type })
    },
    "experimental.text.complete": (input, output) => {
      emit(client, {
        hook: "experimental.text.complete",
        ts: now(),
        sessionID: input?.sessionID,
      })
      return output
    },
  }
}

export default PeaProbe