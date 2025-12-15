import glob
import os
import csv
from datetime import datetime, timedelta
from parse_reports import parse_report

# --- Constants ---

SECURED_TYPES = [
    'Housing Loan', 'Property Loan', 'Auto Loan', 'Gold Loan', 'Two Wheeler Loan', 
    'Tractor Loan', 'Construction Equipment Loan', 'Secured', 'Loan Against Shares',
    'Home Loan', 'Commercial Vehicle Loan'
]

UNSECURED_TYPES = [
    'Personal Loan', 'Credit Card', 'Consumer Loan', 'Business Loan', 
    'Education Loan', 'Overdraft', 'Kisan Credit Card', 'Unsecured',
    'Professional Loan', 'Credit Card Loan'
]

# --- Helper Functions ---

def get_account_category(account_type):
    if not account_type: return 'Other'
    atype = account_type.strip()
    # Direct Match
    if atype in SECURED_TYPES: return 'Secured'
    if atype in UNSECURED_TYPES: return 'Unsecured'
    
    # Substring Match (Case Insensitive)
    atype_lower = atype.lower()
    for s in SECURED_TYPES:
        if s.lower() in atype_lower: return 'Secured'
    for u in UNSECURED_TYPES:
        if u.lower() in atype_lower: return 'Unsecured'
        
    return 'Other'

def parse_date(date_str):
    """Parse YYYY-MM-DD or DD-MM-YYYY to datetime object."""
    if not date_str: return None
    for fmt in ("%Y-%m-%d", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_str, fmt)
        except ValueError:
            continue
    return None

def parse_month_year_key(key):
    """Parse MM-YY key (e.g. '11-25') to datetime (2025-11-01)."""
    try:
        parts = key.split('-')
        if len(parts) == 2:
            month = int(parts[0])
            year_short = int(parts[1])
            # Assume 20xx
            year = 2000 + year_short
            return datetime(year, month, 1)
    except:
        return None
    return None

def parse_dpd_value(val):
    """
    Parse DPD string to int.
    "000", "STD", "NEW", "CLSD", "0" -> 0
    "30+", "30" -> 30
    "SUB", "DBT", "LSS" -> 90 
    "*" -> 0 (No Data/Not Reported)
    """
    s = str(val).upper().strip()
    if s in ["000", "STD", "NEW", "CLSD", "0", "*", "NAP"]:
        return 0
    if "SUB" in s or "DBT" in s or "LSS" in s:
        return 90
    
    # Try parsing number, removing '+'
    clean_s = s.replace('+', '')
    try:
        return int(clean_s)
    except ValueError:
        return 0 # Fallback safe

def is_credit_card(acc_type):
    return "Credit Card" in acc_type

def get_max_dpd_in_window(accounts, report_date, months_lookback, account_types_filter=None, status_filter=None):
    """
    Check history for max DPD in the last X months relative to report_date.
    account_types_filter: 'LOANS' (not CC), 'ALL'
    status_filter: 'Active', 'Closed', 'ALL'
    """
    if not report_date:
        return 0
        
    start_date = report_date - timedelta(days=30 * months_lookback)
    max_dpd = 0
    
    for acc in accounts:
        # Filter Type
        acc_type = acc.get('accountType', 'Unknown')
        if account_types_filter == 'LOANS' and is_credit_card(acc_type):
            continue
            
        # Filter Status
        # sample 'open': 'Yes'/'No'. 'Yes' = Active?
        is_open = acc.get('open', '').lower() == 'yes'
        # 'accountStatus' can also be checked e.g. "Closed Account"
        status_field = acc.get('accountStatus', '')
        
        if status_filter == 'Active' and not is_open:
            continue
        if status_filter == 'Closed' and is_open:
            continue
            
        # Check History
        history = acc.get('history48Months', [])
        for entry in history:
            key = entry.get('key') # "MM-YY"
            entry_date = parse_month_year_key(key)
            
            if not entry_date:
                continue
                
            # Check window: entry_date >= start_date AND entry_date <= report_date
            # Actually history keys are effectively reporting months.
            if start_date <= entry_date <= report_date:
                # Check DPD
                # paymentStatus -> "000", "STD", "30+"? 
                # assetClassificationStatus -> "STD", "SUB"?
                # User says: 60+, 30+ etc will all denote DPD. 
                # Check `paymentStatus` and `assetClassificationStatus`
                
                pymt = entry.get('paymentStatus', '0')
                asset = entry.get('assetClassificationStatus', 'STD')
                
                dpd1 = parse_dpd_value(pymt)
                dpd2 = parse_dpd_value(asset)
                
                current_max = max(dpd1, dpd2)
                if current_max > max_dpd:
                    max_dpd = current_max
                    
    return max_dpd

def get_total_overdue(accounts, account_types_filter=None, status_filter=None):
    """
    Calculate total past due amount.
    """
    total = 0.0
    for acc in accounts:
        # Filter Type
        acc_type = acc.get('accountType', 'Unknown')
        if account_types_filter == 'LOANS' and is_credit_card(acc_type):
            continue
        if account_types_filter == 'CARDS' and not is_credit_card(acc_type):
            continue
            
        # Filter Status
        is_open = acc.get('open', '').lower() == 'yes'
        if status_filter == 'Active' and not is_open:
            continue
        if status_filter == 'Closed' and is_open:
            continue
            
        val = acc.get('pastDueAmount', '0')
        try:
            total += float(val)
        except:
            pass
            
    return total

# --- Check Functions ---

def check_bureau_score(score_value):
    # <700 or customer not found -> 0
    # 700-725 -> 1
    # >=0 & <=300 -> 2 (Assuming valid score range, overlaps with <700? 
    # Usually 0-300 range implies specifically low/bad history but not NTC? 
    # User instruction: ">=0 & <=300 - 2". This MUST take precedence over "<700".
    # 726-750 -> 3
    # 751-800 -> 4
    # 800+ -> 5
    
    try:
        if str(score_value).upper() == "N/A" or str(score_value).upper() == "NTC":
             return 0
        
        score = int(score_value)
        
        # Check explicit ranges from top to bottom logic
        if score > 810: return 5
        elif 776 <= score <= 810: return 4
        elif 751 <= score <= 775: return 3
        elif 720 <= score <= 750: return 1
        elif 0 <= score <= 300: return 2
        elif score < 720: return 0 # Gaps like 301-699 fall here
        else: return 0
        
    except ValueError: return 0

def check_age(age_value):
    try:
        age = int(age_value)
        if age < 21 or age > 60: return 0
        elif 21 <= age <= 24: return 1
        elif 25 <= age <= 30: return 2
        elif 41 <= age <= 60: return 3
        elif 31 <= age <= 35: return 4
        elif 36 <= age <= 40: return 5
        else: return 0 
    except ValueError: return 0

def check_pan_count(pan_list):
    if len(pan_list) > 1: return 0
    else: return 5

# New DPD Checks

def check_dpd_3m_all(data):
    # DPD in Active/Closed loans in last 3 months
    # 01+ -> 0; 0 -> 4
    dpd = get_max_dpd_in_window(data['accounts'], parse_date(data['report_date']), 3, 'LOANS', 'ALL')
    if dpd == 0: return 4
    else: return 0

def check_dpd_6m_all(data):
    # DPD in Active/Closed loans in last 6 months
    # 30+ : 0; 01+ : 1; 0 : 4
    dpd = get_max_dpd_in_window(data['accounts'], parse_date(data['report_date']), 6, 'LOANS', 'ALL')
    if dpd == 0: return 4
    # elif dpd < 30: return 1
    else: return 0

def check_dpd_12m_active(data):
    # DPD in Active loans in last 12 months
    # 60+ : 1; 30+ : 2; 01: 3; 0: 5
    dpd = get_max_dpd_in_window(data['accounts'], parse_date(data['report_date']), 12, 'LOANS', 'Active')
    if dpd == 0: return 5
    elif dpd < 30: return 3
    elif dpd < 60: return 2
    else: return 1

def check_dpd_12m_closed_all(data):
    # DPD in closed loans/cards in last 12 months (Include Cards)
    # 60+ : 1; 30+ : 2; 01: 3; 0: 5
    dpd = get_max_dpd_in_window(data['accounts'], parse_date(data['report_date']), 12, 'ALL', 'Closed')
    if dpd == 0: return 5
    elif 0 < dpd <= 30: return 4
    elif 30 < dpd <= 60: return 3
    elif 60 < dpd <= 90: return 2
    else: return 1

def check_dpd_36m_closed_all(data):
    # DPD in closed loans/cards in last 36 months
    # 90+ : 1; 60+ : 2; 30+: 3; 01+: 4; 0: 5
    dpd = get_max_dpd_in_window(data['accounts'], parse_date(data['report_date']), 36, 'ALL', 'Closed')
    if dpd == 0: return 5
    elif dpd < 30: return 4
    elif dpd < 60: return 3
    elif dpd < 90: return 2
    else: return 1

# New Overdue Checks

def check_overdue_active_loans(data):
    # Overdue in Active/Current loans
    # 0->5, <=1->4, 1-3->3, 3-5->2, >5->1
    total = get_total_overdue(data['accounts'], 'LOANS', 'Active')
    val = total / 1000.0
    if val == 0: return 5
    elif 0 < val <= 1: return 4
    elif 1 < val <= 2: return 3
    elif 2 < val <= 3: return 2
    else: return 1 # >5 is 1 (or 0?) Table has 5 cols: 5 4 3 2 1 0. Last col is 0.
    # Grid: - | 5 | 3-5 | 1-3 | Up to 1 | 0
    # Cols: 0(Left, >5) | 1(5?) | 2(3-5) | 3(1-3) | 4(upto1) | 5(0)
    # The '-' is in column 1 (Score 0?). So >5 is score 0?
    # Wait, the prompt: "5 | 3-5 | 1-3 | Up to 1 | 0" for columns matching Scores?
    # Columns usually: Score 1, 2, 3, 4, 5
    # Let's assume standard risk progression.
    # 0 -> 5
    # <=1k -> 4
    # 1-3k -> 3
    # 3-5k -> 2
    # 5k+ -> ? Prompt says "-", so maybe 0? Or 1?
    # Let's map >5 to 1, since likely 0 is critical fail. And this is Non-Critical.
    return 1 

def check_overdue_active_cards(data):
    # Overdue in Active/Current cards
    # - | 20 | 10-20 | 5-10 | Up to 5 | 0
    # 0 -> 5
    # <=5 -> 4
    # 5-10 -> 3
    # 10-20 -> 2
    # >20 -> 1
    total = get_total_overdue(data['accounts'], 'CARDS', 'Active')
    val = total / 1000.0
    if val == 0: return 5
    elif val <= 3: return 4
    elif val <= 5: return 3
    elif val <= 7.5: return 2
    else: return 1

def check_overdue_closed_all(data):
    # Overdue in closed loans/cards
    # - | 50 | 26-50 | 10-25 | Up to 10 | 0
    total = get_total_overdue(data['accounts'], 'ALL', 'Closed')
    val = total / 1000.0
    if val == 0: return 5
    elif val <= 7.5: return 4
    elif val <= 10: return 3
    elif val <= 15: return 2
    else: return 1

# --- Derogatory & Enquiry Helpers ---

def is_derogatory(value):
    """
    Check for bad status codes/strings.
    "Suit filed", "SMA", "SUB", "DBT", "LSS", "wilful default", "settled", "written off"
    Also: "Settled", "Post (WO) Settled", "Written Off"
    """
    if not value: return False
    val = str(value).lower()
    bad_keywords = [
        "suit filed", "sma", "sub", "dbt", "lss", "wilful default", 
        "settled", "written off", "wrt", "set"
    ]
    for kw in bad_keywords:
        if kw in val:
            return True
    return False

def count_derogs_in_window(accounts, report_date, months_lookback, account_types_filter=None, status_filter=None):
    """
    Count accounts with derogatory markings in history within window.
    """
    if not report_date: return 0
    start_date = report_date - timedelta(days=30 * months_lookback)
    count = 0
    
    for acc in accounts:
        # Filters
        acc_type = acc.get('accountType', 'Unknown')
        if account_types_filter == 'LOANS' and is_credit_card(acc_type): continue
        if account_types_filter == 'CARDS' and not is_credit_card(acc_type): continue
        
        is_open = acc.get('open', '').lower() == 'yes'
        if status_filter == 'Active' and not is_open: continue
        if status_filter == 'Closed' and is_open: continue
        
        # Check Account Level Status if present
        # e.g. 'suitFiledStatus', 'assetClassificationStatus' might be at account level or history level
        # We check history for granular window
        
        history = acc.get('history48Months', [])
        found_derog = False
        
        for entry in history:
            key = entry.get('key')
            entry_date = parse_month_year_key(key)
            if not entry_date: continue
            
            if start_date <= entry_date <= report_date:
                # Check fields
                # "Suit filed, SMA, SUB, DBT, LSS, wilful default, settled, written off"
                fields_to_check = [
                    entry.get('paymentStatus', ''),
                    entry.get('assetClassificationStatus', ''),
                    entry.get('suitFiledStatus', ''),
                    # account level checks might be valid too but user said "parse history48months objects"
                ]
                for f in fields_to_check:
                    if is_derogatory(f):
                        found_derog = True
                        break
            if found_derog: break
        
        if found_derog:
            count += 1
            
    return count

def count_loans_opened_in_window(accounts, report_date, months_lookback):
    """
    Count LOANS (not cards) opened in last X months.
    """
    if not report_date: return 0
    start_date = report_date - timedelta(days=30 * months_lookback)
    count = 0
    
    for acc in accounts:
        acc_type = acc.get('accountType', 'Unknown')
        if is_credit_card(acc_type): continue
        
        # Check dateOpened
        date_opened_str = acc.get('dateOpened', '')
        date_opened = parse_date(date_opened_str)
        
        if date_opened:
            if start_date <= date_opened <= report_date:
                count += 1
    return count

def get_credit_vintage(accounts, report_date):
    """
    Calculate years between oldest account open date and report date.
    """
    if not report_date: return 0.0
    
    oldest_date = None
    
    for acc in accounts:
        open_date = parse_date(acc.get('dateOpened', ''))
        if open_date:
            if oldest_date is None or open_date < oldest_date:
                oldest_date = open_date
                
    if oldest_date:
        delta = report_date - oldest_date
        return delta.days / 365.25
        
    return 0.0

def get_unsecured_secured_ratio(accounts):
    """
    Calculate Unsecured Sanction Amount / Secured Sanction Amount.
    """
    sec_amt = 0.0
    unsec_amt = 0.0
    
    for acc in accounts:
        stype = get_account_category(acc.get('accountType', ''))
        
        # Determine Amount (Sanction Amount preferred, else Credit Limit)
        # However, user mentioned "total sanction amount".
        try:
            amt = float(acc.get('sanctionAmount', 0))
        except:
            amt = 0.0
            
        if stype == 'Secured':
            sec_amt += amt
        elif stype == 'Unsecured':
            unsec_amt += amt
            
    if sec_amt == 0:
        if unsec_amt > 0:
            return 999.0 # Max Risk
        else:
            return 0.0 # No Exposure
            
    return unsec_amt / sec_amt

def get_vintage_by_type(accounts, report_date, category):
    """
    Get vintage for specific category (Secured/Unsecured).
    """
    if not report_date: return 0.0
    oldest = None
    
    for acc in accounts:
        cat = get_account_category(acc.get('accountType', ''))
        if cat == category:
            od = parse_date(acc.get('dateOpened', ''))
            if od:
                if oldest is None or od < oldest:
                    oldest = od
    
    if oldest:
        return (report_date - oldest).days / 365.25
    return 0.0

def get_max_dpd_history(history):
    """
    Get max DPD from history list.
    """
    m = 0
    for entry in history:
         # "paymentStatus" or "suitFiledStatus" or "assetClassificationStatus" checks?
         # User said "DPD". paymentStatus usually holds DPD like "000", "030".
         val = parse_dpd_value(entry.get('paymentStatus', ''))
         if val > m: m = val
    return m

def count_clean_unsecured_loans_24m(accounts, report_date):
    """
    Count Unsecured loans opened in last 24m with no DPD (Max DPD = 0).
    """
    if not report_date: return 0
    start_date = report_date - timedelta(days=365*2)
    count = 0
    
    for acc in accounts:
        cat = get_account_category(acc.get('accountType', ''))
        if cat == 'Unsecured':
            od = parse_date(acc.get('dateOpened', ''))
            if od and start_date <= od <= report_date:
                # Check DPD
                hist = acc.get('history48Months', [])
                max_dpd = get_max_dpd_history(hist)
                if max_dpd == 0:
                     count += 1
    return count

def get_max_unsecured_sanction(accounts):
    """
    Get highest sanction amount among unsecured loans (in thousands).
    """
    m = 0.0
    for acc in accounts:
        cat = get_account_category(acc.get('accountType', ''))
        if cat == 'Unsecured':
            try:
                amt = float(acc.get('sanctionAmount', 0))
                if amt > m: m = amt
            except:
                pass
    return m / 1000.0

# --- Derogatory & Enquiry Checks ---

def check_derog_active_closed_12m(data):
    # Derog in any active/closed loan/card in last 12m
    # 0 -> 5, 1 -> 1, >1 -> 0
    count = count_derogs_in_window(data['accounts'], parse_date(data['report_date']), 12, 'ALL', 'ALL')
    if count == 0: return 5
    elif count == 1: return 1
    else: return 0

def check_derog_active_closed_36m(data):
    # Derog in any active/current/closed loan/card in last 36m
    # 0 -> 5, 1 -> 3, 2 -> 1, >2 -> 0
    count = count_derogs_in_window(data['accounts'], parse_date(data['report_date']), 36, 'ALL', 'ALL')
    if count == 0: return 5
    elif count == 1: return 3
    elif count == 2: return 2
    else: return 1

def check_enquiry_1m(data):
    # Enquiry in last 1 month
    # 0 -> 5
    # 1-3 -> 3 (Wait, table: `1-3 -> "-"? No, col 4 score 2? wait)
    # Table: 5+ | 4-5 | - | 1-3 | - | 0
    # Cols:  0    1     2   3     4   5
    # So:
    # 0 -> 5
    # 1-3 -> 3
    # 4-5 -> 1
    # 5+ -> 0
    
    val = data.get('enq_summary', {}).get('past30Days', 0)
    try:
        val = int(val)
    except:
        val = 0
        
    if val == 0: return 5
    elif 1 <= val <= 3: return 3
    elif 4 <= val <= 5: return 1
    else: return 0

def check_enquiry_12m(data):
    # Enquiry in last 12 months
    # - | 10 | 7-9 | 5-6 | 3-4 | up to 2
    # 0-2 -> 5
    # 3-4 -> 4
    # 5-6 -> 3
    # 7-9 -> 2
    # >=10 -> 1 (or 0? Co1 1 is usually score 1 if score 0 is next to it but here - is col 0, so 10 is col 1 -> Score 1)
    
    val = data.get('enq_summary', {}).get('past12Months', 0)
    try:
        val = int(val)
    except:
        val = 0
        
    if val <= 2: return 5
    elif val <= 4: return 4
    elif val <= 6: return 3
    elif val <= 9: return 2
    else: return 1

def check_enquiry_loan_ratio_12m(data):
    # Total enquiry to loan ratio in last 12 months
    # Enq 12m / Loans Opened 12m
    # - | >=5 | 3.1-5 | 2.1-3 | 1.1-2 | 1
    # <=1 -> 5
    # 1.1-2 -> 4
    # 2.1-3 -> 3
    # 3.1-5 -> 2
    # >=5 -> 1
    
    enq_12m = int(data.get('enq_summary', {}).get('past12Months', 0))
    loans_12m = count_loans_opened_in_window(data['accounts'], parse_date(data['report_date']), 12)
    
    if loans_12m == 0:
        if enq_12m == 0:
            ratio = 0
        else:
            ratio = 999 # Infinite
    else:
        ratio = enq_12m / loans_12m
        
    if ratio <= 1: return 5
    elif ratio <= 2: return 4
    elif ratio <= 3: return 3
    elif ratio <= 5: return 2
    else: return 1

def check_credit_vintage(data):
    # Credit Vintage (Oldest Loan)
    # 5+ -> 5, 3-4 -> 4, 2-3 -> 3, 1-2 -> 2, Up to 1 -> 1
    # Table cols usually: 5 | 4 | 3 | 2 | 1 | 0
    # Prompt: "up to 1 | 1-2 | 2-3 | 3-4 | 5+"
    # Order seems reverse or mixed?
    # User format: "Up to 1" "1-2" ...
    # Wait, usually higher vintage is better. 5+ years is good.
    # Scores: "Up to 1" -> ? prompt shows columns but no score header.
    # Assuming standard:
    # 5+ years -> 5 (Low Risk)
    # 3-4 -> 4
    # 2-3 -> 3
    # 1-2 -> 2
    # <1 -> 1 (New borrower)
    
    v = get_credit_vintage(data['accounts'], parse_date(data['report_date']))
    
    if v >= 5: return 5
    elif v >= 4: return 5 # 4-5? Prompt: "3-4". Let's say >=4?
    # Prompt Key: "Up to 1", "1-2", "2-3", "3-4", "5+"
    # Let's map strict buckets from prompt:
    # 5+ -> 5
    # 3-4 -> 4 ( >=3 and <4 ?) or 3-5? "3-4" implies <4?
    # 2-3 -> 3
    # 1-2 -> 2
    # <1 -> ? User said "Up to 1"
    # Let's assume buckets:
    # >= 5: 5
    # 3 <= v < 5: 4 (covering "3-4" and maybe 4-5 gap)
    # 2 <= v < 3: 3
    # 1 <= v < 2: 2
    # < 1: 1
    
    if v >= 5: return 5
    elif v >= 3: return 4
    elif v >= 2: return 3
    elif v >= 1: return 2
    else: return 1

def check_ltd_ratio(data):
    # Unsecured vs Secured exposure (LTD)
    # >0.5,0 | 0.4-0.5 | 0.3-0.4 | 0.2-0.3 | up to 0.2
    # Cols: 1     2        3        4         5
    # Score 5: <= 0.2
    # Score 4: 0.2 - 0.3
    # Score 3: 0.3 - 0.4
    # Score 2: 0.4 - 0.5
    # Score 1: > 0.5 (and 0? " >0.5,0 " -> Maybe >0.5 OR 0? Wait.
    # "Up to 0.2" usually best (Score 5).
    # ">0.5,0" is in the column usually associated with Score 1?
    # Or maybe "0" unsecured is good? 
    # If unsec=0, ratio=0. "Up to 0.2" includes 0. So 0 is Score 5.
    # ">0.5,0" might be specific fail condition? Or typo "0.5+"?
    # Let's assume:
    # <= 0.2 -> 5
    # <= 0.3 -> 4
    # <= 0.4 -> 3
    # <= 0.5 -> 2
    # > 0.5 -> 1
    
    r = get_unsecured_secured_ratio(data['accounts'])
    
    if r <= 0.2: return 5
    elif r <= 0.3: return 4
    elif r <= 0.4: return 3
    elif r <= 0.5: return 2
    else: return 1

def check_unsecured_vintage(data):
    # Unsecured loans served LTD (Unsecured Vintage)
    # 5+ -> 5, 3-4 -> 4, 2-3 -> 3, 1-2 -> 2, Up to 1 -> 1
    v = get_vintage_by_type(data['accounts'], parse_date(data['report_date']), 'Unsecured')
    if v >= 5: return 5
    elif v >= 3: return 4
    elif v >= 2: return 3
    elif v >= 1: return 2
    else: return 1

def check_secured_vintage(data):
    # Secured loans served LTD
    v = get_vintage_by_type(data['accounts'], parse_date(data['report_date']), 'Secured')
    if v >= 5: return 5
    elif v >= 3: return 4
    elif v >= 2: return 3
    elif v >= 1: return 2
    else: return 1

def check_closed_loans_ratio(data):
    # Closed/Zero balance loans to total loans ratio (Count)
    # >0.60 -> 5 (Assuming higher closed ratio is better? Or worse? Usually showing repayment capacity is good. "Served" implies completed.)
    # User Table: 0 -> ? | 0.01-0.25 -> ? | ... | >0.60 -> ?
    # Typically higher closed ratio is good. 
    # Let's map: >0.6 -> 5, 0.41-0.6 -> 4, 0.25-0.4 -> 3, 0.01-0.25 -> 2, 0 -> 1.
    
    s = data.get('summary', {})
    try:
        total = int(s.get('noOfAccounts', 0))
        zero = int(s.get('noOfZeroBalanceAccounts', 0))
    except:
        total = 0
        zero = 0
        
    if total == 0: return 5 # No loans? Neutral/Good? Or Bad?
    
    ratio = zero / total
    
    if ratio > 0.5: return 5
    elif ratio > 0.4: return 4
    elif ratio > 0.25: return 3
    elif ratio > 0: return 2
    else: return 1

def check_utilization_ratio(data):
    # Current balance / High Credit ratio
    # up to 0.25 -> 5
    # 0.25-0.35 -> 4
    # 0.35-0.45 -> 3
    # 0.45-0.6 -> 2
    # >0.6 -> 1
    
    s = data.get('summary', {})
    try:
        bal = float(s.get('totalBalanceAmount', 0))
        sanc = float(s.get('totalSanctionAmount', 0))
    except:
        bal = 0.0
        sanc = 0.0
        
    if sanc == 0:
        if bal > 0: ratio = 999.0
        else: ratio = 0.0
    else:
        ratio = bal / sanc
        
    if ratio <= 0.25: return 5
    elif ratio <= 0.35: return 4
    elif ratio <= 0.45: return 3
    elif ratio <= 0.6: return 2
    else: return 1

def check_overdue_balance_ratio(data):
    # Overdue / Current balance ratio (amount) - Critical
    # 0 -> 5
    # up to 0.1 -> 4
    # 0.11-0.15 -> 3
    # 0.16-0.20 -> 2
    # 0.21-0.30 -> 1
    # 0.3+ -> 0 (Critical Failure?)
    
    s = data.get('summary', {})
    try:
        od = float(s.get('totalPastDue', 0))
        bal = float(s.get('totalBalanceAmount', 0))
    except:
        od = 0.0
        bal = 0.0
        
    if bal == 0:
        if od > 0: ratio = 999.0
        else: ratio = 0.0
    else:
        ratio = od / bal
        
    if ratio == 0: return 5
    elif ratio <= 0.1: return 4
    elif ratio <= 0.15: return 3
    elif ratio <= 0.20: return 2
    elif ratio <= 0.25: return 1
    else: return 0

def check_unsecured_clean_24m(data):
    # Unsecured loans served in last 24 months (Non DPD loans)
    # 7+ -> 5, 5-7 -> 4, 3-4 -> 3, 1-2 -> 2, 0 -> 1
    c = count_clean_unsecured_loans_24m(data['accounts'], parse_date(data['report_date']))
    
    if c >= 7: return 5
    elif c >= 5: return 4
    elif c >= 3: return 3
    elif c >= 1: return 2
    else: return 1

def check_max_usl_amount(data):
    # Max. USL amount of loan served (Per loan) ('000)
    # >1000 -> 5
    # 501-1000 -> 4
    # 251-500 -> 3
    # 100-250 -> 2
    # up to 100 -> 1
    
    val = get_max_unsecured_sanction(data['accounts']) # Returns in '000
    
    if val > 1000: return 5
    elif val > 500: return 4
    elif val > 250: return 3
    elif val >= 100: return 2
    else: return 1

def check_credit_lines_count(data):
    # No. of credit lines till date (Active & closed)
    # >10 -> 5
    # 6-9 -> 4
    # 4-6 -> 3
    # 2-3 -> 2
    # 1 -> 1
    
    # We can use length of accounts list or summary['noOfAccounts']
    s = data.get('summary', {})
    try:
        count = int(s.get('noOfAccounts', 0))
    except:
        count = len(data.get('accounts', []))
        
    if count > 10: return 5
    elif count >= 6: return 4
    elif count >= 4: return 3
    elif count >= 2: return 2
    else: return 1

# --- Configuration ---

BRE_CHECKS = [
    {
        "name": "Bureau Score",
        "func": check_bureau_score,
        "weight": 0.12,
        "critical": True,
        "extractor": lambda d: d.get('score', 'N/A')
    },
    {
        "name": "Age Check",
        "func": check_age,
        "weight": 0.03,
        "critical": True,
        "extractor": lambda d: d.get('age', '0')
    },
    {
        "name": "PAN Count",
        "func": check_pan_count,
        "weight": 0.02,
        "critical": True,
        "extractor": lambda d: d.get('pan_list', [])
    },
    {
        "name": "DPD 3m Loans",
        "func": check_dpd_3m_all,
        "weight": 0.05, # 5%
        "critical": True,
        "extractor": lambda d: d # Pass full data
    },
    {
        "name": "DPD 6m Loans",
        "func": check_dpd_6m_all,
        "weight": 0.03,
        "critical": True,
        "extractor": lambda d: d
    },
    {
        "name": "DPD 12m Active Loans",
        "func": check_dpd_12m_active,
        "weight": 0.03,
        "critical": False,
        "extractor": lambda d: d
    },
    {
        "name": "DPD 12m Closed Loans/Cards",
        "func": check_dpd_12m_closed_all,
        "weight": 0.03,
        "critical": False,
        "extractor": lambda d: d
    },
    {
        "name": "DPD 36m Closed Loans/Cards",
        "func": check_dpd_36m_closed_all,
        "weight": 0.02,
        "critical": False,
        "extractor": lambda d: d
    },
    {
        "name": "Overdue Active Loans",
        "func": check_overdue_active_loans,
        "weight": 0.05,
        "critical": False,
        "extractor": lambda d: d
    },
    {
        "name": "Overdue Active Cards",
        "func": check_overdue_active_cards,
        "weight": 0.05,
        "critical": False,
        "extractor": lambda d: d
    },
    {
        "name": "Overdue Closed All",
        "func": check_overdue_closed_all,
        "weight": 0.02,
        "critical": False,
        "extractor": lambda d: d
    },
    {
        "name": "Derog 12m",
        "func": check_derog_active_closed_12m,
        "weight": 0.06,
        "critical": True,
        "extractor": lambda d: d
    },
    {
        "name": "Derog 36m",
        "func": check_derog_active_closed_36m,
        "weight": 0.02,
        "critical": False,
        "extractor": lambda d: d
    },
    {
        "name": "Enquiry 1m",
        "func": check_enquiry_1m,
        "weight": 0.04,
        "critical": True,
        "extractor": lambda d: d
    },
    {
        "name": "Enquiry 12m",
        "func": check_enquiry_12m,
        "weight": 0.02,
        "critical": False,
        "extractor": lambda d: d
    },
    {
        "name": "Enquiry Ratio 12m",
        "func": check_enquiry_loan_ratio_12m,
        "weight": 0.02,
        "critical": False,
        "extractor": lambda d: d
    },
    {
        "name": "Credit Vintage",
        "func": check_credit_vintage,
        "weight": 0.06,
        "critical": False,
        "extractor": lambda d: d
    },
    {
        "name": "LTD Ratio",
        "func": check_ltd_ratio,
        "weight": 0.03,
        "critical": False,
        "extractor": lambda d: d
    },
    {
        "name": "Unsecured Vintage",
        "func": check_unsecured_vintage,
        "weight": 0.05,
        "critical": False,
        "extractor": lambda d: d
    },
    {
        "name": "Secured Vintage",
        "func": check_secured_vintage,
        "weight": 0.02,
        "critical": False,
        "extractor": lambda d: d
    },
    {
        "name": "Closed Loan Ratio",
        "func": check_closed_loans_ratio,
        "weight": 0.02,
        "critical": False,
        "extractor": lambda d: d
    },
    {
        "name": "Utilization Ratio",
        "func": check_utilization_ratio,
        "weight": 0.02,
        "critical": False,
        "extractor": lambda d: d
    },
    {
        "name": "Overdue Balance Ratio",
        "func": check_overdue_balance_ratio,
        "weight": 0.03,
        "critical": True,
        "extractor": lambda d: d
    },
    {
        "name": "Unsec Clean 24m",
        "func": check_unsecured_clean_24m,
        "weight": 0.04,
        "critical": False,
        "extractor": lambda d: d
    },
    {
        "name": "Max USL Amount",
        "func": check_max_usl_amount,
        "weight": 0.08,
        "critical": False,
        "extractor": lambda d: d
    },
    {
        "name": "Credit Lines Count",
        "func": check_credit_lines_count,
        "weight": 0.02,
        "critical": False,
        "extractor": lambda d: d
    }
]

# --- Engine Logic ---

def calculate_bre_score(report_data):
    weighted_score = 0.0
    status = "PASS"
    details = {}
    
    # Handle Consumer Not Found (NTC)
    is_ntc_case = not report_data.get('consumer_found', True)
    
    total_weight = sum(c['weight'] for c in BRE_CHECKS)
    
    for check in BRE_CHECKS:
        # If NTC Case, only run Bureau Score
        if is_ntc_case:
            if check['name'] == "Bureau Score":
                 # Bureau Score should return NTC score (2)
                 val = check['extractor'](report_data)
                 score = check['func'](val)
                 details[check['name']] = score
                 # For NTC, this is the only score? 
                 # If we normalized, 100% weight on this.
                 # User said "rest all be empty".
                 weighted_score = float(score) # 100% weight
            else:
                details[check['name']] = "N/A"
            continue

        # Extract value
        val = check['extractor'](report_data)
        
        # Calculate score
        score = check['func'](val)
        
        # Store detail
        details[check['name']] = score
        
        # Critical Failure Check
        if check['critical'] and score == 0:
            status = "FAIL"
        
        # Add to weighted score
        # Normalize weight: (weight / total_weight)
        normalized_weight = check['weight'] / total_weight
        weighted_score += (score * normalized_weight)
        
    if is_ntc_case:
         # Hardcode or ensure logic for NTC
         # If Bureau score 2 (NTC) -> we have weighted score 2.
         # Status PASS.
         pass
         
    if status == "FAIL":
        final_score = 0.0
        final_status = "REJECT"
    else:
        final_score = round(weighted_score, 2)
        # Check Threshold (65% of 5 = 3.25)
        if final_score <= 3.25:
            final_status = "REJECT"
        else:
            final_status = "APPROVE"
            
    # Calculate Loan Amount if Approved
    loan_amount = 0
    if final_status == "APPROVE" and final_score > 0:
        pct = (final_score / 5.0) * 100
        
        # Grid
        # 61-65% -> 50,000  (>60 to <=65)
        # 66-70% -> 100,000 (>65 to <=70)
        # 71-80% -> 150,000 (>70 to <=80)
        # 81-85% -> 200,000 (>80 to <=85)
        # >85%   -> 300,000
        
        if pct > 90:
            loan_amount = 300000
        elif pct > 85:
            loan_amount = 275000
        elif pct > 80:
            loan_amount = 225000
        elif pct > 75:
            loan_amount = 175000
        elif pct > 70:
            loan_amount = 125000
        elif pct > 65:
            loan_amount = 75000
        else:
            loan_amount = 0 # Should count as reject if <= 65 logic holds, but safe fallback
    
    return {
        "status": status,
        "final_score": final_score,
        "final_status": final_status,
        "loan_amount": loan_amount,
        "details": details
    }

def filter_data_by_qec(report_data):
    """
    Filter report data based on qec_date.
    - Remove accounts opened > qec_date.
    - Remove history entries >= QEC month.
    """
    qec_date_str = report_data.get('qec_date')
    if not qec_date_str:
        return report_data
        
    # Parse QEC date (ISO format usually)
    # Sample: "2025-04-06T18:06:11.418Z"
    try:
        # Handle ISO with T and Z
        qec_date_str_clean = qec_date_str.split('T')[0]
        qec_date = datetime.strptime(qec_date_str_clean, "%Y-%m-%d")
    except:
        return report_data # Fallback
        
    import copy
    filtered_data = copy.deepcopy(report_data)
    
    original_accounts = filtered_data.get('accounts', [])
    filtered_accounts = []
    
    for acc in original_accounts:
        # 1. Filter by Date Opened
        date_opened_str = acc.get('dateOpened', '')
        date_opened = parse_date(date_opened_str)
        
        if date_opened and date_opened > qec_date:
            continue # Skip this account
            
        # 2. Filter History
        history = acc.get('history48Months', [])
        filtered_history = []
        
        for entry in history:
            key = entry.get('key')
            entry_date = parse_month_year_key(key)
            if not entry_date:
                filtered_history.append(entry)
                continue
            
            # Remove if entry_date > QEC Month-Year (Actually, keep if <= QEC Month Start)
            # User wants to include the QEC month data (e.g. March if QEC is in March)
            
            qec_month_start = datetime(qec_date.year, qec_date.month, 1)
            
            # Use <= to include the QEC month itself
            if entry_date <= qec_month_start:
                filtered_history.append(entry)
                
        acc['history48Months'] = filtered_history
        filtered_accounts.append(acc)
        
    filtered_data['accounts'] = filtered_accounts
    # IMPORTANT: Update report_date to qec_date so that "last 3 months" checks use QEC date as anchor
    filtered_data['report_date'] = qec_date_str_clean
    # Note: 'summary' dict is NOT updated, as discussed.
    
    return filtered_data

def generate_csv_report(results, output_file='bureau_bre_results.csv'):
    # Define Headers
    headers = ['File Name', 'Applicant Name', 'QEC Date', 'Sanction Limit', 'Lender Status', 'Sanction Limit 2']
    check_names = [c['name'] for c in BRE_CHECKS]
    headers.extend(check_names)
    headers.extend(['Status', 'Final Weighted Score', 'Final Decision', 'Sanctioned Amount'])
    
    try:
        with open(output_file, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow(headers)
            
            for res in results:
                report = res['report']
                result = res['result']
                details = result['details']
                
                row = [
                    report['file_name'],
                    report['name'],
                    report.get('qec_date', 'N/A'),
                    report.get('sanction_limit', 'N/A'),
                    report.get('lender_status', 'N/A'),
                    report.get('sanction_limit_2', 'N/A')
                ]
                
                for name in check_names:
                    row.append(details.get(name, 'N/A'))
                    
                row.append(result['status'])
                row.append(result['final_score'])
                row.append(result['final_status'])
                row.append(f"{result['loan_amount']:,}") # Format with commas
                
                writer.writerow(row)
        print(f"CSV generated: {output_file}")
    except Exception as e:
        print(f"Error generating CSV: {e}")

def main():
    import csv 
    txt_files = glob.glob('files/*.txt')
    if not txt_files:
        print("No .txt files found.")
        return

    print(f"{'Name':<20} | {'Status':<5} | {'Score':<5} | {'Decision':<10} | {'Amount'}")
    
    results_original = []
    results_filtered = []

    for file_path in txt_files:
        for report in parse_report(file_path):
            # 1. Original Run
            result = calculate_bre_score(report)
            
            # Print to console (Original)
            print(f"{report['name'][:20]:<20} | {result['status']:<5} | {result['final_score']:<5} | {result['final_status']:<10} | {result['loan_amount']:,}")
            
            results_original.append({
                'report': report,
                'result': result
            })
            
            # 2. Filtered Run
            # If QEC Date exists, filter. Else, use original report.
            if report.get('qec_date'):
                filtered_report = filter_data_by_qec(report)
                result_filtered = calculate_bre_score(filtered_report)
            else:
                filtered_report = report
                result_filtered = result # Reuse original result
                
            results_filtered.append({
                'report': filtered_report,
                'result': result_filtered
            })
            
    # Generate CSVs
    generate_csv_report(results_original, 'bureau_bre_results.csv')
    generate_csv_report(results_filtered, 'bureau_bre_results_filtered.csv')

if __name__ == "__main__":
    main()
