import base64
import datetime as dt
import io
import logging
import random
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import spacy
import streamlit as st
import streamlit.components.v1 as components
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfinterp import PDFPageInterpreter, PDFResourceManager
from pdfminer.pdfpage import PDFPage
from PIL import Image
from streamlit_tags import st_tags

from Courses import (
    android_course,
    ds_course,
    interview_videos,
    ios_course,
    resume_videos,
    uiux_course,
    web_course,
)

logging.getLogger("streamlit.runtime.scriptrunner_utils.script_run_context").setLevel(logging.ERROR)

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "Uploaded_Resumes"
DB_PATH = BASE_DIR / "resume_data.db"


def in_streamlit_runtime():
    try:
        from streamlit.runtime.scriptrunner import get_script_run_ctx

        return get_script_run_ctx() is not None
    except Exception:
        return False


if in_streamlit_runtime():
    st.set_page_config(page_title="Smart Resume Analyzer", page_icon="📄", layout="wide")

# ---------------------------
# UI Theme and Layout Helpers
# ---------------------------
def inject_custom_css():
    st.markdown(
        """
        <style>
        :root {
            --bg-main: #070b18;
            --bg-panel: rgba(15, 19, 38, 0.70);
            --bg-card: rgba(18, 24, 47, 0.72);
            --line-soft: rgba(125, 92, 255, 0.24);
            --line-strong: rgba(92, 225, 230, 0.42);
            --text-main: #f5f7ff;
            --text-soft: #a9b3d1;
            --pink: #ff4fd8;
            --purple: #8a5cff;
            --blue: #4ea8ff;
            --cyan: #62f4ff;
            --success: #42f5b9;
            --shadow-glow: 0 0 0 1px rgba(131, 102, 255, 0.10), 0 14px 50px rgba(12, 17, 36, 0.65);
        }

        .stApp {
            background:
                radial-gradient(circle at 12% 18%, rgba(122, 76, 255, 0.18), transparent 18%),
                radial-gradient(circle at 88% 12%, rgba(78, 168, 255, 0.18), transparent 20%),
                radial-gradient(circle at 82% 42%, rgba(255, 79, 216, 0.10), transparent 18%),
                linear-gradient(180deg, #050815 0%, #090d1f 36%, #060912 100%);
            color: var(--text-main);
        }

        .main .block-container {
            max-width: 1240px;
            padding-top: 2rem;
            padding-bottom: 3rem;
        }

        [data-testid="stSidebar"] {
            background:
                linear-gradient(180deg, rgba(13, 17, 33, 0.96), rgba(10, 14, 26, 0.94)),
                radial-gradient(circle at top left, rgba(255, 79, 216, 0.10), transparent 28%);
            border-right: 1px solid rgba(138, 92, 255, 0.25);
        }

        [data-testid="stSidebar"] .block-container {
            padding-top: 1.2rem;
        }

        h1, h2, h3, h4, h5, h6, label, span, div {
            color: var(--text-main);
        }

        [data-testid="stMarkdownContainer"] p {
            color: var(--text-soft);
        }

        .hero-shell {
            position: relative;
            overflow: hidden;
            padding: 2.6rem 2rem 2.2rem 2rem;
            border-radius: 28px;
            border: 1px solid var(--line-soft);
            background:
                linear-gradient(135deg, rgba(21, 27, 53, 0.92), rgba(9, 13, 27, 0.76)),
                radial-gradient(circle at top right, rgba(78, 168, 255, 0.15), transparent 26%);
            box-shadow: var(--shadow-glow);
            text-align: center;
            backdrop-filter: blur(18px);
            margin-bottom: 1.25rem;
        }

        .hero-shell::before,
        .hero-shell::after {
            content: "";
            position: absolute;
            border-radius: 999px;
            filter: blur(12px);
            opacity: 0.75;
        }

        .hero-shell::before {
            width: 220px;
            height: 220px;
            top: -60px;
            right: -40px;
            background: rgba(255, 79, 216, 0.16);
        }

        .hero-shell::after {
            width: 180px;
            height: 180px;
            left: -50px;
            bottom: -50px;
            background: rgba(78, 168, 255, 0.14);
        }

        .hero-badge {
            display: inline-block;
            padding: 0.45rem 0.9rem;
            border-radius: 999px;
            border: 1px solid rgba(98, 244, 255, 0.30);
            background: rgba(98, 244, 255, 0.08);
            color: #dffcff;
            font-size: 0.86rem;
            letter-spacing: 0.04em;
            margin-bottom: 1rem;
        }

        .hero-title {
            margin: 0;
            font-size: clamp(2.4rem, 5vw, 4.3rem);
            line-height: 1.02;
            font-weight: 800;
            background: linear-gradient(90deg, #72b5ff 0%, #8a5cff 45%, #ff6adf 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .hero-subtitle {
            max-width: 760px;
            margin: 0.9rem auto 0;
            font-size: 1.06rem;
            line-height: 1.8;
            color: var(--text-soft);
        }

        .hero-pills {
            display: flex;
            justify-content: center;
            gap: 0.8rem;
            flex-wrap: wrap;
            margin-top: 1.2rem;
        }

        .hero-pill {
            padding: 0.55rem 0.9rem;
            border-radius: 999px;
            background: rgba(255, 255, 255, 0.04);
            border: 1px solid rgba(255, 255, 255, 0.08);
            color: #d8def4;
            font-size: 0.92rem;
        }

        .feature-grid {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 1rem;
            margin: 1.3rem 0 1.5rem;
        }

        .feature-card,
        .glass-panel,
        .stats-card {
            position: relative;
            overflow: hidden;
            border-radius: 24px;
            border: 1px solid var(--line-soft);
            background: linear-gradient(180deg, rgba(18, 24, 47, 0.82), rgba(12, 16, 31, 0.74));
            box-shadow: var(--shadow-glow);
            backdrop-filter: blur(16px);
            transition: transform 0.25s ease, border-color 0.25s ease, box-shadow 0.25s ease;
        }

        .feature-card:hover,
        .glass-panel:hover,
        .stats-card:hover {
            transform: translateY(-4px) scale(1.01);
            border-color: var(--line-strong);
            box-shadow: 0 0 0 1px rgba(98, 244, 255, 0.14), 0 18px 45px rgba(17, 23, 46, 0.8);
        }

        .feature-card {
            padding: 1.15rem 1.05rem;
            min-height: 176px;
        }

        .feature-icon {
            width: 52px;
            height: 52px;
            display: grid;
            place-items: center;
            border-radius: 18px;
            margin-bottom: 0.85rem;
            font-size: 1.55rem;
            background: linear-gradient(135deg, rgba(255, 79, 216, 0.18), rgba(78, 168, 255, 0.18));
            box-shadow: 0 0 24px rgba(138, 92, 255, 0.18);
        }

        .feature-title {
            margin: 0 0 0.4rem;
            font-size: 1.08rem;
            font-weight: 700;
            color: var(--text-main);
        }

        .feature-copy {
            margin: 0;
            font-size: 0.94rem;
            line-height: 1.65;
            color: var(--text-soft);
        }

        .section-title {
            margin: 1rem 0 0.75rem;
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--text-main);
        }

        .section-subtitle {
            margin-top: -0.2rem;
            margin-bottom: 1rem;
            color: var(--text-soft);
            font-size: 0.95rem;
        }

        .glass-panel {
            padding: 1.25rem 1.25rem 1rem;
            margin-bottom: 1rem;
        }

        .upload-panel {
            padding: 1.3rem;
        }

        .upload-shell {
            border-radius: 22px;
            padding: 1.5rem 1.4rem 1.2rem;
            border: 1.5px dashed rgba(138, 92, 255, 0.55);
            background: linear-gradient(180deg, rgba(20, 24, 48, 0.85), rgba(16, 20, 38, 0.64));
            box-shadow: inset 0 0 0 1px rgba(98, 244, 255, 0.05), 0 0 35px rgba(138, 92, 255, 0.10);
            transition: border-color 0.2s ease, box-shadow 0.2s ease;
        }

        .upload-shell:hover {
            border-color: rgba(98, 244, 255, 0.72);
            box-shadow: inset 0 0 0 1px rgba(98, 244, 255, 0.08), 0 0 42px rgba(98, 244, 255, 0.12);
        }

        .upload-title {
            margin: 0 0 0.35rem;
            font-size: 1.25rem;
            font-weight: 700;
            color: var(--text-main);
        }

        .upload-copy {
            margin: 0;
            color: var(--text-soft);
            line-height: 1.65;
        }

        [data-testid="stFileUploader"] > section {
            border-radius: 20px !important;
            border: 2px dashed rgba(138, 92, 255, 0.6) !important;
            background: rgba(12, 17, 34, 0.35) !important;
            transition: all 0.3s ease !important;
            position: relative;
            z-index: 1;
        }

        [data-testid="stFileUploader"] > section:hover,
        [data-testid="stFileUploader"] > section.active {
            border-color: rgba(98, 244, 255, 0.9) !important;
            box-shadow: inset 0 0 0 1px rgba(98, 244, 255, 0.15), 0 0 42px rgba(98, 244, 255, 0.2) !important;
            background: rgba(98, 244, 255, 0.08) !important;
        }

        [data-testid="stFileUploader"] > section::before {
            content: 'Drop your resume here ✨';
            position: absolute;
            top: 50%; left: 50%;
            transform: translate(-50%, -50%);
            font-weight: 700;
            font-size: 1.2rem;
            color: rgba(98, 244, 255, 0.9);
            opacity: 0;
            pointer-events: none;
            transition: opacity 0.3s ease;
            z-index: -1;
        }

        [data-testid="stFileUploader"] > section:hover::before {
            opacity: 1;
            animation: pulse-op 1.5s infinite;
        }

        @keyframes pulse-op {
            0% { opacity: 0.6; text-shadow: 0 0 5px rgba(98, 244, 255, 0.4); }
            50% { opacity: 1; text-shadow: 0 0 20px rgba(98, 244, 255, 0.9); }
            100% { opacity: 0.6; text-shadow: 0 0 5px rgba(98, 244, 255, 0.4); }
        }

        [data-testid="stFileUploader"] small,
        [data-testid="stFileUploader"] span {
            color: var(--text-soft) !important;
            transition: opacity 0.3s ease;
        }

        [data-testid="stFileUploader"] > section:hover small,
        [data-testid="stFileUploader"] > section:hover span {
            opacity: 0.1; /* Hide original text slightly to emphasize the Drop text */
        }

        .stButton > button,
        [data-testid="stBaseButton-secondary"],
        [data-testid="baseButton-secondary"] {
            border-radius: 14px !important;
            border: 1px solid rgba(114, 181, 255, 0.22) !important;
            background: linear-gradient(90deg, rgba(255, 79, 216, 0.88), rgba(78, 168, 255, 0.88)) !important;
            color: white !important;
            font-weight: 700 !important;
            box-shadow: 0 10px 30px rgba(93, 77, 255, 0.20);
            transition: transform 0.2s ease, box-shadow 0.2s ease, filter 0.2s ease;
        }

        .stButton > button:hover,
        [data-testid="stBaseButton-secondary"]:hover,
        [data-testid="baseButton-secondary"]:hover {
            transform: translateY(-2px) scale(1.01);
            filter: brightness(1.05);
            box-shadow: 0 15px 34px rgba(78, 168, 255, 0.24);
        }

        [data-baseweb="select"] > div,
        [data-baseweb="input"] > div,
        .stTextInput input {
            border-radius: 14px !important;
            background: rgba(12, 17, 34, 0.78) !important;
            border: 1px solid rgba(138, 92, 255, 0.22) !important;
            color: var(--text-main) !important;
        }

        .stats-row {
            display: grid;
            grid-template-columns: repeat(4, minmax(0, 1fr));
            gap: 1rem;
            margin-bottom: 1rem;
        }

        .stats-card {
            padding: 1rem 1rem 0.85rem;
        }

        .stats-label {
            color: var(--text-soft);
            font-size: 0.86rem;
            text-transform: uppercase;
            letter-spacing: 0.08em;
            margin-bottom: 0.45rem;
        }

        .stats-value {
            font-size: 1.15rem;
            font-weight: 700;
            color: #ffffff;
        }

        .subtle-card {
            border-radius: 20px;
            border: 1px solid rgba(138, 92, 255, 0.18);
            background: rgba(16, 21, 40, 0.72);
            padding: 1rem 1.1rem;
            margin-bottom: 0.85rem;
        }

        .section-chip {
            display: inline-block;
            padding: 0.35rem 0.7rem;
            border-radius: 999px;
            border: 1px solid rgba(98, 244, 255, 0.22);
            background: rgba(98, 244, 255, 0.06);
            color: #dffcff;
            font-size: 0.84rem;
            margin-bottom: 0.65rem;
        }

        [data-testid="stProgressBar"] > div > div {
            background: linear-gradient(90deg, #ff4fd8, #8a5cff, #4ea8ff) !important;
        }

        .sidebar-brand {
            padding: 1rem 1rem 1.15rem;
            border-radius: 22px;
            border: 1px solid rgba(138, 92, 255, 0.22);
            background: linear-gradient(180deg, rgba(20, 24, 48, 0.80), rgba(13, 17, 32, 0.72));
            box-shadow: var(--shadow-glow);
            margin-bottom: 1.1rem;
            text-align: left;
        }

        .sidebar-brand-title {
            font-size: 1.35rem;
            font-weight: 800;
            margin: 0;
            background: linear-gradient(90deg, #ffffff, #82b6ff 40%, #ff6adf 100%);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
        }

        .sidebar-brand-copy {
            margin-top: 0.45rem;
            color: var(--text-soft);
            font-size: 0.92rem;
            line-height: 1.65;
        }

        .sidebar-note {
            padding: 0.95rem 1rem;
            border-radius: 18px;
            border: 1px solid rgba(98, 244, 255, 0.14);
            background: rgba(10, 14, 28, 0.72);
            margin-top: 1rem;
            color: var(--text-soft);
            line-height: 1.6;
        }

        @media (max-width: 980px) {
            .feature-grid,
            .stats-row {
                grid-template-columns: repeat(2, minmax(0, 1fr));
            }
        }

        @media (max-width: 640px) {
            .feature-grid,
            .stats-row {
                grid-template-columns: 1fr;
            }

            .hero-shell {
                padding: 2rem 1.1rem;
            }
        }

        @keyframes pulse-glow {
            0% { box-shadow: 0 0 0 0 rgba(78, 168, 255, 0.4); }
            70% { box-shadow: 0 0 0 20px rgba(78, 168, 255, 0); }
            100% { box-shadow: 0 0 0 0 rgba(78, 168, 255, 0); }
        }
        @keyframes blob-bounce {
            0% { transform: scale(1) translate(0, 0); }
            50% { transform: scale(1.1) translate(20px, -20px); }
            100% { transform: scale(1) translate(0, 0); }
        }
        @keyframes fade-in-scroll {
            from { opacity: 0; transform: translateY(20px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .hero-shell::before {
            animation: blob-bounce 8s infinite alternate ease-in-out;
        }
        .hero-shell::after {
            animation: blob-bounce 10s infinite alternate-reverse ease-in-out;
        }
        .ai-insight-card {
            background: rgba(20, 24, 48, 0.7);
            border: 1px solid rgba(138, 92, 255, 0.3);
            border-radius: 16px;
            padding: 1.2rem;
            margin-bottom: 1rem;
            backdrop-filter: blur(10px);
            transition: all 0.3s ease;
            animation: fade-in-scroll 0.6s ease-out forwards;
        }
        .ai-insight-card:hover {
            transform: translateY(-5px);
            box-shadow: 0 10px 25px rgba(138, 92, 255, 0.2);
            border-color: var(--pink);
        }
        .action-card {
            border-left: 4px solid var(--blue);
            padding: 1rem;
            background: rgba(12, 17, 34, 0.8);
            border-radius: 0 12px 12px 0;
            margin-bottom: 0.8rem;
            transition: all 0.2s ease;
        }
        .action-card:hover {
            background: rgba(25, 30, 50, 0.9);
            border-left-color: var(--cyan);
            transform: scale(1.02);
        }
        .sticky-summary {
            position: sticky;
            top: 20px;
            z-index: 100;
            background: rgba(10, 14, 26, 0.85);
            backdrop-filter: blur(12px);
            border: 1px solid var(--line-soft);
            border-radius: 12px;
            padding: 1rem;
            display: flex;
            justify-content: space-around;
            align-items: center;
            box-shadow: 0 10px 30px rgba(0,0,0,0.5);
            margin-bottom: 1.5rem;
        }
        .summary-item {
            text-align: center;
        }
        .summary-label {
            font-size: 0.8rem;
            color: var(--text-soft);
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        .summary-value {
            font-size: 1.2rem;
            font-weight: 800;
            color: white;
        }
        .summary-value.score-green { color: var(--success); text-shadow: 0 0 10px rgba(66, 245, 185, 0.5); }
        .summary-value.score-yellow { color: #ffeb3b; text-shadow: 0 0 10px rgba(255, 235, 59, 0.5); }
        .summary-value.score-red { color: #ff5252; text-shadow: 0 0 10px rgba(255, 82, 82, 0.5); }
        .action-button {
            display: inline-block;
            padding: 0.6rem 1.2rem;
            border-radius: 12px;
            font-weight: bold;
            font-size: 0.9rem;
            text-decoration: none;
            color: white !important;
            background: linear-gradient(90deg, var(--purple), var(--blue));
            border: 1px solid rgba(255,255,255,0.2);
            transition: all 0.3s ease;
            text-align: center;
            cursor: pointer;
            margin-left: 10px;
        }
        .action-button:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 20px rgba(138, 92, 255, 0.4);
            color: white !important;
            text-decoration: none;
        }
        
        .ats-circle-container {
            display: flex;
            justify-content: center;
            align-items: center;
            margin: 2rem 0;
        }
        .score-circle {
            width: 250px;
            height: 250px;
            border-radius: 50%;
            display: flex;
            flex-direction: column;
            justify-content: center;
            align-items: center;
            background: #0f1326;
            position: relative;
            box-shadow: inset 0 0 20px rgba(0,0,0,0.5);
        }
        .score-circle::before {
            content: "";
            position: absolute;
            inset: -6px;
            border-radius: 50%;
            background: conic-gradient(var(--score-color) var(--score-angle), rgba(255,255,255,0.05) 0);
            z-index: -1;
            transition: --score-angle 1.5s ease-out;
        }
        .score-circle::after {
            content: "";
            position: absolute;
            inset: 8px;
            background: #0f1326;
            border-radius: 50%;
            z-index: -1;
        }
        .score-text {
            font-size: 5rem;
            font-weight: 900;
            line-height: 1;
            color: white;
            text-shadow: 0 0 15px var(--score-color);
        }
        .score-label {
            font-size: 1.2rem;
            color: var(--text-soft);
            text-transform: uppercase;
            letter-spacing: 2px;
            margin-top: 5px;
        }
        .pulse-green { animation: pulse-glow-green 2s infinite; --score-color: var(--success); }
        .pulse-yellow { animation: pulse-glow-yellow 2s infinite; --score-color: #ffeb3b; }
        .pulse-red { animation: pulse-glow-red 2s infinite; --score-color: #ff5252; }

        @keyframes pulse-glow-green { 0% { box-shadow: 0 0 0 0 rgba(66, 245, 185, 0.4); } 70% { box-shadow: 0 0 0 30px rgba(66, 245, 185, 0); } 100% { box-shadow: 0 0 0 0 rgba(66, 245, 185, 0); } }
        @keyframes pulse-glow-yellow { 0% { box-shadow: 0 0 0 0 rgba(255, 235, 59, 0.4); } 70% { box-shadow: 0 0 0 30px rgba(255, 235, 59, 0); } 100% { box-shadow: 0 0 0 0 rgba(255, 235, 59, 0); } }
        @keyframes pulse-glow-red { 0% { box-shadow: 0 0 0 0 rgba(255, 82, 82, 0.4); } 70% { box-shadow: 0 0 0 30px rgba(255, 82, 82, 0); } 100% { box-shadow: 0 0 0 0 rgba(255, 82, 82, 0); } }
        </style>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_brand():
    st.sidebar.markdown(
        """
        <div class="sidebar-brand">
            <div class="section-chip">AI Career Toolkit</div>
            <p class="sidebar-brand-title">Resume Analyzer</p>
            <p class="sidebar-brand-copy">
                Premium resume insights with ATS scoring, skill extraction, role prediction, and improvement guidance.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_sidebar_note():
    st.sidebar.markdown(
        """
        <div class="sidebar-note">
            <strong style="color:#ffffff;">Navigation</strong><br>
            Use the sidebar to switch between the candidate flow and the admin dashboard. All backend logic stays unchanged.
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_hero_section(mode_label):
    st.markdown(
        f"""
        <div class="hero-shell">
            <div class="hero-badge">AI-powered insights • Premium interface</div>
            <h1 class="hero-title">Smart Resume Analyzer 🚀</h1>
            <p class="hero-subtitle">
                Intelligent resume analysis for <strong style="color:#ffffff;">{mode_label}</strong> workflows.
                Upload your resume, extract skills, review ATS-aligned feedback, and explore job-fit signals in a polished AI dashboard.
            </p>
            <div class="hero-pills">
                <span class="hero-pill">ATS Score</span>
                <span class="hero-pill">Resume Feedback</span>
                <span class="hero-pill">Job Match</span>
                <span class="hero-pill">Skills Extraction</span>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_feature_cards():
    st.markdown(
        """
        <div class="feature-grid">
            <div class="feature-card">
                <div class="feature-icon">📈</div>
                <h3 class="feature-title">ATS Score</h3>
                <p class="feature-copy">Understand how resume structure, essentials, and relevance contribute to a stronger screening score.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">🧠</div>
                <h3 class="feature-title">Resume Feedback</h3>
                <p class="feature-copy">Get explainable score breakdowns, section quality signals, and actionable improvement cues.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">🎯</div>
                <h3 class="feature-title">Job Match</h3>
                <p class="feature-copy">Predict likely role alignment from technologies, domain terms, and profile-specific resume content.</p>
            </div>
            <div class="feature-card">
                <div class="feature-icon">🛠️</div>
                <h3 class="feature-title">Skills Extraction</h3>
                <p class="feature-copy">Automatically identify technical capabilities and compare them against recommended skills.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_upload_intro():
    st.markdown(
        """
        <div class="glass-panel upload-panel">
            <div class="section-chip">Upload Zone</div>
            <div class="upload-shell">
                <h3 class="upload-title">Drop in your resume PDF</h3>
                <p class="upload-copy">
                    Securely upload a single PDF to analyze candidate details, experience depth, ATS score, skill relevance, and role prediction.
                </p>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_section_heading(title, subtitle=""):
    subtitle_html = f'<p class="section-subtitle">{subtitle}</p>' if subtitle else ""
    st.markdown(
        f"""
        <div>
            <div class="section-title">{title}</div>
            {subtitle_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


SKILL_TAXONOMY = {
    "Cyber Security": {
        "keywords": {
            "cyber security",
            "cybersecurity",
            "information security",
            "network security",
            "ethical hacking",
            "penetration testing",
            "penetration tester",
            "vulnerability assessment",
            "vulnerability management",
            "soc",
            "siem",
            "splunk",
            "wireshark",
            "nmap",
            "metasploit",
            "kali linux",
            "incident response",
            "firewall",
            "ids",
            "ips",
            "security operations",
            "security analyst",
            "cryptography",
            "owasp",
        },
        "recommended_skills": [
            "Network Security",
            "Penetration Testing",
            "SIEM",
            "Incident Response",
            "OWASP",
            "Vulnerability Assessment",
        ],
        "courses": ds_course,
    },
    "Backend Development": {
        "keywords": {
            "backend",
            "backend development",
            "backend developer",
            "api",
            "rest api",
            "fastapi",
            "django",
            "flask",
            "spring",
            "spring boot",
            "express",
            "node.js",
            "node",
            "java",
            "python",
            "sql",
            "mysql",
            "postgresql",
            "mongodb",
            "database design",
            "microservices",
            "authentication",
            "authorization",
            "redis",
        },
        "recommended_skills": [
            "REST API Design",
            "Database Design",
            "Authentication and Authorization",
            "Microservices",
            "SQL",
            "System Design",
        ],
        "courses": web_course,
    },
    "Frontend Development": {
        "keywords": {
            "frontend",
            "frontend development",
            "frontend developer",
            "html",
            "css",
            "javascript",
            "typescript",
            "react",
            "next.js",
            "nextjs",
            "angular",
            "vue",
            "tailwind",
            "bootstrap",
            "redux",
            "responsive design",
            "ui development",
            "web design",
        },
        "recommended_skills": [
            "React",
            "TypeScript",
            "Responsive Design",
            "State Management",
            "UI Engineering",
            "Accessibility",
        ],
        "courses": web_course,
    },
    "Full Stack Development": {
        "keywords": {
            "full stack",
            "full stack development",
            "full stack developer",
            "mern",
            "mean",
            "react",
            "node.js",
            "node",
            "express",
            "mongodb",
            "sql",
            "mysql",
            "postgresql",
            "django",
            "flask",
            "rest api",
            "frontend",
            "backend",
            "web application",
            "javascript",
            "typescript",
        },
        "recommended_skills": [
            "Frontend and Backend Integration",
            "REST API Design",
            "Database Design",
            "Authentication",
            "React",
            "Deployment",
        ],
        "courses": web_course,
    },
    "DevOps and Cloud": {
        "keywords": {
            "aws",
            "amazon web services",
            "gcp",
            "google cloud",
            "azure",
            "devops",
            "docker",
            "kubernetes",
            "jenkins",
            "ci/cd",
            "github actions",
            "terraform",
            "ansible",
            "linux",
            "shell scripting",
            "bash",
            "ec2",
            "s3",
            "lambda",
            "vpc",
            "cloud nat",
            "iam",
            "serverless",
            "nginx",
            "monitoring",
        },
        "recommended_skills": [
            "Docker",
            "Kubernetes",
            "CI/CD",
            "Terraform",
            "Linux",
            "Cloud Architecture",
        ],
        "courses": web_course,
    },
    "Data Science": {
        "keywords": {
            "python",
            "pandas",
            "numpy",
            "machine learning",
            "deep learning",
            "tensorflow",
            "pytorch",
            "sql",
            "power bi",
            "tableau",
            "statistics",
            "data analysis",
            "data science",
            "nlp",
            "scikit-learn",
            "opencv",
        },
        "recommended_skills": [
            "Machine Learning",
            "Data Analysis",
            "SQL",
            "Statistics",
            "Power BI",
            "Tableau",
        ],
        "courses": ds_course,
    },
    "Web Development": {
        "keywords": {
            "html",
            "css",
            "javascript",
            "typescript",
            "react",
            "node.js",
            "node",
            "express",
            "mongodb",
            "django",
            "flask",
            "bootstrap",
            "tailwind",
            "rest api",
            "web development",
        },
        "recommended_skills": [
            "React",
            "Node.js",
            "REST API Design",
            "MongoDB",
            "TypeScript",
            "Responsive Design",
        ],
        "courses": web_course,
    },
    "Android Development": {
        "keywords": {
            "java",
            "kotlin",
            "android",
            "android studio",
            "firebase",
            "xml",
            "jetpack compose",
            "room",
            "retrofit",
            "gradle",
        },
        "recommended_skills": [
            "Kotlin",
            "Android Studio",
            "Firebase",
            "Jetpack Compose",
            "REST Integration",
        ],
        "courses": android_course,
    },
    "iOS Development": {
        "keywords": {
            "swift",
            "swiftui",
            "ios",
            "xcode",
            "uikit",
            "core data",
            "cocoapods",
        },
        "recommended_skills": [
            "SwiftUI",
            "UIKit",
            "Xcode",
            "Core Data",
            "App Architecture",
        ],
        "courses": ios_course,
    },
    "UI/UX": {
        "keywords": {
            "figma",
            "adobe xd",
            "photoshop",
            "illustrator",
            "wireframing",
            "prototyping",
            "user research",
            "ui design",
            "ux design",
            "design systems",
        },
        "recommended_skills": [
            "Wireframing",
            "Prototyping",
            "User Research",
            "Design Systems",
            "Usability Testing",
        ],
        "courses": uiux_course,
    },
}

ALL_SKILLS = sorted(
    {
        skill
        for field_data in SKILL_TAXONOMY.values()
        for skill in (field_data["keywords"] | set(field_data["recommended_skills"]))
    }
)

NAME_STOP_WORDS = {
    "resume",
    "curriculum",
    "vitae",
    "profile",
    "developer",
    "engineer",
    "analyst",
    "student",
    "intern",
    "contact",
    "summary",
    "objective",
    "education",
    "experience",
    "projects",
    "skills",
    "certifications",
}

EDUCATION_KEYWORDS = (
    "b.tech",
    "b.e",
    "bachelor",
    "master",
    "m.tech",
    "mca",
    "bca",
    "mba",
    "phd",
    "diploma",
    "college",
    "university",
    "school",
)

EXPERIENCE_KEYWORDS = (
    "intern",
    "internship",
    "engineer",
    "developer",
    "analyst",
    "consultant",
    "manager",
    "lead",
    "specialist",
)

EMAIL_PATTERN = re.compile(r"(?i)\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b")
PHONE_PATTERN = re.compile(
    r"(?:(?:\+?\d{1,3}[\s\-().]*)?(?:\d[\s\-().]*){10,14})"
)
URL_PATTERN = re.compile(r"(?i)(https?://|www\.)")

SECTION_ALIASES = {
    "education": {"education", "academic background", "qualification", "qualifications"},
    "experience": {
        "experience",
        "work experience",
        "professional experience",
        "internship",
        "internships",
        "internship experience",
    },
    "projects": {"projects", "academic projects", "personal projects"},
    "skills": {"technical skills", "skills", "core skills", "tech stack"},
    "summary": {"career objective", "objective", "summary", "profile", "about me"},
    "certifications": {"certifications", "certification", "learning", "trainings"},
}

NLP = spacy.blank("en")
SKILL_MATCHER = spacy.matcher.PhraseMatcher(NLP.vocab, attr="LOWER")
SKILL_MATCHER.add("SKILLS", [NLP.make_doc(skill) for skill in ALL_SKILLS])


def get_connection():
    connection = sqlite3.connect(DB_PATH, check_same_thread=False)
    connection.row_factory = sqlite3.Row
    return connection


CONNECTION = get_connection()


def create_user_table():
    CONNECTION.execute(
        """
        CREATE TABLE IF NOT EXISTS resume_data (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            email TEXT,
            resume_score REAL,
            timestamp TEXT,
            no_of_pages TEXT,
            predicted_field TEXT,
            user_level TEXT,
            skills TEXT,
            recommended_skills TEXT,
            recommended_courses TEXT
        )
        """
    )
    CONNECTION.commit()


def get_table_download_link(dataframe, filename, text):
    csv = dataframe.to_csv(index=False)
    b64 = base64.b64encode(csv.encode()).decode()
    return f'<a href="data:file/csv;base64,{b64}" download="{filename}">{text}</a>'


def pdf_reader(file_path):
    resource_manager = PDFResourceManager()
    fake_file_handle = io.StringIO()
    converter = TextConverter(resource_manager, fake_file_handle, laparams=LAParams())
    page_interpreter = PDFPageInterpreter(resource_manager, converter)

    with open(file_path, "rb") as pdf_file:
        for page in PDFPage.get_pages(pdf_file, caching=True, check_extractable=True):
            page_interpreter.process_page(page)

    text = fake_file_handle.getvalue()
    converter.close()
    fake_file_handle.close()
    return text


def count_pdf_pages(file_path):
    with open(file_path, "rb") as pdf_file:
        return sum(1 for _ in PDFPage.get_pages(pdf_file, caching=True, check_extractable=True))


def normalize_whitespace(value):
    return re.sub(r"\s+", " ", value or "").strip()


def canonicalize_heading(line):
    cleaned = re.sub(r"[^a-zA-Z/& ]", " ", line or "")
    cleaned = re.sub(r"\s+", " ", cleaned).strip().lower()
    return cleaned


def extract_email(text):
    match = EMAIL_PATTERN.search(text or "")
    return match.group(0) if match else None


def extract_phone_number(text):
    for match in PHONE_PATTERN.findall(text or ""):
        digits = re.sub(r"\D", "", match)
        if 10 <= len(digits) <= 13:
            if len(digits) > 10 and digits.startswith("91"):
                digits = digits[-10:]
            return digits
    return None


def is_probable_name(line):
    if not line:
        return False
    if any(char.isdigit() for char in line):
        return False
    if "@" in line or len(line) > 60 or URL_PATTERN.search(line):
        return False
    words = [part for part in re.split(r"\s+", line) if part]
    if not 2 <= len(words) <= 4:
        return False
    lowered = {re.sub(r"[^a-z]", "", word.lower()) for word in words}
    lowered.discard("")
    if lowered & NAME_STOP_WORDS:
        return False
    return all(re.fullmatch(r"[A-Za-z][A-Za-z.\-']*", word) for word in words)


def extract_name_from_line(line):
    cropped = re.split(
        r"(?i)(https?://|www\.|linkedin|github|@|\+\d|\b\d{10}\b)",
        line,
        maxsplit=1,
    )[0]
    fragments = re.split(r"[|,•]+", cropped)
    for fragment in fragments:
        candidate = normalize_whitespace(fragment)
        if "." in candidate and len(candidate.split()) > 2:
            candidate = normalize_whitespace(candidate.split(".")[0])
        if is_probable_name(candidate):
            return candidate.title()
    return None


def extract_name(text):
    lines = [normalize_whitespace(line) for line in (text or "").splitlines()]
    candidate_lines = [line for line in lines[:12] if line]
    for line in candidate_lines:
        candidate = extract_name_from_line(line)
        if candidate:
            return candidate
    return None


def is_section_header(line):
    heading = canonicalize_heading(line)
    if not heading:
        return None
    for section_name, aliases in SECTION_ALIASES.items():
        if heading in aliases:
            return section_name
    return None


def split_resume_sections(lines):
    sections = {}
    current_section = "header"
    sections[current_section] = []

    for raw_line in lines:
        line = normalize_whitespace(raw_line)
        if not line:
            continue
        section_name = is_section_header(line)
        if section_name:
            current_section = section_name
            sections.setdefault(current_section, [])
            continue
        sections.setdefault(current_section, []).append(line)

    return sections


def is_contact_or_link_line(line):
    lowered = line.lower()
    return (
        "@" in line
        or URL_PATTERN.search(line) is not None
        or "linkedin" in lowered
        or "github" in lowered
        or re.search(r"\+?\d[\d\s\-()]{8,}", line) is not None
    )


def deduplicate_preserve_order(values):
    seen = set()
    ordered = []
    for value in values:
        normalized = value.strip().lower()
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        ordered.append(value.strip())
    return ordered


def extract_education(lines, sections):
    education = []
    source_lines = sections.get("education", [])
    if not source_lines:
        source_lines = lines

    for line in source_lines:
        lowered = line.lower()
        if is_contact_or_link_line(line):
            continue
        if any(keyword in lowered for keyword in EDUCATION_KEYWORDS):
            education.append(line)

    return deduplicate_preserve_order(education)[:5]


def extract_experience(lines, sections):
    experience = []
    source_lines = sections.get("experience", [])
    if not source_lines:
        source_lines = lines

    for line in source_lines:
        lowered = line.lower()
        if is_contact_or_link_line(line):
            continue
        if any(keyword in lowered for keyword in EXPERIENCE_KEYWORDS):
            experience.append(line)

    return deduplicate_preserve_order(experience)[:8]


def extract_skills(text):
    doc = NLP(text or "")
    matches = SKILL_MATCHER(doc)
    found = {doc[start:end].text.strip() for _, start, end in matches}

    normalized = set()
    for skill in found:
        lowered = skill.lower()
        for canonical_skill in ALL_SKILLS:
            if lowered == canonical_skill.lower():
                normalized.add(canonical_skill.title() if canonical_skill.islower() else canonical_skill)
                break

    return sorted(normalized, key=str.lower)


def parse_resume(file_path):
    text = pdf_reader(file_path)
    lines = [normalize_whitespace(line) for line in text.splitlines() if normalize_whitespace(line)]
    sections = split_resume_sections(lines)
    return {
        "name": extract_name(text),
        "email": extract_email(text),
        "mobile_number": extract_phone_number(text),
        "education": extract_education(lines, sections),
        "experience": extract_experience(lines, sections),
        "skills": extract_skills(text),
        "sections": sections,
        "raw_text": text,
        "no_of_pages": count_pdf_pages(file_path),
    }


def analyze_resume(uploaded_file):
    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    save_path = UPLOAD_DIR / uploaded_file.name

    with open(save_path, "wb") as output_file:
        output_file.write(uploaded_file.getbuffer())

    show_pdf(save_path)
    return parse_resume(save_path), str(save_path)


def show_pdf(file_path):
    with open(file_path, "rb") as pdf_file:
        base64_pdf = base64.b64encode(pdf_file.read()).decode("utf-8")
    pdf_display = (
        f'<iframe src="data:application/pdf;base64,{base64_pdf}" '
        'width="100%" height="700" type="application/pdf"></iframe>'
    )
    st.markdown(pdf_display, unsafe_allow_html=True)


def analyze_skills(resume_data):
    extracted_skills = {skill.lower() for skill in resume_data.get("skills", [])}
    predicted_field = "General"
    recommended_skills = ["Communication", "Problem Solving", "Project Documentation"]
    fallback_courses = web_course + ds_course
    rec_course = random.sample(fallback_courses, k=min(4, len(fallback_courses)))
    best_score = 0
    raw_text = (resume_data.get("raw_text") or "").lower()

    for field_name, field_data in SKILL_TAXONOMY.items():
        keyword_set = {skill.lower() for skill in field_data["keywords"]}
        overlap = len(extracted_skills & keyword_set)
        text_hits = sum(1 for keyword in keyword_set if keyword in raw_text)
        combined_score = overlap * 3 + text_hits

        # Reward resumes that clearly mention both client and server skills as full stack.
        if field_name == "Full Stack Development":
            has_frontend = bool(
                extracted_skills
                & {"html", "css", "javascript", "typescript", "react", "angular", "vue"}
            )
            has_backend = bool(
                extracted_skills
                & {"node.js", "node", "express", "django", "flask", "java", "spring", "sql", "mysql", "postgresql"}
            )
            if has_frontend and has_backend:
                combined_score += 6

        if overlap > best_score:
            best_score = combined_score
            predicted_field = field_name
            recommended_skills = field_data["recommended_skills"]
            rec_course = field_data["courses"]
        elif combined_score > best_score:
            best_score = combined_score
            predicted_field = field_name
            recommended_skills = field_data["recommended_skills"]
            rec_course = field_data["courses"]

    return recommended_skills, predicted_field, rec_course


def calculate_resume_score(resume_data, recommended_skills):
    raw_score = 0
    raw_text = (resume_data.get("raw_text") or "").lower()
    sections = resume_data.get("sections") or {}
    extracted_skills = {skill.lower() for skill in resume_data.get("skills", [])}
    recommended_skill_hits = sum(
        1 for skill in recommended_skills if skill.lower() in extracted_skills
    )
    breakdown = {
        "Contact Details": {"score": 0, "max_score": 40},
        "Resume Structure": {"score": 0, "max_score": 44},
        "Skills Match": {"score": 0, "max_score": 22},
        "Experience and Projects": {"score": 0, "max_score": 12},
        "Resume Length": {"score": 0, "max_score": 8},
        "Penalties": {"score": 0, "max_score": 0},
    }

    # Contact and identity details.
    if resume_data.get("name") and resume_data.get("name") != "N/A":
        raw_score += 12
        breakdown["Contact Details"]["score"] += 12
    if resume_data.get("email"):
        raw_score += 10
        breakdown["Contact Details"]["score"] += 10
    if resume_data.get("mobile_number"):
        raw_score += 8
        breakdown["Contact Details"]["score"] += 8
    if "linkedin.com" in raw_text:
        raw_score += 5
        breakdown["Contact Details"]["score"] += 5
    if "github.com" in raw_text or "portfolio" in raw_text:
        raw_score += 5
        breakdown["Contact Details"]["score"] += 5

    # Core resume structure.
    if resume_data.get("education"):
        raw_score += 12
        breakdown["Resume Structure"]["score"] += 12
    if resume_data.get("experience"):
        raw_score += 12
        breakdown["Resume Structure"]["score"] += 12
    if sections.get("projects"):
        raw_score += 12
        breakdown["Resume Structure"]["score"] += 12
    if sections.get("skills") or resume_data.get("skills"):
        raw_score += 10
        breakdown["Resume Structure"]["score"] += 10
    if sections.get("summary"):
        raw_score += 6
        breakdown["Resume Structure"]["score"] += 6
    if sections.get("certifications"):
        raw_score += 4
        breakdown["Resume Structure"]["score"] += 4

    # Skill alignment with the predicted profile.
    skill_count = len(extracted_skills)
    if skill_count >= 10:
        raw_score += 10
        breakdown["Skills Match"]["score"] += 10
    elif skill_count >= 6:
        raw_score += 8
        breakdown["Skills Match"]["score"] += 8
    elif skill_count >= 3:
        raw_score += 5
        breakdown["Skills Match"]["score"] += 5

    matched_skill_score = min(12, recommended_skill_hits * 3)
    raw_score += matched_skill_score
    breakdown["Skills Match"]["score"] += matched_skill_score

    # Experience and project depth.
    experience_count = len(resume_data.get("experience") or [])
    project_count = len(sections.get("projects") or [])
    if experience_count >= 2:
        raw_score += 6
        breakdown["Experience and Projects"]["score"] += 6
    elif experience_count == 1:
        raw_score += 3
        breakdown["Experience and Projects"]["score"] += 3

    if project_count >= 3:
        raw_score += 6
        breakdown["Experience and Projects"]["score"] += 6
    elif project_count >= 1:
        raw_score += 3
        breakdown["Experience and Projects"]["score"] += 3

    # Page length: one page is ideal for students and freshers.
    no_of_pages = resume_data.get("no_of_pages") or 1
    if no_of_pages == 1:
        raw_score += 8
        breakdown["Resume Length"]["score"] += 8
    elif no_of_pages == 2:
        raw_score += 5
        breakdown["Resume Length"]["score"] += 5
    elif no_of_pages >= 3:
        raw_score -= 6
        breakdown["Penalties"]["score"] -= 6

    # Penalize obviously incomplete resumes.
    if not resume_data.get("name"):
        raw_score -= 8
        breakdown["Penalties"]["score"] -= 8
    if not resume_data.get("education"):
        raw_score -= 8
        breakdown["Penalties"]["score"] -= 8
    if not resume_data.get("skills"):
        raw_score -= 10
        breakdown["Penalties"]["score"] -= 10

    max_raw_score = 123
    normalized_score = round((raw_score / max_raw_score) * 100)
    final_score = max(0, min(100, normalized_score))
    return final_score, breakdown


def render_score_breakdown(score_breakdown):
    render_section_heading(
        "Score Breakdown",
        "A transparent view of how the resume writing score was calculated.",
    )
    for category, details in score_breakdown.items():
        score = details["score"]
        max_score = details["max_score"]
        if max_score > 0:
            progress_value = max(0.0, min(1.0, score / max_score))
            st.markdown(
                f"""
                <div class="subtle-card">
                    <div class="stats-label">{category}</div>
                    <div class="stats-value">{score}/{max_score}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
            st.progress(progress_value)
        else:
            st.markdown(
                f"""
                <div class="subtle-card">
                    <div class="stats-label">{category}</div>
                    <div class="stats-value">{score}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


def determine_candidate_level(resume_data):
    experience_entries = resume_data.get("experience") or []
    if not experience_entries:
        return "Beginner"
    if len(experience_entries) <= 3:
        return "Intermediate"
    return "Expert"


def insert_data(
    name,
    email,
    resume_score,
    timestamp,
    no_of_pages,
    predicted_field,
    candidate_level,
    skills,
    recommended_skills,
    recommended_courses,
):
    CONNECTION.execute(
        """
        INSERT INTO resume_data (
            name,
            email,
            resume_score,
            timestamp,
            no_of_pages,
            predicted_field,
            user_level,
            skills,
            recommended_skills,
            recommended_courses
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            name,
            email,
            float(resume_score),
            timestamp,
            str(no_of_pages),
            predicted_field,
            candidate_level,
            ", ".join(skills),
            ", ".join(recommended_skills),
            ", ".join(recommended_courses),
        ),
    )
    CONNECTION.commit()


def fetch_all_resumes():
    rows = CONNECTION.execute(
        """
        SELECT
            id AS ID,
            name AS Name,
            email AS Email,
            resume_score AS "Resume Score",
            timestamp AS Timestamp,
            no_of_pages AS "Total Page",
            predicted_field AS "Predicted Field",
            user_level AS "User Level",
            skills AS Skills,
            recommended_skills AS "Recommended Skills",
            recommended_courses AS "Recommended Course"
        FROM resume_data
        ORDER BY id DESC
        """
    ).fetchall()
    columns = [
        "ID",
        "Name",
        "Email",
        "Resume Score",
        "Timestamp",
        "Total Page",
        "Predicted Field",
        "User Level",
        "Skills",
        "Recommended Skills",
        "Recommended Course",
    ]
    if not rows:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame([dict(row) for row in rows], columns=columns)


def display_video_tips():
    with st.expander("🎬 Bonus Video for Resume Writing Tips"):
        if resume_videos:
            st.video(random.choice(resume_videos))

    with st.expander("🎬 Bonus Video for Interview Tips"):
        if interview_videos:
            st.video(random.choice(interview_videos))


def course_recommender(course_list):
    render_section_heading(
        "Course Recommendations",
        "Curated learning paths based on the skills and role prediction above.",
    )
    recommendation_count = st.slider("Choose Number of Course Recommendations:", 1, 10, 4)
    selected_courses = random.sample(course_list, k=min(recommendation_count, len(course_list)))
    recommended_names = []
    for index, (course_name, course_link) in enumerate(selected_courses, start=1):
        st.markdown(f"{index}. [{course_name}]({course_link})")
        recommended_names.append(course_name)

    return recommended_names


def show_resume_overview(resume_data, score_breakdown):
    candidate_name = resume_data.get("name") or "Candidate"
    st.markdown(
        f"""
        <div class="glass-panel">
            <div class="section-chip">Candidate Overview</div>
            <div class="section-title" style="margin-top:0;">Hello {candidate_name}</div>
            <div class="stats-row">
                <div class="stats-card">
                    <div class="stats-label">Name</div>
                    <div class="stats-value">{resume_data.get('name') or 'N/A'}</div>
                </div>
                <div class="stats-card">
                    <div class="stats-label">Email</div>
                    <div class="stats-value">{resume_data.get('email') or 'N/A'}</div>
                </div>
                <div class="stats-card">
                    <div class="stats-label">Contact</div>
                    <div class="stats-value">{resume_data.get('mobile_number') or 'N/A'}</div>
                </div>
                <div class="stats-card">
                    <div class="stats-label">Resume Pages</div>
                    <div class="stats-value">{resume_data.get('no_of_pages') or 'N/A'}</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    struct_ratio = score_breakdown["Resume Structure"]["score"] / max(1, score_breakdown["Resume Structure"]["max_score"])
    exp_ratio = score_breakdown["Experience and Projects"]["score"] / max(1, score_breakdown["Experience and Projects"]["max_score"])

    edu_border = "var(--success)" if struct_ratio > 0.7 else "var(--line-strong)"
    edu_bg = "rgba(66, 245, 185, 0.08)" if struct_ratio > 0.7 else "transparent"
    
    exp_border = "var(--success)" if exp_ratio > 0.7 else ("#ffeb3b" if exp_ratio > 0.4 else "#ff5252")
    exp_bg = "rgba(66, 245, 185, 0.08)" if exp_ratio > 0.7 else ("rgba(255, 235, 59, 0.08)" if exp_ratio > 0.4 else "rgba(255, 82, 82, 0.08)")

    education = resume_data.get("education") or []
    if education:
        render_section_heading("Education (Heatmap Preview)", "Detected education highlights with quality heatmapping.")
        for item in education:
            st.markdown(f'<div class="subtle-card" style="border-left: 4px solid {edu_border}; background: linear-gradient(90deg, {edu_bg}, transparent); transition: all 0.3s ease;">{item}</div>', unsafe_allow_html=True)

    experience = resume_data.get("experience") or []
    if experience:
        render_section_heading("Experience (Heatmap Preview)", "Relevant internships and work experience found in the resume.")
        for item in experience:
            st.markdown(f'<div class="subtle-card" style="border-left: 4px solid {exp_border}; background: linear-gradient(90deg, {exp_bg}, transparent); transition: all 0.3s ease;">{item}</div>', unsafe_allow_html=True)


def handle_normal_user():
    render_hero_section("Candidate analysis")
    render_feature_cards()
    render_upload_intro()
    pdf_file = st.file_uploader("Choose your Resume", type=["pdf"])
    if not pdf_file:
        return

    resume_data, _ = analyze_resume(pdf_file)

    recommended_skills, predicted_field, rec_course = analyze_skills(resume_data)
    resume_score, score_breakdown = calculate_resume_score(resume_data, recommended_skills)
    candidate_level = determine_candidate_level(resume_data)
    timestamp = dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    score_color_class = "pulse-green" if resume_score >= 75 else "pulse-yellow" if resume_score >= 50 else "pulse-red"
    score_color_css = "score-green" if resume_score >= 75 else "score-yellow" if resume_score >= 50 else "score-red"

    st.markdown(f"""
        <div class="sticky-summary">
            <div class="summary-item">
                <div class="summary-label">ATS Score</div>
                <div class="summary-value {score_color_css}">{resume_score:.0f}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Predicted Role</div>
                <div class="summary-value">{predicted_field}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">Candidate Level</div>
                <div class="summary-value">{candidate_level}</div>
            </div>
            <div>
                <a href="#" class="action-button">Download Report</a>
                <a href="#" class="action-button">Share Insights</a>
            </div>
        </div>
    """, unsafe_allow_html=True)

    components.html(f"""
        <style>
            body {{ margin: 0; padding: 0; background: transparent; font-family: sans-serif; display: flex; justify-content: center; }}
            .score-circle {{
                width: 250px;
                height: 250px;
                border-radius: 50%;
                display: flex;
                flex-direction: column;
                justify-content: center;
                align-items: center;
                background: #0f1326;
                position: relative;
                box-shadow: inset 0 0 20px rgba(0,0,0,0.5);
                border: 2px solid transparent;
            }}
            .score-circle::before {{
                content: "";
                position: absolute;
                inset: -6px;
                border-radius: 50%;
                background: conic-gradient(var(--score-color) var(--score-angle), rgba(255,255,255,0.05) 0);
                z-index: -1;
                transition: --score-angle 1.5s ease-out;
            }}
            .score-circle::after {{
                content: "";
                position: absolute;
                inset: 8px;
                background: #0f1326;
                border-radius: 50%;
                z-index: -1;
            }}
            .score-text {{ font-size: 5rem; font-weight: 900; line-height: 1; color: white; text-shadow: 0 0 15px var(--score-color); }}
            .score-label {{ font-size: 1.2rem; color: #a9b3d1; text-transform: uppercase; letter-spacing: 2px; margin-top: 5px; }}
            .pulse-green {{ animation: pulse-glow-green 2s infinite; --score-color: #42f5b9; }}
            .pulse-yellow {{ animation: pulse-glow-yellow 2s infinite; --score-color: #ffeb3b; }}
            .pulse-red {{ animation: pulse-glow-red 2s infinite; --score-color: #ff5252; }}
            @keyframes pulse-glow-green {{ 0% {{ box-shadow: 0 0 0 0 rgba(66, 245, 185, 0.4); }} 70% {{ box-shadow: 0 0 0 30px rgba(66, 245, 185, 0); }} 100% {{ box-shadow: 0 0 0 0 rgba(66, 245, 185, 0); }} }}
            @keyframes pulse-glow-yellow {{ 0% {{ box-shadow: 0 0 0 0 rgba(255, 235, 59, 0.4); }} 70% {{ box-shadow: 0 0 0 30px rgba(255, 235, 59, 0); }} 100% {{ box-shadow: 0 0 0 0 rgba(255, 235, 59, 0); }} }}
            @keyframes pulse-glow-red {{ 0% {{ box-shadow: 0 0 0 0 rgba(255, 82, 82, 0.4); }} 70% {{ box-shadow: 0 0 0 30px rgba(255, 82, 82, 0); }} 100% {{ box-shadow: 0 0 0 0 rgba(255, 82, 82, 0); }} }}
        </style>
        <div class="score-circle {score_color_class}" style="--score-angle: 0deg;" id="score-container">
            <div class="score-text" id="score-value">0</div>
            <div class="score-label">ATS Score</div>
        </div>
        <script>
            let currentScore = 0;
            const targetScore = {resume_score};
            const duration = 1500;
            const fps = 60;
            const steps = duration / (1000 / fps);
            const increment = targetScore / steps;
            let step = 0;
            const valEl = document.getElementById('score-value');
            const contEl = document.getElementById('score-container');
            
            const interval = setInterval(() => {{
                currentScore += increment;
                step++;
                if(step >= steps) {{
                    currentScore = targetScore;
                    clearInterval(interval);
                }}
                valEl.innerText = Math.floor(currentScore);
                contEl.style.setProperty('--score-angle', `${{currentScore * 3.6}}deg`);
            }}, 1000 / fps);
        </script>
    """, height=300)

    st.markdown("### 🤖 AI Recruiter Insights")
    insight_1 = f"Candidate demonstrates a strong alignment with **{predicted_field}** positions."
    insight_2 = f"Based on experience entries, the level is categorized as **{candidate_level}**."
    insight_3 = "The resume score is exceptional." if resume_score >= 75 else "The resume needs improvement to pass standard ATS filters."
    
    st.markdown(f"""
    <div class="ai-insight-card">
        <h4>Snapshot</h4>
        <ul>
            <li>{insight_1}</li>
            <li>{insight_2}</li>
            <li>{insight_3}</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)
    
    show_resume_overview(resume_data, score_breakdown)

    render_section_heading(
        "Data Visualization",
        "Visual breakdown of the resume composition and capabilities mapping.",
    )
    
    col_chart1, col_chart2 = st.columns(2)
    with col_chart1:
        categories = ['Structure', 'Skills', 'Experience', 'Contact', 'Length']
        scores_arr = [
            score_breakdown["Resume Structure"]["score"] / max(1, score_breakdown["Resume Structure"]["max_score"]) * 100,
            score_breakdown["Skills Match"]["score"] / max(1, score_breakdown["Skills Match"]["max_score"]) * 100,
            score_breakdown["Experience and Projects"]["score"] / max(1, score_breakdown["Experience and Projects"]["max_score"]) * 100,
            score_breakdown["Contact Details"]["score"] / max(1, score_breakdown["Contact Details"]["max_score"]) * 100,
            score_breakdown["Resume Length"]["score"] / max(1, score_breakdown["Resume Length"]["max_score"]) * 100,
        ]
        fig_radar = go.Figure(data=go.Scatterpolar(
            r=scores_arr + [scores_arr[0]],
            theta=categories + [categories[0]],
            fill='toself',
            line_color='#ff4fd8',
            fillcolor='rgba(255, 79, 216, 0.3)'
        ))
        fig_radar.update_layout(
            polar=dict(radialaxis=dict(visible=True, range=[0, 100])),
            showlegend=False,
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#a9b3d1'),
            margin=dict(l=40, r=40, t=40, b=40),
            title=dict(text="Resume Category Strengths", font=dict(color='white'))
        )
        st.plotly_chart(fig_radar, use_container_width=True)

    with col_chart2:
        df_scores = pd.DataFrame({
            'Category': list(score_breakdown.keys())[:-1],
            'Score': [score_breakdown[k]["score"] for k in list(score_breakdown.keys())[:-1]]
        })
        fig_bar = px.bar(df_scores, x='Score', y='Category', orientation='h', color='Score', 
                         color_continuous_scale=[(0, '#ff5252'), (0.5, '#ffeb3b'), (1, '#42f5b9')],
                         title="Detailed Score Breakdown")
        fig_bar.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#a9b3d1'),
            margin=dict(l=40, r=40, t=40, b=40)
        )
        st.plotly_chart(fig_bar, use_container_width=True)

    render_section_heading(
        "Skills Recommendation & Action Plan",
        "Compare extracted capabilities with missing core requirements.",
    )
    col_skills1, col_skills2 = st.columns(2)
    with col_skills1:
        st_tags(label="### Validated Skills", text="Extracted from your resume", value=resume_data.get("skills", []), key="skills_have")
    with col_skills2:
        st_tags(label="### Targeted Skills", text="Highly mapped for this role", value=recommended_skills, key="skills_recommended")

    missing_skills = [sk for sk in recommended_skills if sk.lower() not in [s.lower() for s in resume_data.get("skills", [])]]
    if missing_skills:
        st.markdown("### ⚠️ Missing Key Skills")
        for sk in missing_skills:
            st.markdown(f"""
            <div class="action-card">
                <strong>{sk}</strong> - Recommended to bridge the skill gap for {predicted_field} roles.
            </div>
            """, unsafe_allow_html=True)
            
    st.markdown("### 💡 Recommended Actions")
    actions = []
    if score_breakdown["Resume Structure"]["score"] < score_breakdown["Resume Structure"]["max_score"]:
        actions.append("Ensure your resume contains clearly distinguished sections (Education, Experience, Projects).")
    if score_breakdown["Contact Details"]["score"] < score_breakdown["Contact Details"]["max_score"]:
        actions.append("Add a LinkedIn profile and GitHub/Portfolio link for better contact visibility.")
    if score_breakdown["Resume Length"]["score"] < score_breakdown["Resume Length"]["max_score"]:
        actions.append("Your resume might be too long. Keep it strictly to 1 or 2 pages max.")
    if not actions:
        actions.append("Your resume structure looks stellar! Just keep your skills up to date.")
        
    for act in actions:
        st.markdown(f"""
        <div class="ai-insight-card">
            • {act}
        </div>
        """, unsafe_allow_html=True)

    recommended_course_names = course_recommender(rec_course)
    render_score_breakdown(score_breakdown)

    insert_data(
        resume_data.get("name") or "N/A",
        resume_data.get("email") or "N/A",
        resume_score,
        timestamp,
        resume_data.get("no_of_pages") or "0",
        predicted_field,
        candidate_level,
        resume_data.get("skills", []),
        recommended_skills,
        recommended_course_names,
    )

    st.success("Your resume data has been stored successfully.")
    display_video_tips()


def handle_admin():
    render_hero_section("Admin analytics")
    render_section_heading(
        "Admin Access",
        "Review uploaded resume records, export reports, and explore hiring insights.",
    )
    if "admin_logged_in" not in st.session_state:
        st.session_state["admin_logged_in"] = False

    if not st.session_state["admin_logged_in"]:
        ad_user = st.text_input("Username")
        ad_password = st.text_input("Password", type="password")

        if st.button("Login"):
            if ad_user == "Amigoes" and ad_password == "Amigoes":
                st.session_state["admin_logged_in"] = True
            else:
                st.error("Wrong ID and Password Provided")
                return
        else:
            return

    st.success("Welcome Admin")
    if st.button("Logout", key="logout_btn"):
        st.session_state["admin_logged_in"] = False
        if hasattr(st, "rerun"):
            st.rerun()
        else:
            st.experimental_rerun()
    dataframe = fetch_all_resumes()

    if dataframe.empty:
        st.warning("No data found in the database")
        return

    # 1. KPI CARDS
    total_resumes = len(dataframe)
    avg_score = int(dataframe["Resume Score"].mean()) if "Resume Score" in dataframe else 0
    most_common_role = dataframe["Predicted Field"].mode()[0] if not dataframe.empty else "N/A"
    success_rate = round(len(dataframe[dataframe["Resume Score"] >= 75]) / total_resumes * 100) if total_resumes > 0 else 0

    st.markdown(f"""
        <style>
            @keyframes slide-up-fade {{
                from {{ opacity: 0; transform: translateY(15px); }}
                to {{ opacity: 1; transform: translateY(0); }}
            }}
            .animated-val {{
                animation: slide-up-fade 0.6s ease-out forwards;
            }}
        </style>
        <div class="stats-row" style="margin-bottom: 2rem;">
            <div class="stats-card ai-insight-card" style="margin: 0; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                <div class="stats-label">Total Resumes</div>
                <div class="stats-value animated-val" style="font-size: 2.5rem; font-weight: 800; color: var(--blue); text-shadow: 0 0 15px rgba(78, 168, 255, 0.4);">{total_resumes}</div>
            </div>
            <div class="stats-card ai-insight-card" style="margin: 0; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                <div class="stats-label">Avg. ATS Score</div>
                <div class="stats-value animated-val" style="font-size: 2.5rem; font-weight: 800; color: var(--success); text-shadow: 0 0 15px rgba(66, 245, 185, 0.4);">{avg_score}</div>
            </div>
            <div class="stats-card ai-insight-card" style="margin: 0; display: flex; flex-direction: column; justify-content: center; align-items: center; text-align: center;">
                <div class="stats-label">Most Common Role</div>
                <div class="stats-value animated-val" style="font-size: 1.6rem; font-weight: 800; color: var(--pink); text-shadow: 0 0 15px rgba(255, 79, 216, 0.4);">{most_common_role}</div>
            </div>
            <div class="stats-card ai-insight-card" style="margin: 0; display: flex; flex-direction: column; justify-content: center; align-items: center;">
                <div class="stats-label">Success Rate (>75)</div>
                <div class="stats-value animated-val" style="font-size: 2.5rem; font-weight: 800; color: var(--purple); text-shadow: 0 0 15px rgba(138, 92, 255, 0.4);">{success_rate}%</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # 4. AI ADMIN INSIGHTS PANEL
    st.markdown("### 🧠 Hiring Insights")
    insight_role = f"Most candidates are suitable for **{most_common_role}** roles."
    insight_score = "Average ATS score is strong and improving across batches." if avg_score >= 70 else "Consider adjusting your sourcing filters; average ATS scores are below target."
    
    # Calculate most missing skills
    all_recommended = dataframe["Recommended Skills"].dropna().apply(lambda x: [s.strip() for s in str(x).split(',') if s.strip()])
    flat_recommended = [item for sublist in all_recommended for item in sublist]
    from collections import Counter
    top_missing = [item[0] for item in Counter(flat_recommended).most_common(3)] if flat_recommended else ["Docker", "Kubernetes", "CI/CD"]
    insight_skills = f"Top missing skills across all applicants: **{', '.join(top_missing)}**"
    
    st.markdown(f"""
    <div style="display: flex; flex-direction: column; gap: 0.8rem; margin-bottom: 2.5rem;">
        <div class="ai-insight-card" style="margin: 0; padding: 1rem 1.5rem; display: flex; align-items: center; gap: 1rem;">
            <div style="font-size: 2rem;">🎯</div>
            <div style="font-size: 1.05rem; line-height: 1.5;">{insight_role}</div>
        </div>
        <div class="ai-insight-card" style="margin: 0; padding: 1rem 1.5rem; display: flex; align-items: center; gap: 1rem;">
            <div style="font-size: 2rem;">📈</div>
            <div style="font-size: 1.05rem; line-height: 1.5;">{insight_score}</div>
        </div>
        <div class="ai-insight-card" style="margin: 0; padding: 1rem 1.5rem; display: flex; align-items: center; gap: 1rem;">
            <div style="font-size: 2rem;">⚠️</div>
            <div style="font-size: 1.05rem; line-height: 1.5;">{insight_skills}</div>
        </div>
    </div>
    """, unsafe_allow_html=True)

    # 2. ADVANCED CHARTS
    render_section_heading("Role Distribution", "Overall candidate alignment.")
    role_counts = dataframe["Predicted Field"].value_counts().reset_index()
    role_counts.columns = ['Role', 'Count']
    fig_donut = px.pie(role_counts, names='Role', values='Count', hole=0.6, 
                       color_discrete_sequence=['#ff4fd8', '#8a5cff', '#4ea8ff', '#42f5b9', '#ffeb3b'])
    fig_donut.update_layout(
        paper_bgcolor='rgba(0,0,0,0)', plot_bgcolor='rgba(0,0,0,0)',
        font=dict(color='#a9b3d1'), margin=dict(t=20, b=20, l=20, r=20)
    )
    st.plotly_chart(fig_donut, use_container_width=True)

    # 3. SMART TABLE UPGRADE
    render_section_heading("Candidate Directory", "Search, filter, and export candidate records.")
    
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        raw_roles = dataframe["Predicted Field"].dropna().unique().tolist()
        roles_list = sorted(list(set(str(r).strip() for r in raw_roles if str(r).strip())))
        roles = ["All"] + roles_list
        selected_role = st.selectbox("Filter by Role:", roles)
    with col_f2:
        min_score = st.slider("Minimum ATS Score:", 0, 100, 0)

    filtered_df = dataframe.copy()
    if selected_role != "All":
        filtered_df = filtered_df[
            filtered_df["Predicted Field"].astype(str).str.strip().str.lower() == selected_role.strip().lower()
        ]
    
    if min_score > 0:
        filtered_df = filtered_df[filtered_df["Resume Score"] >= min_score]
    
    # 6. BULK ACTION BUTTONS
    st.markdown("""
        <div style="display: flex; gap: 15px; margin-bottom: 0.5rem; flex-wrap: wrap;">
            <a href="#" class="action-button" style="background: rgba(255,255,255,0.05); color: #fff !important; border-color: rgba(255,255,255,0.2);">⬇️ Export All Data</a>
            <a href="#" class="action-button" style="background: linear-gradient(90deg, #4ea8ff, #42f5b9);">📊 Download Filtered Report</a>
            <a href="#" class="action-button" style="background: linear-gradient(90deg, #ff4fd8, #8a5cff);">⭐ Highlight Top Candidates</a>
        </div>
    """, unsafe_allow_html=True)

    st.markdown(f"""
        <div style="margin-bottom: 1rem; padding: 0.6rem 1rem; border-left: 3px solid var(--blue); background: rgba(78, 168, 255, 0.1); border-radius: 0 8px 8px 0; animation: slide-up-fade 0.5s ease;">
            <span style="color: var(--text-soft); font-size: 0.9rem;">Showing results for:</span> 
            <strong style="color: var(--text-main); font-size: 1rem; margin-left: 0.3rem;">{selected_role}</strong> 
            <span style="color: var(--text-soft); font-size: 0.9rem; margin-left: 0.5rem;">(Score &ge; {min_score})</span>
        </div>
    """, unsafe_allow_html=True)
    
    if filtered_df.empty:
        st.markdown("""
        <div style="padding: 2.5rem; text-align: center; background: rgba(255,82,82,0.05); border: 1px dashed rgba(255,82,82,0.4); border-radius: 16px; margin-top: 1rem; animation: slide-up-fade 0.5s ease;">
            <div style="font-size: 2.5rem; margin-bottom: 0.5rem;">📭</div>
            <h3 style="color: #ff5252; margin: 0 0 0.5rem 0;">No results found</h3>
            <p style="color: var(--text-soft); margin: 0;">Try modifying your role filter or lowering the minimum ATS score.</p>
        </div>
        """, unsafe_allow_html=True)
    else:
        if "Date" in filtered_df.columns:
            filtered_df = filtered_df.drop(columns=["Date"])
        st.dataframe(filtered_df, use_container_width=True, height=500)


def render_logo():
    logo_candidates = [
        BASE_DIR / "Logo" / "SRA_Logo.jpg",
        BASE_DIR / "Logo" / "SRA_Logo.png",
    ]

    for logo_path in logo_candidates:
        if logo_path.exists():
            image = Image.open(logo_path).resize((220, 220))
            st.image(image)
            return


def run():
    create_user_table()
    inject_custom_css()
    render_logo()
    render_sidebar_brand()
    choice = st.sidebar.selectbox(
        "Choose among the given options:",
        ["👤 Normal User", "🛡️ Admin"],
    )
    render_sidebar_note()

    if choice == "👤 Normal User":
        handle_normal_user()
    else:
        handle_admin()


if __name__ == "__main__":
    if in_streamlit_runtime():
        run()
    else:
        script_path = str(Path(__file__).resolve())
        print("Starting Smart Resume Analyzer...")
        print("Open this URL in your browser after the server starts: http://localhost:8501")
        subprocess.run(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                script_path,
                "--server.headless",
                "true",
                "--browser.gatherUsageStats",
                "false",
            ],
            check=False,
        )

