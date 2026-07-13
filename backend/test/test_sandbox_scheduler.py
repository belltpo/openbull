"""Regression tests for sandbox scheduler bookkeeping."""

from contextlib import contextmanager
from unittest import TestCase
from unittest.mock import Mock, patch

from sqlalchemy.dialects import postgresql

from backend.sandbox import scheduler


class SandboxSchedulerTests(TestCase):
    def test_mark_ran_uses_conflict_safe_upsert(self):
        """Overlapping reload workers must not race on a new marker row."""
        db = Mock()

        @contextmanager
        def fake_session_scope():
            yield db

        with patch.object(scheduler, "session_scope", fake_session_scope):
            scheduler._mark_ran("squareoff_nse_nfo_bse_bfo", "2026-07-13")

        statement = db.execute.call_args.args[0]
        sql = str(statement.compile(dialect=postgresql.dialect()))
        self.assertIn("ON CONFLICT (key) DO UPDATE", sql)
        self.assertNotIn("SELECT", sql)


if __name__ == "__main__":
    import unittest

    unittest.main()
