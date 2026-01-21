'use client'

import { ThemeProvider } from "@mui/material/styles"
import { CssBaseline } from "@mui/material"
import theme from "../config/theme"

export default function ClientThemeProvider({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <ThemeProvider theme={theme}>
      <CssBaseline />
      {children}
    </ThemeProvider>
  )
}