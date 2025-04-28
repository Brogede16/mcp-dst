from typing import Any, Literal, Optional, Union, Dict, get_args
import sys
import logging
import requests

# NEW: Import Starlette components for HTTP routing
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse, Response
from starlette.concurrency import run_in_threadpool # To run sync functions in async endpoints

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# We don't need the mcp = FastMCP(...) instance here for HTTP routing anymore.
# The decorators are removed.
# The core functions remain.

# Base URL for DST API
BASE_URL = "https://api.statbank.dk/v1" # Korrekt URL

# Define valid formats as a literal type
DataFormat = Literal["JSONSTAT", "JSON", "CSV", "XLSX", "BULK", "PX", "TSV", "HTML5", "HTML5InclNotes", "SDMXCOMPACT", "SDMXGENERIC"]

# --- Kerne Funktioner (Din logik - med rettelse i get_data) ---

# Fjern @mcp.tool()
def get_subjects(subjects: list[str] = None, includeTables: bool = False, recursive: bool = False,
                 omitInactiveSubjects: bool = False, lang: str = "da") -> dict:
    """Get subjects from DST API"""
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


# Fjern @mcp.tool()
def get_tables(subjects: list[str] = None, pastdays: int = None, includeInactive: bool = False, lang: str = "da") -> dict:
    """Get tables from DST API"""
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


# Fjern @mcp.tool()
def get_table_info(table_id: str, lang: str = "da") -> dict:
    """Get table metadata from DST API"""
    url = f"{BASE_URL}/tableinfo"
    payload = {"table": table_id, "format": "JSON", "lang": lang}

    try:
        r = requests.post(url, json=payload)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error in get_table_info: {e}")
        raise

# Fjern @mcp.tool() - RETTET LOGIK TIL BEHANDLING AF 'variables' HER
def get_data(table_id: str, variables: list[dict] = None, format: DataFormat = "JSONSTAT",
             timeOrder: Optional[Literal["Ascending", "Descending"]] = None,
             lang: str = "da",
             valuePresentation: Optional[Literal["Code", "Text"]] = None) -> Union[dict, bytes, str]:
    """Get data from DST API"""
    url = f"{BASE_URL}/data"

    valid_formats = [arg.upper() for arg in get_args(DataFormat)]
    format_upper = format.upper()
    if format_upper not in valid_formats:
         raise ValueError(f"Invalid format: {format}. Valid formats are: {', '.join(valid_formats)}")

    payload = {
        "table": table_id,
        "format": format_upper,
        "lang": lang
    }

    # --- RETTET LOGIK TIL BEHANDLING AF 'variables' ---
    if variables is not None and len(variables) > 0:
        processed_variables_list = [] # Initialiser listen til at opsamle alle variable
        for var in variables:
            # Validering for dict structure and required keys
            if not isinstance(var, dict) or "code" not in var or "values" not in var:
                 logger.warning(f"Skipping invalid variable structure: {var}")
                 continue # Spring denne ugyldige variabel over

            variable_code = var.get("code")
            variable_values = var.get("values")

            if variable_code is None:
                 logger.warning(f"Skipping variable with missing 'code': {var}")
                 continue

            if variable_values is None:
                 logger.warning(f"Skipping variable with missing 'values': {var}")
                 continue

            # Sørg for, at værdierne er en liste
            if not isinstance(variable_values, list):
                 # Hvis det ikke er en liste, pak værdien ind i en liste
                 processed_values_for_this_variable = [variable_values]
            else:
                 # Hvis det allerede er en liste, brug listen som den er
                 processed_values_for_this_variable = variable_values

            # Tilføj den behandlede variabel-definition til den opsamlende liste
            processed_variables_list.append({"code": variable_code, "values": processed_values_for_this_variable})

        # Når løkken er færdig, sæt den opsamlede liste ind i payload'en
        payload["variables"] = processed_variables_list
    else:
         # Hvis variables var None eller tom liste, send en tom liste
         payload["variables"] = []
    # --- SLUT PÅ RETTET LOGIK ---

    if timeOrder:
        payload["timeOrder"] = timeOrder
    if valuePresentation:
        payload["valuePresentation"] = valuePresentation

    try:
        logger.debug(f"Sending payload to DST API: {payload}") # Log payload før kald
        if format_upper in ["BULK", "SDMXCOMPACT", "SDMXGENERIC"]:
             r = requests.post(url, json=payload, stream=True)
        else:
            r = requests.post(url, json=payload)

        r.raise_for_status()

        logger.debug(f"Received status code {r.status_code} from DST API") # Log successful status code

        if format_upper in ["JSON", "JSONSTAT"]:
            return r.json()
        elif format_upper in ["CSV", "PX", "TSV", "HTML5", "HTML5InclNotes"]:
            return r.text
        else:
            return r.content

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error occurred during DST API call: {e.response.status_code} - {e}")
        try:
            # Log API error details if available and parseable as JSON
            if r.headers.get('Content-Type', '').startswith('application/json'):
                 error_detail = r.json()
                 logger.error(f"DST API Error Details: {error_detail}")
                 raise ValueError(f"DST API request failed: {error_detail.get('message', str(error_detail))}") from e
            else:
                 # Log raw error response if not JSON
                 logger.error(f"DST API Error Response (non-JSON): {r.text[:200]}...") # Log first 200 chars
                 raise ValueError(f"DST API request failed with status {r.status_code}. Response was not JSON.") from e
        except Exception as parse_e:
             logger.error(f"An unexpected error occurred while processing DST API error response: {parse_e}")
             raise ValueError(f"DST API request failed with status {r.status_code} and an error occurred while processing the error response.") from parse_e
    except requests.exceptions.RequestException as e:
        logger.error(f"Request Exception occurred during DST API call: {e}")
        raise ValueError(f"DST API request failed due to network or other request error: {e}") from e
    except Exception as e:
        # Fang alle andre uventede fejl under datahentning
        logger.error(f"An unexpected error occurred within get_data: {e}", exc_info=True) # Log traceback
        raise # Re-raise other unexpected errors


# Fjern @mcp.tool()
async def get_statistics(dataset: str) -> str:
    """Get statistics for a specific dataset from Danmarks Statistik."""
    logger.debug(f"Fetching statistics for dataset: {dataset}")
    # Implement actual API call here, using async httpx if needed
    # import httpx
    # async with httpx.AsyncClient() as client:
    #     response = await client.get(f"{BASE_URL}/some_async_endpoint/{dataset}") # Replace with actual endpoint
    #     response.raise_for_status()
    #     return response.text
    # For now, return placeholder
    return f"Statistics for dataset {dataset} (Placeholder - Actual API call needed)"


# --- Starlette Endpoints (definerer HTTP-ruting og kalder kerne-funktioner) ---

# Endpoint for GET /statbank/subjects
async def subjects_endpoint(request: Request):
    subjects = request.query_params.getlist('subjects')
    includeTables = request.query_params.get('includeTables', '').lower() == 'true'
    recursive = request.query_params.get('recursive', '').lower() == 'true'
    omitInactiveSubjects = request.query_params.get('omitInactiveSubjects', '').lower() == 'true'
    lang = request.query_params.get('lang', 'da')

    try:
        data = await run_in_threadpool(get_subjects, subjects=subjects if subjects else None,
                                       includeTables=includeTables, recursive=recursive,
                                       omitInactiveSubjects=omitInactiveSubjects, lang=lang)
        return JSONResponse(data)
    except ValueError as e: # Catch ValueErrors from get_subjects
         return JSONResponse({"detail": str(e)}, status_code=400) # Return 400 for client errors
    except Exception as e:
        logger.error(f"Error in subjects_endpoint: {e}", exc_info=True)
        return JSONResponse({"detail": "Internal Server Error"}, status_code=500)

# Endpoint for GET /statbank/subjects/{subject_id}
async def subject_by_id_endpoint(request: Request):
    subject_id = request.path_params['subject_id']
    lang = request.query_params.get('lang', 'da')

    try:
        data = await run_in_threadpool(get_subjects, subjects=[subject_id], lang=lang)
        # Note: get_subjects returns a list, you might want to return the first item or handle list response
        # For a single subject ID, DST usually returns a list with one item or empty.
        if data and isinstance(data, list) and len(data) > 0:
            return JSONResponse(data[0]) # Return the first item if list has items
        elif data is None or (isinstance(data, list) and len(data) == 0):
             return JSONResponse({"detail": f"Subject with ID '{subject_id}' not found."}, status_code=404) # Return 404 if not found
        else:
             # Unexpected response format from get_subjects
             logger.error(f"Unexpected response format from get_subjects for single ID: {data}")
             return JSONResponse({"detail": "Unexpected response format from upstream API"}, status_code=500)

    except ValueError as e: # Catch ValueErrors from get_subjects
         return JSONResponse({"detail": str(e)}, status_code=400) # Return 400 for client errors
    except Exception as e:
        logger.error(f"Error in subject_by_id_endpoint: {e}", exc_info=True)
        return JSONResponse({"detail": "Internal Server Error"}, status_code=500)


# Endpoint for GET /statbank/tables
async def tables_endpoint(request: Request):
    subjects = request.query_params.getlist('subjects')
    pastdays_str = request.query_params.get('pastdays')
    includeInactive = request.query_params.get('includeInactive', '').lower() == 'true'
    lang = request.query_params.get('lang', 'da')

    pastdays = None
    if pastdays_str:
        try:
            pastdays = int(pastdays_str)
        except ValueError:
             return JSONResponse({"detail": "Invalid 'pastdays' parameter. Must be an integer."}, status_code=400)

    try:
        data = await run_in_threadpool(get_tables, subjects=subjects if subjects else None,
                                       pastdays=pastdays, includeInactive=includeInactive, lang=lang)
        return JSONResponse(data)
    except ValueError as e: # Catch ValueErrors from get_tables
         return JSONResponse({"detail": str(e)}, status_code=400) # Return 400 for client errors
    except Exception as e:
        logger.error(f"Error in tables_endpoint: {e}", exc_info=True)
        return JSONResponse({"detail": "Internal Server Error"}, status_code=500)

# Endpoint for GET /statbank/tableinfo/{table_id}
async def tableinfo_endpoint(request: Request):
    table_id = request.path_params['table_id']
    lang = request.query_params.get('lang', 'da')

    try:
        data = await run_in_threadpool(get_table_info, table_id=table_id, lang=lang)
        # Check if the response indicates table not found (DST API returns 404, handled in get_table_info)
        # Assuming get_table_info raises ValueError for API 404 as per its error handling
        return JSONResponse(data)
    except ValueError as e: # Catch ValueErrors from get_table_info (includes API 404 details)
         # If the ValueError message contains '404' or 'not found', might return 404 here.
         # For simplicity, returning 400 for any ValueError from the underlying function.
         return JSONResponse({"detail": str(e)}, status_code=400) # Return 400 for client errors
    except Exception as e:
        logger.error(f"Error in tableinfo_endpoint: {e}", exc_info=True)
        return JSONResponse({"detail": "Internal Server Error"}, status_code=500)


# Endpoint for POST /statbank/data/{table_id}
async def data_endpoint(request: Request):
    table_id = request.path_params['table_id']

    # Parse query parameters
    format = request.query_params.get('format', 'JSONSTAT')
    timeOrder = request.query_params.get('timeOrder')
    lang = request.query_params.get('lang', 'da')
    valuePresentation = request.query_params.get('valuePresentation')

    # Parse request body for variables (assuming JSON body for POST)
    variables = None # Default if no body or variables key
    try:
        body = await request.json()
        variables = body.get('variables')
        # Basic validation: variables should be a list if present
        if variables is not None and not isinstance(variables, list):
             logger.warning(f"Received non-list 'variables' in request body: {variables}")
             # Decide how to handle: return 400 or try to process?
             # Let's return 400 as per OpenAPI spec expectation
             return JSONResponse({"detail": "'variables' in request body must be a list"}, status_code=400)

    except Exception as e: # Handle JSON parsing errors if body is not valid JSON
        # If body is empty or not valid JSON, request.json() will raise exception
        # In this case, variables remains None. If 'variables' is required, get_data handles it.
        logger.warning(f"Could not parse request body as JSON or body is empty: {e}")
        pass # Continue with variables = None

    # Call the underlying synchronous get_data function in a threadpool
    try:
        data = await run_in_threadpool(get_data, table_id=table_id, variables=variables,
                                       format=format, timeOrder=timeOrder,
                                       lang=lang, valuePresentation=valuePresentation)

        # Determine response type based on format and return appropriate response
        format_upper = format.upper()
        if format_upper in ["JSON", "JSONSTAT"]:
            return JSONResponse(data)
        elif format_upper in ["CSV", "PX", "TSV", "HTML5", "HTML5InclNotes"]:
            return PlainTextResponse(data, media_type=f"text/{format_upper.lower()}") # Use appropriate text media type
        elif format_upper == "XLSX":
             return Response(content=data, media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        elif format_upper in ["BULK", "SDMXCOMPACT", "SDMXGENERIC"]:
            return Response(content=data, media_type="application/octet-stream") # Generic binary type
        else:
             # Should not happen due to get_data format validation, but as a fallback
             return Response(content=data, media_type="application/octet-stream")


    except ValueError as e: # Catch ValueErrors raised from get_data (e.g., invalid format, API error details)
         # Log the specific ValueError detail for debugging
         logger.error(f"ValueError in data_endpoint: {e}")
         return JSONResponse({"detail": str(e)}, status_code=400) # Return 400 for client errors
    except Exception as e: # Catch other unexpected errors
         logger.error(f"Unexpected error in data_endpoint: {e}", exc_info=True) # Log traceback
         return JSONResponse({"detail": "Internal Server Error"}, status_code=500) # Return 500 for server errors


# Endpoint for POST /statbank/statistics/{dataset} (assuming POST for tool)
async def statistics_endpoint(request: Request):
    dataset = request.path_params['dataset']

    try:
        # Assuming get_statistics is async as defined with async def
        statistics_result = await get_statistics(dataset=dataset)
        return PlainTextResponse(statistics_result)
    except Exception as e:
        logger.error(f"Error in statistics_endpoint: {e}", exc_info=True)
        return JSONResponse({"detail": "Internal Server Error"}, status_code=500)


# --- Definer Starlette Ruter ---
# Map HTTP-stier og -metoder til dine endpoints

routes = [
    # Standard GET endpoints for Resources
    Route("/statbank/subjects", endpoint=subjects_endpoint, methods=["GET"]),
    Route("/statbank/subjects/{subject_id}", endpoint=subject_by_id_endpoint, methods=["GET"]),
    Route("/statbank/tables", endpoint=tables_endpoint, methods=["GET"]),
    Route("/statbank/tableinfo/{table_id}", endpoint=tableinfo_endpoint, methods=["GET"]),

    # Standard POST endpoint for Data (som kræver request body)
    Route("/statbank/data/{table_id}", endpoint=data_endpoint, methods=["POST"]),

    # Standard POST endpoint for Statistics Tool
    Route("/statbank/statistics/{dataset}", endpoint=statistics_endpoint, methods=["POST"]),
]

# Initialize the Starlette application instance
# This 'app' instance is what Uvicorn will run.
app = Starlette(routes=routes)

# Fjern hele if __name__ == "__main__": blokken
# if __name__ == "__main__":
#    ... Fjernet ...
