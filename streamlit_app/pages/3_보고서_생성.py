import streamlit as st

import api_client
from auth import require_login

st.set_page_config(page_title="보고서 생성 — 철근 입고 관리 App.", page_icon="\U0001f4c4", layout="wide")
require_login()

st.title("주요자재 검사요청서 생성")

selected_ids = st.session_state.get("selected_invoice_ids") or []
if selected_ids:
    st.info(f"검색에서 선택한 {len(selected_ids)}건을 사용합니다.")

mode = st.radio(
    "자재 내역을 어떻게 채울까요?",
    ["선택한 검색 결과 사용", "반입일자로 집계", "송장 사진 직접 업로드"],
    index=0 if selected_ids else 2,
    horizontal=True,
)

delivery_date = ""
files = []
if mode == "반입일자로 집계":
    delivery_date_input = st.date_input("반입일자", value=None)
    delivery_date = delivery_date_input.isoformat() if delivery_date_input else ""
elif mode == "송장 사진 직접 업로드":
    uploads = st.file_uploader("송장 사진 (여러 장 가능)", type=["jpg", "jpeg", "png"], accept_multiple_files=True)
    files = [(f.name, f.getvalue()) for f in uploads] if uploads else []

with st.form("report_form"):
    project_name = st.text_input("공사명")
    work_type = st.selectbox("공종", ["건축", "토목", "설비", "전기"])
    material_type = st.text_input("자재종류", value="철근")
    sender = st.text_input("시공담당자")
    receiver = st.text_input("담당감리자")

    st.subheader("사진대지 (선택, 최대 5세트)")
    photo_sets = []
    for i in range(1, 6):
        with st.expander(f"사진 세트 {i}"):
            top = st.file_uploader(f"상단 사진 {i}", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key=f"top_{i}")
            bottom = st.file_uploader(f"하단 사진 {i}", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key=f"bottom_{i}")
            photo_sets.append(
                {
                    "top": [(f.name, f.getvalue()) for f in top] if top else [],
                    "bottom": [(f.name, f.getvalue()) for f in bottom] if bottom else [],
                }
            )

    submitted = st.form_submit_button("보고서 생성", type="primary")

if submitted:
    if mode == "선택한 검색 결과 사용" and not selected_ids:
        st.error("검색 화면에서 항목을 먼저 선택해주세요.")
    elif mode == "반입일자로 집계" and not delivery_date:
        st.error("반입일자를 선택해주세요.")
    elif mode == "송장 사진 직접 업로드" and not files:
        st.error("송장 사진을 업로드해주세요.")
    elif not (project_name and sender and receiver):
        st.error("공사명·시공담당자·담당감리자를 입력해주세요.")
    else:
        try:
            with st.spinner("생성 중..."):
                content, warnings, filename = api_client.create_material_inspection_report(
                    fields={
                        "project_name": project_name,
                        "work_type": work_type,
                        "material_type": material_type,
                        "sender": sender,
                        "receiver": receiver,
                    },
                    files=files,
                    photo_sets=photo_sets,
                    delivery_date=delivery_date,
                    invoice_ids=selected_ids if mode == "선택한 검색 결과 사용" else None,
                )
            if warnings:
                from urllib.parse import unquote

                st.warning(unquote(warnings))
            st.success("생성 완료")
            st.download_button(
                "엑셀 다운로드",
                data=content,
                file_name=filename or "자재검수요청서.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        except api_client.ApiError as error:
            st.error(f"생성에 실패했습니다: {error}")
