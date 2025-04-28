from typing import Any, Literal, Optional, Union, Dict, get_args
from mcp.server.fastmcp import FastMCP
import sys
import logging
import requests
# import os # Ikke nødvendigt at importere os her

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server - This instance is the ASGI app callable via .sse_app()
mcp = FastMCP("Danmarks Statistik API")

# Base URL for DST API
BASE_URL = "https://api.statbank.dk/v1" # Korrekt URL

# Define valid formats as a literal type
DataFormat = Literal["JSONSTAT", "JSON", "CSV", "XLSX", "BULK", "PX", "TSV", "HTML5", "HTML5InclNotes", "SDMXCOMPACT", "SDMXGENERIC"]

# --- Tool Funktioner (Inkluderet som ønsket) ---

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

    try:
        r = requests.post(url, json=payload)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error in get_subjects: {e}")
        raise


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

    try:
        r = requests.post(url, json=payload)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error in get_tables: {e}")
        raise


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

    try:
        r = requests.post(url, json=payload)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error in get_table_info: {e}")
        raise

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
        format: Output format. Default "JSONSTAT". Valid formats are: JSONSTAT, JSON, CSV, XLSX, BULK, PX, TSV, HTML5, HTML5InclNotes, SDMXCOMPACT, SDMXGENERIC
        timeOrder: Optional string for sorting time series ("Ascending" or "Descending").
        lang: Language code for metadata in result ("da" or "en", default "da").
        valuePresentation: Optional string to control value presentation ("Code" or "Text").

    Returns:
        Data in the requested format. For JSON formats returns a dict, for other formats returns raw bytes or text.
    """
    url = f"{BASE_URL}/data"

    # Validate and normalize format
    valid_formats = [arg.upper() for arg in get_args(DataFormat)]
    format_upper = format.upper()
    if format_upper not in valid_formats:
         raise ValueError(f"Invalid format: {format}. Valid formats are: {', '.join(valid_formats)}")

    # Build the basic payload
    payload = {
        "table": table_id,
        "format": format_upper,
        "lang": lang
    }

    # Handle variables - ensure proper structure
    if variables is not None and len(variables) > 0:
        processed_variables = []
        for var in variables:
            if not isinstance(var, dict) or "code" not in var or "values" not in var:
                 raise ValueError(f"Invalid variable structure: {var}. Each variable must be a dict with 'code' and 'values' keys")

            values = var.get("values")
            if values is None:
                 raise ValueError(f"Variable '{var.get('code', 'unknown')}' has no 'values' key or 'values' is None")

            if not isinstance(values, list):
                 processed_values = [values]
            else:
                 processed_variables = values # Use original list if it's already a list

            processed_variables.append({"code": var["code"], "values": processed_values})

        payload["variables"] = processed_variables

    # Add optional parameters if provided
    if timeOrder:
        payload["timeOrder"] = timeOrder
    if valuePresentation:
        payload["valuePresentation"] = valuePresentation

    # Make the request
    try:
        if format_upper in ["BULK", "SDMXCOMPACT", "SDMXGENERIC"]:
             # For streaming, you might want to return the raw response object or handle streaming differently
             # depending on how FastMCP resources/tools are expected to return streaming data.
             # For a simple HTTP endpoint, returning r.content is common for binary/large text.
             r = requests.post(url, json=payload, stream=True)
        else:
            r = requests.post(url, json=payload)

        r.raise_for_status()

        # Handle different response formats
        if format_upper in ["JSON", "JSONSTAT"]:
            return r.json()
        elif format_upper in ["CSV", "PX", "TSV", "HTML5", "HTML5InclNotes"]:
            return r.text
        else:
            return r.content # For XLSX, BULK, SDMX...

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error occurred: {e.response.status_code} - {e}")
        try:
            error_detail = r.json()
            logger.error(f"API Error Details: {error_detail}")
            raise ValueError(f"API request failed: {error_detail}") from e
        except requests.exceptions.JSONDecodeError:
            logger.error("Could not decode error response as JSON.")
            raise ValueError(f"API request failed with status {r.status_code} and could not parse error details.") from e
        except Exception as parse_e:
             logger.error(f"An unexpected error occurred while processing API error response: {parse_e}")
             raise ValueError(f"API request failed with status {r.status_code} and an unexpected error occurred during error processing.") from parse_e
    except requests.exceptions.RequestException as e:
        logger.error(f"Request Exception occurred: {e}")
        raise ValueError(f"API request failed due to network or other request error: {e}") from e
    except Exception as e:
        logger.error(f"An unexpected error occurred while fetching data: {e}")
        raise


@mcp.tool()
async def get_statistics(dataset: str) -> str:
    """Get statistics for a specific dataset from Danmarks Statistik.

    Args:
        dataset: The ID of the dataset to query
    """
    logger.debug(f"Fetching statistics for dataset: {dataset}")
    # Example using httpx for async HTTP calls (requires httpx installed)
    # import httpx
    # async with httpx.AsyncClient() as client:
    #     response = await client.get(f"{BASE_URL}/some_async_endpoint/{dataset}") # Replace with actual endpoint
    #     response.raise_for_status()
    #     return response.text
    # Currently returns a placeholder string
    return f"Statistics for dataset {dataset} (Placeholder - Actual API call needed)"


# --- Resource Definition med stibaserede URI'er ---

@mcp.resource("/statbank/subjects")
def subjects_resource() -> dict:
    """Get all subjects from DST API"""
    return get_subjects()

@mcp.resource("/statbank/subjects/{subject_id}")
def subject_by_id_resource(subject_id: str) -> dict:
    """Get a specific subject from DST API"""
    return get_subjects(subjects=[subject_id])

@mcp.resource("/statbank/tables")
def tables_resource() -> dict:
    """Get tables from DST API"""
    return get_tables()

@mcp.resource("/statbank/tableinfo/{table_id}")
def tableinfo_resource(table_id: str) -> dict:
    """Get metadata for a specific table from DST API"""
    return get_table_info(table_id)

# OBS! Denne resource definition med komplekse parametre i URL-stien er IKKE standard for HTTP.
# For nem integration med standard HTTP/OpenAI, bør du overveje at ændre denne
# til en POST-anmodning til f.eks. "/statbank/data/{table_id}" og sende
# 'variables', 'format', osv. i request body og/eller query parametre.
# Koden her bruger den definition du havde, men OpenAPI specifikationen vil
# beskrive det som en standard POST for kompatibilitet.
@mcp.resource("/statbank/data/{table_id}/{variables}/{format}/{timeOrder}/{lang}/{valuePresentation}")
def data_resource(table_id: str, variables: list[dict] = None, format: DataFormat = "JSONSTAT",
                  timeOrder: Optional[Literal["Ascending", "Descending"]] = None,
                  lang: str = "da",
                  valuePresentation: Optional[Literal["Code", "Text"]] = None) -> Union[dict, bytes, str]:
    """Get data from a specific table from DST API"""
    # Som nævnt, usandsynligt at 'variables' og andre komplekse/enum parametre
    # parses korrekt fra URL-stien af et standard HTTP framework/Uvicorn.
    # Den underliggende get_data funktion er dog intakt.
    logger.warning("Data resource called. Parameter parsing from non-standard URL path might not work as expected via HTTP.")
    return get_data(table_id=table_id, variables=variables, format=format,
                    timeOrder=timeOrder, lang=lang, valuePresentation=valuePresentation)


# Resource/Tool definition for get_statistics hvis relevant
# Typisk som et tool, da det potentielt laver et eksternt kald.
# @mcp.tool("/statbank/statistics/{dataset}") # Eksempel på Tool med sti
# async def statistics_tool(dataset: str) -> str:
#     """Get statistics for a specific dataset"""
#     return await get_statistics(dataset) # Kalder den underliggende async funktion


# Fjern hele if __name__ == "__main__": blokken
# da serveren startes af Uvicorn på Render via Start Command
# if __name__ == "__main__":
#    ... Fjernet ...
