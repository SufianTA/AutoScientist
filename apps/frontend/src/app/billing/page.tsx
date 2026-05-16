"use client";

import { useEffect, useState } from "react";
import { apiGet, apiPost } from "@/lib/api";

type Account = {
  id: string;
  owner_email: string;
  display_name: string;
  balance_usd: number;
};

type LedgerEntry = {
  id: string;
  entry_type: string;
  amount_usd: number;
  balance_after_usd: number;
  description: string;
  created_at: string;
};

export default function BillingPage() {
  const [account, setAccount] = useState<Account | null>(null);
  const [entries, setEntries] = useState<LedgerEntry[]>([]);
  const [amount, setAmount] = useState(50);
  const [busy, setBusy] = useState(false);

  async function loadBilling() {
    const ledger = await apiGet<{ account: Account; entries: LedgerEntry[] }>("/billing/ledger");
    setAccount(ledger.account);
    setEntries(ledger.entries);
  }

  async function addCredits() {
    setBusy(true);
    const checkout = await apiPost<{ checkout_session: { id: string } }>("/billing/checkout", {
      amount_usd: amount,
      provider: "mock"
    });
    await apiPost(`/billing/checkout/${checkout.checkout_session.id}/complete`, {});
    await loadBilling();
    setBusy(false);
  }

  useEffect(() => {
    loadBilling();
  }, []);

  return (
    <main className="page">
      <div className="kicker">Billing</div>
      <h1>Research credits</h1>
      <section className="panel">
        <h2>{account?.display_name ?? "Loading account"}</h2>
        <p className="lede">${account?.balance_usd.toFixed(2) ?? "0.00"} available</p>
        <div className="actions">
          <input type="number" min={1} value={amount} onChange={(event) => setAmount(Number(event.target.value))} />
          <button type="button" onClick={addCredits} disabled={busy}>{busy ? "Adding" : "Add mock credits"}</button>
        </div>
      </section>
      <section className="panel" style={{ marginTop: 18 }}>
        <h2>Ledger</h2>
        <table className="table">
          <thead>
            <tr><th>Type</th><th>Amount</th><th>Balance</th><th>Description</th></tr>
          </thead>
          <tbody>
            {entries.map((entry) => (
              <tr key={entry.id}>
                <td>{entry.entry_type}</td>
                <td>${entry.amount_usd.toFixed(2)}</td>
                <td>${entry.balance_after_usd.toFixed(2)}</td>
                <td>{entry.description}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </main>
  );
}

