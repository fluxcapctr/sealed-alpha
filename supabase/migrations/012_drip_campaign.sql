-- Migration 012: Drip email campaign tables
-- Run in Supabase Dashboard SQL Editor

-- Track users for drip campaigns (accessible via PostgREST, unlike auth.users)
CREATE TABLE public.drip_subscribers (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email TEXT NOT NULL UNIQUE,
    signup_date DATE NOT NULL DEFAULT CURRENT_DATE,
    current_step INTEGER NOT NULL DEFAULT 0,
    next_send_date DATE,
    opted_out BOOLEAN DEFAULT FALSE,
    unsubscribe_token UUID DEFAULT gen_random_uuid(),
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- RLS
ALTER TABLE public.drip_subscribers ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access" ON public.drip_subscribers FOR ALL USING (true);

-- Grants
GRANT ALL ON public.drip_subscribers TO service_role;
GRANT SELECT ON public.drip_subscribers TO authenticated;

-- Drip send log (for debugging / analytics)
CREATE TABLE public.drip_log (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    subscriber_id UUID NOT NULL REFERENCES public.drip_subscribers(id) ON DELETE CASCADE,
    step INTEGER NOT NULL,
    template_key TEXT NOT NULL,
    sent_at TIMESTAMPTZ DEFAULT NOW(),
    resend_id TEXT
);

ALTER TABLE public.drip_log ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Service role full access" ON public.drip_log FOR ALL USING (true);
GRANT ALL ON public.drip_log TO service_role;
