/**
 * Chat history utilities for storing and retrieving conversations
 */

// Key used for localStorage
const CHAT_HISTORY_KEY = 'instalily_chat_history';

/**
 * Get all stored chat histories
 * @returns {Array} Array of chat session objects
 */
export const getAllChatHistories = () => {
  try {
    const storedData = localStorage.getItem(CHAT_HISTORY_KEY);
    if (!storedData) return [];
    return JSON.parse(storedData);
  } catch (error) {
    console.error("Error retrieving chat history:", error);
    return [];
  }
};

/**
 * Save a new chat session or update an existing one
 * @param {Object} chatSession - The chat session to save
 * @param {string} chatSession.id - Unique identifier for the chat session
 * @param {string} chatSession.title - Title of the chat session 
 * @param {Array} chatSession.messages - Array of message objects
 * @param {Date} chatSession.lastUpdated - When the chat was last updated
 */
export const saveChatSession = (chatSession) => {
  try {
    // Get existing chat history
    const histories = getAllChatHistories();
    
    // Find index of session with matching id if it exists
    const existingIndex = histories.findIndex(session => session.id === chatSession.id);
    
    if (existingIndex >= 0) {
      // Update existing session
      histories[existingIndex] = { 
        ...histories[existingIndex], 
        ...chatSession,
        lastUpdated: new Date().toISOString()
      };
    } else {
      // Add new session
      histories.push({
        ...chatSession,
        lastUpdated: new Date().toISOString()
      });
    }
    
    // Sort by last updated date (most recent first)
    histories.sort((a, b) => new Date(b.lastUpdated) - new Date(a.lastUpdated));
    
    // Store back to localStorage
    localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(histories));
    
    return true;
  } catch (error) {
    console.error("Error saving chat history:", error);
    return false;
  }
};

/**
 * Delete a specific chat session by ID
 * @param {string} sessionId - ID of the chat session to delete
 * @returns {boolean} Success status
 */
export const deleteChatSession = (sessionId) => {
  try {
    const histories = getAllChatHistories();
    const filteredHistories = histories.filter(session => session.id !== sessionId);
    
    localStorage.setItem(CHAT_HISTORY_KEY, JSON.stringify(filteredHistories));
    return true;
  } catch (error) {
    console.error("Error deleting chat session:", error);
    return false;
  }
};

/**
 * Clear all stored chat histories
 * @returns {boolean} Success status
 */
export const clearAllChatHistories = () => {
  try {
    localStorage.removeItem(CHAT_HISTORY_KEY);
    return true;
  } catch (error) {
    console.error("Error clearing chat histories:", error);
    return false;
  }
};

/**
 * Generate a simple UUID for chat session IDs
 * @returns {string} A UUID string
 */
export const generateSessionId = () => {
  return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, (c) => {
    const r = Math.random() * 16 | 0;
    const v = c === 'x' ? r : (r & 0x3 | 0x8);
    return v.toString(16);
  });
};

/**
 * Create an initial chat message to welcome the user
 * @returns {Object} Welcome message object
 */
export const createWelcomeMessage = () => {
  return {
    id: generateSessionId(),
    role: 'assistant',
    content: 'Hello! I\'m your appliance parts assistant. How can I help you today?',
    timestamp: new Date().toISOString()
  };
};