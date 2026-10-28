import React, { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import { useAuth } from '../contexts/AuthContext'
import './SettingsMenu.css'

import { API_BASE } from '../apiConfig.js'
import {
  VOICE_CHANGE_EVENT,
  getVoiceEnabled,
  setVoiceEnabled,
  stopSpeaking,
} from '../utils/praetorVoice.js'

function SettingsMenu() {
  const { user, logout } = useAuth()
  const [isOpen, setIsOpen] = useState(false)
  const [exporting, setExporting] = useState(false)
  const [showChangePassword, setShowChangePassword] = useState(false)
  const [changePasswordForm, setChangePasswordForm] = useState({
    current_password: '',
    new_password: '',
    confirm_password: ''
  })
  const [changePasswordError, setChangePasswordError] = useState(null)
  const [changePasswordSuccess, setChangePasswordSuccess] = useState(false)
  const [changingPassword, setChangingPassword] = useState(false)
  const menuRef = useRef(null)
  const [voiceOn, setVoiceOn] = useState(() => getVoiceEnabled())

  useEffect(() => {
    const sync = (e) => {
      const on = e?.detail?.on
      setVoiceOn(typeof on === 'boolean' ? on : getVoiceEnabled())
    }
    window.addEventListener(VOICE_CHANGE_EVENT, sync)
    return () => window.removeEventListener(VOICE_CHANGE_EVENT, sync)
  }, [])

  // Close menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (menuRef.current && !menuRef.current.contains(event.target)) {
        setIsOpen(false)
      }
    }

    if (isOpen) {
      document.addEventListener('mousedown', handleClickOutside)
    }

    return () => {
      document.removeEventListener('mousedown', handleClickOutside)
    }
  }, [isOpen])

  return (
    <div className="settings-menu-container" ref={menuRef}>
      <button 
        className="settings-menu-button"
        onClick={() => setIsOpen(!isOpen)}
        aria-label="Settings"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <circle cx="12" cy="12" r="3"/>
          <path d="M12 1v6m0 6v6M5.64 5.64l4.24 4.24m4.24 4.24l4.24 4.24M1 12h6m6 0h6M5.64 18.36l4.24-4.24m4.24-4.24l4.24-4.24"/>
        </svg>
      </button>

      {isOpen && (
        <div className="settings-menu-dropdown">
          <div className="settings-menu-header">
            <div className="settings-user-info">
              <div className="settings-user-name">{user?.full_name}</div>
              <div className="settings-user-role">{user?.role}</div>
            </div>
          </div>

          <div className="settings-menu-content">
            <div className="settings-section">
              <div className="settings-section-title">Account</div>
              <button
                type="button"
                className="settings-export-button"
                onClick={() => {
                  setShowChangePassword(true)
                  setChangePasswordForm({ current_password: '', new_password: '', confirm_password: '' })
                  setChangePasswordError(null)
                  setChangePasswordSuccess(false)
                }}
              >
                Change password
              </button>
            </div>

            <div className="settings-section">
              <div className="settings-section-title">Voice</div>
              <label className="settings-voice-toggle">
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
              <p className="settings-admin-note" style={{ marginTop: '0.5rem', fontSize: '0.8rem' }}>
                P.R.A.E.T.O.R. reads answers aloud. The voice is fixed — a Cortana-style US voice when the PC has one, otherwise a British butler if available.
              </p>
            </div>

            <div className="settings-section">
              <div className="settings-section-title">Data & Privacy</div>
              <button
                type="button"
                className="settings-export-button"
                disabled={exporting}
                onClick={async () => {
                  setExporting(true)
                  try {
                    const res = await axios.get(`${API_BASE}/api/auth/export-my-data`)
                    const blob = new Blob([JSON.stringify(res.data, null, 2)], { type: 'application/json' })
                    const url = URL.createObjectURL(blob)
                    const a = document.createElement('a')
                    a.href = url
                    a.download = `my-data-${new Date().toISOString().slice(0, 10)}.json`
                    a.click()
                    URL.revokeObjectURL(url)
                  } catch (err) {
                    alert(err.response?.data?.detail || 'Export failed')
                  }
                  setExporting(false)
                }}
              >
                {exporting ? 'Exporting...' : 'Export my data'}
              </button>
              <p className="settings-admin-note" style={{ marginTop: '0.5rem', fontSize: '0.8rem' }}>
                Download your profile and chat history (JSON)
              </p>
            </div>

            <div className="settings-menu-footer">
              <button className="settings-logout-button" onClick={logout}>
                Logout
              </button>
            </div>
          </div>
        </div>
      )}

      {showChangePassword && (
        <div className="settings-modal-overlay" onClick={() => setShowChangePassword(false)}>
          <div className="settings-modal" onClick={e => e.stopPropagation()}>
            <div className="settings-modal-header">
              <h3>Change Password</h3>
              <button type="button" className="settings-modal-close" onClick={() => setShowChangePassword(false)} aria-label="Close">&times;</button>
            </div>
            {changePasswordSuccess ? (
              <div className="settings-modal-body">
                <p className="settings-success-msg">Password changed successfully.</p>
                <button type="button" className="settings-export-button" onClick={() => setShowChangePassword(false)}>Close</button>
              </div>
            ) : (
              <form
                className="settings-modal-body"
                onSubmit={async (e) => {
                  e.preventDefault()
                  setChangePasswordError(null)
                  if (changePasswordForm.new_password !== changePasswordForm.confirm_password) {
                    setChangePasswordError('New passwords do not match')
                    return
                  }
                  if (changePasswordForm.new_password.length < 12) {
                    setChangePasswordError('New password must be at least 12 characters')
                    return
                  }
                  setChangingPassword(true)
                  try {
                    await axios.post(`${API_BASE}/api/auth/change-password`, {
                      current_password: changePasswordForm.current_password,
                      new_password: changePasswordForm.new_password
                    })
                    setChangePasswordSuccess(true)
                  } catch (err) {
                    setChangePasswordError(err.response?.data?.detail || 'Failed to change password')
                  } finally {
                    setChangingPassword(false)
                  }
                }}
              >
                <div className="settings-form-group">
                  <label>Current password</label>
                  <input
                    type="password"
                    value={changePasswordForm.current_password}
                    onChange={e => setChangePasswordForm(p => ({ ...p, current_password: e.target.value }))}
                    required
                    autoComplete="current-password"
                  />
                </div>
                <div className="settings-form-group">
                  <label>New password</label>
                  <input
                    type="password"
                    value={changePasswordForm.new_password}
                    onChange={e => setChangePasswordForm(p => ({ ...p, new_password: e.target.value }))}
                    required
                    minLength={12}
                    autoComplete="new-password"
                  />
                </div>
                <div className="settings-form-group">
                  <label>Confirm new password</label>
                  <input
                    type="password"
                    value={changePasswordForm.confirm_password}
                    onChange={e => setChangePasswordForm(p => ({ ...p, confirm_password: e.target.value }))}
                    required
                    minLength={12}
                    autoComplete="new-password"
                  />
                </div>
                {changePasswordError && <div className="settings-form-error">{changePasswordError}</div>}
                <div className="settings-modal-actions">
                  <button type="button" onClick={() => setShowChangePassword(false)} className="settings-btn-secondary">Cancel</button>
                  <button type="submit" disabled={changingPassword} className="settings-export-button">
                    {changingPassword ? 'Changing...' : 'Change password'}
                  </button>
                </div>
              </form>
            )}
          </div>
        </div>
      )}
    </div>
  )
}

export default SettingsMenu

