"use client";

import { Bell, KeyRound, Settings, SlidersHorizontal } from "lucide-react";
import JsonView from "@/components/system/JsonView";
import TelegramTest from "@/components/system/TelegramTest";
import { Badge, Disclosure, ErrorBox, Field, Loading, PageHeader, Panel } from "@/components/ui";
import { useApi } from "@/lib/api";
import type { SettingsResponse } from "@/lib/types";

const SECRET_LABELS: Record<string, string> = {
  cardtrader_api_token: "CardTrader API token",
  telegram_bot_token: "Telegram bot token",
  telegram_chat_id: "Telegram chat id",
  api_key: "Internal API key",
};

const SECTION_HELP: Record<string, string> = {
  pokemon: "Popularity tiers, high-priority and ignored Pokémon, themes, premium targets",
  sets: "Set desirability, aliases, tracked sets, pack counts",
  rarities: "Rarity → scarcity, premium rarities",
  binders: "Binder thresholds, capacities and portfolio modifiers",
  scoring: "Weights, curves, bands and fair-value parameters",
  alerts: "Notification thresholds, daily cap, cooldowns",
  grading: "Grading cost and upside curve",
  currencies: "Exchange-rate source and fallback rates",
  sources: "Seller regions, landed cost, sources, schedules, retention",
};

function Mode({ label, value, good }: { label: string; value: string; good: boolean }) {
  return <Field label={label} value={<Badge tone={good ? "gain" : "warn"}>{value}</Badge>} />;
}

export default function SettingsPage() {
  const { data, error, loading } = useApi<SettingsResponse>("settings");

  return (
    <>
      <PageHeader title="Settings" icon={Settings} subtitle="Effective configuration. Read-only here — edit the files on the server." />
      <ErrorBox error={error} />
      <Loading show={loading && !data} />
      {data && (
        <div className="space-y-6">
          <div className="rounded-xl border border-sky-400/20 bg-sky-500/10 px-4 py-3 text-sm text-sky-100">
            Preferences live in <code className="text-sky-200">config/*.yaml</code> <span className="text-sky-300/70">({data.config_dir})</span> and
            hot-reload when a file changes. Secrets live in <code className="text-sky-200">.env</code> and are never shown — only whether they are set.
          </div>

          <div className="grid gap-4 md:grid-cols-3">
            <Panel title="Modes" icon={SlidersHorizontal}>
              <Field label="Environment" value={data.environment} />
              <Mode label="CardTrader" value={data.modes.cardtrader === "mock" ? "Mock data" : "Live API"} good={data.modes.cardtrader !== "mock"} />
              <Mode label="Telegram" value={data.modes.telegram === "dry-run" ? "Dry-run" : "Live"} good={data.modes.telegram !== "dry-run"} />
            </Panel>
            <Panel title="Secrets" icon={KeyRound}>
              {Object.entries(data.secrets).map(([k, v]) => (
                <Field key={k} label={SECRET_LABELS[k] ?? k} value={v ? <Badge tone="gain">Configured</Badge> : <Badge>Not set</Badge>} />
              ))}
            </Panel>
            <Panel title="Telegram" icon={Bell}>
              <p className="mb-3 text-sm text-ink-3">
                {data.modes.telegram === "dry-run"
                  ? "Alerts are only logged until a bot token and chat id are set in .env."
                  : "Alerts are delivered to your Telegram chat."}
              </p>
              <TelegramTest dryRun={data.modes.telegram === "dry-run"} />
            </Panel>
          </div>

          <Panel title="Effective configuration" subtitle="One section per file in config/.">
            <div className="space-y-2">
              {Object.entries(data.user_config).map(([section, value]) => (
                <Disclosure
                  key={section}
                  title={
                    <span className="flex min-w-0 flex-col sm:flex-row sm:items-baseline sm:gap-2">
                      <span className="font-medium text-ink">{section}</span>
                      <span className="truncate text-xs text-ink-3">
                        config/{section}.yaml{SECTION_HELP[section] ? ` · ${SECTION_HELP[section]}` : ""}
                      </span>
                    </span>
                  }
                >
                  <JsonView value={value} />
                </Disclosure>
              ))}
            </div>
          </Panel>
        </div>
      )}
    </>
  );
}
