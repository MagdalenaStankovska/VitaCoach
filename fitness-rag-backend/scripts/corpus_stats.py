"""Reports the real size of the `documents` corpus in Postgres.

The paper currently claims 1,247 documents. ingest.py (see repo root) has no
dedup guard and can be re-run repeatedly, appending ~277 more rows each time
(data/hku_academic.txt + data/exercises.txt together produce ~277 chunks per
run) — so the live count may be inflated by repeated ingestion runs, not by
an actually larger corpus. This script only REPORTS the real numbers; it
does not modify or delete any rows. See the closing note in its output for
why deduplication is deliberately out of scope here.

Usage (run from fitness-rag-backend/):
    python scripts/corpus_stats.py
"""
import os
import statistics

import psycopg2
from dotenv import load_dotenv

load_dotenv()


def main() -> int:
    conn = psycopg2.connect(
        dbname="fitness_rag",
        user="postgres",
        password=os.getenv("DB_PASSWORD"),
        host="localhost",
        port="5432",
    )
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM documents;")
    (count,) = cursor.fetchone()

    cursor.execute("SELECT LENGTH(content) FROM documents;")
    lengths = [row[0] for row in cursor.fetchall()]

    cursor.execute(
        "SELECT COUNT(*) FROM (SELECT content FROM documents GROUP BY content HAVING COUNT(*) > 1) dup;"
    )
    (duplicated_distinct_contents,) = cursor.fetchone()

    cursor.execute(
        "SELECT COALESCE(SUM(cnt - 1), 0) FROM "
        "(SELECT COUNT(*) AS cnt FROM documents GROUP BY content HAVING COUNT(*) > 1) dup;"
    )
    (redundant_rows,) = cursor.fetchone()

    cursor.close()
    conn.close()

    print("=== Corpus Stats (documents table) ===")
    print(f"Row count:             {count}")
    if lengths:
        print(f"Mean document length:  {statistics.mean(lengths):.1f} chars")
        print(f"Median document length: {statistics.median(lengths):.1f} chars")
    else:
        print("Mean/median document length: n/a (table is empty)")

    print()
    print(f"Distinct contents appearing more than once: {duplicated_distinct_contents}")
    print(f"Redundant rows (duplicates beyond the first occurrence): {redundant_rows}")
    if count:
        print(f"Estimated unique corpus size if deduplicated: {count - redundant_rows}")

    print()
    print(
        "NOTE: This script only reports. Deduplicating `documents` would change "
        "any already-published MRR/P@8 numbers computed against the current "
        "(possibly duplicated) corpus. Do not run any dedup migration without "
        "explicit sign-off from the repo owner -- out of scope for this change."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
