# Infinium DB2 Queries

Queries for extracting data from the Infinium ERP system (DB2).

## Connection

- **Type:** DB2 via pyodbc DSN
- **DSN:** `CRYSTAL-CLIENT EXPRESS`
- **Credentials:** 
  - `INFINIUM_USER` (in `.env`)
  - `INFINIUM_PW` (in `.env`)

## Connection Example

```python
import os
import pyodbc
from dotenv import load_dotenv

load_dotenv()

dsn = os.getenv('DB2_DSN', 'CRYSTAL-CLIENT EXPRESS')
username = os.getenv('INFINIUM_USER')
password = os.getenv('INFINIUM_PW')

conn_string = f'DSN={dsn};UID={username};PWD={password}'
conn = pyodbc.connect(conn_string)
```

## Queries

| Query | Table | Purpose | Frequency |
|-------|-------|---------|-----------|
| `gl_actuals.sql` | GLCUFA.GLPTX1 | GL transactions | Daily |

## Tables

| Schema.Table | Description |
|--------------|-------------|
| GLCUFA.GLPTX1 | GL transaction detail |

