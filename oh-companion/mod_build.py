# -*- coding: utf-8 -*-
"""OH Build Overlay — เลือกบิ้วจาก MrSmitety Hub แล้วโชว์เป็นแถบโปร่งในหน้าใส่ของของ Once Human
ชิ้นไหนใส่ตรงบิ้วแล้วจะสว่างขึ้น · ทำงานจากภาพหน้าจออย่างเดียว: ไม่อ่านหน่วยความจำเกม ไม่แก้ไฟล์เกม ไม่ส่งปุ่มเข้าเกม
by MrSmitety Hub"""
VERSION = '0.2.1'
APP = 'OH Build Overlay'
PORT = 47617
GAME_EXE = 'once_human.exe'
HUB = 'https://hub.mrsmitety.com'
SB_URL = 'https://ejletwoddaqdnjjqjwun.supabase.co'
SB_KEY = 'sb_publishable_uLX_CLa1meE1FxNGOaYm7g_RnvZ83u6'      # คีย์สาธารณะ (anon) ของเว็บ hub

import os, sys, json, time, re, threading, queue, socket, traceback, io, urllib.request, urllib.parse, webbrowser

IS_WIN = sys.platform == 'win32'
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')
BASE = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'OHBuildOverlay')
ICDIR = os.path.join(DATA, 'icons')
os.makedirs(ICDIR, exist_ok=True)
LOG = os.path.join(DATA, 'OH Build Overlay.log')


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
from PIL import Image, ImageTk, ImageDraw

sys.path.insert(0, BASE)
import bo_read as R, bo_match as BM, detect   # noqa: E402

D = json.load(open(os.path.join(BASE, 'bo_data.json'), encoding='utf-8'))

# ───────────── ตั้งค่า ─────────────
SET_PATH = os.path.join(DATA, 'settings.json')
DEFAULT = {'enabled': True, 'any_window': False, 'build': None, 'status': {}, 'pos': None, 'always': False, 'craft': False}


def load_set():
    s = dict(DEFAULT)
    try:
        s.update(json.load(open(SET_PATH, encoding='utf-8')))
    except Exception:
        pass
    return s


SET = load_set()
_save_lock = threading.Lock()


def save_set():
    with _save_lock:
        try:
            json.dump(SET, open(SET_PATH, 'w', encoding='utf-8'), ensure_ascii=False)
        except Exception:
            pass


# ───────────── Windows helpers ─────────────
def game_rect():
    """กรอบพื้นที่ภาพของหน้าต่างเกม (ถ้าเกมอยู่หน้าสุด) → (x, y, w, h) หรือ None"""
    if not IS_WIN:
        return (0, 0, 2560, 1440)
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return None
    if not SET.get('any_window'):
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        h = kernel32.OpenProcess(0x1000, False, pid.value)
        if not h:
            return None
        try:
            buf = ctypes.create_unicode_buffer(520); n = wintypes.DWORD(520)
            if not kernel32.QueryFullProcessImageNameW(h, 0, buf, ctypes.byref(n)):
                return None
            if os.path.basename(buf.value).lower() != GAME_EXE:
                return None
        finally:
            kernel32.CloseHandle(h)
    rc = wintypes.RECT()
    if not user32.GetClientRect(hwnd, ctypes.byref(rc)):
        return None
    pt = wintypes.POINT(0, 0)
    user32.ClientToScreen(hwnd, ctypes.byref(pt))
    w, h = rc.right - rc.left, rc.bottom - rc.top
    if w < 800 or h < 450:
        return None
    return (pt.x, pt.y, w, h)


def our_window_fg(roots):
    if not IS_WIN:
        return False
    fg = user32.GetForegroundWindow()
    for r in roots:
        try:
            if fg in (r.winfo_id(), user32.GetParent(r.winfo_id())):
                return True
        except Exception:
            pass
    return False


def style_ex(win, clickthrough=False):
    if not IS_WIN:
        return
    try:
        hwnd = user32.GetParent(win.winfo_id()) or win.winfo_id()
        st = user32.GetWindowLongW(hwnd, -20)
        st |= 0x00000080 | 0x08000000            # TOOLWINDOW | NOACTIVATE (ไม่แย่งโฟกัสจากเกม)
        if clickthrough:
            st |= 0x00080000 | 0x00000020         # LAYERED | TRANSPARENT
        user32.SetWindowLongW(hwnd, -20, st)
    except Exception as e:
        log('style', e)


# ───────────── เว็บ hub ─────────────
def sb_get(path, timeout=12):
    req = urllib.request.Request(SB_URL + '/rest/v1/' + path, headers={'apikey': SB_KEY, 'Authorization': 'Bearer ' + SB_KEY,
                                                                       'User-Agent': f'OHBuildOverlay/{VERSION}'})
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode('utf-8'))


def list_builds():
    return sb_get('creations_gallery?kind=eq.build&select=id,title,display_name,is_creator,updated_at,summary,like_count,view_count'
                  '&order=updated_at.desc&limit=500')


def get_build(bid):
    r = sb_get('creations_gallery?id=eq.' + urllib.parse.quote(bid) + '&select=id,title,display_name,is_creator,updated_at,data')
    return r[0] if r else None


_ic_lock = threading.Lock()


def icon_img(key, size):
    """ไอคอนจากเว็บ hub (เก็บไว้ในเครื่อง) → PIL Image หรือ None"""
    if not key:
        return None
    if key.startswith('hide:'):
        p = os.path.join(BASE, 'hideic', key[5:] + '.png')
    else:
        p = os.path.join(ICDIR, key.replace('/', '__') + '.png')
        if not os.path.exists(p):
            try:
                data = urllib.request.urlopen(urllib.request.Request(HUB + '/oh/icons/' + key + '.webp', headers={'User-Agent': 'Mozilla/5.0'}), timeout=10).read()
                im = Image.open(io.BytesIO(data)).convert('RGBA')
                with _ic_lock:
                    im.save(p)
            except Exception as e:
                log('icon', key, e)
                return None
    try:
        im = Image.open(p).convert('RGBA')
        im.thumbnail((size, size), Image.LANCZOS)
        return im
    except Exception:
        return None


# ───────────── สี / ฟอนต์ ─────────────
BG = '#0d1318'; BG2 = '#151d25'; LINE = '#2a3644'; FG = '#e9eef2'; DIM = '#7d8894'
TEAL = '#00dcd2'; OK = '#3ddc84'; BAD = '#ff7a45'; GOLD = '#e7b84a'; HINT = '#ffd54a'
FONT = 'Leelawadee UI'
BASE_W = 2200                      # ความกว้างแถบสูงสุดที่จอสูง 1440 (ทุกช่องยังไม่ครบ = ขยายหมด)
COL = {'ok': OK, 'bad': BAD, 'warn': BAD, 'hint': HINT, 'info': '#b8c2cc'}


# ───────────── แถบ Overlay ─────────────
class Strip:
    def __init__(self, root, q):
        self.root = root; self.q = q
        self.w = tk.Toplevel(root); self.w.overrideredirect(True); self.w.attributes('-topmost', True)
        self.w.attributes('-alpha', 0.94); self.w.configure(bg=BG)
        self.c = tk.Canvas(self.w, bg=BG, highlightthickness=1, highlightbackground='#24414a', bd=0)
        self.c.pack(fill='both', expand=True)
        self.w.withdraw(); self.shown = False
        self.build = None; self.status = {}; self.hint = ('', 'info'); self.page = None
        self.sc = 1.0; self.imgs = {}; self.ph = []; self.drag = None; self.geo = None
        self.c.bind('<ButtonPress-1>', self._press); self.c.bind('<B1-Motion>', self._move); self.c.bind('<ButtonRelease-1>', self._release)
        self.c.bind('<ButtonRelease-3>', self._rclick)
        self.root.after(200, lambda: style_ex(self.w))

    # ── ลากย้าย / คลิก ──
    def _press(self, e):
        self.drag = (e.x_root, e.y_root, self.w.winfo_x(), self.w.winfo_y(), False)

    def _move(self, e):
        if not self.drag:
            return
        x0, y0, wx, wy, _ = self.drag
        if abs(e.x_root - x0) + abs(e.y_root - y0) > 6:
            self.drag = (x0, y0, wx, wy, True)
            self.w.geometry(f'+{wx + e.x_root - x0}+{wy + e.y_root - y0}')

    def _release(self, e):
        if not self.drag:
            return
        moved = self.drag[4]; self.drag = None
        if moved and self.geo:
            gx, gy, gw, gh = self.geo
            SET['pos2'] = [(self.w.winfo_x() + self.w.winfo_width() - gx) / gw, (self.w.winfo_y() - gy) / gh]; save_set()
            return
        tags = self.c.gettags('current')
        for t in tags:
            if t.startswith('k:') and t.endswith('m') and self.build and t[2:] in self.build.items:
                nm = self.build.items[t[2:]]['name']             # คลิกชื่อ MOD = คัดลอกชื่อไปวางในช่อง Search ของเกม
                try:
                    self.root.clipboard_clear(); self.root.clipboard_append(nm); self.root.update()
                    self.q.put(('toast', f'คัดลอก "{nm}" แล้ว · ไปที่ช่อง Search ในเกมแล้วกด Ctrl+V'))
                except Exception:
                    pass
                return
            if t.startswith('k:'):
                k = t[2:]
                cur = self.status.get(k, (None,))[0]
                if cur == 'ok':
                    self.status.pop(k, None)
                else:
                    self.status[k] = ('ok', 'ติ๊กเอง')
                self.q.put(('status_changed', None)); self.draw(); return
            if t == 'btn:pick':
                self.q.put(('pick', None)); return
            if t == 'btn:reset':
                self.q.put(('reset', None)); self.draw(); return
            if t == 'btn:hide':
                self.q.put(('toggle', None)); return
            if t == 'btn:web' and self.build:
                webbrowser.open(HUB + '/oh/build.html?id=' + urllib.parse.quote(self.build.id)); return

    def _rclick(self, e):
        """คลิกขวา = ติ๊ก/ยกเลิกติ๊กเองทุกช่อง (รวม MOD)"""
        for t in self.c.gettags('current'):
            if t.startswith('k:'):
                k = t[2:]
                if self.status.get(k, (None,))[0] == 'ok':
                    self.status.pop(k, None)
                else:
                    self.status[k] = ('ok', 'ติ๊กเอง')
                self.q.put(('status_changed', None)); self.draw(); return

    # ── รูป ──
    def _img(self, key, size):
        k = (key, size)
        if k not in self.imgs:
            self.imgs[k] = None
            def job():
                im = icon_img(key, size)
                self.q.put(('img', (k, im)))
            threading.Thread(target=job, daemon=True).start()
        return self.imgs.get(k)

    def set_img(self, k, im):
        self.imgs[k] = ImageTk.PhotoImage(im) if im is not None else False
        if self.shown:
            self.draw()

    def place(self, geo):
        self.geo = geo
        gx, gy, gw, gh = geo
        self.sc = max(0.5, min(1.6, gh / 1440, gw * 0.97 / BASE_W))
        if SET.get('pos2'):
            rx, ry = SET['pos2']; self.right, self.top = gx + int(rx * gw), gy + int(ry * gh)
        else:
            self.right, self.top = gx + int(gw * 0.985), gy + int(gh * 0.062)
        self.resize(self.layout()[1])

    def resize(self, Wd):
        """ความกว้างเปลี่ยนตามช่องที่ย่อ/ขยาย · ยึดขอบขวาไว้ที่เดิม"""
        if not self.geo:
            return
        gx, gy, gw, gh = self.geo
        W, H = int(Wd * self.sc), int(150 * self.sc)
        x = max(gx, min(self.right - W, gx + gw - W)); y = max(gy, min(self.top, gy + gh - H))
        g = f'{W}x{H}+{x}+{y}'
        if g != getattr(self, '_g', None):
            self._g = g; self.w.geometry(g)

    def show(self, geo):
        if self.geo != geo or not self.shown:
            self.place(geo)
        if not self.shown:
            self.w.deiconify(); self.shown = True; self.w.lift(); self.draw()
        self.w.attributes('-topmost', True)

    def hide(self):
        if self.shown:
            self.w.withdraw(); self.shown = False

    # ── วาด ──
    def done(self, k):
        """ช่องนี้ใส่ครบแล้ว (ตัวมันเอง + Calibration/หนัง + MOD) → ย่อเก็บ"""
        b = self.build
        if not b or k not in b.items:
            return False
        subs = [k] + [k + x for x in ('c', 'h', 'm') if k + x in b.items]
        return all(self.status.get(x, (None,))[0] == 'ok' for x in subs)

    def layout(self):
        """[(ชนิด, key, กว้าง)] และความกว้างรวม (หน่วยจอ 1440)"""
        L = []
        if self.build:
            for i in (0, 1):
                k = f'w{i}'
                L.append(('w', k, 176 if self.done(k) else 300))
            for k in BM.ARMOR_KEYS:
                L.append(('a', k, 82 if self.done(k) else 214))
        tot = 270 + sum(w + 8 for _, _, w in L) + 6
        return L, max(tot, 760)

    def draw(self):
        c = self.c; c.delete('all'); s = self.sc
        F = lambda px, w='normal': (FONT, -max(9, int(px * s)), w)
        L, Wd = self.layout(); self.resize(Wd)
        W = int(Wd * s)
        b = self.build
        # ซ้าย: ชื่อบิ้ว + ความคืบหน้า
        c.create_text(14 * s, 12 * s, text='BUILD OVERLAY', fill=TEAL, font=F(11, 'bold'), anchor='nw')
        if not b:
            c.create_text(14 * s, 34 * s, text='ยังไม่ได้เลือกบิ้ว', fill=FG, font=F(16, 'bold'), anchor='nw')
            self._btn(14 * s, 74 * s, 'เลือกบิ้วจากเว็บ', 'btn:pick', F(13, 'bold'), True)
            return
        title = b.title if len(b.title) <= 34 else b.title[:33] + '…'
        c.create_text(14 * s, 30 * s, text=title, fill=FG, font=F(15, 'bold'), anchor='nw', width=250 * s)
        c.create_text(14 * s, 74 * s, text=('โดย ' + b.by) if b.by else '', fill=DIM, font=F(11), anchor='nw')
        done, tot = b.progress(self.status)
        c.create_text(14 * s, 94 * s, text=f'ใส่ตรงบิ้วแล้ว {done}/{tot}', fill=OK if done == tot and tot else FG, font=F(12, 'bold'), anchor='nw')
        bw = 236 * s
        c.create_rectangle(14 * s, 114 * s, 14 * s + bw, 119 * s, fill='#24303b', outline='')
        if tot:
            c.create_rectangle(14 * s, 114 * s, 14 * s + bw * done / tot, 119 * s, fill=OK if done == tot else TEAL, outline='')
        x = 14 * s
        for lab, tag in (('เปลี่ยนบิ้ว', 'btn:pick'), ('ดูบนเว็บ', 'btn:web'), ('ล้างสถานะ', 'btn:reset'), ('ซ่อน', 'btn:hide')):
            x = self._btn(x, 126 * s, lab, tag, F(10)) + 6 * s
        x0 = 270 * s
        for kind, k, w in L:
            if kind == 'w':
                self._weapon_card(x0, 8 * s, w * s, 112 * s, int(k[1]), F, self.done(k))
            else:
                self._armor_card(x0, 8 * s, w * s, 112 * s, k, F, self.done(k))
            x0 += (w + 8) * s
        t, col = self.hint
        c.create_text(270 * s, 128 * s, text=t or 'เปิดหน้าใส่ปืน / เกราะ / MOD ในเกม แล้วเลือกของ โปรแกรมจะเช็คให้ว่าตรงบิ้วไหม · ช่องที่ครบแล้วจะย่อเก็บ · คลิกชื่อ MOD = คัดลอกไปค้นหาในเกม · คลิกขวา = ติ๊กเอง',
                      fill=COL.get(col, FG) if t else DIM, font=F(12, 'bold' if t else 'normal'), anchor='nw', width=W - 280 * s)

    def _btn(self, x, y, text, tag, font, primary=False):
        c = self.c
        tid = c.create_text(x + 8 * self.sc, y + 2 * self.sc, text=text, fill='#052322' if primary else '#cfd8e0', font=font, anchor='nw', tags=(tag,))
        bb = c.bbox(tid)
        r = c.create_rectangle(bb[0] - 7 * self.sc, bb[1] - 3 * self.sc, bb[2] + 7 * self.sc, bb[3] + 3 * self.sc,
                               fill=TEAL if primary else '#1c2530', outline=TEAL if primary else '#2e3a48', tags=(tag,))
        c.tag_raise(tid)
        return bb[2] + 7 * self.sc

    def _st(self, k):
        return self.status.get(k, (None, ''))

    def _frame(self, x, y, w, h, st, tag):
        col = {'ok': OK, 'bad': BAD, 'need': HINT}.get(st, LINE)
        self.c.create_rectangle(x, y, x + w, y + h, fill='#13202a' if st == 'ok' else BG2, outline=col, width=max(1, int((3 if st else 1) * self.sc)), tags=(tag,))

    def _dot(self, x, y, k, text, F):
        st, note = self._st(k)
        if st == 'ok' and (note or '').startswith('สำรอง: ') and text.startswith('MOD: '):
            text = 'MOD: ' + note[7:]
        col = {'ok': OK, 'bad': BAD}.get(st, '#4a5663')
        r = 4 * self.sc
        self.c.create_oval(x, y + 3 * self.sc, x + 2 * r, y + 3 * self.sc + 2 * r, fill=col, outline='', tags=('k:' + k,))
        self.c.create_text(x + 2 * r + 5 * self.sc, y, text=text, fill=FG if st == 'ok' else ('#ffb08a' if st == 'bad' else '#9aa6b2'),
                           font=F(11), anchor='nw', tags=('k:' + k,))

    def _weapon_card(self, x, y, w, h, i, F, small=False):
        b = self.build; k = f'w{i}'; it = b.items.get(k); s = self.sc
        st = self._st(k)[0]
        self._frame(x, y, w, h, 'ok' if small else st, 'k:' + k)
        self.c.create_text(x + 8 * s, y + 4 * s, text=f'ปืน {i + 1}', fill=TEAL, font=F(10, 'bold'), anchor='nw', tags=('k:' + k,))
        if not it:
            self.c.create_text(x + w / 2, y + h / 2, text='ไม่ได้ระบุ', fill=DIM, font=F(12))
            return
        if st == 'ok' or small:
            self.c.create_text(x + w - 8 * s, y + 2 * s, text='✓', fill=OK, font=F(16, 'bold'), anchor='ne', tags=('k:' + k,))
        if small:                                   # ครบแล้ว: ย่อเหลือรูป + ชื่อ
            im = self._img(it.get('icon'), int(96 * s))
            if im:
                self.c.create_image(x + w / 2, y + 44 * s, image=im, tags=('k:' + k,))
            self.c.create_text(x + w / 2, y + 74 * s, text=it['name'], fill=OK, font=F(11, 'bold'), anchor='n', width=w - 12 * s, justify='center', tags=('k:' + k,))
            return
        im = self._img(it.get('icon'), int(110 * s))
        if im:
            self.c.create_image(x + 62 * s, y + 34 * s, image=im, tags=('k:' + k,))
        self.c.create_text(x + 124 * s, y + 18 * s, text=it['name'], fill=FG, font=F(12, 'bold'), anchor='nw', width=w - 132 * s, tags=('k:' + k,))
        yy = y + 62 * s
        if k + 'c' in b.items:
            cc = b.items[k + 'c']
            ps = '+' + ' > '.join(D['calib']['statName'][p][0] for p in cc['ps']) if cc['ps'] else ''
            self._dot(x + 8 * s, yy, k + 'c', ('Calib: ' + ' / '.join(x_.replace(' Style', '') for x_ in cc['styles']) + ('  ' + ps if ps else ''))[:46], F)
            yy += 22 * s
        if k + 'm' in b.items:
            m = b.items[k + 'm']
            self._dot(x + 8 * s, yy, k + 'm', ('MOD: ' + m['name'] + (f" <{m['suf']}>" if m.get('suf') else ''))[:46], F)

    def _armor_disp(self, k, it):
        """ชื่อ + รูปที่จะโชว์ในช่องเกราะ: ใส่ตัวสำรองอยู่ = โชว์ตัวสำรอง · ต้องเปลี่ยนเป็นชิ้นเซ็ต = โชว์ชิ้นที่ต้องใส่"""
        st, note = self._st(k)
        note = note or ''
        A = D.get('armic') or {}
        if note.startswith('สำรอง: '):
            nm = note[7:]
            return nm, (A.get(nm) or [it.get('icon')])[0], HINT, 'แทน ' + it['name']
        if st == 'need':
            nm = note.replace('ใส่ ', '', 1).replace(' แทน', '')
            return nm, (A.get(nm) or [it.get('icon')])[0], HINT, 'ต้องใส่แทน ' + it['name']
        return it['name'], it.get('icon'), FG, ''

    def _armor_card(self, x, y, w, h, k, F, small=False):
        b = self.build; it = b.items.get(k); s = self.sc
        st = self._st(k)[0]
        self._frame(x, y, w, h, 'ok' if small else st, 'k:' + k)
        self.c.create_text(x + 6 * s, y + 3 * s, text=BM.ARMOR_TH[k], fill=TEAL, font=F(9, 'bold'), anchor='nw', tags=('k:' + k,))
        if not it:
            self.c.create_text(x + w / 2, y + h / 2, text='—', fill=DIM, font=F(14))
            return
        if st == 'ok' or small:
            self.c.create_text(x + w - 5 * s, y + 2 * s, text='✓', fill=OK, font=F(14, 'bold'), anchor='ne', tags=('k:' + k,))
        note = self._st(k)[1] or ''
        dnm, dic, dcol, dsub = self._armor_disp(k, it)
        if small:                                   # ครบแล้ว: ย่อเหลือรูป + ชื่อเซ็ต
            im = self._img(dic, int(52 * s))
            if im:
                self.c.create_image(x + w / 2, y + 48 * s, image=im, tags=('k:' + k,))
            lab = dnm if dsub else (it.get('set') or it['name'])
            self.c.create_text(x + w / 2, y + 82 * s, text=lab[:11], fill=OK, font=F(9, 'bold'), anchor='n', tags=('k:' + k,))
            return
        # ยังไม่ครบ: ขยายบอกชื่อชิ้น หนัง และ MOD ที่ต้องใส่
        im = self._img(dic, int(58 * s))
        if im:
            self.c.create_image(x + 38 * s, y + 50 * s, image=im, tags=('k:' + k,))
        self.c.create_text(x + 76 * s, y + 14 * s, text=dnm, fill=dcol, font=F(11, 'bold'), anchor='nw', width=w - 84 * s, tags=('k:' + k,))
        if dsub:
            self.c.create_text(x + 76 * s, y + 40 * s, text=dsub[:28], fill=DIM, font=F(9), anchor='nw', tags=('k:' + k,))
        if k + 'h' in b.items:
            hi = b.items[k + 'h']; hst = self._st(k + 'h')[0]
            him = self._img('hide:' + hi['icon'], int(26 * s))
            cx, cy = x + 18 * s, y + 80 * s
            self.c.create_oval(cx - 14 * s, cy - 14 * s, cx + 14 * s, cy + 14 * s, fill='#0b1116', outline={'ok': OK, 'bad': BAD}.get(hst, '#6b5a3e'),
                               width=max(1, int(2 * s)), tags=('k:' + k + 'h',))
            if him:
                self.c.create_image(cx, cy, image=him, tags=('k:' + k + 'h',))
        yy = y + 58 * s
        if k + 'h' in b.items:
            self._dot(x + 76 * s, yy, k + 'h', ('หนัง: ' + b.items[k + 'h']['name'])[:23], F); yy += 22 * s
        if k + 'm' in b.items:
            m = b.items[k + 'm']
            self._dot(x + 76 * s, yy, k + 'm', ('MOD: ' + m['name'])[:23], F)
            if m.get('suf'):
                mst, mnote = self._st(k + 'm')
                ok_suf = mst == 'ok'
                bad_suf = mst == 'bad' and 'Suffix' in (mnote or '')
                self.c.create_text(x + 90 * s, yy + 18 * s, text=(f"<{m['suf']}>" + (' ✓' if ok_suf else (' ✗' if bad_suf else '')))[:24],
                                   fill=OK if ok_suf else (BAD if bad_suf else DIM), font=F(10, 'bold' if (ok_suf or bad_suf) else 'normal'), anchor='nw', tags=('k:' + k + 'm',))


# ───────────── กรอบไฮไลต์หัวแถว MOD ─────────────
class Marks:
    KEY = '#010203'

    def __init__(self, root):
        self.w = tk.Toplevel(root); self.w.overrideredirect(True); self.w.attributes('-topmost', True)
        self.w.configure(bg=self.KEY)
        try:
            self.w.attributes('-transparentcolor', self.KEY)
        except Exception:
            pass
        self.c = tk.Canvas(self.w, bg=self.KEY, highlightthickness=0); self.c.pack(fill='both', expand=True)
        self.w.withdraw(); self.on = False; self.last = None
        root.after(250, lambda: style_ex(self.w, True))

    def show(self, geo, rects, sc):
        key = (geo, tuple(rects))
        if key == self.last and self.on:
            return
        self.last = key
        if not rects:
            return self.hide()
        gx, gy, gw, gh = geo
        self.w.geometry(f'{gw}x{gh}+{gx}+{gy}'); self.c.delete('all')
        for (x0, y0, x1, y1, lab) in rects:
            p = 10 * sc
            self.c.create_rectangle(x0 - p, y0 - p, x1 + p, y1 + p, outline=TEAL, width=max(2, int(4 * sc)))
            self.c.create_text(x0 - p, y0 - p - 4 * sc, text='★ ' + lab, fill=HINT, font=(FONT, -max(10, int(15 * sc)), 'bold'), anchor='sw')
        if not self.on:
            self.w.deiconify(); self.on = True
        self.w.attributes('-topmost', True)

    def hide(self):
        if self.on:
            self.w.withdraw(); self.on = False; self.last = None


# ───────────── หน้าต่างเลือกบิ้ว ─────────────
class Picker:
    def __init__(self, root, q):
        self.root = root; self.q = q; self.w = None; self.rows = []

    def open(self):
        if self.w and self.w.winfo_exists():
            self.w.deiconify(); self.w.lift(); self.w.focus_force(); return
        w = self.w = tk.Toplevel(self.root)
        w.title('เลือกบิ้ว — OH Build Overlay'); w.configure(bg=BG); w.geometry('720x620'); w.attributes('-topmost', True)
        try:
            w.iconbitmap(os.path.join(BASE, 'build_overlay.ico'))
        except Exception:
            pass
        top = tk.Frame(w, bg=BG); top.pack(fill='x', padx=14, pady=(14, 6))
        tk.Label(top, text='เลือกบิ้วจาก MrSmitety Hub', bg=BG, fg=TEAL, font=(FONT, 15, 'bold')).pack(anchor='w')
        tk.Label(top, text='ค้นหาชื่อบิ้ว / ปืน / คนทำ หรือวางลิงก์บิ้วจากเว็บ (…/oh/build.html?id=…)', bg=BG, fg=DIM, font=(FONT, 10)).pack(anchor='w')
        self.e = tk.Entry(top, bg='#0e141b', fg=FG, insertbackground=FG, relief='flat', font=(FONT, 12))
        self.e.pack(fill='x', pady=(8, 0), ipady=6); self.e.bind('<KeyRelease>', lambda e: self.fill()); self.e.bind('<Return>', lambda e: self.choose())
        self.only = tk.BooleanVar(value=False)
        tk.Checkbutton(top, text='เฉพาะบิ้วของ MrSmitety', variable=self.only, command=self.fill, bg=BG, fg=FG, selectcolor=BG2,
                       activebackground=BG, activeforeground=FG, font=(FONT, 10)).pack(anchor='w', pady=(6, 0))
        mid = tk.Frame(w, bg=BG); mid.pack(fill='both', expand=True, padx=14)
        sb = tk.Scrollbar(mid); sb.pack(side='right', fill='y')
        self.lb = tk.Listbox(mid, bg=BG2, fg=FG, selectbackground='#0f3433', selectforeground='#fff', relief='flat', font=(FONT, 11),
                             activestyle='none', yscrollcommand=sb.set, highlightthickness=0)
        self.lb.pack(fill='both', expand=True); sb.config(command=self.lb.yview)
        self.lb.bind('<Double-Button-1>', lambda e: self.choose())
        bot = tk.Frame(w, bg=BG); bot.pack(fill='x', padx=14, pady=12)
        self.msg = tk.Label(bot, text='กำลังโหลดรายการบิ้ว…', bg=BG, fg=DIM, font=(FONT, 10)); self.msg.pack(side='left')
        tk.Button(bot, text='ใช้บิ้วนี้', command=self.choose, bg=TEAL, fg='#052322', relief='flat', font=(FONT, 11, 'bold'), padx=16).pack(side='right')
        tk.Button(bot, text='โหลดใหม่', command=self.load, bg='#1c2530', fg=FG, relief='flat', font=(FONT, 10), padx=10).pack(side='right', padx=8)
        self.e.focus_set(); self.load()

    def load(self):
        def job():
            try:
                rows = list_builds()
                self.q.put(('builds', rows))
            except Exception as e:
                log('list', e); self.q.put(('builds_err', str(e)))
        threading.Thread(target=job, daemon=True).start()

    def set_rows(self, rows):
        self.rows = sorted(rows, key=lambda r: (not r.get('is_creator'), ''))
        if self.w and self.w.winfo_exists():
            self.msg.config(text=f'บิ้วสาธารณะ {len(rows)} บิ้ว · ดับเบิลคลิกเพื่อเลือก'); self.fill()

    def fill(self):
        if not (self.w and self.w.winfo_exists()):
            return
        q = self.e.get().strip().lower()
        if 'id=' in q:
            return
        self.view = []
        for r in self.rows:
            if self.only.get() and not r.get('is_creator'):
                continue
            sm = r.get('summary') or {}
            hay = ' '.join([r.get('title') or '', r.get('display_name') or '', ' '.join(sm.get('w') or []), ' '.join(sm.get('a') or [])]).lower()
            if q and not all(x in hay for x in q.split()):
                continue
            self.view.append(r)
        self.lb.delete(0, 'end')
        for r in self.view:
            sm = r.get('summary') or {}
            star = '★ ' if r.get('is_creator') else ''
            self.lb.insert('end', f"{star}{r.get('title') or '(ไม่มีชื่อ)'}   ·   {r.get('display_name') or 'FC'}   ·   {' + '.join(sm.get('w') or [])}")

    def choose(self):
        q = self.e.get().strip()
        m = re.search(r'id=([0-9a-fA-F-]{8,})', q)
        bid = m.group(1) if m else None
        if not bid:
            sel = self.lb.curselection()
            if not sel and len(getattr(self, 'view', [])) == 1:
                sel = (0,)
            if not sel:
                return
            bid = self.view[sel[0]]['id']
        self.msg.config(text='กำลังโหลดบิ้ว…')

        def job():
            try:
                r = get_build(bid)
                self.q.put(('build', r) if r else ('builds_err', 'ไม่พบบิ้วนี้ (อาจเป็นส่วนตัวหรือถูกลบ)'))
            except Exception as e:
                log('get', e); self.q.put(('builds_err', str(e)))
        threading.Thread(target=job, daemon=True).start()

    def close(self):
        if self.w and self.w.winfo_exists():
            self.w.destroy()

    def err(self, t):
        if self.w and self.w.winfo_exists():
            self.msg.config(text='โหลดไม่สำเร็จ: ' + t[:80])


class LazyFrame:
    """ภาพหน้าต่างเกมแบบแคปเฉพาะส่วนที่ขอ (แทนการแคปทั้งจอทุกรอบ ประหยัด CPU มาก)
    ใช้ได้เหมือน numpy array: frame.shape และ frame[y0:y1, x0:x1]"""
    def __init__(self, sct, geo):
        self.sct = sct; self.gx, self.gy, self.W, self.H = geo
        self.shape = (self.H, self.W, 3); self.cache = {}; self.full = None

    def _grab(self, x0, y0, x1, y1):
        x0, y0 = max(0, x0), max(0, y0); x1, y1 = min(self.W, x1), min(self.H, y1)
        if x1 <= x0 or y1 <= y0:
            return np.zeros((0, 0, 3), np.uint8)
        k = (x0, y0, x1, y1)
        if k not in self.cache:
            if self.full is not None:
                self.cache[k] = self.full[y0:y1, x0:x1]
            else:
                self.cache[k] = np.asarray(self.sct.grab({'left': self.gx + x0, 'top': self.gy + y0, 'width': x1 - x0, 'height': y1 - y0}))[:, :, 2::-1]
        return self.cache[k]

    def whole(self):
        if self.full is None:
            self.full = np.asarray(self.sct.grab({'left': self.gx, 'top': self.gy, 'width': self.W, 'height': self.H}))[:, :, 2::-1]
        return self.full

    def __getitem__(self, idx):
        if not isinstance(idx, tuple):
            idx = (idx,)
        ys = idx[0] if len(idx) > 0 else slice(None)
        xs = idx[1] if len(idx) > 1 else slice(None)
        rest = idx[2:]
        if not isinstance(ys, slice) or not isinstance(xs, slice):
            return self.whole()[idx]
        y0, y1, ysp = ys.indices(self.H); x0, x1, xsp = xs.indices(self.W)
        a = self._grab(x0, y0, x1, y1)
        if ysp != 1 or xsp != 1:
            a = a[::ysp, ::xsp]
        return a[(slice(None), slice(None)) + rest] if rest else a


# ───────────── ตัวอ่านหน้าจอ ─────────────
class Worker(threading.Thread):
    def __init__(self, q):
        super().__init__(daemon=True)
        self.q = q; self.running = True; self.build = None; self.status = {}
        self.sig = {}; self.cache = {}; self.ui_fg = False; self.flush = False

    def ocr_init(self):
        try:
            from rapidocr import RapidOCR
            self.v3 = True
            try:      # จำกัดให้ใช้ 2 เธรด กันกิน CPU จนเกมกระตุก
                self.ocr = RapidOCR(params={"Det.limit_type": "max", "Det.limit_side_len": 960,
                                            "EngineConfig.onnxruntime.intra_op_num_threads": 2,
                                            "EngineConfig.onnxruntime.inter_op_num_threads": 1})
            except Exception:
                self.ocr = RapidOCR(params={"Det.limit_type": "max", "Det.limit_side_len": 960})
        except ImportError:
            from rapidocr_onnxruntime import RapidOCR
            self.ocr = RapidOCR(); self.v3 = False

    def O(self, img, off=(0, 0)):
        img = np.ascontiguousarray(img[:, :, ::-1])
        if self.v3:
            r = self.ocr(img, use_cls=False)
            if r.boxes is None:
                return []
            res = [([[p[0] + off[0], p[1] + off[1]] for p in r.boxes[i].tolist()], r.txts[i], r.scores[i]) for i in range(len(r.txts))]
        else:
            rr, _ = self.ocr(img, use_cls=False)
            res = [([[p[0] + off[0], p[1] + off[1]] for p in b], t, s) for b, t, s in (rr or [])]
        return R.lines_of(res)

    def region(self, frame, key, thr=6.0):
        """OCR บริเวณนั้นเฉพาะตอนภาพเปลี่ยน"""
        img, off = R.crop(frame, key)
        sg = R.sig(img)
        if not R.changed(sg, self.sig.get(key), thr) and key in self.cache:
            return self.cache[key], False
        self.sig[key] = sg
        self.cache[key] = self.O(img, off)
        return self.cache[key], True

    def run(self):
        try:
            self.ocr_init()
        except Exception:
            log('ocr', traceback.format_exc()); self.q.put(('toast', 'โหลดตัวอ่านตัวอักษรไม่สำเร็จ ดู log')); return
        import mss
        sct = mss.mss()
        page = None; lastgeo = None; bp_sig = None
        self.q.put(('ready', None))
        while self.running:
            time.sleep(0.3 if page else 0.6)            # นอกหน้าใส่ของเช็คช้าลง
            try:
                if not SET['enabled']:
                    self.q.put(('page', (None, None))); continue
                geo = game_rect()
                if not geo:
                    if not self.ui_fg:
                        self.q.put(('page', (None, None)))
                    continue
                gx, gy, gw, gh = geo
                if geo != lastgeo or self.flush:
                    self.flush = False
                    self.sig.clear(); self.cache.clear(); lastgeo = geo
                frame = LazyFrame(sct, geo)
                t, ch1 = self.region(frame, 'title', 4.0)
                # หน้ากระเป๋าทุกหน้ามีตัวหนังสือมุมซ้ายบน (ชื่อหน้า หรือชื่อตัวละคร + Lv) · ไม่มี = กำลังเล่นอยู่ → ไม่ต้องอ่านส่วนอื่น (ประหยัด CPU)
                has_t = any(l['t'] for l in t)
                n = self.region(frame, 'nav', 4.0)[0] if (has_t or SET.get('craft')) else []
                pg = R.page_of(t, n)
                if pg == 'craft' and not SET.get('craft'):
                    pg = None
                if pg in (None, 'gear') and has_t:
                    # เข้าหน้าเลือกปืน/เกราะจากหน้า Gear จะไม่มีชื่อหน้า → ดูจากปุ่มล่าง (Equip/Unequip + Modify) แทน
                    fl0, _ = self.region(frame, 'footer', 5.0)
                    ft = ' '.join(l['t'] for l in fl0).lower()
                    if 'modify' in ft and 'equip' in ft:
                        pl0, _ = self.region(frame, 'panel', 5.0)
                        pg = 'weapons' if R.is_weapon_panel(pl0) else 'armor'
                if pg == 'gear' and R.nav_active(frame, n) != 'gear':
                    pg = None                                   # เปิดกระเป๋าแท็บอื่น (Backpack / Tech / Blueprints ...) → ไม่ต้องโชว์
                if pg != page:
                    page = pg; self.q.put(('hint', ('', 'info')))
                self.q.put(('page', (pg if (pg or SET.get('always')) else None, geo)))
                b = self.build
                if not pg or not b:
                    self.q.put(('marks', None)); continue
                if pg in ('weapons', 'armor'):
                    pl, chp = self.region(frame, 'panel', 5.0)
                    fl, chf = self.region(frame, 'footer', 5.0)
                    tab = R.tab_index(frame, pg)
                    badge = R.equipped_badge(frame)              # ป้าย E / 1 / 2 บนการ์ดที่เลือก = ชิ้นที่ใส่อยู่
                    key = (pg, tab, badge, ' '.join(l['t'] for l in pl[:6]), ' '.join(l['t'] for l in fl))
                    if key != self.cache.get('_last_item'):
                        self.cache['_last_item'] = key
                        it = R.parse_item(pl, D['mats'])
                        eq = ('unequip' in ' '.join(l['t'] for l in fl).lower()) or badge is True
                        r = b.on_item(pg, tab, it, eq, self.status)
                        self.q.put(('hint', r or ('', 'info'))); self.q.put(('status_changed', None))
                    self.q.put(('marks', None))
                elif pg == 'mod':
                    ml, chm = self.region(frame, 'modp', 5.0)
                    pm = R.parse_mod(ml)
                    if chm:
                        r = b.on_mod(pm, self.status)
                        self.q.put(('hint', r or ('', 'info'))); self.q.put(('status_changed', None))
                    # ช่องที่กำลังเลือก MOD อยู่ = ชนิดของ MOD ที่ใส่อยู่ (แผง Core Effects) → นำทางเฉพาะ MOD ของช่องนี้
                    cslot = BM.mod_slot_of(D, pm['name']) if pm else None
                    want = b.mod_keys_for_slot(cslot)
                    if cslot == 'Weapon' and pm:
                        # MOD ปืนใช้ได้ทั้ง 2 กระบอก: ถ้า MOD ที่ใส่อยู่ตรงกับปืนกระบอกไหน แปลว่ากำลังดูปืนกระบอกนั้น → ไม่นำทาง MOD ของอีกกระบอก
                        mine = {k for k in ('w0m', 'w1m') if k in b.items and (BM.same(b.items[k]['name'], pm['name'])
                                or any(BM.same(x, pm['name']) for x in b.mod_alts.get(k, [])))}
                        if mine:
                            want = mine
                    rl, chr_ = self.region(frame, 'rows', 6.0)
                    rows = [(r, v) for r, v in b.mod_rows(R.merge_rows(rl, gh)) if not want or v.get('_key') in want]
                    rects = [(int(r['x0']), int(r['y0']), int(r['x1']), int(r['y1']), 'บิ้วใช้ ' + v['name'] + (f" <{v['suf']}>" if v.get('suf') else '')) for r, v in rows]
                    # นำทางไปหมวด Keyword ของ MOD ที่ยังไม่ได้ใส่ (ไอคอนแถบซ้าย)
                    hl, _ = self.region(frame, 'modhead', 4.0)
                    cur = R.mod_category(hl); sel = R.cat_selected(frame)
                    cats = SET.setdefault('modcats', {})
                    if cur and sel is not None and cats.get(str(sel)) != cur and BM.same(cur, cur):
                        cats[str(sel)] = cur; save_set()                      # จำว่าไอคอนช่องนี้คือหมวดอะไร (เกมเปลี่ยนลำดับก็ยังถูก)
                    pend = [x for x in b.pending_mods(self.status) if not want or x[0] in want]
                    nokw = [(k, v) for k, v, kw in pend if not kw]
                    if nokw and not rows:                                  # MOD เกราะ/ทั่วไป ไม่มีหมวด Keyword → ให้พิมพ์ค้นหา
                        k, v = nokw[0]
                        sx0, sy0, sx1, sy1 = R.SEARCH_BOX
                        rects.append((int(sx0 * gw), int(sy0 * gh), int(sx1 * gw), int(sy1 * gh),
                                      f"พิมพ์ค้นหา \"{v['name']}\" ({v['label']}) · คลิกชื่อ MOD บนแถบเพื่อคัดลอก แล้วกด Ctrl+V"))
                    for k, v, kw in pend:
                        if not kw or (cur and BM.same(cur, kw, 85)):
                            continue
                        idx = next((int(i) for i, cn in cats.items() if BM.same(cn, kw, 85)), None)
                        if idx is None and kw in R.CAT_DEFAULT:
                            idx = R.CAT_DEFAULT.index(kw)
                        if idx is None:
                            continue
                        x0, y0, x1, y1 = R.cat_rect(idx, gw, gh)
                        rects.append((x0, y0, x1, y1, f"ไปหมวด {kw} · {v['label']}: {v['name']}"))
                        break
                    self.q.put(('marks', (geo, rects)))
                elif pg == 'craft':
                    self.q.put(('marks', None))
                    rc = detect.find_tooltip(frame.whole(), None)
                    if rc:
                        x0, y0, x1, y1 = rc
                        sg = R.sig(frame[y0:min(y1, y0 + 300), x0:x1])
                        if R.changed(sg, bp_sig, 5.0):
                            bp_sig = sg
                            bp = R.parse_blueprint(self.O(frame[y0:y1, x0:x1], (x0, y0)))
                            if bp:
                                self.q.put(('hint', b.on_blueprint(bp) or ('', 'info')))
                else:
                    self.q.put(('marks', None))
            except Exception:
                log('loop', traceback.format_exc()); time.sleep(1)


def make_icon(sz=64):
    p = os.path.join(BASE, 'build_overlay.png')
    if os.path.exists(p):
        return Image.open(p).convert('RGBA').resize((sz, sz), Image.LANCZOS)
    im = Image.new('RGBA', (sz, sz), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    d.rounded_rectangle((2, 2, sz - 3, sz - 3), radius=sz // 5, fill=(18, 20, 24, 255), outline=(0, 220, 210, 255), width=3)
    d.text((sz * 0.22, sz * 0.28), 'BO', fill=(0, 220, 210, 255))
    return im


def hotkey_thread(q):
    """Ctrl+Alt+B = ซ่อน/แสดง"""
    if not IS_WIN:
        return
    try:
        if not user32.RegisterHotKey(None, 1, 0x0002 | 0x0001 | 0x4000, ord('B')):
            log('hotkey fail'); return
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) != 0:
            if msg.message == 0x0312:
                q.put(('toggle', None))
    except Exception as e:
        log('hotkey', e)


# ───────────── เริ่มโมดูล (เรียกจาก OH Companion) ─────────────
NAME = 'build'


def start(root, host):
    """สร้างแถบบิ้ว + เธรดอ่านจอ แล้วคืนตัวควบคุมให้ OH Companion"""
    q = queue.Queue()
    strip = Strip(root, q); marks = Marks(root); picker = Picker(root, q)
    wk = Worker(q); wk.start()
    threading.Thread(target=hotkey_thread, args=(q,), daemon=True).start()
    toast = host.toast
    st = {'ready': False}

    def set_build(row, announce=True):
        b = BM.Build(row, D)
        SET['build'] = row; save_set()
        s = SET['status'].setdefault(b.id, {})
        s = {k: tuple(v) for k, v in s.items()}
        strip.build = b; strip.status = s; wk.build = b; wk.status = s
        wk.flush = True                                 # บิ้วใหม่ → อ่านหน้าจอใหม่หมด
        strip.hint = ('', 'info'); strip.imgs.clear()
        if strip.shown:
            strip.draw()
        if announce:
            toast(f'เลือกบิ้ว "{b.title}" แล้ว\nเปิดหน้าใส่ของในเกม (Gear / ปืน / เกราะ / MOD) แถบบิ้วจะขึ้นเอง')
        host.refresh()

    if SET.get('build'):
        try:
            set_build(SET['build'], False)

            def refresh():                             # อัปเดตบิ้วล่าสุดจากเว็บเงียบๆ
                try:
                    r = get_build(SET['build']['id'])
                    if r:
                        q.put(('build_quiet', r))
                except Exception as e:
                    log('refresh', e)
            threading.Thread(target=refresh, daemon=True).start()
        except Exception:
            log('restore', traceback.format_exc())

    def flip(key, on, off):
        def f():
            SET[key] = not SET.get(key); save_set(); toast(on if SET[key] else off); host.refresh()
        return f

    class Ctl:
        name = NAME

        def enabled(self):
            return bool(SET['enabled'])

        def set_enabled(self, on):
            SET['enabled'] = bool(on); save_set()
            if not on:
                strip.hide(); marks.hide()

        def status(self):
            if not st['ready']:
                return 'กำลังโหลดตัวอ่านตัวอักษร…', 'dim'
            if not strip.build:
                return 'ยังไม่ได้เลือกบิ้ว · กด "เลือกบิ้ว"', 'warn'
            t = 'บิ้ว: ' + strip.build.title[:42]
            return (t + ' · ซ่อนอยู่ (Ctrl+Alt+B)', 'dim') if not SET['enabled'] else (t, 'ok')

        def pick(self):
            picker.open()

        def actions(self):
            return [
                ('เลือกบิ้ว…', picker.open, None),
                ('แสดงในหน้าคราฟปืนด้วย (เช็คใบ Calibration)', flip('craft', 'แสดงในหน้าคราฟปืนด้วย', 'ไม่แสดงในหน้าคราฟปืน'), lambda: SET.get('craft')),
                ('แสดงตลอดเวลาในเกม (ไม่ใช่แค่หน้าใส่ของ)', flip('always', 'แสดงตลอดเวลาในเกม', 'แสดงเฉพาะหน้าใส่ของ'), lambda: SET.get('always')),
                ('ล้างสถานะที่เช็คไว้', lambda: q.put(('reset', None)), None),
                ('ย้ายแถบกลับตำแหน่งเดิม', lambda: q.put(('repos', None)), None),
                ('ทำงานกับทุกหน้าต่าง (ทดสอบ)', flip('any_window', 'ทำงานกับทุกหน้าต่าง', 'ทำงานเฉพาะในเกม'), lambda: SET.get('any_window')),
                None,
                ('เปิดหน้าบิ้วบนเว็บ', lambda: webbrowser.open(HUB + '/#oh-builds'), None),
                ('เปิดโฟลเดอร์ข้อมูล', lambda: os.startfile(DATA) if IS_WIN else None, None),
            ]

        def shutdown(self):
            wk.running = False; save_set()

    ctl = Ctl()

    def pump():
        try:
            while True:
                k, v = q.get_nowait()
                if k == 'page':
                    pg, geo = v
                    wk.ui_fg = our_window_fg([picker.w] if picker.w else [])
                    if pg and geo and SET['enabled']:
                        strip.show(geo)
                    elif not wk.ui_fg:
                        strip.hide(); marks.hide()
                elif k == 'hint':
                    if v != strip.hint:
                        strip.hint = v
                        if strip.shown:
                            strip.draw()
                elif k == 'status_changed':
                    if strip.build:
                        SET['status'][strip.build.id] = {a: list(b) for a, b in strip.status.items()}; save_set()
                    if strip.shown:
                        strip.draw()
                elif k == 'marks':
                    if v and strip.shown:
                        marks.show(v[0], v[1], strip.sc)
                    else:
                        marks.hide()
                elif k == 'img':
                    strip.set_img(*v)
                elif k == 'pick':
                    picker.open()
                elif k == 'builds':
                    picker.set_rows(v)
                elif k == 'builds_err':
                    picker.err(v)
                elif k == 'build':
                    set_build(v); picker.close()
                elif k == 'build_quiet':
                    set_build(v, False)
                elif k == 'reset':
                    strip.status.clear(); wk.flush = True; q.put(('status_changed', None)); toast('ล้างสถานะแล้ว')
                elif k == 'repos':
                    SET['pos2'] = None; save_set()
                    if strip.geo:
                        strip.place(strip.geo)
                elif k == 'toggle':
                    ctl.set_enabled(not SET['enabled'])
                    toast('แสดงแถบบิ้วแล้ว' if SET['enabled'] else 'ซ่อนแถบบิ้วแล้ว (Ctrl+Alt+B เพื่อแสดง)')
                    host.refresh()
                elif k == 'toast':
                    toast(v)
                elif k == 'ready':
                    st['ready'] = True; host.refresh()
                elif k == 'quit':
                    host.quit()
        except queue.Empty:
            pass
        except Exception:
            log('pump', traceback.format_exc())
        root.after(50, pump)

    root.after(50, pump)
    return ctl
