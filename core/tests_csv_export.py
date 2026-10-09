"""Tests for core.csv_export formula-injection hardening."""
from __future__ import annotations

import csv
import io
from decimal import Decimal

from django.test import SimpleTestCase

from core.csv_export import _safe_cell, csv_response, csv_string


def _rows(text: str) -> list[list[str]]:
    return list(csv.reader(io.StringIO(text.lstrip("\ufeff"))))


class SafeCellTests(SimpleTestCase):
    def test_formula_leading_strings_are_prefixed(self):
        for value in ('=HYPERLINK("x")', "+SUM(A1)", "-cmd", "@SUM(A1)", "\tx", "\rx"):
            with self.subTest(value=value):
                self.assertEqual(_safe_cell(value), "'" + value)

    def test_plain_numeric_strings_unchanged(self):
        for value in ("-5.00", "-5", "12.50", "0"):
            with self.subTest(value=value):
                self.assertEqual(_safe_cell(value), value)

    def test_phone_with_plus_is_prefixed(self):
        self.assertEqual(_safe_cell("+970599123456"), "'+970599123456")

    def test_non_strings_unchanged(self):
        self.assertEqual(_safe_cell(Decimal("-5.00")), Decimal("-5.00"))
        self.assertEqual(_safe_cell(-3), -3)
        self.assertIsNone(_safe_cell(None))

    def test_ordinary_text_unchanged(self):
        self.assertEqual(_safe_cell("Ahmad = boss"), "Ahmad = boss")


class CsvOutputSanitizationTests(SimpleTestCase):
    def test_csv_string_sanitizes_every_cell(self):
        out = csv_string(["=h"], [['=HYPERLINK("x")', "-5.00", None, 7]])
        rows = _rows(out)
        self.assertEqual(rows[0], ["'=h"])
        self.assertEqual(rows[1], ['\'=HYPERLINK("x")', "-5.00", "", "7"])

    def test_csv_response_sanitizes_every_cell(self):
        response = csv_response(
            "x", ["@h"], [['=HYPERLINK("x")', "-5.00", None]], timestamp=False
        )
        body = b"".join(response.streaming_content).decode("utf-8")
        rows = _rows(body)
        self.assertEqual(rows[0], ["'@h"])
        self.assertEqual(rows[1], ['\'=HYPERLINK("x")', "-5.00", ""])
