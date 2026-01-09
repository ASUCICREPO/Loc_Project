import { useState, useEffect } from "react"
import { Box, useMediaQuery, Drawer, IconButton } from "@mui/material"
import { Menu as MenuIcon } from "@mui/icons-material"
import LeftNav from "./LeftNav"
import ChatBody from "./ChatBody"
import { WHITE, LIGHT_BACKGROUND, PRIMARY_MAIN } from "../utilities/constants"

function MainChat() {
  // Initialize language from localStorage or default to "en"
  const [currentLanguage, setCurrentLanguage] = useState(() => {
    return localStorage.getItem('selectedLanguage') || "en"
  })
  const [showLeftNav, setLeftNav] = useState(false)
  const isMobile = useMediaQuery("(max-width:768px)")
  const isSmallScreen = useMediaQuery("(max-width:600px)")

  const toggleLanguage = () => {
    const newLanguage = currentLanguage === "en" ? "es" : "en"
    // Save the new language to localStorage so it persists after page refresh
    localStorage.setItem('selectedLanguage', newLanguage)
    setCurrentLanguage(newLanguage)
    // Refresh the page to clear chat history when language changes
    // The new language will be loaded from localStorage on page reload
    setTimeout(() => {
      window.location.reload()
    }, 100)
  }

  useEffect(() => {
    if (isMobile) {
      setLeftNav(false)
    }
  }, [isMobile])

  return (
    <Box sx={{ display: "flex", flexDirection: "column" }}>
      <Box
        sx={{
          display: "flex",
          position: "relative",
        }}
      >
        {/* Mobile Drawer */}
        {isSmallScreen && (
          <Drawer
            variant="temporary"
            open={showLeftNav}
            onClose={() => setLeftNav(false)}
            ModalProps={{ keepMounted: true }}
            sx={{
              "& .MuiDrawer-paper": {
                width: "280px",
                backgroundColor: WHITE,
                boxSizing: "border-box",
              },
            }}
          >
            <LeftNav 
              showLeftNav={true} 
              setLeftNav={setLeftNav}
              currentLanguage={currentLanguage}
            />
          </Drawer>
        )}

        {/* Desktop Overlay Drawer */}
        {!isSmallScreen && (
          <Drawer
            variant="temporary"
            open={showLeftNav}
            onClose={() => setLeftNav(false)}
            sx={{
              "& .MuiDrawer-paper": {
                width: "300px",
                backgroundColor: WHITE,
                boxSizing: "border-box",
              },
            }}
          >
            <LeftNav 
              showLeftNav={true} 
              setLeftNav={setLeftNav}
              currentLanguage={currentLanguage}
            />
          </Drawer>
        )}

        {/* Floating Menu Button */}
        {!showLeftNav && (
          <IconButton
            onClick={() => setLeftNav(true)}
            sx={{
              position: "fixed",
              top: "20px",
              left: "20px",
              zIndex: 1000,
              backgroundColor: PRIMARY_MAIN,
              color: WHITE,
              width: "48px",
              height: "48px",
              boxShadow: "0 4px 12px rgba(0, 97, 164, 0.3)",
              "&:hover": {
                backgroundColor: "#004d85",
              },
            }}
          >
            <MenuIcon />
          </IconButton>
        )}

        {/* Chat Content Area */}
        <Box
          sx={{
            flexGrow: 1,
            backgroundColor: LIGHT_BACKGROUND,
            display: "flex",
            flexDirection: "column",
            position: "relative",
          }}
        >
          <Box
            sx={{
              flex: "1 1 auto",
              display: "flex",
              flexDirection: "column",
              position: "relative",
            }}
          >
            <ChatBody 
              currentLanguage={currentLanguage}
              toggleLanguage={toggleLanguage}
              showLeftNav={showLeftNav}
              setLeftNav={setLeftNav}
            />
          </Box>
        </Box>
      </Box>
    </Box>
  )
}

export default MainChat