"use client";

import { Send } from "lucide-react";
import { useState } from "react";
import { btn } from "@/components/ui";
import { api } from "@/lib/api";
import type { TelegramTestResult } from "@/lib/types";

/** Sends a test message. In dry-run mode the message is only logged — said explicitly. */
export default function TelegramTest({ dryRun }: { dryRun: boolean }) {
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<{ tone: "ok" | "warn" | "bad"; text: string } | null>(null);

  async function send() {
    setBusy(true);
    setResult(null);
    try {
      const r = await api<TelegramTestResult>("telegram/test", { method: "POST" });
      if (!r.ok) setResult({ tone: "bad", text: `Failed: ${r.error ?? "unknown error"}` });
      else if (r.dry_run) setResult({ tone: "warn", text: "Dry-run: the message was logged, not sent (no bot token / chat id)." });
      else setResult({ tone: "ok", text: `Sent — Telegram message id ${r.message_id}.` });
    } catch (e) {
      setResult({ tone: "bad", text: (e as Error).message });
    } finally {
      setBusy(false);
    }
  }

  const cls = result?.tone === "ok" ? "text-gain" : result?.tone === "warn" ? "text-warn" : "text-loss";
  return (
    <div className="space-y-2">
      <button className={btn} onClick={send} disabled={busy}>
        <Send size={14} />
        {busy ? "Sending…" : dryRun ? "Send test (dry-run)" : "Send test message"}
      </button>
      {result && <p className={`text-xs ${cls}`}>{result.text}</p>}
    </div>
  );
}
