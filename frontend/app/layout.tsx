import ClientThemeProvider from "./components/ThemeProvider"
import './globals.css'

export const metadata = {
  title: 'Library of Congress AI Chatbot',
  description: 'AI-powered historical document research with persona-based responses',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <head>
        <link
          href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700&display=swap"
          rel="stylesheet"
        />
      </head>
      <body>
        <ClientThemeProvider>
          {children}
        </ClientThemeProvider>
      </body>
    </html>
  )
}