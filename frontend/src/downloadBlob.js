export function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  link.click()
  // 일부 모바일 브라우저는 다운로드를 비동기로 가져가므로, revoke를
  // 곧바로 하면 다운로드가 깨질 수 있어 살짝 지연시킨다.
  setTimeout(() => URL.revokeObjectURL(url), 2000)
}
