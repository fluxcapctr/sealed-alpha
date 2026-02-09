"""
Compute buy/sell signals for all products based on price history and set lifecycle.

Signal Components (each scored -100 to +100, then weighted):
1. Price vs MA (35%): Current price vs 30d/90d moving averages
2. Momentum (20%): 30-day price change rate
3. Volatility (10%): Price stability
4. Listings Trend (15%): Supply changes
5. Sales Velocity (10%): Demand indicators
6. Set Lifecycle (10%): Print/rotation status

Usage:
    python tools/compute_signals.py
    python tools/compute_signals.py --product-id UUID
    python tools/compute_signals.py --dry-run
"""

import argparse
import asyncio
import json
import logging
import math
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from db import Database
from models import Signal, Alert

logger = logging.getLogger("compute_signals")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Signal weights
WEIGHTS = {
    "price_vs_ma": 0.35,
    "momentum": 0.20,
    "volatility": 0.10,
    "listings": 0.15,
    "sales_velocity": 0.10,
    "lifecycle": 0.10,
}


def clamp(value: float, lo: float = -100.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))


def compute_price_vs_ma_score(
    current: float | None, ma_30d: float | None, ma_90d: float | None
) -> float:
    """
    Below MA = positive (buying opportunity). Above MA = negative (overvalued).
    Scale: 20% below MA maps to +100.
    """
    if current is None:
        return 0.0

    scores = []

    if ma_30d and ma_30d > 0:
        pct_from_30d = ((current - ma_30d) / ma_30d) * 100
        scores.append(-pct_from_30d * 5)  # 20% below = +100

    if ma_90d and ma_90d > 0:
        pct_from_90d = ((current - ma_90d) / ma_90d) * 100
        scores.append(-pct_from_90d * 3)

    if not scores:
        return 0.0

    # Weight 30d more heavily
    if len(scores) == 2:
        combined = scores[0] * 0.6 + scores[1] * 0.4
    else:
        combined = scores[0]

    return clamp(combined)


def compute_momentum_score(
    current: float | None, price_30d_ago: float | None
) -> float:
    """
    Falling price = buying opportunity (positive score).
    Uses percentage change over 30 days.
    """
    if current is None or price_30d_ago is None or price_30d_ago == 0:
        return 0.0

    pct_change = ((current - price_30d_ago) / price_30d_ago) * 100

    # Negative momentum (falling price) is a buy signal for sealed products
    # because sealed products tend to appreciate over time
    score = -pct_change * 3  # 30% drop = +90 score

    return clamp(score)


def compute_volatility_score(
    volatility_30d: float | None, current: float | None
) -> float:
    """
    Lower coefficient of variation = more stable = positive.
    High volatility = risky = negative.
    """
    if volatility_30d is None or current is None or current == 0:
        return 0.0

    cv = volatility_30d / current  # Coefficient of variation

    # Low CV (< 0.05) is good, high CV (> 0.15) is bad
    if cv < 0.03:
        return 50.0
    elif cv < 0.05:
        return 25.0
    elif cv < 0.10:
        return 0.0
    elif cv < 0.15:
        return -25.0
    else:
        return -50.0


def compute_listings_score(
    current_listings: int | None, listings_7d_ago: int | None
) -> float:
    """
    Decreasing listings = supply drying up = positive.
    Increasing listings = more supply = negative.
    """
    if current_listings is None:
        return 0.0

    if listings_7d_ago is None or listings_7d_ago == 0:
        # No comparison data — neutral, but fewer listings is slightly positive
        if current_listings < 10:
            return 30.0
        elif current_listings < 30:
            return 10.0
        return 0.0

    pct_change = ((current_listings - listings_7d_ago) / listings_7d_ago) * 100

    # Decreasing listings is positive
    score = -pct_change * 3  # 30% decrease = +90

    return clamp(score)


def compute_sales_velocity_score(
    current_quantity: int | None,
    quantity_90d_ago: int | None,
    quantity_change_90d_pct: float | None,
) -> float:
    """
    Measures demand via quantity depletion over 90 days.

    Decreasing available quantity = units selling = demand = positive signal.
    Uses available_quantity (total units for sale across all sellers) from TCGPlayer.
    """
    # If we have the 90-day percentage change, use it directly
    if quantity_change_90d_pct is not None:
        # Negative change = supply shrinking = positive signal
        # -50% over 90 days → strong demand → +75 score
        # +50% over 90 days → supply flooding → -50 score
        score = -quantity_change_90d_pct * 1.5
        return clamp(score)

    # Fallback: use absolute quantity as a rough indicator
    if current_quantity is not None:
        # Very low quantity = scarce supply = positive
        if current_quantity < 20:
            return 40.0
        elif current_quantity < 100:
            return 20.0
        elif current_quantity < 500:
            return 0.0
        elif current_quantity < 2000:
            return -10.0
        else:
            return -20.0  # Abundant supply

    return 0.0


def compute_lifecycle_score(
    is_in_print: bool | None,
    is_in_rotation: bool | None,
    release_date_str: str | None,
) -> float:
    """
    Out-of-print + older = strong positive (scarcity drives value).
    Recently released + in print = slightly negative (supply still flowing).
    Approaching end of print = buy signal.
    """
    if release_date_str is None:
        return 0.0

    try:
        release = date.fromisoformat(release_date_str)
    except ValueError:
        return 0.0

    age_days = (date.today() - release).days
    score = 0.0

    # Out of print bonus
    if is_in_print is False:
        score += 40.0
        # Older out-of-print sets get bigger bonus
        if age_days > 1460:  # 4+ years
            score += 30.0
        elif age_days > 1095:  # 3+ years
            score += 20.0
        elif age_days > 730:  # 2+ years
            score += 10.0
    else:
        # In print — approaching end of print (~2 years) is a buy signal
        if age_days > 600:  # Approaching 2-year print window
            score += 20.0
        elif age_days > 365:
            score += 10.0
        elif age_days < 90:
            score -= 15.0  # Very new, supply flooding market

    # Post-rotation dip opportunity
    if is_in_rotation is False and age_days < 1000:
        # Recently rotated — potential buying opportunity during the dip
        score += 15.0

    return clamp(score)


def compute_signal(analytics: dict) -> Signal:
    """Compute the composite signal from product analytics data."""
    scores = {
        "price_vs_ma": compute_price_vs_ma_score(
            analytics.get("current_price"),
            analytics.get("ma_30d"),
            analytics.get("ma_90d"),
        ),
        "momentum": compute_momentum_score(
            analytics.get("current_price"),
            analytics.get("price_30d_ago"),
        ),
        "volatility": compute_volatility_score(
            analytics.get("volatility_30d"),
            analytics.get("current_price"),
        ),
        "listings": compute_listings_score(
            analytics.get("current_listings"),
            analytics.get("listings_7d_ago"),
        ),
        "sales_velocity": compute_sales_velocity_score(
            analytics.get("current_quantity"),
            analytics.get("quantity_90d_ago"),
            analytics.get("quantity_change_90d_pct"),
        ),
        "lifecycle": compute_lifecycle_score(
            analytics.get("is_in_print"),
            analytics.get("is_in_rotation"),
            analytics.get("release_date"),
        ),
    }

    composite = sum(scores[k] * WEIGHTS[k] for k in WEIGHTS)

    if composite >= 60:
        recommendation = "STRONG_BUY"
    elif composite >= 30:
        recommendation = "BUY"
    elif composite <= -60:
        recommendation = "STRONG_SELL"
    elif composite <= -30:
        recommendation = "SELL"
    else:
        recommendation = "HOLD"

    return Signal(
        product_id=analytics["product_id"],
        signal_date=str(date.today()),
        composite_score=round(composite, 1),
        price_vs_ma_score=round(scores["price_vs_ma"], 1),
        momentum_score=round(scores["momentum"], 1),
        volatility_score=round(scores["volatility"], 1),
        listings_score=round(scores["listings"], 1),
        sales_velocity_score=round(scores["sales_velocity"], 1),
        lifecycle_score=round(scores["lifecycle"], 1),
        recommendation=recommendation,
    )


def check_for_alerts(
    signal: Signal, prev_signal: Signal | None, analytics: dict
) -> list[Alert]:
    """Check if this signal should trigger any alerts."""
    alerts = []
    product_id = signal.product_id

    # Signal threshold crossing
    if prev_signal:
        prev_rec = prev_signal.recommendation
        new_rec = signal.recommendation

        if prev_rec == "HOLD" and new_rec in ("BUY", "STRONG_BUY"):
            alerts.append(Alert(
                product_id=product_id,
                alert_type="buy" if new_rec == "BUY" else "strong_buy",
                message=f"{analytics.get('product_name', '?')} crossed from Hold to {new_rec} (score: {signal.composite_score})",
                signal_score=signal.composite_score,
            ))
        elif prev_rec == "HOLD" and new_rec in ("SELL", "STRONG_SELL"):
            alerts.append(Alert(
                product_id=product_id,
                alert_type="sell" if new_rec == "SELL" else "strong_sell",
                message=f"{analytics.get('product_name', '?')} crossed from Hold to {new_rec} (score: {signal.composite_score})",
                signal_score=signal.composite_score,
            ))

    # Price drop alert (>10% in last 7 days)
    pct_7d = analytics.get("price_change_7d_pct")
    if pct_7d is not None and pct_7d < -10:
        alerts.append(Alert(
            product_id=product_id,
            alert_type="price_drop",
            message=f"{analytics.get('product_name', '?')} dropped {pct_7d:.1f}% in 7 days",
            signal_score=signal.composite_score,
        ))

    # Price spike alert (>15% in last 7 days)
    if pct_7d is not None and pct_7d > 15:
        alerts.append(Alert(
            product_id=product_id,
            alert_type="price_spike",
            message=f"{analytics.get('product_name', '?')} spiked +{pct_7d:.1f}% in 7 days",
            signal_score=signal.composite_score,
        ))

    return alerts


def main():
    parser = argparse.ArgumentParser(description="Compute buy/sell signals")
    parser.add_argument("--product-id", help="Compute for a specific product")
    parser.add_argument("--dry-run", action="store_true", help="Print signals without saving")
    args = parser.parse_args()

    config = Config()
    db = Database(config)

    # Get product analytics
    analytics_list = db.get_product_analytics(product_id=args.product_id)

    if not analytics_list:
        logger.info("No product analytics data available. Run the scraper first.")
        return

    logger.info(f"Computing signals for {len(analytics_list)} products...")

    results = {"computed": 0, "alerts_created": 0}
    all_signals = []

    for analytics in analytics_list:
        # Skip products with no price data
        if analytics.get("current_price") is None:
            continue

        signal = compute_signal(analytics)
        all_signals.append(signal)

        if args.dry_run:
            logger.info(
                f"  {analytics.get('product_name', '?')}: "
                f"score={signal.composite_score:+.1f} → {signal.recommendation}"
            )
            results["computed"] += 1
            continue

        # Get previous signal for alert comparison
        prev_signals = db.get_latest_signals(limit=1)
        prev = None
        for ps in prev_signals:
            if ps.get("product_id") == signal.product_id:
                prev = Signal(
                    product_id=ps["product_id"],
                    recommendation=ps.get("recommendation", "HOLD"),
                    composite_score=ps.get("composite_score", 0),
                )
                break

        # Save signal
        db.upsert_signal(signal)
        results["computed"] += 1

        # Check for alerts
        alerts = check_for_alerts(signal, prev, analytics)
        for alert in alerts:
            db.create_alert(alert)
            results["alerts_created"] += 1
            logger.info(f"  ALERT: {alert.message}")

        logger.info(
            f"  {analytics.get('product_name', '?')}: "
            f"score={signal.composite_score:+.1f} → {signal.recommendation}"
        )

    # Save results summary
    output = {
        "date": str(date.today()),
        "total_analytics": len(analytics_list),
        **results,
        "signal_distribution": {
            "STRONG_BUY": sum(1 for s in all_signals if s.recommendation == "STRONG_BUY"),
            "BUY": sum(1 for s in all_signals if s.recommendation == "BUY"),
            "HOLD": sum(1 for s in all_signals if s.recommendation == "HOLD"),
            "SELL": sum(1 for s in all_signals if s.recommendation == "SELL"),
            "STRONG_SELL": sum(1 for s in all_signals if s.recommendation == "STRONG_SELL"),
        },
    }
    output_path = config.tmp_dir / "compute_signals_results.json"
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    logger.info(f"Done! {results['computed']} signals computed, {results['alerts_created']} alerts created")


if __name__ == "__main__":
    main()
