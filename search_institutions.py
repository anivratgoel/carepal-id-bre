import glob
import os
from parse_reports import parse_report

def search_institutions(keyword="ramtirth"):
    txt_files = glob.glob('files/*.txt')
    if not txt_files:
        print("No .txt files found in files/ directory.")
        return

    print(f"Searching {len(txt_files)} files for institutions containing '{keyword}'...\n")
    
    found_institutions = set()
    
    for file_path in txt_files:
        try:
            for report in parse_report(file_path):
                accounts = report.get('accounts', [])
                for acc in accounts:
                    inst_name = acc.get('institution', '')
                    if inst_name and keyword.lower() in inst_name.lower():
                        found_institutions.add(inst_name)
                        print(f"Found in: {file_path} => {inst_name}")
                        break # Found in this file, move to next file

                        
        except Exception as e:
            print(f"Error processing {file_path}: {e}")

    print("Found Institutions:")
    print("-" * 20)
    if found_institutions:
        for name in sorted(found_institutions):
            print(name)
    else:
        print("No matching institutions found.")
    print("-" * 20)

if __name__ == "__main__":
    search_institutions()
