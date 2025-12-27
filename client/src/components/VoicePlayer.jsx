import React, { useState, useRef, useEffect } from 'react'
import axios from 'axios'
import './VoicePlayer.css'

const API_BASE = import.meta.env.VITE_API_URL || ''

function VoicePlayer({ text, autoPlay = false }) {
  const [isPlaying, setIsPlaying] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [audioUrl, setAudioUrl] = useState(null)
  const [error, setError] = useState(null)
  const audioRef = useRef(null)
  const hasAutoPlayedRef = useRef(false)
  const textHashRef = useRef(null)
  const isRequestingRef = useRef(false)

  useEffect(() => {
    // Reset auto-play flag when text changes
    const currentHash = text ? text.substring(0, 50) : null
    if (textHashRef.current !== currentHash) {
      hasAutoPlayedRef.current = false
      textHashRef.current = currentHash
    }
  }, [text])

  useEffect(() => {
    // Cleanup audio on unmount
    return () => {
      if (audioRef.current) {
        audioRef.current.pause()
        audioRef.current.removeEventListener('play', () => {})
        audioRef.current.removeEventListener('pause', () => {})
        audioRef.current.removeEventListener('ended', () => {})
        audioRef.current.removeEventListener('error', () => {})
        audioRef.current = null
      }
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl)
      }
    }
  }, [audioUrl])

  const handlePlay = async () => {
    if (!text || !text.trim()) {
      setError('No text to speak')
      return
    }

    // Prevent concurrent requests
    if (isRequestingRef.current || isLoading) {
      return
    }

    // If audio already loaded, just play it
    if (audioUrl && audioRef.current) {
      try {
        await audioRef.current.play()
        setIsPlaying(true)
      } catch (e) {
        console.error('Error playing audio:', e)
        setError('Error playing audio')
      }
      return
    }

    isRequestingRef.current = true
    setIsLoading(true)
    setError(null)

    try {
      // Request audio from backend
      const response = await axios.post(
        `${API_BASE}/api/tts/speak`,
        { text: text },
        {
          responseType: 'blob',
          headers: {
            'Authorization': `Bearer ${localStorage.getItem('token')}`
          }
        }
      )

      // Create object URL from blob
      const blob = new Blob([response.data], { type: 'audio/wav' })
      const url = URL.createObjectURL(blob)
      setAudioUrl(url)

      // Create audio element and play
      const audio = new Audio(url)
      audioRef.current = audio

      audio.onplay = () => setIsPlaying(true)
      audio.onpause = () => setIsPlaying(false)
      audio.onended = () => {
        setIsPlaying(false)
        // Don't clean up immediately - keep audio available for replay
      }
      audio.onerror = (e) => {
        setError('Error playing audio')
        setIsPlaying(false)
        setIsLoading(false)
      }

      // Wait until audio is ready before playing to avoid "play() interrupted" errors
      audio.oncanplay = () => {
        audio.play().then(() => {
          setIsPlaying(true)
        }).catch((e) => {
          console.error('Play blocked:', e)
          setError('Click to enable audio')
        }).finally(() => {
          setIsLoading(false)
        })
      }
    } catch (err) {
      console.error('TTS Error:', err)
      let errorMsg = 'Failed to generate speech'
      
      if (err.response) {
        if (err.response.status === 503) {
          errorMsg = 'Voice feature not available. Coqui TTS may not be installed. Please contact administrator.'
        } else if (err.response.data?.detail) {
          errorMsg = err.response.data.detail
        } else {
          errorMsg = `Server error: ${err.response.status}`
        }
      } else if (err.message) {
        errorMsg = err.message
      }
      
      setError(errorMsg)
      setIsPlaying(false)
      // Clean up on error
      if (audioUrl) {
        URL.revokeObjectURL(audioUrl)
        setAudioUrl(null)
      }
    } finally {
      setIsLoading(false)
      isRequestingRef.current = false
    }
  }

  const handleStop = () => {
    if (audioRef.current) {
      audioRef.current.pause()
      audioRef.current.currentTime = 0
      setIsPlaying(false)
    }
  }

  // Auto-play when text changes and autoPlay is enabled (only once per text)
  useEffect(() => {
    if (autoPlay && text && text.trim() && !isLoading && !isPlaying && !hasAutoPlayedRef.current && !isRequestingRef.current) {
      hasAutoPlayedRef.current = true
      // Small delay to ensure typing is complete
      const timer = setTimeout(() => {
        handlePlay()
      }, 1000) // Increased delay to ensure typing is done
      return () => clearTimeout(timer)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [autoPlay, text]) // Only depend on autoPlay and text

  if (error && (error.includes('not available') || error.includes('503'))) {
    // TTS not available - show error message instead of hiding button
    return (
      <div className="voice-player">
        <span className="voice-error" style={{color: '#ff6b6b', fontSize: '0.85em'}}>
          Voice unavailable - TTS not installed
        </span>
      </div>
    )
  }

  return (
    <div className="voice-player">
      {isLoading ? (
        <button className="voice-button loading" disabled>
          <span className="voice-icon">🔊</span>
          <span>Generating...</span>
        </button>
      ) : isPlaying ? (
        <button className="voice-button playing" onClick={handleStop}>
          <span className="voice-icon">⏸</span>
          <span>Stop</span>
        </button>
      ) : (
        <button className="voice-button" onClick={handlePlay}>
          <span className="voice-icon">🔊</span>
          <span>Listen</span>
        </button>
      )}
      {error && <span className="voice-error">{error}</span>}
    </div>
  )
}

export default VoicePlayer

