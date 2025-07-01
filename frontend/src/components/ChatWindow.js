import React, { useState, useEffect, useRef } from "react";
import "./ChatWindow.css";
import { getAIMessage } from "../api/api";
import { marked } from "marked";

function ChatWindow() {
  const defaultMessage = [{
    role: "assistant",
    content: "Hi, I'm your appliance parts and repair assistant. How can I help you today?"
  }];

  const [messages, setMessages] = useState(defaultMessage);
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSend = async (e) => {
    e.preventDefault();
    
    if (input.trim() === "") return;
    
    // Add user message to chat
    const userMessage = { role: "user", content: input };
    setMessages(prevMessages => [...prevMessages, userMessage]);
    
    // Clear input field
    setInput("");
    
    // Show loading indicator
    setIsLoading(true);
    
    try {
      // Add a temporary loading message
      setMessages(prevMessages => [
        ...prevMessages, 
        { role: "assistant", content: "Thinking...", isLoading: true }
      ]);
      
      // Get response from AI
      const aiResponse = await getAIMessage(userMessage.content);
      
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
          content: "Sorry, I encountered an error. Please try again later." 
        }
      ]);
    } finally {
      setIsLoading(false);
    }
  };

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
  }, []);

  // Helper function to render a product card from JSON
  const renderProductCard = (product) => {
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
  };

  // Helper function to render a list of products
  const renderProductList = (products) => {
    if (products.length === 0) return '<p>No products found</p>';
    
    return `
      <div class="product-list">
        ${products.map(product => renderProductCard(product)).join('')}
      </div>
    `;
  };

  return (
    <div className="messages-container">
      {messages.map((message, index) => (
        <div key={index} className={`${message.role}-message-container`}>
          {message.content && (
            <div className={`message ${message.role}-message ${message.isLoading ? 'loading' : ''}`}>
              <div dangerouslySetInnerHTML={{
                __html: marked(message.content).replace(/<p>|<\/p>/g, "")
              }}></div>
            </div>
          )}
        </div>
      ))}
      <div ref={messagesEndRef} />
      <div className="input-area">
        <form onSubmit={handleSend}>
          <input
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Type a message..."
            disabled={isLoading}
          />
          <button 
            className="send-button" 
            type="submit"
            disabled={isLoading}
          >
            Send
          </button>
        </form>
      </div>
    </div>
  );
}

export default ChatWindow;