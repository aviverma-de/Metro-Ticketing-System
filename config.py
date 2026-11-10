"""
Configuration Constants for the Metro Ticketing System
-------------------------------------------------------
All other modules must read config.DB_PATH at call time (not copy it at import),
so tests can point it at a temporary file.
"""

NUM_STATIONS = 8
MINUTES_PER_STATION = 2.5
BUFFER_MINUTES = 1.5  # must stay below MINUTES_PER_STATION
TIME_LIMIT = (NUM_STATIONS - 1) * MINUTES_PER_STATION + BUFFER_MINUTES  # 19.0 minutes
OVERTIME_CHARGE = 20

# HMAC secret key (demo value — never use in production)
SECRET_KEY = b"metro-demo-secret-key-2024"

# SQLite database path — tests override this to use a temp file
DB_PATH = "metro.db"
