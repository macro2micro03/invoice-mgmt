from urllib.parse import unquote

import pandas as pd
import streamlit as st

import api_client
from auth import require_login

st.set_page_config(page_title="수불부 생성 — 철근 입고 관리 App.", page_icon="\U0001f4d1", layout="wide")
require_login()

st.title("주요자재 검사 및 수불부")

selected_ids = st.session_state.get("selected_invoice_ids") or []
if selected_ids:
    st.success(f"검색에서 선택한 {len(selected_ids)}건을 수불부에 추가합니다.")
else:
    st.warning("검색 화면에서 항목을 선택한 뒤 오면 새 항목을 추가할 수 있습니다. 아래 목록만 보거나 내려받는 것은 지금도 가능합니다.")

col1, col2 = st.columns(2)
inspector = col1.text_input("검수자 (신규 추가 항목 기본값)")
supervisor = col2.text_input("담당감리원 (신규 추가 항목 기본값)")

if st.button("수불부 생성 (선택 항목 추가 + 다운로드)", type="primary", disabled=not selected_ids):
    try:
        with st.spinner("생성 중..."):
            content, warnings, filename = api_client.create_material_ledger(selected_ids, inspector, supervisor)
        if warnings:
            st.warning(unquote(warnings))
        st.success("생성 완료")
        st.download_button(
            "엑셀 다운로드",
            data=content,
            file_name=filename or "주요자재검사및수불부.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.session_state["selected_invoice_ids"] = []
    except api_client.ApiError as error:
        st.error(f"생성에 실패했습니다: {error}")

st.divider()
st.subheader("현재 수불부 포함 목록")

try:
    entries = api_client.get_ledger_entries()
except api_client.ApiError as error:
    st.error(f"목록을 불러오지 못했습니다: {error}")
    entries = []

if not entries:
    st.info("아직 수불부에 포함된 기록이 없습니다.")
else:
    df = pd.DataFrame(entries)
    manual_cols = ["defect_qty", "defect_reason", "release_date", "release_qty", "remaining_qty", "inspector", "supervisor"]
    labels = {
        "invoice_id": "연번", "delivery_date": "반입일", "spec": "규격", "weight": "반입량",
        "defect_qty": "불합격량", "defect_reason": "사유", "release_date": "반출일",
        "release_qty": "반출량", "remaining_qty": "잔량", "inspector": "검수자", "supervisor": "담당감리원",
    }
    display_cols = ["invoice_id", "delivery_date", "spec", "weight"] + manual_cols
    edited = st.data_editor(
        df[display_cols].rename(columns=labels),
        hide_index=True,
        use_container_width=True,
        disabled=[labels[c] for c in ["invoice_id", "delivery_date", "spec", "weight"]],
        key="ledger_editor",
    )
    inverse_labels = {v: k for k, v in labels.items()}

    if st.button("변경사항 저장"):
        original_by_id = {row["invoice_id"]: row for row in entries}
        saved = 0
        try:
            for _, row in edited.iterrows():
                invoice_id = int(row[labels["invoice_id"]])
                fields = {}
                for col in manual_cols:
                    value = row[labels[col]]
                    original_value = original_by_id[invoice_id].get(col)
                    if pd.isna(value):
                        value = None
                    if value != original_value:
                        fields[col] = value
                if fields:
                    api_client.update_ledger_entry(invoice_id, fields)
                    saved += 1
            st.success(f"{saved}건 저장했습니다." if saved else "변경된 내용이 없습니다.")
            st.rerun()
        except api_client.ApiError as error:
            st.error(f"저장에 실패했습니다: {error}")

    st.caption("제외할 연번을 선택하세요 (송장 기록 자체는 삭제되지 않습니다).")
    exclude_id = st.selectbox("제외할 연번", options=[e["invoice_id"] for e in entries])
    if st.button("선택 항목 수불부에서 제외"):
        try:
            api_client.delete_ledger_entry(exclude_id)
            st.success("제외했습니다.")
            st.rerun()
        except api_client.ApiError as error:
            st.error(f"제외에 실패했습니다: {error}")
