const API_BASE = import.meta.env.VITE_API_BASE || ''

function authHeaders() {
  return { 'X-App-Password': sessionStorage.getItem('appPassword') || '' }
}

function handleUnauthorized(response) {
  if (response.status === 401) {
    sessionStorage.removeItem('appPassword')
    window.location.reload()
    throw new Error('인증이 만료되었습니다')
  }
}

export async function runOcr(imageFile) {
  const formData = new FormData()
  formData.append('file', imageFile)
  const response = await fetch(`${API_BASE}/ocr`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error('OCR 요청 실패')
  return response.json()
}

export async function runTagOcr(imageFile, spec) {
  const formData = new FormData()
  formData.append('file', imageFile)
  if (spec) formData.append('spec', spec)
  const response = await fetch(`${API_BASE}/ocr/tag`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error('택 인식 요청 실패')
  return response.json()
}

export async function createInvoice(fields, photoFile, tagPhotoFile) {
  const formData = new FormData()
  Object.entries(fields).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      formData.append(key, value)
    }
  })
  if (photoFile) formData.append('photo', photoFile)
  if (tagPhotoFile) formData.append('tag_photo', tagPhotoFile)
  const response = await fetch(`${API_BASE}/invoices`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error('저장 실패')
  return response.json()
}

export async function searchInvoices(params) {
  const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value)).toString()
  const response = await fetch(`${API_BASE}/invoices?${query}`, {
    headers: authHeaders(),
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error('검색 실패')
  return response.json()
}

export async function getInvoice(id) {
  const response = await fetch(`${API_BASE}/invoices/${id}`, {
    headers: authHeaders(),
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error('조회 실패')
  return response.json()
}

export async function deleteInvoice(id) {
  const response = await fetch(`${API_BASE}/invoices/${id}`, {
    method: 'DELETE',
    headers: authHeaders(),
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error('삭제 실패')
}

export async function bulkDeleteInvoices(ids) {
  const response = await fetch(`${API_BASE}/invoices/bulk-delete`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify({ ids }),
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error('일괄 삭제 실패')
  return response.json()
}

export async function updateInvoice(id, fields) {
  const response = await fetch(`${API_BASE}/invoices/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json', ...authHeaders() },
    body: JSON.stringify(fields),
  })
  handleUnauthorized(response)
  if (!response.ok) throw new Error('수정 실패')
  return response.json()
}

export async function createMaterialInspectionReport(fields, files, photoSets = [], deliveryDate = '') {
  const formData = new FormData()
  Object.entries(fields).forEach(([key, value]) => {
    formData.append(key, value)
  })
  files.forEach((file) => {
    formData.append('files', file)
  })
  const nonEmptySets = photoSets.filter((set) => set.top.length > 0 || set.bottom.length > 0)
  nonEmptySets.forEach((set, index) => {
    const setNumber = index + 1
    set.top.forEach((file) => {
      formData.append(`photo_set_${setNumber}_top`, file)
    })
    set.bottom.forEach((file) => {
      formData.append(`photo_set_${setNumber}_bottom`, file)
    })
  })
  if (deliveryDate) {
    formData.append('delivery_date', deliveryDate)
  }
  const response = await fetch(`${API_BASE}/reports/material-inspection`, {
    method: 'POST',
    headers: authHeaders(),
    body: formData,
  })
  handleUnauthorized(response)
  if (!response.ok) {
    const body = await response.json().catch(() => ({}))
    throw new Error(body.detail || '보고서 생성에 실패했습니다')
  }
  const blob = await response.blob()
  const encodedWarnings = response.headers.get('X-Report-Warnings')
  const warnings = encodedWarnings ? decodeURIComponent(encodedWarnings) : null
  return { blob, warnings }
}
