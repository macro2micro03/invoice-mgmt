import streamlit as st

import api_client


def restore_session() -> None:
    """새로고침으로 세션이 초기화돼도 로그인 상태가 풀리지 않도록,
    URL 쿼리스트링에 저장해 둔 비밀번호로 세션을 복원한다.

    Streamlit의 session_state는 브라우저 새로고침 시 완전히 새로운
    세션으로 취급돼 매번 사라진다. 반면 쿼리스트링은 새로고침해도
    URL에 그대로 남아있으므로, 여기에 비밀번호를 저장해 뒀다가 매
    페이지 로드 시 이 값으로 재검증한다. (내부 도구이고 이미 단일
    공유 비밀번호를 헤더로 매 요청마다 보내는 구조라, URL에 저장해도
    기존 대비 보안 수준이 낮아지지 않는다.)
    """
    if not st.session_state.get("app_password"):
        saved = st.query_params.get("pw")
        if saved:
            if api_client.check_password(saved):
                st.session_state["app_password"] = saved
            else:
                del st.query_params["pw"]

    # Streamlit 멀티페이지 앱은 사이드바로 다른 페이지로 이동할 때
    # 쿼리스트링을 URL에서 지워버린다(같은 세션이라 session_state는
    # 그대로 남지만, 이 상태에서 그대로 새로고침하면 쿼리스트링이 없어
    # 복원할 수 없다). 그래서 페이지를 이동할 때마다 항상 다시 넣어준다.
    password = st.session_state.get("app_password")
    if password and st.query_params.get("pw") != password:
        st.query_params["pw"] = password


def login(password: str) -> None:
    st.session_state["app_password"] = password
    st.query_params["pw"] = password


def logout() -> None:
    st.session_state.pop("app_password", None)
    if "pw" in st.query_params:
        del st.query_params["pw"]


def require_login() -> None:
    """페이지를 직접 열어 들어온 경우에도 로그인 상태를 강제한다."""
    restore_session()
    if not st.session_state.get("app_password"):
        st.warning("먼저 로그인해주세요.")
        st.page_link("app.py", label="로그인 화면으로 이동")
        st.stop()
