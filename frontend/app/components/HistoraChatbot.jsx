'use client'

import { useState, useRef, useEffect } from 'react';
import { svgPaths, svgPathsHeader } from '../config/svg-paths.js';

// Placeholder for missing Figma asset
const imgChatGptImageJul302025125524Pm1 = "data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iNDAiIGhlaWdodD0iNDAiIHZpZXdCb3g9IjAgMCA0MCA0MCIgZmlsbD0ibm9uZSIgeG1sbnM9Imh0dHA6Ly93d3cudzMub3JnLzIwMDAvc3ZnIj4KPGNpcmNsZSBjeD0iMjAiIGN5PSIyMCIgcj0iMjAiIGZpbGw9IiNFRkUzRDMiLz4KPHN2ZyB4PSIxMCIgeT0iOSIgd2lkdGg9IjIwIiBoZWlnaHQ9IjIzIiB2aWV3Qm94PSIwIDAgMjAgMjMiIGZpbGw9Im5vbmUiPgo8cGF0aCBkPSJNMTAgMEMxNS41MjMgMCAyMCA0LjQ3NyAyMCAxMEMyMCAxNS41MjMgMTUuNTIzIDIwIDEwIDIwQzQuNDc3IDIwIDAgMTUuNTIzIDAgMTBDMCA0LjQ3NyA0LjQ3NyAwIDEwIDBaIiBmaWxsPSIjMjgzMzNBIi8+CjxjaXJjbGUgY3g9IjciIGN5PSI4IiByPSIyIiBmaWxsPSJ3aGl0ZSIvPgo8Y2lyY2xlIGN4PSIxMyIgY3k9IjgiIHI9IjIiIGZpbGw9IndoaXRlIi8+CjxwYXRoIGQ9Ik02IDEzQzYgMTMgOCAxNSAxMCAxNUMxMiAxNSAxNCAxMyAxNCAxMyIgc3Ryb2tlPSJ3aGl0ZSIgc3Ryb2tlLXdpZHRoPSIyIiBzdHJva2UtbGluZWNhcD0icm91bmQiLz4KPC9zdmc+Cjwvc3ZnPgo=";

export default function HistoraChatbot() {
  const [messages, setMessages] = useState([
    {
      id: '1',
      type: 'bot',
      content: (
        <div>
          <p className="mb-0">
            <span className="font-bold">Hi, I'm Histora — your AI assistant!</span>
            <br />
            <br />
          </p>
          <p className="mb-0">I'm here to help you dive deeper into the content on this page.</p>
          <p className="mb-0">To tailor the experience to your learning style, could you tell me your age group?</p>
          <p className="mb-0">&nbsp;</p>
          <p className="font-semibold">Please select one to get started:</p>
        </div>
      ),
      timestamp: new Date()
    }
  ]);
  const [conversationState, setConversationState] = useState('initial');
  const [inputValue, setInputValue] = useState('');
  const [isMinimized, setIsMinimized] = useState(false);
  const [isFullscreen, setIsFullscreen] = useState(false);
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);
  const chatContainerRef = useRef(null);

  // Auto-scroll to bottom when new messages arrive
  useEffect(() => {
    if (chatContainerRef.current) {
      chatContainerRef.current.scrollTo({
        top: chatContainerRef.current.scrollHeight,
        behavior: 'smooth'
      });
    }
  }, [messages, isTyping]);

  const handleAgeSelection = (ageGroup) => {
    // Add user message
    const userMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: ageGroup,
      timestamp: new Date()
    };

    // Simulate typing delay for bot response
    setMessages(prev => [...prev, userMessage]);
    setIsTyping(true);
    
    setTimeout(() => {
      const botMessage = {
        id: (Date.now() + 1).toString(),
        type: 'bot',
        content: (
          <div>
            <p className="mb-0">Awesome! Let's explore U.S. Constitution history in a fun and simple way. Here are some topics you can tap to learn more about:</p>
          </div>
        ),
        timestamp: new Date()
      };
      setMessages(prev => [...prev, botMessage]);
      setConversationState('age-selected');
      setIsTyping(false);
    }, 800);
  };

  const handleTopicSelection = (topic) => {
    // Add user message
    const userMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: topic,
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage]);
    setIsTyping(true);

    // Simulate typing delay for bot response
    setTimeout(() => {
      const botMessage = {
        id: (Date.now() + 1).toString(),
        type: 'bot',
        content: getTopicContent(topic),
        timestamp: new Date()
      };
      setMessages(prev => [...prev, botMessage]);
      setConversationState('topic-selected');
      setIsTyping(false);
    }, 1000);
  };

  const getTopicContent = (topic) => {
    if (topic === 'First Amendment') {
      return (
        <div>
          <p className="font-bold mb-0">Okay, let's explore the First Amendment!</p>
          <p className="mb-0">&nbsp;</p>
          <p className="mb-0">The First Amendment is part of the U.S. Constitution. It gives us some of the most important freedoms we have in America.</p>
          <p className="mb-0">&nbsp;</p>
          <p className="italic mb-0">Here's what it says (in fancy legal words):</p>
          <p className="mb-0">&nbsp;</p>
          <p className="mb-0">"Congress shall make no law respecting an establishment of religion, or prohibiting the free exercise thereof; or abridging the freedom of speech, or of the press; or the right of the people peaceably to assemble, and to petition the Government for a redress of grievances."</p>
          <p className="mb-0">&nbsp;</p>
          <p className="font-bold mb-0">That's a lot of big words — so let's break it down into 5 key freedoms:</p>
          <p className="mb-0">&nbsp;</p>
          <p className="font-bold mb-0">What freedoms does it give you?<br /><br /></p>
          <ol className="list-decimal mb-0" start={1}>
            <li className="mb-2 ms-[21px]">
              <span className="font-bold">Freedom of Religion</span>
              <span> – You can follow any religion you want, or none at all. The government can't tell you what to believe.</span>
            </li>
            <li className="mb-2 ms-[21px]">
              <span className="font-bold">Freedom of Speech </span>
              <span>– You can say what you think (as long as it doesn't hurt others or break the law).</span>
            </li>
            <li className="mb-2 ms-[21px]">
              <span className="font-bold">Freedom of the Press </span>
              <span>– News reporters and websites can share information freely, even if it criticizes the government.</span>
            </li>
            <li className="mb-2 ms-[21px]">
              <span className="font-bold">Freedom to Assemble </span>
              <span>– People can meet in groups, go to protests, or have public gatherings peacefully.</span>
            </li>
            <li className="ms-[21px]">
              <span className="font-bold">Freedom to Petition the Government </span>
              <span>– If something isn't fair, you can ask the government to fix it.</span>
            </li>
          </ol>
          <p className="mb-0">&nbsp;</p>
          <p className="font-bold mb-0">Why it matters:</p>
          <p className="mb-0">
            The First Amendment helps make sure everyone has a voice.<br />
            It lets people share ideas, speak up for what they believe, and stay informed — without being afraid of the government stopping them.
          </p>
          <p className="mb-0">&nbsp;</p>
          <p>Would you like to learn more about one of these freedoms? Or see a real-life example of how it works?</p>
        </div>
      );
    } else {
      return (
        <div>
          <p className="font-bold mb-0">Let's explore the Fourteenth Amendment - Equal Protection!</p>
          <p className="mb-0">&nbsp;</p>
          <p>This amendment is one of the most important protections in American law, ensuring that all people are treated equally under the law.</p>
        </div>
      );
    }
  };

  const handleSendMessage = () => {
    if (!inputValue.trim()) return;

    const userMessage = {
      id: Date.now().toString(),
      type: 'user',
      content: inputValue,
      timestamp: new Date()
    };

    const botMessage = {
      id: (Date.now() + 1).toString(),
      type: 'bot',
      content: "That's a great question! I'm here to help you explore the content in more depth. Feel free to ask me anything about the topics we've discussed!",
      timestamp: new Date()
    };

    setMessages(prev => [...prev, userMessage, botMessage]);
    setInputValue('');
  };

  return (
    <div className={`bg-[#f4eee5] flex flex-col rounded-[10px] shadow-[-1px_2px_6px_0px_rgba(0,0,0,0.25)] transition-all duration-300 ${isFullscreen ? 'fixed inset-0 z-50 w-screen h-screen rounded-none' : 'w-[509px] h-[600px]'}`}>
      {/* Header */}
      <div className="bg-[#28333a] flex h-[60px] items-center justify-between leading-[0] px-[32px] py-[10px] rounded-tl-[10px] rounded-tr-[10px] shrink-0">
        <div className="grid-cols-[max-content] grid-rows-[max-content] inline-grid place-items-start relative shrink-0">
          <p className="[grid-area:1_/_1] font-['Inter:Semi_Bold',sans-serif] font-semibold leading-[1.35] ml-[125.5px] mt-[9px] not-italic relative text-[16px] text-center text-nowrap text-white translate-x-[-50%]">
            Histora AI Chatbot
          </p>
          <div className="[grid-area:1_/_1] grid-cols-[max-content] grid-rows-[max-content] inline-grid leading-[0] ml-0 mt-0 place-items-start relative">
            <div className="[grid-area:1_/_1] ml-0 mt-0 relative size-[40px]">
              <svg className="block size-full" fill="none" preserveAspectRatio="none" viewBox="0 0 40 40">
                <circle cx="20" cy="20" fill="#EFE3D3" r="20" />
              </svg>
            </div>
            <div className="[grid-area:1_/_1] h-[23px] ml-[10px] mt-[9px] relative w-[20px]">
              <div className="absolute inset-0 overflow-hidden pointer-events-none">
                <img alt="" className="absolute h-[117.16%] left-[-17.78%] max-w-none top-[-8.58%] w-[136.9%]" src={imgChatGptImageJul302025125524Pm1} />
              </div>
            </div>
          </div>
        </div>
        
        <div className="grid-cols-[max-content] grid-rows-[max-content] inline-grid place-items-start relative shrink-0">
          <div className="[grid-area:1_/_1] relative size-[24px] ml-[108px] mt-0">
            <button 
              className="hover:opacity-70 transition-opacity w-full h-full"
              aria-label="Close"
            >
              <svg className="block size-full" fill="none" preserveAspectRatio="none" viewBox="0 0 24 24">
                <path d={svgPathsHeader.pb2ba0a0} stroke="white" strokeLinecap="round" strokeLinejoin="round" strokeWidth="2" />
              </svg>
            </button>
          </div>
          <div className="[grid-area:1_/_1] h-[2px] ml-0 mt-[19px] relative w-[17px]">
            <button 
              onClick={() => setIsMinimized(!isMinimized)}
              className="absolute inset-[-12.5%_-1.47%] hover:opacity-70 transition-opacity"
              aria-label="Minimize"
            >
              <svg className="block size-full" fill="none" preserveAspectRatio="none" viewBox="0 0 17.5 2.5">
                <path d={svgPathsHeader.p1c3cbe00} fill="white" stroke="white" strokeWidth="0.5" />
              </svg>
            </button>
          </div>
          <div className="[grid-area:1_/_1] flex items-center justify-center ml-[51px] mt-0 relative size-[24px]">
            <button
              onClick={() => setIsFullscreen(!isFullscreen)}
              className="flex-none rotate-[90deg] hover:opacity-70 transition-opacity"
              aria-label="Fullscreen"
            >
              <div className="relative size-[24px]">
                <svg className="block size-full" fill="none" preserveAspectRatio="none" viewBox="0 0 24 24">
                  <path d={svgPathsHeader.p2c72ae00} fill="white" />
                </svg>
              </div>
            </button>
          </div>
        </div>
      </div>

      {/* Chat Messages */}
      <div className="flex-1 overflow-y-auto px-[29.5px] py-[29px]" ref={chatContainerRef}>
        <div className="flex flex-col gap-[30px]">
          {messages.map((message, index) => (
            <div key={message.id}>
              {message.type === 'bot' && (
                <div className="font-['Inter:Regular',sans-serif] text-[14px] text-black leading-[1.35]">
                  {message.content}
                </div>
              )}
              {message.type === 'user' && (
                <div className="flex justify-end">
                  <div className="bg-[#28333a] px-[18px] py-[8px] rounded-[30px] max-w-[80%]">
                    <p className="font-['Inter:Regular',sans-serif] text-[14px] text-white leading-[1.35] m-0">
                      {message.content}
                    </p>
                  </div>
                </div>
              )}
              
              {/* Show age selection buttons after initial message */}
              {index === 0 && conversationState === 'initial' && (
                <div className="flex gap-[17px] mt-[17px]">
                  <button
                    onClick={() => handleAgeSelection('K-12 Student')}
                    className="bg-[rgba(198,156,115,0.3)] h-[34px] px-[19px] py-[7px] rounded-[30px] hover:bg-[rgba(198,156,115,0.4)] transition-colors"
                  >
                    <p className="font-['Inter:Regular',sans-serif] text-[14px] text-black leading-[1.35] m-0">K-12 Student</p>
                  </button>
                  <button
                    onClick={() => handleAgeSelection('College or Adult Learner')}
                    className="bg-[rgba(198,156,115,0.3)] h-[34px] px-[19px] py-[7px] rounded-[30px] hover:bg-[rgba(198,156,115,0.4)] transition-colors"
                  >
                    <p className="font-['Inter:Regular',sans-serif] text-[14px] text-black leading-[1.35] m-0">College or Adult Learner</p>
                  </button>
                </div>
              )}

              {/* Show topic selection buttons after age selection response */}
              {message.type === 'bot' && index === 2 && conversationState === 'age-selected' && (
                <div className="flex flex-col gap-[17px] mt-[17px]">
                  <button
                    onClick={() => handleTopicSelection('First Amendment')}
                    className="bg-[rgba(198,156,115,0.3)] h-[34px] px-[19px] rounded-[30px] text-left hover:bg-[rgba(198,156,115,0.4)] transition-colors w-fit"
                  >
                    <p className="font-['Inter:Regular',sans-serif] text-[14px] text-black leading-[1.35] m-0">First Amendment</p>
                  </button>
                  <button
                    onClick={() => handleTopicSelection('Fourteenth Amendment - Equal Protection')}
                    className="bg-[rgba(198,156,115,0.3)] h-[34px] px-[19px] rounded-[30px] text-left hover:bg-[rgba(198,156,115,0.4)] transition-colors w-fit"
                  >
                    <p className="font-['Inter:Regular',sans-serif] text-[14px] text-black leading-[1.35] m-0">Fourteenth Amendment - Equal Protection</p>
                  </button>
                </div>
              )}
            </div>
          ))}
          {isTyping && (
            <div className="flex items-center gap-2">
              <div className="bg-[rgba(198,156,115,0.2)] px-[18px] py-[10px] rounded-[20px]">
                <div className="flex gap-1">
                  <div className="w-2 h-2 bg-[#28333a] rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></div>
                  <div className="w-2 h-2 bg-[#28333a] rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></div>
                  <div className="w-2 h-2 bg-[#28333a] rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></div>
                </div>
              </div>
            </div>
          )}
          <div ref={messagesEndRef} />
        </div>
      </div>

      {/* Input Area */}
      <div className="px-[32px] pb-[29px] shrink-0">
        <div className="bg-[rgba(93,85,67,0.1)] flex h-[46px] items-center justify-between px-[12px] py-[6px] rounded-[10px]">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => e.key === 'Enter' && handleSendMessage()}
            placeholder="Type your question..."
            className="flex-1 bg-transparent font-['Inter:Regular',sans-serif] text-[14px] text-black placeholder:text-[#737376] leading-[1.35] outline-none"
          />
          <button
            onClick={handleSendMessage}
            className="flex items-center justify-center size-[33.944px] hover:opacity-70 transition-opacity"
            aria-label="Send message"
          >
            <div className="rotate-[45deg]">
              <svg className="block w-[24px] h-[24px]" fill="none" preserveAspectRatio="none" viewBox="0 0 24.0031 24.0014">
                <path clipRule="evenodd" d={svgPaths.p3c5b50c0} fill="#28333A" fillRule="evenodd" />
              </svg>
            </div>
          </button>
        </div>
      </div>
    </div>
  );
}