import React, { useState } from 'react'

function ExpandableSources({ sources, messageId, summaryCounts }) {
  const [isExpanded, setIsExpanded] = useState(false)
  const INITIAL_DISPLAY = 5

  if (!sources || sources.length === 0) return null

  const displaySources = isExpanded ? sources : sources.slice(0, INITIAL_DISPLAY)
  const hasMore = sources.length > INITIAL_DISPLAY

  return (
    <div className="sources">
      <div className="sources-header">
        <strong>
          Sources
          {summaryCounts[messageId]?.unique != null && (
            <>
              {' '}(
              {isExpanded 
                ? `${sources.length} of ${summaryCounts[messageId].total || sources.length}`
                : `${displaySources.length} of ${sources.length}`
              }
              {summaryCounts[messageId]?.total != null && summaryCounts[messageId].total > sources.length
                ? ` (${summaryCounts[messageId].total} total)`
                : ''}
              )
            </>
          )}
          :
        </strong>
        {hasMore && (
          <button
            className="expand-sources-btn"
            onClick={() => setIsExpanded(!isExpanded)}
            aria-label={isExpanded ? 'Show fewer sources' : 'Show all sources'}
          >
            {isExpanded ? '▼ Show Less' : '▶ Show All'}
          </button>
        )}
      </div>
      <ul>
        {displaySources.map((source, i) => (
          <li key={i}>
            {source.link ? (
              <a
                href={source.link}
                target="_blank"
                rel="noreferrer"
              >
                {source.source} ({source.jurisdiction})
                {source.citation ? ` – ${source.citation}` : ''}
              </a>
            ) : (
              <>
                {source.source} ({source.jurisdiction})
                {source.citation ? ` – ${source.citation}` : ''}
              </>
            )}
          </li>
        ))}
      </ul>
    </div>
  )
}

export default ExpandableSources









