import React, { useState } from 'react'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import ErrorBoundary from './components/ErrorBoundary'
import Login from './components/Login'
import ChatInterface from './components/ChatInterface'
import ChatHistory from './components/ChatHistory'
import UploadDocument from './components/UploadDocument'
import SettingsMenu from './components/SettingsMenu'
import './App.css'

function AppContent() {
  const { isAuthenticated, loading, user } = useAuth()
  const [activeTab, setActiveTab] = useState('chat')

  if (loading) {
    return (
      <div className="App">
        <div className="loading-container">
          <p>Loading...</p>
        </div>
      </div>
    )
  }

  if (!isAuthenticated) {
    return <Login />
  }

  return (
    <div className="App">
      <header className="App-header">
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', width: '100%' }}>
          <div>
            <h1 style={{ letterSpacing: '2px' }}>P.R.A.E.T.O.R.</h1>
            <p style={{ fontSize: '12px', letterSpacing: '1px', textTransform: 'uppercase', opacity: 0.8 }}>Si Vis Pacem, Para Bellum</p>
            <p style={{ fontSize: '10px', opacity: 0.6, marginTop: '4px', fontFamily: 'monospace' }}>PROFESSIONAL RESEARCH AGENT // V.1.0</p>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '20px' }}>
            <SettingsMenu />
          </div>
        </div>
      </header>
      <div className="tabs">
        <button
          className={activeTab === 'chat' ? 'active' : ''}
          onClick={() => setActiveTab('chat')}
        >
          Chat
        </button>
        {(user?.role === 'admin' || user?.role === 'attorney' || user?.role === 'attorney_partner') && (
          <button
            className={activeTab === 'history' ? 'active' : ''}
            onClick={() => setActiveTab('history')}
          >
            Chat History
          </button>
        )}
        {(user?.role === 'admin' || user?.role === 'attorney' || user?.role === 'paralegal' || user?.role === 'attorney_partner') && (
          <button
            className={activeTab === 'upload' ? 'active' : ''}
            onClick={() => setActiveTab('upload')}
          >
            Upload Docs
          </button>
        )}
      </div>
      <main>
        {activeTab === 'chat' && <ChatInterface />}
        {activeTab === 'history' && <ChatHistory />}
        {activeTab === 'upload' && <UploadDocument />}
      </main>
      <footer className="App-footer">
        <span className="App-version">v1.0</span>
        <a href="/compliance.html" target="_blank" rel="noopener noreferrer" className="App-compliance-link">Privacy &amp; Compliance</a>
      </footer>
    </div>
  )
}

function App() {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <AppContent />
      </AuthProvider>
    </ErrorBoundary>
  )
}

export default App
