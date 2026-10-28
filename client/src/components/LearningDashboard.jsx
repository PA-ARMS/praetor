import React, { useState, useEffect } from 'react'
import axios from 'axios'
import './LearningDashboard.css'

import { API_BASE } from '../apiConfig.js'

function LearningDashboard() {
  const [stats, setStats] = useState({
    casesDownloaded: 0,
    casesProcessed: 0,
    scenariosInDatabase: 0,
    successRate: 0,
    outcomeDistribution: {},
    isProcessing: false,
    lastUpdate: null,
    progress: null
  })
  const [isLoading, setIsLoading] = useState(true)
  const [sessionStatus, setSessionStatus] = useState({
    status: 'idle',
    session: { is_running: false }
  })
  const [maxCases, setMaxCases] = useState('')
  const [isStarting, setIsStarting] = useState(false)
  const [isStopping, setIsStopping] = useState(false)
  const [continuousMode, setContinuousMode] = useState(false)

  const fetchStats = async () => {
    try {
      // Get download/processing stats
      const response = await axios.get(`${API_BASE}/api/scenarios/stats`).catch((error) => {
        // Log error but don't hide dashboard - allow it to show with empty stats
        console.error('Error fetching stats:', error)
        return null
      })
      
      if (!response) {
        // If stats fetch failed, set default values and continue
        setStats({
          casesDownloaded: 0,
          casesProcessed: 0,
          scenariosInDatabase: 0,
          successRate: 0,
          outcomeDistribution: {},
          isProcessing: false,
          lastUpdate: new Date().toLocaleTimeString(),
          progress: null
        })
        setIsLoading(false)
        return
      }
      
      // Get processing progress if available
      const progressResponse = await axios.get(`${API_BASE}/api/scenarios/progress`).catch(() => null)
      
      const progressData = progressResponse?.data || {}
      
      setStats({
        casesDownloaded: response.data.total_cases || 0,
        casesProcessed: progressData.total_processed || 0,
        scenariosInDatabase: response.data.total_scenarios || 0,
        successRate: progressData.success_rate || 0,
        outcomeDistribution: response.data.outcome_distribution || {},
        isProcessing: progressData.is_processing || false,
        lastUpdate: new Date().toLocaleTimeString(),
        progress: progressData.progress || null
      })
    } catch (error) {
      // Log error but continue - show dashboard with default/empty stats
      console.error('Error fetching learning stats:', error)
      // Set default stats so dashboard still shows
      setStats({
        casesDownloaded: 0,
        casesProcessed: 0,
        scenariosInDatabase: 0,
        successRate: 0,
        outcomeDistribution: {},
        isProcessing: false,
        lastUpdate: new Date().toLocaleTimeString(),
        progress: null
      })
    } finally {
      setIsLoading(false)
    }
  }

  const [logTail, setLogTail] = useState([])

  const fetchSessionStatus = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/scenarios/learning/status`).catch(() => null)
      if (response) {
        setSessionStatus(response.data)
        if (response.data.log_tail) {
          setLogTail(response.data.log_tail)
        }
      }
    } catch (error) {
      // Silently fail if not accessible
      if (error.response?.status !== 403) {
        console.error('Error fetching session status:', error)
      }
    }
  }

  const handleStartSession = async () => {
    setIsStarting(true)
    try {
      const maxCasesNum = maxCases ? parseInt(maxCases) : null
      console.log('Starting learning session:', { maxCasesNum, continuousMode })
      
      const response = await axios.post(
        `${API_BASE}/api/scenarios/learning/start`,
        { 
          max_cases: maxCasesNum,
          continuous: continuousMode
        }
      ).catch((error) => {
        console.error('Error starting learning session:', error)
        if (error.response?.status === 403) {
          alert('Learning controls are only available from localhost. Please access the dashboard from http://localhost:3000')
          return null
        }
        throw error
      })
      
      if (response) {
        console.log('Learning session started:', response.data)
        setSessionStatus(response.data)
        setMaxCases('') // Clear input
        // Refresh stats immediately
        setTimeout(() => {
          fetchStats()
          fetchSessionStatus()
        }, 1000)
      } else {
        console.warn('No response from start learning session')
      }
    } catch (error) {
      console.error('Failed to start learning session:', error)
      if (error.response?.status !== 403) {
        const errorMsg = error.response?.data?.detail || error.message || 'Unknown error'
        alert(`Error starting learning session: ${errorMsg}`)
      }
    } finally {
      setIsStarting(false)
    }
  }

  const handleStopSession = async () => {
    setIsStopping(true)
    try {
      console.log('Stopping learning session...')
      const response = await axios.post(`${API_BASE}/api/scenarios/learning/stop`).catch((error) => {
        console.error('Error stopping learning session:', error)
        if (error.response?.status === 403) {
          alert('Learning controls are only available from localhost. Please access the dashboard from http://localhost:3000')
          return null
        }
        throw error
      })
      
      if (response) {
        console.log('Learning session stopped:', response.data)
        setSessionStatus(response.data)
        // Refresh stats immediately
        setTimeout(() => {
          fetchStats()
          fetchSessionStatus()
        }, 1000)
      } else {
        console.warn('No response from stop learning session')
      }
    } catch (error) {
      console.error('Failed to stop learning session:', error)
      if (error.response?.status !== 403) {
        const errorMsg = error.response?.data?.detail || error.message || 'Unknown error'
        alert(`Error stopping learning session: ${errorMsg}`)
      }
    } finally {
      setIsStopping(false)
    }
  }

  useEffect(() => {
    fetchStats()
    fetchSessionStatus()
    // Update every 5 seconds
    const interval = setInterval(() => {
      fetchStats()
      fetchSessionStatus()
    }, 5000)
    return () => clearInterval(interval)
  }, [])

  if (isLoading) {
    return (
      <div className="learning-dashboard">
        <div className="learning-loading">Loading learning statistics...</div>
      </div>
    )
  }

  // Show dashboard even if no data yet - allow user to start learning sessions
  // The message about localhost has been removed since restrictions are gone

  const processingRate = stats.casesProcessed > 0 
    ? ((stats.scenariosInDatabase / stats.casesProcessed) * 100).toFixed(1)
    : 0

  const isSessionRunning = sessionStatus.session?.is_running || false

  // If this is the standalone page version, make it full-width
  const isStandalone = window.location.pathname.includes('learning-dashboard')
  
  return (
    <div className={`learning-dashboard ${isStandalone ? 'standalone' : ''}`}>
      <div className="learning-header">
        <h3>🧠 AI Learning Dashboard</h3>
        <div className="learning-status">
          {(stats.isProcessing || isSessionRunning) ? (
            <span className="status-active">● Active</span>
          ) : (
            <span className="status-idle">○ Idle</span>
          )}
        </div>
      </div>

      {/* Learning Session Controls */}
      <div className="learning-controls">
        <div className="learning-controls-header">
          <h4>Learning Session Controls</h4>
        </div>
        <div className="learning-controls-content">
          <div className="learning-input-group">
            <label htmlFor="max-cases">Max Cases (optional):</label>
            <input
              id="max-cases"
              type="number"
              min="1"
              placeholder="All cases"
              value={maxCases}
              onChange={(e) => setMaxCases(e.target.value)}
              disabled={isSessionRunning || isStarting}
              className="learning-input"
            />
          </div>
          <div className="learning-input-group">
            <label htmlFor="continuous-mode" style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer' }}>
              <input
                id="continuous-mode"
                type="checkbox"
                checked={continuousMode}
                onChange={(e) => setContinuousMode(e.target.checked)}
                disabled={isSessionRunning || isStarting}
                style={{ cursor: 'pointer' }}
              />
              <span>🔄 Continuous Learning Loop (runs until stopped)</span>
            </label>
            {continuousMode && (
              <p style={{ fontSize: '0.85em', color: '#666', marginTop: '4px', marginLeft: '24px' }}>
                The system will continuously learn from available cases, getting better over time.
                {maxCases && ` Batch size: ${maxCases} cases.`}
              </p>
            )}
          </div>
          <div className="learning-buttons">
            {!isSessionRunning ? (
              <button
                className="learning-button learning-button-start"
                onClick={handleStartSession}
                disabled={isStarting || isStopping}
              >
                {isStarting ? 'Starting...' : '▶ Start Learning Session'}
              </button>
            ) : (
              <button
                className="learning-button learning-button-stop"
                onClick={handleStopSession}
                disabled={isStopping || isStarting}
              >
                {isStopping ? 'Stopping...' : '⏹ Stop Learning Session'}
              </button>
            )}
          </div>
          {isSessionRunning && sessionStatus.session?.started_at && (
            <div className="learning-session-info">
              <p>Session started: {new Date(sessionStatus.session.started_at).toLocaleString()}</p>
              {sessionStatus.session.continuous ? (
                <p>🔄 <strong>Continuous Learning Mode</strong> - Running until stopped</p>
              ) : sessionStatus.session.max_cases ? (
                <p>Processing up to {sessionStatus.session.max_cases.toLocaleString()} cases</p>
              ) : null}
              {sessionStatus.continuous_learning && (
                <div style={{ marginTop: '8px', padding: '8px', background: '#f0f0f0', borderRadius: '4px' }}>
                  <p><strong>Continuous Learning Stats:</strong></p>
                  <p>Total Processed: {sessionStatus.continuous_learning.total_processed || 0}</p>
                  <p>Correct: {sessionStatus.continuous_learning.total_correct || 0}</p>
                  <p>Incorrect: {sessionStatus.continuous_learning.total_incorrect || 0}</p>
                  {sessionStatus.continuous_learning.total_processed > 0 && (
                    <p>Accuracy: {((sessionStatus.continuous_learning.total_correct / sessionStatus.continuous_learning.total_processed) * 100).toFixed(1)}%</p>
                  )}
                  <p>Patterns Detected: {sessionStatus.continuous_learning.patterns_detected || 0}</p>
                </div>
              )}
            </div>
          )}

          {/* Progress Bar */}
          {stats.progress && stats.progress.progress_percent !== undefined && (
            <div className="learning-progress-section">
              <div className="learning-progress-header">
                <span>Processing Progress</span>
                <span className="learning-progress-percent">
                  {stats.progress.progress_percent}%
                </span>
              </div>
              <div className="learning-progress-bar-container">
                <div 
                  className="learning-progress-bar"
                  style={{ width: `${Math.min(100, Math.max(0, stats.progress.progress_percent))}%` }}
                >
                  <div className="learning-progress-bar-fill"></div>
                </div>
              </div>
              <div className="learning-progress-details">
                <span>
                  {stats.progress.total_attempted || 0} / {stats.progress.total_to_process || 0} cases
                </span>
                <span className="learning-progress-stats">
                  {stats.progress.total_processed || 0} processed • {stats.progress.total_failed || 0} failed
                </span>
              </div>
              {stats.progress.current_batch && (
                <div className="learning-progress-batch">
                  Batch {stats.progress.current_batch}: {stats.progress.batch_processed || 0} processed, {stats.progress.batch_failed || 0} failed
                </div>
              )}
            </div>
          )}

          {/* Log Output */}
          {logTail.length > 0 && (
            <div className="learning-log-output">
              <div className="learning-log-header">Recent Activity</div>
              <div className="learning-log-content">
                {logTail.map((line, idx) => (
                  <div key={idx} className="learning-log-line">{line}</div>
                ))}
              </div>
            </div>
          )}
        </div>
      </div>

      <div className="learning-stats-grid">
        <div className="learning-stat-card">
          <div className="stat-icon">📥</div>
          <div className="stat-content">
            <div className="stat-label">Cases Downloaded</div>
            <div className="stat-value">{stats.casesDownloaded.toLocaleString()}</div>
          </div>
        </div>

        <div className="learning-stat-card">
          <div className="stat-icon">⚙️</div>
          <div className="stat-content">
            <div className="stat-label">Cases Processed</div>
            <div className="stat-value">{stats.casesProcessed.toLocaleString()}</div>
            {stats.casesDownloaded > 0 && (
              <div className="stat-progress">
                {((stats.casesProcessed / stats.casesDownloaded) * 100).toFixed(1)}% complete
              </div>
            )}
          </div>
        </div>

        <div className="learning-stat-card">
          <div className="stat-icon">💾</div>
          <div className="stat-content">
            <div className="stat-label">Scenarios in Database</div>
            <div className="stat-value">{stats.scenariosInDatabase.toLocaleString()}</div>
            {stats.casesProcessed > 0 && (
              <div className="stat-progress">
                {processingRate}% success rate
              </div>
            )}
          </div>
        </div>
      </div>

      {Object.keys(stats.outcomeDistribution).length > 0 && (
        <div className="learning-outcomes">
          <h4>Outcome Distribution</h4>
          <div className="outcome-bars">
            {Object.entries(stats.outcomeDistribution)
              .sort((a, b) => b[1] - a[1])
              .map(([outcome, count]) => {
                const total = Object.values(stats.outcomeDistribution).reduce((a, b) => a + b, 0)
                const percentage = (count / total * 100).toFixed(1)
                return (
                  <div key={outcome} className="outcome-bar-item">
                    <div className="outcome-label">
                      <span>{outcome}</span>
                      <span className="outcome-count">{count} ({percentage}%)</span>
                    </div>
                    <div className="outcome-bar-container">
                      <div 
                        className="outcome-bar" 
                        style={{ width: `${percentage}%` }}
                      />
                    </div>
                  </div>
                )
              })}
          </div>
        </div>
      )}

      <div className="learning-footer">
        <div className="last-update">
          Last updated: {stats.lastUpdate}
        </div>
        {stats.isProcessing && (
          <div className="processing-indicator">
            <span className="pulse-dot"></span>
            Processing cases...
          </div>
        )}
      </div>
    </div>
  )
}

export default LearningDashboard

