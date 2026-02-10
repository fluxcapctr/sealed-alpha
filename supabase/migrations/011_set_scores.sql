-- Migration 011: Set Investibility Scores
-- Run in Supabase Dashboard SQL Editor

CREATE TABLE public.set_scores (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    set_id UUID NOT NULL REFERENCES public.sets(id) ON DELETE CASCADE,
    overall_grade TEXT NOT NULL CHECK (overall_grade IN ('S', 'A', 'B', 'C', 'D', 'F')),
    chase_card_score INTEGER NOT NULL CHECK (chase_card_score BETWEEN 1 AND 10),
    art_quality_score INTEGER NOT NULL CHECK (art_quality_score BETWEEN 1 AND 10),
    nostalgia_score INTEGER NOT NULL CHECK (nostalgia_score BETWEEN 1 AND 10),
    fun_factor_score INTEGER NOT NULL CHECK (fun_factor_score BETWEEN 1 AND 10),
    scarcity_score INTEGER NOT NULL CHECK (scarcity_score BETWEEN 1 AND 10),
    set_depth_score INTEGER NOT NULL CHECK (set_depth_score BETWEEN 1 AND 10),
    chase_card_name TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(set_id)
);

-- RLS
ALTER TABLE public.set_scores ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anon read" ON public.set_scores FOR SELECT USING (true);

-- Grant access
GRANT SELECT ON public.set_scores TO anon;
GRANT SELECT ON public.set_scores TO authenticated;
