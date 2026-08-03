from app.spec_grade import match_tag_to_spec, parse_spec_grade_diameter


def test_parse_spec_grade_diameter_shd_is_sd500():
    assert parse_spec_grade_diameter("SHD13") == ("SD500", "13")


def test_parse_spec_grade_diameter_uhd_is_sd600():
    assert parse_spec_grade_diameter("UHD16") == ("SD600", "16")


def test_parse_spec_grade_diameter_unknown_prefix_returns_none():
    assert parse_spec_grade_diameter("HD13") == (None, None)


def test_parse_spec_grade_diameter_empty_spec_returns_none():
    assert parse_spec_grade_diameter("") == (None, None)


def test_match_tag_to_spec_matched():
    assert match_tag_to_spec("SD500", "13", "SHD13") == "matched"


def test_match_tag_to_spec_mismatched_diameter():
    assert match_tag_to_spec("SD500", "10", "SHD13") == "mismatched"


def test_match_tag_to_spec_mismatched_grade():
    assert match_tag_to_spec("SD600", "13", "SHD13") == "mismatched"


def test_match_tag_to_spec_missing_tag_info_returns_none():
    assert match_tag_to_spec(None, None, "SHD13") is None


def test_match_tag_to_spec_unsupported_spec_prefix_returns_none():
    assert match_tag_to_spec("SD400", "13", "HD13") is None


def test_match_tag_to_spec_diameter_with_unit_suffix_normalizes():
    assert match_tag_to_spec("SD500", "13mm", "SHD13") == "matched"


def test_match_tag_to_spec_grade_case_insensitive():
    assert match_tag_to_spec("sd500", "13", "SHD13") == "matched"


def test_match_tag_to_spec_grade_with_space_normalizes():
    assert match_tag_to_spec("SD 500", "13", "SHD13") == "matched"


def test_match_tag_to_spec_grade_with_hyphen_normalizes():
    assert match_tag_to_spec("sd-500", "13", "SHD13") == "matched"
