// Get base URL from environment or use a fallback that works in both development and production
const API_BASE_URL = process.env.REACT_APP_API_URL || window.location.origin;

export const getAIMessage = async (userQuery) => {
  try {
    console.log(`Sending request to ${API_BASE_URL}/api/query`);
    
    const response = await fetch(`${API_BASE_URL}/api/query`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'application/json',
      },
      body: JSON.stringify({ query: userQuery }),
    });

    if (!response.ok) {
      const errorText = await response.text();
      console.error(`Server responded with ${response.status}: ${errorText}`);
      throw new Error(`HTTP error! Status: ${response.status}`);
    }

    const data = await response.json();
    
    return {
      role: "assistant",
      content: data.response || "Sorry, I couldn't process your request."
    };
  } catch (error) {
    console.error("Error querying AI:", error);
    return {
      role: "assistant",
      content: `Sorry, I encountered an error while processing your request: ${error.message}. Please try again later.`
    };
  }
};