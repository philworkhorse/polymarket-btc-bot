#!/usr/bin/env python3
"""
Polymarket 5m BTC Trading Bot

Main loop:
1. Connect to Binance for real-time BTC prices
2. Find active Polymarket 5m BTC market
3. Analyze edge using momentum strategy
4. Place bets when edge exceeds threshold
5. Track P&L
"""

import asyncio
import time
import json
from datetime import datetime
from pathlib import Path

import config
from price_feed import BTCPriceFeed
from polymarket import PolymarketClient, Market, MarketPrices
from strategy import Strategy, Signal

class Bot:
    def __init__(self):
        self.price_feed = BTCPriceFeed()
        self.polymarket = PolymarketClient()
        self.strategy = Strategy(min_edge=config.MIN_EDGE)
        
        # State
        self.daily_pnl = 0.0
        self.total_bets = 0
        self.wins = 0
        self.losses = 0
        self.current_positions: list[dict] = []
        
        # Logging
        self.log_file = Path("bot_log.jsonl")
        
    def log(self, event: str, data: dict = None):
        """Log event to file and console"""
        entry = {
            "timestamp": datetime.now().isoformat(),
            "event": event,
            "data": data or {}
        }
        print(f"[{entry['timestamp'][:19]}] {event}: {json.dumps(data or {})}")
        
        with open(self.log_file, "a") as f:
            f.write(json.dumps(entry) + "\n")
            
    async def run(self):
        """Main bot loop"""
        self.log("BOT_START", {
            "min_edge": config.MIN_EDGE,
            "bet_size": config.BET_SIZE,
            "max_daily_loss": config.MAX_DAILY_LOSS
        })
        
        # Start price feed in background
        price_task = asyncio.create_task(self.price_feed.start())
        
        # Wait for price feed to warm up
        self.log("WARMING_UP", {"seconds": 10})
        await asyncio.sleep(10)
        
        try:
            while True:
                await self.run_cycle()
                await asyncio.sleep(5)  # Check every 5 seconds
                
        except KeyboardInterrupt:
            self.log("BOT_STOP", {"reason": "keyboard"})
        except Exception as e:
            self.log("BOT_ERROR", {"error": str(e)})
            raise
        finally:
            self.price_feed.stop()
            
    async def run_cycle(self):
        """Single cycle: check for opportunity and act"""
        
        # Check daily loss limit
        if self.daily_pnl <= -config.MAX_DAILY_LOSS:
            self.log("DAILY_LIMIT_HIT", {"pnl": self.daily_pnl})
            await asyncio.sleep(3600)  # Wait an hour
            return
            
        # Find active market
        market = self.polymarket.get_active_market()
        if not market:
            # No active market, wait for next one
            return
            
        # Get time remaining
        now = int(time.time())
        time_remaining = market.end_time - now
        
        if time_remaining < config.MIN_TIME_BEFORE_CLOSE:
            # Too close to expiry
            return
            
        # Get market prices
        try:
            prices = self.polymarket.get_prices(market)
        except Exception as e:
            self.log("PRICE_ERROR", {"error": str(e)})
            return
            
        # Get our prediction
        direction, confidence = self.price_feed.predict_direction(
            horizon_seconds=time_remaining
        )
        
        # Analyze edge
        signal = self.strategy.analyze(
            predicted_direction=direction,
            predicted_confidence=confidence,
            market_up_price=prices.up_mid,
            market_down_price=prices.down_mid,
            time_remaining_sec=time_remaining
        )
        
        self.log("SIGNAL", {
            "direction": signal.direction,
            "our_prob": f"{signal.our_probability:.1%}",
            "market_prob": f"{signal.market_probability:.1%}",
            "edge": f"{signal.edge:.1%}",
            "confidence": signal.confidence,
            "time_remaining": time_remaining
        })
        
        # Should we bet?
        if not signal.should_bet:
            return
            
        if signal.edge < config.MIN_EDGE:
            return
            
        # Calculate bet size
        bankroll = self.polymarket.get_balance()
        bet_size = self.strategy.size_bet(
            edge=signal.edge,
            confidence=signal.confidence,
            base_size=config.BET_SIZE,
            bankroll=bankroll,
            daily_pnl=self.daily_pnl,
            max_daily_loss=config.MAX_DAILY_LOSS
        )
        
        if bet_size < 1:  # Minimum $1 bet
            return
            
        # Place bet
        token_id = market.token_id_up if signal.direction == "UP" else market.token_id_down
        
        self.log("PLACING_BET", {
            "direction": signal.direction,
            "size": bet_size,
            "edge": f"{signal.edge:.1%}",
            "market_end": market.end_time
        })
        
        try:
            result = self.polymarket.buy_outcome(token_id, bet_size)
            self.log("BET_PLACED", {"result": result})
            
            self.current_positions.append({
                "market": market,
                "direction": signal.direction,
                "size": bet_size,
                "entry_price": prices.up_mid if signal.direction == "UP" else prices.down_mid,
                "placed_at": now
            })
            
            self.total_bets += 1
            
        except Exception as e:
            self.log("BET_FAILED", {"error": str(e)})
            
    def record_outcome(self, won: bool, pnl: float):
        """Record bet outcome"""
        self.daily_pnl += pnl
        if won:
            self.wins += 1
        else:
            self.losses += 1
            
        self.log("OUTCOME", {
            "won": won,
            "pnl": pnl,
            "daily_pnl": self.daily_pnl,
            "record": f"{self.wins}W-{self.losses}L"
        })


async def main():
    print("""
    ╔═══════════════════════════════════════╗
    ║  Polymarket 5m BTC Bot                ║
    ║  ──────────────────────────────────── ║
    ║  Strategy: Momentum + Edge Detection  ║
    ║  Market: BTC 5-minute Up/Down         ║
    ╚═══════════════════════════════════════╝
    """)
    
    if not config.PRIVATE_KEY:
        print("ERROR: Set POLYMARKET_PRIVATE_KEY in .env")
        return
        
    bot = Bot()
    await bot.run()


if __name__ == "__main__":
    asyncio.run(main())
