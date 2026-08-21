from tap.config.responsive import build_layout_profile, records_page_uses_full_width, table_display_columns


def test_compact_profile_prioritizes_records():
    profile = build_layout_profile(800)

    assert profile.name == "compact"
    assert "Nom" in table_display_columns(profile.name)
    assert "Statut des versements" in table_display_columns(profile.name)
    assert "Statut Souscription" not in table_display_columns(profile.name)


def test_wide_profile_keeps_all_record_columns():
    profile = build_layout_profile(1920)

    assert profile.name == "wide"
    assert len(table_display_columns(profile.name)) == 8


def test_records_page_prioritizes_table_width_on_narrow_profiles():
    assert records_page_uses_full_width("compact") is True
    assert records_page_uses_full_width("medium") is True
    assert records_page_uses_full_width("wide") is False
