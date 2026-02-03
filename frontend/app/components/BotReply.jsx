'use client'

import { useState } from "react"
import MarkdownContent from "./MarkdownContent"

function BotReply({ message, sources = [], currentLanguage }) {
  const [showAllSources, setShowAllSources] = useState(false)
  
  const displayedSources = showAllSources ? sources : sources.slice(0, 3)
  const remainingSources = sources.length - 3
  
  return (
    <div className="mb-6">
      {/* Message Text - Rendered with Markdown Support */}
      <div className="mb-4">
        <MarkdownContent content={message} />
      </div>

      {/* Sources */}
      {sources && sources.length > 0 && (
        <div className="mt-4 p-3 bg-gray-50 rounded-lg border-l-4 border-[#28333a]">
          <div className="text-sm font-medium text-gray-700 mb-2">
            📄 {currentLanguage === "es" ? "Fuentes" : "Sources"}
          </div>
          
          <div className="space-y-2">
            {displayedSources.map((source, index) => (
              <div key={index} className="p-2 bg-white rounded border border-gray-200">
                <a
                  href={source.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-[#28333a] text-xs font-medium no-underline flex items-center gap-1 hover:text-blue-600 hover:underline break-all"
                  style={{ lineHeight: '1.5' }}
                >
                  {/* Show PDF or web icon */}
                  <span className="flex-shrink-0" style={{ fontSize: '14px' }}>
                    {source.url.includes('.pdf') ? '📄' : '🌐'}
                  </span>
                  
                  {/* Show full URL */}
                  <span className="flex-1">{source.url}</span>
                  
                  {/* Smaller external link icon with inline styles to ensure size */}
                  <svg 
                    className="ml-1 flex-shrink-0" 
                    style={{ 
                      width: '12px', 
                      height: '12px', 
                      minWidth: '12px', 
                      minHeight: '12px',
                      display: 'inline-block',
                      verticalAlign: 'middle'
                    }}
                    fill="none" 
                    stroke="currentColor" 
                    viewBox="0 0 24 24"
                  >
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14" />
                  </svg>
                </a>
              </div>
            ))}
          </div>
          
          {/* Show remaining sources count and expand button */}
          {remainingSources > 0 && (
            <button
              onClick={() => setShowAllSources(!showAllSources)}
              className="text-[#28333a] text-xs mt-2 px-1 py-1 hover:bg-gray-100 rounded transition-colors"
            >
              {showAllSources 
                ? (currentLanguage === "es" ? "Mostrar menos" : "Show less")
                : (currentLanguage === "es" 
                    ? `+${remainingSources} fuentes más` 
                    : `+${remainingSources} more sources`)
              }
            </button>
          )}
        </div>
      )}
    </div>
  )
}

export default BotReply