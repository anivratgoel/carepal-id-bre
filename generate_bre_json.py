import glob
import json
import os
from parse_reports import parse_report
from bre_engine import calculate_bre_score, filter_data_by_qec, is_credit_card, BRE_CHECKS

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

def get_rejection_details(result):
    """
    Determine if hard reject occurred and the reason.
    Returns: (hard_reject_bool, reason_string)
    """
    details = result.get('details', {})
    final_status = result.get('final_status')
    
    # Identify Hard Rejects (Critical Checks with Score 0)
    hard_rejects = []
    
    for check in BRE_CHECKS:
        name = check['name']
        score = details.get(name)
        
        # Check if critical and score is 0
        # Note: score might be "N/A" for NTC cases, ensuring we handle int/float comparison safely
        if check['critical'] and isinstance(score, (int, float)) and score == 0:
            hard_rejects.append(check)
            
    if hard_rejects:
        # Sort by weight descending to find highest weightage failure
        # If weights are equal, order in list prevails (stable sort)
        hard_rejects.sort(key=lambda x: x['weight'], reverse=True)
        top_reason = hard_rejects[0]['name']
        return True, top_reason
        
    # If no hard reject (critical failures), but status is REJECT
    # It means weighted score < threshold
    if final_status == "REJECT":
        return False, "does not meet our credit criteria"
        
    return False, None

def generate_json():
    txt_files = glob.glob('files/*.txt')
    if not txt_files:
        print("No .txt files found.")
        return

    results = []

    for file_path in txt_files:
         try:
            for report in parse_report(file_path):
                # 1. Filter by QEC if present
                if report.get('qec_date'):
                    filtered_report = filter_data_by_qec(report)
                    result = calculate_bre_score(filtered_report)
                    report_to_check = filtered_report
                else:
                    report_to_check = report
                    result = calculate_bre_score(report)
                
                # Check Active Credit Card
                has_active_cc = check_active_credit_card(report_to_check.get('accounts', []))
                
                # Check Rejection Reason
                is_hard_reject, rejection_reason = get_rejection_details(result)
                
                results.append({
                    "file_name": report.get('file_name', os.path.basename(file_path)),
                    "bre_status": result['final_status'],
                    "sanction_limit": str(result['loan_amount']), 
                    "active_credit_card": has_active_cc,
                    "hard_reject": is_hard_reject,
                    "rejection_reason": rejection_reason
                })
         except Exception as e:
             print(f"Error processing {file_path}: {e}")

    print(json.dumps(results, indent=None))

if __name__ == "__main__":
    generate_json()
