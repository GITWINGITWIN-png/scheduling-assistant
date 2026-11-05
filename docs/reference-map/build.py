#!/usr/bin/env python3
"""สร้าง แผนที่ผู้ช่วย AI โอเพนซอร์ส

    python3 build.py                     เขียน reference-map.html (เปิดในเบราว์เซอร์ได้เลย)
    python3 build.py --check             ตรวจการจัดวางและการอ้างอิงอย่างเดียว
    python3 build.py --fragment X.html   เขียนฉบับไม่มี <html>/<head> สำหรับเผยแพร่เป็น artifact ด้วย
"""
import sys
from pathlib import Path

sys.dont_write_bytecode = True   # ไม่ทิ้ง __pycache__ ไว้ในโฟลเดอร์งาน
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import spec                      # noqa: E402
from submap.build import main    # noqa: E402

if __name__ == "__main__":
    main(spec, out=HERE / "reference-map.html")
