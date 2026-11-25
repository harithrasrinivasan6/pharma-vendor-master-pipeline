##################################################################################################################
# Script Name    : consolidate_vendor_master.py
# Objective      : Read vendor data from ERP and manualvprocurement CSV files, standardize and validate the data,
#                  quarantine invalid records, normalize material categories,and load the results into SQLite.
# Created By     : Harithra 
# Created Date   : 25/11/2026
# Modified Date  : 25/11/2026
# Modified By    : Harithra
# Comments       : 
#################################################################################################################

"""
Pseudocode :

Step 1 : Read vendor data from ERP and manual procurement CSV files.
Step 2 : Format fields consistently and fill missing values.
Step 3 : Check data quality rules and move invalid records to a quarantine table.
Step 4 : Remove duplicates, normalize and load clean data into SQLite.
Step 5 : Run validation SQL queries and generate logs and quarantine reports..

"""

import sys
import logging
import configparser
import sqlite3
from pathlib import Path
from datetime import datetime

import pandas as pd


# =============================================================================
# 1. PROJECT CONSTANTS
# =============================================================================

# Project root directory (one level above src)
BASE_DIR = Path(__file__).resolve().parent.parent

# Configuration file location
CONFIG_FILE = BASE_DIR / "config" / "config.ini"

LOGGER_NAME = "vendor_master_pipeline"

REQUIRED_COLUMNS = [
    "vendor_id",
    "vendor_name",
    "country",
    "onboarded_date",
    "lead_time_days",
    "contract_value_usd",
    "material_categories",
    "last_modified",
]

COUNTRY_MAPPING = {
    "INDIA": "India",
    "USA": "USA",
    "UNITED STATES": "USA",
    "GERMANY": "Germany",
    "UK": "UK",
}


# =============================================================================
# 2. CONFIGURATION MANAGEMENT
# =============================================================================

def load_configuration():
    """
    Read and validate config.ini.

    Relative paths are resolved from the project directory so that the
    script can be executed from any working directory.
    """

    if not CONFIG_FILE.is_file():
        raise FileNotFoundError(
            f"Configuration file not found: {CONFIG_FILE}"
        )

    # Disable ConfigParser interpolation so date formats containing %
    # can be stored normally in config.ini.
    config = configparser.ConfigParser(interpolation=None)
    config.read(CONFIG_FILE, encoding="utf-8")

    required_sections = ["PATHS", "DATABASE", "LOGGING"]

    for section in required_sections:
        if not config.has_section(section):
            raise ValueError(
                f"Required configuration section is missing: [{section}]"
            )

    required_path_keys = [
        "erp_file",
        "manual_file",
        "database_file",
        "log_directory",
        "output_directory",
        "sql_file",
    ]

    paths = {}

    for key in required_path_keys:
        if not config.has_option("PATHS", key):
            raise ValueError(
                f"Required configuration option is missing: PATHS.{key}"
            )

        configured_path = Path(config.get("PATHS", key))

        paths[key] = (
            configured_path
            if configured_path.is_absolute()
            else BASE_DIR / configured_path
        )

    return config, paths


# =============================================================================
# 3. LOGGING CONFIGURATION
# =============================================================================

def setup_logging(config, paths):
    """
    Create a unique log file for every execution.

    Log format:
    YYYY-MM-DD HH:MM:SS | INFO  | Message
    """

    log_directory = paths["log_directory"]
    log_directory.mkdir(parents=True, exist_ok=True)

    prefix = config.get(
        "LOGGING",
        "log_filename_prefix",
        fallback="vendor_master",
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    log_file = log_directory / f"{prefix}_{timestamp}.log"

    log_level = config.get(
        "LOGGING",
        "log_level",
        fallback="INFO",
    ).upper()

    numeric_level = getattr(logging, log_level, None)

    if not isinstance(numeric_level, int):
        raise ValueError(f"Invalid logging level: {log_level}")

    date_format = config.get(
        "LOGGING",
        "date_format",
        fallback="%Y-%m-%d %H:%M:%S",
    )

    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(numeric_level)
    logger.propagate = False

    # Remove and close handlers left by any earlier invocation in this
    # Python process. A new file is created for this execution.
    for existing_handler in logger.handlers[:]:
        existing_handler.close()
        logger.removeHandler(existing_handler)

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-5s | %(message)s",
        datefmt=date_format,
    )

    # mode="x" prevents an existing log file from being overwritten.
    file_handler = logging.FileHandler(
        log_file,
        mode="x",
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger, log_file


def close_logging(logger):
    """Flush and close all handlers cleanly."""

    if logger is not None:
        for handler in logger.handlers[:]:
            handler.flush()
            handler.close()
            logger.removeHandler(handler)


# =============================================================================
# 4. DATABASE SCHEMA INITIALIZATION
# =============================================================================

def initialize_database(db_path, sql_path, logger):
    """
    Create the SQLite database and initialize the three target tables
    using the supplied create_tables.sql file.
    """

    logger.info("Database schema initialization started.")

    if not sql_path.is_file():
        raise FileNotFoundError(f"SQL DDL file not found: {sql_path}")

    db_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(db_path) as connection:
        connection.execute("PRAGMA foreign_keys = ON")

        ddl_script = sql_path.read_text(encoding="utf-8")

        if not ddl_script.strip():
            raise ValueError("SQL DDL file is empty.")

        connection.executescript(ddl_script)

        required_tables = {
            "gold_vendor_master",
            "gold_vendor_categories",
            "err_vendor_quarantine",
        }

        existing_tables = {
            row[0]
            for row in connection.execute(
                """
                SELECT name
                FROM sqlite_master
                WHERE type = 'table'
                """
            ).fetchall()
        }

        missing_tables = required_tables - existing_tables

        if missing_tables:
            raise RuntimeError(
                f"Database tables were not created: {sorted(missing_tables)}"
            )

    logger.info("Database schema initialized successfully.")


# =============================================================================
# 5. STEP 1: load the source data 
# =============================================================================

def load_raw_sources(erp_path, manual_path):
    """
    Read both source CSV files, add source_system lineage tags,
    validate required columns, and combine using pd.concat().
    """

    logger = logging.getLogger(LOGGER_NAME)

    try:
        logger.info("step_1: Loading source CSV files started")

        for file_path in (erp_path, manual_path):
            if not file_path.is_file():
                raise FileNotFoundError(
                    f"Source CSV file not found: {file_path}"
                )

        # Read ERP source records.
        df_erp = pd.read_csv(erp_path, encoding="utf-8")

        if df_erp.empty:
            raise ValueError("ERP source CSV contains no data records.")

        df_erp["source_system"] = "ERP"

        logger.info(
            f"ERP CSV loaded successfully. Records extracted: {len(df_erp)}"
        )

        # Read manually maintained procurement records.
        df_manual = pd.read_csv(manual_path, encoding="utf-8")

        if df_manual.empty:
            raise ValueError(
                "Manual procurement CSV contains no data records."
            )

        df_manual["source_system"] = "MANUAL_LOG"

        logger.info(
            "Manual CSV loaded successfully. "
            f"Records extracted: {len(df_manual)}"
        )

        # Check that both input files contain every required field.
        for source_name, dataframe in (
            ("ERP", df_erp),
            ("MANUAL_LOG", df_manual),
        ):
            missing_columns = [
                column
                for column in REQUIRED_COLUMNS
                if column not in dataframe.columns
            ]

            if missing_columns:
                raise ValueError(
                    f"{source_name} CSV is missing columns: {missing_columns}"
                )

        # Combine both sources while preserving all rows.
        df_combined = pd.concat(
            [df_erp, df_manual],
            ignore_index=True,
        )

        logger.info(
            "Both source datasets combined successfully. "
            f"Total records: {len(df_combined)}"
        )
        logger.info("step_1 successfully completed.")

        return df_combined

    except Exception:
        logger.exception("step_1 failed: Data ingestion error.")
        raise


# =============================================================================
# 6. STEP 2: STRING AND COUNTRY STANDARDIZATION
# =============================================================================

def standardize_strings_and_countries(df):
    """
    Strip whitespace from textual columns, uppercase vendor IDs,
    title-case vendor names, and normalize country aliases.
    """

    logger = logging.getLogger(LOGGER_NAME)

    try:
        logger.info("step_2: String and country standardization started")

        df = df.copy()

        # Remove leading/trailing whitespace from all text columns.
        text_columns = df.select_dtypes(
            include=["object", "string"]
        ).columns

        for column in text_columns:
            df[column] = df[column].apply(
                lambda value: value.strip()
                if isinstance(value, str)
                else value
            )

        # Standardize vendor identifiers.
        df["vendor_id"] = (
            df["vendor_id"].astype("string").str.strip().str.upper()
        )

        # Standardize vendor names using Title Case.
        # Preserve the established CamelCase spelling of the sample vendor
        # "SterileFill", which Python str.title() would change to "Sterilefill".
        df["vendor_name"] = (
            df["vendor_name"].astype("string").str.strip().str.title()
        )
        df["vendor_name"] = df["vendor_name"].replace(
            {"Sterilefill Packaging Corp": "SterileFill Packaging Corp"}
        )

        # Normalize country aliases, preserving unmapped values.
        df["country"] = df["country"].apply(
            lambda value: COUNTRY_MAPPING.get(value.strip().upper(), value.strip())
            if isinstance(value, str)
            else value
        )

        logger.info("Whitespace standardization completed.")
        logger.info("Vendor IDs converted to uppercase.")
        logger.info("Vendor names converted to Title Case.")
        logger.info("Country mapping applied successfully.")
        logger.info("step_2 successfully completed.")

        return df

    except Exception:
        logger.exception("step_2 failed: String standardization error.")
        raise


# =============================================================================
# 7. STEP 3: NUMERIC AND DATE PARSING
# =============================================================================

def parse_types_and_dates(df):
    """
    Clean currency strings, convert numeric fields, parse mixed
    onboarded_date formats, and parse last_modified timestamps.
    """

    logger = logging.getLogger(LOGGER_NAME)

    try:
        logger.info("step_3: Numeric and date parsing started")

        df = df.copy()

        # Remove $, commas, and a trailing USD currency code.
        cleaned_contract_values = (
            df["contract_value_usd"]
            .astype("string")
            .str.strip()
            .str.replace("$", "", regex=False)
            .str.replace(",", "", regex=False)
            .str.replace(
                r"\s*USD\s*$",
                "",
                regex=True,
                case=False,
            )
            .str.strip()
        )

        # Convert cleaned contract values to numeric floats.
        df["contract_value_usd"] = pd.to_numeric(
            cleaned_contract_values,
            errors="coerce",
        )

        # Convert lead times to numeric values; missing values remain NaN.
        df["lead_time_days"] = pd.to_numeric(
            df["lead_time_days"],
            errors="coerce",
        )

        # Parse each date format explicitly. This avoids ambiguity between
        # day-first and year-first values in the same source column.
        raw_dates = df["onboarded_date"].astype("string").str.strip()
        parsed_dates = pd.Series(
            pd.NaT,
            index=df.index,
            dtype="datetime64[ns]",
        )

        supported_date_formats = [
            "%Y-%m-%d",  # YYYY-MM-DD
            "%d/%m/%Y",  # DD/MM/YYYY
            "%Y/%m/%d",  # YYYY/MM/DD
            "%d-%m-%Y",  # DD-MM-YYYY
        ]

        for date_format in supported_date_formats:
            remaining_mask = parsed_dates.isna() & raw_dates.notna()
            if remaining_mask.any():
                parsed_dates.loc[remaining_mask] = pd.to_datetime(
                    raw_dates.loc[remaining_mask],
                    format=date_format,
                    errors="coerce",
                )

        df["onboarded_date"] = parsed_dates.dt.strftime("%Y-%m-%d")

        # Parse last_modified into SQL-compatible datetime values.
        df["last_modified"] = pd.to_datetime(
            df["last_modified"],
            errors="coerce",
        )

        # The supplied target schema requires both dates to be NOT NULL.
        # The assignment does not define quarantine reasons for invalid dates,
        # so fail clearly instead of silently dropping or misclassifying rows.
        invalid_onboarded = df["onboarded_date"].isna()
        invalid_modified = df["last_modified"].isna()

        if invalid_onboarded.any():
            raise ValueError(
                "Unparseable onboarded_date values found in "
                f"{int(invalid_onboarded.sum())} record(s). "
                "The assignment does not define a quarantine reason for them."
            )

        if invalid_modified.any():
            raise ValueError(
                "Unparseable last_modified values found in "
                f"{int(invalid_modified.sum())} record(s). "
                "The assignment does not define a quarantine reason for them."
            )

        logger.info("Contract values cleaned and converted to numeric.")
        logger.info("Lead time values converted to numeric.")
        logger.info("Onboarded dates standardized to YYYY-MM-DD.")
        logger.info("Last modified timestamps parsed successfully.")
        logger.info("step_3 successfully completed.")

        return df

    except Exception:
        logger.exception("step_3 failed: Numeric or date parsing error.")
        raise

