from __future__ import annotations

import os
from datetime import datetime
from html import escape
from typing import Optional

import streamlit as st
from dotenv import load_dotenv
from loguru import logger

from bot.execution import OrderRequest, execute_order, prepare_order_request
from bot.exceptions import BinanceAPIError, BinanceNetworkError, BinanceTimeoutError
from bot.logging_config import setup_logging
from bot.orders import OrderResult

load_dotenv()
setup_logging()

st.set_page_config(
    page_title="Atlas One Trading Deck",
    page_icon="A",
    layout="wide",
    initial_sidebar_state="collapsed",
)

DEFAULTS = {
    "symbol": "ETHUSDT",
    "side": "BUY",
    "order_type": "LIMIT",
    "quantity": 0.05,
    "price": 3000.0,
    "stop_price": 2950.0,
    "time_in_force": "GTC",
    "dry_run": True,
}

SYMBOL_PRESETS = {
    "BTCUSDT": 65000.0,
    "ETHUSDT": 3000.0,
    "SOLUSDT": 150.0,
    "BNBUSDT": 600.0,
}

PAIR_STORIES = {
    "BTCUSDT": "Macro liquidity anchor with the tightest test-ticket feel.",
    "ETHUSDT": "Balanced default for controlled preview and limit workflows.",
    "SOLUSDT": "High-beta route for showing off the reactive form states.",
    "BNBUSDT": "Clean mid-range pair for precise quantity and pricing demos.",
}


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500;600&family=Sora:wght@400;500;600;700&family=Space+Grotesk:wght@500;700&display=swap');

        :root {
            --bg-0: #04111c;
            --bg-1: #081927;
            --bg-2: #0d2437;
            --surface-0: rgba(7, 20, 34, 0.76);
            --surface-1: rgba(10, 27, 44, 0.84);
            --surface-2: rgba(13, 35, 57, 0.66);
            --surface-soft: rgba(240, 248, 255, 0.06);
            --line: rgba(135, 180, 235, 0.14);
            --line-strong: rgba(135, 180, 235, 0.28);
            --text: #eef5ff;
            --text-soft: #c8d8ea;
            --muted: #8ea6bc;
            --mint: #48e3c1;
            --mint-soft: rgba(72, 227, 193, 0.14);
            --amber: #f3cb88;
            --amber-soft: rgba(243, 203, 136, 0.15);
            --coral: #ff8b83;
            --coral-soft: rgba(255, 139, 131, 0.14);
            --blue: #87b8ff;
            --blue-soft: rgba(135, 184, 255, 0.16);
            --shadow-heavy: 0 34px 120px rgba(0, 0, 0, 0.45);
            --shadow-soft: 0 18px 60px rgba(4, 13, 25, 0.28);
            --radius-xl: 34px;
            --radius-lg: 26px;
            --radius-md: 18px;
        }

        html, body, [data-testid="stAppViewContainer"] {
            background:
                radial-gradient(circle at 12% 18%, rgba(72, 227, 193, 0.14), transparent 24%),
                radial-gradient(circle at 86% 12%, rgba(243, 203, 136, 0.12), transparent 22%),
                radial-gradient(circle at 52% 100%, rgba(135, 184, 255, 0.14), transparent 30%),
                linear-gradient(180deg, #04111c 0%, #091827 44%, #07131e 100%);
            color: var(--text);
            font-family: "Sora", "Segoe UI", sans-serif;
        }

        body::before {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            background:
                linear-gradient(rgba(255, 255, 255, 0.02), rgba(255, 255, 255, 0.02)),
                repeating-linear-gradient(
                    90deg,
                    rgba(135, 184, 255, 0.04) 0,
                    rgba(135, 184, 255, 0.04) 1px,
                    transparent 1px,
                    transparent 120px
                ),
                repeating-linear-gradient(
                    180deg,
                    rgba(135, 184, 255, 0.028) 0,
                    rgba(135, 184, 255, 0.028) 1px,
                    transparent 1px,
                    transparent 120px
                );
            opacity: 0.22;
        }

        body::after {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            background:
                radial-gradient(circle at center, rgba(255, 255, 255, 0.08), transparent 55%);
            mix-blend-mode: screen;
            opacity: 0.2;
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        [data-testid="stToolbar"] {
            right: 1rem;
        }

        .block-container {
            max-width: 1320px;
            padding-top: 1.2rem;
            padding-bottom: 4.5rem;
        }

        h1, h2, h3, h4, h5 {
            font-family: "Space Grotesk", "Sora", sans-serif;
            color: var(--text);
            letter-spacing: -0.03em;
        }

        p, div, span, label {
            font-family: "Sora", "Segoe UI", sans-serif;
        }

        .mono {
            font-family: "IBM Plex Mono", monospace;
            text-transform: uppercase;
            letter-spacing: 0.14em;
        }

        .space-sm {
            height: 0.9rem;
        }

        .space-lg {
            height: 1.35rem;
        }

        .space-xl {
            height: 2rem;
        }

        .hero-shell {
            position: relative;
            overflow: hidden;
            padding: 2.2rem;
            border-radius: var(--radius-xl);
            border: 1px solid rgba(255, 255, 255, 0.08);
            background:
                linear-gradient(145deg, rgba(9, 25, 42, 0.96), rgba(5, 17, 28, 0.96) 62%, rgba(16, 42, 65, 0.9)),
                radial-gradient(circle at top left, rgba(72, 227, 193, 0.16), transparent 26%);
            box-shadow: var(--shadow-heavy);
            animation: rise 0.75s ease both;
        }

        .hero-shell::before {
            content: "";
            position: absolute;
            inset: 1rem;
            border-radius: calc(var(--radius-xl) - 10px);
            border: 1px solid rgba(255, 255, 255, 0.06);
            pointer-events: none;
        }

        .hero-shell::after {
            content: "";
            position: absolute;
            inset: -20% auto auto 55%;
            width: 380px;
            height: 380px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(72, 227, 193, 0.22), transparent 60%);
            filter: blur(20px);
            opacity: 0.75;
            pointer-events: none;
        }

        .hero-grid {
            position: relative;
            display: grid;
            grid-template-columns: minmax(0, 1.05fr) minmax(320px, 0.95fr);
            gap: 1.5rem;
            align-items: center;
            z-index: 2;
        }

        .hero-kicker {
            display: inline-flex;
            align-items: center;
            gap: 0.65rem;
            padding: 0.5rem 0.8rem;
            border-radius: 999px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            background: rgba(255, 255, 255, 0.04);
            color: var(--text-soft);
            font-size: 0.72rem;
        }

        .hero-title {
            margin: 1rem 0 0;
            font-size: clamp(3.8rem, 9vw, 7.4rem);
            line-height: 0.9;
            color: #f7fbff;
        }

        .hero-subtitle {
            margin: 0.8rem 0 0;
            max-width: 18ch;
            font-size: clamp(1.45rem, 2.9vw, 2.2rem);
            line-height: 1.02;
            color: #f2f7fc;
        }

        .hero-copy {
            max-width: 46rem;
            margin: 1rem 0 0;
            color: var(--text-soft);
            line-height: 1.78;
            font-size: 0.98rem;
        }

        .hero-badge-row {
            display: flex;
            flex-wrap: wrap;
            gap: 0.6rem;
            margin-top: 1.1rem;
        }

        .status-chip {
            display: inline-flex;
            align-items: center;
            padding: 0.42rem 0.8rem;
            border-radius: 999px;
            font-size: 0.72rem;
            font-weight: 700;
            letter-spacing: 0.08em;
            text-transform: uppercase;
            backdrop-filter: blur(12px);
        }

        .chip-mint {
            color: #8effe5;
            background: var(--mint-soft);
            border: 1px solid rgba(72, 227, 193, 0.24);
        }

        .chip-amber {
            color: #ffe6af;
            background: var(--amber-soft);
            border: 1px solid rgba(243, 203, 136, 0.22);
        }

        .chip-coral {
            color: #ffc0bb;
            background: var(--coral-soft);
            border: 1px solid rgba(255, 139, 131, 0.22);
        }

        .chip-blue {
            color: #bbd8ff;
            background: var(--blue-soft);
            border: 1px solid rgba(135, 184, 255, 0.22);
        }

        .hero-stat-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.9rem;
            margin-top: 1.55rem;
        }

        .hero-stat {
            position: relative;
            padding: 1rem 1rem 1.05rem;
            border-radius: 22px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.025));
            box-shadow: 0 18px 40px rgba(0, 0, 0, 0.16);
            transform: perspective(1400px) rotateX(9deg);
            transition: transform 0.25s ease, border-color 0.25s ease, background 0.25s ease;
        }

        .hero-stat:hover {
            transform: perspective(1400px) rotateX(3deg) translateY(-4px);
            border-color: rgba(255, 255, 255, 0.15);
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.03));
        }

        .hero-stat span {
            display: block;
            color: var(--muted);
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
        }

        .hero-stat strong {
            display: block;
            margin-top: 0.55rem;
            color: #f5fbff;
            font-size: 1.45rem;
            line-height: 1.05;
            font-family: "Space Grotesk", sans-serif;
        }

        .hero-stat p {
            margin: 0.45rem 0 0;
            color: var(--text-soft);
            line-height: 1.6;
            font-size: 0.88rem;
        }

        .hero-stage {
            position: relative;
            height: 440px;
            border-radius: 30px;
            overflow: hidden;
            border: 1px solid rgba(255, 255, 255, 0.08);
            background:
                radial-gradient(circle at top, rgba(72, 227, 193, 0.18), transparent 26%),
                radial-gradient(circle at bottom, rgba(135, 184, 255, 0.12), transparent 30%),
                linear-gradient(180deg, rgba(8, 23, 37, 0.96), rgba(4, 14, 24, 0.94));
            perspective: 1800px;
            transform-style: preserve-3d;
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.05), var(--shadow-soft);
        }

        .hero-stage::before {
            content: "";
            position: absolute;
            inset: auto auto -12% -8%;
            width: 260px;
            height: 260px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(243, 203, 136, 0.16), transparent 66%);
            filter: blur(8px);
        }

        .hero-stage::after {
            content: "";
            position: absolute;
            inset: 18% 14% auto auto;
            width: 180px;
            height: 180px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(72, 227, 193, 0.16), transparent 72%);
            filter: blur(10px);
        }

        .stage-grid {
            position: absolute;
            inset: auto 8% 9% 8%;
            height: 38%;
            border-radius: 50%;
            background:
                repeating-linear-gradient(
                    90deg,
                    rgba(135, 184, 255, 0.11) 0,
                    rgba(135, 184, 255, 0.11) 1px,
                    transparent 1px,
                    transparent 32px
                ),
                repeating-linear-gradient(
                    180deg,
                    rgba(135, 184, 255, 0.08) 0,
                    rgba(135, 184, 255, 0.08) 1px,
                    transparent 1px,
                    transparent 32px
                );
            transform: rotateX(79deg) translateZ(-80px);
            transform-style: preserve-3d;
            opacity: 0.4;
        }

        .orbital-ring {
            position: absolute;
            top: 50%;
            left: 50%;
            border-radius: 50%;
            border: 1px solid rgba(135, 184, 255, 0.18);
            transform-style: preserve-3d;
            animation: orbit 15s linear infinite;
        }

        .ring-one {
            width: 280px;
            height: 280px;
            margin-top: -140px;
            margin-left: -140px;
            transform: rotateX(75deg) rotateZ(0deg);
        }

        .ring-two {
            width: 350px;
            height: 350px;
            margin-top: -175px;
            margin-left: -175px;
            border-color: rgba(72, 227, 193, 0.22);
            transform: rotateY(68deg) rotateZ(0deg);
            animation-duration: 21s;
            animation-direction: reverse;
        }

        .ring-three {
            width: 240px;
            height: 240px;
            margin-top: -120px;
            margin-left: -120px;
            border-color: rgba(243, 203, 136, 0.22);
            transform: rotateX(30deg) rotateY(60deg);
            animation-duration: 17s;
        }

        .core-sphere {
            position: absolute;
            top: 50%;
            left: 50%;
            width: 154px;
            height: 154px;
            margin-left: -77px;
            margin-top: -77px;
            border-radius: 50%;
            background:
                radial-gradient(circle at 30% 30%, rgba(255, 255, 255, 0.96), rgba(135, 184, 255, 0.38) 24%, rgba(7, 20, 34, 0.98) 74%);
            box-shadow:
                0 0 0 1px rgba(255, 255, 255, 0.12),
                0 0 0 14px rgba(72, 227, 193, 0.05),
                0 24px 80px rgba(72, 227, 193, 0.22);
            animation: sphereFloat 6s ease-in-out infinite;
            transform-style: preserve-3d;
        }

        .core-sphere::before {
            content: "";
            position: absolute;
            inset: 14px;
            border-radius: 50%;
            border: 1px solid rgba(255, 255, 255, 0.14);
        }

        .core-sphere::after {
            content: "";
            position: absolute;
            inset: auto 18px 12px 18px;
            height: 34px;
            border-radius: 50%;
            background: radial-gradient(circle, rgba(0, 0, 0, 0.32), transparent 72%);
            filter: blur(10px);
            transform: translateZ(-20px);
        }

        .core-label {
            position: absolute;
            inset: auto 50% 18px auto;
            transform: translateX(50%);
            padding: 0.32rem 0.55rem;
            border-radius: 999px;
            border: 1px solid rgba(255, 255, 255, 0.12);
            background: rgba(5, 17, 28, 0.6);
            color: var(--text);
            font-size: 0.62rem;
        }

        .scene-card {
            position: absolute;
            width: 190px;
            padding: 0.9rem 1rem;
            border-radius: 18px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            background: linear-gradient(180deg, rgba(255, 255, 255, 0.08), rgba(255, 255, 255, 0.04));
            backdrop-filter: blur(18px);
            box-shadow: 0 18px 42px rgba(0, 0, 0, 0.22);
            transform-style: preserve-3d;
        }

        .scene-card span {
            display: block;
            color: var(--muted);
            font-size: 0.66rem;
        }

        .scene-card strong {
            display: block;
            margin-top: 0.45rem;
            color: #f7fbff;
            font-size: 1.05rem;
            line-height: 1.15;
        }

        .scene-card small {
            display: block;
            margin-top: 0.32rem;
            color: var(--text-soft);
            line-height: 1.45;
        }

        .card-top {
            top: 14%;
            left: 8%;
            transform: translateZ(80px) rotateX(12deg) rotateY(-12deg);
            animation: floatCardA 7s ease-in-out infinite;
        }

        .card-side {
            top: 16%;
            right: 8%;
            transform: translateZ(110px) rotateX(10deg) rotateY(10deg);
            animation: floatCardB 8s ease-in-out infinite;
        }

        .card-bottom {
            bottom: 13%;
            right: 13%;
            transform: translateZ(90px) rotateX(-2deg) rotateY(-10deg);
            animation: floatCardC 7.4s ease-in-out infinite;
        }

        .scene-column-wrap {
            position: absolute;
            inset: auto 10% 11% 10%;
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 0.7rem;
            align-items: end;
        }

        .scene-column {
            position: relative;
            padding-top: 4.5rem;
        }

        .scene-column::before {
            content: "";
            position: absolute;
            inset: auto 0 0 0;
            height: var(--column-height);
            border-radius: 18px 18px 8px 8px;
            background:
                linear-gradient(180deg, rgba(255, 255, 255, 0.22), rgba(72, 227, 193, 0.08) 18%, rgba(72, 227, 193, 0.02) 100%);
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.08);
        }

        .scene-column span {
            position: absolute;
            bottom: calc(var(--column-height) + 0.6rem);
            left: 0;
            color: var(--muted);
            font-size: 0.7rem;
            letter-spacing: 0.08em;
            text-transform: uppercase;
        }

        .section-grid {
            display: grid;
            gap: 1rem;
        }

        .signal-grid {
            display: grid;
            grid-template-columns: repeat(3, minmax(0, 1fr));
            gap: 1rem;
        }

        .surface-card {
            position: relative;
            overflow: hidden;
            padding: 1.28rem 1.28rem 1.22rem;
            border-radius: var(--radius-lg);
            border: 1px solid var(--line);
            background:
                linear-gradient(180deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.03)),
                linear-gradient(180deg, rgba(11, 30, 48, 0.92), rgba(8, 22, 36, 0.9));
            box-shadow: var(--shadow-soft);
            backdrop-filter: blur(16px);
            animation: rise 0.75s ease both;
            transition: transform 0.22s ease, border-color 0.22s ease, box-shadow 0.22s ease;
        }

        .surface-card:hover {
            transform: translateY(-3px);
            border-color: var(--line-strong);
            box-shadow: 0 24px 64px rgba(2, 10, 18, 0.34);
        }

        .surface-card::before {
            content: "";
            position: absolute;
            inset: 0 auto auto 0;
            width: 100%;
            height: 1px;
            background: linear-gradient(90deg, rgba(255, 255, 255, 0.22), transparent);
            opacity: 0.5;
        }

        .surface-kicker {
            margin: 0;
            color: var(--muted);
            font-size: 0.72rem;
        }

        .surface-title {
            margin: 0.4rem 0 0;
            font-size: 1.95rem;
            line-height: 1;
            color: #f6fbff;
        }

        .surface-copy {
            margin: 0.55rem 0 0;
            color: var(--text-soft);
            line-height: 1.72;
            font-size: 0.93rem;
        }

        .surface-note {
            margin-top: 0.9rem;
            padding-top: 0.9rem;
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            color: var(--muted);
            line-height: 1.65;
            font-size: 0.9rem;
        }

        .signal-card {
            min-height: 178px;
        }

        .signal-value {
            margin-top: 1rem;
            color: #f5fbff;
            font-size: 1.65rem;
            line-height: 1.02;
            font-family: "Space Grotesk", sans-serif;
        }

        .signal-copy {
            margin-top: 0.45rem;
            color: var(--text-soft);
            line-height: 1.65;
        }

        .glow-mint::after,
        .glow-amber::after,
        .glow-blue::after {
            content: "";
            position: absolute;
            inset: auto -5% -35% auto;
            width: 150px;
            height: 150px;
            border-radius: 50%;
            filter: blur(18px);
            opacity: 0.55;
            pointer-events: none;
        }

        .glow-mint::after {
            background: radial-gradient(circle, rgba(72, 227, 193, 0.22), transparent 70%);
        }

        .glow-amber::after {
            background: radial-gradient(circle, rgba(243, 203, 136, 0.2), transparent 70%);
        }

        .glow-blue::after {
            background: radial-gradient(circle, rgba(135, 184, 255, 0.22), transparent 70%);
        }

        .subsection-intro {
            margin: 0 0 0.85rem;
            padding: 0.95rem 1rem;
            border-radius: 18px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            background: rgba(255, 255, 255, 0.035);
        }

        .subsection-intro span {
            display: block;
            color: var(--muted);
            font-size: 0.7rem;
        }

        .subsection-intro p {
            margin: 0.4rem 0 0;
            color: var(--text-soft);
            line-height: 1.62;
            font-size: 0.9rem;
        }

        .detail-grid {
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.75rem;
            margin-top: 1rem;
        }

        .detail-cell,
        .intel-row,
        .activity-item {
            padding: 0.85rem 0.95rem;
            border-radius: 16px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            background: rgba(255, 255, 255, 0.04);
        }

        .detail-cell span,
        .intel-row span,
        .activity-item span,
        .activity-meta span {
            display: block;
            color: var(--muted);
            font-size: 0.7rem;
            text-transform: uppercase;
            letter-spacing: 0.1em;
        }

        .detail-cell strong,
        .intel-row strong,
        .activity-item strong,
        .activity-meta strong {
            display: block;
            margin-top: 0.38rem;
            color: #f6fbff;
            font-size: 1rem;
            line-height: 1.25;
        }

        .intel-grid {
            display: grid;
            gap: 0.75rem;
            margin-top: 1rem;
        }

        .terminal-shell {
            margin-top: 1rem;
            padding: 1rem 1rem 0.95rem;
            border-radius: 18px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            background:
                radial-gradient(circle at top left, rgba(72, 227, 193, 0.1), transparent 28%),
                linear-gradient(180deg, rgba(4, 14, 24, 0.96), rgba(7, 18, 29, 0.98));
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
        }

        .terminal-title {
            color: var(--muted);
            font-size: 0.72rem;
            text-transform: uppercase;
            letter-spacing: 0.12em;
        }

        .terminal-code {
            margin: 0.75rem 0 0;
            color: #dffbff;
            font-family: "IBM Plex Mono", monospace;
            font-size: 0.82rem;
            line-height: 1.75;
            white-space: pre-wrap;
            word-break: break-word;
        }

        .check-stack,
        .activity-stack {
            display: grid;
            gap: 0.75rem;
            margin-top: 1rem;
        }

        .check-row,
        .activity-item {
            display: flex;
            justify-content: space-between;
            gap: 1rem;
            align-items: flex-start;
        }

        .check-copy,
        .activity-copy {
            margin-top: 0.18rem;
            color: var(--text-soft);
            font-size: 0.9rem;
            line-height: 1.55;
        }

        .activity-meta {
            margin-top: 0.6rem;
            display: grid;
            grid-template-columns: repeat(2, minmax(0, 1fr));
            gap: 0.55rem;
        }

        .result-card.success {
            border-color: rgba(72, 227, 193, 0.24);
            background:
                linear-gradient(180deg, rgba(72, 227, 193, 0.08), rgba(255, 255, 255, 0.03)),
                linear-gradient(180deg, rgba(11, 30, 48, 0.92), rgba(8, 22, 36, 0.9));
        }

        .result-card.error {
            border-color: rgba(255, 139, 131, 0.24);
            background:
                linear-gradient(180deg, rgba(255, 139, 131, 0.08), rgba(255, 255, 255, 0.03)),
                linear-gradient(180deg, rgba(11, 30, 48, 0.92), rgba(8, 22, 36, 0.9));
        }

        .result-title {
            margin: 0.4rem 0 0;
            font-size: 2rem;
            line-height: 1;
        }

        .result-copy {
            margin: 0.6rem 0 0;
            color: var(--text-soft);
            line-height: 1.72;
        }

        .preset-caption {
            margin-top: 0.55rem;
            color: var(--muted);
            font-size: 0.82rem;
            line-height: 1.5;
        }

        label,
        .stRadio label,
        .stSelectbox label,
        .stTextInput label,
        .stNumberInput label,
        .stToggle label {
            color: var(--text) !important;
            font-weight: 700 !important;
            font-size: 0.93rem !important;
        }

        div[data-baseweb="input"] > div,
        div[data-baseweb="select"] > div,
        [data-testid="stNumberInput"] div[data-baseweb="input"] > div {
            min-height: 3.45rem;
            border-radius: 18px;
            border: 1px solid var(--line-strong);
            background: rgba(255, 255, 255, 0.05);
            box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.04);
        }

        div[data-baseweb="input"] > div:focus-within,
        div[data-baseweb="select"] > div:focus-within,
        [data-testid="stNumberInput"] div[data-baseweb="input"] > div:focus-within {
            border-color: rgba(72, 227, 193, 0.45);
            box-shadow:
                inset 0 1px 0 rgba(255, 255, 255, 0.05),
                0 0 0 4px rgba(72, 227, 193, 0.08);
        }

        div[data-baseweb="input"] input,
        div[data-baseweb="select"] input,
        div[data-baseweb="select"] span,
        [data-testid="stNumberInput"] input {
            color: var(--text) !important;
            font-family: "Sora", sans-serif !important;
        }

        div[role="radiogroup"] {
            gap: 0.55rem;
        }

        div[role="radiogroup"] > label {
            margin-right: 0 !important;
            padding: 0.45rem 0.82rem;
            border-radius: 999px;
            border: 1px solid rgba(255, 255, 255, 0.09);
            background: rgba(255, 255, 255, 0.04);
            transition: transform 0.18s ease, border-color 0.18s ease, background 0.18s ease;
        }

        div[role="radiogroup"] > label:hover {
            transform: translateY(-1px);
            border-color: rgba(72, 227, 193, 0.26);
            background: rgba(255, 255, 255, 0.06);
        }

        div[role="radiogroup"] > label:has(input:checked) {
            border-color: transparent;
            background: linear-gradient(135deg, rgba(72, 227, 193, 0.24), rgba(135, 184, 255, 0.22));
            box-shadow: 0 14px 28px rgba(0, 0, 0, 0.16);
        }

        div[role="radiogroup"] > label:has(input:checked) p {
            color: #f8fdff !important;
        }

        .stButton > button {
            min-height: 3.45rem;
            border-radius: 18px;
            border: 1px solid rgba(255, 255, 255, 0.08);
            box-shadow: 0 18px 36px rgba(0, 0, 0, 0.18);
            font-weight: 700;
            letter-spacing: 0.02em;
            transition: transform 0.18s ease, box-shadow 0.18s ease, border-color 0.18s ease;
        }

        .stButton > button[kind="primary"] {
            background: linear-gradient(135deg, #47e1c0, #2ab69f);
            color: #031018;
            border-color: rgba(72, 227, 193, 0.18);
        }

        .stButton > button[kind="secondary"] {
            background: linear-gradient(135deg, rgba(255, 255, 255, 0.07), rgba(255, 255, 255, 0.03));
            color: var(--text);
        }

        .stButton > button:hover {
            transform: translateY(-2px);
            box-shadow: 0 22px 44px rgba(0, 0, 0, 0.22);
            border-color: rgba(135, 184, 255, 0.18);
        }

        .stButton > button:focus {
            outline: none;
            box-shadow:
                0 22px 44px rgba(0, 0, 0, 0.22),
                0 0 0 4px rgba(72, 227, 193, 0.08);
        }

        [data-testid="stExpander"] details {
            border-radius: 18px;
            border: 1px solid var(--line);
            background: rgba(255, 255, 255, 0.04);
        }

        [data-testid="stExpander"] summary {
            color: var(--text);
            font-weight: 700;
        }

        [data-testid="stJson"] {
            border-radius: 18px;
            overflow: hidden;
        }

        .stAlert {
            border-radius: 18px;
        }

        @media (max-width: 1180px) {
            .hero-grid,
            .signal-grid,
            .hero-stat-grid,
            .detail-grid {
                grid-template-columns: 1fr;
            }

            .hero-stage {
                height: 390px;
            }
        }

        @media (max-width: 840px) {
            .block-container {
                padding-left: 1rem;
                padding-right: 1rem;
            }

            .hero-shell {
                padding: 1.35rem;
            }

            .hero-stage {
                height: 320px;
            }

            .scene-card {
                width: 150px;
                padding: 0.72rem 0.82rem;
            }

            .scene-column-wrap {
                inset: auto 6% 9% 6%;
            }
        }

        @keyframes rise {
            from {
                opacity: 0;
                transform: translateY(14px);
            }
            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        @keyframes orbit {
            from {
                rotate: 0deg;
            }
            to {
                rotate: 360deg;
            }
        }

        @keyframes sphereFloat {
            0%, 100% {
                transform: translateY(0px);
            }
            50% {
                transform: translateY(-10px);
            }
        }

        @keyframes floatCardA {
            0%, 100% {
                transform: translateZ(80px) rotateX(12deg) rotateY(-12deg) translateY(0px);
            }
            50% {
                transform: translateZ(92px) rotateX(12deg) rotateY(-10deg) translateY(-8px);
            }
        }

        @keyframes floatCardB {
            0%, 100% {
                transform: translateZ(110px) rotateX(10deg) rotateY(10deg) translateY(0px);
            }
            50% {
                transform: translateZ(122px) rotateX(8deg) rotateY(8deg) translateY(-10px);
            }
        }

        @keyframes floatCardC {
            0%, 100% {
                transform: translateZ(90px) rotateX(-2deg) rotateY(-10deg) translateY(0px);
            }
            50% {
                transform: translateZ(102px) rotateX(0deg) rotateY(-8deg) translateY(-7px);
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


def apply_symbol_preset(symbol: str) -> None:
    st.session_state["symbol"] = symbol
    if st.session_state.get("order_type") != "MARKET":
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


def format_number(value: Optional[float]) -> str:
    if value is None:
        return "-"
    number = float(value)
    if number.is_integer():
        return f"{number:,.0f}"
    return f"{number:,.4f}".rstrip("0").rstrip(".")


def format_delta(current: Optional[float], reference: Optional[float]) -> str:
    if current is None or reference in (None, 0):
        return "Reference unavailable"
    delta = ((float(current) - float(reference)) / float(reference)) * 100
    sign = "+" if delta >= 0 else ""
    return f"{sign}{delta:.2f}% vs reference"


def chip(text: str, tone: str) -> str:
    return f'<span class="status-chip {tone}">{escape(text)}</span>'


def ellipsis(text: str, limit: int = 70) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def reference_price(symbol: str) -> Optional[float]:
    return SYMBOL_PRESETS.get(symbol.strip().upper())


def build_cli_command(request: OrderRequest) -> str:
    command = [
        "python",
        "cli.py",
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
    return " ".join(command)


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


def render_hero(creds_ready: bool, score: int, request: Optional[OrderRequest], error: Optional[str]) -> None:
    history = st.session_state["history"]
    symbol = request.symbol if request else st.session_state["symbol"].strip().upper()
    side = request.side if request else st.session_state["side"]
    order_type = request.order_type if request else st.session_state["order_type"]
    mode_label = "Dry Run" if request and request.dry_run else ("Live Ready" if creds_ready else "Live Locked")
    mode_tone = "chip-amber" if request and request.dry_run else ("chip-mint" if creds_ready else "chip-coral")
    validation_state = "Validated" if request else ("Attention" if error else "Drafting")
    validation_tone = "chip-mint" if request else ("chip-coral" if error else "chip-blue")
    latest_status = history[0]["status"] if history else "Idle"
    latest_pair = history[0]["symbol"] if history else symbol
    reference = reference_price(symbol)
    reference_copy = format_number(reference) if reference is not None else "Custom"
    message = (
        "Shared execution, exchange-aware validation, and cinematic 3D presentation in one testnet control surface."
    )
    if error:
        message = f"Current draft needs attention: {ellipsis(error, 110)}"

    stat_cards = "".join(
        [
            f"""
            <div class="hero-stat">
                <span>Build Readiness</span>
                <strong>{score}%</strong>
                <p>Completion score reacts to the exact fields required by the selected order type.</p>
            </div>
            """,
            f"""
            <div class="hero-stat">
                <span>Execution Lane</span>
                <strong>{escape(mode_label)}</strong>
                <p>Live orders need credentials. Dry-run mode still signs and previews the final payload.</p>
            </div>
            """,
            f"""
            <div class="hero-stat">
                <span>Session Pulse</span>
                <strong>{escape(latest_status)}</strong>
                <p>{len(history)} orders in local memory. Latest route: {escape(latest_pair)}.</p>
            </div>
            """,
        ]
    )

    hero_markup = f"""
    <section class="hero-shell">
        <div class="hero-grid">
            <div>
                <div class="hero-kicker mono">Atlas One / Binance Futures Testnet / Premium UI Bonus</div>
                <h1 class="hero-title">Atlas One</h1>
                <p class="hero-subtitle">A 3D trading deck for a Python bot that feels investment-grade, not assignment-grade.</p>
                <p class="hero-copy">{escape(message)}</p>
                <div class="hero-badge-row">
                    {chip(symbol, "chip-blue")}
                    {chip(order_type, "chip-mint")}
                    {chip(side, "chip-amber" if side == "BUY" else "chip-coral")}
                    {chip(mode_label, mode_tone)}
                    {chip(validation_state, validation_tone)}
                </div>
                <div class="hero-stat-grid">
                    {stat_cards}
                </div>
            </div>
            <div class="hero-stage">
                <div class="stage-grid"></div>
                <div class="orbital-ring ring-one"></div>
                <div class="orbital-ring ring-two"></div>
                <div class="orbital-ring ring-three"></div>
                <div class="core-sphere">
                    <div class="core-label mono">{escape(mode_label)}</div>
                </div>
                <div class="scene-card card-top">
                    <span class="mono">Primary Route</span>
                    <strong>{escape(symbol)}</strong>
                    <small>{escape(order_type)} execution path with {escape(side)} side engaged.</small>
                </div>
                <div class="scene-card card-side">
                    <span class="mono">Reference</span>
                    <strong>{escape(reference_copy)}</strong>
                    <small>Preset market anchor used to make the draft feel believable at a glance.</small>
                </div>
                <div class="scene-card card-bottom">
                    <span class="mono">Gate Status</span>
                    <strong>{escape(validation_state)}</strong>
                    <small>Exchange filters, field validation, and logging stay aligned with the CLI backend.</small>
                </div>
                <div class="scene-column-wrap">
                    <div class="scene-column" style="--column-height: 116px;">
                        <span>Readiness</span>
                    </div>
                    <div class="scene-column" style="--column-height: 158px;">
                        <span>Precision</span>
                    </div>
                    <div class="scene-column" style="--column-height: 132px;">
                        <span>Audit Trail</span>
                    </div>
                </div>
            </div>
        </div>
    </section>
    """
    st.markdown(hero_markup, unsafe_allow_html=True)


def signal_card(kicker: str, title: str, copy: str, glow_class: str) -> str:
    return f"""
    <div class="surface-card signal-card {glow_class}">
        <p class="surface-kicker mono">{escape(kicker)}</p>
        <div class="signal-value">{escape(title)}</div>
        <p class="signal-copy">{escape(copy)}</p>
    </div>
    """


def render_capability_strip() -> None:
    st.markdown(
        f"""
        <section class="signal-grid">
            {signal_card("Shared Core", "One execution engine", "The Streamlit UI and CLI both use the same request preparation and order execution workflow.", "glow-mint")}
            {signal_card("Exchange Guard", "Preflight filter checks", "Tick size, step size, and minimum notional are checked before the order is sent when metadata is available.", "glow-amber")}
            {signal_card("Telemetry", "Useful logs by default", "Sanitized requests, responses, and failures land in rotating log files instead of disappearing in the terminal.", "glow-blue")}
        </section>
        """,
        unsafe_allow_html=True,
    )


def render_section_intro(kicker: str, title: str, copy: str, note: Optional[str] = None) -> str:
    note_markup = f'<div class="surface-note">{escape(note)}</div>' if note else ""
    return f"""
    <div class="surface-card">
        <p class="surface-kicker mono">{escape(kicker)}</p>
        <h2 class="surface-title">{escape(title)}</h2>
        <p class="surface-copy">{escape(copy)}</p>
        {note_markup}
    </div>
    """


def render_quick_pairs() -> None:
    st.markdown(
        render_section_intro(
            "Hot Routes",
            "Launch from believable market anchors",
            "Preset pairs make the interface feel guided instead of empty while still leaving room for custom symbols.",
        ),
        unsafe_allow_html=True,
    )
    cols = st.columns(len(SYMBOL_PRESETS))
    for col, symbol in zip(cols, SYMBOL_PRESETS):
        with col:
            if st.button(symbol, key=f"preset_{symbol}", use_container_width=True, type="secondary"):
                apply_symbol_preset(symbol)
                st.rerun()
            st.markdown(
                f'<div class="preset-caption">Ref {escape(format_number(SYMBOL_PRESETS[symbol]))} · {escape(PAIR_STORIES[symbol])}</div>',
                unsafe_allow_html=True,
            )


def render_ticket_header(order_type: str, dry_run: bool) -> str:
    mode = "Dry-run preview active" if dry_run else "Live sandbox routing active"
    return render_section_intro(
        "Execution Ticket",
        "Build the order",
        "Every field in this form maps directly to the validated backend request object. Nothing visual is faked.",
        note=f"Current focus: {order_type}. Market orders skip price input. Stop-limit adds a trigger layer. {mode}.",
    )


def render_subsection_intro(kicker: str, copy: str) -> str:
    return f"""
    <div class="subsection-intro">
        <span class="mono">{escape(kicker)}</span>
        <p>{escape(copy)}</p>
    </div>
    """


def render_mode_note(creds_ready: bool, dry_run: bool) -> str:
    if dry_run:
        title = "Dry-run mode protects the experience."
        copy = "The ticket is still validated and signed, but no live order is sent to Binance."
        tone = "chip-amber"
    elif creds_ready:
        title = "Live sandbox mode is unlocked."
        copy = "The desk can route real Binance Futures Testnet orders with your configured credentials."
        tone = "chip-mint"
    else:
        title = "Live mode is blocked until credentials exist."
        copy = "Add BINANCE_TESTNET_API_KEY and BINANCE_TESTNET_SECRET to .env to enable live testnet execution."
        tone = "chip-coral"

    return f"""
    <div class="surface-card">
        <p class="surface-kicker mono">Execution Lane</p>
        <h2 class="surface-title">{escape(title)}</h2>
        <p class="surface-copy">{escape(copy)}</p>
        <div class="hero-badge-row" style="margin-top:0.95rem;">
            {chip("Dry Run" if dry_run else "Live", tone)}
            {chip("Shared CLI + UI Backend", "chip-blue")}
            {chip("Logs Enabled", "chip-mint")}
        </div>
    </div>
    """


def preview_card(request: Optional[OrderRequest], error: Optional[str], creds_ready: bool) -> str:
    if error:
        return f"""
        <div class="surface-card">
            <p class="surface-kicker mono">Order Preview</p>
            <h2 class="surface-title">Draft needs attention</h2>
            <p class="surface-copy">{escape(error)}</p>
            <div class="hero-badge-row" style="margin-top:0.95rem;">
                {chip("Validation Blocked", "chip-coral")}
                {chip("Dry Run Works Without Keys", "chip-amber")}
            </div>
        </div>
        """

    mode_chip = chip("Dry Run" if request and request.dry_run else "Live Testnet", "chip-amber" if request and request.dry_run else "chip-mint")
    side_chip = chip(request.side if request else "-", "chip-amber" if request and request.side == "BUY" else "chip-coral")
    creds_chip = chip("Credentials Ready" if creds_ready else "Keys Missing", "chip-mint" if creds_ready else "chip-blue")
    reference = reference_price(request.symbol) if request else None
    price_delta = format_delta(request.price, reference) if request else "Reference unavailable"

    return f"""
    <div class="surface-card">
        <p class="surface-kicker mono">Order Preview</p>
        <h2 class="surface-title">Ready to route</h2>
        <p class="surface-copy">This is the normalized request object the backend will use if you submit now.</p>
        <div class="hero-badge-row" style="margin-top:0.95rem;">
            {side_chip}
            {mode_chip}
            {creds_chip}
            {chip(price_delta, "chip-blue")}
        </div>
        <div class="detail-grid">
            <div class="detail-cell"><span>Pair</span><strong>{escape(request.symbol if request else "-")}</strong></div>
            <div class="detail-cell"><span>Order Type</span><strong>{escape(request.order_type if request else "-")}</strong></div>
            <div class="detail-cell"><span>Quantity</span><strong>{escape(format_number(request.quantity if request else None))}</strong></div>
            <div class="detail-cell"><span>Limit Price</span><strong>{escape(format_number(request.price if request else None))}</strong></div>
            <div class="detail-cell"><span>Stop Price</span><strong>{escape(format_number(request.stop_price if request else None))}</strong></div>
            <div class="detail-cell"><span>Time In Force</span><strong>{escape(request.time_in_force if request else "-")}</strong></div>
        </div>
    </div>
    """


def intelligence_card(request: Optional[OrderRequest], error: Optional[str], creds_ready: bool) -> str:
    if request is None:
        return f"""
        <div class="surface-card">
            <p class="surface-kicker mono">Execution Intelligence</p>
            <h2 class="surface-title">Waiting for a complete draft</h2>
            <p class="surface-copy">{escape(error or "Fill in the remaining fields to unlock the command preview, reference delta, and execution hints.")}</p>
        </div>
        """

    reference = reference_price(request.symbol)
    stop_relation = "-"
    if request.order_type == "STOP_LIMIT" and request.price is not None and request.stop_price is not None:
        stop_relation = "Trigger below limit" if request.stop_price < request.price else "Trigger above limit"

    intel_rows = "".join(
        [
            f"""
            <div class="intel-row">
                <span>Reference Price</span>
                <strong>{escape(format_number(reference)) if reference is not None else "Custom Pair"}</strong>
            </div>
            """,
            f"""
            <div class="intel-row">
                <span>Delta vs Reference</span>
                <strong>{escape(format_delta(request.price, reference) if request.price is not None else "Market order uses live price")}</strong>
            </div>
            """,
            f"""
            <div class="intel-row">
                <span>Trigger Geometry</span>
                <strong>{escape(stop_relation if request.order_type == "STOP_LIMIT" else "Not applicable")}</strong>
            </div>
            """,
            f"""
            <div class="intel-row">
                <span>Credential Lane</span>
                <strong>{escape("Ready for live testnet" if creds_ready else "Dry run only until keys exist")}</strong>
            </div>
            """,
        ]
    )

    return f"""
    <div class="surface-card">
        <p class="surface-kicker mono">Execution Intelligence</p>
        <h2 class="surface-title">Context around the ticket</h2>
        <p class="surface-copy">The UI adds decision support without diverging from the actual API request your bot will send.</p>
        <div class="intel-grid">
            {intel_rows}
        </div>
    </div>
    """


def command_card(request: Optional[OrderRequest], error: Optional[str]) -> str:
    if request is None:
        return f"""
        <div class="surface-card">
            <p class="surface-kicker mono">Command Mirror</p>
            <h2 class="surface-title">CLI preview unlocks when the draft validates</h2>
            <p class="surface-copy">{escape(error or "The exact command equivalent appears here once the request is complete.")}</p>
        </div>
        """

    return f"""
    <div class="surface-card">
        <p class="surface-kicker mono">Command Mirror</p>
        <h2 class="surface-title">Same request, terminal edition</h2>
        <p class="surface-copy">This keeps the premium UI grounded in the exact CLI path a reviewer can run from the repository.</p>
        <div class="terminal-shell">
            <div class="terminal-title">CLI Equivalent</div>
            <pre class="terminal-code">{escape(build_cli_command(request))}</pre>
        </div>
    </div>
    """


def result_panel(kind: str, title: str, copy: str) -> str:
    return f"""
    <div class="surface-card result-card {'success' if kind == 'success' else 'error'}">
        <p class="surface-kicker mono">{'Execution Result' if kind == 'success' else 'Execution Blocked'}</p>
        <h2 class="result-title">{escape(title)}</h2>
        <p class="result-copy">{escape(copy)}</p>
    </div>
    """


def activity_feed(history: list[dict[str, str]]) -> str:
    if not history:
        return """
        <div class="surface-card">
            <p class="surface-kicker mono">Session Activity</p>
            <h2 class="surface-title">No submissions yet</h2>
            <p class="surface-copy">Send a dry-run order and the feed turns into a polished session ledger with side, mode, and status context.</p>
        </div>
        """

    items = "".join(
        f"""
        <div class="activity-item">
            <div style="flex:1;">
                <span>Route</span>
                <strong>{escape(item['symbol'])} / {escape(item['order_type'])}</strong>
                <div class="activity-copy">{escape(item['timestamp'])} · Order #{escape(item['order_id'])}</div>
                <div class="activity-meta">
                    <div><span>Quantity</span><strong>{escape(item['quantity'])}</strong></div>
                    <div><span>Status</span><strong>{escape(item['status'])}</strong></div>
                </div>
            </div>
            <div style="display:flex; gap:0.45rem; flex-wrap:wrap; justify-content:flex-end;">
                {chip(item['side'], "chip-amber" if item['side'] == 'BUY' else "chip-coral")}
                {chip(item['mode'], "chip-amber" if item['mode'] == 'DRY RUN' else "chip-mint")}
            </div>
        </div>
        """
        for item in history[:6]
    )
    return f"""
    <div class="surface-card">
        <p class="surface-kicker mono">Session Activity</p>
        <h2 class="surface-title">Recent routes</h2>
        <p class="surface-copy">Local session memory turns this UI into a believable desk instead of a one-shot form.</p>
        <div class="activity-stack">
            {items}
        </div>
    </div>
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


def build_request_preview() -> tuple[Optional[OrderRequest], Optional[str]]:
    try:
        request = prepare_order_request(
            symbol=st.session_state["symbol"],
            side=st.session_state["side"],
            order_type=st.session_state["order_type"],
            quantity=st.session_state["quantity"],
            price=st.session_state["price"],
            stop_price=st.session_state["stop_price"],
            time_in_force=st.session_state["time_in_force"],
            dry_run=st.session_state["dry_run"],
            validate_exchange_metadata=True,
        )
        return request, None
    except ValueError as exc:
        return None, str(exc)


def main() -> None:
    bootstrap_state()
    inject_styles()

    creds_ready = credentials_ready()
    preview_request, preview_error = build_request_preview()
    score = completion_score(
        st.session_state["order_type"],
        st.session_state["symbol"],
        st.session_state["quantity"],
        st.session_state["price"],
        st.session_state["stop_price"],
    )

    render_hero(creds_ready, score, preview_request, preview_error)
    st.markdown('<div class="space-lg"></div>', unsafe_allow_html=True)
    render_capability_strip()
    st.markdown('<div class="space-lg"></div>', unsafe_allow_html=True)
    render_quick_pairs()

    st.markdown('<div class="space-xl"></div>', unsafe_allow_html=True)
    left, right = st.columns([1.02, 0.98], gap="large")

    with left:
        st.markdown(
            render_ticket_header(st.session_state["order_type"], st.session_state["dry_run"]),
            unsafe_allow_html=True,
        )
        st.markdown(
            render_subsection_intro(
                "Route Design",
                "Set the pair, side, and order type first. The rest of the interface adapts around that trading intent.",
            ),
            unsafe_allow_html=True,
        )

        st.text_input(
            "Symbol",
            key="symbol",
            placeholder="BTCUSDT",
            help="Binance Futures symbol ending in USDT or BUSD.",
        )

        top_row = st.columns([1, 1], gap="large")
        with top_row[0]:
            st.radio("Side", options=["BUY", "SELL"], horizontal=True, key="side")
        with top_row[1]:
            st.selectbox("Order Type", options=["MARKET", "LIMIT", "STOP_LIMIT"], key="order_type")

        st.markdown(
            render_subsection_intro(
                "Pricing Geometry",
                "Market orders skip pricing, limit orders require price, and stop-limit orders add a trigger layer.",
            ),
            unsafe_allow_html=True,
        )

        middle_row = st.columns([1, 1], gap="large")
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

        lower_row = st.columns([1, 1], gap="large")
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

        st.markdown(
            render_subsection_intro(
                "Execution Controls",
                "Keep dry-run on for a safe demo or turn it off when your Binance Futures Testnet credentials are ready.",
            ),
            unsafe_allow_html=True,
        )

        st.toggle(
            "Dry-run mode",
            key="dry_run",
            help="When enabled, the desk validates and previews execution without sending a live API call.",
        )

        action_cols = st.columns([1.45, 1], gap="large")
        submit_clicked = action_cols[0].button("Submit Order", use_container_width=True, type="primary")
        reset_clicked = action_cols[1].button("Reset Form", use_container_width=True, type="secondary")

        if reset_clicked:
            reset_ticket()
            st.rerun()

        st.markdown('<div class="space-sm"></div>', unsafe_allow_html=True)
        st.markdown(render_mode_note(creds_ready, st.session_state["dry_run"]), unsafe_allow_html=True)

    with right:
        st.markdown(preview_card(preview_request, preview_error, creds_ready), unsafe_allow_html=True)
        st.markdown('<div class="space-sm"></div>', unsafe_allow_html=True)
        st.markdown(intelligence_card(preview_request, preview_error, creds_ready), unsafe_allow_html=True)
        st.markdown('<div class="space-sm"></div>', unsafe_allow_html=True)
        st.markdown(command_card(preview_request, preview_error), unsafe_allow_html=True)

    if submit_clicked:
        try:
            request = preview_request or prepare_order_request(
                symbol=st.session_state["symbol"],
                side=st.session_state["side"],
                order_type=st.session_state["order_type"],
                quantity=st.session_state["quantity"],
                price=st.session_state["price"],
                stop_price=st.session_state["stop_price"],
                time_in_force=st.session_state["time_in_force"],
                dry_run=st.session_state["dry_run"],
                validate_exchange_metadata=True,
            )
            with st.spinner("Routing through the execution deck..."):
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

    st.markdown('<div class="space-xl"></div>', unsafe_allow_html=True)
    lower_left, lower_right = st.columns([0.98, 1.02], gap="large")

    feedback = st.session_state["feedback"]
    last_submission = st.session_state["last_submission"]

    with lower_left:
        st.markdown(
            render_section_intro(
                "Response Surface",
                "Execution feedback",
                "The latest backend outcome stays visible here so the UI feels persistent and reviewer-friendly.",
            ),
            unsafe_allow_html=True,
        )

        if feedback:
            st.markdown(
                result_panel(feedback["kind"], feedback["title"], feedback["copy"]),
                unsafe_allow_html=True,
            )
            if last_submission:
                with st.expander("View normalized request and response"):
                    st.json(last_submission)
        else:
            st.markdown(
                """
                <div class="surface-card">
                    <p class="surface-kicker mono">Awaiting Submission</p>
                    <h2 class="surface-title">Nothing has been routed yet</h2>
                    <p class="surface-copy">Send a dry-run order first and this area turns into the persistent result surface for the session.</p>
                </div>
                """,
                unsafe_allow_html=True,
            )

    with lower_right:
        st.markdown(activity_feed(st.session_state["history"]), unsafe_allow_html=True)


if __name__ == "__main__":
    main()
