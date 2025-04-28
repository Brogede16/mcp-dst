from typing import Any, Literal, Optional, Union, Dict
from mcp.server.fastmcp import FastMCP
import sys
import logging

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("Danmarks Statistik API")

# Try to import requests, but handle case when it's not available
try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    logger.error("Requests module not found. Installing...")
    try:
        import pip
        pip.main(['install', 'requests'])
        import requests
        REQUESTS_AVAILABLE = True
        logger.info("Successfully installed requests module")
    except Exception as e:
        logger.error(f"Failed to install requests: {e}")
        REQUESTS_AVAILABLE = False

# Base URL for DST API
BASE_URL = "https://api.statbank.dk/v1"

# Define valid formats as a literal type
DataFormat = Literal["JSONSTAT", "JSON", "CSV", "XLSX", "BULK", "PX", "TSV", "HTML5", "HTML5InclNotes"]

# Add tools for direct API access
@mcp.tool()
def get_subjects(subjects: list[str] = None, includeTables: bool = False, recursive: bool = False, 
                 omitInactiveSubjects: bool = False, lang: str = "da") -> dict:
    """Get subjects from DST API
    
    Args:
        subjects: Optional list of subject codes. If provided, fetches sub-subjects for these subjects.
        includeTables: If True, includes tables in the result under each subject.
        recursive: If True, fetches sub-subjects (and tables) recursively through all levels.
        omitInactiveSubjects: If True, omits subjects/sub-subjects that are no longer updated.
        lang: Language code ("da" or "en", default "da").
    
    Returns:
        A dictionary containing the subjects hierarchy in JSON format.
    """
    url = f"{BASE_URL}/subjects"
    payload = {"format": "JSON", "lang": lang}
    if subjects:
        payload["subjects"] = subjects
    if includeTables:
        payload["includeTables"] = True
    if recursive:
        payload["recursive"] = True
    if omitInactiveSubjects:
        payload["omitInactiveSubjects"] = True
    
    r = requests.post(url, json=payload)
    r.raise_for_status()
    return r.json()

@mcp.tool()
def get_tables(subjects: list[str] = None, pastdays: int = None, includeInactive: bool = False, lang: str = "da") -> dict:
    """Get tables from DST API
    
    Args:
        subjects: Optional list of subject codes to filter tables on.
        pastdays: Optional number of days; only tables updated within these days are included.
        includeInactive: If True, includes inactive (discontinued) tables.
        lang: Language code ("da" or "en", default "da").
    
    Returns:
        A dictionary containing the list of tables in JSON format.
    """
    url = f"{BASE_URL}/tables"
    payload = {"format": "JSON", "lang": lang}
    if subjects:
        payload["subjects"] = subjects
    if pastdays is not None:
        payload["pastdays"] = pastdays
    if includeInactive:
        payload["includeInactive"] = True
    
    r = requests.post(url, json=payload)
    r.raise_for_status()
    return r.json()

@mcp.tool()
def get_table_info(table_id: str, lang: str = "da") -> dict:
    """Get table metadata from DST API
    
    Args:
        table_id: The table code (e.g., "folk1c").
        lang: Language code ("da" or "en", default "da").
    
    Returns:
        A dictionary containing metadata for the table (variables, value codes, etc.).
    """
    url = f"{BASE_URL}/tableinfo"
    payload = {"table": table_id, "format": "JSON", "lang": lang}
    
    r = requests.post(url, json=payload)
    r.raise_for_status()
    return r.json()

@mcp.tool()
def get_data(table_id: str, variables: list[dict] = None, format: DataFormat = "JSONSTAT", 
             timeOrder: Optional[Literal["Ascending", "Descending"]] = None, 
             lang: str = "da",
             valuePresentation: Optional[Literal["Code", "Text"]] = None) -> Union[dict, bytes, str]:
    """Get data from DST API
    
    Args:
        table_id: The table code (e.g., "folk1c").
        variables: Optional list of dicts to filter data. Each dict must have "code" (variable code) 
                  and "values" (list of desired value codes). If None or empty, fetches data for all 
                  values (with automatic elimination of variables).
        format: Output format. Default "JSONSTAT". Valid formats are: JSONSTAT, JSON, CSV, XLSX, BULK, PX, TSV, HTML5, HTML5InclNotes
        timeOrder: Optional string for sorting time series ("Ascending" or "Descending").
        lang: Language code for metadata in result ("da" or "en", default "da").
        valuePresentation: Optional string to control value presentation ("Code" or "Text").
    
    Returns:
        Data in the requested format. For JSON formats returns a dict, for other formats returns raw bytes or text.
    """
    url = f"{BASE_URL}/data"
    
    # Validate and normalize format
    format = format.upper()
    
    # Build the basic payload
    payload = {
        "table": table_id,
        "format": format,
        "lang": lang
    }
    
    # Handle variables - ensure proper structure
    if variables:
        # Ensure each variable has required structure
        for var in variables:
            if not isinstance(var, dict) or "code" not in var or "values" not in var:
                raise ValueError("Each variable must be a dict with 'code' and 'values' keys")
            if not isinstance(var["values"], list):
                var["values"] = [var["values"]]  # Convert single value to list
        payload["variables"] = variables
    
    # Add optional parameters if provided
    if timeOrder:
        payload["timeOrder"] = timeOrder
    if valuePresentation:
        payload["valuePresentation"] = valuePresentation
    
    # For large datasets, use streaming formats
    if format in ["BULK", "SDMXCOMPACT", "SDMXGENERIC"]:
        r = requests.post(url, json=payload, stream=True)
        r.raise_for_status()
        return r.content
    
    # Make the request
    r = requests.post(url, json=payload)
    
    # Handle potential errors with more detail
    try:
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        if r.status_code == 400:
            error_detail = r.json() if r.text else "No error details provided"
            raise ValueError(f"Bad request to DST API: {error_detail}")
        raise
    
    # Handle different response formats
    if format in ["JSON", "JSONSTAT"]:
        return r.json()
    elif format in ["CSV", "PX", "TSV", "HTML5", "HTML5InclNotes"]:
        return r.text
    else:
        return r.content

# Add resources for RESTful access
@mcp.resource("statbank://subjects")
def subjects_resource() -> dict:
    """Get all subjects"""
    return get_subjects()

@mcp.resource("statbank://subjects/{subject_id}")
def subject_by_id_resource(subject_id: str) -> dict:
    """Get a specific subject"""
    return get_subjects(subjects=[subject_id])

@mcp.resource("statbank://tables")
def tables_resource() -> dict:
    """Get all tables"""
    return get_tables()

@mcp.resource("statbank://tableinfo/{table_id}")
def tableinfo_resource(table_id: str) -> dict:
    """Get info for a specific table"""
    return get_table_info(table_id)

@mcp.resource("statbank://data/{table_id}/{variables}/{format}/{timeOrder}/{lang}/{valuePresentation}")
def data_resource(table_id: str, variables: list[dict] = None, format: DataFormat = "JSON", 
                  timeOrder: Optional[Literal["Ascending", "Descending"]] = None, 
                  lang: str = "da",
                  valuePresentation: Optional[Literal["Code", "Text"]] = None) -> Union[dict, bytes, str]:
    """Get data from a specific table
    
    Args:
        table_id: The table code (e.g., "folk1c").
        variables: Optional list of dicts to filter data. Each dict must have "code" (variable code) 
                  and "values" (list of desired value codes). If None or empty, fetches data for all 
                  values (with automatic elimination of variables).
        format: Output format. Default "JSONSTAT". Valid formats are: JSONSTAT, JSON, CSV, XLSX, BULK, PX, TSV, HTML5, HTML5InclNotes
        timeOrder: Optional string for sorting time series ("Ascending" or "Descending").
        lang: Language code for metadata in result ("da" or "en", default "da").
        valuePresentation: Optional string to control value presentation ("Code" or "Text").
    
    Returns:
        Data in the requested format. For JSON formats returns a dict, for other formats returns raw bytes or text.
    """
    return get_data(table_id, variables, format, timeOrder, lang, valuePresentation)

# Only define this tool if requests is available
if REQUESTS_AVAILABLE:
    @mcp.tool()
    async def get_statistics(dataset: str) -> str:
        """Get statistics from Danmarks Statistik.
        
        Args:
            dataset: The ID of the dataset to query
        """
        logger.debug(f"Fetching statistics for dataset: {dataset}")
        # Add your actual API logic here
        return f"Statistics for dataset {dataset}"

if __name__ == "__main__":
    try:
        logger.info("Starting Danmarks Statistik API Server...")
        mcp.run(transport='sse', host='0.0.0.0', port=8000, log_level='debug')
    except:
::contentReference[oaicite:0]{index=0}
 
