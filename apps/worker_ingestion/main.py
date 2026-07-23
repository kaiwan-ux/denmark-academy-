import argparse
from pathlib import Path

from denmark_academy.ingestion.pipeline import IngestionPipeline


def main() -> None:
    parser = argparse.ArgumentParser(description="Run Denmark Academy ingestion jobs.")
    parser.add_argument("root_path", type=Path, help="Folder containing pr/ and citizenship/ material.")
    parser.add_argument("--dry-run", action="store_true", help="Parse and validate without DB/Qdrant writes.")
    parser.add_argument("--skip-qdrant", action="store_true", help="Write PostgreSQL only.")
    parser.add_argument("--migrate", action="store_true", help="Run database migrations before ingestion.")
    args = parser.parse_args()

    if args.migrate:
        from denmark_academy.db.migrate import run_migrations

        run_migrations()

    pipeline = IngestionPipeline()
    if args.dry_run:
        result = pipeline.dry_run(args.root_path)
    else:
        result = pipeline.run(args.root_path, upsert_qdrant=not args.skip_qdrant)
    print(result)


if __name__ == "__main__":
    main()
