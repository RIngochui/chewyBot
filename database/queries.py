"""
chewyBot SQL statements.

ALL SQL lives here — zero SQL string literals anywhere else in the codebase.
This is the single source of truth for every DDL and DML statement.
"""

# ------------------------------------------------------------------ #
# DDL — Table creation (idempotent, safe to run on every startup)     #
# ------------------------------------------------------------------ #

CREATE_TABLES_SQL: list[str] = [
    # --- Raw ingest from The Odds API ---
    """
    CREATE TABLE IF NOT EXISTS odds_snapshots (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id        TEXT NOT NULL,
        market_key      TEXT NOT NULL,
        book_name       TEXT NOT NULL,
        sport           TEXT NOT NULL,
        decimal_odds    REAL NOT NULL,
        american_odds   INTEGER NOT NULL,
        selection_name  TEXT NOT NULL,
        fetched_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,

    # --- Normalized canonical odds records ---
    """
    CREATE TABLE IF NOT EXISTS normalized_odds (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        event_id        TEXT NOT NULL,
        market_key      TEXT NOT NULL,
        sport           TEXT NOT NULL,
        league          TEXT NOT NULL,
        event_name      TEXT NOT NULL,
        home_team       TEXT NOT NULL,
        away_team       TEXT NOT NULL,
        start_time      TIMESTAMP NOT NULL,
        market_type     TEXT NOT NULL,
        selection_name  TEXT NOT NULL,
        line_value      REAL,
        decimal_odds    REAL NOT NULL,
        american_odds   INTEGER NOT NULL,
        book_name       TEXT NOT NULL,
        fetched_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,

    # --- Detected arbitrage opportunities ---
    """
    CREATE TABLE IF NOT EXISTS arb_signals (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        market_key       TEXT NOT NULL,
        event_name       TEXT NOT NULL,
        sport            TEXT NOT NULL,
        market_type      TEXT NOT NULL,
        arb_pct          REAL NOT NULL,
        stake_side_a     REAL NOT NULL,
        stake_side_b     REAL NOT NULL,
        estimated_profit REAL NOT NULL,
        book_a           TEXT NOT NULL,
        book_b           TEXT NOT NULL,
        odds_a           REAL NOT NULL,
        odds_b           REAL NOT NULL,
        selection_a      TEXT NOT NULL,
        selection_b      TEXT NOT NULL,
        detected_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        alerted          INTEGER DEFAULT 0
    )
    """,

    # --- Detected positive-EV bets ---
    """
    CREATE TABLE IF NOT EXISTS ev_signals (
        id               INTEGER PRIMARY KEY AUTOINCREMENT,
        market_key       TEXT NOT NULL,
        event_name       TEXT NOT NULL,
        sport            TEXT NOT NULL,
        market_type      TEXT NOT NULL,
        selection_name   TEXT NOT NULL,
        book_name        TEXT NOT NULL,
        decimal_odds     REAL NOT NULL,
        fair_probability REAL NOT NULL,
        ev_pct           REAL NOT NULL,
        detected_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        alerted          INTEGER DEFAULT 0
    )
    """,

    # --- Generated parlay slips ---
    """
    CREATE TABLE IF NOT EXISTS parlays (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        discord_message_id  TEXT,
        generated_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        combined_odds       REAL NOT NULL,
        confidence_score    REAL NOT NULL,
        outcome             TEXT DEFAULT 'pending',
        leg_count           INTEGER NOT NULL
    )
    """,

    # --- Individual legs within a parlay ---
    """
    CREATE TABLE IF NOT EXISTS parlay_legs (
        id           INTEGER PRIMARY KEY AUTOINCREMENT,
        parlay_id    INTEGER NOT NULL REFERENCES parlays(id),
        team         TEXT NOT NULL,
        market_type  TEXT NOT NULL,
        line_value   REAL,
        american_odds INTEGER NOT NULL,
        leg_score    REAL NOT NULL,
        leg_type     TEXT NOT NULL,
        outcome      TEXT DEFAULT 'pending'
    )
    """,

    # --- Self-learning weights per leg type (updated from Discord reactions) ---
    """
    CREATE TABLE IF NOT EXISTS leg_type_weights (
        leg_type   TEXT PRIMARY KEY,
        weight     REAL NOT NULL DEFAULT 1.0,
        hit_count  INTEGER DEFAULT 0,
        miss_count INTEGER DEFAULT 0,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,

    # --- Runtime-adjustable bot configuration (overrides env defaults) ---
    """
    CREATE TABLE IF NOT EXISTS bot_config (
        key        TEXT PRIMARY KEY,
        value      TEXT NOT NULL,
        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
]

# ------------------------------------------------------------------ #
# DML — bot_config seeding / lookup                                   #
# ------------------------------------------------------------------ #

UPSERT_BOT_CONFIG: str = """
    INSERT INTO bot_config (key, value) VALUES (?, ?)
    ON CONFLICT(key) DO NOTHING
"""

GET_BOT_CONFIG: str = "SELECT key, value FROM bot_config"

GET_BOT_CONFIG_KEY: str = "SELECT value FROM bot_config WHERE key = ?"

# ------------------------------------------------------------------ #
# DML — TTS language preference per-user (stored in bot_config table)#
# ------------------------------------------------------------------ #

UPSERT_TTS_LANG: str = """
    INSERT INTO bot_config (key, value) VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
"""

GET_TTS_LANG: str = "SELECT value FROM bot_config WHERE key = ?"

# ------------------------------------------------------------------ #
# DML — Arbitrage and EV signal persistence (Phase 3)                #
# ------------------------------------------------------------------ #

INSERT_ARB_SIGNAL: str = """
    INSERT INTO arb_signals
        (market_key, event_name, sport, market_type, arb_pct,
         stake_side_a, stake_side_b, estimated_profit,
         book_a, book_b, odds_a, odds_b, selection_a, selection_b,
         detected_at, alerted)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

INSERT_EV_SIGNAL: str = """
    INSERT INTO ev_signals
        (market_key, event_name, sport, market_type, selection_name,
         book_name, decimal_odds, fair_probability, ev_pct, detected_at, alerted)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
"""

SELECT_LATEST_ARB_SIGNALS: str = """
    SELECT * FROM arb_signals ORDER BY detected_at DESC LIMIT ?
"""

SELECT_LATEST_EV_SIGNALS: str = """
    SELECT * FROM ev_signals ORDER BY detected_at DESC LIMIT ?
"""

UPDATE_BOT_CONFIG: str = """
    INSERT INTO bot_config (key, value) VALUES (?, ?)
    ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = CURRENT_TIMESTAMP
"""

# ------------------------------------------------------------------ #
# DML — Parlay persistence (Phase 4)                                  #
# ------------------------------------------------------------------ #

INSERT_PARLAY: str = """
    INSERT INTO parlays (combined_odds, confidence_score, leg_count, generated_at)
    VALUES (?, ?, ?, ?)
"""

UPDATE_PARLAY_MESSAGE_ID: str = """
    UPDATE parlays SET discord_message_id = ? WHERE id = ?
"""

UPDATE_PARLAY_OUTCOME: str = """
    UPDATE parlays SET outcome = ? WHERE id = ?
"""

INSERT_PARLAY_LEG: str = """
    INSERT INTO parlay_legs (parlay_id, team, market_type, line_value, american_odds, leg_score, leg_type)
    VALUES (?, ?, ?, ?, ?, ?, ?)
"""

SELECT_PARLAY_BY_MESSAGE_ID: str = """
    SELECT id, generated_at, outcome FROM parlays WHERE discord_message_id = ?
"""

SELECT_PARLAY_LEGS: str = """
    SELECT leg_type, leg_score FROM parlay_legs WHERE parlay_id = ?
"""

SELECT_LATEST_PARLAYS: str = """
    SELECT id, generated_at, combined_odds, confidence_score, outcome, leg_count
    FROM parlays ORDER BY generated_at DESC LIMIT ?
"""

SELECT_PARLAY_WITH_LEGS: str = """
    SELECT p.id, p.generated_at, p.combined_odds, p.confidence_score, p.outcome, p.leg_count,
           pl.team, pl.market_type, pl.line_value, pl.american_odds, pl.leg_score, pl.leg_type
    FROM parlays p
    JOIN parlay_legs pl ON pl.parlay_id = p.id
    WHERE p.id = ?
"""

SELECT_PARLAY_COUNT: str = """
    SELECT COUNT(*) FROM parlays WHERE outcome != 'pending'
"""

# ------------------------------------------------------------------ #
# DML — Leg type weight persistence (Phase 4)                         #
# ------------------------------------------------------------------ #

SEED_LEG_TYPE_WEIGHTS: str = """
    INSERT INTO leg_type_weights (leg_type, weight, hit_count, miss_count)
    VALUES (?, 1.0, 0, 0)
    ON CONFLICT(leg_type) DO NOTHING
"""

SELECT_ALL_LEG_TYPE_WEIGHTS: str = """
    SELECT leg_type, weight, hit_count, miss_count FROM leg_type_weights
"""

SELECT_LEG_TYPE_WEIGHT: str = """
    SELECT weight, hit_count, miss_count FROM leg_type_weights WHERE leg_type = ?
"""

UPSERT_LEG_TYPE_WEIGHT_HIT: str = """
    INSERT INTO leg_type_weights (leg_type, weight, hit_count, miss_count)
    VALUES (?, ?, 1, 0)
    ON CONFLICT(leg_type) DO UPDATE SET
        weight = excluded.weight,
        hit_count = hit_count + 1,
        updated_at = CURRENT_TIMESTAMP
"""

UPSERT_LEG_TYPE_WEIGHT_MISS: str = """
    INSERT INTO leg_type_weights (leg_type, weight, hit_count, miss_count)
    VALUES (?, ?, 0, 1)
    ON CONFLICT(leg_type) DO UPDATE SET
        weight = excluded.weight,
        miss_count = miss_count + 1,
        updated_at = CURRENT_TIMESTAMP
"""

SELECT_LOW_HIT_RATE_LEG_TYPES: str = """
    SELECT leg_type FROM leg_type_weights
    WHERE (hit_count + miss_count) > 0
      AND CAST(hit_count AS REAL) / (hit_count + miss_count) < 0.3
"""

# ------------------------------------------------------------------ #
# DML — Parlay stats queries (Phase 4)                                #
# ------------------------------------------------------------------ #

SELECT_PARLAY_STATS: str = """
    SELECT
        COUNT(*) as total_tracked,
        SUM(CASE WHEN outcome = 'hit' THEN 1 ELSE 0 END) as total_hits,
        SUM(CASE WHEN outcome = 'miss' THEN 1 ELSE 0 END) as total_misses
    FROM parlays
    WHERE outcome != 'pending'
"""
