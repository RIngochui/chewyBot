"""
Tracker SQL statements.

ALL SQL for the flight tracker lives here — zero SQL literals anywhere else
in the tracker package. Mirrors the convention in database/queries.py.
"""

CREATE_TABLES_SQL: list[str] = [
    """
    CREATE TABLE IF NOT EXISTS routes (
        id                      INTEGER  PRIMARY KEY AUTOINCREMENT,
        origin                  TEXT     NOT NULL,
        destination             TEXT     NOT NULL,
        depart_date             TEXT     NOT NULL,
        return_date             TEXT,
        max_stops               INTEGER  NOT NULL DEFAULT 1,
        passengers              INTEGER  NOT NULL DEFAULT 1,
        cabin_class             TEXT     NOT NULL DEFAULT 'ECONOMY',
        absolute_threshold_cad  REAL,
        active                  INTEGER  NOT NULL DEFAULT 1,
        created_at              TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS price_snapshots (
        id                      INTEGER  PRIMARY KEY AUTOINCREMENT,
        route_id                INTEGER  NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
        timestamp               TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        cheapest_price_cad      REAL,
        cheapest_price_original REAL,
        original_currency       TEXT,
        carrier                 TEXT,
        stops                   INTEGER,
        offer_json              TEXT,
        poll_success            INTEGER  NOT NULL DEFAULT 1
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS alerts_sent (
        id                  INTEGER  PRIMARY KEY AUTOINCREMENT,
        route_id            INTEGER  NOT NULL REFERENCES routes(id) ON DELETE CASCADE,
        timestamp           TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        trigger_price_cad   REAL     NOT NULL,
        baseline_price_cad  REAL     NOT NULL,
        trigger_reason      TEXT     NOT NULL,
        discord_message_id  TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_price_snapshots_route_id ON price_snapshots(route_id)",
    "CREATE INDEX IF NOT EXISTS idx_alerts_sent_route_id     ON alerts_sent(route_id)",
    "CREATE INDEX IF NOT EXISTS idx_routes_active            ON routes(active)",
]

INSERT_ROUTE: str = """
    INSERT INTO routes (
        origin, destination, depart_date, return_date,
        max_stops, passengers, cabin_class, absolute_threshold_cad
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""

SELECT_ALL_ROUTES: str = "SELECT * FROM routes ORDER BY id"

SELECT_ROUTE_BY_ID: str = "SELECT * FROM routes WHERE id = ?"

DELETE_ROUTE: str = "DELETE FROM routes WHERE id = ?"

UPDATE_ROUTE_ACTIVE: str = "UPDATE routes SET active = ? WHERE id = ?"

INSERT_PRICE_SNAPSHOT: str = """
    INSERT INTO price_snapshots (
        route_id, cheapest_price_cad, cheapest_price_original, original_currency,
        carrier, stops, offer_json, poll_success
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
"""

SELECT_RECENT_SNAPSHOTS: str = """
    SELECT * FROM price_snapshots
    WHERE route_id = ?
    ORDER BY timestamp DESC
    LIMIT ?
"""
