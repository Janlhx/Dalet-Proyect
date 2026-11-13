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


SAMPLE_OSU_BYTES = (
    b"osu file format v14\n\n"
    b"[General]\nAudioFilename: audio.mp3\nMode: 0\n\n"
    b"[Metadata]\nTitle: Test Map\nArtist: Dalet\nCreator: Mapper\nVersion: Insane\nBeatmapID: 129891\nBeatmapSetID: 39804\n\n"
    b"[Difficulty]\nHPDrainRate:5\nCircleSize:4\nOverallDifficulty:8\nApproachRate:9\nSliderMultiplier:1.8\nSliderTickRate:1\n\n"
    b"[TimingPoints]\n0,333.333333333333,4,2,0,100,1,0\n\n"
    b"[HitObjects]\n"
    b"64,192,1000,1,0,0:0:0:0:\n"
    b"448,192,1166,1,0,0:0:0:0:\n"
    b"64,64,1333,1,0,0:0:0:0:\n"
    b"448,320,1500,1,0,0:0:0:0:\n"
    b"256,64,1666,1,0,0:0:0:0:\n"
    b"256,320,1833,1,0,0:0:0:0:\n"
    b"128,128,2000,1,0,0:0:0:0:\n"
    b"384,256,2166,1,0,0:0:0:0:\n"
)


class TestRosuPPAndMapCard(unittest.TestCase):
    """Pruebas unitarias para simulación rosu-pp (fails, if FC), d.m / /map y tarjetas enriquecidas."""

    def test_compute_rosu_score_pp_failed_and_if_fc(self):
        from services.osu_service import OsuService

        failed_score = {
            "pp": None,
            "passed": False,
            "rank": "F",
            "accuracy": 0.96,
            "max_combo": 4,
            "mods": ["HD", "DT"],
            "statistics": {"count_300": 4, "count_100": 1, "count_50": 0, "count_miss": 1},
        }
        res = OsuService.compute_rosu_score_pp(SAMPLE_OSU_BYTES, failed_score, mode="osu")
        self.assertTrue(res["pp_is_simulated"])
        self.assertGreater(res["actual_pp"], 0.0)
        self.assertIsNotNone(res["fc_pp"])
        self.assertGreater(res["fc_pp"], res["actual_pp"])
        self.assertGreater(res["ar"], 9.5)  # DT scales AR 9 up to ~10.33
        self.assertEqual(res["clock_rate"], 1.5)

    def test_simulate_map_pp_table_monotonic(self):
        import asyncio
        from services.osu_service import OsuService

        svc = OsuService(0, "")
        svc._osu_file_cache[129891] = SAMPLE_OSU_BYTES

        async def _run():
            return await svc.simulate_map_pp_table(129891, mode="osu", mods=["HD", "DT"])

        table = asyncio.run(_run())
        self.assertIn("pp", table)
        pp_map = table["pp"]
        self.assertLessEqual(pp_map[95], pp_map[98])
        self.assertLessEqual(pp_map[98], pp_map[99])
        self.assertLessEqual(pp_map[99], pp_map[100])
        self.assertGreater(table["stars"], 0.0)

    def test_parse_beatmap_reference_map_args_and_channel_context(self):
        from services.osu_service import OsuService

        bid, bsid, mode = OsuService.parse_beatmap_reference("https://osu.ppy.sh/beatmapsets/39804#osu/129891")
        self.assertEqual(bid, 129891)
        self.assertEqual(bsid, 39804)
        self.assertEqual(mode, "osu")

        bid2, _, mode2 = OsuService.parse_beatmap_reference("https://osu.ppy.sh/b/252002 -m mania")
        self.assertEqual(bid2, 252002)

        q, mods, ov = OsuService.parse_map_args("https://osu.ppy.sh/b/129891 +HDDT -taiko")
        self.assertEqual(q, "https://osu.ppy.sh/b/129891")
        self.assertEqual(mods, ["HD", "DT"])
        self.assertEqual(ov, "taiko")

        svc = OsuService(0, "")
        svc.remember_channel_map(999001, 129891, "osu")
        self.assertEqual(svc.get_channel_map(999001), (129891, "osu"))

    def test_recent_top_and_map_cards_show_pp_if_fc_without_emojis(self):
        play_fail = {
            "pp": None,
            "_pp_actual": 142.85,
            "_pp_is_simulated": True,
            "_pp_fc": 310.40,
            "passed": False,
            "rank": "F",
            "accuracy": 0.9645,
            "max_combo": 210,
            "total_score": 450000,
            "mods": ["HD", "DT"],
            "statistics": {"count_300": 150, "count_100": 8, "count_50": 1, "count_miss": 3},
            "beatmap": {
                "id": 129891, "version": "FD", "ar": 9.0, "accuracy": 8.0,
                "drain": 5.0, "cs": 4.0, "bpm": 222, "total_length": 240, "max_combo": 450,
                "count_circles": 200, "count_sliders": 20, "count_spinners": 0,
            },
            "beatmapset": {"title": "Freedom Dive", "artist": "xi", "creator": "Nakagawa-Kanon", "status": "ranked"},
            "beatmap_attributes": {"star_rating": 8.42, "approach_rate": 10.333, "overall_difficulty": 9.8, "hp": 5.0, "cs": 4.0, "clock_rate": 1.5},
        }
        recent_embed = OsuPresenter.build_recent_card("Maluca", "osu", play_fail, lang="es")
        desc_val = recent_embed.description or ""
        self.assertEqual(len(recent_embed.fields), 0)
        self.assertNotIn("───", desc_val)
        self.assertIn("~142.85pp", desc_val)
        self.assertIn("310.40pp FC", desc_val)
        self.assertNotIn("0.00pp", desc_val)
        self.assertNotIn("Sin PP", desc_val)
        self.assertIn("AR 10.3", desc_val)

        user_dict = {"username": "Maluca", "country_code": "CO", "statistics": {"pp": 5000, "global_rank": 10000}}
        top_embed = OsuPresenter.build_top_card(user_dict, [play_fail], mode="osu", lang="es")
        top_text = (top_embed.description or "") + "\n" + "\n".join(f.value for f in top_embed.fields)
        self.assertIn("~142.8pp", top_text)
        self.assertIn("310pp FC", top_text)

        map_embed = OsuPresenter.build_map_card(
            {"id": 129891, "version": "FD", "status": "ranked", "bpm": 222, "total_length": 240,
             "beatmapset": {"id": 39804, "title": "Freedom Dive", "artist": "xi", "creator": "Nakagawa-Kanon"}},
            pp_table={"stars": 8.42, "max_combo": 450, "ar": 10.33, "od": 9.8, "hp": 5.0, "cs": 4.0,
                      "clock_rate": 1.5, "n_circles": 200, "n_sliders": 20, "n_spinners": 0,
                      "pp": {95: 720.0, 98: 830.0, 99: 890.0, 100: 960.0}},
            mode="osu", mods=["HD", "DT"], lang="es"
        )
        self.assertIn("Freedom Dive", map_embed.title)
        pp_field = next(f.value for f in map_embed.fields if "PP" in f.name)
        self.assertIn("720pp", pp_field)
        self.assertIn("960pp", pp_field)

    def test_extract_beatmap_from_external_bot_embeds_and_map_compare_card(self):
        import asyncio
        from types import SimpleNamespace
        from services.osu_service import OsuService

        # Simula embed estilo Bathbot (beatmap URL en description y cover en thumbnail)
        bathbot_msg = SimpleNamespace(
            id=111,
            content="",
            embeds=[
                SimpleNamespace(
                    url="https://osu.ppy.sh/b/252002",
                    author=SimpleNamespace(url="https://osu.ppy.sh/users/12345"),
                    title="",
                    description="**[Remote Control [Max Control!]](https://osu.ppy.sh/beatmapsets/51972#osu/252002)**",
                    fields=[],
                    footer=None,
                    thumbnail=None,
                    image=None,
                )
            ],
        )
        bid, _, mode = OsuService.extract_beatmap_from_message(bathbot_msg)
        self.assertEqual(bid, 252002)

        # Simula embed estilo owo (link en field.value sin emb.url)
        owo_msg = SimpleNamespace(
            id=222,
            content="",
            embeds=[
                SimpleNamespace(
                    url=None,
                    author=None,
                    title="Recent Play",
                    description="Accuracy: 98.5%",
                    fields=[SimpleNamespace(name="Map", value="[Song [Insane]](https://osu.ppy.sh/beatmapsets/39804#mania/777777)")],
                    footer=None,
                    thumbnail=None,
                    image=None,
                )
            ],
        )
        bid2, bsid2, mode2 = OsuService.extract_beatmap_from_message(owo_msg)
        self.assertEqual(bid2, 777777)
        self.assertEqual(bsid2, 39804)
        self.assertEqual(mode2, "mania")

        # Cascada detect_beatmap_from_discord: Reply tiene prioridad sobre historial reciente
        async def _fake_history(limit=25):
            yield owo_msg

        fake_channel = SimpleNamespace(id=555, history=_fake_history)
        svc = OsuService(0, "")
        det_bid, _, det_mode = asyncio.run(svc.detect_beatmap_from_discord(fake_channel, ref_message=bathbot_msg))
        self.assertEqual(det_bid, 252002)

        det_hist_bid, _, det_hist_mode = asyncio.run(svc.detect_beatmap_from_discord(fake_channel, ref_message=None))
        self.assertEqual(det_hist_bid, 777777)
        self.assertEqual(det_hist_mode, "mania")

        # Normalización de estadísticas Lazer (great/ok/meh/miss)
        lazer_stats = OsuService._normalize_score_stats({"great": 500, "ok": 12, "meh": 1, "miss": 2})
        self.assertEqual(lazer_stats["count_300"], 500)
        self.assertEqual(lazer_stats["count_100"], 12)
        self.assertEqual(lazer_stats["count_miss"], 2)

        # Renderizado de tarjeta build_map_compare_card (con mods + NM + if FC)
        scores = [
            {
                "pp": 412.5,
                "_pp_fc": 465.2,
                "rank": "A",
                "accuracy": 0.9812,
                "max_combo": 512,
                "total_score": 8900123,
                "mods": ["HD", "DT"],
                "statistics": {"count_300": 400, "count_100": 8, "count_50": 0, "count_miss": 2},
                "beatmap_attributes": {"star_rating": 7.85},
            },
            {
                "pp": 298.4,
                "rank": "S",
                "accuracy": 0.9920,
                "max_combo": 700,
                "total_score": 7200450,
                "mods": [],
                "statistics": {"count_300": 405, "count_100": 5, "count_50": 0, "count_miss": 0},
                "beatmap_attributes": {"star_rating": 5.62},
            },
        ]
        user_d = {"username": "Yiyi", "id": 99, "_server": "bancho"}
        bm_d = {
            "id": 252002, "version": "Max Control!", "difficulty_rating": 5.62, "bpm": 165, "total_length": 210, "max_combo": 700,
            "beatmapset": {"title": "Remote Control", "artist": "Kagamine Rin/Len"},
        }
        cmp_embed = OsuPresenter.build_map_compare_card(user_d, bm_d, scores, mode="osu", lang="es")
        self.assertIn("Remote Control", cmp_embed.description)
        self.assertIn("412.50pp", cmp_embed.description)
        self.assertIn("465pp FC", cmp_embed.description)
        self.assertIn("+HDDT", cmp_embed.description)
        self.assertIn("+NM", cmp_embed.description)

    def test_dalet_atoms_application_emojis_and_fallbacks(self):
        from types import SimpleNamespace
        from ui.atoms import DaletAtoms

        DaletAtoms.CUSTOM_EMOJIS.clear()
        try:
            # Fallback sin emojis cargados
            self.assertEqual(DaletAtoms.get_grade_emoji("SH", "1x"), "`S (1x)`")
            self.assertEqual(DaletAtoms.get_mode_emoji("osu"), "")
            self.assertEqual(DaletAtoms.get_dalet_reaction_emojis(), [])

            # Cargar Application Emojis simulados
            fake_emojis = [
                SimpleNamespace(name="grade_sh", id=1001, animated=False),
                SimpleNamespace(name="mode_osu", id=1002, animated=False),
                SimpleNamespace(name="dalet_stare", id=1003, animated=False),
                SimpleNamespace(name="dalet_meh", id=1004, animated=True),
            ]
            loaded = DaletAtoms.load_application_emojis(fake_emojis)
            self.assertEqual(loaded, 4)

            self.assertEqual(DaletAtoms.get_grade_emoji("SH", "1x"), "<:grade_sh:1001> `(1x)`")
            self.assertEqual(DaletAtoms.get_grade_emoji("SH"), "<:grade_sh:1001>")
            self.assertEqual(DaletAtoms.get_grade_emoji("X"), "`SS`")
            self.assertEqual(DaletAtoms.get_mode_emoji("osu"), "<:mode_osu:1002>")
            self.assertEqual(DaletAtoms.get_dalet_reaction_emojis(), ["dalet_meh", "dalet_stare"])
            self.assertEqual(DaletAtoms.resolve_custom_emoji("dalet_meh"), "<a:dalet_meh:1004>")

            # Verificar renderizado en tarjetas (/op, /firsts)
            profile_emb = OsuPresenter.build_profile_card(
                {
                    "id": 1, "username": "Maluca",
                    "statistics": {"pp": 5000, "global_rank": 1000, "grade_counts": {"ss": 5, "s": 10, "a": 20}},
                },
                mode="osu", lang="es",
            )
            profile_text = "\n".join(f.name + f.value for f in profile_emb.fields)
            self.assertIn("<:mode_osu:1002>", profile_text)

            firsts_emb = OsuPresenter.build_firsts_card(
                "Maluca",
                [{"rank": "SH", "accuracy": 0.99, "mods": ["HD"], "pp": 300, "max_combo": 200, "beatmap": {"id": 1}, "beatmapset": {"title": "Map"}}],
                mode="osu", lang="es",
            )
            self.assertIn("<:grade_sh:1001>", firsts_emb.description)

            # Regresión: 5 top plays con custom emojis largos + if FC + timestamps no deben exceder 1024 chars en fields
            long_scores = [
                {
                    "rank": "SH",
                    "pp": 412.5,
                    "_pp_fc": 495.2,
                    "accuracy": 0.9854,
                    "max_combo": 720,
                    "mods": ["HD", "DT"],
                    "created_at": "2026-11-12T20:00:00Z",
                    "statistics": {"count_miss": 2},
                    "beatmap": {"id": 1234567 + idx, "version": "Extra Difficulty Name", "max_combo": 900, "difficulty_rating": 7.5},
                    "beatmapset": {"title": "Very Long Beatmap Title Example"},
                }
                for idx in range(5)
            ]
            top_emb = OsuPresenter.build_top_card(
                {"id": 1, "username": "Litxe", "country_code": "CO", "statistics": {"pp": 7000, "global_rank": 12345, "hit_accuracy": 98.5}},
                long_scores,
                mode="osu",
                lang="es",
                sort_by="recent",
            )
            self.assertLessEqual(len(top_emb.description or ""), 4096)
            self.assertGreaterEqual(len(top_emb.fields), 1)
            for fld in top_emb.fields:
                self.assertLessEqual(len(fld.value), 1024)
            all_top_text = "\n".join(fld.value for fld in top_emb.fields)
            self.assertIn("<:grade_sh:1001>", all_top_text)
        finally:
            DaletAtoms.CUSTOM_EMOJIS.clear()

    def test_analytics_repository_persists_and_tracks_intraday_pp_snapshots(self):
        import asyncio
        import sqlite3
        from unittest.mock import patch
        from database.repositories.analytics_repository import AnalyticsRepository

        conn = sqlite3.connect(":memory:")
        conn.row_factory = sqlite3.Row

        class _FakeResult:
            def __init__(self, rows):
                self.rows = rows

        class _FakeTursoClient:
            async def execute(self, query, args=()):
                cur = conn.execute(query, tuple(args or ()))
                conn.commit()
                return _FakeResult([dict(r) for r in cur.fetchall()])

        async def _run():
            fake_client = _FakeTursoClient()
            AnalyticsRepository._history_schema_ensured = False
            repo = AnalyticsRepository()
            with patch("database.repositories.base_repository.get_db", return_value=fake_client):
                await repo.record_osu_snapshot(123, 5000.0, 20000, 300, 98.5, "osu")
                # Mismo PP mismo día -> actualiza en vez de duplicar
                await repo.record_osu_snapshot(123, 5000.0, 19950, 299, 98.5, "osu")
                hist_1 = await repo.get_osu_progress(123, mode="osu", limit=30)
                self.assertEqual(len(hist_1), 1)
                self.assertEqual(hist_1[0]["global_rank"], 19950)

                # Cambio de PP mismo día -> guarda 2do snapshot para poder graficar progreso
                await repo.record_osu_snapshot(123, 5042.5, 19500, 290, 98.55, "osu")
                hist_2 = await repo.get_osu_progress(123, mode="osu", limit=30)
                self.assertEqual(len(hist_2), 2)
                self.assertAlmostEqual(hist_2[0]["pp"], 5042.5)
                self.assertAlmostEqual(hist_2[1]["pp"], 5000.0)

        try:
            asyncio.run(_run())
        finally:
            AnalyticsRepository._history_schema_ensured = False
            conn.close()


if __name__ == '__main__':
    unittest.main()

