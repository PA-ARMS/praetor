import React, { createContext, useState, useEffect, useContext } from 'react'
import axios from 'axios'
import { API_BASE } from '../apiConfig.js'

const AuthContext = createContext()

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null)
  const [loading, setLoading] = useState(true)
  const [token, setToken] = useState(localStorage.getItem('token'))

  // Set up axios interceptor for auth token
  useEffect(() => {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`
      localStorage.setItem('token', token)
    } else {
      delete axios.defaults.headers.common['Authorization']
      localStorage.removeItem('token')
    }
  }, [token])

  // Load user on mount if token exists
  useEffect(() => {
    if (token) {
      loadUser()
    } else {
      setLoading(false)
    }
  }, [token])

  const loadUser = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/auth/me`)
      setUser(response.data)
    } catch (error) {
      console.error('Failed to load user:', error)
      setToken(null)
      setUser(null)
    } finally {
      setLoading(false)
    }
  }

  const login = async (username, password) => {
    try {
      console.log('[AUTH] Attempting login to:', `${API_BASE}/api/auth/login`);
      console.log('[AUTH] API_BASE value:', API_BASE);
      
      const response = await axios.post(`${API_BASE}/api/auth/login`, {
        username,
        password
      })
      
      console.log('[AUTH] Login successful:', response.data);
      setToken(response.data.access_token)
      setUser(response.data.user)
      return { success: true }
    } catch (error) {
      console.error('[AUTH] Login error:', error);
      console.error('[AUTH] Error response:', error.response?.data);
      console.error('[AUTH] Error status:', error.response?.status);
      console.error('[AUTH] Error message:', error.message);
      
      // Provide more helpful error messages
      let errorMessage = 'Login failed';
      if (error.code === 'ECONNREFUSED' || error.message.includes('Network Error')) {
        errorMessage = 'Cannot connect to server. Please ensure the backend is running on port 5001.';
      } else if (error.response?.data?.detail) {
        errorMessage = error.response.data.detail;
      } else if (error.response?.status === 401) {
        errorMessage = 'Incorrect username or password';
      }
      
      return {
        success: false,
        error: errorMessage
      }
    }
  }

  const logout = () => {
    setToken(null)
    setUser(null)
  }

  const register = async (userData) => {
    try {
      const response = await axios.post(`${API_BASE}/api/auth/register`, userData)
      return { success: true, user: response.data }
    } catch (error) {
      return {
        success: false,
        error: error.response?.data?.detail || 'Registration failed'
      }
    }
  }

  return (
    <AuthContext.Provider value={{
      user,
      token,
      loading,
      login,
      logout,
      register,
      isAuthenticated: !!token && !!user
    }}>
      {children}
    </AuthContext.Provider>
  )
}

export function useAuth() {
  const context = useContext(AuthContext)
  if (!context) {
    throw new Error('useAuth must be used within AuthProvider')
  }
  return context
}

