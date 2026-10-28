import React, { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import TypingText from './TypingText'
import LegalResponseFormatter from './LegalResponseFormatter'
import ExpandableSources from './ExpandableSources'
import { useAuth } from '../contexts/AuthContext'
import './ChatInterface.css'
import { API_BASE } from '../apiConfig.js'
import {
  VOICE_CHANGE_EVENT,
  getVoiceEnabled,
  setVoiceEnabled,
  speakResponse,
  stopSpeaking,
} from '../utils/praetorVoice.js'

/** Matches server config.ALLOWED_FILE_EXTENSIONS (subset clients check before upload). */
const ACCEPT_UPLOAD =
  '.pdf,.txt,.docx,.html,.htm,.md,.png,.jpg,.jpeg,.jfif,.webp,.tif,.tiff,.bmp'

const ALLOWED_EXT = new Set(
  ACCEPT_UPLOAD.split(',').map((x) => x.trim().toLowerCase().replace(/^\./, ''))
)

const DEFAULT_DOC_WORKFLOW_PROMPT =
  'I attached document(s). Summarize what they show based on the extracted text, note any deadlines or key dates you see, ' +
  'and give me numbered practical next steps (what to do next, what to verify, and what to gather). If text looks like a poor scan, say so.'

function ChatInterface() {
  const { token } = useAuth()
  const [messages, setMessages] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [sources, setSources] = useState([])
  const [files, setFiles] = useState([])
  const [dragOver, setDragOver] = useState(false)
  const [uploadStatus, setUploadStatus] = useState(null)
  const [detailLevel, setDetailLevel] = useState(null) // null = auto (smart default)
  const [recommendedLevel, setRecommendedLevel] = useState(null)
  const [showDetailSelector, setShowDetailSelector] = useState(false)
  const [exhaustiveMode, setExhaustiveMode] = useState(false)
  const [skipClarification, setSkipClarification] = useState(false)
  const [useWeb, setUseWeb] = useState(true)
  const [voiceOn, setVoiceOn] = useState(() => getVoiceEnabled())
  const [summaryCounts, setSummaryCounts] = useState({})
  const lastSpokenIdRef = useRef(null)
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
  const [chatReady, setChatReady] = useState(null)

  useEffect(() => {
    const sync = (e) => {
      const on = e?.detail?.on
      setVoiceOn(typeof on === 'boolean' ? on : getVoiceEnabled())
    }
    window.addEventListener(VOICE_CHANGE_EVENT, sync)
    return () => window.removeEventListener(VOICE_CHANGE_EVENT, sync)
  }, [])

  useEffect(() => {
    if (!voiceOn) {
      stopSpeaking()
      return
    }
    const last = messages[messages.length - 1]
    if (!last || last.role !== 'assistant' || last.error) return
    const speakKey = last.messageId || last.content
    if (lastSpokenIdRef.current === speakKey) return
    lastSpokenIdRef.current = speakKey
    speakResponse(last.content)
  }, [messages, voiceOn])

  useEffect(() => {
    let cancelled = false
    async function check() {
      try {
        const r = await axios.get(`${API_BASE}/api/chat/ready`, { timeout: 5000 })
        if (!cancelled) {
          const data = r.data || {}
          if (data.corpus_update_in_progress) {
            data.ready = true
            data.message =
              data.message ||
              'Statute index is rebuilding. Chat works; legal search may be slow until indexing finishes.'
          }
          setChatReady(data)
        }
      } catch {
        if (cancelled) return
        setChatReady({
          ready: false,
          message:
            'Backend not reachable at ' +
            API_BASE +
            '. Start the server on port 5001 (START_BACKEND.bat). For a different host, set VITE_API_URL in client/.env and restart Vite.',
        })
      }
    }
    check()
    return () => { cancelled = true }
  }, [])

  const mergeFileList = (incoming) => {
    const list = Array.from(incoming || []).filter((f) => {
      const ext = (f.name.split('.').pop() || '').toLowerCase()
      return ALLOWED_EXT.has(ext)
    })
    if (list.length === 0) return
    setFiles((prev) => {
      const seen = new Set(prev.map((p) => `${p.name}:${p.size}`))
      const next = [...prev]
      for (const f of list) {
        const k = `${f.name}:${f.size}`
        if (!seen.has(k)) {
          seen.add(k)
          next.push(f)
        }
      }
      return next
    })
  }

  const handleSubmit = async (e) => {
    e.preventDefault()
    if (loading) return

    const messageText = input.trim() || (files.length > 0 ? DEFAULT_DOC_WORKFLOW_PROMPT : '')
    if (!messageText) return

    const userMessage = { role: 'user', content: messageText }
    setMessages(prev => [...prev, userMessage])
    const currentInput = messageText
    const docSources = files.map(f => f.name)
    setInput('')
    setLoading(true)
    setSources([])
    stopSpeaking()

    try {
      // If files selected, upload them first so they become searchable; capture extracted_text for chat (reliable path).
      let attachmentExtractedText = ''
      const indexerSummaries = []
      if (files.length > 0) {
        setUploadStatus('Uploading documents...')
        const uploadHeaders = {}
        if (token) uploadHeaders['Authorization'] = `Bearer ${token}`
        for (let i = 0; i < files.length; i++) {
          const file = files[i]
          const form = new FormData()
          form.append('file', file)
          form.append('jurisdiction', 'Virginia')
          const isPDF = file.name.toLowerCase().endsWith('.pdf')
          const up = await axios.post(`${API_BASE}/api/rag/upload-document`, form, {
            headers: uploadHeaders,
            timeout: isPDF ? 1_800_000 : 300_000,
          })
          if (up.data?.status !== 'success') {
            throw new Error(
              (typeof up.data?.detail === 'string' && up.data.detail) ||
                up.data?.message ||
                'Upload did not return success'
            )
          }
          const sum = up.data?.understanding?.summary
          if (typeof sum === 'string' && sum.trim()) {
            indexerSummaries.push(`## ${file.name}\n${sum.trim()}`)
          }
          const t = up.data?.extracted_text
          if (typeof t === 'string' && t.trim()) {
            attachmentExtractedText += `\n\n--- ${file.name} ---\n\n${t}`
          } else {
            console.warn(`Upload ${file.name}: no extracted_text in response (empty PDF / OCR failed?)`, up.data)
          }
        }
        let merged = attachmentExtractedText.trim()
        if (indexerSummaries.length > 0) {
          merged =
            '[Indexer summaries — use to identify what each file is before reading raw text; exhibits may OCR as noise.]\n\n' +
            indexerSummaries.join('\n\n---\n\n') +
            '\n\n=== Extracted plain text (full pass; may include exhibit OCR) ===\n\n' +
            merged
        }
        attachmentExtractedText = merged.slice(0, 150000)
        if (docSources.length > 0 && !attachmentExtractedText) {
          setUploadStatus('Uploaded but no extractable text — chat may not see the file. Try a text PDF or enable OCR.')
        } else {
          setUploadStatus(`Uploaded ${files.length} document(s).`)
        }
        setFiles([])
      } else {
        setUploadStatus(null)
      }

      const payload = {
        message: currentInput,
        conversation_id: conversationId,
        // Always request RAG from the UI; backend intent routing now decides
        // whether to actually use legal retrieval for this specific prompt.
        use_rag: true,
        use_web: useWeb,
        ...(docSources.length > 0 ? { doc_sources: docSources } : {}),
        ...(attachmentExtractedText.length > 0 ? { attachment_extracted_text: attachmentExtractedText } : {}),
      }
      const chatHeaders = { 'Content-Type': 'application/json' }
      if (token) chatHeaders['Authorization'] = `Bearer ${token}`
      const response = await axios.post(`${API_BASE}/api/chat/simple`, payload, {
        timeout: 180000,
        headers: chatHeaders
      })
      
      if (!response.data?.response?.trim()) {
        throw new Error('Empty response from server. Try again in a moment.')
      }
      
      // Update conversation ID if this is a new conversation
      if (!conversationId && response.data.conversation_id) {
        setConversationId(response.data.conversation_id)
      }

      const responseText = response.data.response || ''
      const aiMessage = {
        role: 'assistant',
        content: responseText || 'No response received. Please try again.',
        sources: response.data.sources || [],
        warnings: response.data.warnings || [],
        messageId: response.data.message_id,
        isTyping: false,
        clarificationOnly: false,
        clarificationQuestions: null,
      }
      setMessages(prev => [...prev, aiMessage])
      setSources(response.data.sources || [])
    } catch (error) {
      console.error('Chat error:', error)
      console.error('Error details:', {
        message: error.message,
        response: error.response?.data,
        status: error.response?.status,
        statusText: error.response?.statusText,
        request: error.config
      })
      
      let errorText = 'An error occurred while processing your request.'
      
      // Handle 400 Bad Request (validation errors)
      if (error.response?.status === 400) {
        const errorData = error.response?.data
        if (errorData?.message) {
          errorText = errorData.message
        } else if (errorData?.detail) {
          errorText = Array.isArray(errorData.detail) 
            ? errorData.detail.map(d => d.msg || d).join(', ')
            : errorData.detail
        } else {
          errorText = 'Invalid request. Please check your message and try again.'
        }
      }
      
      if (error.code === 'ECONNABORTED' || error.message?.includes('timeout')) {
        errorText = 'Request timed out. The AI can take 1–5 minutes for complex queries. Try a shorter question or try again.'
      } else if (error.response) {
        const detail = (typeof error.response.data?.detail === 'string')
          ? error.response.data.detail
          : (Array.isArray(error.response.data?.detail) ? error.response.data.detail.map(d => d.msg || d).join(', ') : error.response.statusText)
        errorText = `Error (${error.response.status}): ${detail}`
        if (error.response.status === 401) {
          errorText = 'Session expired or not logged in. Please log out and log in again, then try your question again.'
        } else if (error.response.status === 500) {
          const rawDetail = (error.response.data?.detail || '').toString()
          const d = rawDetail.toLowerCase()
          if (d.includes('ollama') || d.includes('timeout') || d.includes('model')) {
            errorText = rawDetail.length > 400 ? rawDetail.slice(0, 400) + '...' : rawDetail
          } else {
            errorText = rawDetail.length > 300 ? rawDetail.slice(0, 300) + '...' : (rawDetail || `Server error (${error.response.status}). Check backend logs.`)
          }
        }
      } else if (error.request) {
        errorText = 'No response from server. Is the backend running on port 5001? Start it and try again.'
      } else {
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

  return (
    <div className="chat-interface-wrapper">
      <div
        className={`chat-interface chat-drop-zone ${dragOver ? 'drag-over' : ''}`}
        onDragEnter={(e) => {
          e.preventDefault()
          e.stopPropagation()
          setDragOver(true)
        }}
        onDragOver={(e) => {
          e.preventDefault()
          e.stopPropagation()
          setDragOver(true)
        }}
        onDragLeave={(e) => {
          e.preventDefault()
          e.stopPropagation()
          if (!e.currentTarget.contains(e.relatedTarget)) setDragOver(false)
        }}
        onDrop={(e) => {
          e.preventDefault()
          e.stopPropagation()
          setDragOver(false)
          mergeFileList(e.dataTransfer?.files)
        }}
      >
        <div className="chat-messages" ref={messagesContainerRef}>
        {messages.length === 0 && (
          <div className="welcome-message">
            <h2>P.R.A.E.T.O.R. System Online.</h2>
            <p>Awaiting tactical legal parameters.</p>
            <p className="disclaimer">
              <strong>Protocol:</strong> Legal questions use a structured research memo (Issue, Short answer, Analysis, Authorities, Gaps). Verify all citations before filing or client advice. Live official lookup pulls current Code text from law.lis.virginia.gov — not the open internet.
            </p>
            <p className="doc-workflow-hint">
              Attach or drag and drop PDFs, Word, images, or text files. The system extracts text (OCR for scans), then answers—including a summary and practical next steps. You can send with only attachments.
            </p>
            {chatReady && (
              <p className={`chat-ready-status ${chatReady.ready ? 'ready' : 'not-ready'}`}>
                {chatReady.corpus_update_in_progress
                  ? `⚠ ${chatReady.message || 'Statute index rebuilding — chat may be slow'}`
                  : chatReady.ready
                    ? '✓ Chat ready'
                    : `⚠ ${chatReady.message || 'Chat not ready'}`}
              </p>
            )}
          </div>
        )}
        
        {messages.map((msg, idx) => (
          <div key={`msg-${idx}-${msg.content?.substring(0, 20)}`} className={`message ${msg.role} ${msg.clarificationOnly ? 'clarification-only' : ''}`}>
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
              {msg.role === 'assistant' && msg.clarificationOnly && msg.clarificationQuestions && msg.clarificationQuestions.length > 0 && !msg.isTyping && (
                <div className="clarification-prompts">
                  <span className="clarification-prompt-label">Click to answer:</span>
                  {msg.clarificationQuestions.map((q, qIdx) => (
                    <button
                      key={qIdx}
                      type="button"
                      className="clarification-prompt-btn"
                      onClick={() => setInput(q)}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              )}
              {msg.role === 'assistant' && !msg.error && !msg.isTyping && msg.verificationStatus && !msg.clarificationOnly && (
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
              {msg.sources && msg.sources.length > 0 && !msg.isTyping && !msg.clarificationOnly && (
                <ExpandableSources 
                  sources={msg.sources}
                  messageId={msg.messageId}
                  summaryCounts={summaryCounts}
                />
              )}
              {msg.warnings && msg.warnings.length > 0 && !msg.isTyping && !msg.clarificationOnly && (
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

        <form className="chat-input-form" onSubmit={handleSubmit}>
        <label className="attach-label" title="Choose files or drag onto chat">
          <input
            type="file"
            multiple
            accept={ACCEPT_UPLOAD}
            onChange={(e) => {
              mergeFileList(e.target.files)
              e.target.value = ''
            }}
          />
          <span>Attach</span>
        </label>
        {uploadStatus && <span className="upload-status">{uploadStatus}</span>}
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder={
            files.length > 0
              ? 'Optional: add instructions, or send for summary + next steps…'
              : 'Ask a legal question, or attach / drop files for extraction and next steps…'
          }
          disabled={loading}
          className="chat-input"
          maxLength={50000}
          title="Max 50,000 characters"
        />
        <button type="submit" disabled={loading || (!input.trim() && files.length === 0)} className="send-button">
          Send
        </button>
      </form>
      <div className="chat-toggles">
        <label className="live-lookup-toggle" title="Fetch current official statute pages from law.lis.virginia.gov">
          <input
            type="checkbox"
            checked={useWeb}
            onChange={(e) => setUseWeb(e.target.checked)}
            disabled={loading}
          />
          Live official lookup (LIS)
        </label>
        <label className="live-lookup-toggle" title="Speak replies aloud. Voice is fixed (Cortana-style if available, otherwise a British butler).">
          <input
            type="checkbox"
            checked={voiceOn}
            onChange={(e) => {
              const on = e.target.checked
              setVoiceOn(on)
              setVoiceEnabled(on)
              if (!on) stopSpeaking()
            }}
          />
          Speak replies
        </label>
      </div>
        {files.length > 0 && (
          <div className="queued-files" aria-live="polite">
            <span className="queued-files-label">Queued ({files.length})</span>
            <ul className="queued-files-list">
              {files.map((f, i) => (
                <li key={`${f.name}-${f.size}-${i}`} className="file-chip">
                  <span className="file-chip-name" title={f.name}>{f.name}</span>
                  <button
                    type="button"
                    className="file-chip-remove"
                    onClick={() => setFiles((prev) => prev.filter((_, idx) => idx !== i))}
                    aria-label={`Remove ${f.name}`}
                  >
                    ×
                  </button>
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    </div>
  )
}

export default ChatInterface

