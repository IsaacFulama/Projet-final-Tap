from tap.config.responsive import build_layout_profile, table_display_columns


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
