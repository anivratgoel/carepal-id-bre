import json

def analyze_json():
    input_file = 'bre_output.json'
    try:
        with open(input_file, 'r') as f:
            data = json.load(f)
            
        total = len(data)
        true_count = sum(1 for item in data if item.get('active_credit_card') is True)
        false_count = sum(1 for item in data if item.get('active_credit_card') is False)
        
        print(f"Total Records: {total}")
        print(f"Active Credit Card (True): {true_count}")
        print(f"Active Credit Card (False): {false_count}")
        
    except FileNotFoundError:
        print(f"Error: {input_file} not found.")
    except json.JSONDecodeError:
        print(f"Error: Failed to decode JSON from {input_file}.")

if __name__ == "__main__":
    analyze_json()
