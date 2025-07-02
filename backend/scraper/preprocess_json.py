import json
import os

def flatten_json_structure(file_path):
    """
    Flatten the nested 'details' structure in the JSON file by bringing
    properties up to the top level.
    """
    print(f"Processing file: {file_path}")
    
    try:
        # Read the JSON file
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Process each item in the array
        for item in data:
            if 'details' in item:
                details = item['details']
                
                # Move each property from details to the top level
                for key, value in details.items():
                    # Skip 'name' if it already exists at the top level
                    if key == 'name' and 'name' in item:
                        continue
                    # For part_number, rename it to a more descriptive name
                    elif key == 'part_number':
                        item['manufacturer_number'] = value
                    # Otherwise, copy the property to the top level
                    else:
                        item[key] = value
                
                # Remove the details object
                del item['details']
        
        # Write the flattened data back to the file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        
        print(f"Successfully flattened {file_path}")
        
    except Exception as e:
        print(f"Error processing {file_path}: {str(e)}")

def process_all_json_files(folder_path):
    """Process all JSON files in the specified folder."""
    json_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) 
                  if f.endswith('.json')]
    
    print(f"Found {len(json_files)} JSON files to process")
    
    for json_file in json_files:
        flatten_json_structure(json_file)
    
    print("Processing complete!")

if __name__ == "__main__":
    # Path to the folder containing JSON files
    folder_path = r"c:\D_Backup\Github\Applications_2025\instalily-case-study\backend\scraper\data"
    json_files = [os.path.join(folder_path, f) for f in os.listdir(folder_path) 
                if f.endswith('.json')]

    # Process a single file
    # file_path = os.path.join(folder_path, "Amana-Dishwasher-Parts.json")
    for file_path in json_files:
        flatten_json_structure(file_path)
    
    # Or process all files in the folder
    # process_all_json_files(folder_path)