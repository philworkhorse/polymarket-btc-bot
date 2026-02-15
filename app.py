#!/usr/bin/env python3
"""
Polymarket 5m BTC Paper Trading Bot - Web Dashboard
Runs paper trading in background, shows stats via web.
"""

import asyncio
import json
import threading
import time
from datetime import datetime
from collections import deque
from pathlib import Path
from flask import Flask, jsonify, render_template_string

from paper_trader import PaperTrader

app = Flask(__name__)
trader = None
trader_thread = None

# Activity log for thought process
activity_log = deque(maxlen=100)

def log_activity(msg: str, level: str = "info"):
    """Add to activity log"""
    activity_log.append({
        "time": datetime.now().strftime("%H:%M:%S"),
        "msg": msg,
        "level": level
    })

DASHBOARD_HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Polymarket BTC</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=DM+Sans:wght@400;500;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        :root {
            --bg: #09090b;
            --surface: #18181b;
            --surface-2: #27272a;
            --border: #3f3f46;
            --text: #fafafa;
            --text-dim: #a1a1aa;
            --accent: #f97316;
            --accent-dim: rgba(249, 115, 22, 0.15);
            --up: #22c55e;
            --up-dim: rgba(34, 197, 94, 0.15);
            --down: #ef4444;
            --down-dim: rgba(239, 68, 68, 0.15);
            --pending: #eab308;
        }
        
        body {
            font-family: 'DM Sans', system-ui, sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.5;
            min-height: 100vh;
        }
        
        .mono { font-family: 'Space Mono', monospace; }
        
        .container {
            max-width: 1100px;
            margin: 0 auto;
            padding: 32px 24px;
        }
        
        header {
            display: flex;
            justify-content: space-between;
            align-items: baseline;
            margin-bottom: 40px;
        }
        
        .logo {
            font-family: 'Space Mono', monospace;
            font-size: 13px;
            font-weight: 700;
            letter-spacing: 0.05em;
            color: var(--accent);
            text-transform: uppercase;
        }
        
        .status {
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            padding: 6px 12px;
            border-radius: 4px;
        }
        
        .status.scanning { background: var(--surface-2); color: var(--text-dim); }
        .status.open { background: var(--accent-dim); color: var(--accent); }
        
        .hero {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr 1fr;
            gap: 1px;
            background: var(--border);
            border: 1px solid var(--border);
            margin-bottom: 32px;
        }
        
        .hero-stat {
            background: var(--surface);
            padding: 24px;
        }
        
        .hero-stat .label {
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--text-dim);
            margin-bottom: 8px;
        }
        
        .hero-stat .value {
            font-family: 'Space Mono', monospace;
            font-size: 28px;
            font-weight: 700;
        }
        
        .hero-stat .value.positive { color: var(--up); }
        .hero-stat .value.negative { color: var(--down); }
        
        @media (max-width: 800px) {
            .hero { grid-template-columns: 1fr 1fr; }
        }
        
        /* Live Chart */
        .chart-panel {
            background: var(--surface);
            border: 1px solid var(--border);
            margin-bottom: 24px;
            position: relative;
        }
        
        .chart-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 20px;
            border-bottom: 1px solid var(--border);
        }
        
        .chart-title {
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--text-dim);
        }
        
        .chart-price {
            font-family: 'Space Mono', monospace;
            font-size: 24px;
            font-weight: 700;
        }
        
        .chart-change {
            font-family: 'Space Mono', monospace;
            font-size: 13px;
            margin-left: 12px;
        }
        
        .chart-change.up { color: var(--up); }
        .chart-change.down { color: var(--down); }
        
        .chart-container {
            position: relative;
            height: 200px;
            padding: 20px;
        }
        
        #priceChart {
            width: 100%;
            height: 100%;
        }
        
        .chart-overlay {
            position: absolute;
            top: 20px;
            right: 20px;
            display: flex;
            gap: 16px;
            font-size: 11px;
            color: var(--text-dim);
        }
        
        .chart-overlay span {
            font-family: 'Space Mono', monospace;
        }
        
        /* Prediction Panel */
        .prediction-row {
            display: grid;
            grid-template-columns: 1fr 1fr 1fr;
            gap: 1px;
            background: var(--border);
            border: 1px solid var(--border);
            margin-bottom: 24px;
        }
        
        @media (max-width: 800px) {
            .prediction-row { grid-template-columns: 1fr; }
        }
        
        .pred-cell {
            background: var(--surface);
            padding: 24px;
            text-align: center;
        }
        
        .pred-cell .label {
            font-size: 10px;
            font-weight: 600;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--text-dim);
            margin-bottom: 12px;
        }
        
        /* Direction Arrow */
        .direction-display {
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 8px;
        }
        
        .direction-arrow {
            width: 80px;
            height: 80px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .direction-arrow.up {
            background: var(--up-dim);
            border: 2px solid var(--up);
        }
        
        .direction-arrow.down {
            background: var(--down-dim);
            border: 2px solid var(--down);
        }
        
        .direction-arrow.neutral {
            background: var(--surface-2);
            border: 2px solid var(--border);
        }
        
        .direction-arrow svg {
            width: 32px;
            height: 32px;
        }
        
        .direction-arrow.up svg { color: var(--up); }
        .direction-arrow.down svg { color: var(--down); }
        .direction-arrow.neutral svg { color: var(--text-dim); }
        
        .direction-label {
            font-family: 'Space Mono', monospace;
            font-size: 18px;
            font-weight: 700;
        }
        
        .direction-label.up { color: var(--up); }
        .direction-label.down { color: var(--down); }
        .direction-label.neutral { color: var(--text-dim); }
        
        /* Probability */
        .prob-value {
            font-family: 'Space Mono', monospace;
            font-size: 36px;
            font-weight: 700;
        }
        
        .prob-value.up { color: var(--up); }
        .prob-value.down { color: var(--down); }
        
        .prob-bar {
            display: flex;
            gap: 3px;
            margin-top: 12px;
            justify-content: center;
        }
        
        .prob-seg {
            width: 16px;
            height: 6px;
            background: var(--surface-2);
            border-radius: 1px;
        }
        
        .prob-seg.filled.up { background: var(--up); }
        .prob-seg.filled.down { background: var(--down); }
        
        /* Confidence */
        .conf-gauge {
            display: flex;
            justify-content: center;
            gap: 6px;
            margin-bottom: 8px;
        }
        
        .conf-bar {
            width: 24px;
            height: 36px;
            background: var(--surface-2);
            border-radius: 3px;
        }
        
        .conf-bar.low { border-bottom: 2px solid var(--pending); }
        .conf-bar.med { border-bottom: 2px solid var(--accent); }
        .conf-bar.high { border-bottom: 2px solid var(--up); }
        
        .conf-bar.active.low { background: rgba(234, 179, 8, 0.25); }
        .conf-bar.active.med { background: rgba(249, 115, 22, 0.25); }
        .conf-bar.active.high { background: rgba(34, 197, 94, 0.25); }
        
        .conf-label {
            font-family: 'Space Mono', monospace;
            font-size: 16px;
            font-weight: 700;
        }
        
        .conf-label.low { color: var(--pending); }
        .conf-label.med { color: var(--accent); }
        .conf-label.high { color: var(--up); }
        
        .edge-val {
            font-family: 'Space Mono', monospace;
            font-size: 12px;
            color: var(--text-dim);
            margin-top: 4px;
        }
        
        /* Panels */
        .panels {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 24px;
            margin-bottom: 24px;
        }
        
        @media (max-width: 800px) {
            .panels { grid-template-columns: 1fr; }
        }
        
        .panel {
            background: var(--surface);
            border: 1px solid var(--border);
        }
        
        .panel-head {
            padding: 16px 20px;
            border-bottom: 1px solid var(--border);
            font-size: 11px;
            font-weight: 600;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--text-dim);
        }
        
        .panel-body {
            padding: 20px;
        }
        
        /* Components */
        .components {
            display: grid;
            grid-template-columns: repeat(3, 1fr);
            gap: 12px;
        }
        
        @media (max-width: 600px) {
            .components { grid-template-columns: 1fr 1fr; }
        }
        
        .comp {
            padding: 10px;
            background: var(--bg);
            border: 1px solid var(--border);
        }
        
        .comp .label {
            font-size: 9px;
            font-weight: 600;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            color: var(--text-dim);
            margin-bottom: 4px;
        }
        
        .comp .value {
            font-family: 'Space Mono', monospace;
            font-size: 13px;
            font-weight: 500;
        }
        
        .comp .value.up { color: var(--up); }
        .comp .value.down { color: var(--down); }
        
        /* Log */
        .log-scroll {
            max-height: 240px;
            overflow-y: auto;
            font-family: 'Space Mono', monospace;
            font-size: 11px;
            line-height: 1.7;
        }
        
        .log-entry {
            padding: 5px 0;
            border-bottom: 1px solid var(--border);
            display: flex;
            gap: 10px;
        }
        
        .log-entry:last-child { border-bottom: none; }
        .log-entry .time { color: var(--text-dim); flex-shrink: 0; }
        .log-entry .msg { word-break: break-word; }
        .log-entry.signal { color: var(--accent); }
        .log-entry.trade { color: var(--pending); }
        .log-entry.win { color: var(--up); }
        .log-entry.loss { color: var(--down); }
        
        /* Trades */
        .trades-list {
            max-height: 240px;
            overflow-y: auto;
        }
        
        .trade-row {
            display: grid;
            grid-template-columns: 20px 1fr auto;
            gap: 10px;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid var(--border);
            font-size: 12px;
        }
        
        .trade-row:last-child { border-bottom: none; }
        
        .trade-row.pending-row {
            background: var(--accent-dim);
            margin: 0 -20px;
            padding: 10px 20px;
            border-left: 3px solid var(--accent);
        }
        
        .trade-icon {
            width: 18px;
            height: 18px;
            border-radius: 50%;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 9px;
            font-weight: 700;
        }
        
        .trade-icon.win { background: var(--up-dim); color: var(--up); }
        .trade-icon.loss { background: var(--down-dim); color: var(--down); }
        .trade-icon.open { background: var(--accent-dim); color: var(--accent); }
        
        .trade-info .dir {
            font-weight: 600;
            font-family: 'Space Mono', monospace;
        }
        
        .trade-info .meta {
            font-size: 10px;
            color: var(--text-dim);
            margin-top: 2px;
        }
        
        .trade-pnl {
            font-family: 'Space Mono', monospace;
            font-weight: 600;
        }
        
        .trade-pnl.positive { color: var(--up); }
        .trade-pnl.negative { color: var(--down); }
        .trade-pnl.pending { color: var(--accent); }
        
        .empty {
            padding: 32px 20px;
            text-align: center;
            color: var(--text-dim);
            font-size: 12px;
        }
        
        footer {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding-top: 24px;
            border-top: 1px solid var(--border);
            font-size: 11px;
            color: var(--text-dim);
        }
        
        .pulse {
            width: 6px;
            height: 6px;
            background: var(--up);
            border-radius: 50%;
            display: inline-block;
            margin-right: 8px;
            animation: pulse 2s infinite;
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <div class="logo">Polymarket BTC / 5m</div>
            <span class="status {{ 'open' if pending else 'scanning' }}">
                {{ "Position Open" if pending else "Scanning" }}
            </span>
        </header>
        
        <div class="hero">
            <div class="hero-stat">
                <div class="label">Bankroll</div>
                <div class="value mono">${{ "%.2f"|format(bankroll) }}</div>
            </div>
            <div class="hero-stat">
                <div class="label">Total P/L</div>
                <div class="value {{ 'positive' if total_pnl >= 0 else 'negative' }}">
                    ${{ "%+.2f"|format(total_pnl) }}
                </div>
            </div>
            <div class="hero-stat">
                <div class="label">Record</div>
                <div class="value mono">{{ wins }}-{{ losses }}</div>
            </div>
            <div class="hero-stat">
                <div class="label">Win Rate</div>
                <div class="value mono">{{ "%.0f"|format(win_rate * 100) }}%</div>
            </div>
        </div>
        
        <!-- Live Price Chart -->
        <div class="chart-panel">
            <div class="chart-header">
                <span class="chart-title">BTC/USD Live</span>
                <div>
                    <span class="chart-price" id="livePrice">${{ "{:,.2f}".format(price) if price else "---" }}</span>
                    <span class="chart-change {{ 'up' if momentum_1m and momentum_1m >= 0 else 'down' }}" id="liveChange">
                        {% if momentum_1m %}{{ "%+.3f"|format(momentum_1m * 100) }}%{% endif %}
                    </span>
                </div>
            </div>
            <div class="chart-container">
                <canvas id="priceChart"></canvas>
            </div>
            <div class="chart-overlay">
                <span>5m window</span>
                <span id="chartRange"></span>
            </div>
        </div>
        
        <!-- Prediction Row -->
        <div class="prediction-row">
            <div class="pred-cell">
                <div class="label">Prediction</div>
                <div class="direction-display">
                    {% if last_signal %}
                    <div class="direction-arrow {{ last_signal.direction|lower }}">
                        {% if last_signal.direction == "UP" %}
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M12 19V5M5 12l7-7 7 7"/>
                        </svg>
                        {% else %}
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M12 5v14M5 12l7 7 7-7"/>
                        </svg>
                        {% endif %}
                    </div>
                    <div class="direction-label {{ last_signal.direction|lower }}">{{ last_signal.direction }}</div>
                    {% else %}
                    <div class="direction-arrow neutral">
                        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                            <circle cx="12" cy="12" r="1"/><circle cx="19" cy="12" r="1"/><circle cx="5" cy="12" r="1"/>
                        </svg>
                    </div>
                    <div class="direction-label neutral">WAIT</div>
                    {% endif %}
                </div>
            </div>
            
            <div class="pred-cell">
                <div class="label">Probability</div>
                {% if last_signal %}
                <div class="prob-value {{ last_signal.direction|lower }}">{{ "%.0f"|format(last_signal.our_probability * 100) }}%</div>
                <div class="prob-bar">
                    {% set prob_pct = (last_signal.our_probability * 100)|int %}
                    {% for i in range(10) %}
                    <div class="prob-seg {{ 'filled ' + last_signal.direction|lower if (i + 1) * 10 <= prob_pct else '' }}"></div>
                    {% endfor %}
                </div>
                {% else %}
                <div class="prob-value" style="color: var(--text-dim);">--</div>
                {% endif %}
            </div>
            
            <div class="pred-cell">
                <div class="label">Confidence</div>
                {% if last_signal %}
                <div class="conf-gauge">
                    <div class="conf-bar low {{ 'active' if last_signal.confidence in ['LOW', 'MEDIUM', 'HIGH'] else '' }}"></div>
                    <div class="conf-bar med {{ 'active' if last_signal.confidence in ['MEDIUM', 'HIGH'] else '' }}"></div>
                    <div class="conf-bar high {{ 'active' if last_signal.confidence == 'HIGH' else '' }}"></div>
                </div>
                <div class="conf-label {{ last_signal.confidence|lower }}">{{ last_signal.confidence }}</div>
                <div class="edge-val">Edge: {{ "%.1f"|format(last_signal.edge * 100) }}%</div>
                {% else %}
                <div class="conf-gauge">
                    <div class="conf-bar low"></div>
                    <div class="conf-bar med"></div>
                    <div class="conf-bar high"></div>
                </div>
                <div class="conf-label" style="color: var(--text-dim);">--</div>
                {% endif %}
            </div>
        </div>
        
        {% if components %}
        <div class="panel" style="margin-bottom: 24px;">
            <div class="panel-head">Strategy Components</div>
            <div class="panel-body">
                <div class="components">
                    <div class="comp">
                        <div class="label">Mom 30s</div>
                        <div class="value {{ 'up' if components.mom_30s >= 0 else 'down' }}">{{ "%+.4f"|format(components.mom_30s) }}</div>
                    </div>
                    <div class="comp">
                        <div class="label">Mom 1m</div>
                        <div class="value {{ 'up' if components.mom_1m >= 0 else 'down' }}">{{ "%+.4f"|format(components.mom_1m) }}</div>
                    </div>
                    <div class="comp">
                        <div class="label">Mom 3m</div>
                        <div class="value {{ 'up' if components.mom_3m >= 0 else 'down' }}">{{ "%+.4f"|format(components.mom_3m) }}</div>
                    </div>
                    <div class="comp">
                        <div class="label">Accel</div>
                        <div class="value {{ 'up' if components.mom_accel >= 0 else 'down' }}">{{ "%+.4f"|format(components.mom_accel) }}</div>
                    </div>
                    <div class="comp">
                        <div class="label">Volatility</div>
                        <div class="value">{{ "%.4f"|format(components.volatility) }}</div>
                    </div>
                    <div class="comp">
                        <div class="label">Trend</div>
                        <div class="value {{ 'up' if components.trend_alignment == 1 else 'down' if components.trend_alignment == -1 else '' }}">
                            {% if components.trend_alignment == 1 %}UP{% elif components.trend_alignment == -1 %}DOWN{% else %}MIX{% endif %}
                        </div>
                    </div>
                </div>
            </div>
        </div>
        {% endif %}
        
        <div class="panels">
            <div class="panel">
                <div class="panel-head">Activity Log</div>
                <div class="panel-body">
                    <div class="log-scroll">
                        {% for log in logs|reverse %}
                        <div class="log-entry {{ log.level }}">
                            <span class="time">{{ log.time }}</span>
                            <span class="msg">{{ log.msg }}</span>
                        </div>
                        {% else %}
                        <div class="empty">Waiting for activity</div>
                        {% endfor %}
                    </div>
                </div>
            </div>
            
            <div class="panel">
                <div class="panel-head">Recent Trades</div>
                <div class="panel-body">
                    <div class="trades-list">
                        {% if pending %}
                        <div class="trade-row pending-row">
                            <div class="trade-icon open">O</div>
                            <div class="trade-info">
                                <div class="dir">{{ pending.direction }} @ ${{ "{:,.2f}".format(pending.entry_price) }}</div>
                                <div class="meta">Edge {{ "%.1f"|format(pending.edge * 100) }}%</div>
                            </div>
                            <div class="trade-pnl pending">OPEN</div>
                        </div>
                        {% endif %}
                        {% for trade in trades[-8:]|reverse %}
                        <div class="trade-row">
                            <div class="trade-icon {{ 'win' if trade.won else 'loss' }}">{{ "W" if trade.won else "L" }}</div>
                            <div class="trade-info">
                                <div class="dir">{{ trade.direction }} @ ${{ "{:,.2f}".format(trade.entry_price) }}</div>
                                <div class="meta">${{ "%+.2f"|format(trade.pnl) if trade.pnl else "---" }}</div>
                            </div>
                            <div class="trade-pnl {{ 'positive' if trade.pnl and trade.pnl >= 0 else 'negative' }}">
                                {{ "%.1f"|format(trade.edge * 100) }}%
                            </div>
                        </div>
                        {% else %}
                        {% if not pending %}
                        <div class="empty">No trades yet</div>
                        {% endif %}
                        {% endfor %}
                    </div>
                </div>
            </div>
        </div>
        
        <footer>
            <span>Started {{ start_time }}</span>
            <span><span class="pulse"></span>Live</span>
        </footer>
    </div>
    
    <script>
        const canvas = document.getElementById('priceChart');
        const ctx = canvas.getContext('2d');
        let priceData = {{ price_history | tojson }};
        
        function resizeCanvas() {
            const rect = canvas.parentElement.getBoundingClientRect();
            canvas.width = rect.width - 40;
            canvas.height = rect.height - 40;
        }
        
        function drawChart() {
            if (!priceData || priceData.length < 2) {
                ctx.fillStyle = '#a1a1aa';
                ctx.font = '12px Space Mono';
                ctx.textAlign = 'center';
                ctx.fillText('Collecting price data...', canvas.width / 2, canvas.height / 2);
                return;
            }
            
            const w = canvas.width;
            const h = canvas.height;
            const padding = 10;
            
            // Get price range
            const prices = priceData.map(p => p[0]);
            const minPrice = Math.min(...prices);
            const maxPrice = Math.max(...prices);
            const priceRange = maxPrice - minPrice || 1;
            
            // Update range display
            const rangeEl = document.getElementById('chartRange');
            if (rangeEl) {
                rangeEl.textContent = '$' + minPrice.toFixed(0) + ' - $' + maxPrice.toFixed(0);
            }
            
            // Clear
            ctx.clearRect(0, 0, w, h);
            
            // Draw grid
            ctx.strokeStyle = '#27272a';
            ctx.lineWidth = 1;
            for (let i = 0; i <= 4; i++) {
                const y = padding + (h - 2 * padding) * i / 4;
                ctx.beginPath();
                ctx.moveTo(0, y);
                ctx.lineTo(w, y);
                ctx.stroke();
            }
            
            // Determine color based on trend
            const startPrice = prices[0];
            const endPrice = prices[prices.length - 1];
            const isUp = endPrice >= startPrice;
            const lineColor = isUp ? '#22c55e' : '#ef4444';
            const fillColor = isUp ? 'rgba(34, 197, 94, 0.1)' : 'rgba(239, 68, 68, 0.1)';
            
            // Draw filled area
            ctx.beginPath();
            ctx.moveTo(padding, h - padding);
            
            priceData.forEach((point, i) => {
                const x = padding + (w - 2 * padding) * i / (priceData.length - 1);
                const y = padding + (h - 2 * padding) * (1 - (point[0] - minPrice) / priceRange);
                if (i === 0) ctx.lineTo(x, y);
                else ctx.lineTo(x, y);
            });
            
            ctx.lineTo(w - padding, h - padding);
            ctx.closePath();
            ctx.fillStyle = fillColor;
            ctx.fill();
            
            // Draw line
            ctx.beginPath();
            priceData.forEach((point, i) => {
                const x = padding + (w - 2 * padding) * i / (priceData.length - 1);
                const y = padding + (h - 2 * padding) * (1 - (point[0] - minPrice) / priceRange);
                if (i === 0) ctx.moveTo(x, y);
                else ctx.lineTo(x, y);
            });
            ctx.strokeStyle = lineColor;
            ctx.lineWidth = 2;
            ctx.stroke();
            
            // Draw current price dot
            const lastX = w - padding;
            const lastY = padding + (h - 2 * padding) * (1 - (endPrice - minPrice) / priceRange);
            ctx.beginPath();
            ctx.arc(lastX, lastY, 4, 0, Math.PI * 2);
            ctx.fillStyle = lineColor;
            ctx.fill();
        }
        
        resizeCanvas();
        drawChart();
        
        // Fetch and update
        async function updateChart() {
            try {
                const resp = await fetch('/api/prices');
                const data = await resp.json();
                if (data.prices && data.prices.length > 0) {
                    priceData = data.prices;
                    drawChart();
                    
                    // Update price display
                    const priceEl = document.getElementById('livePrice');
                    const changeEl = document.getElementById('liveChange');
                    if (priceEl && data.current_price) {
                        priceEl.textContent = '$' + data.current_price.toLocaleString('en-US', {minimumFractionDigits: 2, maximumFractionDigits: 2});
                    }
                    if (changeEl && data.momentum_1m !== null) {
                        const pct = (data.momentum_1m * 100).toFixed(3);
                        changeEl.textContent = (data.momentum_1m >= 0 ? '+' : '') + pct + '%';
                        changeEl.className = 'chart-change ' + (data.momentum_1m >= 0 ? 'up' : 'down');
                    }
                }
            } catch (e) {
                console.error('Chart update error:', e);
            }
        }
        
        // Update chart every 2 seconds
        setInterval(updateChart, 2000);
        
        // Full page refresh every 30 seconds
        setTimeout(() => location.reload(), 30000);
        
        window.addEventListener('resize', () => {
            resizeCanvas();
            drawChart();
        });
    </script>
</body>
</html>
"""

start_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")

def run_trader():
    """Run trader in background thread with logging"""
    global trader
    trader = PaperTrader(log_callback=log_activity)
    asyncio.run(trader.run())

@app.route('/')
def dashboard():
    global trader
    
    # Get price history for chart
    price_history = []
    if trader and trader.price_feed and trader.price_feed.price_history:
        # Get last 60 points (about 5 min at 1 update/5s)
        history = list(trader.price_feed.price_history)[-120:]
        price_history = [[p.price, p.timestamp] for p in history]
    
    if trader is None:
        return render_template_string(DASHBOARD_HTML,
            price=None, bankroll=1000, total_pnl=0, wins=0, losses=0,
            win_rate=0, trades=[], pending=None, last_signal=None, 
            components=None, momentum_1m=None, logs=list(activity_log),
            start_time=start_time, price_history=price_history)
    
    win_rate = trader.wins / (trader.wins + trader.losses) if (trader.wins + trader.losses) > 0 else 0
    
    # Get momentum for display
    momentum_1m = trader.price_feed.get_momentum(60) if trader.price_feed else None
    
    # Get signal components
    components = None
    if hasattr(trader, 'last_signal') and trader.last_signal:
        components = trader.last_signal.components
    
    return render_template_string(DASHBOARD_HTML,
        price=trader.price_feed.current_price if trader.price_feed else None,
        bankroll=trader.bankroll,
        total_pnl=trader.total_pnl,
        wins=trader.wins,
        losses=trader.losses,
        win_rate=win_rate,
        trades=trader.trades,
        pending=trader.pending_trade,
        last_signal=getattr(trader, 'last_signal', None),
        components=components,
        momentum_1m=momentum_1m,
        logs=list(activity_log),
        start_time=start_time,
        price_history=price_history
    )

@app.route('/api/prices')
def api_prices():
    """Return recent price history for live chart"""
    global trader
    if trader is None or not trader.price_feed:
        return jsonify({"prices": [], "current_price": None, "momentum_1m": None})
    
    history = list(trader.price_feed.price_history)[-120:]
    prices = [[p.price, p.timestamp] for p in history]
    
    return jsonify({
        "prices": prices,
        "current_price": trader.price_feed.current_price,
        "momentum_1m": trader.price_feed.get_momentum(60)
    })

@app.route('/api/stats')
def api_stats():
    global trader
    if trader is None:
        return jsonify({"status": "starting"})
    
    return jsonify({
        "price": trader.price_feed.current_price if trader.price_feed else None,
        "bankroll": trader.bankroll,
        "total_pnl": trader.total_pnl,
        "daily_pnl": trader.daily_pnl,
        "wins": trader.wins,
        "losses": trader.losses,
        "trades": len(trader.trades),
        "pending": trader.pending_trade is not None,
        "logs": list(activity_log)[-20:]
    })

@app.route('/health')
def health():
    return jsonify({"status": "ok"})

if __name__ == '__main__':
    import os
    
    # Start trader in background
    trader_thread = threading.Thread(target=run_trader, daemon=True)
    trader_thread.start()
    
    # Run web server
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
