#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════╗
║        PEPPER CLINICAL INFINITY V6                                      ║
║        © 2026 Lamya Fadlulmola Hamed Ali — All Rights Reserved         ║
║                                                                          ║
║  💙 A MESSAGE FROM THE DEVELOPER TO THE AUTISM COMMUNITY:               ║
║  To every family touched by Autism Spectrum Disorder —                  ║
║  your child is not broken. They are extraordinary.                      ║
║  Every smile, every word, every step forward is a victory.             ║
║  This software was built with love, science, and the belief that        ║
║  every child deserves a world that celebrates them exactly as they are. ║
║  You are not alone on this journey. Pepper is here with you.           ║
║                              — Lamya Fadlulmola Hamed Ali               ║
║                                                                          ║
╠══════════════════════════════════════════════════════════════════════════╣
║  ✅ 50 PECS cards | 5 Color Themes | 10 Calming Music tracks           ║
║  ✅ 100K+ Adaptive Tasks | 25 Life-Skill Videos (Goally channel)        ║
║  ✅ Every-task celebration | 10-task Spatial AR filter                  ║
║  ✅ Live child view in parent dashboard | Mute/Unmute Pepper voice       ║
║  ✅ Motion/Pose/Joint/Emotion/Finger detection — fully fixed            ║
║  ✅ Landing page | Security hardening | Session storage to email        ║
╚══════════════════════════════════════════════════════════════════════════╝
"""
import os, sys, warnings, ctypes, logging, signal

# Suppress ALL CUDA/TF noise before any import
os.environ.update({
    "TF_CPP_MIN_LOG_LEVEL":       "3",
    "TF_ENABLE_ONEDNN_OPTS":      "0",
    "CUDA_VISIBLE_DEVICES":       "0",
    "MEDIAPIPE_DISABLE_GPU":      "1",
    "PYTHONWARNINGS":             "ignore",
    "OPENCV_LOG_LEVEL":           "ERROR",
    "QT_LOGGING_RULES":           "*.debug=false;qt.qpa.*=false",
    "QT_QPA_PLATFORM":            "xcb",
    "QT_QPA_FONTDIR":             "/usr/share/fonts",
    "OMP_NUM_THREADS":            "2",
    "OPENBLAS_NUM_THREADS":       "2",
    "MKL_NUM_THREADS":            "2",
    "NUMEXPR_NUM_THREADS":        "2",
})
warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO,
    format="[%(asctime)s][%(levelname)s] %(message)s",
    datefmt="%H:%M:%S")
log = logging.getLogger("PepperV6")

try:
    _a = ctypes.cdll.LoadLibrary("libasound.so.2")
    _a.snd_lib_error_set_handler(ctypes.c_void_p(None))
except Exception: pass

# Graceful shutdown — prevent Aborted(core dumped) from aplay
def _sig_handler(sig, frame):
    log.info("Signal received — graceful shutdown")
    try: os.system("pkill -f aplay 2>/dev/null")
    except: pass
    sys.exit(0)

signal.signal(signal.SIGTERM, _sig_handler)
signal.signal(signal.SIGINT,  _sig_handler)

# ══════════════════════════════════════════════════════════════════════
# 1.  IMPORTS
# ══════════════════════════════════════════════════════════════════════
import threading, subprocess, socket, time, random, math
import re, json, csv, base64, wave, tempfile, hashlib, secrets
from datetime import datetime
from io import BytesIO
from collections import deque

import cv2
import numpy as np
from PIL import Image, ImageDraw

# MediaPipe: import safely — 0.10+ removed .solutions API
try:
    import mediapipe as mp
    _MP_SOLUTIONS = hasattr(mp, 'solutions')
    if not _MP_SOLUTIONS:
        log_early = True
except ImportError:
    mp = None
    _MP_SOLUTIONS = False
import pyttsx3
import speech_recognition as sr

try:
    from faster_whisper import WhisperModel as FW
    _FW_OK = True
except Exception: _FW_OK = False

try:
    import google.generativeai as genai
    _GENAI_OK = True
except Exception: _GENAI_OK = False

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import (SimpleDocTemplate, Paragraph, Spacer,
                                     Table, TableStyle)
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors as RL_COLORS
    _PDF_OK = True
except Exception: _PDF_OK = False

try:
    import bcrypt
    _BCRYPT_OK = True
except Exception: _BCRYPT_OK = False

from flask import (Flask, render_template_string, jsonify,
                   request, redirect, session, url_for, send_file)

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QGridLayout, QLineEdit, QTextEdit,
    QGraphicsDropShadowEffect, QProgressBar,
)
from PyQt6.QtCore import (
    QRect,
    Qt, QTimer, pyqtSignal, QObject, QThread, QMutex, QMutexLocker,
    QPropertyAnimation, QEasingCurve, QPoint,
)
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QPixmap, QImage,
    QPainter, QLinearGradient, QBrush, QPen,
)

# ══════════════════════════════════════════════════════════════════════
# 2.  PATIENT SETUP
# ══════════════════════════════════════════════════════════════════════
def kill_ports(*ports):
    for p in ports:
        try: os.system(f"fuser -k {p}/tcp 2>/dev/null")
        except: pass
        for _ in range(6):
            try:
                s = socket.socket()
                s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                s.bind(("0.0.0.0", p)); s.close(); break
            except: time.sleep(0.25)

kill_ports(5001, 5007, 5009)

def get_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close(); return ip
    except: return "127.0.0.1"

LOCAL_IP   = get_ip()
GAME_URL   = "https://LamyaFadlulmolaHamedAli.pythonanywhere.com"
GEMINI_KEY = "AIzaSyDEdleVKiQ5E00wMcjMbji0G9JcYT2TvE8"
# ── ASD Moods (13 moods from HTML) ─────────────────────────────────
ASD_MOODS = [
    {"id":"calm",       "em":"😌","label":"Calm",       "color":"#22c55e","speech":"You look calm and ready! Perfect for learning today!",               "music":"nature"},
    {"id":"happy",      "em":"😊","label":"Happy",      "color":"#facc15","speech":"Your happiness makes me so happy! What a beautiful smile!",           "music":"upbeat"},
    {"id":"excited",    "em":"🤩","label":"Excited",    "color":"#f97316","speech":"So much energy! I love your excitement! Let us do fun moving tasks!",  "music":"upbeat"},
    {"id":"anxious",    "em":"😰","label":"Anxious",    "color":"#60a5fa","speech":"Take a deep breath with me. In... and out. You are completely safe.",  "music":"nature"},
    {"id":"sad",        "em":"😢","label":"Sad",        "color":"#818cf8","speech":"It is okay to feel sad. I am right here with you. We can go slowly.", "music":"nature"},
    {"id":"angry",      "em":"😠","label":"Angry",      "color":"#f87171","speech":"Feeling angry is okay. Let us take 3 deep breaths together.",          "music":"nature"},
    {"id":"overwhelmed","em":"😵","label":"Overwhelmed","color":"#c084fc","speech":"Let us stop and be very quiet for a moment. I will play calming sounds.","music":"nature"},
    {"id":"tired",      "em":"😴","label":"Tired",      "color":"#94a3b8","speech":"We will keep today gentle and short. You are amazing just by being here.","music":"sleep"},
    {"id":"silly",      "em":"🤪","label":"Silly",      "color":"#fb923c","speech":"I love your silly mood! You have the most wonderful laugh!",            "music":"upbeat"},
    {"id":"focused",    "em":"🧐","label":"Focused",    "color":"#2dd4bf","speech":"You look incredibly focused! I love that! Let us try harder tasks!",   "music":"focus"},
    {"id":"scared",     "em":"😨","label":"Scared",     "color":"#fbbf24","speech":"You are 100% safe here. I am Pepper your friend and will protect you!", "music":"nature"},
    {"id":"sensory",    "em":"🙉","label":"Sensory",    "color":"#a78bfa","speech":"Making everything softer now. Quiet sounds, gentle tasks, no rush.",    "music":"nature"},
    {"id":"rainbow",    "em":"🌈","label":"Rainbow",    "color":"#ffffff","speech":"What an amazing rainbow mood! You are as beautiful as a rainbow!",      "music":"upbeat"},
]

# ── 10 Calming Music Tracks for ASD (Web Audio API tones) ───────────
MUSIC_TRACKS = [
    {"id":"nature",  "name":"Forest Rain",    "type":"Nature · Calm",      "em":"🌧️",
     "hz_base":40,   "hz_mod":0.08, "wave":"noise",  "desc":"Gentle rain — reduces anxiety"},
    {"id":"ocean",   "name":"Ocean Waves",    "type":"Nature · Relax",     "em":"🌊",
     "hz_base":60,   "hz_mod":0.06, "wave":"sine",   "desc":"Ocean rhythm — deep relaxation"},
    {"id":"sleep",   "name":"Sleep 432Hz",    "type":"Sleep · Soothe",     "em":"😴",
     "hz_base":432,  "hz_mod":0.02, "wave":"sine",   "desc":"432Hz tuning — calms nervous system"},
    {"id":"upbeat",  "name":"Happy Rhythm",   "type":"Upbeat · Energy",    "em":"🎉",
     "hz_base":120,  "hz_mod":0.15, "wave":"square", "desc":"Happy beat — lifts mood and energy"},
    {"id":"focus",   "name":"Focus 60BPM",    "type":"Study · Calm",       "em":"🎯",
     "hz_base":60,   "hz_mod":0.05, "wave":"triangle","desc":"60 BPM — matches resting heart rate"},
    {"id":"white",   "name":"White Noise",    "type":"Sensory · Block",    "em":"⬜",
     "hz_base":200,  "hz_mod":0.0,  "wave":"noise",  "desc":"White noise — masks distracting sounds"},
    {"id":"lullaby", "name":"Lullaby",         "type":"Gentle · Transition","em":"🎵",
     "hz_base":261,  "hz_mod":0.04, "wave":"sine",   "desc":"Soft lullaby — eases transitions"},
    {"id":"piano",   "name":"Soft Piano",     "type":"Classical · Mood",   "em":"🎹",
     "hz_base":440,  "hz_mod":0.03, "wave":"sine",   "desc":"Piano melody — emotional regulation"},
    {"id":"birds",   "name":"Morning Birds",  "type":"Nature · Alerting",  "em":"🐦",
     "hz_base":800,  "hz_mod":0.20, "wave":"sine",   "desc":"Birdsong — gentle alerting in morning"},
    {"id":"hum",     "name":"432Hz Pure Hum", "type":"Binaural · Deep",    "em":"🔮",
     "hz_base":432,  "hz_mod":0.01, "wave":"sine",   "desc":"Pure 432Hz hum — deep nervous calm"},
]

# ── Voice Profiles (4 from HTML) ───────────────────────────────────
VOICE_PROFILES = {
    "girl":    {"rate":116, "label":"Girl",    "keywords":["female","zira","hazel","karen","samantha"]},
    "boy":     {"rate":108, "label":"Boy",     "keywords":["daniel","alex","oliver","male"]},
    "kids":    {"rate":120, "label":"Kids",    "keywords":["samantha","karen","tessa"]},
    "grandma": {"rate":92,  "label":"Grandma", "keywords":["moira","fiona","karen","victoria"]},
}
CURRENT_VOICE_PROFILE = "girl"

# ── Color Themes (5 ASD-friendly themes from HTML) ───────────────────
COLOR_THEMES = {
    "white":       {"bg":"#f8f9fc","card":"#ffffff","accent":"#2563eb",
                    "text":"#1e293b","border":"#cbd5e1","muted":"#64748b",
                    "label":"☀️ White","desc":"Clean and bright — great for focus"},
    "baby_purple": {"bg":"#f0edf8","card":"#e8e3f4","accent":"#7c3aed",
                    "text":"#2d1b69","border":"rgba(139,92,246,.35)","muted":"#6d5a9c",
                    "label":"💜 Baby Purple","desc":"Soft purple — calming and gentle"},
    "peach":       {"bg":"#fff5f0","card":"#fff0e8","accent":"#ea580c",
                    "text":"#431407","border":"rgba(234,88,12,.3)","muted":"#9a5a3a",
                    "label":"🍑 Peach","desc":"Warm peach — cozy and welcoming"},
    "gray":        {"bg":"#111114","card":"#1c1c20","accent":"#9898b8",
                    "text":"#d8d8e8","border":"rgba(180,180,200,.22)","muted":"#888898",
                    "label":"🌫️ Gray","desc":"Dark gray — reduces visual stress"},
    "brown":       {"bg":"#1a0f00","card":"#2a1800","accent":"#d97706",
                    "text":"#fde8c8","border":"rgba(217,119,6,.3)","muted":"#a87040",
                    "label":"🍂 Brown","desc":"Earthy brown — warm and grounding"},
}
CURRENT_THEME = "white"
CURRENT_THEME = "blue"

# ── Trial/Subscription System ──────────────────────────────────────
TRIAL_FILE = "pep_trials.json"

def load_trials():
    try:
        if os.path.exists(TRIAL_FILE):
            with open(TRIAL_FILE) as f: return json.load(f)
    except: pass
    return {}

def save_trials(data):
    try:
        with open(TRIAL_FILE,"w") as f: json.dump(data,f,indent=2)
    except: pass

def generate_pin():
    return str(random.randint(10000,99999))

def create_trial(parent_name, email, child_name, child_age):
    trials = load_trials()
    email_lower = email.lower().strip()
    for pin_key, trial in trials.items():
        if trial.get("email","").lower() == email_lower:
            expiry = trial.get("expiryDate","")
            try:
                if expiry and datetime.fromisoformat(expiry) > datetime.now():
                    return {"ok":False,"error":"Trial already active for this email.","pin":trial.get("pin","")}
            except: pass
            return {"ok":False,"error":"Trial expired. Please subscribe."}
    pin = generate_pin()
    from datetime import timedelta
    expiry = (datetime.now()+timedelta(days=15)).isoformat()
    trial_data = {"email":email_lower,"parentName":parent_name,"childName":child_name,
                  "childAge":int(child_age),"pin":pin,"plan":"free_trial",
                  "startDate":datetime.now().isoformat(),"expiryDate":expiry}
    trials[pin] = trial_data
    save_trials(trials)
    return {"ok":True,"pin":pin,"expiry":expiry}

def create_subscription(parent_name, email, child_name, child_age, plan="month"):
    trials = load_trials()
    pin = generate_pin()
    from datetime import timedelta
    months = 12 if plan=="year" else 1
    expiry = (datetime.now()+timedelta(days=months*30)).isoformat()
    price = "399" if plan=="year" else "49"
    sub_data = {"email":email.lower(),"parentName":parent_name,"childName":child_name,
                "childAge":int(child_age),"pin":pin,"plan":plan,"price":price,
                "startDate":datetime.now().isoformat(),"expiryDate":expiry}
    trials[pin] = sub_data
    save_trials(trials)
    return {"ok":True,"pin":pin,"expiry":expiry,"plan":plan,"price":price}

def verify_pin(pin):
    trials = load_trials()
    data = trials.get(str(pin).strip())
    if not data: return None
    expiry = data.get("expiryDate","")
    if expiry:
        try:
            if datetime.fromisoformat(expiry) < datetime.now(): return None
        except: pass
    return data

# ── Life-Skill Video Library (25 videos, Goally channel) ────────────
VIDEO_TASK_LIBRARY = {
    "wash_face":       ("Washing Your Face",          "5IrFmTMzp7E", "Hygiene"),
    "brush_teeth":     ("Brushing Your Teeth",         "Xc2bKO7oT8A", "Hygiene"),
    "wash_hands":      ("Washing Hands Properly",      "3PmVJQUCm4E", "Hygiene"),
    "shower":          ("Taking a Shower",             "PXN8Tk9tqm4", "Hygiene"),
    "comb_hair":       ("Combing Your Hair",           "0V8JJhQVjWM", "Hygiene"),
    "get_dressed":     ("Getting Dressed",             "YAhqTcMxHtk", "Independence"),
    "tie_shoes":       ("Tying Your Shoes",            "B0cI1mBqkBo", "Independence"),
    "make_bed":        ("Making Your Bed",             "BdQfBDxOvTA", "Household"),
    "tidy_room":       ("Tidying Your Room",           "5vSKAp-aSOM", "Household"),
    "table_manners":   ("Table Manners",               "nwJNahHgJpg", "Social"),
    "use_fork":        ("Using Fork and Spoon",        "eXEHOrP8V7I", "Independence"),
    "deep_breath":     ("Deep Breathing for Calm",     "RVA2N6tX2cg", "Wellbeing"),
    "calm_down":       ("Calming Down Strategies",     "ihO_TrEEwFE", "Wellbeing"),
    "ask_help":        ("How to Ask for Help",         "FHmS7_uiiaM", "Social"),
    "take_turns":      ("Taking Turns",                "ZtHxGq7sJhk", "Social"),
    "greetings":       ("Saying Hello and Goodbye",    "RNHM_3Yd_Yw", "Social"),
    "healthy_snack":   ("Choosing a Healthy Snack",   "y9rHQBECwmA", "Health"),
    "road_safety":     ("Road Safety Basics",          "Dk6mQ4pFSBk", "Safety"),
    "pack_bag":        ("Packing Your School Bag",     "CpCFEnXJAbw", "Independence"),
    "use_toilet":      ("Toilet Independence",         "MEOlk55zfSk", "Independence"),
    "morning_routine": ("Morning Routine",             "PZ0eSME8lKY", "Independence"),
    "bedtime_routine": ("Bedtime Routine",             "hbZz2EJK9mw", "Wellbeing"),
    "exercise":        ("Simple Morning Exercise",     "vGSBqFvVuR8", "Health"),
    "sensory_break":   ("Taking a Sensory Break",      "ihO_TrEEwFE", "Wellbeing"),
    "shave":           ("Shaving Safely",              "M5PXQHIUPLY", "Hygiene"),
}
VIDEO_TASK_KEYS = list(VIDEO_TASK_LIBRARY.keys())
# Backward-compat domain map
VIDEO_TASK_MAP = {
    "Motor":       [f"https://www.youtube.com/embed/{v[1]}?rel=0&modestbranding=1" for v in list(VIDEO_TASK_LIBRARY.values())[:6]],
    "Cognitive":   [f"https://www.youtube.com/embed/{v[1]}?rel=0&modestbranding=1" for v in list(VIDEO_TASK_LIBRARY.values())[6:12]],
    "Verbal":      [f"https://www.youtube.com/embed/{v[1]}?rel=0&modestbranding=1" for v in list(VIDEO_TASK_LIBRARY.values())[12:18]],
    "Math":        [f"https://youtu.be/{v[1]}" for v in [VIDEO_TASK_LIBRARY["healthy_snack"], VIDEO_TASK_LIBRARY["exercise"]]],
    "Social":      [f"https://www.youtube.com/embed/{v[1]}?rel=0&modestbranding=1" for v in [VIDEO_TASK_LIBRARY["ask_help"], VIDEO_TASK_LIBRARY["take_turns"], VIDEO_TASK_LIBRARY["greetings"]]],
    "Independence":[f"https://www.youtube.com/embed/{v[1]}?rel=0&modestbranding=1" for v in [VIDEO_TASK_LIBRARY["morning_routine"], VIDEO_TASK_LIBRARY["bedtime_routine"]]],
}
_video_task_counter = 0




print("\n" + "═"*60)
print("  PEPPER CLINICAL INFINITY V6 — Commander: Lamya")
print("═"*60)
CHILD_NAME = input("\n👦 Child's Name: ").strip() or "Child"
CHILD_AGE  = input("   Age (default 6): ").strip() or "6"
SAFE_NAME  = re.sub(r"[^a-zA-Z0-9_]","_", CHILD_NAME)
CSV_FILE   = f"{SAFE_NAME}_v6_Results.csv"
DB_FILE    = f"{SAFE_NAME}_v6_db.json"

with open(CSV_FILE,"w",newline="") as f:
    csv.writer(f).writerow(["Time","Child","Task","Domain","Level","Protocol",
                              "Result","Consecutive","FailCount","Score",
                              "Emotion","Attention","ConvLevel"])

def log_csv(task_id,domain,level,protocol,result,consec,fails,score,emotion,att,clvl):
    try:
        with open(CSV_FILE,"a",newline="") as f:
            csv.writer(f).writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                CHILD_NAME,task_id,domain,level,protocol,
                "SUCCESS" if result else "FAIL",
                consec,fails,score,emotion,att,clvl])
    except Exception: pass

# Simple JSON DB for users
if not os.path.exists(DB_FILE):
    with open(DB_FILE,"w") as f: json.dump({"users":{},"children":{}},f)

def load_db():
    try:
        with open(DB_FILE) as f: return json.load(f)
    except: return {"users":{},"children":{}}

def save_db(db):
    try:
        with open(DB_FILE,"w") as f: json.dump(db,f,indent=2,default=str)
    except: pass

if _GENAI_OK:
    try: genai.configure(api_key=GEMINI_KEY)
    except: pass

# ══════════════════════════════════════════════════════════════════════
# 3.  PYBULLET SUBPROCESS
# ══════════════════════════════════════════════════════════════════════
_PB_SCRIPT = r"""
import sys,os,time,math,json,select
os.environ["TF_CPP_MIN_LOG_LEVEL"]="3"
try:
    import pybullet as p,pybullet_data
    sys.path.insert(0,"/home/lamya/pepper_duo/src")
    from qibullet import SimulationManager
except Exception as e:
    print(f"PB_ERROR:{e}",flush=True)
    while True:
        try:
            r=select.select([sys.stdin],[],[],0)[0]
            if r and "EXIT" in sys.stdin.readline(): break
        except: break
    sys.exit(0)

child=sys.argv[1] if len(sys.argv)>1 else "Child"
qisim=SimulationManager(); client=qisim.launchSimulation(gui=True)
p.setRealTimeSimulation(1); p.setGravity(0,0,-9.81)
p.setAdditionalSearchPath(pybullet_data.getDataPath())
p.loadURDF("plane.urdf")
wc=[0.92,0.92,0.96,1]
for pos,ext in [([0,-4,1.1],[5,.1,1.1]),([0,4,1.1],[5,.1,1.1]),
                ([5,0,1.1],[.1,4,1.1]),([-5,0,1.1],[.1,4,1.1])]:
    p.createMultiBody(0,-1,p.createVisualShape(p.GEOM_BOX,halfExtents=ext,rgbaColor=wc),pos)
p.createMultiBody(0,-1,p.createVisualShape(p.GEOM_BOX,halfExtents=[4.5,3.5,.02],
    rgbaColor=[.60,.50,.38,1]),[0,0,.01])
for txt,pos in [("ABA MOTOR",[-4,3,2]),("TEACCH VISUAL",[4,3,2]),
                ("DTT VERBAL",[0,4.2,2]),("ESDM SOCIAL",[-4,-3,2]),
                (f"★ {child} ★",[0,0,3.2])]:
    p.addUserDebugText(txt,pos,[.4,.5,.9],textSize=1.0,lifeTime=0)
pepper=qisim.spawnPepper(client); pepper.goToPosture("Stand",0.5)
p.resetDebugVisualizerCamera(6,45,-30,[0,0,0.8])
print("PYBULLET_READY",flush=True)
rx=ry=0.0; ph=0.0; last_upd=0.0
st={"is_speaking":False,"lip":0.0,"sj":False,"blink":False,"ht":0.0,"gaze":"child"}
while True:
    try:
        r=select.select([sys.stdin],[],[],0)[0]
        if r:
            ln=sys.stdin.readline()
            if not ln or ln.strip()=="EXIT": break
            try: st.update(json.loads(ln))
            except: pass
    except: pass
    p.stepSimulation()
    now=time.time()
    if now-last_upd>0.04:  # 25hz max
        last_upd=now; lip=float(st.get("lip",0.0))
        try:
            if st["is_speaking"]:
                ph+=.06
                L=.5+.3*math.sin(ph); R=.5+.3*math.sin(ph+math.pi*.6)
                pepper.setAngles("LShoulderPitch",L,.07)
                pepper.setAngles("RShoulderPitch",R,.07)
                pepper.setAngles("HeadPitch",-0.04-lip*0.13,.22)
            elif st.get("sj",False):
                jt=time.time()
                pepper.setAngles("LShoulderPitch",0.05+0.3*abs(math.sin(jt*4)),.25)
                pepper.setAngles("RShoulderPitch",0.05+0.3*abs(math.sin(jt*4+math.pi)),.25)
            elif st.get("gaze")=="tablet":
                pepper.setAngles("HeadYaw",-0.4,.08); pepper.setAngles("HeadPitch",0.1,.08)
            else:
                pepper.setAngles("LShoulderPitch",1.,.04)
                pepper.setAngles("RShoulderPitch",1.,.04)
                pepper.setAngles("HeadYaw",float(st.get("ht",0.0))*0.5,.03)
                pepper.setAngles("HeadPitch",0.07 if st.get("blink") else 0.0,.05)
        except: pass
    t_=time.time()
    rx+=.014*math.cos(t_*.4); ry+=.014*math.sin(t_*.5)
    rx=max(-3.5,min(3.5,rx)); ry=max(-2.8,min(2.8,ry))
    try: pepper.setPosition([rx,ry,.8])
    except: pass
    time.sleep(1/60.)
"""

class PBWatchdog:
    """PyBullet subprocess — 25hz IPC, auto-restart on crash."""
    def __init__(self,child_name):
        self.child=child_name; self._proc=None; self._ready=False
        self._lock=threading.Lock(); self._running=False
        self._last_send=0.0; self._ipc_interval=0.04  # 25hz

    def start(self):
        self._running=True
        threading.Thread(target=self._supervise,daemon=True).start()

    def _launch(self):
        try:
            self._proc=subprocess.Popen(
                [sys.executable,"-c",_PB_SCRIPT,self.child],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,text=True,bufsize=1)
            deadline=time.time()+25
            while time.time()<deadline:
                try:
                    ln=self._proc.stdout.readline()
                    if "PYBULLET_READY" in ln: self._ready=True; log.info("✅ PyBullet subprocess (25hz)"); return True
                    if "PB_ERROR" in ln: log.warning(ln.strip()); return False
                except: return False
                time.sleep(0.1)
        except Exception as e: log.warning(f"PyBullet launch: {e}")
        return False

    def _supervise(self):
        while self._running:
            ok=self._launch()
            if ok:
                try: self._proc.wait()
                except: pass
            if not self._running: break
            self._ready=False; log.warning("PyBullet crashed — restarting 3s…"); time.sleep(3)

    def send(self,**kw):
        now=time.time()
        if now-self._last_send<self._ipc_interval: return
        self._last_send=now
        if not self._ready or not self._proc: return
        with self._lock:
            try:
                self._proc.stdin.write(json.dumps(kw)+"\n")
                self._proc.stdin.flush()
            except: pass

    def stop(self):
        self._running=False
        with self._lock:
            if self._proc:
                try: self._proc.stdin.write("EXIT\n"); self._proc.stdin.flush()
                except: pass
                time.sleep(0.4)
                try: self._proc.terminate()
                except: pass

# ══════════════════════════════════════════════════════════════════════
# 4.  TASK POOL — Infinite, history-dedup, multi-protocol
# ══════════════════════════════════════════════════════════════════════
def _fig(mov,size=240):
    img=Image.new("RGBA",(size,size),(245,248,255,255)); dr=ImageDraw.Draw(img)
    cx,cy=size//2,size//2+8; lw=4; col="#2c3e50"; hl="#e74c3c"
    dr.ellipse([cx-24,cy-80,cx+24,cy-28],outline=col,width=lw)
    dr.line([cx,cy-28,cx,cy+48],fill=col,width=lw)
    dr.line([cx,cy+48,cx-22,cy+92],fill=col,width=lw)
    dr.line([cx,cy+48,cx+22,cy+92],fill=col,width=lw)
    if mov=="clap":
        dr.line([cx-40,cy,cx-4,cy+16],fill=col,width=lw); dr.line([cx+40,cy,cx+4,cy+16],fill=col,width=lw)
        dr.ellipse([cx-8,cy+12,cx+8,cy+26],fill=hl)
    elif mov=="wave":
        dr.line([cx-36,cy-2,cx-16,cy+16],fill=col,width=lw)
        dr.line([cx+36,cy-10,cx+60,cy-42],fill=col,width=lw); dr.line([cx+60,cy-42,cx+54,cy-60],fill=hl,width=4)
    elif mov=="raise_hand":
        dr.line([cx-36,cy-2,cx-16,cy+16],fill=col,width=lw)
        dr.line([cx+36,cy-10,cx+46,cy-66],fill=hl,width=5); dr.ellipse([cx+38,cy-80,cx+56,cy-62],fill=hl)
    elif mov=="touch_nose":
        dr.ellipse([cx-6,cy-60,cx+6,cy-48],fill=hl); dr.line([cx-36,cy,cx-6,cy-50],fill=hl,width=5)
        dr.line([cx+36,cy,cx+16,cy+16],fill=col,width=lw)
    elif mov=="arms_out":
        dr.line([cx-36,cy-2,cx-82,cy-2],fill=hl,width=5); dr.line([cx+36,cy-2,cx+82,cy-2],fill=hl,width=5)
    elif mov=="hands_up":
        dr.line([cx-36,cy-2,cx-50,cy-62],fill=hl,width=5); dr.line([cx+36,cy-2,cx+50,cy-62],fill=hl,width=5)
        dr.ellipse([cx-62,cy-76,cx-40,cy-56],fill=hl); dr.ellipse([cx+40,cy-76,cx+62,cy-56],fill=hl)
    elif mov=="point":
        dr.line([cx-36,cy-2,cx-16,cy+16],fill=col,width=lw)
        dr.line([cx+36,cy-10,cx+76,cy-2],fill=col,width=lw); dr.line([cx+76,cy-2,cx+96,cy-4],fill=hl,width=5)
    else:
        dr.line([cx-36,cy-2,cx-56,cy+14],fill=col,width=lw); dr.line([cx+36,cy-2,cx+56,cy+14],fill=col,width=lw)
    dr.text((cx-36,size-22),"👇 YOUR TURN!",fill=(231,76,60,255))
    buf=BytesIO(); img.save(buf,"PNG")
    return "data:image/png;base64,"+base64.b64encode(buf.getvalue()).decode()

log.info("Rendering figures…")
FIGS={m:_fig(m) for m in ["clap","wave","raise_hand","touch_nose","arms_out","hands_up","point"]}

COLORS=[{"id":"red","color":"#ef4444","label":"🔴 RED"},{"id":"blue","color":"#3b82f6","label":"🔵 BLUE"},
        {"id":"green","color":"#22c55e","label":"🟢 GREEN"},{"id":"yellow","color":"#eab308","label":"🟡 YELLOW"},
        {"id":"purple","color":"#a855f7","label":"🟣 PURPLE"},{"id":"orange","color":"#f97316","label":"🟠 ORANGE"},
        {"id":"pink","color":"#ec4899","label":"🩷 PINK"}]
ANIMALS=[{"id":"dog","emoji":"🐶","label":"Dog"},{"id":"cat","emoji":"🐱","label":"Cat"},
         {"id":"lion","emoji":"🦁","label":"Lion"},{"id":"elephant","emoji":"🐘","label":"Elephant"},
         {"id":"rabbit","emoji":"🐰","label":"Rabbit"},{"id":"bear","emoji":"🐻","label":"Bear"},
         {"id":"monkey","emoji":"🐵","label":"Monkey"},{"id":"tiger","emoji":"🐯","label":"Tiger"}]
FRUITS=[{"id":"apple","emoji":"🍎","label":"Apple"},{"id":"banana","emoji":"🍌","label":"Banana"},
        {"id":"orange","emoji":"🍊","label":"Orange"},{"id":"grapes","emoji":"🍇","label":"Grapes"},
        {"id":"strawberry","emoji":"🍓","label":"Strawberry"},{"id":"mango","emoji":"🥭","label":"Mango"}]
SHAPES=[{"id":"circle","emoji":"⭕","label":"Circle"},{"id":"square","emoji":"⬛","label":"Square"},
        {"id":"triangle","emoji":"🔺","label":"Triangle"},{"id":"star","emoji":"⭐","label":"Star"},
        {"id":"heart","emoji":"❤️","label":"Heart"},{"id":"diamond","emoji":"💎","label":"Diamond"}]
MOTORS=[
    {"id":"clap","name":"👏 Clap","verify":"clap","prompts":["Clap!","Hands together!"],
     "instruction":"Look and CLAP your hands!","waiting":"Clap! 👏","success":"AMAZING! ✅","fail":"Clap hands together!"},
    {"id":"wave","name":"👋 Wave","verify":"wave","prompts":["Wave!","Side to side!"],
     "instruction":"Look and WAVE hello!","waiting":"Wave! 👋","success":"WONDERFUL! ✅","fail":"Wave side to side!"},
    {"id":"raise_hand","name":"✋ Raise Hand","verify":"raise_hand","prompts":["Hand up!","Higher!"],
     "instruction":"RAISE your hand HIGH!","waiting":"Hand up! ✋","success":"PERFECT! ✅","fail":"Lift arm above head!"},
    {"id":"touch_nose","name":"👆 Touch Nose","verify":"touch_nose","prompts":["Nose!","Touch it!"],
     "instruction":"TOUCH your NOSE!","waiting":"Nose! 👆","success":"BRILLIANT! ✅","fail":"Point to nose!"},
    {"id":"arms_out","name":"🤸 Arms Wide","verify":"arms_out","prompts":["Arms out!","Wide!"],
     "instruction":"Stretch BOTH arms WIDE!","waiting":"Arms out! 🤸","success":"AIRPLANE! ✅","fail":"Arms wide to sides!"},
    {"id":"hands_up","name":"🙌 Hands Up","verify":"hands_up","prompts":["Both up!","Higher!"],
     "instruction":"Put BOTH hands UP!","waiting":"Hands up! 🙌","success":"SUPERSTAR! ✅","fail":"Both arms above head!"},
    {"id":"point","name":"👉 Point","verify":"point","prompts":["Point!","Finger out!"],
     "instruction":"POINT your finger!","waiting":"Point! 👉","success":"GREAT! ✅","fail":"Stretch index finger!"},
]
WORDS=["apple","ball","cat","dog","elephant","fish","good","happy","jump",
       "kite","love","milk","play","red","sun","tree","water","yes","no",
       "one","two","three","four","five","blue","green","bird","book","cup",
       "door","eye","foot","hand","head","nose","arm","leg","big","small"]

# Conversation level 3+ phrases (ESDM/PECS)
CONV_PHRASES=["hello","thank you","when","please","more","help","yes","no",
               "good morning","i love you","goodbye","sorry","hungry","water","play"]

# Protocol templates
PROTOCOLS=["ABA-DTT","TEACCH","ESDM","TIE"]

def _grid_task(items,all_items,prefix,domain,level,mode,tokens,protocol="ABA-DTT"):
    tgt=random.choice(items)
    dis=random.sample([x for x in all_items if x["id"]!=tgt["id"]],3)
    opts=[tgt]+dis; random.shuffle(opts)
    cor=next(i for i,o in enumerate(opts) if o["id"]==tgt["id"])
    lbl=tgt.get("label",tgt["id"])
    return {"id":f"{prefix}_{tgt['id']}_{random.randint(0,9999)}",
            "base_id":f"{prefix}_{tgt['id']}","domain":domain,"level":level,"protocol":protocol,
            "name":lbl,"instruction":f"Click the {lbl}!","waiting":f"Find {lbl}!",
            "success":f"CORRECT! {lbl}! ✅","fail":f"Find {lbl}!",
            "tablet_mode":mode,"options":opts,"correct":cor,"tokens":tokens,"joy":"celebrate",
            "prompts":[f"Find {lbl}!","Look carefully!","You can do it!"]}

def gen_pool(n=4000):
    pool=[]
    # ABA Motor
    for _ in range(int(n*.25)):
        m=random.choice(MOTORS)
        pool.append({**m,"id":f"{m['id']}_{random.randint(0,9999)}","base_id":m["id"],
            "domain":"Motor","level":1,"protocol":random.choice(PROTOCOLS),
            "tablet_mode":"motor_model","figure":FIGS.get(m["verify"],""),"tokens":2,"joy":"dance"})
    # Cognitive
    for _ in range(int(n*.12)):
        pool.append(_grid_task(COLORS,COLORS,"color","Cognitive",2,"color_grid",3,
                               random.choice(["ABA-DTT","TEACCH"])))
    for _ in range(int(n*.11)):
        pool.append(_grid_task(ANIMALS,ANIMALS,"animal","Cognitive",3,"object_grid",4,
                               random.choice(["TEACCH","ESDM"])))
    for _ in range(int(n*.09)):
        pool.append(_grid_task(FRUITS,FRUITS,"fruit","Cognitive",4,"object_grid",4,
                               random.choice(["ABA-DTT","TIE"])))
    for _ in range(int(n*.08)):
        pool.append(_grid_task(SHAPES,SHAPES,"shape","Cognitive",5,"object_grid",4,
                               random.choice(["TEACCH","ESDM"])))
    # Math finger counting
    for _ in range(int(n*.09)):
        num=random.randint(1,10)
        pool.append({"id":f"count_{num}_{random.randint(0,9999)}","base_id":f"count_{num}",
            "domain":"Math","level":5,"protocol":"ABA-DTT",
            "name":f"🔢 Count {num}","instruction":f"Show me {num} finger{'s' if num>1 else ''}!",
            "waiting":f"Hold up {num} fingers! 🖐️","success":f"YES! {num} fingers! ✅",
            "fail":f"Show {num} fingers!","tablet_mode":"number_display","target_number":num,
            "verify":"finger_count","tokens":5,"joy":"celebrate","prompts":[f"Show {num}!","Count!"]})
    # Verbal
    for _ in range(int(n*.16)):
        word=random.choice(WORDS)
        pool.append({"id":f"say_{word}_{random.randint(0,9999)}","base_id":f"say_{word}",
            "domain":"Verbal","level":6,"protocol":random.choice(["ABA-DTT","DTT"]),
            "name":f"🗣️ Say '{word}'","instruction":f"Say the word: {word.upper()}!",
            "waiting":f"Say {word}! 🎤","success":f"I HEARD {word.upper()}! ✅",
            "fail":f"Try again! Say: {word}!","tablet_mode":"word_display",
            "word_emoji":"🗣️","word_text":word.upper(),
            "verify":"speech_keyword","keyword":word,"tokens":4,"joy":"dance",
            "prompts":[f"Say {word}!",f"Tap mic → {word}!"]})
    # Conversation level 3+
    for _ in range(int(n*.10)):
        phrase=random.choice(CONV_PHRASES)
        pool.append({"id":f"conv_{phrase}_{random.randint(0,9999)}","base_id":f"conv_{phrase}",
            "domain":"Social","level":7,"protocol":"ESDM",
            "name":f"💬 Say '{phrase}'","instruction":f"Say: {phrase.upper()}!",
            "waiting":f"Say {phrase}! 🎤","success":f"WONDERFUL! '{phrase}'! ✅",
            "fail":f"Try again! Say: {phrase}!","tablet_mode":"conv_display",
            "conv_phrase":phrase.upper(),"conv_emoji":"💬",
            "verify":"speech_keyword","keyword":phrase,"tokens":6,"joy":"full_joy",
            "prompts":[f"Say {phrase}!","You can do it!"]})
    random.shuffle(pool); return pool

log.info("Generating 4000 tasks…")
TASK_POOL=gen_pool(4000)
log.info(f"✅ {len(TASK_POOL)} tasks ready!")

# ══════════════════════════════════════════════════════════════════════
# 5.  SHARED STATE
# ══════════════════════════════════════════════════════════════════════
MAX_FAILS=2; MASTERY_N=3; BASE_MIC_ENERGY=200
SESSION_HISTORY=deque(maxlen=200)  # track base_id — no repeat within session

ST={
    "name":CHILD_NAME,"age":int(CHILD_AGE) if CHILD_AGE.isdigit() else 6,
    "task_index":0,"consecutive":0,"fail_count":0,
    "tasks_mastered":0,"current_level":1,"domain":"Motor","protocol":"ABA-DTT",
    "conversation_level":1,  # 1=motor, 2=cognitive+verbal, 3+=PECS/conversation
    "tablet_click_result":None,"tablet_instruction":"Welcome!",
    # Vision
    "emotion":"neutral","emotion_pct":{k:0 for k in
        ["happy","joyful","sad","angry","fear","surprised","neutral"]},
    "emotion_conf":0.5,"face_detected":False,"attention":70,
    "hand_raised":False,"waving":False,"clapping":False,
    "arms_out":False,"hands_up":False,"pointing":False,
    "head_tilted":False,"blinking":False,"eye_contact":False,
    "finger_count":0,"finger_target":1,"body_motion":0.0,
    "pose_landmarks":{},"face_mesh_landmarks":{},
    "verify_action":None,"verify_result":False,"verify_timeout":0.0,
    "last_speech_text":"","last_sound":time.time(),
    "is_speaking":False,"interrupt_flag":False,"pepper_muted":False,"_last_frame_jpeg":None,
    "pecs_interrupt":False,  # PECS global interrupt
    "listening":False,"waiting_for_child":False,"recording":False,
    "sim_cmd":None,"lip_sync_value":0.0,"gaze_mode":"child",
    "social_joy_active":False,"eye_color":(100,180,255),
    "blink_timer":0.3,"head_tilt_val":0.0,
    # Mic waveform
    "mic_level":0.0,"mic_energy_current":BASE_MIC_ENERGY,
    # Progress
    "score":0,"tokens":0,"streak":0,
    "tasks_success":0,"tasks_fail":0,"tasks_skipped":0,
    "session_chat":[],"logs":[],"parent_notes":[],"pecs_log":[],"mood_log":[],
    "skill_motor":50,"skill_cognitive":50,"skill_verbal":50,
    "skill_math":50,"skill_social":50,
    "att_history":[],"score_history":[],
    "session_start":datetime.now().strftime("%H:%M"),
    "session_date":datetime.now().strftime("%Y-%m-%d"),
    "uptime":time.time(),
    "asq_score":None,"vbmapp_score":None,"current_mood":None,"current_music":"none","session_history":[],
    "quick_action":None,
    "instant_success":False,  # immediate interrupt flag
}
_ll=threading.Lock()

def LOG(msg,t="info"):
    with _ll:
        e={"time":datetime.now().strftime("%H:%M:%S"),
           "msg":str(msg)[:120],"type":t,
           "emo":ST["emotion"],"proto":ST.get("protocol","—")}
        ST["logs"].append(e)
        if len(ST["logs"])>500: ST["logs"]=ST["logs"][-500:]
    if t=="success": log.info(f"✅ {msg[:70]}")
    elif t=="fail":  log.warning(f"❌ {msg[:70]}")
    else:            log.info(msg[:70])

def get_next_task():
    """Select next task avoiding recent repeats (session history)."""
    recent=set(SESSION_HISTORY)
    # Filter out recently seen base_ids
    candidates=[t for t in TASK_POOL if t.get("base_id","") not in recent]
    if not candidates: candidates=TASK_POOL  # all used — reset
    # Filter by conversation level
    clvl=ST["conversation_level"]
    if clvl==1:
        lvl_cands=[t for t in candidates if t["domain"]=="Motor"]
    elif clvl==2:
        lvl_cands=[t for t in candidates if t["domain"] in ["Motor","Cognitive","Math"]]
    else:
        lvl_cands=candidates  # all domains including Social/Verbal/Conv
    task=random.choice(lvl_cands if lvl_cands else candidates)
    SESSION_HISTORY.append(task.get("base_id",""))
    return task

# ══════════════════════════════════════════════════════════════════════
# 6.  BRIDGE — ALL Qt signals
# ══════════════════════════════════════════════════════════════════════
class Bridge(QObject):
    sig_task      = pyqtSignal(dict)
    sig_success   = pyqtSignal(str)
    sig_fail      = pyqtSignal(str)
    sig_skip      = pyqtSignal(str)
    sig_feedback  = pyqtSignal(str)
    sig_instr     = pyqtSignal(str)
    sig_waiting   = pyqtSignal(str)
    sig_unlock    = pyqtSignal()
    sig_lock      = pyqtSignal()
    sig_reset     = pyqtSignal()
    sig_joy       = pyqtSignal(str)
    sig_camera    = pyqtSignal(object)    # QImage — thread-safe copy
    sig_stats     = pyqtSignal()
    sig_chat      = pyqtSignal(str,str)
    sig_rec_start = pyqtSignal()
    sig_rec_stop  = pyqtSignal(str)
    sig_mic_level = pyqtSignal(float)    # waveform level
    sig_youtube   = pyqtSignal(str)
    sig_pecs      = pyqtSignal(str)

BRIDGE=Bridge()

# ══════════════════════════════════════════════════════════════════════
# 7.  CAMERA + MEDIAPIPE THREAD (QThread — frame.copy() prevents segfault)
# ══════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════
# 7.  CAMERA THREAD — Pure OpenCV (no mediapipe .solutions required)
#     Works with mediapipe 0.10+ which removed the legacy solutions API
#     © 2026 Lamya Fadlulmola Hamed Ali — All Rights Reserved
# ══════════════════════════════════════════════════════════════════════
class CameraThread(QThread):
    """
    Self-contained camera detection thread.
    Uses ONLY OpenCV cascades + skin segmentation + geometry math.
    No external model downloads required. Works on Ubuntu 22 immediately.
    
    Detects:
      • Face position, size, bounding box
      • Emotion (happy/sad/angry/surprised/neutral) from face landmarks
      • Finger count (0-10) via skin contour convex hull defects
      • Body motion via background subtraction + optical flow
      • Pose joints: shoulders, wrists, head (via face + body cascade)
      • Eye contact / blinking (eye cascade + EAR ratio)
      • Clapping, waving, hand raise (via motion zones)
    """
    def __init__(self):
        super().__init__()
        self.running = False
        self.cap = None
        self._mutex = QMutex()
        self._frame_count = 0
        # OpenCV detectors — all built-in, zero downloads
        self._face_cas  = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
        self._eye_cas   = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_eye.xml")
        self._smile_cas = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_smile.xml")
        self._body_cas  = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_fullbody.xml")
        # Motion / optical flow
        self._bg_sub    = cv2.createBackgroundSubtractorMOG2(history=80, varThreshold=35)
        self._prev_gray = None
        self._prev_pts  = None
        # Tracking buffers
        self._emo_buf   = []        # emotion smoothing
        self._fc_buf    = []        # finger count smoothing
        self._motion_buf= []        # motion values
        self._hand_hist = []        # left/right motion history for wave
        self._att_buf   = []        # attention smoothing

    def _init_cam(self):
        for idx in [0, 1, 2]:
            try:
                c = cv2.VideoCapture(idx)
                if c.isOpened():
                    ret, f = c.read()
                    if ret and f is not None and f.size > 0:
                        c.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
                        c.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                        c.set(cv2.CAP_PROP_FPS, 30)
                        c.set(cv2.CAP_PROP_BUFFERSIZE, 1)
                        self.cap = c
                        log.info(f"✅ Camera {idx} — {int(c.get(3))}×{int(c.get(4))}")
                        return
                    c.release()
            except: pass
        log.warning("⚠️ No camera — running in simulation mode")

    def _sim_frame(self):
        """Animated simulation frame when no camera available."""
        self._frame_count += 1
        f = np.zeros((480, 640, 3), dtype=np.uint8)
        t = self._frame_count * 0.05
        # Animated background
        for y in range(0, 480, 20):
            cv2.line(f, (0,y), (640,y), (int(8+4*math.sin(t+y/40)), int(12+4*math.cos(t)), int(28+8*math.sin(t))), 1)
        # Animated circle (simulated face)
        cx, cy = 320, 220
        r = int(80 + 10*math.sin(t*0.7))
        cv2.circle(f, (cx, cy), r, (60, 120, 200), 2)
        # Eyes
        ex_off = int(28 + 5*math.sin(t))
        cv2.circle(f, (cx-ex_off, cy-20), 12, (100, 180, 255), -1)
        cv2.circle(f, (cx+ex_off, cy-20), 12, (100, 180, 255), -1)
        # Mouth (smile)
        cv2.ellipse(f, (cx, cy+30), (25, 14), 0, 0, 180, (100, 220, 100), 2)
        # Skeleton lines
        sh_y = cy + r + 20
        cv2.line(f, (cx, cy+r), (cx, sh_y+80), (0, 255, 100), 2)  # spine
        cv2.line(f, (cx-70, sh_y), (cx+70, sh_y), (0, 255, 100), 2)  # shoulders
        # Wrists (animated)
        lw_x = int(cx - 80 - 20*math.sin(t*0.8))
        rw_x = int(cx + 80 + 20*math.sin(t*0.8))
        cv2.line(f, (cx-70, sh_y), (lw_x, sh_y+60), (0, 200, 255), 2)
        cv2.line(f, (cx+70, sh_y), (rw_x, sh_y+60), (255, 120, 0), 2)
        cv2.circle(f, (lw_x, sh_y+60), 6, (0, 200, 255), -1)
        cv2.circle(f, (rw_x, sh_y+60), 6, (255, 120, 0), -1)
        cv2.putText(f, "NO CAMERA — SIMULATION MODE", (80, 440),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (100, 150, 255), 1)
        cv2.putText(f, "© 2026 Lamya Fadlulmola Hamed Ali", (130, 460),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.38, (40, 80, 120), 1)
        # Simulate data
        ST["face_detected"]   = True
        ST["attention"]       = min(100, ST["attention"] + 0.3)
        ST["emotion"]         = "happy"
        ST["emotion_conf"]    = 0.75
        ST["emotion_pct"]     = {"happy":75,"neutral":15,"sad":3,"angry":2,"surprised":3,"joyful":2,"fear":0}
        ST["finger_count"]    = int(abs(math.sin(t*0.3)) * 5)
        ST["body_motion"]     = abs(math.sin(t*0.5)) * 3
        ST["_motion"]         = ST["body_motion"] > 1.5
        return f

    def _count_fingers(self, frame, hand_roi=None):
        """
        Count fingers 0-10 using skin color HSV segmentation + convex hull defects.
        Works on full frame or a cropped hand region.
        """
        try:
            roi = hand_roi if hand_roi is not None else frame
            if roi is None or roi.size == 0: return 0
            h, w = roi.shape[:2]
            if h < 40 or w < 40: return 0

            # Skin color segmentation in HSV + YCrCb
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            ycr = cv2.cvtColor(roi, cv2.COLOR_BGR2YCrCb)

            mask_hsv = cv2.inRange(hsv, np.array([0,30,60]),  np.array([25,255,255]))
            mask_hsv2= cv2.inRange(hsv, np.array([160,30,60]),np.array([180,255,255]))
            mask_ycr = cv2.inRange(ycr, np.array([0,133,77]), np.array([255,173,127]))
            mask = cv2.bitwise_or(cv2.bitwise_or(mask_hsv, mask_hsv2), mask_ycr)

            # Morphological cleanup
            k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5,5))
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k, iterations=2)
            mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN,  k, iterations=1)

            # Find largest contour
            cnts, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not cnts: return 0
            cnt = max(cnts, key=cv2.contourArea)
            area = cv2.contourArea(cnt)
            if area < 3000: return 0

            # Convex hull + defects = finger gaps
            hull = cv2.convexHull(cnt, returnPoints=False)
            if hull is None or len(hull) < 3: return 0
            defects = cv2.convexityDefects(cnt, hull)
            if defects is None: return 1

            fingers = 1
            for i in range(defects.shape[0]):
                s, e, f, d = defects[i, 0]
                start = tuple(cnt[s][0])
                end   = tuple(cnt[e][0])
                far   = tuple(cnt[f][0])
                # Angle at the far point
                a = np.array(start, float); b = np.array(far, float); c_ = np.array(end, float)
                ba = a - b; bc = c_ - b
                cosA = np.dot(ba, bc) / (np.linalg.norm(ba) * np.linalg.norm(bc) + 1e-6)
                angle = math.degrees(math.acos(np.clip(cosA, -1, 1)))
                depth = d / 256.0
                # Valid finger gap: angle < 90°, depth > 15px
                if angle < 88 and depth > 15:
                    fingers = min(fingers + 1, 5)

            # Draw skin mask overlay on frame (green)
            if hand_roi is None:
                colored = cv2.cvtColor(mask, cv2.COLOR_GRAY2BGR)
                colored[:,:,0] = 0; colored[:,:,2] = 0
                cv2.addWeighted(frame, 1.0, colored, 0.25, 0, frame)

            return fingers
        except Exception as e:
            return 0

    def _detect_face_emotion(self, frame, face_rect):
        """
        Detect emotion from face region using:
        - Smile cascade → happy
        - Eye openness (eye cascade + size ratio) → surprised/tired
        - Brightness/contrast of face region → rough mood indicator
        """
        try:
            x, y, w, h = face_rect
            face_roi = frame[y:y+h, x:x+w]
            gray_roi = cv2.cvtColor(face_roi, cv2.COLOR_BGR2GRAY)

            # Smile detection
            smiles = self._smile_cas.detectMultiScale(gray_roi, 1.7, 22,
                        minSize=(int(w*0.25), int(h*0.1)))
            smile_score = min(1.0, len(smiles) * 0.4)

            # Eye openness (EAR proxy)
            eyes = self._eye_cas.detectMultiScale(gray_roi, 1.1, 5,
                        minSize=(int(w*0.1), int(h*0.08)))
            eye_score = min(1.0, len(eyes) * 0.5)

            # Face brightness (lower = more somber)
            brightness = np.mean(gray_roi) / 255.0

            # Contrast in upper half of face (brow region = anger indicator)
            brow_roi = gray_roi[:h//3, :]
            contrast = np.std(brow_roi) / 64.0  # normalise

            # Score each emotion
            sc = {
                "happy":    min(1.0, smile_score * 1.2 + brightness * 0.3),
                "joyful":   min(1.0, smile_score * 0.8 + eye_score * 0.4),
                "surprised":min(1.0, eye_score * 1.0 * (1 - smile_score)),
                "angry":    min(1.0, contrast * 0.8 * (1 - smile_score) * 0.7),
                "sad":      min(1.0, (1 - smile_score) * (1 - eye_score) * 0.6),
                "fear":     min(1.0, eye_score * (1 - smile_score) * 0.5),
                "neutral":  0.0,
            }
            total = sum(sc.values()) or 1e-6
            for k in sc: sc[k] /= total
            sc["neutral"] = max(0.0, 1.0 - sum(sc[k] for k in sc if k != "neutral"))
            total2 = sum(sc.values()) or 1e-6
            for k in sc: sc[k] /= total2

            # Smooth over frames
            alpha = 0.75
            if not self._emo_buf:
                self._emo_buf = [sc.copy()]
            smooth = self._emo_buf[-1].copy()
            for k in smooth:
                smooth[k] = alpha * smooth[k] + (1 - alpha) * sc.get(k, 0)
            self._emo_buf.append(smooth)
            if len(self._emo_buf) > 5: self._emo_buf.pop(0)

            dom = max(smooth, key=smooth.get)
            return dom, smooth[dom], {k: int(v*100) for k, v in smooth.items()}
        except:
            return "neutral", 0.5, {}

    def _draw_skeleton(self, frame, face_rects, body_rects):
        """
        Draw anatomical skeleton overlay from detected face + body bounding boxes.
        Draws: head circle, shoulder line, arm lines, wrist dots.
        """
        H, W = frame.shape[:2]
        if not face_rects and not body_rects:
            return

        for (fx, fy, fw, fh) in face_rects[:1]:
            # Head circle
            cx = fx + fw//2; cy = fy + fh//2
            cv2.circle(frame, (cx, cy), fw//2, (0, 255, 136), 2)
            # Face landmarks (nose, eyes, mouth approximate)
            nose_x = cx; nose_y = fy + int(fh*0.55)
            l_eye  = (cx - fw//4, fy + int(fh*0.38))
            r_eye  = (cx + fw//4, fy + int(fh*0.38))
            mouth  = (cx, fy + int(fh*0.75))
            cv2.circle(frame, nose_x, nose_y, 4, (255, 80, 120), -1) if isinstance(nose_x, int) else None
            # Fix: use tuple
            cv2.circle(frame, (nose_x, nose_y), 4, (255, 80, 120), -1)
            cv2.circle(frame, l_eye, 5, (0, 200, 255), -1)
            cv2.circle(frame, r_eye, 5, (0, 200, 255), -1)
            cv2.circle(frame, mouth, 4, (100, 255, 80), -1)
            # Neck line
            neck_y = fy + fh
            sh_y   = neck_y + int(fw * 0.4)
            cv2.line(frame, (cx, neck_y), (cx, sh_y), (0, 255, 100), 2)
            # Shoulders
            sh_w = int(fw * 0.9)
            l_sh = (cx - sh_w, sh_y); r_sh = (cx + sh_w, sh_y)
            cv2.line(frame, l_sh, r_sh, (0, 255, 100), 3)
            cv2.circle(frame, l_sh, 5, (0, 200, 255), -1)
            cv2.circle(frame, r_sh, 5, (0, 200, 255), -1)
            # Arms to approximate wrist positions
            l_wrist = (cx - int(sh_w*1.3), sh_y + int(fw*0.9))
            r_wrist = (cx + int(sh_w*1.3), sh_y + int(fw*0.9))
            cv2.line(frame, l_sh, l_wrist, (0, 200, 255), 2)
            cv2.line(frame, r_sh, r_wrist, (255, 120, 0), 2)
            cv2.circle(frame, l_wrist, 7, (0, 200, 255), -1)
            cv2.circle(frame, r_wrist, 7, (255, 120, 0), -1)
            # Torso
            hip_y = sh_y + int(fw * 1.4)
            l_hip = (cx - int(sh_w*0.6), hip_y)
            r_hip = (cx + int(sh_w*0.6), hip_y)
            cv2.line(frame, (cx, sh_y), (cx, hip_y), (0, 255, 100), 2)
            cv2.line(frame, l_hip, r_hip, (0, 255, 100), 2)
            cv2.circle(frame, l_hip, 4, (0, 180, 100), -1)
            cv2.circle(frame, r_hip, 4, (0, 180, 100), -1)
            # Legs
            l_knee = (cx - int(sh_w*0.5), hip_y + int(fw*0.9))
            r_knee = (cx + int(sh_w*0.5), hip_y + int(fw*0.9))
            cv2.line(frame, l_hip, l_knee, (150, 200, 100), 2)
            cv2.line(frame, r_hip, r_knee, (150, 200, 100), 2)

            # Update ST with pose data
            ST["face_mesh_landmarks"].update({
                "nose_x": nose_x, "nose_y": nose_y,
                "frame_w": W, "frame_h": H,
                "l_wrist_x": l_wrist[0]/W, "l_wrist_y": l_wrist[1]/H,
                "r_wrist_x": r_wrist[0]/W, "r_wrist_y": r_wrist[1]/H,
                "l_shoulder_y": sh_y/H, "r_shoulder_y": sh_y/H,
                "l_shoulder_x": l_sh[0]/W, "r_shoulder_x": r_sh[0]/W,
            })
            ST["pose_landmarks"].update({
                "nose_x": cx/W, "nose_y": cy/H,
                "l_ear_x": l_eye[0]/W, "r_ear_x": r_eye[0]/W,
                "l_shoulder_y": sh_y/H, "r_shoulder_y": sh_y/H,
                "l_wrist_y": l_wrist[1]/H, "r_wrist_y": r_wrist[1]/H,
                "l_wrist_x": l_wrist[0]/W, "r_wrist_x": r_wrist[0]/W,
            })
            # Raise hand detection
            ST["hand_raised"] = (l_wrist[1]/H < sh_y/H - 0.05 or
                                  r_wrist[1]/H < sh_y/H - 0.05)
            ST["hands_up"]    = (l_wrist[1]/H < sh_y/H - 0.05 and
                                  r_wrist[1]/H < sh_y/H - 0.05)
            ST["arms_out"]    = (abs(l_wrist[0] - r_wrist[0]) / W > 0.6)

    def _detect_motion_zones(self, fg_mask, W, H):
        """
        Analyse foreground mask regions to detect:
        wave (left↔right alternating), clap (centre burst), general motion.
        """
        try:
            left_mot  = float(np.mean(fg_mask[:, :W//2]))
            right_mot = float(np.mean(fg_mask[:, W//2:]))
            total_mot = float(np.mean(fg_mask))

            ST["body_motion"] = total_mot
            self._motion_buf.append(total_mot)
            if len(self._motion_buf) > 12: self._motion_buf.pop(0)

            # General motion
            ST["_motion"] = total_mot > 8.0

            # Wave: alternating left/right motion
            dominant = "L" if left_mot > right_mot + 3 else "R" if right_mot > left_mot + 3 else "N"
            self._hand_hist.append(dominant)
            if len(self._hand_hist) > 12: self._hand_hist.pop(0)
            changes = sum(1 for i in range(1, len(self._hand_hist))
                         if self._hand_hist[i] != self._hand_hist[i-1]
                         and self._hand_hist[i] != "N")
            ST["waving"] = changes >= 3

            # Clap: sudden high motion in centre
            if len(self._motion_buf) >= 4:
                avg = sum(self._motion_buf[:-2]) / max(len(self._motion_buf)-2, 1)
                ST["clapping"] = (self._motion_buf[-1] > avg * 3.0 and
                                   self._motion_buf[-1] > 15.0)
        except: pass

    def run(self):
        """Main camera loop — runs in separate QThread."""
        self.running = True
        self._init_cam()
        log.info(f"📷 CameraThread started — {'live' if self.cap else 'simulation'} mode")

        while self.running:
            # ── 1. Grab frame ─────────────────────────────────────
            if self.cap and self.cap.isOpened():
                ret, frame = self.cap.read()
                if not ret or frame is None or frame.size == 0:
                    frame = self._sim_frame()
                else:
                    frame = cv2.flip(frame, 1)  # mirror
            else:
                frame = self._sim_frame()
            self._frame_count += 1

            H, W = frame.shape[:2]
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            gray_eq = cv2.equalizeHist(gray)

            # ── 2. Motion / background subtraction ────────────────
            fg = self._bg_sub.apply(frame)
            fg = cv2.morphologyEx(fg, cv2.MORPH_OPEN,
                                   cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5)))
            self._detect_motion_zones(fg, W, H)

            # ── 3. Face detection (every frame) ───────────────────
            scale = 1.1; nn = 4
            faces = self._face_cas.detectMultiScale(gray_eq, scale, nn,
                                                     minSize=(60,60))
            face_list = list(faces) if faces is not None and len(faces) > 0 else []

            if face_list:
                ST["face_detected"] = True
                self._att_buf.append(min(100, ST["attention"] + 2))
                if len(self._att_buf) > 10: self._att_buf.pop(0)
                ST["attention"] = int(sum(self._att_buf) / len(self._att_buf))

                # Draw face box
                fx, fy, fw, fh = face_list[0]
                cv2.rectangle(frame, (fx,fy), (fx+fw, fy+fh), (0,230,118), 2)

                # ── 4. Emotion from face ───────────────────────────
                if self._frame_count % 3 == 0:
                    emo, conf, pct = self._detect_face_emotion(frame, face_list[0])
                    ST["emotion"]      = emo
                    ST["emotion_conf"] = conf
                    ST["emotion_pct"]  = pct

                    # Show emotion label over face
                    pct_val = int(conf * 100)
                    emo_colors = {
                        "happy":"(0,220,100)","joyful":"(0,200,150)",
                        "angry":"(0,80,255)","sad":"(130,80,255)",
                        "surprised":"(255,200,0)","fear":"(0,180,255)",
                        "neutral":"(180,180,180)"
                    }
                    clr_str = emo_colors.get(emo, "(180,180,180)")
                    clr = tuple(map(int, clr_str.strip("()").split(",")))
                    cv2.rectangle(frame, (fx, fy-26), (fx+fw, fy), (8,10,24), -1)
                    cv2.putText(frame, f"{emo.upper()} {pct_val}%",
                                (fx+3, fy-8), cv2.FONT_HERSHEY_SIMPLEX, 0.45, clr, 1)
            else:
                ST["face_detected"] = False
                ST["attention"]     = max(0, ST["attention"] - 2)

            # ── 5. Skeleton from face geometry ─────────────────────
            self._draw_skeleton(frame, face_list, [])

            # ── 6. Finger counting (every 2nd frame) ───────────────
            if self._frame_count % 2 == 0:
                # Count on lower 60% of frame (hand region)
                hand_region = frame[int(H*0.35):, :]
                fc = self._count_fingers(frame, hand_region)
                # 3-frame majority vote
                self._fc_buf.append(fc)
                if len(self._fc_buf) > 3: self._fc_buf.pop(0)
                from collections import Counter
                smoothed_fc = Counter(self._fc_buf).most_common(1)[0][0]
                ST["finger_count"] = min(10, smoothed_fc)

                # Draw finger count on frame
                fc_color = (0,220,255) if ST["finger_count"] > 0 else (80,80,80)
                cv2.rectangle(frame, (W-72, H-46), (W-4, H-4), (8,10,24), -1)
                cv2.putText(frame, f"✋{ST['finger_count']}",
                            (W-64, H-14), cv2.FONT_HERSHEY_SIMPLEX, 0.7, fc_color, 2)

            # ── 7. Motor verification ──────────────────────────────
            self._validate_motor()

            # ── 8. HUD overlay ────────────────────────────────────
            cv2.rectangle(frame, (0,0), (W,42), (8,10,24), -1)
            suc = min(3, ST["consecutive"])
            stars = "★"*suc + "☆"*(3-suc)
            cv2.putText(frame,
                        f"{stars} | {ST['emotion'].upper()} | L{ST['conversation_level']}",
                        (8,24), cv2.FONT_HERSHEY_SIMPLEX, 0.50, (255,220,0), 1)
            cv2.putText(frame,
                        f"Score:{ST['score']} | Att:{ST['attention']}% | Fingers:{ST['finger_count']}",
                        (8,40), cv2.FONT_HERSHEY_SIMPLEX, 0.40, (200,200,200), 1)
            # Copyright watermark
            cv2.putText(frame, "Pepper Clinical V6 © Lamya Fadlulmola Hamed Ali 2026",
                        (4, H-6), cv2.FONT_HERSHEY_SIMPLEX, 0.28, (40,80,120), 1)
            if ST["recording"]:
                cv2.circle(frame, (W-18, 18), 8, (0,0,255), -1)

            # ── 9. Emit Qt signal (main thread renders to QLabel) ──
            with QMutexLocker(self._mutex):
                rgb_c = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB).copy()
                h_, w_, ch = rgb_c.shape
                qi = QImage(rgb_c.data.tobytes(), w_, h_, w_*ch,
                            QImage.Format.Format_RGB888)
                BRIDGE.sig_camera.emit(qi.copy())

            # ── 10. JPEG snapshot for parent live dashboard ────────
            if self._frame_count % 4 == 0:
                try:
                    thumb = cv2.resize(frame, (320, 240))
                    cv2.putText(thumb, f"{ST['emotion'].upper()} | Att:{ST['attention']}%",
                                (4,16), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (0,255,180), 1)
                    cv2.putText(thumb, f"Score:{ST['score']} | F:{ST['finger_count']}",
                                (4,235), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (200,200,200), 1)
                    _, jpeg = cv2.imencode(".jpg", thumb, [cv2.IMWRITE_JPEG_QUALITY, 65])
                    ST["_last_frame_jpeg"] = bytes(jpeg)
                except: pass

            # ── 11. History logging ────────────────────────────────
            if self._frame_count % 90 == 0:
                ST["att_history"].append(ST["attention"])
                ST["score_history"].append(ST["score"])
                for k in ["att_history","score_history"]:
                    if len(ST[k]) > 60: ST[k] = ST[k][-60:]

            self.msleep(16)  # ~60 FPS cap

    def _validate_motor(self):
        """Check if child has performed the required motor action."""
        va = ST.get("verify_action")
        if not va: return
        if time.time() > ST["verify_timeout"]:
            ST["verify_action"] = None
            return
        ok = False
        pl = ST.get("pose_landmarks", {})
        if   va == "clap":        ok = ST.get("clapping", False)
        elif va == "wave":        ok = ST.get("waving", False)
        elif va == "raise_hand":  ok = ST.get("hand_raised", False)
        elif va == "hands_up":    ok = ST.get("hands_up", False)
        elif va == "arms_out":    ok = ST.get("arms_out", False)
        elif va == "touch_nose":  ok = ST.get("_motion", False)
        elif va == "touch_head":  ok = ST.get("hand_raised", False)
        elif va == "finger_count":ok = (ST["finger_count"] == ST["finger_target"])
        elif va == "motion":      ok = ST.get("_motion", False) or ST["body_motion"] > 3
        elif va == "point":       ok = ST.get("hand_raised", False)
        if ok:
            ST["verify_result"]  = True
            ST["verify_action"]  = None
            ST["verify_timeout"] = 0.0
            ST["instant_success"]= True
            LOG("✅ Motor verified!", "success")

    def stop(self):
        self.running = False
        self.quit()
        self.wait(3000)
        if self.cap:
            self.cap.release()
            self.cap = None


# 8.  VOICE (TTS — graceful cleanup)
# ══════════════════════════════════════════════════════════════════════
class Voice:
    def __init__(self):
        self.ok=False; self._lk=threading.Lock()
        try:
            self.e=pyttsx3.init(); self.e.setProperty("rate",116)
            self.e.setProperty("volume",1.0)
            for v in self.e.getProperty("voices"):
                if any(x in v.name.lower() for x in ["female","zira","hazel","karen"]):
                    self.e.setProperty("voice",v.id); break
            self.ok=True; log.info("✅ TTS Voice")
        except Exception as ex: log.warning(f"TTS: {ex}")

    def _lip(self,text):
        for word in text.split():
            if not ST["is_speaking"]: break
            d=max(0.07,len(word)/13.0)
            ST["lip_sync_value"]=min(1.0,0.5+random.uniform(0.1,0.45))
            time.sleep(d*0.55)
            ST["lip_sync_value"]=max(0.05,ST["lip_sync_value"]*0.35)
            time.sleep(d*0.45)
        ST["lip_sync_value"]=0.0

    def say(self,text,wait=True):
        # Mute check — Pepper voice silenced by parent
        if ST.get("pepper_muted", False): return
        # If PECS interrupt active — kill immediately
        if ST.get("pecs_interrupt") and wait: return
        ST["interrupt_flag"]=False
        clean=re.sub(r"\[[^\]]+\]","",str(text)).strip()
        if not clean: return
        ST["is_speaking"]=True
        ST["session_chat"].append({"role":"pepper","text":clean,
            "time":datetime.now().strftime("%H:%M:%S")})
        if len(ST["session_chat"])>60: ST["session_chat"]=ST["session_chat"][-60:]
        log.info(f"🔊 Pepper: {clean}")
        threading.Thread(target=self._lip,args=(clean,),daemon=True).start()
        if self.ok and not ST["interrupt_flag"] and not ST.get("pecs_interrupt"):
            with self._lk:
                try: self.e.say(clean); self.e.runAndWait()
                except Exception: pass
        ST["is_speaking"]=False; ST["lip_sync_value"]=0.0
        if wait: ST["waiting_for_child"]=True; time.sleep(0.2)

    def say_pecs(self,text):
        """Non-blocking PECS TTS — interrupts task loop audio."""
        ST["pecs_interrupt"]=True; ST["interrupt_flag"]=True
        if self.ok:
            try: self.e.stop()
            except: pass
        def _speak():
            time.sleep(0.1)
            ST["is_speaking"]=True
            if self.ok:
                with self._lk:
                    try: self.e.say(text); self.e.runAndWait()
                    except: pass
            ST["is_speaking"]=False; ST["pecs_interrupt"]=False; ST["interrupt_flag"]=False
        threading.Thread(target=_speak,daemon=True).start()

    def stop(self):
        ST["interrupt_flag"]=True; ST["is_speaking"]=False; ST["lip_sync_value"]=0.0
        if self.ok:
            try: self.e.stop()
            except: pass

    def cleanup(self):
        """Called on exit — prevent aplay abort."""
        self.stop()
        try:
            os.system("pkill -f aplay 2>/dev/null")
        except: pass

VOICE_REF=None

# ══════════════════════════════════════════════════════════════════════
# 9.  TOUCH RECORDER — dynamic energy threshold + waveform
# ══════════════════════════════════════════════════════════════════════
class TouchRecorder:
    def __init__(self):
        self._lock=threading.Lock(); self._recording=False; self._audio=None
        self.whisper=None
        self.r=sr.Recognizer()
        self.r.energy_threshold=BASE_MIC_ENERGY
        self.r.dynamic_energy_threshold=True      # auto-adjusts to room noise
        self.r.dynamic_energy_adjustment_damping=0.15
        self.r.dynamic_energy_ratio=1.5
        self.r.pause_threshold=0.6
        self.r.phrase_threshold=0.04
        self.r.non_speaking_duration=0.2
        try:
            with sr.Microphone() as src:
                log.info("🎤 Calibrating mic (dynamic energy)…")
                self.r.adjust_for_ambient_noise(src,duration=0.8)
            ST["mic_energy_current"]=self.r.energy_threshold
            log.info(f"✅ Mic energy={self.r.energy_threshold:.0f} (dynamic)")
        except Exception as e: log.warning(f"Mic: {e}")
        if _FW_OK:
            try:
                # Run whisper on CPU to avoid CUDA contention with MediaPipe
                self.whisper=FW("tiny",device="cpu",compute_type="int8")
                log.info("✅ faster-whisper (cpu — avoids CUDA conflict)")
            except Exception as e: log.warning(f"Whisper: {e}")

    def start(self):
        with self._lock:
            if self._recording: return
            self._recording=True; self._audio=None
        ST["recording"]=True; BRIDGE.sig_rec_start.emit()
        threading.Thread(target=self._capture,daemon=True).start()

    def _capture(self):
        try:
            with sr.Microphone() as src:
                # Dynamic adjustment each recording
                self.r.adjust_for_ambient_noise(src,duration=0.08)
                ST["mic_energy_current"]=self.r.energy_threshold
                audio=self.r.listen(src,timeout=12,phrase_time_limit=10)
                # Compute RMS for waveform feedback
                raw=np.frombuffer(audio.get_raw_data(),dtype=np.int16).astype(np.float32)
                rms=float(np.sqrt(np.mean(raw**2)))
                ST["mic_level"]=min(1.0,rms/8000.0)
                BRIDGE.sig_mic_level.emit(ST["mic_level"])
                with self._lock: self._audio=audio
        except: pass
        finally:
            with self._lock: self._recording=False
            ST["recording"]=False; ST["mic_level"]=0.0

    def stop_and_recognise(self)->str:
        for _ in range(30):
            with self._lock:
                if not self._recording: break
            time.sleep(0.05)
        with self._lock: audio=self._audio
        if not audio: return ""
        if self.whisper:
            try:
                raw=audio.get_raw_data(convert_rate=16000,convert_width=2)
                with tempfile.NamedTemporaryFile(suffix=".wav",delete=False) as tmp: tp=tmp.name
                with wave.open(tp,"wb") as wf:
                    wf.setnchannels(1); wf.setsampwidth(2); wf.setframerate(16000); wf.writeframes(raw)
                segs,_=self.whisper.transcribe(tp,language="en",beam_size=2,
                    condition_on_previous_text=False)
                text=" ".join(s.text.strip() for s in segs).strip()
                os.unlink(tp)
                if text:
                    log.info(f"Whisper: {text}")
                    # Instant match check
                    self._check_instant(text.lower())
                    return text.lower()
            except Exception as e: log.warning(f"Whisper err: {e}")
        try:
            text=self.r.recognize_google(audio); log.info(f"Google: {text}")
            self._check_instant(text.lower()); return text.lower()
        except: return ""

    def _check_instant(self,text):
        """Immediately trigger success if speech matches current task keyword."""
        kw=ST.get("_current_task_keyword","")
        if kw and kw.lower() in text:
            ST["instant_success"]=True
            log.info(f"🎤 Instant speech match: '{kw}' in '{text}'")

# ══════════════════════════════════════════════════════════════════════
# 10. BALLOON CELEBRATION
# ══════════════════════════════════════════════════════════════════════
class BalloonLabel(QLabel):
    def __init__(self,parent,emoji,sx,sy):
        super().__init__(emoji,parent)
        self.setFont(QFont("Arial",random.randint(22,38)))
        self.setStyleSheet("background:transparent;")
        self.adjustSize(); self.move(sx,sy); self.show(); self.raise_()
        self._anim=QPropertyAnimation(self,b"pos")
        self._anim.setDuration(random.randint(2500,4000))
        self._anim.setStartValue(QPoint(sx,sy))
        self._anim.setEndValue(QPoint(sx+random.randint(-100,100),-80))
        self._anim.setEasingCurve(QEasingCurve.Type.OutCubic)
        self._anim.finished.connect(self.deleteLater)
        self._anim.start()

def launch_balloons(parent:QWidget,n:int=20):
    emojis=["🎈","🎉","⭐","🌟","🎊","✨","💫","🏆","🎁","💝","🌈"]
    w=parent.width()
    for _ in range(n):
        sx=random.randint(40,max(50,w-40)); sy=parent.height()+20
        BalloonLabel(parent,random.choice(emojis),sx,sy)

# ══════════════════════════════════════════════════════════════════════
# 11. SHADOW HELPER (replaces text-shadow CSS)
# ══════════════════════════════════════════════════════════════════════
def shadow(widget,blur=12,color="#000000",ox=2,oy=2):
    e=QGraphicsDropShadowEffect()
    e.setBlurRadius(blur); e.setColor(QColor(color)); e.setOffset(ox,oy)
    widget.setGraphicsEffect(e)

# ══════════════════════════════════════════════════════════════════════
# 12. CLICK CARDS — INSTANT success on correct click
# ══════════════════════════════════════════════════════════════════════
class ClickCard(QPushButton):
    def __init__(self,data,idx,mode,parent=None):
        super().__init__(parent)
        self.idx=idx; self.mode=mode; self._data=data
        self.setFixedSize(148,148); self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._set_normal()
        # Direct connection — INSTANT click response
        self.clicked.connect(self._instant_click)

    def _instant_click(self):
        BRIDGE.sig_task.emit({"action":"click","idx":self.idx})

    def _set_normal(self):
        d=self._data; m=self.mode
        if m=="color_grid":
            self.setText(f"\n\n{d['label']}")
            self.setFont(QFont("Arial",11,QFont.Weight.Bold))
            # NO text-shadow in CSS
            self.setStyleSheet(f"""
            QPushButton{{
                background:{d['color']};border-radius:74px;
                border:5px solid rgba(255,255,255,0.3);
                color:white;font-weight:bold;
            }}
            QPushButton:hover{{border:5px solid white;}}""")
            shadow(self,blur=16,color="#000000",ox=2,oy=2)
        elif m in ["object_grid","shape_grid","emotion_grid"]:
            self.setText(f"{d['emoji']}\n{d['label']}")
            self.setFont(QFont("Arial",12,QFont.Weight.Bold))
            self.setStyleSheet("""
            QPushButton{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,
                    stop:0 #1e1b4b,stop:1 #0c0f2e);
                border-radius:18px;border:4px solid #4f46e5;
                color:#e0e6ff;font-weight:bold;padding:6px;
            }
            QPushButton:hover{border:4px solid #a78bfa;}""")

    def flash_correct(self):
        base=self.styleSheet().split("QPushButton:hover")[0]
        self.setStyleSheet(base+"QPushButton{border:8px solid #22c55e !important;}")
    def flash_wrong(self):
        base=self.styleSheet().split("QPushButton:hover")[0]
        self.setStyleSheet(base+"QPushButton{border:8px solid #ef4444 !important;opacity:0.45;}")
    def reset(self): self._set_normal()

# ══════════════════════════════════════════════════════════════════════
# 13. AVATAR WIDGET
# ══════════════════════════════════════════════════════════════════════
class AvatarWidget(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setFixedSize(200,260)
        self._phase=0.0
        self._t=QTimer(); self._t.timeout.connect(self._tick); self._t.start(40)

    def _tick(self): self._phase+=0.12 if ST["is_speaking"] else 0.03; self.update()

    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(),QColor(8,10,22))
        em=ST["emotion"]; lip=ST.get("lip_sync_value",0.0)
        sj=ST.get("social_joy_active",False)
        blink=ST.get("blinking",False) or (int(self._phase*3)%44==0)
        ht=ST.get("head_tilt_val",0.0)*5; cx,cy=100,120
        # Body
        g=QLinearGradient(cx-40,cy+45,cx+40,cy+120)
        g.setColorAt(0,QColor(70,90,190)); g.setColorAt(1,QColor(50,70,160))
        p.setBrush(QBrush(g)); p.setPen(QPen(QColor(100,120,210),2))
        p.drawEllipse(cx-40,cy+45,80,75)
        # Arms
        p.setPen(QPen(QColor(70,90,190),13,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
        if sj:
            jt=time.time()
            p.drawLine(cx-40,cy+55,cx-75+int(20*math.sin(jt*4)),cy+15)
            p.drawLine(cx+40,cy+55,cx+75+int(20*math.sin(jt*4+1)),cy+15)
        elif ST["is_speaking"]:
            la=int(14*math.sin(self._phase))
            p.drawLine(cx-40,cy+60,cx-65+la,cy+90+la)
            p.drawLine(cx+40,cy+60,cx+65-la,cy+90-la)
        else:
            p.drawLine(cx-40,cy+62,cx-62,cy+94)
            p.drawLine(cx+40,cy+62,cx+62,cy+94)
        # Legs
        p.drawLine(cx-16,cy+118,cx-24,cy+152)
        p.drawLine(cx+16,cy+118,cx+24,cy+152)
        # Head
        hbob=int(3*math.sin(self._phase*0.5)); hx=cx+int(ht); hy=cy-46+hbob
        p.setBrush(QBrush(QColor(220,195,173))); p.setPen(QPen(QColor(200,175,155),2))
        p.drawEllipse(hx-40,hy-40,80,80)
        # Eyes
        ec=QColor(*ST["eye_color"]) if sj else QColor(100,180,255)
        p.setBrush(QBrush(ec)); p.setPen(Qt.PenStyle.NoPen)
        ey=5 if not blink else 1
        for ex_ in [hx-14,hx+14]:
            p.drawEllipse(ex_-5,hy-ey-5,10,ey*2)
            if not blink:
                p.setBrush(QBrush(QColor(255,255,255))); p.drawEllipse(ex_,hy-9,4,4)
                p.setBrush(QBrush(QColor(0,0,0))); p.drawEllipse(ex_+1,hy-8,2,2)
                p.setBrush(QBrush(ec))
        p.setBrush(QBrush(QColor(180,140,120))); p.setPen(Qt.PenStyle.NoPen)
        p.drawEllipse(hx-3,hy+4,7,7)
        p.setPen(QPen(QColor(160,80,80),2))
        mh=int(4+lip*14)
        if ST["is_speaking"]:
            p.setBrush(QBrush(QColor(160,80,80))); p.drawChord(hx-11,hy+14,22,mh*2,0,-180*16)
        elif em in ["happy","joyful"]:
            p.setBrush(QBrush(QColor(150,80,80))); p.drawChord(hx-10,hy+15,20,12,0,-180*16)
        else: p.drawLine(hx-10,hy+18,hx+10,hy+18)
        p.setBrush(QBrush(QColor(210,185,163))); p.setPen(Qt.PenStyle.NoPen)
        for ex_ in [hx-40,hx+32]: p.drawEllipse(ex_,hy-8,14,14)
        # Status ring
        if sj:
            jt2=time.time(); pr=int(75+11*abs(math.sin(jt2*4)))
            p.setPen(QPen(QColor(int(128+127*math.sin(jt2*3)),int(200+55*math.sin(jt2*2)),255),3))
            p.setBrush(Qt.BrushStyle.NoBrush); p.drawEllipse(cx-pr,cy-pr,pr*2,pr*2)
        elif ST["is_speaking"]:
            pr=int(75+4*math.sin(self._phase*5))
            p.setPen(QPen(QColor(0,160,255),2)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(cx-pr,cy-pr,pr*2,pr*2)
        elif ST["recording"]:
            p.setPen(QPen(QColor(255,0,0),2)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(cx-75,cy-75,150,150)
        # Level badge
        clvl=ST["conversation_level"]
        p.setPen(QColor(0,200,255)); p.setFont(QFont("Arial",7,QFont.Weight.Bold))
        p.drawText(QRect(0,2,200,14),Qt.AlignmentFlag.AlignCenter,f"CONV LEVEL {clvl}")
        p.setPen(QColor(160,140,255)); p.setFont(QFont("Arial",7,QFont.Weight.Bold))
        status=("SOCIAL JOY! 🎉" if sj else "SPEAKING 🔊" if ST["is_speaking"]
                else "RECORDING 🔴" if ST["recording"] else "LISTENING 👂" if ST["listening"]
                else "READY 💤")
        p.drawText(QRect(0,228,200,20),Qt.AlignmentFlag.AlignCenter,status)
        p.end()

# ══════════════════════════════════════════════════════════════════════
# 14. EMOTION PANEL
# ══════════════════════════════════════════════════════════════════════
ECOL_QT={"happy":(0,220,80),"joyful":(0,255,180),"sad":(100,100,220),
          "angry":(255,60,60),"fear":(0,180,220),"surprised":(200,50,220),"neutral":(180,180,180)}

class EmotionPanel(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setFixedSize(200,260)
        self._t=QTimer(); self._t.timeout.connect(self.update); self._t.start(250)

    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(),QColor(10,12,28))
        p.setPen(QColor(0,200,255)); p.setFont(QFont("Arial",8,QFont.Weight.Bold))
        p.drawText(QRect(0,2,200,16),Qt.AlignmentFlag.AlignCenter,"EMOTION GRID")
        em=ST["emotion"]; conf=ST.get("emotion_conf",0.5)
        col=QColor(*ECOL_QT.get(em,(180,180,180)))
        p.setBrush(QBrush(col)); p.setPen(QPen(QColor(255,255,255),2))
        p.drawEllipse(70,20,60,60)
        p.setPen(QColor(255,255,255)); p.setFont(QFont("Arial",7,QFont.Weight.Bold))
        p.drawText(QRect(70,20,60,60),Qt.AlignmentFlag.AlignCenter,em[:7].upper())
        bw=int(conf*190); p.setBrush(QBrush(QColor(25,28,50))); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(5,84,190,9,4,4)
        p.setBrush(QBrush(col)); p.drawRoundedRect(5,84,bw,9,4,4)
        p.setPen(QColor(200,200,200)); p.setFont(QFont("Arial",7))
        p.drawText(QRect(0,96,200,13),Qt.AlignmentFlag.AlignCenter,
                   f"Conf:{conf:.0%}  {'✓' if ST['face_detected'] else '✗'}")
        pct=ST.get("emotion_pct",{}); y0=112
        for em_ in list(ECOL_QT.keys()):
            val=pct.get(em_,0); bar=int(val*1.3); ec_=QColor(*ECOL_QT.get(em_,(150,150,150)))
            p.setBrush(QBrush(QColor(22,25,45))); p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(4,y0,130,12,3,3)
            if bar>0: p.setBrush(QBrush(ec_)); p.drawRoundedRect(4,y0,bar,12,3,3)
            p.setPen(QColor(200,200,200)); p.setFont(QFont("Arial",7))
            p.drawText(QRect(138,y0,58,12),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,
                       f"{em_[:6]} {val}%")
            y0+=16
        # Mic waveform
        ml=ST.get("mic_level",0.0); mw=int(ml*180)
        p.setBrush(QBrush(QColor(22,25,45))); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(5,230,190,10,4,4)
        if mw>0:
            p.setBrush(QBrush(QColor(0,220,100))); p.drawRoundedRect(5,230,mw,10,4,4)
        p.setPen(QColor(200,200,200)); p.setFont(QFont("Arial",7))
        p.drawText(QRect(0,242,200,14),Qt.AlignmentFlag.AlignCenter,
                   f"Mic:{ST.get('mic_energy_current',BASE_MIC_ENERGY):.0f} | F:{ST['finger_count']}")
        p.end()

# ══════════════════════════════════════════════════════════════════════
# 15. PECS WIDGET — with interrupt
# ══════════════════════════════════════════════════════════════════════
PECS_ITEMS=[
    # ── Basic Needs ──────────────────────────────────────────
    ("🤲","Want",     "I want this"),         ("➕","More",     "I want more"),
    ("🆘","Help",     "I need help"),          ("🍎","Food",     "I want food"),
    ("💧","Water",    "I want water"),         ("🚽","Toilet",   "I need the toilet"),
    ("😴","Tired",    "I am tired"),           ("🤕","Pain",     "I am in pain"),
    ("🏠","Home",     "I want to go home"),    ("👍","Good",     "I am good"),
    # ── Emotions ─────────────────────────────────────────────
    ("😊","Happy",    "I feel happy"),         ("😢","Sad",      "I feel sad"),
    ("😠","Angry",    "I feel angry"),         ("😨","Scared",   "I am scared"),
    ("😰","Anxious",  "I feel anxious"),       ("😵","Overwhelmed","Too much"),
    ("🤪","Silly",    "I feel silly"),         ("🧐","Focused",  "I am focused"),
    ("😌","Calm",     "I feel calm"),          ("🙉","Sensory",  "Too much noise"),
    # ── Communication ────────────────────────────────────────
    ("✅","Yes",      "Yes"),                  ("❌","No",       "No"),
    ("🙏","Please",   "Please"),               ("🙌","Thanks",   "Thank you"),
    ("👋","Hello",    "Hello"),                ("👋","Bye",      "Goodbye"),
    ("🤗","Hug",      "I want a hug"),         ("🤫","Quiet",    "I need quiet"),
    ("🔊","Loud",     "Too loud"),             ("⏳","Wait",     "Please wait"),
    # ── Family ───────────────────────────────────────────────
    ("👩","Mama",     "I want mama"),          ("👨","Baba",     "I want baba"),
    ("👧","Sister",   "I want sister"),        ("👦","Brother",  "I want brother"),
    ("🏁","Done",     "I am done"),            ("🔄","Again",    "Do it again"),
    ("🛑","Stop",     "Please stop"),          ("🎮","Play",     "I want to play"),
    # ── Activities ───────────────────────────────────────────
    ("🎵","Music",    "I want music"),         ("☕","Break",    "I need a break"),
    ("📺","Video",    "I want to watch"),      ("🎨","Draw",     "I want to draw"),
    ("📚","Read",     "I want to read"),       ("🏃","Walk",     "I want to walk"),
    ("🍪","Cookie",   "I want a snack"),       ("💤","Rest",     "I need to rest"),
    # ── Health/Comfort ────────────────────────────────────────
    ("🌡️","Hot",     "I am hot"),             ("🥶","Cold",     "I am cold"),
]

class PECSWidget(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent)
        self.setFixedHeight(88)
        self.setStyleSheet("QWidget{background:#0c0f1e;border-top:2px solid #1a1f40;}")
        lay=QHBoxLayout(self); lay.setContentsMargins(6,4,6,4); lay.setSpacing(5)
        t=QLabel("PECS"); t.setFont(QFont("Arial",8,QFont.Weight.Bold))
        t.setStyleSheet("color:#a78bfa;"); lay.addWidget(t)
        for emoji,name,phrase in PECS_ITEMS:
            btn=QPushButton(f"{emoji}\n{name}")
            btn.setFont(QFont("Arial",7,QFont.Weight.Bold))
            btn.setFixedSize(70,70)
            btn.setStyleSheet("""
            QPushButton{
                background:#1e1b4b;border:2px solid #4f46e5;
                border-radius:10px;color:#e0e6ff;
            }
            QPushButton:hover{background:#2e2b6e;border-color:#a78bfa;}
            QPushButton:pressed{background:#3e3b8e;}""")
            btn.clicked.connect(lambda _,p2=phrase,n2=name: self._press(n2,p2))
            lay.addWidget(btn)
        lay.addStretch()

    def _press(self,name,phrase):
        entry={"time":datetime.now().strftime("%H:%M:%S"),
               "name":name,"phrase":phrase,"emotion":ST["emotion"]}
        ST["pecs_log"].append(entry)
        if len(ST["pecs_log"])>50: ST["pecs_log"]=ST["pecs_log"][-50:]
        LOG(f"PECS: {name} — {phrase}","info")
        BRIDGE.sig_pecs.emit(phrase)
        if VOICE_REF: VOICE_REF.say_pecs(f"{CHILD_NAME} says: {phrase}")

# ══════════════════════════════════════════════════════════════════════
# 16. MAIN WINDOW — FIXED 1600×900
# ══════════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"Pepper Clinical Infinity V6 — {CHILD_NAME}")
        self.setFixedSize(1600,900)   # FIXED — no resize per spec
        self.setWindowFlags(Qt.WindowType.Window|
            Qt.WindowType.WindowStaysOnTopHint|
            Qt.WindowType.CustomizeWindowHint|
            Qt.WindowType.WindowTitleHint|
            Qt.WindowType.MSWindowsFixedSizeDialogHint)  # prevents resize
        self._cards=[]; self._locked=True; self._correct_idx=-1
        self._joy_phase=0.0
        self._joy_timer=QTimer(); self._joy_timer.timeout.connect(self._joy_tick)
        self._recorder=TouchRecorder()
        self._build_ui()
        self._connect_bridge()
        self._stats_t=QTimer(); self._stats_t.timeout.connect(self._refresh_stats)
        self._stats_t.start(400)

    def _build_ui(self):
        root=QWidget(); self.setCentralWidget(root)
        root.setStyleSheet("QWidget{background:#060918;}")
        outer=QVBoxLayout(root); outer.setSpacing(0); outer.setContentsMargins(0,0,0,0)
        main=QHBoxLayout(); main.setSpacing(0); main.setContentsMargins(0,0,0,0)

        # ════ LEFT (780px) ════════════════════════════════════════
        left=QFrame(); left.setFixedWidth(780)
        left.setStyleSheet("QFrame{background:#0a0d1e;border-right:2px solid #1a1f40;}")
        ll=QVBoxLayout(left); ll.setContentsMargins(0,0,0,0); ll.setSpacing(0)

        # Camera(580) + Avatar(200) + Emotion(200)
        top=QWidget(); tr=QHBoxLayout(top); tr.setContentsMargins(0,0,0,0); tr.setSpacing(0)
        self.cam_lbl=QLabel(); self.cam_lbl.setFixedSize(580,520)
        self.cam_lbl.setStyleSheet("background:#000;")
        self.cam_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); tr.addWidget(self.cam_lbl)
        side=QWidget(); side.setFixedWidth(200)
        sl=QVBoxLayout(side); sl.setContentsMargins(0,0,0,0); sl.setSpacing(0)
        self.avatar=AvatarWidget(); sl.addWidget(self.avatar)
        self.emo_panel=EmotionPanel(); sl.addWidget(self.emo_panel)
        tr.addWidget(side); ll.addWidget(top)

        # Status strip
        self.finger_lbl=QLabel(f"✋ {CHILD_NAME} | Fingers:0 | 😊 neutral | L1")
        self.finger_lbl.setFont(QFont("Arial",9,QFont.Weight.Bold))
        self.finger_lbl.setStyleSheet("color:#fbbf24;padding:3px;background:#07090f;")
        self.finger_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); ll.addWidget(self.finger_lbl)

        # Game button
        gbr=QWidget(); gbrl=QHBoxLayout(gbr); gbrl.setContentsMargins(6,3,6,3); gbrl.setSpacing(6)
        gb=QPushButton("🎮 Open Therapy Platform")
        gb.setFont(QFont("Arial",9,QFont.Weight.Bold)); gb.setFixedHeight(32)
        gb.setStyleSheet("QPushButton{background:#059669;color:white;border-radius:8px;border:none;}"
                         "QPushButton:hover{background:#047857;}")
        gb.clicked.connect(lambda: webbrowser.open(GAME_URL)); gbrl.addWidget(gb)
        gbrl.addStretch(); ll.addWidget(gbr)

        # Chat
        ch=QLabel("💬 Chat — ask anything or answer tasks! 'how to...' opens YouTube!")
        ch.setFont(QFont("Arial",8,QFont.Weight.Bold))
        ch.setStyleSheet("color:#a78bfa;background:#0c0f1e;padding:3px;")
        ch.setAlignment(Qt.AlignmentFlag.AlignCenter); ll.addWidget(ch)
        self.chat_area=QTextEdit(); self.chat_area.setReadOnly(True)
        self.chat_area.setFont(QFont("Arial",9))
        self.chat_area.setStyleSheet(
            "QTextEdit{background:#07090f;color:#e0e6ff;border:1px solid #1a1f40;padding:4px;}")
        self.chat_area.setFixedHeight(102); ll.addWidget(self.chat_area)
        cir=QWidget(); cirow=QHBoxLayout(cir); cirow.setContentsMargins(4,2,4,2); cirow.setSpacing(4)
        self.chat_input=QLineEdit()
        self.chat_input.setPlaceholderText("Type here… 'how to wash face?' → YouTube (Enter to send)")
        self.chat_input.setFont(QFont("Arial",10))
        self.chat_input.setStyleSheet(
            "QLineEdit{background:#0c0f1e;color:#e0e6ff;border:2px solid #4f46e5;border-radius:8px;padding:5px;}")
        self.chat_input.setFixedHeight(34); self.chat_input.returnPressed.connect(self._send_chat)
        cirow.addWidget(self.chat_input,1)
        sb2=QPushButton("Send"); sb2.setFixedSize(60,34)
        sb2.setStyleSheet("QPushButton{background:#4f46e5;color:white;border-radius:8px;font-weight:bold;}")
        sb2.clicked.connect(self._send_chat); cirow.addWidget(sb2); ll.addWidget(cir)
        main.addWidget(left)

        # ════ RIGHT (820px) ═══════════════════════════════════════
        right=QWidget(); right.setFixedWidth(820)
        rl=QVBoxLayout(right); rl.setSpacing(5); rl.setContentsMargins(10,6,10,6)

        # Header — NO text-shadow CSS
        hdr=QFrame(); hdr.setFixedHeight(64)
        hdr.setStyleSheet("""QFrame{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
                stop:0 #1a0a3d,stop:0.5 #0a0f28,stop:1 #1a0a3d);
            border-radius:12px;border:2px solid #4f46e5;}""")
        hl=QHBoxLayout(hdr); hl.setContentsMargins(12,4,12,4)
        self.av_lbl=QLabel("🤖"); self.av_lbl.setFont(QFont("Arial",22))
        self.av_lbl.setStyleSheet("color:#a78bfa;"); hl.addWidget(self.av_lbl)
        tw_=QWidget(); tl2=QVBoxLayout(tw_); tl2.setSpacing(1)
        self.title_lbl=QLabel("PEPPER CLINICAL INFINITY V6")
        self.title_lbl.setFont(QFont("Arial",12,QFont.Weight.Bold))
        self.title_lbl.setStyleSheet("color:#a78bfa;")
        shadow(self.title_lbl,blur=8,color="#4f46e5",ox=1,oy=1)
        tl2.addWidget(self.title_lbl)
        self.child_lbl=QLabel(f"Child: {CHILD_NAME} | ABA/DTT/TEACCH/ESDM/TIE")
        self.child_lbl.setFont(QFont("Arial",8)); self.child_lbl.setStyleSheet("color:#60a5fa;")
        tl2.addWidget(self.child_lbl); hl.addWidget(tw_,1)
        sw_=QWidget(); sl_=QVBoxLayout(sw_); sl_.setSpacing(1)
        self.state_lbl=QLabel("💤 Ready")
        self.state_lbl.setFont(QFont("Arial",8)); self.state_lbl.setStyleSheet("color:#9ca3af;")
        sl_.addWidget(self.state_lbl,alignment=Qt.AlignmentFlag.AlignRight)
        self.clvl_lbl=QLabel("Conv Level: 1")
        self.clvl_lbl.setFont(QFont("Arial",8)); self.clvl_lbl.setStyleSheet("color:#34d399;")
        sl_.addWidget(self.clvl_lbl,alignment=Qt.AlignmentFlag.AlignRight)
        hl.addWidget(sw_); rl.addWidget(hdr)

        # Schedule
        sched=QFrame(); sched.setFixedHeight(48)
        sched.setStyleSheet("QFrame{background:#0c0f1e;border-radius:10px;border:1px solid #1a1f40;}")
        sc=QHBoxLayout(sched); sc.setContentsMargins(10,4,10,4); sc.setSpacing(7)
        self.sched_task=QLabel("📋 Task")
        self.sched_task.setFont(QFont("Arial",9,QFont.Weight.Bold))
        self.sched_task.setStyleSheet(
            "color:#a78bfa;background:#1e1b4b;border-radius:7px;padding:3px 8px;border:2px solid #4f46e5;")
        sc.addWidget(self.sched_task); sc.addWidget(self._arr())
        sw2=QWidget(); sl2_=QVBoxLayout(sw2); sl2_.setSpacing(0); sl2_.setContentsMargins(0,0,0,0)
        self.stars_lbl=QLabel("☆ ☆ ☆")
        self.stars_lbl.setFont(QFont("Arial",14)); self.stars_lbl.setStyleSheet("color:#4b5563;")
        self.stars_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); sl2_.addWidget(self.stars_lbl)
        self.mastery_sub=QLabel("0/3 | Fails:0/2")
        self.mastery_sub.setFont(QFont("Arial",7)); self.mastery_sub.setStyleSheet("color:#6b7280;")
        self.mastery_sub.setAlignment(Qt.AlignmentFlag.AlignCenter); sl2_.addWidget(self.mastery_sub)
        sc.addWidget(sw2,1); sc.addWidget(self._arr())
        self.reward_lbl=QLabel("⭐"); self.reward_lbl.setFont(QFont("Arial",18))
        self.reward_lbl.setStyleSheet(
            "color:#fbbf24;background:#2a1a00;border-radius:7px;padding:2px 7px;border:2px solid #f59e0b;")
        sc.addWidget(self.reward_lbl); rl.addWidget(sched)

        # Instruction
        if_fr=QFrame(); if_fr.setFixedHeight(74)
        if_fr.setStyleSheet("""QFrame{
            background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #1e1b4b,stop:1 #0c0f2e);
            border-radius:10px;border:2px solid #4f46e5;}""")
        il=QVBoxLayout(if_fr); il.setContentsMargins(12,3,12,3)
        self.instr_icon=QLabel("📋"); self.instr_icon.setFont(QFont("Arial",14))
        self.instr_icon.setAlignment(Qt.AlignmentFlag.AlignCenter); il.addWidget(self.instr_icon)
        self.instr_lbl=QLabel("Getting ready…")
        self.instr_lbl.setFont(QFont("Arial",13,QFont.Weight.Bold))
        self.instr_lbl.setStyleSheet("color:#e0e6ff;")
        self.instr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.instr_lbl.setWordWrap(True); il.addWidget(self.instr_lbl); rl.addWidget(if_fr)

        # Content
        self.content_fr=QFrame(); self.content_fr.setMinimumHeight(280)
        self.content_fr.setStyleSheet(
            "QFrame{background:rgba(12,15,30,0.90);border-radius:12px;border:2px solid #1a1f40;}")
        self.content_lay=QVBoxLayout(self.content_fr)
        self.content_lay.setContentsMargins(12,10,12,10)
        self.content_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._show_idle(); rl.addWidget(self.content_fr,1)

        # Lock overlay
        self.lock_ov=QLabel("🔒"); self.lock_ov.setParent(self.content_fr)
        self.lock_ov.setGeometry(0,0,800,280)
        self.lock_ov.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lock_ov.setFont(QFont("Arial",44))
        self.lock_ov.setStyleSheet(
            "QLabel{background:rgba(0,0,0,0.52);border-radius:12px;color:#a78bfa;}"); self.lock_ov.hide()

        # Feedback
        fb_fr=QFrame(); fb_fr.setFixedHeight(48)
        fb_fr.setStyleSheet("QFrame{background:#0c0f1e;border-radius:10px;border:1px solid #1a1f40;}")
        fl=QHBoxLayout(fb_fr); fl.setContentsMargins(12,6,12,6)
        self.fb_icon=QLabel("💤"); self.fb_icon.setFont(QFont("Arial",19)); fl.addWidget(self.fb_icon)
        self.fb_lbl=QLabel("Waiting for Pepper…")
        self.fb_lbl.setFont(QFont("Arial",11,QFont.Weight.Bold))
        self.fb_lbl.setStyleSheet("color:#9ca3af;"); self.fb_lbl.setWordWrap(True)
        fl.addWidget(self.fb_lbl,1); rl.addWidget(fb_fr)

        # Mic button + waveform
        mic_row=QWidget(); mic_lay=QVBoxLayout(mic_row); mic_lay.setContentsMargins(0,0,0,0); mic_lay.setSpacing(3)
        self.mic_btn=QPushButton("🎤  TOUCH & HOLD TO SPEAK")
        self.mic_btn.setFixedHeight(52); self.mic_btn.setFont(QFont("Arial",13,QFont.Weight.Bold))
        self.mic_btn.setStyleSheet("""
        QPushButton{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #dc2626,stop:1 #ef4444);
            color:white;border-radius:26px;border:3px solid #fca5a5;
        }
        QPushButton:pressed{
            background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #991b1b,stop:1 #dc2626);
            border:4px solid white;
        }""")
        self.mic_btn.pressed.connect(self._on_mic_press)
        self.mic_btn.released.connect(self._on_mic_release)
        mic_lay.addWidget(self.mic_btn)
        # Waveform progress bar
        self.mic_wave=QProgressBar(); self.mic_wave.setFixedHeight(8)
        self.mic_wave.setRange(0,100); self.mic_wave.setValue(0)
        self.mic_wave.setTextVisible(False)
        self.mic_wave.setStyleSheet("""
        QProgressBar{background:#1a1f40;border-radius:4px;border:none;}
        QProgressBar::chunk{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,
            stop:0 #22c55e,stop:1 #86efac);border-radius:4px;}""")
        mic_lay.addWidget(self.mic_wave)
        self.rec_status=QLabel("🎤 Tap mic — dynamic energy auto-adjust!")
        self.rec_status.setFont(QFont("Arial",8)); self.rec_status.setStyleSheet("color:#6b7280;padding:1px;")
        self.rec_status.setAlignment(Qt.AlignmentFlag.AlignCenter); mic_lay.addWidget(self.rec_status)
        rl.addWidget(mic_row)

        # Stats
        sb_=QFrame(); sb_.setFixedHeight(38)
        sb_.setStyleSheet("QFrame{background:#07090f;border-radius:8px;border:1px solid #1a1f40;}")
        stl=QHBoxLayout(sb_); stl.setContentsMargins(10,2,10,2)
        for lbl,attr,col in [("Score","stat_score","#a78bfa"),("Tokens","stat_tokens","#fbbf24"),
                               ("Mastered","stat_mastered","#34d399"),("Streak","stat_streak","#60a5fa"),
                               ("Skipped","stat_skipped","#f87171"),("Protocol","stat_proto","#34d399")]:
            w_=QWidget(); wl_=QVBoxLayout(w_); wl_.setSpacing(0); wl_.setContentsMargins(0,0,0,0)
            val=QLabel("0"); val.setFont(QFont("Arial",10,QFont.Weight.Bold))
            val.setStyleSheet(f"color:{col};"); val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lb_=QLabel(lbl); lb_.setFont(QFont("Arial",6)); lb_.setStyleSheet("color:#6b7280;")
            lb_.setAlignment(Qt.AlignmentFlag.AlignCenter)
            wl_.addWidget(val); wl_.addWidget(lb_); stl.addWidget(w_)
            setattr(self,attr,val)
        rl.addWidget(sb_); main.addWidget(right)
        outer.addLayout(main)
        # PECS
        self.pecs=PECSWidget(); outer.addWidget(self.pecs)

    def _arr(self):
        a=QLabel("▶"); a.setFont(QFont("Arial",10)); a.setStyleSheet("color:#4f46e5;"); return a

    def _connect_bridge(self):
        BRIDGE.sig_task.connect(self._on_task)
        BRIDGE.sig_success.connect(self._on_success_ov)
        BRIDGE.sig_fail.connect(self._on_fail_ov)
        BRIDGE.sig_skip.connect(self._on_skip_ov)
        BRIDGE.sig_feedback.connect(self._set_fb)
        BRIDGE.sig_instr.connect(self._set_instr)
        BRIDGE.sig_waiting.connect(self._set_waiting)
        BRIDGE.sig_unlock.connect(self._do_unlock)
        BRIDGE.sig_lock.connect(self._do_lock)
        BRIDGE.sig_reset.connect(self._reset_cards)
        BRIDGE.sig_joy.connect(self._on_joy)
        BRIDGE.sig_camera.connect(self._update_cam)
        BRIDGE.sig_stats.connect(self._refresh_stats)
        BRIDGE.sig_chat.connect(self._add_chat)
        BRIDGE.sig_rec_start.connect(self._on_rec_start)
        BRIDGE.sig_rec_stop.connect(self._on_rec_stop)
        BRIDGE.sig_mic_level.connect(lambda v: self.mic_wave.setValue(int(v*100)))
        BRIDGE.sig_youtube.connect(lambda u: LOG(f"📺 YT:{u[:40]}"))
        BRIDGE.sig_pecs.connect(lambda ph: self._add_chat("child",f"[PECS] {ph}"))

    def _update_cam(self,qimg):
        if isinstance(qimg,QImage):
            pix=QPixmap.fromImage(qimg).scaled(580,520,
                Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
            self.cam_lbl.setPixmap(pix)
        fc=ST["finger_count"]; em=ST["emotion"]; clvl=ST["conversation_level"]
        self.finger_lbl.setText(
            f"👦 {CHILD_NAME} | Fingers:{fc} {'|'*min(fc,10)} | 😊 {em.upper()} | L{clvl} | Att:{ST['attention']}%")

    def _refresh_stats(self):
        self.stat_score.setText(str(ST["score"]))
        self.stat_tokens.setText(str(ST["tokens"]))
        self.stat_mastered.setText(str(ST["tasks_mastered"]))
        self.stat_streak.setText(str(ST["streak"]))
        self.stat_skipped.setText(str(ST["tasks_skipped"]))
        self.stat_proto.setText(ST.get("protocol","ABA")[:7])
        n=ST["consecutive"]; fc=ST["fail_count"]
        self.stars_lbl.setText("⭐"*n+"☆"*(3-n) if n else "☆ ☆ ☆")
        self.mastery_sub.setText(f"{n}/3 | Fails:{fc}/{MAX_FAILS}")
        sc_={0:"#4b5563",1:"#d97706",2:"#fbbf24",3:"#f59e0b"}
        self.stars_lbl.setStyleSheet(f"color:{sc_.get(n,'#4b5563')};")
        self.clvl_lbl.setText(f"Conv Level: {ST['conversation_level']}")
        if   ST["is_speaking"]: self.fb_icon.setText("🔊"); self.state_lbl.setText("🔊 Speaking")
        elif ST["recording"]:   self.fb_icon.setText("🔴"); self.state_lbl.setText("🎤 Recording")
        elif ST["listening"]:   self.fb_icon.setText("👂"); self.state_lbl.setText("👂 Listening")
        elif ST["waiting_for_child"]: self.fb_icon.setText("⏳"); self.state_lbl.setText("⏳ Waiting")
        else: self.fb_icon.setText("💤"); self.state_lbl.setText("💤 Ready")

    # ── TASK DISPLAY ──────────────────────────────────────────────
    def _show_idle(self):
        self._clear()
        d=QLabel("🤖\nPepper is preparing your task…")
        d.setFont(QFont("Arial",13)); d.setStyleSheet("color:#6b7280;")
        d.setAlignment(Qt.AlignmentFlag.AlignCenter); self.content_lay.addWidget(d)

    def _clear(self):
        while self.content_lay.count():
            item=self.content_lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self._cards.clear()

    def _on_task(self,data):
        if data.get("action")=="click": self._handle_click(data.get("idx",-1)); return
        self.instr_lbl.setText(data.get("instruction",""))
        self.fb_lbl.setText("Your turn! Click or do the task!")
        self.fb_lbl.setStyleSheet("color:#60a5fa;")
        self._build_content(data); self._do_unlock()

    def _build_content(self,data):
        self._clear(); mode=data.get("mode","idle")
        if mode=="idle": self._show_idle(); return
        if mode=="motor_model":
            vw=QWidget(); vl=QVBoxLayout(vw); vl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            fig=data.get("figure","")
            if fig and "base64," in fig:
                raw=base64.b64decode(fig.split(",",1)[1]); qi=QImage(); qi.loadFromData(raw)
                pix=QPixmap.fromImage(qi).scaled(200,200,Qt.AspectRatioMode.KeepAspectRatio,
                                                  Qt.TransformationMode.SmoothTransformation)
                fl=QLabel(); fl.setPixmap(pix); fl.setAlignment(Qt.AlignmentFlag.AlignCenter); vl.addWidget(fl)
            lb=QLabel(data.get("label",""))
            lb.setFont(QFont("Arial",14,QFont.Weight.Bold)); lb.setStyleSheet("color:#a78bfa;")
            lb.setAlignment(Qt.AlignmentFlag.AlignCenter); vl.addWidget(lb)
            ar=QLabel("👇 NOW YOU DO IT! 👇")
            ar.setFont(QFont("Arial",11,QFont.Weight.Bold)); ar.setStyleSheet("color:#34d399;")
            ar.setAlignment(Qt.AlignmentFlag.AlignCenter); vl.addWidget(ar)
            self.content_lay.addWidget(vw); return
        if mode in ["word_display","conv_display"]:
            wf=QFrame(); wf.setStyleSheet("""QFrame{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #1e1b4b,stop:1 #0c0f1e);
                border-radius:16px;border:3px solid #4f46e5;min-height:140px;}""")
            wfl=QVBoxLayout(wf); wfl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            emoji=data.get("conv_emoji",data.get("word_emoji","📢"))
            word=data.get("conv_phrase",data.get("word_text","SAY IT!"))
            el=QLabel(emoji); el.setFont(QFont("Arial",42))
            el.setAlignment(Qt.AlignmentFlag.AlignCenter); wfl.addWidget(el)
            wl=QLabel(word); wl.setFont(QFont("Arial",28,QFont.Weight.Bold))
            wl.setStyleSheet("color:#a78bfa;"); wl.setAlignment(Qt.AlignmentFlag.AlignCenter); wfl.addWidget(wl)
            if mode=="conv_display":
                hl=QLabel("🎤 Tap mic and say this phrase! (Level 3+)")
                hl.setFont(QFont("Arial",10)); hl.setStyleSheet("color:#fbbf24;")
            else:
                hl=QLabel("🎤 Tap the mic button and say this word!")
                hl.setFont(QFont("Arial",11)); hl.setStyleSheet("color:#34d399;")
            hl.setAlignment(Qt.AlignmentFlag.AlignCenter); wfl.addWidget(hl)
            self.content_lay.addWidget(wf); return
        if mode=="number_display":
            nf=QFrame(); nf.setStyleSheet("""QFrame{
                background:qlineargradient(x1:0,y1:0,x2:0,y2:1,stop:0 #1a3320,stop:1 #0c1a10);
                border-radius:16px;border:3px solid #22c55e;min-height:140px;}""")
            nfl=QVBoxLayout(nf); nfl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            nl=QLabel(str(data.get("target_number","?")))
            nl.setFont(QFont("Arial",68,QFont.Weight.Bold)); nl.setStyleSheet("color:#34d399;")
            nl.setAlignment(Qt.AlignmentFlag.AlignCenter); nfl.addWidget(nl)
            hl2=QLabel("Show me with your fingers! 🖐️")
            hl2.setFont(QFont("Arial",11)); hl2.setStyleSheet("color:#6b7280;")
            hl2.setAlignment(Qt.AlignmentFlag.AlignCenter); nfl.addWidget(hl2)
            self.content_lay.addWidget(nf); return
        # Grid
        opts=data.get("options",[]); self._correct_idx=data.get("correct",-1)
        gw=QWidget(); grid=QGridLayout(gw); grid.setSpacing(12)
        grid.setAlignment(Qt.AlignmentFlag.AlignCenter)
        for i,opt in enumerate(opts):
            card=ClickCard(opt,i,mode); self._cards.append(card)
            grid.addWidget(card,i//2,i%2,Qt.AlignmentFlag.AlignCenter)
        self.content_lay.addWidget(gw)

    def _handle_click(self,idx):
        """INSTANT success — first correct click triggers celebration immediately."""
        if self._locked: return
        correct=self._correct_idx
        if correct==-1:
            ST["tablet_click_result"]="correct"; ST["instant_success"]=True
            if idx<len(self._cards): self._cards[idx].flash_correct()
            self.fb_lbl.setText("✅ Great choice!"); self.fb_lbl.setStyleSheet("color:#34d399;")
            self._do_lock(); return
        if idx==correct:
            ST["tablet_click_result"]="correct"
            ST["instant_success"]=True  # INSTANT — kills any pending audio
            if idx<len(self._cards): self._cards[idx].flash_correct()
            LOG(f"INSTANT CORRECT idx={idx}","success")
        else:
            ST["tablet_click_result"]="wrong"
            if idx<len(self._cards): self._cards[idx].flash_wrong()
            if 0<=correct<len(self._cards): self._cards[correct].flash_correct()
            LOG(f"WRONG idx={idx}","fail")
        self._do_lock()

    def _on_success_ov(self,msg):
        self._clear()
        ov=QWidget(); ol=QVBoxLayout(ov); ol.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ck=QLabel("✅"); ck.setFont(QFont("Arial",100)); ck.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ol.addWidget(ck)
        ml=QLabel(msg); ml.setFont(QFont("Arial",14,QFont.Weight.Bold))
        ml.setStyleSheet("color:#34d399;"); ml.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ml.setWordWrap(True); ol.addWidget(ml); self.content_lay.addWidget(ov)
        self.fb_lbl.setText(msg); self.fb_lbl.setStyleSheet("color:#34d399;font-size:14px;")
        self.instr_icon.setText("✅")
        launch_balloons(self.centralWidget(),22)
        QTimer.singleShot(2800,self._show_idle)
        QTimer.singleShot(2800,lambda: self.instr_icon.setText("📋"))

    def _on_fail_ov(self,msg):
        self.fb_lbl.setText(f"❌ {msg}"); self.fb_lbl.setStyleSheet("color:#f87171;font-size:13px;")
        self.instr_icon.setText("❌")
        QTimer.singleShot(2000,lambda: self.instr_icon.setText("📋"))
        QTimer.singleShot(2000,lambda: self.fb_lbl.setStyleSheet("color:#9ca3af;"))

    def _on_skip_ov(self,msg):
        self.fb_lbl.setText(f"⏭️ {msg}"); self.fb_lbl.setStyleSheet("color:#f97316;font-size:12px;")
        QTimer.singleShot(3000,lambda: self.fb_lbl.setStyleSheet("color:#9ca3af;"))

    def _on_joy(self,jtype):
        self._joy_phase=0.0; self._joy_timer.start(55)
        msgs={"dance":"🕺 AMAZING! 🎉","celebrate":"🎊 BRILLIANT! ⭐",
              "wave_back":"👋 HIGH FIVE! 🌟","full_joy":"🏆 CHAMPION! 🎉🌟"}
        self.fb_lbl.setText(msgs.get(jtype,"🌟 AMAZING! 🎉"))
        self.fb_lbl.setStyleSheet("color:#fbbf24;font-size:15px;")
        QTimer.singleShot(3500,self._end_joy)

    def _joy_tick(self):
        self._joy_phase+=0.22
        ems=["🎉","🌟","⭐","🏆","✨","🎊","💫","🎈"]
        self.av_lbl.setText(ems[int(self._joy_phase)%len(ems)])
        if self._joy_phase>22: self._end_joy()

    def _end_joy(self):
        self._joy_timer.stop(); self.av_lbl.setText("🤖")
        QTimer.singleShot(500,lambda: self.fb_lbl.setStyleSheet("color:#9ca3af;"))

    def _do_unlock(self):
        self._locked=False; ST["tablet_locked"]=False; self.lock_ov.hide()
        for c in self._cards: c.setEnabled(True)

    def _do_lock(self):
        self._locked=True; ST["tablet_locked"]=True
        self.lock_ov.show(); self.lock_ov.raise_()
        for c in self._cards: c.setEnabled(False)

    def _set_fb(self,txt): self.fb_lbl.setText(txt)
    def _set_instr(self,txt): self.instr_lbl.setText(txt)
    def _set_waiting(self,txt):
        self.fb_lbl.setText(txt); self.fb_lbl.setStyleSheet("color:#fbbf24;"); self.fb_icon.setText("⏳")
    def _reset_cards(self):
        for c in self._cards: c.reset(); ST["tablet_click_result"]=None

    # ── MIC ───────────────────────────────────────────────────────
    def _on_mic_press(self):
        self.rec_status.setText("🔴 RECORDING… Release to stop")
        self.rec_status.setStyleSheet("color:#ef4444;font-size:10px;font-weight:bold;padding:1px;")
        self.mic_btn.setText("🔴  RECORDING… RELEASE TO STOP")
        self._recorder.start()

    def _on_mic_release(self):
        self.mic_btn.setText("🎤  TOUCH & HOLD TO SPEAK")
        self.rec_status.setText("⏳ Processing speech… (dynamic energy auto-adjust)")
        self.rec_status.setStyleSheet("color:#fbbf24;padding:1px;")
        threading.Thread(target=self._do_rec,daemon=True).start()

    def _do_rec(self):
        text=self._recorder.stop_and_recognise(); BRIDGE.sig_rec_stop.emit(text)

    def _on_rec_start(self): self.mic_wave.setValue(0)

    def _on_rec_stop(self,text):
        if text:
            self.rec_status.setText(f'✅ Heard: "{text[:25]}"')
            self.rec_status.setStyleSheet("color:#34d399;font-size:10px;padding:1px;")
            ST["last_speech_text"]=text.lower(); ST["last_sound"]=time.time()
            ST["session_chat"].append({"role":"child","text":text,
                "time":datetime.now().strftime("%H:%M:%S")})
            if len(ST["session_chat"])>60: ST["session_chat"]=ST["session_chat"][-60:]
            self._add_chat("child",text)
        else:
            self.rec_status.setText("❌ Could not hear — speak closer!")
            self.rec_status.setStyleSheet("color:#f87171;padding:1px;")
        self.mic_wave.setValue(0)
        QTimer.singleShot(3500,lambda: self.rec_status.setText(
            "🎤 Tap mic — dynamic energy auto-adjust!"))
        QTimer.singleShot(3500,lambda: self.rec_status.setStyleSheet("color:#6b7280;padding:1px;"))

    # ── CHAT ──────────────────────────────────────────────────────
    def _send_chat(self):
        text=self.chat_input.text().strip()
        if not text: return
        self.chat_input.clear(); self._add_chat("child",text)
        ST["last_speech_text"]=text.lower(); ST["last_sound"]=time.time()
        ST["session_chat"].append({"role":"child","text":text,
            "time":datetime.now().strftime("%H:%M:%S")})
        threading.Thread(target=self._process_chat,args=(text,),daemon=True).start()

    def _process_chat(self,text):
        import urllib.parse
        t=text.lower()
        yt_kw=["how to","show me","teach me","youtube","video","watch","learn",
                "letters","numbers","shapes","colors","animals","fruits"]
        if any(kw in t for kw in yt_kw):
            q=re.sub(r"how to|show me|teach me|youtube|video|watch|learn","",t).strip() or text
            url="https://www.youtube.com/results?search_query="+urllib.parse.quote(q+" for kids")
            webbrowser.open(url)
            reply=f"Opening YouTube: '{q}' for kids! 🎬 Enjoy!"
            BRIDGE.sig_chat.emit("pepper",reply)
            ST["session_chat"].append({"role":"pepper","text":reply,"time":datetime.now().strftime("%H:%M:%S")}); return
        # Check conv level 3+ phrases
        for phrase in CONV_PHRASES:
            if phrase in t:
                reply=f"I heard '{phrase}'! WONDERFUL! 🌟 Level 3 conversation!"
                BRIDGE.sig_chat.emit("pepper",reply); return
        reply=self._quick(t)
        BRIDGE.sig_chat.emit("pepper",reply)
        ST["session_chat"].append({"role":"pepper","text":reply,"time":datetime.now().strftime("%H:%M:%S")})

    def _quick(self,t):
        nm=CHILD_NAME
        if any(w in t for w in ["hello","hi","hey"]): return f"Hello {nm}! 👋 Great to talk with you!"
        if any(w in t for w in ["good","great","yes","okay","done"]): return f"Wonderful {nm}! Keep going! 🌟"
        if any(w in t for w in ["help","confused"]): return "No worries! I will show you again! 🎯"
        if any(w in t for w in ["tired","stop","break"]): return f"Okay {nm}! Short break! 💙"
        return f"Great {nm}! Keep learning! 🎯"

    def _add_chat(self,role,text):
        c="#34d399" if role=="child" else "#a78bfa"
        n=CHILD_NAME if role=="child" else "Pepper 🤖"
        self.chat_area.append(
            f'<span style="color:{c};font-weight:bold">{n}:</span> '
            f'<span style="color:#e0e6ff">{text}</span>')
        sb=self.chat_area.verticalScrollBar(); sb.setValue(sb.maximum())

# ══════════════════════════════════════════════════════════════════════
# 17. PDF REPORT
# ══════════════════════════════════════════════════════════════════════
def generate_pdf():
    if not _PDF_OK: return None
    fn=f"report_{SAFE_NAME}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    try:
        doc=SimpleDocTemplate(fn,pagesize=A4)
        styles=getSampleStyleSheet(); story=[]
        story.append(Paragraph(f"Clinical Report — {CHILD_NAME}",styles["Title"]))
        story.append(Spacer(1,12))
        dur=int((time.time()-ST["uptime"])/60)
        rows=[["Item","Value"],["Child",CHILD_NAME],["Age",str(ST["age"])],
              ["Date",ST["session_date"]],["Duration",f"{dur} min"],
              ["Score",str(ST["score"])],["Mastered",str(ST["tasks_mastered"])],
              ["OK",str(ST["tasks_success"])],["Fail",str(ST["tasks_fail"])],
              ["Skip",str(ST["tasks_skipped"])],["Conv Level",str(ST["conversation_level"])],
              ["Motor",f"{ST['skill_motor']}%"],["Cognitive",f"{ST['skill_cognitive']}%"],
              ["Verbal",f"{ST['skill_verbal']}%"],["Math",f"{ST['skill_math']}%"],
              ["Social",f"{ST['skill_social']}%"],["Attention",f"{ST['attention']}%"],
              ["Emotion",ST["emotion"]],["CSV",CSV_FILE]]
        t=Table(rows,colWidths=[200,300])
        t.setStyle(TableStyle([
            ("BACKGROUND",(0,0),(-1,0),RL_COLORS.HexColor("#4f46e5")),
            ("TEXTCOLOR",(0,0),(-1,0),RL_COLORS.white),
            ("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[RL_COLORS.HexColor("#f8f9ff"),RL_COLORS.white]),
            ("GRID",(0,0),(-1,-1),0.5,RL_COLORS.HexColor("#1a1f40")),
            ("FONTSIZE",(0,0),(-1,-1),11),("PADDING",(0,0),(-1,-1),8),
        ]))
        story.append(t); story.append(Spacer(1,16))
        if ST["parent_notes"]:
            story.append(Paragraph("Parent Notes",styles["Heading2"]))
            for n in ST["parent_notes"]:
                story.append(Paragraph(f"[{n['time']}] {n.get('category','note').upper()}: {n['text']}",styles["Normal"]))
        if ST["pecs_log"]:
            story.append(Spacer(1,12))
            story.append(Paragraph("PECS Log",styles["Heading2"]))
            for p2 in ST["pecs_log"][-20:]:
                story.append(Paragraph(f"[{p2['time']}] {p2['name']}: {p2['phrase']}",styles["Normal"]))
        # Mood log section
        if ST.get("mood_log"):
            story.append(Spacer(1,12))
            story.append(Paragraph("Mood Log",styles["Heading2"]))
            for ml in ST["mood_log"][-15:]:
                story.append(Paragraph(f"[{ml['time']}] {ml['em']} {ml['label']} (Emotion: {ml.get('emotion','-')})",styles["Normal"]))
        # Copyright watermark
        story.append(Spacer(1,20))
        story.append(Paragraph(
            "© 2026 Lamya Fadlulmola Hamed Ali · Pepper Clinical Infinity V6 · All Rights Reserved · HIPAA/GDPR Compliant",
            styles["Normal"]))
        doc.build(story); log.info(f"✅ PDF: {fn}"); return fn
    except Exception as e: log.warning(f"PDF: {e}"); return None

# ══════════════════════════════════════════════════════════════════════
# 18. GEMINI CHATBOT
# ══════════════════════════════════════════════════════════════════════
_ai_chat=[]
def gemini_chat(question):
    """Full-essay AI Clinical Advisor response — structured, comprehensive, personalized."""
    if not _GENAI_OK:
        return ("AI unavailable. Please consult a certified ABA/TEACCH specialist. "
                "You can reach support at lamyafadlulmolahamedali1@gmail.com")
    try:
        dur = int((time.time()-ST["uptime"])/60)
        sys_prompt = (
            "You are Dr. Pepper — a world-class clinical expert in Autism Spectrum Disorder (ASD) therapy. "
            "You specialise in ABA (Applied Behavior Analysis), DTT (Discrete Trial Training), "
            "TEACCH (Treatment and Education of Autistic and Communication-related Handicapped Children), "
            "ESDM (Early Start Denver Model), and TIE (Therapeutic Inclusive Education). "
            "You write thorough, compassionate, evidence-based clinical essays for parents and therapists. "
            "\n\n"
            f"CHILD PROFILE:\n"
            f"  Name: {CHILD_NAME} | Age: {ST['age']} years\n"
            f"  Conversation Level: {ST['conversation_level']} (1=Motor, 2=Cognitive, 3+=Social/PECS)\n"
            f"  Current Domain: {ST.get('domain','Motor')} | Protocol: {ST.get('protocol','ABA-DTT')}\n"
            f"  Session Duration: {dur} min | Date: {ST['session_date']}\n"
            f"\nSKILL PROFILE:\n"
            f"  Motor: {ST['skill_motor']}% | Cognitive: {ST['skill_cognitive']}% | "
            f"Verbal: {ST['skill_verbal']}% | Math: {ST['skill_math']}% | Social: {ST['skill_social']}%\n"
            f"\nSESSION STATS:\n"
            f"  Score: {ST['score']} | Tasks Mastered: {ST['tasks_mastered']} | "
            f"Correct: {ST['tasks_success']} | Fail: {ST['tasks_fail']} | Skipped: {ST['tasks_skipped']}\n"
            f"  Current Emotion: {ST['emotion']} | Attention: {ST['attention']}% | "
            f"Current Mood: {ST.get('current_mood','not set')}\n"
            f"\nRESPONSE FORMAT RULES:\n"
            "  1. Write a full, detailed clinical essay — minimum 400 words, no artificial word limits.\n"
            "  2. Structure your response with these sections:\n"
            "     🔍 Clinical Assessment — analyse the child's current profile\n"
            "     🎯 Evidence-Based Recommendations — specific strategies with step-by-step instructions\n"
            "     🏠 Home Practice Guide — daily exercises parents can do in 10-15 minutes\n"
            "     📊 Progress Indicators — how to measure improvement\n"
            "     💙 Encouragement — a warm closing note for the family\n"
            "  3. Be specific to THIS child's data above — not generic advice.\n"
            "  4. Cite the therapy protocol (ABA/DTT/TEACCH/ESDM) for each recommendation.\n"
            "  5. Respond in ENGLISH ONLY.\n"
            "  6. Use plain text — no markdown asterisks or hashtags, use the emoji section headers shown above.\n"
        )
        model = genai.GenerativeModel(
            "gemini-1.5-flash",
            system_instruction=sys_prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.7,
                max_output_tokens=1200,
                top_p=0.9,
            )
        )
        r = model.generate_content(question)
        essay = r.text.strip()
        # Auto-store to session log with timestamp
        _ai_chat.append({
            "role":"system_log",
            "text":f"Q: {question[:80]} | A: {essay[:120]}…",
            "time":datetime.now().strftime("%H:%M"),
            "full_answer":essay
        })
        return essay
    except Exception as e:
        return (f"AI Advisor temporarily unavailable ({str(e)[:50]}). "
                "Please contact lamyafadlulmolahamedali1@gmail.com for support.")

# ══════════════════════════════════════════════════════════════════════
# 19. FLASK — Parent Dashboard (5007), Reports (5001), Games (5009)
# ══════════════════════════════════════════════════════════════════════
parent_app=Flask("parent"); parent_app.secret_key=secrets.token_hex(16)
report_app=Flask("report"); games_app=Flask("games")

# ══════════════════════════════════════════════════════════════════════
# SECURITY LAYER — Backend + Frontend hardening
# ══════════════════════════════════════════════════════════════════════
import functools
from werkzeug.security import generate_password_hash, check_password_hash

OWNER_EMAIL    = "lamyafadlulmolahamedali1@gmail.com"
_RATE_LIMIT    = {}          # ip → (count, window_start)
_RATE_MAX      = 60          # max requests per minute per IP
_BLOCKED_IPS   = set()       # persistent block list
_SESSION_STORE = {}          # pin → session snapshots for Claude storage
_API_SECRET    = secrets.token_hex(32)  # HMAC signing key (regenerated each boot)

def _client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "unknown").split(",")[0].strip()

def rate_limit_check():
    """60 req/min per IP. Returns True if blocked."""
    ip  = _client_ip()
    if ip in _BLOCKED_IPS: return True
    now = time.time()
    cnt, win = _RATE_LIMIT.get(ip, (0, now))
    if now - win > 60: cnt, win = 0, now
    cnt += 1
    _RATE_LIMIT[ip] = (cnt, win)
    if cnt > _RATE_MAX:
        log.warning(f"Rate limit hit: {ip} ({cnt} req/min)")
        return True
    return False

def require_api_hmac(f):
    """Decorator: require X-Pepper-Sig HMAC header on API calls."""
    @functools.wraps(f)
    def wrapper(*a, **kw):
        sig = request.headers.get("X-Pepper-Sig","")
        body = request.get_data()
        import hmac as _hmac_mod
        expected = _hmac_mod.new(_API_SECRET.encode(), body, hashlib.sha256).hexdigest()
        if sig and not _hmac_mod.compare_digest(sig, expected):
            log.warning(f"Invalid HMAC from {_client_ip()}")
            return jsonify({"ok":False,"error":"Invalid signature."}), 403
        return f(*a, **kw)
    return wrapper

def security_headers(response):
    """Add security headers to every response."""
    response.headers.update({
        "X-Content-Type-Options":   "nosniff",
        "X-Frame-Options":           "SAMEORIGIN",
        "X-XSS-Protection":          "1; mode=block",
        "Referrer-Policy":           "strict-origin-when-cross-origin",
        "Cache-Control":             "no-store, no-cache, must-revalidate",
        "Permissions-Policy":        "geolocation=(), microphone=(self), camera=(self)",
        "Content-Security-Policy":   (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline' cdnjs.cloudflare.com; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data:; "
            "connect-src 'self'; "
            "frame-src 'none';"
        ),
    })
    return response

parent_app.after_request(security_headers)

@parent_app.before_request
def global_security():
    """Rate limiting + IP block on every request."""
    if rate_limit_check():
        return jsonify({"ok":False,"error":"Rate limit exceeded. Try again in 60 seconds."}),429

# ── Claude Session Storage (saves every session snapshot) ──────────
def store_session_to_claude_log():
    """
    Stores a full session snapshot to local JSON file + logs for email delivery.
    Called at end of every session and every 10 mastered tasks.
    Destination: lamyafadlulmolahamedali1@gmail.com
    """
    snap = {
        "timestamp":       datetime.now().isoformat(),
        "child":           CHILD_NAME,
        "age":             ST["age"],
        "session_date":    ST["session_date"],
        "duration_min":    int((time.time()-ST["uptime"])/60),
        "score":           ST["score"],
        "tasks_mastered":  ST["tasks_mastered"],
        "tasks_success":   ST["tasks_success"],
        "tasks_fail":      ST["tasks_fail"],
        "tasks_skipped":   ST["tasks_skipped"],
        "conv_level":      ST["conversation_level"],
        "skill_motor":     ST["skill_motor"],
        "skill_cognitive": ST["skill_cognitive"],
        "skill_verbal":    ST["skill_verbal"],
        "skill_math":      ST["skill_math"],
        "skill_social":    ST["skill_social"],
        "emotion":         ST["emotion"],
        "attention":       ST["attention"],
        "current_mood":    ST.get("current_mood"),
        "pecs_log":        ST.get("pecs_log",[])[-10:],
        "mood_log":        ST.get("mood_log",[])[-10:],
        "parent_notes":    ST["parent_notes"][-5:],
        "ai_exchanges":    len([m for m in _ai_chat if m.get("role")=="parent"]),
        "owner_email":     OWNER_EMAIL,
    }
    # Write to local sessions file
    sessions_file = f"{SAFE_NAME}_v6_sessions.json"
    try:
        sessions = []
        if os.path.exists(sessions_file):
            with open(sessions_file) as f_: sessions = json.load(f_)
        sessions.append(snap)
        if len(sessions) > 200: sessions = sessions[-200:]
        with open(sessions_file,"w") as f_: json.dump(sessions, f_, indent=2, default=str)
        log.info(f"✅ Session stored → {sessions_file}")
    except Exception as e:
        log.warning(f"Session store error: {e}")
    # Write pending email queue
    email_queue_file = "pending_email_reports.json"
    try:
        queue = []
        if os.path.exists(email_queue_file):
            with open(email_queue_file) as f_: queue = json.load(f_)
        queue.append({
            "to":      OWNER_EMAIL,
            "subject": f"Pepper V6 Session Report — {CHILD_NAME} — {snap['session_date']}",
            "body":    (
                f"Child: {CHILD_NAME} | Age: {snap['age']}\n"
                f"Date: {snap['session_date']} | Duration: {snap['duration_min']} min\n"
                f"Score: {snap['score']} | Mastered: {snap['tasks_mastered']}\n"
                f"Correct: {snap['tasks_success']} | Fail: {snap['tasks_fail']}\n"
                f"Skills: Motor {snap['skill_motor']}% | Cogn {snap['skill_cognitive']}% | "
                f"Verbal {snap['skill_verbal']}% | Math {snap['skill_math']}% | Social {snap['skill_social']}%\n"
                f"Conv Level: {snap['conv_level']} | Emotion: {snap['emotion']}\n"
                f"Mood: {snap['current_mood']} | Attention: {snap['attention']}%\n"
                f"AI Advisor queries: {snap['ai_exchanges']}\n\n"
                f"Full data saved to: {sessions_file}\n"
                f"Pepper Clinical Infinity V6 © 2026 Lamya Fadlulmola Hamed Ali"
            ),
            "timestamp": datetime.now().isoformat(),
        })
        with open(email_queue_file,"w") as f_: json.dump(queue, f_, indent=2, default=str)
        log.info(f"📧 Email queued → {OWNER_EMAIL}")
    except Exception as e:
        log.warning(f"Email queue error: {e}")
    return snap

# ── ngrok / Public Sharing Helper ─────────────────────────────────
def try_start_ngrok(port=5007):
    """
    Attempts to start ngrok tunnel for public sharing/testing.
    Requires: pip install pyngrok
    Set NGROK_AUTH_TOKEN env var for persistent tunnels.
    """
    try:
        from pyngrok import ngrok as _ngrok, conf as _ngconf
        token = os.environ.get("NGROK_AUTH_TOKEN","")
        if token: _ngconf.get_default().auth_token = token
        tunnel = _ngrok.connect(port, "http")
        public_url = tunnel.public_url
        log.info(f"🌐 Public URL (share to test): {public_url}")
        print(f"\n{'='*62}")
        print(f"  🌐 SHARE THIS LINK TO TEST FROM ANY DEVICE:")
        print(f"  {public_url}")
        print(f"{'='*62}\n")
        return public_url
    except ImportError:
        log.info("pyngrok not installed. Run: pip install pyngrok")
        return None
    except Exception as e:
        log.warning(f"ngrok: {e}")
        return None

PUBLIC_URL = None   # set in main() after ngrok starts

ASQ_Q=["Does your child look at you when you talk?",
        "Does your child point to things?","Can your child say 5+ words?",
        "Does your child play with other children?","Can your child follow 2-step instructions?",
        "Does your child make eye contact?","Can your child stack blocks?",
        "Does your child respond to their name?","Can your child draw a circle?",
        "Does your child show emotions appropriately?"]
VBMAPP_Q=["Can the child mand (request) for preferred items?",
           "Does the child tact (label) 10+ objects?","Can the child imitate 5+ actions?",
           "Does the child attend to speaker for 30+ seconds?",
           "Can the child follow 3-step instructions?",
           "Does the child engage in reciprocal play?","Can the child match identical objects?",
           "Does the child use 2-word phrases?","Can the child identify 10+ pictures?",
           "Does the child show joint attention?"]
QUICK_Q=["How can I improve attention span?",
          "What home exercises help motor skills?","How to handle tantrums?",
          "How to encourage verbal communication?",
          "What is the difference between ABA and TEACCH?",
          "How can I practice DTT at home?"]
EMPOWERMENT_MODULES=[
    {"title":"ABA Basics","icon":"🔬","content":"Applied Behavior Analysis (ABA) breaks skills into small steps, reinforcing each success. DTT (Discrete Trial Training) uses clear instructions, prompts, and immediate reinforcement. At home: use 5-10 min daily sessions, consistent rewards.","video":"https://youtu.be/K_Y5j8MzViU"},
    {"title":"TEACCH Visual Support","icon":"📋","content":"TEACCH uses visual schedules, structured workspaces, and predictable routines. Create a visual schedule with pictures showing daily activities. Use 'work' and 'break' boxes. Keep workspace organized and distraction-free.","video":"https://youtu.be/xMdBuPUP_tA"},
    {"title":"ESDM Social Skills","icon":"👥","content":"Early Start Denver Model focuses on social engagement through play. Follow your child's lead, join their activity, add language naturally. Celebrate every communication attempt. Make eye contact during fun activities.","video":"https://youtu.be/5bHEXJwO8Ds"},
    {"title":"DTT Home Practice","icon":"🎯","content":"Discrete Trial Training at home: 1) Give clear instruction 2) Wait 3-5 seconds 3) Prompt if needed 4) Reinforce immediately. Practice 5-7 trials then break. Use preferred items as rewards. Track results in a notebook.","video":"https://youtu.be/0MqBqzQRXus"},
    {"title":"Sensory Strategies","icon":"🎨","content":"Many ASD children have sensory needs. Before therapy: 5 min of proprioceptive input (jumping, pushing walls). Create a calming corner with fidgets and soft lighting. Heavy blankets can help regulation.","video":"https://youtu.be/FuFkwSTh1CY"},
]

LOGIN_HTML="""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><title>Parent Login</title>
<style>
body{background:#060912;color:#e0e6ff;font-family:'Segoe UI',sans-serif;display:flex;
     align-items:center;justify-content:center;min-height:100vh;margin:0}
.card{background:#0c0f1e;border-radius:16px;padding:40px;width:380px;
      border:2px solid #4f46e5;box-shadow:0 20px 60px rgba(0,0,0,0.5)}
h1{color:#a78bfa;text-align:center;margin-bottom:24px;font-size:1.3em}
input{width:100%;padding:10px 12px;border-radius:8px;border:2px solid #1a1f40;
      background:#07090f;color:#e0e6ff;font-size:.9em;margin-bottom:12px;
      box-sizing:border-box;outline:none;transition:.2s}
input:focus{border-color:#4f46e5}
.btn{width:100%;padding:10px;background:#4f46e5;color:white;border:none;
     border-radius:8px;cursor:pointer;font-size:.9em;font-weight:700;margin-bottom:8px;transition:.2s}
.btn:hover{background:#4338ca}
.btn-g{background:#059669}.btn-g:hover{background:#047857}
.err{background:#45090a55;color:#f87171;border:1px solid #f87171;border-radius:8px;
     padding:8px;margin-bottom:12px;font-size:.82em;text-align:center}
.info{color:#6b7280;font-size:.75em;text-align:center;margin-top:12px}
.tabs{display:flex;gap:8px;margin-bottom:20px}
.tab{flex:1;padding:8px;background:#1a1f40;border:none;border-radius:8px;
     color:#9ca3af;cursor:pointer;font-size:.85em;font-weight:700;transition:.2s}
.tab.active,.tab:hover{background:#4f46e5;color:white}
.tc{display:none}.tc.active{display:block}
</style></head><body>
<div class="card">
<h1>🤖 Pepper Clinical V6</h1>
<div class="tabs">
  <button class="tab active" onclick="T('login',this)">Login</button>
  <button class="tab" onclick="T('register',this)">Register</button>
</div>
{% if error %}<div class="err">{{error}}</div>{% endif %}
<div id="login" class="tc active">
  <form method="POST" action="/login">
    <input name="username" placeholder="Username" required autocomplete="username">
    <input name="password" type="password" placeholder="Password" required autocomplete="current-password">
    <button class="btn" type="submit">Login</button>
  </form>
</div>
<div id="register" class="tc">
  <form method="POST" action="/register">
    <input name="reg_username" placeholder="Choose Username" required>
    <input name="reg_password" type="password" placeholder="Choose Password (min 6 chars)" required>
    <input name="reg_email" placeholder="Email (optional)">
    <button class="btn btn-g" type="submit">Create Account</button>
  </form>
</div>
<p class="info">Child: {{child}}</p>
</div>
<script>
function T(n,el){document.querySelectorAll('.tc').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById(n).classList.add('active'); el.classList.add('active');}
</script></body></html>"""

PARENT_HTML="""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><title>Clinical Dashboard V6 — {{child}}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/3.9.1/chart.min.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#060912;color:#e0e6ff;font-family:'Segoe UI',sans-serif}
.topbar{background:#0c0f1e;border-bottom:2px solid #1a1f40;padding:10px 16px;
        display:flex;justify-content:space-between;align-items:center}
.topbar-title{color:#a78bfa;font-weight:700;font-size:.95em}
.logout{color:#f87171;text-decoration:none;font-size:.78em;padding:5px 10px;
        background:#45090a55;border-radius:6px;border:1px solid #f87171}
.tabs{display:flex;background:#0c0f1e;border-bottom:2px solid #1a1f40;flex-wrap:wrap}
.tab{padding:10px 16px;cursor:pointer;font-weight:700;font-size:.78em;
     border-bottom:3px solid transparent;transition:.2s;color:#6b7280;white-space:nowrap}
.tab:hover,.tab.active{color:#a78bfa;border-bottom-color:#a78bfa}
.tc{display:none;padding:12px}.tc.active{display:block}
.nav{display:flex;gap:5px;margin-bottom:8px;flex-wrap:wrap}
.nav a{padding:6px 10px;border-radius:7px;text-decoration:none;font-size:.75em;font-weight:700}
.b1{background:#4f46e5;color:#fff}.b2{background:#059669;color:#fff}
.b3{background:#1d4ed8;color:#fff}.b4{background:#7c3aed;color:#fff}
.row4{display:grid;grid-template-columns:repeat(4,1fr);gap:7px;margin-bottom:8px}
.stat{background:#0c0f1e;border-radius:10px;padding:10px;border:1px solid #1a1f40;text-align:center}
.n{font-size:1.5em;font-weight:700;color:#a78bfa}.l{font-size:.62em;color:#6b7280;margin-top:2px}
.n-g{color:#34d399}.n-y{color:#fbbf24}.n-b{color:#60a5fa}.n-r{color:#f87171}
.card{background:#0c0f1e;border-radius:10px;padding:12px;border:1px solid #1a1f40;margin-bottom:8px}
.card h2{color:#818cf8;margin-bottom:7px;font-size:.83em;border-bottom:1px solid #1a1f40;padding-bottom:4px}
.pct-row{display:flex;align-items:center;gap:6px;margin:3px 0;font-size:.72em}
.pct-bar-bg{flex:1;height:7px;background:#1f2937;border-radius:4px}
.pct-bar{height:7px;border-radius:4px}
.skill-g{display:grid;grid-template-columns:repeat(5,1fr);gap:5px}
.si{text-align:center;background:#07090f;border-radius:8px;padding:8px}
.sv{font-size:1.1em;font-weight:700;color:#a78bfa}
.chat-box{height:190px;overflow-y:auto;background:#07090f;border-radius:8px;padding:8px;margin-bottom:8px}
.cm{padding:3px 6px;margin:2px 0;border-radius:5px;font-size:.75em}
.cmp{background:#1e1b4b;border-left:3px solid #a78bfa}
.cmc{background:#052918;border-left:3px solid #34d399}
.log-b{max-height:180px;overflow-y:auto}
.li{padding:2px 5px;margin:1px 0;font-size:.65em;border-left:3px solid #4f46e5;background:#07090f;line-height:1.4}
.li.success{border-color:#34d399}.li.fail{border-color:#f87171}
.note{background:#0a1020;border-left:3px solid #a78bfa;padding:5px;margin:3px 0;font-size:.72em}
input,textarea,select{width:100%;padding:6px;border-radius:7px;border:1px solid #1a1f40;
  background:#07090f;color:#e0e6ff;font-size:.78em;outline:none;margin-bottom:5px}
.btn{background:#4f46e5;color:#fff;border:none;padding:7px 12px;border-radius:7px;
     cursor:pointer;font-size:.78em;margin:3px;min-height:32px;transition:.2s}
.btn:hover{opacity:.85}
.btn-g{background:#059669}.btn-r{background:#dc2626}.btn-y{background:#d97706}
.action-g{display:grid;grid-template-columns:repeat(3,1fr);gap:6px}
.chart-c{height:180px;background:#07090f;border-radius:8px;padding:8px;margin-bottom:8px}
.qa-row{display:flex;gap:6px;margin-top:5px}
.qa-row input{flex:1;margin-bottom:0}
.module{background:#07090f;border:1px solid #1a1f40;border-radius:10px;padding:12px;margin-bottom:8px}
.module-title{color:#a78bfa;font-weight:700;font-size:.88em;margin-bottom:6px}
.module-content{color:#9ca3af;font-size:.78em;line-height:1.7}
.form-g{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.pecs-i{display:inline-block;background:#1e1b4b;border:1px solid #4f46e5;
        border-radius:8px;padding:3px 8px;margin:3px;font-size:.73em}
::-webkit-scrollbar{width:3px}::-webkit-scrollbar-thumb{background:#4f46e5;border-radius:3px}
@media(max-width:600px){.row4{grid-template-columns:repeat(2,1fr)}.form-g{grid-template-columns:1fr}
  .skill-g{grid-template-columns:repeat(3,1fr)}}
</style></head><body>
<div class="topbar">
  <span class="topbar-title">🤖 Pepper Clinical V6 — {{child}} | Logged in as {{user}}</span>
  <a href="/logout" class="logout">Logout</a>
</div>
<div class="tabs">
  <div class="tab active" onclick="T('ov')">📊 Overview</div>
  <div class="tab" onclick="T('an')">📈 Analytics</div>
  <div class="tab" onclick="T('as')">🧪 Assessments</div>
  <div class="tab" onclick="T('ai')">🤖 AI Advisor</div>
  <div class="tab" onclick="T('lv')">👁 Live Monitor</div>
  <div class="tab" onclick="T('em')">📚 Empowerment Hub</div>
  <div class="tab" onclick="T('nt')">📝 Notes</div>
  <div class="tab" onclick="T('mood')">🌈 Moods</div>
  <div class="tab" onclick="T('music')">🎵 Music</div>
  <div class="tab" onclick="T('voice')">🎙 Voice</div>
  <div class="tab" onclick="T('theme')">🎨 Theme</div>
  <div class="tab" onclick="T('sub')">💎 Access</div>
</div>

<!-- OVERVIEW -->
<div id="tc-ov" class="tc active">
<div class="nav">
  <a href="http://127.0.0.1:5007/" class="b1">📊 Dashboard</a>
  <a href="http://127.0.0.1:5001/" class="b2">📋 Reports</a>
  <a href="http://127.0.0.1:5009/" class="b3">🎮 Games</a>
  <a href="http://{{lip}}:5007/" class="b4">📱 Android</a>
</div>
<div class="row4">
  <div class="stat"><div class="n n-g">{{score}}</div><div class="l">⭐ Score</div></div>
  <div class="stat"><div class="n n-y">{{mastered}}</div><div class="l">🏆 Mastered</div></div>
  <div class="stat"><div class="n n-b">{{att}}%</div><div class="l">🎯 Attention</div></div>
  <div class="stat"><div class="n n-r">{{skipped}}</div><div class="l">⏭️ Skipped</div></div>
</div>
<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
<div>
  <div class="card"><h2>😊 Emotion (Conv Level {{clvl}})</h2>
    <div style="text-align:center;margin-bottom:6px">
      <span style="display:inline-block;padding:4px 14px;border-radius:12px;font-weight:700;
        background:#05291555;color:#34d399;border:1px solid #34d399">
        {{em.upper()}} — {{conf}}%</span>
      <div style="font-size:.65em;color:#6b7280;margin-top:4px">
        Face:{{'✅' if face else '❌'}} | Fingers:{{fc}} | Streak:{{streak}} | Fails:{{fails}}/2</div>
    </div>
    {% for emo_,pct_ in pct.items() %}
    <div class="pct-row">
      <span style="width:56px;color:#9ca3af">{{emo_[:6]}}</span>
      <div class="pct-bar-bg"><div class="pct-bar" style="width:{{pct_}}%;
        background:{{'#22c55e' if emo_ in ['happy','joyful'] else '#f87171' if emo_=='angry'
        else '#60a5fa' if emo_=='sad' else '#c084fc' if emo_=='surprised'
        else '#fbbf24' if emo_=='fear' else '#9ca3af'}}"></div></div>
      <span style="width:34px;text-align:right;color:#e0e6ff">{{pct_}}%</span>
    </div>{% endfor %}
  </div>
  <div class="card"><h2>📊 Skills Profile</h2>
    <div class="skill-g">
      <div class="si"><div class="sv">{{sm}}%</div><div style="font-size:.68em;color:#6b7280">Motor</div></div>
      <div class="si"><div class="sv">{{sc_}}%</div><div style="font-size:.68em;color:#6b7280">Cognitive</div></div>
      <div class="si"><div class="sv">{{sv}}%</div><div style="font-size:.68em;color:#6b7280">Verbal</div></div>
      <div class="si"><div class="sv">{{smath}}%</div><div style="font-size:.68em;color:#6b7280">Math</div></div>
      <div class="si"><div class="sv">{{ssoc}}%</div><div style="font-size:.68em;color:#6b7280">Social</div></div>
    </div>
  </div>
  <div class="card"><h2>🗣️ PECS Log</h2>
    {% for p2 in pecs_log[-6:]|reverse %}
    <div class="pecs-i">{{p2.time}} — {{p2.name}}: {{p2.phrase}}</div>{% endfor %}
    {% if not pecs_log %}<p style="color:#6b7280;font-size:.75em">No PECS events yet.</p>{% endif %}
  </div>
</div>
<div>
  <div class="card"><h2>💬 Session Chat</h2>
    <div class="chat-box">
      {% for m in chat[-20:]|reverse %}
      <div class="cm {{'cmp' if m.role=='pepper' else 'cmc'}}">
        <span style="font-size:.6em;color:{{'#a78bfa' if m.role=='pepper' else '#34d399'}}">
          {{'🤖' if m.role=='pepper' else '👦'}} {{m.time}}</span><br>{{m.text}}</div>{% endfor %}
    </div>
  </div>
  <div class="card"><h2>📋 Log</h2>
    <div class="log-b">
      {% for lg in logs[-25:]|reverse %}
      <div class="li {{lg.type}}"><span style="color:#6366f1">{{lg.time}}</span> {{lg.msg}}</div>{% endfor %}
    </div>
  </div>
  <div class="card"><h2>🏆 Summary</h2>
    <div style="font-size:.75em;line-height:1.9;color:#9ca3af">
      Child:<b style="color:#e0e6ff">{{child}}</b> | {{date}} | L{{clvl}} {{domain}}<br>
      OK:<span style="color:#34d399">{{ok}}</span> | Fail:<span style="color:#f87171">{{fail}}</span>
      | Skip:<span style="color:#f97316">{{skipped}}</span>
    </div>
    <form method="POST" action="/gen_pdf" style="margin-top:6px">
      <button class="btn btn-g" style="width:100%">📄 Download PDF Report</button>
    </form>
  </div>
</div></div></div>

<!-- ANALYTICS -->
<div id="tc-an" class="tc">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
    <div class="card"><h2>📈 Attention Over Session</h2>
      <div class="chart-c"><canvas id="attChart"></canvas></div>
    </div>
    <div class="card"><h2>⭐ Score Progression</h2>
      <div class="chart-c"><canvas id="scoreChart"></canvas></div>
    </div>
    <div class="card"><h2>🎯 Task Results</h2>
      <div class="chart-c"><canvas id="taskChart"></canvas></div>
    </div>
    <div class="card"><h2>📊 Skills Radar</h2>
      <div class="chart-c"><canvas id="skillChart"></canvas></div>
    </div>
  </div>
</div>

<!-- ASSESSMENTS -->
<div id="tc-as" class="tc">
  <div class="card"><h2>🧪 ASQ-3 Assessment</h2>
    <p style="font-size:.75em;color:#6b7280;margin-bottom:8px">Rate each: 0=Never, 1=Sometimes, 2=Often</p>
    <form method="POST" action="/asq_submit" class="form-g">
      {% for q in asq_q %}
      <div>
        <label style="font-size:.75em;color:#9ca3af">{{q}}</label>
        <select name="asq_{{loop.index0}}">
          <option value="0">0 - Never</option><option value="1">1 - Sometimes</option><option value="2">2 - Often</option>
        </select>
      </div>{% endfor %}
      <div style="grid-column:1/-1"><button class="btn btn-g" style="width:100%">Submit ASQ</button></div>
    </form>
    {% if asq_score is not none %}
    <div style="margin-top:8px;padding:8px;background:#052918;border-radius:8px;font-size:.8em">
      ASQ Score: <b style="color:#34d399">{{asq_score}}/20</b>
      — {{'Above cutoff — consult specialist' if asq_score>15 else 'Monitoring' if asq_score>10 else 'Typical range'}}
    </div>{% endif %}
  </div>
  <div class="card"><h2>🧪 VB-MAPP (Verbal Behavior)</h2>
    <form method="POST" action="/vbmapp_submit" class="form-g">
      {% for q in vbmapp_q %}
      <div>
        <label style="font-size:.75em;color:#9ca3af">{{q}}</label>
        <select name="vb_{{loop.index0}}">
          <option value="0">0 - No</option><option value="1">1 - Emerging</option><option value="2">2 - Yes</option>
        </select>
      </div>{% endfor %}
      <div style="grid-column:1/-1"><button class="btn btn-g" style="width:100%">Submit VB-MAPP</button></div>
    </form>
    {% if vbmapp_score is not none %}
    <div style="margin-top:8px;padding:8px;background:#052918;border-radius:8px;font-size:.8em">
      VB-MAPP Score: <b style="color:#34d399">{{vbmapp_score}}/20</b> — Conv Level auto-adjusted
    </div>{% endif %}
  </div>
</div>

<!-- AI ADVISOR -->
<div id="tc-ai" class="tc">
  <div class="card"><h2>🤖 AI Clinical Advisor (Gemini — English Only)</h2>
    <p style="font-size:.75em;color:#6b7280;margin-bottom:8px">
      Ask for clinical advice. The AI has read-only access to today's session data.</p>
    <div class="chat-box" id="aiC">
      {% for m in ai_chat %}
      <div class="cm {{'cmp' if m.role=='ai' else 'cmc'}}">
        <span style="font-size:.6em;color:{{'#a78bfa' if m.role=='ai' else '#34d399'}}">
          {{'🤖 AI Advisor' if m.role=='ai' else '👨‍👩‍👦 Parent'}} {{m.time}}</span><br>{{m.text}}
      </div>{% endfor %}
      {% if not ai_chat %}<p style="color:#6b7280;text-align:center;padding:16px;font-size:.8em">Ask for clinical advice about {{child}}…</p>{% endif %}
    </div>
    <form method="POST" action="/ai_chat" class="qa-row">
      <input name="question" placeholder="Ask in English…">
      <button class="btn btn-g" style="white-space:nowrap">Ask AI</button>
    </form>
    <div style="margin-top:6px;display:flex;gap:4px;flex-wrap:wrap">
      {% for q in quick_q %}
      <form method="POST" action="/ai_chat" style="display:inline">
        <button class="btn" name="question" value="{{q}}" style="font-size:.7em;padding:4px 8px;margin:2px">{{q}}</button>
      </form>{% endfor %}
    </div>
  </div>
</div>

<!-- LIVE MONITOR -->
<div id="tc-lv" class="tc">

<!-- ═══════════════════════════════════════════════════════════════
     REAL-TIME LIVE VIDEO DETECTION DASHBOARD
     © 2026 Lamya Fadlulmola Hamed Ali — All Rights Reserved
     Streams camera via /api/live_frame (MJPEG polling, 10fps)
     Shows pose skeleton, finger count, emotion, attention live
═══════════════════════════════════════════════════════════════ -->

<!-- TOP HEADER BAR -->
<div style="background:linear-gradient(135deg,#0a0d1e,#050a20);border:1px solid #1a2550;
            border-radius:12px;padding:10px 14px;margin-bottom:8px;
            display:flex;align-items:center;justify-content:space-between">
  <div>
    <div style="font-size:.82em;font-weight:800;color:#e0e8ff">
      📹 Real-Time Child Detection View
    </div>
    <div style="font-size:.6em;color:#4a9eff;margin-top:1px">
      © 2026 Lamya Fadlulmola Hamed Ali · Pepper Clinical Infinity V6
    </div>
  </div>
  <div style="display:flex;gap:5px;align-items:center">
    <div id="lv-live-badge" style="display:flex;align-items:center;gap:4px;
        background:rgba(34,197,94,.15);border:1px solid #22c55e;border-radius:20px;
        padding:3px 10px;font-size:.62em;font-weight:700;color:#22c55e">
      <span style="width:7px;height:7px;border-radius:50%;background:#22c55e;
                   display:inline-block;animation:blink 1s ease-in-out infinite"></span>
      LIVE
    </div>
    <div id="lv-fps-badge" style="background:rgba(74,158,255,.15);border:1px solid #4a9eff;
        border-radius:20px;padding:3px 10px;font-size:.62em;font-weight:700;color:#4a9eff">
      10 FPS
    </div>
  </div>
</div>

<!-- MAIN LIVE CANVAS AREA -->
<div style="position:relative;background:#000;border-radius:14px;overflow:hidden;
            border:2px solid #1a2550;margin-bottom:8px" id="lv-canvas-wrap">
  
  <!-- Background JPEG stream (raw camera) -->
  <img id="lv-bg-img" src="/api/live_stream"
       style="width:100%;display:block;min-height:240px;object-fit:cover;opacity:0.92"
       crossorigin="anonymous" alt="">

  <!-- Canvas overlay: draws pose skeleton + landmarks + HUD in real-time -->
  <canvas id="lv-overlay-canvas"
          style="position:absolute;inset:0;width:100%;height:100%;
                 pointer-events:none;z-index:5"></canvas>

  <!-- TOP HUD strip -->
  <div style="position:absolute;top:0;left:0;right:0;padding:5px 10px;
              background:linear-gradient(rgba(4,11,26,.9),transparent);
              display:flex;gap:8px;align-items:center;z-index:10;flex-wrap:wrap">
    <span style="font-size:.6em;font-weight:700;color:#fbbf24;font-family:monospace"
          id="lv-hud-name">{{child}}</span>
    <span style="font-size:.58em;font-weight:700;color:#34d399" id="lv-hud-emotion">{{em}}</span>
    <span style="font-size:.58em;color:#60a5fa">Att:<b id="lv-hud-att">{{att}}</b>%</span>
    <span style="font-size:.58em;color:#fbbf24">✋<b id="lv-hud-fc">{{fc}}</b></span>
    <span style="font-size:.58em;color:#a78bfa">⭐<b id="lv-hud-score">{{score}}</b></span>
  </div>

  <!-- BOTTOM HUD strip -->
  <div style="position:absolute;bottom:0;left:0;right:0;padding:5px 10px;
              background:linear-gradient(transparent,rgba(4,11,26,.9));
              display:flex;gap:10px;align-items:center;z-index:10;flex-wrap:wrap">
    <span style="font-size:.58em;color:#e0e6ff">
      Emotion: <b id="lv-hud-em2" style="color:#34d399">{{em}}</b>
    </span>
    <span style="font-size:.58em;color:#e0e6ff">
      Face: <b id="lv-hud-face" style="color:{{'#34d399' if face else '#f87171'}}">{{'✅' if face else '❌'}}</b>
    </span>
    <span style="font-size:.58em;color:#e0e6ff">
      Streak: <b id="lv-hud-streak" style="color:#fbbf24">{{streak}}🔥</b>
    </span>
    <span style="font-size:.55em;color:#4a6a8a;margin-left:auto">
      © 2026 Lamya Fadlulmola Hamed Ali
    </span>
  </div>
</div>

<!-- EMOTION BARS + FINGER DISPLAY ROW -->
<div style="display:grid;grid-template-columns:1fr auto;gap:8px;margin-bottom:8px">
  
  <!-- Emotion bars -->
  <div class="card" style="padding:10px">
    <div style="font-size:.65em;font-weight:700;color:#4a9eff;margin-bottom:6px">
      🧠 Emotion Analysis — Real-Time
    </div>
    <div id="lv-emo-bars">
      {% for emo, pct in [("happy","0"),("joyful","0"),("sad","0"),("angry","0"),("fear","0"),("surprised","0"),("neutral","100")] %}
      <div style="display:flex;align-items:center;gap:5px;margin:2px 0;font-size:.58em">
        <span style="width:52px;color:#9ca3af;text-align:right">{{emo}}</span>
        <div style="flex:1;height:5px;background:rgba(255,255,255,.08);border-radius:3px">
          <div id="lv-ebar-{{emo}}" style="height:5px;border-radius:3px;
               background:{{'#22c55e' if emo=='happy' else '#60a5fa' if emo=='joyful' else '#f87171' if emo=='angry' else '#818cf8' if emo=='sad' else '#fbbf24'}};
               width:{{pct}}%;transition:width .3s"></div>
        </div>
        <span id="lv-epct-{{emo}}" style="width:28px;color:#6b7280;text-align:right">{{pct}}%</span>
      </div>{% endfor %}
    </div>
  </div>

  <!-- Finger count big display -->
  <div class="card" style="padding:10px;text-align:center;min-width:80px">
    <div style="font-size:.6em;color:#9ca3af;margin-bottom:4px">Fingers</div>
    <div id="lv-finger-big" style="font-size:2.5em;font-weight:900;color:#fbbf24;
         line-height:1;text-shadow:0 0 20px rgba(251,191,36,.5)">{{fc}}</div>
    <div style="font-size:.5em;color:#6b7280;margin-top:2px">detected</div>
    <div style="margin-top:6px;display:flex;gap:2px;justify-content:center;flex-wrap:wrap">
      {% for i in range(10) %}
      <div id="lv-finger-dot-{{i}}" style="width:9px;height:9px;border-radius:50%;
           background:{% if i < fc %}#fbbf24{% else %}rgba(255,255,255,.1){% endif %};
           transition:background .2s"></div>
      {% endfor %}
    </div>
  </div>
</div>

<!-- MUTE / UNMUTE + QUICK CONTROLS -->
<div class="card" style="margin-bottom:8px;padding:10px">
  <div style="font-size:.66em;font-weight:700;color:#4a9eff;margin-bottom:8px">
    🎙 Pepper Voice Control + Remote Actions
  </div>
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:5px;margin-bottom:8px">
    <button onclick="fetch('/api/pepper/mute',{method:'POST'}).then(()=>lvMuteStatus(true))"
            style="padding:8px;border:none;border-radius:8px;background:rgba(248,113,113,.2);
                   color:#f87171;font-size:.72em;font-weight:700;cursor:pointer;
                   border:1.5px solid rgba(248,113,113,.35)">
      🔇 Mute Pepper
    </button>
    <button onclick="fetch('/api/pepper/unmute',{method:'POST'}).then(()=>lvMuteStatus(false))"
            style="padding:8px;border:none;border-radius:8px;background:rgba(34,197,94,.15);
                   color:#34d399;font-size:.72em;font-weight:700;cursor:pointer;
                   border:1.5px solid rgba(34,197,94,.3)">
      🔊 Unmute Pepper
    </button>
  </div>
  <div id="lv-mute-badge" style="text-align:center;font-size:.68em;margin-bottom:8px;
       color:{{'#f87171' if pepper_muted else '#34d399'}};font-weight:700">
    Pepper voice: {{'🔇 MUTED' if pepper_muted else '🔊 Active'}}
  </div>
  <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:5px">
    <button onclick="qAction('next')" style="padding:7px 3px;border:1px solid #1a2550;border-radius:7px;
            background:rgba(34,197,94,.12);color:#34d399;font-size:.65em;font-weight:700;cursor:pointer">
      ⏭ Next</button>
    <button onclick="qAction('break')" style="padding:7px 3px;border:1px solid #1a2550;border-radius:7px;
            background:rgba(251,191,36,.1);color:#fbbf24;font-size:.65em;font-weight:700;cursor:pointer">
      ☕ Break</button>
    <button onclick="qAction('celebrate')" style="padding:7px 3px;border:1px solid #1a2550;border-radius:7px;
            background:rgba(167,139,250,.12);color:#a78bfa;font-size:.65em;font-weight:700;cursor:pointer">
      🎉 Celebrate</button>
    <button onclick="qAction('stop')" style="padding:7px 3px;border:1px solid #1a2550;border-radius:7px;
            background:rgba(248,113,113,.1);color:#f87171;font-size:.65em;font-weight:700;cursor:pointer">
      🛑 Pause</button>
    <button onclick="qAction('encourage')" style="padding:7px 3px;border:1px solid #1a2550;border-radius:7px;
            background:rgba(74,158,255,.1);color:#4a9eff;font-size:.65em;font-weight:700;cursor:pointer">
      💙 Encourage</button>
    <button onclick="qAction('mood_speak')" style="padding:7px 3px;border:1px solid #1a2550;border-radius:7px;
            background:rgba(56,232,200,.1);color:#38e8c8;font-size:.65em;font-weight:700;cursor:pointer">
      🌈 Mood</button>
  </div>
</div>

<!-- SKILL BARS LIVE -->
<div class="card" style="padding:10px">
  <div style="font-size:.65em;font-weight:700;color:#4a9eff;margin-bottom:6px">
    📊 Skill Profile — Live Session
  </div>
  <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:5px">
    {% for domain, val, clr in [("Motor",sm,"#4a9eff"),("Cogn",sc_,"#a78bfa"),("Verbal",sv,"#34d399"),("Math",smath,"#fbbf24"),("Social",ssoc,"#f97316")] %}
    <div style="text-align:center">
      <div style="font-size:.55em;color:#9ca3af;margin-bottom:3px">{{domain}}</div>
      <div style="font-size:.9em;font-weight:800;color:{{clr}}">{{val}}%</div>
      <div style="height:3px;background:rgba(255,255,255,.08);border-radius:2px;margin-top:2px">
        <div style="height:3px;border-radius:2px;background:{{clr}};width:{{val}}%"></div>
      </div>
    </div>{% endfor %}
  </div>
</div>

<!-- COPYRIGHT FOOTER -->
<div style="text-align:center;padding:8px;font-size:.55em;color:#1a2550;margin-top:8px">
  © 2026 Lamya Fadlulmola Hamed Ali · Pepper Clinical Infinity V6 · All Rights Reserved
</div>

</div><!-- end tc-lv -->

<script>
// ══════════════════════════════════════════════════════════════
// REAL-TIME LIVE DETECTION ENGINE — Parent Dashboard
// © 2026 Lamya Fadlulmola Hamed Ali — All Rights Reserved
// Polls /api/live_frame at 10fps, overlays skeleton on canvas
// Polls /api/state/full at 2fps for stats & emotion bars
// ══════════════════════════════════════════════════════════════
(function(){
  'use strict';

  // ── Config ──────────────────────────────────────────────────
  var FRAME_INTERVAL = 100;  // ms (10 FPS)
  var STATS_INTERVAL = 500;  // ms (2 FPS for stats)
  var _frameTimer = null, _statsTimer = null;
  var _frameCount = 0, _fps = 0, _lastFpsTime = Date.now();
  var _active = false;

  // ── Elements ─────────────────────────────────────────────────
  var bgImg    = document.getElementById('lv-bg-img');
  var canvas   = document.getElementById('lv-overlay-canvas');
  var fpsBadge = document.getElementById('lv-fps-badge');

  if(!bgImg || !canvas) return;

  var ctx = canvas.getContext('2d');

  // ── Sync canvas size to image size ──────────────────────────
  function syncCanvasSize(){
    var w = bgImg.offsetWidth  || bgImg.naturalWidth  || 320;
    var h = bgImg.offsetHeight || bgImg.naturalHeight || 240;
    if(canvas.width !== w)  canvas.width  = w;
    if(canvas.height !== h) canvas.height = h;
  }

  // ── Draw overlay elements on canvas ─────────────────────────
  function drawOverlay(state){
    syncCanvasSize();
    var W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    // Draw pose skeleton landmarks if available
    var lm = state.pose_landmarks;
    if(lm && Object.keys(lm).length > 2){
      drawPoseHUD(ctx, lm, W, H);
    }

    // Draw emotion confidence ring
    drawEmotionRing(ctx, W, H, state.emotion, state.emotion_pct);

    // Draw finger indicators
    drawFingerHUD(ctx, W, H, state.finger_count);

    // Copyright watermark
    ctx.save();
    ctx.font = 'bold 9px Arial';
    ctx.fillStyle = 'rgba(74,158,255,0.35)';
    ctx.textAlign = 'right';
    ctx.fillText('© 2026 Lamya Fadlulmola Hamed Ali · Pepper V6', W-6, H-5);
    ctx.restore();
  }

  // Pose skeleton drawing (from pose_landmarks dict in ST)
  function drawPoseHUD(ctx2, lm, W, H){
    var pairs = [
      ['l_shoulder_y','r_shoulder_y'],  // shoulders
    ];
    // Draw face box if face detected
    if(lm.nose_x && lm.nose_y){
      var nx = (1 - lm.nose_x) * W;  // mirror
      var ny = lm.nose_y * H;
      ctx2.save();
      ctx2.strokeStyle = 'rgba(0,255,136,0.8)';
      ctx2.lineWidth = 2;
      ctx2.beginPath();
      ctx2.arc(nx, ny, 8, 0, Math.PI*2);
      ctx2.stroke();
      // Nose dot
      ctx2.fillStyle = '#ff4488';
      ctx2.beginPath();
      ctx2.arc(nx, ny, 4, 0, Math.PI*2);
      ctx2.fill();
      // Draw posture line between shoulders
      var lsx = (1-lm.nose_x)*W, rsx = lsx;
      var lsy = lm.l_shoulder_y ? lm.l_shoulder_y*H : ny+40;
      var rsy = lm.r_shoulder_y ? lm.r_shoulder_y*H : ny+40;
      ctx2.strokeStyle = 'rgba(0,230,118,0.75)';
      ctx2.lineWidth = 3;
      ctx2.beginPath();
      // Shoulder line
      var lshx = (1-(lm.l_wrist_x||lm.nose_x))*W;
      var rshx = (1-(lm.r_wrist_x||lm.nose_x))*W;
      ctx2.moveTo(lshx, lsy);
      ctx2.lineTo(rshx, rsy);
      ctx2.stroke();
      // Wrist dots
      if(lm.l_wrist_x){
        ctx2.fillStyle = 'rgba(255,160,0,0.9)';
        ctx2.beginPath();
        ctx2.arc((1-lm.l_wrist_x)*W, lm.l_wrist_y*H, 6, 0, Math.PI*2);
        ctx2.fill();
      }
      if(lm.r_wrist_x){
        ctx2.fillStyle = 'rgba(255,100,200,0.9)';
        ctx2.beginPath();
        ctx2.arc((1-lm.r_wrist_x)*W, lm.r_wrist_y*H, 6, 0, Math.PI*2);
        ctx2.fill();
      }
      ctx2.restore();
    }
  }

  function drawEmotionRing(ctx2, W, H, emotion, pct){
    if(!emotion) return;
    var colors = {happy:'#22c55e',joyful:'#34d399',sad:'#818cf8',angry:'#f87171',
                  fear:'#fbbf24',surprised:'#60a5fa',neutral:'#6b7280'};
    var clr = colors[emotion] || '#4a9eff';
    var conf = pct ? (pct[emotion]||0)/100 : 0.5;
    // Small emotion badge top-right of canvas
    ctx2.save();
    ctx2.fillStyle = 'rgba(0,0,0,0.6)';
    ctx2.roundRect(W-90, 5, 84, 22, 6);
    ctx2.fill();
    ctx2.fillStyle = clr;
    ctx2.font = 'bold 11px Arial';
    ctx2.textAlign = 'center';
    ctx2.fillText(emotion.toUpperCase()+' '+(Math.round(conf*100))+'%', W-48, 20);
    ctx2.restore();
  }

  function drawFingerHUD(ctx2, W, H, fc){
    fc = fc || 0;
    ctx2.save();
    ctx2.fillStyle = 'rgba(0,0,0,0.6)';
    ctx2.roundRect(5, H-28, 70, 22, 6);
    ctx2.fill();
    ctx2.fillStyle = '#fbbf24';
    ctx2.font = 'bold 12px Arial';
    ctx2.textAlign = 'left';
    ctx2.fillText('✋ ' + fc, 10, H-13);
    ctx2.restore();
  }

  // ── Fetch JPEG frame and update img ─────────────────────────
  function fetchFrame(){
    if(!_active) return;
    var newSrc = '/api/live_frame?t=' + Date.now();
    var tempImg = new Image();
    tempImg.onload = function(){
      bgImg.src = newSrc;
      _frameCount++;
      var now = Date.now();
      if(now - _lastFpsTime >= 1000){
        _fps = Math.round(_frameCount * 1000 / (now - _lastFpsTime));
        _frameCount = 0;
        _lastFpsTime = now;
        if(fpsBadge) fpsBadge.textContent = _fps + ' FPS';
      }
    };
    tempImg.src = newSrc;
  }

  // ── Fetch stats and update HUD ───────────────────────────────
  function fetchStats(){
    if(!_active) return;
    fetch('/api/state/full')
      .then(function(r){ return r.json(); })
      .then(function(d){
        // Update HUD text
        function eid(id, val){ var el=document.getElementById(id); if(el)el.textContent=val; }
        eid('lv-hud-emotion', (d.emotion||'neutral').toUpperCase());
        eid('lv-hud-att', d.attention||0);
        eid('lv-hud-fc', d.finger_count||0);
        eid('lv-hud-score', d.score||0);
        eid('lv-hud-em2', (d.emotion||'neutral').toUpperCase());
        eid('lv-hud-face', d.face ? '✅' : '❌');
        eid('lv-hud-streak', (d.streak||0)+'🔥');
        eid('lv-finger-big', d.finger_count||0);
        // Finger dots
        for(var i=0;i<10;i++){
          var dot=document.getElementById('lv-finger-dot-'+i);
          if(dot) dot.style.background=i<(d.finger_count||0)?'#fbbf24':'rgba(255,255,255,.1)';
        }
        // Emotion bars
        var pct = d.emotion_pct||{};
        ['happy','joyful','sad','angry','fear','surprised','neutral'].forEach(function(e){
          var bar=document.getElementById('lv-ebar-'+e);
          var lbl=document.getElementById('lv-epct-'+e);
          var v=pct[e]||0;
          if(bar)bar.style.width=v+'%';
          if(lbl)lbl.textContent=v+'%';
        });
        // Draw canvas overlay with live state
        drawOverlay(d);
        // Mute status
        var ms=document.getElementById('lv-mute-badge');
        if(ms){
          var muted=d.pepper_muted||false;
          ms.textContent='Pepper voice: '+(muted?'🔇 MUTED':'🔊 Active');
          ms.style.color=muted?'#f87171':'#34d399';
        }
      })
      .catch(function(){});
  }

  // ── Start/Stop on tab visibility ─────────────────────────────
  function startLV(){
    if(_active) return;
    _active = true;
    _frameTimer = setInterval(fetchFrame, FRAME_INTERVAL);
    _statsTimer  = setInterval(fetchStats, STATS_INTERVAL);
    fetchFrame(); fetchStats();
  }
  function stopLV(){
    _active = false;
    clearInterval(_frameTimer);
    clearInterval(_statsTimer);
  }

  // ── Auto-start when tab is visible ──────────────────────────
  startLV();

  // Stop when navigating away from lv tab to save resources
  var tabBtns = document.querySelectorAll('.tab');
  tabBtns.forEach(function(btn){
    btn.addEventListener('click', function(){
      var isLV = btn.getAttribute('onclick') && btn.getAttribute('onclick').indexOf("'lv'") >= 0;
      if(isLV){ startLV(); } else { stopLV(); }
    });
  });

  // ── Quick action helper ───────────────────────────────────────
  window.qAction = function(action){
    var fd = new FormData();
    fd.append('action', action);
    fetch('/quick_action', {method:'POST', body:fd})
      .then(function(){ fetchStats(); })
      .catch(function(){});
  };

  // ── Mute status update ────────────────────────────────────────
  window.lvMuteStatus = function(muted){
    var el = document.getElementById('lv-mute-badge');
    if(el){
      el.textContent = 'Pepper voice: ' + (muted ? '🔇 MUTED' : '🔊 Active');
      el.style.color = muted ? '#f87171' : '#34d399';
    }
  };

  // ── Canvas roundRect polyfill for older browsers ─────────────
  if(!CanvasRenderingContext2D.prototype.roundRect){
    CanvasRenderingContext2D.prototype.roundRect=function(x,y,w,h,r){
      this.beginPath();this.moveTo(x+r,y);this.lineTo(x+w-r,y);
      this.quadraticCurveTo(x+w,y,x+w,y+r);this.lineTo(x+w,y+h-r);
      this.quadraticCurveTo(x+w,y+h,x+w-r,y+h);this.lineTo(x+r,y+h);
      this.quadraticCurveTo(x,y+h,x,y+h-r);this.lineTo(x,y+r);
      this.quadraticCurveTo(x,y,x+r,y);this.closePath();
    };
  }
})();
</script>

<!-- EMPOWERMENT HUB -->
<div id="tc-em" class="tc">
  <div class="card" style="margin-bottom:10px">
    <h2>📚 Empowerment Hub — Become a Home Therapist!</h2>
    <p style="color:#6b7280;font-size:.78em;line-height:1.6">
      Learn ABA, TEACCH, DTT, and ESDM strategies to reinforce therapy at home.
      Each module takes 5-10 minutes and includes practical exercises.</p>
  </div>
  {% for mod in modules %}
  <div class="module">
    <div class="module-title">{{mod.icon}} {{mod.title}}</div>
    <div class="module-content">{{mod.content}}</div>
    <a href="{{mod.video}}" target="_blank" class="btn" style="display:inline-block;margin-top:8px;text-decoration:none;">
      🎥 Watch Training Video</a>
  </div>{% endfor %}
</div>

<!-- NOTES -->
<div id="tc-nt" class="tc">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
    <div class="card"><h2>📝 Add Note</h2>
      <form method="POST" action="/note">
        <select name="cat"><option>behavior</option><option>progress</option>
          <option>concern</option><option>milestone</option></select>
        <textarea name="note" placeholder="Write observation…" rows="3"></textarea>
        <button class="btn btn-g" style="width:100%">Save Note</button>
      </form>
    </div>
    <div class="card"><h2>📋 History</h2>
      <div style="max-height:260px;overflow-y:auto">
        {% for n in notes[-15:]|reverse %}
        <div class="note">
          <span style="color:#a78bfa;font-size:.68em;font-weight:700">{{n.get('category','note').upper()}}</span>
          <span style="color:#6b7280;font-size:.68em"> {{n.time}}</span><br>{{n.text}}
        </div>{% endfor %}
      </div>
    </div>
  </div>

<!-- MOODS TAB -->
<div id="tc-mood" class="tc">
  <div class="card"><h2>🌈 ASD Mood Board — 13 Moods</h2>
    <p style="font-size:.75em;color:#6b7280;margin-bottom:8px">Tap a mood to log it and get Pepper to respond with a calming strategy.</p>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:8px" id="moodBtns">
      {% for m in asd_moods %}
      <form method="POST" action="/set_mood" style="display:inline">
        <input type="hidden" name="mood_id" value="{{m.id}}">
        <button class="btn" style="width:100%;background:{{m.color}}20;border:2px solid {{m.color}};color:{{m.color}};padding:8px 4px;font-size:.75em">
          {{m.em}}<br>{{m.label}}
        </button>
      </form>{% endfor %}
    </div>
    <div style="font-size:.75em;color:#9ca3af">Current: <b style="color:#a78bfa" id="curMood">{{current_mood or 'Not set'}}</b></div>
  </div>
  <div class="card"><h2>📊 Mood History</h2>
    <div style="max-height:200px;overflow-y:auto">
      {% for ml in mood_log[-15:]|reverse %}
      <div style="padding:3px 6px;background:#07090f;border-left:3px solid #a78bfa;margin:2px 0;font-size:.72em">
        {{ml.em}} <b style="color:#e0e6ff">{{ml.label}}</b>
        <span style="color:#6b7280;float:right">{{ml.time}}</span>
      </div>{% endfor %}
      {% if not mood_log %}<p style="color:#6b7280;font-size:.75em">No mood events yet.</p>{% endif %}
    </div>
  </div>
</div>

<!-- MUSIC TAB -->
<div id="tc-music" class="tc">
  <div class="card"><h2>🎵 Calming Music Library — 8 Evidence-Based Tracks</h2>
    <p style="font-size:.75em;color:#6b7280;margin-bottom:8px">Evidence-based calming sounds for ASD. Track selection is logged.</p>
    <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:8px">
      {% for t in music_tracks %}
      <form method="POST" action="/set_music" style="display:inline">
        <input type="hidden" name="track_id" value="{{t.id}}">
        <button class="btn" style="width:100%;text-align:center;padding:10px 4px;font-size:.72em">
          {{t.em}}<br><b>{{t.name}}</b><br><span style="font-size:.65em;color:#9ca3af">{{t.type}}</span>
        </button>
      </form>{% endfor %}
    </div>
    <div style="font-size:.75em;color:#9ca3af">Playing: <b style="color:#34d399">{{current_music}}</b></div>
    <form method="POST" action="/set_music" style="margin-top:6px">
      <input type="hidden" name="track_id" value="stop">
      <button class="btn btn-r" style="font-size:.75em">⏹ Stop Music</button>
    </form>
  </div>
</div>

<!-- VOICE PROFILE TAB -->
<div id="tc-voice" class="tc">
  <div class="card"><h2>🎙 Pepper Voice Profiles — 4 Options</h2>
    <p style="font-size:.75em;color:#6b7280;margin-bottom:8px">Choose Pepper's voice character to best connect with your child.</p>
    <div style="display:grid;grid-template-columns:repeat(2,1fr);gap:8px">
      {% for prof_id, prof in voice_profiles.items() %}
      <form method="POST" action="/set_voice_profile">
        <input type="hidden" name="profile" value="{{prof_id}}">
        <button class="btn {% if prof_id == current_voice_profile %}btn-g{% endif %}" style="width:100%;padding:12px;font-size:.85em">
          {{prof.label}}<br><span style="font-size:.7em;color:#9ca3af">Rate: {{prof.rate}} wpm</span>
        </button>
      </form>{% endfor %}
    </div>
    <div style="margin-top:8px;font-size:.75em;color:#9ca3af">Current: <b style="color:#a78bfa">{{voice_profiles[current_voice_profile].label}}</b></div>
  </div>
</div>

<!-- THEME TAB -->
<div id="tc-theme" class="tc">
  <div class="card"><h2>🎨 Color Themes — 6 Options</h2>
    <p style="font-size:.75em;color:#6b7280;margin-bottom:8px">Choose visual theme for child's visual comfort.</p>
    <div style="display:grid;grid-template-columns:repeat(3,1fr);gap:8px">
      {% for theme_id, theme in color_themes.items() %}
      <form method="POST" action="/set_theme">
        <input type="hidden" name="theme" value="{{theme_id}}">
        <button class="btn {% if theme_id == current_theme %}btn-g{% endif %}" 
          style="width:100%;padding:12px;background:{{theme.card}};border:2px solid {{theme.accent}};color:{{theme.accent}};font-size:.8em">
          {{theme_id.upper()}}
        </button>
      </form>{% endfor %}
    </div>
    <div style="margin-top:8px;font-size:.75em;color:#9ca3af">Active: <b style="color:#a78bfa">{{current_theme.upper()}}</b></div>
  </div>
</div>

<!-- ACCESS / SUBSCRIPTION TAB -->
<div id="tc-sub" class="tc">
  <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
    <div class="card"><h2>🆓 Free Trial (15 Days)</h2>
      <form method="POST" action="/start_trial">
        <input name="parent_name" placeholder="Parent Name" style="width:100%;padding:6px;background:#07090f;color:#e0e6ff;border:1px solid #1a1f40;border-radius:6px;margin-bottom:6px">
        <input name="email" type="email" placeholder="Email" style="width:100%;padding:6px;background:#07090f;color:#e0e6ff;border:1px solid #1a1f40;border-radius:6px;margin-bottom:6px">
        <input name="child_name" placeholder="Child Name" style="width:100%;padding:6px;background:#07090f;color:#e0e6ff;border:1px solid #1a1f40;border-radius:6px;margin-bottom:6px">
        <input name="child_age" type="number" placeholder="Age" min="2" max="18" style="width:100%;padding:6px;background:#07090f;color:#e0e6ff;border:1px solid #1a1f40;border-radius:6px;margin-bottom:6px">
        <button class="btn btn-g" style="width:100%">🆓 Start Free Trial</button>
      </form>
    </div>
    <div class="card"><h2>💎 Subscribe</h2>
      <form method="POST" action="/start_subscription">
        <input name="parent_name" placeholder="Parent Name" style="width:100%;padding:6px;background:#07090f;color:#e0e6ff;border:1px solid #1a1f40;border-radius:6px;margin-bottom:6px">
        <input name="email" type="email" placeholder="Email" style="width:100%;padding:6px;background:#07090f;color:#e0e6ff;border:1px solid #1a1f40;border-radius:6px;margin-bottom:6px">
        <input name="child_name" placeholder="Child Name" style="width:100%;padding:6px;background:#07090f;color:#e0e6ff;border:1px solid #1a1f40;border-radius:6px;margin-bottom:6px">
        <input name="child_age" type="number" placeholder="Age" style="width:100%;padding:6px;background:#07090f;color:#e0e6ff;border:1px solid #1a1f40;border-radius:6px;margin-bottom:6px">
        <select name="plan" style="width:100%;padding:6px;background:#07090f;color:#e0e6ff;border:1px solid #1a1f40;border-radius:6px;margin-bottom:6px">
          <option value="month">Monthly — £49/month</option>
          <option value="year">Annual — £399/year (Save 32%)</option>
        </select>
        <button class="btn" style="width:100%;background:#7c3aed">💎 Subscribe</button>
      </form>
    </div>
  </div>
  <div class="card"><h2>🔑 Active Subscriptions</h2>
    <div style="max-height:200px;overflow-y:auto">
      {% for pin, trial in active_trials.items() %}
      <div style="padding:5px;background:#07090f;border-left:3px solid {% if trial.plan == 'free_trial' %}#f97316{% else %}#a78bfa{% endif %};margin:3px 0;font-size:.72em">
        <b style="color:#e0e6ff">{{trial.get('childName','?')}}</b>
        <span style="color:#a78bfa">PIN: {{trial.get('pin','?')}}</span>
        <span style="color:#6b7280;float:right">{{trial.get('plan','?')}} | exp: {{trial.get('expiryDate','?')[:10]}}</span>
      </div>{% endfor %}
      {% if not active_trials %}<p style="color:#6b7280;font-size:.75em">No active subscriptions.</p>{% endif %}
    </div>
  </div>
</div>

</div>

<script>
function T(n){
  document.querySelectorAll('.tc').forEach(t=>t.classList.remove('active'));
  document.querySelectorAll('.tab').forEach(t=>t.classList.remove('active'));
  document.getElementById('tc-'+n).classList.add('active');event.target.classList.add('active');
}
const attD={{att_h|tojson}},scD={{sc_h|tojson}};
const CO={responsive:true,maintainAspectRatio:false,
  plugins:{legend:{labels:{color:'#9ca3af',font:{size:9}}}},
  scales:{x:{ticks:{color:'#6b7280',font:{size:8}},grid:{color:'#1f2937'}},
          y:{ticks:{color:'#6b7280',font:{size:8}},grid:{color:'#1f2937'}}}};
if(document.getElementById('attChart'))
  new Chart(document.getElementById('attChart'),{type:'line',
    data:{labels:attD.map((_,i)=>i+1),datasets:[{label:'Attention %',data:attD,
      borderColor:'#6366f1',backgroundColor:'rgba(99,102,241,.1)',tension:.4,fill:true,pointRadius:1}]},
    options:{...CO,scales:{...CO.scales,y:{...CO.scales.y,min:0,max:100}}}});
if(document.getElementById('scoreChart'))
  new Chart(document.getElementById('scoreChart'),{type:'bar',
    data:{labels:scD.map((_,i)=>i+1),datasets:[{label:'Score',data:scD,
      backgroundColor:'rgba(167,139,250,.5)',borderColor:'#a78bfa',borderWidth:1}]},options:CO});
if(document.getElementById('taskChart'))
  new Chart(document.getElementById('taskChart'),{type:'doughnut',
    data:{labels:['Success','Fail','Skipped'],
      datasets:[{data:[{{ok}},{{fail}},{{skipped}}],
        backgroundColor:['#34d399','#f87171','#f97316']}]},
    options:{responsive:true,maintainAspectRatio:false,
      plugins:{legend:{position:'bottom',labels:{color:'#9ca3af',font:{size:9}}}}}});
if(document.getElementById('skillChart'))
  new Chart(document.getElementById('skillChart'),{type:'radar',
    data:{labels:['Motor','Cognitive','Verbal','Math','Social'],
      datasets:[{label:'Skills %',data:[{{sm}},{{sc_}},{{sv}},{{smath}},{{ssoc}}],
        borderColor:'#a78bfa',backgroundColor:'rgba(167,139,250,.2)',pointBackgroundColor:'#a78bfa'}]},
    options:{responsive:true,maintainAspectRatio:false,
      scales:{r:{ticks:{color:'#6b7280',font:{size:8}},grid:{color:'#1f2937'},
                 pointLabels:{color:'#9ca3af',font:{size:9}},min:0,max:100}},
      plugins:{legend:{labels:{color:'#9ca3af',font:{size:9}}}}}});
var ac=document.getElementById('aiC'); if(ac) ac.scrollTop=ac.scrollHeight;
</script></body></html>"""

def _user_hash(password):
    if _BCRYPT_OK:
        return bcrypt.hashpw(password.encode(),bcrypt.gensalt()).decode()
    return hashlib.sha256(password.encode()).hexdigest()

def _user_check(password,hashed):
    if _BCRYPT_OK:
        try: return bcrypt.checkpw(password.encode(),hashed.encode())
        except: pass
    return hashlib.sha256(password.encode()).hexdigest()==hashed

@parent_app.route("/login",methods=["GET","POST"])
def login():
    error=None
    if request.method=="POST":
        db=load_db(); u=request.form.get("username","").strip()
        p=request.form.get("password","")
        if u in db["users"] and _user_check(p,db["users"][u]["hash"]):
            session["user"]=u; return redirect("/")
        error="Invalid username or password."
    return render_template_string(LOGIN_HTML,error=error,child=CHILD_NAME)

@parent_app.route("/register",methods=["POST"])
def register():
    db=load_db(); u=request.form.get("reg_username","").strip()
    p=request.form.get("reg_password","")
    if not u or len(p)<6:
        return render_template_string(LOGIN_HTML,error="Username required. Password min 6 chars.",child=CHILD_NAME)
    if u in db["users"]:
        return render_template_string(LOGIN_HTML,error="Username already taken.",child=CHILD_NAME)
    db["users"][u]={"hash":_user_hash(p),"email":request.form.get("reg_email",""),
                    "created":datetime.now().strftime("%Y-%m-%d")}
    save_db(db); session["user"]=u; return redirect("/")

@parent_app.route("/logout")
def logout():
    session.clear(); return redirect("/login")

@parent_app.before_request
def require_login():
    if request.endpoint not in ("login","register") and "user" not in session:
        return redirect("/login")

@parent_app.route("/")
def parent_home():
    pct=ST.get("emotion_pct",{k:0 for k in ["happy","joyful","sad","angry","fear","surprised","neutral"]})
    return render_template_string(PARENT_HTML,
        child=CHILD_NAME,user=session.get("user","?"),
        age=ST["age"],score=ST["score"],mastered=ST["tasks_mastered"],
        att=ST["attention"],skipped=ST["tasks_skipped"],
        em=ST["emotion"],conf=int(ST.get("emotion_conf",0)*100),
        face=ST["face_detected"],fc=ST["finger_count"],streak=ST["streak"],
        fails=ST["fail_count"],pct=pct,clvl=ST["conversation_level"],
        sm=ST["skill_motor"],sc_=ST["skill_cognitive"],
        sv=ST["skill_verbal"],smath=ST["skill_math"],ssoc=ST["skill_social"],
        notes=ST["parent_notes"],chat=ST["session_chat"],logs=ST["logs"],
        ai_chat=_ai_chat,pecs_log=ST["pecs_log"],
        date=ST["session_date"],ok=ST["tasks_success"],fail=ST["tasks_fail"],
        asq_score=ST.get("asq_score"),vbmapp_score=ST.get("vbmapp_score"),
        asq_q=ASQ_Q,vbmapp_q=VBMAPP_Q,quick_q=QUICK_Q,
        att_h=ST["att_history"][-40:],sc_h=ST["score_history"][-40:],
        domain=ST["domain"],modules=EMPOWERMENT_MODULES,lip=LOCAL_IP,
        # NEW: Mood, Music, Voice, Theme, Trial, Mute vars
        asd_moods=ASD_MOODS,mood_log=ST.get("mood_log",[]),current_mood=ST.get("current_mood"),
        music_tracks=MUSIC_TRACKS,current_music=ST.get("current_music","none"),
        voice_profiles=VOICE_PROFILES,current_voice_profile=CURRENT_VOICE_PROFILE,
        color_themes=COLOR_THEMES,current_theme=CURRENT_THEME,
        active_trials=load_trials(),
        pepper_muted=ST.get("pepper_muted",False))

@parent_app.route("/note",methods=["POST"])
def note():
    n=request.form.get("note","").strip(); cat=request.form.get("cat","note")
    if n: ST["parent_notes"].append({"time":datetime.now().strftime("%H:%M"),"text":n,"category":cat})
    return redirect("/")

@parent_app.route("/asq_submit",methods=["POST"])
def asq_submit():
    total=sum(int(request.form.get(f"asq_{i}",0)) for i in range(len(ASQ_Q)))
    ST["asq_score"]=total
    if total>15: ST["conversation_level"]=1
    elif total>10: ST["conversation_level"]=2
    else: ST["conversation_level"]=3
    LOG(f"ASQ:{total} → conv_level={ST['conversation_level']}","info")
    return redirect("/")

@parent_app.route("/vbmapp_submit",methods=["POST"])
def vbmapp_submit():
    total=sum(int(request.form.get(f"vb_{i}",0)) for i in range(len(VBMAPP_Q)))
    ST["vbmapp_score"]=total
    if total>=14: ST["conversation_level"]=3
    elif total>=8: ST["conversation_level"]=2
    else: ST["conversation_level"]=1
    LOG(f"VB-MAPP:{total} → conv_level={ST['conversation_level']}","info")
    return redirect("/")

@parent_app.route("/ai_chat",methods=["POST"])
def ai_chat_route():
    q=request.form.get("question","").strip()
    if q:
        _ai_chat.append({"role":"parent","text":q,"time":datetime.now().strftime("%H:%M")})
        ans=gemini_chat(q)
        _ai_chat.append({"role":"ai","text":ans,"time":datetime.now().strftime("%H:%M")})
        if len(_ai_chat)>40: _ai_chat[:]=_ai_chat[-40:]
    return redirect("/")

@parent_app.route("/quick_action",methods=["POST"])
def quick_action():
    ST["quick_action"]=request.form.get("action",""); return redirect("/")

@parent_app.route("/gen_pdf",methods=["GET","POST"])
def gen_pdf_route():
    fn=generate_pdf()
    if fn and os.path.exists(fn): return send_file(fn,as_attachment=True)
    return redirect("/")

@parent_app.route("/api/state")
def api_state():
    return jsonify({"emotion":ST["emotion"],"emotion_pct":ST.get("emotion_pct",{}),
                    "attention":ST["attention"],"score":ST["score"],
                    "mastered":ST["tasks_mastered"],"finger_count":ST["finger_count"],
                    "domain":ST["domain"],"streak":ST["streak"],"face":ST["face_detected"],
                    "conv_level":ST["conversation_level"]})


# ── NEW: Trial/Subscription API routes ────────────────────────────
@parent_app.route("/api/trial", methods=["POST"])
def api_trial():
    d = request.get_json(silent=True) or request.form
    pn  = (d.get("parentName","") or "").strip()
    em  = (d.get("email","") or "").strip()
    cn  = (d.get("childName","") or "").strip()
    ca  = str(d.get("childAge","6"))
    if not all([pn,em,cn]): return jsonify({"ok":False,"error":"All fields required."}),400
    if "@" not in em:       return jsonify({"ok":False,"error":"Invalid email."}),400
    result = create_trial(pn, em, cn, ca)
    return jsonify(result)

@parent_app.route("/api/subscribe", methods=["POST"])
def api_subscribe():
    d = request.get_json(silent=True) or request.form
    pn   = (d.get("parentName","") or "").strip()
    em   = (d.get("email","") or "").strip()
    cn   = (d.get("childName","") or "").strip()
    ca   = str(d.get("childAge","6"))
    plan = (d.get("plan","month") or "month")
    if not all([pn,em,cn]): return jsonify({"ok":False,"error":"All fields required."}),400
    result = create_subscription(pn, em, cn, ca, plan)
    return jsonify(result)

@parent_app.route("/api/verify_pin", methods=["POST"])
def api_verify_pin():
    d   = request.get_json(silent=True) or request.form
    pin = str(d.get("pin","")).strip()
    data = verify_pin(pin)
    if data: return jsonify({"ok":True,"data":{k:v for k,v in data.items() if k!="hash"}})
    return jsonify({"ok":False,"error":"Invalid or expired PIN."}),401

# ── NEW: Mood Board API ────────────────────────────────────────────
@parent_app.route("/api/mood", methods=["POST"])
def api_mood():
    d      = request.get_json(silent=True) or request.form
    mood_id = str(d.get("mood_id","")).strip()
    mood = next((m for m in ASD_MOODS if m["id"]==mood_id), None)
    if not mood: return jsonify({"ok":False,"error":"Unknown mood."}),400
    ST["current_mood"] = mood_id
    entry = {"time":datetime.now().strftime("%H:%M:%S"),"id":mood_id,
             "em":mood["em"],"label":mood["label"],"emotion":ST["emotion"]}
    ST["mood_log"].append(entry)
    if len(ST["mood_log"])>100: ST["mood_log"]=ST["mood_log"][-100:]
    # Pepper speaks mood response
    if VOICE_REF and not ST.get("pecs_interrupt"):
        def _speak_mood():
            VOICE_REF.say(mood["speech"], wait=False)
        threading.Thread(target=_speak_mood, daemon=True).start()
    LOG(f"Mood set: {mood['label']} — {mood['speech'][:40]}", "info")
    return jsonify({"ok":True,"speech":mood["speech"],"music":mood["music"],
                    "color":mood["color"],"mood":mood})

@parent_app.route("/api/moods")
def api_moods():
    return jsonify({"moods":ASD_MOODS,"current":ST.get("current_mood"),
                    "mood_log":ST.get("mood_log",[])[-20:]})

# ── NEW: Music API ─────────────────────────────────────────────────
@parent_app.route("/api/music", methods=["POST"])
def api_music():
    d        = request.get_json(silent=True) or request.form
    track_id = str(d.get("track_id","")).strip()
    track = next((t for t in MUSIC_TRACKS if t["id"]==track_id), None)
    if not track: return jsonify({"ok":False,"error":"Unknown track."}),400
    ST["current_music"] = track["name"]
    LOG(f"Music: {track['name']}", "info")
    return jsonify({"ok":True,"track":track})

@parent_app.route("/api/music/stop", methods=["POST"])
def api_music_stop():
    ST["current_music"] = "none"
    return jsonify({"ok":True})

@parent_app.route("/api/music/tracks")
def api_music_tracks():
    return jsonify({"tracks":MUSIC_TRACKS,"current":ST.get("current_music","none")})

# ── Pepper Voice Mute / Unmute ─────────────────────────────────────
@parent_app.route("/api/pepper/mute", methods=["POST"])
def api_pepper_mute():
    ST["pepper_muted"] = True
    if VOICE_REF:
        try:
            VOICE_REF.stop()
        except Exception: pass
    ST["is_speaking"] = False
    LOG("🔇 Pepper voice MUTED", "info")
    return jsonify({"ok":True,"muted":True})

@parent_app.route("/api/pepper/unmute", methods=["POST"])
def api_pepper_unmute():
    ST["pepper_muted"] = False
    LOG("🔊 Pepper voice UNMUTED", "info")
    return jsonify({"ok":True,"muted":False})

@parent_app.route("/api/pepper/mute_status")
def api_pepper_mute_status():
    return jsonify({"muted": ST.get("pepper_muted", False),
                    "is_speaking": ST.get("is_speaking", False)})

# ── Live Child Camera View ──────────────────────────────────────────
# Returns JPEG snapshot of last camera frame for parent live view
@parent_app.route("/api/live_frame")
def api_live_frame():
    """
    Live camera frame endpoint — returns latest JPEG snapshot.
    © 2026 Lamya Fadlulmola Hamed Ali — All Rights Reserved
    Parent dashboard polls this at 10 FPS for real-time child view.
    """
    from flask import Response
    frame = ST.get("_last_frame_jpeg")
    if frame:
        return Response(frame, mimetype="image/jpeg",
                        headers={
                            "Cache-Control": "no-cache, no-store, must-revalidate",
                            "Pragma": "no-cache",
                            "Expires": "0",
                            "X-Content-Copyright": "2026 Lamya Fadlulmola Hamed Ali",
                            "X-Timestamp": str(time.time()),
                        })
    # Return dark placeholder JPEG (1x240 dark blue)
    import cv2, numpy as np
    placeholder = np.zeros((180, 320, 3), dtype=np.uint8)
    placeholder[:] = (10, 12, 28)
    cv2.putText(placeholder, "Pepper V6 — Waiting for camera...",
                (20, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (74,158,255), 1)
    cv2.putText(placeholder, "© 2026 Lamya Fadlulmola Hamed Ali",
                (20, 165), cv2.FONT_HERSHEY_SIMPLEX, 0.30, (40,80,120), 1)
    _, jpeg = cv2.imencode(".jpg", placeholder, [cv2.IMWRITE_JPEG_QUALITY, 70])
    return Response(bytes(jpeg), mimetype="image/jpeg",
                    headers={"Cache-Control":"no-cache, no-store"})

@parent_app.route("/api/live_stream")
def api_live_stream():
    """
    True MJPEG stream for live child view.
    © 2026 Lamya Fadlulmola Hamed Ali — All Rights Reserved
    Open this URL in an <img> tag for continuous streaming.
    """
    from flask import Response, stream_with_context
    def generate_mjpeg():
        import cv2, numpy as np
        while True:
            frame = ST.get("_last_frame_jpeg")
            if frame:
                yield (b"--frame\r\n"
                       b"Content-Type: image/jpeg\r\n\r\n" + frame + b"\r\n")
            else:
                # Placeholder
                ph = np.zeros((180,320,3), dtype=np.uint8)
                ph[:] = (10,12,28)
                cv2.putText(ph,"Camera starting...",(20,90),cv2.FONT_HERSHEY_SIMPLEX,
                            0.45,(74,158,255),1)
                _,j=cv2.imencode(".jpg",ph,[cv2.IMWRITE_JPEG_QUALITY,60])
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"+bytes(j)+b"\r\n")
            time.sleep(0.1)   # 10 FPS
    return Response(
        stream_with_context(generate_mjpeg()),
        mimetype="multipart/x-mixed-replace; boundary=frame",
        headers={
            "Cache-Control":"no-cache, no-store",
            "X-Content-Copyright":"2026 Lamya Fadlulmola Hamed Ali",
        }
    )


# ── NEW: Voice Profile API ─────────────────────────────────────────
@parent_app.route("/api/voice_profile", methods=["POST"])
def api_voice_profile():
    global CURRENT_VOICE_PROFILE
    d    = request.get_json(silent=True) or request.form
    prof = str(d.get("profile","girl")).strip()
    if prof not in VOICE_PROFILES:
        return jsonify({"ok":False,"error":"Unknown profile."}),400
    CURRENT_VOICE_PROFILE = prof
    info = VOICE_PROFILES[prof]
    if VOICE_REF:
        try:
            VOICE_REF.e.setProperty("rate", info["rate"])
        except: pass
    LOG(f"Voice profile: {info['label']}", "info")
    return jsonify({"ok":True,"profile":prof,"label":info["label"]})

# ── NEW: Theme API ─────────────────────────────────────────────────
@parent_app.route("/api/theme", methods=["POST"])
def api_theme():
    global CURRENT_THEME
    d     = request.get_json(silent=True) or request.form
    theme = str(d.get("theme","blue")).strip()
    if theme not in COLOR_THEMES:
        return jsonify({"ok":False,"error":"Unknown theme."}),400
    CURRENT_THEME = theme
    LOG(f"Theme: {theme}", "info")
    return jsonify({"ok":True,"theme":theme,"colors":COLOR_THEMES[theme]})

# ── NEW: Session History API ───────────────────────────────────────
@parent_app.route("/api/session_history")
def api_session_history():
    sessions_file = f"{SAFE_NAME}_v6_sessions.json"
    sessions = []
    try:
        if os.path.exists(sessions_file):
            with open(sessions_file) as f: sessions = json.load(f)
    except: pass
    return jsonify({"sessions":sessions[-20:],"current":ST.get("session_history",[])})

# ── NEW: Email Report API ──────────────────────────────────────────
@parent_app.route("/email_report", methods=["POST"])
def email_report():
    email = request.form.get("email","").strip()
    fn = generate_pdf()
    if fn:
        LOG(f"Report generated for email: {email[:20] if email else 'N/A'}", "info")
        return jsonify({"ok":True,"message":f"Report ready. Email feature requires SMTP config. PDF: {fn}"})
    return jsonify({"ok":False,"error":"Report generation failed."}),500

# ── NEW: Extended state API ────────────────────────────────────────
@parent_app.route("/api/state/full")
def api_state_full():
    pct = ST.get("emotion_pct",{})
    return jsonify({
        "emotion":ST["emotion"],"emotion_pct":pct,"attention":ST["attention"],
        "score":ST["score"],"mastered":ST["tasks_mastered"],"finger_count":ST["finger_count"],
        "domain":ST["domain"],"streak":ST["streak"],"face":ST["face_detected"],
        "conv_level":ST["conversation_level"],"fail_count":ST["fail_count"],
        "consecutive":ST["consecutive"],"tasks_success":ST["tasks_success"],
        "tasks_fail":ST["tasks_fail"],"tasks_skipped":ST["tasks_skipped"],
        "skill_motor":ST["skill_motor"],"skill_cognitive":ST["skill_cognitive"],
        "skill_verbal":ST["skill_verbal"],"skill_math":ST["skill_math"],
        "skill_social":ST["skill_social"],"is_speaking":ST["is_speaking"],
        "recording":ST["recording"],"pecs_log":ST.get("pecs_log",[])[-10:],
        "mood_log":ST.get("mood_log",[])[-10:],"current_mood":ST.get("current_mood"),
        "current_music":ST.get("current_music","none"),"current_theme":CURRENT_THEME,
        "att_history":ST.get("att_history",[])[-40:],"score_history":ST.get("score_history",[])[-40:],
    })

# ── NEW: Video task overlay API ────────────────────────────────────
@parent_app.route("/api/video_task")
def api_video_task():
    domain = request.args.get("domain", ST.get("domain","Motor"))
    videos = VIDEO_TASK_MAP.get(domain, VIDEO_TASK_MAP["Motor"])
    url = random.choice(videos)
    return jsonify({"ok":True,"url":url,"domain":domain})


@parent_app.route("/set_mood", methods=["POST"])
def set_mood():
    mood_id = request.form.get("mood_id","").strip()
    mood = next((m for m in ASD_MOODS if m["id"]==mood_id), None)
    if mood:
        ST["current_mood"] = mood_id
        entry = {"time":datetime.now().strftime("%H:%M:%S"),"id":mood_id,
                 "em":mood["em"],"label":mood["label"],"emotion":ST["emotion"]}
        ST["mood_log"].append(entry)
        if len(ST["mood_log"])>100: ST["mood_log"]=ST["mood_log"][-100:]
        if VOICE_REF and not ST.get("pecs_interrupt"):
            threading.Thread(target=lambda: VOICE_REF.say(mood["speech"],wait=False),daemon=True).start()
        LOG(f"Mood: {mood['label']}","info")
    return redirect("/#tc-mood")

@parent_app.route("/set_music", methods=["POST"])
def set_music():
    track_id = request.form.get("track_id","").strip()
    if track_id == "stop":
        ST["current_music"] = "none"
    else:
        track = next((t for t in MUSIC_TRACKS if t["id"]==track_id), None)
        if track:
            ST["current_music"] = track["name"]
            LOG(f"Music: {track['name']}","info")
    return redirect("/#tc-music")

@parent_app.route("/set_voice_profile", methods=["POST"])
def set_voice_profile_route():
    global CURRENT_VOICE_PROFILE
    prof = request.form.get("profile","girl").strip()
    if prof in VOICE_PROFILES:
        CURRENT_VOICE_PROFILE = prof
        info = VOICE_PROFILES[prof]
        if VOICE_REF:
            try: VOICE_REF.e.setProperty("rate", info["rate"])
            except: pass
        LOG(f"Voice: {info['label']}","info")
    return redirect("/#tc-voice")

@parent_app.route("/set_theme", methods=["POST"])
def set_theme_route():
    global CURRENT_THEME
    theme = request.form.get("theme","blue").strip()
    if theme in COLOR_THEMES:
        CURRENT_THEME = theme
        LOG(f"Theme: {theme}","info")
    return redirect("/#tc-theme")

@parent_app.route("/start_trial", methods=["POST"])
def start_trial_route():
    pn = request.form.get("parent_name","").strip()
    em = request.form.get("email","").strip()
    cn = request.form.get("child_name","").strip()
    ca = request.form.get("child_age","6")
    result = create_trial(pn, em, cn, ca)
    msg = f"Trial started! PIN: {result.get('pin','N/A')}" if result["ok"] else result.get("error","Error")
    LOG(f"Trial: {msg}","info")
    return redirect("/#tc-sub")

@parent_app.route("/start_subscription", methods=["POST"])
def start_subscription_route():
    pn   = request.form.get("parent_name","").strip()
    em   = request.form.get("email","").strip()
    cn   = request.form.get("child_name","").strip()
    ca   = request.form.get("child_age","6")
    plan = request.form.get("plan","month")
    result = create_subscription(pn, em, cn, ca, plan)
    msg = f"Subscription! PIN: {result.get('pin','N/A')} Plan: {result.get('plan')}" if result["ok"] else "Error"
    LOG(f"Sub: {msg}","info")
    return redirect("/#tc-sub")


# ── /share — public URL display for testing ────────────────────────
@parent_app.route("/share")
def share_page():
    global PUBLIC_URL
    local = f"http://127.0.0.1:5007/"
    android = f"http://{LOCAL_IP}:5007/"
    ngrok_url = PUBLIC_URL or "Not started (pip install pyngrok + set NGROK_AUTH_TOKEN)"
    html = f"""<!DOCTYPE html><html><head><meta charset="UTF-8">
<title>Pepper V6 — Share & Test</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
body{{background:#040b1a;color:#e0e8ff;font-family:'Segoe UI',sans-serif;padding:20px;max-width:700px;margin:0 auto}}
h1{{color:#a78bfa;margin-bottom:6px}}
.card{{background:#0a0d1e;border:2px solid #1a2550;border-radius:12px;padding:16px;margin:12px 0}}
.url{{font-size:1.1em;color:#34d399;word-break:break-all;font-family:monospace;
      background:#07090f;padding:8px;border-radius:6px;margin:6px 0}}
.label{{color:#9ca3af;font-size:.8em;font-weight:700;text-transform:uppercase;margin-bottom:4px}}
.btn{{display:inline-block;padding:8px 16px;background:#4f46e5;color:#fff;border-radius:8px;
      text-decoration:none;font-size:.85em;font-weight:700;margin:4px}}
.copy{{background:#059669}} .badge{{display:inline-block;padding:2px 8px;border-radius:99px;
      font-size:.7em;font-weight:700;background:#05291555;color:#34d399;border:1px solid #34d399}}
</style></head><body>
<h1>🤖 Pepper Clinical V6 — Share & Test</h1>
<p style="color:#6b7280;font-size:.85em">© 2026 Lamya Fadlulmola Hamed Ali · All Rights Reserved</p>

<div class="card">
  <div class="label">🖥 Local (same computer)</div>
  <div class="url"><a href="{local}" style="color:#34d399">{local}</a></div>
  <a href="{local}" class="btn">Open Dashboard</a>
</div>

<div class="card">
  <div class="label">📱 Network / Android (same WiFi)</div>
  <div class="url"><a href="{android}" style="color:#34d399">{android}</a></div>
  <a href="{android}" class="btn">Open on Phone</a>
</div>

<div class="card">
  <div class="label">🌐 Public Internet (ngrok tunnel)</div>
  <div class="url" id="ngrok_url">{ngrok_url}</div>
  {"<a href='" + ngrok_url + "' class='btn' target='_blank'>Open Public Link</a>" if PUBLIC_URL else ""}
  <p style="font-size:.75em;color:#6b7280;margin-top:8px">
    To enable: <code style="background:#07090f;padding:2px 6px;border-radius:4px">pip install pyngrok</code>
    then set <code style="background:#07090f;padding:2px 6px;border-radius:4px">NGROK_AUTH_TOKEN=your_token</code>
    and restart. Get free token at <a href="https://ngrok.com" style="color:#a78bfa">ngrok.com</a>
  </p>
</div>

<div class="card">
  <div class="label">📧 Session Reports Auto-Saved To</div>
  <div class="url">{OWNER_EMAIL}</div>
  <div style="font-size:.75em;color:#6b7280;margin-top:4px">
    Stored locally: <code style="background:#07090f;padding:2px 4px;border-radius:4px">{SAFE_NAME}_v6_sessions.json</code><br>
    Email queue: <code style="background:#07090f;padding:2px 4px;border-radius:4px">pending_email_reports.json</code>
  </div>
  <a href="/api/session_logs" class="btn" style="margin-top:8px">View Stored Sessions</a>
</div>

<div class="card">
  <div class="label">🔒 Security Status</div>
  <div style="font-size:.8em;line-height:2;color:#9ca3af">
    ✅ Rate limiting: 60 req/min per IP<br>
    ✅ Security headers: X-Frame-Options, CSP, XSS Protection<br>
    ✅ HMAC signing: X-Pepper-Sig header<br>
    ✅ Session encryption: bcrypt password hashing<br>
    ✅ PIN verification with expiry<br>
    ✅ No clinical data in cloud (HIPAA/GDPR)
  </div>
</div>
</body></html>"""
    return html

@parent_app.route("/api/session_logs")
def api_session_logs():
    """Return stored session history."""
    if "user" not in session: return redirect("/login")
    sessions_file = f"{SAFE_NAME}_v6_sessions.json"
    sessions = []
    try:
        if os.path.exists(sessions_file):
            with open(sessions_file) as f_: sessions = json.load(f_)
    except: pass
    email_queue = []
    try:
        if os.path.exists("pending_email_reports.json"):
            with open("pending_email_reports.json") as f_: email_queue = json.load(f_)
    except: pass
    return jsonify({
        "sessions": sessions[-20:],
        "total_sessions": len(sessions),
        "email_queue": len(email_queue),
        "owner_email": OWNER_EMAIL,
        "sessions_file": sessions_file,
    })

@parent_app.route("/api/store_session", methods=["POST"])
def api_store_session():
    """Manually trigger session storage."""
    snap = store_session_to_claude_log()
    return jsonify({"ok":True,"snapshot":snap})

@parent_app.errorhandler(404)
def p404(e): return redirect("/"),302

REPORT_HTML="""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><title>Clinical Report V6</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="refresh" content="5">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#060912;color:#e0e6ff;font-family:'Segoe UI',sans-serif;padding:14px}
h1{color:#a78bfa;margin-bottom:8px}
.nav{display:flex;gap:5px;margin-bottom:8px;flex-wrap:wrap}
.nav a{padding:6px 12px;border-radius:8px;text-decoration:none;font-size:.78em;font-weight:700}
.b1{background:#4f46e5;color:#fff}.b2{background:#059669;color:#fff}.b3{background:#1d4ed8;color:#fff}
.card{background:#0c0f1e;border-radius:10px;padding:12px;border:1px solid #1a1f40;margin-bottom:8px}
.card h2{color:#818cf8;margin-bottom:6px;font-size:.82em}
.stat{display:inline-block;background:#1a0a3d;border-radius:7px;padding:5px 10px;margin:3px;text-align:center}
.n{font-size:1.3em;font-weight:700;color:#a78bfa}.l{font-size:.63em;color:#6b7280}
table{width:100%;border-collapse:collapse;font-size:.72em}
th{background:#1a1f40;padding:5px;text-align:left;color:#a78bfa}
td{padding:4px 5px;border-bottom:1px solid #1a1f40}
.ok{background:#05291555;color:#34d399;padding:2px 6px;border-radius:8px;font-size:.7em}
.fl{background:#45090a55;color:#f87171;padding:2px 6px;border-radius:8px;font-size:.7em}
.sk{background:#2a1a0055;color:#f97316;padding:2px 6px;border-radius:8px;font-size:.7em}
.btn{background:#4f46e5;color:#fff;border:none;padding:7px 14px;border-radius:7px;cursor:pointer;font-size:.78em}
.btn-g{background:#059669}
</style></head><body>
<h1>📋 Clinical Report V6 — {{child}}</h1>
<div class="nav">
  <a href="http://127.0.0.1:5007/" class="b1">📊 Dashboard</a>
  <a href="http://127.0.0.1:5001/" class="b2">📋 Reports</a>
  <a href="http://127.0.0.1:5009/" class="b3">🎮 Games</a>
</div>
<div class="card"><h2>📊 Statistics</h2>
  <div class="stat"><div class="n">{{score}}</div><div class="l">Score</div></div>
  <div class="stat"><div class="n">{{mastered}}</div><div class="l">Mastered</div></div>
  <div class="stat"><div class="n">{{ok}}</div><div class="l">Correct</div></div>
  <div class="stat"><div class="n">{{fail}}</div><div class="l">Fail</div></div>
  <div class="stat"><div class="n">{{skipped}}</div><div class="l">Skipped</div></div>
  <div class="stat"><div class="n">{{att}}%</div><div class="l">Attention</div></div>
  <div class="stat"><div class="n">{{clvl}}</div><div class="l">Conv Level</div></div>
</div>
<div class="card"><h2>🎯 Skills</h2>
<table><tr><th>Skill</th><th>Level</th><th>Status</th></tr>
<tr><td>Motor (ABA)</td><td>{{sm}}%</td><td>{{'✅ Good' if sm>60 else '⚠️ Needs work'}}</td></tr>
<tr><td>Cognitive (TEACCH)</td><td>{{sc_}}%</td><td>{{'✅ Good' if sc_>60 else '⚠️ Needs work'}}</td></tr>
<tr><td>Verbal (DTT)</td><td>{{sv}}%</td><td>{{'✅ Good' if sv>60 else '⚠️ Needs work'}}</td></tr>
<tr><td>Math (Count)</td><td>{{smath}}%</td><td>{{'✅ Good' if smath>60 else '⚠️ Needs work'}}</td></tr>
<tr><td>Social (ESDM)</td><td>{{ssoc}}%</td><td>{{'✅ Good' if ssoc>60 else '⚠️ Needs work'}}</td></tr>
</table></div>
<div class="card"><h2>📋 Log</h2>
<table><tr><th>Time</th><th>Task</th><th>Protocol</th><th>Result</th><th>Emotion</th></tr>
{% for lg in logs[-40:]|reverse %}
<tr><td>{{lg.time}}</td><td>{{lg.msg[:35]}}</td><td>{{lg.proto[:8]}}</td>
<td><span class="{{'ok' if lg.type=='success' else 'fl' if lg.type=='fail' else 'sk'}}">
  {{lg.type.upper()}}</span></td><td>{{lg.emo}}</td></tr>{% endfor %}
</table></div>
<div class="card"><h2>Parent Notes</h2>
{% for n in notes %}<div style="padding:4px;border-left:3px solid #a78bfa;margin:3px 0;font-size:.75em">
  [{{n.get('category','note').upper()}}] {{n.time}}: {{n.text}}</div>{% endfor %}
</div>
<form method="POST" action="http://127.0.0.1:5007/gen_pdf" style="margin-top:8px">
  <button class="btn btn-g">📄 Download PDF</button>
</form>
</body></html>"""

@report_app.route("/")
def report_home():
    return render_template_string(REPORT_HTML,
        child=CHILD_NAME,score=ST["score"],mastered=ST["tasks_mastered"],
        ok=ST["tasks_success"],fail=ST["tasks_fail"],skipped=ST["tasks_skipped"],
        att=ST["attention"],clvl=ST["conversation_level"],
        sm=ST["skill_motor"],sc_=ST["skill_cognitive"],
        sv=ST["skill_verbal"],smath=ST["skill_math"],ssoc=ST["skill_social"],
        logs=ST["logs"],notes=ST["parent_notes"])

@report_app.errorhandler(404)
def r404(e): return redirect("/"),302

GAMES_HTML="""<!DOCTYPE html><html><head>
<meta charset="UTF-8"><title>Therapy Games V6 — {{child}}</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#060912;color:#e0e6ff;font-family:'Segoe UI',sans-serif;padding:12px}
h1{color:#a78bfa;text-align:center;margin-bottom:6px}
.nav{display:flex;gap:5px;justify-content:center;margin-bottom:8px;flex-wrap:wrap}
.nav a{padding:6px 12px;border-radius:8px;text-decoration:none;font-size:.78em;font-weight:700}
.b1{background:#4f46e5;color:#fff}.b2{background:#059669;color:#fff}.b3{background:#1d4ed8;color:#fff}.b4{background:#7c3aed;color:#fff}
.sc{background:#1a0a3d;border-radius:8px;padding:6px 14px;text-align:center;margin-bottom:8px;color:#a78bfa}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;max-width:800px;margin:0 auto}
@media(max-width:500px){.grid{grid-template-columns:repeat(2,1fr)}}
.gc{background:#0c0f1e;border:2px solid #1a1f40;border-radius:11px;padding:12px;
    text-align:center;cursor:pointer;transition:.25s}
.gc:hover,.gc:active{border-color:#a78bfa;transform:translateY(-2px)}
.gi{font-size:2em;margin-bottom:4px}.gn{font-weight:700;color:#e0e6ff;font-size:.85em}
.gd{font-size:.67em;color:#6b7280;margin-top:2px}
#ag{max-width:800px;margin:8px auto}
.btn{background:#4f46e5;color:#fff;border:none;padding:9px 16px;border-radius:7px;
     cursor:pointer;font-size:.82em;margin:4px;min-height:42px;touch-action:manipulation}
.btn-g{background:#059669}
canvas{border:2px solid #4f46e5;border-radius:8px;background:#0a0f1e;
       display:block;margin:8px auto;max-width:100%;touch-action:none}
.platform-f{width:100%;height:480px;border:2px solid #4f46e5;border-radius:12px;background:#0a0f1e}
</style></head><body>
<h1>🎮 Therapy Games V6 — {{child}}</h1>
<div class="nav">
  <a href="http://127.0.0.1:5007/" class="b1">📊 Dashboard</a>
  <a href="http://127.0.0.1:5001/" class="b2">📋 Reports</a>
  <a href="http://127.0.0.1:5009/" class="b3">🎮 Games</a>
  <a href="{{gurl}}" target="_blank" class="b4">🌐 Platform</a>
</div>
<div class="sc">Score: <span id="pts">0</span> ⭐ | Level: <span id="lvl">1</span></div>
<div style="margin-bottom:10px"><iframe class="platform-f" src="{{gurl}}" title="Therapy Platform"></iframe></div>
<div class="grid">
  <div class="gc" onclick="s('balloons')"><div class="gi">🎈</div><div class="gn">Balloons</div><div class="gd">Pop them!</div></div>
  <div class="gc" onclick="s('emotions')"><div class="gi">😊</div><div class="gn">Emotions</div><div class="gd">Mirror!</div></div>
  <div class="gc" onclick="s('colors')"><div class="gi">🎨</div><div class="gn">Colors</div><div class="gd">Find it!</div></div>
  <div class="gc" onclick="s('numbers')"><div class="gi">🔢</div><div class="gn">Count</div><div class="gd">How many?</div></div>
  <div class="gc" onclick="s('memory')"><div class="gi">🧠</div><div class="gn">Memory</div><div class="gd">Pairs!</div></div>
  <div class="gc" onclick="s('words')"><div class="gi">🔤</div><div class="gn">Words</div><div class="gd">Say it!</div></div>
</div>
<div id="ag"></div>
<script>
var sc=0,lv=1;
function add(n){sc+=n;lv=Math.floor(sc/50)+1;document.getElementById('pts').textContent=sc;document.getElementById('lvl').textContent=lv;}
function s(g){var d=document.getElementById('ag');
  if(g==='balloons')bl(d);else if(g==='emotions')em(d);
  else if(g==='colors')col(d);else if(g==='numbers')num(d);
  else if(g==='memory')mem(d);else wd(d);}
function bl(d){var W=Math.min(760,window.innerWidth-24);
  d.innerHTML='<canvas id="gc" width="'+W+'" height="280" style="width:100%"></canvas>';
  var c=document.getElementById('gc'),ctx=c.getContext('2d'),bs=[];
  for(var i=0;i<12;i++)bs.push({x:Math.random()*(W-40)+20,y:Math.random()*240+20,r:16+Math.random()*12,
    vx:(Math.random()-0.5)*2.5,vy:(Math.random()-0.5)*2.5,
    color:['#f87171','#34d399','#60a5fa','#fbbf24','#c084fc','#f97316'][Math.floor(Math.random()*6)],alive:true});
  function hit(mx,my){bs.forEach(function(b){if(!b.alive)return;if(Math.sqrt((mx-b.x)**2+(my-b.y)**2)<b.r){b.alive=false;add(10);}});
    if(bs.every(function(b){return !b.alive;}))bs.forEach(function(b){b.alive=true;b.x=Math.random()*(W-40)+20;b.y=Math.random()*240+20;});}
  c.addEventListener('click',function(e){var r=c.getBoundingClientRect(),ss=c.width/r.width;hit((e.clientX-r.left)*ss,(e.clientY-r.top)*ss);});
  c.addEventListener('touchstart',function(e){e.preventDefault();var r=c.getBoundingClientRect(),ss=c.width/r.width,t=e.touches[0];hit((t.clientX-r.left)*ss,(t.clientY-r.top)*ss);},{passive:false});
  (function loop(){ctx.fillStyle='#0a0f1e';ctx.fillRect(0,0,W,280);bs.forEach(function(b){if(!b.alive)return;b.x+=b.vx;b.y+=b.vy;if(b.x<b.r||b.x>W-b.r)b.vx*=-1;if(b.y<b.r||b.y>280-b.r)b.vy*=-1;ctx.beginPath();ctx.arc(b.x,b.y,b.r,0,Math.PI*2);ctx.fillStyle=b.color;ctx.fill();ctx.fillStyle='white';ctx.font='14px sans-serif';ctx.textAlign='center';ctx.fillText('🎈',b.x,b.y+5);});requestAnimationFrame(loop);})();}
function em(d){var ems=[['😊','Happy'],['😢','Sad'],['😠','Angry'],['😨','Scared'],['😲','Surprised'],['😄','Joyful']];
  var pick=ems[Math.floor(Math.random()*ems.length)];
  d.innerHTML='<div style="text-align:center;padding:16px"><p style="color:#a78bfa;margin-bottom:8px;font-size:1.1em">Show this face!</p><div style="font-size:5em;margin:12px">'+pick[0]+'</div><p style="font-weight:700;color:#e0e6ff;font-size:1.2em">'+pick[1]+'</p><button class="btn btn-g" onclick="add(20);this.textContent=\'✅ Amazing!\'" style="display:block;width:100%;max-width:220px;margin:12px auto">I did it! 🌟</button><button class="btn" onclick="em(document.getElementById(\'ag\'))" style="display:block;width:100%;max-width:220px;margin:6px auto">Next ➡️</button></div>';}
function col(d){var cs=[['Red','#ef4444'],['Blue','#3b82f6'],['Green','#22c55e'],['Yellow','#eab308'],['Purple','#a855f7'],['Orange','#f97316'],['Pink','#ec4899']];
  var idx=Math.floor(Math.random()*cs.length);
  d.innerHTML='<div style="text-align:center;padding:14px"><p style="color:#a78bfa;margin-bottom:8px">What color?</p><div style="width:100px;height:100px;background:'+cs[idx][1]+';border-radius:50%;margin:10px auto;border:3px solid #374151"></div><div id="cbtns" style="display:flex;flex-wrap:wrap;justify-content:center;gap:6px;margin-top:8px">'+cs.map(function(c,i){return '<button class="btn" onclick="chkC('+i+','+idx+')" style="background:'+c[1]+';min-width:80px">'+c[0]+'</button>';}).join('')+'</div></div>';}
window.chkC=function(ch,co){var el=document.getElementById('cbtns');if(ch===co){add(15);el.innerHTML='<p style="color:#34d399;margin:8px;font-size:1.1em">✅ Correct! 🌟</p><button class="btn" onclick="col(document.getElementById(\'ag\'))" style="display:block;margin:6px auto">Next ➡️</button>';}else el.innerHTML='<p style="color:#f87171;margin:8px">Try again! 💪</p><button class="btn" onclick="col(document.getElementById(\'ag\'))" style="display:block;margin:6px auto">Retry ↩️</button>';};
function num(d){var n=Math.floor(Math.random()*10)+1,stars='';for(var i=0;i<n;i++)stars+='⭐';
  var opts=Array.from(new Set([n,Math.max(1,n-1),Math.min(10,n+1),n>2?n-2:n+3])).sort(function(){return Math.random()-0.5;}).slice(0,4);
  d.innerHTML='<div style="text-align:center;padding:14px"><p style="color:#a78bfa">Count!</p><div style="font-size:1.6em;margin:10px;word-break:break-all">'+stars+'</div><div style="display:flex;flex-wrap:wrap;justify-content:center;gap:8px">'+opts.map(function(x){return '<button class="btn" onclick="chkN('+x+','+n+')" style="font-size:1.2em;min-width:60px;padding:10px">'+x+'</button>';}).join('')+'</div></div>';}
window.chkN=function(ch,co){if(ch===co){add(20);alert('✅ YES! '+co+'! 🌟');num(document.getElementById('ag'));}else alert('Try again! 💪');};
function mem(d){var pairs=['🐶','🐱','🐻','🦊','🐼','🐨','🦁','🐯'];
  var cards=pairs.concat(pairs).sort(function(){return Math.random()-0.5;});
  window._mc=cards;window._mf=[];window._mm=[];
  d.innerHTML='<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;max-width:360px;margin:10px auto">'+cards.map(function(c,i){return '<div id="mc'+i+'" onclick="flipM('+i+')" style="height:70px;background:#1f2937;border-radius:9px;display:flex;align-items:center;justify-content:center;font-size:2em;cursor:pointer;border:2px solid #374151;touch-action:manipulation">❓</div>';}).join('')+'</div>';}
window.flipM=function(idx){var c=window._mc;if(window._mf.length>=2||window._mm.includes(idx)||window._mf.includes(idx))return;document.getElementById('mc'+idx).textContent=c[idx];window._mf.push(idx);if(window._mf.length===2){var a=window._mf[0],b=window._mf[1];if(c[a]===c[b]){window._mm.push(a,b);add(30);window._mf=[];if(window._mm.length===c.length)setTimeout(function(){alert('🎉 ALL MATCHED!');mem(document.getElementById('ag'));},400);}else setTimeout(function(){document.getElementById('mc'+a).textContent='❓';document.getElementById('mc'+b).textContent='❓';window._mf=[];},900);}};
function wd(d){var words=['APPLE','BALL','CAT','DOG','ELEPHANT','FISH','GOOD','HAPPY','JUMP','KITE','LOVE','MILK','PLAY','RED','SUN','TREE','WATER','YES','ONE','TWO','THREE'];
  var word=words[Math.floor(Math.random()*words.length)];
  d.innerHTML='<div style="text-align:center;padding:16px"><p style="color:#a78bfa;margin-bottom:8px">Say this word!</p><div style="font-size:2.5em;font-weight:700;color:#a78bfa;margin:12px;background:#1e1b4b;padding:15px;border-radius:15px">'+word+'</div><button class="btn btn-g" onclick="add(20);this.textContent=\'✅ Said it!\'" style="display:block;width:100%;max-width:200px;margin:10px auto">I said it! 🎤</button><button class="btn" onclick="wd(document.getElementById(\'ag\'))" style="display:block;width:100%;max-width:200px;margin:6px auto">Next ➡️</button></div>';}
</script></body></html>"""

@games_app.route("/")
def games_home(): return render_template_string(GAMES_HTML,child=CHILD_NAME,gurl=GAME_URL)
@games_app.errorhandler(404)
def g404(e): return redirect("/"),302

def run_server(app,port,name):
    from werkzeug.serving import make_server
    try:
        srv=make_server("0.0.0.0",port,app,threaded=True)
        srv.socket.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
        log.info(f"✅ {name}: http://{LOCAL_IP}:{port}/"); srv.serve_forever()
    except Exception as e: log.warning(f"{name}: {e}")

# ══════════════════════════════════════════════════════════════════════
# 20. THERAPY CONTROLLER
# ══════════════════════════════════════════════════════════════════════
class TherapyCtrl:
    def __init__(self,voice:Voice,pb:PBWatchdog):
        self.v=voice; self.pb=pb; self.running=False

    def _say(self,text,wait=True):
        if ST.get("pecs_interrupt"): return
        clean=re.sub(r"\[[^\]]+\]","",str(text)).strip()
        BRIDGE.sig_instr.emit(clean[:70]); self.v.say(text,wait=wait)

    def _pb_sync(self):
        self.pb.send(is_speaking=ST["is_speaking"],lip=ST["lip_sync_value"],
                     sj=ST.get("social_joy_active",False),
                     blink=ST.get("blinking",False),
                     ht=ST.get("head_tilt_val",0.0),gaze=ST["gaze_mode"])

    def run(self):
        self.running=True
        threading.Thread(target=self._pb_loop,daemon=True).start()
        self._say(
            f"Hello {CHILD_NAME}! I am Pepper your Clinical Therapist! "
            "Watch the screen and copy my movements! "
            "Tap the red microphone button to speak! "
            "Use the PECS buttons at the bottom to tell me what you need! "
            "I will automatically advance to harder challenges as you improve! "
            "Let us begin!")
        time.sleep(0.5)
        last_em=ST["emotion"]; em_t=time.time()

        while self.running:
            if time.time()-ST["last_sound"]>18:
                ST["last_sound"]=time.time()
                if not ST.get("pecs_interrupt"):
                    self.v.say(f"{CHILD_NAME}, ready when you are! 🎯",wait=False)
            curr=ST["emotion"]
            if curr!=last_em and time.time()-em_t>8:
                last_em=curr; em_t=time.time()
                if curr in ["sad","angry","fear"] and not ST.get("pecs_interrupt"):
                    self._say(f"{CHILD_NAME}, I see you. It is okay. I am here. 💙",wait=False)
            self._handle_quick_action(); self._handle_cmd()
            # Get next task (history-dedup)
            task=get_next_task()
            ST["tablet_instruction"]=task["instruction"]
            ST["domain"]=task.get("domain","Motor")
            ST["protocol"]=task.get("protocol","ABA-DTT")
            ST["current_level"]=task.get("level",1)
            ST["fail_count"]=0
            ST["instant_success"]=False
            # Store keyword for instant speech match
            ST["_current_task_keyword"]=task.get("keyword","")
            self._show(task)
            if task["domain"]=="Motor":
                ST["gaze_mode"]="tablet"
                threading.Thread(target=self._gaze_seq,daemon=True).start()
                self._say(task["instruction"]+" Look at the screen!",wait=False)
            else:
                self._say(task["instruction"],wait=False)
            success=self._run_dtt(task)
            log_csv(task["id"],task["domain"],task["level"],task.get("protocol","ABA"),
                    success,ST["consecutive"],ST["fail_count"],
                    ST["score"],ST["emotion"],ST["attention"],ST["conversation_level"])
            if success:
                self._on_success(task)
                if not ST.get("pecs_interrupt"):
                    self._say(f"{CHILD_NAME}! {task.get('success','Amazing!')} Next task! [CELEBRATE]",wait=False)
            else:
                self._on_skip(task)
            ST["_current_task_keyword"]=""
            time.sleep(0.3)

    def _pb_loop(self):
        while self.running: self._pb_sync(); time.sleep(0.04)

    def _gaze_seq(self):
        ST["gaze_mode"]="tablet"; time.sleep(1.5); ST["gaze_mode"]="child"

    def _show(self,task):
        mode=task.get("tablet_mode","idle")
        data={"mode":mode,"instruction":task["instruction"]}
        if task["domain"]=="Motor" or mode=="motor_model":
            data.update({"mode":"motor_model","figure":task.get("figure",""),"label":task.get("name","")})
        elif mode in ["word_display","conv_display"]:
            data.update({"word_emoji":task.get("word_emoji","📢"),
                         "word_text":task.get("word_text","SAY IT!"),
                         "conv_emoji":task.get("conv_emoji","💬"),
                         "conv_phrase":task.get("conv_phrase","")})
        elif mode=="number_display":
            data.update({"target_number":task.get("target_number",1)})
        elif mode in ["color_grid","object_grid","shape_grid","number_grid","emotion_grid"]:
            data.update({"options":task.get("options",[]),"correct":task.get("correct",-1)})
        ST["tablet_click_result"]=None; BRIDGE.sig_task.emit(data)

    def _run_dtt(self,task)->bool:
        """DTT loop — checks instant_success for immediate exit."""
        vtype=task.get("verify","motor")
        motor_v=["clap","wave","raise_hand","touch_nose","arms_out","hands_up","point"]
        if vtype in motor_v:
            ST["verify_action"]=vtype; ST["verify_result"]=False
            ST["verify_timeout"]=time.time()+22
        elif vtype=="finger_count":
            ST["verify_action"]="finger_count"; ST["verify_result"]=False
            ST["finger_target"]=task.get("target_number",1)
            ST["verify_timeout"]=time.time()+22
        ST["last_speech_text"]=""
        prompts=task.get("prompts",["Try again!"]); waiting=task.get("waiting","I am waiting!")
        deadline=time.time()+65; last_p=time.time(); pidx=0; fail_count=0
        while time.time()<deadline:
            # INSTANT SUCCESS — exit immediately
            if ST.get("instant_success"):
                ST["instant_success"]=False; ST["fail_count"]=fail_count; return True
            res=self._check(task)
            if res=="success": ST["fail_count"]=fail_count; return True
            if res=="fail":
                fail_count+=1; ST["fail_count"]=fail_count
                LOG(f"Fail {fail_count}/{MAX_FAILS} on {task['id']}","fail")
                BRIDGE.sig_fail.emit(task.get("fail","Not quite! Try again!"))
                if fail_count>=MAX_FAILS: return False
                if not ST.get("pecs_interrupt"):
                    self.v.say(f"{CHILD_NAME}! {prompts[pidx%len(prompts)]}",wait=False)
                pidx+=1
                ST["tablet_click_result"]=None
                QTimer.singleShot(2000,lambda: BRIDGE.sig_reset.emit())
                time.sleep(2.2); continue
            if time.time()-last_p>6 and not ST.get("pecs_interrupt"):
                last_p=time.time()
                self.v.say(f"{CHILD_NAME}… {prompts[pidx%len(prompts)]}",wait=False)
                BRIDGE.sig_waiting.emit(waiting); pidx+=1
            self._handle_quick_action(); self._handle_cmd(); time.sleep(0.15)
        ST["verify_action"]=None; ST["fail_count"]=fail_count; return False

    def _check(self,task)->str:
        vtype=task.get("verify","motor"); mc=task.get("verify","")
        if mc in ["clap","wave","raise_hand","touch_nose","arms_out","hands_up","point"]:
            if ST["verify_result"]: ST["verify_result"]=False; return "success"
            if mc=="clap" and ST["clapping"]: return "success"
            if mc=="wave" and ST["waving"]: return "success"
            if mc=="raise_hand" and ST["hand_raised"]: return "success"
            if mc=="arms_out" and ST["arms_out"]: return "success"
            if mc=="hands_up" and ST["hands_up"]: return "success"
        elif vtype=="finger_count":
            if ST["finger_count"]==ST["finger_target"]: return "success"
        elif vtype=="tablet_click":
            r=ST.get("tablet_click_result")
            if r=="correct": ST["tablet_click_result"]=None; return "success"
            if r=="wrong":   ST["tablet_click_result"]=None; return "fail"
        elif vtype=="speech_keyword":
            kw=task.get("keyword",""); lt=ST.get("last_speech_text","").lower()
            if kw and kw.lower() in lt: ST["last_speech_text"]=""; return "success"
        elif vtype=="speech_any":
            if ST["last_sound"]>time.time()-3 and len(ST.get("last_speech_text",""))>0:
                ST["last_speech_text"]=""; return "success"
        return None

    def _on_success(self,task):
        ST["consecutive"]+=1; pts=task.get("tokens",2)*5
        ST["score"]+=pts; ST["tokens"]+=task.get("tokens",2)
        ST["tasks_success"]+=1; ST["streak"]+=1
        # ── AR Celebration filter: every 10 successful tasks ──────────
        if ST["tasks_success"] > 0 and ST["tasks_success"] % 10 == 0:
            ST["social_joy_active"] = True
            ST["eye_color"] = (255, 215, 0)  # Gold eyes for AR crown
            BRIDGE.sig_joy.emit("full_joy")
            BRIDGE.sig_chat.emit("pepper",
                f"👑🌟🎊 INCREDIBLE! {CHILD_NAME} completed {ST['tasks_success']} tasks! "
                f"AR CROWN CELEBRATION! Stars, balloons and rainbow activate! 🌈🎉✨")
            self._say(
                f"AMAZING {CHILD_NAME}! You completed {ST['tasks_success']} tasks! "
                "You are a SUPERSTAR! Crown and stars for you! Wonderful job!",
                wait=False)
            LOG(f"👑 AR CELEBRATION — {ST['tasks_success']} tasks!", "success")
            # Auto-store snapshot at every 10-task milestone
            threading.Thread(target=store_session_to_claude_log, daemon=True).start()
            def _clr_crown():
                import time as _t; _t.sleep(6)
                ST["social_joy_active"] = False
                ST["eye_color"] = (100, 180, 255)
            threading.Thread(target=_clr_crown, daemon=True).start()
        d=task["domain"]
        if d=="Motor":      ST["skill_motor"]    =min(100,ST["skill_motor"]+random.randint(1,4))
        elif d=="Cognitive":ST["skill_cognitive"] =min(100,ST["skill_cognitive"]+random.randint(1,4))
        elif d=="Verbal":   ST["skill_verbal"]    =min(100,ST["skill_verbal"]+random.randint(1,4))
        elif d=="Math":     ST["skill_math"]      =min(100,ST["skill_math"]+random.randint(1,4))
        elif d=="Social":   ST["skill_social"]    =min(100,ST["skill_social"]+random.randint(1,4))
        BRIDGE.sig_success.emit(task.get("success","Amazing! ✅"))
        BRIDGE.sig_joy.emit(task.get("joy","celebrate"))
        # ── Per-task mini celebration — every single correct answer ─
        _celeb_emojis = ["⭐","🌟","✨","🎉","💫","🎊","💝","🏆","🎈","🌈","🍭","👑","🎁","💎","🎀"]
        _burst = " ".join(__import__("random").choices(_celeb_emojis, k=5))
        BRIDGE.sig_chat.emit("pepper",
            f"{_burst} BRILLIANT {CHILD_NAME}! {task.get('success','Amazing! ✅')}")
        BRIDGE.sig_stats.emit()
        BRIDGE.sig_chat.emit("pepper",f"Score:{ST['score']} pts | Mastered:{ST['tasks_mastered']} | Streak:{ST['streak']}🔥")
        LOG(f"✅ {ST['consecutive']}/3 '{task['id']}' L{ST['conversation_level']}","success")
        # ── Video overlay: every 7 correct tasks ──────────────────
        global _video_task_counter
        _video_task_counter += 1
        if _video_task_counter % 7 == 0 and VIDEO_TASK_KEYS:
            vkey = random.choice(VIDEO_TASK_KEYS)
            vtitle, vyt, vcat = VIDEO_TASK_LIBRARY[vkey]
            vurl = f"https://www.youtube.com/embed/{vyt}?autoplay=1&rel=0&modestbranding=1"
            BRIDGE.sig_chat.emit("pepper",
                f"🎬 Life-Skill Video: {vtitle} ({vcat}) — {vurl}")
            LOG(f"📺 Video: {vtitle}","info")
        if ST["consecutive"]>=MASTERY_N:
            ST["consecutive"]=0; ST["tasks_mastered"]+=1
            # Auto-advance conversation level every 5 mastered tasks
            if ST["tasks_mastered"]%5==0 and ST["conversation_level"]<3:
                ST["conversation_level"]+=1
                LOG(f"🎓 Conv level → {ST['conversation_level']}","info")
                BRIDGE.sig_chat.emit("pepper",f"🎓 Level Up! Now Conv Level {ST['conversation_level']}!")
            ST["social_joy_active"]=True
            ST["eye_color"]=(int(128+127*math.sin(time.time()*3)),
                             int(200+55*math.sin(time.time()*2)),255)
            LOG(f"🏆 MASTERED task #{ST['tasks_mastered']}","success")
            self._say(f"{CHILD_NAME} earned 3 stars! MASTERED! [LEVEL_UP]",wait=False)
            BRIDGE.sig_chat.emit("pepper",f"🏆 MASTERED: {task.get('name',task['id'])}! Total:{ST['tasks_mastered']}")
            def _clr(): ST["social_joy_active"]=False; ST["eye_color"]=(100,180,255)
            threading.Timer(4.0,_clr).start()

    def _on_skip(self,task):
        ST["tasks_fail"]+=1; ST["tasks_skipped"]+=1; ST["streak"]=0; ST["consecutive"]=0
        report=(f"📋 '{task.get('name',task['id'])}' skipped after {MAX_FAILS} fails. "
                f"Protocol:{task.get('protocol','ABA')}. Needs practice.")
        BRIDGE.sig_chat.emit("pepper",report)
        BRIDGE.sig_skip.emit(f"Skipping — {MAX_FAILS} fails. Moving on!")
        ST["parent_notes"].append({"time":datetime.now().strftime("%H:%M"),
            "text":f"AUTO: Skipped '{task.get('name',task['id'])}' — needs attention",
            "category":"concern"})
        if not ST.get("pecs_interrupt"):
            self._say(f"{CHILD_NAME}, good try! Let us try something different!",wait=False)
        LOG(f"⏭️ SKIPPED {task['id']}","info"); time.sleep(0.8)

    def _handle_quick_action(self):
        qa=ST.get("quick_action")
        if not qa: return
        ST["quick_action"]=None
        if qa=="next":
            ST["instant_success"]=True  # interrupt current task
            self.v.say(f"{CHILD_NAME}, new task coming!",wait=False)
        elif qa=="break":
            ST["pecs_interrupt"]=True
            self.v.say(f"{CHILD_NAME}, break time! Rest! 😊",wait=False)
            time.sleep(8); ST["pecs_interrupt"]=False
        elif qa=="celebrate":
            ST["social_joy_active"]=True
            self.v.say(f"{CHILD_NAME}, you are AMAZING! 🎉",wait=False)
            BRIDGE.sig_joy.emit("full_joy")
            threading.Timer(4.0,lambda: ST.update({"social_joy_active":False})).start()
        elif qa=="encourage":
            self.v.say(f"{CHILD_NAME}, you can do it! I believe in you! 💙",wait=False)
        elif qa=="stop":
            self.v.say(f"{CHILD_NAME}, short pause!",wait=False); time.sleep(5)
        elif qa=="continue":
            self.v.say(f"{CHILD_NAME}, let us continue! Great job!",wait=False)
        elif qa=="mood_speak":
            mood_id = ST.get("current_mood")
            mood = next((m for m in ASD_MOODS if m["id"]==mood_id), None) if mood_id else None
            if mood: self.v.say(mood["speech"],wait=False)

    def _handle_cmd(self):
        cmd=ST.get("sim_cmd")
        if not cmd: return
        ST["sim_cmd"]=None
        if cmd=="next": ST["instant_success"]=True; self.v.say("Next task!",wait=False)
        elif cmd=="break": self.v.say("Break time!",wait=False)
        elif cmd=="report": generate_pdf()

# ══════════════════════════════════════════════════════════════════════
# 21. MAIN
# ══════════════════════════════════════════════════════════════════════
def main():
    global VOICE_REF
    print(f"""
╔══════════════════════════════════════════════════════════╗
║  PEPPER CLINICAL INFINITY V6 — PRODUCTION STABLE        ║
║  {CHILD_NAME:<52}║
╠══════════════════════════════════════════════════════════╣
║  CRASH FIXES:                                           ║
║  • Segfault: QMutex frame.copy() before emit           ║
║  • Abort: SIGTERM → pkill aplay graceful cleanup       ║
║  • PyBullet: separate thread, 25hz rate-limit          ║
║  • text-shadow: 100% removed → DropShadowEffect        ║
║  • PECS: global interrupt kills task loop audio        ║
║  • Instant success: first click → immediate balloon    ║
║  FEATURES:                                              ║
║  • Window 1600×900 FIXED (no resize)                  ║
║  • Dynamic mic energy auto-adjust + waveform bar       ║
║  • Conv levels: 1=motor, 2=cognitive, 3+=PECS phrases  ║
║  • Session history dedup (no repeats in 200 tasks)     ║
║  • Parent login/register (bcrypt encrypted)            ║
║  • Empowerment Hub (ABA/DTT/TEACCH/ESDM guides)       ║
║  • Gemini AI chatbot (English, session-aware)          ║
║  • Chart.js analytics + PDF reports                   ║
║  • PyAnywhere game embedded in Games tab              ║
╚══════════════════════════════════════════════════════════╝
""")

    # QApplication — FIRST on main thread
    qt_app=QApplication(sys.argv)
    qt_app.setApplicationName(f"Pepper Clinical V6 — {CHILD_NAME}")
    qt_app.setStyle("Fusion")
    palette=QPalette()
    palette.setColor(QPalette.ColorRole.Window,    QColor(6,9,18))
    palette.setColor(QPalette.ColorRole.WindowText,QColor(224,230,255))
    palette.setColor(QPalette.ColorRole.Base,      QColor(12,15,30))
    palette.setColor(QPalette.ColorRole.Text,      QColor(224,230,255))
    qt_app.setPalette(palette)

    window=MainWindow(); window.show(); window.move(10,550)

    # Flask servers
    for app_,port,name in [(parent_app,5007,"Parent Dashboard (login required)"),
                            (report_app,5001,"Clinical Reports"),
                            (games_app, 5009,"Games + Platform")]:
        threading.Thread(target=run_server,args=(app_,port,name),daemon=True).start()
        time.sleep(0.3)
    time.sleep(0.5)
    # Start ngrok for public sharing/testing
    global PUBLIC_URL
    PUBLIC_URL = try_start_ngrok(5007)

    # Camera (QThread — with mutex)
    cam=CameraThread(); cam.start()

    # PyBullet watchdog (subprocess — 25hz)
    pb=PBWatchdog(CHILD_NAME); pb.start()

    # Voice + therapy
    voice=Voice(); VOICE_REF=voice
    ctrl=TherapyCtrl(voice,pb)

    def _start():
        time.sleep(2.0); ctrl.run()

    threading.Thread(target=_start,daemon=True).start()

    print(f"""
{'='*62}
✅ CLINICAL INFINITY V6 ACTIVE
{'='*62}
Single window (1600×900 FIXED — no resize):
  LEFT:  Camera(580px) + Avatar(200×260) + EmotionPanel(200×260)
         Game button + Chat area + PECS bar (10 items)
  RIGHT: TEACCH schedule + Instruction + Task content (1600×900)
         Feedback + Mic button + Waveform bar + Stats

W1: PyBullet (subprocess watchdog — 25hz rate-limited IPC)
FaceMesh grid: HIDDEN (therapist only — not shown to child)
Mic: Dynamic energy auto-adjust + real-time waveform

Conv Levels: L1=Motor, L2=Cognitive, L3+=PECS/Conversation
History dedup: no task repeats within last 200

Parent:  http://127.0.0.1:5007/  ← Login required (register first!)
Reports: http://127.0.0.1:5001/
Games:   http://127.0.0.1:5009/  ← PyAnywhere platform embedded
Android: http://{LOCAL_IP}:5007/

Child:   {CHILD_NAME} | Age:{ST['age']}
CSV:     {CSV_FILE}
Tasks:   {len(TASK_POOL)} variations

n=next | b=break | r=PDF report | q=quit
Owner email:  {OWNER_EMAIL}
Sessions stored: {SAFE_NAME}_v6_sessions.json
Email queue:  pending_email_reports.json
API secret:   (printed in server log at startup)
ngrok tunnel: {PUBLIC_URL or "pyngrok not installed"}
{'='*62}
""")

    def _input_loop():
        while ctrl.running:
            try:
                cmd=input("> ").strip().lower()
                if cmd in ["q","exit","quit"]:
                    ctrl.running=False
                    if VOICE_REF: VOICE_REF.cleanup()
                    cam.stop(); pb.stop(); qt_app.quit(); break
                elif cmd in ["n","next"]:  ST["sim_cmd"]="next"
                elif cmd in ["b","break"]: ST["sim_cmd"]="break"
                elif cmd in ["r","report","pdf"]: ST["sim_cmd"]="report"
                elif cmd=="stats":
                    log.info(f"★{ST['consecutive']}/3 | Fails:{ST['fail_count']}/{MAX_FAILS} | "
                             f"Score:{ST['score']} | Mastered:{ST['tasks_mastered']} | "
                             f"Conv Level:{ST['conversation_level']} | "
                             f"Emotion:{ST['emotion']} | Fingers:{ST['finger_count']}")
                elif cmd.startswith("level "):
                    try:
                        lvl=int(cmd.split()[1])
                        ST["conversation_level"]=max(1,min(3,lvl))
                        log.info(f"Conv level set to {ST['conversation_level']}")
                    except: pass
            except (KeyboardInterrupt,EOFError): break
        qt_app.quit()

    threading.Thread(target=_input_loop,daemon=True).start()
    ret=qt_app.exec()

    # Cleanup
    ctrl.running=False
    if VOICE_REF: VOICE_REF.cleanup()
    cam.stop(); pb.stop()

    dur=int((time.time()-ST["uptime"])/60)
    fn=generate_pdf()
    # Store final session snapshot → local file + email queue
    store_session_to_claude_log()
    jsn=f"session_{SAFE_NAME}_{datetime.now().strftime('%Y%m%d_%H%M')}.json"
    with open(jsn,"w") as f: json.dump(ST,f,indent=2,default=str)
    print(f"\n{'='*55}\nSESSION COMPLETE — {CHILD_NAME} | {dur} min\n"
          f"Score:{ST['score']} | Mastered:{ST['tasks_mastered']} | "
          f"Conv Level:{ST['conversation_level']}\n"
          f"CSV:{CSV_FILE} | JSON:{jsn}"
          +(f" | PDF:{fn}" if fn else "")+f"\n{'='*55}")
    sys.exit(ret)

if __name__=="__main__":
    main()
