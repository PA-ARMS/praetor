import React, { useState } from 'react'
import axios from 'axios'
import './CorrectionModal.css'
import { API_BASE } from '../apiConfig.js'

const CORRECTION_TYPES = [
  { value: 'factual_error', label: 'Factual Error' },
  { value: 'citation_error', label: 'Citation Error' },
  { value: 'missing_info', label: 'Missing Information' },
  { value: 'incorrect_interpretation', label: 'Incorrect Interpretation' },
  { value: 'other', label: 'Other' }
]

function CorrectionModal({ messageId, onClose, onSuccess }) {
  const [correctionType, setCorrectionType] = useState('factual_error')
  const [correctionDetails, setCorrectionDetails] = useState('')
  const [correctedResponse, setCorrectedResponse] = useState('')
  const [submitting, setSubmitting] = useState(false)
  const [error, setError] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!correctionDetails.trim()) {
      setError('Please describe what is incorrect.')
      return
    }
    setSubmitting(true)
    setError(null)
    try {
      await axios.post(`${API_BASE}/api/corrections/submit`, {
        chat_message_id: messageId,
        correction_type: correctionType,
        correction_details: correctionDetails.trim(),
        corrected_response: correctedResponse.trim() || null
      })
      onSuccess?.()
      onClose()
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Failed to submit correction.')
    } finally {
      setSubmitting(false)
    }
  }

  return (
    <div className="correction-modal-overlay" onClick={onClose}>
      <div className="correction-modal" onClick={e => e.stopPropagation()}>
        <div className="correction-modal-header">
          <h3>Report Incorrect Response</h3>
          <button type="button" className="correction-modal-close" onClick={onClose} aria-label="Close">&times;</button>
        </div>
        <p className="correction-modal-info">
          Your report will be reviewed by a Partner Attorney (Peyton or Yulia) for learning and quality improvement.
        </p>
        <form onSubmit={handleSubmit} className="correction-modal-form">
          <div className="correction-form-group">
            <label>Type of Issue *</label>
            <select
              value={correctionType}
              onChange={e => setCorrectionType(e.target.value)}
              required
            >
              {CORRECTION_TYPES.map(t => (
                <option key={t.value} value={t.value}>{t.label}</option>
              ))}
            </select>
          </div>
          <div className="correction-form-group">
            <label>What is incorrect? *</label>
            <textarea
              value={correctionDetails}
              onChange={e => setCorrectionDetails(e.target.value)}
              placeholder="Describe the error (e.g., wrong statute cited, missing case, incorrect interpretation...)"
              rows={4}
              required
            />
          </div>
          <div className="correction-form-group">
            <label>Corrected Response (optional)</label>
            <textarea
              value={correctedResponse}
              onChange={e => setCorrectedResponse(e.target.value)}
              placeholder="If you know the correct answer, provide it here..."
              rows={3}
            />
          </div>
          {error && <div className="correction-form-error">{error}</div>}
          <div className="correction-modal-actions">
            <button type="button" onClick={onClose} className="correction-btn-secondary">Cancel</button>
            <button type="submit" disabled={submitting} className="correction-btn-primary">
              {submitting ? 'Submitting...' : 'Submit Report'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default CorrectionModal
