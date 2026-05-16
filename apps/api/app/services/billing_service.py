from __future__ import annotations

from sqlalchemy.orm import Session

from app.db.models import BillingAccount, CheckoutSession, CreditLedgerEntry, Run


DEMO_ACCOUNT_EMAIL = "demo@bioautoscientist.local"


class InsufficientCreditsError(Exception):
    pass


def get_or_create_account(
    db: Session,
    owner_email: str = DEMO_ACCOUNT_EMAIL,
    display_name: str = "Demo Research Lab",
) -> BillingAccount:
    account = db.query(BillingAccount).filter(BillingAccount.owner_email == owner_email).first()
    if account is not None:
        return account
    account = BillingAccount(owner_email=owner_email, display_name=display_name, balance_usd=0.0)
    db.add(account)
    db.flush()
    add_credits(db, account, 100.0, "Initial demo credits", external_reference="demo_seed")
    db.commit()
    db.refresh(account)
    return account


def add_credits(
    db: Session,
    account: BillingAccount,
    amount_usd: float,
    description: str,
    external_reference: str | None = None,
) -> CreditLedgerEntry:
    amount = round(float(amount_usd), 2)
    account.balance_usd = round(account.balance_usd + amount, 2)
    entry = CreditLedgerEntry(
        account_id=account.id,
        entry_type="credit",
        amount_usd=amount,
        balance_after_usd=account.balance_usd,
        description=description,
        external_reference=external_reference,
    )
    db.add(entry)
    return entry


def reserve_credits(db: Session, account: BillingAccount, run: Run) -> CreditLedgerEntry:
    amount = round(float(run.estimated_cost_usd), 2)
    if account.balance_usd < amount:
        raise InsufficientCreditsError(
            f"Insufficient credits: need ${amount:.2f}, available ${account.balance_usd:.2f}"
        )
    account.balance_usd = round(account.balance_usd - amount, 2)
    run.account_id = account.id
    run.payment_status = "reserved"
    entry = CreditLedgerEntry(
        account_id=account.id,
        run_id=run.id,
        entry_type="reserve",
        amount_usd=-amount,
        balance_after_usd=account.balance_usd,
        description=f"Reserved credits for run {run.id}",
    )
    db.add(entry)
    return entry


def settle_run_payment(db: Session, run: Run, status: str) -> None:
    if not run.account_id or run.payment_status != "reserved":
        return
    account = db.get(BillingAccount, run.account_id)
    if account is None:
        return
    if status == "completed":
        run.payment_status = "settled"
        db.add(
            CreditLedgerEntry(
                account_id=account.id,
                run_id=run.id,
                entry_type="settle",
                amount_usd=0.0,
                balance_after_usd=account.balance_usd,
                description=f"Settled completed run {run.id}",
            )
        )
    else:
        refund = round(float(run.estimated_cost_usd), 2)
        account.balance_usd = round(account.balance_usd + refund, 2)
        run.payment_status = "refunded"
        db.add(
            CreditLedgerEntry(
                account_id=account.id,
                run_id=run.id,
                entry_type="refund",
                amount_usd=refund,
                balance_after_usd=account.balance_usd,
                description=f"Refunded failed run {run.id}",
            )
        )


def create_checkout_session(
    db: Session,
    account: BillingAccount,
    amount_usd: float,
    provider: str = "mock",
) -> CheckoutSession:
    amount = round(float(amount_usd), 2)
    session = CheckoutSession(
        account_id=account.id,
        amount_usd=amount,
        provider=provider,
        status="created",
        checkout_url=f"/billing/mock-checkout?amount={amount:.2f}&account_id={account.id}",
    )
    db.add(session)
    db.commit()
    db.refresh(session)
    return session


def complete_checkout_session(db: Session, session: CheckoutSession) -> BillingAccount:
    account = db.get(BillingAccount, session.account_id)
    if account is None:
        raise ValueError("Billing account not found")
    if session.status != "completed":
        add_credits(
            db,
            account,
            session.amount_usd,
            f"Completed {session.provider} checkout {session.id}",
            external_reference=session.id,
        )
        session.status = "completed"
        db.commit()
        db.refresh(account)
    return account


def serialize_account(account: BillingAccount) -> dict:
    return {
        "id": account.id,
        "owner_email": account.owner_email,
        "display_name": account.display_name,
        "balance_usd": account.balance_usd,
        "created_at": account.created_at.isoformat(),
    }

