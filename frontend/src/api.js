const API_BASE = import.meta.env.VITE_API_BASE || ''

export async function runOcr(imageFile) {
  const formData = new FormData()
  formData.append('file', imageFile)
  const response = await fetch(`${API_BASE}/ocr`, { method: 'POST', body: formData })
  if (!response.ok) throw new Error('OCR 요청 실패')
  return response.json()
}

export async function createInvoice(fields, photoFile) {
  const formData = new FormData()
  Object.entries(fields).forEach(([key, value]) => {
    if (value !== null && value !== undefined && value !== '') {
      formData.append(key, value)
    }
  })
  if (photoFile) formData.append('photo', photoFile)
  const response = await fetch(`${API_BASE}/invoices`, { method: 'POST', body: formData })
  if (!response.ok) throw new Error('저장 실패')
  return response.json()
}

export async function searchInvoices(params) {
  const query = new URLSearchParams(Object.entries(params).filter(([, value]) => value)).toString()
  const response = await fetch(`${API_BASE}/invoices?${query}`)
  if (!response.ok) throw new Error('검색 실패')
  return response.json()
}

export async function getInvoice(id) {
  const response = await fetch(`${API_BASE}/invoices/${id}`)
  if (!response.ok) throw new Error('조회 실패')
  return response.json()
}

export async function updateInvoice(id, fields) {
  const response = await fetch(`${API_BASE}/invoices/${id}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(fields),
  })
  if (!response.ok) throw new Error('수정 실패')
  return response.json()
}
