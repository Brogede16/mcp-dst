# MCP Server for Danmarks Statistik

En MCP server, der eksponerer Danmarks Statistiks Statistikbank API som programmerbare ressourcer, hvilket gør det nemt at integrere med sprogmodeller og moderne AI-applikationer.

## Funktioner

- Fuld adgang til Danmarks Statistik API endpoints:
  - Emner (subjects)
  - Tabeller (tables)
  - Tabelmetadata (tableinfo)
  - Data
- Understøtter alle originale parametre fra API'et
- Returnerer data i forskellige formater: JSON, JSONSTAT, CSV, m.fl.
- Velegnet til integration med Large Language Models (LLMs) der understøtter MCP

## Værdi og anvendelse

Denne MCP-integration giver mulighed for at bygge AI-assistenter, der kan udføre datadrevne analyser baseret på naturlig sproginteraktion med Danmarks Statistiks data. Brugerne kan stille almindelige spørgsmål på dansk, og AI-assistenten finder selv de relevante tabeller, henter data, og præsenterer resultaterne på en forståelig måde.

### Konkrete eksempler på spørgsmål

Med denne integration kan brugere stille simple spørgsmål som:

- **"Hvor mange mennesker bor der i København?"** *(667.099 indbyggere iflg. seneste tal)*
- **"Hvilken kommune har de sidste 10 år haft det største procentvise fald i indbyggere?"** *(Lolland med et fald på 9,07%)*
- **"I hvilken kommune bor flest i almen boligbyggeri?"** *(absolut: København, procentvis: Brøndby med 50,9%)*
- **"Hvordan er kønsfordelingen blandt beboere i almene boliger?"** *(53,3% kvinder / 46,7% mænd nationalt)*

### Fordele

- **Ingen kodekundskaber krævet** - Slutbrugeren behøver ikke kende til SQL, programmering eller datastrukturer
- **Naturligt sprog** - Interaktion foregår med almindelige spørgsmål på dansk
- **Automatisk datafinding** - AI-assistenten finder selv de relevante tabeller og data
- **Kontekstbevidst analyse** - Kan sammenligne data på tværs af tid, geografi og kategorier
- **Tidsbesparende** - Eliminerer behovet for manuel datasøgning og -behandling
- **Demokratiserer data** - Gør komplekse statistiske data tilgængelige for alle

![Danmarks Statistik MCP Demo](images/comic.png)

