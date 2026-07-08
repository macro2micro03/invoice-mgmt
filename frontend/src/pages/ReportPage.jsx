import { useState } from 'react'
import { createMaterialInspectionReport } from '../api.js'

export default function ReportPage() {
  const [projectName, setProjectName] = useState('')
  const [workType, setWorkType] = useState('건축')
  const [materialType, setMaterialType] = useState('')
  const [sender, setSender] = useState('')
  const [receiver, setReceiver] = useState('')
  const [files, setFiles] = useState([])
  const [topPhotos, setTopPhotos] = useState([])
  const [bottomPhotos, setBottomPhotos] = useState([])
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')
  const [generating, setGenerating] = useState(false)

  function handleFilesChange(event) {
    setFiles(Array.from(event.target.files))
  }

  function handleTopPhotosChange(event) {
    setTopPhotos(Array.from(event.target.files))
  }

  function handleBottomPhotosChange(event) {
    setBottomPhotos(Array.from(event.target.files))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setWarning('')
    setGenerating(true)
    try {
      const { blob, warnings } = await createMaterialInspectionReport(
        {
          project_name: projectName,
          work_type: workType,
          material_type: materialType,
          sender,
          receiver,
        },
        files,
        topPhotos,
        bottomPhotos,
      )
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `자재검수요청서-${materialType || '자재'}.xlsx`
      link.click()
      URL.revokeObjectURL(url)
      if (warnings) {
        setWarning(warnings)
      }
    } catch (err) {
      setError(err.message || '보고서 생성에 실패했습니다')
    } finally {
      setGenerating(false)
    }
  }

  return (
    <div style={{ padding: 16 }}>
      <h1>자재검수요청서 생성</h1>
      <form onSubmit={handleSubmit}>
        <div>
          <label>
            공사명
            <input value={projectName} onChange={(e) => setProjectName(e.target.value)} required />
          </label>
        </div>
        <div>
          <label>
            공종
            <select value={workType} onChange={(e) => setWorkType(e.target.value)}>
              <option value="건축">건축</option>
              <option value="토목">토목</option>
              <option value="기계">기계</option>
              <option value="전기">전기</option>
            </select>
          </label>
        </div>
        <div>
          <label>
            자재종류
            <input value={materialType} onChange={(e) => setMaterialType(e.target.value)} required />
          </label>
        </div>
        <div>
          <label>
            발신자(현장대리인)
            <input value={sender} onChange={(e) => setSender(e.target.value)} required />
          </label>
        </div>
        <div>
          <label>
            수신자(총괄관리원)
            <input value={receiver} onChange={(e) => setReceiver(e.target.value)} required />
          </label>
        </div>
        <div>
          <label>
            송장 갑지 파일 (PDF 또는 이미지, 여러 장 가능)
            <input type="file" accept="application/pdf,image/*" multiple onChange={handleFilesChange} required />
          </label>
        </div>
        <div>
          <label>
            사진대지 상단 사진 (선택, 여러 장 가능)
            <input type="file" accept="image/*" multiple onChange={handleTopPhotosChange} />
          </label>
        </div>
        <div>
          <label>
            사진대지 하단 사진 (선택, 여러 장 가능)
            <input type="file" accept="image/*" multiple onChange={handleBottomPhotosChange} />
          </label>
        </div>
        <button type="submit" disabled={generating || files.length === 0}>
          {generating ? '생성 중...' : '보고서 생성'}
        </button>
      </form>
      {error && <p style={{ color: 'red' }}>{error}</p>}
      {warning && <p style={{ color: '#b8860b' }}>{warning}</p>}
    </div>
  )
}
