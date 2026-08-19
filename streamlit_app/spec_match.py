"""택 강도/직경과 규격 매칭 로직.

backend/app/spec_grade.py와 동일한 규칙이다 — 별도 배포本(Render 등)에서
독립적으로 실행되는 Streamlit 앱이라 백엔드 패키지를 import하지 않고
이 작은 순수 로직만 복제해 둔다(frontend/src/pages/EditPage.jsx도 동일하게
독립 복제하고 있다). backend/app/spec_grade.py가 바뀌면 이 파일도 맞춰 바꿔야 한다.
"""
import re

GRADE_BY_PREFIX = {"SD": "SD400", "SHD": "SD500", "UHD": "SD600"}


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


def match_tag_against_items(tag_grade: str | None, tag_diameter: str | None, items: list[dict]):
    for item in items:
        if match_tag_to_spec(tag_grade, tag_diameter, item.get("spec", "")) == "matched":
            return {"status": "matched", "spec": item.get("spec")}
    return {"status": "mismatched", "spec": None}
