from typing import Any, Literal, Optional, Union, Dict
from mcp.server.fastmcp import FastMCP
import sys
import logging
import requests # Fjernet try...except for import, da afhængigheder håndteres via requirements.txt

# Set up logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# Initialize FastMCP server
mcp = FastMCP("Danmarks Statistik API")

# Fjernet den problematiske blok der forsøgte at installere requests med pip.main()
# Antager nu at requests er installeret korrekt via requirements.txt under build.
# REQUESTS_AVAILABLE vil altid være True hvis importen lykkes her i starten.

# Base URL for DST API
BASE_URL = "https://api.statbank.dk/v1"

# Define valid formats as a literal type
# Tilføjet SDMXCOMPACT og SDMXGENERIC baseret på brug i get_data
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

    # Tjekker om requests er importeret (skulle altid være True nu)
    # if not REQUESTS_AVAILABLE:
    #     logger.error("Requests module is not available.")
    #     # Returner passende fejl eller raise en exception
    #     return {"error": "Requests module not available"}

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
        format: Output format. Default "JSONSTAT". Valid formats are: JSONSTAT, JSON, CSV, XLSX, BULK, PX, TSV, HTML5, HTML5InclNotes, SDMXCOMPACT, SDMXGENERIC
        timeOrder: Optional string for sorting time series ("Ascending" or "Descending").
        lang: Language code for metadata in result ("da" or "en", default "da").
        valuePresentation: Optional string to control value presentation ("Code" or "Text").

    Returns:
        Data in the requested format. For JSON formats returns a dict, for other formats returns raw bytes or text.
    """
    url = f"{BASE_URL}/data"

    # Validate and normalize format
    # Tjekker om format er i de tilladte, da Literal kun er for type-hinting
    valid_formats = get_args(DataFormat) # Henter alle tilladte værdier fra Literal
    format = format.upper()
    if format not in valid_formats:
         raise ValueError(f"Invalid format: {format}. Valid formats are: {', '.join(valid_formats)}")

    # Build the basic payload
    payload = {
        "table": table_id,
        "format": format,
        "lang": lang
    }

    # Handle variables - ensure proper structure
    # Tilføjet tjek for tom liste []
    if variables is not None and len(variables) > 0:
        # Ensure each variable has required structure
        for var in variables:
            if not isinstance(var, dict) or "code" not in var or "values" not in var:
                raise ValueError("Each variable must be a dict with 'code' and 'values' keys")
            if not isinstance(var.get("values"), list): # Brug .get for sikkerhed og tjek om det er en liste
                 # Konverterer enkelt værdi til liste, hvis det ikke allerede er en liste
                 # Sørger også for at håndtere None eller andre typer i values
                 if var.get("values") is not None:
                      var["values"] = [var["values"]]
                 else:
                      var["values"] = [] # Eller håndter som en fejl afhængig af API krav

        payload["variables"] = variables
    # Hvis variables er None eller en tom liste [], sendes "variables" nøglen ikke i payload
    # som forventet af DST API'et for at hente alle værdier.

    # Add optional parameters if provided
    if timeOrder:
        payload["timeOrder"] = timeOrder
    if valuePresentation:
        payload["valuePresentation"] = valuePresentation

    # For store datasæt, brug streaming formater
    # Inkluderer SDMXCOMPACT og SDMXGENERIC her, som nu er i DataFormat
    if format in ["BULK", "SDMXCOMPACT", "SDMXGENERIC"]:
        r = requests.post(url, json=payload, stream=True)
        r.raise_for_status()
        return r.content # Returner raw bytes for streaming

    # Make the request
    r = requests.post(url, json=payload)

    # Handle potential errors with more detail
    try:
        r.raise_for_status()
    except requests.exceptions.HTTPError as e:
        logger.error(f"HTTP error occurred: {e.response.status_code} - {e}")
        # Forsøg at parse fejl-response, hvis den er i JSON
        try:
            error_detail = r.json()
            logger.error(f"API Error Details: {error_detail}")
            raise ValueError(f"API request failed: {error_detail}") from e # Kæder exceptions
        except requests.exceptions.JSONDecodeError:
            logger.error("Could not decode error response as JSON.")
            raise ValueError(f"API request failed with status {r.status_code} and no JSON error details.") from e
        except Exception as parse_e:
             logger.error(f"An unexpected error occurred while processing API error: {parse_e}")
             raise ValueError(f"API request failed with status {r.status_code} and unexpected error.") from parse_e

    # Handle different response formats
    if format in ["JSON", "JSONSTAT"]:
        return r.json()
    # Antager at disse formater er tekstbaserede
    elif format in ["CSV", "PX", "TSV", "HTML5", "HTML5InclNotes"]:
        return r.text # Returner tekst for disse formater
    else:
        # For andre formater defineret i DataFormat, returner bytes (inkl. XLSX, BULK, SDMX...)
        return r.content


# Add resources for RESTful access
# Beholder de originale resource-stier, men vær opmærksom på potentialet
# problem med at sende komplekse 'variables' via URL-sti.
# En mere robust løsning ville sende 'variables' i request body for POST.
@mcp.resource("statbank://subjects")
def subjects_resource() -> dict:
    """Get all subjects"""
    # Kald den underliggende tool funktion
    return get_subjects()

@mcp.resource("statbank://subjects/{subject_id}")
def subject_by_id_resource(subject_id: str) -> dict:
    """Get a specific subject"""
    # Kald den underliggende tool funktion
    return get_subjects(subjects=[subject_id]) # Sender subject_id som en liste

@mcp.resource("statbank://tables")
def tables_resource() -> dict:
    """Get all tables"""
    # Kald den underliggende tool funktion
    return get_tables()

@mcp.resource("statbank://tableinfo/{table_id}")
def tableinfo_resource(table_id: str) -> dict:
    """Get info for a specific table"""
    # Kald den underliggende tool funktion
    return get_table_info(table_id)

# Denne resource definition er sandsynligvis problematisk for 'variables' argumentet.
# Den forventer 'variables' som en del af URL'en, men get_data forventer list[dict].
# Hvis du bruger denne resource, skal du finde ud af, hvordan FastMCP fortolker
# {variables} i stien og konverterer det til den nødvendige list[dict] struktur,
# eller ændre API designet til at sende komplekser argumenter i request body.
# For demonstration er signaturen beholdt, men bemærk det logiske mismatch med get_data.
@mcp.resource("statbank://data/{table_id}/{variables}/{format}/{timeOrder}/{lang}/{valuePresentation}")
def data_resource(table_id: str, variables: list[dict] = None, format: DataFormat = "JSONSTAT",
                  timeOrder: Optional[Literal["Ascending", "Descending"]] = None,
                  lang: str = "da",
                  valuePresentation: Optional[Literal["Code", "Text"]] = None) -> Union[dict, bytes, str]:
    """Get data from a specific table (Note: Sending 'variables' via URL path might be problematic)

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
    # Kald den underliggende tool funktion.
    # Vær opmærksom på, at 'variables' modtaget her fra URL'en sandsynligvis ikke
    # er i det format, som get_data funktionen forventer (list[dict]).
    # Du skal muligvis tilføje logik her for at parse URL-parameteren 'variables'
    # til en list[dict] struktur, eller revidere hvordan denne resource bruges.
    return get_data(table_id=table_id, variables=variables, format=format,
                    timeOrder=timeOrder, lang=lang, valuePresentation=valuePresentation)

# Dette tool afhænger ikke længere af den problematiske REQUESTS_AVAILABLE variabel.
@mcp.tool()
async def get_statistics(dataset: str) -> str:
    """Get statistics from Danmarks Statistik.

    Args:
        dataset: The ID of the dataset to query
    """
    logger.debug(f"Fetching statistics for dataset: {dataset}")
    # Add your actual API logic here
    # Da dette er en async funktion, skal den bruge en async http klient som httpx
    # i stedet for requests, hvis den skal lave http kald.
    # Eksempel (kræver httpx installeret i requirements.txt):
    # async with httpx.AsyncClient() as client:
    #     response = await client.get(f"{BASE_URL}/your_endpoint/{dataset}")
    #     response.raise_for_status()
    #     return response.text # Eller response.json()
    return f"Statistics for dataset {dataset} (Placeholder)"


# Korrekt try...except blok med indrykket kode
if __name__ == "__main__":
    try:
        logger.info("Starting Danmarks Statistik API Server...")
        # mcp.run starter serveren. Tjek FastMCP dokumentation for korrekt brug
        # med asynkrone tools som get_statistics, hvis du bruger dem.
        mcp.run(transport='sse', host='0.0.0.0', port=8000, log_level='debug')
    except Exception as e:
        # Dette er den rettede og indrykkede fejlhåndtering
        logger.error(f"An error occurred during server startup: {e}")
        sys.exit(1) # Vigtigt: Afslut processen med en fejlkode ved fejl
