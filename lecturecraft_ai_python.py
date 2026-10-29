#!/usr/bin/env python3
"""A standalone, single-file Python version of the LectureCraft planning app.

Run with: python3 lecturecraft_ai_python.py
Uses only the Python standard library. Lesson plans and sessions are stored in
lecturecraft_data.json beside this file. This is a single-user demo app; add
authentication and deployment hardening before exposing private data publicly.
"""

from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlparse


HOST = os.environ.get("HOST", "0.0.0.0")
PORT = int(os.environ.get("PORT", "5000"))
DATA_FILE = Path(
    os.environ.get(
        "LECTURECRAFT_DATA_FILE",
        str(Path(__file__).resolve().with_name("lecturecraft_data.json")),
    )
)
MAX_BODY_BYTES = 32_000
STORE_LOCK = threading.Lock()


PAGE = r"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <meta name="theme-color" content="#fbf5ff">
  <title>LectureCraft AI · Bhumika's teaching desk</title>
  <style>
    :root {
      color-scheme: light;
      --ink: #321944;
      --muted: #806d8a;
      --line: #eee2f2;
      --paper: #ffffff;
      --canvas: #fcf8fe;
      --purple: #7950c8;
      --purple-dark: #60369f;
      --purple-soft: #f1e9fb;
      --pink: #d96cae;
      --pink-soft: #fff0f7;
      --green: #278268;
      --shadow: 0 16px 45px rgba(68, 30, 91, .08);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    }

    * { box-sizing: border-box; }
    body { margin: 0; min-height: 100vh; color: var(--ink); background: var(--canvas); }
    button, input, textarea, select { font: inherit; }
    button { cursor: pointer; }
    button:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible {
      outline: 3px solid #caa9f1; outline-offset: 2px;
    }
    .shell { min-height: 100vh; display: grid; grid-template-columns: 248px minmax(0, 1fr); }
    .sidebar {
      position: sticky; top: 0; height: 100vh; padding: 26px 18px 20px;
      display: flex; flex-direction: column; background: #fff;
      border-right: 1px solid var(--line);
    }
    .brand { display: flex; gap: 12px; align-items: center; padding: 0 7px 28px; }
    .brand-mark {
      display: grid; place-items: center; width: 42px; height: 42px; border-radius: 14px;
      color: white; font-size: 19px; font-weight: 800;
      background: linear-gradient(140deg, var(--purple), var(--pink));
      box-shadow: 0 8px 18px rgba(121, 80, 200, .22);
    }
    .brand-name { font-size: 15px; font-weight: 800; letter-spacing: -.3px; }
    .brand-caption { margin-top: 3px; font-size: 11px; color: var(--muted); }
    .nav-label { margin: 11px 10px 9px; color: #a18ea9; font-size: 10px; font-weight: 800; letter-spacing: 1.15px; text-transform: uppercase; }
    .nav-list { display: grid; gap: 6px; }
    .nav-button {
      display: flex; width: 100%; align-items: center; gap: 12px; border: 0; border-radius: 11px;
      padding: 11px 12px; color: #76667f; background: transparent; text-align: left; font-size: 13px; font-weight: 650;
      transition: background .18s ease, color .18s ease, transform .18s ease;
    }
    .nav-button:hover { color: var(--purple-dark); background: #faf5ff; transform: translateX(2px); }
    .nav-button.active { color: var(--purple-dark); background: var(--purple-soft); }
    .nav-icon { display: grid; place-items: center; width: 21px; color: var(--pink); font-size: 15px; font-weight: 800; }
    .sidebar-bottom { margin-top: auto; }
    .tip-card { margin: 15px 3px 18px; padding: 15px; border: 1px solid #f2ddef; border-radius: 15px; background: linear-gradient(145deg, #fff5fb, #f6f0ff); }
    .tip-title { margin: 0 0 6px; color: var(--purple-dark); font-size: 12px; font-weight: 800; }
    .tip-text { margin: 0; color: #806d8a; font-size: 11px; line-height: 1.55; }
    .profile { display: flex; gap: 10px; align-items: center; padding: 13px 5px 0; border-top: 1px solid var(--line); }
    .avatar { display: grid; place-items: center; flex: 0 0 36px; height: 36px; border-radius: 50%; color: #fff; font-weight: 800; background: linear-gradient(145deg, var(--pink), var(--purple)); }
    .profile-name { font-size: 12px; font-weight: 750; }
    .profile-caption { margin-top: 3px; color: var(--muted); font-size: 10px; }
    .main-area { min-width: 0; }
    .topbar { display: flex; height: 76px; align-items: center; justify-content: space-between; gap: 18px; padding: 0 38px; border-bottom: 1px solid var(--line); background: rgba(255,255,255,.8); }
    .crumb { color: var(--muted); font-size: 12px; }
    .topbar-right { display: flex; align-items: center; gap: 12px; }
    .search-box { position: relative; }
    .search-box input { width: min(245px, 32vw); height: 38px; padding: 0 12px 0 35px; border: 1px solid var(--line); border-radius: 10px; color: var(--ink); background: #fff; font-size: 12px; }
    .search-symbol { position: absolute; top: 9px; left: 12px; color: #a28dad; font-size: 15px; pointer-events: none; }
    .button {
      display: inline-flex; align-items: center; justify-content: center; gap: 8px; min-height: 39px;
      padding: 0 14px; border: 1px solid transparent; border-radius: 10px; font-size: 12px; font-weight: 750;
      transition: transform .18s ease, box-shadow .18s ease, background .18s ease;
    }
    .button:hover { transform: translateY(-1px); }
    .button-primary { color: white; background: linear-gradient(110deg, var(--purple), var(--pink)); box-shadow: 0 7px 17px rgba(121,80,200,.18); }
    .button-primary:hover { box-shadow: 0 10px 23px rgba(121,80,200,.26); }
    .button-light { color: var(--purple-dark); border-color: var(--line); background: white; }
    .button-danger { color: #a34470; border-color: #f1d9e7; background: #fff8fb; }
    .icon-button { width: 36px; height: 36px; border: 1px solid var(--line); border-radius: 10px; color: var(--purple-dark); background: white; font-weight: 800; }
    .content { width: min(1240px, 100%); margin: 0 auto; padding: 34px 38px 54px; }
    .page-heading { display: flex; align-items: flex-end; justify-content: space-between; gap: 18px; margin-bottom: 25px; }
    .eyebrow { margin: 0 0 8px; color: var(--pink); font-size: 10px; font-weight: 850; letter-spacing: 1.2px; text-transform: uppercase; }
    h1 { margin: 0; color: var(--ink); font-size: clamp(25px, 3vw, 34px); letter-spacing: -1.25px; line-height: 1.15; }
    .subtitle { margin: 9px 0 0; color: var(--muted); font-size: 13px; line-height: 1.6; }
    .hero {
      position: relative; display: flex; align-items: center; justify-content: space-between; gap: 26px;
      min-height: 176px; overflow: hidden; padding: 29px 31px; border: 1px solid #f0dff1; border-radius: 19px;
      background:
        radial-gradient(circle at 90% 10%, rgba(231, 153, 203, .26), transparent 29%),
        radial-gradient(circle at 78% 100%, rgba(160, 125, 219, .20), transparent 32%),
        linear-gradient(110deg, #fff 0%, #fff8fc 50%, #f8f3ff 100%);
      box-shadow: var(--shadow);
    }
    .hero h2 { max-width: 550px; margin: 0; font-size: 22px; letter-spacing: -.6px; }
    .hero p { max-width: 510px; margin: 9px 0 18px; color: var(--muted); font-size: 12px; line-height: 1.65; }
    .hero-mark { display: grid; place-items: center; width: 88px; height: 88px; flex: 0 0 88px; border: 1px solid #ead8f5; border-radius: 26px; color: var(--purple); background: rgba(255,255,255,.75); font-size: 34px; box-shadow: 0 12px 30px rgba(121,80,200,.1); transform: rotate(7deg); }
    .stats { display: grid; grid-template-columns: repeat(3, minmax(0,1fr)); gap: 14px; margin: 20px 0; }
    .stat-card { padding: 17px 18px; border: 1px solid var(--line); border-radius: 15px; background: var(--paper); box-shadow: 0 7px 20px rgba(68,30,91,.035); }
    .stat-top { display: flex; justify-content: space-between; align-items: center; color: var(--muted); font-size: 11px; font-weight: 650; }
    .stat-bubble { display: grid; place-items: center; width: 30px; height: 30px; border-radius: 10px; color: var(--purple); background: var(--purple-soft); font-weight: 850; }
    .stat-card:nth-child(2) .stat-bubble { color: #bd4c8a; background: var(--pink-soft); }
    .stat-value { margin-top: 12px; font-size: 26px; font-weight: 850; letter-spacing: -.8px; }
    .stat-note { margin-top: 4px; color: #9b8aa3; font-size: 10px; }
    .section-grid { display: grid; grid-template-columns: minmax(0, 1.35fr) minmax(275px, .8fr); gap: 16px; align-items: start; }
    .panel { min-width: 0; padding: 19px; border: 1px solid var(--line); border-radius: 16px; background: var(--paper); box-shadow: 0 7px 20px rgba(68,30,91,.035); }
    .panel-heading { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-bottom: 14px; }
    .panel-heading h2 { margin: 0; font-size: 14px; letter-spacing: -.2px; }
    .text-button { border: 0; color: var(--purple-dark); background: none; font-size: 11px; font-weight: 750; }
    .session-feature { padding: 16px; border: 1px solid #f1d8eb; border-radius: 13px; background: linear-gradient(130deg, #fff6fb, #f8f3ff); }
    .session-date { color: var(--pink); font-size: 10px; font-weight: 850; letter-spacing: .6px; text-transform: uppercase; }
    .session-feature h3 { margin: 8px 0 5px; font-size: 15px; }
    .session-meta { color: var(--muted); font-size: 11px; }
    .lesson-list { display: grid; gap: 10px; }
    .lesson-row { display: flex; align-items: center; gap: 12px; padding: 12px; border: 1px solid #f2eaf4; border-radius: 12px; background: #fff; }
    .lesson-icon { display: grid; place-items: center; flex: 0 0 36px; height: 36px; border-radius: 11px; color: var(--purple); background: var(--purple-soft); font-weight: 850; }
    .lesson-row:nth-child(even) .lesson-icon { color: #bd4c8a; background: var(--pink-soft); }
    .lesson-copy { min-width: 0; flex: 1; }
    .lesson-title { overflow: hidden; color: var(--ink); font-size: 12px; font-weight: 760; text-overflow: ellipsis; white-space: nowrap; }
    .lesson-course { margin-top: 4px; color: var(--muted); font-size: 10px; }
    .lesson-card-grid { display: grid; grid-template-columns: repeat(2, minmax(0,1fr)); gap: 14px; }
    .lesson-card { display: flex; min-height: 186px; flex-direction: column; padding: 17px; border: 1px solid var(--line); border-radius: 15px; background: white; box-shadow: 0 7px 20px rgba(68,30,91,.035); transition: transform .2s ease, box-shadow .2s ease; }
    .lesson-card:hover { transform: translateY(-2px); box-shadow: var(--shadow); }
    .lesson-card h3 { margin: 12px 0 6px; font-size: 14px; line-height: 1.35; }
    .lesson-card p { display: -webkit-box; overflow: hidden; margin: 0; color: var(--muted); font-size: 11px; line-height: 1.55; -webkit-box-orient: vertical; -webkit-line-clamp: 3; }
    .lesson-footer { display: flex; justify-content: space-between; align-items: center; gap: 8px; margin-top: auto; padding-top: 15px; }
    .tag { display: inline-flex; align-items: center; padding: 5px 8px; border-radius: 999px; color: var(--purple-dark); background: var(--purple-soft); font-size: 9px; font-weight: 750; }
    .tag-pink { color: #a7447b; background: var(--pink-soft); }
    .card-actions { display: flex; gap: 6px; }
    .small-button { padding: 6px 9px; border: 1px solid var(--line); border-radius: 8px; color: var(--purple-dark); background: white; font-size: 10px; font-weight: 700; }
    .empty-state { padding: 29px 16px; border: 1px dashed #e7d7ef; border-radius: 13px; color: var(--muted); background: #fdfaff; text-align: center; font-size: 12px; line-height: 1.6; }
    .empty-state strong { display: block; margin-bottom: 4px; color: var(--ink); font-size: 13px; }
    .calendar-toolbar { display: flex; align-items: center; justify-content: space-between; margin: 16px 0 12px; }
    .calendar-toolbar strong { font-size: 13px; }
    .calendar-controls { display: flex; gap: 7px; }
    .calendar-grid { display: grid; grid-template-columns: repeat(7, minmax(0, 1fr)); gap: 5px; }
    .weekday { padding: 7px 0; color: #9b8aa3; text-align: center; font-size: 9px; font-weight: 800; text-transform: uppercase; }
    .day-cell { min-height: 67px; padding: 6px; border: 1px solid #f2eaf4; border-radius: 9px; background: white; }
    .day-cell.muted-day { opacity: .37; }
    .day-cell.today { border-color: #d3b9ee; background: #fcf8ff; }
    .day-number { font-size: 10px; font-weight: 750; }
    .day-event { display: block; overflow: hidden; margin-top: 5px; padding: 3px 4px; border-radius: 5px; color: #8f3d77; background: #ffedf7; font-size: 8px; text-overflow: ellipsis; white-space: nowrap; }
    .schedule-list { display: grid; gap: 9px; margin-top: 15px; }
    .schedule-item { display: grid; grid-template-columns: 48px 1fr auto; align-items: center; gap: 12px; padding: 11px 12px; border: 1px solid #f1e8f4; border-radius: 12px; }
    .schedule-time { color: var(--purple-dark); font-size: 11px; font-weight: 800; }
    .schedule-title { font-size: 11px; font-weight: 760; }
    .schedule-course { margin-top: 3px; color: var(--muted); font-size: 10px; }
    .schedule-date { color: var(--muted); font-size: 10px; white-space: nowrap; }
    .dialog {
      width: min(500px, calc(100vw - 28px)); max-height: min(88vh, 760px); padding: 0; overflow: auto;
      border: 1px solid #eadcf0; border-radius: 18px; color: var(--ink); background: white; box-shadow: 0 25px 90px rgba(49,20,65,.25);
    }
    .dialog::backdrop { background: rgba(43,20,55,.33); backdrop-filter: blur(3px); }
    .dialog-inner { padding: 24px; }
    .dialog-header { display: flex; align-items: start; justify-content: space-between; gap: 16px; margin-bottom: 19px; }
    .dialog-header h2 { margin: 0; font-size: 19px; letter-spacing: -.4px; }
    .dialog-header p { margin: 6px 0 0; color: var(--muted); font-size: 11px; }
    .close-button { width: 31px; height: 31px; border: 1px solid var(--line); border-radius: 9px; color: var(--muted); background: white; font-size: 17px; }
    .form-grid { display: grid; gap: 13px; }
    .field { display: grid; gap: 6px; }
    .field label { color: #5e4869; font-size: 11px; font-weight: 750; }
    .field input, .field textarea { width: 100%; padding: 10px 11px; border: 1px solid #e8ddeb; border-radius: 9px; color: var(--ink); background: #fff; font-size: 12px; }
    .field textarea { min-height: 84px; resize: vertical; }
    .field-row { display: grid; grid-template-columns: 1fr 1fr; gap: 11px; }
    .form-actions { display: flex; justify-content: flex-end; gap: 8px; margin-top: 5px; }
    .toast { position: fixed; z-index: 5; right: 22px; bottom: 22px; max-width: min(380px, calc(100vw - 44px)); padding: 12px 16px; border: 1px solid #e8d7ef; border-radius: 11px; color: var(--purple-dark); background: white; box-shadow: var(--shadow); font-size: 12px; opacity: 0; transform: translateY(9px); pointer-events: none; transition: opacity .2s ease, transform .2s ease; }
    .toast.show { opacity: 1; transform: translateY(0); }
    #printRoot { display: none; }
    .mobile-menu { display: none; }

    @media (max-width: 900px) {
      .shell { grid-template-columns: 210px minmax(0,1fr); }
      .topbar { padding: 0 23px; }
      .content { padding: 28px 23px 42px; }
      .section-grid { grid-template-columns: 1fr; }
    }
    @media (max-width: 650px) {
      .shell { display: block; }
      .sidebar { position: fixed; z-index: 4; left: 0; top: 0; width: 248px; height: 100dvh; box-shadow: 18px 0 50px rgba(49,20,65,.14); transform: translateX(-105%); transition: transform .2s ease; }
      body.menu-open .sidebar { transform: translateX(0); }
      .topbar { height: 64px; padding: 0 15px; }
      .crumb { display: none; }
      .mobile-menu { display: inline-grid; place-items: center; }
      .search-box input { width: min(180px, 38vw); }
      .topbar .button { min-height: 36px; padding: 0 10px; font-size: 11px; }
      .content { padding: 24px 15px 38px; }
      .hero { align-items: flex-start; min-height: 0; padding: 22px; }
      .hero-mark { width: 58px; height: 58px; flex-basis: 58px; border-radius: 19px; font-size: 25px; }
      .hero h2 { font-size: 19px; }
      .stats { gap: 8px; }
      .stat-card { padding: 12px; }
      .stat-value { font-size: 22px; }
      .stat-note { min-height: 22px; }
      .lesson-card-grid { grid-template-columns: 1fr; }
      .panel { padding: 14px; }
      .day-cell { min-height: 52px; padding: 4px; }
      .day-event { font-size: 7px; }
    }
    @media (max-width: 390px) {
      .topbar-right { gap: 7px; }
      .search-box input { width: 35vw; }
      .stats { grid-template-columns: 1fr; }
      .stat-card { display: flex; align-items: center; justify-content: space-between; }
      .stat-value { margin: 0; }
      .stat-note { display: none; }
      .hero-mark { display: none; }
    }
    @media print {
      body.printing #app { display: none !important; }
      body.printing #printRoot { display: block !important; padding: 35px; color: #25152d; font-family: Georgia, serif; }
      body.printing #printRoot h1 { margin-bottom: 8px; font-family: Georgia, serif; }
      body.printing #printRoot .print-meta { margin-bottom: 22px; color: #765c80; font: 12px system-ui, sans-serif; }
      body.printing #printRoot .print-body { white-space: pre-wrap; font-size: 14px; line-height: 1.75; }
    }
    @media (prefers-reduced-motion: reduce) {
      *, *::before, *::after { scroll-behavior: auto !important; animation-duration: .01ms !important; transition-duration: .01ms !important; }
    }
  </style>
</head>
<body>
  <div id="app" class="shell">
    <aside class="sidebar" aria-label="Main navigation">
      <div class="brand">
        <div class="brand-mark" aria-hidden="true">L</div>
        <div><div class="brand-name">LectureCraft AI</div><div class="brand-caption">Teaching workspace</div></div>
      </div>
      <div class="nav-label">Workspace</div>
      <nav class="nav-list">
        <button class="nav-button active" data-page="overview"><span class="nav-icon">⌂</span>Overview</button>
        <button class="nav-button" data-page="lessons"><span class="nav-icon">▤</span>Lesson plans</button>
        <button class="nav-button" data-page="schedule"><span class="nav-icon">▦</span>Schedule</button>
      </nav>
      <div class="sidebar-bottom">
        <div class="tip-card">
          <p class="tip-title">A thoughtful teaching day</p>
          <p class="tip-text">Keep lesson ideas and class sessions together, ready whenever you need them.</p>
        </div>
        <div class="profile">
          <div class="avatar" aria-hidden="true">B</div>
          <div><div class="profile-name">Bhumika</div><div class="profile-caption">Teaching workspace</div></div>
        </div>
      </div>
    </aside>

    <section class="main-area">
      <header class="topbar">
        <div style="display:flex;align-items:center;gap:12px">
          <button id="mobileMenu" class="icon-button mobile-menu" aria-label="Open navigation">☰</button>
          <div class="crumb">Workspace <span aria-hidden="true">/</span> <strong id="crumbPage">Overview</strong></div>
        </div>
        <div class="topbar-right">
          <label class="search-box">
            <span class="search-symbol" aria-hidden="true">⌕</span>
            <input id="globalSearch" type="search" placeholder="Search lessons…" aria-label="Search lesson plans">
          </label>
          <button class="button button-primary" data-action="new-lesson"><span aria-hidden="true">＋</span> New lesson</button>
        </div>
      </header>
      <main id="content" class="content" tabindex="-1"></main>
    </section>
  </div>

  <dialog id="lessonDialog" class="dialog" aria-labelledby="lessonDialogTitle">
    <div class="dialog-inner">
      <div class="dialog-header">
        <div><h2 id="lessonDialogTitle">Create a lesson plan</h2><p>Capture the key idea and teaching notes.</p></div>
        <button class="close-button" data-close="lessonDialog" aria-label="Close">×</button>
      </div>
      <form id="lessonForm" class="form-grid">
        <div class="field"><label for="lessonTitle">Lesson title</label><input id="lessonTitle" name="title" maxlength="100" required placeholder="For example, The water cycle"></div>
        <div class="field"><label for="lessonCourse">Course or subject</label><input id="lessonCourse" name="course" maxlength="80" placeholder="For example, Environmental science"></div>
        <div class="field"><label for="lessonSummary">Teaching notes</label><textarea id="lessonSummary" name="summary" maxlength="1500" placeholder="Add objectives, activities, key questions, or materials."></textarea></div>
        <div class="form-actions"><button type="button" class="button button-light" data-close="lessonDialog">Cancel</button><button class="button button-primary" type="submit">Save lesson</button></div>
      </form>
    </div>
  </dialog>

  <dialog id="sessionDialog" class="dialog" aria-labelledby="sessionDialogTitle">
    <div class="dialog-inner">
      <div class="dialog-header">
        <div><h2 id="sessionDialogTitle">Add a class session</h2><p>Put an upcoming teaching session on your schedule.</p></div>
        <button class="close-button" data-close="sessionDialog" aria-label="Close">×</button>
      </div>
      <form id="sessionForm" class="form-grid">
        <div class="field"><label for="sessionTitle">Session title</label><input id="sessionTitle" name="title" maxlength="100" required placeholder="For example, Intro to ecosystems"></div>
        <div class="field"><label for="sessionCourse">Course or subject</label><input id="sessionCourse" name="course" maxlength="80" placeholder="For example, Biology"></div>
        <div class="field-row">
          <div class="field"><label for="sessionDate">Date</label><input id="sessionDate" name="date" type="date" required></div>
          <div class="field"><label for="sessionTime">Time</label><input id="sessionTime" name="time" type="time" required value="09:00"></div>
        </div>
        <div class="form-actions"><button type="button" class="button button-light" data-close="sessionDialog">Cancel</button><button class="button button-primary" type="submit">Save session</button></div>
      </form>
    </div>
  </dialog>

  <div id="toast" class="toast" role="status" aria-live="polite"></div>
  <div id="printRoot" aria-hidden="true"></div>

  <script>
    const content = document.getElementById("content");
    const toastNode = document.getElementById("toast");
    let appState = {lessons: [], sessions: []};
    let currentPage = "overview";
    let calendarMonth = new Date(new Date().getFullYear(), new Date().getMonth(), 1);
    let toastTimer;

    const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({
      "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
    })[char]);
    const localKey = (date) => `${date.getFullYear()}-${String(date.getMonth()+1).padStart(2,"0")}-${String(date.getDate()).padStart(2,"0")}`;
    const dateLabel = (key, options = {weekday:"short", month:"short", day:"numeric"}) => {
      const d = new Date(`${key}T12:00:00`);
      return Number.isNaN(d.getTime()) ? key : d.toLocaleDateString(undefined, options);
    };
    const isUpcoming = (session) => new Date(`${session.date}T${session.time}:00`).getTime() > Date.now();
    const sortedUpcoming = () => [...appState.sessions].filter(isUpcoming).sort((a,b) =>
      `${a.date}T${a.time}`.localeCompare(`${b.date}T${b.time}`));
    const greeting = () => {
      const hour = new Date().getHours();
      return hour < 12 ? "Good morning" : hour < 18 ? "Good afternoon" : "Good evening";
    };

    async function request(url, options = {}) {
      const response = await fetch(url, {
        ...options,
        headers: {"Content-Type":"application/json", ...(options.headers || {})}
      });
      const body = await response.json().catch(() => ({}));
      if (!response.ok) throw new Error(body.error || "The request could not be completed.");
      return body;
    }
    async function refresh() {
      appState = await request("/api/state");
      render();
    }
    function notify(message) {
      toastNode.textContent = message;
      toastNode.classList.add("show");
      clearTimeout(toastTimer);
      toastTimer = setTimeout(() => toastNode.classList.remove("show"), 2800);
    }
    function setPage(page) {
      currentPage = page;
      document.body.classList.remove("menu-open");
      document.querySelectorAll(".nav-button").forEach((button) => {
        button.classList.toggle("active", button.dataset.page === page);
      });
      document.getElementById("crumbPage").textContent = page === "overview" ? "Overview" : page === "lessons" ? "Lesson plans" : "Schedule";
      render();
      content.focus({preventScroll:true});
    }
    function emptyState(title, text, actionLabel, action) {
      return `<div class="empty-state"><strong>${escapeHtml(title)}</strong>${escapeHtml(text)}${actionLabel ? `<div style="margin-top:14px"><button class="button button-light" data-action="${action}">${escapeHtml(actionLabel)}</button></div>` : ""}</div>`;
    }
    function lessonRow(lesson) {
      return `<div class="lesson-row">
        <div class="lesson-icon" aria-hidden="true">${escapeHtml((lesson.title || "L").trim().charAt(0).toUpperCase())}</div>
        <div class="lesson-copy"><div class="lesson-title">${escapeHtml(lesson.title)}</div><div class="lesson-course">${escapeHtml(lesson.course || "General teaching")}</div></div>
        <button class="small-button" data-print="${escapeHtml(lesson.id)}">Print</button>
      </div>`;
    }
    function lessonCard(lesson) {
      return `<article class="lesson-card">
        <div><span class="tag">${escapeHtml(lesson.course || "General teaching")}</span></div>
        <h3>${escapeHtml(lesson.title)}</h3>
        <p>${escapeHtml(lesson.summary || "Add teaching notes to keep objectives, activities, and materials together.")}</p>
        <div class="lesson-footer">
          <span class="tag tag-pink">Lesson plan</span>
          <div class="card-actions">
            <button class="small-button" data-print="${escapeHtml(lesson.id)}">Print</button>
            <button class="small-button" data-delete-lesson="${escapeHtml(lesson.id)}" aria-label="Delete ${escapeHtml(lesson.title)}">Delete</button>
          </div>
        </div>
      </article>`;
    }
    function sessionFeature(session) {
      if (!session) return emptyState("Nothing scheduled yet", "Add a class session to see it here.", "Add session", "new-session");
      return `<div class="session-feature">
        <div class="session-date">${escapeHtml(dateLabel(session.date))} · ${escapeHtml(session.time)}</div>
        <h3>${escapeHtml(session.title)}</h3>
        <div class="session-meta">${escapeHtml(session.course || "General teaching")}</div>
      </div>`;
    }
    function renderOverview() {
      const upcoming = sortedUpcoming();
      const recent = [...appState.lessons].sort((a,b) => (b.created_at || "").localeCompare(a.created_at || "")).slice(0,4);
      return `<div class="page-heading">
        <div><p class="eyebrow">Your teaching workspace</p><h1>${greeting()}, Bhumika</h1><p class="subtitle">A clear view of your lesson ideas and upcoming classes.</p></div>
        <button class="button button-primary" data-action="new-session">＋ Add session</button>
      </div>
      <section class="hero">
        <div><p class="eyebrow">A little more organized</p><h2>Make room for the ideas that make a lesson click.</h2><p>Keep your class plans and schedule in one calm, easy-to-scan workspace.</p><button class="button button-primary" data-action="new-lesson">Create a lesson plan</button></div>
        <div class="hero-mark" aria-hidden="true">✦</div>
      </section>
      <section class="stats" aria-label="Workspace summary">
        <div class="stat-card"><div class="stat-top">Lesson plans <span class="stat-bubble">L</span></div><div class="stat-value">${appState.lessons.length}</div><div class="stat-note">Saved in your workspace</div></div>
        <div class="stat-card"><div class="stat-top">Upcoming sessions <span class="stat-bubble">S</span></div><div class="stat-value">${upcoming.length}</div><div class="stat-note">Future classes on your schedule</div></div>
        <div class="stat-card"><div class="stat-top">Next teaching day <span class="stat-bubble">↗</span></div><div class="stat-value" style="font-size:18px">${upcoming.length ? escapeHtml(dateLabel(upcoming[0].date,{month:"short",day:"numeric"})) : "—"}</div><div class="stat-note">${upcoming.length ? escapeHtml(upcoming[0].title) : "No session scheduled"}</div></div>
      </section>
      <div class="section-grid">
        <section class="panel"><div class="panel-heading"><h2>Recent lesson plans</h2><button class="text-button" data-page="lessons">View all</button></div>
          ${recent.length ? `<div class="lesson-list">${recent.map(lessonRow).join("")}</div>` : emptyState("Your lesson library starts here", "Create a plan to keep your teaching notes close at hand.", "New lesson plan", "new-lesson")}
        </section>
        <section class="panel"><div class="panel-heading"><h2>Coming up</h2><button class="text-button" data-page="schedule">View schedule</button></div>${sessionFeature(upcoming[0])}</section>
      </div>`;
    }
    function renderLessons() {
      const query = document.getElementById("globalSearch").value.trim().toLowerCase();
      const lessons = [...appState.lessons]
        .filter((lesson) => `${lesson.title} ${lesson.course} ${lesson.summary}`.toLowerCase().includes(query))
        .sort((a,b) => (b.created_at || "").localeCompare(a.created_at || ""));
      return `<div class="page-heading">
        <div><p class="eyebrow">Your library</p><h1>Lesson plans</h1><p class="subtitle">Keep useful teaching ideas together and ready to print.</p></div>
        <button class="button button-primary" data-action="new-lesson">＋ New lesson</button>
      </div>
      ${lessons.length ? `<div class="lesson-card-grid">${lessons.map(lessonCard).join("")}</div>` :
        emptyState(query ? "No matching lesson plans" : "No lesson plans yet", query ? "Try another search term." : "Create your first lesson plan to start building your library.", query ? "" : "Create lesson plan", query ? "" : "new-lesson")}`;
    }
    function renderCalendar() {
      const year = calendarMonth.getFullYear();
      const month = calendarMonth.getMonth();
      const first = new Date(year, month, 1);
      const startOffset = (first.getDay() + 6) % 7;
      const daysThisMonth = new Date(year, month + 1, 0).getDate();
      const daysPreviousMonth = new Date(year, month, 0).getDate();
      const todayKey = localKey(new Date());
      const cells = [];
      for (let index = 0; index < 42; index++) {
        let day, date, isCurrentMonth = true;
        if (index < startOffset) { day = daysPreviousMonth - startOffset + index + 1; date = new Date(year, month - 1, day); isCurrentMonth = false; }
        else if (index >= startOffset + daysThisMonth) { day = index - startOffset - daysThisMonth + 1; date = new Date(year, month + 1, day); isCurrentMonth = false; }
        else { day = index - startOffset + 1; date = new Date(year, month, day); }
        const key = localKey(date);
        const matching = appState.sessions.filter((session) => session.date === key);
        cells.push(`<div class="day-cell ${isCurrentMonth ? "" : "muted-day"} ${key === todayKey ? "today" : ""}">
          <div class="day-number">${day}</div>${matching.slice(0,2).map((session) => `<span class="day-event" title="${escapeHtml(session.title)}">${escapeHtml(session.title)}</span>`).join("")}
        </div>`);
      }
      return `<section class="panel">
        <div class="panel-heading"><h2>Monthly calendar</h2><button class="button button-light" data-action="new-session">＋ Add session</button></div>
        <div class="calendar-toolbar"><strong>${calendarMonth.toLocaleDateString(undefined,{month:"long",year:"numeric"})}</strong>
          <div class="calendar-controls"><button class="icon-button" data-calendar="-1" aria-label="Previous month">‹</button><button class="icon-button" data-calendar="1" aria-label="Next month">›</button></div>
        </div>
        <div class="calendar-grid" aria-label="Calendar"><div class="weekday">Mon</div><div class="weekday">Tue</div><div class="weekday">Wed</div><div class="weekday">Thu</div><div class="weekday">Fri</div><div class="weekday">Sat</div><div class="weekday">Sun</div>${cells.join("")}</div>
      </section>`;
    }
    function renderSchedule() {
      const upcoming = sortedUpcoming();
      const sessionRows = upcoming.map((session) => `<div class="schedule-item">
        <div class="schedule-time">${escapeHtml(session.time)}</div>
        <div><div class="schedule-title">${escapeHtml(session.title)}</div><div class="schedule-course">${escapeHtml(session.course || "General teaching")}</div></div>
        <div style="display:flex;align-items:center;gap:8px"><span class="schedule-date">${escapeHtml(dateLabel(session.date))}</span><button class="small-button" data-delete-session="${escapeHtml(session.id)}" aria-label="Delete ${escapeHtml(session.title)}">Delete</button></div>
      </div>`).join("");
      return `<div class="page-heading">
        <div><p class="eyebrow">Plan your teaching day</p><h1>Schedule</h1><p class="subtitle">Browse the month or review upcoming class sessions.</p></div>
        <button class="button button-primary" data-action="new-session">＋ Add session</button>
      </div>
      ${renderCalendar()}
      <section class="panel" style="margin-top:16px"><div class="panel-heading"><h2>Upcoming sessions</h2><span class="tag tag-pink">${upcoming.length} scheduled</span></div>
        ${sessionRows ? `<div class="schedule-list">${sessionRows}</div>` : emptyState("No upcoming sessions", "Add a class session and it will appear here.", "Add session", "new-session")}
      </section>`;
    }
    function render() {
      content.innerHTML = currentPage === "lessons" ? renderLessons() : currentPage === "schedule" ? renderSchedule() : renderOverview();
    }
    function openDialog(id) {
      const dialog = document.getElementById(id);
      if (id === "sessionDialog") {
        const dateInput = document.getElementById("sessionDate");
        if (!dateInput.value) dateInput.value = localKey(new Date());
      }
      dialog.showModal();
    }
    function printLesson(id) {
      const lesson = appState.lessons.find((item) => item.id === id);
      if (!lesson) return;
      const printRoot = document.getElementById("printRoot");
      printRoot.innerHTML = `<p class="eyebrow">LectureCraft AI · Bhumika's teaching workspace</p>
        <h1>${escapeHtml(lesson.title)}</h1><div class="print-meta">${escapeHtml(lesson.course || "General teaching")}</div>
        <div class="print-body">${escapeHtml(lesson.summary || "No teaching notes added yet.")}</div>`;
      document.body.classList.add("printing");
      window.addEventListener("afterprint", () => {
        document.body.classList.remove("printing");
        printRoot.innerHTML = "";
      }, {once:true});
      window.print();
    }

    document.addEventListener("click", async (event) => {
      const target = event.target.closest("button");
      if (!target) return;
      if (target.dataset.page) { setPage(target.dataset.page); return; }
      if (target.dataset.action === "new-lesson") { openDialog("lessonDialog"); return; }
      if (target.dataset.action === "new-session") { openDialog("sessionDialog"); return; }
      if (target.dataset.close) { document.getElementById(target.dataset.close).close(); return; }
      if (target.dataset.calendar) {
        calendarMonth.setMonth(calendarMonth.getMonth() + Number(target.dataset.calendar), 1);
        render(); return;
      }
      if (target.dataset.print) { printLesson(target.dataset.print); return; }
      if (target.dataset.deleteLesson || target.dataset.deleteSession) {
        const isLesson = Boolean(target.dataset.deleteLesson);
        const id = target.dataset.deleteLesson || target.dataset.deleteSession;
        if (!window.confirm(isLesson ? "Delete this lesson plan?" : "Delete this class session?")) return;
        try {
          await request(`/api/${isLesson ? "lessons" : "sessions"}/${encodeURIComponent(id)}`, {method:"DELETE"});
          await refresh();
          notify(isLesson ? "Lesson plan deleted." : "Session deleted.");
        } catch (error) { notify(error.message); }
      }
    });

    document.getElementById("globalSearch").addEventListener("input", () => {
      if (currentPage === "lessons") render();
    });
    document.getElementById("mobileMenu").addEventListener("click", () => document.body.classList.toggle("menu-open"));
    document.querySelectorAll(".dialog").forEach((dialog) => {
      dialog.addEventListener("click", (event) => {
        if (event.target === dialog) dialog.close();
      });
    });
    document.getElementById("lessonForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      try {
        await request("/api/lessons", {method:"POST", body:JSON.stringify({
          title:form.get("title"), course:form.get("course"), summary:form.get("summary")
        })});
        event.currentTarget.reset();
        document.getElementById("lessonDialog").close();
        await refresh();
        notify("Lesson plan saved.");
      } catch (error) { notify(error.message); }
    });
    document.getElementById("sessionForm").addEventListener("submit", async (event) => {
      event.preventDefault();
      const form = new FormData(event.currentTarget);
      try {
        await request("/api/sessions", {method:"POST", body:JSON.stringify({
          title:form.get("title"), course:form.get("course"), date:form.get("date"), time:form.get("time")
        })});
        event.currentTarget.reset();
        document.getElementById("sessionTime").value = "09:00";
        document.getElementById("sessionDialog").close();
        await refresh();
        notify("Class session added.");
      } catch (error) { notify(error.message); }
    });
    refresh().catch((error) => {
      content.innerHTML = `<div class="empty-state"><strong>Could not load your workspace</strong>${escapeHtml(error.message)} Check that the Python server is running and try again.</div>`;
    });
  </script>
</body>
</html>
"""


def empty_state() -> dict[str, list[dict]]:
    return {"lessons": [], "sessions": []}


def read_state() -> dict[str, list[dict]]:
    if not DATA_FILE.exists():
        return empty_state()
    with DATA_FILE.open("r", encoding="utf-8") as file:
        state = json.load(file)
    if not isinstance(state, dict):
        raise ValueError("The data file must contain a JSON object.")
    lessons = state.get("lessons", [])
    sessions = state.get("sessions", [])
    if not isinstance(lessons, list) or not isinstance(sessions, list):
        raise ValueError("The data file has an invalid lessons or sessions list.")
    return {"lessons": lessons, "sessions": sessions}


def write_state(state: dict[str, list[dict]]) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = DATA_FILE.with_name(f".{DATA_FILE.name}.{uuid.uuid4().hex}.tmp")
    try:
        with temp_file.open("w", encoding="utf-8") as file:
            json.dump(state, file, ensure_ascii=False, indent=2)
            file.flush()
            os.fsync(file.fileno())
        os.replace(temp_file, DATA_FILE)
    finally:
        if temp_file.exists():
            temp_file.unlink()


def clean_text(value: object, limit: int, field_name: str, required: bool = False) -> str:
    if value is None:
        text = ""
    elif isinstance(value, str):
        text = value.strip()
    else:
        raise ValueError(f"{field_name} must be text.")
    if required and not text:
        raise ValueError(f"{field_name} is required.")
    if len(text) > limit:
        raise ValueError(f"{field_name} must be {limit} characters or fewer.")
    return text


def valid_date(value: object) -> str:
    text = clean_text(value, 10, "Date", required=True)
    if not re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        raise ValueError("Date must use the YYYY-MM-DD format.")
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as error:
        raise ValueError("Enter a real calendar date.") from error
    return text


def valid_time(value: object) -> str:
    text = clean_text(value, 5, "Time", required=True)
    if not re.fullmatch(r"\d{2}:\d{2}", text):
        raise ValueError("Time must use the HH:MM format.")
    try:
        datetime.strptime(text, "%H:%M")
    except ValueError as error:
        raise ValueError("Enter a valid time.") from error
    return text


class LectureCraftHandler(BaseHTTPRequestHandler):
    server_version = "LectureCraftPython/1.0"

    def send_bytes(self, body: bytes, content_type: str, status: int = 200) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "same-origin")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def send_json(self, data: dict, status: int = 200) -> None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_bytes(body, "application/json; charset=utf-8", status)

    def send_problem(self, message: str, status: int = 400) -> None:
        self.send_json({"error": message}, status)

    def read_json_body(self) -> dict:
        raw_length = self.headers.get("Content-Length", "0")
        try:
            length = int(raw_length)
        except ValueError as error:
            raise ValueError("Invalid request length.") from error
        if length < 0 or length > MAX_BODY_BYTES:
            raise ValueError("Request is too large.")
        if length == 0:
            return {}
        try:
            value = json.loads(self.rfile.read(length).decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            raise ValueError("Request body must be valid JSON.") from error
        if not isinstance(value, dict):
            raise ValueError("Request body must be a JSON object.")
        return value

    def do_GET(self) -> None:
        route = urlparse(self.path).path
        if route in ("/", "/index.html"):
            self.send_bytes(PAGE.encode("utf-8"), "text/html; charset=utf-8")
            return
        if route == "/healthz":
            self.send_json({"ok": True})
            return
        if route == "/api/state":
            try:
                with STORE_LOCK:
                    self.send_json(read_state())
            except (OSError, ValueError, json.JSONDecodeError) as error:
                self.send_problem(f"Could not read saved workspace data: {error}", 500)
            return
        if route == "/favicon.ico":
            self.send_bytes(b"", "image/x-icon", 204)
            return
        self.send_problem("Route not found.", 404)

    def do_POST(self) -> None:
        route = urlparse(self.path).path
        try:
            payload = self.read_json_body()
            if route == "/api/lessons":
                lesson = {
                    "id": uuid.uuid4().hex,
                    "title": clean_text(payload.get("title"), 100, "Lesson title", required=True),
                    "course": clean_text(payload.get("course"), 80, "Course"),
                    "summary": clean_text(payload.get("summary"), 1500, "Teaching notes"),
                    "created_at": datetime.now().astimezone().isoformat(timespec="seconds"),
                }
                with STORE_LOCK:
                    state = read_state()
                    state["lessons"].insert(0, lesson)
                    write_state(state)
                self.send_json(lesson, 201)
                return
            if route == "/api/sessions":
                session = {
                    "id": uuid.uuid4().hex,
                    "title": clean_text(payload.get("title"), 100, "Session title", required=True),
                    "course": clean_text(payload.get("course"), 80, "Course"),
                    "date": valid_date(payload.get("date")),
                    "time": valid_time(payload.get("time")),
                }
                with STORE_LOCK:
                    state = read_state()
                    state["sessions"].append(session)
                    write_state(state)
                self.send_json(session, 201)
                return
            self.send_problem("Route not found.", 404)
        except ValueError as error:
            self.send_problem(str(error), 400)
        except (OSError, json.JSONDecodeError) as error:
            self.send_problem(f"Could not save workspace data: {error}", 500)

    def do_DELETE(self) -> None:
        parts = [unquote(part) for part in urlparse(self.path).path.strip("/").split("/")]
        if len(parts) != 3 or parts[0] != "api" or parts[1] not in ("lessons", "sessions"):
            self.send_problem("Route not found.", 404)
            return
        collection, item_id = parts[1], parts[2]
        try:
            with STORE_LOCK:
                state = read_state()
                previous_count = len(state[collection])
                state[collection] = [item for item in state[collection] if item.get("id") != item_id]
                if len(state[collection]) == previous_count:
                    self.send_problem("That item no longer exists.", 404)
                    return
                write_state(state)
            self.send_json({"ok": True})
        except (OSError, ValueError, json.JSONDecodeError) as error:
            self.send_problem(f"Could not update workspace data: {error}", 500)

    def log_message(self, format_string: str, *args: object) -> None:
        print(f"{self.address_string()} - {format_string % args}")


def main() -> None:
    try:
        server = ThreadingHTTPServer((HOST, PORT), LectureCraftHandler)
    except OSError as error:
        raise SystemExit(f"Could not start the LectureCraft server: {error}") from error
    print(f"LectureCraft Python is running at http://{HOST}:{PORT}")
    print(f"Workspace data will be saved in: {DATA_FILE}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping LectureCraft Python.")
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
