"""
Enhanced edge detection strategy for 5m BTC markets.
Multiple signals combined for stronger edge.
"""

from dataclasses import dataclass, field
from typing import Optional
import time

@dataclass
class Signal:
    direction: str
    our_probability: float
    market_probability: float
    edge: float
    confidence: str
    components: dict = field(default_factory=dict)
    
    @property
    def should_bet(self) -> bool:
        return self.edge > 0 and self.confidence in ("MEDIUM", "HIGH")

class EnhancedStrategy:
    """
    Multi-factor edge detection:
    1. Multi-timeframe momentum (30s, 1m, 3m)
    2. Momentum acceleration (is momentum increasing?)
    3. Volatility regime (high vol = lower confidence)
    4. Mean reversion after large moves
    5. Price vs VWAP-like measure
    """
    
    def __init__(self, min_edge: float = 0.03):
        self.min_edge = min_edge
        self.recent_predictions: list[dict] = []
        
    def analyze(
        self,
        price_feed,  # BTCPriceFeed instance
        market_up_price: float,
        market_down_price: float,
        time_remaining_sec: int
    ) -> Signal:
        """
        Analyze all factors and combine into single prediction.
        """
        components = {}
        
        # 1. Multi-timeframe momentum
        mom_30s = price_feed.get_momentum(30) or 0
        mom_1m = price_feed.get_momentum(60) or 0
        mom_3m = price_feed.get_momentum(180) or 0
        mom_5m = price_feed.get_momentum(300) or 0
        
        components['mom_30s'] = mom_30s
        components['mom_1m'] = mom_1m
        components['mom_3m'] = mom_3m
        
        # 2. Momentum acceleration (is trend strengthening?)
        mom_accel = mom_30s - mom_1m  # Positive = accelerating in current direction
        components['mom_accel'] = mom_accel
        
        # 3. Volatility
        vol = price_feed.get_volatility(300) or 0.0005
        is_high_vol = vol > 0.001
        components['volatility'] = vol
        components['high_vol'] = is_high_vol
        
        # 4. Mean reversion signal (large recent move = expect pullback)
        mean_reversion_signal = 0
        if abs(mom_30s) > 0.002:  # >0.2% in 30s is big
            mean_reversion_signal = -mom_30s * 0.3  # Expect 30% reversion
        components['mean_reversion'] = mean_reversion_signal
        
        # 5. Trend alignment (all timeframes agree?)
        trend_alignment = 0
        if mom_30s > 0 and mom_1m > 0 and mom_3m > 0:
            trend_alignment = 1  # All bullish
        elif mom_30s < 0 and mom_1m < 0 and mom_3m < 0:
            trend_alignment = -1  # All bearish
        components['trend_alignment'] = trend_alignment
        
        # Combine signals
        # Weighted momentum
        weighted_mom = (
            mom_30s * 0.35 +  # Recent momentum most important
            mom_1m * 0.30 +
            mom_3m * 0.20 +
            mom_5m * 0.15
        )
        
        # Add acceleration bonus
        if mom_accel * weighted_mom > 0:  # Acceleration in same direction
            weighted_mom *= 1.2
            
        # Add mean reversion for extreme moves
        if abs(mom_30s) > 0.003:  # Very large move
            weighted_mom += mean_reversion_signal
            
        # Trend alignment bonus
        if trend_alignment != 0:
            weighted_mom *= 1.15
            
        components['weighted_mom'] = weighted_mom
        
        # Convert to probability
        # Scale: 0.1% momentum ≈ 5% edge
        raw_edge = weighted_mom * 50  # 0.001 -> 0.05
        raw_edge = max(-0.35, min(0.35, raw_edge))  # Cap at ±35%
        
        # Reduce edge in high vol (less predictable)
        if is_high_vol:
            raw_edge *= 0.7
            
        # Reduce edge near expiry (execution risk)
        if time_remaining_sec < 60:
            raw_edge *= 0.5
        elif time_remaining_sec < 120:
            raw_edge *= 0.8
            
        # Direction and probability
        direction = "UP" if weighted_mom >= 0 else "DOWN"
        our_prob = 0.5 + abs(raw_edge)
        
        # Market implied probability
        market_prob = market_up_price if direction == "UP" else market_down_price
        
        # Actual edge vs market
        edge = our_prob - market_prob
        
        # Confidence level
        if edge > 0.12 and time_remaining_sec > 90:
            confidence = "HIGH"
        elif edge > 0.06 and time_remaining_sec > 60:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"
            
        return Signal(
            direction=direction,
            our_probability=our_prob,
            market_probability=market_prob,
            edge=edge,
            confidence=confidence,
            components=components
        )
        
    def size_bet(
        self,
        signal: Signal,
        base_size: float,
        bankroll: float,
        daily_pnl: float,
        max_daily_loss: float
    ) -> float:
        """Kelly-inspired bet sizing"""
        
        if daily_pnl <= -max_daily_loss:
            return 0.0
            
        if signal.confidence == "LOW":
            return 0.0
            
        # Base multiplier
        mult = 1.5 if signal.confidence == "HIGH" else 1.0
        
        # Scale by edge (Kelly-ish)
        # Full Kelly would be: edge / odds, but we use fractional
        kelly_fraction = 0.25  # Use 25% Kelly
        edge_mult = (signal.edge / 0.10) * kelly_fraction
        edge_mult = max(0.5, min(2.0, edge_mult))
        
        # Final size
        size = base_size * mult * edge_mult
        
        # Risk limits
        size = min(size, bankroll * 0.15)  # Max 15% of bankroll
        size = min(size, max_daily_loss + daily_pnl)  # Respect daily limit
        
        return max(0, round(size, 2))
