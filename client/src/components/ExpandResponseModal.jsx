import React, { useState } from 'react'
import axios from 'axios'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './Modal.css'

const API_BASE = import.meta.env.VITE_API_URL || ''

function ExpandResponseModal({ messageId, originalResponse, onClose }) {
  const [detailLevel, setDetailLevel] = useState('comprehensive')
  const [expandedResponse, setExpandedResponse] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [viewMode, setViewMode] = useState('side-by-side') // 'side-by-side' or 'expanded-only'

  const estimatedTimes = {
    comprehensive: '8-20 seconds',
    complete: '25-60 seconds',
    unlimited: '60-120 seconds'
  }

  const handleExpand = async () => {
    setLoading(true)
    setError(null)
    
    try {
      const response = await axios.post(
        `${API_BASE}/api/chat/message/${messageId}/expand-response`,
        null,
        { params: { detail_level: detailLevel } }
      )
      setExpandedResponse(response.data)
    } catch (err) {
      setError(err.response?.data?.detail || 'Failed to expand response')
    } finally {
      setLoading(false)
    }
  }

  if (!messageId) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content expand-response-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>Expand Response</h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          {!expandedResponse && (
            <div className="expand-controls">
              <div className="detail-level-selection">
                <label>Select Detail Level:</label>
                <select 
                  value={detailLevel} 
                  onChange={(e) => setDetailLevel(e.target.value)}
                  disabled={loading}
                >
                  <option value="comprehensive">📚 Comprehensive (~4,500 words)</option>
                  <option value="complete">📖 Complete (~12,000 words)</option>
                  <option value="unlimited">🔥 Unlimited (~24,000 words)</option>
                </select>
                <p className="estimated-time">
                  Estimated time: {estimatedTimes[detailLevel]}
                </p>
              </div>

              <button 
                className="expand-button"
                onClick={handleExpand}
                disabled={loading}
              >
                {loading ? 'Expanding...' : 'Expand Response'}
              </button>

              {error && <div className="modal-error">{error}</div>}
            </div>
          )}

          {loading && (
            <div className="modal-loading">
              <div className="loading-spinner"></div>
              <p>Generating expanded response... This may take up to {estimatedTimes[detailLevel]}</p>
            </div>
          )}

          {expandedResponse && (
            <>
              <div className="view-mode-selector">
                <button
                  className={viewMode === 'side-by-side' ? 'active' : ''}
                  onClick={() => setViewMode('side-by-side')}
                >
                  Side by Side
                </button>
                <button
                  className={viewMode === 'expanded-only' ? 'active' : ''}
                  onClick={() => setViewMode('expanded-only')}
                >
                  Expanded Only
                </button>
              </div>

              <div className={`response-comparison ${viewMode}`}>
                {(viewMode === 'side-by-side') && (
                  <div className="response-pane original">
                    <h3>Original Response</h3>
                    <div className="response-content">
                      <ReactMarkdown remarkPlugins={[remarkGfm]}>
                        {originalResponse}
                      </ReactMarkdown>
                    </div>
                  </div>
                )}

                <div className="response-pane expanded">
                  <h3>
                    Expanded Response ({expandedResponse.detail_level})
                    <span className="source-count">
                      Used {expandedResponse.sources_used} sources
                    </span>
                  </h3>
                  <div className="response-content">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {expandedResponse.expanded_response}
                    </ReactMarkdown>
                  </div>
                </div>
              </div>

              <div className="expand-actions">
                <button 
                  className="modal-button secondary"
                  onClick={() => setExpandedResponse(null)}
                >
                  Expand Again
                </button>
                <button
                  className="modal-button"
                  onClick={() => {
                    navigator.clipboard.writeText(expandedResponse.expanded_response)
                  }}
                >
                  Copy Expanded Response
                </button>
              </div>
            </>
          )}
        </div>

        <div className="modal-footer">
          <button className="modal-button" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  )
}

export default ExpandResponseModal

