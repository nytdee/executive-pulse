"""
Data loading and validation layer for Executive Pulse.
Handles CSV, XLSX, and Google Sheets input with strict validation.
"""

from __future__ import annotations
import pandas as pd
from typing import Tuple, List, Optional
from datetime import datetime
import io


REQUIRED_COLUMNS = [
    "Task_ID",
    "Task",
    "Project",
    "Department",
    "Owner",
    "Status",
    "Priority",
    "Due_Date",
    "Impact",
    "Last_Updated",
    "Executive_Decision_Required",
]

OPTIONAL_COLUMNS = [
    "Owner_Role",
    "Start_Date",
    "Completed_Date",
    "Impact_Value",
    "Blocker",
    "Dependency",
    "Blocker_Owner",
    "Decision_By",
    "Decision_Requested",
    "Source_URL",
    "Notes",
]

ALL_COLUMNS = REQUIRED_COLUMNS + OPTIONAL_COLUMNS

VALID_STATUSES = {"Not Started", "In Progress", "Blocked", "Done", "On Hold", "Overdue"}
VALID_PRIORITIES = {"Low", "Medium", "High", "Critical"}
VALID_IMPACTS = {"Low", "Medium", "High", "Critical"}
VALID_DECISION_VALUES = {"Yes", "No", "True", "False", "true", "false", "1", "0", 1, 0, True, False}


class DataValidationError(Exception):
    """Raised when data validation fails."""
    pass


def load_csv(file_path: str) -> pd.DataFrame:
    """Load data from CSV file."""
    df = pd.read_csv(file_path, dtype=str)
    return df.fillna("")


def load_xlsx(file_path: str) -> pd.DataFrame:
    """Load data from Excel file."""
    df = pd.read_excel(file_path, dtype=str)
    return df.fillna("")


def load_google_sheet(sheet_id: str, gid: str = "0") -> pd.DataFrame:
    """Load data from Google Sheet via CSV export.
    
    Requirements:
    - Sheet must be "Published to the web" (File → Share → Publish to web)
    - Use the full sheet ID from the URL: https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit
    - gid is the sheet tab ID (default 0 = first tab). Find it in the URL: #gid=123456
    """
    # Try the standard export URL first
    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv&gid={gid}"
    
    try:
        df = pd.read_csv(url, dtype=str)
        if df.empty or len(df.columns) < 2:
            raise DataValidationError(
                "Google Sheet returned empty or invalid data. "
                "Ensure the sheet is 'Published to the web' (File → Share → Publish to web → Entire Document → CSV). "
                "Also verify the Sheet ID and gid are correct."
            )
        return df.fillna("")
    except pd.errors.EmptyDataError:
        raise DataValidationError(
            "Google Sheet appears empty or not published. "
            "Go to File → Share → Publish to web → Entire Document → CSV, then click Publish. "
            "Use the Sheet ID from the URL: https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit"
        )
    except Exception as e:
        if "404" in str(e):
            raise DataValidationError(
                "Google Sheet not found (404). Check the Sheet ID. "
                "Format: https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit\n"
                "Also ensure 'Publish to web' is enabled: File → Share → Publish to web → CSV"
            )
        raise DataValidationError(f"Failed to load Google Sheet: {e}")


def load_uploaded_file(uploaded_file) -> pd.DataFrame:
    """Load data from Streamlit uploaded file."""
    name = uploaded_file.name.lower()
    if name.endswith(".csv"):
        df = pd.read_csv(uploaded_file, dtype=str)
        return df.fillna("")
    elif name.endswith((".xlsx", ".xls")):
        df = pd.read_excel(uploaded_file, dtype=str)
        return df.fillna("")
    else:
        raise DataValidationError(f"Unsupported file format: {name}")


def validate_columns(df: pd.DataFrame) -> Tuple[List[str], List[str]]:
    """Validate required columns are present. Returns (missing_required, extra_columns)."""
    df_cols = set(df.columns)
    required_set = set(REQUIRED_COLUMNS)
    missing = list(required_set - df_cols)
    extra = list(df_cols - set(ALL_COLUMNS))
    return missing, extra


def validate_data(df: pd.DataFrame) -> List[str]:
    """Validate data quality. Returns list of error messages."""
    errors = []

    if df.empty:
        errors.append("Dataset is empty")
        return errors

    # Check for blank Task_ID
    blank_ids = df[df["Task_ID"].isna() | (df["Task_ID"].str.strip() == "")]
    if not blank_ids.empty:
        errors.append(f"Found {len(blank_ids)} rows with blank Task_ID")

    # Check for duplicate Task_ID
    dup_ids = df[df.duplicated(subset=["Task_ID"], keep=False)]
    if not dup_ids.empty:
        errors.append(f"Found duplicate Task_ID values: {dup_ids['Task_ID'].unique().tolist()}")

    # Validate Status values
    invalid_status = df[~df["Status"].isin(VALID_STATUSES)]
    if not invalid_status.empty:
        errors.append(f"Invalid Status values: {invalid_status['Status'].unique().tolist()}")

    # Validate Priority values
    invalid_priority = df[~df["Priority"].isin(VALID_PRIORITIES)]
    if not invalid_priority.empty:
        errors.append(f"Invalid Priority values: {invalid_priority['Priority'].unique().tolist()}")

    # Validate Impact values
    invalid_impact = df[~df["Impact"].isin(VALID_IMPACTS)]
    if not invalid_impact.empty:
        errors.append(f"Invalid Impact values: {invalid_impact['Impact'].unique().tolist()}")

    # Validate Executive_Decision_Required
    invalid_decision = df[~df["Executive_Decision_Required"].astype(str).isin([str(v) for v in VALID_DECISION_VALUES])]
    if not invalid_decision.empty:
        errors.append(f"Invalid Executive_Decision_Required values: {invalid_decision['Executive_Decision_Required'].unique().tolist()}")

    # Validate dates
    date_cols = ["Due_Date", "Start_Date", "Completed_Date", "Last_Updated", "Decision_By"]
    for col in date_cols:
        if col in df.columns:
            invalid_dates = df[col].dropna()
            invalid_dates = invalid_dates[invalid_dates.str.strip() != ""]
            try:
                pd.to_datetime(invalid_dates, errors="raise")
            except Exception:
                errors.append(f"Invalid date format in {col}: {invalid_dates.unique().tolist()[:5]}")

    # Validate Impact_Value is numeric
    if "Impact_Value" in df.columns:
        non_numeric = df["Impact_Value"].dropna()
        non_numeric = non_numeric[non_numeric.str.strip() != ""]
        try:
            pd.to_numeric(non_numeric, errors="raise")
        except Exception:
            errors.append(f"Non-numeric Impact_Value values: {non_numeric.unique().tolist()[:5]}")

    return errors


def normalize_data(df: pd.DataFrame) -> pd.DataFrame:
    """Normalize and clean the dataframe."""
    df = df.copy()

    # Strip whitespace from string columns
    str_cols = df.select_dtypes(include=["object"]).columns
    for col in str_cols:
        df[col] = df[col].astype(str).str.strip()
        df[col] = df[col].replace({"nan": "", "None": "", "NaT": ""})

    # Normalize boolean-like columns
    def normalize_bool(val):
        if isinstance(val, bool):
            return val
        s = str(val).strip().lower()
        return s in ("yes", "true", "1", "y")

    df["Executive_Decision_Required"] = df["Executive_Decision_Required"].apply(normalize_bool)

    # Parse dates
    date_cols = ["Due_Date", "Start_Date", "Completed_Date", "Last_Updated", "Decision_By"]
    for col in date_cols:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce")

    # Parse numeric
    if "Impact_Value" in df.columns:
        df["Impact_Value"] = pd.to_numeric(df["Impact_Value"], errors="coerce")

    # Ensure all optional columns exist
    for col in OPTIONAL_COLUMNS:
        if col not in df.columns:
            df[col] = ""

    return df


def load_and_validate(file_path: str = None, uploaded_file=None, sheet_id: str = None, gid: str = "0") -> pd.DataFrame:
    """Main entry point: load data from source and validate."""
    if uploaded_file is not None:
        df = load_uploaded_file(uploaded_file)
    elif sheet_id:
        df = load_google_sheet(sheet_id, gid)
    elif file_path:
        if file_path.endswith(".csv"):
            df = load_csv(file_path)
        elif file_path.endswith((".xlsx", ".xls")):
            df = load_xlsx(file_path)
        else:
            raise DataValidationError(f"Unsupported file format: {file_path}")
    else:
        raise DataValidationError("No data source provided")

    # Validate columns
    missing, extra = validate_columns(df)
    if missing:
        raise DataValidationError(f"Missing required columns: {missing}")
    if extra:
        print(f"Warning: Extra columns ignored: {extra}")

    # Validate data
    errors = validate_data(df)
    if errors:
        raise DataValidationError("; ".join(errors))

    # Normalize
    df = normalize_data(df)

    return df


def get_data_freshness(df: pd.DataFrame) -> str:
    """Get the latest Last_Updated timestamp as a formatted string."""
    if "Last_Updated" in df.columns and not df["Last_Updated"].isna().all():
        latest = df["Last_Updated"].max()
        if pd.notna(latest):
            return latest.strftime("%Y-%m-%d %H:%M")
    return "Unknown"


def filter_by_date_range(df: pd.DataFrame, start: datetime = None, end: datetime = None, date_col: str = "Due_Date") -> pd.DataFrame:
    """Filter dataframe by date range."""
    if date_col not in df.columns:
        return df
    result = df.copy()
    if start:
        result = result[result[date_col] >= pd.Timestamp(start)]
    if end:
        result = result[result[date_col] <= pd.Timestamp(end)]
    return result


def filter_by_departments(df: pd.DataFrame, departments: List[str]) -> pd.DataFrame:
    """Filter dataframe by departments."""
    if not departments:
        return df
    return df[df["Department"].isin(departments)]


def filter_by_owners(df: pd.DataFrame, owners: List[str]) -> pd.DataFrame:
    """Filter dataframe by owners."""
    if not owners:
        return df
    return df[df["Owner"].isin(owners)]


def filter_by_status(df: pd.DataFrame, statuses: List[str]) -> pd.DataFrame:
    """Filter dataframe by statuses."""
    if not statuses:
        return df
    return df[df["Status"].isin(statuses)]


def filter_by_priority(df: pd.DataFrame, priorities: List[str]) -> pd.DataFrame:
    """Filter dataframe by priorities."""
    if not priorities:
        return df
    return df[df["Priority"].isin(priorities)]


def search_tasks(df: pd.DataFrame, query: str) -> pd.DataFrame:
    """Search tasks by text across multiple columns."""
    if not query:
        return df
    query = query.lower()
    mask = (
        df["Task"].str.lower().str.contains(query, na=False) |
        df["Project"].str.lower().str.contains(query, na=False) |
        df["Owner"].str.lower().str.contains(query, na=False) |
        df["Blocker"].str.lower().str.contains(query, na=False) |
        df["Notes"].str.lower().str.contains(query, na=False)
    )
    return df[mask]