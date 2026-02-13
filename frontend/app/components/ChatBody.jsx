'use client'

import { useState, useRef, useEffect } from "react"
import { Send as SendIcon } from "@mui/icons-material"
import Image from "next/image"
import UserReply from "./UserReply"
import BotReply from "./BotReply"

function ChatBody({ currentLanguage }) {
  const [messages, setMessages] = useState([
    {
      id: '1',
      type: 'bot',
      content: (
        <div>
          <p className="mb-0">You can discover more about the formation of the United States during the American Revolution through: Constitutional history and amendments; Congressional bills and legislation; Historical newspapers and documents; and Legal precedents and court cases.</p>
          <p className="mb-0">To tailor responses to your needs, tell me who you are:</p>
          <p className="mb-0">&nbsp;</p>
          <p className="font-semibold mb-2">Persona descriptions:</p>
          <div className="ml-4 mb-3 space-y-2">
            <p className="mb-0"><strong>1. Interested Person</strong> - I'll tell you all that I know based on my training with a special set of curated historical materials.</p>
            <p className="mb-0"><strong>2. Policy Analyst</strong> - I'll focus more on the historical precedents and constitutional interpretations.</p>
            <p className="mb-0"><strong>3. Research Journalist</strong> - I'll give you historical and cultural context in a tone more suited for the news.</p>
            <p className="mb-0"><strong>4. Law Student</strong> - I'll give you responses with precise legal terminology, referencing cases and legal reasoning found in the special set of historical documents I was trained on.</p>
          </div>
          <p className="font-semibold">Please select one to get started:</p>
        </div>
      ),
      timestamp: new Date()
    }
  ])
  const [conversationState, setConversationState] = useState('initial')
  const [selectedPersona, setSelectedPersona] = useState('')
  const [inputValue, setInputValue] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [isTyping, setIsTyping] = useState(false)
  const [sessionId, setSessionId] = useState(() => {
    // Generate unique session ID for this conversation
    return `session-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
  })
  const [userId] = useState(() => {
    // Get or create persistent user ID
    if (typeof window === 'undefined') return 'anonymous'
    const stored = localStorage.getItem('histora_user_id')
    if (stored) return stored
    const newId = `user-${Date.now()}-${Math.random().toString(36).substr(2, 9)}`
    localStorage.setItem('histora_user_id', newId)
    return newId
  })
  const messagesEndRef = useRef(null)
  const chatContainerRef = useRef(null)

  // Define personas
  const personas = {
    'interested_person': 'Interested Person',
    'policy_analyst': 'Policy Analyst',
    'research_journalist': 'Research Journalist',
    'law_student': 'Law Student'
  }

  const scrollToBottom = () => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTo({
        top: chatContainerRef.current.scrollHeight,
        behavior: 'smooth'
      });
    }
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages, isTyping])

  const handlePersonaSelection = (persona) => {
    setSelectedPersona(persona)

    const userMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: personas[persona],
      timestamp: new Date()
    }

    setMessages(prev => [...prev, userMessage])
    setIsTyping(true)

    setTimeout(() => {
      const botMessage = {
        id: (Date.now() + 1).toString(),
        type: 'bot',
        content: (
          <div>
            <p className="mb-0">Perfect! I'm now configured for <strong>{personas[persona]}</strong> responses.</p>
            <p className="mb-0">You can ask questions in your own words. I'm especially helpful with things like:</p>
            <ul className="list-disc ml-5 mt-2">
              <li>Explaining why a law, amendment, or case mattered at the time</li>
              <li>Summarizing historical documents or newspaper coverage</li>
              <li>Connecting related legislation,court cases or historical events</li>
              <li>Clarifying legal or constitutional concepts in plain language</li>
            </ul>
            <p className="mt-3 mb-0">What would you like to explore?</p>
          </div>
        ),
        timestamp: new Date()
      }
      setMessages(prev => [...prev, botMessage])
      setConversationState('persona-selected')
      setIsTyping(false)
    }, 800)
  }

  const handlePersonaChange = (newPersona) => {
    if (newPersona === selectedPersona) return

    setSelectedPersona(newPersona)

    const notificationMessage = {
      id: Date.now().toString(),
      type: 'bot',
      content: (
        <div>
          <p className="mb-0">
            <span className="italic">Persona switched to <strong>{personas[newPersona]}</strong></span>
          </p>
        </div>
      ),
      timestamp: new Date()
    }

    setMessages(prev => [...prev, notificationMessage])
  }

  const handleSendMessage = async (messageText = null) => {
    const messageToSend = messageText || inputValue.trim()
    if (!messageToSend || isLoading) return

    setInputValue("")
    setMessages(prev => [...prev, { type: "user", content: messageToSend }])
    setIsLoading(true)
    setIsTyping(true)

    try {
      // Replace with your actual API endpoint
      const apiUrl = process.env.NEXT_PUBLIC_API_BASE_URL || process.env.NEXT_PUBLIC_CHAT_ENDPOINT
      const chatEndpoint = `${apiUrl}chat`
      
      const response = await fetch(chatEndpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: messageToSend,
          persona: selectedPersona,
          language: currentLanguage,
          user_id: userId,
          session_id: sessionId,
        }),
      })

      if (!response.ok) {
        throw new Error("Failed to get response")
      }

      const data = await response.json()
      
      // Update session ID if server returns one
      if (data.session_id) {
        setSessionId(data.session_id)
      }
      
      setIsTyping(false)
      setMessages(prev => [...prev, { 
        type: "bot", 
        content: data.message || "I'm sorry, I couldn't process your request.",
        sources: data.sources || []
      }])
    } catch (error) {
      setIsTyping(false)
      setMessages(prev => [...prev, { 
        type: "bot", 
        content: "I'm sorry, there was an error processing your request. Please try again.",
        sources: []
      }])
    } finally {
      setIsLoading(false)
    }
  }

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault()
      handleSendMessage()
    }
  }

  return (
    <div className="bg-[#f4eee5] flex flex-col fixed inset-0 z-50 w-screen h-screen">
      {/* Header */}
      <div className="bg-[#28333a] flex h-[60px] items-center justify-between leading-[0] px-[32px] py-[10px] shrink-0">
        <div className="flex items-center gap-3">
          <div className="w-[48px] h-[48px] bg-white rounded-full flex items-center justify-center overflow-hidden p-1">
            <Image
              src="/logo.png"
              alt="Historical Figure Avatar"
              width={32}
              height={32}
              className="w-full h-full object-cover rounded-full"
              style={{ maxWidth: '32px', maxHeight: '32px' }}
            />
          </div>
          <p className="font-['Inter:Semi_Bold',sans-serif] font-semibold text-[16px] text-white">
            Cultural Heritage Chatbot
          </p>
        </div>

        {/* Persona Dropdown - Only show after persona is selected */}
        {selectedPersona && (
          <div className="flex items-center gap-2">
            <label className="text-white text-[14px] font-['Inter:Regular',sans-serif]">
              Persona:
            </label>
            <select
              value={selectedPersona}
              onChange={(e) => handlePersonaChange(e.target.value)}
              className="bg-white text-black text-[14px] font-['Inter:Regular',sans-serif] px-3 py-1.5 rounded-md border border-[rgba(255,255,255,0.3)] outline-none hover:bg-gray-100 focus:bg-gray-100 focus:border-gray-400 cursor-pointer transition-colors"
              style={{
                WebkitAppearance: 'none',
                MozAppearance: 'none',
                appearance: 'none',
                backgroundImage: `url("data:image/svg+xml,%3Csvg width='12' height='8' viewBox='0 0 12 8' fill='none' xmlns='http://www.w3.org/2000/svg'%3E%3Cpath d='M1 1.5L6 6.5L11 1.5' stroke='black' stroke-width='1.5' stroke-linecap='round' stroke-linejoin='round'/%3E%3C/svg%3E")`,
                backgroundRepeat: 'no-repeat',
                backgroundPosition: 'right 0.75rem center',
                paddingRight: '2.5rem'
              }}
            >
              {Object.entries(personas).map(([key, value]) => (
                <option key={key} value={key} className="bg-white text-black">
                  {value}
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto px-[29.5px] py-[29px]" ref={chatContainerRef}>
        <div className="flex flex-col gap-[30px]">
          {messages.map((message, index) => (
            <div key={message.id || index}>
              {message.type === 'bot' && (
                <div className="font-['Inter:Regular',sans-serif] text-[14px] text-black leading-[1.35]">
                  {typeof message.content === 'string' ? (
                    <BotReply 
                      message={message.content} 
                      sources={message.sources || []}
                      currentLanguage={currentLanguage}
                    />
                  ) : (
                    message.content
                  )}
                </div>
              )}
              {message.type === 'user' && (
                <div className="flex justify-end">
                  <div className="bg-[#28333a] px-[18px] py-[8px] rounded-[30px] max-w-[80%]">
                    <UserReply message={message.content} />
                  </div>
                </div>
              )}
              
              {/* Show persona selection buttons after initial message */}
              {index === 0 && conversationState === 'initial' && (
                <div className="flex flex-wrap gap-3 mt-[17px]">
                  {Object.entries(personas).map(([key, value]) => (
                    <button
                      key={key}
                      onClick={() => handlePersonaSelection(key)}
                      className="bg-[rgba(198,156,115,0.3)] h-[34px] px-[19px] py-[7px] rounded-[30px] hover:bg-[rgba(198,156,115,0.4)] transition-colors"
                    >
                      <p className="font-['Inter:Regular',sans-serif] text-[14px] text-black leading-[1.35] m-0">{value}</p>
                    </button>
                  ))}
                </div>
              )}
            </div>
          ))}
          
          {/* Typing Indicator */}
          {isTyping && (
            <div className="flex items-center gap-2">
              <div className="bg-[rgba(198,156,115,0.2)] px-[18px] py-[10px] rounded-[20px]">
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-[#28333a] rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                  <div className="w-2 h-2 bg-[#28333a] rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                  <div className="w-2 h-2 bg-[#28333a] rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="px-[32px] pb-[29px] shrink-0">
        <div className="bg-[rgba(93,85,67,0.1)] flex h-[46px] items-center justify-between px-[12px] py-[6px] rounded-[10px]">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type your question..."
            disabled={isLoading}
            className="flex-1 bg-transparent font-['Inter:Regular',sans-serif] text-[14px] text-black placeholder:text-[#737376] leading-[1.35] outline-none"
          />
          <button
            onClick={() => handleSendMessage()}
            disabled={!inputValue.trim() || isLoading}
            className="flex items-center justify-center w-[34px] h-[34px] hover:opacity-70 transition-opacity disabled:opacity-50"
            aria-label="Send message"
          >
            <SendIcon sx={{ fontSize: "18px", color: "#28333A" }} />
          </button>
        </div>
      </div>
    </div>
  )
}

export default ChatBody