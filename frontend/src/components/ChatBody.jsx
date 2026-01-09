import { useState, useRef, useEffect } from "react"
import { 
  Box, 
  TextField, 
  IconButton, 
  Typography,
  CircularProgress,
  ButtonGroup,
  Button,
  useMediaQuery
} from "@mui/material"
import { Send as SendIcon, Menu as MenuIcon } from "@mui/icons-material"
import FAQExamples from "./FAQExamples"
import BotReply from "./BotReply"
import UserReply from "./UserReply"
import { 
  getCurrentText, 
  WHITE, 
  PRIMARY_MAIN,
  LIGHT_BACKGROUND,
  DARK_BLUE
} from "../utilities/constants"

function ChatBody({ currentLanguage, toggleLanguage, showLeftNav, setLeftNav }) {
  const [messages, setMessages] = useState([])
  const [inputValue, setInputValue] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const messagesEndRef = useRef(null)
  const isSmallScreen = useMediaQuery("(max-width:600px)")
  const TEXT = getCurrentText(currentLanguage)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  const handleSendMessage = async (messageText = null) => {
    const messageToSend = messageText || inputValue.trim()
    if (!messageToSend || isLoading) return

    setInputValue("")
    setMessages(prev => [...prev, { type: "user", content: messageToSend }])
    setIsLoading(true)

    try {
      // Replace with your actual API endpoint
      const apiUrl = process.env.REACT_APP_API_BASE_URL || process.env.REACT_APP_CHAT_ENDPOINT
      const chatEndpoint = `${apiUrl}chat`
      
      const response = await fetch(chatEndpoint, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          message: messageToSend,
          language: currentLanguage,
        }),
      })

      if (!response.ok) {
        throw new Error("Failed to get response")
      }

      const data = await response.json()
      
      setMessages(prev => [...prev, { 
        type: "bot", 
        content: data.message || "I'm sorry, I couldn't process your request.",
        sources: data.sources || [],
        debugInfo: data.debug_info || null
      }])
    } catch (error) {
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

  const handleFAQClick = (question) => {
    // Directly send the FAQ question as a message
    handleSendMessage(question)
  }

  return (
    <Box
      sx={{
        height: "100vh", // Fixed viewport height
        display: "flex",
        flexDirection: "column",
        backgroundColor: LIGHT_BACKGROUND,
        overflow: "hidden", // Prevent page scroll
      }}
    >
      {/* Header with Logo and Language Toggle */}
      <Box
        sx={{
          padding: { xs: "0.5rem 1rem", sm: "0.75rem 1.5rem", md: "1rem 2rem" },
          paddingBottom: { xs: "0.5rem", sm: "1rem" },
          flexShrink: 0, // Don't shrink header
        }}
      >
        {/* Top Row: Logo (left) and Language Toggle (right) */}
        <Box
          sx={{
            display: "flex",
            justifyContent: "space-between",
            alignItems: "center",
            mb: { xs: 1, sm: 1.5 },
            ml: !isSmallScreen && !showLeftNav ? "50px" : "10px",
          }}
        >
          {/* Left side: Mobile Menu + Logo */}
          <Box sx={{ display: "flex", alignItems: "center", gap: 1 }}>
            {/* Mobile Menu Button */}
            {isSmallScreen && (
              <IconButton
                onClick={() => setLeftNav && setLeftNav(true)}
                sx={{
                  color: PRIMARY_MAIN,
                  padding: "5px",
                }}
              >
                <MenuIcon />
              </IconButton>
            )}
            
            <Typography
              variant="h4"
              sx={{
                fontSize: { xs: "1.2rem", sm: "1.5rem", md: "1.8rem" },
                fontWeight: "bold",
                color: PRIMARY_MAIN,
                fontFamily: "'Roboto', sans-serif",
              }}
            >
              {currentLanguage === "en" ? "Library of Congress" : "Biblioteca del Congreso"}
            </Typography>
          </Box>

          {/* Right side: Language Toggle */}
          <ButtonGroup
            variant="outlined"
            size="small"
            sx={{
              "& .MuiButton-root": {
                minWidth: "40px",
                padding: "6px 12px",
                fontSize: "0.875rem",
                fontWeight: "bold",
                border: `1px solid ${DARK_BLUE}`,
                color: DARK_BLUE,
                backgroundColor: WHITE,
                "&:hover": {
                  backgroundColor: DARK_BLUE,
                  color: WHITE,
                },
              },
              "& .MuiButton-root.active": {
                backgroundColor: DARK_BLUE,
                color: WHITE,
                "&:hover": {
                  backgroundColor: DARK_BLUE,
                },
              },
            }}
          >
            <Button
              className={currentLanguage === "en" ? "active" : ""}
              onClick={() => currentLanguage !== "en" && toggleLanguage()}
            >
              EN
            </Button>
            <Button
              className={currentLanguage === "es" ? "active" : ""}
              onClick={() => currentLanguage !== "es" && toggleLanguage()}
            >
              ES
            </Button>
          </ButtonGroup>
        </Box>
      </Box>

      {/* Scrollable Messages Area with Input at Bottom */}
      <Box
        sx={{
          flex: 1,
          overflow: "auto", // Enable scrolling for messages
          display: "flex",
          flexDirection: "column",
        }}
      >
        {/* Content Container */}
        <Box
          sx={{
            flex: 1,
            maxWidth: "1200px",
            margin: "0 auto",
            width: "100%",
            padding: { xs: "0 1rem", sm: "0 1.5rem", md: "0 2rem" },
          }}
        >
          {/* Show Welcome Content only when no messages */}
          {messages.length === 0 && (
            <Box sx={{ 
              paddingTop: { xs: "1rem", sm: "2rem", md: "3rem" },
            }}>
              {/* Welcome Title and Subtitle */}
              <Box sx={{ 
                textAlign: "center", 
                mb: { xs: 3, sm: 4, md: 5 },
              }}>
                <Typography
                  variant="h2"
                  sx={{
                    fontSize: { xs: "2rem", sm: "2.5rem", md: "3rem" },
                    fontWeight: "bold",
                    color: DARK_BLUE,
                    mb: 2,
                    fontFamily: "'Roboto', sans-serif",
                  }}
                >
                  {currentLanguage === "en" ? "Chronicling America" : "Crónicas de América"}
                </Typography>
                <Typography
                  variant="h6"
                  sx={{
                    fontSize: { xs: "1rem", sm: "1.1rem", md: "1.25rem" },
                    color: "#666",
                    maxWidth: "600px",
                    margin: "0 auto",
                    lineHeight: 1.5,
                  }}
                >
                  {currentLanguage === "en" 
                    ? "Explore historical Congressional bills and documents from America's early legislative history."
                    : "Explora proyectos de ley del Congreso históricos y documentos de la historia legislativa temprana de América."
                  }
                </Typography>
              </Box>
              
              <FAQExamples 
                currentLanguage={currentLanguage}
                onFAQClick={handleFAQClick}
              />
            </Box>
          )}

          {/* Chat Messages */}
          {messages.length > 0 && (
            <Box sx={{ paddingTop: "1rem" }}>
              {messages.map((message, index) => (
                <Box key={index} sx={{ mb: 2 }}>
                  {message.type === "user" ? (
                    <UserReply message={message.content} />
                  ) : (
                    <BotReply 
                      message={message.content} 
                      sources={message.sources}
                      currentLanguage={currentLanguage}
                      debugInfo={message.debugInfo}
                    />
                  )}
                </Box>
              ))}

              {/* Loading Indicator */}
              {isLoading && (
                <Box sx={{ display: "flex", justifyContent: "center", my: 2 }}>
                  <CircularProgress size={24} sx={{ color: PRIMARY_MAIN }} />
                </Box>
              )}

              <div ref={messagesEndRef} />
            </Box>
          )}
        </Box>

        {/* Input Area - Integrated with Chat Body */}
        <Box
          sx={{
            backgroundColor: LIGHT_BACKGROUND, // Same as chat body background
            padding: { xs: "0.75rem 1rem", sm: "1rem 1.5rem", md: "1.5rem 2rem" },
            paddingTop: { xs: "1rem", sm: "1.5rem", md: "2rem" }, // Extra top padding for spacing
            flexShrink: 0, // Don't shrink the input area
          }}
        >
          <Box sx={{ 
            maxWidth: "1200px", 
            margin: "0 auto",
            position: "relative",
          }}>
            <TextField
              fullWidth
              value={inputValue}
              onChange={(e) => setInputValue(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={TEXT.CHAT_PLACEHOLDER}
              variant="outlined"
              disabled={isLoading}
              sx={{
                "& .MuiOutlinedInput-root": {
                  borderRadius: "25px",
                  backgroundColor: WHITE,
                  border: "1px solid #E0E0E0",
                  paddingRight: { xs: "50px", sm: "60px" }, // Responsive padding for send button
                  "& fieldset": {
                    border: "none",
                  },
                  "&:hover": {
                    backgroundColor: WHITE,
                    boxShadow: "0 2px 8px rgba(0,0,0,0.1)",
                  },
                  "&.Mui-focused": {
                    backgroundColor: WHITE,
                    boxShadow: `0 0 0 2px ${PRIMARY_MAIN}20, 0 2px 8px rgba(0,0,0,0.1)`,
                  },
                },
                "& .MuiOutlinedInput-input": {
                  padding: { xs: "12px 16px", sm: "14px 20px" }, // Responsive padding
                  fontSize: { xs: "0.9rem", sm: "1rem" }, // Responsive font size
                },
              }}
            />
            <IconButton
              onClick={() => handleSendMessage()}
              disabled={!inputValue.trim() || isLoading}
              sx={{
                backgroundColor: PRIMARY_MAIN,
                color: WHITE,
                width: { xs: "40px", sm: "44px" }, // Responsive size
                height: { xs: "40px", sm: "44px" }, // Responsive size
                position: "absolute",
                right: { xs: "3px", sm: "4px" }, // Responsive positioning
                top: "50%",
                transform: "translateY(-50%)",
                "&:hover": {
                  backgroundColor: PRIMARY_MAIN,
                  opacity: 0.9,
                },
                "&:disabled": {
                  backgroundColor: "#E0E0E0",
                  color: "#999",
                },
              }}
            >
              <SendIcon sx={{ fontSize: { xs: "1rem", sm: "1.2rem" } }} />
            </IconButton>
          </Box>
        </Box>
      </Box>
    </Box>
  )
}

export default ChatBody