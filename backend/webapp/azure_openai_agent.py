import os
import json
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.cosmos import CosmosClient

# Load environment variables
load_dotenv()

# Azure OpenAI configuration
endpoint =   "https://foundry-ai-agents.cognitiveservices.azure.com/"
deployment = "gpt-4.1-nano"
api_version ="2024-12-01-preview"

# Get API key from environment variable
subscription_key = os.getenv("AZURE_OPENAI_API_KEY")
if not subscription_key:
    raise ValueError("AZURE_OPENAI_API_KEY environment variable is not set.")

# Initialize Azure OpenAI client
client = AzureOpenAI(
    api_version=api_version,
    azure_endpoint=endpoint,
    api_key=subscription_key,
)

# CosmosDB settings
COSMOS_CONNECTION_STRING = os.getenv("COSMOS_CONNECTION_STRING")
COSMOS_DATABASE = os.getenv("CONFIGURATION__AZURECOSMOSDB__DATABASENAME", "cosmicworks")
COSMOS_CONTAINER = os.getenv("CONFIGURATION__AZURECOSMOSDB__CONTAINERNAME", "products")

SCHEMA_DESCRIPTION = """
The CosmosDB 'products' container contains documents with the following structure:

products (top-level document)
- id: string
- brand_product: string (e.g., "Dacor-Refrigerator". this is what you use to search type of product eg dishwasher, refrigerator, etc.)
- type: string (always 'parts_catalog', useuless for indexing)
- parts: array of part objects

Each part object (joinable as 'item') has:
- url: string
- image_url: string
- details:
    - name: string
    - part_number: string
    - price: string (e.g., "$49.86")
    - rating: string (e.g., "4.8/5")
    - reviews_count: integer
    - reviews: array of review objects

Each review object has:
- rating: string
- reviewer: string
- date: string
- title: string
- content: string

Use JOIN item IN p.parts to access part records in SQL.
Use dot notation like item.details.name or item.details.reviews[0].content to access nested values.
Only SELECT queries are allowed.
"""


def query_cosmosdb(sql_query, max_items=10):
    """
    Execute a SQL SELECT query against CosmosDB and return the results.
    """
    try:
        cosmos_client = CosmosClient.from_connection_string(COSMOS_CONNECTION_STRING)
        database = cosmos_client.get_database_client(COSMOS_DATABASE)
        container = database.get_container_client(COSMOS_CONTAINER)

        # Only allow SELECT queries for safety
        if not sql_query.strip().lower().startswith("select"):
            return json.dumps({"error": "Only SELECT queries are allowed."})

        items = list(container.query_items(
            query=sql_query,
            enable_cross_partition_query=True,
            max_item_count=max_items
        ))
        return json.dumps(items, indent=2)
    
    except Exception as e:
        return json.dumps({"error": str(e)})

def query_azure_openai(user_query, writeOutput=print):
    """
    Function to be called from app.py - handles user queries to Azure OpenAI.
    This is a wrapper around the azure_openai_agent function to maintain API compatibility.
    """
    return azure_openai_agent(user_query, deployment, writeOutput)

def azure_openai_agent(user_query, deployment_name=deployment, writeOutput=print):
    """
    Handles user queries, supports CosmosDB SQL tool use via function calling.
    """
    # Define the CosmosDB query tool
    tools = [
        {
            "type": "function",
            "function": {
                "name": "query_cosmosdb",
                "description": """
                Execute a SQL SELECT query against the CosmosDB products container and return the results.
                
                """,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "sql_query": {
                            "type": "string",
                            "description": "The SQL SELECT query to execute, e.g. SELECT * FROM products p WHERE p.type = 'parts_catalog'"
                        },
                        "max_items": {
                            "type": "integer",
                            "description": "Maximum number of items to return (default 10)."
                        }
                    },
                    "required": ["sql_query"]
                }
            }
        }
    ]

    # Initial system and user messages
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant specializing in appliance parts and repair knowledge.\n"
                "You are able to generate SQL queries for Azure CosmosDB using SQL-like syntax.\n"
                "If you haven't yet narrowed down the search, display your results as a list.\n"
                "If you are very certain about the result, or if there is only one item returned, note that you believe you have found the item and display your results as json.\n"
                
                "The schema is as follows:\n"
                + SCHEMA_DESCRIPTION + \
                """
                "Here are some working example queries:\n
                
                Example 1
                SELECT p.brand_product, item.name, item.manufacturer_number, item.partselect_number, item.price
                FROM products p
                JOIN item IN p.parts
                WHERE p.brand_product LIKE 'Dacor-Refrigerator%'
                
                Example 2
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
                WHERE item.partselect_number = 'PS8728568'

                Example 3
                SELECT p.brand_product, 
                    item.name, 
                    item.details.reviews_count,
                    item.details.reviews
                FROM products p
                JOIN item IN p.parts
                WHERE item.manufacturer_number = 'WR23X37285' 
                
                
                """
                
            )
        },
        {
            "role": "user",
            "content": user_query,
        },
    ]


    writeOutput("Sending request to Azure OpenAI...", isCode=True)

    try:
        # First call: let the model decide if it wants to use the tool
        response = client.chat.completions.create(
            messages=messages,
            max_completion_tokens=800,
            temperature=0.7,
            top_p=1.0,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            model=deployment_name,
            tools=tools,
            tool_choice="auto"
        )

        response_message = response.choices[0].message
        messages.append(response_message)

        writeOutput(f"AI Response: {response_message.content}", isCode=True)
        # If the model called a tool, execute it and append the result
        if getattr(response_message, "tool_calls", None):
            writeOutput("AI is querying the database...", isCode=True)
            for tool_call in response_message.tool_calls:
                if tool_call.function.name == "query_cosmosdb":
                    args = json.loads(tool_call.function.arguments)
                    sql_query = args.get("sql_query")
                    max_items = args.get("max_items", 5)
                    
                    # Log the SQL query being executed
                    writeOutput(f"Executing SQL: {sql_query}", isCode=True)
                    
                    tool_result = query_cosmosdb(sql_query, max_items)
                    messages.append({
                        "tool_call_id": tool_call.id,
                        "role": "tool",
                        "name": "query_cosmosdb",
                        "content": tool_result,
                    })

            # Second call: get the final answer from the model
            writeOutput("Processing database results...", isCode=True)
            final_response = client.chat.completions.create(
                messages=messages,
                max_completion_tokens=100,
                temperature=0.7,
                top_p=1.0,
                frequency_penalty=0.0,
                presence_penalty=0.0,
                model=deployment_name
            )
            # log that it's done
            writeOutput("Final response received from Azure OpenAI.", isCode=True)
            writeOutput(f"Final AI Response: {final_response.choices[0].message.content}", isCode=True)
            return final_response.choices[0].message.content
        else:
            # No tool call, just return the model's direct response
            return response_message.content
    
    except Exception as e:
        error_message = f"Error calling Azure OpenAI: {str(e)}"
        writeOutput(error_message, isCode=True)
        return {"error": error_message}

# Example usage
if __name__ == "__main__":
    def writeOutput(msg, isCode=False):
        print(msg)
    user_query = "List all Dacor Refrigerator parts and their prices."
    result = query_azure_openai(user_query, writeOutput)
    print(result)