from pathlib import Path

import psycopg

from denmark_academy.config import get_settings


def run_migrations() -> None:
    settings = get_settings()
    migrations_dir = Path(__file__).parent / "migrations"
    with psycopg.connect(settings.database_url, connect_timeout=settings.database_connect_timeout_seconds) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS schema_migrations (
                  version text PRIMARY KEY,
                  applied_at timestamptz NOT NULL DEFAULT now()
                )
                """
            )
            for migration in sorted(migrations_dir.glob("*.sql")):
                version = migration.name
                cur.execute("SELECT 1 FROM schema_migrations WHERE version = %s", (version,))
                if cur.fetchone():
                    continue
                cur.execute(migration.read_text(encoding="utf-8-sig"))
                cur.execute("INSERT INTO schema_migrations (version) VALUES (%s)", (version,))
        conn.commit()


if __name__ == "__main__":
    run_migrations()

