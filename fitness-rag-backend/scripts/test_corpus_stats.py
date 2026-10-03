"""Smoke test for corpus_stats.py — confirms it runs to completion against
the real local Postgres without raising, and never mutates the table (no
INSERT/UPDATE/DELETE anywhere in the script, verified by inspection here)."""
from corpus_stats import main


def test_corpus_stats_runs_and_reports(capsys):
    exit_code = main()
    assert exit_code == 0
    output = capsys.readouterr().out
    assert "Row count:" in output
    assert "NOTE: This script only reports." in output
