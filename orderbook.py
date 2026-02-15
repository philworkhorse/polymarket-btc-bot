"""
Polymarket order book analysis for additional edge signals.
"""

import requests
from typing import Optional
from dataclasses import dataclass

CLOB_HOST = "https://clob.polymarket.com"

@dataclass  
class OrderBookSignal:
    up_bid_depth: float  # Total $ on UP bids
    up_ask_depth: float  # Total $ on UP asks
    down_bid_depth: float
    down_ask_depth: float
    imbalance: float  # Positive = more buying pressure on UP
    spread_up: float
    spread_down: float
    
    @property
    def direction_bias(self) -> tuple[str, float]:
        """Returns direction and strength of order flow bias"""
        if abs(self.imbalance) < 0.1:
            return ("NEUTRAL", 0.0)
        direction = "UP" if self.imbalance > 0 else "DOWN"
        strength = min(abs(self.imbalance), 1.0)
        return (direction, strength)

def get_order_book_signal(token_id_up: str, token_id_down: str) -> Optional[OrderBookSignal]:
    """
    Fetch order books and calculate imbalance signal.
    """
    try:
        # Get UP order book
        resp_up = requests.get(f"{CLOB_HOST}/book", params={"token_id": token_id_up})
        book_up = resp_up.json()
        
        # Get DOWN order book
        resp_down = requests.get(f"{CLOB_HOST}/book", params={"token_id": token_id_down})
        book_down = resp_down.json()
        
        # Calculate depths
        up_bid_depth = sum(float(b.get("size", 0)) * float(b.get("price", 0)) 
                          for b in book_up.get("bids", []))
        up_ask_depth = sum(float(a.get("size", 0)) * float(a.get("price", 0)) 
                          for a in book_up.get("asks", []))
        down_bid_depth = sum(float(b.get("size", 0)) * float(b.get("price", 0)) 
                            for b in book_down.get("bids", []))
        down_ask_depth = sum(float(a.get("size", 0)) * float(a.get("price", 0)) 
                            for a in book_down.get("asks", []))
        
        # Imbalance: (UP buying - DOWN buying) / total
        total = up_bid_depth + down_bid_depth + 0.001
        imbalance = (up_bid_depth - down_bid_depth) / total
        
        # Spreads
        up_bids = book_up.get("bids", [])
        up_asks = book_up.get("asks", [])
        down_bids = book_down.get("bids", [])
        down_asks = book_down.get("asks", [])
        
        spread_up = (float(up_asks[0]["price"]) - float(up_bids[0]["price"])) if up_asks and up_bids else 0.1
        spread_down = (float(down_asks[0]["price"]) - float(down_bids[0]["price"])) if down_asks and down_bids else 0.1
        
        return OrderBookSignal(
            up_bid_depth=up_bid_depth,
            up_ask_depth=up_ask_depth,
            down_bid_depth=down_bid_depth,
            down_ask_depth=down_ask_depth,
            imbalance=imbalance,
            spread_up=spread_up,
            spread_down=spread_down
        )
        
    except Exception as e:
        print(f"[OrderBook] Error: {e}")
        return None
