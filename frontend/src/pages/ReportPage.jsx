import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import PhotoPicker from '../components/PhotoPicker.jsx'
import EmailSendCard from '../components/EmailSendCard.jsx'
import { createMaterialInspectionReport } from '../api.js'

const MAX_PHOTO_SETS = 5

export default function ReportPage() {
  const location = useLocation()
  const invoiceIds = location.state?.invoiceIds ?? []
  const [mode, setMode] = useState(invoiceIds.length > 0 ? 'selected' : 'file')
  const [projectName, setProjectName] = useState('서소문 재개발')
  const [workType, setWorkType] = useState('건축')
  const [materialType, setMaterialType] = useState('철근')
  const [sender, setSender] = useState('')
  const [receiver, setReceiver] = useState('')
  const [files, setFiles] = useState([])
  const [photoSets, setPhotoSets] = useState([{ top: [], bottom: [] }])
  const [error, setError] = useState('')
  const [warning, setWarning] = useState('')
  const [generating, setGenerating] = useState(false)
  const [generatedFile, setGeneratedFile] = useState(null)

  const canSubmit = mode === 'file' ? files.length > 0 : invoiceIds.length > 0

  function handleAddPhotoSet() {
    setPhotoSets((prev) => (prev.length < MAX_PHOTO_SETS ? [...prev, { top: [], bottom: [] }] : prev))
  }

  function handleSetTopChange(index, newFiles) {
    setPhotoSets((prev) => prev.map((set, i) => (i === index ? { ...set, top: newFiles } : set)))
  }

  function handleSetBottomChange(index, newFiles) {
    setPhotoSets((prev) => prev.map((set, i) => (i === index ? { ...set, bottom: newFiles } : set)))
  }

  async function handleSubmit(event) {
    event.preventDefault()
    setError('')
    setWarning('')
    setGenerating(true)
    setGeneratedFile(null)
    try {
      const { blob, warnings, filename } = await createMaterialInspectionReport(
        {
          project_name: projectName,
          work_type: workType,
          material_type: materialType,
          sender,
          receiver,
        },
        mode === 'file' ? files : [],
        photoSets,
        '',
        mode === 'selected' ? invoiceIds : [],
      )
      const resolvedFilename = filename || `자재검수요청서-${materialType || '자재'}.xlsx`
      // 모바일 브라우저 일부는 download 트리거가 페이지 이동처럼 동작하거나
      // 비동기로 blob을 가져가는 경우가 있어, 그 직후 상태를 지우거나 URL을
      // 곧바로 해제하면 이메일 발송 카드가 안 뜨거나 다운로드가 깨질 수
      // 있다. 클릭 전에 상태를 먼저 반영하고, URL 해제도 지연시킨다.
      setGeneratedFile({ blob, filename: resolvedFilename })
      const url = URL.createObjectURL(blob)
      const link = document.createElement('a')
      link.href = url
      link.download = resolvedFilename
      link.click()
      setTimeout(() => URL.revokeObjectURL(url), 2000)
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
              className={`btn ${mode === 'selected' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setMode('selected')}
              style={{ flex: 1 }}
            >
              선택 항목 ({invoiceIds.length}건)
            </button>
            <button
              type="button"
              className={`btn ${mode === 'file' ? 'btn-primary' : 'btn-secondary'}`}
              onClick={() => setMode('file')}
              style={{ flex: 1 }}
            >
              파일 업로드
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
            value={materialType}
            onChange={(e) => setMaterialType(e.target.value)}
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
        {mode === 'file' && (
          <PhotoPicker
            label="송장 갑지 파일 (PDF 또는 이미지, 여러 장 가능)"
            accept="application/pdf,image/*"
            files={files}
            onFilesChange={setFiles}
          />
        )}
        {mode === 'selected' && (
          <p className="banner banner-success">
            검색에서 선택한 {invoiceIds.length}건의 촬영 기록으로 보고서를 생성합니다.
          </p>
        )}
        {photoSets.map((set, index) => (
          <div key={index} className="card item-card">
            <p className="field-group-label">사진대지 {index + 1}세트</p>
            <PhotoPicker
              label={`사진대지 ${index + 1}세트 상단 사진 (선택, 여러 장 가능)`}
              accept="image/*"
              files={set.top}
              onFilesChange={(newFiles) => handleSetTopChange(index, newFiles)}
            />
            <PhotoPicker
              label={`사진대지 ${index + 1}세트 하단 사진 (선택, 여러 장 가능)`}
              accept="image/*"
              files={set.bottom}
              onFilesChange={(newFiles) => handleSetBottomChange(index, newFiles)}
            />
          </div>
        ))}
        {photoSets.length < MAX_PHOTO_SETS && (
          <button
            type="button"
            className="btn btn-secondary"
            onClick={handleAddPhotoSet}
            style={{ width: '100%', marginBottom: 16 }}
          >
            + 세트 추가
          </button>
        )}
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
      {generatedFile && (
        <EmailSendCard
          blob={generatedFile.blob}
          filename={generatedFile.filename}
          defaultSubject={`자재검수요청서 - ${projectName}`}
        />
      )}
    </div>
  )
}
