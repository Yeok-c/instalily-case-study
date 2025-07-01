from dotenv import load_dotenv

from azure.cosmos import CosmosClient
from azure.identity import DefaultAzureCredential
import datetime
import json
import os
import glob
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

def getLastRequestCharge(c):
    return c.client_connection.last_response_headers["x-ms-request-charge"]
def setup_chat_history_container(database):
    """
    Create or get the chat history container
    """
    try:
        container_name = "chat_histories"
        container = database.create_container_if_not_exists(
            id=container_name,
            partition_key="/user_id",
        )
        return container
    except Exception as e:
        print(f"Error setting up chat history container: {str(e)}")
        raise
def save_chat_history(container, user_id, chat_id, messages):
    """
    Save chat history to Cosmos DB
    """
    try:
        # Create document with user_id as partition key and chat_id as id
        document = {
            "id": chat_id,
            "user_id": user_id,
            "messages": messages,
            "last_updated": datetime.datetime.utcnow().isoformat()
        }
        
        # Upsert to create or update
        container.upsert_item(document)
        return True
    except Exception as e:
        print(f"Error saving chat history: {str(e)}")
        return False

def get_chat_history(container, user_id, chat_id):
    """
    Retrieve chat history from Cosmos DB
    """
    try:
        # Query with both user_id (partition key) and chat_id
        query = f"SELECT * FROM c WHERE c.id = '{chat_id}' AND c.user_id = '{user_id}'"
        items = list(container.query_items(
            query=query,
            enable_cross_partition_query=False
        ))
        
        if items:
            return items[0].get("messages", [])
        return []
    except Exception as e:
        print(f"Error retrieving chat history: {str(e)}")
        return []

def clear_chat_history(container, user_id, chat_id):
    """
    Clear chat history in Cosmos DB by saving empty message list
    """
    try:
        save_chat_history(container, user_id, chat_id, [])
        return True
    except Exception as e:
        print(f"Error clearing chat history: {str(e)}")
        return False
    
def upload_json_files_to_cosmos(container, data_dir, writeOutput=print):
    """
    Upload all JSON files from a directory to CosmosDB
    
    Args:
        container: CosmosDB container client
        data_dir: Directory containing JSON files
        writeOutput: Function to output results
    
    Returns:
        dict: Summary of upload results
    """
    # Get absolute path to data directory
    base_dir = Path(__file__).parent.parent
    full_data_dir = os.path.join(base_dir, data_dir)
    
    if not os.path.exists(full_data_dir):
        writeOutput(f"Error: Data directory not found at {full_data_dir}")
        return {"error": "Directory not found", "uploaded": 0, "failed": 0}
    
    # Find all JSON files
    json_files = glob.glob(os.path.join(full_data_dir, "*.json"))
    
    if not json_files:
        writeOutput(f"No JSON files found in {full_data_dir}")
        return {"error": "No JSON files found", "uploaded": 0, "failed": 0}
    
    # Upload stats
    stats = {
        "total": len(json_files),
        "uploaded": 0,
        "failed": 0,
        "files": []
    }
    
    for json_file in json_files:
        file_name = os.path.basename(json_file)
        brand_product = os.path.splitext(file_name)[0]  # Remove .json extension
        
        try:
            # Load JSON content
            with open(json_file, 'r', encoding='utf-8') as f:
                parts_data = json.load(f)
            
            # Prepare document with metadata
            document = {
                "id": brand_product.replace("-", "_").lower(),  # Create a valid ID
                "brand_product": brand_product,
                "type": "parts_catalog",
                "parts": parts_data
            }
            
            # Upload to Cosmos DB
            created_item = container.upsert_item(document)
            
            stats["uploaded"] += 1
            stats["files"].append({
                "file": file_name, 
                "status": "success", 
                "id": created_item["id"],
                "request_charge": getLastRequestCharge(container)
            })
            
            writeOutput(f"Uploaded: {file_name} -> Document ID: {created_item['id']}")
            
        except Exception as e:
            stats["failed"] += 1
            stats["files"].append({"file": file_name, "status": "failed", "error": str(e)})
            writeOutput(f"Failed to upload {file_name}: {str(e)}")
    
    writeOutput(f"Upload complete. Total: {stats['total']}, Succeeded: {stats['uploaded']}, Failed: {stats['failed']}")
    return stats


def runDemo(writeOutput):
    load_dotenv()

    client = CosmosClient.from_connection_string(os.getenv("COSMOS_CONNECTION_STRING"))

    databaseName = os.getenv("CONFIGURATION__AZURECOSMOSDB__DATABASENAME", "cosmicworks")
    database = client.get_database_client(databaseName)

    writeOutput(f"Get database:\t{database.id}")

    containerName = os.getenv("CONFIGURATION__AZURECOSMOSDB__CONTAINERNAME", "products")
    container = database.get_container_client(containerName)

    writeOutput(f"Get container:\t{container.id}")

    # Original demo code for reference
    new_item = {
        "id": "aaaaaaaa-0000-1111-2222-bbbbbbbbbbbb",
        "category": "gear-surf-surfboards",
        "name": "Yamba Surfboard",
        "quantity": 12,
        "sale": False,
    }
    created_item = container.upsert_item(new_item)

    writeOutput(f"Upserted item:\t{created_item}")
    writeOutput("Request charge:\t" f"{getLastRequestCharge(container)}")

    # Add option to upload all JSON files from data directory
    data_dir = "./scraper/data"
    upload_stats = upload_json_files_to_cosmos(container, data_dir, writeOutput)
    
    # Query to verify upload
    queryText = "SELECT * FROM products p WHERE p.type = 'parts_catalog'"
    results = container.query_items(
        query=queryText,
        enable_cross_partition_query=True,
    )

    items = [{"id": item["id"], "brand_product": item["brand_product"]} for item in results]
    output = json.dumps(items, indent=2)

    writeOutput("Uploaded parts catalogs: ")
    writeOutput(output, isCode=True)

def test_upload_json_files(writeOutput=None):
    """
    Test function to upload JSON files to Cosmos DB
    
    Args:
        writeOutput: Optional function to handle output messages.
                    If None, defaults to print function.
    """
    # Use provided writeOutput function or default to print
    if writeOutput is None:
        def log_output(message, isCode=False):
            print(message)
        writeOutput = log_output
    
    load_dotenv()
    
    client = CosmosClient.from_connection_string(os.getenv("COSMOS_CONNECTION_STRING"))
    
    databaseName = os.getenv("CONFIGURATION__AZURECOSMOSDB__DATABASENAME", "cosmicworks")
    database = client.get_database_client(databaseName)
    
    containerName = os.getenv("CONFIGURATION__AZURECOSMOSDB__CONTAINERNAME", "products")
    container = database.get_container_client(containerName)
    
    writeOutput(f"Connected to database: {database.id}, container: {containerName}")
    
    # Upload all JSON files from data directory
    data_dir = "./scraper/data"
    upload_stats = upload_json_files_to_cosmos(container, data_dir, writeOutput)
    
    # Print summary
    writeOutput("\nUpload Summary:")
    # writeOutput(f"Total files: {upload_stats['total']}")
    # writeOutput(f"Uploaded: {upload_stats['uploaded']}")
    # writeOutput(f"Failed: {upload_stats['failed']}")
    
    for key, val in upload_stats.items():
        if key == "files":
            writeOutput(f"{key.capitalize()}:")
            for file_info in val:
                writeOutput(f"  - {file_info['file']}: {file_info['status']}")
                if file_info.get("id"):
                    writeOutput(f"    ID: {file_info['id']}, Request Charge: {file_info.get('request_charge', 'N/A')}")
                if file_info.get("error"):
                    writeOutput(f"    Error: {file_info['error']}")
        else:
            writeOutput(f"{key.capitalize()}: {val}")
    
    return upload_stats

def run_cosmos_queries(writeOutput=None):
    """
    Run test queries against CosmosDB:
    1. List all Dacor Refrigerator parts
    2. Find item by partselect_number
    3. Find item by manufacturer_number and return specific fields
    
    Args:
        writeOutput: Optional function to handle output messages.
                    If None, defaults to print function.
    """
    # Use provided writeOutput function or default to print
    if writeOutput is None:
        writeOutput = print
    
    load_dotenv()
    
    # Connect to Cosmos DB
    client = CosmosClient.from_connection_string(os.getenv("COSMOS_CONNECTION_STRING"))
    
    databaseName = os.getenv("CONFIGURATION__AZURECOSMOSDB__DATABASENAME", "cosmicworks")
    database = client.get_database_client(databaseName)
    
    containerName = os.getenv("CONFIGURATION__AZURECOSMOSDB__CONTAINERNAME", "products")
    container = database.get_container_client(containerName)
    
    writeOutput("Connected to CosmosDB")
    writeOutput(f"Database: {database.id}, Container: {containerName}")
    writeOutput("-" * 80)
    
    # Query 1: List all Dacor Refrigerator parts
    writeOutput("QUERY 1: List all Dacor Refrigerator parts")
    query1 = """
    SELECT p.brand_product, item.name, item.manufacturer_number, item.partselect_number, item.price
    FROM products p
    JOIN item IN p.parts
    WHERE p.brand_product LIKE 'Dacor-Refrigerator%'
    """
    
    items1 = list(container.query_items(
        query=query1,
        enable_cross_partition_query=True
    ))
    
    if items1:
        writeOutput(f"Found {len(items1)} Dacor refrigerator parts:")
        for i, item in enumerate(items1, 1):
            writeOutput(f"{i}. {item['name']} - {item['manufacturer_number']} - {item['price']}")
    else:
        writeOutput("No Dacor refrigerator parts found.")
    
    writeOutput("-" * 80)
    
    # Query 2: Find item of partselect_number=PS8728568
    writeOutput("QUERY 2: Find item with partselect_number=PS8728568")
    query2 = """
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
    """

    items2 = list(container.query_items(
        query=query2,
        enable_cross_partition_query=True
    ))

    if items2:
        writeOutput(f"Found item with partselect_number PS8728568:")
        writeOutput(json.dumps(items2[0], indent=2), isCode=True)
    else:
        writeOutput("No item found with partselect_number PS8728568")
    
    # Query 3: Find item with manufacturer_number=WR23X37285 and return specific fields
    writeOutput("QUERY 3: Find item with manufacturer_number=WR23X37285")
    query3 = """
    SELECT p.brand_product, 
           item.name, 
           item.details.reviews_count,
           item.details.reviews
    FROM products p
    JOIN item IN p.parts
    WHERE item.manufacturer_number = 'WR23X37285'
    """
    
    items3 = list(container.query_items(
        query=query3,
        enable_cross_partition_query=True
    ))
    
    if items3:
        writeOutput(f"Found item with manufacturer_number WR23X37285:")
        result = {
            "brand_product": items3[0]["brand_product"],
            "name": items3[0]["name"],
            "reviews_count": items3[0].get("reviews_count"),
            "reviews": items3[0].get("reviews")
        }
        writeOutput(json.dumps(result, indent=2), isCode=True)
    else:
        writeOutput("No item found with manufacturer_number WR23X37285")

if __name__ == "__main__":
    # When run directly, execute the test function
    test_upload_json_files()
    run_cosmos_queries()