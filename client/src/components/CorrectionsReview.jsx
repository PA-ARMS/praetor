import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { useAuth } from '../contexts/AuthContext'
import './CorrectionsReview.css'

import { API_BASE } from '../apiConfig.js'

function CorrectionsReview() {
  const { user } = useAuth()
  const [corrections, setCorrections] = useState([])
  const [loading, setLoading] = useState(true)
  const [statusFilter, setStatusFilter] = useState('needs_review')
  const [scope, setScope] = useState('assigned') // 'assigned' | 'all' (admin only)
  const [verifyingId, setVerifyingId] = useState(null)

  const isAdmin = user?.role === 'admin' || user?.role === 'attorney_partner'

  useEffect(() => {
    loadCorrections()
  }, [statusFilter, scope])

  const loadCorrections = async () => {
    setLoading(true)
    try {
      if (scope === 'all' && isAdmin) {
        const params = statusFilter ? `?status=${statusFilter}` : ''
        const response = await axios.get(`${API_BASE}/api/corrections/list${params}`)
        setCorrections(Array.isArray(response.data) ? response.data : (response.data.corrections || []))
      } else {
        const params = statusFilter ? `?status=${statusFilter}` : ''
        const response = await axios.get(`${API_BASE}/api/corrections/assigned-to-me${params}`)
        setCorrections(response.data)
      }
    } catch (error) {
      console.error('Failed to load corrections:', error)
      setCorrections([])
    } finally {
      setLoading(false)
    }
  }

  const handleVerify = async (correctionId) => {
    setVerifyingId(correctionId)
    try {
      await axios.post(`${API_BASE}/api/corrections/${correctionId}/verify`)
      loadCorrections()
    } catch (error) {
      console.error('Failed to verify:', error)
      alert(error.response?.data?.detail || 'Failed to verify correction.')
    } finally {
      setVerifyingId(null)
    }
  }

  const formatDate = (iso) => {
    if (!iso) return ''
    const d = new Date(iso)
    return d.toLocaleDateString() + ' ' + d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  const getTypeLabel = (type) => {
    const labels = {
      factual_error: 'Factual Error',
      citation_error: 'Citation Error',
      missing_info: 'Missing Information',
      incorrect_interpretation: 'Incorrect Interpretation',
      other: 'Other'
    }
    return labels[type] || type
  }

  // Normalize correction shape: assigned-to-me returns full objects, list returns { corrections: [...] }
  const items = Array.isArray(corrections) ? corrections : (corrections?.corrections || [])

  return (
    <div className="corrections-review">
      <div className="corrections-review-header">
        <h2>{scope === 'all' ? 'All Corrections' : 'Corrections Assigned to You'}</h2>
        <p className="corrections-review-subtitle">
          {scope === 'all'
            ? 'All user corrections across the system (Admin/Partner view).'
            : 'User-reported issues routed for partner review (Peyton / Yulia). Verify and incorporate into learning.'}
        </p>
        <div className="corrections-review-filters">
          {isAdmin && (
            <>
              <label>View:</label>
              <select value={scope} onChange={e => setScope(e.target.value)}>
                <option value="assigned">Assigned to me</option>
                <option value="all">All corrections</option>
              </select>
            </>
          )}
          <label>Status:</label>
          <select
            value={statusFilter}
            onChange={e => setStatusFilter(e.target.value)}
          >
            <option value="needs_review">Needs Review</option>
            <option value="">All</option>
            <option value="verified">Verified</option>
            <option value="pending">Pending</option>
          </select>
          <button type="button" onClick={loadCorrections} className="refresh-btn">Refresh</button>
        </div>
      </div>

      {loading ? (
        <div className="corrections-review-loading">Loading...</div>
      ) : items.length === 0 ? (
        <div className="corrections-review-empty">
          <p>{scope === 'all' ? 'No corrections in the system.' : 'No corrections assigned to you at this time.'}</p>
          <p className="hint">When regular users report incorrect responses, they are routed to you or your partner for review.</p>
        </div>
      ) : (
        <div className="corrections-review-list">
          {items.map(c => (
            <div key={c.id} className="correction-card">
              <div className="correction-card-header">
                <span className="correction-type-badge">{getTypeLabel(c.correction_type)}</span>
                <span className="correction-meta">
                  {c.user_name ? `From ${c.user_name} (${c.user_role}) · ` : ''}
                  {formatDate(c.created_at)}
                </span>
              </div>
              {c.user_message && (
                <div className="correction-section">
                  <strong>Original question:</strong>
                  <div className="correction-content">{c.user_message}</div>
                </div>
              )}
              {c.original_response != null && (
                <div className="correction-section">
                  <strong>AI response (excerpt):</strong>
                  <div className="correction-content excerpt">
                    {(c.original_response || '').substring(0, 400)}
                    {(c.original_response || '').length > 400 ? '...' : ''}
                  </div>
                </div>
              )}
              <div className="correction-section">
                <strong>User&apos;s report:</strong>
                <div className="correction-content">{c.correction_details || '(no details)'}</div>
              </div>
              {c.corrected_response && (
                <div className="correction-section">
                  <strong>User&apos;s suggested correction:</strong>
                  <div className="correction-content">{c.corrected_response}</div>
                </div>
              )}
              <div className="correction-card-actions">
                <span className="correction-status">{c.verification_status}</span>
                {c.verification_status === 'needs_review' && (
                  <button
                    type="button"
                    className="verify-btn"
                    onClick={() => handleVerify(c.id)}
                    disabled={verifyingId === c.id}
                  >
                    {verifyingId === c.id ? 'Verifying...' : 'Verify & Incorporate'}
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

export default CorrectionsReview
