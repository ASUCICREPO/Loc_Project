import React from "react"
import { Box, Typography, List, ListItem, ListItemText, useMediaQuery, IconButton } from "@mui/material"
import { getCurrentText, ABOUT_US_TEXT, FAQ_TEXT, PRIMARY_MAIN, WHITE } from "../utilities/constants"
import MenuIcon from "@mui/icons-material/Menu"
import CloseIcon from "@mui/icons-material/Close"

function LeftNav({ showLeftNav, setLeftNav, currentLanguage }) {
  const isSmallScreen = useMediaQuery("(max-width:600px)")
  const TEXT = getCurrentText(currentLanguage)

  return (
    <Box
      sx={{
        height: "100%",
        color: ABOUT_US_TEXT,
        padding: "1rem", // Reduced top padding
        paddingTop: "1rem", // Start closer to top
        position: "relative",
        overflow: "auto",
        backgroundColor: WHITE,
        borderRight: "1px solid #E0E0E0",
      }}
    >
      {/* Toggle button - Show hamburger menu when collapsed, X when expanded */}
      {!isSmallScreen && (
        <IconButton
          sx={{
            position: "absolute",
            right: "5px",
            top: "5px", // Moved closer to top
            backgroundColor: PRIMARY_MAIN,
            color: WHITE,
            padding: "5px",
            "&:hover": {
              backgroundColor: "#004d85",
            },
          }}
          onClick={() => setLeftNav(!showLeftNav)}
        >
          {showLeftNav ? <CloseIcon /> : <MenuIcon />}
        </IconButton>
      )}

      {/* Close button for small screens */}
      {isSmallScreen && (
        <IconButton
          sx={{
            position: "absolute",
            right: "5px",
            top: "5px", // Moved closer to top
            backgroundColor: PRIMARY_MAIN,
            color: WHITE,
            padding: "5px",
            "&:hover": {
              backgroundColor: "#004d85",
            },
          }}
          onClick={() => setLeftNav(false)}
        >
          <CloseIcon />
        </IconButton>
      )}

      {/* About Us Section */}
      {(showLeftNav || isSmallScreen) && (
        <>
          <Typography
            variant="h6"
            sx={{
              color: ABOUT_US_TEXT,
              fontWeight: "bold",
              marginBottom: "1rem",
            }}
          >
            {TEXT.ABOUT_US_TITLE}
          </Typography>
          <Typography
            variant="body2"
            sx={{
              color: ABOUT_US_TEXT,
              marginBottom: "2rem",
            }}
          >
            {TEXT.ABOUT_US}
          </Typography>

          {/* FAQs Section */}
          <Typography
            variant="h6"
            sx={{
              color: FAQ_TEXT,
              fontWeight: "bold",
              marginBottom: "1rem",
            }}
          >
            {TEXT.FAQ_TITLE}
          </Typography>
          <List>
            {TEXT.FAQS && TEXT.FAQS.map((faq, index) => (
              <ListItem key={index} sx={{ padding: "0.25rem 0" }}>
                <ListItemText
                  primary={faq}
                  sx={{
                    color: FAQ_TEXT,
                    "& .MuiListItemText-primary": {
                      fontSize: "0.9rem",
                    },
                  }}
                />
              </ListItem>
            ))}
          </List>
        </>
      )}
    </Box>
  )
}

export default LeftNav