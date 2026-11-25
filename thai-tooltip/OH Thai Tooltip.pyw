# -*- coding: utf-8 -*-
"""OH Thai Tooltip — ชี้ที่ไอเทมใน Once Human แล้วขึ้นคำแปลไทยข้างกล่องรายละเอียด
ทำงานจากภาพหน้าจออย่างเดียว: ไม่อ่านหน่วยความจำเกม ไม่แก้ไฟล์เกม ไม่ส่งปุ่มเข้าเกม
by MrSmitety Hub"""
VERSION = '0.8.2'
APP = 'OH Thai Tooltip'
PORT = 47616
GAME_EXE = 'once_human.exe'

import os, sys, json, time, re, threading, queue, hashlib, socket, traceback, urllib.request, urllib.parse, urllib.error

IS_WIN = sys.platform == 'win32'
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')
BASE = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'OHThaiTooltip')
os.makedirs(DATA, exist_ok=True)
LOG = os.path.join(DATA, 'OH Thai Tooltip.log')


def log(*a):
    try:
        with open(LOG, 'a', encoding='utf-8') as f:
            f.write(time.strftime('%Y-%m-%d %H:%M:%S ') + ' '.join(str(x) for x in a) + '\n')
    except Exception:
        pass


try:
    if os.path.getsize(LOG) > 2_000_000:
        os.remove(LOG)
except Exception:
    pass

if IS_WIN:
    import ctypes
    from ctypes import wintypes
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass
    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

import tkinter as tk
import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, BASE)
import engine, detect   # noqa: E402

# เวอร์ชัน Member: build ที่มีไฟล์ member_edition.flag ต้องตรวจยศ Member ผ่าน Discord ก่อนถึงจะแปลได้
MEMBER_ED = os.path.exists(os.path.join(BASE, 'member_edition.flag'))
if MEMBER_ED:
    APP = 'OH Thai Tooltip Member'
GATE = threading.Event()          # เปิด = แปลได้
if not MEMBER_ED:
    GATE.set()

# ───────────── ตั้งค่า ─────────────
SET_PATH = os.path.join(DATA, 'settings.json')
DEFAULT = {'enabled': True, 'mt': True, 'any_window': False, 'show_en': False, 'scale': 1.0}


def load_set():
    s = dict(DEFAULT)
    try:
        s.update(json.load(open(SET_PATH, encoding='utf-8')))
    except Exception:
        pass
    return s


SET = load_set()


def save_set():
    try:
        json.dump(SET, open(SET_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    except Exception:
        pass


# ───────────── Windows helpers ─────────────
def cursor_pos():
    if not IS_WIN:
        return (0, 0)
    p = wintypes.POINT()
    user32.GetCursorPos(ctypes.byref(p))
    return (p.x, p.y)


def fg_is_game():
    if not IS_WIN:
        return True
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False
    pid = wintypes.DWORD()
    user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    h = kernel32.OpenProcess(0x1000, False, pid.value)   # PROCESS_QUERY_LIMITED_INFORMATION
    if not h:
        return False
    try:
        buf = ctypes.create_unicode_buffer(520)
        n = wintypes.DWORD(520)
        if kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
            return os.path.basename(buf.value).lower() == GAME_EXE
    finally:
        kernel32.CloseHandle(h)
    return False


def make_clickthrough(win):
    if not IS_WIN:
        return
    try:
        hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()
        GWL_EXSTYLE = -20
        st = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        st |= 0x00080000 | 0x00000020 | 0x00000080 | 0x08000000   # LAYERED|TRANSPARENT|TOOLWINDOW|NOACTIVATE
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, st)
    except Exception as e:
        log('clickthrough', e)


# ───────────── แปลด้วยเครื่อง (สำรอง) ─────────────
MT_PATH = os.path.join(DATA, 'mt_cache.json')
try:
    MT_CACHE = json.load(open(MT_PATH, encoding='utf-8'))
except Exception:
    MT_CACHE = {}
_mt_lock = threading.Lock()
PROTECT = ["Unstable Bomber", "Power Surge", "Frost Vortex", "Fast Gunner", "Fortress Warfare", "The Bull's Eye",
           "Bull's Eye", "Shrapnel", "Bounce", "Burn", "Psi Intensity", "Weakspot", "Deviant Power", "Deviation",
           "Deviant", "Sanity", "Stamina", "Super Armor", "Status Vulnerability", "Weapon Vulnerability", "Crit"]
FIX = [("ดาเมจที่สำคัญ", "ดาเมจคริ"), ("ความเสียหาย", "ดาเมจ"), ("ความเสียหายที่สำคัญ", "ดาเมจคริ")]


MT_PAUSE = [0.0]


def mt(text):
    key = text.strip()
    if key in MT_CACHE:
        return MT_CACHE[key]
    if time.time() < MT_PAUSE[0]:
        raise RuntimeError('mt paused')                 # Google จำกัดจำนวนครั้ง พักก่อน
    s = key
    toks = []
    for i, w in enumerate(sorted(PROTECT, key=len, reverse=True)):
        if w in s:
            t = f'ZQ{len(toks)}X'
            s = s.replace(w, t)
            toks.append((t, w))
    s = s.replace('DMG', 'damage')
    url = 'https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=th&dt=t&q=' + urllib.parse.quote(s)
    req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
    try:
        d = json.loads(urllib.request.urlopen(req, timeout=5).read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        if e.code in (429, 500, 502, 503):
            MT_PAUSE[0] = time.time() + 600             # โดนจำกัด: พักแปลสำรอง 10 นาที
        raise
    out = ''.join(x[0] for x in d[0] if x and x[0])
    for t, w in toks:
        out = re.sub(re.escape(t), w, out, flags=re.I)
    for a, b in FIX:
        out = out.replace(a, b)
    with _mt_lock:
        MT_CACHE[key] = out
        if len(MT_CACHE) % 5 == 0:
            try:
                json.dump(MT_CACHE, open(MT_PATH, 'w', encoding='utf-8'), ensure_ascii=False)
            except Exception:
                pass
    return out


# ───────────── อ่าน + แปล ─────────────
class Reader:
    def __init__(self):
        try:
            from rapidocr import RapidOCR          # rapidocr 3.x (Python 3.8–3.14)
            self.v3 = True
        except ImportError:
            from rapidocr_onnxruntime import RapidOCR
            self.v3 = False
        try:
            # ตัวหากรอบข้อความ: ย่อภาพด้านยาวไม่เกิน 736 (ค่าเดิมขยายภาพขึ้น ทำให้ช้ากว่า 5 เท่า)
            self.ocr = RapidOCR(params={"Det.limit_type": "max", "Det.limit_side_len": 736}) if self.v3 else RapidOCR()
        except Exception:
            self.ocr = RapidOCR()
        self.db = engine.DB(os.path.join(BASE, 'oh_thai_db.json'))
        self.db.add_user(os.path.join(DATA, 'custom_th.json'))
        self.web = None
        for pth in (os.path.join(DATA, 'oh_web.json'), os.path.join(BASE, 'oh_web.json')):   # ที่โหลดอัปเดตมาก่อน
            try:
                self.set_web(json.load(open(pth, encoding='utf-8')))
                break
            except Exception:
                continue

    def set_web(self, web):
        names = {}
        for cat in ('weapons', 'kg', 'mods', 'food', 'cradle'):
            for k in web.get(cat, {}):
                names[k.lower()] = (cat, k)
        for a_, k in web.get('alias', {}).items():
            for cat in ('kg', 'mods'):
                if k in web.get(cat, {}):
                    names[a_.lower()] = (cat, k)
        if web.get('pairs'):
            self.db.apply_pairs(web['pairs'])
        self.web, self.names = web, names
        if getattr(self, 'member', None):
            self.apply_member(self.member)              # คำแปลมือของ Member ทับข้อมูลเว็บเสมอ

    def apply_member(self, pack):
        self.member = pack
        self.db.apply_pairs(pack.get('tmpl') or {})
        self.db.set_terms(pack.get('terms') or {})

    # ── โหมดเร็ว: อ่านแค่แถบหัว → จำชื่อ → ดึงคำแปลจากข้อมูลเว็บ ──
    def read_header(self, crop, hb):
        h = max(20, min(crop.shape[0], hb + 4))
        res = self.ocr_band(crop[:h, :, ::-1], 0)
        lines = engine.lines_from_ocr(res)
        return lines

    def lookup(self, lines):
        if not self.web or not lines:
            return None
        from rapidfuzz import process, fuzz
        texts = [L['text'] for L in lines]
        typ = None
        if len(texts) >= 2 and self.db.term(re.sub(r'\s*\|.*$', '', texts[-1])):
            typ = self.db.term(re.sub(r'\s*\|.*$', '', texts[-1]))
            texts = texts[:-1]
        elif len(texts) >= 2:
            t2 = re.sub(r'\s*(Set)\s*$', ' Set', texts[-1])
            if self.db.term(t2) or re.search(r'Blueprint|Mods?|Food|Drink|Cradle', texts[-1]):
                typ = self.db.term(t2) or texts[-1]
                texts = texts[:-1]
        name = ' '.join(texts)
        name = re.sub(r'\s*Tier\s*[IVX]*\s*$', '', name).strip()
        name = re.sub(r'^[\dS$&]\s+(?=[A-Z])', '', name)
        base = re.sub(r'\s*B\.?\s*P\.?$', '', name).strip()
        base = re.sub(r'\s*<[^>]*>?\s*$', '', base).strip()
        if len(base) < 3:
            return None
        hit = process.extractOne(base.lower(), list(self.names), scorer=fuzz.ratio, score_cutoff=88)
        W = self.web
        lh = float(np.median([L['y1'] - L['y0'] for L in lines])) * 0.85
        items = [('name', name, name)]
        if typ:
            items.append(('term', typ, typ))
        if hit:
            cat, key = self.names[hit[0]]
            if cat == 'weapons':
                w = W['weapons'][key]
                items.append(('term', 'ความสามารถปืน', ''))
                if w.get('kw'):
                    items.append(('title', '[' + w['kw'] + ']', ''))
                if w.get('kwd'):
                    items.append(('ok', w['kwd'], ''))
                items += [('ok', t, '') for t in w['lines']]
            elif cat == 'kg':
                items.append(('term', 'เอฟเฟกต์ Key Gear', ''))
                items += [('ok', t, '') for t in W['kg'][key]]
            elif cat == 'mods':
                m = W['mods'][key]
                items.append(('term', 'เอฟเฟกต์ม็อด', ''))
                items.append(('ok', m['effect'], ''))
                if m.get('flash'):
                    items.append(('ok', 'Flash Effect: ' + m['flash'], ''))
            elif cat == 'food':
                f = W['food'][key]
                items.append(('term', 'ผลของอาหาร', ''))
                items.append(('ok', f['th'], ''))
                if f.get('dur'):
                    items.append(('ok', f'นาน {int(f["dur"]) // 60} นาที', ''))
            else:
                items.append(('ok', W['cradle'][key], ''))
            return {'items': items, 'lh': lh, 'web': True, 'cat': cat}
        first = base.split()[0] if base.split() else ''
        st = first + ' Set'
        if st in W['sets']:
            items.append(('term', 'เอฟเฟกต์เซ็ต', ''))
            items.append(('title', st, ''))
            items += [('ok', t, '') for t in W['sets'][st]]
            return {'items': items, 'lh': lh, 'web': True, 'cat': 'sets'}
        return None

    @staticmethod
    def with_stats(web, ocr):
        """ของที่รู้จัก: ใช้ข้อความจากเว็บทั้งหมด + ค่าพื้นฐานจริงจากเกม (ตัวเลขเปลี่ยนตามเลเวล/ดาว)"""
        stats = [it for it in (ocr or {}).get('items', []) if it[0] == 'term' and re.search(r'\d', it[1])]
        if not stats:
            return web
        items = list(web['items'])
        k = 1 + (1 if len(items) > 1 and items[1][0] == 'term' and not re.search(r'\d', items[1][1])
                 and items[1][1] not in ('ความสามารถปืน', 'เอฟเฟกต์เซ็ต', 'เอฟเฟกต์ม็อด', 'เอฟเฟกต์ Key Gear') else 0)
        out = dict(web)
        out['items'] = items[:k] + [('term', 'ค่าพื้นฐาน', '')] + stats + items[k:]
        return out

    @staticmethod
    def merge(web, ocr):
        """ผลอ่านเต็มกล่อง (ตัวเลขจริง) + เติมบรรทัดจากเว็บที่ OCR อ่านไม่ถึง (เช่น กล่องตกขอบจอ)"""
        if not ocr or sum(1 for it in ocr['items'] if it[0] in ('ok', 'term', 'title')) < 3:
            return web
        from rapidfuzz import fuzz
        have = [it[1] for it in ocr['items'] if it[0] == 'ok' and it[1]]
        add = [it for it in web['items'] if it[0] == 'ok' and re.search(r'[\u0E00-\u0E7F]', it[1])   # ค่าสถานะล้วน OCR มีแล้ว
               and not any(fuzz.ratio(it[1], h) > 70 for h in have)]
        out = dict(ocr)
        out['items'] = list(ocr['items']) + add
        out['web'] = True
        return out

    def bands(self, crop, step=330):
        """แบ่งกล่องเป็นช่วงๆ ตรงแถวว่าง (ไม่ตัดกลางบรรทัด) เพื่ออ่านทีละช่วงแล้วโชว์ทันที"""
        g = crop.mean(2)
        txt = (g > 140).sum(1) > 2
        H = crop.shape[0]; cuts = [0]; y = step
        while y < H - 120:
            best = None
            for yy in range(y, min(H - 60, y + 160)):
                if not txt[max(0, yy - 4):yy + 4].any():
                    best = yy; break
            if best is None:
                y += 80; continue
            cuts.append(best); y = best + step
        cuts.append(H)
        return [(cuts[i], cuts[i + 1]) for i in range(len(cuts) - 1)]

    def ocr_band(self, img, y0):
        if self.v3:
            r = self.ocr(np.ascontiguousarray(img), use_cls=False)
            if r.boxes is None:
                return []
            return [([[p[0], p[1] + y0] for p in r.boxes[i].tolist()], r.txts[i], r.scores[i]) for i in range(len(r.txts))]
        res, _ = self.ocr(np.ascontiguousarray(img), use_cls=False)
        return [([[p[0], p[1] + y0] for p in b], t, sc) for b, t, sc in (res or [])]

    def read_iter(self, crop):
        """อ่านทีละช่วงจากบนลงล่าง คืนผลสะสมหลังอ่านแต่ละช่วง"""
        h = crop.shape[0]
        sc = 1300 / h if h > 1300 else 1.0
        img = crop
        if sc < 1:
            img = np.asarray(Image.fromarray(crop).resize((int(crop.shape[1] * sc), int(h * sc)), Image.BILINEAR))
        res = []
        last = None
        bands = self.bands(img)
        for k, (a, b) in enumerate(bands):
            res += self.ocr_band(img[a:b, :, ::-1], a)
            stop = any(re.search(r'view\s*details|ask\s*wiki|^\W*[A-Z]?\W*equip\W*$', t, re.I) for _, t, _ in res)
            d = self.finish(res, sc)
            if d:
                last = d
                yield d, (k == len(bands) - 1 or stop)
            if stop:
                break
        if last is None:
            yield None, True

    def finish(self, res, sc):
        lines = engine.lines_from_ocr(res)
        self.last_lines = [L['text'] for L in lines]
        # ตัดตั้งแต่แถบปุ่มด้านล่าง (Tab View Details / Ask Wiki) ลงไป
        cut = []
        for L in lines:
            q = engine.squash(L['text'])
            if 'viewdetails' in q or 'askwiki' in q or re.fullmatch(r'[a-z]?(equip|unequip|use|craft)', q):
                break
            cut.append(L)
        if not cut:
            return None
        lh = float(np.median([L['y1'] - L['y0'] for L in cut])) / sc
        items = engine.translate_lines(self.db, cut)
        # บรรทัดก่อนหัวข้อแรก = ชื่อไอเทม/ประเภท: เก็บไว้เป็นหัวข้อ ตัดเลขลอยๆ (เช่น จำนวนดาว) ทิ้ง
        k0 = next((i for i, it in enumerate(items) if it[0] in ('term', 'ok', 'title')), 0)
        head = []
        for it in items[:k0 + 3]:
            if it[0] in ('raw', 'keep') and re.search(r'[A-Za-z]{3}', it[2]):
                nm = re.sub(r'\s*Tier\s*[IVX]*\s*$', '', it[2]).strip()
                nm = re.sub(r'^[\dS$&]\s+(?=[A-Z])', '', nm)        # ไอคอนหน้าชื่อที่ OCR อ่านเป็นตัวเลข
                if head and head[-1][0] == 'name':
                    head[-1] = ('name', head[-1][1] + ' ' + nm, head[-1][2] + ' ' + it[2])   # ชื่อยาวตัดบรรทัด
                else:
                    head.append(('name', nm, it[2]))
            elif it[0] != 'keep':
                head.append(it)
        items = head + items[k0 + 3:]
        # แถว "DMG Fire Rate MAG" + "255 650 60" -> รวมเป็นแถวเดียว
        out = []
        for it in items:
            if it[0] == 'keep' and out and out[-1][0] == 'term' and re.fullmatch(r'[\d\s.,%]+', it[2]):
                labs = [x for x in re.split(r'\s{3}', out[-1][1]) if x]
                vals = it[2].split()
                if len(labs) == len(vals) > 1:
                    out[-1] = ('term', '   ·   '.join(f'{a} {b}' for a, b in zip(labs, vals)), out[-1][2] + ' ' + it[2])
                    continue
            out.append(it)
        out = [it for it in out if 'levelsyieldbetter' not in engine.squash(it[2] or '')]   # บรรทัดคำแนะนำเลเวลม็อด ไม่ต้องแปล
        if sum(1 for it in out if it[0] in ('ok', 'term', 'title')) < 2:
            return None                                         # ไม่ใช่กล่องข้อมูลไอเทม (detect พลาด)
        seen_t = set(); items = []
        for it in out:
            if it[0] == 'title':
                if it[1] in seen_t:
                    continue
                seen_t.add(it[1])
            items.append(it)
        return {'items': items, 'lh': lh}


# ───────────── หน้าต่างแสดงผล ─────────────
BG = '#1b2027'; PANEL = '#20262e'; FG = '#e9edf2'; DIM = '#8b95a5'; TEAL = '#5ff0e6'; GOLD = '#e8c46a'
MTC = '#eadfc0'; LINE = '#323a45'; SEC = '#262d36'
SECTIONS = {'ค่าพื้นฐาน', 'ความสามารถปืน', 'เอฟเฟกต์เซ็ต', 'เอฟเฟกต์เซ็ตเกราะ', 'เอฟเฟกต์ม็อด', 'ค่าสถานะ', 'สกิล',
            'สกิล Deviation', 'สกิลต่อสู้', 'ผลของอาหาร', 'เอฟเฟกต์หลัก', 'คำอธิบาย', 'เอฟเฟกต์'}
KWS = ["Unstable Bomber", "Power Surge", "Frost Vortex", "Fast Gunner", "Fortress Warfare", "The Bull's Eye",
       "Shrapnel", "Bounce", "Burn", "Lone Shadow", "Bastille", "Sync", "Overload", "Upper Hand", "Deviant Power"]
KW_RE = re.compile('|'.join(re.escape(k) for k in sorted(KWS, key=len, reverse=True)) + r"|\[[^\]]{2,30}\]")
NUM_RE = re.compile(r'[+\-−]?\d+(?:[.,]\d+)?\s?%?')
UIF = 'Leelawadee UI'


def _hex(c):
    return '#%02x%02x%02x' % tuple(int(max(0, min(255, v))) for v in c)


def _mix(c, k):
    return tuple(int(v * k) for v in c)


class Overlay:
    """กล่องแปลหน้าตาแบบกล่องข้อมูลบนหน้าบิ้วของเว็บ"""

    def __init__(self, root):
        self.root = root
        self.w = tk.Toplevel(root)
        self.w.overrideredirect(True)
        self.w.attributes('-topmost', True)
        try:
            self.w.attributes('-alpha', 0.97)
        except Exception:
            pass
        self.w.configure(bg=BG, highlightthickness=1, highlightbackground='#39424e')
        self.body = tk.Frame(self.w, bg=BG)
        self.body.pack(fill='both', expand=True)
        self.w.withdraw()
        self.visible = False
        self.rect = None
        self.size = None
        self.w.update_idletasks()
        make_clickthrough(self.w)
        self._round()

    def _round(self):
        if not IS_WIN:
            return
        try:
            hwnd = user32.GetParent(self.w.winfo_id()) or self.w.winfo_id()
            v = ctypes.c_int(2)    # DWMWCP_ROUND (Windows 11: มุมมน + เงา)
            ctypes.windll.dwmapi.DwmSetWindowAttribute(hwnd, 33, ctypes.byref(v), 4)
        except Exception:
            pass

    def hide(self):
        if self.visible:
            self.w.withdraw()
            self.visible = False
            self.rect = None
            self.anchor_y = None

    # ── ส่วนประกอบ ──
    def _header(self, name, sub, hdr, px, width):
        base = hdr or (150, 120, 70)
        h = int(px * (3.3 if sub else 2.4))
        cv = tk.Canvas(self.body, width=width, height=h, bg=BG, highlightthickness=0, bd=0)
        cv.pack(fill='x')
        for x in range(0, width, 4):   # ไล่สีจากซ้าย (เข้ม) ไปขวา (สว่าง) แบบแถบหัวในเกม
            k = 0.62 + 0.38 * (x / max(1, width))
            cv.create_rectangle(x, 0, x + 4, h, fill=_hex(_mix(base, k)), width=0)
        cv.create_rectangle(0, h - 3, width, h, fill=_hex(_mix(base, 1.15)), width=0)
        lum = 0.299 * base[0] + 0.587 * base[1] + 0.114 * base[2]
        tc = '#15171b' if lum > 92 else '#ffffff'
        sc = '#1c1f24' if lum > 92 else '#eef2f6'
        cv.create_text(16, int(px * 0.55), text=name or 'แปลไทย', anchor='nw', fill=tc,
                       font=('Segoe UI Semibold', -int(px * 1.15)), width=width - 32)
        if sub:
            cv.create_text(16, int(px * 1.95), text=sub, anchor='nw', fill=sc, font=(UIF, -int(px * 0.86), 'bold'))

    def _section(self, text, px):
        f = tk.Frame(self.body, bg=SEC)
        f.pack(fill='x', pady=(10, 4))
        tk.Frame(f, bg=TEAL, width=3).pack(side='left', fill='y')
        tk.Label(f, text=text, bg=SEC, fg='#d5dde8', font=(UIF, -int(px * 0.92), 'bold'), anchor='w',
                 padx=10, pady=4).pack(side='left', fill='x')

    def _dash(self, width):
        cv = tk.Canvas(self.body, width=width, height=3, bg=BG, highlightthickness=0, bd=0)
        cv.pack(fill='x', padx=14)
        for x in range(0, width - 28, 7):
            cv.create_line(x, 1, x + 3, 1, fill=LINE)

    def _grid(self, pairs, px, width):
        f = tk.Frame(self.body, bg=PANEL)
        f.pack(fill='x', padx=12, pady=(2, 4))
        n = len(pairs)
        for i, (lab, val) in enumerate(pairs):
            c = tk.Frame(f, bg=PANEL)
            c.grid(row=0, column=i * 2, sticky='nsew', pady=6)
            f.grid_columnconfigure(i * 2, weight=1)
            tk.Label(c, text=lab, bg=PANEL, fg=DIM, font=(UIF, -int(px * 0.78))).pack()
            tk.Label(c, text=val, bg=PANEL, fg='#ffffff', font=('Segoe UI Semibold', -int(px * 1.35))).pack()
            if i < n - 1:
                tk.Frame(f, bg=LINE, width=1).grid(row=0, column=i * 2 + 1, sticky='ns', pady=10)

    def _stat(self, lab, val, px):
        f = tk.Frame(self.body, bg=BG)
        f.pack(fill='x', padx=16, pady=(3, 1))
        tk.Label(f, text=lab, bg=BG, fg='#cfd6e0', font=(UIF, -px), anchor='w').pack(side='left')
        if val:
            tk.Label(f, text=val, bg=BG, fg=FG, font=('Segoe UI Semibold', -px), anchor='e').pack(side='right')

    def _rich(self, text, px, width, color=FG, bullet='▪'):
        """ย่อหน้ามีสี: ตัวเลข = ฟ้าอมเขียว, คีย์เวิร์ด = ทอง"""
        f = tk.Frame(self.body, bg=BG)
        f.pack(fill='x', padx=(14, 12), pady=(4, 2))
        if bullet:
            tk.Label(f, text=bullet, bg=BG, fg='#7d8794', font=(UIF, -int(px * 0.8))).pack(side='left', anchor='n', pady=(2, 0))
        t = tk.Text(f, bg=BG, fg=color, font=(UIF, -px), wrap='word', bd=0, highlightthickness=0,
                    padx=6, pady=0, width=10, height=1, cursor='arrow', spacing1=1, spacing3=1)
        t.pack(side='left', fill='x', expand=True)
        t.tag_configure('num', foreground=TEAL)
        t.tag_configure('kw', foreground=GOLD)
        pos = 0
        spans = sorted([(m.start(), m.end(), 'kw') for m in KW_RE.finditer(text)] +
                       [(m.start(), m.end(), 'num') for m in NUM_RE.finditer(text)])
        for a, b, tag in spans:
            if a < pos:
                continue
            t.insert('end', text[pos:a]); t.insert('end', text[a:b], tag); pos = b
        t.insert('end', text[pos:])
        t.configure(width=1, state='disabled')
        self._texts.append(t)

    # ── แสดงผล ──
    def show(self, data, rect, mon):
        x0, y0, x1, y1 = rect
        width = max(380, min(620, int((x1 - x0) * 0.98)))
        px = max(15, min(24, int(data['lh'] * 0.72 * SET.get('scale', 1.0))))
        self._begin()
        self._texts = []
        items = list(data['items'])
        name = None; sub = None
        while items and items[0][0] == 'name':
            name = (name + ' ' if name else '') + items.pop(0)[1]
        if items and items[0][0] == 'term' and not re.search(r'\d', items[0][1]) and items[0][1] not in SECTIONS:
            sub = items.pop(0)[1]
        self._header(name, sub, data.get('hdr'), px, width)
        prev = None
        for kind, th, en in items:
            if kind == 'name':
                self._stat(th, '', px)
            elif kind == 'term':
                if not re.search(r'\d', th):
                    self._section(th, px)
                elif '·' in th:
                    pairs = []
                    for part in th.split('·'):
                        m = re.match(r'\s*(.*?)\s+([\d.,/%]+)\s*$', part)
                        if m:
                            pairs.append((m.group(1), m.group(2)))
                    if pairs:
                        self._grid(pairs, px, width)
                    else:
                        self._stat(th, '', px)
                else:
                    m = re.match(r'\s*(.*?)\s+([+\-]?[\d.,/]+%?)\s*$', th)
                    self._stat(m.group(1), m.group(2), px) if m else self._stat(th, '', px)
            elif kind == 'title':
                t = re.sub(r'(?<=[a-z])(?=[A-Z])', ' ', th)
                tk.Label(self.body, text=t, bg=BG, fg=GOLD, font=(UIF, -px, 'bold'), anchor='w',
                         padx=16).pack(fill='x', pady=(6, 0))
            elif kind == 'keep':
                if not re.fullmatch(r'[\d\s.,%:/+\-]+', en):
                    self._stat(en, '', px)
            elif kind == 'ok' and re.fullmatch(r"[A-Za-z' ()/\-]{3,40}\s[+\-−]?\d[\d.,]*%?", th.strip()):
                m = re.match(r"(.*\S)\s+(\S+)$", th.strip())
                self._stat(m.group(1), m.group(2), px)      # ค่าสถานะบรรทัดเดียว เช่น Roll Stamina Cost -20%
                kind = 'term'
            elif kind == 'ok':
                if prev == 'ok':
                    self._dash(width)
                self._rich(th, px, width)
                if SET.get('show_en') and en:
                    self._rich(en, px - 3, width, color=DIM, bullet='')
            else:   # raw
                if not th and len(en) <= 26 and not re.search(r'[.,:;]$', en) and en[:1].isupper():
                    tk.Label(self.body, text=en, bg=BG, fg=GOLD, font=(UIF, -px, 'bold'), anchor='w',
                             padx=16).pack(fill='x', pady=(6, 0))
                elif th:
                    if prev in ('ok', 'raw'):
                        self._dash(width)
                    self._rich(th, px, width, color=MTC, bullet='≈')
                else:
                    self._rich(en, px - 2, width, color=DIM, bullet='')
            prev = kind
        tk.Label(self.body, text='OH Thai Tooltip  ·  Ctrl+Alt+T เปิด/ปิด', bg=BG, fg='#4f5966',
                 font=(UIF, -max(11, px - 6)), anchor='e', padx=12).pack(fill='x', pady=(8, 6))
        self._finish(width, rect, mon)

    def _begin(self):
        """ซ่อนชั่วคราวระหว่างวาดใหม่ กันภาพเก่าซ้อน/กระตุก"""
        if self.visible:
            try:
                self.w.attributes('-alpha', 0.0)
            except Exception:
                pass
        for c in self.body.winfo_children():
            c.destroy()

    def _finish(self, width, rect, mon):
        # รอบ 1: กำหนดความกว้างจริงก่อน แล้วนับบรรทัดที่ตัดคำจริง
        self.w.update_idletasks()
        self.size = (width, min(2000, self.w.winfo_reqheight()))
        self.place(rect, mon, show=False)
        self.w.update()
        for t in getattr(self, '_texts', []):
            try:
                t.update_idletasks()
                n = t.count('1.0', 'end', 'displaylines')
                n = n[0] if isinstance(n, tuple) else n
                t.configure(height=max(1, int(n or 1)))
            except Exception:
                pass
        # รอบ 2: ความสูงจริง แล้วค่อยโชว์
        self.w.update_idletasks()
        self.size = (width, self.w.winfo_reqheight())
        self.place(rect, mon)
        try:
            self.w.attributes('-alpha', 0.97)
        except Exception:
            pass

    def place(self, rect, mon, show=True):
        """วางกล่องแปลข้างกล่องเกม (ซ้ายก่อน ถ้าไม่พอไปขวา) เปิดอยู่แล้วค้างที่เดิม"""
        x0, y0, x1, y1 = rect
        width, h = self.size
        mx0, my0, mw, mh = mon
        gap = 10
        if self.visible and self.rect:
            x, y = self.rect[0], (self.anchor_y if getattr(self, 'anchor_y', None) is not None else self.rect[1])
        elif x0 - gap - width >= mx0:
            x, y = x0 - gap - width, y0
        elif x1 + gap + width <= mx0 + mw:
            x, y = x1 + gap, y0
        else:
            x, y = max(mx0, x0 - width // 2), y0
        if not (self.visible and self.rect):
            self.anchor_y = y                           # จำตำแหน่งบนสุดที่ตั้งใจไว้ (ไม่ใช่ค่าที่ถูกดันขึ้น)
        y = max(my0, min(y, my0 + mh - h - 8))
        self.w.geometry(f'{width}x{h}+{int(x)}+{int(y)}')
        if not self.visible:
            try:
                self.w.attributes('-alpha', 0.0)
            except Exception:
                pass
            self.w.deiconify()
            self.visible = True
            make_clickthrough(self.w)
            self._round()
        self.w.lift()
        if show:
            self.rect = (int(x), int(y), int(x) + width, int(y) + h)
        elif not self.rect:
            self.rect = (int(x), int(y), int(x) + width, int(y) + h)

    def loading(self, rect, mon):
        self._begin()
        self._texts = []
        x0, y0, x1, y1 = rect
        width = max(380, min(620, int((x1 - x0) * 0.98)))
        self._header('กำลังแปล…', None, (70, 78, 90), 16, width)
        self._finish(width, rect, mon)


# ───────────── งานเบื้องหลัง ─────────────
class Worker(threading.Thread):
    def __init__(self, q, ov):
        super().__init__(daemon=True)
        self.q = q; self.ov = ov
        self.reader = None
        self.cache = {}
        self.thumbs = {}
        self.cur_box = None
        self.box_now = None
        self.prev_th = None
        self.cur_thumb = None
        self.cur_rect = None
        self.miss = 0
        self.cur_key = None
        self.busy = False
        self.job_key = None
        self.debug_next = False
        self.running = True

    def thumb(self, crop, hb):
        """ลายนิ้วมือของกล่อง: ค่าเฉลี่ยเป็นบล็อกของแถบหัว + ช่วง 44-200px ใต้หัว (ข้ามแถวดาวที่กระพริบ)
        ลบค่าเฉลี่ยออก จึงไม่สนแสงวิ่ง และไม่สนฉากที่ขยับด้านล่างกล่อง"""
        g = crop[:, :, :3].mean(2).astype(np.float32)
        if hb < 12 or g.shape[0] < hb + 30 or g.shape[1] < 60:
            return None

        def blocks(a, rows, cols):
            im = Image.fromarray(a).resize((cols, rows), Image.BOX)
            v = np.asarray(im, dtype=np.float32)
            return v - v.mean()
        # แถบหัว: ใช้ 'ตัวหนังสือสีเข้ม' (ชื่อไอเทม) ไม่ใช้ความสว่าง จึงไม่สนแสงวิ่ง/สีรุ้ง
        hg = g[2:hb - 2, 6:-6]
        bg = np.asarray(Image.fromarray(hg.astype(np.uint8)).filter(ImageFilter.MaxFilter(9)), dtype=np.float32)
        hm = ((bg - hg) > 45).astype(np.float32) * 255   # จุดที่เข้มกว่ารอบข้างชัดๆ = ตัวหนังสือ
        head = np.asarray(Image.fromarray(hm).resize((96, 8), Image.BOX), dtype=np.float32)
        return np.concatenate([head.ravel(), blocks(g[min(hb + 44, g.shape[0] - 20):hb + 200, 6:-6], 16, 48).ravel()])

    def same(self, a, b):
        """กล่องเดียวกันจริงไหม: ชื่อในแถบหัวต้องแทบเหมือนเป๊ะ (ของต่างชิ้น ค่าต่าง ≥17, แสงวิ่งแรงๆ ≤5)"""
        if a is None or b is None or a.shape != b.shape:
            return False
        n = 8 * 96
        return float(np.abs(a[:n] - b[:n]).mean()) < 10 and float(np.abs(a[n:] - b[n:]).mean()) < 3.5

    def run(self):
        try:
            self.reader = Reader()
            self.q.put(('ready', None))
        except Exception:
            log('reader init', traceback.format_exc())
            self.q.put(('fatal', 'โหลดตัวอ่านตัวอักษรไม่สำเร็จ ดู log ที่ ' + LOG))
            return
        import mss
        sct = mss.mss()
        last_pos = None; still = time.time()
        while self.running:
            time.sleep(0.12)
            try:
                if not GATE.is_set() or not SET['enabled'] or not (SET['any_window'] or fg_is_game()):
                    if self.cur_rect:
                        self.q.put(('hide', None)); self.cur_rect = None; self.cur_thumb = None
                    continue
                pos = cursor_pos()
                if pos != last_pos:
                    last_pos = pos; still = time.time()
                mon = None
                for m in sct.monitors[1:]:
                    if m['left'] <= pos[0] < m['left'] + m['width'] and m['top'] <= pos[1] < m['top'] + m['height']:
                        mon = m; break
                mon = mon or sct.monitors[1]
                frame = np.asarray(sct.grab(mon))[:, :, 2::-1]   # BGRA -> RGB
                ign = None
                if self.ov.rect:
                    r = self.ov.rect
                    ign = (r[0] - mon['left'], r[1] - mon['top'], r[2] - mon['left'], r[3] - mon['top'])
                rect = detect.find_tooltip(frame, (pos[0] - mon['left'], pos[1] - mon['top']), ign)
                if self.debug_next:
                    self.debug_next = False
                    self.save_debug(frame, rect)
                if not rect:
                    self.miss += 1
                    if self.cur_rect and self.miss >= 4:      # หายจริงต่อเนื่อง ~0.5 วิ ค่อยซ่อน (กันกระพริบ)
                        self.q.put(('hide', None)); self.cur_rect = None; self.cur_thumb = None
                    continue
                self.miss = 0
                x0, y0, x1, y1 = rect
                hb = max(0, detect.LAST_HEAD - y0)              # ใช้เฉพาะเนื้อหาใต้แถบหัว (แถบหัวบางแบบมีแสงวิ่ง)
                if self.cur_rect and self.cur_box:
                    cx0, cy0, cx1, cy1, chb = self.cur_box
                    if abs(cx0 - x0) <= 16 and abs(cy0 - y0) <= 16 and abs((cx1 - cx0) - (x1 - x0)) <= 24:
                        x0, y0, x1, hb = cx0, cy0, cx1, chb     # กรอบสั่นนิดหน่อย = กล่องเดิม ใช้กรอบเดิม (กันอ่านซ้ำ)
                        y1 = max(y1, cy1)
                crop = np.ascontiguousarray(frame[y0:y1, x0:x1])
                self.box_now = (x0, y0, x1, y1, hb)
                th = self.thumb(crop, hb)
                if th is None:
                    continue
                absr = (x0 + mon['left'], y0 + mon['top'], x1 + mon['left'], y1 + mon['top'])
                monr = (mon['left'], mon['top'], mon['width'], mon['height'])
                same = self.cur_rect and self.same(th, self.cur_thumb)
                if same:
                    if self.cur_key in self.cache or self.job_key == self.cur_key or self.busy:
                        continue
                if not same and self.cur_box and self.cur_thumb is not None and th.shape == self.cur_thumb.shape \
                        and self.box_now[:2] == self.cur_box[:2]:
                    log('flip', round(float(np.abs(th - self.cur_thumb).mean()), 2))   # กรอบเดิมแต่ภาพต่าง (ไว้ดีบัก)
                key = self.cur_key if same else hashlib.md5((th // 32).astype(np.int8).tobytes()).hexdigest()
                if not same and key not in self.cache:
                    for k2, t2 in self.thumbs.items():           # เคยอ่านกล่องนี้แล้ว (ภาพต่างกันนิดหน่อย)
                        if k2 in self.cache and self.same(th, t2):
                            key = k2; break
                self.thumbs[key] = th
                if len(self.thumbs) > 300:
                    self.thumbs.pop(next(iter(self.thumbs)))
                if key in self.cache:
                    if self.cache[key] is None:                 # เคยอ่านแล้วไม่ใช่กล่องไอเทม
                        if self.cur_rect and self.cur_key != key:
                            self.q.put(('hide', None)); self.cur_rect = None; self.cur_thumb = None; self.cur_key = None
                        continue
                    self.q.put(('show', (self.cache[key], absr, monr)))
                    self.cur_rect = absr; self.cur_thumb = th; self.cur_key = key; self.cur_box = self.box_now
                    continue
                if time.time() - still < 0.12:
                    continue
                settled = self.prev_th is not None and self.same(th, self.prev_th)
                self.prev_th = th
                if not same and not settled:
                    continue                                    # กล่องกำลังค่อยๆ โผล่ (fade-in) รอให้นิ่งก่อนอ่าน
                if not same:
                    if self.ov.visible:
                        self.q.put(('loading', (absr, monr)))  # ขึ้น 'กำลังแปล…' เฉพาะตอนกล่องแปลเปิดอยู่แล้ว
                    self.cur_rect = absr; self.cur_thumb = th; self.cur_key = key; self.cur_box = self.box_now
                if self.busy:
                    continue                                    # กำลังอ่านกล่องก่อนหน้า เสร็จแล้วค่อยอ่านกล่องนี้
                self.busy = True; self.job_key = key
                hdr = tuple(int(v) for v in np.median(crop[2:max(4, hb - 3), 8:-8].reshape(-1, 3), 0)) if hb > 8 else None
                threading.Thread(target=self.ocr_job, args=(key, crop, monr, hdr, hb), daemon=True).start()
            except Exception:
                log('loop', traceback.format_exc())
                time.sleep(1)

    def ocr_job(self, key, crop, monr, hdr=None, hb=0):
        try:
            t = time.time()
            data = None
            shown = 0
            web = None
            last_ocr = None
            interrupted = False
            if hb > 12:
                try:
                    web = self.reader.lookup(self.reader.read_header(crop, hb))
                except Exception:
                    log('lookup', traceback.format_exc())
                if web and self.cur_key == key and self.cur_rect:
                    web['hdr'] = hdr
                    self.q.put(('show', (web, self.cur_rect, monr)))   # โชว์ทันทีจากข้อมูลเว็บ
                    shown = 1
                    log('web', round(time.time() - t, 2), 's', web['items'][0][1])
            for d, done in self.reader.read_iter(crop):
                if d is None:
                    break
                data = d
                d['hdr'] = hdr
                if self.cur_key != key or not self.cur_rect:
                    interrupted = True
                    break                                       # ผู้ใช้ชี้ที่อื่นไปแล้ว
                if web and web.get('cat') != 'mods':
                    secs = [it for it in d['items'] if it[0] == 'term' and not re.search(r'\d', it[1])
                            and it[1] in ('ความสามารถปืน', 'เอฟเฟกต์เซ็ต', 'เอฟเฟกต์ม็อด', 'ผลของอาหาร', 'คำอธิบาย')]
                    if secs or done:                            # อ่านถึงหัวข้อความสามารถแล้ว = ได้ค่าพื้นฐานครบ หยุดอ่าน
                        data = self.reader.with_stats(web, d); data['hdr'] = hdr; data['web'] = True
                        self.q.put(('show', (data, self.cur_rect, monr)))
                        done = True
                        break
                    continue
                if web:
                    last_ocr = d                                # มีข้อมูลเว็บแล้ว: เงียบไว้ อ่านจบค่อยอัปเดตครั้งเดียว (ด้านล่าง)
                elif shown == 0 or done:                        # โชว์ 2 จังหวะ: ส่วนบนก่อน แล้วทั้งหมดตอนจบ (ลดกระพริบ)
                    self.q.put(('show', (d, self.cur_rect, monr)))
                    shown += 1
            log('ocr', round(time.time() - t, 2), 's', len(data['items']) if data else 0, 'rect', self.cur_rect)
            if web and web.get('cat') == 'mods' and last_ocr is not None and (self.cur_key == key and self.cur_rect):
                data = self.reader.merge(web, last_ocr); data['hdr'] = hdr
                self.q.put(('show', (data, self.cur_rect, monr)))
            if interrupted:
                return                                          # อ่านไม่จบ (ชี้ที่อื่นไปแล้ว) ไม่เก็บ cache ไว้ รอบหน้าอ่านใหม่ให้ครบ
            if web and (data is None or not data.get('web')):
                data = web                                      # อ่านเต็มไม่สำเร็จ ใช้ข้อมูลเว็บ
            self.cache[key] = data
            if len(self.cache) > 300:
                self.cache.pop(next(iter(self.cache)))
            if not data:
                self.save_miss(crop)
                if self.cur_key == key:
                    self.q.put(('hide', None)); self.cur_rect = None; self.cur_thumb = None
                return
            if SET['mt'] and self.cur_key == key:
                threading.Thread(target=self.fill_mt, args=(key, data, monr), daemon=True).start()
        except Exception:
            log('ocr_job', traceback.format_exc())
        finally:
            self.job_key = None
            self.busy = False

    def fill_mt(self, key, data, monr):
        changed = False
        items = list(data['items'])
        for i, (k, th, en) in enumerate(items):
            if k == 'raw' and not th and len(en) > 26 and re.search(r'[a-z]{3}', en):
                try:
                    items[i] = ('raw', mt(en), en); changed = True
                except Exception as e:
                    log('mt', e); break
        if changed:
            data['items'] = items
            if self.cur_key == key and self.cur_rect:
                self.q.put(('show', (data, self.cur_rect, monr)))

    def save_miss(self, crop):
        """เก็บภาพกล่องที่อ่านแล้วไม่ได้คำแปล (สูงสุด 40 ไฟล์) ไว้ให้แอดมินดู"""
        try:
            d = os.path.join(DATA, 'miss'); os.makedirs(d, exist_ok=True)
            fs = sorted(os.listdir(d))
            for f in fs[:-78]:
                os.remove(os.path.join(d, f))
            st = time.strftime('%H%M%S') + f'_{int(time.time() * 1000) % 1000:03d}'
            im = Image.fromarray(crop)
            if im.height > 900:
                im = im.resize((im.width * 900 // im.height, 900))
            im.save(os.path.join(d, st + '.jpg'), quality=80)
            json.dump(getattr(self.reader, 'last_lines', []), open(os.path.join(d, st + '.json'), 'w', encoding='utf-8'), ensure_ascii=False)
        except Exception as e:
            log('save_miss', e)

    def save_debug(self, frame, rect):
        try:
            d = os.path.join(DATA, 'debug'); os.makedirs(d, exist_ok=True)
            st = time.strftime('%Y%m%d-%H%M%S')
            Image.fromarray(frame).save(os.path.join(d, f'{st}.png'))
            json.dump({'rect': rect}, open(os.path.join(d, f'{st}.json'), 'w'))
            self.q.put(('toast', 'บันทึกภาพดีบักแล้ว: ' + d))
        except Exception as e:
            log('debug', e)


# ───────────── อัปเดตข้อมูลแปลอัตโนมัติจากเว็บ ─────────────
WEB_BASE = 'https://hub.mrsmitety.com/addons/thai-tooltip/'


def updater_thread(q, wk):
    time.sleep(8)
    while True:
        try:
            r = wk.reader
            cur = (r.web or {}).get('ver') if r else None
            ua = {'User-Agent': f'OHThaiTooltip/{VERSION}'}
            v = json.loads(urllib.request.urlopen(urllib.request.Request(
                WEB_BASE + 'version.json?t=%d' % time.time(), headers=ua), timeout=10).read().decode('utf-8'))
            if r and v.get('ver') and v['ver'] != cur:
                raw = urllib.request.urlopen(urllib.request.Request(
                    WEB_BASE + 'oh_web.json?v=' + v['ver'], headers=ua), timeout=30).read()
                web = json.loads(raw.decode('utf-8'))
                if web.get('ver') == v['ver'] and len(web.get('weapons', {})) > 5:
                    open(os.path.join(DATA, 'oh_web.json'), 'wb').write(raw)
                    r.set_web(web)
                    wk.cache.clear(); wk.thumbs.clear()
                    log('web data updated', v['ver'])
                    q.put(('toast', f'อัปเดตข้อมูลแปลล่าสุดแล้ว ({web.get("updated", v["ver"])})'))
        except Exception as e:
            log('updater', e)
        time.sleep(3 * 3600)


# ───────────── เวอร์ชัน Member: ตรวจยศทุกครั้งที่เปิด + ทุก 6 ชั่วโมง ─────────────
def member_thread(q, wk, mb, want_login):
    import member as M
    first = True
    while True:
        try:
            if want_login.is_set():
                want_login.clear()
                q.put(('toast', 'เปิดเบราว์เซอร์ให้ล็อกอิน Discord แล้ว\nล็อกอินเสร็จจะกลับมาทำงานเอง'))
                if not mb.login():
                    q.put(('toast', 'ยังไม่ได้ล็อกอิน (หมดเวลา) · คลิกขวาไอคอน → ล็อกอิน Member'))
            st = mb.check()
            log('member', st)
            while wk.reader is None:
                time.sleep(0.3)
            if st.get('ok'):
                if mb.pack and (st.get('changed') or first or getattr(wk.reader, 'member', None) is not mb.pack):
                    wk.reader.apply_member(mb.pack)
                    wk.cache.clear(); wk.thumbs.clear()
                if not GATE.is_set():
                    q.put(('toast', '💎 ' + M.reason_text(st) + '\nใช้คำแปลของ MrSmitety แล้ว'))
                GATE.set()
            else:
                GATE.clear(); q.put(('hide', None))
                if st.get('reason') in ('login', 'session') and first:
                    want_login.set(); first = False
                    continue
                q.put(('fatal', 'OH Thai Tooltip Member ใช้งานไม่ได้\n' + M.reason_text(st) + '\nคลิกขวาไอคอนมุมขวาล่าง → ล็อกอิน Member'))
            q.put(('menu', None))
        except Exception:
            log('member', traceback.format_exc())
        first = False
        want_login.wait(6 * 3600)


# ───────────── ปุ่มลัด Ctrl+Alt+T ─────────────
def hotkey_thread(q):
    if not IS_WIN:
        return
    MOD_ALT, MOD_CONTROL, MOD_NOREPEAT = 1, 2, 0x4000
    ok = user32.RegisterHotKey(None, 1, MOD_CONTROL | MOD_ALT | MOD_NOREPEAT, ord('T'))
    log('hotkey', ok)
    msg = wintypes.MSG()
    while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
        if msg.message == 0x0312:
            q.put(('toggle', None))


# ───────────── ไอคอน ─────────────
def make_icon(sz=64):
    p = os.path.join(BASE, 'thai_tooltip.png')
    if os.path.exists(p):
        return Image.open(p).convert('RGBA').resize((sz, sz), Image.LANCZOS)
    im = Image.new('RGBA', (sz, sz), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle((2, 2, sz - 3, sz - 3), radius=sz // 5, fill=(18, 20, 24, 255), outline=(95, 240, 230, 255), width=3)
    d.text((sz * 0.2, sz * 0.25), 'TH', fill=(95, 240, 230, 255))
    return im


# ───────────── main ─────────────
def main():
    try:
        lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock.bind(('127.0.0.1', PORT)); lock.listen(1)
    except OSError:
        r = tk.Tk(); r.withdraw()
        from tkinter import messagebox
        messagebox.showinfo(APP, 'OH Thai Tooltip เปิดอยู่แล้ว (ดูไอคอนที่มุมขวาล่างของ Taskbar)')
        return

    root = tk.Tk()
    root.withdraw()
    ov = Overlay(root)
    q = queue.Queue()
    wk = Worker(q, ov)
    wk.start()
    threading.Thread(target=hotkey_thread, args=(q,), daemon=True).start()
    threading.Thread(target=updater_thread, args=(q, wk), daemon=True).start()
    mb = None; want_login = threading.Event()
    if MEMBER_ED:
        import member as M
        mb = M.Member(DATA, VERSION, log)
        threading.Thread(target=member_thread, args=(q, wk, mb, want_login), daemon=True).start()

    toast_w = tk.Toplevel(root); toast_w.overrideredirect(True); toast_w.attributes('-topmost', True)
    toast_w.configure(bg=BG, highlightthickness=1, highlightbackground=TEAL)
    toast_l = tk.Label(toast_w, bg=BG, fg=FG, font=('Leelawadee UI', -15), padx=16, pady=10, justify='left')
    toast_l.pack(); toast_w.withdraw()
    toast_job = [None]

    def toast(msg, ms=3500):
        toast_l.config(text=msg)
        toast_w.update_idletasks()
        sw = root.winfo_screenwidth()
        toast_w.geometry(f'+{sw - toast_w.winfo_reqwidth() - 24}+24')
        toast_w.deiconify(); toast_w.lift()
        make_clickthrough(toast_w)
        if toast_job[0]:
            root.after_cancel(toast_job[0])
        toast_job[0] = root.after(ms, toast_w.withdraw)

    # ถาด
    tray = None
    try:
        import pystray

        def chk(key):
            return lambda item: bool(SET.get(key))

        def flip(key, msg_on, msg_off):
            def f(icon, item):
                SET[key] = not SET.get(key); save_set()
                q.put(('toast', msg_on if SET[key] else msg_off))
            return f

        def dbg(icon, item):
            wk.debug_next = True
            q.put(('toast', 'จะบันทึกภาพหน้าจอถัดไปไว้ดีบัก (ชี้ที่ไอเทมค้างไว้)'))

        def opendir(icon, item):
            os.startfile(DATA) if IS_WIN else None

        def quit_(icon, item):
            q.put(('quit', None))

        def m_login(icon, item):
            want_login.set()

        def m_logout(icon, item):
            mb.logout(); GATE.clear(); q.put(('hide', None)); q.put(('menu', None))
            q.put(('toast', 'ออกจากระบบ Member แล้ว · ลบคำแปลมือออกจากเครื่องแล้ว'))

        mitems = []
        if MEMBER_ED:
            mitems = [pystray.MenuItem(lambda item: M.reason_text(mb.status), None, enabled=False),
                      pystray.MenuItem('ล็อกอิน Member (Discord)', m_login),
                      pystray.MenuItem('ออกจากระบบ Member', m_logout, enabled=lambda item: mb.has_login()),
                      pystray.Menu.SEPARATOR]
        menu = pystray.Menu(
            pystray.MenuItem(f'{APP} v{VERSION}', None, enabled=False),
            *mitems,
            pystray.MenuItem('เปิดใช้งาน (Ctrl+Alt+T)', flip('enabled', 'เปิดแปลไทยแล้ว', 'ปิดแปลไทยแล้ว'), checked=chk('enabled'), default=True),
            pystray.MenuItem('แปลประโยคที่ไม่มีในคลังด้วย Google (ใช้เน็ต)', flip('mt', 'เปิดแปลสำรองด้วย Google', 'ปิดแปลสำรอง'), checked=chk('mt')),
            pystray.MenuItem('แสดงภาษาอังกฤษใต้คำแปล', flip('show_en', 'แสดงภาษาอังกฤษด้วย', 'ซ่อนภาษาอังกฤษ'), checked=chk('show_en')),
            pystray.MenuItem('ทำงานกับทุกหน้าต่าง (ทดสอบ)', flip('any_window', 'ทำงานกับทุกหน้าต่าง', 'ทำงานเฉพาะในเกม'), checked=chk('any_window')),
            pystray.Menu.SEPARATOR,
            pystray.MenuItem('บันทึกภาพดีบัก (ส่งให้แอดมินถ้าแปลไม่ขึ้น)', dbg),
            pystray.MenuItem('เปิดโฟลเดอร์ข้อมูล', opendir),
            pystray.MenuItem('ออก', quit_),
        )
        tray = pystray.Icon('ohthaitooltip', make_icon(64), APP, menu)
        tray.run_detached()
    except Exception:
        log('tray', traceback.format_exc())

    pumping = [False]

    def pump():
        if pumping[0]:
            return
        pumping[0] = True
        try:
            while True:
                k, v = q.get_nowait()
                if k == 'show':
                    if SET['enabled']:
                        ov.show(*v)
                elif k == 'hide':
                    ov.hide()
                elif k == 'loading':
                    if SET['enabled']:
                        ov.loading(*v)
                elif k == 'toggle':
                    SET['enabled'] = not SET['enabled']; save_set()
                    if not SET['enabled']:
                        ov.hide()
                    toast('เปิดแปลไทยแล้ว' if SET['enabled'] else 'ปิดแปลไทยแล้ว (Ctrl+Alt+T เพื่อเปิด)')
                    if tray:
                        tray.update_menu()
                elif k == 'toast':
                    toast(v)
                elif k == 'menu':
                    if tray:
                        tray.update_menu()
                elif k == 'ready' and GATE.is_set():
                    toast('OH Thai Tooltip พร้อมใช้งาน\nเอาเมาส์ชี้ที่ปืน เกราะ ม็อด หรืออาหารในเกม\nเปิด/ปิด: Ctrl+Alt+T', 5000)
                elif k == 'fatal':
                    toast(v, 15000)
                elif k == 'quit':
                    try:
                        json.dump(MT_CACHE, open(MT_PATH, 'w', encoding='utf-8'), ensure_ascii=False)
                    except Exception:
                        pass
                    if tray:
                        tray.stop()
                    root.destroy(); os._exit(0)
        except queue.Empty:
            pass
        finally:
            pumping[0] = False
        root.after(40, pump)

    root.after(40, pump)
    if not MEMBER_ED:                      # แจ้งว่ามี OH Companion แล้ว (เลือกย้ายหรือไม่ก็ได้)
        try:
            import oc_notice
            oc_notice.check(root, 'OH Thai Tooltip', DATA, lambda: q.put(('quit', None)), log)
        except Exception:
            log('notice', traceback.format_exc())
    root.mainloop()


if __name__ == '__main__':
    try:
        main()
    except Exception:
        log('fatal', traceback.format_exc())
        try:
            from tkinter import messagebox
            messagebox.showerror(APP, 'โปรแกรมหยุดทำงาน\nดูรายละเอียดที่\n' + LOG)
        except Exception:
            pass
