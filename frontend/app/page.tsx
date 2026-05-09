export default function Home() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <header className="mb-8">
        <h1 className="text-3xl font-semibold tracking-tight">
          AI Accounts Receivable Manager
        </h1>
        <p className="mt-2 text-slate-600">
          Watching payments. Matching invoices. Chasing late ones.
        </p>
      </header>

      <section className="rounded-lg border bg-white p-6">
        <p className="text-sm text-slate-500">
          Setup phase complete. Dashboard, Invoices, and Review Queue land in
          the next phase.
        </p>
      </section>
    </main>
  );
}
