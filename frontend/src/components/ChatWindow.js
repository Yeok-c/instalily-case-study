import React, { useState, useEffect, useRef, useMemo, useCallback } from "react";
import "./ChatWindow.css";
import { getAIMessage } from "../api/api";
import { marked } from "marked";

function ChatWindow() {
  // Storage key for chat history
  const CHAT_HISTORY_KEY = 'instalily_chat_history';
  const CURRENT_SESSION_KEY = 'instalily_current_session';

  // Use useMemo to prevent recreation of defaultMessage on every render
  const defaultMessage = useMemo(() => [{
    role: "assistant",
    content: "Hi, I'm your appliance parts and repair assistant. How can I help you today?",
    timestamp: new Date().toISOString()
  }], []);

  // Main state variables
  const [messages, setMessages] = useState(defaultMessage);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [chatHistory, setChatHistory] = useState([]);
  const [currentSessionId, setCurrentSessionId] = useState(null);
  const [showHistory, setShowHistory] = useState(false);

  const messagesEndRef = useRef(null);
  const inputRef = useRef(null);
  
  // Store previous state to avoid infinite loops
  const prevMessagesRef = useRef(messages);
  const prevSessionIdRef = useRef(currentSessionId);

  // Helper function to generate a unique session ID
  const generateSessionId = () => {
    return Date.now().toString(36) + Math.random().toString(36).substring(2);
  };

  // Initialize chat history and load previous session if available
  useEffect(() => {
    // Load chat history from localStorage
    const storedHistory = localStorage.getItem(CHAT_HISTORY_KEY);
    const history = storedHistory ? JSON.parse(storedHistory) : [];
    setChatHistory(history);

    // Try to load last active session
    const storedSessionId = localStorage.getItem(CURRENT_SESSION_KEY);
    
    if (storedSessionId && history.some(session => session.id === storedSessionId)) {
      const session = history.find(s => s.id === storedSessionId);
      setMessages(session.messages);
      setCurrentSessionId(storedSessionId);
    } else {
      // Start a new session if no valid stored session
      const newSessionId = generateSessionId();
      setCurrentSessionId(newSessionId);
      
      // Create new session with default welcome message
      const newSession = {
        id: newSessionId,
        title: "New Conversation",
        messages: defaultMessage,
        timestamp: new Date().toISOString()
      };
      
      // Save to chat history
      const updatedHistory = [newSession, ...history];
      setChatHistory(updatedHistory);
      localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(updatedHistory));
      localStorage.setItem(CURRENT_SESSION_KEY, newSessionId);
    }
  }, [defaultMessage]); // defaultMessage is now memoized so it won't change between renders

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  // Save current session whenever messages change
  useEffect(() => {
    // Skip if no session is active
    if (!currentSessionId || messages.length === 0) return;
    
    // Skip if messages haven't actually changed
    if (
      prevMessagesRef.current === messages && 
      prevSessionIdRef.current === currentSessionId
    ) {
      return;
    }
    
    // Update refs with current values
    prevMessagesRef.current = messages;
    prevSessionIdRef.current = currentSessionId;
    
    // Use a function to get the latest chatHistory state
    const updateSessionInStorage = () => {
      // Get the most up-to-date data from localStorage
      const storedData = localStorage.getItem(CHAT_HISTORY_KEY);
      const storedHistory = storedData ? JSON.parse(storedData) : [];
      
      const sessionIndex = storedHistory.findIndex(s => s.id === currentSessionId);
      if (sessionIndex === -1) return;
      
      // Get current session
      const currentSession = storedHistory[sessionIndex];
      
      // Generate title from first user message if not custom set
      let title = currentSession.title;
      if (title === "New Conversation") {
        const firstUserMessage = messages.find(m => m.role === "user");
        if (firstUserMessage) {
          title = firstUserMessage.content.split(" ").slice(0, 4).join(" ") + "...";
        }
      }
      
      // Skip if nothing changed
      if (
        JSON.stringify(currentSession.messages) === JSON.stringify(messages) && 
        currentSession.title === title
      ) {
        return;
      }
      
      // Update the session in our local copy
      const updatedSession = {
        ...currentSession,
        title,
        messages,
        timestamp: new Date().toISOString()
      };
      
      storedHistory[sessionIndex] = updatedSession;
      
      // Save to localStorage
      localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(storedHistory));
      
      // Only update state if it's different from current state
      setChatHistory(prev => {
        const currentJSON = JSON.stringify(prev);
        const updatedJSON = JSON.stringify(storedHistory);
        return currentJSON === updatedJSON ? prev : storedHistory;
      });
    };
    
    updateSessionInStorage();
  }, [messages, currentSessionId]);
  
  // Update the handleSend function to send conversation history
  const handleSend = async (e) => {
    e.preventDefault();
    
    if (input.trim() === "") return;
    
    // Add user message to chat
    const userMessage = { 
      role: "user", 
      content: input,
      timestamp: new Date().toISOString()
    };
    
    // Add user message to the chat immediately
    const updatedMessages = [...messages, userMessage];
    setMessages(updatedMessages);
    
    // Clear input field
    setInput("");
    
    // Show loading indicator
    setIsLoading(true);
    
    try {
      // Add a loading message (now without text content)
      const messagesWithLoading = [...updatedMessages, { role: "assistant", isLoading: true }];
      setMessages(messagesWithLoading);
      
      // Get response from AI - send conversation context
      // We're sending all previous messages except the loading one
      const aiResponse = await getAIMessage(
        userMessage.content,
        updatedMessages // Send the conversation history including the new message
      );
      
      // Remove the loading message and add the real response
      setMessages(prevMessages => [
        ...prevMessages.filter(msg => !msg.isLoading),
        aiResponse
      ]);
    } catch (error) {
      console.error("Error getting AI response:", error);
      
      // Remove the loading message and add an error message
      setMessages(prevMessages => [
        ...prevMessages.filter(msg => !msg.isLoading),
        { 
          role: "assistant", 
          content: "Sorry, I encountered an error. Please try again later.",
          timestamp: new Date().toISOString()
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

  // Start a new chat session
  const startNewChat = useCallback(() => {
    const newSessionId = generateSessionId();
    
    const newSession = {
      id: newSessionId,
      title: "New Conversation",
      messages: defaultMessage,
      timestamp: new Date().toISOString()
    };
    
    // Add new session to history
    setChatHistory(prevHistory => {
      const updatedHistory = [newSession, ...prevHistory];
      localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(updatedHistory));
      return updatedHistory;
    });
    
    // Set as current session
    setCurrentSessionId(newSessionId);
    localStorage.setItem(CURRENT_SESSION_KEY, newSessionId);
    
    // Reset messages to default
    setMessages(defaultMessage);
    
    // Focus input field
    inputRef.current?.focus();
    
    // Hide history panel on mobile
    setShowHistory(false);
  }, [defaultMessage]);

  // Load a specific chat session
  const loadSession = useCallback((sessionId) => {
    setChatHistory(prevHistory => {
      const session = prevHistory.find(s => s.id === sessionId);
      if (session) {
        setMessages(session.messages);
        setCurrentSessionId(sessionId);
        localStorage.setItem(CURRENT_SESSION_KEY, sessionId);
        
        // Hide history panel on mobile after selection
        setShowHistory(false);
        
        // Focus input field
        inputRef.current?.focus();
      }
      return prevHistory;
    });
  }, []);

  // Delete a chat session
  const deleteSession = useCallback((e, sessionId) => {
    e.stopPropagation(); // Prevent triggering loadSession
    
    setChatHistory(prevHistory => {
      const updatedHistory = prevHistory.filter(session => session.id !== sessionId);
      localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(updatedHistory));
      
      // If we're deleting the current session, switch to another or create new
      if (sessionId === currentSessionId) {
        if (updatedHistory.length > 0) {
          // Switch to first available session
          setMessages(updatedHistory[0].messages);
          setCurrentSessionId(updatedHistory[0].id);
          localStorage.setItem(CURRENT_SESSION_KEY, updatedHistory[0].id);
        } else {
          // No sessions left, create a new one
          // Call in a setTimeout to avoid state updates during render
          setTimeout(() => startNewChat(), 0);
        }
      }
      
      return updatedHistory;
    });
  }, [currentSessionId, startNewChat]);

  // Format timestamp to readable time
  const formatTime = useCallback((timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
  }, []);

  // Format date for chat history
  const formatDate = useCallback((timestamp) => {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleDateString();
  }, []);

  // Helper function to render a product card from JSON - wrapped in useCallback
  const renderProductCard = useCallback((product) => {
    return `
      <div class="product-card">
        <div class="product-header">
          <h3>${product.part_name || product.name || 'Product'}</h3>
          <span class="product-price">${product.price || ''}</span>
        </div>
        ${product.image_url ? `<img src="${product.image_url}" alt="${product.part_name || 'Product'}" class="product-image" />` : ''}
        <div class="product-details">
          ${product.manufacturer_number ? `<p><strong>Manufacturer #:</strong> ${product.manufacturer_number}</p>` : ''}
          ${product.partselect_number ? `<p><strong>PartSelect #:</strong> ${product.partselect_number}</p>` : ''}
          ${product.description ? `<p>${product.description}</p>` : ''}
          ${product.url ? `<a href="${product.url}" target="_blank" class="product-link">View Details</a>` : ''}
        </div>
      </div>
    `;
  }, []);

  // Helper function to render a list of products - wrapped in useCallback
  const renderProductList = useCallback((products) => {
    if (products.length === 0) return '<p>No products found</p>';
    
    return `
      <div class="product-list">
        ${products.map(product => renderProductCard(product)).join('')}
      </div>
    `;
  }, [renderProductCard]);

  // Custom renderer for JSON blocks
  useEffect(() => {
    const renderer = new marked.Renderer();
    const originalCodeRenderer = renderer.code;
    
    renderer.code = function(code, language) {
      if (language === 'json-to-render' || language === 'dictionary-list-to-render') {
        try {
          const jsonData = JSON.parse(code);
          if (Array.isArray(jsonData)) {
            return renderProductList(jsonData);
          } else {
            return renderProductCard(jsonData);
          }
        } catch (e) {
          console.error("Failed to parse JSON:", e);
          return originalCodeRenderer.call(this, code, language);
        }
      }
      return originalCodeRenderer.call(this, code, language);
    };
    
    marked.setOptions({ renderer });
  }, [renderProductCard, renderProductList]); // Now these dependencies won't change on every render

  return (
    <div className="chat-layout">
      {/* Chat History Sidebar */}
      <div className={`chat-history ${showHistory ? 'show' : ''}`}>
        <div className="history-header">
          <h2>Chat History</h2>
          <button 
            className="new-chat-button" 
            onClick={startNewChat}
          >
            + New Chat
          </button>
          <button 
            className="close-history" 
            onClick={() => setShowHistory(false)}
          >
            &times;
          </button>
        </div>
        <div className="history-list">
          {chatHistory.length === 0 ? (
            <div className="no-history">No previous chats</div>
          ) : (
            chatHistory.map(session => (
              <div 
                key={session.id} 
                className={`history-item ${session.id === currentSessionId ? 'active' : ''}`}
                onClick={() => loadSession(session.id)}
              >
                <div className="history-item-content">
                  <div className="history-title">{session.title}</div>
                  <div className="history-date">{formatDate(session.timestamp)}</div>
                </div>
                <button 
                  className="delete-session" 
                  onClick={(e) => deleteSession(e, session.id)}
                  aria-label="Delete conversation"
                >
                  &times;
                </button>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Main Chat Area */}
      <div className="messages-wrapper">
        <div className="chat-header">
          <button 
            className="history-toggle"
            onClick={() => setShowHistory(!showHistory)}
            aria-label="Toggle chat history"
          >
            ☰
          </button>
          <h1>Appliance Parts Assistant</h1>
        </div>

        <div className="messages-container">
          {messages.map((message, index) => (
            <div key={index} className={`${message.role}-message-container`}>
              {message.isLoading ? (
                <div className="message assistant-message loading">
                  <div className="loading-spinner">
                    <div></div>
                    <div></div>
                  </div>
                </div>
              ) : (
                message.content && (
                  <div className={`message ${message.role}-message`}>
                    <div dangerouslySetInnerHTML={{
                      __html: marked(message.content).replace(/<p>|<\/p>/g, "")
                    }}></div>
                    {message.timestamp && (
                      <div className="message-timestamp">{formatTime(message.timestamp)}</div>
                    )}
                  </div>
                )
              )}
            </div>
          ))}
          <div ref={messagesEndRef} />
          <div className="input-area">
            <form onSubmit={handleSend}>
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Type a message..."
                disabled={isLoading}
              />
              <button 
                className="send-button" 
                type="submit"
                disabled={isLoading || !input.trim()}
              >
                Send
              </button>
            </form>
          </div>
        </div>

      </div>
    </div>
  );
}

export default ChatWindow;