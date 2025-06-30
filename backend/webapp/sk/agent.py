# Copyright (c) Microsoft. All rights reserved.

import asyncio
import os
from typing import Annotated, Dict, Any, Optional, Callable

from azure.identity.aio import DefaultAzureCredential
from semantic_kernel.agents import AzureAIAgent, AzureAIAgentSettings
from semantic_kernel.functions import kernel_function
from dotenv import load_dotenv

load_dotenv()

"""
Azure AI Agent implementation that provides part information and installation help.
This simple agent handles all customer inquiries without routing between specialized agents.
"""

# Store agents and threads by user ID
_agents: Dict[str, AzureAIAgent] = {}
_threads: Dict[str, Any] = {}

class PartsPlugin:
    """Plugin for appliance parts information and troubleshooting."""

    @kernel_function(description="Provides information about common refrigerator parts.")
    def get_refrigerator_parts(self) -> Annotated[str, "Returns common refrigerator parts."]:
        return """
        Common Refrigerator Parts:
        1. Water Filter (PS8728568) - $49.99
        2. Door Gasket (PS9865421) - $89.95
        3. Temperature Control (PS6743219) - $65.50
        4. Compressor (PS3312687) - $199.99
        5. Ice Maker Assembly (PS4526781) - $129.95
        """

    @kernel_function(description="Provides information about common dishwasher parts.")
    def get_dishwasher_parts(self) -> Annotated[str, "Returns common dishwasher parts."]:
        return """
        Common Dishwasher Parts:
        1. Spray Arm (PS2376541) - $35.99
        2. Pump and Motor (PS8812645) - $129.50
        3. Door Latch (PS7654321) - $45.75
        4. Control Board (PS9087123) - $175.25
        5. Water Inlet Valve (PS5432198) - $65.99
        """

    @kernel_function(description="Provides installation instructions for a part.")
    def get_installation_guide(self, part_number: Annotated[str, "The part number"]) -> Annotated[str, "Installation instructions"]:
        # Simple mapping of part numbers to installation guides
        guides = {
            "PS8728568": "Water Filter Installation:\n1. Turn off water supply\n2. Twist old filter counterclockwise to remove\n3. Insert new filter and twist clockwise until it locks\n4. Run water for 5 minutes to flush system",
            "PS9865421": "Door Gasket Installation:\n1. Remove old gasket by pulling it away from the door\n2. Clean the channel thoroughly\n3. Start at the top corner and press new gasket into channel\n4. Work your way around the door, ensuring gasket is fully seated",
            "PS2376541": "Spray Arm Installation:\n1. Remove lower dish rack\n2. Unscrew central mounting nut\n3. Remove old spray arm\n4. Align and place new spray arm\n5. Secure with mounting nut"
        }
        
        return guides.get(
            part_number, 
            f"No specific installation guide available for part {part_number}. Please refer to the manufacturer's manual or contact customer service."
        )
    
    @kernel_function(description="Provides URL to help find model number.")
    def get_model_number_help_url(self, appliance_type: Annotated[str, "Type of appliance"]) -> Annotated[str, "Help URL"]:
        appliance_type = appliance_type.lower()
        
        if "refrigerator" in appliance_type:
            return "https://www.partselect.com/Find-Your-Refrigerator-Model-Number/"
        elif "dishwasher" in appliance_type:
            return "https://www.partselect.com/Find-Your-Dishwasher-Model-Number/"
        else:
            return "https://www.partselect.com/model-number-faq/"


async def get_or_create_agent(user_id: str) -> tuple:
    """Get existing agent or create a new one for the user."""
    if user_id not in _agents or user_id not in _threads:
        async with DefaultAzureCredential() as creds, AzureAIAgent.create_client(credential=creds) as client:
            # Create agent on the Azure AI agent service
            agent_definition = await client.agents.create_agent(
                model=AzureAIAgentSettings().model_deployment_name,
                name="Parts Assistant",
                instructions="""
                You are a helpful assistant for a parts service company. Your job is to:
                1. Help users identify the parts they need for their appliances
                2. Provide installation instructions when asked
                3. Direct users to resources for finding their model numbers
                
                When users need help finding their model number, use the get_model_number_help_url function.
                For refrigerator parts, use the get_refrigerator_parts function.
                For dishwasher parts, use the get_dishwasher_parts function.
                When users need installation help, use the get_installation_guide function.
                
                Be friendly but professional. Focus on helping users find exactly what they need.
                """,
            )

            # Create agent instance
            _agents[user_id] = AzureAIAgent(
                client=client,
                definition=agent_definition,
                plugins=[PartsPlugin()],
            )
            _threads[user_id] = None
    
    return _agents[user_id], _threads[user_id]


async def query_agent(message: str, user_id: str, output_callback: Optional[Callable] = None) -> str:
    """
    Process a user message through the agent.
    
    Args:
        message: The user's message
        user_id: Unique identifier for the user
        output_callback: Function to call with output from the agent
    
    Returns:
        The agent's response
    """
    if output_callback is None:
        output_callback = print
    
    try:
        # Get or create agent for this user
        agent, thread = await get_or_create_agent(user_id)
        
        # Invoke the agent and capture the response
        response_text = ""
        
        output_callback("Processing your request...")
        
        async for response in agent.invoke(
            messages=message,
            thread=thread,
        ):
            # Update the response text
            response_text += str(response)
            
            # Update the thread reference
            thread = response.thread
            
        # Update the thread dictionary
        _threads[user_id] = thread
        
        return response_text
        
    except Exception as e:
        error_message = f"Error processing request: {str(e)}"
        output_callback(error_message)
        return error_message


async def clear_context(user_id: str, output_callback: Optional[Callable] = None) -> str:
    """
    Clear the conversation context for a specific user.
    
    Args:
        user_id: Unique identifier for the user
        output_callback: Function to call with output messages
    """
    if output_callback is None:
        output_callback = print
    
    try:
        # Check if the user has active agent and thread
        if user_id in _agents:
            # Delete the thread if it exists
            if user_id in _threads and _threads[user_id]:
                async with DefaultAzureCredential() as creds, AzureAIAgent.create_client(credential=creds) as client:
                    await _threads[user_id].delete()
                    await client.agents.delete_agent(_agents[user_id].id)
            
            # Remove agent and thread from dictionaries
            if user_id in _agents:
                del _agents[user_id]
            if user_id in _threads:
                del _threads[user_id]
            
            message = f"Conversation history cleared for user {user_id}"
            output_callback(message)
            return message
        else:
            message = f"No active conversation found for user {user_id}"
            output_callback(message)
            return message
            
    except Exception as e:
        error_message = f"Error clearing conversation context: {str(e)}"
        output_callback(error_message)
        return error_message


# Synchronous wrappers for app.py to call
def query_semantic_kernel(user_query: str, user_id: str, output_callback: Optional[Callable] = None) -> str:
    """
    Process a user query through the semantic kernel agent.
    
    Args:
        user_query: The user's query text
        user_id: Unique identifier for the user
        output_callback: Function to call with output from the agent
    """
    return asyncio.run(query_agent(user_query, user_id, output_callback))


def clear_conversation_history(user_id: str, output_callback: Optional[Callable] = None) -> str:
    """
    Clear the conversation history for a specific user.
    
    Args:
        user_id: Unique identifier for the user
        output_callback: Function to call with output messages
    """
    return asyncio.run(clear_context(user_id, output_callback))


# For testing the agent directly
async def demo():
    test_user_id = "test_user"
    test_messages = [
        "Hello, I need help finding a part for my refrigerator",
        "I don't know my model number",
        "Can you show me some common refrigerator parts?",
        "How do I install a water filter?",
        "Thanks for your help"
    ]
    
    for msg in test_messages:
        print(f"\nUser: {msg}")
        response = await query_agent(msg, test_user_id)
        print(f"Agent: {response}")
    
    await clear_context(test_user_id)


if __name__ == "__main__":
    # Run demo when executed directly
    asyncio.run(demo())