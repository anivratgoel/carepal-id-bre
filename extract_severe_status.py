import csv
import glob
import os
from datetime import datetime
from parse_reports import parse_report
from bre_engine import parse_dpd_value, parse_month_year_key

TARGET_INSTITUTION = "Ramtirth Leasing and Finance Company Private Limited"

def get_latest_max_dpd_info(accounts):
    """
    Finds the maximum DPD across all passed accounts and history,
    and the latest month (YYYY-MM-DD) it occurred.
    
    Returns:
        (max_dpd_value, latest_date_obj)
    """
    max_dpd = 0
    latest_date = None
    
    for acc in accounts:
        history = acc.get('history48Months', [])
        for entry in history:
            # Parse DPD
            val_str = entry.get('paymentStatus', '')
            val = parse_dpd_value(val_str)
            
            # Parse Date
            key = entry.get('key') # MM-YY
            date_obj = parse_month_year_key(key)
            
            if not date_obj:
                continue
                
            if val > max_dpd:
                max_dpd = val
                latest_date = date_obj
            elif val == max_dpd and max_dpd > 0:
                # If equal, pick the later date
                if latest_date is None or date_obj > latest_date:
                    latest_date = date_obj
                    
    return max_dpd, latest_date

def get_institution_severe_remark(accounts):
    """
    Finds the most severe remark specifically from the filtered accounts.
    Checks: "Suit Filed", "Wilful Default", "Written Off", "Settled", "Substandard", "Doubtful", "Loss"
    Returns the most severe string found, or 'N/A' if none.
    """
    severe_statuses = set()
    
    # helper to normalize and check
    def check_status(s):
        if not s: return
        s_lower = s.lower()
        if "suit" in s_lower: severe_statuses.add("Suit Filed")
        elif "wilful" in s_lower: severe_statuses.add("Wilful Default")
        elif "write" in s_lower or "written" in s_lower: severe_statuses.add("Written Off")
        elif "settled" in s_lower: severe_statuses.add("Settled")
        elif "loss" in s_lower: severe_statuses.add("Loss")
        elif "doubtful" in s_lower: severe_statuses.add("Doubtful")
        elif "substandard" in s_lower: severe_statuses.add("Substandard")
        elif "sma" in s_lower: severe_statuses.add("SMA")

    for acc in accounts:
        # Check Account Level Fields
        check_status(acc.get('accountStatus', ''))
        check_status(acc.get('suitFiledStatus', ''))
        check_status(acc.get('assetClassificationStatus', ''))
        
        # Check History
        history = acc.get('history48Months', [])
        for entry in history:
             check_status(entry.get('paymentStatus', ''))
             check_status(entry.get('assetClassificationStatus', ''))
             check_status(entry.get('suitFiledStatus', ''))

    # Rank them
    hierarchy = ["Suit Filed", "Wilful Default", "Loss", "Written Off", "Settled", "Doubtful", "Substandard", "SMA"]
    
    for status in hierarchy:
        if status in severe_statuses:
            return status
            
    return 'N/A'

def main():
    output_file = 'severe_status_results.csv'
    txt_files = glob.glob('files/*.txt')
    
    if not txt_files:
        print("No .txt files found in files/ directory.")
        return

    print(f"Processing {len(txt_files)} files for institution: {TARGET_INSTITUTION}...")
    
    results = []
    
    for file_path in txt_files:
        try:
            for report in parse_report(file_path):
                file_name = report.get('file_name', os.path.basename(file_path))
                lender_status = report.get('lender_status', 'N/A')
                all_accounts = report.get('accounts', [])
                
                # Filter Accounts
                target_accounts = [
                    acc for acc in all_accounts 
                    if acc.get('institution', '').strip().lower() == TARGET_INSTITUTION.lower()
                ]
                
                if not target_accounts:
                    # If this report has no accounts for this institution, skip it logic "only give me defaults from Ramtirth"
                    # If no Ramtirth accounts, certainly no defaults.
                    continue
                
                # 1. Most Severe Remark (Local to Ramtirth)
                severe_remark = get_institution_severe_remark(target_accounts)
                
                # 2. Latest Month of Highest DPD (Local to Ramtirth)
                max_dpd_val, latest_date_obj = get_latest_max_dpd_info(target_accounts)
                
                latest_month_str = "N/A"
                if latest_date_obj:
                    # Format: YYYY-MM
                    latest_month_str = latest_date_obj.strftime("%Y-%m")
                
                # Filter out rows with no defaults (clean Ramtirth accounts or no Ramtirth accounts)
                if severe_remark == 'N/A' and latest_month_str == 'N/A':
                    continue

                results.append({
                    'file_name': file_name,
                    'lender_status': lender_status,
                    'most_severe_remark': severe_remark,
                    'latest_month': latest_month_str
                })
                
        except Exception as e:
            print(f"Error processing {file_path}: {e}")
            continue

    # Write to CSV
    headers = ['file_name', 'lender_status', 'most_severe_remark', 'latest_month']
    
    try:
        with open(output_file, 'w', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            writer.writerows(results)
        print(f"Successfully wrote {len(results)} rows to {output_file}")
    except Exception as e:
        print(f"Error writing CSV: {e}")

if __name__ == "__main__":
    main()
