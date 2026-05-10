import { api } from "@/lib/api";

interface SystemStatus {
  store_backend: "google_sheets" | "in_memory";
  sheet_id: string | null;
  gemini_enabled: boolean;
  send_emails_for_real: boolean;
}

async function loadStatus(): Promise<SystemStatus | null> {
  try {
    return await api<SystemStatus>("/system-status");
  } catch {
    return null;
  }
}

function StatusPill({ ok, label }: { ok: boolean; label: string }) {
  return (
    <span
      className={`rounded-md px-2 py-0.5 text-xs font-medium ${
        ok ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-700"
      }`}
    >
      {label}
    </span>
  );
}

export default async function SettingsPage() {
  const status = await loadStatus();

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-slate-500">
          What is wired up and what is in demo-mode.
        </p>
      </header>

      <section className="rounded-lg border bg-white p-5">
        <h2 className="text-sm font-semibold">Integrations</h2>
        <ul className="mt-3 divide-y">
          <li className="flex items-center justify-between py-3">
            <div>
              <div className="font-medium">Google Sheets</div>
              <div className="text-xs text-slate-500">
                Source of truth for invoices, payments, activity.
              </div>
              {status?.sheet_id && (
                <div className="mt-0.5 truncate font-mono text-xs text-slate-400">
                  sheet: {status.sheet_id.slice(0, 12)}...
                </div>
              )}
            </div>
            <StatusPill
              ok={status?.store_backend === "google_sheets"}
              label={
                status?.store_backend === "google_sheets" ? "Connected" : "In-memory (demo)"
              }
            />
          </li>
          <li className="flex items-center justify-between py-3">
            <div>
              <div className="font-medium">Gemini 2.5 Flash</div>
              <div className="text-xs text-slate-500">
                Fuzzy entity resolution and risk reasoning for the Smart Match engine.
              </div>
            </div>
            <StatusPill ok={!!status?.gemini_enabled} label={status?.gemini_enabled ? "Connected" : "Heuristic only"} />
          </li>
          <li className="flex items-center justify-between py-3">
            <div>
              <div className="font-medium">Stripe</div>
              <div className="text-xs text-slate-500">
                Receives payment events via webhook. Demo uses /payments/simulate instead.
              </div>
            </div>
            <span className="rounded-md bg-amber-100 px-2 py-0.5 text-xs font-medium text-amber-800">
              Demo (simulate)
            </span>
          </li>
          <li className="flex items-center justify-between py-3">
            <div>
              <div className="font-medium">Gmail</div>
              <div className="text-xs text-slate-500">Sends reminders and the daily summary.</div>
            </div>
            <StatusPill
              ok={!!status?.send_emails_for_real}
              label={status?.send_emails_for_real ? "Live" : "Drafts only (safe)"}
            />
          </li>
        </ul>
      </section>

      <section className="rounded-lg border bg-white p-5">
        <h2 className="text-sm font-semibold">Reminder cadence</h2>
        <p className="mt-2 text-sm text-slate-600">
          Default: friendly at day 0, firmer at +7, escalation at +14, flagged at-risk at +30.
        </p>
      </section>
    </div>
  );
}
