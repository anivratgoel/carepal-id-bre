import csv
import glob
import os
from datetime import datetime
from parse_reports import parse_report
from bre_engine import parse_dpd_value, parse_month_year_key

def get_latest_max_dpd_info(accounts):
    """
    Finds the maximum DPD across all accounts and history,
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
            # paymentStatus is the usual field for DPD
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

def get_most_severe_remark(report_summary):
    """
    Finds the most severe status from 'mostSevereStatusWithIn24Months' field
    in the report summary.
    """
    return report_summary.get('mostSevereStatusWithIn24Months', 'N/A')

def main():
    output_file = 'severe_status_results.csv'
    txt_files = glob.glob('files/*.txt')
    
    if not txt_files:
        print("No .txt files found in files/ directory.")
        return

    print(f"Processing {len(txt_files)} files...")
    
    results = []
    
    for file_path in txt_files:
        try:
            # parse_report yields one or more reports (usually one per file)
            for report in parse_report(file_path):
                file_name = report.get('file_name', os.path.basename(file_path))
                lender_status = report.get('lender_status', 'N/A')
                accounts = report.get('accounts', [])
                summary = report.get('summary', {})
                
                # 1. Most Severe Remark
                severe_remark = get_most_severe_remark(summary)
                
                # 2. Latest Month of Highest DPD
                # Note: The user asked for "latest month in which THIS dpd was reported"
                # "This dpd" referring to "mostSevereStatusWithIn24Months" or "highest dpd"?
                # Context: "Also, fetch the latest month in which this dpd was reported. You might have to parse all objects in retailAccountDetails to identify in which month the highest dpd was reported last."
                # Interpreting as: Identify Global Max DPD (which ideally matches the Severe Status logic) and find its latest date.
                
                max_dpd_val, latest_date_obj = get_latest_max_dpd_info(accounts)
                
                latest_month_str = "N/A"
                if latest_date_obj:
                    # Format: YYYY-MM
                    latest_month_str = latest_date_obj.strftime("%Y-%m")
                
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
