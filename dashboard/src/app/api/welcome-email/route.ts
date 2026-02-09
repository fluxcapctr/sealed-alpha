import { Resend } from "resend";
import { NextResponse } from "next/server";

const resend = new Resend(process.env.RESEND_API_KEY);

export async function POST(request: Request) {
  try {
    const { email } = await request.json();

    if (!email) {
      return NextResponse.json({ error: "Email required" }, { status: 400 });
    }

    // Skip if no API key configured (dev mode)
    if (!process.env.RESEND_API_KEY) {
      console.log(`[Welcome Email] Would send to ${email} (no API key)`);
      return NextResponse.json({ success: true, skipped: true });
    }

    const { error } = await resend.emails.send({
      from: "Sealed Alpha <onboarding@resend.dev>",
      to: email,
      subject: "Welcome to Sealed Alpha - Pokemon TCG Investment Tracker",
      html: `
        <div style="font-family: sans-serif; max-width: 500px; margin: 0 auto; padding: 20px;">
          <h1 style="font-size: 24px; margin-bottom: 16px;">Welcome to Sealed Alpha!</h1>
          <p style="color: #666; line-height: 1.6;">
            You now have full access to the Pokemon TCG sealed product investment tracker.
          </p>
          <p style="color: #666; line-height: 1.6;">Here's what you can do:</p>
          <ul style="color: #666; line-height: 1.8;">
            <li>Track 800+ sealed products across 80+ sets</li>
            <li>View buy/sell signals powered by 6 market indicators</li>
            <li>Analyze rip scores and expected value for booster boxes</li>
            <li>Monitor supply depletion and price trends</li>
            <li>Compare product lifecycles across eras</li>
          </ul>
          <p style="color: #999; font-size: 12px; margin-top: 32px;">
            Data sourced from TCGPlayer. Not financial advice.
          </p>
        </div>
      `,
    });

    if (error) {
      console.error("[Welcome Email] Error:", error);
      return NextResponse.json({ error: error.message }, { status: 500 });
    }

    return NextResponse.json({ success: true });
  } catch (err) {
    console.error("[Welcome Email] Unexpected error:", err);
    return NextResponse.json(
      { error: "Internal server error" },
      { status: 500 }
    );
  }
}
