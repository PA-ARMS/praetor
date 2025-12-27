import React, { useEffect } from 'react'
import { AuthProvider, useAuth } from '../contexts/AuthContext'
import LearningDashboard from '../components/LearningDashboard'
import Login from '../components/Login'
import './LearningDashboardPage.css'

function LearningDashboardPage() {
  const { isAuthenticated, loading } = useAuth()

  // Show loading while checking auth
  if (loading) {
    return (
      <div className="learning-dashboard-page">
        <div style={{ padding: '2rem', textAlign: 'center' }}>
          <p>Loading...</p>
        </div>
      </div>
    )
  }

  // Show login if not authenticated
  if (!isAuthenticated) {
    return (
      <div className="learning-dashboard-page">
        <div className="learning-dashboard-header">
          <h1>🧠 AI Learning Dashboard</h1>
          <p>Please login to access the learning dashboard</p>
        </div>
        <div style={{ maxWidth: '400px', margin: '2rem auto' }}>
          <Login />
        </div>
      </div>
    )
  }

  // Show dashboard if authenticated
  return (
    <div className="learning-dashboard-page">
      <div className="learning-dashboard-header">
        <h1>🧠 AI Learning Dashboard</h1>
        <p>Monitor and control the AI learning system</p>
      </div>
      <div className="learning-dashboard-content">
        <LearningDashboard />
      </div>
    </div>
  )
}

// Wrapper with AuthProvider for standalone page
function LearningDashboardPageWithAuth() {
  return (
    <AuthProvider>
      <LearningDashboardPage />
    </AuthProvider>
  )
}

export default LearningDashboardPageWithAuth

