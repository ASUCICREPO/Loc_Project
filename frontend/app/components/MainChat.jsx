'use client'

import { useState } from "react"
import ChatBody from "./ChatBody"

function MainChat() {
  // Initialize language from localStorage or default to "en"
  const [currentLanguage, setCurrentLanguage] = useState(() => {
    if (typeof window !== 'undefined') {
      return localStorage.getItem('selectedLanguage') || "en"
    }
    return "en"
  })

  return (
    <div style={{ display: "flex", flexDirection: "column" }}>
      <div style={{ display: "flex", position: "relative" }}>
        {/* Chat Content Area */}
        <div style={{
          flexGrow: 1,
          display: "flex",
          flexDirection: "column",
          position: "relative",
        }}>
          <div style={{
            flex: "1 1 auto",
            display: "flex",
            flexDirection: "column",
            position: "relative",
          }}>
            <ChatBody 
              currentLanguage={currentLanguage}
            />
          </div>
        </div>
      </div>
    </div>
  )
}

export default MainChat