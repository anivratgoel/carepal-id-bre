import json
import os
import glob

def parse_report(file_path):
    try:
        with open(file_path, 'r') as f:
            content = f.read()
            # Handle potential BOM or whitespace issues if any, though standard read handles most
            data = json.loads(content)
            
            # Navigate to the list of reports
            # Structure based on sample: json -> data -> cCRResponse -> cIRReportDataLst
            # The root object in file is `{"json": ...}` or just root object?
            # Looking at sample: `{"json":{"decentroTxnId":...`
            
            root = data.get('json', data) # In case "json" key is missing wrapper
            
            ccr_response = root.get('data', {}).get('cCRResponse', {})
            cir_report_data_list = ccr_response.get('cIRReportDataLst', [])
            
            if not cir_report_data_list:
                print(f"[{os.path.basename(file_path)}] No report data found.")
                return

            # Extract Root Fields (New Requirement)
            # Extract Root Fields (New Requirement)
            # Check both 'data' (outer dict) and 'root' (inner dict if 'json' wrapper exists)
            qec_date = data.get('qec-date') or root.get('qec-date')
            sanction_limit = data.get('sanction_limit') or root.get('sanction_limit')
            lender_status = data.get('lender_status') or root.get('lender_status')
            sanction_limit_2 = data.get('sanction_limit_2') or root.get('sanction_limit_2')

            # Check for NTC / Error in first item if list exists
            if cir_report_data_list:
                first_item = cir_report_data_list[0]
                if 'error' in first_item:
                     error_desc = first_item['error'].get('errorDesc', 'Unknown Error')
                     if "Consumer not found" in error_desc:
                         yield {
                             'file_name': os.path.basename(file_path),
                             'name': 'Consumer Not Found',
                             'enquiries': 0,
                             'score': 'NTC',
                             'age': '0',
                             'pan_list': [],
                             'accounts': [],
                             'report_date': None,
                             'enq_summary': {},
                             'consumer_found': False
                         }
                         return

            for report in cir_report_data_list:
                cir_data = report.get('cIRReportData', {})
                if not cir_data: continue

                # Extract Name
                personal_info = cir_data.get('iDAndContactInfo', {}).get('personalInfo', {})
                name_obj = personal_info.get('name', {})
                full_name = name_obj.get('fullName', 'Unknown')
                
                # Extract Enquiry Count
                enq_summary = cir_data.get('enquirySummary', {})
                total_enquiries = enq_summary.get('total', '0')
                
                # Extract Score
                score_details = cir_data.get('scoreDetails', [])
                score_value = "N/A"
                if score_details and isinstance(score_details, list):
                    score_value = score_details[0].get('value', 'N/A')
                
                # Extract Age
                age_obj = personal_info.get('age', {})
                age = age_obj.get('age', '0')

                # Extract PAN Info
                identity_info = cir_data.get('iDAndContactInfo', {}).get('identityInfo', {})
                pan_list = identity_info.get('pANId', [])

                # Extract Account Details
                accounts = cir_data.get('retailAccountDetails', [])

                # Extract Account Summary
                summary = cir_data.get('retailAccountsSummary', {})

                # Extract Date Reported (Reference Date) - Try various locations
                # 1. From Personal Info (often not there or reliable) - Use file name or specific field
                # 2. Looking at sample: `cIRReportDataLst` -> `cIRReportData` -> ...
                # We will pick the `dateOpened` of the most recent account OR use current system date if not found?
                # Actually, `cIRReportData.iDAndContactInfo.phoneInfo[0].reportedDate` might be a proxy.
                # Better: `dateReported` is in each account object. We can use the max of those.
                
                report_date_str = "2025-12-01" # Default fallback
                if accounts:
                    # Find max reported date from accounts to estimate report pull date
                    # Format in JSON is "YYYY-MM-DD" e.g. "2025-11-30" -- Wait, sample shows "2025-11-30" (YYYY-MM-DD)
                    try:
                        dates = [acc.get('dateReported', '') for acc in accounts if acc.get('dateReported')]
                        if dates:
                            report_date_str = max(dates)
                    except:
                        pass
                
                report_data = {
                    'file_name': os.path.basename(file_path),
                    'name': full_name.strip(),
                    'enquiries': total_enquiries,
                    'score': score_value,
                    'age': age,
                    'pan_list': pan_list,
                    'accounts': accounts,
                    'report_date': report_date_str,
                    'enq_summary': enq_summary,
                    'consumer_found': True,
                    'summary': summary,
                    'qec_date': qec_date,
                    'sanction_limit': sanction_limit,
                    'lender_status': lender_status,
                    'sanction_limit_2': sanction_limit_2
                }
                
                yield report_data

    except json.JSONDecodeError as e:
        print(f"Error parsing JSON in {file_path}: {e}")
    except Exception as e:
        print(f"Error processing {file_path}: {e}")

def print_reports():
    # Find all .txt files in the current directory
    txt_files = glob.glob('*.txt')
    
    if not txt_files:
        print("No .txt files found in the current directory.")
        return

    print(f"Found {len(txt_files)} report files.\n")
    
    for file_path in txt_files:
        for report in parse_report(file_path):
            print(f"File: {report['file_name']}")
            print(f"Name: {report['name']}")
            print(f"Number of Enquiries: {report['enquiries']}")
            print(f"Score: {report['score']}")
            print("-" * 30)

if __name__ == "__main__":
    print_reports()
