import asyncio
import json
from typing import Annotated, List, Dict, Any, Optional, Callable
import os

from azure.identity.aio import DefaultAzureCredential
from semantic_kernel.functions import kernel_function
from semantic_kernel.agents import AzureAIAgent, AzureAIAgentSettings

# Import cosmos functions for database access
from cosmos import CosmosClient
from dotenv import load_dotenv

load_dotenv()

"""
Multi-agent system for parts selection service with three specialized agents:
1. Triage Agent: Routes user queries to appropriate specialized agent
2. Retail Agent: Helps users find correct parts for purchase
3. Information Agent: Provides installation guidance and answers FAQs
"""

# Store agent instances and conversation threads by user ID
_agents = {}
_threads = {}

class TriagePlugin:
    """Plugin that helps the Triage agent determine which specialized agent to use."""
    
    @kernel_function(description="Analyzes user query to determine which agent should handle it.")
    def determine_agent(self, user_query: Annotated[str, "The user's query or request"]) -> Annotated[str, "The name of the agent that should handle this query"]:
        """
        Analyzes user query to determine which agent should handle it.
        Returns: 'retail' for part selection queries, 'info' for installation/FAQ queries
        """
        # This function will be used by the AI to determine routing
        # The actual routing logic will be in the agent's instructions
        return "Use this function to determine which agent should handle the query"


class RetailPlugin:
    """Plugin for the Retail agent to help users find the correct parts."""
    
    @kernel_function(description="Searches for parts by model or brand.")
    def search_parts_by_brand_model(
        self, 
        brand_product: Annotated[str, "Brand and product type, e.g., 'Dacor-Refrigerator'"]
    ) -> Annotated[str, "JSON list of parts for the specified brand and product"]:
        """
        Searches for parts by brand and product type.
        Example: search_parts_by_brand_model("Dacor-Refrigerator")
        """
        try:
            # Connect to Cosmos DB
            client = CosmosClient.from_connection_string(os.getenv("COSMOS_CONNECTION_STRING"))
            database = client.get_database_client(os.getenv("CONFIGURATION__AZURECOSMOSDB__DATABASENAME", "cosmicworks"))
            container = database.get_container_client(os.getenv("CONFIGURATION__AZURECOSMOSDB__CONTAINERNAME", "products"))
            
            # Query to find parts by brand and product
            query = f"""
            SELECT p.brand_product, item.name, item.manufacturer_number, item.partselect_number, item.price, item.description
            FROM products p
            JOIN item IN p.parts
            WHERE p.brand_product LIKE '{brand_product}%'
            """
            
            items = list(container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            
            if not items:
                return json.dumps({"error": f"No parts found for {brand_product}", "parts": []})
            
            return json.dumps({"parts": items[:10]})  # Limit to 10 parts for readability
        except Exception as e:
            return json.dumps({"error": str(e), "parts": []})

    @kernel_function(description="Gets detailed information about a specific part by its PartSelect number.")
    def get_part_details(
        self, 
        partselect_number: Annotated[str, "The PartSelect number of the part, e.g., 'PS8728568'"]
    ) -> Annotated[str, "JSON object with detailed information about the part"]:
        """
        Gets detailed information about a specific part by its PartSelect number.
        Example: get_part_details("PS8728568")
        """
        try:
            # Connect to Cosmos DB
            client = CosmosClient.from_connection_string(os.getenv("COSMOS_CONNECTION_STRING"))
            database = client.get_database_client(os.getenv("CONFIGURATION__AZURECOSMOSDB__DATABASENAME", "cosmicworks"))
            container = database.get_container_client(os.getenv("CONFIGURATION__AZURECOSMOSDB__CONTAINERNAME", "products"))
            
            # Query to find part by partselect_number
            query = f"""
            SELECT p.brand_product, 
                item.name,
                item.url,
                item.description,
                item.partselect_number,
                item.manufacturer_number,
                item.price,
                item.stock_status,
                item.details
            FROM products p
            JOIN item IN p.parts
            WHERE item.partselect_number = '{partselect_number}'
            """
            
            items = list(container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            
            if not items:
                return json.dumps({"error": f"No part found with partselect_number {partselect_number}"})
            
            return json.dumps(items[0])
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @kernel_function(description="Gets a URL to help user find their appliance model number.")
    def get_model_number_help_url(
        self, 
        appliance_type: Annotated[str, "Type of appliance, e.g., 'refrigerator', 'dishwasher'"]
    ) -> Annotated[str, "URL to guide for finding model number"]:
        """
        Gets a URL to help the user find their appliance model number.
        """
        appliance_type = appliance_type.lower()
        
        if "refrigerator" in appliance_type:
            return "https://www.partselect.com/Find-Your-Refrigerator-Model-Number/"
        elif "dishwasher" in appliance_type:
            return "https://www.partselect.com/Find-Your-Dishwasher-Model-Number/"
        else:
            return "https://www.partselect.com/model-number-faq/"


class InformationPlugin:
    """Plugin for the Information agent to provide installation guidance and FAQs."""
    
    @kernel_function(description="Gets installation instructions for a specific part.")
    def get_installation_guide(
        self, 
        partselect_number: Annotated[str, "The PartSelect number of the part, e.g., 'PS8728568'"]
    ) -> Annotated[str, "Installation guide for the specified part"]:
        """
        Gets installation instructions for a specific part by partselect_number.
        """
        try:
            # Connect to Cosmos DB
            client = CosmosClient.from_connection_string(os.getenv("COSMOS_CONNECTION_STRING"))
            database = client.get_database_client(os.getenv("CONFIGURATION__AZURECOSMOSDB__DATABASENAME", "cosmicworks"))
            container = database.get_container_client(os.getenv("CONFIGURATION__AZURECOSMOSDB__CONTAINERNAME", "products"))
            
            # Query to find installation instructions
            query = f"""
            SELECT p.brand_product, 
                item.name,
                item.description,
                item.details.installation_guide,
                item.details.installation_video_url
            FROM products p
            JOIN item IN p.parts
            WHERE item.partselect_number = '{partselect_number}'
            """
            
            items = list(container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            
            if not items:
                return json.dumps({"error": f"No installation guide found for part {partselect_number}"})
            
            result = items[0]
            
            # If no installation guide in the data, provide a generic response
            if not result.get("installation_guide"):
                return json.dumps({
                    "part_name": result.get("name", "Unknown part"),
                    "message": "No specific installation guide available for this part.",
                    "general_advice": "For installation assistance, please contact customer support or refer to the appliance manual."
                })
                
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})
    
    @kernel_function(description="Gets frequently asked questions about a specific part.")
    def get_part_faqs(
        self, 
        partselect_number: Annotated[str, "The PartSelect number of the part, e.g., 'PS8728568'"]
    ) -> Annotated[str, "FAQs for the specified part"]:
        """
        Gets FAQs for a specific part by partselect_number.
        """
        try:
            # Connect to Cosmos DB
            client = CosmosClient.from_connection_string(os.getenv("COSMOS_CONNECTION_STRING"))
            database = client.get_database_client(os.getenv("CONFIGURATION__AZURECOSMOSDB__DATABASENAME", "cosmicworks"))
            container = database.get_container_client(os.getenv("CONFIGURATION__AZURECOSMOSDB__CONTAINERNAME", "products"))
            
            # Query to find FAQs
            query = f"""
            SELECT p.brand_product, 
                item.name,
                item.details.faqs,
                item.details.reviews
            FROM products p
            JOIN item IN p.parts
            WHERE item.partselect_number = '{partselect_number}'
            """
            
            items = list(container.query_items(
                query=query,
                enable_cross_partition_query=True
            ))
            
            if not items:
                return json.dumps({"error": f"No FAQs found for part {partselect_number}"})
            
            result = items[0]
            
            # If no FAQs in the data, provide a generic response
            if not result.get("faqs"):
                return json.dumps({
                    "part_name": result.get("name", "Unknown part"),
                    "message": "No specific FAQs available for this part.",
                    "reviews": result.get("reviews", [])
                })
                
            return json.dumps(result)
        except Exception as e:
            return json.dumps({"error": str(e)})


async def create_agent(client, name, instructions, plugins=None):
    """Helper function to create an agent with the specified parameters."""
    agent_definition = await client.agents.create_agent(
        model=AzureAIAgentSettings().model_deployment_name,
        name=name,
        instructions=instructions,
    )

    agent = AzureAIAgent(
        client=client,
        definition=agent_definition,
        plugins=plugins or [],
    )
    
    return agent


async def setup_agents(client):
    """Set up all three agents and return them as a dictionary."""
    
    # 1. Triage Agent
    triage_instructions = """
    You are a helpful triage agent for a parts service company. Your job is to:
    1. Greet users professionally
    2. Determine what kind of help they need
    3. Route their query to the appropriate specialized agent:
       - Retail Agent: For users trying to identify or purchase parts
       - Information Agent: For users needing installation help or FAQs

    If the user is looking for specific parts, trying to find what parts they need, or asking
    about purchasing, route them to the Retail Agent.

    If the user needs help with installation, maintenance, troubleshooting, or has general
    questions about products they already have, route them to the Information Agent.

    When you determine which agent should help, say: "I'll connect you with our [agent type] to assist with that."
    """
    triage_agent = await create_agent(
        client, 
        "Triage Agent", 
        triage_instructions,
        plugins=[TriagePlugin()]
    )

    # 2. Retail Agent
    retail_instructions = """
    You are a helpful retail agent for a parts service company. Your job is to:
    1. Help users identify the exact part they need for their appliance
    2. Provide detailed information about parts including price, availability, and specifications
    3. Guide users in selecting the right part for their needs
    
    Important guidelines:
    - If users don't know their model number, provide them with a relevant URL to help them find it
    - Use the search_parts_by_brand_model function to look up available parts
    - Use the get_part_details function to get detailed information about specific parts
    - Your job is complete when the user has confirmed the correct part they need and you have the exact partselect_number
    
    If users need help with installation or have questions about a part they already own,
    let them know they should speak with our Information Agent instead.
    """
    retail_agent = await create_agent(
        client, 
        "Retail Agent", 
        retail_instructions,
        plugins=[RetailPlugin()]
    )

    # 3. Information Agent
    info_instructions = """
    You are a helpful information agent for a parts service company. Your job is to:
    1. Provide installation guidance for specific parts
    2. Answer FAQs about parts and appliances
    3. Help troubleshoot common issues
    
    Use the get_installation_guide function to find installation instructions for specific parts.
    Use the get_part_faqs function to find FAQs and common questions about specific parts.
    
    If the user is trying to identify which part they need or wants to purchase a part,
    let them know they should speak with our Retail Agent instead.
    """
    info_agent = await create_agent(
        client, 
        "Information Agent", 
        info_instructions,
        plugins=[InformationPlugin()]
    )
    
    return {
        "triage": triage_agent,
        "retail": retail_agent,
        "info": info_agent
    }


async def init_conversation_context(user_id):
    """Initialize conversation context for a user."""
    if user_id not in _agents or user_id not in _threads:
        async with (
            DefaultAzureCredential() as creds,
            AzureAIAgent.create_client(credential=creds) as client,
        ):
            _agents[user_id] = await setup_agents(client)
            _threads[user_id] = None
            
    return _agents[user_id], _threads[user_id]


async def determine_agent_type(message):
    """Simple logic to determine which agent should handle a message."""
    message_lower = message.lower()
    
    # Installation or troubleshooting related terms
    info_terms = ["install", "how to", "steps", "guide", "help me", "instructions", 
                  "broken", "not working", "issue", "problem", "fix", "repair"]
                  
    # Part selection or identification related terms
    retail_terms = ["find", "part", "need", "looking for", "buy", "purchase", 
                    "order", "replacement", "model", "number", "refrigerator part",
                    "dishwasher part", "price", "cost"]
    
    # Count matches
    info_count = sum(1 for term in info_terms if term in message_lower)
    retail_count = sum(1 for term in retail_terms if term in message_lower)
    
    # Default to triage agent for initial interaction
    if info_count == 0 and retail_count == 0:
        return "triage"
    
    # Return the agent type with more matching terms
    return "info" if info_count > retail_count else "retail"


async def query_multi_agent(message, user_id, output_callback=None):
    """
    Process a user message through the multi-agent system.
    
    Args:
        message: The user's message
        user_id: Unique identifier for the user
        output_callback: Function to call with output from the agents
    
    Returns:
        The agent's response
    """
    if output_callback is None:
        output_callback = print
    
    try:
        # Initialize or get the conversation context
        agents, thread = await init_conversation_context(user_id)
        
        # Determine which agent should handle this message
        agent_type = await determine_agent_type(message)
        current_agent = agents[agent_type]
        
        # Capture the response
        response_text = ""
        output_callback(f"Agent type: {agent_type.capitalize()}")
        
        # Invoke the agent and capture the response
        async for response in current_agent.invoke(
            messages=message,
            thread=thread,
        ):
            # Accumulate the response
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


async def clear_user_context(user_id, output_callback=None):
    """
    Clear the conversation context for a specific user.
    
    Args:
        user_id: Unique identifier for the user
        output_callback: Function to call with output messages
    """
    if output_callback is None:
        output_callback = print
        
    try:
        # Check if the user has active agents and thread
        if user_id in _agents:
            # Delete the thread if it exists
            if user_id in _threads and _threads[user_id]:
                async with DefaultAzureCredential() as creds, AzureAIAgent.create_client(credential=creds) as client:
                    await _threads[user_id].delete()
                    
            # Remove agents and thread from dictionaries
            if user_id in _agents:
                del _agents[user_id]
            if user_id in _threads:
                del _threads[user_id]
                
            output_callback(f"Conversation context cleared for user {user_id}")
        else:
            output_callback(f"No active conversation found for user {user_id}")
            
    except Exception as e:
        error_message = f"Error clearing conversation context: {str(e)}"
        output_callback(error_message)
        return error_message


def query_multi_agent_sync(message, user_id, output_callback=None):
    """
    Synchronous wrapper for query_multi_agent.
    """
    return asyncio.run(query_multi_agent(message, user_id, output_callback))


def clear_user_context_sync(user_id, output_callback=None):
    """
    Synchronous wrapper for clear_user_context.
    """
    return asyncio.run(clear_user_context(user_id, output_callback))