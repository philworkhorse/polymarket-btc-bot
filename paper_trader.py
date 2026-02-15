#!/usr/bin/env python3
"""
Paper trading bot for Polymarket 5m BTC markets.
Logs all signals and tracks theoretical P&L.
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional, Callable

from price_feed import BTCPriceFeed
from strategy import EnhancedStrategy
import config

@dataclass
class PaperTrade:
    timestamp: str
    direction: str
    entry_price: float
    size: float
    our_prob: float
    market_prob: float
    edge: float
    confidence: str
    time_remaining: int
    components: dict
    # Filled after settlement
    exit_price: Optional[float] = None
    won: Optional[bool] = None
    pnl: Optional[float] = None

class PaperTrader:
    def __init__(self, log_callback: Optional[Callable] = None):
        self.price_feed = BTCPriceFeed()
        self.strategy = EnhancedStrategy(min_edge=config.MIN_EDGE)
        
        # Paper trading state
        self.bankroll = 1000.0  # Start with $1000
        self.daily_pnl = 0.0
        self.total_pnl = 0.0
        self.trades: list[PaperTrade] = []
        self.pending_trade: Optional[PaperTrade] = None
        self.market_start_price: Optional[float] = None
        self.market_end_time: Optional[float] = None
        self.last_signal = None
        
        # Log callback for web UI
        self.log_callback = log_callback
        
        # Files
        self.trades_file = Path("paper_trades.jsonl")
        self.stats_file = Path("paper_stats.json")
        
        # Stats
        self.wins = 0
        self.losses = 0
        
    def log(self, msg: str, level: str = "info"):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {msg}")
        if self.log_callback:
            self.log_callback(msg, level)
        
    async def run(self):
        """Main paper trading loop"""
        self.log("Bot starting up...")
        self.log(f"Config: Min edge {config.MIN_EDGE:.1%}, Base bet ${config.BET_SIZE}")
        
        # Start price feed
        price_task = asyncio.create_task(self.price_feed.start())
        
        # Warm up
        self.log("Warming up price feed (30s)...")
        await asyncio.sleep(30)
        
        self.log("Price feed ready. Starting paper trading loop.", "signal")
        
        try:
            while True:
                await self.trading_cycle()
                await asyncio.sleep(2)
        except KeyboardInterrupt:
            self.log("Shutting down...")
            self.save_stats()
        finally:
            self.price_feed.stop()
            
    async def trading_cycle(self):
        """One cycle of the trading loop"""
        
        if not self.price_feed.current_price:
            return
            
        now = time.time()
        price = self.price_feed.current_price
        
        # Simulate market timing (5-minute intervals)
        current_minute = int(now // 60)
        market_minute = (current_minute // 5) * 5
        market_start = market_minute * 60
        market_end = market_start + 300
        time_remaining = int(market_end - now)
        
        # New market started?
        if self.market_end_time != market_end:
            # Settle previous trade if exists
            if self.pending_trade and self.market_start_price:
                await self.settle_trade()
            
            # New market
            self.market_end_time = market_end
            self.market_start_price = price
            self.pending_trade = None
            self.log(f"New 5m market opened | Reference: ${price:,.2f} | {time_remaining}s remaining", "signal")
            
        # Don't trade in last 30 seconds
        if time_remaining < 30:
            return
            
        # Already have a trade for this market
        if self.pending_trade:
            return
            
        # Simulate market prices (in reality, fetch from Polymarket)
        market_up = 0.51
        market_down = 0.49
        
        # Get signal
        signal = self.strategy.analyze(
            self.price_feed,
            market_up,
            market_down,
            time_remaining
        )
        
        # Store for display
        self.last_signal = signal
        
        # Build thought process log
        components = signal.components
        thought = f"Analyzing: "
        thought += f"Mom(30s)={components['mom_30s']*100:+.3f}% "
        thought += f"Mom(1m)={components['mom_1m']*100:+.3f}% "
        thought += f"Accel={components['mom_accel']*100:+.4f}% "
        
        if components.get('trend_alignment') == 1:
            thought += "| Trend: ALIGNED UP "
        elif components.get('trend_alignment') == -1:
            thought += "| Trend: ALIGNED DOWN "
        else:
            thought += "| Trend: MIXED "
            
        if components.get('high_vol'):
            thought += "| HIGH VOL "
            
        self.log(thought)
        
        # Log decision
        decision = f"Signal: {signal.direction} | Edge: {signal.edge:.1%} | Conf: {signal.confidence}"
        if signal.should_bet and signal.edge >= config.MIN_EDGE:
            decision += " → TRADEABLE"
            self.log(decision, "signal")
        else:
            if signal.edge < config.MIN_EDGE:
                decision += f" → PASS (edge < {config.MIN_EDGE:.1%})"
            elif signal.confidence == "LOW":
                decision += " → PASS (low confidence)"
            else:
                decision += " → PASS"
            self.log(decision)
            return
            
        # Calculate size
        size = self.strategy.size_bet(
            signal,
            config.BET_SIZE,
            self.bankroll,
            self.daily_pnl,
            config.MAX_DAILY_LOSS
        )
        
        if size < 1:
            self.log(f"Bet size too small (${size:.2f}), skipping")
            return
        
        # Log sizing rationale
        kelly_mult = signal.edge / 0.10 * 0.25
        self.log(f"Sizing: Base ${config.BET_SIZE} × {signal.confidence} × Kelly({kelly_mult:.2f}) = ${size:.2f}")
            
        # Place paper trade
        self.pending_trade = PaperTrade(
            timestamp=datetime.now().isoformat(),
            direction=signal.direction,
            entry_price=price,
            size=size,
            our_prob=signal.our_probability,
            market_prob=signal.market_probability,
            edge=signal.edge,
            confidence=signal.confidence,
            time_remaining=time_remaining,
            components=signal.components
        )
        
        self.log(f"TRADE: {signal.direction} ${size:.2f} @ ${price:,.2f}", "trade")
        
    async def settle_trade(self):
        """Settle pending trade against current price"""
        if not self.pending_trade or not self.market_start_price:
            return
            
        trade = self.pending_trade
        exit_price = self.price_feed.current_price
        
        # Determine winner
        price_went_up = exit_price >= self.market_start_price
        price_change = (exit_price - self.market_start_price) / self.market_start_price * 100
        
        if trade.direction == "UP":
            won = price_went_up
        else:
            won = not price_went_up
        
        self.log(f"Market closed: ${self.market_start_price:,.2f} → ${exit_price:,.2f} ({price_change:+.2f}%)")
            
        # Calculate P&L
        if won:
            pnl = trade.size * 0.95  # 95% of bet (accounting for edge)
        else:
            pnl = -trade.size
            
        trade.exit_price = exit_price
        trade.won = won
        trade.pnl = pnl
        
        # Update stats
        self.daily_pnl += pnl
        self.total_pnl += pnl
        self.bankroll += pnl
        
        if won:
            self.wins += 1
            self.log(f"WIN: {trade.direction} | P&L: ${pnl:+.2f} | Record: {self.wins}W-{self.losses}L", "win")
        else:
            self.losses += 1
            self.log(f"LOSS: {trade.direction} | P&L: ${pnl:+.2f} | Record: {self.wins}W-{self.losses}L", "loss")
        
        self.log(f"Bankroll: ${self.bankroll:.2f} | Total P&L: ${self.total_pnl:+.2f}")
        
        self.trades.append(trade)
        
        # Save trade
        with open(self.trades_file, "a") as f:
            f.write(json.dumps(asdict(trade)) + "\n")
            
        self.pending_trade = None
        
    def save_stats(self):
        """Save final stats"""
        stats = {
            "timestamp": datetime.now().isoformat(),
            "bankroll": self.bankroll,
            "total_pnl": self.total_pnl,
            "daily_pnl": self.daily_pnl,
            "wins": self.wins,
            "losses": self.losses,
            "win_rate": self.wins / (self.wins + self.losses) if (self.wins + self.losses) > 0 else 0,
            "total_trades": len(self.trades)
        }
        
        with open(self.stats_file, "w") as f:
            json.dump(stats, f, indent=2)


async def main():
    trader = PaperTrader()
    await trader.run()


if __name__ == "__main__":
    asyncio.run(main())
