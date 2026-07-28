#!/bin/bash
echo "╔══════════════════════════════════════════════════════════╗"
echo "║  Pepper Clinical V6+V8 — Enhanced Edition                ║"
echo "║  5 Themes | 50 PECS | 8 Music | 13 Moods | Clap Sound   ║"
echo "╚══════════════════════════════════════════════════════════╝"
source $(conda info --base)/etc/profile.d/conda.sh 2>/dev/null || true
conda activate pepper_stable 2>/dev/null || conda create -n pepper_stable python=3.9 -y && conda activate pepper_stable
pip install PyQt6 opencv-python-headless mediapipe faster-whisper SpeechRecognition \
    pyaudio pyttsx3 flask pybullet qibullet google-generativeai reportlab numpy scipy Pillow -q
mkdir -p ~/pepper_duo/src
cp "$(dirname "$0")/src/pepper_v6_v8_enhanced.py" ~/pepper_duo/src/
echo "✅ Done! Run: cd ~/pepper_duo/src && conda activate pepper_stable && python3 pepper_v6_v8_enhanced.py"
