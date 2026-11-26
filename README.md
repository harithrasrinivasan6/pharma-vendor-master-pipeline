# Pharmaceutical Procurement Intelligence: Vendor Master Consolidation

## Project Overview
This repository contains the ETL data engineering pipeline for consolidating dirty, multi-source enterprise vendor data. The solution standardizes heterogeneous datasets (ERP vendor master records and manual procurement logs), resolves string formatting anomalies, imputes missing metrics, segregates invalid records into a quarantine layer, and loads cleaned data into a SQLite analytical warehouse for spend auditing.

## Repository Structure
```text
pharma-vendor-master-pipeline/
├── config/
│   └── config.example.ini        # Template connection settings
├── data/
│   ├── raw/                      # Raw input datasets (CSV)
│   └── output/                   # Processed outputs (Ignored by Git)
├── sql/
│   ├── ddl_schema.sql            # Table definitions
│   └── verification_queries.sql  # Audit verification scripts
├── src/
│   └── consolidate_vendor_master.py  # Primary Python ETL engine
├── .gitignore                    # Git exclusion rules
├── requirements.txt              # Dependency specifications
└── README.md                     # Pipeline documentation
```

## Setup & Installation

1. Clone the repository locally:
   ```bash
   git clone https://github.com/<your-username>/pharma-vendor-master-pipeline.git
   cd pharma-vendor-master-pipeline
   ```

2. Initialize a virtual environment and install dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Setup environment configuration:
   ```bash
   cp config/config.example.ini config/config.ini
   ```

## Pipeline Execution
Run the full ETL pipeline using:
```bash
python src/consolidate_vendor_master.py
```

## Verification & Output Rules
Upon execution, the pipeline creates two outputs in `data/output/`:
* `vendor_intelligence.db` (SQLite Database containing cleaned tables)
* `quarantine_report.csv` (Records flagged for manual review)
