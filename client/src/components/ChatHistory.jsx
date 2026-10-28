import React, { useState, useEffect, useRef } from 'react'
import axios from 'axios'
import { useAuth } from '../contexts/AuthContext'
import './ChatHistory.css'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

import { API_BASE } from '../apiConfig.js'

function ChatHistory() {
  const { user } = useAuth()
  const [accessibleUsers, setAccessibleUsers] = useState([])
  const [selectedUserId, setSelectedUserId] = useState(null)
  const [conversations, setConversations] = useState([])
  const [selectedConversation, setSelectedConversation] = useState(null)
  const [messages, setMessages] = useState([])
  const [loading, setLoading] = useState(false)
  const messagesListRef = useRef(null)
  const scrollPositionsRef = useRef({}) // Store scroll positions per conversation

  // Check if user can view all chats (Senior Partner or Admin)
  const canViewAllChats = user?.role === 'attorney_partner' || user?.role === 'admin'

  // Load accessible users on mount
  useEffect(() => {
    loadAccessibleUsers()
  }, [])

  // Load conversations when user is selected
  useEffect(() => {
    if (selectedUserId) {
      loadConversations(selectedUserId)
    }
  }, [selectedUserId])

  // Load messages when conversation is selected
  useEffect(() => {
    if (selectedConversation) {
      loadMessages(selectedConversation)
    }
  }, [selectedConversation])

  // Restore scroll position when messages change
  useEffect(() => {
    if (messagesListRef.current && selectedConversation) {
      const savedPosition = scrollPositionsRef.current[selectedConversation]
      if (savedPosition !== undefined) {
        // Use requestAnimationFrame to ensure DOM is updated
        requestAnimationFrame(() => {
          if (messagesListRef.current) {
            messagesListRef.current.scrollTop = savedPosition
          }
        })
      }
    }
  }, [messages, selectedConversation])

  // Save scroll position when scrolling
  const handleScroll = () => {
    if (messagesListRef.current && selectedConversation) {
      scrollPositionsRef.current[selectedConversation] = messagesListRef.current.scrollTop
    }
  }

  const loadAccessibleUsers = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/auth/users/accessible`)
      setAccessibleUsers(response.data.users)
      // Auto-select current user
      if (response.data.users.length > 0) {
        const currentUser = response.data.users.find(u => u.id === user?.id)
        // If user can only see their own chats, auto-select themselves
        // Otherwise, select current user if available, or first user
        if (!canViewAllChats) {
          setSelectedUserId(user?.id || response.data.users[0].id)
        } else {
          setSelectedUserId(currentUser ? currentUser.id : response.data.users[0].id)
        }
      }
    } catch (error) {
      console.error('Failed to load users:', error)
    }
  }

  const loadConversations = async (userId) => {
    try {
      setLoading(true)
      const response = await axios.get(`${API_BASE}/api/chat/history/conversations`, {
        params: { user_id: userId }
      })
      setConversations(response.data.conversations)
      setSelectedConversation(null)
      setMessages([])
    } catch (error) {
      console.error('Failed to load conversations:', error)
    } finally {
      setLoading(false)
    }
  }

  const loadMessages = async (conversationId) => {
    try {
      setLoading(true)
      const response = await axios.get(`${API_BASE}/api/chat/history`, {
        params: {
          conversation_id: conversationId,
          user_id: selectedUserId,
          limit: 1000
        }
      })
      // Reverse to show oldest first
      setMessages(response.data.messages.reverse())
    } catch (error) {
      console.error('Failed to load messages:', error)
    } finally {
      setLoading(false)
    }
  }

  const selectedUser = accessibleUsers.find(u => u.id === selectedUserId)

  return (
    <div className="chat-history-container">
      <div className="chat-history-sidebar">
        <h2>Chat History</h2>
        
        {canViewAllChats && (
          <div className="user-selector">
            <label>View chats for:</label>
            <select
              value={selectedUserId || ''}
              onChange={(e) => setSelectedUserId(parseInt(e.target.value))}
              className="user-select"
            >
              {accessibleUsers.map(u => (
                <option key={u.id} value={u.id}>
                  {u.full_name} ({u.role})
                </option>
              ))}
            </select>
          </div>
        )}

        {selectedUserId && (
          <div className="conversations-list">
            <h3>Conversations</h3>
            {loading ? (
              <p>Loading...</p>
            ) : conversations.length === 0 ? (
              <p className="no-data">No conversations found</p>
            ) : (
              <ul>
                {conversations.map((conv, idx) => (
                  <li
                    key={conv}
                    className={selectedConversation === conv ? 'active' : ''}
                    onClick={() => {
                      // Save current scroll position before switching
                      if (messagesListRef.current && selectedConversation) {
                        scrollPositionsRef.current[selectedConversation] = messagesListRef.current.scrollTop
                      }
                      // Only set if different conversation to avoid unnecessary reload
                      if (selectedConversation !== conv) {
                        setSelectedConversation(conv)
                      }
                    }}
                  >
                    Conversation {idx + 1}
                    <br />
                    <small>{conv}</small>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>

      <div className="chat-history-main">
        {selectedConversation ? (
          <div className="messages-view">
            <div className="messages-header">
              <h3>
                {selectedUser?.full_name}'s Conversation
              </h3>
              <button onClick={() => setSelectedConversation(null)}>Back</button>
            </div>
            
            {loading ? (
              <div className="loading">Loading messages...</div>
            ) : (
              <div 
                className="messages-list" 
                ref={messagesListRef}
                onScroll={handleScroll}
              >
                {messages.map((msg) => (
                    <div key={msg.id} className={`message-item ${msg.message ? 'user' : 'assistant'}`}>
                      <div className="message-header">
                        <strong>{msg.message ? 'User' : 'Praetor'}</strong>
                      <span className="timestamp">
                        {new Date(msg.timestamp).toLocaleString()}
                      </span>
                    </div>
                    <div className="message-content">
                      {msg.message && <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.message}</ReactMarkdown>}
                      {msg.response && <ReactMarkdown remarkPlugins={[remarkGfm]}>{msg.response}</ReactMarkdown>}
                      {msg.sources && msg.sources.length > 0 && (
                        <div className="sources">
                          <strong>Sources:</strong>
                          <ul>
                            {msg.sources.slice(0, 10).map((source, i) => (
                              <li key={i}>
                                {source.source} ({source.jurisdiction})
                                {source.citation ? ` – ${source.citation}` : ''}
                              </li>
                            ))}
                            {msg.sources.length > 10 && (
                              <li>… and {msg.sources.length - 10} more</li>
                            )}
                          </ul>
                        </div>
                      )}
                      {msg.warnings && msg.warnings.length > 0 && (
                        <div className="warnings">
                          {msg.warnings.map((warning, i) => (
                            <div key={i} className="warning">⚠️ {warning}</div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        ) : (
          <div className="no-selection">
            <p>Select a conversation to view messages</p>
          </div>
        )}
      </div>
    </div>
  )
}

export default ChatHistory

