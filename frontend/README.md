# LOC Chronicling America Frontend

A React-based frontend for the Library of Congress Chronicling America project, designed to help users explore historical Congressional bills and documents from America's early legislative history (1789-1821).

## Features

- **Clean, Modern Interface**: Built with Material-UI components
- **Bilingual Support**: English and Spanish language toggle
- **Responsive Design**: Works on desktop and mobile devices
- **Interactive FAQ Examples**: Quick-start questions to guide users
- **Source Citations**: Displays source documents for bot responses
- **Markdown Support**: Rich text formatting for bot responses

## Getting Started

### Prerequisites

- Node.js (version 14 or higher)
- npm or yarn

### Installation

1. Navigate to the frontend directory:
```bash
cd LOC_prototype/frontend
```

2. Install dependencies:
```bash
npm install
```

3. Configure the API endpoint by creating a `.env` file:
```bash
REACT_APP_API_BASE_URL=https://your-api-gateway-url.amazonaws.com
```

4. Start the development server:
```bash
npm start
```

The application will open in your browser at `http://localhost:3000`.

### Building for Production

```bash
npm run build
```

This creates a `build` folder with optimized production files.

## Project Structure

```
src/
├── components/           # React components
│   ├── MainChat.jsx     # Main layout component
│   ├── LeftNav.jsx      # Sidebar navigation
│   ├── ChatBody.jsx     # Chat interface
│   ├── BotReply.jsx     # Bot message component
│   ├── UserReply.jsx    # User message component
│   ├── FAQExamples.jsx  # Example questions
│   └── MarkdownContent.jsx # Markdown renderer
├── utilities/
│   └── constants.js     # Colors, text, and configuration
├── services/
│   └── chatService.js   # API communication
├── App.js              # Main app component
├── theme.js            # Material-UI theme
└── index.js            # React entry point
```

## Configuration

### API Endpoint

Update the `REACT_APP_API_BASE_URL` environment variable to point to your deployed backend API.

### Customization

- **Colors**: Modify `src/utilities/constants.js` to change the color scheme
- **Text Content**: Update the `getCurrentText` function in constants.js for different languages
- **FAQ Examples**: Edit the FAQ items in `FAQExamples.jsx`

## Example Queries

- "What is bill HR 1 from congress 6?"
- "Show me bills about taxation from the early congresses"
- "What were the main issues discussed in congress 10?"
- "Find bills related to commerce and trade"

## Technology Stack

- **React 18**: Frontend framework
- **Material-UI**: Component library
- **React Markdown**: Markdown rendering
- **React Router**: Navigation

## License

This project is part of the Library of Congress Chronicling America initiative.