import { createTheme } from "@mui/material/styles"
import {
  PRIMARY_MAIN,
  SECONDARY_MAIN,
  DARK_BLUE,
  LIGHT_BACKGROUND,
  WHITE,
  CHAT_LEFT_PANEL_BACKGROUND,
  BOTMESSAGE_BACKGROUND,
  USERMESSAGE_BACKGROUND,
} from "./utilities/constants"

const theme = createTheme({
  palette: {
    primary: {
      main: PRIMARY_MAIN,
      light: "#42a5f5",
      dark: DARK_BLUE,
    },
    secondary: {
      main: SECONDARY_MAIN,
    },
    background: {
      default: LIGHT_BACKGROUND,
      paper: WHITE,
      chatBody: LIGHT_BACKGROUND,
      chatLeftPanel: CHAT_LEFT_PANEL_BACKGROUND,
      header: LIGHT_BACKGROUND,
      botMessage: BOTMESSAGE_BACKGROUND,
      userMessage: USERMESSAGE_BACKGROUND,
    },
  },
  typography: {
    fontFamily: [
      "Roboto",
      "-apple-system",
      "BlinkMacSystemFont",
      "Segoe UI",
      "Oxygen",
      "Ubuntu",
      "Cantarell",
      "Fira Sans",
      "Droid Sans",
      "Helvetica Neue",
      "sans-serif",
    ].join(","),
    h4: {
      fontWeight: 600,
    },
    h5: {
      fontWeight: 600,
    },
    h6: {
      fontWeight: 600,
    },
  },
  components: {
    MuiButton: {
      styleOverrides: {
        root: {
          textTransform: "none",
          borderRadius: "8px",
        },
      },
    },
    MuiTextField: {
      styleOverrides: {
        root: {
          "& .MuiOutlinedInput-root": {
            borderRadius: "8px",
          },
        },
      },
    },
  },
})

export default theme