---
title: Polymarket BTC 5m Paper Trader
emoji: 📈
colorFrom: green
colorTo: blue
sdk: docker
pinned: false
---

# Polymarket 5m BTC Paper Trader

Paper trading bot for Polymarket's 5-minute BTC up/down prediction markets.

Uses Chainlink oracle prices via Polymarket RTDS for accurate settlement simulation.

## Features
- Real-time Chainlink BTC/USD prices
- Multi-factor edge detection (momentum, volatility, trend alignment)
- Paper trading with P&L tracking
- Web dashboard

## Strategy
- Multi-timeframe momentum (30s/1m/3m/5m)
- Momentum acceleration detection
- Mean reversion on large moves
- Volatility regime adjustment
