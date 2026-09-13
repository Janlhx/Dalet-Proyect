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

    def test_build_compare_card_without_skills(self):
        u1 = {
            "username": "PlayerOne",
            "country_code": "ES",
            "statistics": {
                "pp": 5200.5,
                "global_rank": 14000,
                "country_rank": 450,
                "hit_accuracy": 98.45,
                "play_count": 12000,
                "play_time": 720000,
                "maximum_combo": 1100,
                "grade_counts": {"ss": 5, "ssh": 1, "s": 40, "sh": 10}
            }
        }
        u2 = {
            "username": "PlayerTwo",
            "country_code": "MX",
            "statistics": {
                "pp": 4800.0,
                "global_rank": 19000,
                "country_rank": 620,
                "hit_accuracy": 97.80,
                "play_count": 9500,
                "play_time": 540000,
                "maximum_combo": 950,
                "grade_counts": {"ss": 2, "ssh": 0, "s": 25, "sh": 5}
            }
        }
        embed = OsuPresenter.build_compare_card(u1, u2, lang="es")
        self.assertIn("Head-to-Head", embed.title)
        self.assertIn("PlayerOne", embed.description)
        self.assertIn("Lidera en PP", embed.description)
        # Verify fields exist
        field_names = [f.name for f in embed.fields]
        self.assertTrue(any("PlayerOne" in n for n in field_names))
        self.assertTrue(any("PlayerTwo" in n for n in field_names))
        self.assertTrue(any("Actividad & Consistencia" in n for n in field_names))

    def test_build_compare_card_with_skills(self):
        u1 = {
            "username": "mrekk",
            "country_code": "AU",
            "statistics": {
                "pp": 25000.0,
                "global_rank": 1,
                "country_rank": 1,
                "hit_accuracy": 99.10,
                "play_count": 150000,
                "play_time": 3600000,
                "maximum_combo": 2500,
                "grade_counts": {"ss": 50, "ssh": 20, "s": 800, "sh": 400}
            }
        }
        u2 = {
            "username": "lifeline",
            "country_code": "ID",
            "statistics": {
                "pp": 23000.0,
                "global_rank": 2,
                "country_rank": 1,
                "hit_accuracy": 98.90,
                "play_count": 130000,
                "play_time": 3200000,
                "maximum_combo": 2200,
                "grade_counts": {"ss": 30, "ssh": 10, "s": 650, "sh": 300}
            }
        }
        skills1 = {
            "overall_skill_stars": 9.2,
            "overall_tier_name": "Élite",
            "dominant_skill": "Speed",
            "Aim": {"stars": 9.5, "points": 99.0},
            "Speed": {"stars": 9.8, "points": 100.0},
            "Accuracy": {"stars": 9.0, "points": 98.0},
            "Stamina": {"stars": 8.8, "points": 97.0},
            "Reading": {"stars": 8.5, "points": 95.0}
        }
        skills2 = {
            "overall_skill_stars": 8.9,
            "overall_tier_name": "Élite",
            "dominant_skill": "Aim",
            "Aim": {"stars": 9.2, "points": 98.0},
            "Speed": {"stars": 9.1, "points": 97.5},
            "Accuracy": {"stars": 8.8, "points": 96.0},
            "Stamina": {"stars": 8.9, "points": 97.2},
            "Reading": {"stars": 8.2, "points": 94.0}
        }
        embed = OsuPresenter.build_compare_card(u1, u2, skills1=skills1, skills2=skills2, mode="osu", lang="es")
        field_names = [f.name for f in embed.fields]
        self.assertTrue(any("Desglose de Habilidades" in n for n in field_names))
        # Find skills field
        skills_field = next(f for f in embed.fields if "Desglose de Habilidades" in f.name)
        self.assertIn("Aim", skills_field.value)
        self.assertIn("Speed", skills_field.value)
        self.assertIn("mrekk", skills_field.value)


if __name__ == '__main__':
    unittest.main()

