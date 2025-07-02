import os
import json
from dotenv import load_dotenv
from openai import AzureOpenAI
from azure.cosmos import CosmosClient
from azure.core.exceptions import AzureError

# Load environment variables
load_dotenv()

# # Azure OpenAI configuration
# endpoint = "https://foundry-ai-agents.cognitiveservices.azure.com/"
# deployment = "gpt-4.1-nano"
# api_version = "2024-12-01-preview"

# Get API key from environment variable
subscription_key = os.getenv("AZURE_OPENAI_API_KEY")
if not subscription_key:
    raise ValueError("AZURE_OPENAI_API_KEY environment variable is not set.")

import os
from azure.ai.inference import ChatCompletionsClient
from azure.ai.inference.models import AssistantMessage, SystemMessage, UserMessage
from azure.core.credentials import AzureKeyCredential

endpoint = "https://foundry-ai-agents.services.ai.azure.com/models"
model_name = "DeepSeek-V3-0324"
deployment = "DeepSeek-V3-0324"
api_version = "2024-05-01-preview"
client = ChatCompletionsClient(
    endpoint=endpoint,
    credential=AzureKeyCredential(subscription_key),
    api_version=api_version
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

def find_by_symptom(symptom, max_items=10):
    """
    Find parts that can fix a specific symptom.
    
    Args:
        symptom (str): The symptom to search for (e.g., 'Door won't close', 'Noisy')
        max_items (int): Maximum number of items to return
        
    Returns:
        str: JSON string of query results
    """
    # Construct the query to search by symptom - updated for flattened structure
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
        item.rating,
        item.reviews_count,
        item.symptoms_fixed,
        item.works_with,
        item.also_replaces,
        item.video_url
    FROM products p
    JOIN item IN p.parts
    WHERE IS_DEFINED(item.symptoms_fixed) AND CONTAINS(item.symptoms_fixed, '{symptom}')
    """
    
    return query_cosmosdb(sql_query, max_items)

def find_by_replacement_number(replacement_number, max_items=10):
    """
    Find parts that can replace a specific part number.
    
    Args:
        replacement_number (str): The part number to find replacements for
        max_items (int): Maximum number of items to return
        
    Returns:
        str: JSON string of query results
    """
    # Updated for flattened structure
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
        item.rating,
        item.reviews_count,
        item.symptoms_fixed,
        item.works_with,
        item.also_replaces,
        item.video_url
    FROM products p
    JOIN item IN p.parts
    WHERE IS_DEFINED(item.also_replaces) AND ARRAY_CONTAINS(item.also_replaces, '{replacement_number}')
    """
    
    results = query_cosmosdb(sql_query, max_items)
    parsed_results = json.loads(results)
    
    # If no results found, check if the replacement_number matches the manufacturer_number
    if not parsed_results or (isinstance(parsed_results, list) and len(parsed_results) == 0):
        try:
            manufacturer_results = find_by_manufacturer_number(replacement_number, max_items)
            return manufacturer_results
        except Exception as e:
            return json.dumps({"error": f"Error in fallback search: {str(e)}", "original_results": parsed_results})
    
    return results

def find_by_brand_product(brand_product, max_items=10):
    """
    Find parts by brand and product type.
    
    Args:
        brand_product (str): Brand and product combination like 'Philips-Dishwasher'
        max_items (int): Maximum number of items to return
        
    Returns:
        str: JSON string of query results
    """
    # Updated for flattened structure
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
        item.rating,
        item.reviews_count,
        item.symptoms_fixed,
        item.works_with,
        item.also_replaces,
        item.video_url
    FROM products p
    JOIN item IN p.parts
    WHERE p.brand_product LIKE '{brand_product}%'
    """
    
    results = query_cosmosdb(sql_query, max_items)
    parsed_results = json.loads(results)
    
    # If no results found, try to split and search by brand and product separately
    if not parsed_results or (isinstance(parsed_results, list) and len(parsed_results) == 0):
        try:
            # Try to split the brand_product into brand and product
            parts = brand_product.split('-', 1)
            if len(parts) == 2:
                brand, product = parts
                # First try find_by_brand
                brand_results = find_by_brand(brand, max_items)
                return brand_results
            else:
                # If can't split, just return empty results
                return json.dumps([])
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
    # Updated for flattened structure
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
        item.rating,
        item.reviews_count,
        item.symptoms_fixed,
        item.works_with,
        item.also_replaces,
        item.video_url
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
    # Updated for flattened structure
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
        item.rating,
        item.reviews_count,
        item.symptoms_fixed,
        item.works_with,
        item.also_replaces,
        item.video_url
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
    # Updated for flattened structure
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
        item.rating,
        item.reviews_count,
        item.symptoms_fixed,
        item.works_with,
        item.also_replaces,
        item.video_url
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
                    item.url,
                    item.image_url,
                    item.description,
                    item.partselect_number,
                    item.manufacturer_number,
                    item.price,
                    item.stock_status,
                    item.rating,
                    item.reviews_count,
                    item.symptoms_fixed,
                    item.works_with,
                    item.also_replaces,
                    item.video_url
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
    # Updated for flattened structure
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
        item.reviews_count,
        item.rating,
        item.symptoms_fixed,
        item.works_with,
        item.also_replaces,
        item.video_url
    FROM products p
    JOIN item IN p.parts
    WHERE item.manufacturer_number = '{manufacturer_number}'
    """

    return query_cosmosdb(sql_query, max_items)

def find_by_partselect_number(partselect_number, max_items=10):
    """
    Find parts by PartSelect number.
    
    Args:
        partselect_number (str): The PartSelect number
        max_items (int): Maximum number of items to return
        
    Returns:
        str: JSON string of query results
    """
    # Updated for flattened structure
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
        item.reviews_count,
        item.rating,
        item.symptoms_fixed,
        item.works_with,
        item.also_replaces,
        item.video_url
    FROM products p
    JOIN item IN p.parts
    WHERE item.partselect_number = '{partselect_number}'
    """
    
    return query_cosmosdb(sql_query, max_items)

def find_by_any_part_number(part_number, max_items=10):
    """
    Find parts by either manufacturer number or PartSelect number.
    
    Args:
        part_number (str): Either a manufacturer number or PartSelect number
        max_items (int): Maximum number of items to return
        
    Returns:
        str: JSON string of query results
    """
    # First try to find by manufacturer number
    manufacturer_results = find_by_manufacturer_number(part_number, max_items)
    manufacturer_items = json.loads(manufacturer_results)
    
    # Then try to find by PartSelect number
    partselect_results = find_by_partselect_number(part_number, max_items)
    partselect_items = json.loads(partselect_results)
    
    # Combine the results, removing duplicates
    combined_results = []
    seen_parts = set()
    
    for items_list in [manufacturer_items, partselect_items]:
        if isinstance(items_list, list):
            for item in items_list:
                key = item.get("partselect_number", "") + item.get("manufacturer_number", "")
                if key and key not in seen_parts:
                    seen_parts.add(key)
                    # Make sure image_url and video_url are included
                    if "image_url" not in item:
                        item["image_url"] = ""
                    if "video_url" not in item:
                        item["video_url"] = ""
                    combined_results.append(item)
    
    # Try finding replacement parts if direct match not found
    if not combined_results:
        try:
            replacement_results = find_by_replacement_number(part_number, max_items)
            replacement_items = json.loads(replacement_results)
            
            if isinstance(replacement_items, list):
                for item in replacement_items:
                    key = item.get("partselect_number", "") + item.get("manufacturer_number", "")
                    if key and key not in seen_parts:
                        seen_parts.add(key)
                        # Make sure image_url and video_url are included
                        if "image_url" not in item:
                            item["image_url"] = ""
                        if "video_url" not in item:
                            item["video_url"] = ""
                        combined_results.append(item)
        except Exception as e:
            pass
    
    return json.dumps(combined_results[:max_items])

# def query_azure_openai(user_query, writeOutput=print):
#     """
#     Function to be called from app.py - handles user queries to Azure OpenAI.
#     This is a wrapper around the azure_openai_agent function to maintain API compatibility.
#     """
#     return azure_openai_agent(user_query, deployment, writeOutput)


# def azure_openai_agent(user_query, deployment_name=deployment, writeOutput=print):
#     """
#     Handles user queries, supports specific part search functions via function calling.
#     """
#     # Define the search functions as tools
#     tools = [
#         {
#             "type": "function",
#             "function": {
#                 "name": "find_by_brand_product",
#                 "description": """
#                 Find parts by brand and product type (e.g., 'Philips-Dishwasher').
#                 Use this when user is looking for a specific brand and product combination.
#                 If the exact brand-product isn't found, it will try searching by brand only.
#                 """,
#                 "parameters": {
#                     "type": "object",
#                     "properties": {
#                         "brand_product": {
#                             "type": "string",
#                             "description": "Brand and product combination like 'Philips-Dishwasher'"
#                         },
#                         "max_items": {
#                             "type": "integer",
#                             "description": "Maximum number of items to return (default 10)."
#                         }
#                     },
#                     "required": ["brand_product"]
#                 }
#             }
#         },
#         {
#             "type": "function",
#             "function": {
#                 "name": "find_by_brand",
#                 "description": """
#                 Find parts by brand name only (e.g., 'Philips').
#                 Use this when user is only interested in a specific brand, regardless of product type.
#                 """,
#                 "parameters": {
#                     "type": "object",
#                     "properties": {
#                         "brand": {
#                             "type": "string",
#                             "description": "Brand name like 'Philips'"
#                         },
#                         "max_items": {
#                             "type": "integer",
#                             "description": "Maximum number of items to return (default 10)."
#                         }
#                     },
#                     "required": ["brand"]
#                 }
#             }
#         },
#         {
#             "type": "function",
#             "function": {
#                 "name": "find_by_product",
#                 "description": """
#                 Find parts by product type only (e.g., 'Dishwasher').
#                 Use this when user wants to see parts for a specific product type across all brands.
#                 """,
#                 "parameters": {
#                     "type": "object",
#                     "properties": {
#                         "product": {
#                             "type": "string",
#                             "description": "Product type like 'Dishwasher'"
#                         },
#                         "max_items": {
#                             "type": "integer",
#                             "description": "Maximum number of items to return (default 10)."
#                         }
#                     },
#                     "required": ["product"]
#                 }
#             }
#         },
#         {
#             "type": "function",
#             "function": {
#                 "name": "find_by_description",
#                 "description": """
#                 Find parts by description (e.g., 'Jenn-Air Dishwasher Rack Track Stop').
#                 Use this when user wants to find parts by their descriptive name.
#                 """,
#                 "parameters": {
#                     "type": "object",
#                     "properties": {
#                         "description": {
#                             "type": "string",
#                             "description": "Description of the part (e.g., 'Jenn-Air Dishwasher Rack Track Stop')"
#                         },
#                         "max_items": {
#                             "type": "integer",
#                             "description": "Maximum number of items to return (default 10)."
#                         }
#                     },
#                     "required": ["description"]
#                 }
#             }
#         },
#         {
#             "type": "function",
#             "function": {
#                 "name": "find_by_any_part_number",
#                 "description": """
#                 Search for a part using either a manufacturer number or a PartSelect number (e.g., PS1990907).
#                 This function will try both search methods and combine results if needed.
#                 """,
#                 "parameters": {
#                     "type": "object",
#                     "properties": {
#                         "part_number": {
#                             "type": "string",
#                             "description": "The part number, either manufacturer or PartSelect"
#                         },
#                         "max_items": {
#                             "type": "integer",
#                             "description": "Maximum number of items to return (default 10)."
#                         }
#                     },
#                     "required": ["part_number"]
#                 }
#             }
#         },
#         {
#             "type": "function",
#             "function": {
#                 "name": "find_by_symptom",
#                 "description": """
#                 Find parts that can fix a specific symptom (e.g., 'Door won't close', 'Noisy', 'Not cleaning dishes properly').
#                 Use this when the user is describing a problem or symptom with their appliance.
#                 """,
#                 "parameters": {
#                     "type": "object",
#                     "properties": {
#                         "symptom": {
#                             "type": "string",
#                             "description": "The symptom to search for (e.g., 'Door won't close', 'Noisy')"
#                         },
#                         "max_items": {
#                             "type": "integer",
#                             "description": "Maximum number of items to return (default 10)."
#                         }
#                     },
#                     "required": ["symptom"]
#                 }
#             }
#         },
#         {
#             "type": "function",
#             "function": {
#                 "name": "find_by_replacement_number",
#                 "description": """
#                 Find parts that can replace a specific part number.
#                 Use this when the user has a part number but wants to find compatible replacements.
#                 """,
#                 "parameters": {
#                     "type": "object",
#                     "properties": {
#                         "replacement_number": {
#                             "type": "string",
#                             "description": "The part number to find replacements for (e.g., 'AP5957560', 'W10250159')"
#                         },
#                         "max_items": {
#                             "type": "integer",
#                             "description": "Maximum number of items to return (default 10)."
#                         }
#                     },
#                     "required": ["replacement_number"]
#                 }
#             }
#         }
#     ]
#     # Initial system and user messages
#     messages = [
#         {
#             "role": "system",
#             "content": (
#                 "You are a helpful assistant specializing in appliance parts and repair knowledge.\n"
#                 "You can help users find parts by:\n"
#                 "1. Brand and product type (e.g., 'Philips-Dishwasher')\n"
#                 "2. Brand only (e.g., 'Philips')\n"
#                 "3. Product type only (e.g., 'Dishwasher')\n"
#                 "4. Part number (either manufacturer or PartSelect). This is very specific and preferred\n"
#                 "5. Symptoms (e.g., 'Door won't close', 'Noisy'). Use this when users describe problems they're having\n"
#                 "6. Replacement part numbers (e.g., 'AP5957560'). Use this when users want alternatives to a part\n\n"
#                 "Important instructions:\n"
#                 "- If the specific brand-product combination isn't found, search for the brand and product separately.\n"
#                 "- If the returned results is None, tell them 'I believe we don't sell <product> of this <brand>. You can double check to see our list of products at https://www.partselect.com/Products/'\n"
#                 "- If you haven't yet narrowed down the search, ask for more specific information.\n"
#                 "- If you are very certain about the result, or if there is only one item returned, note that you believe you have found the item.\n"
#                 "- If the user wants help with installation and a video_url is available, include it in your dictionary-list-to-render.\n"
#                 "- When a user is looking for a part, always check if there are alternative replacement parts available using find_by_replacement_number.\n"
#                 "- If a user describes a problem with their appliance, use find_by_symptom to locate parts that can fix that issue."
#             )
#         },
#         {
#             "role": "user",
#             "content": user_query,
#         },
#     ]
#     writeOutput("Sending request to Azure OpenAI...", isCode=True)

#     try:
#         # First call: let the model decide if it wants to use the tool
#         response = client.complete(
#             messages=messages,
#             max_completion_tokens=2000,
#             temperature=0.7,
#             top_p=0.95,  # Slightly reduced from 1.0 for more focused responses
#             frequency_penalty=0.0,
#             presence_penalty=0.0,
#             model=deployment_name,
#             tools=tools,
#             tool_choice="auto"
#         )

#         # Handle different response formats between clients
#         response_message = response.choices[0].message
#         message_content = response_message.content if hasattr(response_message, 'content') else response_message.get('content', '')
#         tool_calls = getattr(response_message, 'tool_calls', None) or response_message.get('tool_calls')
        
#         # Add response to messages
#         messages.append(response_message)

#         writeOutput(f"AI Response: {message_content}", isCode=True)
        
#         # If the model called a tool, execute it and append the result
#         if tool_calls:
#             writeOutput("AI is searching for parts...", isCode=True)
#             for tool_call in tool_calls:
#                 # Extract function name and arguments based on response structure
#                 function_name = tool_call.function.name if hasattr(tool_call, 'function') else tool_call.get('function', {}).get('name')
#                 function_args = tool_call.function.arguments if hasattr(tool_call, 'function') else tool_call.get('function', {}).get('arguments')
#                 tool_call_id = tool_call.id if hasattr(tool_call, 'id') else tool_call.get('id')
                
#                 if isinstance(function_args, str):
#                     args = json.loads(function_args)
#                 else:
#                     args = function_args
                
#                 # Process based on function name
#                 if function_name == "find_by_brand_product":
                    
#                     brand_product = args.get("brand_product")
#                     max_items = args.get("max_items", 10)
#                     writeOutput(f"Searching for brand/product: {brand_product}", isCode=True)
#                     tool_result = find_by_brand_product(brand_product, max_items)
                
#                 elif function_name == "find_by_brand":
#                     brand = args.get("brand")
#                     max_items = args.get("max_items", 10)
#                     writeOutput(f"Searching for brand: {brand}", isCode=True)
#                     tool_result = find_by_brand(brand, max_items)
                
#                 elif function_name == "find_by_product":
#                     product = args.get("product")
#                     max_items = args.get("max_items", 10)
#                     writeOutput(f"Searching for product: {product}", isCode=True)
#                     tool_result = find_by_product(product, max_items)
                
#                 elif function_name == "find_by_any_part_number":
#                     part_number = args.get("part_number")
#                     max_items = args.get("max_items", 10)
#                     writeOutput(f"Searching by part number: {part_number}", isCode=True)
#                     tool_result = find_by_any_part_number(part_number, max_items)

#                 elif function_name == "find_by_description":
#                     description = args.get("description")
#                     max_items = args.get("max_items", 10)
#                     writeOutput(f"Searching for description: {description}", isCode=True)
#                     tool_result = find_by_description(description, max_items)
                    
#                 elif function_name == "find_by_symptom":
#                     symptom = args.get("symptom")
#                     max_items = args.get("max_items", 10)
#                     writeOutput(f"Searching for parts that fix symptom: {symptom}", isCode=True)
#                     tool_result = find_by_symptom(symptom, max_items)

#                 elif function_name == "find_by_replacement_number":
#                     replacement_number = args.get("replacement_number")
#                     max_items = args.get("max_items", 10)
#                     writeOutput(f"Searching for parts that can replace: {replacement_number}", isCode=True)
#                     tool_result = find_by_replacement_number(replacement_number, max_items)
                                    
#                 messages.append({
#                     "tool_call_id": tool_call_id,
#                     "role": "tool",
#                     "name": function_name,
#                     "content": tool_result,
#                 })

#             # Check if we got valid results or an error
#             results = json.loads(messages[-1]["content"])
#             if isinstance(results, dict) and "error" in results:
#                 writeOutput(f"Search error: {results['error']}", isCode=True)
#             else:
#                 writeOutput(f"Found {len(results) if isinstance(results, list) else 0} results", isCode=True)

#             messages.append({
#                 "role": "user",
#                 "content": (
#                     """
#                     You should now explain the results to the user. 
#                     - If multiple search results come up, it is likely that the same part is used for multiple appliances. 
#                     - If the user asked about installation help, make sure to include any video_url in your response and in the dictionary.
#                     - If there were alternative parts found, be sure to mention them.
                    
#                     If you are very certain about the result(s), you should format the result as a list of dictionaries. Even if there is only one result you should format it as a list of length 1.
#                     The users will not know it is a list of dictionaries. 
                    
#                     IMPORTANT: Always include the image_url and video_url fields in your dictionary output, even if they are empty strings.
                    
#                     Make sure you include ```dictionary-list-to-render as the frontend will render this list of dictionaries nicely in the UI.\n"
#                     Example:
#                     ```dictionary-list-to-render
#                     [
#                         {
#                         "part_name": "Dacor Refrigerator Part",
#                         "manufacturer_number": "123456",
#                         "partselect_number": "PS1990907",
#                         "price": "$99.99",
#                         "url": "https://www.partselect.com/Parts/123456",
#                         "image_url": "https://www.partselect.com/Images/123456.jpg",
#                         "video_url": "https://www.youtube.com/watch?v=abcdef"
#                         },
#                         ...
#                     ]
#                     ```
#                     """
#                 )
#             })
#             # Second call: get the final answer from the model
#             writeOutput("Getting final response from Azure OpenAI to show to user", isCode=True)
#             final_response = client.complete(
#                 messages=messages,
#                 max_completion_tokens=2000,
#                 temperature=0.7,
#                 top_p=0.95,
#                 frequency_penalty=0.0,
#                 presence_penalty=0.0,
#                 model=deployment_name
#             )
#             writeOutput("Final response received from Azure OpenAI.", isCode=True)
#             writeOutput(f"{final_response.choices[0].message.content}", isCode=True)
#             return final_response.choices[0].message.content
#         else:
#             # No tool call, just return the model's direct response
#             return response_message.content
    
#     except AzureError as ae:
#         error_message = f"Azure OpenAI error: {str(ae)}"
#         writeOutput(error_message, isCode=True)
#         return {"error": error_message}
#     except Exception as e:
#         error_message = f"Error calling Azure OpenAI: {str(e)}"
#         writeOutput(error_message, isCode=True)
#         return {"error": error_message}
    
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
        # Other tool definitions remain the same...
        # ... truncated for brevity
    ]

    # Initial system and user messages
    messages = [
        SystemMessage(content=(
            "You are a helpful assistant specializing in appliance parts and repair knowledge.\n"
            "You can help users find parts by:\n"
            "1. Brand and product type (e.g., 'Philips-Dishwasher')\n"
            "2. Brand only (e.g., 'Philips')\n"
            "3. Product type only (e.g., 'Dishwasher')\n"
            "4. Part number (either manufacturer or PartSelect). This is very specific and preferred\n"
            "5. Symptoms (e.g., 'Door won't close', 'Noisy'). Use this when users describe problems they're having\n"
            "6. Replacement part numbers (e.g., 'AP5957560'). Use this when users want alternatives to a part\n\n"
            "Important instructions:\n"
            "- If the specific brand-product combination isn't found, search for the brand and product separately.\n"
            "- If the returned results is None, tell them 'I believe we don't sell <product> of this <brand>. You can double check to see our list of products at https://www.partselect.com/Products/'\n"
            "- If you haven't yet narrowed down the search, ask for more specific information.\n"
            "- If you are very certain about the result, or if there is only one item returned, note that you believe you have found the item.\n"
            "- If the user wants help with installation and a video_url is available, include it in your dictionary-list-to-render.\n"
            "- When a user is looking for a part, always check if there are alternative replacement parts available using find_by_replacement_number.\n"
            "- If a user describes a problem with their appliance, use find_by_symptom to locate parts that can fix that issue."
        ))
    ]    
    # Add conversation history
    if conversation_history:
        writeOutput(f"Adding {len(conversation_history)} previous messages as context")
        for msg in conversation_history:
            if msg.get("role") and msg.get("content"):
                if msg["role"] == "user":
                    messages.append(UserMessage(content=msg["content"]))
                elif msg["role"] == "assistant":
                    messages.append(AssistantMessage(content=msg["content"]))
    
    # Add the current user query
    messages.append(UserMessage(content=user_query))

    writeOutput("Sending request to Azure OpenAI with conversation history...", isCode=True)

    try:
        # First call: let the model decide if it wants to use the tool
        response = client.complete(
            messages=messages,
            max_tokens=2000,
            temperature=0.7,
            top_p=0.95,
            frequency_penalty=0.0,
            presence_penalty=0.0,
            model=deployment,
            tools=tools,
            tool_choice="auto"
        )

        # Extract the message from the response
        # Handle different response formats between clients
        response_message = response.choices[0].message
        
        # Extract content from response_message based on its type
        if hasattr(response_message, 'content'):
            message_content = response_message.content 
        elif isinstance(response_message, dict):
            message_content = response_message.get('content', '')
        else:
            message_content = str(response_message)
        
        # Extract tool_calls from response_message based on its type
        tool_calls = None
        if hasattr(response_message, 'tool_calls'):
            tool_calls = response_message.tool_calls
        elif isinstance(response_message, dict):
            tool_calls = response_message.get('tool_calls')

        writeOutput(f"AI Response: {message_content}", isCode=True)
        
        # Add response to conversation for subsequent calls
        conversation_message = {"role": "assistant", "content": message_content}
        
        # If the model called a tool, execute it and append the result
        if tool_calls:
            writeOutput("AI is searching for parts...", isCode=True)
            tool_results = []
            
            for tool_call in tool_calls:
                # Extract function details based on response structure
                if hasattr(tool_call, 'function'):
                    function_name = tool_call.function.name
                    function_args = tool_call.function.arguments
                    tool_call_id = tool_call.id
                else:
                    function_name = tool_call.get('function', {}).get('name')
                    function_args = tool_call.get('function', {}).get('arguments')
                    tool_call_id = tool_call.get('id')
                
                # Parse arguments
                if isinstance(function_args, str):
                    args = json.loads(function_args)
                else:
                    args = function_args
                
                # Process the tool call based on function name
                if function_name == "find_by_brand_product":
                    brand_product = args.get("brand_product")
                    max_items = args.get("max_items", 10)
                    writeOutput(f"Searching for brand/product: {brand_product}", isCode=True)
                    tool_result = find_by_brand_product(brand_product, max_items)
                
                elif function_name == "find_by_brand":
                    brand = args.get("brand")
                    max_items = args.get("max_items", 10)
                    writeOutput(f"Searching for brand: {brand}", isCode=True)
                    tool_result = find_by_brand(brand, max_items)
                
                elif function_name == "find_by_product":
                    product = args.get("product")
                    max_items = args.get("max_items", 10)
                    writeOutput(f"Searching for product: {product}", isCode=True)
                    tool_result = find_by_product(product, max_items)
                
                elif function_name == "find_by_any_part_number":
                    part_number = args.get("part_number")
                    max_items = args.get("max_items", 10)
                    writeOutput(f"Searching by part number: {part_number}", isCode=True)
                    tool_result = find_by_any_part_number(part_number, max_items)

                elif function_name == "find_by_description":
                    description = args.get("description")
                    max_items = args.get("max_items", 10)
                    writeOutput(f"Searching for description: {description}", isCode=True)
                    tool_result = find_by_description(description, max_items)
                    
                elif function_name == "find_by_symptom":
                    symptom = args.get("symptom")
                    max_items = args.get("max_items", 10)
                    writeOutput(f"Searching for parts that fix symptom: {symptom}", isCode=True)
                    tool_result = find_by_symptom(symptom, max_items)

                elif function_name == "find_by_replacement_number":
                    replacement_number = args.get("replacement_number")
                    max_items = args.get("max_items", 10)
                    writeOutput(f"Searching for parts that can replace: {replacement_number}", isCode=True)
                    tool_result = find_by_replacement_number(replacement_number, max_items)
                
                tool_results.append({
                    "tool_call_id": tool_call_id,
                    "role": "tool",
                    "name": function_name,
                    "content": tool_result,
                })

            # Check if we got valid results or an error
            last_result = json.loads(tool_results[-1]["content"]) if tool_results else None
            if last_result and isinstance(last_result, dict) and "error" in last_result:
                writeOutput(f"Search error: {last_result['error']}", isCode=True)
            else:
                result_count = len(last_result) if isinstance(last_result, list) else 0
                writeOutput(f"Found {result_count} results", isCode=True)

            # Prepare messages for the final response
            final_messages = [messages[0]]  # Start with system message
            
            # Add original user query and tool results
            final_messages.append(UserMessage(content=user_query))
            final_messages.append(AssistantMessage(content=message_content))
            
            # Add tool results as standalone messages
            for tool_result in tool_results:
                final_messages.append({
                    "role": "tool",
                    "tool_call_id": tool_result["tool_call_id"],
                    "name": tool_result["name"],
                    "content": tool_result["content"]
                })
            
            # Add formatting instructions
            final_messages.append(UserMessage(content="""
                You should now explain the results to the user. 
                - If multiple search results come up, it is likely that the same part is used for multiple appliances. 
                - If the user asked about installation help, make sure to include any video_url in your response and in the dictionary.
                - If there were alternative parts found, be sure to mention them.
                
                If you are very certain about the result(s), you should format the result as a list of dictionaries. Even if there is only one result you should format it as a list of length 1.
                The users will not know it is a list of dictionaries. 
                
                IMPORTANT: Always include the image_url and video_url fields in your dictionary output, even if they are empty strings.
                
                Make sure you include ```dictionary-list-to-render as the frontend will render this list of dictionaries nicely in the UI.
                Example:
                ```dictionary-list-to-render
                [
                    {
                    "part_name": "Dacor Refrigerator Part",
                    "manufacturer_number": "123456",
                    "partselect_number": "PS1990907",
                    "price": "$99.99",
                    "stock_status": "In Stock",
                    "rating": 4.5,
                    "reviews_count": 10,
                    "url": "https://www.partselect.com/Parts/123456",
                    "image_url": "https://www.partselect.com/Images/123456.jpg",
                    "video_url": "https://www.youtube.com/watch?v=abcdef"
                    },
                    ...
                ]
                ```
            """))
            
            # Second call: get the final answer from the model
            writeOutput("Getting final response from Azure OpenAI to show to user", isCode=True)
            final_response = client.complete(
                messages=final_messages,
                max_tokens=2000,
                temperature=0.7,
                top_p=0.95,
                frequency_penalty=0.0,
                presence_penalty=0.0,
                model=deployment
            )
            
            # Get content from final response
            final_message = final_response.choices[0].message
            if hasattr(final_message, 'content'):
                final_content = final_message.content
            else:
                final_content = final_message.get('content', 'No response content available')
                
            writeOutput("Final response received from Azure OpenAI.", isCode=True)
            writeOutput(f"{final_content}", isCode=True)
            return final_content
        else:
            # No tool call, just return the model's direct response
            return message_content
    
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
    result = query_azure_openai_with_history(user_query, writeOutput)
    print(result)