"""
Basic unit tests for SLAYBILL builder utility functions.

Run with: python -m pytest test_builders.py
Or simply: python test_builders.py (uses built-in unittest)
"""

import unittest
from datetime import date
from pathlib import Path
import sys

# Add project root to path so we can import from builders/
sys.path.insert(0, str(Path(__file__).parent))

from builders.build_live_shows import derive_status, _parse_date


class TestBuildLiveShowsUtils(unittest.TestCase):
    """Test utility functions from build_live_shows.py"""

    def test_parse_date_valid_iso(self):
        """Test parsing valid ISO date strings"""
        result = _parse_date("2026-04-27")
        self.assertEqual(result, date(2026, 4, 27))

    def test_parse_date_none(self):
        """Test parsing None returns None"""
        result = _parse_date(None)
        self.assertIsNone(result)

    def test_parse_date_empty_string(self):
        """Test parsing empty string returns None"""
        result = _parse_date("")
        self.assertIsNone(result)

    def test_parse_date_invalid(self):
        """Test parsing invalid date string returns None"""
        result = _parse_date("not-a-date")
        self.assertIsNone(result)

    def test_derive_status_closed(self):
        """Test status derivation for closed show"""
        show = {
            "closing_date": "2026-01-01",
            "opening_date": "2025-10-01",
        }
        today = date(2026, 4, 27)
        result = derive_status(show, today)
        self.assertEqual(result, "closed")

    def test_derive_status_live(self):
        """Test status derivation for live show"""
        show = {
            "opening_date": "2026-03-01",
            "closing_date": "2026-06-01",
        }
        today = date(2026, 4, 27)
        result = derive_status(show, today)
        self.assertEqual(result, "live")

    def test_derive_status_in_previews(self):
        """Test status derivation for show in previews"""
        show = {
            "first_preview_date": "2026-04-01",
            "opening_date": "2026-05-15",
        }
        today = date(2026, 4, 27)
        result = derive_status(show, today)
        self.assertEqual(result, "in_previews")

    def test_derive_status_coming_soon(self):
        """Test status derivation for coming soon show"""
        show = {
            "first_preview_date": "2026-06-01",
        }
        today = date(2026, 4, 27)
        result = derive_status(show, today)
        self.assertEqual(result, "coming_soon")

    def test_derive_status_explicit(self):
        """Test that explicit status in shows.json is honored"""
        show = {
            "status": "cancelled",
            "first_preview_date": "2026-06-01",
        }
        today = date(2026, 4, 27)
        result = derive_status(show, today)
        self.assertEqual(result, "cancelled")


if __name__ == "__main__":
    # Run tests
    unittest.main(verbosity=2)
