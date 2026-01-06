"""
Infinium DB2 database connection.
"""

import pyodbc
from src.config import Config


def get_infinium_connection():
    """
    Create a connection to the Infinium DB2 database.
    
    Returns:
        pyodbc.Connection: Active database connection
        
    Raises:
        Exception: If connection fails
    """
    conn_string = Config.get_db2_connection_string()
    return pyodbc.connect(conn_string)


def test_connection():
    """Test the Infinium DB2 connection."""
    try:
        conn = get_infinium_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT CURRENT DATE FROM SYSIBM.SYSDUMMY1")
        result = cursor.fetchone()
        conn.close()
        return True, f"Connected. DB2 date: {result[0]}"
    except Exception as e:
        return False, str(e)

