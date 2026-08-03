import re

GRADE_BY_PREFIX = {
    "SHD": "SD500",
    "UHD": "SD600",
}


def parse_spec_grade_diameter(spec: str) -> tuple[str | None, str | None]:
    if not spec:
        return None, None
    spec_upper = spec.strip().upper()
    for prefix, grade in GRADE_BY_PREFIX.items():
        if spec_upper.startswith(prefix):
            diameter = re.sub(r"[^0-9]", "", spec_upper[len(prefix):])
            return grade, diameter or None
    return None, None


def _normalize_diameter(value: str | None) -> str | None:
    if not value:
        return None
    digits = re.sub(r"[^0-9]", "", value)
    return digits or None


def _normalize_grade(value: str | None) -> str | None:
    if not value:
        return None
    normalized = re.sub(r"[^A-Z0-9]", "", value.strip().upper())
    return normalized or None


def match_tag_to_spec(tag_grade: str | None, tag_diameter: str | None, spec: str) -> str | None:
    spec_grade, spec_diameter = parse_spec_grade_diameter(spec)
    norm_tag_grade = _normalize_grade(tag_grade)
    norm_tag_diameter = _normalize_diameter(tag_diameter)
    if spec_grade is None or norm_tag_grade is None or norm_tag_diameter is None:
        return None
    if spec_grade == norm_tag_grade and spec_diameter == norm_tag_diameter:
        return "matched"
    return "mismatched"
