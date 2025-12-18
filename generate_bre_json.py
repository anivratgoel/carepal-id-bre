import glob
import json
import os
from parse_reports import parse_report
from bre_engine import calculate_bre_score, filter_data_by_qec, is_credit_card

def check_active_credit_card(accounts):
    """
    Check if there is any active credit card in the accounts.
    """
    for acc in accounts:
        # Check Type
        acc_type = acc.get('accountType', 'Unknown')
        if is_credit_card(acc_type):
            # Check Status
            # 'open' field: "Yes" means active/open
            is_open = acc.get('open', '').lower() == 'yes'
            # Also check 'accountStatus' for "Closed Account" explicitly if 'open' is missing/ambiguous?
            # Usually 'open' matches 'Yes'.
            if is_open:
                return True
    return False

def generate_json():
    txt_files = glob.glob('files/*.txt')
    if not txt_files:
        print("No .txt files found.")
        return

    results = []

    for file_path in txt_files:
         try:
            for report in parse_report(file_path):
                # 1. Filter by QEC if present (Assuming user wants result on filtered execution if relevant, or original? 
                # Prompt says: "Give me a json response... for all files that you parse".
                # Usually we want the FINAL status used for decisioning.
                # I will apply QEC filtering as per bre_engine main logic.
                
                if report.get('qec_date'):
                    filtered_report = filter_data_by_qec(report)
                    result = calculate_bre_score(filtered_report)
                    report_to_check = filtered_report
                else:
                    report_to_check = report
                    result = calculate_bre_score(report)
                
                # Check Active Credit Card
                # Using the accounts from the report used for scoring (filtered or original)
                has_active_cc = check_active_credit_card(report_to_check.get('accounts', []))
                
                results.append({
                    "file_name": report.get('file_name', os.path.basename(file_path)),
                    "bre_status": result['final_status'],
                    "sanction_limit": str(result['loan_amount']), # Output as string per example "<sanction_limit>" ? Or int? Example showed quotes.
                    "active_credit_card": has_active_cc
                })
         except Exception as e:
             print(f"Error processing {file_path}: {e}")

    # Output JSON
    # Wrap in list as per example structure? 
    # Example structure:
    # {
    # {"file_name":..., ...},
    # {"file_name":..., ...}
    # }
    # Wait, the example structure provided is invalid JSON:
    # {
    # {...},
    # {...}
    # }
    # A JSON object `{}` cannot contain objects without keys.
    # It likely means a LIST of objects: `[ {...}, {...} ]` OR newline delimited JSON objects? 
    # "Give me a json response in the below structure... { {...}, {...} }"
    # Maybe they mean a dictionary keyed by something? Or just a list?
    # Common interpretation: A List `[...]`. 
    # Or maybe User actually typed `{ ... }` meaning the whole thing is a JSON object.
    # But `{ {"..."}, {"..."} }` is definitely invalid.
    # I will assume it's a list `[ ... ]`.
    
    print(json.dumps(results, indent=None)) # Indent None for compact, or 4 for readability?
    # User didn't specify compact. I'll use default.

if __name__ == "__main__":
    generate_json()
