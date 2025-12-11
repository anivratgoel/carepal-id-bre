# Bureau Back Test

This project contains scripts to parse credit bureau reports and apply business rule engine (BRE) logic to calculate credit scores and risk assessments.

## Files

- `bre_engine.py`: The main business rule engine logic. It processes parsed data and applies various checks (DPD, enquiries, vintage, etc.) to generate scores.
- `parse_reports.py`: Helper script to parse the raw bureau report files (JSON format) and extract relevant fields.
- `files/`: Directory containing raw input files (ignored by git).

## Setup

1. Place your input files in the `files/` directory.
2. Run `python bre_engine.py` to process the files.

## Output

The scripts generate CSV reports:
- `bureau_bre_results.csv`: Detailed results.
- `bureau_bre_results_filtered.csv`: Filtered results.
