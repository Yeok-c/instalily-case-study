# Copyright (c) Microsoft. All rights reserved.

import asyncio
import os

from azure.ai.agents.models import FileInfo, FileSearchTool, VectorStore
from azure.identity.aio import DefaultAzureCredential  # Keep only this one for async version


from azure.ai.agents.models import MessageTextContent, ListSortOrder
from azure.ai.projects import AIProjectClient
# Remove this line which imports the synchronous version:
# from azure.identity import DefaultAzureCredential  

from semantic_kernel.agents import AzureAIAgent, AzureAIAgentSettings, AzureAIAgentThread
from semantic_kernel.contents import AuthorRole

from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential

from semantic_kernel.connectors.azure_cosmos_db import CosmosNoSqlStore
from semantic_kernel.data.vector import VectorStoreField
from dataclasses import dataclass


import dotenv
dotenv.load_dotenv()

# Rest of your code remains the same
"""
The following sample demonstrates how to create a simple, Azure AI agent that
uses a file search tool to answer user questions.
"""

# Simulate a conversation with the agent
USER_INPUTS = [
    "Who is the youngest employee?",
    "Who works in sales?",
    "I have a customer request, who can help me?",
]

endpoint="https://foundry-ai-agents.services.ai.azure.com/api/projects/foundry-ai-agents"

model_name = "gpt-4.1-nano"
deployment = "gpt-4.1-nano"
api_version = "2025-04-14"

from typing import Annotated, List, Optional, Dict
from semantic_kernel.data.vector import VectorStoreField, vectorstoremodel

@vectorstoremodel
@dataclass
class RefrigeratorPart:
    # Unique identifier
    url: Annotated[str, VectorStoreField("key")]
    
    # Basic part information
    name: Annotated[str, VectorStoreField()]
    description: Annotated[str, VectorStoreField("data")]  # Primary searchable content
    partselect_number: Annotated[str, VectorStoreField()]
    manufacturer_number: Annotated[str, VectorStoreField()]
    price: Annotated[str, VectorStoreField()]
    stock_status: Annotated[str, VectorStoreField()]
    
    # Combined review text for searchability
    review_text: Annotated[str, VectorStoreField()]
    
    # Combined repair story text
    repair_text: Annotated[str, VectorStoreField()]
    
    # Optional metadata
    rating: Annotated[Optional[str], VectorStoreField()]
    reviews_count: Annotated[Optional[int], VectorStoreField()]
    part_number: Annotated[Optional[str], VectorStoreField()]
    
# project_client = AIProjectClient(
#     endpoint=endpoint,
#     credential=DefaultAzureCredential()
# )
async def main() -> None:
    # Initialize variables that need cleanup
    client = None
    thread = None
    file = None
    vector_store = None
    agent = None
    creds = None
    
    try:
        # Create credentials - make sure to initialize it properly
        creds = DefaultAzureCredential()
        
        # Create the client using the credentials
        client = AIProjectClient(
            endpoint=endpoint,
            credential=creds,
            api_version=api_version  # Make sure to include the API version
        )
        
        # # 1. Read and upload the file to the Azure AI agent service
        # pdf_file_path = "./backend/webapp/sk/useful_examples/employees.pdf"  # Use this path
        # file = await client.agents.files.upload_and_poll(file_path=pdf_file_path, purpose="assistants")
        # vector_store = await client.agents.vector_stores.create_and_poll(
        #     file_ids=[file.id], name="my_vectorstore"
        # )


        vector_store = CosmosNoSqlStore(
            url="https://foundry-ai-agents-db.documents.azure.com:443/", # "https://<your-account-name>.documents.azure.com:443/",
            key=os.environ.get("COSMOS_DB_KEY"),  # Replace with your Cosmos DB key
            database_name="cosmicworks"
        )


        # 2. Create file search tool with uploaded resources
        file_search = FileSearchTool(vector_store_ids=[vector_store])

        # 3. Create an agent on the Azure AI agent service with the file search tool
        agent_definition = await client.agents.create_agent(
            model=model_name,
            name="FileSearchAgent",
            tools=file_search.definitions,
            tool_resources=file_search.resources,
        )
    
        # 4. Create a Semantic Kernel agent for the Azure AI agent
        agent = AzureAIAgent(
            client=client,
            definition=agent_definition,
        )

        # 5. Create a thread for the agent
        # If no thread is provided, a new thread will be
        # created and returned with the initial response
        thread = None

        for user_input in USER_INPUTS:
            print(f"# User: '{user_input}'")
            # 6. Invoke the agent for the specified thread for response
            async for response in agent.invoke(messages=user_input, thread=thread):
                if response.role != AuthorRole.TOOL:
                    print(f"# Agent: {response}")
                thread = response.thread
    finally:
        # 7. Cleanup: Delete the thread and agent and other resources
        if thread:
            await thread.delete()
        if vector_store and client:
            await client.agents.vector_stores.delete(vector_store)
        if file and client:
            await client.agents.files.delete(file.id)
        if agent and client: 
            await client.agents.delete_agent(agent.id)
        if creds:
            await creds.close()
            
if __name__ == "__main__":
    asyncio.run(main())
