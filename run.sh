#!/bin/bash
cd "$(dirname "$0")/frontend"
python3 -m streamlit run app.py "$@"
