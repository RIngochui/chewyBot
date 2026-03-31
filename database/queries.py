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
