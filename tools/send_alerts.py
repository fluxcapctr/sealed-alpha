"""
Send email alerts for pending signals via Resend.

Usage:
    python tools/send_alerts.py
    python tools/send_alerts.py --dry-run
"""

import argparse
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from db import Database

logger = logging.getLogger("send_alerts")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")


def render_alert_email(alerts: list[dict]) -> str:
    """Render alerts into an HTML email body."""
    rows = ""
    for alert in alerts:
        product = alert.get("products", {}) or {}
        product_name = product.get("name", "Unknown Product")
        rows += f"""
        <tr>
            <td style="padding: 8px; border-bottom: 1px solid #333;">{product_name}</td>
            <td style="padding: 8px; border-bottom: 1px solid #333;">{alert['alert_type'].replace('_', ' ').title()}</td>
            <td style="padding: 8px; border-bottom: 1px solid #333;">{alert.get('message', '')}</td>
            <td style="padding: 8px; border-bottom: 1px solid #333;">{alert.get('signal_score', '--')}</td>
        </tr>
        """

    return f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #0a0a0f; color: #e5e5e5; padding: 20px;">
        <div style="max-width: 600px; margin: 0 auto;">
            <h1 style="color: #fbbf24; font-size: 20px;">Pokemon TCG Alert</h1>
            <p style="color: #a3a3a3;">{len(alerts)} new signal(s) detected</p>
            <table style="width: 100%; border-collapse: collapse; margin-top: 16px;">
                <thead>
                    <tr style="color: #a3a3a3; text-align: left;">
                        <th style="padding: 8px; border-bottom: 2px solid #333;">Product</th>
                        <th style="padding: 8px; border-bottom: 2px solid #333;">Type</th>
                        <th style="padding: 8px; border-bottom: 2px solid #333;">Message</th>
                        <th style="padding: 8px; border-bottom: 2px solid #333;">Score</th>
                    </tr>
                </thead>
                <tbody>
                    {rows}
                </tbody>
            </table>
            <p style="color: #525252; font-size: 12px; margin-top: 24px;">
                Sent by Pokemon TCG Sealed Tracker
            </p>
        </div>
    </body>
    </html>
    """


def send_alerts(db: Database, config: Config, dry_run: bool = False) -> dict:
    """Send pending alerts via email."""
    pending = db.get_pending_alerts()

    if not pending:
        logger.info("No pending alerts to send")
        return {"sent": 0}

    logger.info(f"Found {len(pending)} pending alerts")

    if dry_run:
        for alert in pending:
            product = alert.get("products", {}) or {}
            logger.info(
                f"  [DRY RUN] {alert['alert_type']}: "
                f"{product.get('name', '?')} — {alert.get('message', '')}"
            )
        return {"sent": 0, "pending": len(pending)}

    if not config.resend_api_key or not config.alert_email:
        logger.warning("Resend API key or alert email not configured. Skipping send.")
        return {"sent": 0, "error": "Missing RESEND_API_KEY or ALERT_EMAIL in .env"}

    import resend

    html = render_alert_email(pending)

    try:
        resend.api_key = config.resend_api_key
        resend.Emails.send({
            "from": "Pokemon Tracker <alerts@yourdomain.com>",
            "to": config.alert_email,
            "subject": f"Pokemon TCG Alert: {len(pending)} new signal(s)",
            "html": html,
        })

        for alert in pending:
            db.mark_alert_sent(alert["id"])

        logger.info(f"Sent alert email with {len(pending)} alerts to {config.alert_email}")
        return {"sent": len(pending)}

    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return {"sent": 0, "error": str(e)}


def main():
    parser = argparse.ArgumentParser(description="Send alert emails")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    config = Config()
    db = Database(config)
    result = send_alerts(db, config, dry_run=args.dry_run)

    output_path = config.tmp_dir / "send_alerts_results.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()
