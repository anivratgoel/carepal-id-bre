# Bureau Back Test

This project contains scripts to parse credit bureau reports and apply business rule engine (BRE) logic to calculate credit scores and risk assessments.

## Scripts & Usage

### 1. Business Rule Engine (`bre_engine.py`)
The main engine that processes parsed data and applies rules for DPD, enquiries, vintage, etc.
- **Usage**: `python3 bre_engine.py` (Outputs CSV reports)
- **Output**: 
    - `bureau_bre_results.csv`: Detailed results.
    - `bureau_bre_results_filtered.csv`: Filtered results based on QEC date.

### 2. JSON Report Generator (`generate_bre_json.py`)
Generates a JSON response for all parsed files, including a specific check for active credit cards.
- **Usage**: `python3 generate_bre_json.py > bre_output.json`
- **Output**: JSON array containing:
    - `file_name`: Name of the input file
    - `bre_status`: Final decision (APPROVE/REJECT)
    - `sanction_limit`: Calculated loan amount
    - `active_credit_card`: Boolean (True if any active credit card is found)

### 3. Severe Status Extractor (`extract_severe_status.py`)
Extracts severe derogatory statuses and latest DPD information for a specific institution (default: Ramtirth).
- **Usage**: `python3 extract_severe_status.py`
- **Output**: `severe_status_results.csv`

### 4. Institution Search (`search_institutions.py`)
Helper to find files containing records for a specific institution.
- **Usage**: `python3 search_institutions.py`

## Directory Structure
- `bre_engine.py`: Core logic and constants (Secured/Unsecured lists, Score logic).
- `parse_reports.py`: Parser for the raw text/JSON files.
- `files/`: Place raw input `.txt` files here (Git ignored).

## Key Logic Details
- **Active Credit Card**: Checks for accounts with `accountType` containing "Credit Card" and `open` status as "Yes".
- **Loan Categories**: Extensive lists of `SECURED_TYPES` and `UNSECURED_TYPES` are defined in `bre_engine.py`.
- **Derogatory Checks**: Includes keywords like WOF, SF, SUIT, WILFUL, etc.
