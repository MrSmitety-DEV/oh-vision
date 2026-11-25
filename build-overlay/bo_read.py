# -*- coding: utf-8 -*-
"""OH Build Overlay – อ่านหน้าจอเกม (เฉพาะภาพหน้าจอ ไม่แตะเกม)
หน้าที่รองรับ: Weapons / Armor (กระเป๋าเลือกของ), Mod Backpack, Weapon Crafting (ใบ Calibration), หน้า Gear รวม
พิกัดทั้งหมดเป็นสัดส่วนของหน้าต่างเกม (อ้างอิงจากจอ 16:9)"""
import re, unicodedata
import numpy as np

REG = {
    'title':  (0.00, 0.00, 0.25, 0.065),   # ชื่อหน้า: Weapons / Armor / Mod Backpack
    'nav':    (0.28, 0.00, 0.78, 0.06),    # แถบเมนูบน: Backpack Gear Tech ... / Weapon Crafting Armor Crafting
    'panel':  (0.725, 0.20, 0.97, 0.88),   # แผงรายละเอียดขวา (ปืน/เกราะ)
    'footer': (0.60, 0.94, 0.99, 0.99),    # ปุ่มล่าง: Equip / Unequip
    'modp':   (0.735, 0.24, 0.97, 0.46),   # แผง Core Effects ของ MOD
    'rows':   (0.08, 0.14, 0.24, 0.86),    # หัวแถวชื่อ MOD (ตัวอักษรห่างๆ)
    'modhead': (0.085, 0.135, 0.5, 0.188), # หัวข้อหมวด เช่น "The Bull's Eye Mod"
}


def squash(s):
    s = unicodedata.normalize('NFKC', s or '').lower().replace('’', "'").replace('–', '-').replace('—', '-')
    return re.sub(r'[^a-z0-9]', '', s)


def crop(frame, key):
    H, W = frame.shape[:2]
    x0, y0, x1, y1 = REG[key]
    X0, Y0, X1, Y1 = int(x0 * W), int(y0 * H), int(x1 * W), int(y1 * H)
    return frame[Y0:Y1, X0:X1], (X0, Y0)


def sig(img):
    """ลายเซ็นภาพย่อ ใช้ดูว่าบริเวณนั้นเปลี่ยนไหม (ไม่ต้อง OCR ซ้ำ)"""
    a = img[::8, ::8].astype(np.int16)
    return a


def changed(a, b, thr=6.0):
    if a is None or b is None or a.shape != b.shape:
        return True
    return float(np.abs(a - b).mean()) > thr


def lines_of(res):
    """res: [(box, text, score)] → เรียงบนลงล่าง ซ้ายไปขวา"""
    out = []
    for b, t, s in res:
        ys = [p[1] for p in b]; xs = [p[0] for p in b]
        out.append({'t': unicodedata.normalize('NFKC', t).strip(), 'x0': min(xs), 'x1': max(xs), 'y0': min(ys), 'y1': max(ys), 's': s})
    out.sort(key=lambda r: (round(r['y0'] / 12), r['x0']))
    return out


def page_of(title_lines, nav_lines):
    t = ' '.join(l['t'] for l in title_lines).lower()
    n = ' '.join(l['t'] for l in nav_lines).lower()
    if 'mod backpack' in t or ('mod' in t and 'backpack' in t):
        return 'mod'
    if re.search(r'\bweapons?\b', t):
        return 'weapons'
    if re.search(r'\barmou?r\b', t):
        return 'armor'
    if 'crafting' in n:
        return 'craft'
    if 'blueprints' in n or 'backpack' in n or 'cosmetics' in n:
        return 'gear'
    return None


def tab_index(frame, page):
    """ช่องที่เลือกอยู่ (แท็บไอคอนแถวบน) ดูจากแถบสีเขียวอมฟ้าใต้แท็บ"""
    H, W = frame.shape[:2]
    band = frame[int(0.125 * H):int(0.16 * H), int(0.04 * W):int(0.45 * W)].astype(np.int16)
    teal = (band[:, :, 1] > 80) & (band[:, :, 2] > 70) & (band[:, :, 1] - band[:, :, 0] > 50)
    col = teal.mean(0) > 0.25
    # หาช่วงสีต่อเนื่องที่ยาวที่สุด (กันสีอื่น เช่นตัวหนังสือของแถบ overlay มาปน)
    best = (0, 0, 0); st = None
    for i, v in enumerate(list(col) + [False]):
        if v and st is None:
            st = i
        elif not v and st is not None:
            if i - st > best[0]:
                best = (i - st, st, i)
            st = None
    if best[0] < 0.02 * W:
        return None
    cx = (best[1] + best[2]) / 2 / W * 2560 + 0.04 * 2560     # แปลงเป็นพิกัดจอ 2560
    if page == 'weapons':
        return int(max(0, min(2, (cx - 136) // 112)))
    if page == 'armor':
        return int(max(0, min(5, (cx - 136) // 141)))
    return None


# ลำดับแท็บเกราะในเกม → ช่องใน Build Maker (a0..a5 = Helmet, Mask, Top, Gloves, Bottoms, Shoes)
ARMOR_TAB_TO_KEY = ['a0', 'a1', 'a2', 'a4', 'a3', 'a5']    # หมวก หน้ากาก เสื้อ กางเกง ถุงมือ รองเท้า


def parse_item(lines, mats):
    """แผงขวาของหน้า Weapons/Armor → ชื่อ, บรรทัดประเภท, สไตล์ Calibration, หนัง/วัสดุ"""
    L = [l for l in lines if l['t']]
    if not L:
        return None
    name = None
    for l in L:
        t = l['t']
        if t.lower() in ('tier', 'v', 'iv', 'iii', 'ii', 'i') or len(t) < 3:
            continue
        name = re.sub(r'\s*Tier\s*[IV]+\s*$', '', t).strip(); break
    sub = next((l['t'] for l in L if re.search(r'\[.*Style\]', l['t']) or re.search(r'\b(Armor|Gear|Rifle|Pistol|Shotgun|SMG|LMG|Sniper|Bow|Crossbow|Launcher|Melee)\b', l['t'])), '')
    style = None
    m = re.search(r'\[([^\]]*Style)\]', ' '.join(l['t'] for l in L))
    if m:
        style = m.group(1).strip()
    mat = None
    sq = {squash(x): x for x in mats}
    for l in L:
        k = squash(l['t'])
        if k in sq:
            mat = sq[k]; break
    return {'name': name, 'sub': sub, 'style': style, 'mat': mat}


def parse_mod(lines):
    L = [l['t'] for l in lines if l['t']]
    name = suf = None; lvl = None
    for i, t in enumerate(L):
        if 'core effects' in t.lower() and i + 1 < len(L):
            name = L[i + 1]; break
    for i, t in enumerate(L):
        m = re.search(r'<([^>]+)>', t)
        if m:
            suf = m.group(1).strip()
            m2 = re.match(r'\s*(\d{1,2})\b', t) or (re.match(r'^\d{1,2}$', L[i - 1]) if i else None)
            if m2:
                lvl = int(m2.group(1) if m2.lastindex else m2.group(0))
            break
    return {'name': name, 'suf': suf, 'lvl': lvl} if name else None


def merge_rows(lines, H):
    """หัวแถว MOD เป็นตัวอักษรห่างๆ อาจถูกอ่านแยกเป็น 2 บรรทัด → รวมบรรทัดที่อยู่ใกล้กัน"""
    out = []
    for l in lines:
        if out and l['y0'] - out[-1]['y1'] < 0.03 * H and abs(l['x0'] - out[-1]['x0']) < 0.08 * H:
            o = out[-1]; o['t'] += l['t']; o['y1'] = max(o['y1'], l['y1']); o['x1'] = max(o['x1'], l['x1']); o['x0'] = min(o['x0'], l['x0'])
        else:
            out.append(dict(l))
    return [o for o in out if not o['t'].lower().startswith(('i the', 'the bull', 'i '))]


STAT_KEYS = [('cr', r'^crit\s*rate'), ('cd', r'^crit\s*dmg'), ('ws', r'^weak\s*spot'), ('el', r'^elemental')]


def parse_blueprint(lines):
    """กล่องรายละเอียดใบ Calibration (หน้าคราฟ/กระเป๋า)"""
    T = [l['t'] for l in lines if l['t']]
    if not any('calibration blueprint' in t.lower() for t in T[:4]):
        return None
    txt = '\n'.join(T)
    m = re.search(r'\[([^\]]*Style)\]', txt)
    style = m.group(1).strip() if m else None
    wd = re.search(r'Weapon\s*DMG\s*\+\s*([\d.]+)%\s*\[?\s*([\d.]+)%?\s*[-–~]\s*([\d.]+)%', txt)
    sub = None
    flat = re.sub(r'\s*\n\s*', ' ', txt)
    for k, rx in STAT_KEYS:
        mm = re.search(rx[1:].replace('\\s*', r'\s*') + r'[^%\[]*?\+\s*([\d.]+)%\s*\[\s*([\d.]+)%?\s*[-–~]\s*([\d.]+)%', flat, re.I)
        if mm:
            sub = {'k': k, 'v': float(mm.group(1)), 'lo': float(mm.group(2)), 'hi': float(mm.group(3))}
            break
    app = re.search(r'Applicable to (.*?)(?:\.\s*(?:Single|A one|One-time|$)|$)', flat)
    return {'style': style,
            'wd': {'v': float(wd.group(1)), 'lo': float(wd.group(2)), 'hi': float(wd.group(3))} if wd else None,
            'sub': sub, 'applies': app.group(1) if app else ''}


WEAPON_WORDS = r'\b(Rifle|Pistol|Shotgun|SMG|Submachine|LMG|Machine Gun|Sniper|Bow|Crossbow|Launcher|Melee|Weapon Features)\b|\[[^\]]*Style\]'


def is_weapon_panel(lines):
    return any(re.search(WEAPON_WORDS, l['t'], re.I) for l in lines[:14])


# ───── แถบไอคอนหมวด MOD ด้านซ้าย (หน้า Mod Backpack) ─────
CAT_DEFAULT = ['Burn', 'Power Surge', 'Frost Vortex', "The Bull's Eye", 'Fortress Warfare', 'Fast Gunner', 'Unstable Bomber', 'Bounce', 'Shrapnel']
CAT_X, CAT_Y0, CAT_DY = 0.0633, 0.172, 0.0625


def cat_rect(i, W, H):
    cx, cy = CAT_X * W, (CAT_Y0 + CAT_DY * i) * H
    r = 0.028 * H
    return int(cx - r), int(cy - r), int(cx + r), int(cy + r)


def cat_selected(frame):
    """ไอคอนหมวดที่เลือกอยู่ (มีแสงสีเขียวอมฟ้า) → index หรือ None"""
    H, W = frame.shape[:2]
    best, bi = 0.08, None
    for i in range(10):
        x0, y0, x1, y1 = cat_rect(i, W, H)
        blk = frame[max(0, y0):y1, max(0, x0):x1].astype(np.int16)
        if not blk.size:
            continue
        t = ((blk[:, :, 1] - blk[:, :, 0]) > 40).mean()
        if t > best:
            best, bi = t, i
    return bi


def mod_category(lines):
    t = ' '.join(l['t'] for l in lines).strip()
    m = re.search(r'(.+?)\s*Mods?\b', t, re.I)
    return (m.group(1) if m else t).lstrip('I|l ').strip() or None


SEARCH_BOX = (0.091, 0.872, 0.236, 0.904)   # ช่อง Search ของหน้า Mod Backpack


def nav_active(frame, nav_lines):
    """แท็บเมนูบนที่เลือกอยู่ (ตัวหนังสือสว่างกว่าแท็บอื่นชัดเจน) → ชื่อแท็บตัวเล็ก หรือ None"""
    vals = []
    for l in nav_lines:
        t = re.sub(r'[^a-z]', '', l['t'].lower())
        if len(t) < 3:
            continue
        b = frame[int(l['y0']):int(l['y1']), int(l['x0']):int(l['x1'])]
        if not b.size:
            continue
        vals.append((float(np.percentile(b.max(2), 95)), t))
    if len(vals) < 2:
        return None
    vals.sort(reverse=True)
    return vals[0][1] if vals[0][0] - vals[1][0] > 18 else None


def equipped_badge(frame):
    """การ์ดที่เลือกอยู่ (กรอบเขียวอมฟ้า) มีป้ายสีเหลืองมุมขวาบนไหม (E = ใส่อยู่ / 1,2 = ปืนที่ใส่อยู่)
    คืน True / False หรือ None ถ้าหาการ์ดที่เลือกไม่เจอ"""
    H, W = frame.shape[:2]
    x0, x1 = int(0.528 * W), int(0.717 * W); y0, y1 = int(0.19 * H), int(0.87 * H)
    reg = frame[y0:y1, x0:x1].astype(np.int16)
    teal = (reg[:, :, 1] > 150) & (reg[:, :, 2] > 140) & (reg[:, :, 0] < 120)
    rows = np.where(teal.mean(1) > 0.5)[0]
    if not len(rows):
        return None
    top = rows[0] + y0
    b = frame[top + 2:top + int(0.03 * H), int(0.700 * W):int(0.716 * W)].astype(np.int16)
    if not b.size:
        return None
    return bool(((b[:, :, 0] > 170) & (b[:, :, 1] > 140) & (b[:, :, 2] < 110)).mean() > 0.03)
