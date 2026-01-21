import React from 'react';
import ReactMarkdown from 'react-markdown';
import { Box, Typography, Link } from '@mui/material';
import { PRIMARY_MAIN } from '../config/constants';

function MarkdownContent({ content, className = '' }) {
  if (!content) return null;
  
  return (
    <Box className={`markdown-content ${className}`}>
      <ReactMarkdown
        components={{
          // Style links
          a: ({ children, href, ...props }) => (
            <Link 
              href={href} 
              target="_blank" 
              rel="noopener noreferrer"
              sx={{
                color: PRIMARY_MAIN,
                textDecoration: 'none',
                '&:hover': {
                  textDecoration: 'underline',
                },
              }}
              {...props}
            >
              {children}
            </Link>
          ),
          
          // Style code blocks - smaller font
          code: ({ children, ...props }) => (
            <Box
              component="code"
              sx={{
                backgroundColor: '#f5f5f5',
                padding: '2px 4px',
                borderRadius: '3px',
                fontSize: '0.8125rem', // 13px - smaller than default
                fontFamily: 'monospace',
                border: '1px solid #e0e0e0',
              }}
              {...props}
            >
              {children}
            </Box>
          ),
          
          // Style unordered lists - more compact
          ul: ({ children, ...props }) => (
            <Box
              component="ul"
              sx={{
                paddingLeft: '1.25rem', // Reduced from 1.5rem
                margin: '0.4rem 0', // Reduced from 0.5rem
                '& li': {
                  marginBottom: '0.2rem', // Reduced from 0.25rem
                  lineHeight: 1.6,
                },
              }}
              {...props}
            >
              {children}
            </Box>
          ),
          
          // Style ordered lists - more compact
          ol: ({ children, ...props }) => (
            <Box
              component="ol"
              sx={{
                paddingLeft: '1.25rem', // Reduced from 1.5rem
                margin: '0.4rem 0', // Reduced from 0.5rem
                '& li': {
                  marginBottom: '0.2rem', // Reduced from 0.25rem
                  lineHeight: 1.6,
                },
              }}
              {...props}
            >
              {children}
            </Box>
          ),
          
          // Style list items - smaller font size
          li: ({ children, ...props }) => (
            <Typography
              component="li"
              variant="body2"
              sx={{
                fontSize: '0.875rem', // 14px - smaller than default
                lineHeight: 1.6,
                marginBottom: '0.2rem',
              }}
              {...props}
            >
              {children}
            </Typography>
          ),
          
          // Style paragraphs - smaller font size
          p: ({ children, ...props }) => (
            <Typography
              variant="body2"
              sx={{
                fontSize: '0.875rem', // 14px - smaller than default
                lineHeight: 1.6,
                marginBottom: '0.6rem',
                '&:last-child': {
                  marginBottom: 0,
                },
              }}
              {...props}
            >
              {children}
            </Typography>
          ),
          
          // Style headings - smaller sizes appropriate for chatbot
          h1: ({ children, ...props }) => (
            <Typography
              variant="body1"
              component="h1"
              sx={{
                fontSize: '1.125rem', // 18px - equivalent to text-lg
                fontWeight: 'bold',
                marginBottom: '0.5rem',
                marginTop: '0.75rem',
                color: '#333',
                '&:first-of-type': {
                  marginTop: 0,
                },
              }}
              {...props}
            >
              {children}
            </Typography>
          ),
          
          h2: ({ children, ...props }) => (
            <Typography
              variant="body1"
              component="h2"
              sx={{
                fontSize: '1rem', // 16px - equivalent to text-base
                fontWeight: 'bold',
                marginBottom: '0.5rem',
                marginTop: '0.75rem',
                color: '#333',
                '&:first-of-type': {
                  marginTop: 0,
                },
              }}
              {...props}
            >
              {children}
            </Typography>
          ),
          
          h3: ({ children, ...props }) => (
            <Typography
              variant="body1"
              component="h3"
              sx={{
                fontSize: '0.9375rem', // 15px - equivalent to text-[15px]
                fontWeight: 'bold',
                marginBottom: '0.4rem',
                marginTop: '0.6rem',
                color: '#333',
                '&:first-of-type': {
                  marginTop: 0,
                },
              }}
              {...props}
            >
              {children}
            </Typography>
          ),
          
          h4: ({ children, ...props }) => (
            <Typography
              variant="body1"
              component="h4"
              sx={{
                fontSize: '0.875rem', // 14px - smaller than h3
                fontWeight: 'bold',
                marginBottom: '0.4rem',
                marginTop: '0.6rem',
                color: '#333',
                '&:first-of-type': {
                  marginTop: 0,
                },
              }}
              {...props}
            >
              {children}
            </Typography>
          ),
          
          h5: ({ children, ...props }) => (
            <Typography
              variant="body1"
              component="h5"
              sx={{
                fontSize: '0.875rem', // 14px - same as h4
                fontWeight: '600',
                marginBottom: '0.4rem',
                marginTop: '0.6rem',
                color: '#333',
                '&:first-of-type': {
                  marginTop: 0,
                },
              }}
              {...props}
            >
              {children}
            </Typography>
          ),
          
          h6: ({ children, ...props }) => (
            <Typography
              variant="body1"
              component="h6"
              sx={{
                fontSize: '0.875rem', // 14px - same as body text but bold
                fontWeight: '600',
                marginBottom: '0.4rem',
                marginTop: '0.6rem',
                color: '#333',
                '&:first-of-type': {
                  marginTop: 0,
                },
              }}
              {...props}
            >
              {children}
            </Typography>
          ),
          
          // Style strong/bold
          strong: ({ children, ...props }) => (
            <Box
              component="strong"
              sx={{
                fontWeight: 'bold',
              }}
              {...props}
            >
              {children}
            </Box>
          ),
          
          // Style emphasis/italic
          em: ({ children, ...props }) => (
            <Box
              component="em"
              sx={{
                fontStyle: 'italic',
              }}
              {...props}
            >
              {children}
            </Box>
          ),
          
          // Style blockquotes - more compact
          blockquote: ({ children, ...props }) => (
            <Box
              component="blockquote"
              sx={{
                borderLeft: `3px solid ${PRIMARY_MAIN}`,
                paddingLeft: '0.75rem',
                margin: '0.6rem 0',
                backgroundColor: '#f9f9f9',
                padding: '0.5rem 0.75rem',
                borderRadius: '0 3px 3px 0',
                fontStyle: 'italic',
                fontSize: '0.875rem', // Same as paragraph text
              }}
              {...props}
            >
              {children}
            </Box>
          ),
        }}
      >
        {content}
      </ReactMarkdown>
    </Box>
  );
}

export default MarkdownContent;