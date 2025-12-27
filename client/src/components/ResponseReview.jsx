import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { useAuth } from '../contexts/AuthContext'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import './ResponseReview.css'

const API_BASE = import.meta.env.VITE_API_URL || ''

function ResponseReview() {
  const { user } = useAuth()
  const [messages, setMessages] = useState([])
  const [selectedMessage, setSelectedMessage] = useState(null)
  const [reviews, setReviews] = useState([])
  const [loading, setLoading] = useState(false)
  const [stats, setStats] = useState(null)
  const [reviewForm, setReviewForm] = useState({
    review_status: 'approved',
    accuracy_rating: null,
    completeness_rating: null,
    clarity_rating: null,
    feedback_notes: '',
    correction_suggestions: '',
    strengths: '',
    weaknesses: '',
    should_incorporate: true,
    learning_priority: 'normal'
  })

  useEffect(() => {
    loadPendingReviews()
    loadStats()
  }, [])

  useEffect(() => {
    if (selectedMessage) {
      loadMessageReviews(selectedMessage.id)
    }
  }, [selectedMessage])

  const loadPendingReviews = async () => {
    setLoading(true)
    try {
      const response = await axios.get(`${API_BASE}/api/reviews/pending?limit=100`)
      setMessages(response.data)
    } catch (error) {
      console.error('Failed to load pending reviews:', error)
      alert('Failed to load reviews. Please try again.')
    } finally {
      setLoading(false)
    }
  }

  const loadStats = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/reviews/stats`)
      setStats(response.data)
    } catch (error) {
      console.error('Failed to load stats:', error)
    }
  }

  const loadMessageReviews = async (messageId) => {
    try {
      const response = await axios.get(`${API_BASE}/api/reviews/message/${messageId}`)
      setReviews(response.data)
    } catch (error) {
      console.error('Failed to load message reviews:', error)
    }
  }

  const handleSubmitReview = async (e) => {
    e.preventDefault()
    if (!selectedMessage) return

    try {
      await axios.post(`${API_BASE}/api/reviews/submit`, {
        chat_message_id: selectedMessage.id,
        ...reviewForm
      })
      
      alert('Review submitted successfully!')
      setSelectedMessage(null)
      setReviewForm({
        review_status: 'approved',
        accuracy_rating: null,
        completeness_rating: null,
        clarity_rating: null,
        feedback_notes: '',
        correction_suggestions: '',
        strengths: '',
        weaknesses: '',
        should_incorporate: true,
        learning_priority: 'normal'
      })
      loadPendingReviews()
      loadStats()
    } catch (error) {
      console.error('Failed to submit review:', error)
      alert(error.response?.data?.detail || 'Failed to submit review. Please try again.')
    }
  }

  const getStatusColor = (status) => {
    switch (status) {
      case 'approved': return '#4caf50'
      case 'needs_correction': return '#ff9800'
      case 'flagged': return '#f44336'
      default: return '#9e9e9e'
    }
  }

  const getStatusLabel = (status) => {
    switch (status) {
      case 'approved': return 'Approved'
      case 'needs_correction': return 'Needs Correction'
      case 'flagged': return 'Flagged'
      default: return 'Pending'
    }
  }

  return (
    <div className="response-review-container">
      <div className="review-header">
        <h2>AI Response Review System</h2>
        <p className="review-subtitle">Review AI responses to help the system learn and improve</p>
        {stats && (
          <div className="review-stats">
            <div className="stat-item">
              <span className="stat-label">Total Messages:</span>
              <span className="stat-value">{stats.total_messages}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Reviewed:</span>
              <span className="stat-value">{stats.reviewed_messages}</span>
            </div>
            <div className="stat-item">
              <span className="stat-label">Pending:</span>
              <span className="stat-value pending">{stats.pending_reviews}</span>
            </div>
            {stats.average_ratings.accuracy && (
              <div className="stat-item">
                <span className="stat-label">Avg Accuracy:</span>
                <span className="stat-value">{stats.average_ratings.accuracy}/5</span>
              </div>
            )}
          </div>
        )}
      </div>

      <div className="review-layout">
        <div className="messages-list-panel">
          <div className="panel-header">
            <h3>Messages for Review</h3>
            <button onClick={loadPendingReviews} className="refresh-btn">Refresh</button>
          </div>
          {loading ? (
            <div className="loading">Loading messages...</div>
          ) : (
            <div className="messages-list">
              {messages.length === 0 ? (
                <div className="empty-state">No messages available for review</div>
              ) : (
                messages.map((msg) => (
                  <div
                    key={msg.id}
                    className={`message-card ${selectedMessage?.id === msg.id ? 'selected' : ''} ${msg.has_review ? 'reviewed' : ''}`}
                    onClick={() => setSelectedMessage(msg)}
                  >
                    <div className="message-card-header">
                      <div className="message-meta">
                        <strong>{msg.user_name}</strong>
                        <span className="user-role">({msg.user_role})</span>
                      </div>
                      <div className="message-status">
                        {msg.has_review && (
                          <span
                            className="status-badge"
                            style={{ backgroundColor: getStatusColor(msg.review_status) }}
                          >
                            {getStatusLabel(msg.review_status)}
                          </span>
                        )}
                        {msg.review_count > 0 && (
                          <span className="review-count">{msg.review_count} review(s)</span>
                        )}
                      </div>
                    </div>
                    <div className="message-preview">
                      <div className="preview-label">Query:</div>
                      <div className="preview-text">{msg.message.substring(0, 150)}...</div>
                    </div>
                    {msg.subject && (
                      <div className="message-subject">
                        <strong>Subject:</strong> {msg.subject}
                      </div>
                    )}
                    <div className="message-timestamp">
                      {new Date(msg.timestamp).toLocaleString()}
                    </div>
                  </div>
                ))
              )}
            </div>
          )}
        </div>

        <div className="review-panel">
          {selectedMessage ? (
            <div className="review-content">
              <div className="review-content-header">
                <h3>Review Response</h3>
                <button
                  className="close-btn"
                  onClick={() => setSelectedMessage(null)}
                >
                  ×
                </button>
              </div>

              <div className="message-display">
                <div className="message-section">
                  <h4>User Query</h4>
                  <div className="message-box">
                    <div className="message-author">
                      <strong>{selectedMessage.user_name}</strong> ({selectedMessage.user_role})
                    </div>
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {selectedMessage.message}
                    </ReactMarkdown>
                  </div>
                </div>

                <div className="message-section">
                  <h4>AI Response</h4>
                  <div className="message-box ai-response">
                    <ReactMarkdown remarkPlugins={[remarkGfm]}>
                      {selectedMessage.response}
                    </ReactMarkdown>
                  </div>
                </div>

                {selectedMessage.sources && selectedMessage.sources.length > 0 && (
                  <div className="message-section">
                    <h4>Sources ({selectedMessage.sources.length})</h4>
                    <div className="sources-list">
                      {selectedMessage.sources.slice(0, 10).map((source, i) => (
                        <div key={i} className="source-item">
                          <strong>{source.source}</strong>
                          {source.citation && <span> - {source.citation}</span>}
                          {source.jurisdiction && <span> ({source.jurisdiction})</span>}
                        </div>
                      ))}
                      {selectedMessage.sources.length > 10 && (
                        <div className="source-item">... and {selectedMessage.sources.length - 10} more</div>
                      )}
                    </div>
                  </div>
                )}

                {selectedMessage.warnings && selectedMessage.warnings.length > 0 && (
                  <div className="message-section">
                    <h4>Warnings</h4>
                    <div className="warnings-list">
                      {selectedMessage.warnings.map((warning, i) => (
                        <div key={i} className="warning-item">⚠️ {warning}</div>
                      ))}
                    </div>
                  </div>
                )}
              </div>

              {reviews.length > 0 && (
                <div className="existing-reviews">
                  <h4>Previous Reviews</h4>
                  {reviews.map((review) => (
                    <div key={review.id} className="review-item">
                      <div className="review-item-header">
                        <strong>{review.reviewer_name}</strong>
                        <span
                          className="status-badge"
                          style={{ backgroundColor: getStatusColor(review.review_status) }}
                        >
                          {getStatusLabel(review.review_status)}
                        </span>
                        <span className="review-date">
                          {new Date(review.reviewed_at || review.created_at).toLocaleString()}
                        </span>
                      </div>
                      {review.feedback_notes && (
                        <div className="review-feedback">
                          <strong>Feedback:</strong> {review.feedback_notes}
                        </div>
                      )}
                    </div>
                  ))}
                </div>
              )}

              <form onSubmit={handleSubmitReview} className="review-form">
                <div className="form-group">
                  <label>Review Status *</label>
                  <select
                    value={reviewForm.review_status}
                    onChange={(e) => setReviewForm({ ...reviewForm, review_status: e.target.value })}
                    required
                  >
                    <option value="approved">Approved</option>
                    <option value="needs_correction">Needs Correction</option>
                    <option value="flagged">Flagged</option>
                  </select>
                </div>

                <div className="ratings-group">
                  <div className="form-group">
                    <label>Accuracy Rating (1-5)</label>
                    <select
                      value={reviewForm.accuracy_rating || ''}
                      onChange={(e) => setReviewForm({ ...reviewForm, accuracy_rating: e.target.value ? parseInt(e.target.value) : null })}
                    >
                      <option value="">Not rated</option>
                      {[1, 2, 3, 4, 5].map(n => (
                        <option key={n} value={n}>{n}</option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group">
                    <label>Completeness Rating (1-5)</label>
                    <select
                      value={reviewForm.completeness_rating || ''}
                      onChange={(e) => setReviewForm({ ...reviewForm, completeness_rating: e.target.value ? parseInt(e.target.value) : null })}
                    >
                      <option value="">Not rated</option>
                      {[1, 2, 3, 4, 5].map(n => (
                        <option key={n} value={n}>{n}</option>
                      ))}
                    </select>
                  </div>

                  <div className="form-group">
                    <label>Clarity Rating (1-5)</label>
                    <select
                      value={reviewForm.clarity_rating || ''}
                      onChange={(e) => setReviewForm({ ...reviewForm, clarity_rating: e.target.value ? parseInt(e.target.value) : null })}
                    >
                      <option value="">Not rated</option>
                      {[1, 2, 3, 4, 5].map(n => (
                        <option key={n} value={n}>{n}</option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="form-group">
                  <label>Feedback Notes</label>
                  <textarea
                    value={reviewForm.feedback_notes}
                    onChange={(e) => setReviewForm({ ...reviewForm, feedback_notes: e.target.value })}
                    rows={4}
                    placeholder="Overall feedback on the response..."
                  />
                </div>

                <div className="form-group">
                  <label>Strengths</label>
                  <textarea
                    value={reviewForm.strengths}
                    onChange={(e) => setReviewForm({ ...reviewForm, strengths: e.target.value })}
                    rows={3}
                    placeholder="What did the AI do well?"
                  />
                </div>

                <div className="form-group">
                  <label>Weaknesses / Areas for Improvement</label>
                  <textarea
                    value={reviewForm.weaknesses}
                    onChange={(e) => setReviewForm({ ...reviewForm, weaknesses: e.target.value })}
                    rows={3}
                    placeholder="What could be improved?"
                  />
                </div>

                <div className="form-group">
                  <label>Correction Suggestions</label>
                  <textarea
                    value={reviewForm.correction_suggestions}
                    onChange={(e) => setReviewForm({ ...reviewForm, correction_suggestions: e.target.value })}
                    rows={4}
                    placeholder="Specific corrections or improvements..."
                  />
                </div>

                <div className="form-group checkbox-group">
                  <label>
                    <input
                      type="checkbox"
                      checked={reviewForm.should_incorporate}
                      onChange={(e) => setReviewForm({ ...reviewForm, should_incorporate: e.target.checked })}
                    />
                    Use this review for system learning
                  </label>
                </div>

                <div className="form-group">
                  <label>Learning Priority</label>
                  <select
                    value={reviewForm.learning_priority}
                    onChange={(e) => setReviewForm({ ...reviewForm, learning_priority: e.target.value })}
                  >
                    <option value="high">High</option>
                    <option value="normal">Normal</option>
                    <option value="low">Low</option>
                  </select>
                </div>

                <button type="submit" className="submit-review-btn">
                  Submit Review
                </button>
              </form>
            </div>
          ) : (
            <div className="no-selection">
              <p>Select a message from the list to review</p>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

export default ResponseReview










