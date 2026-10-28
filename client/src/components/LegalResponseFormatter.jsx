import React from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

/**
 * LegalResponseFormatter - Research memos (Markdown ##), legacy 10-box, or plain text.
 */
function looksLikeMarkdownMemo(text) {
  if (!text || typeof text !== 'string') return false
  return /^##\s+\S/m.test(text) || /^###\s+\S/m.test(text)
}

function LegalResponseFormatter({ text }) {
  if (!text) return null

  // Parse the structured response format
  const parseStructuredResponse = (text) => {
    const sections = []
    const lines = text.split('\n')
    let currentSection = null
    let currentContent = []

    const boxPatterns = [
      { pattern: /^1st box:?\s*(.+)/i, type: 'statement', label: 'Statement to the User' },
      { pattern: /^2nd box:?\s*(.+)/i, type: 'user', label: 'User' },
      { pattern: /^3rd box:?\s*(.+)/i, type: 'date', label: 'Date' },
      { pattern: /^4th box:?\s*(.+)/i, type: 'conclusion', label: 'Conclusion (C.R.A.C.)' },
      { pattern: /^5th box:?\s*(.+)/i, type: 'rule', label: 'Rule (C.R.A.C.)' },
      { pattern: /^6th box:?\s*(.+)/i, type: 'analysis', label: 'Analysis (C.R.A.C.)' },
      { pattern: /^7th box:?\s*(.+)/i, type: 'application', label: 'Application (C.R.A.C.)' },
      { pattern: /^8th box:?\s*(.+)/i, type: 'sources', label: 'Sources and Citations' },
      { pattern: /^9th box:?\s*(.+)/i, type: 'prediction', label: 'Analytic Predictive Outcome' },
      { pattern: /^10th box:?\s*(.+)/i, type: 'limitations', label: 'Limitations and Explanations' },
    ]

    // Also check for C.R.A.C. section headers
    const cracPatterns = [
      { pattern: /^(Conclusion|CONCLUSION):?\s*(.+)/i, type: 'conclusion', label: 'Conclusion' },
      { pattern: /^(Rule|RULE):?\s*(.+)/i, type: 'rule', label: 'Rule' },
      { pattern: /^(Analysis|ANALYSIS):?\s*(.+)/i, type: 'analysis', label: 'Analysis' },
      { pattern: /^(Application|APPLICATION):?\s*(.+)/i, type: 'application', label: 'Application' },
      // Handle "[Insert X]" format followed by content
      { pattern: /^\[Insert\s+Conclusion\]\s*$/i, type: 'conclusion', label: 'Conclusion', isPlaceholder: true },
      { pattern: /^\[Insert\s+Rule\]\s*$/i, type: 'rule', label: 'Rule', isPlaceholder: true },
      { pattern: /^\[Insert\s+Analysis\]\s*$/i, type: 'analysis', label: 'Analysis', isPlaceholder: true },
      { pattern: /^\[Insert\s+Application\]\s*$/i, type: 'application', label: 'Application', isPlaceholder: true },
      { pattern: /^\[Insert\/List\s+all\s+sources\s+and\s+citations\s+used\]\s*$/i, type: 'sources', label: 'Sources and Citations', isPlaceholder: true },
      { pattern: /^\[Insert\s+analytic\s+predictive\s+percentage\s+outcome\]\s*$/i, type: 'prediction', label: 'Analytic Predictive Outcome', isPlaceholder: true },
      { pattern: /^\[Insert\s+explanation[^\]]*\]\s*$/i, type: 'limitations', label: 'Limitations and Explanations', isPlaceholder: true },
    ]

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim()
      if (!line) {
        if (currentContent.length > 0) {
          currentContent.push('')
        }
        continue
      }

      // Check for box patterns
      let matched = false
      for (const { pattern, type, label } of boxPatterns) {
        const match = line.match(pattern)
        if (match) {
          // Save previous section
          if (currentSection) {
            sections.push({
              ...currentSection,
              content: currentContent.join('\n').trim()
            })
          }
          // Start new section
          currentSection = { type, label, header: match[1] || label }
          currentContent = []
          matched = true
          break
        }
      }

      // Check for C.R.A.C. patterns if no box match
      if (!matched) {
        for (const { pattern, type, label, isPlaceholder } of cracPatterns) {
          const match = line.match(pattern)
          if (match) {
            // Save previous section
            if (currentSection) {
              sections.push({
                ...currentSection,
                content: currentContent.join('\n').trim()
              })
            }
            // Start new section
            if (isPlaceholder) {
              // For placeholder format, the content comes on the next line(s)
              currentSection = { type, label, header: label, isCrac: true, isPlaceholder: true }
              currentContent = []
            } else {
              // For direct format like "Conclusion: content"
              currentSection = { type, label, header: label, isCrac: true }
              currentContent = [match[2] || '']
            }
            matched = true
            break
          }
        }
      }

      if (!matched) {
        currentContent.push(line)
      }
    }

    // Save last section
    if (currentSection) {
      sections.push({
        ...currentSection,
        content: currentContent.join('\n').trim()
      })
    }

    // If no structured format found, return original text
    if (sections.length === 0) {
      return null
    }

    return sections
  }

  // Clean up placeholder text before parsing
  const cleanedText = text
    .replace(/\[Insert\s+Conclusion\]/gi, 'Conclusion:')
    .replace(/\[Insert\s+Rule\]/gi, 'Rule:')
    .replace(/\[Insert\s+Analysis\]/gi, 'Analysis:')
    .replace(/\[Insert\s+Application\]/gi, 'Application:')
    .replace(/\[Insert\/List\s+all\s+sources\s+and\s+citations\s+used\]/gi, 'Sources and Citations Used:')
    .replace(/\[Insert\s+analytic\s+predictive\s+percentage\s+outcome\]/gi, 'Analytic Predictive Percentage Outcome:')
    .replace(/\[Insert\s+explanation[^\]]*\]/gi, 'Explanation:')
    .replace(/\[Insert\s+Date\]/gi, 'Date:')
    .replace(/\[Insert\s+[^\]]+\]/gi, '') // Remove any other [Insert X] patterns

  const sections = parseStructuredResponse(cleanedText)

  // Firm-style research memo (Markdown headings from backend prompt)
  if (looksLikeMarkdownMemo(cleanedText)) {
    return (
      <div className="legal-response research-memo-md">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{cleanedText}</ReactMarkdown>
      </div>
    )
  }

  // If parsing didn't find structure, render as plain text with improved spacing
  if (!sections || sections.length === 0) {
    return (
      <div className="legal-response">
        <div className="legal-section-content" style={{ whiteSpace: 'pre-wrap' }}>
          {cleanedText}
        </div>
      </div>
    )
  }

  // Render structured sections
  return (
    <div className="legal-response">
      {sections.map((section, idx) => {
        const { type, label, content, header, isCrac } = section

        // Statement section
        if (type === 'statement') {
          return (
            <div key={idx} className="legal-statement">
              {header && <div style={{ marginBottom: '0.5rem', fontWeight: 600 }}>{header}</div>}
              <div className="legal-section-content">{content}</div>
            </div>
          )
        }

        // User/Date sections (smaller, less prominent)
        if (type === 'user' || type === 'date') {
          return (
            <div key={idx} className="legal-section" style={{ marginBottom: '1rem', paddingBottom: '0.5rem' }}>
              <div className="legal-section-header" style={{ fontSize: '0.85rem', padding: '0.5rem 0.75rem' }}>
                {label}
              </div>
              <div className="legal-section-content" style={{ fontSize: '0.9rem', paddingLeft: '1rem' }}>
                {content || header}
              </div>
            </div>
          )
        }

        // C.R.A.C. sections (Conclusion, Rule, Analysis, Application)
        if (isCrac || ['conclusion', 'rule', 'analysis', 'application'].includes(type)) {
          return (
            <div key={idx} className="crac-section">
              <div className="crac-header">{label}</div>
              <div className="crac-content" style={{ whiteSpace: 'pre-wrap' }}>
                {content}
              </div>
            </div>
          )
        }

        // Sources section
        if (type === 'sources') {
          const sourceItems = content.split('\n').filter(line => line.trim())
          return (
            <div key={idx} className="legal-sources">
              <div className="legal-sources-header">{label}</div>
              <ul className="legal-sources-list">
                {sourceItems.map((item, i) => (
                  <li key={i}>{item.trim()}</li>
                ))}
              </ul>
            </div>
          )
        }

        // Prediction section
        if (type === 'prediction') {
          return (
            <div key={idx} className="legal-prediction">
              <div className="legal-prediction-header">{label}</div>
              <div className="legal-prediction-content" style={{ whiteSpace: 'pre-wrap' }}>
                {content}
              </div>
            </div>
          )
        }

        // Limitations section
        if (type === 'limitations') {
          return (
            <div key={idx} className="legal-limitations">
              <div className="legal-limitations-header">{label}</div>
              <div className="legal-limitations-content" style={{ whiteSpace: 'pre-wrap' }}>
                {content}
              </div>
            </div>
          )
        }

        // Default section
        return (
          <div key={idx} className="legal-section">
            <div className="legal-section-header">{label}</div>
            <div className="legal-section-content" style={{ whiteSpace: 'pre-wrap' }}>
              {content}
            </div>
          </div>
        )
      })}
    </div>
  )
}

export default LegalResponseFormatter

