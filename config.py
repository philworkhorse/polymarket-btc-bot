import os
from dotenv import load_dotenv

load_dotenv()

# Polymarket
CLOB_HOST = "https://clob.polymarket.com"
CHAIN_ID = 137
PRIVATE_KEY = os.getenv("POLYMARKET_PRIVATE_KEY")
FUNDER_ADDRESS = os.getenv("POLYMARKET_FUNDER_ADDRESS")

# Strategy - aggressive for frequent trades
MIN_EDGE = float(os.getenv("MIN_EDGE", "0.01"))  # 1% min edge (was 3%)
BET_SIZE = float(os.getenv("BET_SIZE_USDC", "10"))
MAX_DAILY_LOSS = float(os.getenv("MAX_DAILY_LOSS", "50"))

# Timing
MARKET_DURATION_SEC = 300
MIN_TIME_BEFORE_CLOSE = 30
