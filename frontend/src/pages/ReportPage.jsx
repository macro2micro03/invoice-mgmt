import { useState } from 'react'
import PhotoPicker from '../components/PhotoPicker.jsx'
import { createMaterialInspectionReport } from '../api.js'

export default function ReportPage() {
  const [mode, setMode] = useState('file')
  const [projectName, setProjectName] = useState('서소문 재개발')
  const [workType, setWorkType] = useState('건축')
  const [materialType, setMaterialType] = useState('철근')
  const [sender, setSender] = useState('')
  const [receiver, setReceiver] = useState('')
  const [files, setFiles] = useState([])
  const [deliveryDate, setDeliveryDate] = useState('')
  const [topPhotos, setTopPhotos] = useState([])
  const [bottomPhotos, setBottomPhotos] = useState([])
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')
  const [generating, setGenerating] = useState(false)

  const effectiveMaterialType = mode === 'date' ? '철근' : materialType
  const canSubmit = mode === 'file' ? files.length > 0 : !!deliveryDate

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
          material_type: effectiveMaterialType,
          sender,
          receiver,
        },
        mode === 'file' ? files : [],
        topPhotos,
        bottomPhotos,
        mode === 'date' ? deliveryDate : '',
      )
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = `자재검수요청서-${effectiveMaterialType || '자재'}.xlsx`
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
    <div className="page">
      <h1>자재검수요청서 생성</h1>
      <form className="card" onSubmit={handleSubmit}>
        <div className="field">
          <label>생성 방식</label>
          <div style={{ display: 'flex', gap: 8 }}>
            <button
              type="button"
              className={`btn ${mode === 'file' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setMode('file')}
              style={{ flex: 1 }}
            >
              파일 업로드
            </button>
            <button
              type="button"
              className={`btn ${mode === 'date' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setMode('date')}
              style={{ flex: 1 }}
            >
              날짜로 생성
            </button>
          </div>
        </div>
        <div className="field">
          <label>공사명</label>
          <input className="input" value={projectName} onChange={(e) => setProjectName(e.target.value)} required />
        </div>
        <div className="field">
          <label>공종</label>
          <select className="select" value={workType} onChange={(e) => setWorkType(e.target.value)}>
            <option value="건축">건축</option>
            <option value="토목">토목</option>
            <option value="기계">기계</option>
            <option value="전기">전기</option>
          </select>
        </div>
        <div className="field">
          <label>자재종류</label>
          <input
            className="input"
            value={effectiveMaterialType}
            onChange={(e) => setMaterialType(e.target.value)}
            disabled={mode === 'date'}
            required
          />
        </div>
        <div className="field">
          <label>발신자(현장대리인)</label>
          <input className="input" value={sender} onChange={(e) => setSender(e.target.value)} required />
        </div>
        <div className="field">
          <label>수신자(총괄관리원)</label>
          <input className="input" value={receiver} onChange={(e) => setReceiver(e.target.value)} required />
        </div>
        {mode === 'file' ? (
          <PhotoPicker
            label="송장 갑지 파일 (PDF 또는 이미지, 여러 장 가능)"
            accept="application/pdf,image/*"
            files={files}
            onFilesChange={setFiles}
          />
        ) : (
          <div className="field">
            <label>반입일자</label>
            <input
              className="input"
              type="date"
              value={deliveryDate}
              onChange={(e) => setDeliveryDate(e.target.value)}
            />
          </div>
        )}
        <PhotoPicker
          label="사진대지 상단 사진 (선택, 여러 장 가능)"
          accept="image/*"
          files={topPhotos}
          onFilesChange={setTopPhotos}
        />
        <PhotoPicker
          label="사진대지 하단 사진 (선택, 여러 장 가능)"
          accept="image/*"
          files={bottomPhotos}
          onFilesChange={setBottomPhotos}
        />
        <button
          className="btn btn-primary"
          type="submit"
          disabled={generating || !canSubmit}
          style={{ width: '100%' }}
        >
          {generating ? '생성 중...' : '보고서 생성'}
        </button>
      </form>
      {error && <p className="banner banner-error">{error}</p>}
      {warning && <p className="banner banner-warning">{warning}</p>}
    </div>
  )
}
