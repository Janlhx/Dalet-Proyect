import unittest
from handlers.dalet_osu_presenter import OsuPresenter


class TestOsuPresenter(unittest.TestCase):
    """Pruebas unitarias para formateadores y logica de presentacion de osu!."""

    def test_format_mods_empty(self):
        self.assertEqual(OsuPresenter.format_mods([]), "+NM")
        self.assertEqual(OsuPresenter.format_mods(None), "+NM")

    def test_format_mods_strings(self):
        self.assertEqual(OsuPresenter.format_mods(["HD", "DT"]), "+HDDT")
        self.assertEqual(OsuPresenter.format_mods(["HR"]), "+HR")

    def test_format_mods_dicts_v2_api(self):
        mods = [{"acronym": "HD"}, {"acronym": "HR"}]
        self.assertEqual(OsuPresenter.format_mods(mods), "+HDHR")

    def test_format_acc(self):
        self.assertEqual(OsuPresenter.format_acc(0.9856), "98.56%")
        self.assertEqual(OsuPresenter.format_acc(99.12), "99.12%")
        self.assertEqual(OsuPresenter.format_acc(None), "0.00%")

    def test_extract_score_classic_and_solo(self):
        self.assertEqual(OsuPresenter._extract_score({"total_score": 1250000}), "1,250,000")
        self.assertEqual(OsuPresenter._extract_score({"classic_total_score": 980000}), "980,000")

    def test_generate_progress_chart_insufficient_data(self):
        # Con menos de 2 snapshots no debe fallar ni colgarse, debe retornar None limpiamente
        self.assertIsNone(OsuPresenter.generate_progress_chart("test_user", []))
        self.assertIsNone(OsuPresenter.generate_progress_chart("test_user", [{"pp": 100}]))


if __name__ == '__main__':
    unittest.main()
