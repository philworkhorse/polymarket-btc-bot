"""
Enhanced edge detection strategy for 5m BTC markets.
Multiple signals combined for stronger edge.
Tuned for frequent trading.
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
        # Allow all confidence levels - sizing handles risk
        return self.edge > 0

class EnhancedStrategy:
    """
    Multi-factor edge detection:
    1. Multi-timeframe momentum (30s, 1m, 3m)
    2. Momentum acceleration (is momentum increasing?)
    3. Volatility regime (high vol = lower confidence)
    4. Mean reversion after large moves
    5. Price vs VWAP-like measure
    """
    
    def __init__(self, min_edge: float = 0.01):
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
        is_high_vol = vol > 0.0015  # Raised threshold
        components['volatility'] = vol
        components['high_vol'] = is_high_vol
        
        # 4. Mean reversion signal (large recent move = expect pullback)
        mean_reversion_signal = 0
        if abs(mom_30s) > 0.003:  # >0.3% in 30s is big
            mean_reversion_signal = -mom_30s * 0.25
        components['mean_reversion'] = mean_reversion_signal
        
        # 5. Trend alignment (all timeframes agree?)
        trend_alignment = 0
        if mom_30s > 0 and mom_1m > 0 and mom_3m > 0:
            trend_alignment = 1  # All bullish
        elif mom_30s < 0 and mom_1m < 0 and mom_3m < 0:
            trend_alignment = -1  # All bearish
        components['trend_alignment'] = trend_alignment
        
        # Combine signals - weighted momentum
        weighted_mom = (
            mom_30s * 0.40 +  # Recent momentum most important
            mom_1m * 0.30 +
            mom_3m * 0.20 +
            mom_5m * 0.10
        )
        
        # Add acceleration bonus
        if mom_accel * weighted_mom > 0:  # Acceleration in same direction
            weighted_mom *= 1.3
            
        # Add mean reversion for extreme moves
        if abs(mom_30s) > 0.004:  # Very large move
            weighted_mom += mean_reversion_signal
            
        # Trend alignment bonus
        if trend_alignment != 0:
            weighted_mom *= 1.2
            
        components['weighted_mom'] = weighted_mom
        
        # Convert to probability - more aggressive scaling
        # Scale: 0.05% momentum = 5% edge
        raw_edge = weighted_mom * 100  # More sensitive (was 50)
        raw_edge = max(-0.40, min(0.40, raw_edge))  # Cap at +/-40%
        
        # Reduce edge in high vol (less predictable)
        if is_high_vol:
            raw_edge *= 0.8  # Less penalty (was 0.7)
            
        # Reduce edge near expiry (execution risk)
        if time_remaining_sec < 45:
            raw_edge *= 0.6
        elif time_remaining_sec < 90:
            raw_edge *= 0.85
            
        # Direction and probability
        direction = "UP" if weighted_mom >= 0 else "DOWN"
        our_prob = 0.5 + abs(raw_edge)
        
        # Market implied probability
        market_prob = market_up_price if direction == "UP" else market_down_price
        
        # Actual edge vs market
        edge = our_prob - market_prob
        
        # Confidence level - lowered thresholds
        if edge > 0.08 and time_remaining_sec > 60:
            confidence = "HIGH"
        elif edge > 0.03 and time_remaining_sec > 45:
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
        """Kelly-inspired bet sizing with confidence tiers"""
        
        if daily_pnl <= -max_daily_loss:
            return 0.0
            
        # Base multiplier by confidence
        if signal.confidence == "HIGH":
            mult = 1.5
        elif signal.confidence == "MEDIUM":
            mult = 1.0
        else:  # LOW - still trade but smaller
            mult = 0.5
        
        # Scale by edge (Kelly-ish)
        kelly_fraction = 0.3  # Use 30% Kelly (was 25%)
        edge_mult = (signal.edge / 0.08) * kelly_fraction
        edge_mult = max(0.4, min(2.5, edge_mult))
        
        # Final size
        size = base_size * mult * edge_mult
        
        # Risk limits
        size = min(size, bankroll * 0.20)  # Max 20% of bankroll (was 15%)
        size = min(size, max_daily_loss + daily_pnl)  # Respect daily limit
        
        return max(0, round(size, 2))
