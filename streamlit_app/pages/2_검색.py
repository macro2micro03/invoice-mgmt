import pandas as pd
import streamlit as st

import api_client
from auth import require_login

st.set_page_config(page_title="검색 — 철근 입고 관리 App.", page_icon="\U0001f50d", layout="wide")
require_login()

st.title("송장 검색")

with st.form("search_form"):
    cols = st.columns(4)
    vendor = cols[0].text_input("거래처")
    material_type = cols[1].text_input("자재종류")
    invoice_no = cols[2].text_input("송장번호")
    delivery_date = cols[3].date_input("납품일", value=None)
    submitted = st.form_submit_button("검색")

if "search_results" not in st.session_state:
    st.session_state.search_results = None

if submitted or st.session_state.search_results is None:
    params = {
        "vendor": vendor,
        "material_type": material_type,
        "invoice_no": invoice_no,
        "delivery_date": delivery_date.isoformat() if delivery_date else "",
    }
    try:
        st.session_state.search_results = api_client.search_invoices(params)
    except api_client.ApiError as error:
        st.error(f"검색에 실패했습니다: {error}")
        st.session_state.search_results = []

results = st.session_state.search_results or []
st.caption(f"{len(results)}건")

if results:
    df = pd.DataFrame(results)
    display_cols = [
        "id", "vendor", "material_type", "spec", "delivery_date", "invoice_no",
        "quantity", "weight", "tag_match_status",
    ]
    display_cols = [c for c in display_cols if c in df.columns]
    df["선택"] = False
    edited = st.data_editor(
        df[["선택"] + display_cols],
        hide_index=True,
        use_container_width=True,
        disabled=display_cols,
        key="search_table",
    )

    selected_ids = edited.loc[edited["선택"], "id"].tolist()
    st.session_state["selected_invoice_ids"] = selected_ids
    st.caption(f"{len(selected_ids)}건 선택됨 — 보고서/수불부 생성 화면에서 이어서 사용할 수 있습니다.")

    col_a, col_b = st.columns(2)
    with col_a:
        if st.button("선택 항목 삭제", disabled=not selected_ids):
            try:
                api_client.bulk_delete_invoices(selected_ids)
                st.success(f"{len(selected_ids)}건 삭제했습니다.")
                st.session_state.search_results = None
                st.rerun()
            except api_client.ApiError as error:
                st.error(f"삭제에 실패했습니다: {error}")
    with col_b:
        st.page_link("pages/4_수불부_생성.py", label="선택 항목으로 수불부 생성 →")
else:
    st.info("검색 결과가 없습니다.")
