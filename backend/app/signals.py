from __future__ import annotations

from difflib import SequenceMatcher

from app.models import CaseContext, SignalCheck


RISKY_MERCHANT_CATEGORIES = {
    "atm",
    "gas_station",
    "money_transfer",
    "nightlife",
    "pawn_shop",
    "wire_transfer",
}


def normalize(value: str) -> str:
    return "".join(char.lower() for char in value if char.isalnum())


def merchant_similarity(a: str, b: str) -> float:
    return SequenceMatcher(None, normalize(a), normalize(b)).ratio()


def merchant_match_signal(context: CaseContext) -> SignalCheck:
    txn = context.transaction
    best_name = ""
    best_score = 0.0
    amount_delta: float | None = None

    for known in context.known_merchants:
        names = [known.merchant_name, *known.aliases]
        for name in names:
            score = merchant_similarity(txn.merchant_name, name)
            if score > best_score:
                best_score = score
                best_name = known.merchant_name
                if known.typical_amount is not None:
                    amount_delta = abs(txn.amount - known.typical_amount)

    if best_score >= 0.9:
        if amount_delta is not None and amount_delta > max(5, txn.amount * 0.2):
            return SignalCheck(
                id="merchant_match",
                label="Merchant match",
                status="partial",
                fired=True,
                detail=f"Merchant resembles {best_name}, but the amount differs from the known pattern.",
                weight=1,
            )
        return SignalCheck(
            id="merchant_match",
            label="Merchant match",
            status="match",
            fired=True,
            detail=f"Merchant strongly matches known merchant {best_name}.",
            weight=-3,
        )

    if best_score >= 0.72:
        return SignalCheck(
            id="merchant_match",
            label="Merchant match",
            status="partial",
            fired=True,
            detail=f"Merchant partially matches known merchant {best_name}.",
            weight=0,
        )

    return SignalCheck(
        id="merchant_match",
        label="Merchant match",
        status="unknown",
        fired=False,
        detail="Merchant does not strongly match the customer's known transaction context.",
        weight=1,
    )


def merchant_category_signal(context: CaseContext) -> SignalCheck:
    category = normalize(context.transaction.merchant_category)
    risk = category in {normalize(item) for item in RISKY_MERCHANT_CATEGORIES}
    return SignalCheck(
        id="merchant_category_risk",
        label="Merchant category risk",
        status="risk" if risk else "clear",
        fired=risk,
        detail=(
            f"{context.transaction.merchant_category} is on the explicit risk category list."
            if risk
            else f"{context.transaction.merchant_category} is not on the explicit risk category list."
        ),
        weight=2 if risk else 0,
    )


def lost_or_stolen_signal(context: CaseContext) -> SignalCheck:
    reported = context.card_status.lost_or_stolen_reported
    return SignalCheck(
        id="lost_or_stolen_card",
        label="Lost or stolen card report",
        status="risk" if reported else "clear",
        fired=reported,
        detail=(
            "A recent lost or stolen card report exists."
            if reported
            else "No lost or stolen card report is present."
        ),
        weight=4 if reported else 0,
    )


def cluster_signal(context: CaseContext) -> SignalCheck:
    known_names = [
        name
        for known in context.known_merchants
        for name in [known.merchant_name, *known.aliases]
    ]
    unfamiliar = 0
    for charge in context.recent_charges:
        best = max((merchant_similarity(charge.merchant_name, known) for known in known_names), default=0)
        if best < 0.72:
            unfamiliar += 1

    fired = unfamiliar >= 3
    return SignalCheck(
        id="cluster_unfamiliar_charges",
        label="Cluster of unfamiliar charges",
        status="risk" if fired else "clear",
        fired=fired,
        detail=(
            f"{unfamiliar} unfamiliar recent charges were found."
            if fired
            else f"{unfamiliar} unfamiliar recent charges were found, below the escalation threshold."
        ),
        weight=3 if fired else 0,
    )


def cross_border_signal(context: CaseContext) -> SignalCheck:
    fired = normalize(context.transaction.country) != normalize(context.home_country)
    return SignalCheck(
        id="cross_border",
        label="Cross-border transaction",
        status="risk" if fired else "clear",
        fired=fired,
        detail=(
            f"Transaction country {context.transaction.country} differs from home country {context.home_country}."
            if fired
            else "Transaction country matches the customer's home country."
        ),
        weight=1 if fired else 0,
    )


def recurring_signal(context: CaseContext) -> SignalCheck:
    recurring = context.transaction.recurring
    return SignalCheck(
        id="recurring_or_one_time",
        label="Recurring versus one-time",
        status="match" if recurring else "unknown",
        fired=recurring,
        detail=(
            "Transaction is marked as recurring."
            if recurring
            else "Transaction is marked as one-time."
        ),
        weight=-1 if recurring else 0,
    )


def currency_signal(context: CaseContext) -> SignalCheck:
    fired = normalize(context.transaction.currency) != normalize(context.account_currency)
    return SignalCheck(
        id="currency",
        label="Currency",
        status="risk" if fired else "clear",
        fired=fired,
        detail=(
            f"Transaction currency {context.transaction.currency} differs from account currency {context.account_currency}."
            if fired
            else "Transaction currency matches the account currency."
        ),
        weight=1 if fired else 0,
    )


def evaluate_signals(context: CaseContext) -> list[SignalCheck]:
    return [
        merchant_match_signal(context),
        merchant_category_signal(context),
        lost_or_stolen_signal(context),
        cluster_signal(context),
        cross_border_signal(context),
        recurring_signal(context),
        currency_signal(context),
    ]

