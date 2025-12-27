import React, { useState } from 'react'
import axios from 'axios'
import './UploadDocument.css'

const API_BASE = import.meta.env.VITE_API_URL || ''

function UploadDocument() {
  const [files, setFiles] = useState([])
  const [jurisdiction, setJurisdiction] = useState('Virginia')
  const [status, setStatus] = useState(null)
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)
  const [processingOCR, setProcessingOCR] = useState(false)
  const [docStats, setDocStats] = useState(null)
  const [analyzeMotion, setAnalyzeMotion] = useState(false)
  const [motionAnalysis, setMotionAnalysis] = useState(null)

  const onSelectFiles = (e) => {
    setFiles(Array.from(e.target.files || []))
    setStatus(null)
  }

  const onUpload = async () => {
    if (!files.length) return
    setUploading(true)
    setStatus(null)
    setProgress(0)

    try {
      // Get auth token if available
      const token = localStorage.getItem('token')
      const headers = { 'Content-Type': 'multipart/form-data' }
      if (token) {
        headers['Authorization'] = `Bearer ${token}`
      }

      let successCount = 0
      let failCount = 0
      const errors = []

      for (let i = 0; i < files.length; i++) {
        const file = files[i]
        const form = new FormData()
        form.append('file', file)
        form.append('jurisdiction', jurisdiction)
        if (analyzeMotion) {
          form.append('analyze_against_scenarios', 'true')
        }

        try {
          // Check if file is PDF - might need OCR
          const isPDF = file.name.toLowerCase().endsWith('.pdf')
          if (isPDF) {
            setProcessingOCR(true)
          }
          
          const response = await axios.post(`${API_BASE}/api/rag/upload-document`, form, {
            headers,
            timeout: isPDF ? 300000 : 60000, // 5 minutes for PDFs (OCR can take time), 1 minute for others
            onUploadProgress: (evt) => {
              if (evt.total) {
              const pct = Math.round((evt.loaded / evt.total) * 100)
              setProgress(Math.min(100, Math.max(0, pct)))
            }
            }
          })
          successCount++
          setProcessingOCR(false)
          console.log(`Uploaded ${file.name}:`, response.data)
          
          // Check if OCR was used and display info
          if (response.data.ocr_used) {
            console.log(`OCR was used for ${file.name}`, response.data.ocr_details)
            if (response.data.ocr_details) {
              const ocrInfo = response.data.ocr_details
              setStatus({
                ok: true,
                msg: `Successfully processed scanned PDF using OCR: ${ocrInfo.pages_with_text}/${ocrInfo.pages_processed} pages extracted`
              })
            }
          }
          
          // Update stats if provided
          if (response.data.total_documents) {
            setDocStats({
              total: response.data.total_documents,
              textLength: response.data.text_length
            })
          }
          
          // Store motion analysis if provided
          if (response.data.motion_analysis) {
            setMotionAnalysis(response.data.motion_analysis)
          }
        } catch (err) {
          setProcessingOCR(false)
          failCount++
          let msg = 'Upload failed'
          if (err?.response?.data?.detail) {
            msg = err.response.data.detail
          } else if (err?.response?.data?.message) {
            msg = err.response.data.message
          } else if (err?.message) {
            msg = err.message
          }
          
          // Enhance error message for OCR-related issues
          if (msg.toLowerCase().includes('scanned') || msg.toLowerCase().includes('ocr')) {
            if (msg.toLowerCase().includes('tesseract') || msg.toLowerCase().includes('not installed')) {
              msg = `${msg}\n\nTo enable OCR for scanned PDFs, install Tesseract OCR. See docs/OCR_SETUP.md for instructions.`
            }
          }
          
          errors.push(`${file.name}: ${msg}`)
          console.error(`Failed to upload ${file.name}:`, {
            error: err,
            response: err?.response,
            data: err?.response?.data,
            status: err?.response?.status
          })
        }
      }

      if (successCount > 0) {
        setStatus({ 
          ok: true, 
          msg: `Successfully uploaded ${successCount} file(s)${failCount > 0 ? `. ${failCount} failed.` : '.'}` 
        })
      } else {
        setStatus({ 
          ok: false, 
          msg: `Failed to upload all files. ${errors.join('; ')}` 
        })
      }
      
      if (successCount === files.length) {
        setFiles([])
      }
      setProgress(100)
    } catch (err) {
      const msg = err?.response?.data?.detail || err?.message || 'Upload failed'
      setStatus({ ok: false, msg })
    } finally {
      setUploading(false)
    }
  }

  return (
    <div className="upload-doc-container">
      <h2>Upload Documents for Analysis</h2>
      <p className="hint">
        Supported: PDF (including scanned PDFs with OCR), HTML/HTM, TXT, DOCX, PPTX, XLSX (others may be ignored).
      </p>
      {processingOCR && (
        <div className="ocr-notice">
          <strong>Processing scanned PDF with OCR...</strong> This may take a few minutes for large documents.
        </div>
      )}

      <div className="upload-controls">
        <div className="field">
          <label>Jurisdiction</label>
          <select value={jurisdiction} onChange={(e) => setJurisdiction(e.target.value)}>
            <option value="Virginia">Virginia</option>
            <option value="Federal">Federal</option>
            <option value="Multi">Multi</option>
          </select>
        </div>

        <div className="field">
          <label>Choose files</label>
          <input type="file" multiple onChange={onSelectFiles} />
        </div>

        <div className="field">
          <label>
            <input 
              type="checkbox" 
              checked={analyzeMotion}
              onChange={(e) => setAnalyzeMotion(e.target.checked)}
            />
            Analyze motion against scenario database (compare to similar cases)
          </label>
        </div>

        <button className="upload-btn" onClick={onUpload} disabled={!files.length || uploading}>
          {uploading ? 'Uploading...' : 'Upload & Index'}
        </button>

        {uploading && (
          <div className="progress">
            <div className="bar" style={{ width: `${progress}%` }} />
          </div>
        )}

        {status && (
          <div className={`status ${status.ok ? 'ok' : 'err'}`}>
            {status.msg}
          </div>
        )}

        {!!files.length && !uploading && (
          <div className="selected-files">
            <strong>Selected:</strong>
            <ul>
              {files.map((f, i) => (
                <li key={`${f.name}-${i}`}>{f.name}</li>
              ))}
            </ul>
          </div>
        )}
      </div>

      <div className="note">
        Once uploaded, documents are added to the searchable corpus (RAG).
        Ask questions and Praetor will use them when relevant.
      </div>

      {docStats && (
        <div className="doc-stats">
          <strong>Corpus Status:</strong> {docStats.total} document(s) indexed
        </div>
      )}

      {motionAnalysis && !motionAnalysis.error && (
        <div className="motion-analysis">
          <h3>Motion Analysis Results</h3>
          <div className="analysis-section">
            <h4>Success Probability</h4>
            <div className="probability">
              <strong>{motionAnalysis.success_probability}%</strong> confidence
              <div className="outcome">Predicted: {motionAnalysis.predicted_outcome}</div>
            </div>
          </div>
          
          {motionAnalysis.similar_cases && motionAnalysis.similar_cases.length > 0 && (
            <div className="analysis-section">
              <h4>Similar Cases Found</h4>
              <p>Found {motionAnalysis.similar_cases_count} similar cases</p>
              {motionAnalysis.outcome_analysis && (
                <div className="outcomes">
                  <strong>Outcomes in similar cases:</strong>
                  <ul>
                    {Object.entries(motionAnalysis.outcome_analysis.outcome_percentages || {}).map(([outcome, pct]) => (
                      <li key={outcome}>{outcome}: {pct}%</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
          
          {motionAnalysis.recommendations && motionAnalysis.recommendations.length > 0 && (
            <div className="analysis-section">
              <h4>Recommendations</h4>
              <ul>
                {motionAnalysis.recommendations.map((rec, i) => (
                  <li key={i}>{rec}</li>
                ))}
              </ul>
            </div>
          )}
          
          {motionAnalysis.risk_assessment && (
            <div className="analysis-section">
              <h4>Risk Assessment</h4>
              <div className={`risk-level risk-${motionAnalysis.risk_assessment.risk_level}`}>
                Risk Level: <strong>{motionAnalysis.risk_assessment.risk_level.toUpperCase()}</strong>
              </div>
              {motionAnalysis.risk_assessment.warnings && motionAnalysis.risk_assessment.warnings.length > 0 && (
                <div className="warnings">
                  {motionAnalysis.risk_assessment.warnings.map((warning, i) => (
                    <div key={i} className="warning">⚠ {warning}</div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

export default UploadDocument


