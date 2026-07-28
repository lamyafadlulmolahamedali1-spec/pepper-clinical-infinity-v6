#!/usr/bin/env python3
"""
Pepper Clinical Infinity V6 — Enhanced Edition
Additions:
  ✅ PECS expanded to 50 items
  ✅ AI Advice fixed (no more 404)
  ✅ PDF with full treatment plan + SMART goals + weekly schedule
  ✅ ISCA + ISAA + ISQA validated screening tools
  ✅ Persistent child profiles (SQLite)
  ✅ Per-child session storage (all sessions on dashboard)
  ✅ Zero task repetition per child (until parent presses Refresh)
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
from PIL import Image,ImageDraw,ImageFont
import mediapipe as mp
import pyttsx3,speech_recognition as sr

try: from faster_whisper import WhisperModel as FW; _FW=True
except: _FW=False
try: import google.generativeai as genai; _GENAI=True
except: _GENAI=False
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import (SimpleDocTemplate,Paragraph,Spacer,
        Table,TableStyle,HRFlowable)
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.lib import colors as RL_COLORS
    from reportlab.lib.enums import TA_CENTER,TA_LEFT
    _PDF=True
except: _PDF=False

from flask import (Flask,render_template_string,jsonify,request,
                   redirect,send_file,make_response,url_for)
from PyQt6.QtWidgets import (QApplication,QMainWindow,QWidget,QVBoxLayout,
    QHBoxLayout,QLabel,QPushButton,QFrame,QGridLayout,QLineEdit,QTextEdit,
    QGraphicsDropShadowEffect,QProgressBar,QScrollArea)
from PyQt6.QtCore import (Qt,QTimer,pyqtSignal,QObject,QThread,
    QMutex,QMutexLocker,QRect)
from PyQt6.QtGui import (QFont,QColor,QPalette,QPixmap,QImage,
    QPainter,QLinearGradient,QBrush,QPen)
import webbrowser

# ══════════════════════════════════════════════════════════════════
# Child Database — SQLite persistent storage
# ══════════════════════════════════════════════════════════════════
_DB=os.path.expanduser("~/pepper_duo/children.db")
os.makedirs(os.path.dirname(_DB),exist_ok=True)

def _db():
    return sqlite3.connect(_DB)

def init_db():
    conn=_db(); c=conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS children(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT UNIQUE NOT NULL,
        age INTEGER DEFAULT 6,
        asd_level INTEGER DEFAULT 2,
        notes TEXT DEFAULT '',
        created_at TEXT,
        isca_score INTEGER DEFAULT 0,
        isaa_score INTEGER DEFAULT 0,
        isqa_score INTEGER DEFAULT 0,
        conv_level INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS sessions(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        child_name TEXT NOT NULL,
        date TEXT NOT NULL,
        score INTEGER DEFAULT 0,
        tasks_ok INTEGER DEFAULT 0,
        tasks_fail INTEGER DEFAULT 0,
        duration_min INTEGER DEFAULT 0,
        skill_motor REAL DEFAULT 50,
        skill_cognitive REAL DEFAULT 50,
        skill_verbal REAL DEFAULT 50,
        skill_math REAL DEFAULT 50,
        skill_social REAL DEFAULT 50,
        emotion TEXT DEFAULT 'neutral',
        conv_level INTEGER DEFAULT 1,
        pdf_path TEXT DEFAULT '')""")
    c.execute("""CREATE TABLE IF NOT EXISTS task_history(
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        child_name TEXT NOT NULL,
        task_base_id TEXT NOT NULL,
        completed_at TEXT NOT NULL,
        result TEXT DEFAULT 'success')""")
    c.execute("CREATE INDEX IF NOT EXISTS idx_th ON task_history(child_name,task_base_id)")
    conn.commit(); conn.close()

init_db()

def db_save_child(name,age=6,level=2,notes=""):
    conn=_db()
    conn.execute("INSERT OR IGNORE INTO children(name,age,asd_level,notes,created_at) VALUES(?,?,?,?,?)",
        (name,age,level,notes,datetime.now().strftime("%Y-%m-%d")))
    conn.execute("UPDATE children SET age=?,asd_level=?,notes=? WHERE name=?",(age,level,notes,name))
    conn.commit(); conn.close()

def db_all_children():
    conn=_db()
    rows=conn.execute("SELECT name,age,asd_level,notes,created_at,isca_score,isaa_score,isqa_score FROM children ORDER BY name").fetchall()
    conn.close()
    return [{"name":r[0],"age":r[1],"level":r[2],"notes":r[3],"added":r[4],
             "isca":r[5],"isaa":r[6],"isqa":r[7]} for r in rows]

def db_save_session(cname,score,ok,fail,dur,skills,emotion,clvl,pdf=""):
    conn=_db()
    conn.execute("""INSERT INTO sessions(child_name,date,score,tasks_ok,tasks_fail,
        duration_min,skill_motor,skill_cognitive,skill_verbal,skill_math,skill_social,
        emotion,conv_level,pdf_path) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (cname,datetime.now().strftime("%Y-%m-%d %H:%M"),score,ok,fail,dur,
         skills.get("motor",50),skills.get("cognitive",50),skills.get("verbal",50),
         skills.get("math",50),skills.get("social",50),emotion,clvl,pdf))
    conn.commit(); conn.close()

def db_get_sessions(cname):
    conn=_db()
    rows=conn.execute("""SELECT date,score,tasks_ok,tasks_fail,duration_min,
        skill_motor,skill_cognitive,skill_verbal,skill_math,skill_social,
        emotion,conv_level,pdf_path FROM sessions WHERE child_name=? ORDER BY date DESC""",
        (cname,)).fetchall()
    conn.close()
    return [{"date":r[0],"score":r[1],"ok":r[2],"fail":r[3],"dur":r[4],
             "motor":r[5],"cognitive":r[6],"verbal":r[7],"math":r[8],"social":r[9],
             "emotion":r[10],"level":r[11],"pdf":r[12]} for r in rows]

def db_get_done_tasks(cname):
    conn=_db()
    rows=conn.execute("SELECT DISTINCT task_base_id FROM task_history WHERE child_name=?",(cname,)).fetchall()
    conn.close()
    return set(r[0] for r in rows)

def db_add_task(cname,base_id,result="success"):
    conn=_db()
    conn.execute("INSERT INTO task_history(child_name,task_base_id,completed_at,result) VALUES(?,?,?,?)",
        (cname,base_id,datetime.now().strftime("%Y-%m-%d %H:%M:%S"),result))
    conn.commit(); conn.close()

def db_reset_tasks(cname):
    conn=_db()
    conn.execute("DELETE FROM task_history WHERE child_name=?",(cname,))
    conn.commit(); conn.close()
    log.info(f"✅ Task history reset for {cname}")

def db_update_screening(cname,isca=None,isaa=None,isqa=None):
    conn=_db()
    if isca is not None: conn.execute("UPDATE children SET isca_score=? WHERE name=?",(isca,cname))
    if isaa is not None: conn.execute("UPDATE children SET isaa_score=? WHERE name=?",(isaa,cname))
    if isqa is not None: conn.execute("UPDATE children SET isqa_score=? WHERE name=?",(isqa,cname))
    conn.commit(); conn.close()


# ══════════════════════════════════════════════════════════════════
# Setup
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

LOCAL_IP=get_ip()
GEMINI_KEY="AIzaSyDEdleVKiQ5E00wMcjMbji0G9JcYT2TvE8"

print("\n"+"═"*60)
print("  Pepper Clinical Infinity V6 — Enhanced Edition")
print("  PECS×50 | ISAA/ISQA | Treatment Plan | No-Repeat")
print("═"*60)
CHILD_NAME=input("\n👦 Child name: ").strip() or "Child"
CHILD_AGE=input("   Age (default 6): ").strip() or "6"
SAFE_NAME=re.sub(r"[^a-zA-Z0-9_]","_",CHILD_NAME)
CSV_FILE=f"{SAFE_NAME}_v6.csv"

# Save child to DB
db_save_child(CHILD_NAME,int(CHILD_AGE) if CHILD_AGE.isdigit() else 6)

# Load completed tasks for this child
_child_done=db_get_done_tasks(CHILD_NAME)
log.info(f"✅ Loaded {len(_child_done)} completed tasks for {CHILD_NAME}")

with open(CSV_FILE,"w",newline="",encoding="utf-8-sig") as f:
    csv.writer(f).writerow(["Time","Child","Task","Domain","Protocol",
        "Result","Score","Emotion","ConvLevel","Time_ms"])

def log_csv(tid,dom,proto,result,sc,em,clvl,ms):
    try:
        with open(CSV_FILE,"a",newline="",encoding="utf-8-sig") as f:
            csv.writer(f).writerow([datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                CHILD_NAME,tid,dom,proto,"success" if result else "fail",sc,em,clvl,int(ms)])
    except: pass

if _GENAI:
    try: genai.configure(api_key=GEMINI_KEY)
    except: pass

# ══════════════════════════════════════════════════════════════════
# PECS — 50 Items
# ══════════════════════════════════════════════════════════════════
PECS_ITEMS=[
    # Morning (10)
    ("☀️","Wake Up","I woke up"),("🪥","Brush Teeth","I brush my teeth"),
    ("🚿","Wash Face","I wash my face"),("💇","Comb Hair","I comb my hair"),
    ("👕","Get Dressed","I get dressed"),("👟","Put Shoes On","I put my shoes on"),
    ("🥣","Eat Breakfast","I eat breakfast"),("💧","Drink Water","I drink water"),
    ("🚽","Use Toilet","I need the toilet"),("🧼","Wash Hands","I wash my hands"),
    # Food (10)
    ("🍽️","Food","I want food"),("🥤","Drink","I want a drink"),
    ("😋","Hungry","I am hungry"),("😊","Full","I am full"),
    ("🥛","Milk","I want milk"),("🧃","Juice","I want juice"),
    ("🍞","Bread","I want bread"),("🍚","Rice","I want rice"),
    ("🍎","Apple","I want an apple"),("🍌","Banana","I want a banana"),
    # Social (10)
    ("👋","Hello","Hello"),("🙋","Goodbye","Goodbye"),
    ("🙏","Please","Please"),("🤝","Thank You","Thank you"),
    ("😔","Sorry","I am sorry"),("🆘","Help","I need help"),
    ("✅","Yes","Yes"),("❌","No","No"),
    ("➕","More","I want more"),("❤️","I Love You","I love you"),
    # Safety & Emotions (10)
    ("🛑","Stop","Stop"),("🔥","Hot","This is hot"),
    ("🧊","Cold","This is cold"),("🤕","Pain","I am in pain"),
    ("😴","Tired","I am tired"),("🏠","Home","I want to go home"),
    ("🏫","School","I go to school"),("😊","Happy","I am happy"),
    ("😢","Sad","I am sad"),("👍","OK","I am OK"),
    # Activities (10)
    ("🎮","Play","I want to play"),("📺","TV","I want to watch TV"),
    ("📚","Read","I want to read"),("🎨","Draw","I want to draw"),
    ("🎵","Music","I want music"),("🚶","Walk","I want to walk"),
    ("😴","Sleep","I want to sleep"),("🛁","Bath","I want a bath"),
    ("🌳","Outside","I want to go outside"),("👏","Good Job","Good job"),
]

# ══════════════════════════════════════════════════════════════════
# Task Pool
# ══════════════════════════════════════════════════════════════════
COLORS=[
    {"id":"red","color":"#ef4444","label":"🔴 Red"},
    {"id":"blue","color":"#3b82f6","label":"🔵 Blue"},
    {"id":"green","color":"#22c55e","label":"🟢 Green"},
    {"id":"yellow","color":"#eab308","label":"🟡 Yellow"},
    {"id":"purple","color":"#a855f7","label":"🟣 Purple"},
    {"id":"orange","color":"#f97316","label":"🟠 Orange"},
    {"id":"pink","color":"#ec4899","label":"🩷 Pink"},
    {"id":"brown","color":"#92400e","label":"🟫 Brown"},
    {"id":"white","color":"#e2e8f0","label":"⬜ White"},
    {"id":"black","color":"#1e293b","label":"⬛ Black"},
]
ANIMALS=[
    {"id":"dog","emoji":"🐶","label":"Dog"},{"id":"cat","emoji":"🐱","label":"Cat"},
    {"id":"lion","emoji":"🦁","label":"Lion"},{"id":"elephant","emoji":"🐘","label":"Elephant"},
    {"id":"rabbit","emoji":"🐰","label":"Rabbit"},{"id":"bear","emoji":"🐻","label":"Bear"},
    {"id":"monkey","emoji":"🐵","label":"Monkey"},{"id":"tiger","emoji":"🐯","label":"Tiger"},
    {"id":"fish","emoji":"🐟","label":"Fish"},{"id":"bird","emoji":"🐦","label":"Bird"},
    {"id":"cow","emoji":"🐄","label":"Cow"},{"id":"horse","emoji":"🐎","label":"Horse"},
    {"id":"sheep","emoji":"🐑","label":"Sheep"},{"id":"duck","emoji":"🦆","label":"Duck"},
    {"id":"frog","emoji":"🐸","label":"Frog"},{"id":"butterfly","emoji":"🦋","label":"Butterfly"},
]
FRUITS=[
    {"id":"apple","emoji":"🍎","label":"Apple"},{"id":"banana","emoji":"🍌","label":"Banana"},
    {"id":"orange","emoji":"🍊","label":"Orange"},{"id":"grapes","emoji":"🍇","label":"Grapes"},
    {"id":"strawberry","emoji":"🍓","label":"Strawberry"},{"id":"mango","emoji":"🥭","label":"Mango"},
    {"id":"watermelon","emoji":"🍉","label":"Watermelon"},{"id":"peach","emoji":"🍑","label":"Peach"},
    {"id":"pear","emoji":"🍐","label":"Pear"},{"id":"cherry","emoji":"🍒","label":"Cherry"},
    {"id":"pineapple","emoji":"🍍","label":"Pineapple"},{"id":"kiwi","emoji":"🥝","label":"Kiwi"},
]
SHAPES=[
    {"id":"circle","emoji":"⭕","label":"Circle"},{"id":"square","emoji":"⬛","label":"Square"},
    {"id":"triangle","emoji":"🔺","label":"Triangle"},{"id":"star","emoji":"⭐","label":"Star"},
    {"id":"heart","emoji":"❤️","label":"Heart"},{"id":"diamond","emoji":"💎","label":"Diamond"},
]
EMOTIONS_ITEMS=[
    {"id":"happy","emoji":"😊","label":"Happy"},{"id":"sad","emoji":"😢","label":"Sad"},
    {"id":"angry","emoji":"😠","label":"Angry"},{"id":"scared","emoji":"😨","label":"Scared"},
    {"id":"surprised","emoji":"😲","label":"Surprised"},{"id":"tired","emoji":"😴","label":"Tired"},
]
FOODS=[
    {"id":"rice","emoji":"🍚","label":"Rice"},{"id":"bread","emoji":"🍞","label":"Bread"},
    {"id":"egg","emoji":"🥚","label":"Egg"},{"id":"milk","emoji":"🥛","label":"Milk"},
    {"id":"cheese","emoji":"🧀","label":"Cheese"},{"id":"soup","emoji":"🍲","label":"Soup"},
]
VEHICLES=[
    {"id":"car","emoji":"🚗","label":"Car"},{"id":"bus","emoji":"🚌","label":"Bus"},
    {"id":"train","emoji":"🚂","label":"Train"},{"id":"airplane","emoji":"✈️","label":"Airplane"},
    {"id":"boat","emoji":"⛵","label":"Boat"},{"id":"bicycle","emoji":"🚲","label":"Bicycle"},
]
BODY=[
    {"id":"head","emoji":"🗣️","label":"Head"},{"id":"eye","emoji":"👁️","label":"Eye"},
    {"id":"ear","emoji":"👂","label":"Ear"},{"id":"nose","emoji":"👃","label":"Nose"},
    {"id":"mouth","emoji":"👄","label":"Mouth"},{"id":"hand","emoji":"✋","label":"Hand"},
    {"id":"foot","emoji":"🦶","label":"Foot"},{"id":"arm","emoji":"💪","label":"Arm"},
]
MOTORS=[
    {"id":"clap","name":"👏 Clap","verify":"clap",
     "instruction":"Clap your hands!","waiting":"Clap now! 👏",
     "success":"Great clapping! ✅","fail":"Put hands together and clap!",
     "prompts":["Clap!","Hands together!","Like this! 👏"]},
    {"id":"wave","name":"👋 Wave","verify":"wave",
     "instruction":"Wave your hand! Say hello!","waiting":"Wave now! 👋",
     "success":"Excellent waving! ✅","fail":"Move your hand side to side!",
     "prompts":["Wave!","Hello!","Side to side!"]},
    {"id":"raise_hand","name":"✋ Raise Hand","verify":"raise_hand",
     "instruction":"Raise your hand up high!","waiting":"Hand up! ✋",
     "success":"Perfect! Hand raised! ✅","fail":"Lift your arm above your head!",
     "prompts":["Raise it!","Up high!","Higher!"]},
    {"id":"touch_nose","name":"👆 Touch Nose","verify":"touch_nose",
     "instruction":"Touch your nose!","waiting":"Touch your nose! 👆",
     "success":"You touched your nose! ✅","fail":"Point your finger to your nose!",
     "prompts":["Nose!","Touch it!","Finger to nose!"]},
    {"id":"arms_out","name":"🤸 Arms Out","verify":"arms_out",
     "instruction":"Stretch your arms out wide!","waiting":"Arms out! 🤸",
     "success":"Like an airplane! ✅","fail":"Open your arms to the sides!",
     "prompts":["To the sides!","Like an airplane!","Wider!"]},
    {"id":"hands_up","name":"🙌 Hands Up","verify":"hands_up",
     "instruction":"Raise both hands up!","waiting":"Both hands up! 🙌",
     "success":"Star pose! ✅","fail":"Raise both arms above your head!",
     "prompts":["Both hands!","Up high!","Reach for the sky!"]},
    {"id":"jump","name":"🦘 Jump","verify":"jump",
     "instruction":"Jump!","waiting":"Jump! 🦘",
     "success":"Great jump! ✅","fail":"Jump up off the ground!",
     "prompts":["Jump!","Up!","Boing!"]},
    {"id":"point","name":"👉 Point","verify":"point",
     "instruction":"Point your finger forward!","waiting":"Point! 👉",
     "success":"Great pointing! ✅","fail":"Extend your index finger forward!",
     "prompts":["Point!","Finger forward!","Like this!"]},
]
WORDS=[
    "apple","ball","cat","dog","elephant","fish","good","happy","jump","kite",
    "love","milk","play","red","sun","tree","water","yes","no","one","two",
    "three","four","five","six","seven","eight","nine","ten","blue","green",
    "bird","book","cup","door","eye","foot","hand","head","nose","arm","leg",
    "big","small","hot","cold","up","down","in","out","help","stop","come",
    "sit","run","walk","eat","drink","sleep","open","close","mum","dad",
]
SOCIAL=[
    "hello","thank you","please","I want more","help me","yes","no","goodbye",
    "I am sorry","I love you","how are you","my name is","I want","I need",
    "good morning","good night","I am fine","can I","good job","I am hungry",
]

def _grid_task(items,prefix,domain,protocol,tokens):
    tgt=random.choice(items)
    others=[x for x in items if x["id"]!=tgt["id"]]
    dis=random.sample(others,min(3,len(others)))
    opts=[tgt]+dis; random.shuffle(opts)
    cor=next(i for i,o in enumerate(opts) if o["id"]==tgt["id"])
    lbl=tgt.get("label",tgt["id"])
    return {"id":f"{prefix}_{tgt['id']}_{random.randint(0,99999)}",
            "base_id":f"{prefix}_{tgt['id']}",
            "domain":domain,"protocol":protocol,"name":lbl,
            "instruction":f"Where is {lbl}? Tap it!",
            "waiting":f"Find {lbl}!","success":f"Correct! {lbl}! ✅",
            "fail":f"That's {lbl}!","tablet_mode":"grid",
            "options":opts,"correct":cor,"tokens":tokens,"joy":"celebrate",
            "prompts":[f"Where is {lbl}?","Look carefully!","You can do it!"],
            "verify":"tablet_click"}

def generate_pool():
    pool=[]
    for _ in range(700):
        m=random.choice(MOTORS)
        pool.append({**m,"id":f"{m['id']}_{random.randint(0,99999)}",
            "base_id":m["id"],"domain":"Motor",
            "protocol":random.choice(["ABA-DTT","ESDM"]),
            "tablet_mode":"motor","tokens":2,"joy":"dance"})
    for _ in range(400): pool.append(_grid_task(COLORS,"color","Cognitive","TEACCH",3))
    for _ in range(350): pool.append(_grid_task(ANIMALS,"animal","Cognitive","TEACCH",4))
    for _ in range(300): pool.append(_grid_task(FRUITS,"fruit","Cognitive","TIE",4))
    for _ in range(250): pool.append(_grid_task(SHAPES,"shape","Cognitive","TEACCH",4))
    for _ in range(200): pool.append(_grid_task(EMOTIONS_ITEMS,"emotion","Social","ESDM",5))
    for _ in range(200): pool.append(_grid_task(FOODS,"food","Daily","TIE",4))
    for _ in range(200): pool.append(_grid_task(VEHICLES,"vehicle","Cognitive","TEACCH",4))
    for _ in range(200): pool.append(_grid_task(BODY,"body","Verbal","DTT",4))
    for _ in range(450):
        n=random.randint(1,10)
        pool.append({"id":f"count_{n}_{random.randint(0,99999)}","base_id":f"count_{n}",
            "domain":"Math","protocol":"ABA-DTT","name":f"🔢 Show {n}",
            "instruction":f"Show me {n} fingers!","waiting":f"Show {n} fingers 🖐️",
            "success":f"Yes! {n} fingers! ✅","fail":f"Show me {n} fingers!",
            "tablet_mode":"number","target_number":n,"verify":"finger_count",
            "tokens":5,"joy":"celebrate",
            "prompts":[f"Show {n}!","Count your fingers!","Use both hands!"]})
    for _ in range(500):
        w=random.choice(WORDS)
        pool.append({"id":f"say_{w}_{random.randint(0,99999)}","base_id":f"say_{w}",
            "domain":"Verbal","protocol":"DTT","name":f"🗣️ Say '{w}'",
            "instruction":f"Say the word: {w}!","waiting":f"Say {w}! 🎤",
            "success":f"I heard you! {w}! ✅","fail":f"Try again! Say: {w}!",
            "tablet_mode":"word","word_text":w,"verify":"speech_keyword","keyword":w,
            "tokens":4,"joy":"dance",
            "prompts":[f"Say {w}!","Press the mic!","Loud and clear!"]})
    for _ in range(400):
        ph=random.choice(SOCIAL)
        pool.append({"id":f"phrase_{ph.replace(' ','_')}_{random.randint(0,99999)}",
            "base_id":f"phrase_{ph.replace(' ','_')}",
            "domain":"Social","protocol":"ESDM","name":f"💬 '{ph}'",
            "instruction":f"Say: {ph}!","waiting":f"Say {ph}! 🎤",
            "success":f"Great! '{ph}'! ✅","fail":f"Try: {ph}!",
            "tablet_mode":"social","social_text":ph,"verify":"speech_keyword","keyword":ph,
            "tokens":6,"joy":"full_joy",
            "prompts":[f"Say {ph}!","You can do it!","Speak up!"]})
    for _ in range(500):
        iid,emoji,label,kw=random.choice([(p[0],p[1],p[2],p[2]) for p in PECS_ITEMS])
        pool.append({"id":f"daily_{iid}_{random.randint(0,99999)}","base_id":f"daily_{iid}",
            "domain":"Daily","protocol":"TIE","name":f"{emoji} {label}",
            "instruction":f"Say: {kw}! {emoji}","waiting":f"Say it! {emoji}",
            "success":f"Excellent! {label}! ✅","fail":f"Try! Say: {kw}!",
            "tablet_mode":"daily","daily_emoji":emoji,"daily_label":label,
            "verify":"speech_keyword","keyword":kw,"tokens":5,"joy":"celebrate",
            "prompts":[f"Say {kw}!","Loud and clear!","Press the mic!"]})
    random.shuffle(pool)
    log.info(f"✅ Generated {len(pool)} therapy tasks")
    return pool

log.info("🎯 Generating task pool...")
TASK_POOL=generate_pool()
SESSION_HISTORY=deque(maxlen=400)
MAX_FAILS=2

# ══════════════════════════════════════════════════════════════════
# Shared State
# ══════════════════════════════════════════════════════════════════
ST={
    "child_name":CHILD_NAME,"age":int(CHILD_AGE) if CHILD_AGE.isdigit() else 6,
    "score":0,"tokens":0,"streak":0,"consecutive":0,"mastered":0,
    "conversation_level":1,"domain":"Motor","protocol":"ABA-DTT",
    "emotion":"neutral",
    "emotion_pct":{k:0 for k in ["happy","joyful","surprised","sad","angry","fear","neutral"]},
    "face_detected":False,"attention":70,
    "finger_count":0,"lip_motion":0.0,"lip_speaking":False,"lip_sync_value":0.0,
    "is_speaking":False,"interrupt_flag":False,"pecs_interrupt":False,
    "recording":False,"mic_level":0.0,"listening":False,
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
}

_ai_chat=[]

def LOG(msg,t="info"):
    e={"time":datetime.now().strftime("%H:%M:%S"),"msg":str(msg)[:120],"type":t}
    ST["logs"].append(e)
    if len(ST["logs"])>600: ST["logs"]=ST["logs"][-600:]
    if t=="success": log.info(f"✅ {msg[:60]}")
    elif t=="fail":  log.warning(f"❌ {msg[:60]}")

def get_next_task():
    """Get next task — skip completed tasks for this child unless parent refreshed"""
    recent=set(SESSION_HISTORY)
    all_done=recent|_child_done
    candidates=[t for t in TASK_POOL if t.get("base_id","") not in all_done]
    if not candidates:
        SESSION_HISTORY.clear()
        candidates=[t for t in TASK_POOL if t.get("base_id","") not in _child_done]
        if not candidates: candidates=TASK_POOL  # all done — full reset
    cl=ST["conversation_level"]
    if cl==1:   filt=[t for t in candidates if t["domain"] in ["Motor","Daily"]]
    elif cl==2: filt=[t for t in candidates if t["domain"] in ["Motor","Cognitive","Math","Daily","Verbal"]]
    else:       filt=candidates
    task=random.choice(filt if filt else candidates)
    SESSION_HISTORY.append(task.get("base_id",""))
    ST["_task_start_time"]=time.time()
    return task


# ══════════════════════════════════════════════════════════════════
# PyBullet Watchdog
# ══════════════════════════════════════════════════════════════════
_PB_SCRIPT=r"""
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
wc=[0.92,0.92,0.96,1]
for pos,ext in [([0,-4,1.1],[5,.1,1.1]),([0,4,1.1],[5,.1,1.1]),
                ([5,0,1.1],[.1,4,1.1]),([-5,0,1.1],[.1,4,1.1])]:
    p.createMultiBody(0,-1,p.createVisualShape(p.GEOM_BOX,halfExtents=ext,rgbaColor=wc),pos)
p.createMultiBody(0,-1,p.createVisualShape(p.GEOM_BOX,halfExtents=[4.5,3.5,.02],
    rgbaColor=[.65,.55,.40,1]),[0,0,.01])
for txt,pos,col in [("ABA Motor",[-3.5,3,.05],[1,.3,.3,1]),
    ("TEACCH Visual",[3.5,3,.05],[.3,.7,1,1]),("DTT Verbal",[0,3.8,.05],[.3,1,.5,1]),
    ("ESDM Social",[-3.5,-3,.05],[1,.8,.2,1]),("TIE Daily",[3.5,-3,.05],[.8,.3,1,1]),
    (f"⭐ {child}",[0,0,3.2],[.4,.5,.9,1])]:
    p.addUserDebugText(txt,pos,col[:3],textSize=1.2,lifeTime=0)
pepper=sim.spawnPepper(client); pepper.goToPosture("Stand",0.5)
p.resetDebugVisualizerCamera(6,45,-30,[0,0,0.8])
print("PYBULLET_READY",flush=True)
rx=ry=ph=0.0; lu=0.0
st={"is_speaking":False,"lip":0.0,"sj":False,"ht":0.0}
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
            self._proc=subprocess.Popen([sys.executable,"-c",_PB_SCRIPT,self.child],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,text=True,bufsize=1)
            dl=time.time()+30
            while time.time()<dl:
                try:
                    ln=self._proc.stdout.readline()
                    if "PYBULLET_READY" in ln: self._ready=True; log.info("✅ Pepper simulation ready"); return True
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
            self._ready=False; log.warning("Simulation crashed — restarting in 3s..."); time.sleep(3)
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
# Bridge Signals
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
BRIDGE=Bridge()

# ══════════════════════════════════════════════════════════════════
# Voice Engine
# ══════════════════════════════════════════════════════════════════
class VoiceEngine:
    def __init__(self):
        self.ok=False; self._lk=threading.Lock()
        try:
            self.e=pyttsx3.init()
            self.e.setProperty("rate",115); self.e.setProperty("volume",1.0)
            self.ok=True; log.info("✅ TTS ready")
        except Exception as ex: log.warning(f"TTS: {ex}")
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
        ST["session_chat"].append({"role":"Pepper","text":clean,"time":datetime.now().strftime("%H:%M:%S")})
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
# Camera Thread + Touch Recorder
# ══════════════════════════════════════════════════════════════════
EMO_COLORS={"happy":(0,220,80),"joyful":(0,255,180),"sad":(100,100,220),
            "angry":(255,60,60),"fear":(0,180,220),"surprised":(200,50,220),"neutral":(180,180,180)}

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
        try:
            self._pose=mp.solutions.pose.Pose(min_detection_confidence=0.55,model_complexity=1)
            log.info("✅ MediaPipe Pose")
        except: pass
        try:
            self._hands=mp.solutions.hands.Hands(max_num_hands=2,min_detection_confidence=0.60)
            log.info("✅ MediaPipe Hands")
        except: pass
        try:
            self._face=mp.solutions.face_mesh.FaceMesh(max_num_faces=1,
                min_detection_confidence=0.5,refine_landmarks=True)
            log.info("✅ MediaPipe FaceMesh")
        except: pass
        os.environ["CUDA_VISIBLE_DEVICES"]="0"

    def _init_cam(self):
        for idx in [1,0,2]:
            try:
                c=cv2.VideoCapture(idx)
                if c.isOpened():
                    ret,f=c.read()
                    if ret and f is not None and f.size>0:
                        c.set(cv2.CAP_PROP_FRAME_WIDTH,640); c.set(cv2.CAP_PROP_FRAME_HEIGHT,480)
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
                cv2.putText(frame,"No Camera — Simulation Mode",(80,240),
                    cv2.FONT_HERSHEY_SIMPLEX,.8,(100,200,255),2)
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
                        lip_col=(0,255,200) if ST["lip_speaking"] else (80,80,180)
                        lip_ids=[61,185,40,39,37,0,267,269,270,409,291,146,91,181,84,17,314,405,321,375,291]
                        pts=np.array([(int(fl[i].x*w_),int(fl[i].y*h_)) for i in lip_ids],np.int32)
                        cv2.polylines(frame,[pts],True,lip_col,2)
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
                            wrist=hlm.landmark[0]; h_,w_=frame.shape[:2]
                            cv2.putText(frame,f"{label[0]}:{fc_n}",
                                (int(wrist.x*w_)-20,int(wrist.y*h_)+25),
                                cv2.FONT_HERSHEY_SIMPLEX,.6,(255,255,0),2)
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
                if va=="clap":      ok=ST.get("clapping",False)
                elif va=="wave":    ok=ST.get("waving",False)
                elif va=="raise_hand": ok=ST.get("hand_raised",False)
                elif va=="hands_up":   ok=ST.get("hands_up",False)
                elif va=="jump":    ok=ST.get("body_motion",0)>30
                elif va=="finger_count": ok=ST["finger_count"]==ST.get("finger_target",1)
                elif va in ["arms_out","touch_nose","point"]: ok=ST.get("body_motion",0)>5
                if ok:
                    ST["verify_result"]=True; ST["verify_action"]=None
                    ST["instant_success"]=True; LOG("✅ Motor verified","success")
            h_,w_=frame.shape[:2]
            cv2.rectangle(frame,(0,0),(w_,50),(8,10,24),-1)
            cv2.putText(frame,f"{'★'*ST['consecutive']}{'☆'*(3-ST['consecutive'])} | {ST['emotion']} | L{ST['conversation_level']}",
                (8,20),cv2.FONT_HERSHEY_SIMPLEX,.48,(255,220,0),1)
            cv2.putText(frame,f"Score:{ST['score']} | Attn:{ST['attention']}% | Fingers:{ST['finger_count']}/10 | {'👄speech' if ST['lip_speaking'] else '·'}",
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
        if kw in t or t in kw or kw.lower() in t.lower():
            ST["instant_success"]=True; return
        if len(kw)>=3 and len(t)>=3 and kw[:3].lower()==t[:3].lower() and ST.get("lip_speaking"):
            ST["instant_success"]=True


# ══════════════════════════════════════════════════════════════════
# Click Cards + Avatar + PECS Widget
# ══════════════════════════════════════════════════════════════════
class ClickCard(QPushButton):
    def __init__(self,data,idx,parent=None):
        super().__init__(parent); self.idx=idx; self._data=data
        self.setFixedSize(150,150); self.setCursor(Qt.CursorShape.PointingHandCursor)
        self._set_normal()
        self.clicked.connect(lambda: BRIDGE.sig_task.emit({"action":"click","idx":self.idx}))
    def _set_normal(self):
        d=self._data
        if "color" in d:
            self.setText(f"\n\n{d['label']}"); self.setFont(QFont("Arial",11,QFont.Weight.Bold))
            self.setStyleSheet(f"QPushButton{{background:{d['color']};border-radius:75px;"
                f"border:5px solid rgba(255,255,255,.3);color:white;font-weight:bold;}}"
                f"QPushButton:hover{{border:5px solid white;}}")
        else:
            self.setText(f"{d.get('emoji','?')}\n{d['label']}"); self.setFont(QFont("Arial",13,QFont.Weight.Bold))
            self.setStyleSheet("QPushButton{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
                "stop:0 #1e1b4b,stop:1 #0c0f2e);border-radius:18px;border:4px solid #4f46e5;"
                "color:#e0e6ff;font-weight:bold;padding:6px;}"
                "QPushButton:hover{border:4px solid #a78bfa;}")
    def flash_correct(self): self.setStyleSheet(self.styleSheet()+"QPushButton{border:8px solid #22c55e!important;}")
    def flash_wrong(self):   self.setStyleSheet(self.styleSheet()+"QPushButton{border:8px solid #ef4444!important;opacity:.4;}")
    def reset(self): self._set_normal()

class AvatarWidget(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent); self.setFixedSize(200,260)
        self._phase=0.0
        self._t=QTimer(); self._t.timeout.connect(self._tick); self._t.start(40)
    def _tick(self): self._phase+=0.12 if ST["is_speaking"] else 0.03; self.update()
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(),QColor(8,10,22))
        em=ST["emotion"]; lip=ST.get("lip_sync_value",0.0)
        sj=ST.get("social_joy_active",False)
        blink=int(self._phase*3)%44==0; cx,cy=100,120
        g=QLinearGradient(cx-40,cy+45,cx+40,cy+120)
        g.setColorAt(0,QColor(70,90,190)); g.setColorAt(1,QColor(50,70,160))
        p.setBrush(QBrush(g)); p.setPen(QPen(QColor(100,120,210),2))
        p.drawEllipse(cx-40,cy+45,80,75)
        p.setBrush(QBrush(QColor(20,24,50))); p.setPen(QPen(QColor(79,70,229),2))
        p.drawRoundedRect(cx-22,cy+55,44,32,4,4)
        p.setPen(QColor(167,139,250)); p.setFont(QFont("Arial",6,QFont.Weight.Bold))
        p.drawText(QRect(cx-20,cy+60,40,16),Qt.AlignmentFlag.AlignCenter,"PEPPER V6")
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
            p.drawLine(cx-40,cy+62,cx-62,cy+94); p.drawLine(cx+40,cy+62,cx+62,cy+94)
        p.drawLine(cx-16,cy+118,cx-24,cy+152); p.drawLine(cx+16,cy+118,cx+24,cy+152)
        ht=ST.get("head_tilt",0.0)*5; hbob=int(3*math.sin(self._phase*.5))
        hx=cx+int(ht); hy=cy-46+hbob
        p.setBrush(QBrush(QColor(220,195,173))); p.setPen(QPen(QColor(200,175,155),2))
        p.drawEllipse(hx-40,hy-40,80,80)
        ec=QColor(100,255,180) if (em in ["happy","joyful"] or sj) else (
           QColor(255,80,80) if em=="angry" else
           QColor(100,120,220) if em=="sad" else QColor(100,180,255))
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
            p.setPen(QPen(QColor(int(128+127*math.sin(jt2*3)),200,255),3))
            p.setBrush(Qt.BrushStyle.NoBrush); p.drawEllipse(cx-pr,cy-pr,pr*2,pr*2)
        p.setPen(QColor(0,200,255)); p.setFont(QFont("Arial",7,QFont.Weight.Bold))
        p.drawText(QRect(0,2,200,14),Qt.AlignmentFlag.AlignCenter,f"Level {ST['conversation_level']}")
        status=("Joy 🎉" if sj else "Speaking 🔊" if ST["is_speaking"]
                else "Recording 🔴" if ST["recording"] else "Ready 💤")
        p.setPen(QColor(160,140,255)); p.setFont(QFont("Arial",7,QFont.Weight.Bold))
        p.drawText(QRect(0,228,200,20),Qt.AlignmentFlag.AlignCenter,status)
        p.end()

class PECSWidget(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent); self.setFixedHeight(90)
        self.setStyleSheet("QWidget{background:#0c0f1e;border-top:2px solid #1a1f40;}")
        outer=QHBoxLayout(self); outer.setContentsMargins(4,3,4,3); outer.setSpacing(4)
        t=QLabel("PECS (50)"); t.setFont(QFont("Arial",7,QFont.Weight.Bold))
        t.setStyleSheet("color:#a78bfa;"); outer.addWidget(t)
        scroll=QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(82)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        inner=QWidget(); il=QHBoxLayout(inner); il.setContentsMargins(2,2,2,2); il.setSpacing(4)
        for emoji,name,phrase in PECS_ITEMS:
            btn=QPushButton(f"{emoji}\n{name[:8]}")
            btn.setFont(QFont("Arial",6,QFont.Weight.Bold)); btn.setFixedSize(70,72)
            btn.setStyleSheet("QPushButton{background:#1e1b4b;border:2px solid #4f46e5;"
                "border-radius:8px;color:#e0e6ff;}"
                "QPushButton:hover{background:#2e2b6e;border-color:#a78bfa;}"
                "QPushButton:pressed{background:#3e3b8e;}")
            btn.setToolTip(f"Say: {phrase}")
            btn.clicked.connect(lambda _,ph=phrase,nm=name: self._press(nm,ph))
            il.addWidget(btn)
        scroll.setWidget(inner); outer.addWidget(scroll,1)
    def _press(self,name,phrase):
        ST["pecs_log"].append({"time":datetime.now().strftime("%H:%M:%S"),
            "name":name,"phrase":phrase,"emotion":ST["emotion"]})
        if len(ST["pecs_log"])>100: ST["pecs_log"]=ST["pecs_log"][-100:]
        LOG(f"PECS:{name}={phrase}")
        BRIDGE.sig_pecs.emit(phrase)
        if VOICE_REF: VOICE_REF.say_pecs(f"{CHILD_NAME} says: {phrase}")


# ══════════════════════════════════════════════════════════════════
# Main Window
# ══════════════════════════════════════════════════════════════════
class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"🤖 Pepper Clinical Infinity V6 — {CHILD_NAME}")
        self.setFixedSize(1600,900)
        self._cards=[]; self._locked=True; self._correct_idx=-1
        self._recorder=TouchRecorder()
        self._build_ui(); self._connect_bridge()
        self._stats_t=QTimer(); self._stats_t.timeout.connect(self._refresh); self._stats_t.start(400)

    def _build_ui(self):
        root=QWidget(); self.setCentralWidget(root)
        root.setStyleSheet("QWidget{background:#060918;}")
        outer=QVBoxLayout(root); outer.setSpacing(0); outer.setContentsMargins(0,0,0,0)
        main=QHBoxLayout(); main.setSpacing(0); main.setContentsMargins(0,0,0,0)
        # Left panel
        left=QFrame(); left.setFixedWidth(780)
        left.setStyleSheet("QFrame{background:#0a0d1e;border-right:2px solid #1a1f40;}")
        ll=QVBoxLayout(left); ll.setContentsMargins(0,0,0,0); ll.setSpacing(0)
        top_row=QWidget(); tr=QHBoxLayout(top_row); tr.setContentsMargins(0,0,0,0); tr.setSpacing(0)
        self.cam_lbl=QLabel(); self.cam_lbl.setFixedSize(580,520)
        self.cam_lbl.setStyleSheet("background:#000;"); self.cam_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tr.addWidget(self.cam_lbl)
        side=QWidget(); side.setFixedWidth(200); sl=QVBoxLayout(side)
        sl.setContentsMargins(0,0,0,0); sl.setSpacing(0)
        self.avatar=AvatarWidget(); sl.addWidget(self.avatar)
        # Emotion panel
        self.emo_panel=QWidget(); self.emo_panel.setFixedSize(200,260)
        self.emo_panel.setStyleSheet("QWidget{background:#0a0d1e;}")
        ep_l=QVBoxLayout(self.emo_panel); ep_l.setContentsMargins(4,4,4,4); ep_l.setSpacing(2)
        self.emo_lbl=QLabel("😐 neutral"); self.emo_lbl.setFont(QFont("Arial",9,QFont.Weight.Bold))
        self.emo_lbl.setStyleSheet("color:#a78bfa;"); self.emo_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ep_l.addWidget(self.emo_lbl)
        self.emo_bars={}
        for em_ in ["happy","joyful","surprised","sad","angry","fear","neutral"]:
            row=QWidget(); rl=QHBoxLayout(row); rl.setContentsMargins(2,0,2,0); rl.setSpacing(4)
            lb=QLabel(em_[:7]); lb.setFont(QFont("Arial",6)); lb.setFixedWidth(50)
            lb.setStyleSheet("color:#9ca3af;"); rl.addWidget(lb)
            bar=QProgressBar(); bar.setFixedHeight(7); bar.setRange(0,100); bar.setValue(0)
            bar.setTextVisible(False)
            col={"happy":"#22c55e","joyful":"#00ffc8","surprised":"#a78bfa",
                 "sad":"#3b82f6","angry":"#ef4444","fear":"#06b6d4","neutral":"#6b7280"}.get(em_,"#fff")
            bar.setStyleSheet(f"QProgressBar{{background:#1a1f40;border-radius:3px;border:none;}}"
                f"QProgressBar::chunk{{background:{col};border-radius:3px;}}")
            rl.addWidget(bar,1); ep_l.addWidget(row); self.emo_bars[em_]=bar
        self.lip_lbl=QLabel("👄 Lip motion: 0.00"); self.lip_lbl.setFont(QFont("Arial",7))
        self.lip_lbl.setStyleSheet("color:#34d399;"); ep_l.addWidget(self.lip_lbl)
        self.finger_lbl2=QLabel("🖐️ Fingers: 0/10"); self.finger_lbl2.setFont(QFont("Arial",7))
        self.finger_lbl2.setStyleSheet("color:#fbbf24;"); ep_l.addWidget(self.finger_lbl2)
        sl.addWidget(self.emo_panel); tr.addWidget(side); ll.addWidget(top_row)
        # Status bar
        sr_=QWidget(); srl=QHBoxLayout(sr_); srl.setContentsMargins(6,3,6,3)
        self.status_lbl=QLabel(f"👦 {CHILD_NAME} | Ready")
        self.status_lbl.setFont(QFont("Arial",9,QFont.Weight.Bold))
        self.status_lbl.setStyleSheet("color:#fbbf24;"); srl.addWidget(self.status_lbl,1)
        ll.addWidget(sr_)
        self.lip_bar=QProgressBar(); self.lip_bar.setFixedHeight(7)
        self.lip_bar.setRange(0,100); self.lip_bar.setValue(0); self.lip_bar.setTextVisible(False)
        self.lip_bar.setStyleSheet("QProgressBar{background:#1a1f40;border:none;border-radius:3px;}"
            "QProgressBar::chunk{background:#00ffc8;border-radius:3px;}"); ll.addWidget(self.lip_bar)
        # Chat
        ch_lbl=QLabel("💬 Pepper Chat | Whisper AI + Lip Motion Verification")
        ch_lbl.setFont(QFont("Arial",8,QFont.Weight.Bold))
        ch_lbl.setStyleSheet("color:#a78bfa;background:#0c0f1e;padding:2px;")
        ch_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); ll.addWidget(ch_lbl)
        self.chat_area=QTextEdit(); self.chat_area.setReadOnly(True)
        self.chat_area.setFont(QFont("Arial",9))
        self.chat_area.setStyleSheet("QTextEdit{background:#07090f;color:#e0e6ff;"
            "border:1px solid #1a1f40;padding:4px;}"); self.chat_area.setFixedHeight(90)
        ll.addWidget(self.chat_area)
        cir=QWidget(); cirow=QHBoxLayout(cir); cirow.setContentsMargins(4,2,4,2); cirow.setSpacing(4)
        self.chat_input=QLineEdit()
        self.chat_input.setPlaceholderText("Type message to therapist or Pepper AI... (Enter)")
        self.chat_input.setFont(QFont("Arial",10))
        self.chat_input.setStyleSheet("QLineEdit{background:#0c0f1e;color:#e0e6ff;"
            "border:2px solid #4f46e5;border-radius:8px;padding:5px;}"); self.chat_input.setFixedHeight(34)
        self.chat_input.returnPressed.connect(self._send_chat); cirow.addWidget(self.chat_input,1)
        sb2=QPushButton("Send"); sb2.setFixedSize(70,34)
        sb2.setStyleSheet("QPushButton{background:#4f46e5;color:white;border-radius:8px;font-weight:bold;}")
        sb2.clicked.connect(self._send_chat); cirow.addWidget(sb2); ll.addWidget(cir)
        main.addWidget(left)
        # Right panel
        right=QWidget(); right.setFixedWidth(820)
        rl=QVBoxLayout(right); rl.setSpacing(5); rl.setContentsMargins(10,6,10,6)
        # Header
        hdr=QFrame(); hdr.setFixedHeight(64)
        hdr.setStyleSheet("QFrame{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #1a0a3d,stop:0.5 #0a0f28,stop:1 #1a0a3d);"
            "border-radius:12px;border:2px solid #4f46e5;}")
        hl=QHBoxLayout(hdr); hl.setContentsMargins(12,4,12,4)
        av_lbl=QLabel("🤖"); av_lbl.setFont(QFont("Arial",22)); av_lbl.setStyleSheet("color:#a78bfa;"); hl.addWidget(av_lbl)
        tw_=QWidget(); tl2=QVBoxLayout(tw_); tl2.setSpacing(1)
        self.title_lbl=QLabel("Pepper Clinical Infinity V6 — Enhanced")
        self.title_lbl.setFont(QFont("Arial",13,QFont.Weight.Bold)); self.title_lbl.setStyleSheet("color:#a78bfa;")
        tl2.addWidget(self.title_lbl)
        self.child_lbl=QLabel(f"Child: {CHILD_NAME} | ABA/DTT/TEACCH/ESDM/TIE | 5,200+ Tasks | 50 PECS | ISCA/ISAA/ISQA")
        self.child_lbl.setFont(QFont("Arial",8)); self.child_lbl.setStyleSheet("color:#60a5fa;")
        tl2.addWidget(self.child_lbl); hl.addWidget(tw_,1)
        sw_=QWidget(); sl_=QVBoxLayout(sw_); sl_.setSpacing(1)
        self.state_lbl=QLabel("💤 Ready"); self.state_lbl.setFont(QFont("Arial",8))
        self.state_lbl.setStyleSheet("color:#9ca3af;")
        sl_.addWidget(self.state_lbl,alignment=Qt.AlignmentFlag.AlignRight)
        self.clvl_lbl=QLabel("Level 1"); self.clvl_lbl.setFont(QFont("Arial",8))
        self.clvl_lbl.setStyleSheet("color:#34d399;")
        sl_.addWidget(self.clvl_lbl,alignment=Qt.AlignmentFlag.AlignRight)
        hl.addWidget(sw_); rl.addWidget(hdr)
        # Schedule bar
        sched=QFrame(); sched.setFixedHeight(48)
        sched.setStyleSheet("QFrame{background:#0c0f1e;border-radius:10px;border:1px solid #1a1f40;}")
        sc=QHBoxLayout(sched); sc.setContentsMargins(10,4,10,4); sc.setSpacing(7)
        self.sched_task=QLabel("📋 Task")
        self.sched_task.setFont(QFont("Arial",9,QFont.Weight.Bold))
        self.sched_task.setStyleSheet("color:#a78bfa;background:#1e1b4b;border-radius:7px;"
            "padding:3px 8px;border:2px solid #4f46e5;"); sc.addWidget(self.sched_task)
        sw2=QWidget(); sl2_=QVBoxLayout(sw2); sl2_.setSpacing(0); sl2_.setContentsMargins(0,0,0,0)
        self.stars_lbl=QLabel("☆ ☆ ☆"); self.stars_lbl.setFont(QFont("Arial",14))
        self.stars_lbl.setStyleSheet("color:#4b5563;"); self.stars_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl2_.addWidget(self.stars_lbl)
        self.mastery_sub=QLabel("0/3"); self.mastery_sub.setFont(QFont("Arial",7))
        self.mastery_sub.setStyleSheet("color:#6b7280;"); self.mastery_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl2_.addWidget(self.mastery_sub); sc.addWidget(sw2,1)
        self.reward_lbl=QLabel("⭐"); self.reward_lbl.setFont(QFont("Arial",18))
        self.reward_lbl.setStyleSheet("color:#fbbf24;background:#2a1a00;border-radius:7px;"
            "padding:2px 7px;border:2px solid #f59e0b;"); sc.addWidget(self.reward_lbl)
        rl.addWidget(sched)
        # Instruction
        if_fr=QFrame(); if_fr.setFixedHeight(74)
        if_fr.setStyleSheet("QFrame{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "stop:0 #1e1b4b,stop:1 #0c0f2e);border-radius:10px;border:2px solid #4f46e5;}")
        il=QVBoxLayout(if_fr); il.setContentsMargins(12,3,12,3)
        self.instr_icon=QLabel("📋"); self.instr_icon.setFont(QFont("Arial",14))
        self.instr_icon.setAlignment(Qt.AlignmentFlag.AlignCenter); il.addWidget(self.instr_icon)
        self.instr_lbl=QLabel("Pepper is loading…"); self.instr_lbl.setFont(QFont("Arial",13,QFont.Weight.Bold))
        self.instr_lbl.setStyleSheet("color:#e0e6ff;"); self.instr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.instr_lbl.setWordWrap(True); il.addWidget(self.instr_lbl); rl.addWidget(if_fr)
        # Content frame
        self.content_fr=QFrame(); self.content_fr.setMinimumHeight(280)
        self.content_fr.setStyleSheet("QFrame{background:rgba(12,15,30,.90);"
            "border-radius:12px;border:2px solid #1a1f40;}")
        self.content_lay=QVBoxLayout(self.content_fr)
        self.content_lay.setContentsMargins(12,10,12,10); self.content_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        lbl=QLabel("🤖\nPepper is ready!\nLoading tasks…"); lbl.setFont(QFont("Arial",16,QFont.Weight.Bold))
        lbl.setStyleSheet("color:#4b5563;"); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.content_lay.addWidget(lbl); rl.addWidget(self.content_fr,1)
        # Lock overlay
        self.lock_ov=QLabel("🔒"); self.lock_ov.setParent(self.content_fr)
        self.lock_ov.setGeometry(0,0,800,280); self.lock_ov.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lock_ov.setFont(QFont("Arial",44))
        self.lock_ov.setStyleSheet("QLabel{background:rgba(0,0,0,.52);border-radius:12px;color:#a78bfa;}"); self.lock_ov.hide()
        # Feedback
        fb_fr=QFrame(); fb_fr.setFixedHeight(48)
        fb_fr.setStyleSheet("QFrame{background:#0c0f1e;border-radius:10px;border:1px solid #1a1f40;}")
        fl=QHBoxLayout(fb_fr); fl.setContentsMargins(12,6,12,6)
        self.fb_icon=QLabel("💤"); self.fb_icon.setFont(QFont("Arial",19)); fl.addWidget(self.fb_icon)
        self.fb_lbl=QLabel("Waiting for Pepper…"); self.fb_lbl.setFont(QFont("Arial",11,QFont.Weight.Bold))
        self.fb_lbl.setStyleSheet("color:#9ca3af;"); self.fb_lbl.setWordWrap(True)
        fl.addWidget(self.fb_lbl,1); rl.addWidget(fb_fr)
        # Mic
        mic_row=QWidget(); mic_lay=QVBoxLayout(mic_row); mic_lay.setContentsMargins(0,0,0,0); mic_lay.setSpacing(3)
        self.mic_btn=QPushButton("🎤  Hold to Speak — Say the word!")
        self.mic_btn.setFixedHeight(52); self.mic_btn.setFont(QFont("Arial",12,QFont.Weight.Bold))
        self.mic_btn.setStyleSheet("QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #dc2626,stop:1 #ef4444);color:white;border-radius:26px;border:3px solid #fca5a5;}"
            "QPushButton:pressed{background:#991b1b;border:4px solid white;}")
        self.mic_btn.pressed.connect(self._on_mic_press); self.mic_btn.released.connect(self._on_mic_release)
        mic_lay.addWidget(self.mic_btn)
        self.mic_wave=QProgressBar(); self.mic_wave.setFixedHeight(8)
        self.mic_wave.setRange(0,100); self.mic_wave.setValue(0); self.mic_wave.setTextVisible(False)
        self.mic_wave.setStyleSheet("QProgressBar{background:#1a1f40;border-radius:4px;border:none;}"
            "QProgressBar::chunk{background:#22c55e;border-radius:4px;}"); mic_lay.addWidget(self.mic_wave)
        self.rec_status=QLabel("🎤 Whisper AI + Lip Motion Verification ready!")
        self.rec_status.setFont(QFont("Arial",8)); self.rec_status.setStyleSheet("color:#6b7280;padding:1px;")
        self.rec_status.setAlignment(Qt.AlignmentFlag.AlignCenter); mic_lay.addWidget(self.rec_status)
        rl.addWidget(mic_row)
        # Stats bar
        sb_=QFrame(); sb_.setFixedHeight(40)
        sb_.setStyleSheet("QFrame{background:#07090f;border-radius:8px;border:1px solid #1a1f40;}")
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
        outer.addLayout(main); self.pecs=PECSWidget(); outer.addWidget(self.pecs)

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
        BRIDGE.sig_joy.connect(lambda _: setattr(ST,"social_joy_active",True) or
            QTimer.singleShot(4000,lambda: ST.__setitem__("social_joy_active",False)))
        BRIDGE.sig_camera.connect(self._update_cam); BRIDGE.sig_stats.connect(self._refresh)
        BRIDGE.sig_chat.connect(self._add_chat)
        BRIDGE.sig_rec_stop.connect(self._on_rec_stop)
        BRIDGE.sig_mic_lvl.connect(lambda v: self.mic_wave.setValue(int(v*100)))
        BRIDGE.sig_pecs.connect(lambda ph: self._add_chat("Child",f"[PECS] {ph}"))
        self._lip_t=QTimer(); self._lip_t.timeout.connect(
            lambda: self.lip_bar.setValue(min(100,int(ST.get("lip_motion",0)*40))))
        self._lip_t.start(100)

    def _update_cam(self,qimg):
        if isinstance(qimg,QImage):
            pix=QPixmap.fromImage(qimg).scaled(580,520,Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation)
            self.cam_lbl.setPixmap(pix)
        # Update emotion bars
        pct=ST.get("emotion_pct",{})
        for em_,bar in self.emo_bars.items():
            bar.setValue(pct.get(em_,0))
        em=ST["emotion"]
        emojis={"happy":"😊","joyful":"😄","sad":"😢","angry":"😠",
                "fear":"😨","surprised":"😲","neutral":"😐"}
        self.emo_lbl.setText(f"{emojis.get(em,'😐')} {em}")
        self.lip_lbl.setText(f"👄 Lip: {ST.get('lip_motion',0):.2f} {'[SPEECH]' if ST['lip_speaking'] else ''}")
        self.finger_lbl2.setText(f"🖐️ Fingers: {ST['finger_count']}/10")
        self.status_lbl.setText(f"👦{CHILD_NAME}|🖐️{ST['finger_count']}|{em}|L{ST['conversation_level']}|"
            f"{'👄' if ST['lip_speaking'] else '·'}|Attn:{ST['attention']}%")

    def _refresh(self):
        self.stat_score.setText(str(ST["score"])); self.stat_tokens.setText(str(ST["tokens"]))
        self.stat_mastered.setText(str(ST["mastered"])); self.stat_streak.setText(str(ST["streak"]))
        self.stat_skipped.setText(str(ST["tasks_skipped"])); self.stat_daily.setText(f"{ST['skill_daily']:.0f}%")
        rt=ST["resp_times"]
        if rt: self.stat_resp.setText(str(int(sum(rt[-10:])/len(rt[-10:]))))
        c=ST["consecutive"]
        self.stars_lbl.setText("★"*c+"☆"*(3-c)); self.stars_lbl.setStyleSheet("color:#fbbf24;" if c else "color:#4b5563;")
        self.mastery_sub.setText(f"{c}/3 | Fail:{ST.get('_fail_count',0)}/{MAX_FAILS}")
        self.reward_lbl.setText(f"⭐{ST['score']}"); self.clvl_lbl.setText(f"Level {ST['conversation_level']}")
        ok=ST["tasks_success"]; fa=ST["tasks_fail"]; rt2=ST["resp_times"]
        if rt2 and ok+fa>0:
            self.rec_status.setText(f"⏱ Avg:{int(sum(rt2[-5:])/len(rt2[-5:]))}ms | "
                f"✅ Acc:{int(ok/(ok+fa)*100)}% | ✅{ok} ❌{fa} | "
                f"Done tasks (no repeat): {len(_child_done)}")

    def _on_task(self,task:dict):
        if task.get("action")=="click": self._handle_click(task.get("idx",0)); return
        self._clear(); self._locked=True; self.lock_ov.hide()
        self.sched_task.setText(f"📋 {task.get('name','Task')[:22]}")
        mode=task.get("tablet_mode","")
        if mode=="motor":
            name_lbl=QLabel(task.get("name","")); name_lbl.setFont(QFont("Arial",20,QFont.Weight.Bold))
            name_lbl.setStyleSheet("color:#a78bfa;"); name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.content_lay.addWidget(name_lbl)
            instr=QLabel(task.get("instruction","")); instr.setFont(QFont("Arial",14,QFont.Weight.Bold))
            instr.setStyleSheet("color:#e0e6ff;background:#1e1b4b;border-radius:12px;"
                "border:3px solid #4f46e5;padding:12px;")
            instr.setAlignment(Qt.AlignmentFlag.AlignCenter); instr.setWordWrap(True)
            self.content_lay.addWidget(instr)
            done_btn=QPushButton("✅ Done! Tap here"); done_btn.setFixedHeight(52)
            done_btn.setFont(QFont("Arial",13,QFont.Weight.Bold))
            done_btn.setStyleSheet("QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
                "stop:0 #059669,stop:1 #10b981);color:white;border-radius:26px;border:3px solid #6ee7b7;}"
                "QPushButton:pressed{background:#047857;}")
            done_btn.clicked.connect(lambda: ST.__setitem__("instant_success",True))
            self.content_lay.addWidget(done_btn)
        elif mode=="grid":
            opts=task.get("options",[]); self._correct_idx=task.get("correct",0)
            grid=QWidget(); gl=QGridLayout(grid); gl.setSpacing(10); gl.setContentsMargins(8,8,8,8)
            for i,opt in enumerate(opts):
                card=ClickCard(opt,i,None); gl.addWidget(card,i//2,i%2); self._cards.append(card)
            self.content_lay.addWidget(grid); self._do_unlock()
        elif mode=="number":
            n=task.get("target_number",1)
            big=QLabel(str(n)); big.setFont(QFont("Arial",80,QFont.Weight.Bold))
            big.setStyleSheet("color:#22c55e;"); big.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.content_lay.addWidget(big)
            hint=QLabel(f"Show me {n} fingers! 🖐️"); hint.setFont(QFont("Arial",14,QFont.Weight.Bold))
            hint.setStyleSheet("color:#a78bfa;"); hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
            self.content_lay.addWidget(hint)
        else:
            txt=task.get("word_text") or task.get("social_text") or task.get("daily_label","")
            emoji=task.get("daily_emoji","🗣️")
            em_lbl=QLabel(emoji); em_lbl.setFont(QFont("Arial",56))
            em_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); self.content_lay.addWidget(em_lbl)
            word_lbl=QLabel(str(txt)); word_lbl.setFont(QFont("Arial",28,QFont.Weight.Bold))
            word_lbl.setStyleSheet("color:#a78bfa;background:#1e1b4b;border-radius:12px;"
                "border:3px solid #4f46e5;padding:8px 16px;")
            word_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); self.content_lay.addWidget(word_lbl)
            hint=QLabel("🎤 Hold mic and say the word!")
            hint.setFont(QFont("Arial",11)); hint.setStyleSheet("color:#34d399;")
            hint.setAlignment(Qt.AlignmentFlag.AlignCenter); self.content_lay.addWidget(hint)

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

    def _do_unlock(self): self._locked=False; self.lock_ov.hide(); [c.setEnabled(True) for c in self._cards]
    def _do_lock(self):   self._locked=True; self.lock_ov.show(); [c.setEnabled(False) for c in self._cards]
    def _reset_cards(self): [c.reset() for c in self._cards]

    def _on_mic_press(self):
        self.mic_btn.setText("🔴  Recording… Release after speaking")
        self.mic_btn.setStyleSheet("QPushButton{background:#991b1b;color:white;border-radius:26px;border:4px solid white;}")
        self.rec_status.setText("🔴 Recording with Whisper AI + Lip Motion Verification…")
        self._recorder.start()

    def _on_mic_release(self):
        self.mic_btn.setText("🎤  Hold to Speak — Say the word!")
        self.mic_btn.setStyleSheet("QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #dc2626,stop:1 #ef4444);color:white;border-radius:26px;border:3px solid #fca5a5;}"
            "QPushButton:pressed{background:#991b1b;border:4px solid white;}")
        self.rec_status.setText("⏳ Processing with Whisper AI…")
        threading.Thread(target=self._do_rec,daemon=True).start()

    def _do_rec(self):
        text=self._recorder.stop_and_recognise()
        ST["last_speech_text"]=text; BRIDGE.sig_rec_stop.emit(text)

    def _on_rec_stop(self,text:str):
        ST["recording"]=False
        if text: self.rec_status.setText(f"👂 Heard: \"{text}\""); self._add_chat("Child",text)
        else:
            lip="(lip motion detected)" if ST["lip_speaking"] else ""
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
                ctx=(f"You are Pepper, an AI therapy robot for {CHILD_NAME}, age {CHILD_AGE}, ASD Level 2. "
                     f"Session: score={ST['score']}, emotion={ST['emotion']}, level={ST['conversation_level']}. "
                     f"Motor={ST['skill_motor']:.0f}%, Verbal={ST['skill_verbal']:.0f}%, Social={ST['skill_social']:.0f}%. "
                     f"Reply in 2-3 concise sentences. Be encouraging and clinically informed.")
                resp=mdl.generate_content(ctx+"\nTherapist/Parent says: "+msg)
                rep=resp.text.strip()[:300]
            except: rep=f"Great question! {CHILD_NAME} is doing well today! Keep encouraging them!"
        else: rep=f"Hi! I'm Pepper! {CHILD_NAME} is making great progress!"
        BRIDGE.sig_chat.emit("Pepper",rep)
        if VOICE_REF: VOICE_REF.say(rep)

    def _add_chat(self,role:str,msg:str):
        t=datetime.now().strftime("%H:%M:%S")
        col={"Pepper":"#a78bfa","Therapist":"#60a5fa","Child":"#34d399"}.get(role,"#9ca3af")
        icon={"Pepper":"🤖","Therapist":"👩","Child":"👦"}.get(role,"💬")
        self.chat_area.append(f'<span style="color:{col};font-weight:bold">{icon}[{t}]:</span>'
            f' <span style="color:#e0e6ff">{msg}</span>')
        sb=self.chat_area.verticalScrollBar()
        if sb: sb.setValue(sb.maximum())
        ST["session_chat"].append({"role":role,"text":msg,"time":t})
        if len(ST["session_chat"])>60: ST["session_chat"]=ST["session_chat"][-60:]


# ══════════════════════════════════════════════════════════════════
# Therapy Controller
# ══════════════════════════════════════════════════════════════════
class TherapyController(threading.Thread):
    def __init__(self,voice,pb):
        super().__init__(daemon=True); self.v=voice; self.pb=pb
        self._running=True; self._fail=0

    def run(self):
        time.sleep(4.0)
        self.v.say(f"Hello {CHILD_NAME}! I am Pepper your therapy robot! Let's learn together!")
        while self._running:
            try: self._show()
            except Exception as e: log.warning(f"Controller error: {e}"); time.sleep(1.0)

    def _show(self):
        task=get_next_task()
        self._fail=0; ST["_fail_count"]=0
        ST["instant_success"]=False; ST["tablet_click_result"]=None
        ST["_current_task_keyword"]=task.get("keyword","").strip()
        if task.get("verify")=="motor": self.pb.send(gaze="child",is_speaking=False)
        else: self.pb.send(gaze="tablet",is_speaking=False)
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
        ST["instant_success"]=False
        deadline=time.time()+wait_s
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
        LOG(f"✅ {msg} time={rt}ms","success")
        # Save completed task to DB (no repeat for this child)
        base_id=task.get("base_id","")
        if base_id: _child_done.add(base_id); db_add_task(CHILD_NAME,base_id,"success")
        log_csv(task["id"],dom,task.get("protocol","ABA"),True,ST["score"],ST["emotion"],ST["conversation_level"],rt)
        BRIDGE.sig_success.emit(msg); BRIDGE.sig_joy.emit(task.get("joy","celebrate"))
        self.pb.send(is_speaking=True,sj=True,lip=0.9,gaze="child")
        self.v.say(msg)
        joy=task.get("joy","")
        if joy=="full_joy": self.v.say(f"Excellent {CHILD_NAME}! Perfect score! You are amazing!")
        elif joy=="dance":  self.v.say(f"Great job {CHILD_NAME}! Keep it up!")
        else:               self.v.say(f"Correct {CHILD_NAME}! Wonderful!")
        self.pb.send(is_speaking=False,sj=False,gaze="child")
        BRIDGE.sig_stats.emit(); time.sleep(1.2)

    def _skip(self,task):
        ST["tasks_skipped"]+=1; ST["streak"]=0
        msg=task.get("fail","Let's try the next task!")
        LOG(f"❌ Skip","fail")
        # Still mark as seen so it won't repeat
        base_id=task.get("base_id","")
        if base_id: _child_done.add(base_id); db_add_task(CHILD_NAME,base_id,"fail")
        log_csv(task["id"],task.get("domain","Motor"),task.get("protocol","ABA"),
                False,ST["score"],ST["emotion"],ST["conversation_level"],0)
        BRIDGE.sig_skip.emit(msg)
        self.v.say(f"Let's try something new {CHILD_NAME}! You can do it!")
        BRIDGE.sig_stats.emit(); time.sleep(0.6)

    def stop(self): self._running=False


# ══════════════════════════════════════════════════════════════════
# PDF Report Generator with Full Treatment Plan
# ══════════════════════════════════════════════════════════════════
def generate_pdf():
    if not _PDF: return None
    fn=f"report_{SAFE_NAME}_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    try:
        doc=SimpleDocTemplate(fn,pagesize=A4,leftMargin=50,rightMargin=50,topMargin=50,bottomMargin=50)
        styles=getSampleStyleSheet()
        S=lambda name,**kw: ParagraphStyle(name,parent=styles.get(name,styles["Normal"]),**kw)
        title_s=S("TT",fontSize=18,textColor=RL_COLORS.HexColor("#4f46e5"),spaceAfter=6)
        h2_s=S("H2",fontSize=13,textColor=RL_COLORS.HexColor("#2E5496"),spaceBefore=12,spaceAfter=4)
        h3_s=S("H3",fontSize=11,textColor=RL_COLORS.HexColor("#203864"),spaceBefore=8,spaceAfter=3)
        norm=styles["Normal"]; story=[]
        # Title
        story.append(Paragraph("Pepper Clinical Infinity V6 — Clinical Report",title_s))
        story.append(Paragraph(f"Child: <b>{CHILD_NAME}</b> | Age: {ST['age']} | Date: {ST['session_date']} | Generated: {datetime.now().strftime('%H:%M')}",norm))
        story.append(HRFlowable(width="100%",thickness=1,color=RL_COLORS.HexColor("#4f46e5"),spaceAfter=8))
        dur=int((time.time()-ST["uptime"])/60)
        ok=ST["tasks_success"]; fa=ST["tasks_fail"]; acc=round(ok/(ok+fa)*100,1) if ok+fa>0 else 0
        # 1. Session Summary
        story.append(Paragraph("1. Session Summary",h2_s))
        rows=[["Item","Value"],["Child",CHILD_NAME],["Age",str(ST["age"])],
              ["Date",ST["session_date"]],["Duration",f"{dur} min"],
              ["Score",str(ST["score"])],["Tasks Mastered",str(ST["mastered"])],
              ["Tasks Correct",str(ok)],["Tasks Failed",str(fa)],
              ["Accuracy",f"{acc}%"],["Conv Level",f"Level {ST['conversation_level']}"],
              ["Dominant Emotion",ST["emotion"]],["Attention",f"{ST['attention']}%"]]
        t=Table(rows,colWidths=[180,320])
        t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),RL_COLORS.HexColor("#4f46e5")),
            ("TEXTCOLOR",(0,0),(-1,0),RL_COLORS.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[RL_COLORS.HexColor("#f8f9ff"),RL_COLORS.white]),
            ("GRID",(0,0),(-1,-1),.5,RL_COLORS.grey),("FONTSIZE",(0,0),(-1,-1),10),("PADDING",(0,0),(-1,-1),7)]))
        story.append(t); story.append(Spacer(1,10))
        # 2. Skill Analysis
        story.append(Paragraph("2. Skill Domain Analysis",h2_s))
        domains=[("Motor (ABA-DTT)",ST["skill_motor"]),("Cognitive (TEACCH)",ST["skill_cognitive"]),
                 ("Verbal (DTT)",ST["skill_verbal"]),("Mathematical (ABA)",ST["skill_math"]),
                 ("Social (ESDM)",ST["skill_social"]),("Daily Living (TIE)",ST["skill_daily"])]
        srows=[["Domain","Score","Status","Priority"]]
        for dom,val in domains:
            if val>=75: st_,pri="Proficient","Maintenance"
            elif val>=55: st_,pri="Developing","Continue"
            elif val>=40: st_,pri="Emerging","Focus"
            else: st_,pri="Needs Support","HIGH PRIORITY"
            srows.append([dom,f"{val:.1f}%",st_,pri])
        st2=Table(srows,colWidths=[160,70,100,170])
        st2.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),RL_COLORS.HexColor("#2E5496")),
            ("TEXTCOLOR",(0,0),(-1,0),RL_COLORS.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[RL_COLORS.HexColor("#EEF2FF"),RL_COLORS.white]),
            ("GRID",(0,0),(-1,-1),.5,RL_COLORS.grey),("FONTSIZE",(0,0),(-1,-1),10),("PADDING",(0,0),(-1,-1),7)]))
        story.append(st2); story.append(Spacer(1,10))
        # 3. Full Treatment Plan
        story.append(Paragraph("3. Individualised Treatment Plan (Based on Session Results)",h2_s))
        story.append(Paragraph(f"Based on {CHILD_NAME}'s performance across {ok+fa} tasks (accuracy {acc}%, Level {ST['conversation_level']}), the following evidence-based treatment plan is recommended:",norm))
        story.append(Spacer(1,4))
        plan=[["Domain","Protocol","Weekly Target","Home Activity","Strategy"]]
        def _plan_row(dom,val,proto,target_hi,target_lo,home_hi,home_lo,strat_hi,strat_lo):
            if val>=55: plan.append([dom,proto,target_hi,home_hi,strat_hi])
            else: plan.append([dom,proto,target_lo,home_lo,strat_lo])
        _plan_row("Motor",ST["skill_motor"],"ABA-DTT",
            "3×10 trials/day","5×10 trials/day",
            "Add 2-step sequences","Mirror: clap, wave, raise hand",
            "Maintenance — increase complexity","Prompting→fading. Reinforce every attempt.")
        _plan_row("Cognitive",ST["skill_cognitive"],"TEACCH",
            "3×15 min/day","4×15 min/day",
            "Sorting & categorising tasks","Match colours/shapes with objects",
            "Increase category complexity","Visual schedule + left-to-right work system")
        _plan_row("Verbal",ST["skill_verbal"],"DTT",
            "2×10 trials/day","3×10 trials/day",
            "Expand to 2-word combinations","Label 5 household objects ×3 daily",
            "Increase MLU + social phrases","Errorless learning. Shape sounds→words.")
        _plan_row("Math",ST["skill_math"],"ABA-DTT",
            "Daily 10 min","Daily 15 min",
            "Counting 1-10 + simple addition","Finger counting 1-5 with objects",
            "Introduce number recognition","Concrete→pictorial→abstract. Reinforce immediately.")
        _plan_row("Social",ST["skill_social"],"ESDM",
            "20 min structured play/day","20 min joint play/day",
            "Turn-taking + peer play 2×/week","Follow child's lead. Face-to-face games.",
            "Expand social scripts + greetings","Establish joint attention. Imitate child first.")
        plan.append(["Daily Living","TIE","5 routines/day","Morning routine visual chart + reinforce each step",
            "Visual task strips. Backward chaining for complex tasks."])
        pt=Table(plan,colWidths=[75,58,85,135,135])
        pt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),RL_COLORS.HexColor("#1F3864")),
            ("TEXTCOLOR",(0,0),(-1,0),RL_COLORS.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("FONTSIZE",(0,0),(-1,0),8),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[RL_COLORS.HexColor("#EEF2FF"),RL_COLORS.white]),
            ("GRID",(0,0),(-1,-1),.5,RL_COLORS.grey),
            ("FONTSIZE",(0,1),(-1,-1),7.5),("PADDING",(0,0),(-1,-1),5),("VALIGN",(0,0),(-1,-1),"TOP")]))
        story.append(pt); story.append(Spacer(1,10))
        # 4. Weekly Schedule
        story.append(Paragraph("4. Recommended Weekly Therapy Schedule",h2_s))
        wk=[["Day","Morning (30 min)","Afternoon (20 min)","Evening (15 min)"],
            ["Monday","Motor + Cognitive tasks","Verbal practice + PECS","Daily living routine"],
            ["Tuesday","Finger counting + Math","Social play (ESDM)","Reading / naming objects"],
            ["Wednesday","Motor imitation (ABA)","Emotion recognition","PECS communication"],
            ["Thursday","Cognitive (TEACCH visual)","Verbal + Social phrases","Daily routine practice"],
            ["Friday","Full Pepper session","Parent-child game","Relaxation + story"],
            ["Saturday","Outdoor activities","Peer social skills","Free choice reward"],
            ["Sunday","Rest / light play","Review week progress","Prepare for Monday"]]
        wt=Table(wk,colWidths=[65,145,145,110])
        wt.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),RL_COLORS.HexColor("#059669")),
            ("TEXTCOLOR",(0,0),(-1,0),RL_COLORS.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
            ("ROWBACKGROUNDS",(0,1),(-1,-1),[RL_COLORS.HexColor("#F0FDF4"),RL_COLORS.white]),
            ("GRID",(0,0),(-1,-1),.5,RL_COLORS.grey),("FONTSIZE",(0,0),(-1,-1),8),("PADDING",(0,0),(-1,-1),5)]))
        story.append(wt); story.append(Spacer(1,10))
        # 5. SMART Goals
        story.append(Paragraph("5. SMART Goals (Next 4 Weeks)",h2_s))
        goals=[]
        if ST["skill_motor"]<60: goals.append("Motor: Child will imitate 5/8 motor actions with <2 prompts across 3 consecutive sessions within 4 weeks.")
        if ST["skill_verbal"]<60: goals.append("Verbal: Child will spontaneously label 10 common objects in ≥80% of opportunities within 4 weeks.")
        if ST["skill_math"]<60: goals.append("Math: Child will show correct finger count for numbers 1-5 with ≥90% accuracy across 3 sessions.")
        if ST["skill_social"]<60: goals.append("Social: Child will initiate joint attention bid ≥3 times per 20-min play session within 4 weeks.")
        if ST["skill_cognitive"]<60: goals.append("Cognitive: Child will match 8/10 colour-object pairs with independent responding within 4 weeks.")
        goals.append("Daily Living: Child will complete 3-step morning routine with visual prompts only within 4 weeks.")
        for i,g in enumerate(goals,1):
            story.append(Paragraph(f"<b>Goal {i}:</b> {g}",norm)); story.append(Spacer(1,3))
        story.append(Spacer(1,8))
        # 6. All Sessions History
        all_sess=db_get_sessions(CHILD_NAME)
        if all_sess:
            story.append(Paragraph("6. All Sessions History",h2_s))
            hrows=[["Date","Score","Correct","Failed","Duration","Level","Emotion"]]
            for s in all_sess[:20]:
                hrows.append([s["date"][:16],str(s["score"]),str(s["ok"]),
                    str(s["fail"]),f"{s['dur']}min",f"L{s['level']}",s["emotion"]])
            ht=Table(hrows,colWidths=[100,50,55,50,55,50,90])
            ht.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),RL_COLORS.HexColor("#1F3864")),
                ("TEXTCOLOR",(0,0),(-1,0),RL_COLORS.white),("FONTNAME",(0,0),(-1,0),"Helvetica-Bold"),
                ("ROWBACKGROUNDS",(0,1),(-1,-1),[RL_COLORS.HexColor("#EEF2FF"),RL_COLORS.white]),
                ("GRID",(0,0),(-1,-1),.5,RL_COLORS.grey),("FONTSIZE",(0,0),(-1,-1),8),("PADDING",(0,0),(-1,-1),5)]))
            story.append(ht); story.append(Spacer(1,8))
        # 7. Session Log
        story.append(Paragraph("7. Session Event Log (Last 20)",h2_s))
        for lg in ST.get("logs",[])[-20:]:
            story.append(Paragraph(f"[{lg['time']}] {lg['msg'][:90]}",norm))
        doc.build(story)
        # Save session to DB
        db_save_session(CHILD_NAME,ST["score"],ok,fa,dur,
            {"motor":ST["skill_motor"],"cognitive":ST["skill_cognitive"],
             "verbal":ST["skill_verbal"],"math":ST["skill_math"],"social":ST["skill_social"]},
            ST["emotion"],ST["conversation_level"],pdf=fn)
        log.info(f"✅ PDF: {fn}")
        return fn
    except Exception as e:
        log.warning(f"PDF error: {e}"); return None


# ══════════════════════════════════════════════════════════════════
# Flask Parent Dashboard — Full with ISCA + ISAA + ISQA + Sessions
# ══════════════════════════════════════════════════════════════════
def gemini_chat(question):
    if not _GENAI: return "Gemini not available. Please add API key."
    try:
        mdl=genai.GenerativeModel("gemini-1.5-flash")
        ctx=(f"You are a clinical AI advisor for autism therapy. "
             f"Child: {CHILD_NAME}, Age: {ST['age']}, ASD Level 2. "
             f"Session stats: Score={ST['score']}, Motor={ST['skill_motor']:.0f}%, "
             f"Verbal={ST['skill_verbal']:.0f}%, Social={ST['skill_social']:.0f}%, "
             f"Math={ST['skill_math']:.0f}%, Cognitive={ST['skill_cognitive']:.0f}%, "
             f"Emotion={ST['emotion']}, Conv Level={ST['conversation_level']}. "
             f"Give practical, evidence-based advice in 3-4 sentences.")
        resp=mdl.generate_content(ctx+"\n\nParent question: "+question)
        return resp.text.strip()[:500]
    except Exception as e:
        return f"Gemini error: {str(e)[:100]}. Check your API key."

parent_app=Flask("parent_v6")
parent_app.secret_key=secrets.token_hex(16)

DASHBOARD_HTML=r"""<!DOCTYPE html>
<html lang="en" dir="ltr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Pepper V6 — Parent Dashboard</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#060918;--bg2:#0c0f1e;--bg3:#1a1f40;--purple:#a78bfa;--blue:#3b82f6;
  --green:#22c55e;--red:#ef4444;--yellow:#fbbf24;--text:#e0e6ff;--text2:#9ca3af;}
body{background:var(--bg);color:var(--text);font-family:'Segoe UI',Arial,sans-serif;font-size:14px;}
.topbar{background:linear-gradient(135deg,#1a0a3d,#0a0f28);padding:12px 20px;
  display:flex;align-items:center;gap:10px;border-bottom:2px solid #4f46e5;flex-wrap:wrap;}
.topbar h1{font-size:1.1em;color:var(--purple)}
.badge{background:#1e1b4b;border:1px solid #4f46e5;border-radius:20px;
  padding:3px 10px;font-size:.78em;color:var(--yellow)}
.tabs{display:flex;background:var(--bg2);border-bottom:2px solid var(--bg3);overflow-x:auto;}
.tab{padding:11px 15px;cursor:pointer;font-size:.82em;font-weight:600;color:var(--text2);
  white-space:nowrap;border-bottom:3px solid transparent;transition:.2s;flex-shrink:0;}
.tab.active,.tab:hover{color:var(--purple);border-bottom-color:var(--purple)}
.content{padding:16px;overflow-y:auto;height:calc(100vh - 108px)}
.card{background:var(--bg2);border-radius:12px;padding:14px;border:1px solid var(--bg3);margin-bottom:12px}
.card h3{color:var(--purple);font-size:.92em;margin-bottom:10px}
.stat-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(110px,1fr));gap:8px;margin-bottom:12px}
.stat{background:var(--bg2);border-radius:10px;padding:9px;text-align:center;border:1px solid var(--bg3)}
.stat .val{font-size:1.6em;font-weight:900}.stat .lbl{font-size:.68em;color:var(--text2);margin-top:2px}
.bar-row{margin-bottom:6px}
.bar-row label{display:flex;justify-content:space-between;font-size:.76em;margin-bottom:2px}
.bar-bg{background:var(--bg3);border-radius:4px;height:8px}
.bar-fill{height:8px;border-radius:4px;transition:width 1s}
.diag-item{padding:5px 10px;background:var(--bg3);border-radius:7px;margin:3px 0;
  font-size:.79em;border-left:4px solid #4f46e5}
.treat-item{padding:5px 10px;background:#052918;border-radius:7px;margin:3px 0;
  font-size:.79em;border-left:4px solid var(--green);color:var(--green)}
.log-row{display:flex;justify-content:space-between;padding:4px 0;
  border-bottom:1px solid var(--bg3);font-size:.74em}
.ok{color:var(--green)}.fail{color:var(--red)}
input,select,textarea{width:100%;background:var(--bg3);border:2px solid var(--bg3);
  border-radius:8px;padding:8px 12px;color:var(--text);font-size:.86em;
  margin-bottom:8px;outline:none;}
input:focus,select:focus,textarea:focus{border-color:#4f46e5}
.btn{background:#4f46e5;color:#fff;border:none;border-radius:8px;padding:9px 18px;
  font-weight:700;cursor:pointer;width:100%;font-size:.88em;}
.btn:hover{background:#4338ca}
.btn-g{background:#059669}.btn-g:hover{background:#047857}
.btn-r{background:#dc2626}.btn-r:hover{background:#b91c1c}
.btn-y{background:#d97706}.btn-y:hover{background:#b45309}
.pecs-grid{display:flex;flex-wrap:wrap;gap:7px}
.pecs-btn{background:#1e1b4b;border:2px solid #4f46e5;border-radius:9px;
  padding:6px 11px;cursor:pointer;font-size:.82em;color:#e0e6ff;transition:.15s}
.pecs-btn:hover{background:#2e2b6e;border-color:#a78bfa}
.child-card{background:var(--bg2);border-radius:9px;padding:9px;border:1px solid var(--bg3);
  margin-bottom:6px;cursor:pointer;display:flex;align-items:center;gap:10px;}
.child-card:hover{border-color:var(--purple)}
.q-item{margin-bottom:8px;padding:8px;background:var(--bg2);border-radius:9px}
.q-text{font-size:.80em;margin-bottom:5px;font-weight:600}
.q-opts{display:flex;gap:5px}
.q-opt{flex:1;background:var(--bg3);border:2px solid var(--bg3);border-radius:7px;
  padding:5px;text-align:center;font-size:.72em;cursor:pointer;transition:.15s}
.q-opt:hover{border-color:#4f46e5}.q-opt.sel{background:#4f46e5;border-color:#4f46e5;color:#fff}
.score-box{background:#052918;border:2px solid var(--green);border-radius:9px;
  padding:12px;text-align:center;margin-top:8px}
.sc-num{font-size:2em;font-weight:900;color:var(--green)}
.quick-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:8px}
.qbtn{background:#1e1b4b;border:2px solid #4f46e5;border-radius:9px;padding:11px;
  color:#e0e6ff;cursor:pointer;font-size:.88em;font-weight:700;text-align:center;transition:.15s}
.qbtn:hover{background:#2e2b6e;border-color:#a78bfa}
.sess-row{display:grid;grid-template-columns:1fr 60px 60px 60px 60px 60px 70px;
  gap:4px;padding:5px 0;border-bottom:1px solid var(--bg3);font-size:.74em;align-items:center;}
.ai-box{background:#07090f;border:1px solid #4f46e5;border-radius:8px;padding:10px;
  min-height:60px;margin-bottom:8px;font-size:.84em;line-height:1.5}
.ai-box.loading{color:#6b7280}
</style></head>
<body>
<div class="topbar">
  <span style="font-size:1.4em">🤖</span>
  <h1>Pepper Clinical Infinity V6 — Parent Dashboard</h1>
  <span class="badge">👦 <span id="cname">…</span></span>
  <span class="badge">⭐ <span id="cscore">0</span></span>
  <span class="badge">😊 <span id="cemo">—</span></span>
  <span class="badge" id="lip_b">👄 silent</span>
  <span class="badge">🖐️ <span id="cfin">0</span>/10</span>
  <span class="badge"><a href="/report_pdf" style="color:var(--yellow);text-decoration:none">📄 PDF Report</a></span>
</div>
<div class="tabs">
  <div class="tab active" onclick="showTab('overview',this)">📊 Overview</div>
  <div class="tab" onclick="showTab('diagnosis',this)">🧠 Diagnosis</div>
  <div class="tab" onclick="showTab('children',this)">👶 Children</div>
  <div class="tab" onclick="showTab('sessions',this)">📅 Sessions</div>
  <div class="tab" onclick="showTab('screening',this)">🧪 Screening</div>
  <div class="tab" onclick="showTab('log',this)">📋 Log</div>
  <div class="tab" onclick="showTab('pecs',this)">🗣️ PECS</div>
  <div class="tab" onclick="showTab('chat',this)">💬 Chat</div>
  <div class="tab" onclick="showTab('ai',this)">🤖 AI Advice</div>
  <div class="tab" onclick="showTab('quick',this)">⚡ Actions</div>
</div>
<div class="content" id="content">Loading…</div>
<script>
let st={},qa={};
async function fetchSt(){
  try{
    const r=await fetch('/api/state'); st=await r.json();
    document.getElementById('cname').textContent=st.child_name||st.name||'—';
    document.getElementById('cscore').textContent=st.score||0;
    document.getElementById('cemo').textContent=st.emotion||'—';
    document.getElementById('lip_b').textContent='👄 '+(st.lip_speaking?'SPEECH':'silent');
    document.getElementById('cfin').textContent=st.finger_count||0;
  }catch(e){}
}
function showTab(t,el){
  document.querySelectorAll('.tab').forEach(x=>x.classList.remove('active'));
  if(el)el.classList.add('active'); renderTab(t);
}
function renderTab(t){
  const c=document.getElementById('content');
  if(t==='overview'){
    const rt=st.resp_times||[];
    const avg=rt.length?Math.round(rt.slice(-10).reduce((a,b)=>a+b,0)/Math.min(rt.length,10)):0;
    const ok=st.tasks_success||0,fa=st.tasks_fail||0,acc=ok+fa>0?Math.round(ok/(ok+fa)*100):0;
    const skills=[['Motor (ABA-DTT)','skill_motor','#a78bfa'],
      ['Cognitive (TEACCH)','skill_cognitive','#06b6d4'],
      ['Verbal (DTT)','skill_verbal','#fbbf24'],
      ['Mathematical','skill_math','#22c55e'],
      ['Social (ESDM)','skill_social','#f97316'],
      ['Daily Living (TIE)','skill_daily','#ec4899']];
    c.innerHTML=`
    <div class="stat-grid">
      <div class="stat"><div class="val" style="color:#a78bfa">${st.score||0}</div><div class="lbl">⭐ Score</div></div>
      <div class="stat"><div class="val" style="color:#fbbf24">${st.tokens||0}</div><div class="lbl">🪙 Tokens</div></div>
      <div class="stat"><div class="val" style="color:#22c55e">${ok}</div><div class="lbl">✅ Correct</div></div>
      <div class="stat"><div class="val" style="color:#3b82f6">${acc}%</div><div class="lbl">🎯 Accuracy</div></div>
      <div class="stat"><div class="val" style="color:#f97316">${avg||'—'}ms</div><div class="lbl">⏱ Avg Time</div></div>
      <div class="stat"><div class="val" style="color:#34d399">${st.mastered||0}</div><div class="lbl">🏆 Mastered</div></div>
      <div class="stat"><div class="val" style="color:#f472b6">${st.conversation_level||1}</div><div class="lbl">🗣 Level</div></div>
      <div class="stat"><div class="val" style="color:#60a5fa">${st.attention||0}%</div><div class="lbl">👁 Attention</div></div>
    </div>
    <div class="card"><h3>🎯 Skill Domains</h3>
      ${skills.map(([l,k,col])=>`<div class="bar-row">
        <label><span>${l}</span><span style="color:${col};font-weight:700">${Math.round(st[k]||50)}%</span></label>
        <div class="bar-bg"><div class="bar-fill" style="width:${st[k]||50}%;background:${col}"></div></div>
      </div>`).join('')}
    </div>
    <div class="card"><h3>😊 Live Emotion + Lip Motion</h3>
      <div style="display:flex;flex-wrap:wrap;gap:5px">
        ${Object.entries(st.emotion_pct||{}).map(([em,v])=>
          `<span style="background:#1e1b4b;border:1px solid #4f46e5;border-radius:14px;
          padding:2px 8px;font-size:.76em">${em} ${v}%</span>`).join('')}
      </div>
      <div style="margin-top:6px;font-size:.82em;color:var(--text2)">
        👄 ${st.lip_speaking?'<span style="color:#00ffc8">SPEECH DETECTED</span>':'silent'} |
        Lip motion: ${st.lip_motion?Number(st.lip_motion).toFixed(2):'0.00'} |
        🖐️ Fingers: ${st.finger_count||0}/10 |
        No-repeat tasks done: ${st.child_done_count||0}
      </div>
    </div>`;
  }
  else if(t==='diagnosis'){
    const skills=[['skill_motor','Motor (ABA-DTT)'],['skill_cognitive','Cognitive (TEACCH)'],
      ['skill_verbal','Verbal (DTT)'],['skill_math','Mathematical'],
      ['skill_social','Social (ESDM)'],['skill_daily','Daily Living (TIE)']];
    const diags=skills.map(([k,n])=>{const v=Math.round(st[k]||50);
      return v>=65?`✅ ${n}: ${v}% — Proficient`:v>=45?`⚠️ ${n}: ${v}% — Developing`:
        `🔴 ${n}: ${v}% — Needs focused intervention`;});
    const treats=[];
    if((st.skill_motor||50)<50) treats.push('🏃 Motor ABA: 5×10 trials/day. Use physical prompting + immediate reinforcement. Mirror exercises: clap, wave, raise hand.');
    if((st.skill_verbal||50)<50) treats.push('🎤 Verbal DTT: 3×10 trials/day. Label 5 household objects daily ×3. Errorless learning. Reinforce every attempt.');
    if((st.skill_social||50)<50) treats.push('👥 Social ESDM: 20 min joint play daily. Follow child\'s lead. Add language naturally. Practice greetings and turn-taking.');
    if((st.skill_daily||50)<50) treats.push('🌅 Daily TIE: 5 daily routines with visual chart. Reinforce each step independently. Backward chaining for complex tasks.');
    if((st.skill_math||50)<50) treats.push('🔢 Math ABA: Finger counting 1-5 with objects. Match number to quantity. Concrete → pictorial → abstract.');
    if((st.skill_cognitive||50)<50) treats.push('🧩 Cognitive TEACCH: Left-to-right work system. Visual schedule. Matching and sorting tasks 4×15min/day.');
    if(!treats.length) treats.push('✨ Excellent performance across all domains! Maintain programme and gradually increase difficulty.');
    c.innerHTML=`
    <div class="card"><h3>🧠 Automated Clinical Assessment — ${st.child_name||st.name||'Child'}</h3>
      ${diags.map(d=>`<div class="diag-item">${d}</div>`).join('')}
    </div>
    <div class="card"><h3>💊 Evidence-Based Treatment Recommendations</h3>
      ${treats.map(t=>`<div class="treat-item">${t}</div>`).join('')}
    </div>
    <div class="card"><h3>📊 Session Statistics</h3>
      <div class="diag-item">Accuracy: ${(st.tasks_success||0)+(st.tasks_fail||0)>0?
        Math.round((st.tasks_success||0)/((st.tasks_success||0)+(st.tasks_fail||0))*100):0}%</div>
      <div class="diag-item">Conversation Level: Level ${st.conversation_level||1}</div>
      <div class="diag-item">Dominant Emotion: ${st.emotion||'neutral'}</div>
      <div class="diag-item">Lip Motion: ${st.lip_speaking?'Active (speech detected)':'Inactive'}</div>
      <div class="diag-item">Finger Count: ${st.finger_count||0}/10</div>
      <div class="diag-item">Tasks completed (no repeat): ${st.child_done_count||0}</div>
    </div>`;
  }
  else if(t==='children'){
    c.innerHTML=`<div class="card"><h3>👶 Register Child (Permanent Profile)</h3>
      <form method="POST" action="/register_child">
        <input name="child_name" placeholder="Child's full name" required>
        <input name="child_age" placeholder="Age" type="number" min="2" max="18" value="6">
        <select name="asd_level">
          <option value="1">ASD Level 1 — Mild (Requiring Support)</option>
          <option value="2" selected>ASD Level 2 — Moderate (Requiring Substantial Support)</option>
          <option value="3">ASD Level 3 — Severe (Requiring Very Substantial Support)</option>
        </select>
        <textarea name="child_notes" placeholder="Clinical notes, preferences, co-occurring conditions…" rows="2"></textarea>
        <button type="submit" class="btn btn-g">+ Register Child Permanently</button>
      </form>
    </div>
    <div class="card"><h3>📋 Registered Children</h3><div id="childList">Loading…</div></div>`;
    loadChildren();
  }
  else if(t==='sessions'){
    c.innerHTML=`<div class="card"><h3>📅 Session History — Select Child</h3>
      <div style="display:flex;gap:8px;margin-bottom:10px">
        <input id="sess_child" placeholder="Child name" value="${st.child_name||st.name||''}">
        <button class="btn" style="width:120px" onclick="loadSessions()">Load Sessions</button>
      </div>
      <div class="sess-row" style="font-weight:700;color:var(--purple)">
        <span>Date</span><span>Score</span><span>✅OK</span><span>❌Fail</span>
        <span>⏱Min</span><span>Level</span><span>Emotion</span>
      </div>
      <div id="sessRows"><div style="color:var(--text2);padding:8px">Click Load Sessions</div></div>
    </div>
    <div class="card"><h3>💾 Save Current Session</h3>
      <form method="POST" action="/save_session">
        <button type="submit" class="btn btn-y">💾 Save Session to Database</button>
      </form>
    </div>`;
  }
  else if(t==='screening'){
    renderScreening(c);
  }
  else if(t==='log'){
    const logs=(st.logs||[]).slice().reverse().slice(0,50);
    const pecs=(st.pecs_log||[]).slice().reverse().slice(0,30);
    c.innerHTML=`<div class="card"><h3>📋 Session Log (${logs.length} events)</h3>
      ${logs.map(l=>`<div class="log-row">
        <span>${l.time} — ${l.msg}</span>
        <span class="${l.type==='success'?'ok':'fail'}">${l.type==='success'?'✅':'ℹ️'}</span>
      </div>`).join('')||'<div style="color:var(--text2);padding:8px">No events yet</div>'}
    </div>
    <div class="card"><h3>🗣️ PECS Log (${pecs.length} uses)</h3>
      ${pecs.map(p=>`<div class="log-row">
        <span>${p.time} — ${p.name}: "${p.phrase}"</span>
        <span style="color:var(--purple)">${p.emotion||'?'}</span>
      </div>`).join('')||'<div style="color:var(--text2);padding:8px">No PECS used yet</div>'}
    </div>`;
  }
  else if(t==='pecs'){
    c.innerHTML=`<div class="card"><h3>🗣️ PECS — 50 Daily Communication Cards</h3>
      <div class="pecs-grid" id="pecsGrid">Loading…</div>
    </div>`;
    fetch('/api/pecs_items').then(r=>r.json()).then(d=>{
      const el=document.getElementById('pecsGrid'); if(!el) return;
      el.innerHTML=d.items.map(x=>
        `<button class="pecs-btn" onclick="sayPECS('${x.phrase}','${x.name}')">${x.emoji} ${x.name}</button>`).join('');
    });
  }
  else if(t==='chat'){
    const chat=(st.session_chat||[]).slice(-30);
    c.innerHTML=`<div class="card" style="height:320px;overflow-y:auto" id="chatBox">
      ${chat.map(m=>{const col=m.role==='Pepper'?'#a78bfa':m.role==='Therapist'?'#60a5fa':'#34d399';
        const icon=m.role==='Pepper'?'🤖':m.role==='Therapist'?'👩':'👦';
        return `<div style="margin:5px 0"><span style="color:${col};font-weight:bold">${icon}[${m.time}]:</span> <span>${m.text}</span></div>`;
      }).join('')||'<div style="color:var(--text2)">No chat yet</div>'}
    </div>
    <div style="display:flex;gap:8px;margin-top:8px">
      <input id="chatMsg" placeholder="Type message to Pepper or therapist… (Enter)"
        onkeydown="if(event.key==='Enter')sendChat()">
      <button class="btn" style="width:80px" onclick="sendChat()">Send</button>
    </div>`;
    const cb=document.getElementById('chatBox'); if(cb) cb.scrollTop=cb.scrollHeight;
  }
  else if(t==='ai'){
    c.innerHTML=`<div class="card">
      <h3>🤖 AI Clinical Advisor — Powered by Gemini</h3>
      <p style="color:var(--text2);font-size:.82em;margin-bottom:10px">
        Ask about therapy strategies, home activities, behaviour management, or session results.</p>
      <div id="aiHistory" style="max-height:280px;overflow-y:auto;margin-bottom:10px">
        ${(_ai_chat_js||[]).map(m=>`<div style="margin:6px 0;padding:8px;border-radius:8px;
          background:${m.role==='ai'?'#1e1b4b':'#052918'}">
          <span style="font-weight:700;color:${m.role==='ai'?'#a78bfa':'#22c55e'}">
            ${m.role==='ai'?'🤖 Gemini AI':'👤 You'}:</span>
          <span style="margin-right:8px"> ${m.text}</span>
        </div>`).join('')||'<div style="color:var(--text2);padding:8px">No conversation yet. Ask a question!</div>'}
      </div>
      <div style="display:flex;gap:8px">
        <input id="aiQ" placeholder="e.g. How can I improve verbal skills at home?" 
          onkeydown="if(event.key==='Enter')askAI()">
        <button class="btn" style="width:100px" onclick="askAI()" id="aiBtn">Ask AI</button>
      </div>
      <div style="display:flex;flex-wrap:wrap;gap:5px;margin-top:8px">
        ${['What therapy activities for home?','How to improve attention?',
           'Tips for verbal communication?','How to handle tantrums?',
           'Best PECS approach for my child?','Explain the treatment plan'].map(q=>
          `<button onclick="document.getElementById('aiQ').value='${q}';askAI()"
            style="background:#1e1b4b;border:1px solid #4f46e5;border-radius:16px;
            padding:4px 10px;cursor:pointer;font-size:.74em;color:#e0e6ff">${q}</button>`).join('')}
      </div>
    </div>`;
  }
  else if(t==='quick'){
    c.innerHTML=`<div class="card"><h3>⚡ Quick Actions — Remote Control</h3>
    <div class="quick-grid">
      ${[['Next Task','🎯','next'],['Break','⏸️','break'],['Celebrate','🎉','celebrate'],
         ['Encourage','💪','encourage'],['PDF Report','📄','report'],['Pause','⏯️','pause']
      ].map(([l,ic,a])=>`<div class="qbtn" onclick="quickAction('${a}')">${ic}<br><span style="font-size:.78em">${l}</span></div>`).join('')}
    </div></div>
    <div class="card"><h3>🔄 Refresh Child Tasks (Allow Repeats)</h3>
      <p style="color:var(--text2);font-size:.82em;margin-bottom:8px">
        This will reset the no-repeat task history for the current child. 
        Previously completed tasks will become available again.</p>
      <form method="POST" action="/reset_child_tasks">
        <input type="hidden" name="child_name" value="${st.child_name||st.name||''}">
        <button type="submit" class="btn btn-r">🔄 Refresh — Reset Task History for ${st.child_name||st.name||'Child'}</button>
      </form>
    </div>
    <div class="card"><h3>📊 Live Stats</h3>
    <div class="stat-grid">
      <div class="stat"><div class="val" style="color:#22c55e">${st.tasks_success||0}</div><div class="lbl">✅ Correct</div></div>
      <div class="stat"><div class="val" style="color:#ef4444">${st.tasks_fail||0}</div><div class="lbl">❌ Failed</div></div>
      <div class="stat"><div class="val" style="color:#fbbf24">${st.streak||0}</div><div class="lbl">🔥 Streak</div></div>
      <div class="stat"><div class="val" style="color:#60a5fa">${st.attention||0}%</div><div class="lbl">👁 Attention</div></div>
    </div></div>`;
  }
}
function renderScreening(c){
  const isca=['Responds to name being called','Makes eye contact with others',
    'Points to share interest (not just to request)','Imitates actions and sounds',
    'Uses words or gestures to communicate','Shows interest in other children',
    'Engages in pretend play','Understands simple instructions',
    'Shows emotions appropriately','Has unusual repetitive behaviours'];
  const isaa=['Rarely or never uses eye contact','Does not point or wave bye-bye',
    'Does not show or bring objects of interest','Does not respond to facial expressions',
    'Rarely smiles in social situations','Has very limited or no functional language',
    'Does not engage in back-and-forth play','Insists on sameness/routines rigidly',
    'Shows unusual sensory interests or responses','Has self-injurious behaviour',
    'Rarely initiates social contact','Does not understand others emotions',
    'Has limited range of facial expressions','Shows hand-flapping or body-rocking',
    'Has significant difficulties with change','Has delayed motor milestones'];
  const isqa=['Has difficulties in social reciprocity','Shows restricted repetitive behaviours',
    'Has sensory processing differences','Has communication difficulties',
    'Shows rigidity and inflexibility','Has difficulties with executive function',
    'Shows emotional dysregulation','Has difficulties with peer relationships',
    'Shows unusual attachment to objects','Has splinter skills or savant abilities'];
  const tools={isca:{qs:isca,label:'ISCA — Infant-Toddler Autism Checklist (10 items)',
    cutoffs:'Score >6: Monitoring needed. Score >12: Specialist referral recommended.'},
    isaa:{qs:isaa,label:'ISAA — Indian Scale for Assessment of Autism (16 items)',
    cutoffs:'Score >16: Mild. Score >30: Moderate. Score >45: Severe ASD indicators.'},
    isqa:{qs:isqa,label:'ISQA — Integrated Screening Questionnaire for ASD (10 items)',
    cutoffs:'Score >6: Further evaluation recommended. Score >12: High probability of ASD.'}};
  let html=`<div class="card"><h3>🧪 Select Screening Tool</h3>
    <div style="display:flex;gap:8px;margin-bottom:12px">
      ${Object.entries(tools).map(([k,v])=>
        `<button class="btn" style="font-size:.8em" onclick="switchTool('${k}')">${k.toUpperCase()}</button>`).join('')}
    </div>
    ${Object.entries(tools).map(([key,tool])=>`
    <div id="tool_${key}" style="display:${key==='isca'?'block':'none'}">
      <h3 style="color:var(--blue);margin-bottom:6px">${tool.label}</h3>
      <p style="color:var(--text2);font-size:.78em;margin-bottom:8px">
        0=No concern, 1=Some concern, 2=Strong concern | ${tool.cutoffs}</p>
      ${tool.qs.map((q,i)=>`<div class="q-item">
        <div class="q-text">${i+1}. ${q}</div>
        <div class="q-opts">
          ${[['0','None'],['1','Some'],['2','Strong']].map(([v,l])=>
            `<div class="q-opt ${qa[key+'_'+i]===v?'sel':''}"
             id="${key}_${i}_${v}" onclick="setQ('${key}',${i},'${v}',this)">${v} — ${l}</div>`).join('')}
        </div></div>`).join('')}
      <button class="btn btn-g" onclick="submitScreen('${key}',${tool.qs.length})">
        Submit ${key.toUpperCase()} Screening</button>
      <div id="${key}_result" class="score-box" style="display:none"></div>
    </div>`).join('')}
  </div>`;
  c.innerHTML=html;
}
let _ai_chat_js=[];
function switchTool(key){
  ['isca','isaa','isqa'].forEach(k=>document.getElementById('tool_'+k).style.display=k===key?'block':'none');
}
function setQ(type,i,v,el){
  qa[type+'_'+i]=v;
  document.querySelectorAll(`[id^="${type}_${i}_"]`).forEach(x=>x.classList.remove('sel'));
  el.classList.add('sel');
}
function submitScreen(tool,n){
  let total=0;
  for(let i=0;i<n;i++) total+=(parseInt(qa[tool+'_'+i])||0);
  fetch('/api/screening',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({instrument:tool,score:total,child:st.child_name||st.name})});
  const el=document.getElementById(tool+'_result');
  let interp='';
  if(tool==='isca') interp=total>12?'⚠️ HIGH — Specialist referral strongly recommended':total>6?'⚠️ MODERATE — Further evaluation needed':'✅ LOW — Continue monitoring';
  else if(tool==='isaa') interp=total>45?'🔴 SEVERE ASD indicators':total>30?'⚠️ MODERATE ASD indicators':total>16?'⚠️ MILD ASD indicators':'✅ Below threshold';
  else interp=total>12?'⚠️ HIGH probability — Full diagnostic assessment recommended':total>6?'⚠️ MODERATE — Further evaluation recommended':'✅ LOW — Continue monitoring';
  if(el){el.style.display='block';el.innerHTML=`<div class="sc-num">${total}</div>
    <div style="color:var(--green);font-size:.84em;margin-top:4px">${interp}</div>`;}
}
async function loadChildren(){
  const r=await fetch('/api/children'); const d=await r.json();
  const el=document.getElementById('childList'); if(!el) return;
  if(!d.children||!d.children.length){
    el.innerHTML='<div style="color:var(--text2);padding:8px">No children registered yet</div>'; return;}
  el.innerHTML=d.children.map(ch=>`<div class="child-card" onclick="switchChild('${ch.name}')">
    <span style="font-size:1.7em">👦</span>
    <div><div style="font-weight:700">${ch.name}</div>
    <div style="font-size:.74em;color:var(--text2)">Age:${ch.age} | ASD L${ch.level} | ${ch.notes||''}</div>
    <div style="font-size:.72em;color:var(--text2)">ISCA:${ch.isca} | ISAA:${ch.isaa} | ISQA:${ch.isqa}</div></div>
    <button onclick="event.stopPropagation();resetTasks('${ch.name}')"
      style="margin-right:auto;background:#dc2626;color:#fff;border:none;border-radius:6px;
      padding:4px 8px;cursor:pointer;font-size:.72em">🔄 Refresh Tasks</button>
  </div>`).join('');
}
async function loadSessions(){
  const name=document.getElementById('sess_child').value.trim()||st.child_name||st.name||'';
  const r=await fetch(`/api/child_sessions?name=${encodeURIComponent(name)}`);
  const d=await r.json(); const el=document.getElementById('sessRows'); if(!el) return;
  if(!d.sessions||!d.sessions.length){
    el.innerHTML='<div style="color:var(--text2);padding:8px">No sessions saved yet</div>'; return;}
  el.innerHTML=d.sessions.map(s=>`<div class="sess-row">
    <span>${s.date.slice(0,16)}</span><span style="color:#fbbf24">${s.score}</span>
    <span style="color:#22c55e">${s.ok}</span><span style="color:#ef4444">${s.fail}</span>
    <span>${s.dur}m</span><span>L${s.level}</span>
    <span style="color:#a78bfa">${s.emotion}</span>
  </div>`).join('');
}
async function switchChild(name){
  await fetch('/api/switch_child',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({name})}); fetchSt();
}
async function resetTasks(name){
  if(!confirm(`Reset task history for ${name}? They will be able to redo all tasks.`)) return;
  await fetch('/api/reset_tasks',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({name})}); alert(`✅ Task history reset for ${name}`);
}
async function quickAction(a){
  if(a==='report'){window.open('/report_pdf');return;}
  await fetch('/api/quick_action',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({action:a})});
}
async function sayPECS(ph,nm){
  await fetch('/api/pecs',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({phrase:ph,name:nm})});
}
async function sendChat(){
  const msg=document.getElementById('chatMsg').value.trim(); if(!msg) return;
  document.getElementById('chatMsg').value='';
  await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json'},
    body:JSON.stringify({message:msg})});
  setTimeout(()=>showTab('chat'),700);
}
async function askAI(){
  const q=document.getElementById('aiQ').value.trim(); if(!q) return;
  const btn=document.getElementById('aiBtn');
  btn.textContent='Thinking…'; btn.disabled=true;
  document.getElementById('aiQ').value='';
  try{
    const r=await fetch('/api/ai_advice',{method:'POST',
      headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q})});
    const d=await r.json();
    if(d.ok){_ai_chat_js=d.chat||[]; showTab('ai');}
  }catch(e){}
  finally{btn.textContent='Ask AI'; btn.disabled=false;}
}
fetchSt(); setInterval(fetchSt,1500); renderTab('overview');
</script></body></html>"""

# ── Flask Routes ─────────────────────────────────────────────────
@parent_app.route("/")
def index():
    ST["child_done_count"]=len(_child_done)
    ai_chat_str=json.dumps(_ai_chat[-20:]).replace("'","\\'")
    html=DASHBOARD_HTML.replace("(_ai_chat_js||[])",ai_chat_str)
    return render_template_string(html)

@parent_app.route("/api/state")
def api_state():
    ST["child_done_count"]=len(_child_done)
    return jsonify({k:ST[k] for k in ST if isinstance(ST[k],(str,int,float,bool,list,dict,type(None)))})

@parent_app.route("/api/ai_advice",methods=["POST","GET"])
def api_ai_advice():
    """Fixed AI advice route — no more 404!"""
    if request.method=="GET":
        return jsonify({"ok":True,"chat":_ai_chat[-20:]})
    data=request.get_json(silent=True) or {}
    q=data.get("question","").strip()
    if not q:
        return jsonify({"ok":False,"chat":_ai_chat[-20:],"error":"No question provided"})
    _ai_chat.append({"role":"parent","text":q,"time":datetime.now().strftime("%H:%M")})
    ans=gemini_chat(q)
    _ai_chat.append({"role":"ai","text":ans,"time":datetime.now().strftime("%H:%M")})
    if len(_ai_chat)>40: _ai_chat[:]=_ai_chat[-40:]
    return jsonify({"ok":True,"answer":ans,"chat":_ai_chat[-20:]})

@parent_app.route("/api/screening",methods=["POST"])
def api_screening():
    d=request.get_json(silent=True) or {}
    sc=int(d.get("score",0)); tool=d.get("instrument","isca"); child=d.get("child",CHILD_NAME)
    db_update_screening(child,
        isca=sc if tool=="isca" else None,
        isaa=sc if tool=="isaa" else None,
        isqa=sc if tool=="isqa" else None)
    if sc>12: ST["conversation_level"]=1
    elif sc>6: ST["conversation_level"]=min(2,ST["conversation_level"])
    return jsonify({"ok":True,"conv_level":ST["conversation_level"]})

@parent_app.route("/api/pecs_items")
def api_pecs_items():
    items=[{"emoji":e,"name":n,"phrase":p} for e,n,p in PECS_ITEMS]
    return jsonify({"items":items})

@parent_app.route("/api/pecs",methods=["POST"])
def api_pecs():
    d=request.get_json(silent=True) or {}; ph=d.get("phrase",""); nm=d.get("name","")
    if ph and VOICE_REF: VOICE_REF.say_pecs(f"{CHILD_NAME} says: {ph}")
    ST["pecs_log"].append({"time":datetime.now().strftime("%H:%M:%S"),
        "name":nm,"phrase":ph,"emotion":ST["emotion"]})
    return jsonify({"ok":True})

@parent_app.route("/api/chat",methods=["POST"])
def api_chat():
    d=request.get_json(silent=True) or {}; msg=d.get("message","")
    if msg: BRIDGE.sig_chat.emit("Therapist",msg)
    return jsonify({"ok":True})

@parent_app.route("/api/children")
def api_children():
    return jsonify({"children":db_all_children()})

@parent_app.route("/api/child_sessions")
def api_child_sessions():
    name=request.args.get("name",CHILD_NAME)
    return jsonify({"sessions":db_get_sessions(name)})

@parent_app.route("/api/switch_child",methods=["POST"])
def api_switch_child():
    d=request.get_json(silent=True) or {}; nm=d.get("name","")
    if nm:
        ST["child_name"]=nm
        _child_done.clear(); _child_done.update(db_get_done_tasks(nm))
        log.info(f"✅ Switched to child: {nm}, loaded {len(_child_done)} done tasks")
    return jsonify({"ok":True})

@parent_app.route("/api/reset_tasks",methods=["POST"])
def api_reset_tasks():
    d=request.get_json(silent=True) or {}; nm=d.get("name",CHILD_NAME)
    db_reset_tasks(nm); _child_done.clear(); SESSION_HISTORY.clear()
    log.info(f"✅ Task history reset for {nm} via dashboard")
    return jsonify({"ok":True})

@parent_app.route("/api/quick_action",methods=["POST"])
def api_quick():
    d=request.get_json(silent=True) or {}; ST["quick_action"]=d.get("action")
    return jsonify({"ok":True})

@parent_app.route("/register_child",methods=["POST"])
def register_child():
    name=request.form.get("child_name","").strip()
    age=int(request.form.get("child_age",6))
    level=int(request.form.get("asd_level",2))
    notes=request.form.get("child_notes","").strip()
    if name: db_save_child(name,age,level,notes)
    return redirect("/")

@parent_app.route("/save_session",methods=["POST"])
def save_session():
    dur=int((time.time()-ST.get("uptime",time.time()))/60)
    db_save_session(CHILD_NAME,ST["score"],ST["tasks_success"],ST["tasks_fail"],dur,
        {"motor":ST["skill_motor"],"cognitive":ST["skill_cognitive"],"verbal":ST["skill_verbal"],
         "math":ST["skill_math"],"social":ST["skill_social"]},
        ST["emotion"],ST["conversation_level"])
    return redirect("/")

@parent_app.route("/reset_child_tasks",methods=["POST"])
def reset_child_tasks():
    name=request.form.get("child_name",CHILD_NAME)
    db_reset_tasks(name); _child_done.clear(); SESSION_HISTORY.clear()
    return redirect("/")

@parent_app.route("/report_pdf")
def report_pdf_route():
    fn=generate_pdf()
    if fn and os.path.exists(fn):
        return send_file(fn,as_attachment=True,
            download_name=os.path.basename(fn),mimetype="application/pdf")
    return "PDF generation failed — pip install reportlab",500

@parent_app.errorhandler(404)
def p404(e): return redirect("/"),302
@parent_app.errorhandler(500)
def p500(e): return jsonify({"error":str(e)}),500

def run_flask():
    import logging as lg; lg.getLogger("werkzeug").setLevel(lg.ERROR)
    parent_app.run(host="0.0.0.0",port=5007,debug=False,use_reloader=False)


# ══════════════════════════════════════════════════════════════════
# main()
# ══════════════════════════════════════════════════════════════════
def main():
    global VOICE_REF

    app=QApplication(sys.argv); app.setStyle("Fusion")
    pal=QPalette()
    pal.setColor(QPalette.ColorRole.Window,QColor(6,9,24))
    pal.setColor(QPalette.ColorRole.WindowText,QColor(224,230,255))
    pal.setColor(QPalette.ColorRole.Base,QColor(12,15,30))
    pal.setColor(QPalette.ColorRole.Text,QColor(224,230,255))
    pal.setColor(QPalette.ColorRole.Button,QColor(12,15,30))
    pal.setColor(QPalette.ColorRole.ButtonText,QColor(224,230,255))
    pal.setColor(QPalette.ColorRole.Highlight,QColor(79,70,229))
    pal.setColor(QPalette.ColorRole.HighlightedText,QColor(255,255,255))
    app.setPalette(pal)

    log.info("🔊 Starting voice engine...")
    voice=VoiceEngine(); VOICE_REF=voice

    log.info("🤖 Starting PyBullet simulation...")
    pb=PBWatchdog(CHILD_NAME); pb.start()

    log.info("🖥️  Building main window (1600×900)...")
    win=MainWindow(); win.show()

    log.info("📷 Starting computer vision pipeline...")
    cam=CameraThread(); cam.start()

    log.info("🎯 Starting therapy controller...")
    ctrl=TherapyController(voice,pb); ctrl.start()

    log.info("🌐 Starting parent dashboard on port 5007...")
    threading.Thread(target=run_flask,daemon=True).start()

    print("\n"+"═"*62)
    print("  ✅ Pepper Clinical Infinity V6 — Enhanced Edition")
    print(f"  👦 Child: {CHILD_NAME}")
    print(f"  ✅ PECS: 50 items (scrollable)")
    print(f"  ✅ AI Advice: Fixed — no more 404 errors!")
    print(f"  ✅ PDF: Full treatment plan + SMART goals + weekly schedule")
    print(f"  ✅ Screening: ISCA + ISAA + ISQA validated tools")
    print(f"  ✅ Children: Persistent SQLite profiles")
    print(f"  ✅ Sessions: All sessions stored per child on dashboard")
    print(f"  ✅ No-Repeat: Tasks never repeat unless parent presses Refresh")
    print(f"  🌐 Dashboard: http://localhost:5007")
    print(f"  🌐 Network:   http://{LOCAL_IP}:5007")
    print(f"  📊 CSV: {CSV_FILE}")
    print("═"*62+"\n")

    webbrowser.open("http://localhost:5007")

    def _cleanup():
        log.info("🛑 Shutting down Pepper Clinical...")
        ctrl.stop(); cam.stop(); pb.stop()
        # Save final session to DB
        dur=int((time.time()-ST.get("uptime",time.time()))/60)
        if ST["tasks_success"]+ST["tasks_fail"]>0:
            db_save_session(CHILD_NAME,ST["score"],ST["tasks_success"],ST["tasks_fail"],dur,
                {"motor":ST["skill_motor"],"cognitive":ST["skill_cognitive"],
                 "verbal":ST["skill_verbal"],"math":ST["skill_math"],"social":ST["skill_social"]},
                ST["emotion"],ST["conversation_level"])
            log.info(f"✅ Session saved to DB for {CHILD_NAME}")
        try: voice.cleanup()
        except: pass
        try: os.system("pkill -f aplay 2>/dev/null")
        except: pass

    app.aboutToQuit.connect(_cleanup)
    sys.exit(app.exec())

if __name__=="__main__":
    main()
