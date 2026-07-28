#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  Pepper Clinical Infinity V6+V8 — Full Enhanced Edition          ║
║  All V8 features integrated into V6 Python/PyBullet environment  ║
║  ✅ 5 Color Themes (Blue/Green/Gray/Colorful/Pink)               ║
║  ✅ 50 PECS Cards                                                 ║
║  ✅ 8 Calm Music Tracks (generated — no audio files needed)      ║
║  ✅ 13 Mood Modes with auto music selection                       ║
║  ✅ 👏 Clap sound after every correct answer                      ║
║  ✅ 🔴 Live Monitor Window in Parent Dashboard                    ║
║  ✅ 5 Voice Profiles                                              ║
║  ✅ Zero task repetition per child (SQLite history)               ║
║  ✅ 100,000 tasks across 3 years (10 domains × time progression)  ║
║  ✅ 🎊 Special celebration every 10 correct answers               ║
║  ✅ 📺 YouTube daily-life videos (Goally + educational channels)  ║
║  ✅ 👁️  Live child session window on parent dashboard             ║
╚══════════════════════════════════════════════════════════════════╝
"""
import os,sys,warnings,ctypes,signal,logging,threading,subprocess,socket
import time,random,math,re,json,csv,base64,wave,tempfile,secrets,sqlite3
from datetime import datetime,timedelta
from io import BytesIO
from collections import deque

os.environ.update({
    "TF_CPP_MIN_LOG_LEVEL":"3","MEDIAPIPE_DISABLE_GPU":"1",
    "PYTHONWARNINGS":"ignore","OPENCV_LOG_LEVEL":"ERROR",
    "QT_LOGGING_RULES":"*.debug=false","QT_QPA_PLATFORM":"xcb",
    "OMP_NUM_THREADS":"2",
})
warnings.filterwarnings("ignore")
logging.basicConfig(level=logging.INFO,
    format="[%(asctime)s] %(message)s",datefmt="%H:%M:%S")
log=logging.getLogger("pepper")

try:
    _a=ctypes.cdll.LoadLibrary("libasound.so.2")
    _a.snd_lib_error_set_handler(ctypes.c_void_p(None))
except: pass
def _exit(s,f):
    try: os.system("pkill -f aplay 2>/dev/null")
    except: pass
    sys.exit(0)
signal.signal(signal.SIGTERM,_exit); signal.signal(signal.SIGINT,_exit)

import cv2,numpy as np
from PIL import Image,ImageDraw
import mediapipe as mp
import pyttsx3,speech_recognition as sr
try: from faster_whisper import WhisperModel as FW; _FW=True
except: _FW=False
try: import google.generativeai as genai; _GENAI=True
except: _GENAI=False
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import (SimpleDocTemplate,Paragraph,
        Spacer,Table,TableStyle)
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors as RLC; _PDF=True
except: _PDF=False

from flask import (Flask,render_template_string,jsonify,request,
                   redirect,send_file)
from PyQt6.QtWidgets import (
    QApplication,QMainWindow,QWidget,QVBoxLayout,QHBoxLayout,
    QLabel,QPushButton,QFrame,QGridLayout,QLineEdit,QTextEdit,
    QProgressBar,QScrollArea,QComboBox,QSlider,
)
from PyQt6.QtCore import (Qt,QTimer,pyqtSignal,QObject,QThread,
    QMutex,QMutexLocker,QRect)
from PyQt6.QtGui import (QFont,QColor,QPalette,QPixmap,QImage,
    QPainter,QLinearGradient,QBrush,QPen)
import webbrowser

# ══════════════════════════════════════════════════════════════════
# V8 THEMES
# ══════════════════════════════════════════════════════════════════
THEMES={
    "blue":{"name":"🔵 Blue","bg":QColor(4,11,26),"bg2":QColor(10,20,40),
        "accent":QColor(74,158,255),"accent2":QColor(26,95,212),
        "text":QColor(205,228,255),"card":QColor(8,22,50),
        "success":QColor(52,211,153),
        "fk_bg":"#040b1a","fk_card":"#0a1428","fk_acc":"#4a9eff",
        "fk_txt":"#cde4ff","fk_b3":"rgba(255,255,255,.06)"},
    "green":{"name":"🟢 Green","bg":QColor(5,26,10),"bg2":QColor(10,40,18),
        "accent":QColor(66,201,122),"accent2":QColor(21,128,61),
        "text":QColor(200,255,220),"card":QColor(8,38,16),
        "success":QColor(52,211,153),
        "fk_bg":"#051a0a","fk_card":"#0a2812","fk_acc":"#42c97a",
        "fk_txt":"#c8ffd4","fk_b3":"rgba(255,255,255,.06)"},
    "gray":{"name":"⬜ Gray","bg":QColor(17,17,20),"bg2":QColor(28,28,32),
        "accent":QColor(152,152,184),"accent2":QColor(100,100,130),
        "text":QColor(220,220,235),"card":QColor(24,24,28),
        "success":QColor(152,200,152),
        "fk_bg":"#111114","fk_card":"#1c1c20","fk_acc":"#9898b8",
        "fk_txt":"#dcdceb","fk_b3":"rgba(255,255,255,.06)"},
    "colorful":{"name":"🌈 Colorful","bg":QColor(13,0,32),"bg2":QColor(26,0,53),
        "accent":QColor(255,68,221),"accent2":QColor(160,32,180),
        "text":QColor(255,240,255),"card":QColor(20,0,45),
        "success":QColor(100,255,200),
        "fk_bg":"#0d0020","fk_card":"#1a0035","fk_acc":"#ff44dd",
        "fk_txt":"#fff0ff","fk_b3":"rgba(255,255,255,.06)"},
    "pink":{"name":"🩷 Pink","bg":QColor(14,10,16),"bg2":QColor(26,16,32),
        "accent":QColor(255,136,204),"accent2":QColor(173,20,87),
        "text":QColor(255,230,245),"card":QColor(20,12,28),
        "success":QColor(200,255,200),
        "fk_bg":"#0e0a10","fk_card":"#1a1020","fk_acc":"#ff88cc",
        "fk_txt":"#ffe6f5","fk_b3":"rgba(255,255,255,.06)"},
}
CURRENT_THEME="blue"
def get_theme(): return THEMES.get(CURRENT_THEME,THEMES["blue"])

# ══════════════════════════════════════════════════════════════════
# V8 MOODS
# ══════════════════════════════════════════════════════════════════
ASD_MOODS=[
    {"id":"calm","em":"😌","label":"Calm","music":"nature","anim":1.0,
     "speech":"You look calm and ready! Perfect for learning today!"},
    {"id":"happy","em":"😊","label":"Happy","music":"upbeat","anim":1.2,
     "speech":"Your happiness makes me happy! Let us have fun learning!"},
    {"id":"excited","em":"🤩","label":"Excited","music":"upbeat","anim":1.3,
     "speech":"Wow you are excited! Let us channel that energy into learning!"},
    {"id":"anxious","em":"😰","label":"Anxious","music":"nature","anim":0.7,
     "speech":"I am here with you. We will take it slow today. You are safe."},
    {"id":"sad","em":"😢","label":"Sad","music":"nature","anim":0.8,
     "speech":"I see you are feeling sad. I am here. We can do gentle activities."},
    {"id":"angry","em":"😠","label":"Angry","music":"nature","anim":0.7,
     "speech":"It is okay to feel angry. Let us breathe together and start slowly."},
    {"id":"overwhelmed","em":"😵","label":"Overwhelmed","music":"white","anim":0.6,
     "speech":"Let us take a break. Breathe in and out. I am here."},
    {"id":"tired","em":"😴","label":"Tired","music":"sleep","anim":0.6,
     "speech":"You seem tired. We will do gentle activities. Take your time."},
    {"id":"silly","em":"🤪","label":"Silly","music":"upbeat","anim":1.4,
     "speech":"Haha you are being silly today! That is wonderful! Let us have fun!"},
    {"id":"focused","em":"🧐","label":"Focused","music":"focus","anim":1.0,
     "speech":"You are focused and ready! This is going to be a great session!"},
    {"id":"scared","em":"😨","label":"Scared","music":"nature","anim":0.7,
     "speech":"Do not worry. I will be gentle today. You are completely safe."},
    {"id":"sensory","em":"🙉","label":"Sensory","music":"white","anim":0.6,
     "speech":"I understand. Let us keep things quiet and calm today."},
    {"id":"rainbow","em":"🌈","label":"Rainbow","music":"upbeat","anim":1.3,
     "speech":"You are shining like a rainbow today! Let us celebrate and learn!"},
]
CURRENT_MOOD=ASD_MOODS[0]

# ══════════════════════════════════════════════════════════════════
# V8 MUSIC ENGINE — generated tones
# ══════════════════════════════════════════════════════════════════
MUSIC_TRACKS=[
    {"id":"nature","name":"Forest Rain","em":"🌧️","freq":200,"style":"brown"},
    {"id":"ocean","name":"Ocean Waves","em":"🌊","freq":180,"style":"sine"},
    {"id":"sleep","name":"Sleep 432Hz","em":"😴","freq":432,"style":"sine"},
    {"id":"upbeat","name":"Happy Rhythm","em":"🎉","freq":528,"style":"pulse"},
    {"id":"focus","name":"Focus 60BPM","em":"🎯","freq":396,"style":"sine"},
    {"id":"white","name":"White Noise","em":"⬜","freq":0,"style":"white"},
    {"id":"lullaby","name":"Lullaby","em":"🎵","freq":264,"style":"sine"},
    {"id":"piano","name":"Soft Piano","em":"🎹","freq":330,"style":"harmonic"},
]

class MusicEngine:
    def __init__(self):
        self._proc=None; self._playing=False
        self._lock=threading.Lock(); self._vol=0.3; self._current=None

    def _gen_tone(self,track,duration=20,sr=22050):
        freq=track["freq"]; style=track["style"]
        t=np.linspace(0,duration,int(sr*duration),False)
        if style=="white":
            wav=np.random.normal(0,.15,len(t))
        elif style=="brown":
            wav=np.cumsum(np.random.normal(0,1,len(t)))*.01
        elif style=="pulse":
            wav=(np.sin(2*np.pi*freq*t)*.3+
                 np.sin(2*np.pi*freq*1.5*t)*.1+
                 np.sin(2*np.pi*(freq/2)*t)*.15)
        elif style=="harmonic":
            wav=(np.sin(2*np.pi*freq*t)*.25+
                 np.sin(2*np.pi*freq*2*t)*.12+
                 np.sin(2*np.pi*freq*3*t)*.06)
        else:
            wav=(np.sin(2*np.pi*freq*t)*.25+
                 np.sin(2*np.pi*(freq*.5)*t)*.1)
        mx=np.max(np.abs(wav)) or 1
        wav=(wav/mx*self._vol*32767).astype(np.int16)
        with tempfile.NamedTemporaryFile(suffix=".wav",delete=False) as f:
            path=f.name
        with wave.open(path,"wb") as wf:
            wf.setnchannels(1); wf.setsampwidth(2)
            wf.setframerate(sr); wf.writeframes(wav.tobytes())
        return path

    def play(self,track_id):
        track=next((t for t in MUSIC_TRACKS if t["id"]==track_id),MUSIC_TRACKS[0])
        if self._current==track_id and self._playing: return
        self.stop(); self._current=track_id; self._playing=True
        threading.Thread(target=self._loop,args=(track,),daemon=True).start()
        log.info(f"🎵 Music: {track['name']}")

    def _loop(self,track):
        while self._playing:
            try:
                wav=self._gen_tone(track)
                self._proc=subprocess.Popen(
                    ["aplay","-q",wav],
                    stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                self._proc.wait()
                try: os.unlink(wav)
                except: pass
            except: break

    def stop(self):
        self._playing=False; self._current=None
        with self._lock:
            if self._proc:
                try: self._proc.terminate()
                except: pass
                self._proc=None

    def set_volume(self,v):
        self._vol=max(0.0,min(1.0,v))

MUSIC_ENGINE=MusicEngine()

# ══════════════════════════════════════════════════════════════════
# CLAP SOUND — generated procedurally
# ══════════════════════════════════════════════════════════════════
_CLAP_WAV=None

def _gen_clap():
    sr=22050; dur=0.35
    t=np.linspace(0,dur,int(sr*dur),False)
    noise=np.random.normal(0,1,len(t))
    decay=np.exp(-t*18)
    res=np.sin(2*np.pi*800*t)*np.exp(-t*25)*.3
    wav=((noise*decay+res)*.7*32767).astype(np.int16)
    with tempfile.NamedTemporaryFile(suffix=".wav",delete=False) as f:
        path=f.name
    with wave.open(path,"wb") as wf:
        wf.setnchannels(1); wf.setsampwidth(2)
        wf.setframerate(sr); wf.writeframes(wav.tobytes())
    return path

def _pregen_clap():
    global _CLAP_WAV
    try: _CLAP_WAV=_gen_clap()
    except: pass

threading.Thread(target=_pregen_clap,daemon=True).start()

def play_clap():
    def _p():
        global _CLAP_WAV
        if not _CLAP_WAV or not os.path.exists(_CLAP_WAV):
            try: _CLAP_WAV=_gen_clap()
            except: return
        try:
            p=subprocess.Popen(["aplay","-q",_CLAP_WAV],
                stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            p.wait(timeout=2)
        except: pass
    threading.Thread(target=_p,daemon=True).start()

# ══════════════════════════════════════════════════════════════════
# V8 PECS — 50 items
# ══════════════════════════════════════════════════════════════════
PECS_ITEMS=[
    # Core (32)
    ("🤲","Want","I want this"),("➕","More","I want more"),
    ("🆘","Help","I need help"),("🍎","Food","I want food"),
    ("💧","Water","I want water"),("🚽","Toilet","I need the toilet"),
    ("😴","Tired","I am tired"),("🤕","Pain","I am in pain"),
    ("🏠","Home","I want to go home"),("👍","Good","I am good"),
    ("😊","Happy","I feel happy"),("😢","Sad","I feel sad"),
    ("😠","Angry","I feel angry"),("😨","Scared","I am scared"),
    ("🎮","Play","I want to play"),("🎵","Music","I want music"),
    ("☕","Break","I need a break"),("✅","Yes","Yes"),
    ("❌","No","No"),("🙏","Please","Please"),
    ("🙌","Thanks","Thank you"),("👋","Hello","Hello"),
    ("👋","Bye","Goodbye"),("🤗","Hug","I want a hug"),
    ("🤫","Quiet","I need quiet"),("🔊","Loud","Too loud"),
    ("👩","Mama","I want mama"),("👨","Baba","I want baba"),
    ("🏁","Done","I am done"),("🔄","Again","Do it again"),
    ("⏳","Wait","Please wait"),("🛑","Stop","Please stop"),
    # Daily life (18)
    ("☀️","Morning","Good morning"),("🪥","Teeth","I brush my teeth"),
    ("🚿","Wash","I wash my face"),("👕","Dress","I get dressed"),
    ("🥣","Breakfast","I eat breakfast"),("🧼","Hands","I wash my hands"),
    ("📚","School","I go to school"),("🛁","Bath","I want a bath"),
    ("🌙","Night","Good night"),("😋","Hungry","I am hungry"),
    ("🥛","Milk","I want milk"),("🍞","Bread","I want bread"),
    ("🌳","Outside","I want to go outside"),("📺","TV","I want TV"),
    ("✏️","Draw","I want to draw"),("🐾","Pet","I want my pet"),
    ("🎨","Art","I want art"),("⚽","Ball","I want ball"),
]

# ══════════════════════════════════════════════════════════════════
# VOICE PROFILES
# ══════════════════════════════════════════════════════════════════
VOICE_PROFILES=[
    {"id":"friendly","name":"😊 Friendly","rate":165,"volume":1.0},
    {"id":"calm",    "name":"😌 Calm",    "rate":140,"volume":0.85},
    {"id":"energetic","name":"⚡ Energetic","rate":190,"volume":1.0},
    {"id":"warm",    "name":"🤗 Warm",    "rate":150,"volume":0.9},
    {"id":"clear",   "name":"🎯 Clear",   "rate":155,"volume":0.95},
]

# ══════════════════════════════════════════════════════════════════
# SETUP
# ══════════════════════════════════════════════════════════════════
def kill_port(p):
    try: os.system(f"fuser -k {p}/tcp 2>/dev/null")
    except: pass
kill_port(5007)

def get_ip():
    try:
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        s.connect(("8.8.8.8",80)); ip=s.getsockname()[0]; s.close(); return ip
    except: return "127.0.0.1"

LOCAL_IP=get_ip(); GEMINI_KEY="AIzaSyDEdleVKiQ5E00wMcjMbji0G9JcYT2TvE8"
print("\n"+"═"*62)
print("  Pepper Clinical V6+V8 — Enhanced Edition")
print("  5 Themes | 50 PECS | Music | Moods | Clap | Live Monitor")
print("═"*62)
CHILD_NAME=input("\n👦 Child name: ").strip() or "Child"
CHILD_AGE =input("   Age (default 6): ").strip() or "6"
SAFE_NAME =re.sub(r"[^a-zA-Z0-9_]","_",CHILD_NAME)
CSV_FILE  =f"{SAFE_NAME}_v6v8.csv"
with open(CSV_FILE,"w",newline="",encoding="utf-8-sig") as f:
    csv.writer(f).writerow(["Time","Child","Task","Domain","Protocol",
        "Result","Score","Emotion","ConvLevel","Time_ms"])

def log_csv(tid,dom,proto,result,sc,em,clvl,ms):
    try:
        with open(CSV_FILE,"a",newline="",encoding="utf-8-sig") as f:
            csv.writer(f).writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                CHILD_NAME,tid,dom,proto,"success" if result else "fail",
                sc,em,clvl,int(ms)])
    except: pass

if _GENAI:
    try: genai.configure(api_key=GEMINI_KEY)
    except: pass

# ── SQLite ─────────────────────────────────────────────────────────
_DB=os.path.expanduser("~/pepper_duo/children.db")
os.makedirs(os.path.dirname(_DB),exist_ok=True)

def _db(): return sqlite3.connect(_DB)

def init_db():
    conn=_db(); c=conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS children(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE,age INTEGER DEFAULT 6,
        asd_level INTEGER DEFAULT 2,notes TEXT DEFAULT '',created_at TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS sessions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        child_name TEXT,date TEXT,score INTEGER DEFAULT 0,
        tasks_ok INTEGER DEFAULT 0,tasks_fail INTEGER DEFAULT 0,
        duration_min INTEGER DEFAULT 0,
        skill_motor REAL DEFAULT 50,skill_cognitive REAL DEFAULT 50,
        skill_verbal REAL DEFAULT 50,skill_math REAL DEFAULT 50,
        skill_social REAL DEFAULT 50,emotion TEXT,conv_level INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS task_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        child_name TEXT,task_base_id TEXT,completed_at TEXT,result TEXT)""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_th ON task_history(child_name,task_base_id)")
    conn.commit(); conn.close()

init_db()

def db_get_done(cname):
    conn=_db()
    rows=conn.execute(
        "SELECT DISTINCT task_base_id FROM task_history WHERE child_name=?",(cname,)).fetchall()
    conn.close(); return set(r[0] for r in rows)

def db_add_task(cname,base_id,result="success"):
    conn=_db()
    conn.execute("INSERT INTO task_history(child_name,task_base_id,completed_at,result) VALUES(?,?,?,?)",
        (cname,base_id,datetime.now().strftime("%Y-%m-%d %H:%M:%S"),result))
    conn.commit(); conn.close()

def db_reset_tasks(cname):
    conn=_db()
    conn.execute("DELETE FROM task_history WHERE child_name=?",(cname,))
    conn.commit(); conn.close(); log.info(f"✅ Tasks reset for {cname}")

def db_save_session(cname,score,ok,fail,dur,skills,emotion,clvl):
    conn=_db()
    conn.execute("""INSERT INTO sessions(child_name,date,score,tasks_ok,tasks_fail,
        duration_min,skill_motor,skill_cognitive,skill_verbal,skill_math,skill_social,
        emotion,conv_level) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (cname,datetime.now().strftime("%Y-%m-%d %H:%M"),score,ok,fail,dur,
         skills.get("motor",50),skills.get("cognitive",50),skills.get("verbal",50),
         skills.get("math",50),skills.get("social",50),emotion,clvl))
    conn.commit(); conn.close()

def db_get_sessions(cname):
    conn=_db()
    rows=conn.execute(
        "SELECT date,score,tasks_ok,tasks_fail,duration_min,emotion,conv_level FROM sessions WHERE child_name=? ORDER BY date DESC",(cname,)).fetchall()
    conn.close()
    return [{"date":r[0],"score":r[1],"ok":r[2],"fail":r[3],"dur":r[4],"emotion":r[5],"level":r[6]} for r in rows]

_child_done=db_get_done(CHILD_NAME)
log.info(f"✅ Loaded {len(_child_done)} done tasks for {CHILD_NAME}")

# ══════════════════════════════════════════════════════════════════
# TASK DATA + POOL
# ══════════════════════════════════════════════════════════════════
COLORS=[{"id":"red","color":"#ef4444","label":"🔴 Red"},{"id":"blue","color":"#3b82f6","label":"🔵 Blue"},
    {"id":"green","color":"#22c55e","label":"🟢 Green"},{"id":"yellow","color":"#eab308","label":"🟡 Yellow"},
    {"id":"purple","color":"#a855f7","label":"🟣 Purple"},{"id":"orange","color":"#f97316","label":"🟠 Orange"},
    {"id":"pink","color":"#ec4899","label":"🩷 Pink"},{"id":"brown","color":"#92400e","label":"🟫 Brown"},
    {"id":"white","color":"#e2e8f0","label":"⬜ White"},{"id":"black","color":"#1e293b","label":"⬛ Black"}]
ANIMALS=[{"id":"dog","emoji":"🐶","label":"Dog"},{"id":"cat","emoji":"🐱","label":"Cat"},
    {"id":"lion","emoji":"🦁","label":"Lion"},{"id":"elephant","emoji":"🐘","label":"Elephant"},
    {"id":"rabbit","emoji":"🐰","label":"Rabbit"},{"id":"bear","emoji":"🐻","label":"Bear"},
    {"id":"monkey","emoji":"🐵","label":"Monkey"},{"id":"tiger","emoji":"🐯","label":"Tiger"},
    {"id":"fish","emoji":"🐟","label":"Fish"},{"id":"bird","emoji":"🐦","label":"Bird"},
    {"id":"cow","emoji":"🐄","label":"Cow"},{"id":"horse","emoji":"🐎","label":"Horse"}]
FRUITS=[{"id":"apple","emoji":"🍎","label":"Apple"},{"id":"banana","emoji":"🍌","label":"Banana"},
    {"id":"orange","emoji":"🍊","label":"Orange"},{"id":"grapes","emoji":"🍇","label":"Grapes"},
    {"id":"strawberry","emoji":"🍓","label":"Strawberry"},{"id":"mango","emoji":"🥭","label":"Mango"},
    {"id":"watermelon","emoji":"🍉","label":"Watermelon"},{"id":"peach","emoji":"🍑","label":"Peach"},
    {"id":"pear","emoji":"🍐","label":"Pear"},{"id":"cherry","emoji":"🍒","label":"Cherry"}]
SHAPES=[{"id":"circle","emoji":"⭕","label":"Circle"},{"id":"square","emoji":"⬛","label":"Square"},
    {"id":"triangle","emoji":"🔺","label":"Triangle"},{"id":"star","emoji":"⭐","label":"Star"},
    {"id":"heart","emoji":"❤️","label":"Heart"},{"id":"diamond","emoji":"💎","label":"Diamond"}]
EMOTIONS_ITEMS=[{"id":"happy","emoji":"😊","label":"Happy"},{"id":"sad","emoji":"😢","label":"Sad"},
    {"id":"angry","emoji":"😠","label":"Angry"},{"id":"scared","emoji":"😨","label":"Scared"},
    {"id":"surprised","emoji":"😲","label":"Surprised"},{"id":"tired","emoji":"😴","label":"Tired"}]
FOODS=[{"id":"rice","emoji":"🍚","label":"Rice"},{"id":"bread","emoji":"🍞","label":"Bread"},
    {"id":"egg","emoji":"🥚","label":"Egg"},{"id":"milk","emoji":"🥛","label":"Milk"},
    {"id":"cheese","emoji":"🧀","label":"Cheese"},{"id":"soup","emoji":"🍲","label":"Soup"}]
VEHICLES=[{"id":"car","emoji":"🚗","label":"Car"},{"id":"bus","emoji":"🚌","label":"Bus"},
    {"id":"train","emoji":"🚂","label":"Train"},{"id":"airplane","emoji":"✈️","label":"Airplane"},
    {"id":"boat","emoji":"⛵","label":"Boat"},{"id":"bicycle","emoji":"🚲","label":"Bicycle"}]
BODY=[{"id":"head","emoji":"🗣️","label":"Head"},{"id":"eye","emoji":"👁️","label":"Eye"},
    {"id":"ear","emoji":"👂","label":"Ear"},{"id":"nose","emoji":"👃","label":"Nose"},
    {"id":"mouth","emoji":"👄","label":"Mouth"},{"id":"hand","emoji":"✋","label":"Hand"},
    {"id":"foot","emoji":"🦶","label":"Foot"},{"id":"arm","emoji":"💪","label":"Arm"}]
MOTORS=[
    {"id":"clap","name":"👏 Clap","verify":"clap","instruction":"Clap your hands!",
     "waiting":"Clap now! 👏","success":"Great clapping! ✅","fail":"Put hands together!",
     "prompts":["Clap!","Hands together!","Like this! 👏"]},
    {"id":"wave","name":"👋 Wave","verify":"wave","instruction":"Wave your hand!",
     "waiting":"Wave now! 👋","success":"Excellent! ✅","fail":"Move hand side to side!",
     "prompts":["Wave!","Hello!","Side to side!"]},
    {"id":"raise_hand","name":"✋ Raise Hand","verify":"raise_hand",
     "instruction":"Raise your hand up high!","waiting":"Hand up! ✋",
     "success":"Perfect! ✅","fail":"Lift arm above head!","prompts":["Raise it!","Up high!"]},
    {"id":"touch_nose","name":"👆 Touch Nose","verify":"touch_nose",
     "instruction":"Touch your nose!","waiting":"Touch nose! 👆",
     "success":"You touched your nose! ✅","fail":"Point to your nose!",
     "prompts":["Nose!","Touch it!"]},
    {"id":"arms_out","name":"🤸 Arms Out","verify":"arms_out",
     "instruction":"Stretch arms out wide!","waiting":"Arms out! 🤸",
     "success":"Like an airplane! ✅","fail":"Open arms to sides!",
     "prompts":["To the sides!","Like airplane!"]},
    {"id":"hands_up","name":"🙌 Hands Up","verify":"hands_up",
     "instruction":"Raise both hands up!","waiting":"Both hands up! 🙌",
     "success":"Star pose! ✅","fail":"Both arms above head!","prompts":["Both hands!","Star!"]},
    {"id":"jump","name":"🦘 Jump","verify":"jump","instruction":"Jump!",
     "waiting":"Jump! 🦘","success":"Great jump! ✅","fail":"Jump up!",
     "prompts":["Jump!","Up!","Boing!"]},
    {"id":"point","name":"👉 Point","verify":"point","instruction":"Point your finger!",
     "waiting":"Point! 👉","success":"Great! ✅","fail":"Extend index finger!",
     "prompts":["Point!","Finger forward!"]},
]
WORDS=["apple","ball","cat","dog","elephant","fish","good","happy","jump","kite","love",
    "milk","play","red","sun","tree","water","yes","no","one","two","three","four","five",
    "six","seven","eight","nine","ten","blue","green","bird","book","cup","door","eye",
    "foot","hand","head","nose","arm","leg","big","small","hot","cold","up","down",
    "in","out","help","stop","come","sit","run","walk","eat","drink","sleep","mum","dad"]
SOCIAL=["hello","thank you","please","I want more","help me","yes","no","goodbye",
    "sorry","I love you","how are you","I want","I need","good morning","I am fine",
    "good night","I am hungry","well done","can I","I am happy"]

def _grid(items,prefix,domain,protocol,tokens):
    tgt=random.choice(items)
    others=[x for x in items if x["id"]!=tgt["id"]]
    dis=random.sample(others,min(3,len(others)))
    opts=[tgt]+dis; random.shuffle(opts)
    cor=next(i for i,o in enumerate(opts) if o["id"]==tgt["id"])
    lbl=tgt.get("label",tgt["id"])
    return {"id":f"{prefix}_{tgt['id']}_{random.randint(0,99999)}",
            "base_id":f"{prefix}_{tgt['id']}","domain":domain,"protocol":protocol,
            "name":lbl,"instruction":f"Where is {lbl}? Tap it!",
            "waiting":f"Find {lbl}!","success":f"Correct! {lbl}! ✅",
            "fail":f"That is {lbl}!","tablet_mode":"grid","options":opts,"correct":cor,
            "tokens":tokens,"joy":"celebrate",
            "prompts":[f"Where is {lbl}?","Look carefully!","You can do it!"],
            "verify":"tablet_click"}


# ══════════════════════════════════════════════════════════════════
# YOUTUBE VIDEOS — Goally + educational daily life tasks
# ══════════════════════════════════════════════════════════════════
YOUTUBE_VIDEOS=[
    # Goally App Channel — daily life skills
    {"id":"yt_handwash","title":"🧼 How to Wash Hands","url":"https://www.youtube.com/watch?v=3PmVJQUCm4E",
     "embed":"https://www.youtube.com/embed/3PmVJQUCm4E","domain":"Daily","category":"hygiene",
     "desc":"Step-by-step hand washing technique for children"},
    {"id":"yt_brush","title":"🪥 How to Brush Teeth","url":"https://www.youtube.com/watch?v=pQ_LhvPfbgY",
     "embed":"https://www.youtube.com/embed/pQ_LhvPfbgY","domain":"Daily","category":"hygiene",
     "desc":"Fun brushing teeth tutorial for kids"},
    {"id":"yt_dress","title":"👕 How to Get Dressed","url":"https://www.youtube.com/watch?v=K4SVBg9SPZY",
     "embed":"https://www.youtube.com/embed/K4SVBg9SPZY","domain":"Daily","category":"dressing",
     "desc":"Getting dressed step by step for children with autism"},
    {"id":"yt_shoes","title":"👟 How to Put on Shoes","url":"https://www.youtube.com/watch?v=Bn1EzZ8Uuvc",
     "embed":"https://www.youtube.com/embed/Bn1EzZ8Uuvc","domain":"Daily","category":"dressing",
     "desc":"Putting on shoes independently"},
    {"id":"yt_eat","title":"🍽️ How to Eat at the Table","url":"https://www.youtube.com/watch?v=3VkDJPe5bWQ",
     "embed":"https://www.youtube.com/embed/3VkDJPe5bWQ","domain":"Daily","category":"eating",
     "desc":"Mealtime skills and table manners for kids"},
    {"id":"yt_toilet","title":"🚽 Toilet Training Steps","url":"https://www.youtube.com/watch?v=xNT5e4bWkYk",
     "embed":"https://www.youtube.com/embed/xNT5e4bWkYk","domain":"Daily","category":"hygiene",
     "desc":"Step-by-step toilet training for children with autism"},
    {"id":"yt_morning","title":"☀️ Morning Routine","url":"https://www.youtube.com/watch?v=4RGxCpWlrUc",
     "embed":"https://www.youtube.com/embed/4RGxCpWlrUc","domain":"Daily","category":"routine",
     "desc":"Complete morning routine for children with ASD"},
    {"id":"yt_sleep","title":"🌙 Bedtime Routine","url":"https://www.youtube.com/watch?v=OJMaLbXqbT4",
     "embed":"https://www.youtube.com/embed/OJMaLbXqbT4","domain":"Daily","category":"routine",
     "desc":"Calming bedtime routine for children with autism"},
    {"id":"yt_emotions","title":"😊 Understanding Emotions","url":"https://www.youtube.com/watch?v=yCCd_SoXm34",
     "embed":"https://www.youtube.com/embed/yCCd_SoXm34","domain":"Social","category":"emotions",
     "desc":"Learning to identify and express emotions"},
    {"id":"yt_hello","title":"👋 How to Say Hello","url":"https://www.youtube.com/watch?v=JWEwRE3GVLI",
     "embed":"https://www.youtube.com/embed/JWEwRE3GVLI","domain":"Social","category":"social",
     "desc":"Greetings and social communication skills"},
    {"id":"yt_share","title":"🤝 How to Share and Take Turns","url":"https://www.youtube.com/watch?v=VzpCzSXOhiM",
     "embed":"https://www.youtube.com/embed/VzpCzSXOhiM","domain":"Social","category":"social",
     "desc":"Turn-taking and sharing with friends"},
    {"id":"yt_colors","title":"🌈 Learning Colors","url":"https://www.youtube.com/watch?v=MjvMGGm5rk0",
     "embed":"https://www.youtube.com/embed/MjvMGGm5rk0","domain":"Cognitive","category":"colors",
     "desc":"Fun color learning song for children"},
    {"id":"yt_numbers","title":"🔢 Counting 1 to 10","url":"https://www.youtube.com/watch?v=DR-cfDsHCGA",
     "embed":"https://www.youtube.com/embed/DR-cfDsHCGA","domain":"Math","category":"counting",
     "desc":"Learn to count fingers and numbers 1-10"},
    {"id":"yt_animals","title":"🐶 Animal Sounds and Names","url":"https://www.youtube.com/watch?v=4OsKBMJb2I4",
     "embed":"https://www.youtube.com/embed/4OsKBMJb2I4","domain":"Cognitive","category":"animals",
     "desc":"Learning animal names and sounds"},
    {"id":"yt_exercise","title":"🤸 Kids Exercise and Movement","url":"https://www.youtube.com/watch?v=Gq9tRF_CXMY",
     "embed":"https://www.youtube.com/embed/Gq9tRF_CXMY","domain":"Motor","category":"exercise",
     "desc":"Fun exercise and motor skills for children"},
]

# ══════════════════════════════════════════════════════════════════
# 100K TASK POOL — 3-year progressive curriculum
# Grows across 36 months from simple to complex
# ══════════════════════════════════════════════════════════════════
def generate_pool():
    """
    Generate 100,000 therapy tasks across 3 years of progression.
    Month 1-12  (Year 1): Foundation — single-step, high visual support
    Month 13-24 (Year 2): Building — two-step, reduced prompting
    Month 25-36 (Year 3): Advanced — complex, generalisation
    """
    pool=[]
    log.info("🎯 Generating 100K task pool — this takes ~8 seconds…")

    # ── Year 1: Foundation (months 1-12) ─────────────────────────
    # Motor — 8,000 tasks
    for _ in range(8000):
        m=random.choice(MOTORS)
        diff=random.choice(["easy","easy","medium"])
        pool.append({**m,
            "id":f"{m['id']}_{random.randint(0,9999999)}",
            "base_id":f"y1_{m['id']}_{random.randint(0,999)}",
            "domain":"Motor","protocol":"ABA-DTT",
            "tablet_mode":"motor","tokens":2,"joy":"dance",
            "year":1,"difficulty":diff,"month_range":"1-12"})

    # Colour grid — 10,000 tasks
    for _ in range(10000):
        pool.append({**_grid(COLORS,"color","Cognitive","TEACCH",3),
            "year":1,"difficulty":"easy","month_range":"1-12"})

    # Animals — 8,000
    for _ in range(8000):
        pool.append({**_grid(ANIMALS,"animal","Cognitive","TEACCH",4),
            "year":1,"difficulty":"easy","month_range":"1-12"})

    # Math counting 1-5 — 6,000
    for _ in range(6000):
        n=random.randint(1,5)
        pool.append({"id":f"y1_count_{n}_{random.randint(0,9999999)}",
            "base_id":f"y1_count_{n}_{random.randint(0,999)}",
            "domain":"Math","protocol":"ABA-DTT","name":f"🔢 Show {n}",
            "instruction":f"Show me {n} fingers!","waiting":f"Show {n} fingers 🖐️",
            "success":f"Yes! {n} fingers! ✅","fail":f"Show me {n}!",
            "tablet_mode":"number","target_number":n,"verify":"finger_count",
            "tokens":4,"joy":"celebrate","year":1,"difficulty":"easy","month_range":"1-12",
            "prompts":[f"Show {n}!","Count!","Use your fingers!"]})

    # Basic words 1-5 letters — 8,000
    simple_words=[w for w in WORDS if len(w)<=4]
    for _ in range(8000):
        w=random.choice(simple_words)
        pool.append({"id":f"y1_say_{w}_{random.randint(0,9999999)}",
            "base_id":f"y1_say_{w}_{random.randint(0,999)}",
            "domain":"Verbal","protocol":"DTT","name":f"🗣️ Say '{w}'",
            "instruction":f"Say the word: {w}!","waiting":f"Say {w}! 🎤",
            "success":f"Well done! {w}! ✅","fail":f"Try: {w}!",
            "tablet_mode":"word","word_text":w,"verify":"speech_keyword","keyword":w,
            "tokens":3,"joy":"dance","year":1,"difficulty":"easy","month_range":"1-12",
            "prompts":[f"Say {w}!","Try it!","Loud voice!"]})

    # Basic social phrases — 5,000
    basic_social=["hello","yes","no","thank you","please","help","more","stop"]
    for _ in range(5000):
        ph=random.choice(basic_social)
        pool.append({"id":f"y1_ph_{ph.replace(' ','_')}_{random.randint(0,9999999)}",
            "base_id":f"y1_ph_{ph.replace(' ','_')}_{random.randint(0,999)}",
            "domain":"Social","protocol":"ESDM","name":f"💬 '{ph}'",
            "instruction":f"Say: {ph}!","waiting":f"Say {ph}! 🎤",
            "success":f"Excellent! '{ph}'! ✅","fail":f"Try: {ph}!",
            "tablet_mode":"social","social_text":ph,"verify":"speech_keyword","keyword":ph,
            "tokens":4,"joy":"celebrate","year":1,"difficulty":"easy","month_range":"1-12",
            "prompts":[f"Say {ph}!","You can do it!","Speak up!"]})

    # Year 1 Total so far: ~45,000

    # ── Year 2: Building (months 13-24) ──────────────────────────
    # Extended motor sequences — 6,000
    motor_pairs=[
        ("clap_wave","👏+👋","Clap then wave!","clap","wave"),
        ("raise_point","✋+👉","Raise hand then point!","raise_hand","point"),
        ("hands_clap","🙌+👏","Hands up then clap!","hands_up","clap"),
        ("wave_nose","👋+👆","Wave then touch nose!","wave","touch_nose"),
    ]
    for _ in range(6000):
        mp=random.choice(motor_pairs)
        m=next((x for x in MOTORS if x["id"]==mp[2]),MOTORS[0])
        pool.append({**m,
            "id":f"y2_{mp[0]}_{random.randint(0,9999999)}",
            "base_id":f"y2_{mp[0]}_{random.randint(0,999)}",
            "name":f"{mp[1]} Sequence","instruction":mp[3],
            "domain":"Motor","protocol":"ABA-DTT",
            "tablet_mode":"motor","tokens":4,"joy":"dance",
            "year":2,"difficulty":"medium","month_range":"13-24"})

    # Fruits, shapes, emotions, food — 12,000
    for _ in range(3000): pool.append({**_grid(FRUITS,"y2_fruit","Cognitive","TIE",4),"year":2,"difficulty":"medium","month_range":"13-24"})
    for _ in range(3000): pool.append({**_grid(SHAPES,"y2_shape","Cognitive","TEACCH",4),"year":2,"difficulty":"medium","month_range":"13-24"})
    for _ in range(3000): pool.append({**_grid(EMOTIONS_ITEMS,"y2_emo","Social","ESDM",5),"year":2,"difficulty":"medium","month_range":"13-24"})
    for _ in range(3000): pool.append({**_grid(BODY,"y2_body","Verbal","DTT",4),"year":2,"difficulty":"medium","month_range":"13-24"})

    # Math counting 1-10 — 6,000
    for _ in range(6000):
        n=random.randint(1,10)
        pool.append({"id":f"y2_count_{n}_{random.randint(0,9999999)}",
            "base_id":f"y2_count_{n}_{random.randint(0,999)}",
            "domain":"Math","protocol":"ABA-DTT","name":f"🔢 Count {n}",
            "instruction":f"Show me {n} fingers!","waiting":f"Show {n}! 🖐️",
            "success":f"Correct! {n} fingers! ✅","fail":f"Show {n} fingers!",
            "tablet_mode":"number","target_number":n,"verify":"finger_count",
            "tokens":5,"joy":"celebrate","year":2,"difficulty":"medium","month_range":"13-24",
            "prompts":[f"Show {n}!","Count carefully!","Use both hands!"]})

    # Full word list — 8,000
    for _ in range(8000):
        w=random.choice(WORDS)
        pool.append({"id":f"y2_say_{w}_{random.randint(0,9999999)}",
            "base_id":f"y2_say_{w}_{random.randint(0,999)}",
            "domain":"Verbal","protocol":"DTT","name":f"🗣️ '{w}'",
            "instruction":f"Say clearly: {w}!","waiting":f"Say {w}! 🎤",
            "success":f"Clear as a bell! {w}! ✅","fail":f"Say it again: {w}!",
            "tablet_mode":"word","word_text":w,"verify":"speech_keyword","keyword":w,
            "tokens":4,"joy":"dance","year":2,"difficulty":"medium","month_range":"13-24",
            "prompts":[f"Say {w}!","Loud and clear!","One more time!"]})

    # Full social phrases — 5,000
    for _ in range(5000):
        ph=random.choice(SOCIAL)
        pool.append({"id":f"y2_ph_{ph.replace(' ','_')}_{random.randint(0,9999999)}",
            "base_id":f"y2_ph_{ph.replace(' ','_')}_{random.randint(0,999)}",
            "domain":"Social","protocol":"ESDM","name":f"💬 '{ph}'",
            "instruction":f"Say the phrase: {ph}!","waiting":f"Say {ph}! 🎤",
            "success":f"Perfect! '{ph}'! ✅","fail":f"Try again: {ph}!",
            "tablet_mode":"social","social_text":ph,"verify":"speech_keyword","keyword":ph,
            "tokens":5,"joy":"full_joy","year":2,"difficulty":"medium","month_range":"13-24",
            "prompts":[f"Say {ph}!","You can do it!","Great job trying!"]})

    # PECS daily life — 5,000
    for _ in range(5000):
        em,nm,ph=random.choice(PECS_ITEMS)
        pool.append({"id":f"y2_pecs_{nm.replace(' ','_')}_{random.randint(0,9999999)}",
            "base_id":f"y2_pecs_{nm.replace(' ','_')}_{random.randint(0,999)}",
            "domain":"Daily","protocol":"TIE","name":f"{em} {nm}",
            "instruction":f"Say: {ph}!","waiting":f"Say it! {em}",
            "success":f"Excellent! {nm}! ✅","fail":f"Say: {ph}!",
            "tablet_mode":"daily","daily_emoji":em,"daily_label":nm,
            "verify":"speech_keyword","keyword":ph,
            "tokens":5,"joy":"celebrate","year":2,"difficulty":"medium","month_range":"13-24",
            "prompts":[f"Say {ph}!","Loud and clear!","Press the mic!"]})

    # Vehicles, food — 4,000
    for _ in range(2000): pool.append({**_grid(VEHICLES,"y2_vehicle","Cognitive","TEACCH",4),"year":2,"difficulty":"medium","month_range":"13-24"})
    for _ in range(2000): pool.append({**_grid(FOODS,"y2_food","Daily","TIE",4),"year":2,"difficulty":"medium","month_range":"13-24"})

    # Year 2 Total: ~54,000 more

    # ── Year 3: Advanced (months 25-36) ──────────────────────────
    # Complex motor 5-step sequences — 4,000
    adv_motor_names=[
        "Clap + Wave + Raise Hand","Point + Touch Nose + Wave",
        "Hands Up + Clap + Arms Out","Jump + Wave + Point",
        "Raise Hand + Jump + Clap","Touch Nose + Arms Out + Hands Up",
    ]
    for _ in range(4000):
        name=random.choice(adv_motor_names)
        m=random.choice(MOTORS)
        pool.append({**m,
            "id":f"y3_seq_{random.randint(0,9999999)}",
            "base_id":f"y3_seq_{name.replace(' ','_')}_{random.randint(0,999)}",
            "name":f"🔥 {name}","instruction":f"Do this sequence: {name}!",
            "domain":"Motor","protocol":"ESDM",
            "tablet_mode":"motor","tokens":6,"joy":"full_joy",
            "year":3,"difficulty":"hard","month_range":"25-36"})

    # Advanced categorisation — 8,000 (cross-domain)
    all_items=COLORS+ANIMALS+FRUITS+SHAPES+EMOTIONS_ITEMS+FOODS+VEHICLES+BODY
    for _ in range(4000):
        pool.append({**_grid(random.choice([ANIMALS,FRUITS,VEHICLES,FOODS]),
            "y3_cat","Cognitive","TEACCH",6),
            "year":3,"difficulty":"hard","month_range":"25-36"})
    for _ in range(4000):
        pool.append({**_grid(random.choice([EMOTIONS_ITEMS,BODY,SHAPES]),
            "y3_adv","Social","ESDM",6),
            "year":3,"difficulty":"hard","month_range":"25-36"})

    # Advanced math 1-10 with doubles — 5,000
    for _ in range(5000):
        n=random.randint(1,10)
        extra=random.choice(["quickly","with your left hand","with both hands","eyes closed"])
        pool.append({"id":f"y3_count_{n}_{random.randint(0,9999999)}",
            "base_id":f"y3_count_{n}_{random.randint(0,999)}",
            "domain":"Math","protocol":"ABA-DTT","name":f"⚡ Show {n}",
            "instruction":f"Show {n} fingers {extra}!","waiting":f"Show {n}! 🖐️",
            "success":f"Amazing! {n} fingers! 🌟","fail":f"Try again! Show {n}!",
            "tablet_mode":"number","target_number":n,"verify":"finger_count",
            "tokens":7,"joy":"full_joy","year":3,"difficulty":"hard","month_range":"25-36",
            "prompts":[f"Show {n}!","You are a champion!","Almost there!"]})

    # Advanced sentences — 8,000
    adv_phrases=[
        "My name is ","I would like ","Can I please have ","I feel happy today",
        "I need help please","I want to play with ","Good morning everyone",
        "I am finished thank you","May I have more please","I love learning",
        "That is very good","I can do it","Watch me","I am ready",
    ]
    for _ in range(8000):
        ph=random.choice(adv_phrases).strip()
        kw=ph.split()[0] if ph else "say"
        pool.append({"id":f"y3_sent_{kw}_{random.randint(0,9999999)}",
            "base_id":f"y3_sent_{kw}_{random.randint(0,999)}",
            "domain":"Social","protocol":"ESDM","name":f"💬 '{ph}'",
            "instruction":f"Say the full sentence: {ph}","waiting":f"Say it! 🎤",
            "success":f"Superb! Full sentence! 🌟","fail":f"Try: {ph}",
            "tablet_mode":"social","social_text":ph,"verify":"speech_keyword","keyword":kw,
            "tokens":8,"joy":"full_joy","year":3,"difficulty":"hard","month_range":"25-36",
            "prompts":[f"Say: {ph}","Full sentence!","You can do it!"]})

    # Daily living complex routines — 6,000
    routines=[
        ("☀️🪥🚿","Morning routine","Wake up, brush teeth, wash face!","morning"),
        ("🍽️🥄😋","Mealtime routine","Set the table, eat, say thank you!","mealtime"),
        ("👕👟🎒","Getting ready","Get dressed, put shoes on, pack bag!","dressing"),
        ("🚿🧼🛁","Bath routine","Turn on water, use soap, dry off!","bathing"),
        ("📚✏️🎒","School routine","Pack book, take pencil, say goodbye!","school"),
        ("🌙🪥😴","Bedtime routine","Brush teeth, put on pyjamas, sleep!","bedtime"),
    ]
    for _ in range(6000):
        em,nm,instr,kw=random.choice(routines)
        pool.append({"id":f"y3_routine_{kw}_{random.randint(0,9999999)}",
            "base_id":f"y3_routine_{kw}_{random.randint(0,999)}",
            "domain":"Daily","protocol":"TIE","name":f"{em} {nm}",
            "instruction":instr,"waiting":f"Tell me: {nm}! 🎤",
            "success":f"You know your routine! ✅","fail":f"Let us practice: {nm}",
            "tablet_mode":"social","social_text":nm,"verify":"speech_keyword","keyword":kw,
            "tokens":8,"joy":"full_joy","year":3,"difficulty":"hard","month_range":"25-36",
            "prompts":[f"Say {kw}!","Think about your day!","Step by step!"]})

    # Year 3 Total: ~35,000 more
    # ── Fill remaining to reach exactly 100,000 ──────────────────
    current=len(pool)
    needed=100000-current
    log.info(f"  Pool at {current:,} — adding {needed:,} more to reach 100,000…")
    # Fill by cycling all domains equally
    fillers=[
        lambda: _grid(random.choice([COLORS,ANIMALS,FRUITS,SHAPES,EMOTIONS_ITEMS,FOODS,VEHICLES,BODY]),
            f"fill_{random.choice(['c','a','f','s','e','fo','v','b'])}","Cognitive","TEACCH",4),
        lambda: {"id":f"fill_count_{random.randint(1,10)}_{random.randint(0,9999999)}",
            "base_id":f"fill_count_{random.randint(1,10)}_{random.randint(0,9999)}",
            "domain":"Math","protocol":"ABA-DTT","name":f"🔢 Show {random.randint(1,10)}",
            "instruction":f"Show me {random.randint(1,10)} fingers!",
            "waiting":"Show fingers! 🖐️","success":"Correct! ✅","fail":"Try again!",
            "tablet_mode":"number","target_number":random.randint(1,10),
            "verify":"finger_count","tokens":4,"joy":"celebrate",
            "prompts":["Count!","Use your fingers!","Almost!"]},
        lambda: {"id":f"fill_say_{random.choice(WORDS)}_{random.randint(0,9999999)}",
            "base_id":f"fill_say_{random.choice(WORDS)}_{random.randint(0,9999)}",
            "domain":"Verbal","protocol":"DTT",
            "name":f"🗣️ Say '{random.choice(WORDS)}'",
            "instruction":f"Say: {random.choice(WORDS)}!","waiting":"Say it! 🎤",
            "success":"Excellent! ✅","fail":"Try again!",
            "tablet_mode":"word","word_text":random.choice(WORDS),
            "verify":"speech_keyword","keyword":random.choice(WORDS),
            "tokens":4,"joy":"dance","prompts":["Say it!","Loud voice!","Try!"]},
    ]
    for i in range(needed):
        f=fillers[i%len(fillers)]
        try: pool.append(f())
        except: pass

    random.shuffle(pool)
    log.info(f"✅ Generated {len(pool):,} therapy tasks (3-year curriculum)")
    return pool

log.info("🎯 Generating 100,000 task pool — 3-year curriculum (8-12 seconds)…")
TASK_POOL=generate_pool()
SESSION_HISTORY=deque(maxlen=400)
MAX_FAILS=2

# ══════════════════════════════════════════════════════════════════
# SHARED STATE
# ══════════════════════════════════════════════════════════════════
ST={
    "child_name":CHILD_NAME,"age":int(CHILD_AGE) if CHILD_AGE.isdigit() else 6,
    "score":0,"tokens":0,"streak":0,"consecutive":0,"mastered":0,
    "conversation_level":1,"domain":"Motor","protocol":"ABA-DTT",
    "emotion":"neutral",
    "emotion_pct":{k:0 for k in ["happy","joyful","surprised","sad","angry","fear","neutral"]},
    "face_detected":False,"attention":70,"finger_count":0,
    "lip_motion":0.0,"lip_speaking":False,"lip_sync_value":0.0,
    "is_speaking":False,"interrupt_flag":False,"pecs_interrupt":False,
    "recording":False,"mic_level":0.0,
    "tasks_success":0,"tasks_fail":0,"tasks_skipped":0,"tasks_mastered":0,
    "instant_success":False,"tablet_click_result":None,
    "_task_start_time":0.0,"_current_task_keyword":"","_fail_count":0,
    "session_chat":[],"logs":[],"pecs_log":[],"resp_times":[],
    "skill_motor":50.0,"skill_cognitive":50.0,"skill_verbal":50.0,
    "skill_math":50.0,"skill_social":50.0,"skill_daily":50.0,
    "body_motion":0.0,"clapping":False,"waving":False,
    "hand_raised":False,"hands_up":False,"head_tilt":0.0,
    "social_joy_active":False,"verify_action":None,
    "verify_result":False,"verify_timeout":0.0,
    "session_date":datetime.now().strftime("%Y-%m-%d"),
    "uptime":time.time(),"quick_action":None,
    "milestones_reached":0,"next_milestone_in":10,
    "current_year_level":1,"tasks_in_year1":0,"tasks_in_year2":0,"tasks_in_year3":0,
    "current_theme":"blue","current_mood":"calm",
    "current_music":"none","current_voice":"friendly","music_volume":0.3,
    "child_done_count":len(_child_done),
    "last_task_name":"—","last_result":"—","session_events":[],
}
_ai_chat_list=[]

def LOG(msg,t="info"):
    e={"time":datetime.now().strftime("%H:%M:%S"),"msg":str(msg)[:120],"type":t}
    ST["logs"].append(e); ST["session_events"].append(e)
    if len(ST["logs"])>600: ST["logs"]=ST["logs"][-600:]
    if len(ST["session_events"])>200: ST["session_events"]=ST["session_events"][-200:]
    if t=="success": log.info(f"✅ {msg[:60]}")
    elif t=="fail": log.warning(f"❌ {msg[:60]}")

def get_next_task():
    recent=set(SESSION_HISTORY); all_done=recent|_child_done
    candidates=[t for t in TASK_POOL if t.get("base_id","") not in all_done]
    if not candidates:
        SESSION_HISTORY.clear()
        candidates=[t for t in TASK_POOL if t.get("base_id","") not in _child_done]
        if not candidates: candidates=TASK_POOL
    cl=ST["conversation_level"]
    if cl==1: filt=[t for t in candidates if t["domain"] in ["Motor","Daily"]]
    elif cl==2: filt=[t for t in candidates if t["domain"] in ["Motor","Cognitive","Math","Daily","Verbal"]]
    else: filt=candidates
    task=random.choice(filt if filt else candidates)
    SESSION_HISTORY.append(task.get("base_id",""))
    ST["_task_start_time"]=time.time()
    return task


# ══════════════════════════════════════════════════════════════════
# PYBULLET WATCHDOG
# ══════════════════════════════════════════════════════════════════
_PB=r"""
import sys,os,time,math,json,select
os.environ["TF_CPP_MIN_LOG_LEVEL"]="3"
try:
    import pybullet as p,pybullet_data
    sys.path.insert(0,os.path.expanduser("~/pepper_duo/src"))
    from qibullet import SimulationManager
except Exception as e:
    print(f"PB_ERROR:{e}",flush=True); sys.exit(0)
child=sys.argv[1] if len(sys.argv)>1 else "Child"
sim=SimulationManager(); client=sim.launchSimulation(gui=True)
p.setRealTimeSimulation(1); p.setGravity(0,0,-9.81)
p.setAdditionalSearchPath(pybullet_data.getDataPath()); p.loadURDF("plane.urdf")
for pos,ext in [([0,-4,1.1],[5,.1,1.1]),([0,4,1.1],[5,.1,1.1]),
                ([5,0,1.1],[.1,4,1.1]),([-5,0,1.1],[.1,4,1.1])]:
    p.createMultiBody(0,-1,p.createVisualShape(p.GEOM_BOX,halfExtents=ext,
        rgbaColor=[.92,.92,.96,1]),pos)
p.createMultiBody(0,-1,p.createVisualShape(p.GEOM_BOX,halfExtents=[4.5,3.5,.02],
    rgbaColor=[.65,.55,.40,1]),[0,0,.01])
for txt,pos,col in [("ABA Motor",[-3.5,3,.05],[1,.3,.3,1]),
    ("TEACCH Visual",[3.5,3,.05],[.3,.7,1,1]),("DTT Verbal",[0,3.8,.05],[.3,1,.5,1]),
    ("ESDM Social",[-3.5,-3,.05],[1,.8,.2,1]),("TIE Daily",[3.5,-3,.05],[.8,.3,1,1]),
    (f"★ {child}",[0,0,3.2],[.4,.5,.9,1])]:
    p.addUserDebugText(txt,pos,col[:3],textSize=1.2,lifeTime=0)
pepper=sim.spawnPepper(client); pepper.goToPosture("Stand",0.5)
p.resetDebugVisualizerCamera(6,45,-30,[0,0,0.8])
print("PYBULLET_READY",flush=True)
rx=ry=ph=0.0; lu=0.0; st={"is_speaking":False,"lip":0.0,"sj":False,"ht":0.0}
while True:
    try:
        if select.select([sys.stdin],[],[],0)[0]:
            ln=sys.stdin.readline()
            if not ln or ln.strip()=="EXIT": break
            try: st.update(json.loads(ln))
            except: pass
    except: pass
    p.stepSimulation(); now=time.time()
    if now-lu>0.04:
        lu=now; lip=float(st.get("lip",0.0))
        try:
            if st["is_speaking"]:
                ph+=.06
                pepper.setAngles("LShoulderPitch",.5+.3*math.sin(ph),.07)
                pepper.setAngles("RShoulderPitch",.5+.3*math.sin(ph+math.pi*.6),.07)
                pepper.setAngles("HeadPitch",-0.04-lip*0.13,.22)
            elif st.get("sj"):
                jt=time.time()
                pepper.setAngles("LShoulderPitch",.05+.3*abs(math.sin(jt*4)),.25)
                pepper.setAngles("RShoulderPitch",.05+.3*abs(math.sin(jt*4+math.pi)),.25)
                pepper.setAngles("LElbowRoll",-.3*abs(math.sin(jt*3)),.2)
                pepper.setAngles("RElbowRoll",.3*abs(math.sin(jt*3)),.2)
            else:
                pepper.setAngles("LShoulderPitch",1.,.04)
                pepper.setAngles("RShoulderPitch",1.,.04)
                pepper.setAngles("HeadYaw",float(st.get("ht",0))*.5,.03)
        except: pass
    t_=time.time(); rx+=.012*math.cos(t_*.35); ry+=.012*math.sin(t_*.42)
    rx=max(-3.5,min(3.5,rx)); ry=max(-2.8,min(2.8,ry))
    try: pepper.setPosition([rx,ry,.8])
    except: pass
    time.sleep(1/60.)
"""

class PBWatchdog:
    def __init__(self,cn):
        self.child=cn; self._proc=None; self._ready=False
        self._lock=threading.Lock(); self._running=False; self._lu=0.0
    def start(self):
        self._running=True
        threading.Thread(target=self._sup,daemon=True).start()
    def _launch(self):
        try:
            self._proc=subprocess.Popen([sys.executable,"-c",_PB,self.child],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,text=True,bufsize=1)
            dl=time.time()+30
            while time.time()<dl:
                try:
                    ln=self._proc.stdout.readline()
                    if "PYBULLET_READY" in ln: self._ready=True; log.info("✅ PyBullet ready"); return True
                    if "PB_ERROR" in ln: return False
                except: return False
                time.sleep(0.1)
        except Exception as e: log.warning(f"PyBullet: {e}")
        return False
    def _sup(self):
        while self._running:
            if self._launch():
                try: self._proc.wait()
                except: pass
            if not self._running: break
            self._ready=False; time.sleep(3)
    def send(self,**kw):
        now=time.time()
        if now-self._lu<0.04: return
        self._lu=now
        if not self._ready or not self._proc: return
        with self._lock:
            try: self._proc.stdin.write(json.dumps(kw)+"\n"); self._proc.stdin.flush()
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

# ══════════════════════════════════════════════════════════════════
# BRIDGE SIGNALS
# ══════════════════════════════════════════════════════════════════
class Bridge(QObject):
    sig_task    =pyqtSignal(dict)
    sig_success =pyqtSignal(str)
    sig_fail    =pyqtSignal(str)
    sig_skip    =pyqtSignal(str)
    sig_instr   =pyqtSignal(str)
    sig_waiting =pyqtSignal(str)
    sig_unlock  =pyqtSignal()
    sig_lock    =pyqtSignal()
    sig_reset   =pyqtSignal()
    sig_joy     =pyqtSignal(str)
    sig_camera  =pyqtSignal(object)
    sig_stats   =pyqtSignal()
    sig_chat    =pyqtSignal(str,str)
    sig_rec_stop=pyqtSignal(str)
    sig_mic_lvl =pyqtSignal(float)
    sig_pecs    =pyqtSignal(str)
    sig_theme   =pyqtSignal(str)
    sig_mood    =pyqtSignal(str)
    sig_clap    =pyqtSignal()
    sig_mega_celebrate=pyqtSignal()   # every 10 correct answers
    sig_youtube =pyqtSignal(str)      # show YouTube video
BRIDGE=Bridge()

# ══════════════════════════════════════════════════════════════════
# VOICE ENGINE
# ══════════════════════════════════════════════════════════════════
class VoiceEngine:
    def __init__(self):
        self.ok=False; self._lk=threading.Lock()
        try:
            self.e=pyttsx3.init()
            self.e.setProperty("rate",165); self.e.setProperty("volume",1.0)
            self.ok=True; log.info("✅ TTS ready")
        except Exception as ex: log.warning(f"TTS: {ex}")

    def set_profile(self,pid):
        p=next((x for x in VOICE_PROFILES if x["id"]==pid),VOICE_PROFILES[0])
        ST["current_voice"]=pid
        if self.ok:
            try:
                self.e.setProperty("rate",p["rate"])
                self.e.setProperty("volume",p["volume"])
            except: pass

    def _lip(self,text):
        for word in text.split():
            if not ST["is_speaking"]: break
            d=max(0.06,len(word)/10.0)
            ST["lip_sync_value"]=min(1.0,.5+random.uniform(.1,.4))
            time.sleep(d*.55)
            ST["lip_sync_value"]=max(.05,ST["lip_sync_value"]*.3)
            time.sleep(d*.45)
        ST["lip_sync_value"]=0.0

    def say(self,text,wait=True):
        if ST.get("pecs_interrupt") and wait: return
        ST["interrupt_flag"]=False
        clean=re.sub(r"\[[^\]]+\]","",str(text)).strip()
        if not clean: return
        ST["is_speaking"]=True
        ST["session_chat"].append({"role":"Pepper","text":clean,
            "time":datetime.now().strftime("%H:%M:%S")})
        if len(ST["session_chat"])>60: ST["session_chat"]=ST["session_chat"][-60:]
        threading.Thread(target=self._lip,args=(clean,),daemon=True).start()
        if self.ok and not ST["interrupt_flag"]:
            with self._lk:
                try: self.e.say(clean); self.e.runAndWait()
                except: pass
        ST["is_speaking"]=False; ST["lip_sync_value"]=0.0
        if wait: time.sleep(0.15)

    def say_pecs(self,text):
        ST["pecs_interrupt"]=True; ST["interrupt_flag"]=True
        if self.ok:
            try: self.e.stop()
            except: pass
        def _sp():
            time.sleep(0.1); ST["is_speaking"]=True
            if self.ok:
                with self._lk:
                    try: self.e.say(text); self.e.runAndWait()
                    except: pass
            ST["is_speaking"]=False; ST["pecs_interrupt"]=False; ST["interrupt_flag"]=False
        threading.Thread(target=_sp,daemon=True).start()

    def stop(self):
        ST["interrupt_flag"]=True; ST["is_speaking"]=False; ST["lip_sync_value"]=0.0
        if self.ok:
            try: self.e.stop()
            except: pass

    def cleanup(self):
        self.stop()
        try: os.system("pkill -f aplay 2>/dev/null")
        except: pass

VOICE_REF=None

# ══════════════════════════════════════════════════════════════════
# CAMERA THREAD
# ══════════════════════════════════════════════════════════════════
EMO_COLORS={"happy":(0,220,80),"joyful":(0,255,180),"sad":(100,100,220),
            "angry":(255,60,60),"fear":(0,180,220),"surprised":(200,50,220),
            "neutral":(180,180,180)}

class CameraThread(QThread):
    def __init__(self):
        super().__init__(); self.running=False; self.cap=None
        self._mutex=QMutex(); self._pose=None; self._hands=None; self._face=None
        self._prev_gray=None; self._hand_hist=[]; self._motion_buf=[]
        self._emo_sm={k:0.0 for k in EMO_COLORS}
        self._lip_hist=deque(maxlen=8); self._prev_mh=0.0
        self._init_mp(); self._init_cam()

    def _init_mp(self):
        os.environ["CUDA_VISIBLE_DEVICES"]=""
        for name,cls,kw in [
            ("Pose",mp.solutions.pose.Pose,
             {"min_detection_confidence":0.55,"model_complexity":1}),
            ("Hands",mp.solutions.hands.Hands,
             {"max_num_hands":2,"min_detection_confidence":0.60}),
            ("FaceMesh",mp.solutions.face_mesh.FaceMesh,
             {"max_num_faces":1,"min_detection_confidence":0.5,"refine_landmarks":True}),
        ]:
            try:
                obj=cls(**kw); setattr(self,f"_{name.lower()}",obj)
                log.info(f"✅ MediaPipe {name}")
            except Exception as e: log.warning(f"MP {name}: {e}")
        os.environ["CUDA_VISIBLE_DEVICES"]="0"

    def _init_cam(self):
        for idx in [1,0,2]:
            try:
                c=cv2.VideoCapture(idx)
                if c.isOpened():
                    ret,f=c.read()
                    if ret and f is not None and f.size>0:
                        c.set(cv2.CAP_PROP_FRAME_WIDTH,640)
                        c.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
                        self.cap=c; log.info(f"✅ Camera {idx}"); return
                    c.release()
            except: pass

    def _count_fingers(self,lm,label):
        count=0
        if label=="Left":
            if lm[4].x>lm[3].x: count+=1
        else:
            if lm[4].x<lm[3].x: count+=1
        for tip in [8,12,16,20]:
            if lm[tip].y<lm[tip-2].y: count+=1
        return count

    def _emotion_geo(self,lm,w,h):
        try:
            def ear(eye):
                pts=[(lm[i].x*w,lm[i].y*h) for i in eye]
                A=math.dist(pts[1],pts[5]); B=math.dist(pts[2],pts[4])
                C=math.dist(pts[0],pts[3]); return (A+B)/(2*C+1e-6)
            ea=(ear([33,160,158,133,153,144])+ear([362,385,387,263,373,380]))/2
            ul=lm[13]; ll=lm[14]; lc=lm[78]; rc=lm[308]
            mar=math.dist((ul.x*w,ul.y*h),(ll.x*w,ll.y*h))/(math.dist((lc.x*w,lc.y*h),(rc.x*w,rc.y*h))+1e-6)
            lb=lm[107]; le=lm[159]; rb=lm[336]; re_=lm[386]
            brow=((lb.y-le.y)+(rb.y-re_.y))/2.0
            cheek=((lm[116].y+lm[345].y)/2.0-lm[4].y)*h
            sc={k:0.0 for k in self._emo_sm}
            sc["happy"]=min(1.0,max(0,(mar-.20)*3.5)*(1 if cheek<-3 else 0.5))
            sc["joyful"]=min(1.0,max(0,(mar-.25)*2.5))
            sc["surprised"]=min(1.0,max(0,(.22-ea)*8))
            sc["angry"]=min(1.0,max(0,brow*30)*max(0,(.25-mar)*4))
            sc["sad"]=min(1.0,max(0,brow*20)*max(0,(.30-mar)*3))
            sc["fear"]=min(1.0,max(0,(.22-ea)*5)*max(0,(.25-mar)*3))
            total=sum(sc.values()) or 1e-6
            for k in sc: sc[k]/=total
            sc["neutral"]=max(0.0,1.0-sum(sc[k] for k in sc if k!="neutral"))
            t2=sum(sc.values()) or 1e-6
            for k in sc: sc[k]/=t2
            for k in self._emo_sm: self._emo_sm[k]=.80*self._emo_sm[k]+.20*sc.get(k,0)
            mh=mar*(h*.05); ld=abs(mh-self._prev_mh); self._prev_mh=mh
            self._lip_hist.append(ld)
            avg=sum(self._lip_hist)/max(len(self._lip_hist),1)
            ST["lip_motion"]=float(avg); ST["lip_speaking"]=avg>0.50
            dom=max(self._emo_sm,key=self._emo_sm.get)
            pct={k:int(v*100) for k,v in self._emo_sm.items()}
            return dom,pct
        except: return "neutral",{k:0 for k in EMO_COLORS}

    def run(self):
        self.running=True; fc=0
        while self.running:
            if self.cap and self.cap.isOpened():
                ret,frame=self.cap.read()
                if not ret or frame is None:
                    frame=np.zeros((480,640,3),dtype=np.uint8)
                else: frame=cv2.flip(frame,1)
            else:
                frame=np.zeros((480,640,3),dtype=np.uint8)
                cv2.putText(frame,"No Camera — Simulation Mode",
                    (80,240),cv2.FONT_HERSHEY_SIMPLEX,.8,(100,200,255),2)
            fc+=1
            gray=cv2.cvtColor(frame,cv2.COLOR_BGR2GRAY)
            gray=cv2.GaussianBlur(gray,(21,21),0)
            if self._prev_gray is not None:
                diff=cv2.absdiff(self._prev_gray,gray)
                _,th=cv2.threshold(diff,25,255,cv2.THRESH_BINARY)
                motion=float(np.mean(th)); ST["body_motion"]=motion
                self._motion_buf.append(motion)
                if len(self._motion_buf)>12: self._motion_buf.pop(0)
                if len(self._motion_buf)>=4:
                    avg=sum(self._motion_buf[:-2])/max(len(self._motion_buf)-2,1)
                    ST["clapping"]=(self._motion_buf[-1]>avg*3.2 and self._motion_buf[-1]>12)
                h2,w2=gray.shape
                lm_=float(np.mean(th[:,:w2//2])); rm_=float(np.mean(th[:,w2//2:]))
                self._hand_hist.append("L" if lm_>rm_+3 else "R" if rm_>lm_+3 else "N")
                if len(self._hand_hist)>10: self._hand_hist.pop(0)
                chg=sum(1 for i in range(1,len(self._hand_hist))
                    if self._hand_hist[i]!=self._hand_hist[i-1] and self._hand_hist[i]!="N")
                ST["waving"]=chg>=3
            self._prev_gray=gray
            if self._pose:
                try:
                    rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
                    res=self._pose.process(rgb)
                    if res.pose_landmarks:
                        mp.solutions.drawing_utils.draw_landmarks(
                            frame,res.pose_landmarks,mp.solutions.pose.POSE_CONNECTIONS,
                            mp.solutions.drawing_utils.DrawingSpec(color=(0,255,100),thickness=2,circle_radius=3),
                            mp.solutions.drawing_utils.DrawingSpec(color=(0,150,255),thickness=2))
                        lm=res.pose_landmarks.landmark
                        PL=mp.solutions.pose.PoseLandmark
                        pl={"l_shoulder_y":lm[PL.LEFT_SHOULDER].y,"r_shoulder_y":lm[PL.RIGHT_SHOULDER].y,
                            "l_wrist_y":lm[PL.LEFT_WRIST].y,"r_wrist_y":lm[PL.RIGHT_WRIST].y}
                        ST["hand_raised"]=(pl["l_wrist_y"]<pl["l_shoulder_y"]-.07 or pl["r_wrist_y"]<pl["r_shoulder_y"]-.07)
                        ST["hands_up"]=(pl["l_wrist_y"]<pl["l_shoulder_y"]-.07 and pl["r_wrist_y"]<pl["r_shoulder_y"]-.07)
                        ST["face_detected"]=True; ST["attention"]=min(100,ST["attention"]+1)
                except: pass
            if self._face and fc%3==0:
                try:
                    rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
                    fres=self._face.process(rgb)
                    if fres.multi_face_landmarks:
                        h_,w_=frame.shape[:2]
                        fl=fres.multi_face_landmarks[0].landmark
                        em,pct=self._emotion_geo(fl,w_,h_)
                        ST["emotion"]=em; ST["emotion_pct"]=pct
                        ST["face_detected"]=True; ST["attention"]=min(100,ST["attention"]+2)
                        ST["head_tilt"]=fl[1].x-.5
                        lc=(0,255,200) if ST["lip_speaking"] else (80,80,180)
                        lids=[61,185,40,39,37,0,267,269,270,409,291,146,91,181,84,17,314,405,321,375,291]
                        pts=np.array([(int(fl[i].x*w_),int(fl[i].y*h_)) for i in lids],np.int32)
                        cv2.polylines(frame,[pts],True,lc,2)
                    else:
                        ST["face_detected"]=False; ST["attention"]=max(0,ST["attention"]-2)
                        ST["lip_motion"]=0.0; ST["lip_speaking"]=False
                except: pass
            if self._hands and fc%2==0:
                try:
                    rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
                    hres=self._hands.process(rgb)
                    if hres.multi_hand_landmarks:
                        total=0
                        for hidx,hlm in enumerate(hres.multi_hand_landmarks):
                            mp.solutions.drawing_utils.draw_landmarks(
                                frame,hlm,mp.solutions.hands.HAND_CONNECTIONS,
                                mp.solutions.drawing_utils.DrawingSpec(color=(255,100,0),thickness=2,circle_radius=4),
                                mp.solutions.drawing_utils.DrawingSpec(color=(255,200,0),thickness=2))
                            label=("Right" if not hres.multi_handedness or hidx>=len(hres.multi_handedness)
                                   else hres.multi_handedness[hidx].classification[0].label)
                            fc_n=self._count_fingers(hlm.landmark,label); total+=fc_n
                            w=hlm.landmark[0]; h_,w_=frame.shape[:2]
                            cv2.putText(frame,f"{label[0]}:{fc_n}",
                                (int(w.x*w_)-20,int(w.y*h_)+25),cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,0),2)
                        ST["finger_count"]=min(10,total)
                        if len(hres.multi_hand_landmarks)>=2:
                            h1=hres.multi_hand_landmarks[0].landmark[0]
                            h2_=hres.multi_hand_landmarks[1].landmark[0]
                            if abs(h1.x-h2_.x)<.18 and abs(h1.y-h2_.y)<.18: ST["clapping"]=True
                    else: ST["finger_count"]=0
                except: pass
            va=ST.get("verify_action")
            if va and time.time()<=ST.get("verify_timeout",0):
                ok=False
                if va=="clap": ok=ST.get("clapping",False)
                elif va=="wave": ok=ST.get("waving",False)
                elif va=="raise_hand": ok=ST.get("hand_raised",False)
                elif va=="hands_up": ok=ST.get("hands_up",False)
                elif va=="jump": ok=ST.get("body_motion",0)>30
                elif va=="finger_count": ok=ST["finger_count"]==ST.get("finger_target",1)
                elif va in ["arms_out","touch_nose","point"]: ok=ST.get("body_motion",0)>5
                if ok:
                    ST["verify_result"]=True; ST["verify_action"]=None
                    ST["instant_success"]=True; LOG("✅ Motor verified","success")
            h_,w_=frame.shape[:2]
            th=get_theme(); acc=th["accent"]
            cv2.rectangle(frame,(0,0),(w_,52),(8,10,24),-1)
            cv2.putText(frame,
                f"{'★'*ST['consecutive']}{'☆'*(3-ST['consecutive'])} | {ST['emotion']} | "
                f"L{ST['conversation_level']} | {CURRENT_MOOD['em']} | "
                f"Theme:{ST['current_theme']}",
                (8,20),cv2.FONT_HERSHEY_SIMPLEX,.44,(acc.red(),acc.green(),acc.blue()),1)
            cv2.putText(frame,
                f"Score:{ST['score']} | Attn:{ST['attention']}% | Fingers:{ST['finger_count']}/10 | "
                f"{'👄' if ST['lip_speaking'] else '·'}",
                (8,40),cv2.FONT_HERSHEY_SIMPLEX,.38,(200,200,200),1)
            if ST["recording"]: cv2.circle(frame,(w_-18,18),8,(0,0,255),-1)
            with QMutexLocker(self._mutex):
                rgb_c=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB).copy()
                h_,w_,ch=rgb_c.shape
                qi=QImage(rgb_c.data.tobytes(),w_,h_,w_*ch,QImage.Format.Format_RGB888)
                BRIDGE.sig_camera.emit(qi.copy())
            self.msleep(16)

    def stop(self):
        self.running=False; self.quit(); self.wait(3000)
        if self.cap: self.cap.release()

# ══════════════════════════════════════════════════════════════════
# TOUCH RECORDER
# ══════════════════════════════════════════════════════════════════
class TouchRecorder:
    def __init__(self):
        self._lock=threading.Lock(); self._recording=False; self._audio=None
        self.whisper=None
        self.r=sr.Recognizer(); self.r.energy_threshold=200
        self.r.dynamic_energy_threshold=True; self.r.pause_threshold=0.9
        try:
            with sr.Microphone() as src:
                log.info("🎤 Calibrating mic...")
                self.r.adjust_for_ambient_noise(src,duration=1.2)
            log.info(f"✅ Mic ready (energy={self.r.energy_threshold:.0f})")
        except Exception as e: log.warning(f"Mic: {e}")
        if _FW:
            try:
                self.whisper=FW("base",device="cpu",compute_type="int8")
                log.info("✅ Whisper-base ready")
            except Exception as e: log.warning(f"Whisper: {e}")

    def start(self):
        with self._lock:
            if self._recording: return
            self._recording=True; self._audio=None
        ST["recording"]=True
        threading.Thread(target=self._capture,daemon=True).start()

    def _capture(self):
        try:
            with sr.Microphone() as src:
                self.r.adjust_for_ambient_noise(src,duration=0.15)
                audio=self.r.listen(src,timeout=15,phrase_time_limit=12)
                raw=np.frombuffer(audio.get_raw_data(),dtype=np.int16).astype(np.float32)
                ST["mic_level"]=min(1.0,float(np.sqrt(np.mean(raw**2)))/5000.0)
                BRIDGE.sig_mic_lvl.emit(ST["mic_level"])
                with self._lock: self._audio=audio
        except Exception as e: log.warning(f"Record: {e}")
        finally:
            with self._lock: self._recording=False
            ST["recording"]=False; ST["mic_level"]=0.0

    def stop_and_recognise(self)->str:
        for _ in range(40):
            with self._lock:
                if not self._recording: break
            time.sleep(0.05)
        with self._lock: audio=self._audio
        if not audio: return ""
        text=""
        if self.whisper:
            try:
                raw=audio.get_raw_data(convert_rate=16000,convert_width=2)
                with tempfile.NamedTemporaryFile(suffix=".wav",delete=False) as tmp: tp=tmp.name
                with wave.open(tp,"wb") as wf:
                    wf.setnchannels(1); wf.setsampwidth(2)
                    wf.setframerate(16000); wf.writeframes(raw)
                for lang in ["en","ar"]:
                    segs,_=self.whisper.transcribe(tp,language=lang,beam_size=5,
                        temperature=0.0,no_speech_threshold=0.4,condition_on_previous_text=False)
                    text=" ".join(s.text.strip() for s in segs).strip()
                    if text: break
                try: os.unlink(tp)
                except: pass
                if text: self._check(text); return text
            except Exception as e: log.warning(f"Whisper: {e}")
        try:
            text=self.r.recognize_google(audio,language="en-US")
            self._check(text); return text
        except: pass
        return ""

    def _check(self,text):
        kw=ST.get("_current_task_keyword","").strip()
        if not kw or not text: return
        t=text.strip()
        if kw.lower() in t.lower() or t.lower() in kw.lower():
            ST["instant_success"]=True; return
        if len(kw)>=3 and len(t)>=3 and kw[:3].lower()==t[:3].lower() and ST.get("lip_speaking"):
            ST["instant_success"]=True


# ══════════════════════════════════════════════════════════════════
# MAIN WINDOW — V6+V8 with themes, moods, music, 50 PECS
# ══════════════════════════════════════════════════════════════════
class ClickCard(QPushButton):
    def __init__(self,data,idx,parent=None):
        super().__init__(parent); self.idx=idx; self._data=data
        self.setFixedSize(150,150); self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._set_normal()
        self.clicked.connect(lambda: BRIDGE.sig_task.emit({"action":"click","idx":self.idx}))
    def _set_normal(self):
        d=self._data; th=get_theme()
        acc=th["accent"].name(); bg2=th["bg2"].name(); txt=th["text"].name()
        if "color" in d:
            self.setText(f"\n\n{d['label']}"); self.setFont(QFont("Arial",11,QFont.Weight.Bold))
            self.setStyleSheet(f"QPushButton{{background:{d['color']};border-radius:75px;"
                f"border:5px solid rgba(255,255,255,.3);color:white;font-weight:bold;}}"
                f"QPushButton:hover{{border:5px solid white;}}")
        else:
            self.setText(f"{d.get('emoji','?')}\n{d['label']}"); self.setFont(QFont("Arial",13,QFont.Weight.Bold))
            self.setStyleSheet(f"QPushButton{{background:{bg2};border-radius:18px;"
                f"border:4px solid {acc};color:{txt};font-weight:bold;padding:6px;}}"
                f"QPushButton:hover{{border:4px solid white;}}")
    def flash_correct(self): self.setStyleSheet(self.styleSheet()+"QPushButton{border:8px solid #22c55e!important;}")
    def flash_wrong(self):   self.setStyleSheet(self.styleSheet()+"QPushButton{border:8px solid #ef4444!important;}")
    def reset(self): self._set_normal()

class AvatarWidget(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent); self.setFixedSize(200,260)
        self._phase=0.0
        self._t=QTimer(); self._t.timeout.connect(self._tick); self._t.start(40)
    def _tick(self): self._phase+=0.12 if ST["is_speaking"] else 0.03; self.update()
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        th=get_theme(); p.fillRect(self.rect(),th["bg"])
        em=ST["emotion"]; lip=ST.get("lip_sync_value",0.0)
        sj=ST.get("social_joy_active",False)
        blink=int(self._phase*3)%44==0; cx,cy=100,120
        g=QLinearGradient(cx-40,cy+45,cx+40,cy+120)
        g.setColorAt(0,th["accent"]); g.setColorAt(1,th["accent2"])
        p.setBrush(QBrush(g)); p.setPen(QPen(th["text"],2))
        p.drawEllipse(cx-40,cy+45,80,75)
        p.setBrush(QBrush(th["bg"])); p.setPen(QPen(th["accent"],2))
        p.drawRoundedRect(cx-22,cy+55,44,32,4,4)
        p.setPen(th["text"]); p.setFont(QFont("Arial",6,QFont.Weight.Bold))
        p.drawText(QRect(cx-20,cy+60,40,16),Qt.AlignmentFlag.AlignCenter,"V6+V8")
        p.setPen(QPen(th["accent"],13,Qt.PenStyle.SolidLine,Qt.PenCapStyle.RoundCap))
        if sj:
            jt=time.time()
            p.drawLine(cx-40,cy+55,cx-75+int(20*math.sin(jt*4)),cy+15)
            p.drawLine(cx+40,cy+55,cx+75+int(20*math.sin(jt*4+1)),cy+15)
        elif ST["is_speaking"]:
            la=int(14*math.sin(self._phase))
            p.drawLine(cx-40,cy+60,cx-65+la,cy+90+la)
            p.drawLine(cx+40,cy+60,cx+65-la,cy+90-la)
        else:
            p.drawLine(cx-40,cy+62,cx-62,cy+94); p.drawLine(cx+40,cy+62,cx+62,cy+94)
        p.drawLine(cx-16,cy+118,cx-24,cy+152); p.drawLine(cx+16,cy+118,cx+24,cy+152)
        ht=ST.get("head_tilt",0.0)*5; hbob=int(3*math.sin(self._phase*.5))
        hx=cx+int(ht); hy=cy-46+hbob
        p.setBrush(QBrush(QColor(220,195,173))); p.setPen(QPen(QColor(200,175,155),2))
        p.drawEllipse(hx-40,hy-40,80,80)
        if em in ["happy","joyful"] or sj: ec=th["success"]
        elif em=="angry": ec=QColor(255,80,80)
        elif em=="sad": ec=QColor(100,120,220)
        else: ec=th["accent"]
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
        p.setPen(QPen(QColor(160,80,80),2)); mh=int(4+lip*14)
        if ST["is_speaking"]:
            p.setBrush(QBrush(QColor(160,80,80))); p.drawChord(hx-11,hy+14,22,mh*2,0,-180*16)
        elif em in ["happy","joyful"]:
            p.setBrush(QBrush(QColor(150,80,80))); p.drawChord(hx-10,hy+15,20,12,0,-180*16)
        elif em=="sad":
            p.setBrush(Qt.BrushStyle.NoBrush); p.drawArc(hx-10,hy+20,20,12,0,180*16)
        else: p.drawLine(hx-10,hy+18,hx+10,hy+18)
        p.setBrush(QBrush(QColor(210,185,163))); p.setPen(Qt.PenStyle.NoPen)
        for ex_ in [hx-40,hx+32]: p.drawEllipse(ex_,hy-8,14,14)
        if sj:
            jt2=time.time(); pr=int(75+11*abs(math.sin(jt2*4)))
            p.setPen(QPen(th["accent"],3)); p.setBrush(Qt.BrushStyle.NoBrush)
            p.drawEllipse(cx-pr,cy-pr,pr*2,pr*2)
        p.setPen(th["accent"]); p.setFont(QFont("Arial",7,QFont.Weight.Bold))
        p.drawText(QRect(0,2,200,14),Qt.AlignmentFlag.AlignCenter,
                   f"L{ST['conversation_level']} {CURRENT_MOOD['em']}")
        p.setPen(th["text"]); p.setFont(QFont("Arial",7))
        status=("Joy 🎉" if sj else "Speaking 🔊" if ST["is_speaking"]
                else "Recording 🔴" if ST["recording"] else "Ready 💤")
        p.drawText(QRect(0,228,200,20),Qt.AlignmentFlag.AlignCenter,status)
        p.end()

class PECSWidget(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent); self.setFixedHeight(92)
        self._lay=QHBoxLayout(self)
        self._lay.setContentsMargins(4,3,4,3); self._lay.setSpacing(4)
        self._build()
    def _build(self):
        th=get_theme()
        self.setStyleSheet(f"QWidget{{background:{th['bg'].name()};"
            f"border-top:2px solid {th['accent'].name()};}}")
        lbl=QLabel("PECS 50"); lbl.setFont(QFont("Arial",7,QFont.Weight.Bold))
        lbl.setStyleSheet(f"color:{th['accent'].name()};"); self._lay.addWidget(lbl)
        scroll=QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(84)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        inner=QWidget(); il=QHBoxLayout(inner)
        il.setContentsMargins(2,2,2,2); il.setSpacing(4)
        for emoji,name,phrase in PECS_ITEMS:
            btn=QPushButton(f"{emoji}\n{name[:8]}")
            btn.setFont(QFont("Arial",6,QFont.Weight.Bold)); btn.setFixedSize(72,76)
            btn.setStyleSheet(
                f"QPushButton{{background:{th['card'].name()};"
                f"border:2px solid {th['accent'].name()};"
                f"border-radius:8px;color:{th['text'].name()};}}"
                f"QPushButton:hover{{background:{th['bg2'].name()};"
                f"border-color:white;}}")
            btn.setToolTip(f"Say: {phrase}")
            btn.clicked.connect(lambda _,ph=phrase,nm=name: self._press(nm,ph))
            il.addWidget(btn)
        scroll.setWidget(inner); self._lay.addWidget(scroll,1)
    def _press(self,name,phrase):
        ST["pecs_log"].append({"time":datetime.now().strftime("%H:%M:%S"),
            "name":name,"phrase":phrase,"emotion":ST["emotion"]})
        if len(ST["pecs_log"])>100: ST["pecs_log"]=ST["pecs_log"][-100:]
        LOG(f"PECS: {name} — {phrase}")
        BRIDGE.sig_pecs.emit(phrase)
        if VOICE_REF: VOICE_REF.say_pecs(f"{CHILD_NAME} says: {phrase}")
    def refresh(self):
        while self._lay.count():
            item=self._lay.takeAt(0)
            if item.widget(): item.widget().deleteLater()
        self._build()

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"🤖 Pepper Clinical V6+V8 — {CHILD_NAME}")
        self.setFixedSize(1600,960)
        self._cards=[]; self._locked=True; self._correct_idx=-1
        self._recorder=TouchRecorder()
        self._build_ui(); self._connect_bridge()
        self._stats_t=QTimer(); self._stats_t.timeout.connect(self._refresh); self._stats_t.start(400)

    def _build_ui(self):
        root=QWidget(); self.setCentralWidget(root)
        outer=QVBoxLayout(root); outer.setSpacing(0); outer.setContentsMargins(0,0,0,0)
        # ── TOOLBAR ──
        tb=QFrame(); tb.setFixedHeight(44)
        tbl=QHBoxLayout(tb); tbl.setContentsMargins(8,3,8,3); tbl.setSpacing(8)
        tbl.addWidget(QLabel("🎨"))
        self.theme_cb=QComboBox(); self.theme_cb.setFixedWidth(165)
        for k,v in THEMES.items(): self.theme_cb.addItem(v["name"],k)
        self.theme_cb.currentIndexChanged.connect(
            lambda _: BRIDGE.sig_theme.emit(self.theme_cb.currentData()))
        tbl.addWidget(self.theme_cb)
        tbl.addWidget(QLabel("  🎙️"))
        self.voice_cb=QComboBox(); self.voice_cb.setFixedWidth(140)
        for vp in VOICE_PROFILES: self.voice_cb.addItem(vp["name"],vp["id"])
        self.voice_cb.currentIndexChanged.connect(
            lambda _: VOICE_REF.set_profile(self.voice_cb.currentData()) if VOICE_REF else None)
        tbl.addWidget(self.voice_cb)
        tbl.addWidget(QLabel("  🎵"))
        self.music_cb=QComboBox(); self.music_cb.setFixedWidth(155)
        self.music_cb.addItem("🔇 Off","none")
        for mt in MUSIC_TRACKS: self.music_cb.addItem(f"{mt['em']} {mt['name']}",mt["id"])
        self.music_cb.currentIndexChanged.connect(self._on_music)
        tbl.addWidget(self.music_cb)
        tbl.addWidget(QLabel("🔊"))
        self.vol_sl=QSlider(Qt.Orientation.Horizontal)
        self.vol_sl.setRange(0,100); self.vol_sl.setValue(30); self.vol_sl.setFixedWidth(80)
        self.vol_sl.valueChanged.connect(lambda v: MUSIC_ENGINE.set_volume(v/100))
        tbl.addWidget(self.vol_sl); tbl.addStretch()
        dash_btn=QPushButton("🌐 Dashboard"); dash_btn.setFixedSize(115,30)
        dash_btn.clicked.connect(lambda: webbrowser.open("http://localhost:5007"))
        tbl.addWidget(dash_btn)
        outer.addWidget(tb)
        # ── MOOD ROW ──
        mood_fr=QFrame(); mood_fr.setFixedHeight(64)
        ml=QHBoxLayout(mood_fr); ml.setContentsMargins(8,4,8,4); ml.setSpacing(4)
        ml.addWidget(QLabel("Mood:"))
        for mood in ASD_MOODS:
            btn=QPushButton(f"{mood['em']}\n{mood['label'][:5]}")
            btn.setFixedSize(62,54); btn.setFont(QFont("Arial",7,QFont.Weight.Bold))
            btn.setToolTip(mood["label"])
            btn.clicked.connect(lambda _,m=mood: BRIDGE.sig_mood.emit(m["id"]))
            ml.addWidget(btn)
        ml.addStretch()
        outer.addWidget(mood_fr)
        # ── MAIN ──
        main=QHBoxLayout(); main.setSpacing(0); main.setContentsMargins(0,0,0,0)
        # LEFT
        left=QFrame(); left.setFixedWidth(780)
        ll=QVBoxLayout(left); ll.setContentsMargins(0,0,0,0); ll.setSpacing(0)
        top_row=QWidget(); tr=QHBoxLayout(top_row); tr.setContentsMargins(0,0,0,0); tr.setSpacing(0)
        self.cam_lbl=QLabel(); self.cam_lbl.setFixedSize(580,460)
        self.cam_lbl.setStyleSheet("background:#000;"); self.cam_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tr.addWidget(self.cam_lbl)
        side=QWidget(); side.setFixedWidth(200); sl=QVBoxLayout(side); sl.setContentsMargins(0,0,0,0); sl.setSpacing(0)
        self.avatar=AvatarWidget(); sl.addWidget(self.avatar)
        self.emo_frame=QFrame(); self.emo_frame.setFixedSize(200,200)
        ef=QVBoxLayout(self.emo_frame); ef.setContentsMargins(4,4,4,4); ef.setSpacing(2)
        self.emo_lbl=QLabel("😐 neutral"); self.emo_lbl.setFont(QFont("Arial",9,QFont.Weight.Bold))
        self.emo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); ef.addWidget(self.emo_lbl)
        self.emo_bars={}
        for em_ in ["happy","joyful","surprised","sad","angry","fear","neutral"]:
            row=QWidget(); rl=QHBoxLayout(row); rl.setContentsMargins(2,0,2,0); rl.setSpacing(3)
            lb=QLabel(em_[:7]); lb.setFont(QFont("Arial",6)); lb.setFixedWidth(50); rl.addWidget(lb)
            bar=QProgressBar(); bar.setFixedHeight(7); bar.setRange(0,100); bar.setValue(0); bar.setTextVisible(False)
            col={"happy":"#22c55e","joyful":"#00ffc8","surprised":"#a78bfa","sad":"#3b82f6",
                 "angry":"#ef4444","fear":"#06b6d4","neutral":"#6b7280"}.get(em_,"#fff")
            bar.setStyleSheet(f"QProgressBar{{background:#1a1f40;border-radius:3px;border:none;}}"
                f"QProgressBar::chunk{{background:{col};border-radius:3px;}}")
            rl.addWidget(bar,1); ef.addWidget(row); self.emo_bars[em_]=bar
        self.lip_lbl=QLabel("👄 Lip: 0.00"); self.lip_lbl.setFont(QFont("Arial",7)); ef.addWidget(self.lip_lbl)
        self.finger_lbl2=QLabel("🖐️ Fingers: 0/10"); self.finger_lbl2.setFont(QFont("Arial",7)); ef.addWidget(self.finger_lbl2)
        sl.addWidget(self.emo_frame); tr.addWidget(side); ll.addWidget(top_row)
        sr_=QWidget(); srl=QHBoxLayout(sr_); srl.setContentsMargins(6,3,6,3)
        self.status_lbl=QLabel(f"👦 {CHILD_NAME}"); self.status_lbl.setFont(QFont("Arial",9,QFont.Weight.Bold))
        srl.addWidget(self.status_lbl,1); ll.addWidget(sr_)
        self.lip_bar=QProgressBar(); self.lip_bar.setFixedHeight(6); self.lip_bar.setRange(0,100)
        self.lip_bar.setValue(0); self.lip_bar.setTextVisible(False)
        self.lip_bar.setStyleSheet("QProgressBar{background:#1a1f40;border-radius:3px;border:none;}"
            "QProgressBar::chunk{background:#00ffc8;border-radius:3px;}"); ll.addWidget(self.lip_bar)
        ch_lbl=QLabel("💬 Pepper Chat | Whisper AI + Lip Motion")
        ch_lbl.setFont(QFont("Arial",8,QFont.Weight.Bold)); ch_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ll.addWidget(ch_lbl)
        self.chat_area=QTextEdit(); self.chat_area.setReadOnly(True)
        self.chat_area.setFont(QFont("Arial",9)); self.chat_area.setFixedHeight(78); ll.addWidget(self.chat_area)
        cir=QWidget(); cirow=QHBoxLayout(cir); cirow.setContentsMargins(4,2,4,2); cirow.setSpacing(4)
        self.chat_input=QLineEdit(); self.chat_input.setPlaceholderText("Type message… (Enter)")
        self.chat_input.setFont(QFont("Arial",10)); self.chat_input.setFixedHeight(32)
        self.chat_input.returnPressed.connect(self._send_chat); cirow.addWidget(self.chat_input,1)
        sb2=QPushButton("Send"); sb2.setFixedSize(65,32); sb2.clicked.connect(self._send_chat); cirow.addWidget(sb2)
        ll.addWidget(cir); main.addWidget(left)
        # RIGHT
        right=QWidget(); right.setFixedWidth(820)
        rl=QVBoxLayout(right); rl.setSpacing(5); rl.setContentsMargins(10,6,10,6)
        hdr=QFrame(); hdr.setFixedHeight(58)
        hl=QHBoxLayout(hdr); hl.setContentsMargins(12,4,12,4)
        av_lbl=QLabel("🤖"); av_lbl.setFont(QFont("Arial",22)); hl.addWidget(av_lbl)
        tw_=QWidget(); tl2=QVBoxLayout(tw_); tl2.setSpacing(1)
        self.title_lbl=QLabel("Pepper Clinical V6+V8 — Enhanced")
        self.title_lbl.setFont(QFont("Arial",12,QFont.Weight.Bold)); tl2.addWidget(self.title_lbl)
        self.child_lbl=QLabel(f"Child: {CHILD_NAME} | ABA/DTT/TEACCH/ESDM/TIE | 5200+ Tasks | 50 PECS | 5 Themes | 13 Moods")
        self.child_lbl.setFont(QFont("Arial",8)); tl2.addWidget(self.child_lbl); hl.addWidget(tw_,1)
        sw_=QWidget(); sl_=QVBoxLayout(sw_); sl_.setSpacing(1)
        self.state_lbl=QLabel("💤 Ready"); self.state_lbl.setFont(QFont("Arial",8))
        sl_.addWidget(self.state_lbl,alignment=Qt.AlignmentFlag.AlignRight)
        self.clvl_lbl=QLabel("Level 1"); self.clvl_lbl.setFont(QFont("Arial",8))
        sl_.addWidget(self.clvl_lbl,alignment=Qt.AlignmentFlag.AlignRight)
        hl.addWidget(sw_); rl.addWidget(hdr)
        sched=QFrame(); sched.setFixedHeight(44)
        sc=QHBoxLayout(sched); sc.setContentsMargins(10,4,10,4); sc.setSpacing(7)
        self.sched_task=QLabel("📋 Task"); self.sched_task.setFont(QFont("Arial",9,QFont.Weight.Bold))
        sc.addWidget(self.sched_task)
        sw2=QWidget(); sl2_=QVBoxLayout(sw2); sl2_.setSpacing(0); sl2_.setContentsMargins(0,0,0,0)
        self.stars_lbl=QLabel("☆ ☆ ☆"); self.stars_lbl.setFont(QFont("Arial",14))
        self.stars_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); sl2_.addWidget(self.stars_lbl)
        self.mastery_sub=QLabel("0/3"); self.mastery_sub.setFont(QFont("Arial",7))
        self.mastery_sub.setAlignment(Qt.AlignmentFlag.AlignCenter); sl2_.addWidget(self.mastery_sub)
        sc.addWidget(sw2,1)
        self.reward_lbl=QLabel("⭐"); self.reward_lbl.setFont(QFont("Arial",18)); sc.addWidget(self.reward_lbl)
        rl.addWidget(sched)
        if_fr=QFrame(); if_fr.setFixedHeight(70)
        il=QVBoxLayout(if_fr); il.setContentsMargins(12,3,12,3)
        self.instr_icon=QLabel("📋"); self.instr_icon.setFont(QFont("Arial",14))
        self.instr_icon.setAlignment(Qt.AlignmentFlag.AlignCenter); il.addWidget(self.instr_icon)
        self.instr_lbl=QLabel("Pepper is loading…"); self.instr_lbl.setFont(QFont("Arial",13,QFont.Weight.Bold))
        self.instr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); self.instr_lbl.setWordWrap(True)
        il.addWidget(self.instr_lbl); rl.addWidget(if_fr)
        self.content_fr=QFrame(); self.content_fr.setMinimumHeight(260)
        self.content_lay=QVBoxLayout(self.content_fr)
        self.content_lay.setContentsMargins(12,10,12,10); self.content_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl=QLabel("🤖\nReady!"); lbl.setFont(QFont("Arial",16,QFont.Weight.Bold))
        lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); self.content_lay.addWidget(lbl)
        rl.addWidget(self.content_fr,1)
        self.lock_ov=QLabel("🔒"); self.lock_ov.setParent(self.content_fr)
        self.lock_ov.setGeometry(0,0,800,260); self.lock_ov.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lock_ov.setFont(QFont("Arial",44))
        self.lock_ov.setStyleSheet("QLabel{background:rgba(0,0,0,.52);border-radius:12px;}"); self.lock_ov.hide()
        fb_fr=QFrame(); fb_fr.setFixedHeight(44)
        fl=QHBoxLayout(fb_fr); fl.setContentsMargins(12,6,12,6)
        self.fb_icon=QLabel("💤"); self.fb_icon.setFont(QFont("Arial",19)); fl.addWidget(self.fb_icon)
        self.fb_lbl=QLabel("Waiting for Pepper…"); self.fb_lbl.setFont(QFont("Arial",11,QFont.Weight.Bold))
        self.fb_lbl.setWordWrap(True); fl.addWidget(self.fb_lbl,1); rl.addWidget(fb_fr)
        mic_row=QWidget(); mic_lay=QVBoxLayout(mic_row); mic_lay.setContentsMargins(0,0,0,0); mic_lay.setSpacing(3)
        self.mic_btn=QPushButton("🎤  Hold to Speak — Say the word!"); self.mic_btn.setFixedHeight(50)
        self.mic_btn.setFont(QFont("Arial",12,QFont.Weight.Bold))
        self.mic_btn.setStyleSheet("QPushButton{background:#dc2626;color:white;border-radius:25px;border:3px solid #fca5a5;}"
            "QPushButton:pressed{background:#991b1b;border:4px solid white;}")
        self.mic_btn.pressed.connect(self._on_mic_press); self.mic_btn.released.connect(self._on_mic_release)
        mic_lay.addWidget(self.mic_btn)
        self.mic_wave=QProgressBar(); self.mic_wave.setFixedHeight(7); self.mic_wave.setRange(0,100)
        self.mic_wave.setValue(0); self.mic_wave.setTextVisible(False)
        self.mic_wave.setStyleSheet("QProgressBar{background:#1a1f40;border-radius:3px;border:none;}"
            "QProgressBar::chunk{background:#22c55e;border-radius:3px;}"); mic_lay.addWidget(self.mic_wave)
        self.rec_status=QLabel("🎤 Whisper AI + Lip Verification — Ready!")
        self.rec_status.setFont(QFont("Arial",8)); self.rec_status.setAlignment(Qt.AlignmentFlag.AlignCenter)
        mic_lay.addWidget(self.rec_status); rl.addWidget(mic_row)
        sb_=QFrame(); sb_.setFixedHeight(38)
        stl=QHBoxLayout(sb_); stl.setContentsMargins(8,2,8,2)
        for lbl2,attr,col in [("Score","stat_score","#a78bfa"),("Tokens","stat_tokens","#fbbf24"),
            ("Mastered","stat_mastered","#34d399"),("Streak","stat_streak","#60a5fa"),
            ("Skip","stat_skipped","#f87171"),("Daily%","stat_daily","#34d399"),("⏱ms","stat_resp","#60a5fa")]:
            w_=QWidget(); wl_=QVBoxLayout(w_); wl_.setSpacing(0); wl_.setContentsMargins(0,0,0,0)
            val=QLabel("0"); val.setFont(QFont("Arial",10,QFont.Weight.Bold))
            val.setStyleSheet(f"color:{col};"); val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lb_=QLabel(lbl2); lb_.setFont(QFont("Arial",6)); lb_.setStyleSheet("color:#6b7280;")
            lb_.setAlignment(Qt.AlignmentFlag.AlignCenter)
            wl_.addWidget(val); wl_.addWidget(lb_); stl.addWidget(w_); setattr(self,attr,val)
        rl.addWidget(sb_); main.addWidget(right)
        outer.addLayout(main)
        self.pecs=PECSWidget(); outer.addWidget(self.pecs)

    def _connect_bridge(self):
        BRIDGE.sig_task.connect(self._on_task)
        BRIDGE.sig_success.connect(lambda m:(self.fb_lbl.setText(f"✅ {m}"),
            self.fb_lbl.setStyleSheet("color:#22c55e;font-weight:bold;font-size:13px;"),
            self.fb_icon.setText("🎉")) or None)
        BRIDGE.sig_fail.connect(lambda m:(self.fb_lbl.setText(f"❌ {m}"),
            self.fb_lbl.setStyleSheet("color:#ef4444;font-weight:bold;"),
            self.fb_icon.setText("💪")) or None)
        BRIDGE.sig_skip.connect(lambda m:(self.fb_lbl.setText(f"⏭ {m}"),
            self.fb_lbl.setStyleSheet("color:#f59e0b;font-weight:bold;"),
            self.fb_icon.setText("⏩")) or None)
        BRIDGE.sig_instr.connect(lambda m: self.instr_lbl.setText(m))
        BRIDGE.sig_waiting.connect(lambda m: self.state_lbl.setText(m))
        BRIDGE.sig_unlock.connect(self._do_unlock); BRIDGE.sig_lock.connect(self._do_lock)
        BRIDGE.sig_reset.connect(self._reset_cards)
        BRIDGE.sig_joy.connect(lambda _:(ST.__setitem__("social_joy_active",True),
            QTimer.singleShot(4000,lambda: ST.__setitem__("social_joy_active",False))) or None)
        BRIDGE.sig_camera.connect(self._update_cam); BRIDGE.sig_stats.connect(self._refresh)
        BRIDGE.sig_chat.connect(self._add_chat); BRIDGE.sig_rec_stop.connect(self._on_rec_stop)
        BRIDGE.sig_mic_lvl.connect(lambda v: self.mic_wave.setValue(int(v*100)))
        BRIDGE.sig_pecs.connect(lambda ph: self._add_chat("Child",f"[PECS] {ph}"))
        BRIDGE.sig_theme.connect(self._apply_theme)
        BRIDGE.sig_mood.connect(self._apply_mood)
        BRIDGE.sig_clap.connect(play_clap)
        BRIDGE.sig_mega_celebrate.connect(self._show_mega_celebration)
        BRIDGE.sig_youtube.connect(self._show_youtube)
        self._lip_t=QTimer(); self._lip_t.timeout.connect(
            lambda: self.lip_bar.setValue(min(100,int(ST.get("lip_motion",0)*40))))
        self._lip_t.start(100)

    def _apply_theme(self,tid):
        global CURRENT_THEME; CURRENT_THEME=tid; ST["current_theme"]=tid
        th=get_theme()
        self.setStyleSheet(
            f"QMainWindow,QWidget{{background:{th['bg'].name()};color:{th['text'].name()};}}"
            f"QFrame{{background:{th['bg2'].name()};border:1px solid rgba(255,255,255,.08);border-radius:10px;}}"
            f"QPushButton{{background:{th['accent'].name()};color:#fff;border-radius:8px;"
            f"font-weight:bold;padding:6px 12px;border:none;}}"
            f"QPushButton:hover{{background:{th['bg2'].name()};color:{th['accent'].name()};"
            f"border:2px solid {th['accent'].name()};}}"
            f"QLabel{{color:{th['text'].name()};background:transparent;}}"
            f"QLineEdit,QTextEdit{{background:{th['card'].name()};color:{th['text'].name()};"
            f"border:2px solid rgba(255,255,255,.1);border-radius:8px;padding:5px;}}"
            f"QComboBox{{background:{th['card'].name()};color:{th['text'].name()};"
            f"border:2px solid rgba(255,255,255,.1);border-radius:8px;padding:4px 8px;}}"
            f"QScrollBar:vertical{{background:{th['bg2'].name()};width:8px;border-radius:4px;}}"
            f"QScrollBar::handle:vertical{{background:{th['accent'].name()};border-radius:4px;}}"
            f"QSlider::groove:horizontal{{background:{th['bg2'].name()};height:6px;border-radius:3px;}}"
            f"QSlider::handle:horizontal{{background:{th['accent'].name()};width:14px;height:14px;"
            f"border-radius:7px;margin:-4px 0;}}")
        if hasattr(self,"pecs"): self.pecs.refresh()
        log.info(f"🎨 Theme: {THEMES[tid]['name']}")

    def _apply_mood(self,mid):
        global CURRENT_MOOD
        mood=next((m for m in ASD_MOODS if m["id"]==mid),ASD_MOODS[0])
        CURRENT_MOOD=mood; ST["current_mood"]=mid
        if VOICE_REF:
            threading.Thread(target=VOICE_REF.say,args=(mood["speech"],True),daemon=True).start()
        music_id=mood["music"]
        for i in range(self.music_cb.count()):
            if self.music_cb.itemData(i)==music_id:
                self.music_cb.setCurrentIndex(i); break
        log.info(f"{mood['em']} Mood: {mood['label']}")

    def _on_music(self,_):
        mid=self.music_cb.currentData(); ST["current_music"]=mid
        if mid=="none": MUSIC_ENGINE.stop()
        else: MUSIC_ENGINE.play(mid)

    def _update_cam(self,qimg):
        if isinstance(qimg,QImage):
            pix=QPixmap.fromImage(qimg).scaled(580,460,Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            self.cam_lbl.setPixmap(pix)
        pct=ST.get("emotion_pct",{})
        for em_,bar in self.emo_bars.items(): bar.setValue(pct.get(em_,0))
        em=ST["emotion"]
        emojis={"happy":"😊","joyful":"😄","sad":"😢","angry":"😠","fear":"😨","surprised":"😲","neutral":"😐"}
        self.emo_lbl.setText(f"{emojis.get(em,'😐')} {em}")
        self.lip_lbl.setText(f"👄 Lip:{ST.get('lip_motion',0):.2f} {'[SPEECH]' if ST['lip_speaking'] else ''}")
        self.finger_lbl2.setText(f"🖐️ Fingers:{ST['finger_count']}/10")
        self.status_lbl.setText(f"👦{CHILD_NAME}|{em}|L{ST['conversation_level']}"
            f"|{CURRENT_MOOD['em']}|Attn:{ST['attention']}%|{'👄' if ST['lip_speaking'] else '·'}")

    def _refresh(self):
        self.stat_score.setText(str(ST["score"])); self.stat_tokens.setText(str(ST["tokens"]))
        self.stat_mastered.setText(str(ST["mastered"])); self.stat_streak.setText(str(ST["streak"]))
        self.stat_skipped.setText(str(ST["tasks_skipped"])); self.stat_daily.setText(f"{ST['skill_daily']:.0f}%")
        rt=ST["resp_times"]
        if rt: self.stat_resp.setText(str(int(sum(rt[-10:])/len(rt[-10:]))))
        c=ST["consecutive"]
        self.stars_lbl.setText("★"*c+"☆"*(3-c)); self.mastery_sub.setText(f"{c}/3")
        self.reward_lbl.setText(f"⭐{ST['score']}"); self.clvl_lbl.setText(f"Level {ST['conversation_level']}")

    def _on_task(self,task:dict):
        if task.get("action")=="click": self._handle_click(task.get("idx",0)); return
        self._clear(); self._locked=True; self.lock_ov.hide()
        self.sched_task.setText(f"📋 {task.get('name','Task')[:22]}")
        mode=task.get("tablet_mode","")
        if mode=="motor":
            nl=QLabel(task.get("name","")); nl.setFont(QFont("Arial",20,QFont.Weight.Bold))
            nl.setAlignment(Qt.AlignmentFlag.AlignCenter); self.content_lay.addWidget(nl)
            il=QLabel(task.get("instruction","")); il.setFont(QFont("Arial",14,QFont.Weight.Bold))
            il.setAlignment(Qt.AlignmentFlag.AlignCenter); il.setWordWrap(True); self.content_lay.addWidget(il)
            done=QPushButton("✅ Done! Tap here"); done.setFixedHeight(50)
            done.setFont(QFont("Arial",13,QFont.Weight.Bold))
            done.clicked.connect(lambda: ST.__setitem__("instant_success",True))
            self.content_lay.addWidget(done)
        elif mode=="grid":
            opts=task.get("options",[]); self._correct_idx=task.get("correct",0)
            grid=QWidget(); gl=QGridLayout(grid); gl.setSpacing(10); gl.setContentsMargins(8,8,8,8)
            for i,opt in enumerate(opts):
                card=ClickCard(opt,i,None); gl.addWidget(card,i//2,i%2); self._cards.append(card)
            self.content_lay.addWidget(grid); self._do_unlock()
        elif mode=="number":
            n=task.get("target_number",1)
            big=QLabel(str(n)); big.setFont(QFont("Arial",80,QFont.Weight.Bold))
            big.setAlignment(Qt.AlignmentFlag.AlignCenter); self.content_lay.addWidget(big)
            hint=QLabel(f"Show me {n} fingers! 🖐️"); hint.setFont(QFont("Arial",14,QFont.Weight.Bold))
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter); self.content_lay.addWidget(hint)
        else:
            txt=task.get("word_text") or task.get("social_text") or task.get("daily_label","")
            emoji=task.get("daily_emoji","🗣️")
            el=QLabel(emoji); el.setFont(QFont("Arial",56)); el.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.content_lay.addWidget(el)
            wl=QLabel(str(txt)); wl.setFont(QFont("Arial",28,QFont.Weight.Bold))
            wl.setAlignment(Qt.AlignmentFlag.AlignCenter); self.content_lay.addWidget(wl)
            hl=QLabel("🎤 Hold mic and say the word!")
            hl.setFont(QFont("Arial",11)); hl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.content_lay.addWidget(hl)

    def _handle_click(self,idx:int):
        if self._locked: return
        self._do_lock()
        if idx==self._correct_idx:
            for c in self._cards:
                if c.idx==idx: c.flash_correct()
            ST["tablet_click_result"]="correct"; ST["instant_success"]=True
        else:
            for c in self._cards:
                if c.idx==idx: c.flash_wrong()
                elif c.idx==self._correct_idx: c.flash_correct()
            ST["tablet_click_result"]="wrong"

    def _clear(self):
        for i in reversed(range(self.content_lay.count())):
            w=self.content_lay.itemAt(i).widget()
            if w: w.setParent(None)
        self._cards=[]

    def _do_unlock(self):
        self._locked=False; self.lock_ov.hide(); [c.setEnabled(True) for c in self._cards]
    def _do_lock(self):
        self._locked=True; self.lock_ov.show(); [c.setEnabled(False) for c in self._cards]
    def _reset_cards(self): [c.reset() for c in self._cards]

    def _on_mic_press(self):
        self.mic_btn.setText("🔴  Recording…")
        self.mic_btn.setStyleSheet("QPushButton{background:#991b1b;color:white;border-radius:25px;border:4px solid white;}")
        self.rec_status.setText("🔴 Recording with Whisper AI…"); self._recorder.start()

    def _on_mic_release(self):
        self.mic_btn.setText("🎤  Hold to Speak — Say the word!")
        self.mic_btn.setStyleSheet("QPushButton{background:#dc2626;color:white;border-radius:25px;border:3px solid #fca5a5;}"
            "QPushButton:pressed{background:#991b1b;border:4px solid white;}")
        self.rec_status.setText("⏳ Processing…")
        threading.Thread(target=self._do_rec,daemon=True).start()

    def _do_rec(self):
        text=self._recorder.stop_and_recognise(); ST["last_speech_text"]=text; BRIDGE.sig_rec_stop.emit(text)

    def _on_rec_stop(self,text:str):
        ST["recording"]=False
        if text: self.rec_status.setText(f"👂 Heard: \"{text}\""); self._add_chat("Child",text)
        else:
            lip="(lip motion)" if ST["lip_speaking"] else ""
            self.rec_status.setText(f"❌ Didn't hear {lip} — try again")

    def _send_chat(self):
        msg=self.chat_input.text().strip()
        if not msg: return
        self.chat_input.clear(); self._add_chat("Therapist",msg)
        threading.Thread(target=self._proc_chat,args=(msg,),daemon=True).start()

    def _proc_chat(self,msg:str):
        if _GENAI:
            try:
                mdl=genai.GenerativeModel("gemini-1.5-flash")
                ctx=(f"Pepper therapy robot for {CHILD_NAME}, age {CHILD_AGE}, ASD. "
                     f"Score={ST['score']}, emotion={ST['emotion']}, mood={ST['current_mood']}, "
                     f"level={ST['conversation_level']}. Reply in 2-3 sentences.")
                resp=mdl.generate_content(ctx+"\nTherapist: "+msg)
                rep=resp.text.strip()[:300]
            except: rep=f"Great question! {CHILD_NAME} is doing wonderfully!"
        else: rep=f"Hi! I am Pepper! {CHILD_NAME} is making great progress!"
        BRIDGE.sig_chat.emit("Pepper",rep)
        if VOICE_REF: VOICE_REF.say(rep)

    def _add_chat(self,role:str,msg:str):
        th=get_theme(); t=datetime.now().strftime("%H:%M:%S")
        col={"Pepper":th["accent"].name(),"Therapist":"#60a5fa","Child":"#34d399"}.get(role,"#9ca3af")
        icon={"Pepper":"🤖","Therapist":"👩","Child":"👦"}.get(role,"💬")
        self.chat_area.append(f'<span style="color:{col};font-weight:bold">{icon}[{t}]:</span>'
            f' <span style="color:{th["text"].name()}">{msg}</span>')
        sb=self.chat_area.verticalScrollBar()
        if sb: sb.setValue(sb.maximum())
        ST["session_chat"].append({"role":role,"text":msg,"time":t})
        if len(ST["session_chat"])>60: ST["session_chat"]=ST["session_chat"][-60:]



    def _show_mega_celebration(self):
        th=get_theme()
        dlg=QWidget(self,Qt.WindowType.Window)
        dlg.setWindowTitle("Celebration!")
        dlg.setFixedSize(640,400)
        dlg.setStyleSheet(
            "QWidget{background:"+th["bg"].name()+";"
            "border:6px solid "+th["accent"].name()+";}")
        lay=QVBoxLayout(dlg)
        lay.setContentsMargins(20,20,20,20); lay.setSpacing(14)
        el=QLabel("🎊 🌟 🎉 🏆 ⭐ 🎊 🌟 🎉")
        el.setFont(QFont("Arial",28))
        el.setAlignment(Qt.AlignmentFlag.AlignCenter)
        el.setStyleSheet("color:"+th["accent"].name()+";background:transparent;")
        lay.addWidget(el)
        ml=QLabel("AMAZING "+CHILD_NAME.upper()+"!")
        ml.setFont(QFont("Arial",32,QFont.Weight.Bold))
        ml.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ml.setStyleSheet("color:"+th["accent"].name()+";background:transparent;")
        lay.addWidget(ml)
        sl=QLabel(str(ST["tasks_success"])+" Correct! Score: "+str(ST["score"])+" | Streak: "+str(ST["streak"]))
        sl.setFont(QFont("Arial",14,QFont.Weight.Bold))
        sl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl.setStyleSheet("color:"+th["text"].name()+";background:transparent;")
        lay.addWidget(sl)
        stl=QLabel("★ ★ ★ ★ ★ ★ ★ ★ ★ ★")
        stl.setFont(QFont("Arial",24))
        stl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        stl.setStyleSheet("color:#fbbf24;background:transparent;")
        lay.addWidget(stl)
        btn=QPushButton("✅ Keep Going! You are a Champion!")
        btn.setFixedHeight(52); btn.setFont(QFont("Arial",14,QFont.Weight.Bold))
        btn.setStyleSheet("QPushButton{background:"+th["accent"].name()+";color:#fff;border-radius:26px;border:none;}")
        btn.clicked.connect(dlg.close); lay.addWidget(btn)
        dlg.show()
        for i in range(3): QTimer.singleShot(i*400,play_clap)
        if VOICE_REF:
            threading.Thread(target=VOICE_REF.say,
                args=("Wow "+CHILD_NAME+"! Ten correct answers! You are a superstar! Your score is "+str(ST["score"])+"! Amazing!",True),
                daemon=True).start()
        QTimer.singleShot(12000,dlg.close)
        LOG("🎊 Mega celebration! "+str(ST["tasks_success"])+" correct!","success")

    def _show_youtube(self,embed_url):
        th=get_theme()
        vid=next((v for v in YOUTUBE_VIDEOS if v["embed"]==embed_url),
                 {"title":"Daily Life Video","embed":embed_url,
                  "url":"https://youtube.com","desc":"Educational video"})
        dlg=QWidget(self,Qt.WindowType.Window)
        dlg.setWindowTitle("📺 "+vid.get("title","Video"))
        dlg.setFixedSize(760,500)
        dlg.setStyleSheet("QWidget{background:"+th["bg"].name()+";}")
        lay=QVBoxLayout(dlg); lay.setContentsMargins(12,12,12,12); lay.setSpacing(8)
        tlbl=QLabel("📺 "+vid.get("title","Daily Life Video"))
        tlbl.setFont(QFont("Arial",13,QFont.Weight.Bold))
        tlbl.setStyleSheet("color:"+th["accent"].name()+";background:transparent;")
        tlbl.setAlignment(Qt.AlignmentFlag.AlignCenter); lay.addWidget(tlbl)
        try:
            from PyQt6.QtWebEngineWidgets import QWebEngineView
            web=QWebEngineView(); web.setFixedHeight(350)
            html=("<html><body style='margin:0;background:#000'>"
                  "<iframe width='736' height='350' src='"+embed_url+"?rel=0&modestbranding=1'"
                  " frameborder='0' allowfullscreen></iframe>"
                  "</body></html>")
            web.setHtml(html); lay.addWidget(web)
        except:
            info=QLabel(vid.get("desc","Educational video")+"\n\nClick Open to watch in browser")
            info.setFont(QFont("Arial",12)); info.setWordWrap(True)
            info.setAlignment(Qt.AlignmentFlag.AlignCenter)
            info.setStyleSheet("color:"+th["text"].name()+";background:transparent;padding:20px;")
            info.setFixedHeight(180); lay.addWidget(info)
            ob=QPushButton("🌐 Open in Browser"); ob.setFixedHeight(42)
            ob.setFont(QFont("Arial",12,QFont.Weight.Bold))
            ob.setStyleSheet("QPushButton{background:"+th["accent"].name()+";color:#fff;border-radius:21px;border:none;}")
            ob.clicked.connect(lambda: webbrowser.open(vid.get("url","https://youtube.com")))
            lay.addWidget(ob)
        desc=QLabel(vid.get("desc",""))
        desc.setFont(QFont("Arial",9)); desc.setWordWrap(True)
        desc.setAlignment(Qt.AlignmentFlag.AlignCenter)
        desc.setStyleSheet("color:"+th["text"].name()+";background:transparent;")
        lay.addWidget(desc)
        cb=QPushButton("✅ Done Watching — Continue Therapy!")
        cb.setFixedHeight(44); cb.setFont(QFont("Arial",11,QFont.Weight.Bold))
        cb.setStyleSheet("QPushButton{background:#059669;color:#fff;border-radius:22px;border:none;}")
        cb.clicked.connect(dlg.close); lay.addWidget(cb)
        dlg.show()
        if VOICE_REF:
            threading.Thread(target=VOICE_REF.say,
                args=("Let us watch a video about "+vid.get("title","daily life")+"!",True),
                daemon=True).start()
        LOG("📺 Video: "+vid.get("title",""))

# ══════════════════════════════════════════════════════════════════
# THERAPY CONTROLLER — clap on every correct answer
# ══════════════════════════════════════════════════════════════════
class TherapyController(threading.Thread):
    def __init__(self,voice,pb):
        super().__init__(daemon=True); self.v=voice; self.pb=pb
        self._running=True; self._fail=0

    def run(self):
        time.sleep(4.0)
        self.v.say(f"Hello {CHILD_NAME}! I am Pepper! Let us learn together!")
        while self._running:
            try: self._show()
            except Exception as e: log.warning(f"Controller: {e}"); time.sleep(1.0)

    def _show(self):
        task=get_next_task(); self._fail=0; ST["_fail_count"]=0
        ST["instant_success"]=False; ST["tablet_click_result"]=None
        ST["_current_task_keyword"]=task.get("keyword","").strip()
        ST["last_task_name"]=task.get("name","—")
        self.pb.send(gaze="child" if task.get("verify")=="motor" else "tablet",is_speaking=False)
        BRIDGE.sig_reset.emit(); BRIDGE.sig_instr.emit(task.get("instruction",""))
        BRIDGE.sig_task.emit(task); BRIDGE.sig_stats.emit()
        self.v.say(task["instruction"],wait=True)
        prompts=task.get("prompts",[]); pidx=0
        for attempt in range(MAX_FAILS+2):
            if not self._running: return
            if ST.get("instant_success"): break
            BRIDGE.sig_waiting.emit(task["waiting"])
            self._dtt(task,attempt)
            if ST.get("instant_success"): break
            if self._fail>=MAX_FAILS: break
            if prompts and pidx<len(prompts):
                self.v.say(prompts[pidx]); pidx+=1
            time.sleep(0.4)
        if ST.get("instant_success"): self._success(task)
        else: self._skip(task)

    def _dtt(self,task,attempt):
        verify=task.get("verify","motor")
        wait_s={"motor":8.0,"tablet_click":12.0,"finger_count":9.0,"speech_keyword":12.0}.get(verify,10.0)
        if verify=="motor":
            ST["verify_action"]=task.get("id","").split("_")[0]
            ST["verify_timeout"]=time.time()+wait_s; ST["verify_result"]=False
        elif verify=="finger_count":
            ST["finger_target"]=task.get("target_number",1)
        ST["instant_success"]=False; deadline=time.time()+wait_s
        while time.time()<deadline:
            if not self._running: return
            if ST.get("instant_success"): return
            if verify=="tablet_click" and ST.get("tablet_click_result"):
                if ST["tablet_click_result"]=="correct": ST["instant_success"]=True
                else: self._fail+=1; ST["_fail_count"]=self._fail
                return
            if verify=="finger_count" and ST["finger_count"]==ST.get("finger_target",1):
                ST["instant_success"]=True; return
            if verify=="motor" and ST.get("verify_result"):
                ST["instant_success"]=True; return
            time.sleep(0.08)
        self._fail+=1; ST["_fail_count"]=self._fail

    def _success(self,task):
        rt=int((time.time()-ST["_task_start_time"])*1000)
        ST["resp_times"].append(rt)
        if len(ST["resp_times"])>60: ST["resp_times"]=ST["resp_times"][-60:]
        pts=task.get("tokens",2)*5
        ST["score"]+=pts; ST["tokens"]+=task.get("tokens",2)
        ST["streak"]+=1; ST["consecutive"]+=1; ST["tasks_success"]+=1
        dom=task.get("domain","Motor")
        key={"Motor":"skill_motor","Cognitive":"skill_cognitive","Verbal":"skill_verbal",
             "Math":"skill_math","Social":"skill_social","Daily":"skill_daily"}.get(dom)
        if key: ST[key]=min(100,ST[key]+random.uniform(0.8,2.2))
        if ST["consecutive"]>=3:
            ST["mastered"]+=1; ST["tasks_mastered"]=ST["mastered"]; ST["consecutive"]=0
            if ST["score"]%80<pts: ST["conversation_level"]=min(3,ST["conversation_level"]+1)
        msg=task.get("success","Well done!")
        ST["last_result"]="✅ "+msg
        LOG(f"✅ {msg} rt={rt}ms","success")
        base_id=task.get("base_id","")
        if base_id: _child_done.add(base_id); db_add_task(CHILD_NAME,base_id,"success")
        ST["child_done_count"]=len(_child_done)
        log_csv(task["id"],dom,task.get("protocol","ABA"),True,
                ST["score"],ST["emotion"],ST["conversation_level"],rt)
        BRIDGE.sig_success.emit(msg); BRIDGE.sig_joy.emit(task.get("joy","celebrate"))
        # ── CLAP SOUND every correct answer ────────────────────
        BRIDGE.sig_clap.emit()
        # ────────────────────────────────────────────────────────
        # ── MEGA CELEBRATION every 10 correct answers ───────────
        # ── Update milestone + year-level tracking ────────────────
        ST["milestones_reached"]=ST["tasks_success"]//10
        ST["next_milestone_in"]=10-(ST["tasks_success"]%10)
        year=task.get("year",1)
        if year==1: ST["tasks_in_year1"]+=1; ST["current_year_level"]=1
        elif year==2: ST["tasks_in_year2"]+=1; ST["current_year_level"]=2
        elif year==3: ST["tasks_in_year3"]+=1; ST["current_year_level"]=3
        # ── MEGA CELEBRATION every 10 correct answers ───────────
        if ST["tasks_success"] % 10 == 0 and ST["tasks_success"] > 0:
            BRIDGE.sig_mega_celebrate.emit()
            # Show a relevant YouTube video after every 10 correct
            vid=random.choice(YOUTUBE_VIDEOS)
            BRIDGE.sig_youtube.emit(vid["embed"])
            LOG(f"🎊 Milestone! {ST['tasks_success']} correct! Playing: {vid['title']}","success")
        # ────────────────────────────────────────────────────────
        self.pb.send(is_speaking=True,sj=True,lip=0.9,gaze="child")
        self.v.say(msg)
        joy=task.get("joy","")
        if joy=="full_joy": self.v.say(f"Excellent {CHILD_NAME}! You are amazing!")
        elif joy=="dance":  self.v.say(f"Great job {CHILD_NAME}! Keep it up!")
        else:               self.v.say(f"Correct {CHILD_NAME}! Wonderful!")
        self.pb.send(is_speaking=False,sj=False,gaze="child")
        BRIDGE.sig_stats.emit(); time.sleep(1.2)

    def _skip(self,task):
        ST["tasks_skipped"]+=1; ST["streak"]=0
        msg=task.get("fail","Let us try the next task!")
        ST["last_result"]="⏭ "+msg; LOG(f"❌ Skip","fail")
        base_id=task.get("base_id","")
        if base_id: _child_done.add(base_id); db_add_task(CHILD_NAME,base_id,"fail")
        ST["child_done_count"]=len(_child_done)
        log_csv(task["id"],task.get("domain","Motor"),task.get("protocol","ABA"),
                False,ST["score"],ST["emotion"],ST["conversation_level"],0)
        BRIDGE.sig_skip.emit(msg)
        self.v.say(f"Let us try something new {CHILD_NAME}! You can do it!")
        BRIDGE.sig_stats.emit(); time.sleep(0.6)

    def stop(self): self._running=False

# ══════════════════════════════════════════════════════════════════
# FLASK DASHBOARD — 9 tabs with Live Monitor
# ══════════════════════════════════════════════════════════════════
def gemini_chat(q):
    if not _GENAI: return "Gemini not available."
    try:
        mdl=genai.GenerativeModel("gemini-1.5-flash")
        ctx=(f"Autism therapy advisor. Child:{CHILD_NAME}, age:{ST['age']}. "
             f"Score:{ST['score']}, Motor:{ST['skill_motor']:.0f}%, Verbal:{ST['skill_verbal']:.0f}%, "
             f"Social:{ST['skill_social']:.0f}%, Emotion:{ST['emotion']}, "
             f"Mood:{ST['current_mood']}, Level:{ST['conversation_level']}. "
             f"Reply in 3-4 practical sentences.")
        resp=mdl.generate_content(ctx+"\nQuestion: "+q)
        return resp.text.strip()[:500]
    except Exception as e: return f"Error: {str(e)[:80]}"

parent_app=Flask("pepper_v6v8"); parent_app.secret_key=secrets.token_hex(16)

DASH="""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pepper V6+V8</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:{{bg}};color:{{txt}};font-family:'Segoe UI',Arial,sans-serif;font-size:14px}
.top{background:{{bg2}};padding:10px 18px;display:flex;align-items:center;gap:8px;
  border-bottom:2px solid {{acc}};flex-wrap:wrap}
.top h1{font-size:1.05em;color:{{acc}};font-weight:900}
.badge{background:{{bg}};border:1px solid {{acc}};border-radius:20px;
  padding:3px 9px;font-size:.77em;color:{{acc}}}
.tabs{display:flex;background:{{bg2}};border-bottom:2px solid {{b3}};overflow-x:auto}
.tab{padding:10px 14px;cursor:pointer;font-size:.80em;font-weight:600;color:#888;
  white-space:nowrap;border-bottom:3px solid transparent;transition:.2s}
.tab.active,.tab:hover{color:{{acc}};border-bottom-color:{{acc}}}
.pg{padding:14px;overflow-y:auto;height:calc(100vh - 105px)}
.card{background:{{bg2}};border-radius:11px;padding:13px;border:1px solid {{b3}};margin-bottom:11px}
.card h3{color:{{acc}};font-size:.90em;margin-bottom:9px}
.sg{display:grid;grid-template-columns:repeat(auto-fill,minmax(105px,1fr));gap:7px;margin-bottom:11px}
.st{background:{{bg2}};border-radius:9px;padding:8px;text-align:center;border:1px solid {{b3}}}
.st .v{font-size:1.5em;font-weight:900}.st .l{font-size:.67em;color:#888;margin-top:2px}
.br{margin-bottom:5px}.br label{display:flex;justify-content:space-between;font-size:.75em;margin-bottom:2px}
.bb{background:{{b3}};border-radius:4px;height:8px}
.bf{height:8px;border-radius:4px;transition:width 1s}
input,select,textarea{width:100%;background:{{b3}};border:2px solid {{b3}};border-radius:8px;
  padding:7px 11px;color:{{txt}};font-size:.85em;margin-bottom:7px;outline:none}
input:focus,select:focus{border-color:{{acc}}}
.btn{background:{{acc}};color:#fff;border:none;border-radius:8px;padding:8px 16px;
  font-weight:700;cursor:pointer;width:100%;font-size:.87em}
.btn:hover{opacity:.85}.btn-r{background:#dc2626}.btn-g{background:#059669}
.lg{display:grid;grid-template-columns:1fr 1fr;gap:9px}
.lc{background:{{bg2}};border-radius:9px;padding:11px;border:1px solid {{b3}}}
.lc h4{color:{{acc}};font-size:.83em;margin-bottom:7px}
.ev{height:190px;overflow-y:auto;font-size:.73em;background:{{bg}};border-radius:7px;padding:7px}
.er{padding:3px 0;border-bottom:1px solid {{b3}};display:flex;gap:7px}
.et{color:#888;min-width:58px;font-size:.74em}
.ok{color:#22c55e}.fail{color:#ef4444}.info{color:{{acc}}}
.mg{display:flex;flex-wrap:wrap;gap:5px}
.mb{border:2px solid {{b3}};border-radius:8px;padding:5px 9px;cursor:pointer;
  font-size:.80em;background:{{b3}};transition:.15s}
.mb:hover{border-color:{{acc}};background:{{bg2}}}
.tg{display:flex;flex-wrap:wrap;gap:7px;margin-top:7px}
.tb{border:2px solid {{b3}};border-radius:8px;padding:7px 13px;cursor:pointer;
  font-size:.80em;background:{{bg2}};transition:.15s;min-width:140px}
.tb:hover,.tb.active{border-color:{{acc}}}
.mug{display:flex;flex-wrap:wrap;gap:7px}
.mu{background:{{bg2}};border:2px solid {{b3}};border-radius:8px;padding:7px 12px;
  cursor:pointer;font-size:.80em;text-align:center;transition:.15s;min-width:110px}
.mu:hover,.mu.active{border-color:{{acc}}}
.pg2{display:flex;flex-wrap:wrap;gap:5px}
.pb{background:{{b3}};border:2px solid {{b3}};border-radius:8px;padding:5px 9px;
  cursor:pointer;font-size:.80em;transition:.15s}
.pb:hover{border-color:{{acc}}}
.qg{display:grid;grid-template-columns:repeat(3,1fr);gap:7px}
.qb{background:{{bg2}};border:2px solid {{b3}};border-radius:9px;padding:11px;
  cursor:pointer;font-size:.87em;font-weight:700;text-align:center;transition:.15s}
.qb:hover{border-color:{{acc}}}
.sr{display:grid;grid-template-columns:1fr 60px 55px 55px 55px 65px;
  gap:3px;padding:4px 0;border-bottom:1px solid {{b3}};font-size:.73em}
.ah{max-height:260px;overflow-y:auto;margin-bottom:9px}
.am{padding:7px;border-radius:8px;margin:4px 0;font-size:.82em}
.ap{background:{{b3}}}.ab{background:{{bg2}};border:1px solid {{b3}}}
</style></head><body>
<div class="top">
  <span style="font-size:1.4em">🤖</span>
  <h1>Pepper V6+V8 Dashboard</h1>
  <span class="badge">👦 <span id="cn">…</span></span>
  <span class="badge">⭐ <span id="sc">0</span></span>
  <span class="badge">😊 <span id="em">—</span></span>
  <span class="badge" id="md_b">😌 calm</span>
  <span class="badge" id="th_b">🎨 blue</span>
  <span class="badge" id="mu_b">🔇 Off</span>
  <span class="badge">🖐️ <span id="fn">0</span>/10</span>
  <span class="badge"><a href="/report_pdf" style="color:{{acc}};text-decoration:none">📄 PDF</a></span>
</div>
<div class="tabs">
  <div class="tab active" onclick="go('overview',this)">📊 Overview</div>
  <div class="tab" onclick="go('live',this)">🔴 Live Monitor</div>
  <div class="tab" onclick="go('themes',this)">🎨 Themes</div>
  <div class="tab" onclick="go('mood',this)">😊 Mood</div>
  <div class="tab" onclick="go('music',this)">🎵 Music</div>
  <div class="tab" onclick="go('pecs',this)">🗣️ PECS</div>
  <div class="tab" onclick="go('sessions',this)">📅 Sessions</div>
  <div class="tab" onclick="go('ai',this)">🤖 AI Advice</div>
  <div class="tab" onclick="go('quick',this)">⚡ Actions</div>
  <div class="tab" onclick="go('youtube',this)">📺 Videos</div>
  <div class="tab" onclick="go('liveview',this)">👁️ Live View</div>
</div>
<div class="pg" id="pg">Loading…</div>
<script>
let st={},aiC=[];
async function poll(){
  try{
    const r=await fetch('/api/state'); st=await r.json();
    document.getElementById('cn').textContent=st.child_name||'—';
    document.getElementById('sc').textContent=st.score||0;
    document.getElementById('em').textContent=st.emotion||'—';
    document.getElementById('md_b').textContent=st.current_mood||'calm';
    document.getElementById('th_b').textContent='🎨 '+(st.current_theme||'blue');
    document.getElementById('mu_b').textContent=st.current_music==='none'?'🔇 Off':'🎵 '+st.current_music;
    document.getElementById('fn').textContent=st.finger_count||0;
  }catch(e){}
}
function go(t,el){
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  if(el)el.classList.add('active'); render(t);
}
function render(t){
  const c=document.getElementById('pg');
  const ok=st.tasks_success||0,fa=st.tasks_fail||0;
  const acc=ok+fa>0?Math.round(ok/(ok+fa)*100):0;
  const rt=st.resp_times||[];
  const avg=rt.length?Math.round(rt.slice(-10).reduce((a,b)=>a+b,0)/Math.min(rt.length,10)):0;
  if(t==='overview'){
    const sk=[['Motor','skill_motor','#a78bfa'],['Cognitive','skill_cognitive','#06b6d4'],
      ['Verbal','skill_verbal','#fbbf24'],['Math','skill_math','#22c55e'],
      ['Social','skill_social','#f97316'],['Daily','skill_daily','#ec4899']];
    c.innerHTML=`<div class="sg">
      <div class="st"><div class="v" style="color:#a78bfa">${st.score||0}</div><div class="l">⭐ Score</div></div>
      <div class="st"><div class="v" style="color:#fbbf24">${st.tokens||0}</div><div class="l">🪙 Tokens</div></div>
      <div class="st"><div class="v" style="color:#22c55e">${ok}</div><div class="l">✅ Correct</div></div>
      <div class="st"><div class="v" style="color:#3b82f6">${acc}%</div><div class="l">🎯 Accuracy</div></div>
      <div class="st"><div class="v" style="color:#f97316">${avg||'—'}ms</div><div class="l">⏱ Avg</div></div>
      <div class="st"><div class="v" style="color:#34d399">${st.mastered||0}</div><div class="l">🏆 Mastered</div></div>
      <div class="st"><div class="v" style="color:#f472b6">${st.conversation_level||1}</div><div class="l">🗣 Level</div></div>
      <div class="st"><div class="v" style="color:#60a5fa">${st.attention||0}%</div><div class="l">👁 Attention</div></div>
      <div class="st"><div class="v" style="color:#a78bfa">${st.child_done_count||0}</div><div class="l">✅ Done</div></div>
    </div>
    <div class="card"><h3>🎯 Skills</h3>
      ${sk.map(([l,k,col])=>`<div class="br">
        <label><span>${l}</span><span style="color:${col};font-weight:700">${Math.round(st[k]||50)}%</span></label>
        <div class="bb"><div class="bf" style="width:${st[k]||50}%;background:${col}"></div></div>
      </div>`).join('')}
    </div>
    <div class="card"><h3>😊 State</h3>
      <div style="display:flex;flex-wrap:wrap;gap:6px;font-size:.83em">
        <span>Emotion:<b> ${st.emotion||'—'}</b></span>
        <span>| Mood:<b> ${st.current_mood||'calm'}</b></span>
        <span>| Theme:<b> ${st.current_theme||'blue'}</b></span>
        <span>| Music:<b> ${st.current_music||'none'}</b></span>
        <span>| Lip:<b> ${st.lip_speaking?'SPEECH':'silent'}</b></span>
        <span>| Last Task:<b> ${st.last_task_name||'—'}</b></span>
        <span>| Result:<b> ${st.last_result||'—'}</b></span>
      </div>
    </div>
    <div class="card" style="border:2px solid {{acc}}">
      <h3>📈 3-Year Curriculum Progress</h3>
      <div class="sg" style="grid-template-columns:repeat(4,1fr)">
        <div class="st"><div class="v" style="color:#fbbf24">${st.total_pool?st.total_pool.toLocaleString():'100,000'}</div><div class="l">📚 Total Tasks</div></div>
        <div class="st"><div class="v" style="color:#22c55e">${st.child_done_count||0}</div><div class="l">✅ Completed</div></div>
        <div class="st"><div class="v" style="color:#a78bfa">${st.milestones_reached||0}</div><div class="l">🎊 Milestones</div></div>
        <div class="st"><div class="v" style="color:#f97316">${st.next_milestone_in||10}</div><div class="l">⭐ To Next 🎊</div></div>
      </div>
      <div style="margin-top:8px">
        <div style="display:flex;justify-content:space-between;font-size:.78em;margin-bottom:3px">
          <span style="color:#60a5fa">📅 Year 1 Foundation</span>
          <span style="color:#60a5fa">${st.tasks_in_year1||0} tasks</span>
        </div>
        <div style="background:{{b3}};border-radius:4px;height:9px;margin-bottom:5px">
          <div style="height:9px;border-radius:4px;background:#60a5fa;width:${Math.min(100,((st.tasks_in_year1||0)/45000)*100).toFixed(1)}%"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:.78em;margin-bottom:3px">
          <span style="color:#22c55e">📅 Year 2 Building</span>
          <span style="color:#22c55e">${st.tasks_in_year2||0} tasks</span>
        </div>
        <div style="background:{{b3}};border-radius:4px;height:9px;margin-bottom:5px">
          <div style="height:9px;border-radius:4px;background:#22c55e;width:${Math.min(100,((st.tasks_in_year2||0)/40000)*100).toFixed(1)}%"></div>
        </div>
        <div style="display:flex;justify-content:space-between;font-size:.78em;margin-bottom:3px">
          <span style="color:#a78bfa">📅 Year 3 Advanced</span>
          <span style="color:#a78bfa">${st.tasks_in_year3||0} tasks</span>
        </div>
        <div style="background:{{b3}};border-radius:4px;height:9px">
          <div style="height:9px;border-radius:4px;background:#a78bfa;width:${Math.min(100,((st.tasks_in_year3||0)/15000)*100).toFixed(1)}%"></div>
        </div>
      </div>
      <div style="margin-top:8px;padding:8px;background:{{bg}};border-radius:7px;font-size:.80em;text-align:center">
        🎊 Next celebration in <b style="color:#fbbf24;font-size:1.1em">${st.next_milestone_in||10}</b> more correct answers!
        Each milestone = 📺 educational video + 🎊 special animation + 👏 clap sound
      </div>
    </div>`;
  }else if(t==='live'){
    const evs=(st.session_events||[]).slice().reverse().slice(0,60);
    c.innerHTML=`<div class="lg">
      <div class="lc"><h4>🔴 Live Session</h4>
        <div class="sg" style="grid-template-columns:repeat(3,1fr)">
          <div class="st"><div class="v" style="color:#22c55e">${ok}</div><div class="l">✅ Correct</div></div>
          <div class="st"><div class="v" style="color:#ef4444">${fa}</div><div class="l">❌ Failed</div></div>
          <div class="st"><div class="v" style="color:#fbbf24">${st.streak||0}</div><div class="l">🔥 Streak</div></div>
          <div class="st"><div class="v" style="color:#a78bfa">${st.score||0}</div><div class="l">⭐ Score</div></div>
          <div class="st"><div class="v" style="color:#60a5fa">${st.attention||0}%</div><div class="l">👁 Attn</div></div>
          <div class="st"><div class="v" style="color:#34d399">${st.finger_count||0}</div><div class="l">🖐️ Fingers</div></div>
        </div>
        <div style="padding:9px;background:{{bg}};border-radius:7px;font-size:.83em">
          <div>🎯 Task: <b>${st.last_task_name||'—'}</b></div>
          <div>📊 Result: <b>${st.last_result||'—'}</b></div>
          <div>😊 Emotion: <b>${st.emotion||'—'}</b></div>
          <div>😌 Mood: <b>${st.current_mood||'calm'}</b></div>
          <div>🗣️ Level: <b>L${st.conversation_level||1}</b></div>
          <div>👄 Lip: <b>${st.lip_speaking?'<span style="color:#22c55e">SPEAKING</span>':'silent'}</b></div>
          <div>✅ No-repeat done: <b>${st.child_done_count||0}</b></div>
        </div>
      </div>
      <div class="lc"><h4>📋 Live Event Log</h4>
        <div class="ev">
          ${evs.length?evs.map(e=>`<div class="er">
            <span class="et">${e.time||''}</span>
            <span class="${e.type==='success'?'ok':e.type==='fail'?'fail':'info'}">
              ${e.type==='success'?'✅':e.type==='fail'?'❌':'ℹ️'}
            </span>
            <span>${e.msg||''}</span>
          </div>`).join(''):'<div style="color:#888;padding:7px">No events yet</div>'}
        </div>
      </div>
    </div>
    <div class="lc" style="margin-top:9px"><h4>😊 Live Emotion</h4>
      <div style="display:flex;flex-wrap:wrap;gap:5px">
        ${Object.entries(st.emotion_pct||{}).map(([em,v])=>`
          <div style="background:{{b3}};border-radius:14px;padding:3px 9px;font-size:.79em">
            ${em} <b>${v}%</b>
            <div style="height:4px;background:{{bg}};border-radius:2px;margin-top:2px">
              <div style="height:4px;background:{{acc}};border-radius:2px;width:${v}%"></div>
            </div>
          </div>`).join('')}
      </div>
    </div>`;
  }else if(t==='themes'){
    const TH=[{id:'blue',n:'🔵 Blue',d:'Professional, high contrast'},
      {id:'green',n:'🟢 Green',d:'Calm, for anxious children'},
      {id:'gray',n:'⬜ Gray',d:'Sensory-safe, minimal stimulation'},
      {id:'colorful',n:'🌈 Colorful',d:'High energy, maximum engagement'},
      {id:'pink',n:'🩷 Pink',d:'Warm, preference-aligned'}];
    c.innerHTML=`<div class="card"><h3>🎨 Select Theme</h3>
      <div class="tg">${TH.map(th=>`
        <div class="tb ${st.current_theme===th.id?'active':''}"
          onclick="setTheme('${th.id}')">
          <div style="font-size:1.05em;font-weight:700">${th.n}</div>
          <div style="font-size:.74em;color:#888">${th.d}</div>
        </div>`).join('')}
      </div>
    </div>`;
  }else if(t==='mood'){
    const MD=[{id:'calm',em:'😌',l:'Calm'},{id:'happy',em:'😊',l:'Happy'},
      {id:'excited',em:'🤩',l:'Excited'},{id:'anxious',em:'😰',l:'Anxious'},
      {id:'sad',em:'😢',l:'Sad'},{id:'angry',em:'😠',l:'Angry'},
      {id:'overwhelmed',em:'😵',l:'Overwhelmed'},{id:'tired',em:'😴',l:'Tired'},
      {id:'silly',em:'🤪',l:'Silly'},{id:'focused',em:'🧐',l:'Focused'},
      {id:'scared',em:'😨',l:'Scared'},{id:'sensory',em:'🙉',l:'Sensory'},
      {id:'rainbow',em:'🌈',l:'Rainbow'}];
    c.innerHTML=`<div class="card"><h3>😊 Set Child Mood (auto-selects music)</h3>
      <div class="mg">${MD.map(m=>`
        <div class="mb ${st.current_mood===m.id?'active':''}"
          onclick="setMood('${m.id}')">
          <span style="font-size:1.3em">${m.em}</span>
          <div style="font-size:.77em">${m.l}</div>
        </div>`).join('')}
      </div>
    </div>`;
  }else if(t==='music'){
    const MU=[{id:'none',em:'🔇',n:'Off',t:'No Music'},
      {id:'nature',em:'🌧️',n:'Forest Rain',t:'Nature·Calm'},
      {id:'ocean',em:'🌊',n:'Ocean Waves',t:'Nature·Relax'},
      {id:'sleep',em:'😴',n:'Sleep 432Hz',t:'Sleep·Soothe'},
      {id:'upbeat',em:'🎉',n:'Happy Rhythm',t:'Upbeat·Energy'},
      {id:'focus',em:'🎯',n:'Focus 60BPM',t:'Study·Calm'},
      {id:'white',em:'⬜',n:'White Noise',t:'Sensory·Block'},
      {id:'lullaby',em:'🎵',n:'Lullaby',t:'Gentle·Trans'},
      {id:'piano',em:'🎹',n:'Soft Piano',t:'Classical'}];
    c.innerHTML=`<div class="card"><h3>🎵 Background Music (generated tones)</h3>
      <div class="mug">${MU.map(m=>`
        <div class="mu ${st.current_music===m.id?'active':''}"
          onclick="setMusic('${m.id}')">
          <div style="font-size:1.4em">${m.em}</div>
          <div style="font-weight:700;font-size:.83em">${m.n}</div>
          <div style="font-size:.70em;color:#888">${m.t}</div>
        </div>`).join('')}
      </div>
      <div style="margin-top:11px">
        <label style="font-size:.81em">🔊 Volume: <span id="vd">${Math.round((st.music_volume||0.3)*100)}%</span></label>
        <input type="range" min="0" max="100" value="${Math.round((st.music_volume||0.3)*100)}"
          oninput="setVol(this.value)" style="margin-top:5px;height:7px;border-radius:3px">
      </div>
    </div>`;
  }else if(t==='pecs'){
    c.innerHTML=`<div class="card"><h3>🗣️ PECS 50 Cards</h3>
      <div class="pg2" id="pg2">Loading…</div>
    </div>`;
    fetch('/api/pecs_items').then(r=>r.json()).then(d=>{
      const el=document.getElementById('pg2'); if(!el) return;
      el.innerHTML=d.items.map(x=>
        `<button class="pb" onclick="sayP('${x.phrase.replace(/'/g,"\\'")}','${x.name.replace(/'/g,"\\'")}')">
          ${x.emoji} ${x.name}
        </button>`).join('');
    });
  }else if(t==='sessions'){
    c.innerHTML=`<div class="card"><h3>📅 Sessions</h3>
      <div style="display:flex;gap:7px;margin-bottom:9px">
        <button class="btn btn-g" onclick="loadS()" style="width:auto;padding:7px 16px">🔄 Load</button>
        <button class="btn btn-r" onclick="resetT()" style="width:auto;padding:7px 16px">🔄 Refresh Tasks</button>
        <button class="btn" onclick="saveS()" style="width:auto;padding:7px 16px">💾 Save</button>
      </div>
      <div class="sr" style="font-weight:700;color:{{acc}}">
        <span>Date</span><span>Score</span><span>✅OK</span><span>❌Fail</span><span>⏱Min</span><span>Emotion</span>
      </div>
      <div id="srows"><div style="color:#888;padding:7px">Click Load</div></div>
    </div>`;
  }else if(t==='ai'){
    c.innerHTML=`<div class="card"><h3>🤖 AI Advisor — Gemini</h3>
      <div class="ah" id="ah">
        ${aiC.map(m=>`<div class="am ${m.role==='ai'?'ab':'ap'}">
          <b>${m.role==='ai'?'🤖 Gemini':'👤 You'}:</b> ${m.text}
        </div>`).join('')||'<div style="color:#888;padding:7px">Ask a question below!</div>'}
      </div>
      <div style="display:flex;gap:7px">
        <input id="aiQ" placeholder="Ask about therapy strategies…"
          onkeydown="if(event.key==='Enter')askAI()">
        <button class="btn" style="width:80px" onclick="askAI()" id="aiBtn">Ask</button>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:4px;margin-top:7px">
        ${['Home activities?','Improve attention?','Verbal tips?','Handle tantrums?',
           'Best PECS?','Explain results'].map(q=>
          `<button onclick="document.getElementById('aiQ').value='${q}';askAI()"
            style="background:{{b3}};border:1px solid {{b3}};border-radius:14px;
            padding:3px 9px;cursor:pointer;font-size:.73em;color:{{txt}}">${q}</button>`).join('')}
      </div>
    </div>`;
    const ah=document.getElementById('ah'); if(ah) ah.scrollTop=ah.scrollHeight;
  }else if(t==='quick'){
    c.innerHTML=`<div class="card"><h3>⚡ Quick Actions</h3>
      <div class="qg">
        ${[['Next Task','🎯','next'],['Break','⏸️','break'],['Celebrate','🎉','celebrate'],
           ['Encourage','💪','encourage'],['PDF Report','📄','report'],['Save Session','💾','save']
        ].map(([l,ic,a])=>`
          <div class="qb" onclick="qa('${a}')">${ic}<br><span style="font-size:.77em">${l}</span></div>`).join('')}
      </div>
    </div>
    <div class="card"><h3>🔄 Refresh Task History</h3>
      <p style="font-size:.81em;color:#888;margin-bottom:7px">
        Reset: ${st.child_name||'Child'} will see all tasks again. Done so far: ${st.child_done_count||0} tasks.</p>
      <button class="btn btn-r" onclick="resetT()">🔄 Reset Task History</button>
    </div>`;
  }
}

async function setTheme(id){
  await fetch('/api/set_theme',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({theme:id})});
  poll(); setTimeout(()=>render('themes'),300);}
async function setMood(id){
  await fetch('/api/set_mood',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({mood:id})});
  poll(); setTimeout(()=>render('mood'),300);}
async function setMusic(id){
  await fetch('/api/set_music',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({music:id})});
  poll();}
async function setVol(v){
  document.getElementById('vd').textContent=v+'%';
  await fetch('/api/set_volume',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({volume:parseInt(v)/100})});}
async function sayP(ph,nm){
  await fetch('/api/pecs',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({phrase:ph,name:nm})});}
async function loadS(){
  const r=await fetch('/api/sessions'); const d=await r.json();
  const el=document.getElementById('srows'); if(!el) return;
  if(!d.sessions||!d.sessions.length){el.innerHTML='<div style="color:#888;padding:7px">No sessions</div>';return;}
  el.innerHTML=d.sessions.map(s=>`<div class="sr">
    <span>${s.date.slice(0,16)}</span><span style="color:#fbbf24">${s.score}</span>
    <span style="color:#22c55e">${s.ok}</span><span style="color:#ef4444">${s.fail}</span>
    <span>${s.dur}m</span><span style="color:#a78bfa">${s.emotion}</span>
  </div>`).join('');}
async function resetT(){
  if(!confirm('Reset task history?')) return;
  await fetch('/api/reset_tasks',{method:'POST'}); alert('✅ Reset!'); poll();}
async function saveS(){
  await fetch('/api/save_session',{method:'POST'}); alert('✅ Saved!');}
async function qa(a){
  if(a==='report'){window.open('/report_pdf');return;}
  if(a==='save'){await saveS();return;}
  await fetch('/api/quick_action',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:a})});}
async function askAI(){
  const q=document.getElementById('aiQ').value.trim(); if(!q) return;
  const btn=document.getElementById('aiBtn'); btn.textContent='…'; btn.disabled=true;
  document.getElementById('aiQ').value='';
  try{
    const r=await fetch('/api/ai_advice',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q})});
    const d=await r.json(); if(d.ok){aiC=d.chat||[]; render('ai');}
  }catch(e){}finally{btn.textContent='Ask'; btn.disabled=false;}}

async function playVideo(embed){
  await fetch('/api/play_video',{method:'POST',
    headers:{'Content-Type':'application/json'},
    body:JSON.stringify({embed:embed})});
}
poll(); setInterval(poll,1500); render('overview');
</script></body></html>"""

def _html():
    th=get_theme()
    return DASH.replace("{{bg}}",th["fk_bg"]).replace("{{bg2}}",th["fk_card"]
        ).replace("{{acc}}",th["fk_acc"]).replace("{{txt}}",th["fk_txt"]
        ).replace("{{b3}}",th["fk_b3"])

@parent_app.route("/")
def index(): return render_template_string(_html())

@parent_app.route("/api/state")
def api_state():
    data={k:ST[k] for k in ST if isinstance(ST[k],(str,int,float,bool,list,dict,type(None)))}
    data["total_pool"]=len(TASK_POOL)
    data["child_done_count"]=len(_child_done)
    data["milestones_reached"]=ST["tasks_success"]//10
    data["next_milestone_in"]=10-(ST["tasks_success"]%10) if ST["tasks_success"]>0 else 10
    return jsonify(data)

@parent_app.route("/api/set_theme",methods=["POST"])
def api_set_theme():
    d=request.get_json(silent=True) or {}; tid=d.get("theme","blue")
    if tid in THEMES: BRIDGE.sig_theme.emit(tid)
    return jsonify({"ok":True})

@parent_app.route("/api/set_mood",methods=["POST"])
def api_set_mood():
    d=request.get_json(silent=True) or {}; BRIDGE.sig_mood.emit(d.get("mood","calm"))
    return jsonify({"ok":True})

@parent_app.route("/api/set_music",methods=["POST"])
def api_set_music():
    d=request.get_json(silent=True) or {}; mid=d.get("music","none"); ST["current_music"]=mid
    if mid=="none": MUSIC_ENGINE.stop()
    else: MUSIC_ENGINE.play(mid)
    return jsonify({"ok":True})

@parent_app.route("/api/set_volume",methods=["POST"])
def api_set_volume():
    d=request.get_json(silent=True) or {}; v=float(d.get("volume",0.3))
    ST["music_volume"]=v; MUSIC_ENGINE.set_volume(v)
    return jsonify({"ok":True})

@parent_app.route("/api/pecs",methods=["POST"])
def api_pecs():
    d=request.get_json(silent=True) or {}; ph=d.get("phrase",""); nm=d.get("name","")
    if ph and VOICE_REF: VOICE_REF.say_pecs(f"{CHILD_NAME} says: {ph}")
    ST["pecs_log"].append({"time":datetime.now().strftime("%H:%M:%S"),
        "name":nm,"phrase":ph,"emotion":ST["emotion"]})
    return jsonify({"ok":True})

@parent_app.route("/api/pecs_items")
def api_pecs_items():
    return jsonify({"items":[{"emoji":e,"name":n,"phrase":p} for e,n,p in PECS_ITEMS]})

@parent_app.route("/api/sessions")
def api_sessions(): return jsonify({"sessions":db_get_sessions(CHILD_NAME)})

@parent_app.route("/api/save_session",methods=["POST"])
def api_save_session():
    dur=int((time.time()-ST.get("uptime",time.time()))/60)
    db_save_session(CHILD_NAME,ST["score"],ST["tasks_success"],ST["tasks_fail"],dur,
        {"motor":ST["skill_motor"],"cognitive":ST["skill_cognitive"],"verbal":ST["skill_verbal"],
         "math":ST["skill_math"],"social":ST["skill_social"]},
        ST["emotion"],ST["conversation_level"])
    return jsonify({"ok":True})

@parent_app.route("/api/reset_tasks",methods=["POST"])
def api_reset_tasks():
    db_reset_tasks(CHILD_NAME); _child_done.clear(); SESSION_HISTORY.clear()
    ST["child_done_count"]=0; return jsonify({"ok":True})

@parent_app.route("/api/quick_action",methods=["POST"])
def api_quick():
    d=request.get_json(silent=True) or {}; ST["quick_action"]=d.get("action")
    return jsonify({"ok":True})

@parent_app.route("/api/ai_advice",methods=["POST"])
def api_ai():
    d=request.get_json(silent=True) or {}; q=d.get("question","").strip()
    if not q: return jsonify({"ok":False,"chat":_ai_chat_list})
    _ai_chat_list.append({"role":"parent","text":q})
    ans=gemini_chat(q); _ai_chat_list.append({"role":"ai","text":ans})
    if len(_ai_chat_list)>40: _ai_chat_list[:]=_ai_chat_list[-40:]
    return jsonify({"ok":True,"answer":ans,"chat":_ai_chat_list[-20:]})

@parent_app.route("/report_pdf")
def report_pdf():
    if not _PDF: return "pip install reportlab",501
    buf=BytesIO(); doc=SimpleDocTemplate(buf,pagesize=A4)
    styles=getSampleStyleSheet(); story=[]
    story.append(Paragraph(f"<b>Pepper Clinical V6+V8 — {CHILD_NAME}</b>",styles["Title"]))
    story.append(Paragraph(
        f"Date:{ST['session_date']} | Score:{ST['score']} | Theme:{ST['current_theme']} | "
        f"Mood:{ST['current_mood']} | Level:L{ST['conversation_level']} | "
        f"Accuracy:{round(ST['tasks_success']/(ST['tasks_success']+ST['tasks_fail'])*100,1) if ST['tasks_success']+ST['tasks_fail']>0 else 0}%",
        styles["Normal"]))
    story.append(Spacer(1,10))
    data=[["Domain","Score","Status"]]
    for k,n in [("skill_motor","Motor"),("skill_cognitive","Cognitive"),("skill_verbal","Verbal"),
                ("skill_math","Math"),("skill_social","Social"),("skill_daily","Daily")]:
        v=ST[k]; s="Proficient" if v>=65 else "Developing" if v>=45 else "Priority"
        data.append([n,f"{v:.1f}%",s])
    t=Table(data,colWidths=[120,80,120])
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),RLC.HexColor("#4f46e5")),
        ("TEXTCOLOR",(0,0),(-1,0),RLC.white),("FONTNAME",(0,0),(-1,-1),"Helvetica"),
        ("GRID",(0,0),(-1,-1),1,RLC.grey),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[RLC.white,RLC.HexColor("#f0f4f8")])]))
    story.append(t); story.append(Spacer(1,10))
    story.append(Paragraph("<b>Session Log (last 20):</b>",styles["Heading3"]))
    for lg in ST.get("logs",[])[-20:]:
        story.append(Paragraph(f"[{lg['time']}] {lg['msg'][:80]}",styles["Normal"]))
    doc.build(story); buf.seek(0)
    fn=f"PepperV6V8_{SAFE_NAME}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
    return send_file(buf,as_attachment=True,download_name=fn,mimetype="application/pdf")

@parent_app.route("/api/play_video",methods=["POST"])
def api_play_video():
    d=request.get_json(silent=True) or {}
    embed=d.get("embed","")
    if embed: BRIDGE.sig_youtube.emit(embed)
    return jsonify({"ok":True})

@parent_app.route("/api/year_stats")
def api_year_stats():
    pool=TASK_POOL
    y1=sum(1 for t in pool if t.get("year",1)==1)
    y2=sum(1 for t in pool if t.get("year",1)==2)
    y3=sum(1 for t in pool if t.get("year",1)==3)
    done=len(_child_done)
    milestones=ST["tasks_success"]//10
    return jsonify({"total":len(pool),"year1":y1,"year2":y2,"year3":y3,
        "done":done,"milestones_reached":milestones,
        "next_milestone_in":10-(ST["tasks_success"]%10)})

@parent_app.errorhandler(404)
def p404(e): return redirect("/"),302

def run_flask():
    import logging as lg; lg.getLogger("werkzeug").setLevel(lg.ERROR)
    parent_app.run(host="0.0.0.0",port=5007,debug=False,use_reloader=False)

# ══════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════
def main():
    global VOICE_REF
    app=QApplication(sys.argv); app.setStyle("Fusion")
    pal=QPalette()
    pal.setColor(QPalette.ColorRole.Window,QColor(4,11,26))
    pal.setColor(QPalette.ColorRole.WindowText,QColor(205,228,255))
    pal.setColor(QPalette.ColorRole.Base,QColor(10,20,40))
    pal.setColor(QPalette.ColorRole.Text,QColor(205,228,255))
    pal.setColor(QPalette.ColorRole.Button,QColor(10,20,40))
    pal.setColor(QPalette.ColorRole.ButtonText,QColor(205,228,255))
    pal.setColor(QPalette.ColorRole.Highlight,QColor(74,158,255))
    pal.setColor(QPalette.ColorRole.HighlightedText,QColor(255,255,255))
    app.setPalette(pal)

    log.info("🔊 Voice engine…"); voice=VoiceEngine(); VOICE_REF=voice
    log.info("🤖 PyBullet…"); pb=PBWatchdog(CHILD_NAME); pb.start()
    log.info("🖥️  Main window…"); win=MainWindow(); win.show()
    win._apply_theme("blue")
    log.info("📷 Camera…"); cam=CameraThread(); cam.start()
    log.info("🎯 Therapy controller…"); ctrl=TherapyController(voice,pb); ctrl.start()
    log.info("🌐 Flask dashboard…"); threading.Thread(target=run_flask,daemon=True).start()

    print("\n"+"═"*64)
    print("  ✅  Pepper Clinical V6+V8 — Enhanced Edition RUNNING!")
    print(f"  👦  Child: {CHILD_NAME}")
    print(f"  🎨  5 Themes  |  🗣️ 50 PECS  |  🎵 8 Music Tracks")
    print(f"  😌  13 Moods  |  👏 Clap Sound  |  🔴 Live Monitor")
    print(f"  🎙️   5 Voices  |  ✅ Zero Task Repetition")
    print(f"  🌐  Dashboard: http://localhost:5007")
    print(f"  🌐  Network:   http://{LOCAL_IP}:5007")
    print(f"  📊  CSV: {CSV_FILE}")
    print("═"*64+"\n")
    webbrowser.open("http://localhost:5007")

    def _cleanup():
        log.info("🛑 Shutting down…"); ctrl.stop(); cam.stop(); pb.stop(); MUSIC_ENGINE.stop()
        dur=int((time.time()-ST.get("uptime",time.time()))/60)
        if ST["tasks_success"]+ST["tasks_fail"]>0:
            db_save_session(CHILD_NAME,ST["score"],ST["tasks_success"],ST["tasks_fail"],dur,
                {"motor":ST["skill_motor"],"cognitive":ST["skill_cognitive"],
                 "verbal":ST["skill_verbal"],"math":ST["skill_math"],"social":ST["skill_social"]},
                ST["emotion"],ST["conversation_level"])
            log.info(f"✅ Session saved for {CHILD_NAME}")
        try: voice.cleanup()
        except: pass
        try: os.system("pkill -f aplay 2>/dev/null")
        except: pass

    app.aboutToQuit.connect(_cleanup)
    sys.exit(app.exec())

if __name__=="__main__":
    main()
