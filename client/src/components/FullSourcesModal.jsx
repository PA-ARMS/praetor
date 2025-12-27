import React, { useState, useEffect } from 'react'
import axios from 'axios'
import './Modal.css'

const API_BASE = import.meta.env.VITE_API_URL || ''

function FullSourcesModal({ messageId, onClose }) {
  const [sources, setSources] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [searchTerm, setSearchTerm] = useState('')
  const [totalSources, setTotalSources] = useState(null)
  const [uniqueSources, setUniqueSources] = useState(null)

  useEffect(() => {
    const fetchFullSources = async () => {
      try {
        const response = await axios.get(`${API_BASE}/api/chat/message/${messageId}/full-sources`)
        const data = response.data || {}
        setSources(data.sources || [])
        setTotalSources(data.total_sources ?? null)
        setUniqueSources(data.unique_sources ?? null)
      } catch (err) {
        setError(err.response?.data?.detail || 'Failed to load sources')
      } finally {
        setLoading(false)
      }
    }

    if (messageId) {
      fetchFullSources()
    }
  }, [messageId])

  const filteredSources = sources.filter(source =>
    (source.source || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (source.jurisdiction || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (source.citation || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (source.document_type || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
    (source.full_text || source.snippet || '').toLowerCase().includes(searchTerm.toLowerCase())
  )

  const copyToClipboard = (text) => {
    navigator.clipboard.writeText(text)
  }

  if (!messageId) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content full-sources-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h2>
            Complete Source List
            {uniqueSources != null && (
              <span className="source-count-header">
                {' '}
                ({uniqueSources} shown{totalSources != null ? ` of ${totalSources}` : ''})
              </span>
            )}
          </h2>
          <button className="modal-close" onClick={onClose}>✕</button>
        </div>

        <div className="modal-body">
          {loading && <div className="modal-loading">Loading sources...</div>}
          
          {error && <div className="modal-error">{error}</div>}
          
          {!loading && !error && (
            <>
              <div className="source-search">
                <input
                  type="text"
                  placeholder="Search sources..."
                  value={searchTerm}
                  onChange={(e) => setSearchTerm(e.target.value)}
                  className="source-search-input"
                />
              </div>

              <div className="sources-list">
                {filteredSources.length === 0 && (
                  <div className="no-sources">No sources match your search</div>
                )}
                
                {filteredSources.map((source, idx) => (
                  <div key={idx} className="source-item">
                    <div className="source-header">
                      <span className="source-number">#{idx + 1}</span>
                      {source.link ? (
                        <a
                          href={source.link}
                          target="_blank"
                          rel="noreferrer"
                          className="source-name source-link"
                        >
                          {source.source || 'Unknown source'}
                        </a>
                      ) : (
                        <span className="source-name">
                          {source.source || 'Unknown source'}
                        </span>
                      )}
                      <span className="source-jurisdiction">
                        {source.jurisdiction ? `(${source.jurisdiction})` : ''}
                      </span>
                      <button
                        className="copy-button"
                        onClick={() => {
                          const textBlock = source.full_text || source.snippet || ''
                          const headerParts = [
                            source.source,
                            source.jurisdiction,
                            source.citation
                          ].filter(Boolean)
                          const header = headerParts.join(' | ')
                          copyToClipboard(`${header}\n\n${textBlock}`)
                        }}
                        title="Copy to clipboard"
                      >
                        📋 Copy
                      </button>
                    </div>
                    <div className="source-text">
                      {source.citation && (
                        <div className="source-citation">
                          {source.citation}
                        </div>
                      )}
                      {source.document_type && (
                        <div className="source-doc-type">
                          {source.document_type}
                          {source.chunk_count != null && source.chunk_count > 1
                            ? ` • ${source.chunk_count} passages`
                            : ''}
                        </div>
                      )}
                      <div className="source-snippet">
                        {source.full_text || source.snippet || 'No excerpt available.'}
                      </div>
                    </div>
                    {source.distance && (
                      <div className="source-meta">
                        Relevance score: {(1 - source.distance).toFixed(3)}
                      </div>
                    )}
                  </div>
                ))}
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

export default FullSourcesModal

