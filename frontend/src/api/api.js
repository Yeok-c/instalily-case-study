// Get base URL from environment or use a fallback that works in both development and production
const API_BASE_URL = process.env.REACT_APP_API_URL || window.location.origin;

/**
 * Send a user query to the AI service and get a response
 * @param {string} userQuery - The user's question or request
 * @param {Array} [conversationHistory=[]] - Previous messages in the conversation 
 * @param {Object} [options={}] - Additional options like retries
 * @returns {Object} The AI response message object
 */
export const getAIMessage = async (userQuery, conversationHistory = [], options = {}) => {
  try {
    console.log(`Sending request to ${API_BASE_URL}/api/query with conversation history`);
    
    // Format the conversation history for the API
    const formattedHistory = conversationHistory
      .filter(msg => !msg.isLoading) // Filter out any loading messages
      .map(msg => ({
        role: msg.role,
        content: msg.content
      }));
    
    const response = await fetch(`${API_BASE_URL}/api/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ 
        query: userQuery,
        conversation_history: formattedHistory 
      }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`Server responded with ${response.status}: ${errorText}`);
      throw new Error(`HTTP error! Status: ${response.status}`);
    }

    const data = await response.json();
    
    return {
      role: "assistant",
      content: data.response || "Sorry, I couldn't process your request.",
      timestamp: new Date().toISOString()
    };
  } catch (error) {
    console.error("Error querying AI:", error);
    return {
      role: "assistant",
      content: `Sorry, I encountered an error while processing your request: ${error.message}. Please try again later.`,
      timestamp: new Date().toISOString()
    };
  }
};

/**
 * Formats a user message object
 * @param {string} content - Message content
 * @returns {Object} Formatted user message
 */
export const createUserMessage = (content) => {
  return {
    role: "user",
    content,
    timestamp: new Date().toISOString()
  };
};