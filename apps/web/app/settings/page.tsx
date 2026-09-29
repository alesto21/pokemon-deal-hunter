"use client";

import { useState } from "react";
import JsonView from "@/components/JsonView";
import { ErrorBox, Loading, PageHeader, Panel, btnPrimary } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import type { SettingsResponse, TelegramTestResult } from "@/lib/types";

export default function SettingsPage() {
  const { data, error, loading } = useApi<SettingsResponse>("settings");
  const [tg, setTg] = useState<TelegramTestResult | null>(null);
  const [tgError, setTgError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function testTelegram() {
    setBusy(true);
    setTgError(null);
    try {
      setTg(await api<TelegramTestResult>("telegram/test", { method: "POST" }));
    } catch (e) {
      setTgError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <PageHeader title="Settings" subtitle="Effective configuration (read-only here)." />
      <ErrorBox error={error} />
      <Loading show={loading && !data} />
      {data && (
        <div className="space-y-6">
          <div className="rounded-md border border-sky-200 bg-sky-50 px-3 py-2 text-sm text-sky-900 dark:border-sky-900 dark:bg-sky-950 dark:text-sky-200">
            Preferences live in <code>config/*.yaml</code> ({data.config_dir}) and hot-reload on change. Secrets live in <code>.env</code> and are never shown here.
          </div>
          <div className="grid gap-6 md:grid-cols-3">
            <Panel title="Modes">
              <div className="space-y-1 text-sm">
                <div>Environment: <b>{data.environment}</b></div>
                <div>CardTrader: <b className={data.modes.cardtrader === "mock" ? "text-amber-600" : "text-emerald-600"}>{data.modes.cardtrader}</b></div>
                <div>Telegram: <b className={data.modes.telegram === "dry-run" ? "text-amber-600" : "text-emerald-600"}>{data.modes.telegram}</b></div>
              </div>
            </Panel>
            <Panel title="Secrets configured">
              <ul className="space-y-1 text-sm">
                {Object.entries(data.secrets).map(([k, v]) => (
                  <li key={k} className="flex justify-between">
                    <code className="text-xs">{k.toUpperCase()}</code>
                    <span>{v ? "✅" : "—"}</span>
                  </li>
                ))}
              </ul>
            </Panel>
            <Panel title="Telegram">
              <ErrorBox error={tgError} />
              <button className={btnPrimary} onClick={testTelegram} disabled={busy}>{busy ? "Sending…" : "Send test message"}</button>
              {tg && (
                <div className="mt-2 text-sm">
                  {tg.ok ? (tg.dry_run ? "Dry-run: message logged, not sent (no token/chat id)." : `Sent (message id ${tg.message_id}).`) : `Failed: ${tg.error}`}
                </div>
              )}
            </Panel>
          </div>
          <Panel title="Effective user config">
            <div className="space-y-2">
              {Object.entries(data.user_config).map(([section, value]) => (
                <details key={section} className="rounded border border-zinc-200 dark:border-zinc-800">
                  <summary className="cursor-pointer px-3 py-2 text-sm font-medium">{section} <span className="text-xs text-zinc-500">config/{section}.yaml</span></summary>
                  <div className="px-3 pb-3"><JsonView value={value} /></div>
                </details>
              ))}
            </div>
          </Panel>
        </div>
      )}
    </>
  );
}
