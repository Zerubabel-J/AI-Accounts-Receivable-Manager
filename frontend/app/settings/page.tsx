export default function SettingsPage() {
  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-slate-500">
          Connect integrations and tune the agent. Demo mode — these toggles are placeholders.
        </p>
      </header>

      <section className="rounded-lg border bg-white p-5">
        <h2 className="text-sm font-semibold">Integrations</h2>
        <ul className="mt-3 divide-y">
          <li className="flex items-center justify-between py-3">
            <div>
              <div className="font-medium">Stripe</div>
              <div className="text-xs text-slate-500">Receives payment events via webhook.</div>
            </div>
            <span className="rounded-md bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">
              Connected (sandbox)
            </span>
          </li>
          <li className="flex items-center justify-between py-3">
            <div>
              <div className="font-medium">Gmail</div>
              <div className="text-xs text-slate-500">Sends reminders and the daily summary.</div>
            </div>
            <span className="rounded-md bg-emerald-100 px-2 py-0.5 text-xs font-medium text-emerald-800">
              Connected
            </span>
          </li>
          <li className="flex items-center justify-between py-3">
            <div>
              <div className="font-medium">Google Sheets</div>
              <div className="text-xs text-slate-500">Source of truth for invoices and payments.</div>
            </div>
            <span className="rounded-md bg-slate-100 px-2 py-0.5 text-xs font-medium text-slate-700">
              In-memory (demo)
            </span>
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
