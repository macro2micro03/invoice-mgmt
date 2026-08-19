import streamlit as st


def require_login() -> None:
    """페이지를 직접 열어 들어온 경우에도 로그인 상태를 강제한다."""
    if not st.session_state.get("app_password"):
        st.warning("먼저 로그인해주세요.")
        st.page_link("app.py", label="로그인 화면으로 이동")
        st.stop()
