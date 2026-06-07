#!/bin/bash
cd "$(dirname "$0")"
source venv/bin/activate 2>/dev/null || {
  echo "未找到虚拟环境，请先执行: python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
  exit 1
}
python app.py
