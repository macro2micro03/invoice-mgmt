import streamlit as st

import api_client
import auth

st.set_page_config(page_title="철근 입고 관리 App.", page_icon="\U0001f529", layout="wide")


def login_gate() -> bool:
    auth.restore_session()
    if st.session_state.get("app_password"):
        return True

    st.title("철근 입고 관리 App.")
    st.caption("사내망에서 Vercel 접속이 불안정할 때 쓰는 대체 접속 경로입니다.")
    with st.form("login"):
        password = st.text_input("비밀번호", type="password")
        submitted = st.form_submit_button("확인")
    if submitted:
        if not password:
            st.error("비밀번호를 입력해주세요")
        elif api_client.check_password(password):
            auth.login(password)
            st.rerun()
        else:
            st.error("비밀번호가 올바르지 않습니다")
    return False


if not login_gate():
    st.stop()

st.title("철근 입고 관리 App.")
st.write("왼쪽 사이드바에서 원하는 기능을 선택하세요.")
st.markdown(
    """
- **등록** — 송장 사진을 올리면 자동으로 인식해 저장합니다
- **검색** — 저장된 송장 기록을 조회·수정·삭제합니다
- **보고서 생성** — 주요자재 검사요청서(엑셀)를 생성합니다
- **수불부 개정** — 주요자재 검사 및 수불부(엑셀)를 생성·관리합니다
"""
)

with st.sidebar:
    if st.button("로그아웃"):
        auth.logout()
        st.rerun()
