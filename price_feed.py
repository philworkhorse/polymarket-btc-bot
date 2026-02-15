"""
Real-time BTC price from Polymarket RTDS (Chainlink oracle data).
This is the EXACT price used for settlement.
"""

import asyncio
import json
import time
from collections import deque
from dataclasses import dataclass
from typing import Optional, Callable
import websockets

@dataclass
class PricePoint:
    price: float
    timestamp: float

class BTCPriceFeed:
    def __init__(self, window_seconds: int = 300):
        self.ws_url = "wss://ws-live-data.polymarket.com"
        self.current_price: Optional[float] = None
        self.last_update: float = 0
        self.price_history: deque = deque(maxlen=1000)
        self.window_seconds = window_seconds
        self._running = False
        self._callbacks: list[Callable] = []
        
    def add_callback(self, callback: Callable):
        self._callbacks.append(callback)
        
    async def _ping_loop(self, ws):
        """Send pings every 5 seconds to keep connection alive"""
        while self._running:
            try:
                await ws.send("ping")
                await asyncio.sleep(5)
            except:
                break
        
    async def start(self):
        self._running = True
        while self._running:
            try:
                async with websockets.connect(self.ws_url) as ws:
                    # Start ping loop
                    ping_task = asyncio.create_task(self._ping_loop(ws))
                    
                    # Subscribe to Chainlink BTC/USD
                    subscribe_msg = {
                        "action": "subscribe",
                        "subscriptions": [
                            {
                                "topic": "crypto_prices_chainlink",
                                "type": "*"
                            }
                        ]
                    }
                    await ws.send(json.dumps(subscribe_msg))
                    print(f"[PriceFeed] Connected to Polymarket RTDS")
                    
                    async for message in ws:
                        if not self._running:
                            break
                        
                        # Skip pong responses and empty messages
                        if not message or message == "pong" or len(message) < 10:
                            continue
                            
                        try:
                            data = json.loads(message)
                            if "payload" in str(data):
                                self._handle_price(data)
                        except json.JSONDecodeError:
                            continue
                            
                    ping_task.cancel()
                    
            except Exception as e:
                print(f"[PriceFeed] Error: {e}, reconnecting...")
                await asyncio.sleep(1)
                
    def _handle_price(self, data: dict):
        payload = data.get("payload", {})
        symbol = payload.get("symbol", "")
        
        # Only process BTC/USD
        if "btc" not in symbol.lower():
            return
            
        price = payload.get("value")
        ts = payload.get("timestamp", 0) / 1000
        
        if not price or price <= 0:
            return
            
        self.current_price = float(price)
        self.last_update = ts if ts > 0 else time.time()
        self.price_history.append(PricePoint(self.current_price, self.last_update))
        
        for cb in self._callbacks:
            try:
                cb(self.current_price, self.last_update)
            except Exception as e:
                print(f"[PriceFeed] Callback error: {e}")
                
    def stop(self):
        self._running = False
        
    def get_momentum(self, lookback_seconds: int = 60) -> Optional[float]:
        if not self.price_history:
            return None
        now = time.time()
        cutoff = now - lookback_seconds
        prices_in_window = [p for p in self.price_history if p.timestamp >= cutoff]
        if len(prices_in_window) < 2:
            return None
        return (prices_in_window[-1].price - prices_in_window[0].price) / prices_in_window[0].price
        
    def get_volatility(self, lookback_seconds: int = 300) -> Optional[float]:
        if not self.price_history:
            return None
        now = time.time()
        cutoff = now - lookback_seconds
        prices = [p.price for p in self.price_history if p.timestamp >= cutoff]
        if len(prices) < 10:
            return None
        returns = [(prices[i] - prices[i-1]) / prices[i-1] for i in range(1, len(prices))]
        mean = sum(returns) / len(returns)
        variance = sum((r - mean) ** 2 for r in returns) / len(returns)
        return variance ** 0.5
        
    def predict_direction(self, horizon_seconds: int = 300) -> tuple[str, float]:
        mom_1m = self.get_momentum(60)
        mom_3m = self.get_momentum(180)
        if mom_1m is None or mom_3m is None:
            return ("UP", 0.5)
        combined_mom = (mom_1m * 0.6) + (mom_3m * 0.4)
        direction = "UP" if combined_mom >= 0 else "DOWN"
        base_conf = min(abs(combined_mom) * 100, 0.3)
        vol = self.get_volatility(300)
        if vol and vol > 0.001:
            base_conf *= 0.7
        return (direction, min(0.5 + base_conf, 0.85))


if __name__ == "__main__":
    async def test():
        feed = BTCPriceFeed()
        task = asyncio.create_task(feed.start())
        print("Connecting to Polymarket RTDS (Chainlink)...")
        for i in range(6):
            await asyncio.sleep(5)
            if feed.current_price:
                mom = feed.get_momentum(60)
                dir, conf = feed.predict_direction(300)
                print(f"[{(i+1)*5}s] Chainlink BTC: ${feed.current_price:,.2f} | Mom: {mom*100 if mom else 0:.3f}% | {dir} ({conf:.0%})")
            else:
                print(f"[{(i+1)*5}s] Waiting...")
        feed.stop()
    asyncio.run(test())
