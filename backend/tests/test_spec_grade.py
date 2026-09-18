from app.spec_grade import match_manufacturer, match_tag_to_spec, normalize_manufacturer, parse_spec_grade_diameter


def test_parse_spec_grade_diameter_sd_is_sd400():
    assert parse_spec_grade_diameter("SD13") == ("SD400", "13")


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


def test_normalize_manufacturer_matches_code_case_insensitive():
    assert normalize_manufacturer("HS") == "현대제철"
    assert normalize_manufacturer("hs") == "현대제철"
    assert normalize_manufacturer("dk") == "동국제강"


def test_normalize_manufacturer_matches_full_name():
    assert normalize_manufacturer("동국제강") == "동국제강"


def test_normalize_manufacturer_strips_corporate_markers():
    assert normalize_manufacturer("㈜대한제강") == "대한제강"
    assert normalize_manufacturer("주식회사 한국철강") == "한국철강"
    assert normalize_manufacturer("(주)환영철강") == "환영철강"


def test_normalize_manufacturer_matches_with_extra_info():
    assert normalize_manufacturer("동국제강(부산공장)") == "동국제강"


def test_normalize_manufacturer_outside_pool_returns_none():
    assert normalize_manufacturer("알수없는제강") is None


def test_normalize_manufacturer_empty_or_none_returns_none():
    assert normalize_manufacturer("") is None
    assert normalize_manufacturer(None) is None


def test_match_manufacturer_matched_across_code_and_name():
    assert match_manufacturer("HS", "현대제철") == "matched"


def test_match_manufacturer_matched_with_corporate_marker_difference():
    assert match_manufacturer("㈜동국제강", "동국제강") == "matched"


def test_match_manufacturer_mismatched():
    assert match_manufacturer("HS", "동국제강") == "mismatched"


def test_match_manufacturer_returns_none_when_tag_manufacturer_missing():
    assert match_manufacturer(None, "동국제강") is None
    assert match_manufacturer("", "동국제강") is None


def test_match_manufacturer_returns_none_when_note_missing():
    assert match_manufacturer("HS", None) is None
    assert match_manufacturer("HS", "") is None


def test_match_manufacturer_returns_none_when_note_outside_pool():
    assert match_manufacturer("HS", "이상한업체") is None
