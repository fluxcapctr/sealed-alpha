"""
Send drip campaign emails to subscribers.

Usage:
    python tools/send_drip_emails.py
    python tools/send_drip_emails.py --dry-run
    python tools/send_drip_emails.py --email user@example.com
    python tools/send_drip_emails.py --step 3
"""

import argparse
import json
import logging
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import Config
from db import Database

logger = logging.getLogger("drip_emails")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# Days to wait after each step before sending the next
DRIP_SCHEDULE: dict[int, int | None] = {
    1: 3,    # After welcome, wait 3 days for step 2
    2: 4,    # After step 2, wait 4 days for step 3
    3: 4,    # After step 3, wait 4 days for step 4
    4: 4,    # After step 4, wait 4 days for step 5
    5: 7,    # After step 5, wait 7 days for step 6
    6: None, # Sequence complete
}

STEP_TEMPLATES: dict[int, dict] = {
    1: {
        "key": "welcome",
        "subject": "Welcome to Sealed Alpha - Your Pokemon TCG Edge",
    },
    2: {
        "key": "when_to_rip",
        "subject": "When to rip a set (and when to hold sealed)",
    },
    3: {
        "key": "sealed_vs_singles",
        "subject": "Why sealed beats singles for ROI",
    },
    4: {
        "key": "wholesale_intro",
        "subject": "How I source Pokemon cards below market",
    },
    5: {
        "key": "wholesale_offer",
        "subject": "Exclusive pricing for Sealed Alpha users",
    },
    6: {
        "key": "social_proof",
        "subject": "What Sealed Alpha users are buying",
    },
}

TOTAL_STEPS = 6


def email_wrapper(body: str, unsubscribe_url: str) -> str:
    """Wrap email body in the dark-themed shell with header and footer."""
    return f"""
    <html>
    <body style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0f; color: #e5e5e5; padding: 0; margin: 0;">
        <div style="max-width: 560px; margin: 0 auto; padding: 32px 20px;">
            <div style="margin-bottom: 24px;">
                <span style="font-size: 20px; font-weight: 700; color: #f59e0b;">Sealed Alpha</span>
                <span style="color: #525252; font-size: 14px; margin-left: 8px;">Pokemon TCG Analytics</span>
            </div>
            {body}
            <div style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #262626;">
                <p style="color: #525252; font-size: 11px; line-height: 1.5;">
                    You're receiving this because you signed up for Sealed Alpha.<br>
                    <a href="{unsubscribe_url}" style="color: #525252; text-decoration: underline;">Unsubscribe</a>
                </p>
            </div>
        </div>
    </body>
    </html>
    """


def cta_button(text: str, url: str, color: str = "#f59e0b") -> str:
    """Render a CTA button."""
    return f"""
    <div style="margin: 24px 0;">
        <a href="{url}" style="display: inline-block; padding: 12px 28px; background: {color}; color: #0a0a0f; font-weight: 700; font-size: 14px; text-decoration: none; border-radius: 6px;">{text}</a>
    </div>
    """


def render_template(step: int, config: Config, unsubscribe_url: str) -> str:
    """Render the HTML email for a given step."""
    site = "https://sealedalpha.com"
    wholesale = config.wholesale_url

    if step == 1:
        body = f"""
        <h1 style="font-size: 22px; color: #f5f5f5; margin-bottom: 16px;">Welcome to Sealed Alpha!</h1>
        <p style="color: #a3a3a3; line-height: 1.7; font-size: 15px;">
            You now have access to the most comprehensive Pokemon TCG sealed product tracker on the market.
        </p>
        <p style="color: #a3a3a3; line-height: 1.7; font-size: 15px;">Here's what you can do right now:</p>
        <ul style="color: #a3a3a3; line-height: 2; font-size: 15px; padding-left: 20px;">
            <li><strong style="color: #e5e5e5;">Rip Scores</strong> — See the expected value of ripping any booster box</li>
            <li><strong style="color: #e5e5e5;">Supply Tracking</strong> — Watch inventory deplete in real time</li>
            <li><strong style="color: #e5e5e5;">Set Grades</strong> — Our investibility scores rank every set S through F</li>
            <li><strong style="color: #e5e5e5;">Price History</strong> — 2+ years of market data across 800+ products</li>
        </ul>
        {cta_button("Explore the Dashboard", site)}
        <p style="color: #525252; font-size: 12px;">Data sourced from TCGPlayer. Not financial advice.</p>
        """

    elif step == 2:
        body = f"""
        <h1 style="font-size: 22px; color: #f5f5f5; margin-bottom: 16px;">When to Rip a Set (and When to Hold Sealed)</h1>
        <p style="color: #a3a3a3; line-height: 1.7; font-size: 15px;">
            Every booster box has a hidden number: its <strong style="color: #e5e5e5;">Expected Value (EV)</strong>. This is the average dollar value of cards you'd pull if you opened it.
        </p>
        <p style="color: #a3a3a3; line-height: 1.7; font-size: 15px;">
            On Sealed Alpha, we calculate the <strong style="color: #e5e5e5;">Rip Score</strong> for every set: EV divided by box price.
        </p>
        <ul style="color: #a3a3a3; line-height: 2; font-size: 15px; padding-left: 20px;">
            <li><strong style="color: #22c55e;">Rip Score &gt; 1.0</strong> = Positive EV. You'd profit on average by ripping.</li>
            <li><strong style="color: #f59e0b;">Rip Score 0.5 - 1.0</strong> = Borderline. Hold sealed unless you enjoy the gamble.</li>
            <li><strong style="color: #ef4444;">Rip Score &lt; 0.5</strong> = Hold sealed. The box is worth more closed.</li>
        </ul>
        <p style="color: #a3a3a3; line-height: 1.7; font-size: 15px;">
            Sets like <strong style="color: #e5e5e5;">Evolving Skies</strong> and <strong style="color: #e5e5e5;">151</strong> have incredible chase cards that keep their EV high. Other sets crater once the hype dies.
        </p>
        <p style="color: #a3a3a3; line-height: 1.7; font-size: 15px;">
            Check the Rip Score on any set's detail page to decide: rip or hold?
        </p>
        {cta_button("Check Rip Scores", site + "/analytics")}
        """

    elif step == 3:
        body = f"""
        <h1 style="font-size: 22px; color: #f5f5f5; margin-bottom: 16px;">Why Sealed Beats Singles for ROI</h1>
        <p style="color: #a3a3a3; line-height: 1.7; font-size: 15px;">
            Here's something most collectors don't realize: <strong style="color: #e5e5e5;">sealed product almost always appreciates. Singles almost never do.</strong>
        </p>
        <p style="color: #a3a3a3; line-height: 1.7; font-size: 15px;">
            Why? Supply dynamics. Every box that gets opened removes one sealed unit from the market forever. But the cards inside? They flood the singles market and drive prices down.
        </p>
        <p style="color: #a3a3a3; line-height: 1.7; font-size: 15px;">
            Look at any Sword & Shield era booster box on Sealed Alpha. Most are 2-3x their original retail price now, while the chase singles from those sets have dropped.
        </p>
        <p style="color: #a3a3a3; line-height: 1.7; font-size: 15px;">
            The formula is simple:
        </p>
        <ul style="color: #a3a3a3; line-height: 2; font-size: 15px; padding-left: 20px;">
            <li>Buy sealed at or near retail</li>
            <li>Hold while the set goes out of print</li>
            <li>Supply dries up, price goes up</li>
        </ul>
        <p style="color: #a3a3a3; line-height: 1.7; font-size: 15px;">
            Use the <strong style="color: #e5e5e5;">Lifecycle Comparison</strong> chart on Sealed Alpha to see this pattern play out across eras.
        </p>
        {cta_button("Compare Product Lifecycles", site + "/analytics")}
        """

    elif step == 4:
        body = f"""
        <h1 style="font-size: 22px; color: #f5f5f5; margin-bottom: 16px;">How I Source Pokemon Cards Below Market</h1>
        <p style="color: #a3a3a3; line-height: 1.7; font-size: 15px;">
            I built Sealed Alpha because I needed better data for my own Pokemon TCG business: <strong style="color: #f59e0b;">Kitakami Cards</strong>.
        </p>
        <p style="color: #a3a3a3; line-height: 1.7; font-size: 15px;">
            I work directly with distributors to source sealed product at wholesale prices — below what you'd pay on TCGPlayer, eBay, or your local card shop.
        </p>
        <p style="color: #a3a3a3; line-height: 1.7; font-size: 15px;">
            Whether you're looking for:
        </p>
        <ul style="color: #a3a3a3; line-height: 2; font-size: 15px; padding-left: 20px;">
            <li>Booster boxes at distributor pricing</li>
            <li>ETBs and collection boxes in bulk</li>
            <li>Japanese product at competitive rates</li>
            <li>Cases for maximum savings</li>
        </ul>
        <p style="color: #a3a3a3; line-height: 1.7; font-size: 15px;">
            Kitakami Cards has you covered. I'll be sharing exclusive pricing for Sealed Alpha users in the next email.
        </p>
        {cta_button("Check Out Kitakami Cards", wholesale)}
        """

    elif step == 5:
        body = f"""
        <h1 style="font-size: 22px; color: #f5f5f5; margin-bottom: 16px;">Exclusive Pricing for Sealed Alpha Users</h1>
        <p style="color: #a3a3a3; line-height: 1.7; font-size: 15px;">
            As a Sealed Alpha user, you already have the best data on which sets to invest in. Now here's how to get them at the best price.
        </p>
        <p style="color: #a3a3a3; line-height: 1.7; font-size: 15px;">
            <strong style="color: #f59e0b;">Kitakami Cards</strong> offers wholesale pricing on Pokemon TCG sealed product — shipped directly to you.
        </p>
        <p style="color: #a3a3a3; line-height: 1.7; font-size: 15px;">
            No middlemen. No inflated marketplace fees. Just distributor-level pricing passed on to you.
        </p>
        <div style="background: #1a1a2e; border: 1px solid #262626; border-radius: 8px; padding: 20px; margin: 20px 0;">
            <p style="color: #f59e0b; font-weight: 700; font-size: 14px; margin: 0 0 8px 0;">WHY KITAKAMI CARDS?</p>
            <ul style="color: #a3a3a3; line-height: 2; font-size: 14px; padding-left: 20px; margin: 0;">
                <li>Below-market pricing on modern sets</li>
                <li>Both English and Japanese product</li>
                <li>Reliable shipping and packaging</li>
                <li>Same data-driven approach as Sealed Alpha</li>
            </ul>
        </div>
        {cta_button("Browse Wholesale Products", wholesale)}
        """

    elif step == 6:
        body = f"""
        <h1 style="font-size: 22px; color: #f5f5f5; margin-bottom: 16px;">What Sealed Alpha Users Are Buying</h1>
        <p style="color: #a3a3a3; line-height: 1.7; font-size: 15px;">
            Quick update from Kitakami Cards — here's what the community has been picking up recently:
        </p>
        <ul style="color: #a3a3a3; line-height: 2; font-size: 15px; padding-left: 20px;">
            <li>Scarlet & Violet era booster boxes continue to be the most popular pick</li>
            <li>Japanese booster boxes have been flying off the shelves</li>
            <li>Sword & Shield era sealed is getting harder to source as supply dries up</li>
        </ul>
        <p style="color: #a3a3a3; line-height: 1.7; font-size: 15px;">
            If there's a specific set you're watching on Sealed Alpha, reach out — I can usually source it at a better price than what's listed on TCGPlayer.
        </p>
        {cta_button("Shop Kitakami Cards", wholesale)}
        <p style="color: #525252; font-size: 13px; margin-top: 16px;">
            This is the last scheduled email in this series. Keep using Sealed Alpha to track the market — and check Kitakami Cards whenever you're ready to buy.
        </p>
        """

    else:
        body = "<p>Unknown email step.</p>"

    return email_wrapper(body, unsubscribe_url)


def send_drip_emails(db: Database, config: Config, dry_run: bool = False,
                     target_email: str | None = None, force_step: int | None = None) -> dict:
    """Send due drip emails to subscribers."""
    today = date.today()
    today_str = today.isoformat()

    # Query due subscribers
    query = db.client.table("drip_subscribers").select("*").eq("opted_out", False)
    if target_email:
        query = query.eq("email", target_email)
    else:
        query = query.lte("next_send_date", today_str).lt("current_step", TOTAL_STEPS)

    subscribers = query.execute().data or []

    if not subscribers:
        logger.info("No drip emails due today")
        return {"sent": 0}

    logger.info(f"Found {len(subscribers)} subscriber(s) due for drip emails")

    if not config.resend_api_key:
        logger.warning("No RESEND_API_KEY configured. Skipping send.")
        return {"sent": 0, "error": "Missing RESEND_API_KEY"}

    import resend
    resend.api_key = config.resend_api_key

    results = {"sent": 0, "failed": 0, "by_step": {}}
    site_url = "https://sealedalpha.com"

    for sub in subscribers:
        next_step = force_step if force_step else sub["current_step"] + 1

        if next_step > TOTAL_STEPS:
            continue

        template_info = STEP_TEMPLATES.get(next_step)
        if not template_info:
            continue

        unsubscribe_url = f"{site_url}/api/unsubscribe?token={sub['unsubscribe_token']}"
        html = render_template(next_step, config, unsubscribe_url)

        if dry_run:
            logger.info(f"  [DRY RUN] Step {next_step} ({template_info['key']}) → {sub['email']}")
            results["sent"] += 1
            continue

        try:
            resp = resend.Emails.send({
                "from": f"Sealed Alpha <{config.drip_sender_email}>",
                "to": sub["email"],
                "subject": template_info["subject"],
                "html": html,
            })
            resend_id = resp.get("id") if isinstance(resp, dict) else str(resp)

            # Log the send
            db.client.table("drip_log").insert({
                "subscriber_id": sub["id"],
                "step": next_step,
                "template_key": template_info["key"],
                "resend_id": resend_id,
            }).execute()

            # Update subscriber state
            delay = DRIP_SCHEDULE.get(next_step)
            next_date = (today + timedelta(days=delay)).isoformat() if delay else None

            db.client.table("drip_subscribers").update({
                "current_step": next_step,
                "next_send_date": next_date,
                "updated_at": today_str,
            }).eq("id", sub["id"]).execute()

            results["sent"] += 1
            step_key = str(next_step)
            results["by_step"][step_key] = results["by_step"].get(step_key, 0) + 1
            logger.info(f"  Sent step {next_step} ({template_info['key']}) → {sub['email']}")

        except Exception as e:
            results["failed"] += 1
            logger.error(f"  Failed step {next_step} → {sub['email']}: {e}")

    logger.info(f"Drip complete: {results['sent']} sent, {results.get('failed', 0)} failed")
    if results["by_step"]:
        logger.info(f"  By step: {results['by_step']}")
    return results


def main():
    parser = argparse.ArgumentParser(description="Send drip campaign emails")
    parser.add_argument("--dry-run", action="store_true", help="Preview without sending")
    parser.add_argument("--email", type=str, help="Send to specific email only")
    parser.add_argument("--step", type=int, help="Force a specific step number")
    args = parser.parse_args()

    config = Config()
    db = Database(config)

    result = send_drip_emails(
        db, config,
        dry_run=args.dry_run,
        target_email=args.email,
        force_step=args.step,
    )

    output_path = config.tmp_dir / "drip_results.json"
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)


if __name__ == "__main__":
    main()
