import React, { useState, useEffect, useRef } from 'react'
import LegalResponseFormatter from './LegalResponseFormatter'

function TypingText({ text, speed = 30, onComplete }) {
  const [displayedText, setDisplayedText] = useState('')
  const [isTyping, setIsTyping] = useState(true)
  const timeoutRef = useRef(null)
  const currentIndexRef = useRef(0)
  const onCompleteRef = useRef(onComplete)

  // Update ref when onComplete changes
  useEffect(() => {
    onCompleteRef.current = onComplete
  }, [onComplete])

  useEffect(() => {
    // Clear any existing timeout
    if (timeoutRef.current) {
      clearTimeout(timeoutRef.current)
    }

    if (!text) {
      setDisplayedText('')
      setIsTyping(false)
      currentIndexRef.current = 0
      return
    }

    // Reset for new text
    setDisplayedText('')
    setIsTyping(true)
    currentIndexRef.current = 0

    const typeChar = () => {
      if (currentIndexRef.current < text.length) {
        setDisplayedText(text.substring(0, currentIndexRef.current + 1))
        currentIndexRef.current++
        timeoutRef.current = setTimeout(typeChar, speed)
      } else {
        setIsTyping(false)
        if (onCompleteRef.current) {
          onCompleteRef.current()
        }
      }
    }

    // Small delay before starting to type
    timeoutRef.current = setTimeout(() => {
      typeChar()
    }, 100)

    return () => {
      if (timeoutRef.current) {
        clearTimeout(timeoutRef.current)
        timeoutRef.current = null
      }
    }
  }, [text, speed]) // Removed onComplete from dependencies

  // Use LegalResponseFormatter to format the text as it types
  return (
    <>
      <LegalResponseFormatter text={displayedText} />
      {isTyping && <span className="typing-cursor">|</span>}
    </>
  )
}

export default TypingText

