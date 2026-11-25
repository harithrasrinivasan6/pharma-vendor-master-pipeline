# Pharmaceutical Procurement Intelligence: Vendor Master Consolidation

## Project Overview
This repository contains the ETL data engineering pipeline for consolidating
dirty, multi-source enterprise vendor data. The solution standardizes
heterogeneous datasets (ERP vendor master records and manual procurement logs),
resolves string formatting anomalies, imputes missing metrics, segregates
invalid records into a quarantine layer, and loads cleaned data into a SQLite
analytical warehouse for spend auditing.

## Repository Structure
```text
pharma-vendor-master-pipeline/
├── config/
│   └── config.example.ini        # Template connection settings
├── data/
│   ├── raw/                      # Raw input datasets (CSV)
│   └── output/                   # Processed outputs (Ignored by Git)
├── sql/
│   ├── ddl_setup.sql             # Table definitions
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
   git clone https://github.com/harithrasrinivasan6/pharma-vendor-master-pipeline.git
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
Upon execution, the pipeline creates the following outputs:
* `data/output/pharmaceutical_procurement.db` (SQLite database containing cleaned tables: `gold_vendor_master`, `gold_vendor_categories`, `err_vendor_quarantine`)
* `data/output/quarantine_report.csv` (Records flagged for manual review)
* `logs/etl_vendor_master_<timestamp>.log` (Execution log, including the results of the post-load verification queries)

To re-run the audit queries manually against the generated database:
```bash
sqlite3 data/output/pharmaceutical_procurement.db < sql/verification_queries.sql
```

Generated databases, CSV outputs, logs, and `config/config.ini` are excluded
from version control via `.gitignore`.
