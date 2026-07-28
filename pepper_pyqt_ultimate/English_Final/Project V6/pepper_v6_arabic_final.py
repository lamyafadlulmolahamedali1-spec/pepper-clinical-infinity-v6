#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════╗
║  بيبر كلينيكال إنفينيتي V6 — النسخة العربية النهائية           ║
║  صوت Piper (ar_JO-kareem) + مصادقة الوالدين + كل شيء عربي     ║
╚══════════════════════════════════════════════════════════════════╝
"""
import os, sys, warnings, ctypes, signal, logging, threading
import subprocess, socket, time, random, math, re, json, csv
import base64, wave, tempfile, secrets, sqlite3, hashlib
from datetime import datetime, timedelta
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
    format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
log = logging.getLogger("بيبر")

try:
    _a = ctypes.cdll.LoadLibrary("libasound.so.2")
    _a.snd_lib_error_set_handler(ctypes.c_void_p(None))
except: pass
def _exit(s,f):
    try: os.system("pkill -f aplay 2>/dev/null")
    except: pass
    sys.exit(0)
signal.signal(signal.SIGTERM,_exit); signal.signal(signal.SIGINT,_exit)

import cv2, numpy as np
from PIL import Image, ImageDraw
import mediapipe as mp
import speech_recognition as sr

try: from faster_whisper import WhisperModel as FW; _FW=True
except: _FW=False
try: import google.generativeai as genai; _GENAI=True
except: _GENAI=False
try:
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,Table,TableStyle
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.lib import colors as RLC; _PDF=True
except: _PDF=False

from flask import (Flask, render_template_string, jsonify, request,
                   session, redirect, url_for, send_file, make_response)
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QLabel, QPushButton, QFrame, QGridLayout, QLineEdit, QTextEdit,
    QGraphicsDropShadowEffect, QProgressBar, QScrollArea,
)
from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QObject, QThread,
    QMutex, QMutexLocker, QPoint, QRect, QSize,
)
from PyQt6.QtGui import (
    QFont, QColor, QPalette, QPixmap, QImage,
    QPainter, QLinearGradient, QBrush, QPen,
)
import webbrowser

# ══════════════════════════════════════════════════════════════════
# إعداد قاعدة البيانات — Database Setup
# ══════════════════════════════════════════════════════════════════
DB_PATH = os.path.expanduser("~/pepper_duo/auth/parents.db")

def init_db():
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS parents (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        email       TEXT UNIQUE NOT NULL,
        password    TEXT NOT NULL,
        name        TEXT NOT NULL,
        center_name TEXT DEFAULT '',
        phone       TEXT DEFAULT '',
        created_at  TEXT NOT NULL,
        last_login  TEXT,
        is_active   INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS children (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id   INTEGER NOT NULL,
        name        TEXT NOT NULL,
        age         INTEGER DEFAULT 6,
        asd_level   INTEGER DEFAULT 2,
        notes       TEXT DEFAULT '',
        created_at  TEXT NOT NULL,
        FOREIGN KEY (parent_id) REFERENCES parents(id))""")
    c.execute("""CREATE TABLE IF NOT EXISTS auth_sessions (
        token       TEXT PRIMARY KEY,
        parent_id   INTEGER NOT NULL,
        created_at  TEXT NOT NULL,
        expires_at  TEXT NOT NULL,
        FOREIGN KEY (parent_id) REFERENCES parents(id))""")
    conn.commit(); conn.close()
    log.info("✅ قاعدة البيانات جاهزة")

def _hash_pw(pw):
    try:
        import bcrypt
        return bcrypt.hashpw(pw.encode(), bcrypt.gensalt()).decode()
    except ImportError:
        salt = secrets.token_hex(16)
        h = hashlib.sha256((pw+salt).encode()).hexdigest()
        return f"sha256:{salt}:{h}"

def _verify_pw(pw, hashed):
    try:
        if hashed.startswith("sha256:"):
            _, salt, h = hashed.split(":")
            return hashlib.sha256((pw+salt).encode()).hexdigest()==h
        import bcrypt
        return bcrypt.checkpw(pw.encode(), hashed.encode())
    except: return False

def register_parent(email, password, name, center="", phone=""):
    email = email.strip().lower()
    if not re.match(r'^[^@]+@[^@]+\.[^@]+$', email):
        return False, "البريد الإلكتروني غير صحيح"
    if len(password) < 8:
        return False, "كلمة المرور يجب أن تكون 8 أحرف على الأقل"
    if not name.strip():
        return False, "الاسم مطلوب"
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id FROM parents WHERE email=?", (email,))
        if c.fetchone():
            conn.close(); return False, "البريد مسجل مسبقاً"
        c.execute(
            "INSERT INTO parents (email,password,name,center_name,phone,created_at) VALUES (?,?,?,?,?,?)",
            (email, _hash_pw(password), name.strip(), center, phone,
             datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit(); conn.close()
        return True, "تم التسجيل! يمكنك الدخول الآن"
    except Exception as e:
        return False, f"خطأ: {e}"

def login_parent(email, password):
    email = email.strip().lower()
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id,password,name,is_active FROM parents WHERE email=?", (email,))
        row = c.fetchone()
        if not row: conn.close(); return False, None, "البريد غير مسجل"
        pid, hashed, name, active = row
        if not active: conn.close(); return False, None, "الحساب موقوف"
        if not _verify_pw(password, hashed):
            conn.close(); return False, None, "كلمة المرور غير صحيحة"
        token = secrets.token_urlsafe(32)
        exp = (datetime.now()+timedelta(hours=24)).strftime("%Y-%m-%d %H:%M:%S")
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        c.execute("INSERT INTO auth_sessions (token,parent_id,created_at,expires_at) VALUES (?,?,?,?)",
                  (token, pid, now, exp))
        c.execute("UPDATE parents SET last_login=? WHERE id=?", (now, pid))
        conn.commit(); conn.close()
        return True, {"token":token,"name":name,"parent_id":pid}, "مرحباً بك!"
    except Exception as e:
        return False, None, f"خطأ: {e}"

def verify_token(token):
    if not token: return None
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("""SELECT s.parent_id,p.name,p.email,p.center_name
                     FROM auth_sessions s JOIN parents p ON s.parent_id=p.id
                     WHERE s.token=? AND s.expires_at > ?""",
                  (token, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        row = c.fetchone(); conn.close()
        if row: return {"parent_id":row[0],"name":row[1],"email":row[2],"center":row[3]}
        return None
    except: return None

def logout_token(token):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute("DELETE FROM auth_sessions WHERE token=?", (token,))
        conn.commit(); conn.close()
    except: pass

def db_get_children(parent_id):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute("SELECT id,name,age,asd_level,notes FROM children WHERE parent_id=?", (parent_id,))
        rows = c.fetchall(); conn.close()
        return [{"id":r[0],"name":r[1],"age":r[2],"level":r[3],"notes":r[4]} for r in rows]
    except: return []

def db_add_child(parent_id, name, age, level, notes=""):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.execute(
            "INSERT INTO children (parent_id,name,age,asd_level,notes,created_at) VALUES (?,?,?,?,?,?)",
            (parent_id, name, age, level, notes, datetime.now().strftime("%Y-%m-%d %H:%M:%S")))
        conn.commit(); conn.close(); return True
    except: return False

init_db()


# ══════════════════════════════════════════════════════════════════
# إعداد النظام
# ══════════════════════════════════════════════════════════════════
def kill_ports(*ports):
    for p in ports:
        try: os.system(f"fuser -k {p}/tcp 2>/dev/null")
        except: pass
        for _ in range(6):
            try:
                s=socket.socket(); s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1)
                s.bind(("0.0.0.0",p)); s.close(); break
            except: time.sleep(0.25)

kill_ports(5007)

def get_ip():
    try:
        s=socket.socket(socket.AF_INET,socket.SOCK_DGRAM)
        s.connect(("8.8.8.8",80)); ip=s.getsockname()[0]; s.close(); return ip
    except: return "127.0.0.1"

LOCAL_IP   = get_ip()
GEMINI_KEY = "AIzaSyDEdleVKiQ5E00wMcjMbji0G9JcYT2TvE8"
PIPER_MODEL = os.path.expanduser("~/pepper_duo/models/ar_JO-kareem-medium.onnx")

print("\n"+"═"*60)
print("  بيبر كلينيكال إنفينيتي V6 — النسخة العربية النهائية")
print("  صوت Piper العربي + مصادقة الوالدين")
print("═"*60)
CHILD_NAME = input("\n👦 اسم الطفل: ").strip() or "الطفل"
CHILD_AGE  = input("   العمر (الافتراضي 6): ").strip() or "6"
SAFE_NAME  = re.sub(r"[^a-zA-Z0-9_]","_",CHILD_NAME)
CSV_FILE   = f"{SAFE_NAME}_نتائج.csv"

with open(CSV_FILE,"w",newline="",encoding="utf-8-sig") as f:
    csv.writer(f).writerow([
        "الوقت","الطفل","المهمة","المجال","البروتوكول",
        "النتيجة","النقاط","المشاعر","مستوى المحادثة","الزمن_ms"])

def log_csv(tid,dom,proto,result,sc,em,clvl,ms):
    try:
        with open(CSV_FILE,"a",newline="",encoding="utf-8-sig") as f:
            csv.writer(f).writerow([
                datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                CHILD_NAME,tid,dom,proto,"نجاح" if result else "فشل",sc,em,clvl,int(ms)])
    except: pass

if _GENAI:
    try: genai.configure(api_key=GEMINI_KEY)
    except: pass

# ══════════════════════════════════════════════════════════════════
# محرك الصوت — Piper TTS + pyttsx3 fallback
# ══════════════════════════════════════════════════════════════════
class PiperVoice:
    """
    يستخدم: echo "النص" | piper --model ar_JO-kareem-medium.onnx
             --length_scale 0.85 --output_file /tmp/out.wav && aplay /tmp/out.wav
    """
    def __init__(self):
        self.model = PIPER_MODEL
        self.length_scale = 0.85
        self._lock = threading.Lock()
        self._interrupt = False
        self._speaking = False
        self._piper_ok = self._check_piper()
        self._tts = None
        if not self._piper_ok:
            self._init_tts()

    def _check_piper(self):
        try:
            r = subprocess.run(["piper","--version"],
                capture_output=True,text=True,timeout=5)
            if r.returncode==0 and os.path.exists(self.model):
                log.info(f"✅ Piper TTS جاهز — {self.model}")
                return True
            elif r.returncode==0:
                log.warning(f"⚠️  النموذج غير موجود: {self.model}")
                log.warning("    شغّل: bash download_voice.sh")
        except FileNotFoundError:
            log.warning("⚠️  Piper غير مثبت — pip install piper-tts أو apt install piper")
        except: pass
        return False

    def _init_tts(self):
        try:
            import pyttsx3
            self._tts = pyttsx3.init()
            self._tts.setProperty("rate",105)
            self._tts.setProperty("volume",1.0)
            for v in self._tts.getProperty("voices"):
                if any(x in v.name.lower() for x in ["arabic","hoda","naayf","ar-"]):
                    self._tts.setProperty("voice",v.id); break
            log.info("✅ pyttsx3 احتياطي جاهز")
        except Exception as e:
            log.warning(f"TTS: {e}")

    def _lip_sync(self, text, shared_state):
        """محاكاة مزامنة الشفاه أثناء الكلام"""
        for word in text.split():
            if self._interrupt: break
            d = max(0.07, len(word)/12.0)
            shared_state["lip_sync_value"] = min(1.0, 0.5+random.uniform(0.1,0.45))
            time.sleep(d*0.55)
            shared_state["lip_sync_value"] = max(0.05, shared_state["lip_sync_value"]*0.3)
            time.sleep(d*0.45)
        shared_state["lip_sync_value"] = 0.0

    def say(self, text, wait=True, st_ref=None):
        if not text or not text.strip(): return
        self._interrupt = False
        self._speaking = True
        if st_ref: st_ref["is_speaking"] = True
        clean = text.strip()

        # مزامنة الشفاه في خيط منفصل
        if st_ref:
            threading.Thread(
                target=self._lip_sync, args=(clean, st_ref), daemon=True).start()

        def _do():
            try:
                if self._piper_ok:
                    self._piper(clean)
                elif self._tts:
                    with self._lock:
                        try: self._tts.say(clean); self._tts.runAndWait()
                        except: pass
                else:
                    log.info(f"[صوت] {clean}")
            finally:
                self._speaking = False
                if st_ref:
                    st_ref["is_speaking"] = False
                    st_ref["lip_sync_value"] = 0.0

        if wait:
            _do()
        else:
            threading.Thread(target=_do, daemon=True).start()

    def _piper(self, text):
        with self._lock:
            wav = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".wav",delete=False) as f:
                    wav = f.name
                cmd = ["piper","--model",self.model,
                       "--length_scale",str(self.length_scale),
                       "--output_file",wav]
                proc = subprocess.run(cmd,input=text,capture_output=True,
                                      text=True,timeout=20)
                if proc.returncode==0 and os.path.exists(wav):
                    if not self._interrupt:
                        ap = subprocess.Popen(["aplay",wav],
                            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
                        while ap.poll() is None:
                            if self._interrupt: ap.terminate(); break
                            time.sleep(0.05)
                else:
                    log.warning(f"Piper: {proc.stderr[:80]}")
                    if self._tts:
                        try: self._tts.say(text); self._tts.runAndWait()
                        except: pass
            except Exception as e:
                log.warning(f"Piper: {e}")
                if self._tts:
                    try: self._tts.say(text); self._tts.runAndWait()
                    except: pass
            finally:
                if wav:
                    try: os.unlink(wav)
                    except: pass

    def say_pecs(self, text, st_ref=None):
        self.interrupt(st_ref)
        time.sleep(0.15)
        threading.Thread(target=self.say,args=(text,True,st_ref),daemon=True).start()

    def interrupt(self, st_ref=None):
        self._interrupt = True
        self._speaking = False
        try: os.system("pkill -f aplay 2>/dev/null")
        except: pass
        if self._tts:
            try: self._tts.stop()
            except: pass
        if st_ref:
            st_ref["is_speaking"] = False
            st_ref["lip_sync_value"] = 0.0

    def cleanup(self):
        self.interrupt()

VOICE_REF = None


# ══════════════════════════════════════════════════════════════════
# بيانات المهام العربية
# ══════════════════════════════════════════════════════════════════
COLORS_AR=[
    {"id":"أحمر","color":"#ef4444","label":"🔴 أحمر"},
    {"id":"أزرق","color":"#3b82f6","label":"🔵 أزرق"},
    {"id":"أخضر","color":"#22c55e","label":"🟢 أخضر"},
    {"id":"أصفر","color":"#eab308","label":"🟡 أصفر"},
    {"id":"بنفسجي","color":"#a855f7","label":"🟣 بنفسجي"},
    {"id":"برتقالي","color":"#f97316","label":"🟠 برتقالي"},
    {"id":"وردي","color":"#ec4899","label":"🩷 وردي"},
    {"id":"أبيض","color":"#e2e8f0","label":"⬜ أبيض"},
    {"id":"أسود","color":"#1e293b","label":"⬛ أسود"},
    {"id":"بني","color":"#92400e","label":"🟫 بني"},
]
ANIMALS_AR=[
    {"id":"كلب","emoji":"🐶","label":"كلب"},{"id":"قطة","emoji":"🐱","label":"قطة"},
    {"id":"أسد","emoji":"🦁","label":"أسد"},{"id":"فيل","emoji":"🐘","label":"فيل"},
    {"id":"أرنب","emoji":"🐰","label":"أرنب"},{"id":"دب","emoji":"🐻","label":"دب"},
    {"id":"قرد","emoji":"🐵","label":"قرد"},{"id":"نمر","emoji":"🐯","label":"نمر"},
    {"id":"سمكة","emoji":"🐟","label":"سمكة"},{"id":"عصفور","emoji":"🐦","label":"عصفور"},
    {"id":"بقرة","emoji":"🐄","label":"بقرة"},{"id":"حصان","emoji":"🐎","label":"حصان"},
    {"id":"خروف","emoji":"🐑","label":"خروف"},{"id":"بطة","emoji":"🦆","label":"بطة"},
    {"id":"ضفدع","emoji":"🐸","label":"ضفدع"},{"id":"فراشة","emoji":"🦋","label":"فراشة"},
]
FRUITS_AR=[
    {"id":"تفاح","emoji":"🍎","label":"تفاح"},{"id":"موز","emoji":"🍌","label":"موز"},
    {"id":"برتقال","emoji":"🍊","label":"برتقال"},{"id":"عنب","emoji":"🍇","label":"عنب"},
    {"id":"فراولة","emoji":"🍓","label":"فراولة"},{"id":"مانجو","emoji":"🥭","label":"مانجو"},
    {"id":"بطيخ","emoji":"🍉","label":"بطيخ"},{"id":"خوخ","emoji":"🍑","label":"خوخ"},
    {"id":"كمثرى","emoji":"🍐","label":"كمثرى"},{"id":"كرز","emoji":"🍒","label":"كرز"},
    {"id":"أناناس","emoji":"🍍","label":"أناناس"},{"id":"كيوي","emoji":"🥝","label":"كيوي"},
]
SHAPES_AR=[
    {"id":"دائرة","emoji":"⭕","label":"دائرة"},{"id":"مربع","emoji":"⬛","label":"مربع"},
    {"id":"مثلث","emoji":"🔺","label":"مثلث"},{"id":"نجمة","emoji":"⭐","label":"نجمة"},
    {"id":"قلب","emoji":"❤️","label":"قلب"},{"id":"معين","emoji":"💎","label":"معين"},
]
EMOTIONS_AR=[
    {"id":"سعيد","emoji":"😊","label":"سعيد"},{"id":"حزين","emoji":"😢","label":"حزين"},
    {"id":"غاضب","emoji":"😠","label":"غاضب"},{"id":"خائف","emoji":"😨","label":"خائف"},
    {"id":"مندهش","emoji":"😲","label":"مندهش"},{"id":"متعب","emoji":"😴","label":"متعب"},
]
FOODS_AR=[
    {"id":"أرز","emoji":"🍚","label":"أرز"},{"id":"خبز","emoji":"🍞","label":"خبز"},
    {"id":"بيض","emoji":"🥚","label":"بيض"},{"id":"حليب","emoji":"🥛","label":"حليب"},
    {"id":"تمر","emoji":"🌴","label":"تمر"},{"id":"عسل","emoji":"🍯","label":"عسل"},
    {"id":"جبن","emoji":"🧀","label":"جبن"},{"id":"حساء","emoji":"🍲","label":"حساء"},
]
VEHICLES_AR=[
    {"id":"سيارة","emoji":"🚗","label":"سيارة"},{"id":"حافلة","emoji":"🚌","label":"حافلة"},
    {"id":"قطار","emoji":"🚂","label":"قطار"},{"id":"طائرة","emoji":"✈️","label":"طائرة"},
    {"id":"قارب","emoji":"⛵","label":"قارب"},{"id":"دراجة","emoji":"🚲","label":"دراجة"},
]
BODY_AR=[
    {"id":"رأس","emoji":"🗣️","label":"رأس"},{"id":"عين","emoji":"👁️","label":"عين"},
    {"id":"أذن","emoji":"👂","label":"أذن"},{"id":"أنف","emoji":"👃","label":"أنف"},
    {"id":"فم","emoji":"👄","label":"فم"},{"id":"يد","emoji":"✋","label":"يد"},
    {"id":"قدم","emoji":"🦶","label":"قدم"},{"id":"ذراع","emoji":"💪","label":"ذراع"},
]
MOTORS_AR=[
    {"id":"تصفيق","name":"👏 صفِّق","verify":"clap",
     "instruction":"صَفِّق يديك!","waiting":"صَفِّق الآن! 👏",
     "success":"رائع! صَفَّقت! ✅","fail":"ضع يديك معاً وصفّق!",
     "prompts":["صَفِّق!","اليدان معاً!","هكذا! 👏"]},
    {"id":"تلويح","name":"👋 لوِّح","verify":"wave",
     "instruction":"لوِّح بيدك! قل مرحبا!","waiting":"لوِّح الآن! 👋",
     "success":"ممتاز! ✅","fail":"حرِّك يدك يميناً ويساراً!",
     "prompts":["لوِّح!","مرحباً!","يميناً ويساراً!"]},
    {"id":"رفع_يد","name":"✋ ارفع يدك","verify":"raise_hand",
     "instruction":"ارفع يدك عالياً فوق رأسك!","waiting":"اليد لأعلى! ✋",
     "success":"ممتاز جداً! ✅","fail":"ارفع ذراعك فوق رأسك!",
     "prompts":["ارفع!","أعلى!","للأعلى!"]},
    {"id":"لمس_الأنف","name":"👆 المس أنفك","verify":"touch_nose",
     "instruction":"المس أنفك بإصبعك!","waiting":"المس أنفك! 👆",
     "success":"أحسنت! ✅","fail":"أشر إلى أنفك بإصبعك!",
     "prompts":["الأنف!","المسه!","إصبعك على أنفك!"]},
    {"id":"مد_الذراعين","name":"🤸 مدَّ ذراعيك","verify":"arms_out",
     "instruction":"مدَّ ذراعيك للجانبين مثل الطائرة!","waiting":"مدَّ ذراعيك! 🤸",
     "success":"طيارة! ✅","fail":"افتح ذراعيك للجانبين!",
     "prompts":["للجانبين!","مثل الطيارة!","وسِّع!"]},
    {"id":"يدان_فوق","name":"🙌 يداك فوق","verify":"hands_up",
     "instruction":"ارفع كلتا يديك للأعلى!","waiting":"يداك فوق! 🙌",
     "success":"نجم! ✅","fail":"ارفع كلتا يديك فوق رأسك!",
     "prompts":["كلتا اليدين!","للأعلى!","نجمة!"]},
    {"id":"قفز","name":"🦘 اقفز","verify":"jump",
     "instruction":"اقفز للأعلى!","waiting":"اقفز! 🦘",
     "success":"قفزة رائعة! ✅","fail":"ارتفع عن الأرض!",
     "prompts":["اقفز!","للأعلى!","بوينج!"]},
    {"id":"إشارة","name":"👉 أشر","verify":"point",
     "instruction":"أشر بإصبعك للأمام!","waiting":"أشر! 👉",
     "success":"ممتاز! ✅","fail":"مدَّ إصبع السبابة للأمام!",
     "prompts":["أشر!","الإصبع للأمام!","هكذا!"]},
]
WORDS_AR=[
    "تفاحة","كرة","قطة","كلب","فيل","سمكة","جيد","سعيد","اقفز","حليب","العب",
    "أحمر","شمس","شجرة","ماء","نعم","لا","واحد","اثنان","ثلاثة","أربعة","خمسة",
    "ستة","سبعة","ثمانية","تسعة","عشرة","أزرق","أخضر","عصفور","كتاب","كوب",
    "باب","عين","قدم","يد","رأس","أنف","ذراع","كبير","صغير","ساخن","بارد",
    "مساعدة","قف","تعال","اجلس","كل","اشرب","نم","افتح","أغلق","أمي","أبي",
    "صديق","مدرسة","بيت","سيارة","زهرة","قمر","نجمة","تمر","خبز","جبن","أرز",
]
SOCIAL_PHRASES_AR=[
    "مرحبا","شكراً","من فضلك","أريد المزيد","مساعدة","نعم","لا","مع السلامة",
    "آسف","أحبك","كيف حالك","أنا بخير","صباح الخير","مساء الخير","أنا جائع",
    "أنا متعب","أريد أشرب","أنا سعيد","أريد ألعب","أنا لا أريد",
]
PECS_AR=[
    ("صباح_استيقاظ","☀️","أنا صحيت","أنا صحيت","صباح"),
    ("صباح_أسنان","🪥","أفرش أسناني","أفرش أسناني","صباح"),
    ("صباح_وجه","🚿","أغسل وجهي","أغسل وجهي","صباح"),
    ("صباح_شعر","💇","أمشط شعري","أمشط شعري","صباح"),
    ("صباح_ملابس","👕","البس ملابسي","البس ملابسي","صباح"),
    ("صباح_حذاء","👟","ألبس حذائي","ألبس حذائي","صباح"),
    ("صباح_فطور","🥣","آكل الفطور","آكل الفطور","صباح"),
    ("صباح_ماء","💧","أشرب ماء","أشرب ماء","صباح"),
    ("صباح_حمام","🚽","أذهب للحمام","أذهب للحمام","صباح"),
    ("صباح_يدين","🧼","أغسل يديّ","أغسل يديّ","صباح"),
    ("نظافة_حمام","🛁","وقت الحمام","وقت الحمام","نظافة"),
    ("نظافة_منشفة","🏮","أستخدم المنشفة","أستخدم المنشفة","نظافة"),
    ("نظافة_أظافر","💅","أقص أظافري","أقص أظافري","نظافة"),
    ("نظافة_مناديل","🧻","أستخدم المناديل","أستخدم المناديل","نظافة"),
    ("نظافة_شامبو","🧴","أغسل شعري","أغسل شعري","نظافة"),
    ("أكل_طعام","🍽️","أريد آكل","أريد آكل","طعام"),
    ("أكل_شرب","🥤","أريد أشرب","أريد أشرب","طعام"),
    ("أكل_جائع","😋","أنا جائع","أنا جائع","طعام"),
    ("أكل_شبعت","😊","أنا شبعت","أنا شبعت","طعام"),
    ("أكل_حليب","🥛","أريد حليب","أريد حليب","طعام"),
    ("أكل_عصير","🧃","أريد عصير","أريد عصير","طعام"),
    ("أكل_خبز","🍞","أريد خبز","أريد خبز","طعام"),
    ("أكل_تمر","🌴","أريد تمر","أريد تمر","طعام"),
    ("أكل_غداء","🍱","وقت الغداء","وقت الغداء","طعام"),
    ("أكل_عشاء","🍜","وقت العشاء","وقت العشاء","طعام"),
    ("تواصل_مرحبا","👋","مرحبا","مرحبا","اجتماعي"),
    ("تواصل_وداع","🙋","مع السلامة","مع السلامة","اجتماعي"),
    ("تواصل_فضلك","🙏","من فضلك","من فضلك","اجتماعي"),
    ("تواصل_شكرا","🤝","شكراً","شكراً","اجتماعي"),
    ("تواصل_آسف","😔","أنا آسف","أنا آسف","اجتماعي"),
    ("تواصل_مساعدة","🆘","أحتاج مساعدة","أحتاج مساعدة","اجتماعي"),
    ("تواصل_نعم","✅","نعم","نعم","اجتماعي"),
    ("تواصل_لا","❌","لا","لا","اجتماعي"),
    ("تواصل_زيادة","➕","أريد المزيد","أريد المزيد","اجتماعي"),
    ("تواصل_أحبك","❤️","أنا أحبك","أنا أحبك","اجتماعي"),
    ("سلامة_قف","🛑","قف","قف","سلامة"),
    ("سلامة_حار","🔥","هذا حار","هذا حار","سلامة"),
    ("سلامة_بارد","🧊","هذا بارد","هذا بارد","سلامة"),
    ("سلامة_ألم","🤕","أنا أتألم","أنا أتألم","سلامة"),
    ("سلامة_تعب","😴","أنا متعب","أنا متعب","سلامة"),
    ("سلامة_بيت","🏠","أريد أروح البيت","أريد أروح البيت","سلامة"),
    ("سلامة_مدرسة","🏫","أذهب للمدرسة","أذهب للمدرسة","سلامة"),
    ("مشاعر_سعيد","😊","أنا سعيد","أنا سعيد","مشاعر"),
    ("مشاعر_حزين","😢","أنا حزين","أنا حزين","مشاعر"),
    ("مشاعر_أحبك","❤️","أنا أحبك","أنا أحبك","مشاعر"),
    ("مشاعر_خائف","😨","أنا خائف","أنا خائف","مشاعر"),
    ("مشاعر_غاضب","😠","أنا غاضب","أنا غاضب","مشاعر"),
    ("مشاعر_بخير","👍","أنا بخير","أنا بخير","مشاعر"),
    ("مشاعر_ألعب","🎮","أريد ألعب","أريد ألعب","مشاعر"),
    ("مشاعر_نعسان","💤","أنا نعسان","أنا نعسان","مشاعر"),
    ("مشاعر_فرحان","🎉","أنا فرحان","أنا فرحان","مشاعر"),
    ("مشاعر_أكل","🍽️","أريد آكل","أريد آكل","مشاعر"),
]

# ── توليد مجمع المهام ──────────────────────────────────────────
def _grid(items,prefix,domain,protocol,tokens):
    tgt=random.choice(items)
    others=[x for x in items if x["id"]!=tgt["id"]]
    dis=random.sample(others,min(3,len(others)))
    opts=[tgt]+dis; random.shuffle(opts)
    cor=next(i for i,o in enumerate(opts) if o["id"]==tgt["id"])
    lbl=tgt.get("label",tgt["id"])
    return {
        "id":f"{prefix}_{tgt['id']}_{random.randint(0,99999)}",
        "base_id":f"{prefix}_{tgt['id']}","domain":domain,"protocol":protocol,
        "name":lbl,"instruction":f"أين {lbl}؟ اضغط عليها!",
        "waiting":f"أين {lbl}؟","success":f"صحيح! {lbl}! ✅",
        "fail":f"هذه هي {lbl}!","tablet_mode":"grid",
        "options":opts,"correct":cor,"tokens":tokens,"joy":"احتفال",
        "prompts":[f"أين {lbl}؟","انظر جيداً!","أنت تستطيع!"],
        "verify":"tablet_click"}

def generate_pool():
    pool=[]
    for _ in range(700):
        m=random.choice(MOTORS_AR)
        pool.append({**m,"id":f"{m['id']}_{random.randint(0,99999)}",
            "base_id":m["id"],"domain":"حركي",
            "protocol":random.choice(["ABA-DTT","ESDM"]),
            "tablet_mode":"motor","tokens":2,"joy":"رقص"})
    for _ in range(400): pool.append(_grid(COLORS_AR,"لون","معرفي","TEACCH",3))
    for _ in range(350): pool.append(_grid(ANIMALS_AR,"حيوان","معرفي","TEACCH",4))
    for _ in range(300): pool.append(_grid(FRUITS_AR,"فاكهة","معرفي","TIE",4))
    for _ in range(250): pool.append(_grid(SHAPES_AR,"شكل","معرفي","TEACCH",4))
    for _ in range(200): pool.append(_grid(EMOTIONS_AR,"مشاعر","اجتماعي","ESDM",5))
    for _ in range(200): pool.append(_grid(FOODS_AR,"طعام","يومي","TIE",4))
    for _ in range(200): pool.append(_grid(VEHICLES_AR,"مركبة","معرفي","TEACCH",4))
    for _ in range(200): pool.append(_grid(BODY_AR,"جسم","لفظي","DTT",4))
    for _ in range(450):
        n=random.randint(1,10)
        pool.append({"id":f"عد_{n}_{random.randint(0,99999)}","base_id":f"عد_{n}",
            "domain":"رياضيات","protocol":"ABA-DTT","name":f"🔢 اعدد {n}",
            "instruction":f"أرني {n} أصابع!","waiting":f"أرفع {n} أصابع 🖐️",
            "success":f"نعم! {n} أصابع! ✅","fail":f"أرني {n} أصابع!",
            "tablet_mode":"number","target_number":n,
            "verify":"finger_count","tokens":5,"joy":"احتفال",
            "prompts":[f"أرني {n}!","عدّ أصابعك!","استخدم اليدين!"]})
    for _ in range(500):
        w=random.choice(WORDS_AR)
        pool.append({"id":f"قل_{w}_{random.randint(0,99999)}","base_id":f"قل_{w}",
            "domain":"لفظي","protocol":"DTT","name":f"🗣️ قل '{w}'",
            "instruction":f"قل الكلمة: {w}!","waiting":f"قل {w}! 🎤",
            "success":f"سمعتك! {w}! ✅","fail":f"حاول مرة أخرى! قل: {w}!",
            "tablet_mode":"word","word_text":w,
            "verify":"speech_keyword","keyword":w,"tokens":4,"joy":"رقص",
            "prompts":[f"قل {w}!","اضغط الميكروفون!","بصوت واضح!"]})
    for _ in range(400):
        ph=random.choice(SOCIAL_PHRASES_AR)
        pool.append({"id":f"عبارة_{ph.replace(' ','_')}_{random.randint(0,99999)}",
            "base_id":f"عبارة_{ph.replace(' ','_')}",
            "domain":"اجتماعي","protocol":"ESDM","name":f"💬 '{ph}'",
            "instruction":f"قل: {ph}!","waiting":f"قل {ph}! 🎤",
            "success":f"رائع! '{ph}'! ✅","fail":f"حاول: {ph}!",
            "tablet_mode":"social","social_text":ph,
            "verify":"speech_keyword","keyword":ph,"tokens":6,"joy":"فرح_كامل",
            "prompts":[f"قل {ph}!","أنت تستطيع!","تكلم!"]})
    for _ in range(500):
        iid,emoji,label,kw,cat=random.choice(PECS_AR)
        pool.append({"id":f"يومي_{iid}_{random.randint(0,99999)}",
            "base_id":f"يومي_{iid}","domain":"يومي","protocol":"TIE",
            "name":f"{emoji} {label}","instruction":f"قل: {kw}! {emoji}",
            "waiting":f"قل! {emoji}","success":f"ممتاز! {label}! ✅",
            "fail":f"حاول! قل: {kw}!","tablet_mode":"daily",
            "daily_emoji":emoji,"daily_label":label,
            "verify":"speech_keyword","keyword":kw,"tokens":5,"joy":"احتفال",
            "prompts":[f"قل {kw}!","بصوت واضح!","اضغط الميكروفون!"]})
    random.shuffle(pool)
    log.info(f"✅ تم توليد {len(pool)} مهمة عربية")
    return pool

log.info("🎯 توليد المهام...")
TASK_POOL = generate_pool()
SESSION_HISTORY = deque(maxlen=400)
MAX_FAILS = 2

# ══════════════════════════════════════════════════════════════════
# الحالة المشتركة
# ══════════════════════════════════════════════════════════════════
ST={
    "name":CHILD_NAME,"age":int(CHILD_AGE) if CHILD_AGE.isdigit() else 6,
    "score":0,"tokens":0,"streak":0,"consecutive":0,"mastered":0,
    "conv_level":1,"domain":"حركي","protocol":"ABA-DTT",
    "emotion":"محايد",
    "emotion_pct":{k:0 for k in ["سعيد","بهجة","مندهش","حزين","غاضب","خائف","محايد"]},
    "face_detected":False,"attention":70,
    "finger_count":0,"finger_target":1,
    "lip_motion":0.0,"lip_speaking":False,"lip_sync_value":0.0,
    "is_speaking":False,"interrupt_flag":False,
    "pecs_interrupt":False,"listening":False,"recording":False,"mic_level":0.0,
    "tasks_success":0,"tasks_fail":0,"tasks_skipped":0,
    "instant_success":False,"tablet_click_result":None,
    "_task_start_time":0.0,"_current_task_keyword":"","_fail_count":0,
    "session_chat":[],"logs":[],"pecs_log":[],"resp_times":[],
    "skill_حركي":50,"skill_معرفي":50,"skill_لفظي":50,
    "skill_رياضيات":50,"skill_اجتماعي":50,"skill_يومي":50,
    "body_motion":0.0,"clapping":False,"waving":False,
    "hand_raised":False,"hands_up":False,"arms_out":False,
    "pose_landmarks":{},"face_mesh_landmarks":{},
    "social_joy_active":False,"blinking":False,"head_tilt":0.0,
    "verify_action":None,"verify_result":False,"verify_timeout":0.0,
    "session_date":datetime.now().strftime("%Y-%m-%d"),
    "session_start":datetime.now().strftime("%H:%M"),
    "quick_action":None,
}

def LOG(msg,t="info"):
    e={"time":datetime.now().strftime("%H:%M:%S"),"msg":str(msg)[:120],"type":t}
    ST["logs"].append(e)
    if len(ST["logs"])>600: ST["logs"]=ST["logs"][-600:]
    if t=="success": log.info(f"✅ {msg[:60]}")
    elif t=="fail":  log.warning(f"❌ {msg[:60]}")

def get_next_task():
    recent=set(SESSION_HISTORY)
    cands=[t for t in TASK_POOL if t.get("base_id","") not in recent]
    if not cands: SESSION_HISTORY.clear(); cands=TASK_POOL
    cl=ST["conv_level"]
    if cl==1:   filt=[t for t in cands if t["domain"] in ["حركي","يومي"]]
    elif cl==2: filt=[t for t in cands if t["domain"] in ["حركي","معرفي","رياضيات","يومي","لفظي"]]
    else:       filt=cands
    task=random.choice(filt if filt else cands)
    SESSION_HISTORY.append(task.get("base_id",""))
    ST["_task_start_time"]=time.time()
    return task


# ══════════════════════════════════════════════════════════════════
# PyBullet Watchdog
# ══════════════════════════════════════════════════════════════════
_PB_AR = r"""
import sys,os,time,math,json,select
os.environ["TF_CPP_MIN_LOG_LEVEL"]="3"
try:
    import pybullet as p,pybullet_data
    sys.path.insert(0,os.path.expanduser("~/pepper_duo/src"))
    from qibullet import SimulationManager
except Exception as e:
    print(f"PB_ERROR:{e}",flush=True); sys.exit(0)
child=sys.argv[1] if len(sys.argv)>1 else "الطفل"
qisim=SimulationManager()
client=qisim.launchSimulation(gui=True)
p.setRealTimeSimulation(1); p.setGravity(0,0,-9.81)
p.setAdditionalSearchPath(pybullet_data.getDataPath())
p.loadURDF("plane.urdf")
wc=[0.92,0.92,0.96,1]
for pos,ext in [([0,-4,1.1],[5,.1,1.1]),([0,4,1.1],[5,.1,1.1]),
                ([5,0,1.1],[.1,4,1.1]),([-5,0,1.1],[.1,4,1.1])]:
    p.createMultiBody(0,-1,p.createVisualShape(p.GEOM_BOX,halfExtents=ext,rgbaColor=wc),pos)
p.createMultiBody(0,-1,p.createVisualShape(p.GEOM_BOX,halfExtents=[4.5,3.5,.02],
    rgbaColor=[.65,.55,.40,1]),[0,0,.01])
for txt,pos,col in [
    ("ABA حركي",[-3.5,3,0.05],[1,.3,.3,1]),("TEACCH بصري",[3.5,3,0.05],[.3,.7,1,1]),
    ("DTT لفظي",[0,3.8,0.05],[.3,1,.5,1]),("ESDM اجتماعي",[-3.5,-3,0.05],[1,.8,.2,1]),
    ("TIE يومي",[3.5,-3,0.05],[.8,.3,1,1]),(f"نجم {child}",[0,0,3.2],[.4,.5,.9,1])]:
    p.addUserDebugText(txt,pos,col[:3],textSize=1.2,lifeTime=0)
pepper=qisim.spawnPepper(client)
pepper.goToPosture("Stand",0.5)
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
    p.stepSimulation()
    now=time.time()
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
                pepper.setAngles("LShoulderPitch",0.05+0.3*abs(math.sin(jt*4)),.25)
                pepper.setAngles("RShoulderPitch",0.05+0.3*abs(math.sin(jt*4+math.pi)),.25)
                pepper.setAngles("LElbowRoll",-0.3*abs(math.sin(jt*3)),.2)
                pepper.setAngles("RElbowRoll",0.3*abs(math.sin(jt*3)),.2)
            else:
                pepper.setAngles("LShoulderPitch",1.,.04)
                pepper.setAngles("RShoulderPitch",1.,.04)
                pepper.setAngles("HeadYaw",float(st.get("ht",0))*0.5,.03)
        except: pass
    t_=time.time()
    rx+=.012*math.cos(t_*.35); ry+=.012*math.sin(t_*.42)
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
        threading.Thread(target=self._supervise,daemon=True).start()
    def _launch(self):
        try:
            self._proc=subprocess.Popen([sys.executable,"-c",_PB_AR,self.child],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,text=True,bufsize=1)
            dl=time.time()+30
            while time.time()<dl:
                try:
                    ln=self._proc.stdout.readline()
                    if "PYBULLET_READY" in ln:
                        self._ready=True; log.info("✅ محاكاة بيبر تعمل!"); return True
                    if "PB_ERROR" in ln: return False
                except: return False
                time.sleep(0.1)
        except Exception as e: log.warning(f"PyBullet: {e}")
        return False
    def _supervise(self):
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

# ══════════════════════════════════════════════════════════════════
# جسر الإشارات
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
    sig_rec_start=pyqtSignal()
    sig_rec_stop=pyqtSignal(str)
    sig_mic_lvl =pyqtSignal(float)
    sig_pecs    =pyqtSignal(str)
BRIDGE=Bridge()

# ══════════════════════════════════════════════════════════════════
# خيط الكاميرا — MediaPipe كامل
# ══════════════════════════════════════════════════════════════════
EMOTION_MAP={
    "happy":"سعيد","joyful":"بهجة","surprised":"مندهش",
    "sad":"حزين","angry":"غاضب","fear":"خائف","neutral":"محايد"
}
EMO_COLORS={
    "سعيد":(0,220,80),"بهجة":(0,255,180),"حزين":(100,100,220),
    "غاضب":(255,60,60),"خائف":(0,180,220),"مندهش":(200,50,220),"محايد":(180,180,180)
}

class CameraThread(QThread):
    def __init__(self):
        super().__init__(); self.running=False; self.cap=None
        self._mutex=QMutex()
        self._pose=None; self._hands=None; self._face=None
        self._phase=0.0; self._prev_gray=None
        self._hand_hist=[]; self._motion_buf=[]
        self._emo_sm={k:0.0 for k in ["happy","joyful","sad","angry","fear","surprised","neutral"]}
        self._lip_hist=deque(maxlen=8); self._prev_mh=0.0
        self._init_mp(); self._init_cam()

    def _init_mp(self):
        os.environ["CUDA_VISIBLE_DEVICES"]=""
        try:
            self._pose=mp.solutions.pose.Pose(
                min_detection_confidence=0.55,min_tracking_confidence=0.55,model_complexity=1)
            log.info("✅ MediaPipe Pose — الهيكل العظمي")
        except: pass
        try:
            self._hands=mp.solutions.hands.Hands(
                max_num_hands=2,min_detection_confidence=0.60,min_tracking_confidence=0.60)
            log.info("✅ MediaPipe Hands — عدّ الأصابع")
        except: pass
        try:
            self._face=mp.solutions.face_mesh.FaceMesh(
                max_num_faces=1,min_detection_confidence=0.5,
                min_tracking_confidence=0.5,refine_landmarks=True)
            log.info("✅ MediaPipe FaceMesh — المشاعر + الشفاه")
        except: pass
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
                        c.set(cv2.CAP_PROP_FPS,30)
                        self.cap=c; log.info(f"✅ الكاميرا {idx}"); return
                    c.release()
            except: pass
        log.warning("لا توجد كاميرا")

    def _count_fingers(self,lm,label):
        tips=[8,12,16,20]; count=0
        if label=="Left":
            if lm[4].x>lm[3].x: count+=1
        else:
            if lm[4].x<lm[3].x: count+=1
        for tip in tips:
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
            mar=(math.dist((ul.x*w,ul.y*h),(ll.x*w,ll.y*h))/
                 (math.dist((lc.x*w,lc.y*h),(rc.x*w,rc.y*h))+1e-6))
            lb=lm[107]; le=lm[159]; rb=lm[336]; re_=lm[386]
            brow=((lb.y-le.y)+(rb.y-re_.y))/2.0
            lch=lm[116]; rch=lm[345]; nose=lm[4]
            cheek=((lch.y+rch.y)/2.0-nose.y)*h
            sc={k:0.0 for k in self._emo_sm}
            sc["happy"]=min(1.0,max(0,(mar-0.20)*3.5)*(1 if cheek<-3 else 0.5))
            sc["joyful"]=min(1.0,max(0,(mar-0.25)*2.5))
            sc["surprised"]=min(1.0,max(0,(0.22-ea)*8))
            sc["angry"]=min(1.0,max(0,brow*30)*max(0,(0.25-mar)*4))
            sc["sad"]=min(1.0,max(0,brow*20)*max(0,(0.30-mar)*3))
            sc["fear"]=min(1.0,max(0,(0.22-ea)*5)*max(0,(0.25-mar)*3))
            total=sum(sc.values()) or 1e-6
            for k in sc: sc[k]/=total
            sc["neutral"]=max(0.0,1.0-sum(sc[k] for k in sc if k!="neutral"))
            total2=sum(sc.values()) or 1e-6
            for k in sc: sc[k]/=total2
            for k in self._emo_sm:
                self._emo_sm[k]=0.80*self._emo_sm[k]+0.20*sc.get(k,0)
            mouth_h=mar*(h*0.05)
            lip_d=abs(mouth_h-self._prev_mh); self._prev_mh=mouth_h
            self._lip_hist.append(lip_d)
            avg_lip=sum(self._lip_hist)/max(len(self._lip_hist),1)
            ST["lip_motion"]=float(avg_lip)
            ST["lip_speaking"]=avg_lip>0.50
            dom=max(self._emo_sm,key=self._emo_sm.get)
            pct={EMOTION_MAP.get(k,k):int(v*100) for k,v in self._emo_sm.items()}
            return EMOTION_MAP.get(dom,"محايد"),pct,mar
        except:
            return "محايد",{k:0 for k in EMOTION_MAP.values()},0.0

    def _sim_frame(self):
        f=np.zeros((480,640,3),dtype=np.uint8); f[:]=(10,12,28)
        cv2.putText(f,"لا توجد كاميرا — وضع المحاكاة",
            (60,240),cv2.FONT_HERSHEY_SIMPLEX,0.75,(100,200,255),2)
        return f

    def run(self):
        self.running=True; fc=0
        while self.running:
            if self.cap and self.cap.isOpened():
                ret,frame=self.cap.read()
                if not ret or frame is None: frame=self._sim_frame()
                else: frame=cv2.flip(frame,1)
            else:
                frame=self._sim_frame()
            fc+=1
            # حركة
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
            # Pose
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
                        ST["pose_landmarks"]={
                            "l_shoulder_y":lm[PL.LEFT_SHOULDER].y,
                            "r_shoulder_y":lm[PL.RIGHT_SHOULDER].y,
                            "l_wrist_y":lm[PL.LEFT_WRIST].y,
                            "r_wrist_y":lm[PL.RIGHT_WRIST].y,
                        }
                        pl=ST["pose_landmarks"]
                        ST["hand_raised"]=(pl["l_wrist_y"]<pl["l_shoulder_y"]-0.07 or
                                           pl["r_wrist_y"]<pl["r_shoulder_y"]-0.07)
                        ST["hands_up"]=(pl["l_wrist_y"]<pl["l_shoulder_y"]-0.07 and
                                        pl["r_wrist_y"]<pl["r_shoulder_y"]-0.07)
                        ST["face_detected"]=True
                        ST["attention"]=min(100,ST["attention"]+1)
                except: pass
            # FaceMesh
            if self._face and fc%3==0:
                try:
                    rgb=cv2.cvtColor(frame,cv2.COLOR_BGR2RGB)
                    fres=self._face.process(rgb)
                    if fres.multi_face_landmarks:
                        h_,w_=frame.shape[:2]
                        fl=fres.multi_face_landmarks[0].landmark
                        em,pct,mar=self._emotion_geo(fl,w_,h_)
                        ST["emotion"]=em; ST["emotion_pct"]=pct
                        ST["face_detected"]=True
                        ST["attention"]=min(100,ST["attention"]+2)
                        ST["head_tilt"]=fl[1].x-0.5
                        # رسم الشفاه
                        lip_col=(0,255,200) if ST["lip_speaking"] else (80,80,180)
                        lip_ids=[61,185,40,39,37,0,267,269,270,409,291,
                                  146,91,181,84,17,314,405,321,375,291]
                        pts=np.array([(int(fl[i].x*w_),int(fl[i].y*h_))
                                      for i in lip_ids],np.int32)
                        cv2.polylines(frame,[pts],True,lip_col,2)
                    else:
                        ST["face_detected"]=False
                        ST["attention"]=max(0,ST["attention"]-2)
                        ST["lip_motion"]=0.0; ST["lip_speaking"]=False
                except: pass
            # Hands
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
                            fc_n=self._count_fingers(hlm.landmark,label)
                            total+=fc_n
                            wrist=hlm.landmark[0]; h_,w_=frame.shape[:2]
                            wx,wy=int(wrist.x*w_),int(wrist.y*h_)
                            cv2.putText(frame,f"{label[0]}:{fc_n}",
                                (wx-20,wy+25),cv2.FONT_HERSHEY_SIMPLEX,0.6,(255,255,0),2)
                        ST["finger_count"]=min(10,total)
                        if len(hres.multi_hand_landmarks)>=2:
                            h1=hres.multi_hand_landmarks[0].landmark[0]
                            h2_=hres.multi_hand_landmarks[1].landmark[0]
                            if abs(h1.x-h2_.x)<0.18 and abs(h1.y-h2_.y)<0.18:
                                ST["clapping"]=True
                    else: ST["finger_count"]=0
                except: pass
            # تحقق حركي
            va=ST.get("verify_action")
            if va and time.time()<=ST.get("verify_timeout",0):
                ok=False
                if va=="clap":      ok=ST.get("clapping",False)
                elif va=="wave":    ok=ST.get("waving",False)
                elif va=="raise_hand": ok=ST.get("hand_raised",False)
                elif va=="hands_up":   ok=ST.get("hands_up",False)
                elif va=="jump":    ok=ST.get("body_motion",0)>30
                elif va=="finger_count": ok=(ST["finger_count"]==ST["finger_target"])
                elif va in ["arms_out","touch_nose","point"]: ok=ST.get("body_motion",0)>5
                if ok:
                    ST["verify_result"]=True; ST["verify_action"]=None
                    ST["instant_success"]=True; LOG("✅ تحقق حركي","success")
            # HUD
            h_,w_=frame.shape[:2]
            cv2.rectangle(frame,(0,0),(w_,50),(8,10,24),-1)
            cv2.putText(frame,
                f"{'★'*ST['consecutive']}{'☆'*(3-ST['consecutive'])} | {ST['emotion']} | M{ST['conv_level']}",
                (8,20),cv2.FONT_HERSHEY_SIMPLEX,0.48,(255,220,0),1)
            cv2.putText(frame,
                f"نقاط:{ST['score']} | انتباه:{ST['attention']}% | أصابع:{ST['finger_count']}/10 | {'👄كلام' if ST['lip_speaking'] else '·'}",
                (8,40),cv2.FONT_HERSHEY_SIMPLEX,0.38,(200,200,200),1)
            if ST["recording"]: cv2.circle(frame,(w_-18,18),8,(0,0,255),-1)
            # إرسال
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
# مسجل اللمس — Whisper ASR عربي
# ══════════════════════════════════════════════════════════════════
class TouchRecorder:
    def __init__(self):
        self._lock=threading.Lock(); self._recording=False; self._audio=None
        self.whisper=None
        self.r=sr.Recognizer()
        self.r.energy_threshold=200; self.r.dynamic_energy_threshold=True
        self.r.pause_threshold=0.9; self.r.non_speaking_duration=0.5
        try:
            with sr.Microphone() as src:
                log.info("🎤 معايرة الميكروفون...")
                self.r.adjust_for_ambient_noise(src,duration=1.2)
            log.info(f"✅ الميكروفون جاهز (طاقة={self.r.energy_threshold:.0f})")
        except Exception as e: log.warning(f"الميكروفون: {e}")
        if _FW:
            try:
                self.whisper=FW("base",device="cpu",compute_type="int8")
                log.info("✅ Whisper-base جاهز (عربي + إنجليزي)")
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
                self.r.adjust_for_ambient_noise(src,duration=0.15)
                audio=self.r.listen(src,timeout=15,phrase_time_limit=12)
                raw=np.frombuffer(audio.get_raw_data(),dtype=np.int16).astype(np.float32)
                ST["mic_level"]=min(1.0,float(np.sqrt(np.mean(raw**2)))/5000.0)
                BRIDGE.sig_mic_lvl.emit(ST["mic_level"])
                with self._lock: self._audio=audio
        except Exception as e: log.warning(f"تسجيل: {e}")
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
                for lang in ["ar","en"]:
                    segs,_=self.whisper.transcribe(tp,language=lang,beam_size=5,
                        temperature=0.0,no_speech_threshold=0.4,
                        condition_on_previous_text=False)
                    text=" ".join(s.text.strip() for s in segs).strip()
                    if text: break
                try: os.unlink(tp)
                except: pass
                if text:
                    log.info(f"Whisper: '{text}'"); self._check(text); return text
            except Exception as e: log.warning(f"Whisper: {e}")
        try:
            text=self.r.recognize_google(audio,language="ar-SA")
            self._check(text); return text
        except sr.UnknownValueError: pass
        except: pass
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
        if (len(kw)>=2 and len(t)>=2 and
                (kw[:2]==t[:2] or kw[-2:]==t[-2:]) and ST.get("lip_speaking")):
            ST["instant_success"]=True


# ══════════════════════════════════════════════════════════════════
# بطاقات الاختيار + أفاتار بيبر + PECS
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
            self.setText(f"\n\n{d['label']}")
            self.setFont(QFont("Arial",11,QFont.Weight.Bold))
            self.setStyleSheet(f"QPushButton{{background:{d['color']};border-radius:75px;"
                f"border:5px solid rgba(255,255,255,0.3);color:white;font-weight:bold;}}"
                f"QPushButton:hover{{border:5px solid white;}}")
        else:
            self.setText(f"{d.get('emoji','?')}\n{d['label']}")
            self.setFont(QFont("Arial",13,QFont.Weight.Bold))
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
        blink=ST.get("blinking",False) or (int(self._phase*3)%44==0)
        ht=ST.get("head_tilt",0.0)*5; cx,cy=100,120
        g=QLinearGradient(cx-40,cy+45,cx+40,cy+120)
        g.setColorAt(0,QColor(70,90,190)); g.setColorAt(1,QColor(50,70,160))
        p.setBrush(QBrush(g)); p.setPen(QPen(QColor(100,120,210),2))
        p.drawEllipse(cx-40,cy+45,80,75)
        p.setBrush(QBrush(QColor(20,24,50))); p.setPen(QPen(QColor(79,70,229),2))
        p.drawRoundedRect(cx-22,cy+55,44,32,4,4)
        p.setPen(QColor(167,139,250)); p.setFont(QFont("Arial",6,QFont.Weight.Bold))
        p.drawText(QRect(cx-20,cy+60,40,16),Qt.AlignmentFlag.AlignCenter,"بيبر V6")
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
        p.drawLine(cx-16,cy+118,cx-24,cy+152); p.drawLine(cx+16,cy+118,cx+24,cy+152)
        hbob=int(3*math.sin(self._phase*0.5)); hx=cx+int(ht); hy=cy-46+hbob
        p.setBrush(QBrush(QColor(220,195,173))); p.setPen(QPen(QColor(200,175,155),2))
        p.drawEllipse(hx-40,hy-40,80,80)
        ec=QColor(100,255,180) if (em in ["سعيد","بهجة"] or sj) else (
           QColor(255,80,80) if em=="غاضب" else
           QColor(100,120,220) if em=="حزين" else QColor(100,180,255))
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
        elif em in ["سعيد","بهجة"]:
            p.setBrush(QBrush(QColor(150,80,80))); p.drawChord(hx-10,hy+15,20,12,0,-180*16)
        elif em=="حزين":
            p.setBrush(Qt.BrushStyle.NoBrush); p.drawArc(hx-10,hy+20,20,12,0,180*16)
        else:
            p.drawLine(hx-10,hy+18,hx+10,hy+18)
        p.setBrush(QBrush(QColor(210,185,163))); p.setPen(Qt.PenStyle.NoPen)
        for ex_ in [hx-40,hx+32]: p.drawEllipse(ex_,hy-8,14,14)
        if sj:
            jt2=time.time(); pr=int(75+11*abs(math.sin(jt2*4)))
            p.setPen(QPen(QColor(int(128+127*math.sin(jt2*3)),200,255),3))
            p.setBrush(Qt.BrushStyle.NoBrush); p.drawEllipse(cx-pr,cy-pr,pr*2,pr*2)
        p.setPen(QColor(0,200,255)); p.setFont(QFont("Arial",7,QFont.Weight.Bold))
        p.drawText(QRect(0,2,200,14),Qt.AlignmentFlag.AlignCenter,f"مستوى M{ST['conv_level']}")
        status=("فرح 🎉" if sj else "يتكلم 🔊" if ST["is_speaking"]
                else "يسجل 🔴" if ST["recording"] else "جاهز 💤")
        p.setPen(QColor(160,140,255)); p.setFont(QFont("Arial",7,QFont.Weight.Bold))
        p.drawText(QRect(0,228,200,20),Qt.AlignmentFlag.AlignCenter,status)
        p.end()

class EmotionPanel(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent); self.setFixedSize(200,260)
        self._t=QTimer(); self._t.timeout.connect(self.update); self._t.start(250)
    def paintEvent(self,event):
        p=QPainter(self); p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.fillRect(self.rect(),QColor(10,12,28))
        p.setPen(QColor(0,200,255)); p.setFont(QFont("Arial",8,QFont.Weight.Bold))
        p.drawText(QRect(0,2,200,14),Qt.AlignmentFlag.AlignCenter,"كشف المشاعر المباشر")
        em=ST["emotion"]; col=QColor(*EMO_COLORS.get(em,(180,180,180)))
        p.setBrush(QBrush(col)); p.setPen(QPen(QColor(255,255,255),2))
        p.drawEllipse(70,18,60,60)
        emojis={"سعيد":"😊","بهجة":"😄","حزين":"😢","غاضب":"😠",
                "خائف":"😨","مندهش":"😲","محايد":"😐"}
        p.setPen(QColor(255,255,255)); p.setFont(QFont("Arial",7,QFont.Weight.Bold))
        p.drawText(QRect(70,18,60,60),Qt.AlignmentFlag.AlignCenter,
                   f"{emojis.get(em,'😐')}\n{em}")
        pct=ST.get("emotion_pct",{}); y0=90
        for em_ in list(EMO_COLORS.keys()):
            val=pct.get(em_,0); bar=int(val*1.3)
            ec_=QColor(*EMO_COLORS.get(em_,(150,150,150)))
            p.setBrush(QBrush(QColor(22,25,45))); p.setPen(Qt.PenStyle.NoPen)
            p.drawRoundedRect(4,y0,130,12,3,3)
            if bar>0: p.setBrush(QBrush(ec_)); p.drawRoundedRect(4,y0,bar,12,3,3)
            p.setPen(QColor(200,200,200)); p.setFont(QFont("Arial",7))
            p.drawText(QRect(138,y0,58,12),Qt.AlignmentFlag.AlignLeft|Qt.AlignmentFlag.AlignVCenter,
                       f"{em_} {val}%")
            y0+=18
        ml=ST.get("lip_motion",0.0); lmw=min(int(ml*40),190)
        p.setBrush(QBrush(QColor(22,25,45))); p.setPen(Qt.PenStyle.NoPen)
        p.drawRoundedRect(5,220,190,9,4,4)
        if lmw>0:
            p.setBrush(QBrush(QColor(0,255,200) if ST["lip_speaking"] else QColor(100,100,200)))
            p.drawRoundedRect(5,220,lmw,9,4,4)
        p.setPen(QColor(200,200,200)); p.setFont(QFont("Arial",7))
        p.drawText(QRect(0,232,200,13),Qt.AlignmentFlag.AlignCenter,
                   f"👄{'كلام' if ST['lip_speaking'] else 'صامت'} | أصابع:{ST['finger_count']}/10")
        p.end()

class PECSWidget(QWidget):
    def __init__(self,parent=None):
        super().__init__(parent); self.setFixedHeight(90)
        self.setStyleSheet("QWidget{background:#0c0f1e;border-top:2px solid #1a1f40;}")
        outer=QHBoxLayout(self); outer.setContentsMargins(4,3,4,3); outer.setSpacing(4)
        t=QLabel("بطاقات PECS — 50 بطاقة"); t.setFont(QFont("Arial",7,QFont.Weight.Bold))
        t.setStyleSheet("color:#a78bfa;"); outer.addWidget(t)
        scroll=QScrollArea(); scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        scroll.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll.setFixedHeight(82)
        scroll.setStyleSheet("QScrollArea{border:none;background:transparent;}")
        inner=QWidget(); inner_lay=QHBoxLayout(inner)
        inner_lay.setContentsMargins(2,2,2,2); inner_lay.setSpacing(4)
        for iid,emoji,label,kw,cat in PECS_AR:
            btn=QPushButton(f"{emoji}\n{label[:8]}")
            btn.setFont(QFont("Arial",6,QFont.Weight.Bold)); btn.setFixedSize(70,72)
            btn.setStyleSheet("QPushButton{background:#1e1b4b;border:2px solid #4f46e5;"
                "border-radius:8px;color:#e0e6ff;}"
                "QPushButton:hover{background:#2e2b6e;border-color:#a78bfa;}"
                "QPushButton:pressed{background:#3e3b8e;}")
            btn.setToolTip(f"قل: {kw}")
            btn.clicked.connect(lambda _,k=kw,lb=label,em=emoji: self._press(lb,k,em))
            inner_lay.addWidget(btn)
        scroll.setWidget(inner); outer.addWidget(scroll,1)

    def _press(self,label,kw,emoji):
        ST["pecs_log"].append({"time":datetime.now().strftime("%H:%M:%S"),
            "name":label,"phrase":kw,"emotion":ST["emotion"]})
        if len(ST["pecs_log"])>100: ST["pecs_log"]=ST["pecs_log"][-100:]
        LOG(f"PECS:{label}={kw}")
        BRIDGE.sig_pecs.emit(kw)
        if VOICE_REF: VOICE_REF.say_pecs(f"{CHILD_NAME} يقول: {kw}",ST)


# ══════════════════════════════════════════════════════════════════
# النافذة الرئيسية
# ══════════════════════════════════════════════════════════════════
class MainWindowAR(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle(f"🤖 بيبر كلينيكال V6 — {CHILD_NAME}")
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
        # يسار
        left=QFrame(); left.setFixedWidth(780)
        left.setStyleSheet("QFrame{background:#0a0d1e;border-right:2px solid #1a1f40;}")
        ll=QVBoxLayout(left); ll.setContentsMargins(0,0,0,0); ll.setSpacing(0)
        top_row=QWidget(); tr=QHBoxLayout(top_row); tr.setContentsMargins(0,0,0,0); tr.setSpacing(0)
        self.cam_lbl=QLabel(); self.cam_lbl.setFixedSize(580,520)
        self.cam_lbl.setStyleSheet("background:#000;"); self.cam_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        tr.addWidget(self.cam_lbl)
        side=QWidget(); side.setFixedWidth(200)
        sl=QVBoxLayout(side); sl.setContentsMargins(0,0,0,0); sl.setSpacing(0)
        self.avatar=AvatarWidget(); sl.addWidget(self.avatar)
        self.emo_panel=EmotionPanel(); sl.addWidget(self.emo_panel)
        tr.addWidget(side); ll.addWidget(top_row)
        sr_=QWidget(); srl=QHBoxLayout(sr_); srl.setContentsMargins(6,3,6,3); srl.setSpacing(6)
        self.finger_lbl=QLabel(f"👦{CHILD_NAME}|أصابع:0|محايد|M1")
        self.finger_lbl.setFont(QFont("Arial",9,QFont.Weight.Bold))
        self.finger_lbl.setStyleSheet("color:#fbbf24;"); srl.addWidget(self.finger_lbl,1)
        ll.addWidget(sr_)
        self.lip_bar=QProgressBar(); self.lip_bar.setFixedHeight(7)
        self.lip_bar.setRange(0,100); self.lip_bar.setValue(0); self.lip_bar.setTextVisible(False)
        self.lip_bar.setStyleSheet("QProgressBar{background:#1a1f40;border:none;border-radius:3px;}"
            "QProgressBar::chunk{background:#00ffc8;border-radius:3px;}"); ll.addWidget(self.lip_bar)
        self.resp_lbl=QLabel("⏱ زمن الاستجابة: — | الدقة: —")
        self.resp_lbl.setFont(QFont("Arial",8))
        self.resp_lbl.setStyleSheet("color:#60a5fa;padding:2px;background:#07090f;")
        self.resp_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); ll.addWidget(self.resp_lbl)
        ch_lbl=QLabel("💬 محادثة بيبر | Piper TTS عربي + Whisper AI + كشف الشفاه")
        ch_lbl.setFont(QFont("Arial",8,QFont.Weight.Bold))
        ch_lbl.setStyleSheet("color:#a78bfa;background:#0c0f1e;padding:2px;")
        ch_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); ll.addWidget(ch_lbl)
        self.chat_area=QTextEdit(); self.chat_area.setReadOnly(True)
        self.chat_area.setFont(QFont("Arial",9))
        self.chat_area.setStyleSheet("QTextEdit{background:#07090f;color:#e0e6ff;border:1px solid #1a1f40;padding:4px;}")
        self.chat_area.setFixedHeight(90); ll.addWidget(self.chat_area)
        cir=QWidget(); cirow=QHBoxLayout(cir); cirow.setContentsMargins(4,2,4,2); cirow.setSpacing(4)
        self.chat_input=QLineEdit()
        self.chat_input.setPlaceholderText("اكتب رسالة للمعالج أو سؤالاً عن العلاج… (Enter)")
        self.chat_input.setFont(QFont("Arial",10))
        self.chat_input.setStyleSheet("QLineEdit{background:#0c0f1e;color:#e0e6ff;border:2px solid #4f46e5;border-radius:8px;padding:5px;}")
        self.chat_input.setFixedHeight(34); self.chat_input.returnPressed.connect(self._send_chat)
        cirow.addWidget(self.chat_input,1)
        sb2=QPushButton("إرسال"); sb2.setFixedSize(70,34)
        sb2.setStyleSheet("QPushButton{background:#4f46e5;color:white;border-radius:8px;font-weight:bold;}")
        sb2.clicked.connect(self._send_chat); cirow.addWidget(sb2); ll.addWidget(cir)
        main.addWidget(left)
        # يمين
        right=QWidget(); right.setFixedWidth(820)
        rl=QVBoxLayout(right); rl.setSpacing(5); rl.setContentsMargins(10,6,10,6)
        hdr=QFrame(); hdr.setFixedHeight(64)
        hdr.setStyleSheet("QFrame{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #1a0a3d,stop:0.5 #0a0f28,stop:1 #1a0a3d);"
            "border-radius:12px;border:2px solid #4f46e5;}")
        hl=QHBoxLayout(hdr); hl.setContentsMargins(12,4,12,4)
        av_lbl=QLabel("🤖"); av_lbl.setFont(QFont("Arial",22)); av_lbl.setStyleSheet("color:#a78bfa;"); hl.addWidget(av_lbl)
        tw_=QWidget(); tl2=QVBoxLayout(tw_); tl2.setSpacing(1)
        self.title_lbl=QLabel("بيبر كلينيكال إنفينيتي V6 — صوت Piper العربي")
        self.title_lbl.setFont(QFont("Arial",13,QFont.Weight.Bold)); self.title_lbl.setStyleSheet("color:#a78bfa;")
        tl2.addWidget(self.title_lbl)
        self.child_lbl=QLabel(f"طفل:{CHILD_NAME} | ABA/DTT/TEACCH/ESDM/TIE | 5200+ مهمة | 50 PECS")
        self.child_lbl.setFont(QFont("Arial",8)); self.child_lbl.setStyleSheet("color:#60a5fa;")
        tl2.addWidget(self.child_lbl); hl.addWidget(tw_,1)
        sw_=QWidget(); sl_=QVBoxLayout(sw_); sl_.setSpacing(1)
        self.state_lbl=QLabel("💤 جاهز"); self.state_lbl.setFont(QFont("Arial",8))
        self.state_lbl.setStyleSheet("color:#9ca3af;")
        sl_.addWidget(self.state_lbl,alignment=Qt.AlignmentFlag.AlignRight)
        self.clvl_lbl=QLabel("مستوى M1"); self.clvl_lbl.setFont(QFont("Arial",8))
        self.clvl_lbl.setStyleSheet("color:#34d399;")
        sl_.addWidget(self.clvl_lbl,alignment=Qt.AlignmentFlag.AlignRight)
        hl.addWidget(sw_); rl.addWidget(hdr)
        sched=QFrame(); sched.setFixedHeight(48)
        sched.setStyleSheet("QFrame{background:#0c0f1e;border-radius:10px;border:1px solid #1a1f40;}")
        sc=QHBoxLayout(sched); sc.setContentsMargins(10,4,10,4); sc.setSpacing(7)
        self.sched_task=QLabel("📋 المهمة")
        self.sched_task.setFont(QFont("Arial",9,QFont.Weight.Bold))
        self.sched_task.setStyleSheet("color:#a78bfa;background:#1e1b4b;border-radius:7px;padding:3px 8px;border:2px solid #4f46e5;")
        sc.addWidget(self.sched_task)
        sw2=QWidget(); sl2_=QVBoxLayout(sw2); sl2_.setSpacing(0); sl2_.setContentsMargins(0,0,0,0)
        self.stars_lbl=QLabel("☆ ☆ ☆"); self.stars_lbl.setFont(QFont("Arial",14))
        self.stars_lbl.setStyleSheet("color:#4b5563;"); self.stars_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl2_.addWidget(self.stars_lbl)
        self.mastery_sub=QLabel("0/3 | فشل:0/2"); self.mastery_sub.setFont(QFont("Arial",7))
        self.mastery_sub.setStyleSheet("color:#6b7280;"); self.mastery_sub.setAlignment(Qt.AlignmentFlag.AlignCenter)
        sl2_.addWidget(self.mastery_sub); sc.addWidget(sw2,1)
        self.reward_lbl=QLabel("⭐"); self.reward_lbl.setFont(QFont("Arial",18))
        self.reward_lbl.setStyleSheet("color:#fbbf24;background:#2a1a00;border-radius:7px;padding:2px 7px;border:2px solid #f59e0b;")
        sc.addWidget(self.reward_lbl); rl.addWidget(sched)
        if_fr=QFrame(); if_fr.setFixedHeight(74)
        if_fr.setStyleSheet("QFrame{background:qlineargradient(x1:0,y1:0,x2:0,y2:1,"
            "stop:0 #1e1b4b,stop:1 #0c0f2e);border-radius:10px;border:2px solid #4f46e5;}")
        il=QVBoxLayout(if_fr); il.setContentsMargins(12,3,12,3)
        self.instr_icon=QLabel("📋"); self.instr_icon.setFont(QFont("Arial",14))
        self.instr_icon.setAlignment(Qt.AlignmentFlag.AlignCenter); il.addWidget(self.instr_icon)
        self.instr_lbl=QLabel("بيبر يستعد…"); self.instr_lbl.setFont(QFont("Arial",13,QFont.Weight.Bold))
        self.instr_lbl.setStyleSheet("color:#e0e6ff;"); self.instr_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.instr_lbl.setWordWrap(True); il.addWidget(self.instr_lbl); rl.addWidget(if_fr)
        self.content_fr=QFrame(); self.content_fr.setMinimumHeight(280)
        self.content_fr.setStyleSheet("QFrame{background:rgba(12,15,30,0.90);border-radius:12px;border:2px solid #1a1f40;}")
        self.content_lay=QVBoxLayout(self.content_fr)
        self.content_lay.setContentsMargins(12,10,12,10); self.content_lay.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._show_idle(); rl.addWidget(self.content_fr,1)
        self.lock_ov=QLabel("🔒"); self.lock_ov.setParent(self.content_fr)
        self.lock_ov.setGeometry(0,0,800,280); self.lock_ov.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.lock_ov.setFont(QFont("Arial",44))
        self.lock_ov.setStyleSheet("QLabel{background:rgba(0,0,0,0.52);border-radius:12px;color:#a78bfa;}"); self.lock_ov.hide()
        fb_fr=QFrame(); fb_fr.setFixedHeight(48)
        fb_fr.setStyleSheet("QFrame{background:#0c0f1e;border-radius:10px;border:1px solid #1a1f40;}")
        fl=QHBoxLayout(fb_fr); fl.setContentsMargins(12,6,12,6)
        self.fb_icon=QLabel("💤"); self.fb_icon.setFont(QFont("Arial",19)); fl.addWidget(self.fb_icon)
        self.fb_lbl=QLabel("في انتظار بيبر…"); self.fb_lbl.setFont(QFont("Arial",11,QFont.Weight.Bold))
        self.fb_lbl.setStyleSheet("color:#9ca3af;"); self.fb_lbl.setWordWrap(True)
        fl.addWidget(self.fb_lbl,1); rl.addWidget(fb_fr)
        mic_row=QWidget(); mic_lay=QVBoxLayout(mic_row); mic_lay.setContentsMargins(0,0,0,0); mic_lay.setSpacing(3)
        self.mic_btn=QPushButton("🎤  اضغط مع الاستمرار للكلام — قل الكلمة!")
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
        self.rec_status=QLabel("🎤 Piper TTS عربي + Whisper AI + كشف الشفاه — جاهز!")
        self.rec_status.setFont(QFont("Arial",8)); self.rec_status.setStyleSheet("color:#6b7280;padding:1px;")
        self.rec_status.setAlignment(Qt.AlignmentFlag.AlignCenter); mic_lay.addWidget(self.rec_status); rl.addWidget(mic_row)
        sb_=QFrame(); sb_.setFixedHeight(40)
        sb_.setStyleSheet("QFrame{background:#07090f;border-radius:8px;border:1px solid #1a1f40;}")
        stl=QHBoxLayout(sb_); stl.setContentsMargins(8,2,8,2)
        for lbl,attr,col in [("النقاط","stat_score","#a78bfa"),("رموز","stat_tokens","#fbbf24"),
            ("متقن","stat_mastered","#34d399"),("متتالي","stat_streak","#60a5fa"),
            ("تخطي","stat_skipped","#f87171"),("يومي%","stat_daily","#34d399"),("⏱ms","stat_resp","#60a5fa")]:
            w_=QWidget(); wl_=QVBoxLayout(w_); wl_.setSpacing(0); wl_.setContentsMargins(0,0,0,0)
            val=QLabel("0"); val.setFont(QFont("Arial",10,QFont.Weight.Bold))
            val.setStyleSheet(f"color:{col};"); val.setAlignment(Qt.AlignmentFlag.AlignCenter)
            lb_=QLabel(lbl); lb_.setFont(QFont("Arial",6)); lb_.setStyleSheet("color:#6b7280;")
            lb_.setAlignment(Qt.AlignmentFlag.AlignCenter)
            wl_.addWidget(val); wl_.addWidget(lb_); stl.addWidget(w_); setattr(self,attr,val)
        rl.addWidget(sb_); main.addWidget(right)
        outer.addLayout(main)
        self.pecs=PECSWidget(); outer.addWidget(self.pecs)

    def _connect_bridge(self):
        BRIDGE.sig_task.connect(self._on_task)
        BRIDGE.sig_success.connect(lambda m: (self.fb_lbl.setText(f"✅ {m}"),self.fb_lbl.setStyleSheet("color:#22c55e;font-weight:bold;font-size:13px;"),self.fb_icon.setText("🎉")) or None)
        BRIDGE.sig_fail.connect(lambda m: (self.fb_lbl.setText(f"❌ {m}"),self.fb_lbl.setStyleSheet("color:#ef4444;font-weight:bold;"),self.fb_icon.setText("💪")) or None)
        BRIDGE.sig_skip.connect(lambda m: (self.fb_lbl.setText(f"⏭ {m}"),self.fb_lbl.setStyleSheet("color:#f59e0b;font-weight:bold;"),self.fb_icon.setText("⏩")) or None)
        BRIDGE.sig_instr.connect(lambda m: self.instr_lbl.setText(m))
        BRIDGE.sig_waiting.connect(lambda m: self.state_lbl.setText(m))
        BRIDGE.sig_unlock.connect(self._do_unlock); BRIDGE.sig_lock.connect(self._do_lock)
        BRIDGE.sig_reset.connect(self._reset_cards)
        BRIDGE.sig_joy.connect(lambda _: setattr(ST,"social_joy_active",True) or QTimer.singleShot(4000,lambda: ST.__setitem__("social_joy_active",False)))
        BRIDGE.sig_camera.connect(self._update_cam)
        BRIDGE.sig_stats.connect(self._refresh)
        BRIDGE.sig_chat.connect(self._add_chat)
        BRIDGE.sig_rec_stop.connect(self._on_rec_stop)
        BRIDGE.sig_mic_lvl.connect(lambda v: self.mic_wave.setValue(int(v*100)))
        BRIDGE.sig_pecs.connect(lambda ph: self._add_chat("طفل",f"[PECS] {ph}"))
        self._lip_t=QTimer(); self._lip_t.timeout.connect(lambda: self.lip_bar.setValue(min(100,int(ST.get("lip_motion",0)*40))))
        self._lip_t.start(100)

    def _update_cam(self,qimg):
        if isinstance(qimg,QImage):
            pix=QPixmap.fromImage(qimg).scaled(580,520,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation)
            self.cam_lbl.setPixmap(pix)
        fc=ST["finger_count"]; em=ST["emotion"]; cl=ST["conv_level"]
        self.finger_lbl.setText(f"👦{CHILD_NAME}|أصابع:{fc}|{em}|M{cl}|{'👄كلام' if ST['lip_speaking'] else '·'}|انتباه:{ST['attention']}%")

    def _refresh(self):
        self.stat_score.setText(str(ST["score"])); self.stat_tokens.setText(str(ST["tokens"]))
        self.stat_mastered.setText(str(ST["mastered"])); self.stat_streak.setText(str(ST["streak"]))
        self.stat_skipped.setText(str(ST["tasks_skipped"])); self.stat_daily.setText(f"{ST['skill_يومي']:.0f}%")
        rt=ST["resp_times"]
        if rt: self.stat_resp.setText(str(int(sum(rt[-10:])/len(rt[-10:]))))
        c=ST["consecutive"]
        self.stars_lbl.setText("★"*c+"☆"*(3-c)); self.stars_lbl.setStyleSheet("color:#fbbf24;" if c else "color:#4b5563;")
        self.mastery_sub.setText(f"{c}/3 | فشل:{ST.get('_fail_count',0)}/{MAX_FAILS}")
        self.reward_lbl.setText(f"⭐{ST['score']}"); self.clvl_lbl.setText(f"مستوى M{ST['conv_level']}")
        ok=ST["tasks_success"]; fa=ST["tasks_fail"]; rt2=ST["resp_times"]
        if rt2 and ok+fa>0:
            self.resp_lbl.setText(f"⏱ متوسط:{int(sum(rt2[-5:])/len(rt2[-5:]))}ms | ✅ دقة:{int(ok/(ok+fa)*100)}% | ✅{ok} ❌{fa}")

    def _show_idle(self):
        for i in reversed(range(self.content_lay.count())):
            w=self.content_lay.itemAt(i).widget()
            if w: w.setParent(None)
        lbl=QLabel("🤖\nبيبر جاهز!\nجاري التحضير..."); lbl.setFont(QFont("Arial",16,QFont.Weight.Bold))
        lbl.setStyleSheet("color:#4b5563;"); lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); self.content_lay.addWidget(lbl)

    def _clear(self):
        for i in reversed(range(self.content_lay.count())):
            w=self.content_lay.itemAt(i).widget()
            if w: w.setParent(None)
        self._cards=[]

    def _on_task(self,task:dict):
        if task.get("action")=="click": self._handle_click(task.get("idx",0)); return
        self._clear(); self._locked=True; self.lock_ov.hide()
        self.sched_task.setText(f"📋 {task.get('name','مهمة')[:22]}")
        mode=task.get("tablet_mode","")
        if mode=="motor":
            name_lbl=QLabel(task.get("name","")); name_lbl.setFont(QFont("Arial",20,QFont.Weight.Bold))
            name_lbl.setStyleSheet("color:#a78bfa;"); name_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); self.content_lay.addWidget(name_lbl)
            instr=QLabel(task.get("instruction","")); instr.setFont(QFont("Arial",14,QFont.Weight.Bold))
            instr.setStyleSheet("color:#e0e6ff;background:#1e1b4b;border-radius:12px;border:3px solid #4f46e5;padding:12px;")
            instr.setAlignment(Qt.AlignmentFlag.AlignCenter); instr.setWordWrap(True); self.content_lay.addWidget(instr)
            done_btn=QPushButton("✅ فعلتها! اضغط هنا"); done_btn.setFixedHeight(52)
            done_btn.setFont(QFont("Arial",13,QFont.Weight.Bold))
            done_btn.setStyleSheet("QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #059669,stop:1 #10b981);color:white;border-radius:26px;border:3px solid #6ee7b7;}QPushButton:pressed{background:#047857;}")
            done_btn.clicked.connect(lambda: ST.__setitem__("instant_success",True)); self.content_lay.addWidget(done_btn)
        elif mode=="grid":
            opts=task.get("options",[]); self._correct_idx=task.get("correct",0)
            grid=QWidget(); gl=QGridLayout(grid); gl.setSpacing(10); gl.setContentsMargins(8,8,8,8)
            for i,opt in enumerate(opts):
                card=ClickCard(opt,i,None); gl.addWidget(card,i//2,i%2); self._cards.append(card)
            self.content_lay.addWidget(grid); self._do_unlock()
        elif mode=="number":
            n=task.get("target_number",1)
            big=QLabel(str(n)); big.setFont(QFont("Arial",80,QFont.Weight.Bold))
            big.setStyleSheet("color:#22c55e;"); big.setAlignment(Qt.AlignmentFlag.AlignCenter); self.content_lay.addWidget(big)
            stars=QLabel("⭐"*n); stars.setFont(QFont("Arial",20)); stars.setWordWrap(True)
            stars.setAlignment(Qt.AlignmentFlag.AlignCenter); self.content_lay.addWidget(stars)
            hint=QLabel(f"أرني {n} أصابع! 🖐️"); hint.setFont(QFont("Arial",14,QFont.Weight.Bold))
            hint.setStyleSheet("color:#a78bfa;"); hint.setAlignment(Qt.AlignmentFlag.AlignCenter); self.content_lay.addWidget(hint)
        else:
            txt=(task.get("word_text") or task.get("social_text") or task.get("daily_label",""))
            emoji=task.get("daily_emoji","🗣️")
            em_lbl=QLabel(emoji); em_lbl.setFont(QFont("Arial",56)); em_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); self.content_lay.addWidget(em_lbl)
            word_lbl=QLabel(str(txt)); word_lbl.setFont(QFont("Arial",28,QFont.Weight.Bold))
            word_lbl.setStyleSheet("color:#a78bfa;background:#1e1b4b;border-radius:12px;border:3px solid #4f46e5;padding:8px 16px;")
            word_lbl.setAlignment(Qt.AlignmentFlag.AlignCenter); self.content_lay.addWidget(word_lbl)
            hint=QLabel("🎤 اضغط الميكروفون وقل الكلمة!"); hint.setFont(QFont("Arial",11))
            hint.setStyleSheet("color:#34d399;"); hint.setAlignment(Qt.AlignmentFlag.AlignCenter); self.content_lay.addWidget(hint)

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

    def _do_unlock(self): self._locked=False; self.lock_ov.hide(); [c.setEnabled(True) for c in self._cards]
    def _do_lock(self):   self._locked=True;  self.lock_ov.show(); [c.setEnabled(False) for c in self._cards]
    def _reset_cards(self): [c.reset() for c in self._cards]

    def _on_mic_press(self):
        self.mic_btn.setText("🔴  يسجل… أطلق الزر بعد الكلام")
        self.mic_btn.setStyleSheet("QPushButton{background:#991b1b;color:white;border-radius:26px;border:4px solid white;}")
        self.rec_status.setText("🔴 يسجل بـ Whisper AI + كشف حركة الشفاه…")
        self._recorder.start()

    def _on_mic_release(self):
        self.mic_btn.setText("🎤  اضغط مع الاستمرار للكلام — قل الكلمة!")
        self.mic_btn.setStyleSheet("QPushButton{background:qlineargradient(x1:0,y1:0,x2:1,y2:0,stop:0 #dc2626,stop:1 #ef4444);color:white;border-radius:26px;border:3px solid #fca5a5;}QPushButton:pressed{background:#991b1b;border:4px solid white;}")
        self.rec_status.setText("⏳ يعالج الصوت…")
        threading.Thread(target=self._do_rec,daemon=True).start()

    def _do_rec(self):
        text=self._recorder.stop_and_recognise()
        ST["last_speech_text"]=text; BRIDGE.sig_rec_stop.emit(text)

    def _on_rec_stop(self,text:str):
        ST["recording"]=False
        if text: self.rec_status.setText(f"👂 سمعتك: \"{text}\""); self._add_chat("طفل",text)
        else:
            lip="(رُصدت حركة شفاه)" if ST["lip_speaking"] else ""
            self.rec_status.setText(f"❌ لم أسمع {lip} — حاول مرة أخرى")

    def _send_chat(self):
        msg=self.chat_input.text().strip()
        if not msg: return
        self.chat_input.clear(); self._add_chat("معالج",msg)
        threading.Thread(target=self._proc_chat,args=(msg,),daemon=True).start()

    def _proc_chat(self,msg:str):
        if _GENAI:
            try:
                mdl=genai.GenerativeModel("gemini-1.5-flash")
                ctx=(f"أنت روبوت بيبر المعالج لطفل اسمه {CHILD_NAME} عمره {CHILD_AGE} سنوات "
                     f"لديه اضطراب طيف التوحد. نقاط={ST['score']}, مشاعر={ST['emotion']}. "
                     f"أجب بـ 2-3 جمل قصيرة باللغة العربية. كن مشجعاً.")
                resp=mdl.generate_content(ctx+"\nالمعالج: "+msg)
                rep=resp.text.strip()[:300]
            except: rep=f"مرحباً! {CHILD_NAME} يتقدم بشكل رائع اليوم!"
        else: rep=f"مرحباً! أنا بيبر! {CHILD_NAME} يبذل جهداً رائعاً!"
        BRIDGE.sig_chat.emit("بيبر",rep)
        if VOICE_REF: VOICE_REF.say(rep,wait=False,st_ref=ST)

    def _add_chat(self,role:str,msg:str):
        t=datetime.now().strftime("%H:%M:%S")
        col={"بيبر":"#a78bfa","معالج":"#60a5fa","طفل":"#34d399"}.get(role,"#9ca3af")
        icon={"بيبر":"🤖","معالج":"👩","طفل":"👦"}.get(role,"💬")
        self.chat_area.append(f'<span style="color:{col};font-weight:bold">{icon}[{t}]:</span> <span style="color:#e0e6ff">{msg}</span>')
        sb=self.chat_area.verticalScrollBar()
        if sb: sb.setValue(sb.maximum())
        ST["session_chat"].append({"role":role,"text":msg,"time":t})
        if len(ST["session_chat"])>60: ST["session_chat"]=ST["session_chat"][-60:]


# ══════════════════════════════════════════════════════════════════
# محرك العلاج
# ══════════════════════════════════════════════════════════════════
class TherapyController(threading.Thread):
    def __init__(self,voice,pb):
        super().__init__(daemon=True); self.v=voice; self.pb=pb
        self._running=True; self._fail=0

    def run(self):
        time.sleep(4.0)
        self.v.say(f"أهلاً {CHILD_NAME}! أنا صديقك الجديد بيبر! هل تريد أن نلعب معاً؟",wait=True,st_ref=ST)
        while self._running:
            try: self._show()
            except Exception as e: log.warning(f"خطأ: {e}"); time.sleep(1.0)

    def _show(self):
        task=get_next_task()
        self._fail=0; ST["_fail_count"]=0
        ST["instant_success"]=False; ST["tablet_click_result"]=None
        ST["_current_task_keyword"]=task.get("keyword","").strip()
        self.pb.send(gaze="tablet" if task.get("verify")!="motor" else "child",is_speaking=False)
        BRIDGE.sig_reset.emit(); BRIDGE.sig_instr.emit(task.get("instruction",""))
        BRIDGE.sig_task.emit(task); BRIDGE.sig_stats.emit()
        self.v.say(task["instruction"],wait=True,st_ref=ST)
        prompts=task.get("prompts",[]); pidx=0
        for attempt in range(MAX_FAILS+2):
            if not self._running: return
            if ST.get("instant_success"): break
            BRIDGE.sig_waiting.emit(task["waiting"])
            self._run_dtt(task,attempt)
            if ST.get("instant_success"): break
            if self._fail>=MAX_FAILS: break
            if prompts and pidx<len(prompts):
                self.v.say(prompts[pidx],wait=True,st_ref=ST); pidx+=1
            time.sleep(0.4)
        if ST.get("instant_success"): self._success(task)
        else: self._skip(task)

    def _run_dtt(self,task,attempt):
        verify=task.get("verify","motor")
        wait_s={"motor":8.0,"tablet_click":12.0,"finger_count":9.0,"speech_keyword":12.0}.get(verify,10.0)
        if verify=="motor":
            ST["verify_action"]=task.get("id","").split("_")[0]
            ST["verify_timeout"]=time.time()+wait_s; ST["verify_result"]=False
        ST["instant_success"]=False
        deadline=time.time()+wait_s
        while time.time()<deadline:
            if not self._running: return
            if ST.get("instant_success"): return
            if verify=="tablet_click" and ST.get("tablet_click_result"):
                if ST["tablet_click_result"]=="correct": ST["instant_success"]=True
                else: self._fail+=1; ST["_fail_count"]=self._fail
                return
            if verify=="finger_count" and ST["finger_count"]==task.get("target_number",1):
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
        dom=task.get("domain","حركي")
        key=f"skill_{dom}"
        if key in ST: ST[key]=min(100,ST[key]+random.uniform(0.8,2.2))
        if ST["consecutive"]>=3:
            ST["mastered"]+=1; ST["consecutive"]=0
            if ST["score"]%80<pts: ST["conv_level"]=min(3,ST["conv_level"]+1)
        msg=task.get("success","أحسنت!")
        LOG(f"✅ {msg} وقت={rt}ms","success")
        log_csv(task["id"],dom,task.get("protocol","ABA"),True,ST["score"],ST["emotion"],ST["conv_level"],rt)
        BRIDGE.sig_success.emit(msg); BRIDGE.sig_joy.emit(task.get("joy","احتفال"))
        self.pb.send(is_speaking=True,sj=True,lip=0.9,gaze="child")
        self.v.say(msg,wait=True,st_ref=ST)
        joy=task.get("joy","")
        if joy=="فرح_كامل": self.v.say(f"ممتاز يا {CHILD_NAME}! أحسنت! علامة كاملة!",wait=True,st_ref=ST)
        elif joy=="رقص":    self.v.say(f"رائع يا {CHILD_NAME}! استمر!",wait=True,st_ref=ST)
        else:               self.v.say(f"صحيح يا {CHILD_NAME}! عظيم!",wait=True,st_ref=ST)
        self.pb.send(is_speaking=False,sj=False,gaze="child")
        BRIDGE.sig_stats.emit(); time.sleep(1.2)

    def _skip(self,task):
        ST["tasks_skipped"]+=1; ST["streak"]=0
        msg=task.get("fail","حاول المهمة التالية!")
        LOG(f"❌ تخطي","fail")
        log_csv(task["id"],task.get("domain","حركي"),task.get("protocol","ABA"),
                False,ST["score"],ST["emotion"],ST["conv_level"],0)
        BRIDGE.sig_skip.emit(msg)
        self.v.say(f"لنجرب مهمة جديدة يا {CHILD_NAME}! أنت تستطيع!",wait=True,st_ref=ST)
        BRIDGE.sig_stats.emit(); time.sleep(0.6)

    def stop(self): self._running=False


# ══════════════════════════════════════════════════════════════════
# لوحة الوالدين — تسجيل + دخول + لوحة كاملة
# ══════════════════════════════════════════════════════════════════
parent_app = Flask("parent_ar")
parent_app.secret_key = secrets.token_hex(16)

# ── صفحات HTML ────────────────────────────────────────────────────
LOGIN_PAGE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>بيبر كلينيكال — تسجيل الدخول</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{background:#060918;color:#e0e6ff;font-family:'Segoe UI',Tahoma,Arial,sans-serif;
  min-height:100vh;display:flex;align-items:center;justify-content:center;direction:rtl;}
.card{background:#0c0f1e;border:1px solid #1a1f40;border-radius:20px;padding:40px;
  width:100%;max-width:440px;box-shadow:0 20px 60px rgba(79,70,229,.3);}
.logo{text-align:center;margin-bottom:28px;}
.logo .icon{font-size:3.5em;display:block;margin-bottom:8px;}
.logo h1{font-size:1.5em;font-weight:900;color:#a78bfa;}
.logo p{font-size:.88em;color:#9ca3af;margin-top:4px;}
.tabs{display:flex;background:#1a1f40;border-radius:10px;padding:4px;margin-bottom:28px;}
.tab-btn{flex:1;padding:10px;text-align:center;cursor:pointer;border-radius:7px;
  font-size:.9em;font-weight:600;color:#9ca3af;transition:.2s;}
.tab-btn.active{background:#4f46e5;color:#fff;}
.form-group{margin-bottom:16px;}
label{display:block;font-size:.82em;color:#9ca3af;margin-bottom:6px;font-weight:600;}
input{width:100%;background:#1a1f40;border:2px solid #1a1f40;border-radius:10px;
  padding:12px 14px;color:#e0e6ff;font-size:.95em;outline:none;direction:rtl;}
input:focus{border-color:#4f46e5;}
.btn{width:100%;background:linear-gradient(135deg,#4f46e5,#7c3aed);color:#fff;
  border:none;border-radius:10px;padding:14px;font-size:1em;font-weight:700;
  cursor:pointer;margin-top:8px;transition:.2s;}
.btn:hover{opacity:.9;}
.msg{padding:10px 14px;border-radius:8px;font-size:.85em;margin-bottom:14px;text-align:center;}
.msg.error{background:#2a0808;border:1px solid #ef4444;color:#ef4444;}
.msg.success{background:#052918;border:1px solid #22c55e;color:#22c55e;}
.divider{text-align:center;color:#4b5563;font-size:.82em;margin:14px 0;position:relative;}
.divider::before,.divider::after{content:'';position:absolute;top:50%;width:40%;
  height:1px;background:#1a1f40;}
.divider::before{right:0;} .divider::after{left:0;}
#loginForm,#registerForm{display:none;}
#loginForm.active,#registerForm.active{display:block;}
</style></head>
<body>
<div class="card">
  <div class="logo">
    <span class="icon">🤖</span>
    <h1>بيبر كلينيكال إنفينيتي V6</h1>
    <p>لوحة متابعة الوالدين — صوت Piper العربي</p>
  </div>
  {% if msg %}
  <div class="msg {{ 'error' if msg_type=='error' else 'success' }}">{{ msg }}</div>
  {% endif %}
  <div class="tabs">
    <div class="tab-btn active" onclick="switchTab('login',this)">🔑 تسجيل الدخول</div>
    <div class="tab-btn" onclick="switchTab('register',this)">📝 حساب جديد</div>
  </div>
  <!-- دخول -->
  <div id="loginForm" class="active">
    <form method="POST" action="/login">
      <div class="form-group">
        <label>📧 البريد الإلكتروني</label>
        <input type="email" name="email" placeholder="example@email.com" required>
      </div>
      <div class="form-group">
        <label>🔒 كلمة المرور</label>
        <input type="password" name="password" placeholder="كلمة المرور" required>
      </div>
      <button type="submit" class="btn">🚀 دخول للوحة الوالدين</button>
    </form>
  </div>
  <!-- تسجيل -->
  <div id="registerForm">
    <form method="POST" action="/register">
      <div class="form-group">
        <label>👤 الاسم الكامل</label>
        <input type="text" name="name" placeholder="اسم ولي الأمر" required>
      </div>
      <div class="form-group">
        <label>📧 البريد الإلكتروني</label>
        <input type="email" name="email" placeholder="example@email.com" required>
      </div>
      <div class="form-group">
        <label>🏥 اسم المركز (اختياري)</label>
        <input type="text" name="center" placeholder="مركز علاج التوحد">
      </div>
      <div class="form-group">
        <label>📱 رقم الهاتف (اختياري)</label>
        <input type="text" name="phone" placeholder="+966 5x xxx xxxx">
      </div>
      <div class="form-group">
        <label>🔒 كلمة المرور (8 أحرف على الأقل)</label>
        <input type="password" name="password" placeholder="كلمة مرور قوية" required minlength="8">
      </div>
      <div class="form-group">
        <label>🔒 تأكيد كلمة المرور</label>
        <input type="password" name="password2" placeholder="أعد كتابة كلمة المرور" required>
      </div>
      <button type="submit" class="btn">✅ إنشاء حساب</button>
    </form>
  </div>
</div>
<script>
function switchTab(tab,el){
  document.querySelectorAll('.tab-btn').forEach(b=>b.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('loginForm').classList.toggle('active',tab==='login');
  document.getElementById('registerForm').classList.toggle('active',tab==='register');
}
{% if show_register %}switchTab('register',document.querySelectorAll('.tab-btn')[1]);{% endif %}
</script>
</body></html>"""

DASHBOARD_PAGE = """<!DOCTYPE html>
<html lang="ar" dir="rtl">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>بيبر كلينيكال V6 — لوحة الوالدين</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
:root{--bg:#060918;--bg2:#0c0f1e;--bg3:#1a1f40;--purple:#a78bfa;--blue:#3b82f6;
  --green:#22c55e;--red:#ef4444;--yellow:#fbbf24;--text:#e0e6ff;--text2:#9ca3af;}
body{background:var(--bg);color:var(--text);font-family:'Segoe UI',Tahoma,Arial,sans-serif;font-size:14px;direction:rtl;}
.topbar{background:linear-gradient(135deg,#1a0a3d,#0a0f28);padding:12px 20px;
  display:flex;align-items:center;gap:12px;border-bottom:2px solid #4f46e5;flex-wrap:wrap;}
.topbar h1{font-size:1.1em;color:var(--purple)}
.badge{background:#1e1b4b;border:1px solid #4f46e5;border-radius:20px;padding:3px 10px;font-size:.80em;color:var(--yellow)}
.logout-btn{margin-right:auto;background:#ef4444;color:#fff;border:none;border-radius:8px;
  padding:6px 14px;cursor:pointer;font-size:.82em;font-weight:700;}
.logout-btn:hover{background:#dc2626;}
.tabs{display:flex;background:var(--bg2);border-bottom:2px solid var(--bg3);overflow-x:auto;flex-wrap:nowrap;}
.tab{padding:12px 16px;cursor:pointer;font-size:.82em;font-weight:600;color:var(--text2);
  white-space:nowrap;border-bottom:3px solid transparent;transition:.2s;flex-shrink:0;}
.tab.active,.tab:hover{color:var(--purple);border-bottom-color:var(--purple)}
.content{padding:18px;overflow-y:auto;height:calc(100vh - 112px)}
.card{background:var(--bg2);border-radius:14px;padding:16px;border:1px solid var(--bg3);margin-bottom:12px}
.card h3{color:var(--purple);font-size:.95em;margin-bottom:10px}
.stat-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(120px,1fr));gap:8px;margin-bottom:14px}
.stat{background:var(--bg2);border-radius:10px;padding:10px;text-align:center;border:1px solid var(--bg3)}
.stat .val{font-size:1.7em;font-weight:900}.stat .lbl{font-size:.70em;color:var(--text2);margin-top:2px}
.skill-bar{margin-bottom:7px}
.skill-bar label{display:flex;justify-content:space-between;font-size:.78em;margin-bottom:2px}
.bar-bg{background:var(--bg3);border-radius:5px;height:8px}
.bar-fill{height:8px;border-radius:5px;transition:width 1s}
.diag-item{padding:6px 10px;background:var(--bg3);border-radius:8px;margin:3px 0;font-size:.81em;border-right:4px solid #4f46e5}
.treat-item{padding:6px 10px;background:#052918;border-radius:8px;margin:3px 0;font-size:.81em;border-right:4px solid var(--green);color:var(--green)}
.log-row{display:flex;justify-content:space-between;padding:4px 0;border-bottom:1px solid var(--bg3);font-size:.76em}
.ok{color:var(--green)}.fail{color:var(--red)}
input,select,textarea{width:100%;background:var(--bg3);border:2px solid var(--bg3);border-radius:8px;
  padding:9px 12px;color:var(--text);font-size:.88em;margin-bottom:8px;outline:none;direction:rtl}
input:focus,select:focus{border-color:#4f46e5}
.btn{background:#4f46e5;color:#fff;border:none;border-radius:8px;padding:10px 18px;
  font-weight:700;cursor:pointer;width:100%;font-size:.9em;}
.btn:hover{background:#4338ca}.btn-g{background:#059669}.btn-g:hover{background:#047857}
.pecs-grid{display:flex;flex-wrap:wrap;gap:7px}
.pecs-btn{background:#1e1b4b;border:2px solid #4f46e5;border-radius:10px;padding:7px 12px;
  cursor:pointer;font-size:.85em;color:#e0e6ff;transition:.15s}
.pecs-btn:hover{background:#2e2b6e;border-color:#a78bfa}
.child-card{background:var(--bg2);border-radius:10px;padding:10px;border:1px solid var(--bg3);
  margin-bottom:7px;cursor:pointer;display:flex;align-items:center;gap:10px;}
.child-card:hover{border-color:var(--purple)}
.q-item{margin-bottom:8px;padding:8px;background:var(--bg2);border-radius:10px}
.q-text{font-size:.82em;margin-bottom:5px}
.q-opts{display:flex;gap:5px}
.q-opt{flex:1;background:var(--bg3);border:2px solid var(--bg3);border-radius:7px;padding:5px;
  text-align:center;font-size:.74em;cursor:pointer;transition:.15s}
.q-opt:hover{border-color:#4f46e5}.q-opt.sel{background:#4f46e5;border-color:#4f46e5;color:#fff}
.score-box{background:#052918;border:2px solid var(--green);border-radius:10px;padding:12px;text-align:center;margin-top:8px}
.sc-num{font-size:2em;font-weight:900;color:var(--green)}
.quick-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:8px}
.qbtn{background:#1e1b4b;border:2px solid #4f46e5;border-radius:10px;padding:12px;
  color:#e0e6ff;cursor:pointer;font-size:.9em;font-weight:700;text-align:center;transition:.15s}
.qbtn:hover{background:#2e2b6e;border-color:#a78bfa}
.welcome{background:linear-gradient(135deg,#1e1b4b,#0c0f2e);border-radius:12px;padding:14px;
  margin-bottom:14px;border:1px solid #4f46e5;font-size:.88em;color:#a78bfa;}
</style></head>
<body>
<div class="topbar">
  <span style="font-size:1.5em">🤖</span>
  <h1>بيبر كلينيكال V6 — لوحة الوالدين</h1>
  <span class="badge">👤 {{ parent_name }}</span>
  <span class="badge">👦 <span id="cname">…</span></span>
  <span class="badge">⭐ <span id="cscore">0</span></span>
  <span class="badge">😊 <span id="cemo">—</span></span>
  <span class="badge" id="lip_b">👄 صامت</span>
  <span class="badge">🖐️ <span id="cfin">0</span>/10</span>
  <span class="badge"><a href="/report_pdf" style="color:var(--yellow);text-decoration:none">📄 PDF</a></span>
  <button class="logout-btn" onclick="location.href='/logout'">🚪 خروج</button>
</div>
<div class="tabs">
  <div class="tab active" onclick="showTab('overview',this)">📊 نظرة عامة</div>
  <div class="tab" onclick="showTab('diagnosis',this)">🧠 التشخيص</div>
  <div class="tab" onclick="showTab('children',this)">👶 أطفالي</div>
  <div class="tab" onclick="showTab('screening',this)">🧪 الفحص</div>
  <div class="tab" onclick="showTab('log',this)">📋 السجل</div>
  <div class="tab" onclick="showTab('pecs',this)">🗣️ PECS</div>
  <div class="tab" onclick="showTab('chat',this)">💬 المحادثة</div>
  <div class="tab" onclick="showTab('quick',this)">⚡ إجراءات</div>
  <div class="tab" onclick="showTab('training',this)">📚 تدريب</div>
</div>
<div class="content" id="content">جاري التحميل…</div>
<script>
const TOKEN='{{ token }}'; let st={},qa={};
async function fetchSt(){
  try{
    const r=await fetch('/api/state',{headers:{'X-Token':TOKEN}});
    st=await r.json();
    document.getElementById('cname').textContent=st.name||'—';
    document.getElementById('cscore').textContent=st.score||0;
    document.getElementById('cemo').textContent=st.emotion||'—';
    document.getElementById('lip_b').textContent='👄 '+(st.lip_speaking?'كلام':'صامت');
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
    const skills=[['حركي (ABA-DTT)','skill_حركي','#a78bfa'],['معرفي (TEACCH)','skill_معرفي','#06b6d4'],
      ['لفظي (DTT)','skill_لفظي','#fbbf24'],['رياضيات','skill_رياضيات','#22c55e'],
      ['اجتماعي (ESDM)','skill_اجتماعي','#f97316'],['يومي (TIE)','skill_يومي','#ec4899']];
    c.innerHTML=`
    <div class="welcome">مرحباً! جلسة <b>${st.name||'الطفل'}</b> نشطة — صوت Piper العربي يعمل 🔊</div>
    <div class="stat-grid">
      <div class="stat"><div class="val" style="color:#a78bfa">${st.score||0}</div><div class="lbl">⭐ النقاط</div></div>
      <div class="stat"><div class="val" style="color:#fbbf24">${st.tokens||0}</div><div class="lbl">🪙 الرموز</div></div>
      <div class="stat"><div class="val" style="color:#22c55e">${ok}</div><div class="lbl">✅ صحيح</div></div>
      <div class="stat"><div class="val" style="color:#3b82f6">${acc}%</div><div class="lbl">🎯 الدقة</div></div>
      <div class="stat"><div class="val" style="color:#f97316">${avg||'—'}ms</div><div class="lbl">⏱ متوسط</div></div>
      <div class="stat"><div class="val" style="color:#34d399">${st.mastered||0}</div><div class="lbl">🏆 متقن</div></div>
      <div class="stat"><div class="val" style="color:#f472b6">${st.conv_level||1}</div><div class="lbl">🗣 المستوى</div></div>
      <div class="stat"><div class="val" style="color:#60a5fa">${st.attention||0}%</div><div class="lbl">👁 الانتباه</div></div>
    </div>
    <div class="card"><h3>🎯 مجالات المهارات</h3>
      ${skills.map(([l,k,col])=>`<div class="skill-bar">
        <label><span>${l}</span><span style="color:${col};font-weight:700">${Math.round(st[k]||50)}%</span></label>
        <div class="bar-bg"><div class="bar-fill" style="width:${st[k]||50}%;background:${col}"></div></div>
      </div>`).join('')}
    </div>
    <div class="card"><h3>😊 المشاعر والشفاه</h3>
      <div style="display:flex;flex-wrap:wrap;gap:5px">
        ${Object.entries(st.emotion_pct||{}).map(([em,v])=>
          `<span style="background:#1e1b4b;border:1px solid #4f46e5;border-radius:16px;padding:2px 8px;font-size:.78em">${em} ${v}%</span>`).join('')}
      </div>
      <div style="margin-top:6px;font-size:.83em;color:var(--text2)">
        👄 ${st.lip_speaking?'<span style="color:#00ffc8">كلام مرصود</span>':'صامت'} |
        🖐️ أصابع: ${st.finger_count||0}/10 |
        حركة الشفاه: ${st.lip_motion?Number(st.lip_motion).toFixed(2):'0.00'}
      </div>
    </div>`;
  }
  else if(t==='diagnosis'){
    const skills=[['skill_حركي','حركي'],['skill_معرفي','معرفي'],['skill_لفظي','لفظي'],
      ['skill_رياضيات','رياضيات'],['skill_اجتماعي','اجتماعي'],['skill_يومي','يومي']];
    const diags=skills.map(([k,n])=>{const v=Math.round(st[k]||50);
      return v>=65?`✅ ${n}: ${v}% — أداء جيد`:v>=45?`⚠️ ${n}: ${v}% — في طور النمو`:`🔴 ${n}: ${v}% — أولوية`;});
    const treats=[];
    if((st['skill_حركي']||50)<50) treats.push('🏃 حركي ABA: 5 تكرارات يومية للتصفيق والتلويح.');
    if((st['skill_لفظي']||50)<50) treats.push('🎤 لفظي DTT: تدريب الكلمات 10 دقائق 3 مرات يومياً.');
    if((st['skill_اجتماعي']||50)<50) treats.push('👥 ESDM: لعب مشترك 20 دقيقة يومياً.');
    if((st['skill_يومي']||50)<50) treats.push('🌅 TIE: مارس 5 روتينات يومية بجدول بصري.');
    if(!treats.length) treats.push('✨ أداء ممتاز — زد الصعوبة تدريجياً!');
    c.innerHTML=`
    <div class="card"><h3>🧠 التشخيص التلقائي — ${st.name||'الطفل'}</h3>
      ${diags.map(d=>`<div class="diag-item">${d}</div>`).join('')}
    </div>
    <div class="card"><h3>💊 البروتوكول العلاجي</h3>
      ${treats.map(t=>`<div class="treat-item">${t}</div>`).join('')}
    </div>`;
  }
  else if(t==='children'){
    c.innerHTML=`<div class="card"><h3>👶 إضافة طفل</h3>
      <input id="nc_n" placeholder="اسم الطفل">
      <input id="nc_a" placeholder="العمر" type="number">
      <select id="nc_l"><option value="1">المستوى 1 — خفيف</option>
        <option value="2" selected>المستوى 2 — متوسط</option>
        <option value="3">المستوى 3 — شديد</option></select>
      <input id="nc_t" placeholder="ملاحظات">
      <button class="btn btn-g" onclick="addChild()">+ إضافة</button>
    </div><div id="childList"></div>`;
    loadChildren();
  }
  else if(t==='screening'){
    renderScreening(c);
  }
  else if(t==='log'){
    const logs=(st.logs||[]).slice().reverse().slice(0,50);
    const pecs=(st.pecs_log||[]).slice().reverse().slice(0,30);
    c.innerHTML=`<div class="card"><h3>📋 سجل الجلسة (${logs.length})</h3>
      ${logs.map(l=>`<div class="log-row"><span>${l.time} — ${l.msg}</span>
        <span class="${l.type==='success'?'ok':'fail'}">${l.type==='success'?'✅':'ℹ️'}</span></div>`).join('')
      || '<div style="color:var(--text2);padding:8px">لا أحداث بعد</div>'}
    </div>
    <div class="card"><h3>🗣️ سجل PECS (${pecs.length})</h3>
      ${pecs.map(p=>`<div class="log-row"><span>${p.time} — ${p.name}: "${p.phrase}"</span>
        <span style="color:var(--purple)">${p.emotion||'?'}</span></div>`).join('')
      || '<div style="color:var(--text2);padding:8px">لا استخدامات بعد</div>'}
    </div>`;
  }
  else if(t==='pecs'){
    const cats={صباح:'☀️ صباح',نظافة:'🧼 نظافة',طعام:'🍽️ طعام',
                اجتماعي:'💬 اجتماعي',سلامة:'🛑 سلامة',مشاعر:'😊 مشاعر'};
    c.innerHTML=Object.entries(cats).map(([cat,lbl])=>
      `<div class="card"><h3>${lbl}</h3><div class="pecs-grid" id="pc_${cat}">…</div></div>`).join('');
    fetch('/api/pecs_items',{headers:{'X-Token':TOKEN}}).then(r=>r.json()).then(d=>{
      Object.keys(cats).forEach(cat=>{
        const el=document.getElementById('pc_'+cat); if(!el) return;
        el.innerHTML=d.items.filter(x=>x.cat===cat).map(x=>
          `<button class="pecs-btn" onclick="sayPECS('${x.kw}','${x.label}')">${x.emoji} ${x.label}</button>`).join('');
      });
    });
  }
  else if(t==='chat'){
    const chat=(st.session_chat||[]).slice(-30);
    c.innerHTML=`<div class="card" style="height:320px;overflow-y:auto" id="chatBox">
      ${chat.map(m=>{const col=m.role==='بيبر'?'#a78bfa':m.role==='معالج'?'#60a5fa':'#34d399';
        const icon=m.role==='بيبر'?'🤖':m.role==='معالج'?'👩':'👦';
        return `<div style="margin:5px 0"><span style="color:${col};font-weight:bold">${icon}[${m.time}]:</span> <span>${m.text}</span></div>`;
      }).join('')||'<div style="color:var(--text2)">لا محادثة بعد</div>'}
    </div>
    <div style="display:flex;gap:8px;margin-top:8px">
      <input id="chatMsg" placeholder="اكتب رسالة…" onkeydown="if(event.key==='Enter')sendChat()">
      <button class="btn" style="width:80px" onclick="sendChat()">إرسال</button>
    </div>`;
    const cb=document.getElementById('chatBox'); if(cb) cb.scrollTop=cb.scrollHeight;
  }
  else if(t==='quick'){
    c.innerHTML=`<div class="card"><h3>⚡ إجراءات سريعة</h3>
    <div class="quick-grid">
      ${[['المهمة التالية','🎯','next'],['استراحة','⏸️','break'],['احتفال','🎉','celebrate'],
         ['تشجيع','💪','encourage'],['تقرير PDF','📄','report'],['إيقاف','⏯️','pause']
      ].map(([l,ic,a])=>`<div class="qbtn" onclick="quickAction('${a}')">${ic}<br><span style="font-size:.8em">${l}</span></div>`).join('')}
    </div></div>
    <div class="card"><h3>📊 إحصائيات مباشرة</h3>
    <div class="stat-grid">
      <div class="stat"><div class="val" style="color:#22c55e">${st.tasks_success||0}</div><div class="lbl">صحيح</div></div>
      <div class="stat"><div class="val" style="color:#ef4444">${st.tasks_fail||0}</div><div class="lbl">خاطئ</div></div>
      <div class="stat"><div class="val" style="color:#fbbf24">${st.streak||0}</div><div class="lbl">🔥 متتالي</div></div>
      <div class="stat"><div class="val" style="color:#60a5fa">${st.attention||0}%</div><div class="lbl">انتباه</div></div>
    </div></div>`;
  }
  else if(t==='training'){
    c.innerHTML=`<div class="card"><h3>📚 تدريب الوالدين</h3>
      ${[['تحليل السلوك التطبيقي ABA للتوحد','ABA autism therapy Arabic'],
         ['PECS لتبادل الصور والتواصل','PECS picture exchange autism Arabic'],
         ['TEACCH التعليم المنظم للتوحد','TEACCH autism Arabic'],
         ['مهارات الحياة اليومية للتوحد','daily life skills autism Arabic'],
         ['تمارين عدّ الأصابع للأطفال','finger counting autism children Arabic'],
         ['التعرف على المشاعر لأطفال التوحد','emotion recognition autism Arabic'],
         ['التدخل المبكر لاضطراب التوحد','early intervention autism Arabic'],
         ['صوت Piper TTS العربي للروبوتات','piper TTS arabic robot therapy'],
      ].map(([l,q])=>`<div onclick="window.open('https://www.youtube.com/results?search_query=${encodeURIComponent(q)}')"
        style="background:var(--bg3);border-radius:8px;padding:9px 12px;margin:4px 0;cursor:pointer;
        display:flex;align-items:center;gap:8px;border:1px solid var(--bg3)"
        onmouseover="this.style.borderColor='#4f46e5'" onmouseout="this.style.borderColor='var(--bg3)'">
        <span style="font-size:1.3em">📺</span><span>${l}</span></div>`).join('')}
    </div>`;
  }
}
function renderScreening(c){
  const isca=['هل يستجيب طفلك عند مناداته باسمه؟',
    'هل يُقيم طفلك تواصلاً بالعيون؟','هل يُشير طفلك للتشارك في الاهتمام؟',
    'هل يُقلّد طفلك الأفعال والأصوات؟','هل يستخدم طفلك الكلمات للتواصل؟',
    'هل يُبدي طفلك اهتماماً بالأطفال الآخرين؟','هل يمارس طفلك اللعب التخيلي؟',
    'هل يفهم طفلك التعليمات البسيطة؟','هل يُبدي طفلك المشاعر بشكل مناسب؟',
    'هل لدى طفلك سلوكيات متكررة غير معتادة؟'];
  c.innerHTML=`<div class="card"><h3>🧪 فحص ISCA (10 بنود)</h3>
    <p style="color:var(--text2);font-size:.80em;margin-bottom:8px">0=لا قلق، 1=بعض القلق، 2=قلق كبير</p>
    ${isca.map((q,i)=>`<div class="q-item"><div class="q-text">${i+1}. ${q}</div>
      <div class="q-opts">
        ${[['0','لا قلق'],['1','بعض'],['2','كبير']].map(([v,l])=>
          `<div class="q-opt ${qa['i'+i]===v?'sel':''}" id="qi_${i}_${v}"
           onclick="setQ('i',${i},'${v}',this)">${v} — ${l}</div>`).join('')}
      </div></div>`).join('')}
    <button class="btn" onclick="submitISCA()">إرسال فحص ISCA</button>
    <div id="iscaRes" class="score-box" style="display:none"></div>
  </div>`;
}
function setQ(type,i,v,el){
  qa[type+i]=v;
  document.querySelectorAll(`[id^="qi_${i}_"]`).forEach(x=>x.classList.remove('sel'));
  el.classList.add('sel');
}
function submitISCA(){
  let total=0;
  for(let i=0;i<10;i++) total+=(parseInt(qa['i'+i])||0);
  fetch('/api/screening',{method:'POST',headers:{'Content-Type':'application/json','X-Token':TOKEN},
    body:JSON.stringify({instrument:'isca',score:total})});
  const interp=total>12?'⚠️ قلق مرتفع — يُنصح بإحالة متخصص':
               total>6?'⚠️ قلق متوسط — مراقبة دقيقة':'✅ قلق منخفض — استمر في المتابعة';
  const el=document.getElementById('iscaRes');
  if(el){el.style.display='block';el.innerHTML=`<div class="sc-num">${total}/20</div><div style="color:var(--green);font-size:.86em;margin-top:4px">${interp}</div>`;}
}
async function addChild(){
  const n=document.getElementById('nc_n').value.trim(); if(!n)return;
  await fetch('/api/add_child',{method:'POST',headers:{'Content-Type':'application/json','X-Token':TOKEN},
    body:JSON.stringify({name:n,age:document.getElementById('nc_a').value,
      level:document.getElementById('nc_l').value,notes:document.getElementById('nc_t').value})});
  loadChildren();
}
async function loadChildren(){
  const r=await fetch('/api/children',{headers:{'X-Token':TOKEN}});
  const d=await r.json(); const el=document.getElementById('childList'); if(!el)return;
  if(!d.children||!d.children.length){el.innerHTML='<div style="color:var(--text2);padding:10px">لا أطفال مضافون</div>';return;}
  el.innerHTML=d.children.map(ch=>`<div class="child-card" onclick="switchChild('${ch.name}')">
    <span style="font-size:1.8em">👦</span>
    <div><div style="font-weight:700">${ch.name}</div>
    <div style="font-size:.76em;color:var(--text2)">العمر:${ch.age} | المستوى:${ch.level} | ${ch.notes||''}</div></div>
  </div>`).join('');
}
async function switchChild(name){
  await fetch('/api/switch_child',{method:'POST',headers:{'Content-Type':'application/json','X-Token':TOKEN},body:JSON.stringify({name})});
  fetchSt();
}
async function quickAction(a){
  if(a==='report'){window.open('/report_pdf');return;}
  await fetch('/api/quick_action',{method:'POST',headers:{'Content-Type':'application/json','X-Token':TOKEN},body:JSON.stringify({action:a})});
}
async function sayPECS(kw,label){
  await fetch('/api/pecs',{method:'POST',headers:{'Content-Type':'application/json','X-Token':TOKEN},body:JSON.stringify({keyword:kw,label})});
}
async function sendChat(){
  const msg=document.getElementById('chatMsg').value.trim(); if(!msg)return;
  document.getElementById('chatMsg').value='';
  await fetch('/api/chat',{method:'POST',headers:{'Content-Type':'application/json','X-Token':TOKEN},body:JSON.stringify({message:msg})});
  setTimeout(()=>showTab('chat'),800);
}
fetchSt(); setInterval(fetchSt,1500); renderTab('overview');
</script></body></html>"""

# ── مساعد التحقق من التوكن ──────────────────────────────────────
def get_parent():
    token = request.cookies.get("ar_token") or request.headers.get("X-Token","")
    return verify_token(token)

# ── مسارات Flask ────────────────────────────────────────────────
@parent_app.route("/")
def index():
    p = get_parent()
    if p: return redirect("/dashboard")
    return render_template_string(LOGIN_PAGE, msg=None, msg_type=None, show_register=False)

@parent_app.route("/login", methods=["POST"])
def do_login():
    email = request.form.get("email","")
    password = request.form.get("password","")
    ok, info, msg = login_parent(email, password)
    if ok:
        resp = make_response(redirect("/dashboard"))
        resp.set_cookie("ar_token", info["token"], max_age=86400, httponly=True)
        return resp
    return render_template_string(LOGIN_PAGE, msg=msg, msg_type="error", show_register=False)

@parent_app.route("/register", methods=["POST"])
def do_register():
    name     = request.form.get("name","")
    email    = request.form.get("email","")
    password = request.form.get("password","")
    password2= request.form.get("password2","")
    center   = request.form.get("center","")
    phone    = request.form.get("phone","")
    if password != password2:
        return render_template_string(LOGIN_PAGE, msg="كلمتا المرور غير متطابقتين",
                                      msg_type="error", show_register=True)
    ok, msg = register_parent(email, password, name, center, phone)
    msg_type = "success" if ok else "error"
    return render_template_string(LOGIN_PAGE, msg=msg, msg_type=msg_type, show_register=not ok)

@parent_app.route("/logout")
def do_logout():
    token = request.cookies.get("ar_token","")
    if token: logout_token(token)
    resp = make_response(redirect("/"))
    resp.delete_cookie("ar_token")
    return resp

@parent_app.route("/dashboard")
def dashboard():
    p = get_parent()
    if not p: return redirect("/")
    token = request.cookies.get("ar_token","")
    return render_template_string(DASHBOARD_PAGE, parent_name=p["name"], token=token)

# ── API (محمية بالتوكن) ──────────────────────────────────────────
def require_auth(f):
    from functools import wraps
    @wraps(f)
    def decorated(*args, **kwargs):
        if not get_parent():
            return jsonify({"error":"غير مصرح"}), 401
        return f(*args, **kwargs)
    return decorated

@parent_app.route("/api/state")
@require_auth
def api_state():
    return jsonify({k:ST[k] for k in ST if isinstance(ST[k],(str,int,float,bool,list,dict,type(None)))})

@parent_app.route("/api/screening", methods=["POST"])
@require_auth
def api_screening():
    d = request.json or {}
    sc = int(d.get("score",0))
    if sc>12: ST["conv_level"]=1
    elif sc>6: ST["conv_level"]=min(2,ST["conv_level"])
    return jsonify({"ok":True})

@parent_app.route("/api/add_child", methods=["POST"])
@require_auth
def api_add_child():
    p = get_parent(); d = request.json or {}
    db_add_child(p["parent_id"],d.get("name","?"),d.get("age",6),d.get("level",2),d.get("notes",""))
    return jsonify({"ok":True})

@parent_app.route("/api/children")
@require_auth
def api_children():
    p = get_parent()
    return jsonify({"children": db_get_children(p["parent_id"])})

@parent_app.route("/api/switch_child", methods=["POST"])
@require_auth
def api_switch():
    d = request.json or {}
    if d.get("name"): ST["name"]=d["name"]
    return jsonify({"ok":True})

@parent_app.route("/api/quick_action", methods=["POST"])
@require_auth
def api_quick():
    d = request.json or {}; ST["quick_action"]=d.get("action")
    return jsonify({"ok":True})

@parent_app.route("/api/pecs", methods=["POST"])
@require_auth
def api_pecs():
    d = request.json or {}; kw=d.get("keyword",""); label=d.get("label","")
    if kw and VOICE_REF:
        VOICE_REF.say_pecs(f"{ST['name']} يقول: {kw}",ST)
    ST["pecs_log"].append({"time":datetime.now().strftime("%H:%M:%S"),
        "name":label,"phrase":kw,"emotion":ST["emotion"]})
    return jsonify({"ok":True})

@parent_app.route("/api/chat", methods=["POST"])
@require_auth
def api_chat():
    d = request.json or {}; msg=d.get("message","")
    if msg: BRIDGE.sig_chat.emit("معالج",msg)
    return jsonify({"ok":True})

@parent_app.route("/api/pecs_items")
@require_auth
def api_pecs_items():
    items=[{"id":iid,"emoji":emoji,"label":label,"kw":kw,"cat":cat}
           for iid,emoji,label,kw,cat in PECS_AR]
    return jsonify({"items":items})

@parent_app.route("/report_pdf")
@require_auth
def report_pdf():
    if not _PDF: return "pip install reportlab",501
    buf=BytesIO()
    doc=SimpleDocTemplate(buf,pagesize=A4)
    styles=getSampleStyleSheet(); story=[]
    story.append(Paragraph(f"<b>بيبر كلينيكال V6 — التقرير السريري</b>",styles["Title"]))
    story.append(Paragraph(f"الطفل: {ST['name']} | التاريخ: {ST['session_date']} | النقاط: {ST['score']}",styles["Normal"]))
    story.append(Spacer(1,10))
    data=[["المجال","النتيجة","الحالة"]]
    for k,n in [("skill_حركي","حركي"),("skill_معرفي","معرفي"),("skill_لفظي","لفظي"),
                ("skill_رياضيات","رياضيات"),("skill_اجتماعي","اجتماعي"),("skill_يومي","يومي")]:
        v=ST[k]; s="جيد" if v>=65 else "نامٍ" if v>=45 else "أولوية"
        data.append([n,f"{v:.1f}%",s])
    t=Table(data,colWidths=[120,80,100])
    t.setStyle(TableStyle([("BACKGROUND",(0,0),(-1,0),RLC.HexColor("#4f46e5")),
        ("TEXTCOLOR",(0,0),(-1,0),RLC.white),("GRID",(0,0),(-1,-1),1,RLC.grey),
        ("FONTNAME",(0,0),(-1,-1),"Helvetica"),
        ("ROWBACKGROUNDS",(0,1),(-1,-1),[RLC.white,RLC.HexColor("#f0f4f8")])]))
    story.append(t); story.append(Spacer(1,10))
    story.append(Paragraph("<b>السجل (آخر 20):</b>",styles["Heading3"]))
    for lg in ST.get("logs",[])[-20:]:
        story.append(Paragraph(f"[{lg['time']}] {lg['msg'][:80]}",styles["Normal"]))
    doc.build(story); buf.seek(0)
    return send_file(buf,as_attachment=True,
        download_name=f"PepperV6_AR_{SAFE_NAME}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf",
        mimetype="application/pdf")

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
    log.info("🔊 تشغيل محرك الصوت Piper العربي...")
    voice=PiperVoice(); VOICE_REF=voice
    log.info("🤖 تشغيل محاكاة بيبر PyBullet...")
    pb=PBWatchdog(CHILD_NAME); pb.start()
    log.info("🖥️  بناء الواجهة الرئيسية العربية (1600×900)...")
    win=MainWindowAR(); win.show()
    log.info("📷 تشغيل خط أنابيب الرؤية MediaPipe...")
    cam=CameraThread(); cam.start()
    log.info("🎯 تشغيل محرك العلاج العربي...")
    ctrl=TherapyController(voice,pb); ctrl.start()
    log.info("🌐 تشغيل لوحة الوالدين المحمية (المنفذ 5007)...")
    threading.Thread(target=run_flask,daemon=True).start()
    print("\n"+"═"*60)
    print(f"  ✅ بيبر كلينيكال V6 — يعمل!")
    print(f"  🔊 صوت Piper: {PIPER_MODEL}")
    print(f"  👦 الطفل: {CHILD_NAME}")
    print(f"  🌐 لوحة الوالدين: http://localhost:5007")
    print(f"  🌐 على الشبكة:     http://{LOCAL_IP}:5007")
    print(f"  🔑 سجّل أولاً ثم ادخل للوحة الوالدين")
    print(f"  📊 نتائج: {CSV_FILE}")
    print("═"*60+"\n")
    webbrowser.open("http://localhost:5007")
    def _cleanup():
        ctrl.stop(); cam.stop(); pb.stop()
        try: voice.cleanup()
        except: pass
        try: os.system("pkill -f aplay 2>/dev/null")
        except: pass
    app.aboutToQuit.connect(_cleanup)
    sys.exit(app.exec())

if __name__=="__main__":
    main()
