"""Test de verificación de internacionalización (i18n) de embeds con ui.locales."""

import sys
from ui.locales import t, STRINGS
from handlers.dalet_osu_presenter import OsuPresenter

def test_locales():
    print("Testing ui.locales.t...")
    # Check that all keys in en exist in es
    en_keys = set(STRINGS["en"].keys())
    es_keys = set(STRINGS["es"].keys())
    missing_in_es = en_keys - es_keys
    missing_in_en = es_keys - en_keys
    assert not missing_in_es, f"Missing in es: {missing_in_es}"
    assert not missing_in_en, f"Missing in en: {missing_in_en}"
    print(f"All {len(en_keys)} translation keys match across languages.")

    # Check formatting
    en_recent = t("osu.recent_author", "en", username="TestUser", mode="Standard")
    es_recent = t("osu.recent_author", "es", username="TestUser", mode="Standard")
    assert en_recent == "Recent Play · TestUser (Standard)", en_recent
    assert es_recent == "Jugada Reciente · TestUser (Standard)", es_recent
    print("Recent author formatting verified.")

    # Test mock osu cards in EN
    dummy_user = {
        "username": "Mrekk",
        "id": 112233,
        "avatar_url": "https://a.ppy.sh/112233",
        "country": {"code": "AU", "name": "Australia"},
        "statistics": {"pp": 25000.5, "global_rank": 1, "country_rank": 1, "hit_accuracy": 99.12, "play_count": 50000, "play_time": 360000}
    }
    dummy_play = {
        "beatmap": {"id": 12345, "version": "Extra", "difficulty_rating": 8.5, "ar": 10.3, "accuracy": 10.0, "drain": 6.0, "cs": 4.0, "bpm": 270, "total_length": 180, "max_combo": 1500},
        "beatmapset": {"title": "Test Song", "artist": "Test Artist"},
        "statistics": {"count_300": 1000, "count_100": 5, "count_50": 0, "count_miss": 0},
        "mods": ["HD", "DT"],
        "rank": "SH",
        "accuracy": 0.995,
        "pp": 1250.0,
        "score": 105000000,
        "max_combo": 1500,
        "passed": True
    }

    # 1. Profile card (EN & ES)
    card_prof_en = OsuPresenter.build_profile_card(dummy_user, "osu", lang="en")
    card_prof_es = OsuPresenter.build_profile_card(dummy_user, "osu", lang="es")
    assert any("Performance" in f.name for f in card_prof_en.fields)
    assert any("Rendimiento" in f.name for f in card_prof_es.fields)
    print("Profile card bilingual rendering verified.")

    # 2. Recent card (EN & ES)
    card_rec_en = OsuPresenter.build_recent_card("Mrekk", "osu", dummy_play, user_data=dummy_user, lang="en")
    card_rec_es = OsuPresenter.build_recent_card("Mrekk", "osu", dummy_play, user_data=dummy_user, lang="es")
    assert "Recent Play" in card_rec_en.author.name
    assert "Jugada Reciente" in card_rec_es.author.name
    assert any("Performance" in f.name for f in card_rec_en.fields)
    assert any("Rendimiento" in f.name for f in card_rec_es.fields)
    print("Recent card bilingual rendering verified.")

    # 3. Top card (EN & ES)
    card_top_en = OsuPresenter.build_top_card("Mrekk", "osu", [dummy_play], user_data=dummy_user, lang="en")
    card_top_es = OsuPresenter.build_top_card("Mrekk", "osu", [dummy_play], user_data=dummy_user, lang="es")
    assert "Top Scores" in card_top_en.title
    assert "osu! Profile for Mrekk" in card_top_en.author.name
    assert "Perfil de osu! de Mrekk" in card_top_es.author.name
    print("Top card bilingual rendering verified.")

    # 4. Compare card (EN & ES)
    card_comp_en = OsuPresenter.build_compare_card(dummy_user, dummy_user, "osu", lang="en")
    card_comp_es = OsuPresenter.build_compare_card(dummy_user, dummy_user, "osu", lang="es")
    assert "osu! Standard Comparison" in card_comp_en.title
    assert "Comparación osu! Standard" in card_comp_es.title
    assert "PP Leader" in card_comp_en.description
    assert "Lidera en PP" in card_comp_es.description
    print("Compare card bilingual rendering verified.")

    print("\nALL LOCALIZATION TESTS PASSED SUCCESSFULLY!")

if __name__ == "__main__":
    test_locales()
