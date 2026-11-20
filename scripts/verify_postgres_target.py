import json
import os
import sys
from datetime import datetime, timezone

import psycopg

DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
if not DATABASE_URL:
    print(json.dumps({"ok": False, "error": "DATABASE_URL is not set"}))
    raise SystemExit(2)

marker = "FICTIONAL_TRADE_NETWORK_DB_TARGET_CHECK"

def main():
    with psycopg.connect(DATABASE_URL, connect_timeout=8) as conn:
        with conn.cursor() as cur:
            cur.execute("""
                CREATE TABLE IF NOT EXISTS trade_network_pilot_durability (
                    id smallint PRIMARY KEY DEFAULT 1 CHECK (id = 1),
                    marker text NOT NULL,
                    restart_count integer NOT NULL DEFAULT 0,
                    first_seen_at timestamptz NOT NULL DEFAULT now(),
                    last_seen_at timestamptz NOT NULL DEFAULT now()
                )
            """)
            cur.execute("""
                INSERT INTO trade_network_pilot_durability
                    (id, marker, restart_count, first_seen_at, last_seen_at)
                VALUES (1, %s, 1, now(), now())
                ON CONFLICT (id) DO UPDATE
                SET restart_count = trade_network_pilot_durability.restart_count + 1,
                    last_seen_at = now()
                RETURNING marker, restart_count, first_seen_at, last_seen_at
            """, (marker,))
            row = cur.fetchone()
        conn.commit()

    print(json.dumps({
        "ok": True,
        "marker": row[0],
        "restart_count": row[1],
        "first_seen_at": row[2].isoformat(),
        "last_seen_at": row[3].isoformat(),
        "checked_at": datetime.now(timezone.utc).isoformat(),
    }))

if __name__ == "__main__":
    main()
