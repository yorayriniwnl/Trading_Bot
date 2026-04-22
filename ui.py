from __future__ import annotations

import math
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from html import escape
from pathlib import Path
from typing import Optional

import streamlit as st
from loguru import logger

from bot.execution import OrderRequest, execute_order, prepare_order_request
from bot.exceptions import BinanceAPIError, BinanceNetworkError, BinanceTimeoutError
from bot.orders import OrderResult
from bot.runtime import initialize_runtime

ROOT = Path(__file__).resolve().parent

DEFAULTS = {
    "symbol": "ETHUSDT",
    "side": "BUY",
    "order_type": "LIMIT",
    "quantity": 0.05,
    "price": 3000.0,
    "stop_price": 2950.0,
    "time_in_force": "GTC",
    "dry_run": True,
    "validate_exchange_metadata": True,
}

SYMBOL_PRESETS = {
    "BTCUSDT": 65000.0,
    "ETHUSDT": 3000.0,
    "SOLUSDT": 150.0,
    "BNBUSDT": 600.0,
}

PAIR_STORIES = {
    "BTCUSDT": "Macro liquidity anchor for a heavyweight testnet route.",
    "ETHUSDT": "Balanced default for precise limit and stop-limit previews.",
    "SOLUSDT": "Fast-moving pair that makes the ticket feel reactive.",
    "BNBUSDT": "Clean mid-range pricing for quantity and trigger tuning.",
}

TICKER_PRESETS = {
    "BTCUSDT": (65000.0, 2.34),
    "ETHUSDT": (3012.0, 1.89),
    "SOLUSDT": (152.4, 3.21),
    "BNBUSDT": (603.0, 0.87),
    "XRPUSDT": (0.612, -1.24),
    "AVAXUSDT": (38.2, 2.11),
    "DOGEUSDT": (0.162, 5.33),
    "ADAUSDT": (0.445, -0.55),
    "LINKUSDT": (14.62, 0.92),
}


@dataclass(frozen=True)
class DepthRow:
    price: float
    quantity: float
    total: float
    depth: float


@dataclass(frozen=True)
class TradeRow:
    price: float
    quantity: float
    side: str
    stamp: str


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    last_price: float
    delta_pct: float
    delta_value: float
    high: float
    low: float
    bid: float
    ask: float
    spread: float
    volume: str
    open_interest: str
    funding_rate: str
    funding_countdown: str
    sparkline: list[float]
    asks: list[DepthRow]
    bids: list[DepthRow]
    trades: list[TradeRow]


def configure_page() -> None:
    st.set_page_config(
        page_title="Atlas One Trading Deck",
        page_icon="A",
        layout="wide",
        initial_sidebar_state="collapsed",
    )


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url("https://fonts.googleapis.com/css2?family=Orbitron:wght@500;700;900&family=Rajdhani:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500;700&display=swap");

        :root {
            --void: #020810;
            --deep: #030d1c;
            --surface: rgba(3, 12, 24, 0.96);
            --surface-soft: rgba(7, 24, 40, 0.88);
            --panel: rgba(5, 18, 30, 0.94);
            --panel-soft: rgba(6, 19, 32, 0.72);
            --edge: rgba(0, 240, 200, 0.10);
            --edge-mid: rgba(0, 240, 200, 0.22);
            --edge-bright: rgba(0, 240, 200, 0.42);
            --primary: #00f0c8;
            --primary-dim: rgba(0, 240, 200, 0.08);
            --primary-glow: 0 0 24px rgba(0, 240, 200, 0.24);
            --buy: #00cc88;
            --buy-dim: rgba(0, 204, 136, 0.12);
            --sell: #ff2d54;
            --sell-dim: rgba(255, 45, 84, 0.12);
            --gold: #ffb340;
            --gold-dim: rgba(255, 179, 64, 0.12);
            --blue: #6da8ff;
            --blue-dim: rgba(109, 168, 255, 0.13);
            --text: #b8d4e8;
            --text-bright: #e4f2ff;
            --text-dim: #2a4860;
            --sub: #4a7090;
            --font-brand: "Orbitron", monospace;
            --font-ui: "Rajdhani", sans-serif;
            --font-mono: "JetBrains Mono", monospace;
            --shadow: 0 34px 110px rgba(0, 0, 0, 0.42);
            --radius-lg: 20px;
            --radius-md: 14px;
            --radius-sm: 10px;
        }

        html,
        body,
        [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 12% 18%, rgba(0, 240, 200, 0.11), transparent 25%),
                radial-gradient(circle at 86% 12%, rgba(255, 179, 64, 0.10), transparent 20%),
                radial-gradient(circle at 52% 100%, rgba(109, 168, 255, 0.10), transparent 28%),
                linear-gradient(180deg, #020810 0%, #041120 45%, #030c18 100%);
            color: var(--text);
            font-family: var(--font-ui);
        }

        body {
            overflow-x: hidden;
        }

        body::before {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            background:
                repeating-linear-gradient(
                    0deg,
                    transparent,
                    transparent 3px,
                    rgba(0, 0, 0, 0.06) 3px,
                    rgba(0, 0, 0, 0.06) 4px
                );
            opacity: 0.42;
            z-index: 0;
        }

        body::after {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            background: radial-gradient(ellipse at center, transparent 52%, rgba(0, 0, 0, 0.62) 100%);
            z-index: 0;
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        [data-testid="stToolbar"] {
            right: 1rem;
        }

        .block-container {
            max-width: 1480px;
            padding-top: 5.35rem;
            padding-bottom: 3.5rem;
            position: relative;
            z-index: 1;
        }

        p,
        div,
        span,
        label {
            font-family: var(--font-ui);
        }

        .atlas-gap {
            height: 1rem;
        }

        .atlas-gap-lg {
            height: 1.35rem;
        }

        .atlas-topbar {
            position: sticky;
            top: 0.6rem;
            z-index: 20;
            display: flex;
            align-items: center;
            gap: 1.1rem;
            min-height: 56px;
            padding: 0.85rem 1.15rem;
            border: 1px solid var(--edge);
            border-radius: 16px;
            background: rgba(2, 6, 16, 0.95);
            box-shadow: var(--shadow);
            backdrop-filter: blur(20px);
        }

        .atlas-logo {
            display: flex;
            align-items: center;
            gap: 0.8rem;
            flex-shrink: 0;
        }

        .atlas-logo-mark {
            width: 28px;
            height: 28px;
            position: relative;
            display: inline-flex;
            align-items: center;
            justify-content: center;
        }

        .atlas-logo-mark::before {
            content: "";
            position: absolute;
            inset: 0;
            clip-path: polygon(50% 0%, 100% 100%, 0% 100%);
            background: var(--primary);
            filter: drop-shadow(0 0 8px rgba(0, 240, 200, 0.85));
        }

        .atlas-logo-mark::after {
            content: "";
            position: absolute;
            inset: 6px 5px 4px;
            clip-path: polygon(50% 0%, 100% 100%, 0% 100%);
            background: var(--void);
        }

        .atlas-logo-text {
            font-family: var(--font-brand);
            font-size: 0.9rem;
            font-weight: 900;
            color: var(--text-bright);
            letter-spacing: 0.18em;
        }

        .atlas-logo-sub {
            font-family: var(--font-mono);
            font-size: 0.46rem;
            color: var(--primary);
            letter-spacing: 0.22em;
            text-transform: uppercase;
            opacity: 0.8;
        }

        .atlas-ticker-wrap {
            flex: 1 1 auto;
            min-width: 0;
            overflow: hidden;
            position: relative;
        }

        .atlas-ticker-wrap::before,
        .atlas-ticker-wrap::after {
            content: "";
            position: absolute;
            top: 0;
            bottom: 0;
            width: 36px;
            z-index: 2;
            pointer-events: none;
        }

        .atlas-ticker-wrap::before {
            left: 0;
            background: linear-gradient(90deg, rgba(2, 6, 16, 0.98), transparent);
        }

        .atlas-ticker-wrap::after {
            right: 0;
            background: linear-gradient(-90deg, rgba(2, 6, 16, 0.98), transparent);
        }

        .atlas-ticker-roll {
            display: flex;
            gap: 1.6rem;
            white-space: nowrap;
            width: max-content;
            animation: atlasTicker 38s linear infinite;
        }

        @keyframes atlasTicker {
            from {
                transform: translateX(0);
            }
            to {
                transform: translateX(-50%);
            }
        }

        .atlas-tick {
            display: inline-flex;
            align-items: center;
            gap: 0.45rem;
        }

        .atlas-tick-symbol,
        .atlas-tick-price,
        .atlas-tick-change {
            font-family: var(--font-mono);
            font-size: 0.72rem;
        }

        .atlas-tick-symbol {
            color: var(--sub);
            letter-spacing: 0.08em;
        }

        .atlas-tick-price {
            color: var(--text-bright);
        }

        .atlas-tick-change.up {
            color: var(--buy);
        }

        .atlas-tick-change.down {
            color: var(--sell);
        }

        .atlas-topbar-meta {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            flex-shrink: 0;
        }

        .live-dot {
            width: 7px;
            height: 7px;
            border-radius: 50%;
            background: var(--buy);
            box-shadow: 0 0 8px var(--buy);
            animation: pulse 2s ease-in-out infinite;
        }

        @keyframes pulse {
            0%, 100% {
                transform: scale(1);
                opacity: 1;
            }
            50% {
                transform: scale(0.7);
                opacity: 0.6;
            }
        }

        .live-label,
        .clock-label {
            font-family: var(--font-mono);
            font-size: 0.72rem;
            letter-spacing: 0.12em;
        }

        .live-label {
            color: var(--buy);
        }

        .clock-label {
            color: var(--sub);
        }

        .atlas-panel {
            position: relative;
            overflow: hidden;
            padding: 1.15rem 1.2rem;
            border-radius: var(--radius-lg);
            border: 1px solid var(--edge);
            background: var(--panel);
            box-shadow: var(--shadow);
        }

        .atlas-panel::before {
            content: "";
            position: absolute;
            inset: 0;
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.03), transparent 26%);
            pointer-events: none;
        }

        .panel-head {
            position: relative;
            z-index: 1;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 0.9rem;
            padding-bottom: 0.8rem;
            border-bottom: 1px solid var(--edge);
        }

        .panel-title {
            font-family: var(--font-brand);
            font-size: 0.72rem;
            color: var(--primary);
            letter-spacing: 0.24em;
            text-transform: uppercase;
        }

        .panel-sub {
            margin-top: 0.18rem;
            font-family: var(--font-mono);
            font-size: 0.66rem;
            color: var(--text-dim);
            letter-spacing: 0.1em;
        }

        .atlas-badge,
        .atlas-chip {
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
            padding: 0.28rem 0.62rem;
            border-radius: 999px;
            font-family: var(--font-mono);
            font-size: 0.66rem;
            letter-spacing: 0.1em;
            text-transform: uppercase;
            border: 1px solid transparent;
        }

        .atlas-chip-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.45rem;
            margin-top: 0.85rem;
        }

        .tone-primary {
            color: var(--primary);
            border-color: rgba(0, 240, 200, 0.22);
            background: var(--primary-dim);
        }

        .tone-buy {
            color: var(--buy);
            border-color: rgba(0, 204, 136, 0.24);
            background: var(--buy-dim);
        }

        .tone-sell {
            color: var(--sell);
            border-color: rgba(255, 45, 84, 0.24);
            background: var(--sell-dim);
        }

        .tone-gold {
            color: var(--gold);
            border-color: rgba(255, 179, 64, 0.24);
            background: var(--gold-dim);
        }

        .tone-blue {
            color: var(--blue);
            border-color: rgba(109, 168, 255, 0.24);
            background: var(--blue-dim);
        }

        .tone-dim {
            color: var(--text);
            border-color: rgba(255, 255, 255, 0.08);
            background: rgba(255, 255, 255, 0.04);
        }

        .instrument-card {
            display: grid;
            gap: 1rem;
        }

        .instrument-top {
            display: flex;
            align-items: flex-end;
            justify-content: space-between;
            gap: 1rem;
        }

        .instrument-symbol {
            font-family: var(--font-brand);
            font-size: 1.35rem;
            color: var(--text-bright);
            letter-spacing: 0.1em;
        }

        .instrument-meta {
            margin-top: 0.18rem;
            font-family: var(--font-mono);
            font-size: 0.66rem;
            color: var(--sub);
            letter-spacing: 0.08em;
        }

        .price-stack {
            text-align: right;
        }

        .price-main {
            font-family: var(--font-brand);
            font-size: 1.6rem;
            color: var(--text-bright);
            line-height: 1;
        }

        .price-delta {
            margin-top: 0.2rem;
            font-family: var(--font-mono);
            font-size: 0.72rem;
        }

        .up {
            color: var(--buy);
        }

        .down {
            color: var(--sell);
        }

        .mini-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.65rem;
        }

        .mini-metric {
            padding: 0.72rem 0.8rem;
            border-radius: var(--radius-sm);
            border: 1px solid var(--edge);
            background: rgba(255, 255, 255, 0.03);
        }

        .mini-label {
            font-family: var(--font-mono);
            font-size: 0.64rem;
            color: var(--text-dim);
            letter-spacing: 0.14em;
            text-transform: uppercase;
        }

        .mini-value {
            margin-top: 0.2rem;
            font-family: var(--font-brand);
            font-size: 1rem;
            color: var(--text-bright);
        }

        .field-kicker {
            margin: 1rem 0 0.35rem;
            font-family: var(--font-mono);
            font-size: 0.67rem;
            color: var(--text-dim);
            letter-spacing: 0.18em;
            text-transform: uppercase;
        }

        .helper-copy {
            margin: 0 0 0.45rem;
            color: var(--sub);
            font-size: 0.96rem;
            line-height: 1.4;
        }

        .atlas-notice {
            padding: 0.8rem 0.9rem;
            border-radius: var(--radius-sm);
            border: 1px solid rgba(255, 45, 84, 0.22);
            background: rgba(255, 45, 84, 0.08);
            color: #ff9cb1;
            line-height: 1.45;
        }

        .quickstrip {
            display: grid;
            gap: 0.95rem;
        }

        .quickstrip-copy {
            color: var(--sub);
            font-size: 0.98rem;
            line-height: 1.45;
        }

        .preset-note {
            margin-top: 0.45rem;
            font-size: 0.88rem;
            color: var(--sub);
            line-height: 1.35;
        }

        .hero-panel {
            padding: 1.35rem;
        }

        .hero-grid {
            position: relative;
            z-index: 1;
            display: grid;
            grid-template-columns: minmax(0, 1.05fr) minmax(240px, 0.95fr);
            gap: 1rem;
            align-items: stretch;
        }

        .hero-kicker {
            font-family: var(--font-mono);
            font-size: 0.7rem;
            color: var(--primary);
            letter-spacing: 0.18em;
            text-transform: uppercase;
        }

        .hero-title {
            margin: 0.6rem 0 0;
            font-family: var(--font-brand);
            font-size: clamp(2.2rem, 5vw, 3.6rem);
            line-height: 0.96;
            color: var(--text-bright);
        }

        .hero-copy {
            margin: 0.75rem 0 0;
            max-width: 42rem;
            color: var(--text);
            line-height: 1.62;
            font-size: 1rem;
        }

        .hero-metric-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.7rem;
            margin-top: 1rem;
        }

        .hero-metric {
            padding: 0.85rem 0.9rem;
            border-radius: 12px;
            border: 1px solid var(--edge);
            background: rgba(255, 255, 255, 0.03);
        }

        .hero-metric span {
            display: block;
            font-family: var(--font-mono);
            font-size: 0.64rem;
            color: var(--text-dim);
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }

        .hero-metric strong {
            display: block;
            margin-top: 0.22rem;
            font-family: var(--font-brand);
            font-size: 1rem;
            color: var(--text-bright);
        }

        .hero-metric p {
            margin: 0.25rem 0 0;
            color: var(--sub);
            font-size: 0.88rem;
            line-height: 1.35;
        }

        .hero-stage {
            position: relative;
            min-height: 320px;
            border-radius: 18px;
            border: 1px solid var(--edge);
            background:
                linear-gradient(180deg, rgba(0, 240, 200, 0.05), transparent 28%),
                linear-gradient(180deg, rgba(255, 255, 255, 0.02), rgba(255, 255, 255, 0.01)),
                rgba(2, 8, 16, 0.82);
            overflow: hidden;
        }

        .hero-stage::before {
            content: "";
            position: absolute;
            inset: 0;
            background:
                repeating-linear-gradient(
                    90deg,
                    rgba(0, 240, 200, 0.03) 0,
                    rgba(0, 240, 200, 0.03) 1px,
                    transparent 1px,
                    transparent 74px
                ),
                repeating-linear-gradient(
                    180deg,
                    rgba(0, 240, 200, 0.028) 0,
                    rgba(0, 240, 200, 0.028) 1px,
                    transparent 1px,
                    transparent 74px
                );
            opacity: 0.55;
        }

        .orbit-shell {
            position: absolute;
            inset: 18px 18px auto 18px;
            height: 215px;
            display: flex;
            align-items: center;
            justify-content: center;
        }

        .orbit,
        .orbit::before,
        .orbit::after {
            position: absolute;
            border-radius: 50%;
        }

        .orbit {
            border: 1px solid rgba(0, 240, 200, 0.12);
        }

        .orbit-one {
            width: 176px;
            height: 176px;
            animation: spin 14s linear infinite;
        }

        .orbit-two {
            width: 128px;
            height: 128px;
            border-color: rgba(255, 179, 64, 0.14);
            animation: spinReverse 11s linear infinite;
        }

        .orbit-three {
            width: 228px;
            height: 228px;
            border-style: dashed;
            border-color: rgba(109, 168, 255, 0.14);
            animation: spin 19s linear infinite;
        }

        .orbit-dot {
            position: absolute;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--primary);
            box-shadow: 0 0 12px rgba(0, 240, 200, 0.7);
            top: 22px;
            left: calc(50% - 4px);
        }

        .core-sphere {
            position: relative;
            z-index: 2;
            width: 120px;
            height: 120px;
            border-radius: 50%;
            border: 1px solid rgba(0, 240, 200, 0.24);
            background:
                radial-gradient(circle at 28% 28%, rgba(255, 255, 255, 0.18), transparent 40%),
                radial-gradient(circle, rgba(0, 240, 200, 0.18), rgba(0, 12, 22, 0.92) 62%);
            box-shadow:
                inset 0 1px 0 rgba(255, 255, 255, 0.1),
                0 0 36px rgba(0, 240, 200, 0.16);
            display: flex;
            flex-direction: column;
            align-items: center;
            justify-content: center;
            text-align: center;
        }

        .core-sphere span,
        .core-sphere small {
            font-family: var(--font-mono);
            text-transform: uppercase;
            letter-spacing: 0.08em;
        }

        .core-sphere span {
            font-size: 0.58rem;
            color: var(--text-dim);
        }

        .core-sphere strong {
            margin-top: 0.25rem;
            font-family: var(--font-brand);
            font-size: 1rem;
            color: var(--text-bright);
        }

        .core-sphere small {
            margin-top: 0.22rem;
            font-size: 0.62rem;
            color: var(--primary);
        }

        .sparkline-shell {
            position: absolute;
            left: 18px;
            right: 18px;
            bottom: 18px;
            padding: 0.85rem;
            border-radius: 14px;
            border: 1px solid var(--edge);
            background: rgba(2, 9, 18, 0.72);
        }

        .sparkline-head {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            margin-bottom: 0.8rem;
        }

        .sparkline-title,
        .sparkline-meta {
            font-family: var(--font-mono);
            font-size: 0.66rem;
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }

        .sparkline-title {
            color: var(--text-dim);
        }

        .sparkline-meta {
            color: var(--sub);
        }

        .sparkline {
            height: 88px;
            display: flex;
            align-items: flex-end;
            gap: 4px;
        }

        .spark-bar {
            flex: 1 1 auto;
            min-width: 4px;
            border-radius: 999px 999px 4px 4px;
            background: linear-gradient(180deg, rgba(0, 240, 200, 0.78), rgba(0, 240, 200, 0.12));
            box-shadow: 0 0 16px rgba(0, 240, 200, 0.14);
        }

        .detail-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.7rem;
            margin-top: 0.85rem;
        }

        .detail-cell {
            padding: 0.78rem 0.84rem;
            border-radius: 12px;
            border: 1px solid var(--edge);
            background: rgba(255, 255, 255, 0.03);
        }

        .detail-cell span {
            display: block;
            font-family: var(--font-mono);
            font-size: 0.64rem;
            color: var(--text-dim);
            letter-spacing: 0.12em;
            text-transform: uppercase;
        }

        .detail-cell strong {
            display: block;
            margin-top: 0.22rem;
            font-size: 1rem;
            color: var(--text-bright);
            font-weight: 700;
        }

        .intel-rows {
            display: grid;
            gap: 0.55rem;
            margin-top: 0.85rem;
        }

        .intel-row {
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
            padding: 0.72rem 0.82rem;
            border-radius: 10px;
            border: 1px solid var(--edge);
            background: rgba(255, 255, 255, 0.03);
        }

        .intel-row span,
        .intel-row strong {
            font-family: var(--font-mono);
            font-size: 0.72rem;
        }

        .intel-row span {
            color: var(--sub);
            letter-spacing: 0.08em;
        }

        .intel-row strong {
            color: var(--text-bright);
        }

        .terminal-shell {
            margin-top: 0.85rem;
            padding: 0.92rem;
            border-radius: 14px;
            border: 1px solid rgba(0, 240, 200, 0.14);
            background: rgba(1, 7, 14, 0.9);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.03);
        }

        .terminal-title {
            font-family: var(--font-mono);
            font-size: 0.68rem;
            color: var(--primary);
            letter-spacing: 0.14em;
            text-transform: uppercase;
        }

        .terminal-code {
            margin: 0.65rem 0 0;
            color: #90ffd4;
            font-family: var(--font-mono);
            font-size: 0.8rem;
            line-height: 1.58;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .depth-hero {
            display: grid;
            gap: 0.95rem;
        }

        .depth-price {
            font-family: var(--font-brand);
            font-size: 1.8rem;
            line-height: 1;
            color: var(--text-bright);
        }

        .stats-four {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.7rem;
        }

        .stats-card {
            padding: 0.78rem 0.82rem;
            border-radius: 12px;
            border: 1px solid var(--edge);
            background: rgba(255, 255, 255, 0.03);
        }

        .stats-card span {
            display: block;
            font-family: var(--font-mono);
            font-size: 0.62rem;
            color: var(--text-dim);
            letter-spacing: 0.14em;
            text-transform: uppercase;
        }

        .stats-card strong {
            display: block;
            margin-top: 0.22rem;
            font-family: var(--font-brand);
            font-size: 0.94rem;
            color: var(--text-bright);
        }

        .book-head,
        .trade-head,
        .book-row,
        .trade-row {
            display: grid;
            grid-template-columns: 1fr 0.8fr 0.95fr;
            gap: 0.6rem;
            align-items: center;
        }

        .book-head,
        .trade-head {
            margin-top: 0.9rem;
            padding: 0 0.2rem;
            font-family: var(--font-mono);
            font-size: 0.62rem;
            color: var(--text-dim);
            letter-spacing: 0.14em;
            text-transform: uppercase;
        }

        .book-stack,
        .trade-stack {
            display: grid;
            gap: 0.36rem;
            margin-top: 0.55rem;
        }

        .book-row {
            position: relative;
            overflow: hidden;
            padding: 0.48rem 0.6rem;
            border-radius: 9px;
            border: 1px solid rgba(255, 255, 255, 0.03);
            background: rgba(255, 255, 255, 0.02);
            font-family: var(--font-mono);
            font-size: 0.72rem;
        }

        .book-row.sell {
            color: #ffb4c1;
        }

        .book-row.buy {
            color: #9fffd7;
        }

        .book-row > div {
            position: relative;
            z-index: 1;
        }

        .book-bg {
            position: absolute;
            inset: 0 auto 0 0;
            opacity: 0.16;
            z-index: 0;
        }

        .book-row.sell .book-bg {
            background: linear-gradient(90deg, rgba(255, 45, 84, 0.0), rgba(255, 45, 84, 0.45));
        }

        .book-row.buy .book-bg {
            background: linear-gradient(90deg, rgba(0, 204, 136, 0.0), rgba(0, 204, 136, 0.45));
        }

        .book-mid {
            margin-top: 0.75rem;
            padding: 0.8rem 0.85rem;
            border-radius: 12px;
            border: 1px solid var(--edge);
            background: rgba(0, 240, 200, 0.06);
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 1rem;
        }

        .book-mid strong,
        .book-mid span {
            font-family: var(--font-mono);
        }

        .book-mid strong {
            color: var(--text-bright);
        }

        .book-mid span {
            color: var(--primary);
            font-size: 0.74rem;
            letter-spacing: 0.12em;
        }

        .trade-row {
            padding: 0.46rem 0.6rem;
            border-radius: 9px;
            border: 1px solid rgba(255, 255, 255, 0.03);
            background: rgba(255, 255, 255, 0.02);
            font-family: var(--font-mono);
            font-size: 0.72rem;
        }

        .trade-row .buy {
            color: var(--buy);
        }

        .trade-row .sell {
            color: var(--sell);
        }

        .result-card.success {
            border-color: rgba(0, 204, 136, 0.22);
            background: linear-gradient(180deg, rgba(0, 204, 136, 0.08), rgba(255, 255, 255, 0.02));
        }

        .result-card.error {
            border-color: rgba(255, 45, 84, 0.22);
            background: linear-gradient(180deg, rgba(255, 45, 84, 0.08), rgba(255, 255, 255, 0.02));
        }

        .result-title {
            font-family: var(--font-brand);
            font-size: 1rem;
            color: var(--text-bright);
            letter-spacing: 0.06em;
        }

        .result-copy {
            margin-top: 0.4rem;
            font-size: 0.98rem;
            color: var(--text);
            line-height: 1.55;
        }

        .activity-stack {
            display: grid;
            gap: 0.7rem;
            margin-top: 0.85rem;
        }

        .activity-item {
            padding: 0.85rem 0.9rem;
            border-radius: 12px;
            border: 1px solid var(--edge);
            background: rgba(255, 255, 255, 0.03);
        }

        .activity-route {
            display: flex;
            align-items: flex-start;
            justify-content: space-between;
            gap: 0.8rem;
        }

        .activity-route strong {
            display: block;
            font-family: var(--font-brand);
            font-size: 0.96rem;
            color: var(--text-bright);
            letter-spacing: 0.08em;
        }

        .activity-copy {
            margin-top: 0.18rem;
            color: var(--sub);
            font-size: 0.84rem;
        }

        .activity-meta {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.55rem;
            margin-top: 0.7rem;
        }

        .activity-meta div {
            padding: 0.58rem 0.64rem;
            border-radius: 10px;
            background: rgba(255, 255, 255, 0.025);
            border: 1px solid rgba(255, 255, 255, 0.03);
        }

        .activity-meta span {
            display: block;
            font-family: var(--font-mono);
            font-size: 0.62rem;
            color: var(--text-dim);
            letter-spacing: 0.14em;
            text-transform: uppercase;
        }

        .activity-meta strong {
            display: block;
            margin-top: 0.18rem;
            color: var(--text-bright);
        }

        .atlas-empty {
            color: var(--sub);
            line-height: 1.55;
            font-size: 0.98rem;
        }

        [data-testid="stTextInput"] label p,
        [data-testid="stNumberInput"] label p,
        [data-testid="stSelectbox"] label p,
        [data-testid="stRadio"] label p,
        [data-testid="stToggle"] label p {
            font-family: var(--font-mono) !important;
            font-size: 0.68rem !important;
            text-transform: uppercase;
            letter-spacing: 0.16em;
            color: var(--text-dim) !important;
        }

        [data-testid="stTextInput"] > div,
        [data-testid="stNumberInput"] > div,
        [data-testid="stSelectbox"] > div,
        [data-testid="stRadio"] > div,
        [data-testid="stToggle"] > div {
            color: var(--text);
        }

        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div {
            border-radius: 11px !important;
            border: 1px solid var(--edge) !important;
            background: rgba(255, 255, 255, 0.03) !important;
            box-shadow: none !important;
        }

        div[data-baseweb="input"] input,
        div[data-baseweb="select"] input,
        div[data-baseweb="select"] div,
        textarea {
            color: var(--text-bright) !important;
            font-family: var(--font-mono) !important;
        }

        div[data-baseweb="input"] input::placeholder {
            color: var(--text-dim) !important;
        }

        label[data-baseweb="radio"] {
            margin-right: 0 !important;
            padding: 0.7rem 0.85rem !important;
            border-radius: 10px !important;
            border: 1px solid var(--edge) !important;
            background: rgba(255, 255, 255, 0.03) !important;
        }

        label[data-baseweb="radio"][aria-checked="true"] {
            border-color: var(--edge-bright) !important;
            background: rgba(0, 240, 200, 0.09) !important;
            box-shadow: var(--primary-glow);
        }

        label[data-baseweb="radio"] div {
            color: var(--text-bright) !important;
            font-family: var(--font-mono) !important;
        }

        [data-testid="stRadio"] div[role="radiogroup"] {
            gap: 0.45rem;
        }

        [data-testid="stToggle"] label {
            gap: 0.75rem;
        }

        [data-testid="stToggle"] label > div:last-child {
            color: var(--text) !important;
            font-size: 0.96rem !important;
        }

        .stButton > button {
            min-height: 46px;
            border-radius: 10px;
            border: 1px solid var(--edge);
            background: rgba(255, 255, 255, 0.03);
            color: var(--text-bright);
            font-family: var(--font-brand);
            font-size: 0.78rem;
            letter-spacing: 0.16em;
            text-transform: uppercase;
            transition: all 0.2s ease;
        }

        .stButton > button:hover {
            border-color: var(--edge-bright);
            transform: translateY(-1px);
            box-shadow: var(--primary-glow);
            color: var(--text-bright);
        }

        .stButton > button[kind="primary"] {
            border-color: rgba(0, 204, 136, 0.34);
            background: rgba(0, 204, 136, 0.12);
            color: var(--buy);
        }

        .stButton > button[kind="secondary"] {
            background: rgba(255, 255, 255, 0.03);
        }

        [data-testid="stExpander"] {
            border: 1px solid var(--edge);
            border-radius: 12px;
            background: rgba(255, 255, 255, 0.03);
        }

        [data-testid="stExpander"] summary {
            color: var(--text-bright);
            font-family: var(--font-mono);
            letter-spacing: 0.08em;
        }

        [data-testid="stJson"] {
            background: transparent;
        }

        @keyframes spin {
            from {
                transform: rotate(0deg);
            }
            to {
                transform: rotate(360deg);
            }
        }

        @keyframes spinReverse {
            from {
                transform: rotate(360deg);
            }
            to {
                transform: rotate(0deg);
            }
        }

        @media (max-width: 1100px) {
            .block-container {
                padding-top: 6.1rem;
            }

            .atlas-topbar {
                flex-wrap: wrap;
                align-items: flex-start;
            }

            .atlas-ticker-wrap {
                order: 3;
                width: 100%;
            }

            .hero-grid {
                grid-template-columns: 1fr;
            }

            .hero-metric-grid,
            .detail-grid,
            .stats-four,
            .activity-meta {
                grid-template-columns: 1fr;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def bootstrap_state() -> None:
    for key, value in DEFAULTS.items():
        st.session_state.setdefault(key, value)
    st.session_state.setdefault("history", [])
    st.session_state.setdefault("feedback", None)
    st.session_state.setdefault("last_submission", None)


def reset_ticket() -> None:
    for key, value in DEFAULTS.items():
        st.session_state[key] = value
    st.session_state["feedback"] = None
    st.session_state["last_submission"] = None


def apply_symbol_preset(symbol: str) -> None:
    st.session_state["symbol"] = symbol
    st.session_state["price"] = SYMBOL_PRESETS[symbol]
    st.session_state["stop_price"] = round(SYMBOL_PRESETS[symbol] * 0.985, 2)


def credentials_ready() -> bool:
    return bool(os.getenv("BINANCE_TESTNET_API_KEY")) and bool(os.getenv("BINANCE_TESTNET_SECRET"))


def completion_score(order_type: str, symbol: str, quantity: float, price: float, stop_price: float) -> int:
    checks = [bool(symbol.strip()), quantity > 0]
    if order_type != "MARKET":
        checks.append(price > 0)
    if order_type == "STOP_LIMIT":
        checks.append(stop_price > 0)
    return int((sum(checks) / len(checks)) * 100)


def format_number(value: Optional[float], decimals: int = 4) -> str:
    if value is None:
        return "-"
    number = float(value)
    if abs(number) >= 1000:
        return f"{number:,.2f}".rstrip("0").rstrip(".")
    if abs(number) >= 1:
        return f"{number:,.{decimals}f}".rstrip("0").rstrip(".")
    return f"{number:,.6f}".rstrip("0").rstrip(".")


def format_price(value: Optional[float]) -> str:
    if value is None:
        return "-"
    number = float(value)
    if abs(number) >= 1000:
        return f"{number:,.2f}"
    if abs(number) >= 1:
        return f"{number:,.4f}".rstrip("0").rstrip(".")
    return f"{number:,.6f}".rstrip("0").rstrip(".")


def format_notional(value: float) -> str:
    magnitude = abs(value)
    for threshold, suffix in ((1_000_000_000_000, "T"), (1_000_000_000, "B"), (1_000_000, "M"), (1_000, "K")):
        if magnitude >= threshold:
            return f"${value / threshold:.1f}{suffix}"
    return f"${value:,.0f}"


def format_delta(current: Optional[float], reference: Optional[float]) -> str:
    if current is None or reference in (None, 0):
        return "Reference unavailable"
    delta = ((float(current) - float(reference)) / float(reference)) * 100
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.2f}% vs reference"


def chip(text: str, tone: str) -> str:
    return f'<span class="atlas-chip {tone}">{escape(text)}</span>'


def ellipsis(text: str, limit: int = 90) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def reference_price(symbol: str) -> Optional[float]:
    return SYMBOL_PRESETS.get(symbol.strip().upper())


def synthetic_reference_price(symbol: str) -> float:
    preset = reference_price(symbol)
    if preset is not None:
        return preset

    upper = symbol.strip().upper()
    if upper.startswith("BTC"):
        return 65000.0
    if upper.startswith("ETH"):
        return 3000.0
    if upper.startswith("SOL"):
        return 150.0
    if upper.startswith("BNB"):
        return 600.0
    if upper.startswith("XRP"):
        return 0.62

    seed = symbol_seed(upper)
    anchors = [0.84, 3.2, 14.5, 86.0, 420.0, 1800.0, 24500.0]
    base = anchors[seed % len(anchors)]
    return base * (1 + ((seed % 11) - 5) / 100)


def symbol_seed(symbol: str) -> int:
    cleaned = symbol.strip().upper() or "ATLAS"
    return sum((index + 1) * ord(char) for index, char in enumerate(cleaned))


def price_step(price: float) -> float:
    if price >= 10000:
        return 3.5
    if price >= 1000:
        return 1.2
    if price >= 100:
        return 0.18
    if price >= 1:
        return 0.01
    return 0.0005


def build_cli_command(request: OrderRequest) -> str:
    command = [
        sys.executable,
        str(ROOT / "cli.py"),
        "place",
        "--symbol",
        request.symbol,
        "--side",
        request.side,
        "--type",
        request.order_type,
        "--quantity",
        str(request.quantity),
    ]
    if request.price is not None:
        command.extend(["--price", str(request.price)])
    if request.stop_price is not None:
        command.extend(["--stop-price", str(request.stop_price)])
    if request.order_type != "MARKET":
        command.extend(["--tif", request.time_in_force])
    if request.dry_run:
        command.append("--dry-run")
    if not st.session_state["validate_exchange_metadata"]:
        command.append("--no-validate-exchange")
    return subprocess.list2cmdline(command)


def persist_feedback(
    *,
    kind: str,
    title: str,
    copy: str,
    request: Optional[OrderRequest] = None,
    result: Optional[OrderResult] = None,
) -> None:
    st.session_state["feedback"] = {
        "kind": kind,
        "title": title,
        "copy": copy,
    }
    if request is not None and result is not None:
        st.session_state["last_submission"] = {
            "request": {
                "symbol": request.symbol,
                "side": request.side,
                "order_type": request.order_type,
                "quantity": request.quantity,
                "price": request.price,
                "stop_price": request.stop_price,
                "time_in_force": request.time_in_force,
                "dry_run": request.dry_run,
            },
            "result": {
                "orderId": result.orderId,
                "symbol": result.symbol,
                "type": result.type,
                "status": result.status,
                "executedQty": result.executedQty,
                "avgPrice": result.avgPrice,
            },
        }


def build_market_snapshot(
    symbol: str,
    side: str,
    order_type: str,
    request: Optional[OrderRequest],
) -> MarketSnapshot:
    base = synthetic_reference_price(symbol)
    seed = symbol_seed(symbol)

    if request and request.price is not None:
        last_price = float(request.price)
    else:
        side_bias = 0.0065 if side == "BUY" else -0.0055
        type_bias = {"MARKET": 0.0026, "LIMIT": 0.0008, "STOP_LIMIT": -0.0014}[order_type]
        drift = ((seed % 13) - 6) / 1200
        last_price = base * (1 + side_bias + type_bias + drift)

    delta_pct = ((last_price - base) / base) * 100 if base else 0.0
    delta_value = last_price - base
    step = price_step(last_price)
    bid = last_price - step
    ask = last_price + step
    spread = ask - bid
    high = max(last_price, base) * (1.012 + (seed % 5) / 1000)
    low = min(last_price, base) * (0.986 - (seed % 4) / 1000)

    total_volume = last_price * (9600 + (seed % 4000))
    total_interest = last_price * (2100 + (seed % 1800))
    funding_raw = ((seed % 9) - 4) / 10000
    funding_rate = f"{funding_raw:+.4f}%"

    hours = seed % 4
    minutes = (seed * 3) % 60
    seconds = (seed * 7) % 60
    funding_countdown = f"{hours:02d}:{minutes:02d}:{seconds:02d}"

    sparkline = []
    for index in range(32):
        wave = math.sin((seed + index) * 0.31) * 20
        drift = math.cos((seed + index) * 0.12) * 11
        trend = index * (0.55 if delta_pct >= 0 else -0.4)
        value = 48 + wave + drift + trend
        sparkline.append(max(16, min(96, value)))

    asks: list[DepthRow] = []
    bids: list[DepthRow] = []
    running_ask = 0.0
    running_bid = 0.0

    for index in range(8):
        ask_qty = round(0.08 + (((seed + index * 7) % 90) / 100), 3)
        bid_qty = round(0.08 + (((seed + index * 11) % 90) / 100), 3)
        running_ask += ask_qty
        running_bid += bid_qty

        ask_price = ask + step * index * 0.9
        bid_price = bid - step * index * 0.9

        asks.append(
            DepthRow(
                price=ask_price,
                quantity=ask_qty,
                total=running_ask,
                depth=min(0.98, 0.22 + index * 0.085),
            )
        )
        bids.append(
            DepthRow(
                price=bid_price,
                quantity=bid_qty,
                total=running_bid,
                depth=min(0.98, 0.22 + index * 0.085),
            )
        )

    trades: list[TradeRow] = []
    now = datetime.now(timezone.utc)
    for index in range(12):
        trade_side = "buy" if (seed + index) % 2 == 0 else "sell"
        adjustment = step * (0.4 + index * 0.33)
        trade_price = last_price + adjustment if trade_side == "buy" else last_price - adjustment
        quantity = round(0.003 + (((seed // 3) + index * 5) % 60) / 250, 3)
        stamp = (now - timedelta(seconds=index * 17)).strftime("%H:%M:%S")
        trades.append(
            TradeRow(
                price=trade_price,
                quantity=quantity,
                side=trade_side,
                stamp=stamp,
            )
        )

    return MarketSnapshot(
        symbol=symbol,
        last_price=last_price,
        delta_pct=delta_pct,
        delta_value=delta_value,
        high=high,
        low=low,
        bid=bid,
        ask=ask,
        spread=spread,
        volume=format_notional(total_volume),
        open_interest=format_notional(total_interest),
        funding_rate=funding_rate,
        funding_countdown=funding_countdown,
        sparkline=sparkline,
        asks=asks,
        bids=bids,
        trades=trades,
    )


def topbar_markup(snapshot: MarketSnapshot, creds_ready_flag: bool) -> str:
    items: list[tuple[str, float, float]] = [(snapshot.symbol, snapshot.last_price, snapshot.delta_pct)]
    for symbol, (price, delta) in TICKER_PRESETS.items():
        if symbol == snapshot.symbol:
            continue
        items.append((symbol, price, delta))

    ticker_html = "".join(
        f"""
        <div class="atlas-tick">
            <span class="atlas-tick-symbol">{escape(symbol)}</span>
            <span class="atlas-tick-price">{escape(format_price(price))}</span>
            <span class="atlas-tick-change {'up' if delta >= 0 else 'down'}">{delta:+.2f}%</span>
        </div>
        """
        for symbol, price, delta in items * 2
    )

    lane = "LIVE READY" if creds_ready_flag else "TESTNET LOCKED"
    clock = datetime.now(timezone.utc).strftime("%H:%M:%S UTC")

    return f"""
    <section class="atlas-topbar">
        <div class="atlas-logo">
            <span class="atlas-logo-mark"></span>
            <div>
                <div class="atlas-logo-text">ATLAS ONE</div>
                <div class="atlas-logo-sub">QUANTUM TRADING TERMINAL</div>
            </div>
        </div>
        <div class="atlas-ticker-wrap">
            <div class="atlas-ticker-roll">{ticker_html}</div>
        </div>
        <div class="atlas-topbar-meta">
            <span class="live-dot"></span>
            <span class="live-label">{escape(lane)}</span>
            <span class="clock-label">{escape(clock)}</span>
        </div>
    </section>
    """


def render_quick_pairs() -> None:
    st.markdown(
        """
        <section class="atlas-panel quickstrip">
            <div class="panel-head">
                <div>
                    <div class="panel-title">Hot Routes</div>
                    <div class="panel-sub">BELIEVABLE MARKET ANCHORS</div>
                </div>
                <span class="atlas-badge tone-primary">Preset Launches</span>
            </div>
            <div class="quickstrip-copy">
                The imported Atlas terminal used a guided ticket. These preset lanes keep that feel while still driving the real backend request object.
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    cols = st.columns(len(SYMBOL_PRESETS))
    for col, symbol in zip(cols, SYMBOL_PRESETS):
        with col:
            if st.button(symbol, key=f"preset_{symbol}", use_container_width=True, type="secondary"):
                apply_symbol_preset(symbol)
                st.rerun()
            st.markdown(
                f'<div class="preset-note">Ref {escape(format_price(SYMBOL_PRESETS[symbol]))}<br>{escape(PAIR_STORIES[symbol])}</div>',
                unsafe_allow_html=True,
            )


def render_ticket_summary(
    snapshot: MarketSnapshot,
    score: int,
    request: Optional[OrderRequest],
    error: Optional[str],
    creds_ready_flag: bool,
) -> None:
    mode_label = "DRY RUN" if request and request.dry_run else ("LIVE READY" if creds_ready_flag else "LIVE LOCKED")
    mode_tone = "tone-gold" if request and request.dry_run else ("tone-buy" if creds_ready_flag else "tone-sell")
    validation_label = "VALIDATED" if request else ("ATTENTION" if error else "DRAFTING")
    validation_tone = "tone-buy" if request else ("tone-sell" if error else "tone-blue")
    delta_class = "up" if snapshot.delta_pct >= 0 else "down"

    st.markdown(
        f"""
        <section class="atlas-panel">
            <div class="panel-head">
                <div>
                    <div class="panel-title">Execution Ticket</div>
                    <div class="panel-sub">BINANCE FUTURES TESTNET</div>
                </div>
                <span class="atlas-badge {mode_tone}">{escape(mode_label)}</span>
            </div>
            <div class="instrument-card">
                <div class="instrument-top">
                    <div>
                        <div class="instrument-symbol">{escape(snapshot.symbol)}</div>
                        <div class="instrument-meta">BINANCE PERPETUAL ROUTE</div>
                    </div>
                    <div class="price-stack">
                        <div class="price-main">{escape(format_price(snapshot.last_price))}</div>
                        <div class="price-delta {delta_class}">{snapshot.delta_pct:+.2f}%</div>
                    </div>
                </div>
                <div class="atlas-chip-row">
                    {chip(st.session_state["side"], "tone-buy" if st.session_state["side"] == "BUY" else "tone-sell")}
                    {chip(st.session_state["order_type"], "tone-primary")}
                    {chip(validation_label, validation_tone)}
                </div>
                <div class="mini-grid">
                    <div class="mini-metric">
                        <div class="mini-label">Readiness</div>
                        <div class="mini-value">{score}%</div>
                    </div>
                    <div class="mini-metric">
                        <div class="mini-label">Reference Delta</div>
                        <div class="mini-value">{escape(format_delta(snapshot.last_price, synthetic_reference_price(snapshot.symbol)))}</div>
                    </div>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_field_intro(title: str, copy: str) -> None:
    st.markdown(
        f"""
        <div class="field-kicker">{escape(title)}</div>
        <div class="helper-copy">{escape(copy)}</div>
        """,
        unsafe_allow_html=True,
    )


def render_ticket_controls(preview_error: Optional[str], creds_ready_flag: bool, score: int) -> tuple[bool, bool]:
    if preview_error:
        st.markdown(f'<div class="atlas-notice">{escape(preview_error)}</div>', unsafe_allow_html=True)

    render_field_intro("Instrument", "Pick the pair first. The rest of the execution geometry reacts around it.")
    st.text_input(
        "Symbol",
        key="symbol",
        placeholder="BTCUSDT",
        help="Binance Futures symbol ending in USDT or BUSD.",
    )

    top_row = st.columns([1, 1], gap="small")
    with top_row[0]:
        st.radio("Side", options=["BUY", "SELL"], horizontal=True, key="side")
    with top_row[1]:
        st.selectbox("Order Type", options=["MARKET", "LIMIT", "STOP_LIMIT"], key="order_type")

    render_field_intro("Pricing Geometry", "Market orders skip price, limit orders require price, and stop-limit adds a trigger layer.")
    middle_row = st.columns([1, 1], gap="small")
    with middle_row[0]:
        st.number_input(
            "Quantity",
            min_value=0.0,
            step=0.001,
            format="%.8f",
            key="quantity",
        )
    with middle_row[1]:
        if st.session_state["order_type"] == "MARKET":
            st.text_input("Limit Price", value="Not required for market orders", disabled=True)
        else:
            st.number_input(
                "Limit Price",
                min_value=0.0,
                step=10.0,
                format="%.4f",
                key="price",
            )

    lower_row = st.columns([1, 1], gap="small")
    with lower_row[0]:
        if st.session_state["order_type"] == "STOP_LIMIT":
            st.number_input(
                "Stop Price",
                min_value=0.0,
                step=10.0,
                format="%.4f",
                key="stop_price",
            )
        else:
            st.text_input("Stop Price", value="Only used for stop-limit orders", disabled=True)
    with lower_row[1]:
        st.selectbox(
            "Time In Force",
            options=["GTC", "IOC", "FOK"],
            key="time_in_force",
            disabled=st.session_state["order_type"] == "MARKET",
        )

    render_field_intro("Execution Controls", "Stay in dry-run for safe demos, or switch it off when testnet credentials are ready.")
    st.toggle(
        "Dry-run mode",
        key="dry_run",
        help="When enabled, the desk validates and previews execution without sending a live API call.",
    )
    st.toggle(
        "Exchange metadata preflight",
        key="validate_exchange_metadata",
        help=(
            "When enabled, the desk checks Binance exchange filters before submit. "
            "Disable this to keep previews fully offline."
        ),
    )

    lane_title = "Dry run keeps the route safe." if st.session_state["dry_run"] else (
        "Live sandbox lane unlocked." if creds_ready_flag else "Live mode is still credential-gated."
    )
    lane_copy = (
        "The request is validated and mirrored to CLI, but no order is sent."
        if st.session_state["dry_run"]
        else (
            "The desk can route real Binance Futures Testnet orders."
            if creds_ready_flag
            else "Add BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_SECRET to .env before disabling dry-run."
        )
    )
    lane_copy += " "
    lane_copy += (
        "Exchange metadata preflight is enabled."
        if st.session_state["validate_exchange_metadata"]
        else "Exchange metadata preflight is disabled for offline drafting."
    )
    lane_tone = "tone-gold" if st.session_state["dry_run"] else ("tone-buy" if creds_ready_flag else "tone-sell")

    st.markdown(
        f"""
        <section class="atlas-panel">
            <div class="panel-head">
                <div>
                    <div class="panel-title">Lane Status</div>
                    <div class="panel-sub">EXECUTION GUARDRAILS</div>
                </div>
                <span class="atlas-badge {lane_tone}">{score}% READY</span>
            </div>
            <div class="result-title">{escape(lane_title)}</div>
            <div class="result-copy">{escape(lane_copy)}</div>
            <div class="atlas-chip-row">
                {chip("CLI + UI SHARED CORE", "tone-blue")}
                {chip("LOGGING ENABLED", "tone-primary")}
                {chip("EXCHANGE FILTERS ON" if st.session_state["validate_exchange_metadata"] else "LOCAL VALIDATION ONLY", "tone-buy" if st.session_state["validate_exchange_metadata"] else "tone-blue")}
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    action_cols = st.columns([1.45, 1], gap="small")
    submit_disabled = bool(preview_error) or (not st.session_state["dry_run"] and not creds_ready_flag)
    submit_clicked = action_cols[0].button(
        "Execute Order",
        use_container_width=True,
        type="primary",
        disabled=submit_disabled,
    )
    reset_clicked = action_cols[1].button("Reset Form", use_container_width=True, type="secondary")
    return submit_clicked, reset_clicked


def render_stage_panel(
    snapshot: MarketSnapshot,
    score: int,
    request: Optional[OrderRequest],
    error: Optional[str],
    creds_ready_flag: bool,
) -> None:
    history = st.session_state["history"]
    mode_label = "Dry Run" if request and request.dry_run else ("Live Ready" if creds_ready_flag else "Live Locked")
    validation_state = "Validated" if request else ("Attention" if error else "Drafting")
    latest_status = history[0]["status"] if history else "IDLE"
    spark_bars = "".join(
        f'<span class="spark-bar" style="height:{value:.0f}%"></span>' for value in snapshot.sparkline
    )
    hero_copy = (
        "The imported Atlas terminal is now driving the real Streamlit desk, so the visual language, command mirror, and market intel all sit on top of the live trading workflow."
    )
    if error:
        hero_copy = f"Draft needs attention before routing: {ellipsis(error, 120)}"

    st.markdown(
        f"""
        <section class="atlas-panel hero-panel">
            <div class="hero-grid">
                <div>
                    <div class="hero-kicker">Atlas One / Terminal Integration / Streamlit Execution Deck</div>
                    <div class="hero-title">ATLAS ONE</div>
                    <div class="hero-copy">{escape(hero_copy)}</div>
                    <div class="atlas-chip-row">
                        {chip(snapshot.symbol, "tone-blue")}
                        {chip(st.session_state["order_type"], "tone-primary")}
                        {chip(st.session_state["side"], "tone-buy" if st.session_state["side"] == "BUY" else "tone-sell")}
                        {chip(mode_label, "tone-gold" if request and request.dry_run else ("tone-buy" if creds_ready_flag else "tone-sell"))}
                        {chip(validation_state, "tone-buy" if request else ("tone-sell" if error else "tone-blue"))}
                    </div>
                    <div class="hero-metric-grid">
                        <div class="hero-metric">
                            <span>Build Readiness</span>
                            <strong>{score}%</strong>
                            <p>Score reacts only to the fields required by the active order type.</p>
                        </div>
                        <div class="hero-metric">
                            <span>Execution Lane</span>
                            <strong>{escape(mode_label)}</strong>
                            <p>Dry-run protects the demo, live mode stays tied to testnet credentials.</p>
                        </div>
                        <div class="hero-metric">
                            <span>Session Pulse</span>
                            <strong>{escape(latest_status)}</strong>
                            <p>{len(history)} orders cached locally so the desk feels persistent.</p>
                        </div>
                    </div>
                </div>
                <div class="hero-stage">
                    <div class="orbit-shell">
                        <div class="orbit orbit-three"></div>
                        <div class="orbit orbit-one"><span class="orbit-dot"></span></div>
                        <div class="orbit orbit-two"><span class="orbit-dot"></span></div>
                        <div class="core-sphere">
                            <span>{escape(snapshot.symbol)}</span>
                            <strong>{escape(format_price(snapshot.last_price))}</strong>
                            <small>{snapshot.delta_pct:+.2f}%</small>
                        </div>
                    </div>
                    <div class="sparkline-shell">
                        <div class="sparkline-head">
                            <span class="sparkline-title">Signal Strip</span>
                            <span class="sparkline-meta">Open Interest {escape(snapshot.open_interest)}</span>
                        </div>
                        <div class="sparkline">{spark_bars}</div>
                    </div>
                </div>
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def preview_card(request: Optional[OrderRequest], error: Optional[str], creds_ready_flag: bool, snapshot: MarketSnapshot) -> str:
    if request is None:
        return f"""
        <section class="atlas-panel">
            <div class="panel-head">
                <div>
                    <div class="panel-title">Order Preview</div>
                    <div class="panel-sub">NORMALIZED REQUEST LANE</div>
                </div>
                <span class="atlas-badge tone-sell">Blocked</span>
            </div>
            <div class="result-title">Draft needs attention</div>
            <div class="result-copy">{escape(error or "Fill in the remaining fields to unlock the backend preview.")}</div>
        </section>
        """

    creds_chip = "tone-buy" if creds_ready_flag else "tone-blue"
    intel_rows = "".join(
        [
            f"""
            <div class="intel-row">
                <span>Reference Price</span>
                <strong>{escape(format_price(synthetic_reference_price(request.symbol)))}</strong>
            </div>
            """,
            f"""
            <div class="intel-row">
                <span>Delta vs Reference</span>
                <strong>{escape(format_delta(request.price, synthetic_reference_price(request.symbol)) if request.price is not None else "Market order uses live price")}</strong>
            </div>
            """,
            f"""
            <div class="intel-row">
                <span>Funding Window</span>
                <strong>{escape(snapshot.funding_rate)} / {escape(snapshot.funding_countdown)}</strong>
            </div>
            """,
            f"""
            <div class="intel-row">
                <span>Credential Lane</span>
                <strong>{escape("Live testnet ready" if creds_ready_flag else "Dry-run only until keys exist")}</strong>
            </div>
            """,
        ]
    )

    return f"""
    <section class="atlas-panel">
        <div class="panel-head">
            <div>
                <div class="panel-title">Order Preview</div>
                <div class="panel-sub">NORMALIZED REQUEST LANE</div>
            </div>
            <span class="atlas-badge tone-primary">Ready</span>
        </div>
        <div class="atlas-chip-row">
            {chip(request.side, "tone-buy" if request.side == "BUY" else "tone-sell")}
            {chip(request.order_type, "tone-primary")}
            {chip("DRY RUN" if request.dry_run else "LIVE TESTNET", "tone-gold" if request.dry_run else "tone-buy")}
            {chip("CREDENTIALS READY" if creds_ready_flag else "KEYS MISSING", creds_chip)}
        </div>
        <div class="detail-grid">
            <div class="detail-cell"><span>Pair</span><strong>{escape(request.symbol)}</strong></div>
            <div class="detail-cell"><span>Quantity</span><strong>{escape(format_number(request.quantity))}</strong></div>
            <div class="detail-cell"><span>Limit Price</span><strong>{escape(format_price(request.price))}</strong></div>
            <div class="detail-cell"><span>Stop Price</span><strong>{escape(format_price(request.stop_price))}</strong></div>
            <div class="detail-cell"><span>Time In Force</span><strong>{escape(request.time_in_force if request.order_type != "MARKET" else "N/A")}</strong></div>
            <div class="detail-cell"><span>Last Price</span><strong>{escape(format_price(snapshot.last_price))}</strong></div>
        </div>
        <div class="intel-rows">
            {intel_rows}
        </div>
    </section>
    """


def command_card(request: Optional[OrderRequest], error: Optional[str]) -> str:
    if request is None:
        return f"""
        <section class="atlas-panel">
            <div class="panel-head">
                <div>
                    <div class="panel-title">Command Mirror</div>
                    <div class="panel-sub">TERMINAL EDITION</div>
                </div>
                <span class="atlas-badge tone-dim">Awaiting</span>
            </div>
            <div class="result-copy">{escape(error or "The exact CLI equivalent appears here once the ticket validates.")}</div>
        </section>
        """

    return f"""
    <section class="atlas-panel">
        <div class="panel-head">
            <div>
                <div class="panel-title">Command Mirror</div>
                <div class="panel-sub">TERMINAL EDITION</div>
            </div>
            <span class="atlas-badge tone-primary">CLI PARITY</span>
        </div>
        <div class="result-copy">The premium desk stays grounded in the same repository command a reviewer can run locally.</div>
        <div class="terminal-shell">
            <div class="terminal-title">CLI Equivalent</div>
            <pre class="terminal-code">{escape(build_cli_command(request))}</pre>
        </div>
    </section>
    """


def order_book_rows(rows: list[DepthRow], tone: str) -> str:
    return "".join(
        f"""
        <div class="book-row {tone}">
            <div class="book-bg" style="width:{row.depth * 100:.0f}%"></div>
            <div>{escape(format_price(row.price))}</div>
            <div>{escape(format_number(row.quantity, 3))}</div>
            <div>{escape(format_number(row.total, 3))}</div>
        </div>
        """
        for row in rows
    )


def trade_rows(rows: list[TradeRow]) -> str:
    return "".join(
        f"""
        <div class="trade-row">
            <div class="{escape(row.side)}">{escape(format_price(row.price))}</div>
            <div>{escape(format_number(row.quantity, 3))}</div>
            <div>{escape(row.stamp)}</div>
        </div>
        """
        for row in rows
    )


def render_depth_panel(snapshot: MarketSnapshot) -> None:
    delta_class = "up" if snapshot.delta_pct >= 0 else "down"
    st.markdown(
        f"""
        <section class="atlas-panel">
            <div class="panel-head">
                <div>
                    <div class="panel-title">Market Depth</div>
                    <div class="panel-sub">ORDER BOOK + TRADE FEED</div>
                </div>
                <span class="atlas-badge tone-primary">LIVE LOOK</span>
            </div>
            <div class="depth-hero">
                <div>
                    <div class="mini-label">Last Price</div>
                    <div class="depth-price">{escape(format_price(snapshot.last_price))}</div>
                    <div class="price-delta {delta_class}">{snapshot.delta_value:+,.2f} ({snapshot.delta_pct:+.2f}%)</div>
                </div>
                <div class="stats-four">
                    <div class="stats-card"><span>24H High</span><strong>{escape(format_price(snapshot.high))}</strong></div>
                    <div class="stats-card"><span>24H Low</span><strong>{escape(format_price(snapshot.low))}</strong></div>
                    <div class="stats-card"><span>Bid</span><strong>{escape(format_price(snapshot.bid))}</strong></div>
                    <div class="stats-card"><span>Ask</span><strong>{escape(format_price(snapshot.ask))}</strong></div>
                </div>
            </div>
            <div class="book-head"><div>Price</div><div>Size</div><div>Total</div></div>
            <div class="book-stack">{order_book_rows(snapshot.asks, "sell")}</div>
            <div class="book-mid">
                <strong>{escape(format_price(snapshot.last_price))}</strong>
                <span>SPREAD {escape(format_price(snapshot.spread))}</span>
            </div>
            <div class="book-stack">{order_book_rows(snapshot.bids, "buy")}</div>
            <div class="trade-head"><div>Price</div><div>Size</div><div>Time</div></div>
            <div class="trade-stack">{trade_rows(snapshot.trades[:10])}</div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def result_panel(kind: str, title: str, copy: str) -> str:
    return f"""
    <section class="atlas-panel result-card {'success' if kind == 'success' else 'error'}">
        <div class="panel-head">
            <div>
                <div class="panel-title">{'Execution Result' if kind == 'success' else 'Execution Blocked'}</div>
                <div class="panel-sub">LATEST BACKEND OUTCOME</div>
            </div>
            <span class="atlas-badge {'tone-buy' if kind == 'success' else 'tone-sell'}">{'ACCEPTED' if kind == 'success' else 'BLOCKED'}</span>
        </div>
        <div class="result-title">{escape(title)}</div>
        <div class="result-copy">{escape(copy)}</div>
    </section>
    """


def render_feedback_panel() -> None:
    feedback = st.session_state["feedback"]
    last_submission = st.session_state["last_submission"]

    if feedback:
        st.markdown(result_panel(feedback["kind"], feedback["title"], feedback["copy"]), unsafe_allow_html=True)
        if last_submission:
            with st.expander("View normalized request and response"):
                st.json(last_submission)
        return

    st.markdown(
        """
        <section class="atlas-panel">
            <div class="panel-head">
                <div>
                    <div class="panel-title">Execution Feedback</div>
                    <div class="panel-sub">PERSISTENT RESPONSE SURFACE</div>
                </div>
                <span class="atlas-badge tone-dim">Idle</span>
            </div>
            <div class="atlas-empty">
                Nothing has been routed yet. Submit a dry-run first and this rail turns into the persistent result surface for the session.
            </div>
        </section>
        """,
        unsafe_allow_html=True,
    )


def activity_feed(history: list[dict[str, str]]) -> str:
    if not history:
        return """
        <section class="atlas-panel">
            <div class="panel-head">
                <div>
                    <div class="panel-title">Session Activity</div>
                    <div class="panel-sub">LOCAL EXECUTION MEMORY</div>
                </div>
                <span class="atlas-badge tone-dim">Empty</span>
            </div>
            <div class="atlas-empty">
                Route a dry-run order and this stack becomes the recent ledger for pair, side, mode, and status.
            </div>
        </section>
        """

    items = "".join(
        f"""
        <div class="activity-item">
            <div class="activity-route">
                <div>
                    <strong>{escape(item['symbol'])} / {escape(item['order_type'])}</strong>
                    <div class="activity-copy">{escape(item['timestamp'])} / Order #{escape(item['order_id'])}</div>
                </div>
                <div class="atlas-chip-row" style="margin-top:0;">
                    {chip(item['side'], "tone-buy" if item['side'] == 'BUY' else "tone-sell")}
                    {chip(item['mode'], "tone-gold" if item['mode'] == 'DRY RUN' else "tone-primary")}
                </div>
            </div>
            <div class="activity-meta">
                <div><span>Quantity</span><strong>{escape(item['quantity'])}</strong></div>
                <div><span>Status</span><strong>{escape(item['status'])}</strong></div>
            </div>
        </div>
        """
        for item in history[:6]
    )

    return f"""
    <section class="atlas-panel">
        <div class="panel-head">
            <div>
                <div class="panel-title">Session Activity</div>
                <div class="panel-sub">LOCAL EXECUTION MEMORY</div>
            </div>
            <span class="atlas-badge tone-primary">{len(history)} ROUTES</span>
        </div>
        <div class="activity-stack">
            {items}
        </div>
    </section>
    """


def record_activity(request: OrderRequest, result: OrderResult) -> None:
    st.session_state["history"] = [
        {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "symbol": request.symbol,
            "side": request.side,
            "order_type": request.order_type,
            "quantity": format_number(request.quantity),
            "status": result.status,
            "order_id": result.orderId,
            "mode": "DRY RUN" if request.dry_run else "LIVE",
        },
        *st.session_state["history"],
    ][:6]


def current_request_kwargs() -> dict[str, object]:
    return {
        "symbol": st.session_state["symbol"],
        "side": st.session_state["side"],
        "order_type": st.session_state["order_type"],
        "quantity": st.session_state["quantity"],
        "price": st.session_state["price"],
        "stop_price": st.session_state["stop_price"],
        "time_in_force": st.session_state["time_in_force"],
        "dry_run": st.session_state["dry_run"],
        "validate_exchange_metadata": st.session_state["validate_exchange_metadata"],
    }


def build_request_preview() -> tuple[Optional[OrderRequest], Optional[str]]:
    try:
        request = prepare_order_request(**current_request_kwargs())
        return request, None
    except ValueError as exc:
        return None, str(exc)


def handle_submission(preview_request: Optional[OrderRequest]) -> None:
    try:
        request = preview_request or prepare_order_request(**current_request_kwargs())
        with st.spinner("Routing through Atlas One..."):
            result = execute_order(request)

        record_activity(request, result)
        persist_feedback(
            kind="success",
            title="Order accepted.",
            copy=(
                f"{request.symbol} {request.order_type} returned status {result.status}. "
                f"Order ID {result.orderId}."
            ),
            request=request,
            result=result,
        )
        logger.info(
            "UI order executed | symbol={} side={} type={} dry_run={}",
            request.symbol,
            request.side,
            request.order_type,
            request.dry_run,
        )
    except ValueError as exc:
        persist_feedback(
            kind="error",
            title="Validation interrupted the route.",
            copy=str(exc),
        )
    except BinanceAPIError as exc:
        hint = exc.user_hint()
        detail = str(exc) if not hint else f"{exc} {hint}"
        persist_feedback(
            kind="error",
            title="Binance declined the order.",
            copy=detail,
        )
    except (BinanceNetworkError, BinanceTimeoutError) as exc:
        persist_feedback(
            kind="error",
            title="The network lane stalled.",
            copy=str(exc),
        )
    except EnvironmentError as exc:
        persist_feedback(
            kind="error",
            title="Credentials are still missing.",
            copy=str(exc),
        )
    except Exception as exc:
        logger.exception("Unexpected UI error")
        persist_feedback(
            kind="error",
            title="Unexpected issue during execution.",
            copy=str(exc),
        )


def main() -> None:
    initialize_runtime()
    configure_page()

    try:
        bootstrap_state()
        inject_styles()

        creds_ready_flag = credentials_ready()
        preview_request, preview_error = build_request_preview()
        symbol = (preview_request.symbol if preview_request else st.session_state["symbol"].strip().upper()) or DEFAULTS["symbol"]
        snapshot = build_market_snapshot(
            symbol=symbol,
            side=st.session_state["side"],
            order_type=st.session_state["order_type"],
            request=preview_request,
        )
        score = completion_score(
            st.session_state["order_type"],
            st.session_state["symbol"],
            st.session_state["quantity"],
            st.session_state["price"],
            st.session_state["stop_price"],
        )

        st.markdown(topbar_markup(snapshot, creds_ready_flag), unsafe_allow_html=True)
        st.markdown('<div class="atlas-gap-lg"></div>', unsafe_allow_html=True)
        render_quick_pairs()
        st.markdown('<div class="atlas-gap-lg"></div>', unsafe_allow_html=True)

        left, center, right = st.columns([1.04, 1.12, 0.94], gap="medium")

        with left:
            render_ticket_summary(snapshot, score, preview_request, preview_error, creds_ready_flag)
            st.markdown('<div class="atlas-gap"></div>', unsafe_allow_html=True)
            submit_clicked, reset_clicked = render_ticket_controls(preview_error, creds_ready_flag, score)

        if reset_clicked:
            reset_ticket()
            st.rerun()

        if submit_clicked:
            handle_submission(preview_request)

        with center:
            render_stage_panel(snapshot, score, preview_request, preview_error, creds_ready_flag)
            st.markdown('<div class="atlas-gap"></div>', unsafe_allow_html=True)
            st.markdown(preview_card(preview_request, preview_error, creds_ready_flag, snapshot), unsafe_allow_html=True)
            st.markdown('<div class="atlas-gap"></div>', unsafe_allow_html=True)
            st.markdown(command_card(preview_request, preview_error), unsafe_allow_html=True)

        with right:
            render_depth_panel(snapshot)
            st.markdown('<div class="atlas-gap"></div>', unsafe_allow_html=True)
            render_feedback_panel()
            st.markdown('<div class="atlas-gap"></div>', unsafe_allow_html=True)
            st.markdown(activity_feed(st.session_state["history"]), unsafe_allow_html=True)
    except Exception as exc:
        logger.exception("Fatal UI render error")
        st.error("Atlas One hit an unexpected rendering issue. Reload the app after checking the details below.")
        with st.expander("Technical details"):
            st.code(str(exc))


if __name__ == "__main__":
    main()
