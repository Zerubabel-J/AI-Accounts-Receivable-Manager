"""Seed realistic demo data into the store.

Run from /backend with the venv active:

    python ../scripts/seed.py

Creates ~80 invoices and ~20 payments spread across all four states,
with some clean matches, some fuzzy matches, and some unmatched payments
for the Review Queue demo.

Designed to make the dashboard look like a real company at ~$340K outstanding.

Also re-exported as `seed_demo_data()` so the running app can self-seed at
startup when the store is empty (see backend/app/main.py).
"""

import random
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

# Make /backend importable when running from /scripts (no-op when imported from inside backend)
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))

from app.integrations.sheets import get_store  # noqa: E402
from app.models.invoice import Invoice, InvoiceStatus  # noqa: E402
from app.models.payment import (  # noqa: E402
    MatchMethod,
    MatchStatus,
    Payment,
    PaymentSource,
)

CLIENTS = [
    ("Sarah Chen", "Acme Corp", "sarah@acmecorp.com", "555-0101"),
    ("Marcus Johnson", "TechFlow Inc", "marcus@techflow.io", "555-0102"),
    ("Priya Patel", "Bluewave Solutions", "priya@bluewave.co", "555-0103"),
    ("David Kim", "Northwind Trading", "dkim@northwind.com", "555-0104"),
    ("Aisha Mohammed", "Vertex Labs", "aisha@vertexlabs.com", "555-0105"),
    ("James O'Brien", "Cascade Logistics", "james@cascade-log.com", "555-0106"),
    ("Linh Nguyen", "Polaris Studio", "linh@polarisstudio.com", "555-0107"),
    ("Carlos Mendez", "Ironclad Mfg", "cmendez@ironclad.com", "555-0108"),
    ("Hannah Weiss", "Greenleaf Consulting", "hannah@greenleaf.co", "555-0109"),
    ("Tomas Berg", "Aurora Systems", "tomas@aurorasys.com", "555-0110"),
    ("Yuki Tanaka", "Meridian Group", "yuki@meridiangroup.com", "555-0111"),
    ("Robert Chen", "Skyline Partners", "rchen@skylinepartners.com", "555-0112"),
    ("Fatima Al-Hassan", "Coastal Imports", "fatima@coastalimports.com", "555-0113"),
    ("Daniel Rivera", "Horizon Tech", "drivera@horizontech.io", "555-0114"),
    ("Emma Thompson", "Birchwood Co", "emma@birchwood.co", "555-0115"),
]

INVOICE_AMOUNTS = [1250, 2400, 4800, 7500, 950, 3200, 6100, 1800, 5400, 9200, 12500, 3750]


def seed_demo_data(verbose: bool = True) -> dict:
    """Populate the active store with realistic demo data. Returns a summary dict."""
    random.seed(42)  # deterministic
    store = get_store()
    today = date.today()

    invoices: list[Invoice] = []
    inv_counter = 1

    # Generate ~80 invoices across all states.
    # Each client gets multiple invoices over the past 90 days.
    for client_idx, (name, biz, email, phone) in enumerate(CLIENTS):
        n_invoices = random.randint(4, 7)
        for _ in range(n_invoices):
            days_ago = random.randint(0, 90)
            issued = today - timedelta(days=days_ago)
            net_terms = random.choice([14, 30, 30, 45])
            due = issued + timedelta(days=net_terms)
            amount = float(random.choice(INVOICE_AMOUNTS))

            # Determine status from due date and a bit of randomness
            days_past_due = (today - due).days
            if days_past_due < 0:
                status = InvoiceStatus.SENT
                paid_at = None
            elif days_past_due > 30 and random.random() < 0.6:
                status = InvoiceStatus.AT_RISK
                paid_at = None
            elif random.random() < 0.55:
                # Most overdue eventually get paid
                status = InvoiceStatus.PAID
                paid_at = datetime.combine(
                    due + timedelta(days=random.randint(2, 25)),
                    datetime.min.time(),
                )
            elif days_past_due > 0:
                status = InvoiceStatus.OVERDUE
                paid_at = None
            else:
                status = InvoiceStatus.SENT
                paid_at = None

            inv = Invoice(
                invoice_id=f"INV-{inv_counter:04d}",
                customer_name=name,
                business_name=biz,
                email=email,
                phone=phone,
                amount=amount,
                issued_date=issued,
                due_date=due,
                status=status,
                reminder_count=min(3, max(0, days_past_due // 7)) if status != InvoiceStatus.SENT else 0,
                paid_at=paid_at,
            )
            store.upsert_invoice(inv)
            invoices.append(inv)
            inv_counter += 1

    # Risk score the worst clients
    overdue_by_client: dict[str, list[Invoice]] = {}
    for inv in invoices:
        overdue_by_client.setdefault(inv.email, []).append(inv)

    for email, client_invs in overdue_by_client.items():
        late_count = sum(
            1 for i in client_invs if i.status in (InvoiceStatus.OVERDUE, InvoiceStatus.AT_RISK)
        )
        total = len(client_invs)
        if total >= 3 and late_count / total >= 0.5:
            risk = 70 + min(25, late_count * 5)
            reason = f"Late on {late_count} of last {total} invoices; trend worsening."
            for inv in client_invs:
                if inv.status != InvoiceStatus.PAID:
                    inv.risk_score = risk
                    inv.risk_reason = reason
                    store.upsert_invoice(inv)

    # Generate ~20 payments. Mix:
    #   - 12 cleanly matched to paid invoices (already done)
    #   - 4 needing review (fuzzy match cases)
    #   - 4 no-match
    pay_counter = 1

    paid_invoices = [i for i in invoices if i.status == InvoiceStatus.PAID]
    for inv in paid_invoices[:12]:
        pay = Payment(
            payment_id=f"PAY-{pay_counter:04d}",
            source=PaymentSource.STRIPE,
            payer_name=inv.customer_name,
            payer_email=inv.email,
            amount=inv.amount,
            received_at=datetime.combine(
                inv.paid_at.date() if inv.paid_at else inv.due_date,
                datetime.min.time(),
            ),
            matched_invoice_id=inv.invoice_id,
            match_confidence=1.0,
            match_reasoning="Exact email + amount match.",
            match_status=MatchStatus.CONFIRMED,
            reviewed_by_user=False,
        )
        store.upsert_payment(pay)
        pay_counter += 1

    # 4 fuzzy / needs-review payments tied to currently-unpaid invoices
    unpaid = [i for i in invoices if i.status in (InvoiceStatus.OVERDUE, InvoiceStatus.SENT)][:4]
    for inv in unpaid:
        # Mangle the email or use a slightly different name to simulate fuzzy match
        scrambled_email = inv.email.replace("@", ".accounting@")
        pay = Payment(
            payment_id=f"PAY-{pay_counter:04d}",
            source=PaymentSource.STRIPE,
            payer_name=inv.customer_name.split()[0],  # first name only
            payer_email=scrambled_email,
            amount=inv.amount,
            received_at=datetime.now() - timedelta(hours=random.randint(1, 18)),
            matched_invoice_id=inv.invoice_id,
            match_confidence=round(random.uniform(0.65, 0.82), 2),
            match_reasoning=(
                f"Email differs but business name matches '{inv.business_name}'; "
                f"amount exact ({inv.amount:.2f})."
            ),
            match_status=MatchStatus.NEEDS_REVIEW,
            reviewed_by_user=False,
        )
        store.upsert_payment(pay)
        pay_counter += 1

    # 4 no-match payments (unknown payers)
    unknown_payers = [
        ("Mystery Buyer", "accounts@unknowncorp.com", 4200.0),
        ("J Smith", "j.smith@gmail.com", 1500.0),
        ("ABC Holdings LLC", "ap@abcholdings.com", 8750.0),
        ("Kira Zhang", "kira@example.com", 3300.0),
    ]
    for name, email, amount in unknown_payers:
        pay = Payment(
            payment_id=f"PAY-{pay_counter:04d}",
            source=PaymentSource.STRIPE,
            payer_name=name,
            payer_email=email,
            amount=amount,
            received_at=datetime.now() - timedelta(hours=random.randint(1, 48)),
            match_confidence=0.0,
            match_reasoning="No invoice matches this payer email, business, or amount.",
            match_status=MatchStatus.NO_MATCH,
        )
        store.upsert_payment(pay)
        pay_counter += 1

    all_invoices = store.list_invoices()
    by_status: dict[str, int] = {}
    by_status_amt: dict[str, float] = {}
    for inv in all_invoices:
        by_status[inv.status.value] = by_status.get(inv.status.value, 0) + 1
        by_status_amt[inv.status.value] = by_status_amt.get(inv.status.value, 0.0) + inv.amount
    outstanding = sum(
        i.amount
        for i in all_invoices
        if i.status in (InvoiceStatus.SENT, InvoiceStatus.OVERDUE, InvoiceStatus.AT_RISK)
    )

    if verbose:
        print(f"Seeded {len(all_invoices)} invoices and {pay_counter - 1} payments.")
        print()
        print(f"{'Status':<12} {'Count':>6} {'Amount':>14}")
        for status, count in sorted(by_status.items()):
            amt = by_status_amt[status]
            print(f"{status:<12} {count:>6} {'$' + f'{amt:,.0f}':>14}")
        print(f"\nOutstanding total: ${outstanding:,.2f}")

    return {
        "invoices": len(all_invoices),
        "payments": pay_counter - 1,
        "outstanding": outstanding,
        "by_status": by_status,
    }


if __name__ == "__main__":
    seed_demo_data()
