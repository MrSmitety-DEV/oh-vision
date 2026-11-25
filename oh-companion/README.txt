OH Companion — เครื่องมือเสริม Once Human จากช่อง MrSmitety (hub.mrsmitety.com)

รวม 3 โปรแกรมไว้ในไฟล์เดียว มีไอคอนในถาดอันเดียว เปิด/ปิดแต่ละส่วนได้จากหน้าหลัก
  • Vision Timer   นับถอยหลังช่วง Vision ⇄ ช่วงพัก แสดงตลอดเวลา (แม้ไม่ได้เปิดเกม)   Ctrl+Alt+V / Ctrl+Alt+L
  • Thai Tooltip   ชี้ไอเทมในเกมแล้วขึ้นคำแปลไทย (เฉพาะตอนเกมอยู่หน้าจอ)           Ctrl+Alt+T
  • Build Overlay  เช็คของที่ใส่ในหน้า Gear เทียบกับบิ้วจากเว็บ (เฉพาะตอนเกมอยู่หน้าจอ)  Ctrl+Alt+B

ทุกส่วนอ่านจากภาพหน้าจออย่างเดียว ไม่แก้ไฟล์เกม ไม่อ่านหน่วยความจำ ไม่กดปุ่มแทนผู้เล่น
การตั้งค่าเดิมของแต่ละโปรแกรมใช้ต่อได้เลย (%APPDATA%\MrSmitetyVision, OHThaiTooltip, OHBuildOverlay)
ค่าของ OH Companion เอง: %APPDATA%\OHCompanion

ไฟล์ในโฟลเดอร์นี้
  OH Companion.pyw   หน้าหลัก + ถาด + เปิด/ปิดโมดูล
  mod_vision.py      Vision Timer (ดัดแปลงจาก OH-Vision Time Tracker 1.2.0)
  mod_thai.py        Thai Tooltip (ดัดแปลงจาก OH Thai Tooltip 0.8.0 รุ่นฟรี) + engine.py, detect.py
  mod_build.py       Build Overlay (ดัดแปลงจาก OH Build Overlay 0.2.1) + bo_read.py, bo_match.py
  oc_ctx.py          ค่ากลางที่ทุกโมดูลใช้ร่วมกัน

สวิตช์ฟีเจอร์จากเว็บ (ไม่บังคับ): ใส่แถว key = companion_flags ในตาราง app_settings
  ค่าเป็น JSON เช่น {"build":"beta"} · public = ปกติ, beta = ขึ้นป้าย "ทดลอง", off = ซ่อนและปิดส่วนนั้น
