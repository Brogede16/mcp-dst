from typing import Any, Literal, Optional, Union, Dict, get_args
from fastapi import FastAPI, Body
from pydantic import BaseModel
from mcp.server.fastmcp import FastMCP
import sys
import logging
import requests

# --- Setup Logging ---
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)

# --- Initialize Servers ---
app = FastAPI()
mcp = FastMCP("Danmarks Statistik API")
app.mount("/sse", mcp.sse_app())  # Bind MCP server til /sse

# --- Constants ---
BASE_URL = "https://api.statbank.dk/v1"
DataFormat = Literal[
    "JSONSTAT", "JSON", "CSV", "XLSX", "BULK", "PX", "TSV",
    "HTML5", "HTML5InclNotes", "SDMXCOMPACT", "SDMXGENERIC"
]

# --- Helper Functions (kald til DST API) ---
def get_subjects(subjects: list[str] = None, includeTables: bool = False, recursive: bool = False,
                 omitInactiveSubjects: bool = False, lang: str = "da") -> dict:
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

def get_tables(subjects: list[str] = None, pastdays: int = None, includeInactive: bool = False, lang: str = "da") -> dict:
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

def get_table_info(table_id: str, lang: str = "da") -> dict:
    url = f"{BASE_URL}/tableinfo"
    payload = {"table": table_id, "format": "JSON", "lang": lang}
    r = requests.post(url, json=payload)
    r.raise_for_status()
    return r.json()

def get_data(table_id: str, variables: list[dict] = None, format: DataFormat = "JSONSTAT",
             timeOrder: Optional[Literal["Ascending", "Descending"]] = None,
             lang: str = "da",
             valuePresentation: Optional[Literal["Code", "Text"]] = None) -> Union[dict, bytes, str]:
    url = f"{BASE_URL}/data"
    valid_formats = [arg.upper() for arg in get_args(DataFormat)]
    format_upper = format.upper()
    if format_upper not in valid_formats:
        raise ValueError(f"Invalid format: {format}. Valid formats are: {', '.join(valid_formats)}")
    payload = {
        "table": table_id,
        "format": format_upper,
        "lang": lang,
        "variables": variables or []
    }
    if timeOrder:
        payload["timeOrder"] = timeOrder
    if valuePresentation:
        payload["valuePresentation"] = valuePresentation
    r = requests.post(url, json=payload, stream=(format_upper in ["BULK", "SDMXCOMPACT", "SDMXGENERIC"]))
    r.raise_for_status()
    if format_upper in ["JSON", "JSONSTAT"]:
        return r.json()
    elif format_upper in ["CSV", "PX", "TSV", "HTML5", "HTML5InclNotes"]:
        return r.text
    else:
        return r.content

# --- Pydantic model til korrekt parsing af body for data ---
class DataRequest(BaseModel):
    variables: Optional[list[dict]] = None
    format: DataFormat = "JSONSTAT"
    timeOrder: Optional[str] = None
    lang: str = "da"
    valuePresentation: Optional[str] = None

# --- REST API Endpoints (til ChatGPT Actions) ---
@app.post("/statbank/subjects")
def subjects_rest(includeTables: bool = False, recursive: bool = False,
                  omitInactiveSubjects: bool = False, lang: str = "da"):
    return get_subjects(includeTables=includeTables, recursive=recursive,
                        omitInactiveSubjects=omitInactiveSubjects, lang=lang)

@app.post("/statbank/subjects/{subject_id}")
def subject_by_id_rest(subject_id: str, includeTables: bool = False, recursive: bool = False,
                       omitInactiveSubjects: bool = False, lang: str = "da"):
    return get_subjects(subjects=[subject_id], includeTables=includeTables,
                        recursive=recursive, omitInactiveSubjects=omitInactiveSubjects, lang=lang)

@app.post("/statbank/tables")
def tables_rest(includeInactive: bool = False, lang: str = "da"):
    return get_tables(includeInactive=includeInactive, lang=lang)

@app.post("/statbank/tableinfo/{table_id}")
def tableinfo_rest(table_id: str, lang: str = "da"):
    return get_table_info(table_id=table_id, lang=lang)

@app.post("/statbank/data/{table_id}")
def data_rest(table_id: str, body: DataRequest):
    return get_data(
        table_id=table_id,
        variables=body.variables,
        format=body.format,
        timeOrder=body.timeOrder,
        lang=body.lang,
        valuePresentation=body.valuePresentation
    )

# --- MCP Tools (valgfrit) ---
@mcp.tool()
def get_subjects_tool(**kwargs):
    return get_subjects(**kwargs)

@mcp.tool()
def get_tables_tool(**kwargs):
    return get_tables(**kwargs)

@mcp.tool()
def get_table_info_tool(**kwargs):
    return get_table_info(**kwargs)

@mcp.tool()
def get_data_tool(**kwargs):
    return get_data(**kwargs)
