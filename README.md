# MCP Server for Danmarks Statistik

En MCP (Machine Callable Programs) server, der eksponerer Danmarks Statistiks Statistikbank API som programmerbare ressourcer, hvilket gør det nemt at integrere med sprogmodeller og moderne AI-applikationer.

## Funktioner

- Fuld adgang til Danmarks Statistik API endpoints:
  - Emner (subjects)
  - Tabeller (tables)
  - Tabelmetadata (tableinfo)
  - Data
- Understøtter alle originale parametre fra API'et
- Returnerer data i forskellige formater: JSON, JSONSTAT, CSV, m.fl.
- Velegnet til integration med Large Language Models (LLMs) der understøtter MCP

## Installation

### Forudsætninger
- Python 3.9+

### Opsætning

1. Klon projektet:
   ```
   git clone https://github.com/yourusername/mcp-statbank.git
   cd mcp-statbank
   ```

2. Opret et virtuelt miljø:
   ```
   python -m venv .venv
   source .venv/bin/activate  # På Windows: .venv\Scripts\activate
   ```

3. Installer afhængigheder:
   ```
   pip install -r requirements.txt
   ```

## Brug

### Start serveren

```
python server.py
```

Dette starter MCP-serveren på standardporten (localhost:8000).

### Avanceret opstart

Med MCP CLI:

```
mcp dev server.py
```

Dette sikrer, at alle afhængigheder er installeret og starter serveren i udviklingstilstand.

### Ressourcer

Serveren eksponerer følgende MCP-ressource-URIs:

- `statbank://subjects` - Hent alle emner
- `statbank://subjects/{subject_id}` - Hent et specifikt emne
- `statbank://tables` - Hent alle tabeller
- `statbank://tableinfo/{table_id}` - Hent metadata for specifik tabel
- `statbank://data/{table_id}/{variables}/{format}/{timeOrder}/{lang}/{valuePresentation}` - Hent data fra en tabel

## Eksempler

### Hent emner
```python
mcp_client.call("statbank://subjects")
```

### Hent tabelmetadata
```python
mcp_client.call("statbank://tableinfo/folk1c")
```

### Hent data
```python
variables = [
    {"code": "område", "values": ["101"]},
    {"code": "alder", "values": ["*"]}
]
mcp_client.call("statbank://data/folk1c", variables=variables, format="JSON")
```

## Licens

[MIT](LICENSE)

## Bidrag

Bidrag er velkomne! Feel free to open issues or submit pull requests. 