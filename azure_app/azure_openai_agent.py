import os
import json
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.cosmos import CosmosClient
from azure.core.exceptions import AzureError

# Load environment variables
load_dotenv()

# Azure OpenAI configuration
endpoint = "https://foundry-ai-agents.cognitiveservices.azure.com/"
deployment = "gpt-4.1-nano"
api_version = "2024-12-01-preview"

# # if deepseek
# endpoint = "https://foundry-ai-agents.services.ai.azure.com/models"
# deployment="DeepSeek-V3-0324"
# api_version = "2024-05-01-preview"


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

def query_cosmosdb(sql_query, max_items=10):
    """
    Execute a SQL SELECT query against CosmosDB and return the results.
    
    Args:
        sql_query (str): SQL query to execute
        max_items (int): Maximum number of items to return
        
    Returns:
        str: JSON string of query results
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
    
    except AzureError as ae:
        return json.dumps({"error": f"Azure Cosmos DB error: {str(ae)}. Original query: {sql_query}"})
    except Exception as e:
        return json.dumps({"error": f"Error querying database: {str(e)}.  Original query: {sql_query}"})


def find_by_brand_product(brand_product, max_items=10):
    """
    Find parts by brand and product type.
    
    Args:
        brand_product (str): Brand and product combination like 'Philips-Dishwasher'
        max_items (int): Maximum number of items to return
        
    Returns:
        str: JSON string of query results
    """
    # Construct the query to search by brand_product
    sql_query = f"""
    SELECT p.brand_product, 
        item.name,
        item.manufacturer_number, 
        item.partselect_number, 
        item.description,
        item.price,
        item.url,
        item.image_url
    FROM products p
    JOIN item IN p.parts
    WHERE p.brand_product LIKE '{brand_product}%'
    """
    
    results = query_cosmosdb(sql_query, max_items)
    parsed_results = json.loads(results)
    
    # If no results found, try to split and search by brand and product separately
    if not parsed_results or (isinstance(parsed_results, list) and len(parsed_results) == 0):
        try:
            if "-" in brand_product:
                brand, product = brand_product.split("-", 1)
                brand_results = find_by_brand(brand, max_items)
                return brand_results
            else:
                # If there's no hyphen, assume it's just a brand
                return find_by_brand(brand_product, max_items)
        except Exception as e:
            return json.dumps({"error": f"Error in fallback search: {str(e)}", "original_results": parsed_results})
    
    return results


def find_by_brand(brand, max_items=10):
    """
    Find parts by brand only.
    
    Args:
        brand (str): Brand name like 'Philips'
        max_items (int): Maximum number of items to return
        
    Returns:
        str: JSON string of query results
    """
    # Construct the query to search by brand
    sql_query = f"""
    SELECT p.brand_product, 
        item.name,
        item.manufacturer_number, 
        item.partselect_number, 
        item.description,
        item.price,
        item.url,
        item.image_url
    FROM products p
    JOIN item IN p.parts
    WHERE STARTSWITH(p.brand_product, '{brand}')
    """
    
    return query_cosmosdb(sql_query, max_items)


def find_by_product(product, max_items=10):
    """
    Find parts by product type only.
    
    Args:
        product (str): Product type like 'Dishwasher'
        max_items (int): Maximum number of items to return
        
    Returns:
        str: JSON string of query results
    """
    # Construct the query to search by product type
    # This searches for the product type in the brand_product field
    sql_query = f"""
    SELECT p.brand_product, 
        item.name,
        item.manufacturer_number, 
        item.partselect_number, 
        item.description,
        item.price,
        item.url,
        item.image_url
    FROM products p
    JOIN item IN p.parts
    WHERE CONTAINS(p.brand_product, '{product}')
    """
    
    return query_cosmosdb(sql_query, max_items)

def find_by_description(description, max_items=10):
    """
    Find parts by description.
    
    Args:
        description (str): Description text like 'Admiral Dishwasher Upper Rack Adjuster Kit'
        max_items (int): Maximum number of items to return
        
    Returns:
        str: JSON string of query results
    """
    # Construct the query to search by description
    # This searches for the description in the item.description field
    sql_query = f"""
    SELECT p.brand_product, 
        item.name,
        item.manufacturer_number, 
        item.partselect_number, 
        item.price,
        item.url,
        item.image_url,
        item.description
    FROM products p
    JOIN item IN p.parts
    WHERE CONTAINS(item.description, '{description}') OR CONTAINS(item.name, '{description}')
    """
    
    results = query_cosmosdb(sql_query, max_items)
    parsed_results = json.loads(results)
    
    # If no results found, try a more relaxed search
    if not parsed_results or (isinstance(parsed_results, list) and len(parsed_results) == 0):
        try:
            # Try to split the description into words and search for parts matching any of the key terms
            words = description.split()
            if len(words) > 2:  # Only try this for descriptions with multiple words
                # Get the most relevant words (nouns and brand names usually)
                key_terms = [word for word in words if len(word) > 3]
                
                # Build a query that searches for any of these terms
                search_conditions = " OR ".join([f"CONTAINS(item.name, '{term}')" for term in key_terms])
                
                fallback_query = f"""
                SELECT p.brand_product, 
                    item.name,
                    item.manufacturer_number, 
                    item.partselect_number, 
                    item.price,
                    item.url,
                    item.image_url,
                    item.description
                FROM products p
                JOIN item IN p.parts
                WHERE {search_conditions}
                """
                
                return query_cosmosdb(fallback_query, max_items)
        except Exception as e:
            return json.dumps({"error": f"Error in fallback search: {str(e)}", "original_results": parsed_results})
    
    return results

def find_by_manufacturer_number(manufacturer_number, max_items=10):
    """
    Find parts by manufacturer number.
    
    Args:
        manufacturer_number (str): The manufacturer part number
        max_items (int): Maximum number of items to return
        
    Returns:
        str: JSON string of query results
    """
    # Construct the query to search by manufacturer_number
    sql_query = f"""
    SELECT p.brand_product, 
        item.name,
        item.url,
        item.image_url,
        item.description,
        item.partselect_number,
        item.manufacturer_number,
        item.price,
        item.stock_status,
        item.details
    FROM products p
    JOIN item IN p.parts
    WHERE item.manufacturer_number = '{manufacturer_number}'
    """
    
    return query_cosmosdb(sql_query, max_items)


def find_by_partselect_number(partselect_number, max_items=10):
    """
    Find parts by PartSelect number.
    
    Args:
        partselect_number (str): The PartSelect part number
        max_items (int): Maximum number of items to return
        
    Returns:
        str: JSON string of query results
    """
    # Construct the query to search by partselect_number
    sql_query = f"""
    SELECT p.brand_product, 
        item.name,
        item.url,
        item.image_url,
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
    
    return query_cosmosdb(sql_query, max_items)


def find_by_any_part_number(part_number, max_items=10):
    """
    Find parts by either PartSelect number or manufacturer number, then merge results.
    
    Args:
        part_number (str): A string that could be a PartSelect number (e.g., PS1990907) or manufacturer number.
        max_items (int): Max results to return from each method.
        
    Returns:
        str: JSON string of combined query results.
    """
    results = []

    try:
        if part_number.upper().startswith("PS"):
            partselect_results = json.loads(find_by_partselect_number(part_number, max_items))
            if isinstance(partselect_results, list):
                results.extend(partselect_results)
        else:
            manufacturer_results = json.loads(find_by_manufacturer_number(part_number, max_items))
            if isinstance(manufacturer_results, list):
                results.extend(manufacturer_results)

        # Fallback: Try both just in case
        partselect_results = json.loads(find_by_partselect_number(part_number, max_items))
        if isinstance(partselect_results, list):
            results.extend(partselect_results)

        manufacturer_results = json.loads(find_by_manufacturer_number(part_number, max_items))
        if isinstance(manufacturer_results, list):
            results.extend(manufacturer_results)

        # Remove duplicates based on manufacturer_number or partselect_number
        seen = set()
        deduped = []
        for item in results:
            key = item.get("manufacturer_number") or item.get("partselect_number")
            if key and key not in seen:
                seen.add(key)
                deduped.append(item)

        return json.dumps(deduped[:max_items], indent=2)

    except Exception as e:
        return json.dumps({"error": f"Error searching by part number: {str(e)}"})
    
def query_azure_openai(user_query, writeOutput=print):
    """
    Function to be called from app.py - handles user queries to Azure OpenAI.
    This is a wrapper around the azure_openai_agent function to maintain API compatibility.
    """
    return azure_openai_agent(user_query, deployment, writeOutput)


def azure_openai_agent(user_query, deployment_name=deployment, writeOutput=print):
    """
    Handles user queries, supports specific part search functions via function calling.
    """
    # Define the search functions as tools
    tools = [
        {
            "type": "function",
            "function": {
                "name": "find_by_brand_product",
                "description": """
                Find parts by brand and product type (e.g., 'Philips-Dishwasher').
                Use this when user is looking for a specific brand and product combination.
                If the exact brand-product isn't found, it will try searching by brand only.
                """,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "brand_product": {
                            "type": "string",
                            "description": "Brand and product combination like 'Philips-Dishwasher'"
                        },
                        "max_items": {
                            "type": "integer",
                            "description": "Maximum number of items to return (default 10)."
                        }
                    },
                    "required": ["brand_product"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "find_by_brand",
                "description": """
                Find parts by brand name only (e.g., 'Philips').
                Use this when user is only interested in a specific brand, regardless of product type.
                """,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "brand": {
                            "type": "string",
                            "description": "Brand name like 'Philips'"
                        },
                        "max_items": {
                            "type": "integer",
                            "description": "Maximum number of items to return (default 10)."
                        }
                    },
                    "required": ["brand"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "find_by_product",
                "description": """
                Find parts by product type only (e.g., 'Dishwasher').
                Use this when user wants to see parts for a specific product type across all brands.
                """,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product": {
                            "type": "string",
                            "description": "Product type like 'Dishwasher'"
                        },
                        "max_items": {
                            "type": "integer",
                            "description": "Maximum number of items to return (default 10)."
                        }
                    },
                    "required": ["product"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "find_by_description",
                "description": """
                Find parts by description (e.g., 'Jenn-Air Dishwasher Rack Track Stop').
                Use this when user wants to find parts by their descriptive name.
                """,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Description of the part (e.g., 'Jenn-Air Dishwasher Rack Track Stop')"
                        },
                        "max_items": {
                            "type": "integer",
                            "description": "Maximum number of items to return (default 10)."
                        }
                    },
                    "required": ["description"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "find_by_any_part_number",
                "description": """
                Search for a part using either a manufacturer number or a PartSelect number (e.g., PS1990907).
                This function will try both search methods and combine results if needed.
                """,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "part_number": {
                            "type": "string",
                            "description": "The part number, either manufacturer or PartSelect"
                        },
                        "max_items": {
                            "type": "integer",
                            "description": "Maximum number of items to return (default 10)."
                        }
                    },
                    "required": ["part_number"]
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
                "You can help users find parts by:\n"
                "1. Brand and product type (e.g., 'Philips-Dishwasher')\n"
                "2. Brand only (e.g., 'Philips')\n"
                "3. Product type only (e.g., 'Dishwasher')\n"
                "4. Part number (either manufacturer or PartSelect). This is very specific and preferred\n"
                "If the specific brand-product combination isn't found, search for the brand and product separately.\n"
                "If the returned results is None, tell them 'I believe we don't sell <product> of this <brand>. You can double check to see our list of products at https://www.partselect.com/Products/'\n"
                "If you haven't yet narrowed down the search, ask for more specific information.\n"
                "If you are very certain about the result, or if there is only one item returned, note that you believe you have found the item."
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
            max_completion_tokens=2000,
            temperature=0.7,
            top_p=0.95,  # Slightly reduced from 1.0 for more focused responses
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
            writeOutput("AI is searching for parts...", isCode=True)
            for tool_call in response_message.tool_calls:
                args = json.loads(tool_call.function.arguments)
                
                if tool_call.function.name == "find_by_brand_product":
                    brand_product = args.get("brand_product")
                    max_items = args.get("max_items", 10)
                    writeOutput(f"Searching for brand/product: {brand_product}", isCode=True)
                    tool_result = find_by_brand_product(brand_product, max_items)
                
                elif tool_call.function.name == "find_by_brand":
                    brand = args.get("brand")
                    max_items = args.get("max_items", 10)
                    writeOutput(f"Searching for brand: {brand}", isCode=True)
                    tool_result = find_by_brand(brand, max_items)
                
                elif tool_call.function.name == "find_by_product":
                    product = args.get("product")
                    max_items = args.get("max_items", 10)
                    writeOutput(f"Searching for product: {product}", isCode=True)
                    tool_result = find_by_product(product, max_items)
                
                elif tool_call.function.name == "find_by_any_part_number":
                    part_number = args.get("part_number")
                    max_items = args.get("max_items", 10)
                    writeOutput(f"Searching by part number: {part_number}", isCode=True)
                    tool_result = find_by_any_part_number(part_number, max_items)

                elif tool_call.function.name == "find_by_description":
                    description = args.get("description")
                    max_items = args.get("max_items", 10)
                    writeOutput(f"Searching for description: {description}", isCode=True)
                    tool_result = find_by_description(description, max_items)
                
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": tool_call.function.name,
                    "content": tool_result,
                })

            # Check if we got valid results or an error
            results = json.loads(messages[-1]["content"])
            if isinstance(results, dict) and "error" in results:
                writeOutput(f"Search error: {results['error']}", isCode=True)
            else:
                writeOutput(f"Found {len(results) if isinstance(results, list) else 0} results", isCode=True)

            messages.append({
                "role": "user",
                "content": (
                    """
                    You should now explain the results to the user. 
                    - If multiple search results come up, it is likely that the same part is used for multiple appliances. 
                    
                    If you are very certain about the result(s), you should format the result as a list of dictionaries. Even if there is only one result you should format it as a list of length 1.
                    The users will not know it is a list of dictionaries. 
                    Make sure you include ```dictionary-list-to-render as the frontend will render this list of dictionaries nicely in the UI.\n"
                    Example:
                    ```dictionary-list-to-render
                    [
                        {
                        "part_name": "Dacor Refrigerator Part",
                        "manufacturer_number": "123456",
                        "partselect_number": "PS1990907",
                        "price": "$99.99",
                        "url": "https://www.partselect.com/Parts/123456"
                        "image_url": "https://www.partselect.com/Images/123456.jpg",
                        },
                        ...
                    ]
                    ```
                    """
                )
            })
            # Second call: get the final answer from the model
            writeOutput("Getting final response from Azure OpenAI to show to user", isCode=True)
            final_response = client.chat.completions.create(
                messages=messages,
                max_completion_tokens=2000,
                temperature=0.7,
                top_p=0.95,
                frequency_penalty=0.0,
                presence_penalty=0.0,
                model=deployment_name
            )
            writeOutput("Final response received from Azure OpenAI.", isCode=True)
            writeOutput(f"{final_response.choices[0].message.content}", isCode=True)
            return final_response.choices[0].message.content
        else:
            # No tool call, just return the model's direct response
            return response_message.content
    
    except AzureError as ae:
        error_message = f"Azure OpenAI error: {str(ae)}"
        writeOutput(error_message, isCode=True)
        return {"error": error_message}
    except Exception as e:
        error_message = f"Error calling Azure OpenAI: {str(e)}"
        writeOutput(error_message, isCode=True)
        return {"error": error_message}
    
# Add this new function to handle conversation history
def query_azure_openai_with_history(user_query, conversation_history, writeOutput=print):
    """
    Function to handle user queries with conversation history context.
    
    Args:
        user_query (str): The current user query
        conversation_history (list): List of previous messages in the conversation
        writeOutput (function): Function to handle output messages
        
    Returns:
        str: Response from Azure OpenAI
    """
    # Define the search functions as tools (same as in azure_openai_agent)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "find_by_brand_product",
                "description": """
                Find parts by brand and product type (e.g., 'Philips-Dishwasher').
                Use this when user is looking for a specific brand and product combination.
                If the exact brand-product isn't found, it will try searching by brand only.
                """,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "brand_product": {
                            "type": "string",
                            "description": "Brand and product combination like 'Philips-Dishwasher'"
                        },
                        "max_items": {
                            "type": "integer",
                            "description": "Maximum number of items to return (default 10)."
                        }
                    },
                    "required": ["brand_product"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "find_by_brand",
                "description": """
                Find parts by brand name only (e.g., 'Philips').
                Use this when user is only interested in a specific brand, regardless of product type.
                """,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "brand": {
                            "type": "string",
                            "description": "Brand name like 'Philips'"
                        },
                        "max_items": {
                            "type": "integer",
                            "description": "Maximum number of items to return (default 10)."
                        }
                    },
                    "required": ["brand"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "find_by_product",
                "description": """
                Find parts by product type only (e.g., 'Dishwasher').
                Use this when user wants to see parts for a specific product type across all brands.
                """,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "product": {
                            "type": "string",
                            "description": "Product type like 'Dishwasher'"
                        },
                        "max_items": {
                            "type": "integer",
                            "description": "Maximum number of items to return (default 10)."
                        }
                    },
                    "required": ["product"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "find_by_description",
                "description": """
                Find parts by description (e.g., 'Jenn-Air Dishwasher Rack Track Stop').
                Use this when user wants to find parts by their descriptive name.
                """,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "description": {
                            "type": "string",
                            "description": "Description of the part (e.g., 'Jenn-Air Dishwasher Rack Track Stop')"
                        },
                        "max_items": {
                            "type": "integer",
                            "description": "Maximum number of items to return (default 10)."
                        }
                    },
                    "required": ["description"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "find_by_any_part_number",
                "description": """
                Search for a part using either a manufacturer number or a PartSelect number (e.g., PS1990907).
                This function will try both search methods and combine results if needed.
                """,
                "parameters": {
                    "type": "object",
                    "properties": {
                        "part_number": {
                            "type": "string",
                            "description": "The part number, either manufacturer or PartSelect"
                        },
                        "max_items": {
                            "type": "integer",
                            "description": "Maximum number of items to return (default 10)."
                        }
                    },
                    "required": ["part_number"]
                }
            }
        }
    ]

    # Initial system message
    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful assistant specializing in appliance parts and repair knowledge.\n"
                "You can help users find parts by:\n"
                "1. Brand and product type (e.g., 'Philips-Dishwasher')\n"
                "2. Brand only (e.g., 'Philips')\n"
                "3. Product type only (e.g., 'Dishwasher')\n"
                "4. Part number (either manufacturer or PartSelect). This is very specific and preferred\n"
                "If the specific brand-product combination isn't found, search for the brand and product separately.\n"
                "If the returned results is None, tell them 'I believe we don't sell <product> of this <brand>. You can double check to see our list of products at https://www.partselect.com/Products/'\n"
                "If you haven't yet narrowed down the search, ask for more specific information.\n"
                "If you are very certain about the result, or if there is only one item returned, note that you believe you have found the item."
            )
        }
    ]
    
    # Add conversation history
    if conversation_history:
        writeOutput(f"Adding {len(conversation_history)} previous messages as context")
        for msg in conversation_history:
            if msg.get("role") and msg.get("content"):
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })
    
    # Add the current user query
    messages.append({
        "role": "user",
        "content": user_query,
    })

    writeOutput("Sending request to Azure OpenAI with conversation history...", isCode=True)

    try:
        # First call: let the model decide if it wants to use the tool
        response = client.chat.completions.create(
            messages=messages,
            max_completion_tokens=2000,
            temperature=0.7,
            top_p=0.95,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            model=deployment,
            tools=tools,
            tool_choice="auto"
        )

        response_message = response.choices[0].message
        messages.append(response_message)

        writeOutput(f"AI Response: {response_message.content}", isCode=True)
        
        # If the model called a tool, execute it and append the result
        if getattr(response_message, "tool_calls", None):
            writeOutput("AI is searching for parts...", isCode=True)
            for tool_call in response_message.tool_calls:
                args = json.loads(tool_call.function.arguments)
                
                if tool_call.function.name == "find_by_brand_product":
                    brand_product = args.get("brand_product")
                    max_items = args.get("max_items", 10)
                    writeOutput(f"Searching for brand/product: {brand_product}", isCode=True)
                    tool_result = find_by_brand_product(brand_product, max_items)
                
                elif tool_call.function.name == "find_by_brand":
                    brand = args.get("brand")
                    max_items = args.get("max_items", 10)
                    writeOutput(f"Searching for brand: {brand}", isCode=True)
                    tool_result = find_by_brand(brand, max_items)
                
                elif tool_call.function.name == "find_by_product":
                    product = args.get("product")
                    max_items = args.get("max_items", 10)
                    writeOutput(f"Searching for product: {product}", isCode=True)
                    tool_result = find_by_product(product, max_items)
                
                elif tool_call.function.name == "find_by_any_part_number":
                    part_number = args.get("part_number")
                    max_items = args.get("max_items", 10)
                    writeOutput(f"Searching by part number: {part_number}", isCode=True)
                    tool_result = find_by_any_part_number(part_number, max_items)

                elif tool_call.function.name == "find_by_description":
                    description = args.get("description")
                    max_items = args.get("max_items", 10)
                    writeOutput(f"Searching for description: {description}", isCode=True)
                    tool_result = find_by_description(description, max_items)
                
                messages.append({
                    "tool_call_id": tool_call.id,
                    "role": "tool",
                    "name": tool_call.function.name,
                    "content": tool_result,
                })

            # Check if we got valid results or an error
            results = json.loads(messages[-1]["content"])
            if isinstance(results, dict) and "error" in results:
                writeOutput(f"Search error: {results['error']}", isCode=True)
            else:
                writeOutput(f"Found {len(results) if isinstance(results, list) else 0} results", isCode=True)

            messages.append({
                "role": "user",
                "content": (
                    """
                    You should now explain the results to the user. 
                    - If multiple search results come up, it is likely that the same part is used for multiple appliances. 
                    
                    If you are very certain about the result(s), you should format the result as a list of dictionaries. Even if there is only one result you should format it as a list of length 1.
                    The users will not know it is a list of dictionaries. 
                    Make sure you include ```dictionary-list-to-render as the frontend will render this list of dictionaries nicely in the UI.\n"
                    Example:
                    ```dictionary-list-to-render
                    [
                        {
                        "part_name": "Dacor Refrigerator Part",
                        "manufacturer_number": "123456",
                        "partselect_number": "PS1990907",
                        "price": "$99.99",
                        "url": "https://www.partselect.com/Parts/123456"
                        "image_url": "https://www.partselect.com/Images/123456.jpg",
                        },
                        ...
                    ]
                    ```
                    """
                )
            })
            # Second call: get the final answer from the model
            writeOutput("Getting final response from Azure OpenAI to show to user", isCode=True)
            final_response = client.chat.completions.create(
                messages=messages,
                max_completion_tokens=2000,
                temperature=0.7,
                top_p=0.95,
                frequency_penalty=0.0,
                presence_penalty=0.0,
                model=deployment
            )
            writeOutput("Final response received from Azure OpenAI.", isCode=True)
            writeOutput(f"{final_response.choices[0].message.content}", isCode=True)
            return final_response.choices[0].message.content
        else:
            # No tool call, just return the model's direct response
            return response_message.content
    
    except AzureError as ae:
        error_message = f"Azure OpenAI error: {str(ae)}"
        writeOutput(error_message, isCode=True)
        return {"error": error_message}
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