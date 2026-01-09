// Color constants for Library of Congress Chronicling America - Blue Theme
export const PRIMARY_MAIN = "#0061A4"
export const SECONDARY_MAIN = "#08325C" 
export const DARK_BLUE = "#08325C"
export const LIGHT_BACKGROUND = "#F5F8FA"
export const WHITE = "#FFFFFF"
export const LIGHT_GRAY = "#F8F9FA"

// Background colors
export const CHAT_LEFT_PANEL_BACKGROUND = WHITE
export const CHAT_BODY_BACKGROUND = WHITE
export const BOTMESSAGE_BACKGROUND = "#E3F2FD"
export const USERMESSAGE_BACKGROUND = "#E8F4FD"
export const HEADER_TEXT_GRADIENT = DARK_BLUE

// Text colors
export const ABOUT_US_TEXT = DARK_BLUE
export const FAQ_TEXT = DARK_BLUE
export const primary_50 = "rgba(0, 97, 164, 0.1)"

// API Configuration
export const API_BASE_URL = process.env.REACT_APP_API_BASE_URL || 'https://your-api-gateway-url.amazonaws.com'

// Text content
export const getCurrentText = (language) => {
  const texts = {
    en: {
      CHAT_HEADER_TITLE: "Chronicling America",
      ABOUT_US_TITLE: "About this Project",
      ABOUT_US: "Welcome to the Library of Congress Chronicling America AI Assistant. This tool helps you explore historical Congressional bills and documents from America's early legislative history. Search through digitized records to discover insights about the formation of our nation's laws and policies.",
      FAQ_TITLE: "Example Queries",
      FAQS: [
        "What is bill HR 1 from congress 6?",
        "Show me bills about taxation from the early congresses",
        "What were the main issues discussed in congress 10?",
        "Find bills related to commerce and trade",
        "What legislation was passed in the 1800s?",
        "Show me bills from a specific congressman"
      ],
      FAQ_QUESTIONS: [
        "What is bill HR 1 from congress 6?",
        "Show me bills about taxation from the early congresses", 
        "What were the main issues discussed in congress 10?",
        "Find bills related to commerce and trade"
      ],
      CHAT_PLACEHOLDER: "Ask about historical Congressional bills...",
      SEND_BUTTON: "Send",
      LANGUAGE_TOGGLE: "ES"
    },
    es: {
      CHAT_HEADER_TITLE: "Crónicas de América",
      ABOUT_US_TITLE: "Acerca de este Proyecto",
      ABOUT_US: "Bienvenido al Asistente de IA de Chronicling America de la Biblioteca del Congreso. Esta herramienta te ayuda a explorar proyectos de ley del Congreso históricos y documentos de la historia legislativa temprana de América. Busca a través de registros digitalizados para descubrir perspectivas sobre la formación de las leyes y políticas de nuestra nación.",
      FAQ_TITLE: "Consultas de Ejemplo",
      FAQS: [
        "¿Qué es el proyecto de ley HR 1 del congreso 6?",
        "Muéstrame proyectos de ley sobre impuestos de los primeros congresos",
        "¿Cuáles fueron los temas principales discutidos en el congreso 10?",
        "Encuentra proyectos de ley relacionados con comercio",
        "¿Qué legislación se aprobó en los años 1800?",
        "Muéstrame proyectos de ley de un congresista específico"
      ],
      FAQ_QUESTIONS: [
        "¿Qué es el proyecto de ley HR 1 del congreso 6?",
        "Muéstrame proyectos de ley sobre impuestos de los primeros congresos",
        "¿Cuáles fueron los temas principales discutidos en el congreso 10?",
        "Encuentra proyectos de ley relacionados con comercio"
      ],
      CHAT_PLACEHOLDER: "Pregunta sobre proyectos de ley del Congreso históricos...",
      SEND_BUTTON: "Enviar", 
      LANGUAGE_TOGGLE: "EN"
    }
  }
  return texts[language] || texts.en
}