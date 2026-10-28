import React, { useState, useEffect } from 'react'
import axios from 'axios'
import { useAuth } from '../contexts/AuthContext'
import './Login.css'

import { API_BASE } from '../apiConfig.js'

function Login() {
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [mounted, setMounted] = useState(false)
  const [systemStatus, setSystemStatus] = useState('checking')
  const [showForgotPassword, setShowForgotPassword] = useState(false)
  const [forgotUsernameOrEmail, setForgotUsernameOrEmail] = useState('')
  const [forgotResult, setForgotResult] = useState(null)
  const [forgotLoading, setForgotLoading] = useState(false)
  const [resetToken, setResetToken] = useState(() => {
    const params = new URLSearchParams(window.location.search)
    return params.get('token') || ''
  })
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [resetError, setResetError] = useState('')
  const [resetSuccess, setResetSuccess] = useState(false)
  const [resetLoading, setResetLoading] = useState(false)
  const [showSignUp, setShowSignUp] = useState(false)
  const [signupFullName, setSignupFullName] = useState('')
  const [signupUsername, setSignupUsername] = useState('')
  const [signupEmail, setSignupEmail] = useState('')
  const [signupPassword, setSignupPassword] = useState('')
  const [signupConfirmPassword, setSignupConfirmPassword] = useState('')
  const [signupError, setSignupError] = useState('')
  const [signupSuccess, setSignupSuccess] = useState(false)
  const [signupLoading, setSignupLoading] = useState(false)
  const { login } = useAuth()

  useEffect(() => {
    setTimeout(() => setMounted(true), 100)
  }, [])

  useEffect(() => {
    let cancelled = false
    const check = async () => {
      try {
        const res = await axios.get(`${API_BASE}/api/health`, { timeout: 5000 })
        if (!cancelled && res.data?.status === 'healthy') setSystemStatus('online')
        else if (!cancelled) setSystemStatus('offline')
      } catch {
        if (!cancelled) setSystemStatus('offline')
      }
    }
    check()
    const interval = setInterval(check, 30000)
    return () => { cancelled = true; clearInterval(interval) }
  }, [])

  useEffect(() => {
    if (!resetSuccess) return
    const t = setTimeout(() => setResetSuccess(false), 5000)
    return () => clearTimeout(t)
  }, [resetSuccess])

  const handleSubmit = async (e) => {
    e.preventDefault()
    setError('')
    setLoading(true)
    const result = await login(username, password)
    if (!result.success) setError(result.error)
    setLoading(false)
  }

  const handleForgotSubmit = async (e) => {
    e.preventDefault()
    setForgotResult(null)
    setForgotLoading(true)
    try {
      const res = await axios.post(`${API_BASE}/api/auth/request-password-reset`, {
        username_or_email: forgotUsernameOrEmail.trim()
      })
      setForgotResult(res.data)
    } catch (err) {
      setForgotResult({ message: err.response?.data?.detail || 'Request failed' })
    }
    setForgotLoading(false)
  }

  const handleResetSubmit = async (e) => {
    e.preventDefault()
    setResetError('')
    if (newPassword.length < 12) {
      setResetError('Password must be at least 12 characters')
      return
    }
    if (newPassword !== confirmPassword) {
      setResetError('Passwords do not match')
      return
    }
    setResetLoading(true)
    try {
      await axios.post(`${API_BASE}/api/auth/reset-password`, {
        token: resetToken,
        new_password: newPassword
      })
      setResetSuccess(true)
      window.history.replaceState({}, '', window.location.pathname)
      setResetToken('')
      setNewPassword('')
      setConfirmPassword('')
    } catch (err) {
      setResetError(err.response?.data?.detail || 'Reset failed')
    }
    setResetLoading(false)
  }

  const handleSignupSubmit = async (e) => {
    e.preventDefault()
    setSignupError('')
    if (signupPassword.length < 12) {
      setSignupError('Password must be at least 12 characters')
      return
    }
    if (signupPassword !== signupConfirmPassword) {
      setSignupError('Passwords do not match')
      return
    }
    setSignupLoading(true)
    try {
      await axios.post(`${API_BASE}/api/auth/signup`, {
        full_name: signupFullName.trim(),
        username: signupUsername.trim(),
        email: signupEmail.trim(),
        password: signupPassword
      })
      setSignupSuccess(true)
      // Auto sign in after a short delay
      setTimeout(async () => {
        const result = await login(signupUsername.trim(), signupPassword)
        if (result.success) {
          setShowSignUp(false)
          setSignupFullName('')
          setSignupUsername('')
          setSignupEmail('')
          setSignupPassword('')
          setSignupConfirmPassword('')
          setSignupSuccess(false)
        } else {
          setSignupSuccess(false)
          setSignupError('Account created. Please sign in with your username and password.')
        }
      }, 1500)
    } catch (err) {
      setSignupError(err.response?.data?.detail || 'Account creation failed')
    }
    setSignupLoading(false)
  }

  if (resetToken) {
    return (
      <div className="login-container">
        <div className="login-bg-shapes">
          <div className="shape shape-1"></div>
          <div className="shape shape-2"></div>
          <div className="shape shape-3"></div>
        </div>
        <div className={`login-box ${mounted ? 'mounted' : ''}`}>
          <div className="login-brand">
            <h1>Set new password</h1>
          </div>
          {resetSuccess ? (
            <p className="login-success-message">Password reset successfully. You can now sign in below.</p>
          ) : (
            <form onSubmit={handleResetSubmit} className="login-form">
              {resetError && <div className="error-message">{resetError}</div>}
              <div className="form-group">
                <label>New password</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  placeholder="At least 12 characters"
                  disabled={resetLoading}
                  minLength={12}
                />
              </div>
              <div className="form-group">
                <label>Confirm password</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  placeholder="Confirm new password"
                  disabled={resetLoading}
                />
              </div>
              <button type="submit" className="login-button" disabled={resetLoading || !newPassword || !confirmPassword}>
                {resetLoading ? 'Resetting...' : 'Reset password'}
              </button>
            </form>
          )}
        </div>
      </div>
    )
  }

  return (
    <div className="login-container">
      {resetSuccess && (
        <div className="login-success-banner">
          Password reset successfully. You can now sign in.
        </div>
      )}
      {/* Animated background elements */}
      <div className="login-bg-shapes">
        <div className="shape shape-1"></div>
        <div className="shape shape-2"></div>
        <div className="shape shape-3"></div>
      </div>
      
      <div className={`login-box ${mounted ? 'mounted' : ''}`}>
        {/* Logo/Brand Section */}
        <div className="login-brand">
          <div className="brand-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5">
              <path d="M12 2L2 7l10 5 10-5-10-5z"/>
              <path d="M2 17l10 5 10-5"/>
              <path d="M2 12l10 5 10-5"/>
            </svg>
          </div>
          <h1>P.R.A.E.T.O.R.</h1>
          <div className="brand-tagline">
            <span className="tagline-line"></span>
            <span className="tagline-text">SI VIS PACEM, PARA BELLUM</span>
            <span className="tagline-line"></span>
          </div>
        </div>
        
        <form onSubmit={handleSubmit} className="login-form">
          {error && (
            <div className="error-message">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
                <circle cx="12" cy="12" r="10"/>
                <path d="M12 8v4m0 4h.01"/>
              </svg>
              {error}
            </div>
          )}
          
          <div className="form-group">
            <label htmlFor="username">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
              </svg>
              Username
            </label>
            <input
              id="username"
              type="text"
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              required
              disabled={loading}
              autoFocus
              placeholder="Enter your username"
            />
          </div>
          
          <div className="form-group">
            <label htmlFor="password">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="16" height="16">
                <rect x="3" y="11" width="18" height="11" rx="2" ry="2"/>
                <path d="M7 11V7a5 5 0 0110 0v4"/>
              </svg>
              Password
            </label>
            <input
              id="password"
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              disabled={loading}
              placeholder="Enter your password"
            />
          </div>
          
          <button type="submit" disabled={loading || !username || !password} className="login-button">
            {loading ? (
              <>
                <span className="btn-spinner"></span>
                Authenticating...
              </>
            ) : (
              <>
                <span>Sign In</span>
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="18" height="18">
                  <path d="M5 12h14M12 5l7 7-7 7"/>
                </svg>
              </>
            )}
          </button>

          <button
            type="button"
            className="login-forgot-link"
            onClick={() => setShowForgotPassword(true)}
          >
            Forgot password?
          </button>

          <button
            type="button"
            className="login-create-account-link"
            onClick={() => {
              setShowSignUp(true)
              setSignupError('')
              setSignupSuccess(false)
            }}
          >
            Create account
          </button>

          {showSignUp && (
            <div className="login-forgot-overlay" onClick={() => !signupLoading && setShowSignUp(false)}>
              <div className="login-signup-box" onClick={e => e.stopPropagation()}>
                <h3>Create account</h3>
                <p className="login-signup-hint">
                  Create the first account to get started. After that, new accounts are created by your administrator.
                </p>
                {signupSuccess ? (
                  <p className="login-signup-success">
                    Account created successfully. Signing you in...
                  </p>
                ) : (
                  <form onSubmit={handleSignupSubmit} className="login-signup-form">
                    {signupError && <div className="login-forgot-result error">{signupError}</div>}
                    <div className="form-group">
                      <label>Full name</label>
                      <input
                        type="text"
                        value={signupFullName}
                        onChange={e => setSignupFullName(e.target.value)}
                        placeholder="Full name"
                        disabled={signupLoading}
                        required
                      />
                    </div>
                    <div className="form-group">
                      <label>Username</label>
                      <input
                        type="text"
                        value={signupUsername}
                        onChange={e => setSignupUsername(e.target.value)}
                        placeholder="Username (letters, numbers, underscores)"
                        disabled={signupLoading}
                        required
                        minLength={3}
                        maxLength={50}
                      />
                    </div>
                    <div className="form-group">
                      <label>Email</label>
                      <input
                        type="email"
                        value={signupEmail}
                        onChange={e => setSignupEmail(e.target.value)}
                        placeholder="Email address"
                        disabled={signupLoading}
                        required
                      />
                    </div>
                    <div className="form-group">
                      <label>Password</label>
                      <input
                        type="password"
                        value={signupPassword}
                        onChange={e => setSignupPassword(e.target.value)}
                        placeholder="At least 12 characters, mixed case, number, special character"
                        disabled={signupLoading}
                        required
                        minLength={12}
                      />
                    </div>
                    <div className="form-group">
                      <label>Confirm password</label>
                      <input
                        type="password"
                        value={signupConfirmPassword}
                        onChange={e => setSignupConfirmPassword(e.target.value)}
                        placeholder="Confirm password"
                        disabled={signupLoading}
                        required
                      />
                    </div>
                    <div className="login-forgot-actions">
                      <button
                        type="button"
                        className="btn-cancel"
                        onClick={() => {
                          setShowSignUp(false)
                          setSignupError('')
                          setSignupFullName('')
                          setSignupUsername('')
                          setSignupEmail('')
                          setSignupPassword('')
                          setSignupConfirmPassword('')
                        }}
                        disabled={signupLoading}
                      >
                        Cancel
                      </button>
                      <button
                        type="submit"
                        className="login-button"
                        disabled={signupLoading || !signupFullName.trim() || !signupUsername.trim() || !signupEmail.trim() || !signupPassword || !signupConfirmPassword}
                      >
                        {signupLoading ? 'Creating...' : 'Create account'}
                      </button>
                    </div>
                  </form>
                )}
              </div>
            </div>
          )}

          {showForgotPassword && (
            <div className="login-forgot-overlay">
              <div className="login-forgot-box">
                <h3>Reset password</h3>
                <p className="login-forgot-hint">Enter your username or email. A reset link will be generated.</p>
                {forgotResult && (
                  <div className={`login-forgot-result ${forgotResult.reset_url ? 'success' : 'error'}`}>
                    {forgotResult.message}
                    {forgotResult.reset_url && (
                      <button
                        type="button"
                        className="login-forgot-open-link"
                        onClick={() => {
                          window.location.href = forgotResult.reset_url
                        }}
                      >
                        Open reset page
                      </button>
                    )}
                  </div>
                )}
                <form onSubmit={handleForgotSubmit}>
                  <div className="form-group">
                    <input
                      type="text"
                      value={forgotUsernameOrEmail}
                      onChange={(e) => setForgotUsernameOrEmail(e.target.value)}
                      placeholder="Username or email"
                      disabled={forgotLoading}
                    />
                  </div>
                  <div className="login-forgot-actions">
                    <button type="button" className="btn-cancel" onClick={() => { setShowForgotPassword(false); setForgotResult(null) }}>
                      Cancel
                    </button>
                    <button type="submit" className="login-button" disabled={forgotLoading || !forgotUsernameOrEmail.trim()}>
                      {forgotLoading ? 'Sending...' : 'Get reset link'}
                    </button>
                  </div>
                </form>
              </div>
            </div>
          )}
        </form>
        
        <div className="login-footer">
          <div className="security-badge">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" width="14" height="14">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>
            </svg>
            <span>Defense Command Portal</span>
          </div>
          <p className="footer-note">Authorized Personnel Only // Class 1 Data</p>
          <div className="powered-by">
            <span>System Status:</span>
            <span
              className={`login-system-status login-status-${systemStatus}`}
              title={systemStatus === 'online' ? 'Backend is reachable and healthy' : systemStatus === 'offline' ? 'Backend unreachable' : 'Checking...'}
            >
              {systemStatus === 'online' ? 'LIVE' : systemStatus === 'offline' ? 'OFFLINE' : 'Checking...'}
            </span>
          </div>
          <a href="/compliance.html" target="_blank" rel="noopener noreferrer" className="login-compliance-link">
            Privacy &amp; Compliance
          </a>
        </div>
      </div>
    </div>
  )
}

export default Login

