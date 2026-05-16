from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.models import CheckoutSession, CreditLedgerEntry
from app.db.session import get_db
from app.services.billing_service import (
    DEMO_ACCOUNT_EMAIL,
    complete_checkout_session,
    create_checkout_session,
    get_or_create_account,
    serialize_account,
)

router = APIRouter(prefix="/billing", tags=["billing"])


class CheckoutCreate(BaseModel):
    amount_usd: float
    owner_email: str = DEMO_ACCOUNT_EMAIL
    provider: str = "mock"


@router.get("/account")
def get_account(owner_email: str = DEMO_ACCOUNT_EMAIL, db: Session = Depends(get_db)) -> dict:
    account = get_or_create_account(db, owner_email=owner_email)
    return {"account": serialize_account(account)}


@router.get("/ledger")
def get_ledger(owner_email: str = DEMO_ACCOUNT_EMAIL, db: Session = Depends(get_db)) -> dict:
    account = get_or_create_account(db, owner_email=owner_email)
    entries = (
        db.query(CreditLedgerEntry)
        .filter(CreditLedgerEntry.account_id == account.id)
        .order_by(CreditLedgerEntry.created_at.desc())
        .all()
    )
    return {
        "account": serialize_account(account),
        "entries": [
            {
                "id": entry.id,
                "run_id": entry.run_id,
                "entry_type": entry.entry_type,
                "amount_usd": entry.amount_usd,
                "balance_after_usd": entry.balance_after_usd,
                "description": entry.description,
                "created_at": entry.created_at.isoformat(),
            }
            for entry in entries
        ],
    }


@router.post("/checkout")
def create_checkout(payload: CheckoutCreate, db: Session = Depends(get_db)) -> dict:
    if payload.amount_usd <= 0:
        raise HTTPException(status_code=400, detail="amount_usd must be positive")
    account = get_or_create_account(db, owner_email=payload.owner_email)
    session = create_checkout_session(db, account, payload.amount_usd, provider=payload.provider)
    return {
        "checkout_session": {
            "id": session.id,
            "amount_usd": session.amount_usd,
            "provider": session.provider,
            "status": session.status,
            "checkout_url": session.checkout_url,
        }
    }


@router.post("/checkout/{session_id}/complete")
def complete_checkout(session_id: str, db: Session = Depends(get_db)) -> dict:
    session = db.get(CheckoutSession, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Checkout session not found")
    account = complete_checkout_session(db, session)
    return {"account": serialize_account(account)}

