import React, { useState, useEffect } from 'react'
import axios from 'axios'
import './VoiceSettings.css'

const API_BASE = import.meta.env.VITE_API_URL || ''

function VoiceSettings() {
  const [autoPlay, setAutoPlay] = useState(localStorage.getItem('tts_autoplay') === 'true')
  const [availableVoices, setAvailableVoices] = useState([])
  const [selectedVoice, setSelectedVoice] = useState(localStorage.getItem('tts_voice') || '')
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    loadVoices()
  }, [])

  useEffect(() => {
    localStorage.setItem('tts_autoplay', autoPlay.toString())
    // Trigger storage event for other components
    window.dispatchEvent(new Event('storage'))
  }, [autoPlay])

  useEffect(() => {
    if (selectedVoice) {
      localStorage.setItem('tts_voice', selectedVoice)
    }
  }, [selectedVoice])

  const loadVoices = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/tts/voices`, {
        headers: {
          'Authorization': `Bearer ${localStorage.getItem('token')}`
        }
      })
      if (response.data.available) {
        setAvailableVoices(response.data.voices || [])
        if (!selectedVoice && response.data.current_voice) {
          setSelectedVoice(response.data.current_voice)
        }
      }
    } catch (error) {
      console.error('Failed to load voices:', error)
    }
  }

  return (
    <div className="voice-settings">
      <div className="voice-setting-item">
        <label>
          <input
            type="checkbox"
            checked={autoPlay}
            onChange={(e) => setAutoPlay(e.target.checked)}
          />
          <span>Auto-play voice responses</span>
        </label>
      </div>
      {availableVoices.length > 0 && (
        <div className="voice-setting-item">
          <label>
            Voice:
            <select
              value={selectedVoice}
              onChange={(e) => setSelectedVoice(e.target.value)}
              className="voice-select"
            >
              <option value="">Default</option>
              {availableVoices.map((voice) => (
                <option key={voice} value={voice}>
                  {voice}
                </option>
              ))}
            </select>
          </label>
        </div>
      )}
    </div>
  )
}

export default VoiceSettings

