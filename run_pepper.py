"""
Pepper Clinical Infinity V6 — Production Server Launcher
© 2026 Lamya Fadlulmola Hamed Ali — All Rights Reserved

This file launches the compiled Pepper V6 in server mode.
The actual logic is inside pepper_v6_full.so (Cython compiled binary).
"""
import os, sys, logging

logging.basicConfig(level=logging.INFO,
    format="[%(asctime)s][%(levelname)s] %(message)s")
log = logging.getLogger("PepperV6-Server")

# Server-mode flag: disables PyQt6 GUI, enables headless Flask-only mode
os.environ["PEPPER_SERVER_MODE"] = "1"
os.environ["PEPPER_CHILD_NAME"]  = os.environ.get("PEPPER_CHILD_NAME", "Child")
os.environ["PEPPER_CHILD_AGE"]   = os.environ.get("PEPPER_CHILD_AGE",  "6")

# Import compiled binary
try:
    import pepper_v6_full as pepper
    log.info("✅ Loaded compiled Pepper V6 binary")
except ImportError:
    # Fallback to source for development
    log.warning("Binary not found — loading source (dev mode)")
    import importlib.util
    spec = importlib.util.spec_from_file_location("pepper_v6_full", "pepper_v6_full.py")
    pepper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(pepper)

if __name__ == "__main__":
    log.info("🚀 Pepper Clinical Infinity V6 — Server Mode")
    log.info("📊 Dashboard: http://0.0.0.0:5007/")
    log.info("📋 Reports:   http://0.0.0.0:5001/")
    log.info("🎮 Games:     http://0.0.0.0:5009/")
    log.info("🌐 Share:     http://0.0.0.0:5007/share")
    pepper.main()
