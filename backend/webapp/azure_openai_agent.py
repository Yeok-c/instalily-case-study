import os
import json
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.cosmos import CosmosClient

def query_azure_openai(user_query, writeOutput=print):
    """
    Query the Azure OpenAI service with the user's input
    
    Args:
        user_query: The user's question or prompt
        writeOutput: Function to output results
    
    Returns:
        dict: Response from the Azure OpenAI service
    """
    try:
        writeOutput(f"Processing query: {user_query}")
        
        # Azure OpenAI configuration
        endpoint = "https://foundry-ai-agents.cognitiveservices.azure.com/"
        model_name = "gpt-4.1-nano"
        deployment = "gpt-4.1-nano"
        
        subscription_key = os.environ.get("AZURE_OPENAI_API_KEY")
        if not subscription_key:
            writeOutput("Error: AZURE_OPENAI_API_KEY environment variable not set", isCode=True)
            return {"error": "API key not configured"}
            
        api_version = "2024-12-01-preview"
        
        writeOutput("Connecting to Azure OpenAI...", isCode=True)
        
        # Initialize Azure OpenAI client
        client = AzureOpenAI(
            api_version=api_version,
            azure_endpoint=endpoint,
            api_key=subscription_key,
        )
        
        writeOutput("Sending request to Azure OpenAI...", isCode=True)
        
        # Create the completion
        response = client.chat.completions.create(
            messages=[
                {
                    "role": "system",
                    "content": "You are a helpful assistant specializing in appliance parts and repair knowledge.",
                },
                {
                    "role": "user",
                    "content": user_query,
                },
            ],
            max_completion_tokens=800,
            temperature=0.7,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            model=deployment
        )
        
        # Extract and return the response content
        ai_response = response.choices[0].message.content
        writeOutput("Azure OpenAI Response:", isCode=True)
        writeOutput(ai_response)
        
        return {"response": ai_response}
        
    except Exception as e:
        writeOutput(f"Error querying Azure OpenAI: {str(e)}", isCode=True)
        return {"error": str(e)}