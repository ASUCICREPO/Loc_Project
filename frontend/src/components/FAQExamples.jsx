import React from "react"
import { Box, Grid, Button, Typography } from "@mui/material"
import { 
  DescriptionOutlined as BillIcon,
  SearchOutlined as SearchIcon,
  AccountBalanceOutlined as CongressIcon,
  HistoryOutlined as HistoryIcon
} from "@mui/icons-material"
import { 
  getCurrentText, 
  PRIMARY_MAIN,
  WHITE,
  DARK_BLUE
} from "../utilities/constants"

function FAQExamples({ currentLanguage, onFAQClick }) {
  const TEXT = getCurrentText(currentLanguage)

  const faqItems = [
    {
      icon: <BillIcon />,
      title: currentLanguage === "en" ? "Specific Bills" : "Proyectos de Ley Específicos",
      description: currentLanguage === "en" 
        ? "Search for specific Congressional bills by number, congress session, or title."
        : "Busca proyectos de ley específicos del Congreso por número, sesión del congreso o título.",
      question: TEXT.FAQ_QUESTIONS[0]
    },
    {
      icon: <SearchIcon />,
      title: currentLanguage === "en" ? "Topic-Based Search" : "Búsqueda por Tema",
      description: currentLanguage === "en"
        ? "Explore bills related to specific topics like taxation, commerce, or social issues."
        : "Explora proyectos de ley relacionados con temas específicos como impuestos, comercio o temas sociales.",
      question: TEXT.FAQ_QUESTIONS[1]
    },
    {
      icon: <CongressIcon />,
      title: currentLanguage === "en" ? "Congressional Sessions" : "Sesiones del Congreso",
      description: currentLanguage === "en"
        ? "Discover what issues and legislation were discussed in specific Congressional sessions."
        : "Descubre qué temas y legislación se discutieron en sesiones específicas del Congreso.",
      question: TEXT.FAQ_QUESTIONS[2]
    },
    {
      icon: <HistoryIcon />,
      title: currentLanguage === "en" ? "Historical Context" : "Contexto Histórico",
      description: currentLanguage === "en"
        ? "Learn about the historical context and impact of early American legislation."
        : "Aprende sobre el contexto histórico y el impacto de la legislación americana temprana.",
      question: TEXT.FAQ_QUESTIONS[3]
    }
  ]

  return (
    <Box sx={{ 
      mb: 2, 
      maxWidth: "1200px", 
      mx: "auto",
      px: { xs: 2, sm: 3, md: 4 } // Add horizontal padding for all screen sizes
    }}>
      {/* 4 Cards - Responsive Layout */}
      <Grid container spacing={{ xs: 1.5, sm: 2, md: 2 }}>
        {faqItems.map((item, index) => (
          <Grid item xs={6} sm={6} md={3} key={index}>
            <Button
              onClick={() => onFAQClick(item.question)}
              sx={{
                width: "100%",
                height: { xs: "120px", sm: "150px", md: "160px" }, // Shorter on mobile
                padding: { xs: "0.5rem", sm: "0.8rem", md: "0.9rem" },
                backgroundColor: WHITE,
                border: "1px solid #E0E0E0",
                borderRadius: "8px",
                textAlign: "left",
                display: "flex",
                flexDirection: "column",
                alignItems: "flex-start",
                gap: { xs: 0.3, sm: 0.6, md: 0.8 },
                textTransform: "none",
                color: "inherit",
                boxShadow: "0 2px 4px rgba(0,0,0,0.1)",
                transition: "all 0.2s ease",
                "&:hover": {
                  borderColor: PRIMARY_MAIN,
                  boxShadow: "0 4px 12px rgba(0, 97, 164, 0.15)",
                  transform: "translateY(-2px)",
                },
              }}
            >
              <Box
                sx={{
                  display: "flex",
                  alignItems: "center",
                  gap: 1,
                  mb: { xs: 0.25, sm: 0.5 }, // Responsive margin
                  color: PRIMARY_MAIN,
                }}
              >
                {React.cloneElement(item.icon, { 
                  sx: { fontSize: { xs: "1.1rem", sm: "1.2rem", md: "1.3rem" } } 
                })}
              </Box>
              <Typography
                variant="h6"
                sx={{
                  fontWeight: "bold",
                  fontSize: { xs: "0.85rem", sm: "0.9rem", md: "0.95rem" }, // Responsive font size
                  color: DARK_BLUE,
                  mb: { xs: 0.25, sm: 0.5 }, // Responsive margin
                  lineHeight: 1.2,
                  wordBreak: "break-word", // Prevent overflow
                  hyphens: "auto", // Allow hyphenation
                }}
              >
                {item.title}
              </Typography>
              <Typography
                variant="body2"
                sx={{
                  color: "#666",
                  lineHeight: { xs: 1.2, sm: 1.25, md: 1.3 }, // Responsive line height
                  fontSize: { xs: "0.7rem", sm: "0.75rem", md: "0.8rem" }, // Responsive font size
                  flex: 1,
                  wordBreak: "break-word", // Prevent overflow
                  hyphens: "auto", // Allow hyphenation
                  overflow: "hidden", // Hide overflow
                  display: "-webkit-box",
                  WebkitLineClamp: { xs: 4, sm: 5, md: 6 }, // Limit lines based on screen size
                  WebkitBoxOrient: "vertical",
                }}
              >
                {item.description}
              </Typography>
            </Button>
          </Grid>
        ))}
      </Grid>

      {/* Additional FAQ Questions */}
      <Box sx={{ mt: { xs: 4, sm: 5, md: 6 }, textAlign: "center" }}> {/* Increased margin significantly */}
        <Typography
          variant="body2"
          sx={{
            color: "#666",
            mb: { xs: 2, sm: 2.5, md: 3 }, // Increased margin
            fontSize: { xs: "0.8rem", sm: "0.85rem", md: "0.9rem" }, // Responsive font size
          }}
        >
          {currentLanguage === "en" ? "Or try these example queries:" : "O prueba estas consultas de ejemplo:"}
        </Typography>
        <Box sx={{ 
          display: "flex", 
          flexWrap: "wrap", 
          gap: { xs: 0.5, sm: 0.75, md: 1 }, // Responsive gap
          justifyContent: "center",
          px: { xs: 1, sm: 0 }, // Add padding on mobile
        }}>
          {[
            currentLanguage === "en" ? "What legislation was passed in the 1800s?" : "¿Qué legislación se aprobó en los años 1800?",
            currentLanguage === "en" ? "Show me bills from a specific congressman" : "Muéstrame proyectos de ley de un congresista específico",
            currentLanguage === "en" ? "Find bills about westward expansion" : "Encuentra proyectos de ley sobre expansión hacia el oeste",
            currentLanguage === "en" ? "What were the major debates in early Congress?" : "¿Cuáles fueron los debates principales en el Congreso temprano?",
            currentLanguage === "en" ? "Show me bills about slavery" : "Muéstrame proyectos de ley sobre esclavitud",
          ].map((question, index) => (
            <Button
              key={index}
              variant="outlined"
              size="small"
              onClick={() => onFAQClick(question)}
              sx={{
                borderColor: PRIMARY_MAIN,
                color: PRIMARY_MAIN,
                borderRadius: "20px",
                textTransform: "none",
                fontSize: { xs: "0.65rem", sm: "0.7rem", md: "0.75rem" }, // Responsive font size
                padding: { xs: "2px 8px", sm: "3px 10px" }, // Responsive padding
                minWidth: "auto", // Allow buttons to shrink
                whiteSpace: "nowrap", // Prevent text wrapping in buttons
                "&:hover": {
                  borderColor: DARK_BLUE,
                  color: DARK_BLUE,
                  backgroundColor: "rgba(0, 97, 164, 0.05)",
                },
              }}
            >
              {question}
            </Button>
          ))}
        </Box>
      </Box>
    </Box>
  )
}

export default FAQExamples