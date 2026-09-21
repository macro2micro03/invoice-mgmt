from app.spec_grade import (
    match_manufacturer,
    match_tag_to_spec,
    normalize_manufacturer,
    normalize_manufacturers,
    parse_spec_grade_diameter,
)


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


def test_normalize_manufacturer_matches_code_with_stray_whitespace_or_markers():
    assert normalize_manufacturer("D K") == "동국제강"
    assert normalize_manufacturer("(주)DK") == "동국제강"


def test_normalize_manufacturer_matches_full_name():
    assert normalize_manufacturer("동국제강") == "동국제강"


def test_normalize_manufacturer_strips_corporate_markers():
    assert normalize_manufacturer("㈜대한제강") == "대한제강"
    assert normalize_manufacturer("주식회사 한국철강") == "한국철강"
    assert normalize_manufacturer("(주)환영철강") == "환영철강"


def test_normalize_manufacturer_matches_with_extra_info():
    assert normalize_manufacturer("동국제강(부산공장)") == "동국제강"


def test_normalize_manufacturer_does_not_match_generic_substring_of_canonical_name():
    # "제강"/"철강"은 "제철소"라는 뜻의 일반 명사일 뿐 특정 업체를 가리키지
    # 않는다. 여러 풀 항목(동국제강/대한제강/한국제강, 한국철강/환영철강)의
    # 부분 문자열이라서, 이런 짧은 조각만으로 특정 업체로 단정하면 사전
    # 순서에 따라 틀린 업체로 오판정될 위험이 있다.
    assert normalize_manufacturer("제강") is None
    assert normalize_manufacturer("철강") is None


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


def test_normalize_manufacturers_returns_multiple_candidates():
    # "현대"는 "현대제철"의 실제 택에서 확인된 축약 표기다.
    assert normalize_manufacturers("동국제강,현대") == ["동국제강", "현대제철"]


def test_normalize_manufacturers_returns_multiple_codes_comma_separated():
    # LLM이 "코드나 정식명칭을 콤마로 구분해서" 답할 때의 형태.
    assert normalize_manufacturers("DK,HS") == ["동국제강", "현대제철"]
    assert normalize_manufacturers("DK, HS") == ["동국제강", "현대제철"]


def test_normalize_manufacturers_single_code_returns_one_item_list():
    assert normalize_manufacturers("HS") == ["현대제철"]


def test_normalize_manufacturers_recognizes_korean_abbreviation():
    assert normalize_manufacturers("현대") == ["현대제철"]


def test_normalize_manufacturers_recognizes_english_alias():
    assert normalize_manufacturers("DONGKUK STEEL MILL CO., LTD.") == ["동국제강"]
    assert normalize_manufacturers("STEEL MADE IN KOREA HYUNDAI 인천공장") == ["현대제철"]


def test_normalize_manufacturers_does_not_split_english_corporate_suffix_comma():
    # "CO., LTD."의 콤마 때문에 문자열을 분리하면 안 된다 — 분리했다면
    # "LTD." 쪽 토큰만 남아 DONGKUK을 못 찾았을 것이다.
    assert normalize_manufacturers("DONGKUK STEEL MILL CO., LTD.") == ["동국제강"]


def test_normalize_manufacturers_outside_pool_returns_empty_list():
    assert normalize_manufacturers("알수없는업체") == []


def test_normalize_manufacturers_empty_or_none_returns_empty_list():
    assert normalize_manufacturers("") == []
    assert normalize_manufacturers(None) == []


def test_normalize_manufacturers_still_rejects_generic_substring():
    # 기존에 고친 "제강"/"철강" 오판정 방지가 별칭 로직 추가로 깨지지 않아야 한다.
    assert normalize_manufacturers("제강") == []
    assert normalize_manufacturers("철강") == []


def test_normalize_manufacturer_single_value_unchanged():
    assert normalize_manufacturer("HS") == "현대제철"
    assert normalize_manufacturer("현대") == "현대제철"
    assert normalize_manufacturer("알수없는업체") is None


def test_match_manufacturer_matches_when_note_equals_any_candidate():
    assert match_manufacturer("동국제강,현대", "현대제철") == "matched"
    assert match_manufacturer("동국제강,현대", "동국제강") == "matched"


def test_match_manufacturer_mismatched_when_note_matches_none_of_candidates():
    assert match_manufacturer("동국제강,현대", "대한제강") == "mismatched"
