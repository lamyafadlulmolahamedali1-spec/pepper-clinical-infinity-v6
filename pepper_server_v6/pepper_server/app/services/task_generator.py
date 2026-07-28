"""
╔════════════════════════════════════════════════════════════════════╗
║  PEPPER CLINICAL V6 — 100K+ Task Generator                       ║
║  ABA · DTT · TEACCH · ESDM · PRT · Verbal Behavior               ║
╚════════════════════════════════════════════════════════════════════╝
"""
import time
import random
from typing import List, Dict, Optional

# ── Data pools ────────────────────────────────────────────────────────
COLORS = [("red","🔴","#ef4444"),("blue","🔵","#3b82f6"),("green","🟢","#22c55e"),
          ("yellow","🟡","#eab308"),("orange","🟠","#f97316"),("purple","🟣","#a855f7"),
          ("pink","🩷","#ec4899"),("brown","🟤","#92400e"),("white","⬜","#f1f5f9"),
          ("black","⬛","#1e293b"),("gray","🩶","#6b7280"),("cyan","🩵","#06b6d4")]
ANIMALS = [("dog","🐶"),("cat","🐱"),("lion","🦁"),("elephant","🐘"),("rabbit","🐰"),
           ("bear","🐻"),("horse","🐴"),("butterfly","🦋"),("penguin","🐧"),("owl","🦉"),
           ("dolphin","🐬"),("fox","🦊"),("tiger","🐯"),("monkey","🐒"),("giraffe","🦒"),
           ("turtle","🐢"),("frog","🐸"),("bee","🐝"),("fish","🐟"),("bird","🐦")]
FRUITS = [("apple","🍎"),("banana","🍌"),("orange","🍊"),("grapes","🍇"),("strawberry","🍓"),
          ("watermelon","🍉"),("mango","🥭"),("pineapple","🍍"),("kiwi","🥝"),("pear","🍐"),
          ("lemon","🍋"),("cherry","🍒"),("peach","🍑"),("coconut","🥥"),("blueberry","🫐")]
SHAPES = [("circle","⭕"),("square","⬛"),("triangle","🔺"),("star","⭐"),("heart","❤️"),
          ("diamond","🔷"),("rectangle","▬"),("oval","🔵"),("pentagon","⬟"),("cross","✚")]
EMOTIONS = [("happy","😊"),("sad","😢"),("angry","😠"),("scared","😨"),("surprised","😮"),
            ("excited","🤩"),("tired","😴"),("confused","😕"),("proud","😤"),("calm","😌")]
BODY = [("hand","✋"),("foot","🦶"),("eye","👁️"),("nose","👃"),("ear","👂"),
        ("mouth","👄"),("head","🙂"),("arm","💪"),("leg","🦵"),("back","🔙")]
VEHICLES = [("car","🚗"),("bus","🚌"),("plane","✈️"),("train","🚂"),("boat","⛵"),
            ("bike","🚲"),("helicopter","🚁"),("truck","🚛"),("motorcycle","🏍️"),("rocket","🚀")]
CLOTHES = [("shirt","👕"),("pants","👖"),("shoes","👟"),("hat","🎩"),("dress","👗"),
           ("socks","🧦"),("jacket","🧥"),("gloves","🧤"),("scarf","🧣"),("boots","👢")]
LETTERS = list("ABCDEFGHIJKLMNOPQRSTUVWXYZ")
WORDS = ["apple","ball","cat","dog","fish","happy","jump","love","milk","play",
         "red","sun","tree","water","yes","no","one","two","three","go","stop",
         "help","more","done","please","thank you","good morning","I want",
         "I need help","all done","good job","sit down","stand up","come here",
         "look at me","my turn","your turn","I love you","I am happy","I am sad"]

MOTORS = [
    ("clap","👏","CLAP your hands 3 times!","clap",2,"Amazing clap! 👏"),
    ("wave","👋","WAVE hello to the camera!","wave",2,"Great wave! 👋"),
    ("thumbs","👍","Show THUMBS UP!","thumbs",2,"Thumbs up! 👍"),
    ("nose","👃","Touch your NOSE!","touch",3,"Found your nose! 👃"),
    ("head","🙆","Touch the TOP of your HEAD!","touch",3,"Head touch! 🙆"),
    ("arms","🙌","Raise BOTH ARMS up HIGH!","arms",2,"Arms up! 🙌"),
    ("breath","🌬️","Take a DEEP BREATH!","breath",2,"Great breathing! 🌬️"),
    ("smile","😄","Show your BIGGEST SMILE!","smile",2,"Beautiful smile! 😄"),
    ("point","☝️","POINT at the camera!","point",2,"Great pointing! ☝️"),
    ("nod","✅","NOD your head YES!","nod",2,"Great nodding! ✅"),
    ("jump","⬆️","JUMP up once!","jump",3,"Great jump! ⬆️"),
    ("spin","🔄","SPIN around slowly!","spin",3,"Nice spin! 🔄"),
    ("stomp","🦶","STOMP your feet 3 times!","stomp",2,"Stomp! 🦶"),
    ("knee","🦵","Touch your KNEE!","touch",2,"Found your knee! 🦵"),
    ("ear","👂","Touch your EAR!","touch",2,"Found your ear! 👂"),
]

SOCIAL = [
    ("please","🙏","Say PLEASE when you want something! 🙏",3),
    ("thank you","💙","Say THANK YOU! 💙",3),
    ("hello","👋","Say HELLO and wave! 👋",2),
    ("help","🆘","Ask for HELP: Help please! 🆘",3),
    ("sorry","💛","Say SORRY nicely! 💛",3),
    ("yes","✅","Say YES by nodding! ✅",2),
    ("good job","⭐","Say GOOD JOB! ⭐",3),
    ("wait","⏳","WAIT patiently for your turn! ⏳",3),
    ("share","🤝","SHARE with a friend! 🤝",4),
    ("high five","✋","Give a HIGH FIVE! ✋",2),
]

DAILY = [
    ("wash hands","🙌","Show how you WASH hands! 🙌",4),
    ("brush teeth","🦷","Show how you BRUSH teeth! 🦷",4),
    ("comb hair","💆","Show how you COMB hair! 💆",3),
    ("eat spoon","🥄","Pretend to EAT with a spoon! 🥄",3),
    ("drink cup","🥤","Pretend to DRINK from a cup! 🥤",2),
    ("put shoes","👟","Pretend to put on SHOES! 👟",4),
    ("sleep","😴","Show how you SLEEP! 😴",2),
    ("quiet hands","🖐️","Show QUIET HANDS! 🖐️",2),
]


def _rnd(pool):
    return random.choice(pool)


def _mk_grid(pool, domain, protocol, n, task_type):
    tgt = _rnd(pool)
    others = random.sample([x for x in pool if x[0] != tgt[0]], min(n-1, len(pool)-1))
    opts = others + [tgt]
    random.shuffle(opts)
    ci = opts.index(tgt)
    em = tgt[1] if len(tgt) > 1 else "❓"
    lbl = tgt[0]
    return {
        "type": task_type, "name": f"Find {lbl}",
        "instruction": f"Point to {lbl}! {em}", "em": em,
        "options": [{"id": o[0], "label": o[0], "em": o[1],
                     "color": o[2] if len(o) > 2 else "transparent"} for o in opts],
        "correct": ci, "domain": domain, "protocol": protocol,
        "tokens": 3, "level": 1,
        "success": f"YES! {lbl}! {em}", "fail": f"Find {lbl}! {em}",
    }


class TaskGenerator:
    @staticmethod
    def generate(domain: Optional[str] = None, level: int = 1, count: int = 20) -> List[Dict]:
        domains = ([domain] * count if domain
                   else [random.choice(["motor","cognitive","verbal","math","social","daily"])
                         for _ in range(count)])
        return [TaskGenerator._build(d, level) for d in domains]

    @staticmethod
    def _build(domain, level=1):
        return {
            "motor": TaskGenerator._motor, "cognitive": TaskGenerator._cognitive,
            "verbal": TaskGenerator._verbal, "math": TaskGenerator._math,
            "social": TaskGenerator._social, "daily": TaskGenerator._daily,
        }.get(domain, TaskGenerator._motor)(level)

    @staticmethod
    def _motor(lv=1):
        m = _rnd(MOTORS)
        return {"type":"motor","name":f"Motor: {m[1]}","instruction":m[2],"em":m[1],
                "verify":m[3],"domain":"Motor","protocol":random.choice(["ABA-DTT","ESDM","PRT"]),
                "tokens":m[4]+lv-1,"level":lv,"success":m[5],"fail":f"Try again! {m[1]}"}

    @staticmethod
    def _cognitive(lv=1):
        pool_name = random.choice(["color","animal","fruit","shape","emotion","body","vehicle","clothes"])
        pmap = {"color":(COLORS,"Cognitive","TEACCH","color"),"animal":(ANIMALS,"Cognitive","TEACCH","obj"),
                "fruit":(FRUITS,"Cognitive","ABA-DTT","obj"),"shape":(SHAPES,"Math","ABA-DTT","obj"),
                "emotion":(EMOTIONS,"Social","ESDM","obj"),"body":(BODY,"Cognitive","ESDM","obj"),
                "vehicle":(VEHICLES,"Cognitive","TEACCH","obj"),"clothes":(CLOTHES,"Cognitive","TEACCH","obj")}
        pool,dom,prot,t = pmap[pool_name]
        return _mk_grid(pool, dom, prot, min(4+lv, len(pool)), t)

    @staticmethod
    def _verbal(lv=1):
        w = _rnd(WORDS[:20] if lv==1 else WORDS[:30] if lv==2 else WORDS)
        return {"type":"word","name":f"Say: {w}","instruction":f"Say the word: {w.upper()}! 🗣️",
                "em":"🗣️","word":w,"domain":"Verbal","protocol":random.choice(["ESDM","Verbal-Behavior","TEACCH"]),
                "tokens":3+lv,"level":lv,"success":f"I heard {w.upper()}! 🗣️","fail":f"Say: {w}!"}

    @staticmethod
    def _math(lv=1):
        if lv==1:
            n = random.randint(1,5)
            return {"type":"number","name":f"Show {n} fingers",
                    "instruction":f"Show me {n} finger{'s' if n>1 else ''}! 🖐️",
                    "em":"🖐️","target":n,"domain":"Math","protocol":"ABA-DTT",
                    "tokens":4,"level":1,"success":f"YES! {n} fingers! 🖐️","fail":f"Show {n} fingers!"}
        elif lv==2:
            a,b = random.randint(1,5),random.randint(1,5)
            return {"type":"math_add","name":f"{a}+{b}=?","instruction":f"What is {a}+{b}? 🔢",
                    "em":"🔢","answer":a+b,"domain":"Math","protocol":"ABA-DTT",
                    "tokens":5,"level":2,"success":f"Correct! {a}+{b}={a+b}! 🌟","fail":f"Answer is {a+b}!"}
        else:
            L = _rnd(LETTERS)
            opts = random.sample([x for x in LETTERS if x!=L], 7) + [L]
            random.shuffle(opts)
            return {"type":"letter","name":f"Letter {L}","instruction":f"Find letter {L}! 📝","em":"📝",
                    "options":[{"id":x,"label":x,"em":x,"color":"#ede9fe"} for x in opts],
                    "correct":opts.index(L),"domain":"Cognitive","protocol":"TEACCH",
                    "tokens":4,"level":3,"success":f"YES! Letter {L}! 📝","fail":f"Find {L}!"}

    @staticmethod
    def _social(lv=1):
        t = _rnd(SOCIAL[:6] if lv==1 else SOCIAL)
        return {"type":"social","name":t[0].title(),"instruction":t[2],"em":t[1],"phrase":t[0],
                "domain":"Social","protocol":random.choice(["ESDM","PRT","Verbal-Behavior"]),
                "tokens":t[3],"level":lv,"success":f"Excellent! {t[1]} 🌟","fail":f"Try: {t[0]}! {t[1]}"}

    @staticmethod
    def _daily(lv=1):
        t = _rnd(DAILY)
        return {"type":"daily","name":t[0].title(),"instruction":t[2],"em":t[1],
                "domain":"Daily Living","protocol":"TEACCH","tokens":t[3],"level":lv,
                "success":"Amazing life skill! 🌟","fail":"Try again!"}
