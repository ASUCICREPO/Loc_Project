'use client'

import { useState } from "react"
import MarkdownContent from "./MarkdownContent"

function BotReply({ message, sources = [], currentLanguage }) {
  const [showAllSources, setShowAllSources] = useState(false)
  
  // Function to get clean display name for sources
  const getDisplayName = (source) => {
    // Handle S3 presigned URLs and regular URLs
    let cleanUrl = source.url
    
    // For S3 presigned URLs, extract the original path before query parameters
    if (source.url.includes('amazonaws.com') && source.url.includes('?')) {
      cleanUrl = source.url.split('?')[0]
    }
    
    // For PDFs, show the filename without extension
    if (cleanUrl.includes('.pdf')) {
      const filename = cleanUrl.split('/').pop()
      return filename.replace('.pdf', '')
    }
    
    // For websites, use title if available and not generic, otherwise show clean URL
    if (source.title && source.title !== "Web Page") {
      return source.title
    }
    
    // Fallback: show clean hostname and path from URL
    try {
      const urlObj = new URL(cleanUrl)
      const hostname = urlObj.hostname.replace('www.', '')
      const pathname = urlObj.pathname
      
      // For S3 URLs, just show the filename
      if (hostname.includes('amazonaws.com')) {
        const filename = pathname.split('/').pop()
        return filename.replace('.pdf', '')
      }
      
      // For regular websites, show hostname + path
      return hostname + pathname
    } catch (e) {
      // If URL parsing fails, try to extract filename from the end
      const parts = cleanUrl.split('/')
      const lastPart = parts[parts.length - 1]
      return lastPart.replace('.pdf', '') || cleanUrl
    }
  }
  
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
                  className="text-[#28333a] text-xs font-medium no-underline flex items-center gap-1 hover:text-blue-600 hover:underline"
                >
                  {/* Show PDF or web icon */}
                  <span>{source.url.includes('.pdf') ? '📄' : '🌐'}</span>
                  
                  {/* Show meaningful display name */}
                  <span>{getDisplayName(source)}</span>
                  
                  <svg className="w-3 h-3 ml-1" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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