import React, { useState, useEffect } from 'react'
import { AuthProvider, useAuth } from './contexts/AuthContext'
import Login from './components/Login'
import ChatInterface from './components/ChatInterface'
import ChatHistory from './components/ChatHistory'
import UploadDocument from './components/UploadDocument'
import AdminDashboard from './components/AdminDashboard'
import ScenarioAnalysis from './components/ScenarioAnalysis'
import ResponseReview from './components/ResponseReview'
import SettingsMenu from './components/SettingsMenu'
import axios from 'axios'
import './App.css'

const API_BASE = import.meta.env.VITE_API_URL || ''

function AppContent() {
  const { isAuthenticated, loading, user, logout } = useAuth()
  const [activeTab, setActiveTab] = useState('chat')
  const [scenarioDbEnabled, setScenarioDbEnabled] = useState(false)

  // Check if scenario database is enabled
  useEffect(() => {
    const checkScenarioDb = async () => {
      try {
        // Try to access scenario stats endpoint - if it exists, feature is enabled
        await axios.get(`${API_BASE}/api/scenarios/stats`)
        setScenarioDbEnabled(true)
      } catch (err) {
        // Endpoint doesn't exist or feature disabled
        setScenarioDbEnabled(false)
      }
    }
    if (isAuthenticated) {
      checkScenarioDb()
    }
  }, [isAuthenticated])

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
        {scenarioDbEnabled && (user?.role === 'admin' || user?.role === 'attorney' || user?.role === 'attorney_partner') && (
          <button
            className={activeTab === 'scenarios' ? 'active' : ''}
            onClick={() => setActiveTab('scenarios')}
          >
            Scenario Analysis
          </button>
        )}
        {(user?.role === 'admin' || user?.role === 'attorney_partner') && (
          <button
            className={activeTab === 'reviews' ? 'active' : ''}
            onClick={() => setActiveTab('reviews')}
          >
            Review Responses
          </button>
        )}
        {(user?.role === 'admin' || user?.role === 'attorney_partner') && (
          <button
            className={activeTab === 'admin' ? 'active' : ''}
            onClick={() => setActiveTab('admin')}
          >
            Administration
          </button>
        )}
      </div>
      <main>
        {activeTab === 'chat' && <ChatInterface />}
        {activeTab === 'history' && <ChatHistory />}
        {activeTab === 'upload' && <UploadDocument />}
        {activeTab === 'scenarios' && <ScenarioAnalysis />}
        {activeTab === 'reviews' && <ResponseReview />}
        {activeTab === 'admin' && <AdminDashboard />}
      </main>
    </div>
  )
}

function App() {
  return (
    <AuthProvider>
      <AppContent />
    </AuthProvider>
  )
}

export default App

