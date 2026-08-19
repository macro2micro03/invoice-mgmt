import pandas as pd
import streamlit as st

import api_client
from auth import require_login
from spec_match import match_tag_against_items

st.set_page_config(page_title="촬영 — 철근 입고 관리 App.", page_icon="\U0001f4f7", layout="wide")
require_login()

st.title("송장 촬영")

COMMON_FIELDS = [("vendor", "거래처"), ("delivery_date", "납품일"), ("vehicle_no", "차량번호"), ("invoice_no", "송장번호")]
ITEM_COLUMNS = ["material_type", "item_name", "spec", "unit", "quantity", "weight", "note"]
ITEM_LABELS = {
    "material_type": "자재종류",
    "item_name": "품명",
    "spec": "규격",
    "unit": "단위",
    "quantity": "수량",
    "weight": "중량",
    "note": "비고",
}

if "records" not in st.session_state:
    st.session_state.records = None
if "photo_bytes" not in st.session_state:
    st.session_state.photo_bytes = None
if "photo_name" not in st.session_state:
    st.session_state.photo_name = None
if "tag_result" not in st.session_state:
    st.session_state.tag_result = None
if "tag_bytes" not in st.session_state:
    st.session_state.tag_bytes = None

uploaded = st.file_uploader("송장 사진 (촬영 또는 파일 선택)", type=["jpg", "jpeg", "png", "pdf"])

if uploaded is not None and uploaded.name != st.session_state.photo_name:
    st.session_state.photo_bytes = uploaded.getvalue()
    st.session_state.photo_name = uploaded.name
    with st.spinner("인식 중..."):
        try:
            result = api_client.run_ocr(st.session_state.photo_bytes, uploaded.name)
            st.session_state.records = result.get("records") or [{}]
        except api_client.ApiError as error:
            st.error(f"인식에 실패했습니다: {error}")
            st.session_state.records = [{}]
    st.session_state.tag_result = None
    st.session_state.tag_bytes = None

if st.session_state.records is not None:
    records = st.session_state.records
    first = records[0] if records else {}

    st.subheader("공통 정보")
    common_cols = st.columns(4)
    common_values = {}
    for (key, label), col in zip(COMMON_FIELDS, common_cols):
        with col:
            common_values[key] = st.text_input(label, value=first.get(key) or "", key=f"common_{key}")

    st.subheader("자재 내역 (표에서 직접 수정 가능)")
    df = pd.DataFrame(
        [{col: rec.get(col, "") for col in ITEM_COLUMNS} for rec in records]
    ).rename(columns=ITEM_LABELS)
    edited = st.data_editor(df, num_rows="dynamic", use_container_width=True, key="items_editor")
    items = edited.rename(columns={v: k for k, v in ITEM_LABELS.items()}).to_dict("records")

    st.subheader("택 촬영 (선택)")
    tag_file = st.file_uploader("택 사진", type=["jpg", "jpeg", "png"], key="tag_uploader")
    if tag_file is not None and tag_file.getvalue() != st.session_state.tag_bytes:
        st.session_state.tag_bytes = tag_file.getvalue()
        with st.spinner("택 인식 중..."):
            try:
                st.session_state.tag_result = api_client.run_tag_ocr(st.session_state.tag_bytes, tag_file.name)
            except api_client.ApiError as error:
                st.error(f"택 인식에 실패했습니다: {error}")
                st.session_state.tag_result = None

    tag_grade = ""
    tag_diameter = ""
    if st.session_state.tag_result:
        tag_grade = st.text_input("강도 (자동 인식, 다르면 직접 수정)", value=st.session_state.tag_result.get("tag_grade") or "")
        tag_diameter = st.text_input("직경 (자동 인식, 다르면 직접 수정)", value=st.session_state.tag_result.get("tag_diameter") or "")
        match = match_tag_against_items(tag_grade, tag_diameter, items)
        if match["status"] == "matched":
            st.success(f"택 규격({tag_grade} D{tag_diameter})이 일치하는 자재를 확인했습니다: {match['spec']}")
        else:
            st.warning("일치하는 등록 자재가 없습니다 — 규격을 확인해주세요.")

    can_save = len(items) > 0 and all(item.get("material_type") for item in items)
    if st.button("저장", type="primary", disabled=not can_save):
        saved = 0
        try:
            for item in items:
                fields = {**common_values, **item}
                if st.session_state.tag_result:
                    fields.update(
                        tag_site_name=st.session_state.tag_result.get("tag_site_name"),
                        tag_location=st.session_state.tag_result.get("tag_location"),
                        tag_diameter=tag_diameter,
                        tag_grade=tag_grade,
                        tag_length=st.session_state.tag_result.get("tag_length"),
                        tag_quantity=st.session_state.tag_result.get("tag_quantity"),
                        tag_shape=st.session_state.tag_result.get("tag_shape"),
                    )
                photo = (st.session_state.photo_name, st.session_state.photo_bytes) if st.session_state.photo_bytes else None
                tag_photo = (tag_file.name, st.session_state.tag_bytes) if st.session_state.tag_bytes else None
                api_client.create_invoice(fields, photo, tag_photo)
                saved += 1
            st.success(f"{saved}건 저장했습니다.")
            st.session_state.records = None
            st.session_state.photo_bytes = None
            st.session_state.photo_name = None
            st.session_state.tag_result = None
            st.session_state.tag_bytes = None
            st.rerun()
        except api_client.ApiError as error:
            st.error(f"{saved}건 저장 후 실패했습니다: {error}")
    if not can_save and items:
        st.caption("자재종류가 비어 있는 행이 있으면 저장할 수 없습니다.")
