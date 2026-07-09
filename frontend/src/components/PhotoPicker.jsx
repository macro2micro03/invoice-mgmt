import { useEffect, useRef } from 'react'

export default function PhotoPicker({ label, accept, files, onFilesChange }) {
  const objectUrlsRef = useRef(new Map())

  useEffect(() => {
    const urls = objectUrlsRef.current
    return () => {
      urls.forEach((url) => URL.revokeObjectURL(url))
    }
  }, [])

  function getPreviewUrl(file) {
    const urls = objectUrlsRef.current
    if (!urls.has(file)) {
      urls.set(file, URL.createObjectURL(file))
    }
    return urls.get(file)
  }

  function handleAdd(event) {
    const newFiles = Array.from(event.target.files)
    if (newFiles.length > 0) {
      onFilesChange([...files, ...newFiles])
    }
    event.target.value = ''
  }

  function handleRemove(index) {
    const removed = files[index]
    if (objectUrlsRef.current.has(removed)) {
      URL.revokeObjectURL(objectUrlsRef.current.get(removed))
      objectUrlsRef.current.delete(removed)
    }
    onFilesChange(files.filter((_, i) => i !== index))
  }

  return (
    <div className="field">
      <label>{label}</label>
      <label className="btn btn-secondary photo-picker-add">
        + 사진 추가
        <input
          className="photo-picker-input"
          type="file"
          accept={accept}
          multiple
          onChange={handleAdd}
        />
      </label>
      {files.length > 0 && (
        <div className="photo-thumb-grid">
          {files.map((file, index) => (
            <div className="photo-thumb" key={`${file.name}-${index}`}>
              {file.type.startsWith('image/') ? (
                <img src={getPreviewUrl(file)} alt={file.name} />
              ) : (
                <div className="photo-thumb-file">{file.name}</div>
              )}
              <button
                type="button"
                className="photo-thumb-remove"
                onClick={() => handleRemove(index)}
                aria-label={`${file.name} 삭제`}
              >
                ×
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
