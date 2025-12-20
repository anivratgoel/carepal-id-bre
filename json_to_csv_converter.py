import json
import csv
import sys

def convert_json_to_csv():
    input_file = 'bre_output.json'
    output_file = 'bre_final_output.csv'
    
    try:
        with open(input_file, 'r') as f:
            data = json.load(f)
            
        if not data:
            print("JSON file is empty.")
            return

        # key order
        headers = ["file_name", "bre_status", "sanction_limit", "active_credit_card", "hard_reject", "rejection_reason", "customer_category"]
        
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            
            for row in data:
                # Ensure all keys exist, default to None/Empty if missing (though they should exist)
                writer.writerow({
                    "file_name": row.get("file_name"),
                    "bre_status": row.get("bre_status"),
                    "sanction_limit": row.get("sanction_limit"),
                    "active_credit_card": row.get("active_credit_card"),
                    "hard_reject": row.get("hard_reject"),
                    "rejection_reason": row.get("rejection_reason"),
                    "customer_category": row.get("customer_category")
                })
                
        print(f"Successfully converted {input_file} to {output_file}")
        
    except FileNotFoundError:
        print(f"Error: {input_file} not found.")
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from {input_file}.")
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    convert_json_to_csv()
