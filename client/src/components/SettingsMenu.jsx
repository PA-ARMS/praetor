import React, { useState, useRef, useEffect } from 'react'
import { useAuth } from '../contexts/AuthContext'
import VoiceSettings from './VoiceSettings'
import './SettingsMenu.css'

function SettingsMenu() {
  const { user, logout } = useAuth()
  const [isOpen, setIsOpen] = useState(false)
  const menuRef = useRef(null)

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

  const isAdmin = user?.role === 'admin' || user?.role === 'attorney_partner'

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
              <div className="settings-section-title">Voice Settings</div>
              <VoiceSettings />
            </div>

            {isAdmin && (
              <div className="settings-section">
                <div className="settings-section-title">System Administration</div>
                <div className="settings-admin-options">
                  <p className="settings-admin-note">
                    System administration features are available through the control panel.
                  </p>
                  <p className="settings-admin-note">
                    Use the desktop shortcut or run START_CONTROL_PANEL.bat
                  </p>
                </div>
              </div>
            )}

            <div className="settings-section">
              <div className="settings-section-title">AI Learning Status</div>
              <button
                className="learning-dashboard-button"
                onClick={() => {
                  const url = window.location.origin + '/learning-dashboard.html'
                  window.open(url, '_blank', 'width=1200,height=800,resizable=yes,scrollbars=yes')
                }}
              >
                🧠 Open Learning Dashboard
              </button>
              <p className="settings-admin-note" style={{ marginTop: '0.5rem', fontSize: '0.8rem' }}>
                Opens in a new window for full-screen monitoring
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
    </div>
  )
}

export default SettingsMenu

