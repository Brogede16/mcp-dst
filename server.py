from typing import Any, Literal, Optional, Union, Dict, get_args # Importer get_args
from mcp.server.fastmcp import FastMCP
import sys
import logging
import requests
import os # Importer os modulet for at læse miljøvariabler

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("Danmarks Statistik API")

# Vi fjerner den utilrådelige logik til at installere requests med pip.main().
# Afhængigheder skal specificeres i requirements.txt og installeres under build-processen.
# Antager nu at requests er installeret korrekt via requirements.txt under build.

# Base URL for DST API
BASE_URL = "https://api.statbank.dk/v1"

# Define valid formats as a literal type
# Tilføjet SDMXCOMPACT og SDMXGENERIC, der bruges i get_data
DataFormat = Literal["JSONSTAT", "JSON", "CSV", "XLSX", "BULK", "PX", "TSV", "HTML5", "HTML5InclNotes", "SDMXCOMPACT", "SDMXGENERIC"]

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

    try:
        r = requests.post(url, json=payload)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.RequestException as e:
        logger.error(f"Request error in get_subjects: {e}")
        # Overvej at raise en specifik fejl eller returnere et standard fejl-respons
        raise # Re-raise exception after logging

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
        raise # Re-raise exception after logging


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
        raise # Re-raise exception after logging

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
    valid_formats = [arg.upper() for arg in get_args(DataFormat)] # Henter alle tilladte værdier og konverterer til uppercase
    format_upper = format.upper() # Konverter input format til uppercase for tjek
    if format_upper not in valid_formats:
         raise ValueError(f"Invalid format: {format}. Valid formats are: {', '.join(valid_formats)}")

    # Build the basic payload
    payload = {
        "table": table_id,
        "format": format_upper, # Brug den uppercase version her
        "lang": lang
    }

    # Handle variables - ensure proper structure
    # Tjekker for None og tom liste []
    if variables is not None and len(variables) > 0:
        processed_variables = []
        for var in variables:
            if not isinstance(var, dict) or "code" not in var or "values" not in var:
                 # Log fejlen og skip eller raise? Vælger at raise for at indikere problem med input.
                 raise ValueError(f"Invalid variable structure: {var}. Each variable must be a dict with 'code' and 'values' keys")

            values = var.get("values")
            if values is None:
                 # Håndter None i values - afhængig af API krav.
                 # Hvis None betyder "alle værdier for denne variabel", kræver API'et måske bare at nøglen udelades
                 # eller en specifik værdi. Her antager vi det er en fejl i input.
                 raise ValueError(f"Variable '{var.get('code', 'unknown')}' has no 'values' key or 'values' is None")

            if not isinstance(values, list):
                 # Hvis det ikke er en liste, konverter til en liste
                 processed_values = [values]
            else:
                 processed_values = values # Det er allerede en liste

            processed_variables.append({"code": var["code"], "values": processed_values})

        payload["variables"] = processed_variables
    # Hvis variables er None eller en tom liste [], sendes "variables" nøglen ikke i payload,
    # hvilket ifølge DST API'ets dokumentation (typisk) betyder at hente alle værdier.

    # Add optional parameters if provided
    if timeOrder:
        payload["timeOrder"] = timeOrder
    if valuePresentation:
        payload["valuePresentation"] = valuePresentation

    # Make the request
    try:
        # For store datasæt og streaming formater, brug stream=True
        # Inkluderer SDMXCOMPACT og SDMXGENERIC
        if format_upper in ["BULK", "SDMXCOMPACT", "SDMXGENERIC"]:
             r = requests.post(url, json=payload, stream=True)
        else:
            r = requests.post(url, json=payload)

        r.raise_for_status() # Tjek for HTTP statuskoder 4xx/5xx

        # Handle different response formats
        if format_upper in ["JSON", "JSONSTAT"]:
            return r.json()
        # Antager at disse formater er tekstbaserede
        elif format_upper in ["CSV", "PX", "TSV", "HTML5", "HTML5InclNotes"]:
            return r.text # Returner tekst for disse formater
        else:
            # For andre formater defineret i DataFormat (XLSX, BULK, SDMX...), returner bytes
            return r.content

    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error occurred: {e.response.status_code} - {e}")
        # Forsøg at parse fejl-response fra API'et, hvis den er i JSON
        try:
            error_detail = r.json()
            logger.error(f"API Error Details: {error_detail}")
            # Raise en ValueError med API'ets fejl-detaljer for bedre fejlsporing
            raise ValueError(f"API request failed: {error_detail}") from e # Kæder exceptions
        except requests.exceptions.JSONDecodeError:
            logger.error("Could not decode error response as JSON.")
            # Hvis responsen ikke er JSON, raise en fejl med statuskoden
            raise ValueError(f"API request failed with status {r.status_code} and could not parse error details.") from e
        except Exception as parse_e:
             # Fang andre uventede fejl under parse-forsøget
             logger.error(f"An unexpected error occurred while processing API error response: {parse_e}")
             raise ValueError(f"API request failed with status {r.status_code} and an unexpected error occurred during error processing.") from parse_e
    except requests.exceptions.RequestException as e:
        # Fang andre requests-relaterede fejl (netværksproblemer, timeout osv.)
        logger.error(f"Request Exception occurred: {e}")
        raise ValueError(f"API request failed due to network or other request error: {e}") from e
    except Exception as e:
        # Fang alle andre uventede fejl under datahentning
        logger.error(f"An unexpected error occurred while fetching data: {e}")
        raise # Re-raise exception


# Add resources for RESTful access
# Bemærk: Brugen af komplekse argumenter som 'variables' direkte i URL-stier
# via @mcp.resource kan være problematisk afhængigt af FastMCP's implementering.
# Den korrekte måde i et RESTful design ville typisk være at sende 'variables'
# i request body'en for en POST request til en sti som /data/{table_id}.
# Jeg beholder de originale definitioner, men vær opmærksom på dette potentielle designproblem.
@mcp.resource("statbank://subjects")
def subjects_resource() -> dict:
    """Get all subjects"""
    return get_subjects()

@mcp.resource("statbank://subjects/{subject_id}")
def subject_by_id_resource(subject_id: str) -> dict:
    """Get a specific subject"""
    # Sender subject_id som en liste, som get_subjects forventer
    return get_subjects(subjects=[subject_id])

@mcp.resource("statbank://tables")
def tables_resource() -> dict:
    """Get all tables"""
    return get_tables()

@mcp.resource("statbank://tableinfo/{table_id}")
def tableinfo_resource(table_id: str) -> dict:
    """Get info for a specific table"""
    return get_table_info(table_id)

# Denne resource definition er potentiel problematisk for 'variables' argumentet.
# FastMCP skal kunne parse {variables} fra URL'en til en list[dict].
# Hvis dette ikke virker, skal du redesign denne del til at bruge request body.
@mcp.resource("statbank://data/{table_id}/{variables}/{format}/{timeOrder}/{lang}/{valuePresentation}")
def data_resource(table_id: str, variables: list[dict] = None, format: DataFormat = "JSONSTAT",
                  timeOrder: Optional[Literal["Ascending", "Descending"]] = None,
                  lang: str = "da",
                  valuePresentation: Optional[Literal["Code", "Text"]] = None) -> Union[dict, bytes, str]:
    """Get data from a specific table (Note: Sending 'variables' via URL path might require specific FastMCP support)

    Args:
        table_id: The table code (e.g., "folk1c").
        variables: Optional list of dicts to filter data. Expected from URL path (might need parsing).
        format: Output format. Default "JSONSTAT".
        timeOrder: Optional string for sorting time series ("Ascending" or "Descending").
        lang: Language code for metadata in result ("da" or "en", default "da").
        valuePresentation: Optional string to control value presentation ("Code" or "Text").

    Returns:
        Data in the requested format. For JSON formats returns a dict, for other formats returns raw bytes or text.
    """
    # Vær opmærksom på, at 'variables' modtaget her fra URL'en Sandsynligvis
    # ikke er i det format (list[dict]) som get_data forventer direkte.
    # Du skal muligvis tilføje kode her for at parse strengen fra URL'en
    # til den korrekte list[dict] struktur FØR du kalder get_data.
    # Uden kendskab til FastMCP's specifikke URL-parsing for komplekse typer,
    # er dette en antagelse om, at FastMCP måske gør det, eller at du selv skal.
    # Hvis det fejler, er dette punktet at undersøge og rette.
    logger.warning("Calling data_resource - ensure 'variables' is correctly parsed from URL path if complex.")
    return get_data(table_id=table_id, variables=variables, format=format,
                    timeOrder=timeOrder, lang=lang, valuePresentation=valuePresentation)

# Dette tool afhænger ikke længere af en manuel requests-tjek.
# Hvis den skal lave asynkrone http-kald, brug httpx.
@mcp.tool()
async def get_statistics(dataset: str) -> str:
    """Get statistics from Danmarks Statistik.

    Args:
        dataset: The ID of the dataset to query
    """
    logger.debug(f"Fetching statistics for dataset: {dataset}")
    # Hvis du skal lave HTTP kald her, brug en asynkron klient som httpx:
    # import httpx
    # async with httpx.AsyncClient() as client:
    #     response = await client.get(f"{BASE_URL}/some_async_endpoint/{dataset}")
    #     response.raise_for_status()
    #     return response.text
    return f"Statistics for dataset {dataset} (Async Placeholder)"


# Hovedblokken til at starte serveren
if __name__ == "__main__":
    try:
        logger.info("Starting Danmarks Statistik API Server...")
        # Læs den dynamiske PORT miljøvariabel sat af Render.
        # Brug 8000 som en fallback port, hvis variablen ikke er sat (f.eks. ved lokal kørsel).
        render_port = int(os.environ.get("PORT", 8000))
        logger.info(f"Server will attempt to listen on port: {render_port}")

        # Kald mcp.run med den dynamiske port, uden 'host' argumentet.
        mcp.run(transport='sse', port=render_port, log_level='debug')

    except Exception as e:
        # Korrekt håndtering af fejl under opstart
        logger.error(f"An error occurred during server startup: {e}")
        sys.exit(1) # Afslut processen med en fejlkode
