from tap.core.data_validator import DataValidator


def test_phone_cleanup_uses_drc_country_code_by_default():
    validator = DataValidator()

    assert validator._clean_phone("812345678") == "+243812345678"


def test_phone_cleanup_accepts_a_configured_country_code():
    validator = DataValidator(default_phone_country_code="+33")

    assert validator._clean_phone("612345678") == "+33612345678"
