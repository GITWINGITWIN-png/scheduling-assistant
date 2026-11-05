"""submap — engine ของ skill "subject-map": สร้างแผนที่วิชา/โปรเจกต์แบบโต้ตอบเป็น HTML หน้าเดียว

ที่ spec ใช้:
    from submap import Node, Edge, Conn, Graph, Draw, icon, text_w
ที่ build.py ของโปรเจกต์ใช้:
    from submap.build import main

แยกออกมาจาก osmap ของแผนที่ OS ปลายภาค (Final-Exam/scripts/osmap) — โครงหน้า การตรวจ และ JS เดิม
แต่สี หมวด ชั้น ข้อความ และเนื้อหาทั้งหมดมาจาก spec ของแต่ละแผนที่
"""
from .draw import Draw
from .fonts import text_w
from .icons import icon, register
from .svg import Conn, Edge, Graph, Node, esc

VERSION = "1.0"
__all__ = ["Node", "Edge", "Conn", "Graph", "Draw", "icon", "register", "text_w", "esc", "VERSION"]
