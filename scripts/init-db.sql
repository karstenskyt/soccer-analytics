-- Soccer Analytics Database Schema
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

CREATE TABLE IF NOT EXISTS session_plans (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    category TEXT,
    difficulty TEXT,
    author TEXT,
    source_filename TEXT NOT NULL,
    source_page_count INTEGER,
    extraction_timestamp TIMESTAMPTZ DEFAULT NOW(),
    raw_json JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS drill_blocks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    session_plan_id UUID NOT NULL REFERENCES session_plans(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    setup_description TEXT,
    player_count TEXT,
    equipment TEXT[],
    area_dimensions TEXT,
    sequence TEXT[],
    rules TEXT[],
    scoring TEXT[],
    coaching_points TEXT[],
    progressions TEXT[],
    vlm_description TEXT,
    image_ref TEXT,
    raw_json JSONB NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS tactical_contexts (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    drill_block_id UUID NOT NULL REFERENCES drill_blocks(id) ON DELETE CASCADE,
    methodology TEXT,
    game_element TEXT,
    lanes TEXT[],
    situation_type TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_session_plans_title ON session_plans(title);
CREATE INDEX IF NOT EXISTS idx_session_plans_category ON session_plans(category);
CREATE INDEX IF NOT EXISTS idx_drill_blocks_session ON drill_blocks(session_plan_id);
CREATE INDEX IF NOT EXISTS idx_tactical_contexts_drill ON tactical_contexts(drill_block_id);
CREATE INDEX IF NOT EXISTS idx_tactical_contexts_methodology ON tactical_contexts(methodology);
