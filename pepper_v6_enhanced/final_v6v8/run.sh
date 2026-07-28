#!/bin/bash
cd ~/pepper_duo/src
source $(conda info --base)/etc/profile.d/conda.sh && conda activate pepper_stable
export QT_QPA_PLATFORM=xcb TF_CPP_MIN_LOG_LEVEL=3 PYTHONWARNINGS=ignore
python3 pepper_v6_v8_enhanced.py
