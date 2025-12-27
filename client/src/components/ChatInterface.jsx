import React, { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import TypingText from './TypingText'
import VoicePlayer from './VoicePlayer'
import ScenarioPredictionPanel from './ScenarioPredictionPanel'
import LegalResponseFormatter from './LegalResponseFormatter'
import ExpandableSources from './ExpandableSources'
import './ChatInterface.css'

// Use relative URL so Vite proxy handles it (works for both local and network access)
const API_BASE = import.meta.env.VITE_API_URL || ''

function ChatInterface() {
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sources, setSources] = useState([])
  const [files, setFiles] = useState([])
  const [uploadStatus, setUploadStatus] = useState(null)
  const [autoPlayVoice, setAutoPlayVoice] = useState(localStorage.getItem('tts_autoplay') === 'true')
  const [detailLevel, setDetailLevel] = useState(null) // null = auto (smart default)
  const [recommendedLevel, setRecommendedLevel] = useState(null)
  const [showDetailSelector, setShowDetailSelector] = useState(false)
  const [exhaustiveMode, setExhaustiveMode] = useState(false)
  const [summaryCounts, setSummaryCounts] = useState({})
  const messagesEndRef = useRef(null)
  const messagesContainerRef = useRef(null)
  const userHasScrolledUpRef = useRef(false)

  // Check if user is near the bottom of the scroll container
  const isNearBottom = () => {
    const container = messagesContainerRef.current
    if (!container) return true
    
    const threshold = 150 // pixels from bottom
    const distanceFromBottom = container.scrollHeight - container.scrollTop - container.clientHeight
    return distanceFromBottom < threshold
  }

  const scrollToBottom = (force = false) => {
    // Only scroll if user is near bottom or if forced (new message)
    if (force || isNearBottom()) {
      messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
      userHasScrolledUpRef.current = false
    }
  }

  // Track user scroll position
  useEffect(() => {
    const container = messagesContainerRef.current
    if (!container) return

    const handleScroll = () => {
      // If user scrolls up significantly, mark that they've scrolled up
      if (!isNearBottom()) {
        userHasScrolledUpRef.current = true
      } else {
        userHasScrolledUpRef.current = false
      }
    }

    container.addEventListener('scroll', handleScroll)
    return () => container.removeEventListener('scroll', handleScroll)
  }, [])

  // Only auto-scroll on new messages (not while typing)
  useEffect(() => {
    // Only scroll if it's a new message being added, not just content updates
    const lastMessage = messages[messages.length - 1]
    if (lastMessage && !lastMessage.isTyping) {
      scrollToBottom(true) // Force scroll for new messages
    }
  }, [messages.length]) // Only trigger on message count change, not content updates

  // Don't auto-scroll while typing if user has scrolled up
  useEffect(() => {
    const hasTypingMessage = messages.some(msg => msg.isTyping && msg.role === 'assistant')
    if (hasTypingMessage && !userHasScrolledUpRef.current) {
      // Only scroll if user hasn't manually scrolled up
      const timer = setInterval(() => {
        if (isNearBottom()) {
          scrollToBottom()
        }
      }, 300) // Reduced frequency to be less intrusive
      return () => clearInterval(timer)
    }
  }, [messages])

  const [conversationId, setConversationId] = useState(null)

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (!input.trim() || loading) return

    const userMessage = { role: 'user', content: input }
    setMessages(prev => [...prev, userMessage])
    const currentInput = input
    const docSources = files.map(f => f.name)
    setInput('')
    setLoading(true)
    setSources([])

    try {
      // If files selected, upload them first so they become searchable
      if (files.length > 0) {
        setUploadStatus('Uploading documents...')
        for (let i = 0; i < files.length; i++) {
          const file = files[i]
          const form = new FormData()
          form.append('file', file)
          form.append('jurisdiction', 'Virginia')
          await axios.post(`${API_BASE}/api/rag/upload-document`, form, {
            headers: { 'Content-Type': 'multipart/form-data' }
          })
        }
        setUploadStatus(`Uploaded ${files.length} document(s).`)
        setFiles([])
      } else {
        setUploadStatus(null)
      }

      const payload = {
        message: currentInput,
        conversation_id: conversationId,
        use_rag: true,
        max_results: exhaustiveMode ? 0 : 25,  // Limit to 25 results for speed (0 = all for exhaustive mode)
        detail_level: detailLevel,  // null for auto-detect
        exhaustive_search: exhaustiveMode
      }
      if (docSources.length > 0) {
        payload['doc_sources'] = docSources
      }
      console.log('Sending chat request...', { message: currentInput.substring(0, 50) + '...' })
      const startTime = Date.now()
      const response = await axios.post(`${API_BASE}/api/chat/query`, payload, {
        timeout: 600000  // 10 minute timeout (600 seconds) - Ollama can be slow with large models
      })
      const elapsed = ((Date.now() - startTime) / 1000).toFixed(1)
      console.log(`Chat response received after ${elapsed}s!`, { 
        hasResponse: !!response.data.response,
        responseLength: response.data.response?.length || 0,
        hasSources: response.data.sources?.length || 0
      })
      
      // Update conversation ID if this is a new conversation
      if (!conversationId && response.data.conversation_id) {
        setConversationId(response.data.conversation_id)
      }

      // Debug: log scenario prediction data
      console.log('ChatInterface - Full response data:', {
        has_scenario_prediction: !!response.data.scenario_prediction,
        scenario_prediction: response.data.scenario_prediction,
        response_keys: Object.keys(response.data)
      });
      
      if (response.data.scenario_prediction) {
        console.log('ChatInterface - Received scenario prediction:', JSON.stringify(response.data.scenario_prediction, null, 2));
        console.log('ChatInterface - Prediction similar_scenarios:', response.data.scenario_prediction.similar_scenarios);
        console.log('ChatInterface - Prediction top_similar_scenarios:', response.data.scenario_prediction.top_similar_scenarios?.length || 0);
      } else {
        console.log('ChatInterface - NO scenario_prediction in response!');
      }

      // Update recommended level if provided
      if (response.data.recommended_level) {
        setRecommendedLevel(response.data.recommended_level)
      }

      if (response.data.message_id) {
        setSummaryCounts(prev => ({
          ...prev,
          [response.data.message_id]: {
            total: response.data.total_sources ?? null,
            unique: response.data.unique_sources ?? null
          }
        }))
      }

      // Check if response is empty or missing
      const responseText = response.data.response || ''
      if (!responseText || responseText.trim() === '') {
        console.error('WARNING: Empty response received from backend!', {
          responseData: response.data,
          hasResponse: !!response.data.response,
          responseType: typeof response.data.response,
          responseLength: response.data.response?.length || 0
        })
      }

      const aiMessage = {
        role: 'assistant',
        content: responseText || 'No response received from the AI. Please try again.',
        sources: response.data.sources || [],
        warnings: response.data.warnings || [],
        scenarioPrediction: response.data.scenario_prediction || null,
        detailLevel: response.data.detail_level,
        verificationStatus: response.data.verification_status || null,
        authoritativeSourcesCount: response.data.authoritative_sources_count ?? null,
        secondarySourcesCount: response.data.secondary_sources_count ?? null,
        searchTotalResults: response.data.search_total_results ?? null,
        searchUniqueSources: response.data.search_unique_sources ?? null,
        conflictMessages: response.data.conflict_messages || [],
        messageId: response.data.message_id,
        isTyping: responseText && responseText.trim() !== ''  // Only mark as typing if there's actual content
      }
      
      console.log('ChatInterface - Created aiMessage:', {
        hasContent: !!aiMessage.content,
        contentLength: aiMessage.content?.length || 0,
        contentPreview: aiMessage.content?.substring(0, 100) || '(empty)',
        isTyping: aiMessage.isTyping,
        hasScenarioPrediction: !!aiMessage.scenarioPrediction
      })

      setMessages(prev => [...prev, aiMessage])
      setSources(response.data.sources || [])
    } catch (error) {
      console.error('Chat error:', error)
      let errorText = 'An error occurred while processing your request.'
      
      if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        // Request timeout
        errorText = 'Request timed out. The AI is taking too long to respond. This may happen with complex queries. Please try a shorter question or wait a moment and try again.'
      } else if (error.response) {
        // Server responded with error
        const detail = error.response.data?.detail || error.response.statusText
        errorText = `Error (${error.response.status}): ${detail}`
        
        if (error.response.status === 401) {
          errorText = 'Authentication required. Please log in again.'
        } else if (error.response.status === 500) {
          if (detail && 'timeout' in detail.toLowerCase()) {
            errorText = 'The AI response timed out. This may happen with large queries. Please try a shorter question or wait a moment and try again.'
          } else {
            errorText = `Server error: ${detail}. Please check that Ollama is running and try again.`
          }
        }
      } else if (error.request) {
        // Request made but no response
        errorText = 'No response from server. Please check that the backend is running on port 5000.'
      } else {
        // Error setting up request
        errorText = `Error: ${error.message}`
      }
      
      const errorMessage = {
        role: 'assistant',
        content: errorText,
        error: true
      }
      setMessages(prev => [...prev, errorMessage])
    } finally {
      setLoading(false)
    }
  }

  // Listen for auto-play setting changes
  useEffect(() => {
    const handleStorageChange = () => {
      setAutoPlayVoice(localStorage.getItem('tts_autoplay') === 'true')
    }
    window.addEventListener('storage', handleStorageChange)
    // Also check periodically (for same-window changes)
    const interval = setInterval(handleStorageChange, 500)
    return () => {
      window.removeEventListener('storage', handleStorageChange)
      clearInterval(interval)
    }
  }, [])

  // Get the latest prediction from the most recent assistant message
  // Check both typing and non-typing messages to catch predictions immediately
  const allAssistantMessages = messages.filter(msg => msg.role === 'assistant' && msg.scenarioPrediction)
  const latestPrediction = allAssistantMessages.length > 0 
    ? allAssistantMessages[allAssistantMessages.length - 1].scenarioPrediction 
    : null
  
  // Debug: log latest prediction and all messages with predictions
  console.log('ChatInterface - All assistant messages with predictions:', allAssistantMessages.length);
  allAssistantMessages.forEach((msg, idx) => {
    console.log(`Message ${idx}:`, {
      hasPrediction: !!msg.scenarioPrediction,
      isTyping: msg.isTyping,
      prediction: msg.scenarioPrediction
    });
  });
  
  if (latestPrediction) {
    console.log('ChatInterface - Latest prediction for panel:', latestPrediction);
    console.log('Latest prediction similar_scenarios:', latestPrediction.similar_scenarios);
    console.log('Latest prediction top_similar_scenarios:', latestPrediction.top_similar_scenarios?.length || 0);
  } else {
    console.log('ChatInterface - No prediction found in any messages');
  }

  return (
    <div className="chat-interface-wrapper">
      <div className="chat-interface">
        <div className="chat-messages" ref={messagesContainerRef}>
        {messages.length === 0 && (
          <div className="welcome-message">
            <h2>P.R.A.E.T.O.R. System Online.</h2>
            <p>Awaiting tactical legal parameters.</p>
            <p className="disclaimer">
              <strong>Protocol:</strong> All responses follow C.R.A.C. format. Verify citations (e.g., § 18.2-57.2).
            </p>
          </div>
        )}
        
        {messages.map((msg, idx) => (
          <div key={`msg-${idx}-${msg.content?.substring(0, 20)}`} className={`message ${msg.role}`}>
            <div className="message-content">
              <div className="message-text">
                {msg.role === 'assistant' && !msg.error && msg.isTyping !== false ? (
                  <TypingText 
                    text={msg.content} 
                    speed={15}
                    onComplete={() => {
                      // Mark message as done typing (only update if still typing)
                      setMessages(prev => prev.map((m, i) => {
                        if (i === idx && m.isTyping !== false) {
                          const updated = { ...m, isTyping: false };
                          // Debug: log when message finishes typing
                          if (updated.scenarioPrediction) {
                            console.log('Message finished typing, prediction available:', updated.scenarioPrediction);
                          }
                          return updated;
                        }
                        return m;
                      }))
                    }}
                  />
                ) : msg.role === 'assistant' && !msg.error ? (
                  <LegalResponseFormatter text={msg.content} />
                ) : (
                  msg.content
                )}
              </div>
              {msg.role === 'assistant' && !msg.error && msg.isTyping === false && (
                <VoicePlayer key={`voice-${idx}-${msg.content?.substring(0, 20)}`} text={msg.content} autoPlay={autoPlayVoice} />
              )}
              {msg.role === 'assistant' && !msg.error && !msg.isTyping && msg.verificationStatus && (
                <div className={`guardrail-status ${msg.verificationStatus !== 'verified' ? 'guardrail-warning' : ''}`}>
                  <strong>Guardrail status:</strong>{' '}
                  {msg.verificationStatus === 'verified' ? 'Verified by multiple authoritative sources' : 'Limited authoritative support — cross-check required'}
                  {msg.authoritativeSourcesCount != null && (
                    <> · {msg.authoritativeSourcesCount} authoritative source group{msg.authoritativeSourcesCount === 1 ? '' : 's'}</>
                  )}
                  {msg.secondarySourcesCount != null && msg.secondarySourcesCount > 0 && (
                    <> · {msg.secondarySourcesCount} secondary source group{msg.secondarySourcesCount === 1 ? '' : 's'}</>
                  )}
                  {msg.searchTotalResults != null && msg.searchUniqueSources != null && (
                    <> · {msg.searchTotalResults} results across {msg.searchUniqueSources} unique sources</>
                  )}
                </div>
              )}
              {msg.sources && msg.sources.length > 0 && !msg.isTyping && (
                <ExpandableSources 
                  sources={msg.sources}
                  messageId={msg.messageId}
                  summaryCounts={summaryCounts}
                />
              )}
              {msg.warnings && msg.warnings.length > 0 && !msg.isTyping && (
                <div className="warnings">
                  {msg.warnings.map((warning, i) => (
                    <div key={i} className="warning">⚠️ {warning}</div>
                  ))}
                </div>
              )}
            </div>
          </div>
        ))}
        
        {loading && (
          <div className="message assistant">
            <div className="message-content">
              <div className="loading">
                Thinking...
                <span style={{ marginLeft: '10px', fontSize: '0.85em', opacity: 0.7, display: 'block', marginTop: '5px' }}>
                  (This may take 1-5 minutes for complex queries. Please wait...)
                </span>
              </div>
            </div>
          </div>
        )}
        
        <div ref={messagesEndRef} />
        </div>

        {/* Detail Level Selector - Collapsible Advanced Options */}
        <div className="advanced-options-container">
          <button 
            type="button"
            className="advanced-options-toggle"
            onClick={() => setShowDetailSelector(!showDetailSelector)}
          >
            {recommendedLevel && !showDetailSelector && (
              <span className="recommended-badge">Recommended: {recommendedLevel}</span>
            )}
            {showDetailSelector ? '▼' : '▶'} Advanced Options
          </button>
          
          {showDetailSelector && (
            <div className="advanced-options-content">
              <div className="detail-level-selector">
                <label>Response Detail Level:</label>
                <select 
                  value={detailLevel || 'auto'} 
                  onChange={(e) => setDetailLevel(e.target.value === 'auto' ? null : e.target.value)}
                >
                  <option value="auto">⚡ Auto (Smart Default)</option>
                  <option value="summary">📝 Quick Summary (~700 words)</option>
                  <option value="standard">📄 Standard (~1,400 words)</option>
                  <option value="comprehensive">📚 Comprehensive (~4,500 words)</option>
                  <option value="complete">📖 Complete (~12,000 words)</option>
                  <option value="unlimited">🔥 Unlimited (~24,000 words)</option>
                </select>
                {recommendedLevel && (
                  <span className="recommendation-note">
                    Smart default recommends: <strong>{recommendedLevel}</strong>
                  </span>
                )}
              </div>
              
              <div className="exhaustive-mode-toggle">
                <label>
                  <input 
                    type="checkbox" 
                    checked={exhaustiveMode} 
                    onChange={(e) => setExhaustiveMode(e.target.checked)}
                  />
                  <span>🔍 Exhaustive Search (Trial Prep Mode)</span>
                </label>
                <p className="exhaustive-note">
                  Searches 500+ sources with 10+ query variations. Takes 3-5 minutes.
                </p>
              </div>
            </div>
          )}
        </div>

        <form className="chat-input-form" onSubmit={handleSubmit}>
        <label className="attach-label">
          <input type="file" multiple onChange={(e) => setFiles(Array.from(e.target.files || []))} />
          <span>Attach</span>
        </label>
        {uploadStatus && <span className="upload-status">{uploadStatus}</span>}
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Ask a legal question or request a form..."
          disabled={loading}
          className="chat-input"
        />
        <button type="submit" disabled={loading || !input.trim()} className="send-button">
          Send
        </button>
      </form>
      </div>
      <ScenarioPredictionPanel 
        prediction={latestPrediction}
        key={`prediction-${latestPrediction ? 'has-data' : 'empty'}-${messages.length}`}
      />
    </div>
  )
}

export default ChatInterface

