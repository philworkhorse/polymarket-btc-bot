"""
Polymarket CLOB API wrapper for 5m BTC markets.
"""

import time
from typing import Optional
from dataclasses import dataclass

try:
    from py_clob_client.client import ClobClient
    from py_clob_client.clob_types import MarketOrderArgs, OrderArgs, OrderType, BookParams
    from py_clob_client.order_builder.constants import BUY, SELL
except ImportError:
    print("Install: pip install py-clob-client")
    raise

import config

@dataclass
class Market:
    condition_id: str
    question: str
    token_id_up: str
    token_id_down: str
    start_time: int
    end_time: int
    start_price: Optional[float] = None

@dataclass
class MarketPrices:
    up_bid: float
    up_ask: float
    down_bid: float
    down_ask: float
    up_mid: float
    down_mid: float

class PolymarketClient:
    def __init__(self):
        self.client = ClobClient(
            config.CLOB_HOST,
            key=config.PRIVATE_KEY,
            chain_id=config.CHAIN_ID,
            signature_type=0,  # EOA
            funder=config.FUNDER_ADDRESS
        )
        self._authenticated = False
        
    def authenticate(self):
        """Set up API credentials"""
        if not self._authenticated:
            self.client.set_api_creds(self.client.create_or_derive_api_creds())
            self._authenticated = True
            print("[Polymarket] Authenticated")
            
    def get_btc_5m_markets(self) -> list[dict]:
        """
        Find active 5-minute BTC up/down markets.
        These have slugs like 'btc-updown-5m-{timestamp}'
        """
        # Get all markets
        markets = self.client.get_simplified_markets()
        
        btc_5m = []
        for market in markets.get("data", []):
            # Filter for BTC 5m markets
            slug = market.get("slug", "")
            if "btc-updown-5m" in slug.lower():
                btc_5m.append(market)
                
        return btc_5m
        
    def get_active_market(self) -> Optional[Market]:
        """
        Get the currently active 5m BTC market.
        Returns None if no active market.
        """
        markets = self.get_btc_5m_markets()
        now = int(time.time())
        
        for m in markets:
            # Check if market is active (not resolved)
            if m.get("closed"):
                continue
                
            # Parse timestamps from market data
            # The exact field names may vary - adjust as needed
            end_time = m.get("end_date_iso")
            if end_time:
                # Convert ISO to timestamp
                from datetime import datetime
                end_ts = datetime.fromisoformat(end_time.replace('Z', '+00:00')).timestamp()
                
                if end_ts > now:
                    # Market is still active
                    tokens = m.get("tokens", [])
                    up_token = None
                    down_token = None
                    
                    for t in tokens:
                        outcome = t.get("outcome", "").lower()
                        if "up" in outcome or "yes" in outcome:
                            up_token = t.get("token_id")
                        elif "down" in outcome or "no" in outcome:
                            down_token = t.get("token_id")
                            
                    if up_token and down_token:
                        return Market(
                            condition_id=m.get("condition_id"),
                            question=m.get("question", ""),
                            token_id_up=up_token,
                            token_id_down=down_token,
                            start_time=int(end_ts - 300),  # 5 min before end
                            end_time=int(end_ts)
                        )
        return None
        
    def get_prices(self, market: Market) -> MarketPrices:
        """Get current bid/ask for both outcomes"""
        up_book = self.client.get_order_book(market.token_id_up)
        down_book = self.client.get_order_book(market.token_id_down)
        
        # Extract best bid/ask
        up_bid = float(up_book.bids[0].price) if up_book.bids else 0.0
        up_ask = float(up_book.asks[0].price) if up_book.asks else 1.0
        down_bid = float(down_book.bids[0].price) if down_book.bids else 0.0
        down_ask = float(down_book.asks[0].price) if down_book.asks else 1.0
        
        return MarketPrices(
            up_bid=up_bid,
            up_ask=up_ask,
            down_bid=down_bid,
            down_ask=down_ask,
            up_mid=(up_bid + up_ask) / 2,
            down_mid=(down_bid + down_ask) / 2
        )
        
    def buy_outcome(self, token_id: str, amount_usdc: float) -> dict:
        """
        Buy shares of an outcome.
        amount_usdc: how much USDC to spend
        """
        self.authenticate()
        
        order = MarketOrderArgs(
            token_id=token_id,
            amount=amount_usdc,
            side=BUY,
            order_type=OrderType.FOK  # Fill or kill
        )
        
        signed = self.client.create_market_order(order)
        result = self.client.post_order(signed, OrderType.FOK)
        
        return result
        
    def get_balance(self) -> float:
        """Get USDC balance"""
        # This might need adjustment based on actual API
        try:
            balance = self.client.get_balance()
            return float(balance.get("balance", 0))
        except:
            return 0.0


# Test
if __name__ == "__main__":
    client = PolymarketClient()
    
    print("Fetching BTC 5m markets...")
    markets = client.get_btc_5m_markets()
    print(f"Found {len(markets)} markets")
    
    for m in markets[:3]:
        print(f"  - {m.get('question', 'N/A')[:60]}...")
