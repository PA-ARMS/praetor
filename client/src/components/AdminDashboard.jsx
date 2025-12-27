import React, { useState, useEffect, useCallback } from 'react'
import { useAuth } from '../contexts/AuthContext'
import axios from 'axios'
import './AdminDashboard.css'

const API_BASE = import.meta.env.VITE_API_URL || ''

function AdminDashboard() {
  const { user, register } = useAuth()
  const [users, setUsers] = useState([])
  const [loading, setLoading] = useState(true)
  const [systemStatus, setSystemStatus] = useState({
    backend: 'checking',
    database: 'checking',
    aiEngine: 'checking',
    scenarioDb: 'checking',
    lastRestart: null,
    uptime: 0
  })
  const [showCreateModal, setShowCreateModal] = useState(false)
  const [showEditModal, setShowEditModal] = useState(false)
  const [selectedUser, setSelectedUser] = useState(null)
  const [actionLoading, setActionLoading] = useState(false)
  const [notification, setNotification] = useState(null)
  const [stats, setStats] = useState({
    totalUsers: 0,
    activeToday: 0,
    totalQueries: 0,
    documentsUploaded: 0
  })

  // Show notification
  const showNotification = (message, type = 'success') => {
    setNotification({ message, type })
    setTimeout(() => setNotification(null), 4000)
  }

  // Fetch users
  const fetchUsers = useCallback(async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/auth/users`)
      setUsers(response.data.users || [])
    } catch (error) {
      console.error('Failed to fetch users:', error)
      showNotification('Failed to load users', 'error')
    }
  }, [])

  // Check system status
  const checkSystemStatus = useCallback(async () => {
    const status = { ...systemStatus }
    
    // Check backend
    try {
      const start = Date.now()
      await axios.get(`${API_BASE}/api/health`)
      status.backend = 'online'
      status.responseTime = Date.now() - start
    } catch {
      status.backend = 'offline'
    }

    // Check database
    try {
      await axios.get(`${API_BASE}/api/auth/users`)
      status.database = 'online'
    } catch {
      status.database = 'error'
    }

    // Check AI engine (Ollama)
    try {
      const response = await axios.get(`${API_BASE}/api/chat/models`)
      status.aiEngine = response.data?.models?.length > 0 ? 'online' : 'limited'
    } catch {
      status.aiEngine = 'checking'
    }

    // Check scenario database
    try {
      await axios.get(`${API_BASE}/api/scenarios/stats`)
      status.scenarioDb = 'online'
    } catch {
      status.scenarioDb = 'disabled'
    }

    // Get uptime
    try {
      const response = await axios.get(`${API_BASE}/api/system/status`)
      status.uptime = response.data?.uptime || 0
      status.lastRestart = response.data?.started_at
    } catch {
      // System status endpoint may not exist
    }

    setSystemStatus(status)
  }, [])

  // Fetch stats
  const fetchStats = useCallback(async () => {
    try {
      const [usersRes, statsRes] = await Promise.all([
        axios.get(`${API_BASE}/api/auth/users`),
        axios.get(`${API_BASE}/api/system/stats`).catch(() => ({ data: {} }))
      ])
      
      setStats({
        totalUsers: usersRes.data.users?.length || 0,
        activeToday: statsRes.data?.active_today || 0,
        totalQueries: statsRes.data?.total_queries || 0,
        documentsUploaded: statsRes.data?.documents_uploaded || 0
      })
    } catch {
      // Stats endpoint may not exist
    }
  }, [])

  // Initial load
  useEffect(() => {
    const load = async () => {
      setLoading(true)
      await Promise.all([fetchUsers(), checkSystemStatus(), fetchStats()])
      setLoading(false)
    }
    load()

    // Refresh status every 30 seconds
    const interval = setInterval(checkSystemStatus, 30000)
    return () => clearInterval(interval)
  }, [fetchUsers, checkSystemStatus, fetchStats])

  // Create user
  const handleCreateUser = async (userData) => {
    setActionLoading(true)
    try {
      const result = await register(userData)
      if (result.success) {
        showNotification(`User "${userData.username}" created successfully`)
        setShowCreateModal(false)
        fetchUsers()
        fetchStats()
      } else {
        showNotification(result.error, 'error')
      }
    } catch (error) {
      showNotification(error.response?.data?.detail || 'Failed to create user', 'error')
    }
    setActionLoading(false)
  }

  // Toggle user active status
  const handleToggleUser = async (userId, currentStatus) => {
    try {
      await axios.patch(`${API_BASE}/api/auth/users/${userId}`, {
        is_active: !currentStatus
      })
      showNotification(`User ${currentStatus ? 'deactivated' : 'activated'} successfully`)
      fetchUsers()
    } catch (error) {
      showNotification('Failed to update user status', 'error')
    }
  }

  // Reset password
  const handleResetPassword = async (userId, newPassword) => {
    try {
      await axios.patch(`${API_BASE}/api/auth/users/${userId}/password`, {
        password: newPassword
      })
      showNotification('Password reset successfully')
      setShowEditModal(false)
    } catch (error) {
      showNotification('Failed to reset password', 'error')
    }
  }

  // Format uptime
  const formatUptime = (seconds) => {
    if (!seconds) return 'Unknown'
    const days = Math.floor(seconds / 86400)
    const hours = Math.floor((seconds % 86400) / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    if (days > 0) return `${days}d ${hours}h ${mins}m`
    if (hours > 0) return `${hours}h ${mins}m`
    return `${mins}m`
  }

  // Get role badge class
  const getRoleBadgeClass = (role) => {
    const classes = {
      admin: 'role-badge-admin',
      attorney_partner: 'role-badge-partner',
      attorney: 'role-badge-attorney',
      paralegal: 'role-badge-paralegal'
    }
    return classes[role] || 'role-badge-default'
  }

  // Format role display
  const formatRole = (role) => {
    const names = {
      admin: 'Administrator',
      attorney_partner: 'Partner',
      attorney: 'Attorney',
      paralegal: 'Paralegal'
    }
    return names[role] || role
  }

  if (loading) {
    return (
      <div className="admin-loading">
        <div className="loading-spinner"></div>
        <p>Loading Dashboard...</p>
      </div>
    )
  }

  return (
    <div className="admin-dashboard">
      {/* Notification */}
      {notification && (
        <div className={`admin-notification ${notification.type}`}>
          <span className="notification-icon">
            {notification.type === 'success' ? '✓' : '⚠'}
          </span>
          {notification.message}
        </div>
      )}

      {/* Header */}
      <div className="admin-header">
        <div className="admin-title-section">
          <h2>System Administration</h2>
          <p className="admin-subtitle">Manage users, monitor system health, and configure settings</p>
        </div>
        <div className="admin-quick-actions">
          <button className="btn-primary" onClick={() => setShowCreateModal(true)}>
            <span className="btn-icon">+</span>
            Add User
          </button>
          <button className="btn-secondary" onClick={checkSystemStatus}>
            <span className="btn-icon">↻</span>
            Refresh Status
          </button>
        </div>
      </div>

      {/* System Status Cards */}
      <div className="status-grid">
        <div className={`status-card ${systemStatus.backend}`}>
          <div className="status-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <rect x="2" y="3" width="20" height="14" rx="2"/>
              <path d="M8 21h8m-4-4v4"/>
            </svg>
          </div>
          <div className="status-info">
            <span className="status-label">Backend Server</span>
            <span className={`status-value ${systemStatus.backend}`}>
              {systemStatus.backend === 'online' ? 'Online' : 
               systemStatus.backend === 'checking' ? 'Checking...' : 'Offline'}
            </span>
            {systemStatus.responseTime && (
              <span className="status-meta">{systemStatus.responseTime}ms response</span>
            )}
          </div>
          <div className={`status-indicator ${systemStatus.backend}`}></div>
        </div>

        <div className={`status-card ${systemStatus.database}`}>
          <div className="status-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <ellipse cx="12" cy="5" rx="9" ry="3"/>
              <path d="M21 12c0 1.66-4 3-9 3s-9-1.34-9-3"/>
              <path d="M3 5v14c0 1.66 4 3 9 3s9-1.34 9-3V5"/>
            </svg>
          </div>
          <div className="status-info">
            <span className="status-label">Database</span>
            <span className={`status-value ${systemStatus.database}`}>
              {systemStatus.database === 'online' ? 'Connected' : 
               systemStatus.database === 'checking' ? 'Checking...' : 'Error'}
            </span>
          </div>
          <div className={`status-indicator ${systemStatus.database}`}></div>
        </div>

        <div className={`status-card ${systemStatus.aiEngine}`}>
          <div className="status-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 2a2 2 0 012 2c0 .74-.4 1.39-1 1.73V7h1a7 7 0 017 7h1a1 1 0 011 1v3a1 1 0 01-1 1h-1v1a2 2 0 01-2 2H5a2 2 0 01-2-2v-1H2a1 1 0 01-1-1v-3a1 1 0 011-1h1a7 7 0 017-7h1V5.73c-.6-.34-1-.99-1-1.73a2 2 0 012-2z"/>
              <circle cx="7.5" cy="14.5" r="1.5"/>
              <circle cx="16.5" cy="14.5" r="1.5"/>
            </svg>
          </div>
          <div className="status-info">
            <span className="status-label">AI Engine</span>
            <span className={`status-value ${systemStatus.aiEngine}`}>
              {systemStatus.aiEngine === 'online' ? 'Ready' : 
               systemStatus.aiEngine === 'limited' ? 'Limited' :
               systemStatus.aiEngine === 'checking' ? 'Checking...' : 'Offline'}
            </span>
          </div>
          <div className={`status-indicator ${systemStatus.aiEngine}`}></div>
        </div>

        <div className={`status-card ${systemStatus.scenarioDb}`}>
          <div className="status-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
              <path d="M14 2v6h6M16 13H8M16 17H8M10 9H8"/>
            </svg>
          </div>
          <div className="status-info">
            <span className="status-label">Scenario Database</span>
            <span className={`status-value ${systemStatus.scenarioDb}`}>
              {systemStatus.scenarioDb === 'online' ? 'Active' : 
               systemStatus.scenarioDb === 'checking' ? 'Checking...' : 'Disabled'}
            </span>
          </div>
          <div className={`status-indicator ${systemStatus.scenarioDb}`}></div>
        </div>
      </div>

      {/* Stats Overview */}
      <div className="stats-section">
        <div className="stat-card">
          <div className="stat-value">{stats.totalUsers}</div>
          <div className="stat-label">Total Users</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{formatUptime(systemStatus.uptime)}</div>
          <div className="stat-label">System Uptime</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.totalQueries.toLocaleString()}</div>
          <div className="stat-label">Legal Queries</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{stats.documentsUploaded}</div>
          <div className="stat-label">Documents</div>
        </div>
      </div>

      {/* Users Table */}
      <div className="users-section">
        <div className="section-header">
          <h3>User Management</h3>
          <span className="user-count">{users.length} users</span>
        </div>
        
        <div className="users-table-container">
          <table className="users-table">
            <thead>
              <tr>
                <th>User</th>
                <th>Role</th>
                <th>Email</th>
                <th>Status</th>
                <th>Actions</th>
              </tr>
            </thead>
            <tbody>
              {users.map(u => (
                <tr key={u.id} className={!u.is_active ? 'inactive-row' : ''}>
                  <td>
                    <div className="user-cell">
                      <div className="user-avatar">
                        {u.full_name?.charAt(0)?.toUpperCase() || u.username?.charAt(0)?.toUpperCase()}
                      </div>
                      <div className="user-details">
                        <span className="user-name">{u.full_name}</span>
                        <span className="user-username">@{u.username}</span>
                      </div>
                    </div>
                  </td>
                  <td>
                    <span className={`role-badge ${getRoleBadgeClass(u.role)}`}>
                      {formatRole(u.role)}
                    </span>
                  </td>
                  <td className="email-cell">{u.email}</td>
                  <td>
                    <span className={`status-badge ${u.is_active ? 'active' : 'inactive'}`}>
                      {u.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td>
                    <div className="action-buttons">
                      <button 
                        className="btn-icon-only edit"
                        onClick={() => {
                          setSelectedUser(u)
                          setShowEditModal(true)
                        }}
                        title="Edit User"
                      >
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <path d="M11 4H4a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2v-7"/>
                          <path d="M18.5 2.5a2.121 2.121 0 013 3L12 15l-4 1 1-4 9.5-9.5z"/>
                        </svg>
                      </button>
                      {u.id !== user?.id && (
                        <button 
                          className={`btn-icon-only ${u.is_active ? 'deactivate' : 'activate'}`}
                          onClick={() => handleToggleUser(u.id, u.is_active)}
                          title={u.is_active ? 'Deactivate User' : 'Activate User'}
                        >
                          {u.is_active ? (
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <circle cx="12" cy="12" r="10"/>
                              <path d="M4.93 4.93l14.14 14.14"/>
                            </svg>
                          ) : (
                            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                              <path d="M22 11.08V12a10 10 0 11-5.93-9.14"/>
                              <path d="M22 4L12 14.01l-3-3"/>
                            </svg>
                          )}
                        </button>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create User Modal */}
      {showCreateModal && (
        <CreateUserModal
          onClose={() => setShowCreateModal(false)}
          onSubmit={handleCreateUser}
          loading={actionLoading}
          users={users}
        />
      )}

      {/* Edit User Modal */}
      {showEditModal && selectedUser && (
        <EditUserModal
          user={selectedUser}
          onClose={() => {
            setShowEditModal(false)
            setSelectedUser(null)
          }}
          onResetPassword={handleResetPassword}
          loading={actionLoading}
        />
      )}
    </div>
  )
}

// Create User Modal Component
function CreateUserModal({ onClose, onSubmit, loading, users }) {
  const [formData, setFormData] = useState({
    username: '',
    email: '',
    password: '',
    confirmPassword: '',
    full_name: '',
    role: 'paralegal',
    supervising_attorney_id: null
  })
  const [errors, setErrors] = useState({})

  const attorneys = users.filter(u => 
    u.role === 'attorney' || u.role === 'attorney_partner'
  )

  const validate = () => {
    const newErrors = {}
    if (!formData.username.trim()) newErrors.username = 'Username is required'
    if (formData.username.length < 3) newErrors.username = 'Username must be at least 3 characters'
    if (!formData.email.trim()) newErrors.email = 'Email is required'
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) newErrors.email = 'Invalid email format'
    if (!formData.password) newErrors.password = 'Password is required'
    if (formData.password.length < 8) newErrors.password = 'Password must be at least 8 characters'
    if (formData.password !== formData.confirmPassword) newErrors.confirmPassword = 'Passwords do not match'
    if (!formData.full_name.trim()) newErrors.full_name = 'Full name is required'
    if (formData.role === 'paralegal' && !formData.supervising_attorney_id && attorneys.length > 0) {
      newErrors.supervising_attorney_id = 'Supervising attorney is required for paralegals'
    }
    setErrors(newErrors)
    return Object.keys(newErrors).length === 0
  }

  const handleSubmit = (e) => {
    e.preventDefault()
    if (validate()) {
      const { confirmPassword, ...submitData } = formData
      onSubmit(submitData)
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Create New User</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        
        <form onSubmit={handleSubmit} className="user-form">
          <div className="form-row">
            <div className="form-group">
              <label>Username *</label>
              <input
                type="text"
                value={formData.username}
                onChange={e => setFormData({...formData, username: e.target.value.toLowerCase().replace(/\s/g, '')})}
                placeholder="johndoe"
                className={errors.username ? 'error' : ''}
              />
              {errors.username && <span className="error-text">{errors.username}</span>}
            </div>
            <div className="form-group">
              <label>Full Name *</label>
              <input
                type="text"
                value={formData.full_name}
                onChange={e => setFormData({...formData, full_name: e.target.value})}
                placeholder="John Doe"
                className={errors.full_name ? 'error' : ''}
              />
              {errors.full_name && <span className="error-text">{errors.full_name}</span>}
            </div>
          </div>

          <div className="form-group">
            <label>Email Address *</label>
            <input
              type="email"
              value={formData.email}
              onChange={e => setFormData({...formData, email: e.target.value})}
              placeholder="john.doe@lawfirm.com"
              className={errors.email ? 'error' : ''}
            />
            {errors.email && <span className="error-text">{errors.email}</span>}
          </div>

          <div className="form-row">
            <div className="form-group">
              <label>Password *</label>
              <input
                type="password"
                value={formData.password}
                onChange={e => setFormData({...formData, password: e.target.value})}
                placeholder="••••••••"
                className={errors.password ? 'error' : ''}
              />
              {errors.password && <span className="error-text">{errors.password}</span>}
            </div>
            <div className="form-group">
              <label>Confirm Password *</label>
              <input
                type="password"
                value={formData.confirmPassword}
                onChange={e => setFormData({...formData, confirmPassword: e.target.value})}
                placeholder="••••••••"
                className={errors.confirmPassword ? 'error' : ''}
              />
              {errors.confirmPassword && <span className="error-text">{errors.confirmPassword}</span>}
            </div>
          </div>

          <div className="form-group">
            <label>Role *</label>
            <select
              value={formData.role}
              onChange={e => setFormData({...formData, role: e.target.value})}
            >
              <option value="paralegal">Paralegal</option>
              <option value="attorney">Attorney</option>
              <option value="attorney_partner">Attorney Partner</option>
              <option value="admin">Administrator</option>
            </select>
          </div>

          {formData.role === 'paralegal' && attorneys.length > 0 && (
            <div className="form-group">
              <label>Supervising Attorney *</label>
              <select
                value={formData.supervising_attorney_id || ''}
                onChange={e => setFormData({...formData, supervising_attorney_id: e.target.value ? parseInt(e.target.value) : null})}
                className={errors.supervising_attorney_id ? 'error' : ''}
              >
                <option value="">Select an attorney...</option>
                {attorneys.map(a => (
                  <option key={a.id} value={a.id}>{a.full_name}</option>
                ))}
              </select>
              {errors.supervising_attorney_id && <span className="error-text">{errors.supervising_attorney_id}</span>}
            </div>
          )}

          <div className="modal-actions">
            <button type="button" className="btn-cancel" onClick={onClose}>Cancel</button>
            <button type="submit" className="btn-submit" disabled={loading}>
              {loading ? 'Creating...' : 'Create User'}
            </button>
          </div>
        </form>
      </div>
    </div>
  )
}

// Edit User Modal Component
function EditUserModal({ user, onClose, onResetPassword, loading }) {
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [error, setError] = useState('')

  const handleResetPassword = () => {
    if (newPassword.length < 8) {
      setError('Password must be at least 8 characters')
      return
    }
    if (newPassword !== confirmPassword) {
      setError('Passwords do not match')
      return
    }
    onResetPassword(user.id, newPassword)
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={e => e.stopPropagation()}>
        <div className="modal-header">
          <h3>Edit User: {user.full_name}</h3>
          <button className="modal-close" onClick={onClose}>×</button>
        </div>
        
        <div className="user-info-display">
          <div className="info-row">
            <span className="info-label">Username:</span>
            <span className="info-value">@{user.username}</span>
          </div>
          <div className="info-row">
            <span className="info-label">Email:</span>
            <span className="info-value">{user.email}</span>
          </div>
          <div className="info-row">
            <span className="info-label">Role:</span>
            <span className="info-value">{user.role}</span>
          </div>
        </div>

        <div className="password-reset-section">
          <h4>Reset Password</h4>
          {error && <div className="error-message">{error}</div>}
          <div className="form-group">
            <label>New Password</label>
            <input
              type="password"
              value={newPassword}
              onChange={e => {
                setNewPassword(e.target.value)
                setError('')
              }}
              placeholder="Enter new password"
            />
          </div>
          <div className="form-group">
            <label>Confirm New Password</label>
            <input
              type="password"
              value={confirmPassword}
              onChange={e => {
                setConfirmPassword(e.target.value)
                setError('')
              }}
              placeholder="Confirm new password"
            />
          </div>
          <button 
            className="btn-submit" 
            onClick={handleResetPassword}
            disabled={loading || !newPassword || !confirmPassword}
          >
            {loading ? 'Resetting...' : 'Reset Password'}
          </button>
        </div>

        <div className="modal-actions">
          <button className="btn-cancel" onClick={onClose}>Close</button>
        </div>
      </div>
    </div>
  )
}

export default AdminDashboard

