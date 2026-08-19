"""기존 FastAPI 백엔드에 대한 얇은 REST 클라이언트.

프론트엔드(frontend/src/api.js)와 동일한 엔드포인트·필드를 사용한다.
이 파일의 모든 요청은 (브라우저가 아니라) Streamlit 서버 프로세스에서
직접 나가므로, 사용자 PC의 사내망 프록시/방화벽이 개별 외부 도메인을
막더라도 이 서버-서버 호출에는 영향을 주지 않는다.
"""
import os

import requests
import streamlit as st

API_BASE = os.environ.get("API_BASE", "https://invoice-mgmt-backend.onrender.com")
TIMEOUT = 60


class ApiError(Exception):
    pass


def _headers(extra: dict | None = None) -> dict:
    headers = {"X-App-Password": st.session_state.get("app_password", "")}
    if extra:
        headers.update(extra)
    return headers


def _raise_for_status(response: requests.Response, default_message: str) -> None:
    if response.status_code == 401:
        st.session_state.pop("app_password", None)
        raise ApiError("인증이 만료되었습니다. 다시 로그인해주세요.")
    if not response.ok:
        try:
            detail = response.json().get("detail")
        except Exception:
            detail = None
        raise ApiError(detail or default_message)


def check_password(password: str) -> bool:
    response = requests.get(
        f"{API_BASE}/invoices", headers={"X-App-Password": password}, timeout=TIMEOUT
    )
    return response.status_code != 401


def run_ocr(file_bytes: bytes, filename: str) -> dict:
    response = requests.post(
        f"{API_BASE}/ocr",
        headers=_headers(),
        files={"file": (filename, file_bytes)},
        timeout=TIMEOUT,
    )
    _raise_for_status(response, "OCR 요청 실패")
    return response.json()


def run_tag_ocr(file_bytes: bytes, filename: str, spec: str | None = None) -> dict:
    data = {"spec": spec} if spec else {}
    response = requests.post(
        f"{API_BASE}/ocr/tag",
        headers=_headers(),
        files={"file": (filename, file_bytes)},
        data=data,
        timeout=TIMEOUT,
    )
    _raise_for_status(response, "택 인식 요청 실패")
    return response.json()


def create_invoice(fields: dict, photo: tuple[str, bytes] | None, tag_photo: tuple[str, bytes] | None) -> dict:
    data = {k: v for k, v in fields.items() if v not in (None, "")}
    files = {}
    if photo:
        files["photo"] = photo
    if tag_photo:
        files["tag_photo"] = tag_photo
    response = requests.post(
        f"{API_BASE}/invoices", headers=_headers(), data=data, files=files or None, timeout=TIMEOUT
    )
    _raise_for_status(response, "저장 실패")
    return response.json()


def search_invoices(params: dict) -> list[dict]:
    query = {k: v for k, v in params.items() if v}
    response = requests.get(f"{API_BASE}/invoices", headers=_headers(), params=query, timeout=TIMEOUT)
    _raise_for_status(response, "검색 실패")
    return response.json()


def get_invoice(invoice_id: int) -> dict:
    response = requests.get(f"{API_BASE}/invoices/{invoice_id}", headers=_headers(), timeout=TIMEOUT)
    _raise_for_status(response, "조회 실패")
    return response.json()


def update_invoice(invoice_id: int, fields: dict) -> dict:
    response = requests.put(
        f"{API_BASE}/invoices/{invoice_id}", headers=_headers(), json=fields, timeout=TIMEOUT
    )
    _raise_for_status(response, "수정 실패")
    return response.json()


def delete_invoice(invoice_id: int) -> None:
    response = requests.delete(f"{API_BASE}/invoices/{invoice_id}", headers=_headers(), timeout=TIMEOUT)
    _raise_for_status(response, "삭제 실패")


def bulk_delete_invoices(ids: list[int]) -> dict:
    response = requests.post(
        f"{API_BASE}/invoices/bulk-delete", headers=_headers(), json={"ids": ids}, timeout=TIMEOUT
    )
    _raise_for_status(response, "일괄 삭제 실패")
    return response.json()


def create_material_inspection_report(
    fields: dict,
    files: list[tuple[str, bytes]],
    photo_sets: list[dict] | None = None,
    delivery_date: str = "",
    invoice_ids: list[int] | None = None,
) -> tuple[bytes, str | None, str | None]:
    data = dict(fields)
    if delivery_date:
        data["delivery_date"] = delivery_date
    if invoice_ids:
        data["invoice_ids"] = ",".join(str(i) for i in invoice_ids)

    multipart = [("files", (name, content)) for name, content in files]
    for index, photo_set in enumerate(photo_sets or [], start=1):
        for name, content in photo_set.get("top", []):
            multipart.append((f"photo_set_{index}_top", (name, content)))
        for name, content in photo_set.get("bottom", []):
            multipart.append((f"photo_set_{index}_bottom", (name, content)))

    response = requests.post(
        f"{API_BASE}/reports/material-inspection",
        headers=_headers(),
        data=data,
        files=multipart or None,
        timeout=TIMEOUT,
    )
    _raise_for_status(response, "보고서 생성에 실패했습니다")
    warnings = response.headers.get("X-Report-Warnings")
    filename = _extract_filename(response.headers.get("Content-Disposition", ""))
    return response.content, warnings, filename


def create_material_ledger(invoice_ids: list[int], inspector: str, supervisor: str) -> tuple[bytes, str | None, str | None]:
    data = {"invoice_ids": ",".join(str(i) for i in invoice_ids), "inspector": inspector, "supervisor": supervisor}
    response = requests.post(f"{API_BASE}/reports/material-ledger", headers=_headers(), data=data, timeout=TIMEOUT)
    _raise_for_status(response, "수불부 생성에 실패했습니다")
    warnings = response.headers.get("X-Report-Warnings")
    filename = _extract_filename(response.headers.get("Content-Disposition", ""))
    return response.content, warnings, filename


def get_ledger_entries() -> list[dict]:
    response = requests.get(f"{API_BASE}/reports/material-ledger/entries", headers=_headers(), timeout=TIMEOUT)
    _raise_for_status(response, "수불부 목록 조회 실패")
    return response.json()


def update_ledger_entry(invoice_id: int, fields: dict) -> dict:
    response = requests.put(
        f"{API_BASE}/reports/material-ledger/entries/{invoice_id}", headers=_headers(), json=fields, timeout=TIMEOUT
    )
    _raise_for_status(response, "수불부 항목 수정 실패")
    return response.json()


def delete_ledger_entry(invoice_id: int) -> None:
    response = requests.delete(
        f"{API_BASE}/reports/material-ledger/entries/{invoice_id}", headers=_headers(), timeout=TIMEOUT
    )
    _raise_for_status(response, "수불부 항목 삭제 실패")


def _extract_filename(content_disposition: str) -> str | None:
    marker = "filename*=UTF-8''"
    if marker not in content_disposition:
        return None
    from urllib.parse import unquote

    return unquote(content_disposition.split(marker, 1)[1].split(";", 1)[0])
