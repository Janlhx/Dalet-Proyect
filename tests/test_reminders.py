import unittest
from handlers.dalet_reminders import (
    parse_time,
    parse_date,
    parse_days,
    parse_days_or_date,
    format_days_readable,
)


class TestReminderParsers(unittest.TestCase):
    """Pruebas unitarias para el motor de parsing y formateo de recordatorios."""

    # ------------------------------------------------------------------
    # parse_time
    # ------------------------------------------------------------------

    def test_parse_time_24h(self):
        self.assertEqual(parse_time("23:00"), "23:00")
        self.assertEqual(parse_time("08:30"), "08:30")
        self.assertEqual(parse_time("8:30"), "08:30")
        self.assertEqual(parse_time("0:05"), "00:05")

    def test_parse_time_12h_meridiem(self):
        self.assertEqual(parse_time("11:00 PM"), "23:00")
        self.assertEqual(parse_time("11pm"), "23:00")
        self.assertEqual(parse_time("11:30 am"), "11:30")
        self.assertEqual(parse_time("8am"), "08:00")
        self.assertEqual(parse_time("12:00 pm"), "12:00")
        self.assertEqual(parse_time("12:00 am"), "00:00")
        self.assertEqual(parse_time("12:45 am"), "00:45")

    def test_parse_time_invalid(self):
        self.assertIsNone(parse_time("25:00"))
        self.assertIsNone(parse_time("12:60"))
        self.assertIsNone(parse_time("13pm"))
        self.assertIsNone(parse_time("no_time"))
        self.assertIsNone(parse_time(""))

    # ------------------------------------------------------------------
    # parse_date
    # ------------------------------------------------------------------

    def test_parse_date_iso(self):
        self.assertEqual(parse_date("2026-12-25"), "2026-12-25")
        self.assertEqual(parse_date("2026-01-01"), "2026-01-01")

    def test_parse_date_dmy(self):
        self.assertEqual(parse_date("25/12/2026"), "2026-12-25")
        self.assertEqual(parse_date("05-09-2026"), "2026-09-05")
        self.assertEqual(parse_date("5/9/2026"), "2026-09-05")

    def test_parse_date_invalid(self):
        self.assertIsNone(parse_date("32/01/2026"))
        self.assertIsNone(parse_date("2026-02-30"))
        self.assertIsNone(parse_date("not-a-date"))

    # ------------------------------------------------------------------
    # parse_days
    # ------------------------------------------------------------------

    def test_parse_days_daily_aliases(self):
        for alias in ["daily", "diario", "todos", "cada dia", "cada día", "todo"]:
            self.assertEqual(parse_days(alias), "daily")

    def test_parse_days_single_and_multiple_es(self):
        self.assertEqual(parse_days("lunes"), "monday")
        self.assertEqual(parse_days("miércoles, sábado"), "wednesday,saturday")
        self.assertEqual(parse_days("domingo, viernes, lunes"), "monday,friday,sunday")

    def test_parse_days_single_and_multiple_en(self):
        self.assertEqual(parse_days("monday"), "monday")
        self.assertEqual(parse_days("friday, tuesday"), "tuesday,friday")

    def test_parse_days_deduplication(self):
        self.assertEqual(parse_days("lunes, mon, monday"), "monday")

    def test_parse_days_invalid(self):
        self.assertIsNone(parse_days("ayer"))
        self.assertIsNone(parse_days("lunes, inventado"))

    # ------------------------------------------------------------------
    # parse_days_or_date
    # ------------------------------------------------------------------

    def test_parse_days_or_date(self):
        self.assertEqual(parse_days_or_date("2026-12-25"), "2026-12-25")
        self.assertEqual(parse_days_or_date("lunes,viernes"), "monday,friday")
        self.assertIsNone(parse_days_or_date("random_string"))

    # ------------------------------------------------------------------
    # format_days_readable
    # ------------------------------------------------------------------

    def test_format_days_readable_daily(self):
        self.assertEqual(format_days_readable("daily", lang="en"), "Every day")
        self.assertEqual(format_days_readable("daily", lang="es"), "Todos los días")

    def test_format_days_readable_specific_date(self):
        self.assertEqual(format_days_readable("2026-12-25", lang="en"), "25/12/2026")
        self.assertEqual(format_days_readable("2026-12-25", lang="es"), "El 25/12/2026")

    def test_format_days_readable_weekdays(self):
        self.assertEqual(format_days_readable("monday,friday", lang="en"), "Monday, Friday")
        self.assertEqual(format_days_readable("monday,friday", lang="es"), "Lunes, Viernes")


if __name__ == '__main__':
    unittest.main()
