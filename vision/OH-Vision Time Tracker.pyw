# OH-Vision Time Tracker (MrSmitety)
# ตัวจับเวลา Vision ⇄ ช่วงพัก ลอยเหนือจอเกม (Once Human)
#
# วิธีใช้
#   ดับเบิลคลิกไฟล์นี้ (หรือทางลัด OH-Vision Time Tracker) = เปิด · ดับเบิลคลิกอีกครั้ง = ปิด (สลับเปิด/ปิด)
#   ลากด้วยเมาส์ซ้ายเพื่อย้ายที่ · คลิกขวา = เมนู (ล็อก, ความโปร่งใส, ขนาด, เสียงเตือน, ซิงก์เวลา, ปิด)
#   ไอคอนในถาดระบบ (มุมขวาล่าง) คลิกซ้าย = ซ่อน/แสดง · คลิกขวา = เมนูทั้งหมด
#   การ์ดบิ้ว: ก๊อปลิงก์บิ้วจาก hub.mrsmitety.com แล้วเลือก "การ์ดบิ้ว" ในเมนู (จำไว้ เปิดครั้งหน้าขึ้นเอง)
#   Ctrl+Alt+V  ซ่อน/แสดง
#   Ctrl+Alt+L  ล็อก/ปลดล็อก (ล็อกแล้วคลิกทะลุไปที่เกม) · ปิดแล้วเปิดใหม่จะกลับมาเป็นปลดล็อกเสมอ
#   ถ้ามีโปรแกรมอื่นใช้ปุ่มลัดนี้อยู่ จะเปลี่ยนเป็น Ctrl+Alt+Shift+V / L
#
# เวลา: ใช้นาฬิกาเครื่องเป็นหลัก แล้วเทียบกับเวลาอินเทอร์เน็ตทุกครั้งที่เปิด ถ้าเครื่องเพี้ยนเกิน 1.5 วินาทีจะปรับให้อัตโนมัติ
# รอบ Vision: อ่านจากหน้าตั้งค่าแอดมินของ hub.mrsmitety.com (ค่าเดียวกับเว็บ) ถ้าออฟไลน์ใช้ค่าล่าสุดที่จำไว้
# หน้าตาสวยสุดเมื่อมี Pillow (pip install pillow) ถ้าไม่มีจะใช้แบบเรียบ
# เกมต้องเป็นโหมด Borderless/Windowed ถ้าเป็น Fullscreen แบบเต็มจอจริง หน้าต่างอื่นจะขึ้นทับไม่ได้

import json, os, socket, sys, threading, time, urllib.request, email.utils
import tkinter as tk, traceback

FROZEN = getattr(sys, 'frozen', False)                         # True เมื่อรันจากไฟล์ .exe
HERE = os.path.dirname(sys.executable if FROZEN else os.path.abspath(__file__))   # โฟลเดอร์ของ .exe / สคริปต์
RES = getattr(sys, '_MEIPASS', HERE)                              # ไฟล์ที่ฝังมาใน .exe (โลโก้)
LOG = os.path.join(os.environ.get('APPDATA') or HERE, 'MrSmitetyVision', 'OH-Vision Time Tracker.log')
try: os.makedirs(os.path.dirname(LOG), exist_ok=True)
except Exception: pass
def log(msg):
    try:
        with open(LOG, 'a', encoding='utf-8') as f: f.write(time.strftime('%Y-%m-%d %H:%M:%S ') + msg + '\n')
    except Exception: pass
def crash(exc_type, exc, tb):
    txt = ''.join(traceback.format_exception(exc_type, exc, tb)); log('ERROR\n' + txt)
    try:
        from tkinter import messagebox
        r = tk.Tk(); r.withdraw(); messagebox.showerror('OH-Vision Time Tracker', 'เปิดไม่สำเร็จ\n\n' + txt[-900:] + '\n\nบันทึกไว้ที่ ' + LOG); r.destroy()
    except Exception: pass
    os._exit(1)
sys.excepthook = crash

VERSION = '1.2.2'   # เปลี่ยนเลขนี้ทุกครั้งที่แก้โปรแกรมแล้วจะแจกใหม่
APP = 'MrSmitetyVision'
PORT = 47615
SB_URL = 'https://ejletwoddaqdnjjqjwun.supabase.co'
SB_KEY = 'sb_publishable_uLX_CLa1meE1FxNGOaYm7g_RnvZ83u6'   # คีย์สาธารณะสำหรับอ่านค่า (ไม่ใช่คีย์ลับ)
TIME_URLS = ['https://hub.mrsmitety.com/manifest.webmanifest', 'https://www.cloudflare.com/', 'https://www.google.com/']
DEFAULT = {'on': '1', 'anchor': '2026-11-22T22:15:04+07:00', 'len': 30, 'gap': 30, 'name': 'Vision'}
WIN = sys.platform == 'win32'

# ── เปิด/ปิดแบบสลับ: ถ้ามีตัวเปิดอยู่แล้ว ส่งคำสั่งปิดแล้วจบ
def toggle_existing():
    try:
        s = socket.create_connection(('127.0.0.1', PORT), timeout=0.6); s.sendall(b'quit'); s.close(); return True
    except OSError:
        return False

log('start v%s python %s' % (VERSION, sys.version.split()[0]))
if toggle_existing():
    log('มีตัวเปิดอยู่แล้ว -> สั่งปิด'); sys.exit(0)

CFG_DIR = os.path.join(os.environ.get('APPDATA') or os.path.expanduser('~'), APP)
CFG_FILE = os.path.join(CFG_DIR, 'config.json')
def load_cfg():
    try:
        with open(CFG_FILE, encoding='utf-8') as f: return json.load(f)
    except Exception: return {}
def save_cfg():
    try:
        os.makedirs(CFG_DIR, exist_ok=True)
        with open(CFG_FILE, 'w', encoding='utf-8') as f: json.dump(CFG, f, ensure_ascii=False, indent=1)
    except Exception: pass
CFG = load_cfg()
CFG.setdefault('x', 40); CFG.setdefault('y', 40); CFG.setdefault('alpha', 0.88); CFG.setdefault('size', 'm')
CFG['locked'] = False; CFG.setdefault('beep', True); CFG.setdefault('settings', dict(DEFAULT))

def parse_iso(v):
    from datetime import datetime
    try: return datetime.fromisoformat(v.replace('Z', '+00:00')).timestamp()
    except Exception: return None

# ── ค่ารอบ Vision จากเว็บ
def fetch_settings():
    try:
        req = urllib.request.Request(SB_URL + '/rest/v1/app_settings?select=key,value&key=like.vision_*',
                                     headers={'apikey': SB_KEY, 'Authorization': 'Bearer ' + SB_KEY})
        with urllib.request.urlopen(req, timeout=5) as r:
            s = {x['key']: x['value'] for x in json.load(r)}
        out = dict(DEFAULT)
        if s.get('vision_on'): out['on'] = s['vision_on']
        if s.get('vision_anchor') and parse_iso(s['vision_anchor']): out['anchor'] = s['vision_anchor']
        for k in ('len', 'gap'):
            try:
                v = float(s.get('vision_' + k, ''));  out[k] = v if v > 0 else out[k]
            except ValueError: pass
        if s.get('vision_name'): out['name'] = s['vision_name'][:30]
        CFG['settings'] = out; save_cfg(); return True
    except Exception:
        return False

# ── เทียบนาฬิกาเครื่องกับเวลาอินเทอร์เน็ต
OFFSET = 0.0
SYNC_NOTE = 'เวลาเครื่อง'
def sync_clock():
    global OFFSET, SYNC_NOTE
    for u in TIME_URLS:
        try:
            req = urllib.request.Request(u, method='HEAD', headers={'Cache-Control': 'no-cache'})
            t0 = time.time()
            with urllib.request.urlopen(req, timeout=5) as r: d = r.headers.get('Date')
            t1 = time.time()
            if not d: continue
            server = email.utils.parsedate_to_datetime(d).timestamp() + 0.5
            off = server - (t0 + t1) / 2
            if abs(off) > 1.5:
                OFFSET = off; SYNC_NOTE = 'ปรับเวลา %+.0f วิ' % off
            else:
                OFFSET = 0.0; SYNC_NOTE = 'เวลาตรงแล้ว'
            return True
        except Exception:
            continue
    SYNC_NOTE = 'ออฟไลน์'
    return False

def now(): return time.time() + OFFSET

def phase(t):
    S = CFG['settings']; A = parse_iso(S['anchor']) or parse_iso(DEFAULT['anchor'])
    L = float(S['len']) * 60; G = float(S['gap']) * 60; P = L + G
    p = (t - A) % P
    vis = p < L
    return vis, (L - p) if vis else (P - p), (p / L) if vis else ((p - L) / G)

def fmt(sec):
    s = max(0, int(-(-sec // 1))); h, m, x = s // 3600, s % 3600 // 60, s % 60
    return ('%d:%02d:%02d' % (h, m, x)) if h else ('%d:%02d' % (m, x))

# ── หน้าต่าง
# ขนาด: (กว้าง, สูง) หน่วยพิกเซลจอ
SIZES = {'s': (250, 64), 'm': (316, 80), 'l': (404, 102)}
KEY = '#010203'            # สีที่ Windows ทำให้โปร่งใส (มุมโค้งของการ์ด)
C_BG, C_VIS, C_REST, C_SOON, C_TXT, C_MUT = '#0f1320', '#b48cff', '#5ff0e6', '#ffc83c', '#ffffff', '#93a0b4'
FONT_TK = 'Leelawadee UI' if WIN else 'DejaVu Sans'

try:
    from PIL import Image, ImageDraw, ImageFont, ImageTk
    HAS_PIL = True
except Exception:
    HAS_PIL = False

FONT_DIRS = [os.path.join(os.environ.get('WINDIR', r'C:\Windows'), 'Fonts'), '/usr/share/fonts/opentype/tlwg', '/usr/share/fonts/opentype/inter']
def _font(names, size):
    for d in FONT_DIRS:
        for n in names:
            p = os.path.join(d, n)
            if os.path.exists(p):
                try: return ImageFont.truetype(p, size)
                except Exception: pass
    return ImageFont.load_default()
F_THAI_B = ['LeelaUIb.ttf', 'leelauib.ttf', 'Loma-Bold.otf']
F_THAI = ['LeelawUI.ttf', 'leelawui.ttf', 'Loma.otf']
F_NUM = ['bahnschrift.ttf', 'segoeuib.ttf', 'Inter-SemiBold.otf', 'Loma-Bold.otf']
_fcache = {}
def F(kind, size):
    k = (kind, size)
    if k not in _fcache: _fcache[k] = _font({'tb': F_THAI_B, 't': F_THAI, 'n': F_NUM}[kind], size)
    return _fcache[k]

def hex2rgb(h, a=255): h = h.lstrip('#'); return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), a)

def render(w, h, st):
    """วาดการ์ดด้วย Pillow แบบ 3 เท่าแล้วย่อ ให้ขอบเนียน · คืนรูป RGBA"""
    S = 3; W, H = w * S, h * S
    im = Image.new('RGBA', (W, H), (0, 0, 0, 0)); d = ImageDraw.Draw(im)
    col = st['col']; r = H // 2
    # พื้นการ์ด + ขอบสีตามช่วง + แสงจางๆ ด้านซ้าย
    d.rounded_rectangle((0, 0, W - 1, H - 1), radius=r, fill=hex2rgb(C_BG, 242))
    glow = Image.new('RGBA', (W, H), (0, 0, 0, 0)); gd = ImageDraw.Draw(glow)
    for i in range(14):
        a = int(42 * (1 - i / 14)); gd.ellipse((-H * 0.6 - i * 6 * S, -H * 0.4 - i * 3 * S, H * 1.6 + i * 6 * S, H * 1.4 + i * 3 * S), fill=hex2rgb(col, max(0, a // 3)))
    mask = Image.new('L', (W, H), 0); ImageDraw.Draw(mask).rounded_rectangle((0, 0, W - 1, H - 1), radius=r, fill=255)
    im = Image.composite(Image.alpha_composite(im, glow), im, mask); d = ImageDraw.Draw(im)
    d.rounded_rectangle((S, S, W - 1 - S, H - 1 - S), radius=r - S, outline=hex2rgb(col, 150), width=2 * S)
    # วงแหวนความคืบหน้า
    pad = int(H * 0.16); cx0, cy0, cx1, cy1 = pad, pad, H - pad, H - pad; lw = max(3 * S, int(H * 0.085))
    d.ellipse((cx0, cy0, cx1, cy1), outline=(255, 255, 255, 28), width=lw)
    d.arc((cx0, cy0, cx1, cy1), start=-90, end=-90 + 360 * max(0.002, st['frac']), fill=hex2rgb(col), width=lw)
    # ไอคอนกลางวง: Vision = ดาว 4 แฉก, พัก = ขีดคู่, ใกล้เริ่ม = จุดกระพริบ
    mx, my, rr = (cx0 + cx1) / 2, (cy0 + cy1) / 2, (cx1 - cx0) * 0.2
    if st['vis']:
        pts = [(mx, my - rr * 1.5), (mx + rr * .38, my - rr * .38), (mx + rr * 1.5, my), (mx + rr * .38, my + rr * .38),
               (mx, my + rr * 1.5), (mx - rr * .38, my + rr * .38), (mx - rr * 1.5, my), (mx - rr * .38, my - rr * .38)]
        d.polygon(pts, fill=hex2rgb(col))
    elif st['soon']:
        a = 255 if st['blink'] else 110; d.ellipse((mx - rr, my - rr, mx + rr, my + rr), fill=hex2rgb(col, a))
    else:
        bw = rr * .55; d.rounded_rectangle((mx - rr * .95, my - rr, mx - rr * .95 + bw, my + rr), radius=bw / 2, fill=hex2rgb(col))
        d.rounded_rectangle((mx + rr * .95 - bw, my - rr, mx + rr * .95, my + rr), radius=bw / 2, fill=hex2rgb(col))
    # ข้อความ
    x = H + int(H * 0.02)
    f_lab = F('tb', int(H * 0.2)); f_num = F('n', int(H * 0.44)); f_sub = F('t', int(H * 0.15))
    d.text((x, int(H * 0.13)), st['label'], font=f_lab, fill=hex2rgb(col))
    d.text((x - S, int(H * 0.35)), st['time'], font=f_num, fill=hex2rgb(C_TXT))
    if st['sub']:
        d.text((W - int(H * 0.36), int(H * 0.15)), st['sub'], font=f_sub, fill=hex2rgb(C_MUT), anchor='ra')
    if st['locked']:
        ls = int(H * 0.085); lx, ly = W - int(H * 0.36) - ls * 2, H - int(H * 0.2) - ls * 2.6
        d.rounded_rectangle((lx, ly + ls, lx + ls * 2, ly + ls * 2.6), radius=ls // 3, fill=hex2rgb(C_MUT))
        d.arc((lx + ls * .35, ly + ls * .2, lx + ls * 1.65, ly + ls * 1.6), 180, 360, fill=hex2rgb(C_MUT), width=max(2, ls // 3))
    return im.resize((w, h), Image.LANCZOS)

def to_keyed(im):
    """ใส่สีพื้นหลังโปร่งใส (KEY) ตรงที่ alpha ต่ำ ส่วนที่เหลือผสมกับสีการ์ด กันขอบเป็นเงาดำ"""
    bg = Image.new('RGBA', im.size, hex2rgb(C_BG)); out = Image.alpha_composite(bg, im).convert('RGB')
    a = im.split()[3].point(lambda v: 255 if v < 110 else 0)
    out.paste(Image.new('RGB', im.size, tuple(int(KEY[i:i + 2], 16) for i in (1, 3, 5))), mask=a)
    return out

root = tk.Tk(); root.title('OH-Vision Time Tracker')
try: root.iconbitmap(os.path.join(RES, 'vision.ico'))
except Exception: pass
root.report_callback_exception = lambda et, ev, tb: log('CALLBACK ERROR\n' + ''.join(traceback.format_exception(et, ev, tb)))
root.overrideredirect(True); root.attributes('-topmost', True)
try: root.attributes('-alpha', float(CFG['alpha']))
except Exception: pass
if WIN:
    root.configure(bg=KEY)
    try: root.attributes('-transparentcolor', KEY)
    except Exception: pass
else:
    root.configure(bg=C_BG)
cv = tk.Canvas(root, bg=KEY if WIN else C_BG, highlightthickness=0, bd=0); cv.pack(fill='both', expand=True)

if WIN:
    import ctypes
    from ctypes import wintypes
    try: ctypes.windll.shcore.SetProcessDpiAwareness(1)
    except Exception: pass
    user32 = ctypes.windll.user32
    GWL_EXSTYLE, WS_EX_LAYERED, WS_EX_TRANSPARENT, WS_EX_TOOLWINDOW, WS_EX_NOACTIVATE = -20, 0x80000, 0x20, 0x80, 0x08000000
    def hwnd(w=None):
        w = w or root; return user32.GetParent(w.winfo_id()) or w.winfo_id()
    def set_clickthrough(on, w=None):
        h = hwnd(w); st = user32.GetWindowLongW(h, GWL_EXSTYLE) | WS_EX_LAYERED | WS_EX_TOOLWINDOW | WS_EX_NOACTIVATE
        st = (st | WS_EX_TRANSPARENT) if on else (st & ~WS_EX_TRANSPARENT)
        user32.SetWindowLongW(h, GWL_EXSTYLE, st)
    # ปุ่มลัดทั้งเครื่อง: ลงทะเบียนในเธรดแยกที่มีลูปข้อความของตัวเอง (ลูปของ Tk กินข้อความปุ่มลัดทิ้ง)
    import queue
    HKQ = queue.Queue()
    MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_NOREPEAT, WM_HOTKEY = 0x1, 0x2, 0x4, 0x4000, 0x0312
    HK_HIDE, HK_LOCK = 1, 2
    def hotkey_thread():
        regs = [(HK_HIDE, MOD_CONTROL | MOD_ALT, 'V'), (HK_LOCK, MOD_CONTROL | MOD_ALT, 'L')]
        for hid, mod, key in regs:
            ok = user32.RegisterHotKey(None, hid, mod | MOD_NOREPEAT, ord(key))
            if not ok:   # มีโปรแกรมอื่นจองไว้แล้ว ลองเพิ่ม Shift
                ok = user32.RegisterHotKey(None, hid, mod | MOD_SHIFT | MOD_NOREPEAT, ord(key))
                log('hotkey Ctrl+Alt+%s ถูกจองแล้ว -> ใช้ Ctrl+Alt+Shift+%s (%s)' % (key, key, 'ok' if ok else 'fail'))
            else:
                log('hotkey Ctrl+Alt+%s ok' % key)
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY: HKQ.put(msg.wParam)
    threading.Thread(target=hotkey_thread, daemon=True).start()
    def poll_hotkeys():
        try:
            while True:
                k = HKQ.get_nowait()
                if k == HK_HIDE: toggle_hide()
                elif k == HK_LOCK: toggle_lock()
        except queue.Empty: pass
        root.after(50, poll_hotkeys)
    def beep():
        try:
            import winsound; winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except Exception: pass
else:
    def set_clickthrough(on, w=None): pass
    def poll_hotkeys(): pass
    def beep(): root.bell()

HIDDEN = False
def toggle_hide():
    global HIDDEN
    HIDDEN = not HIDDEN
    root.withdraw() if HIDDEN else (root.deiconify(), root.attributes('-topmost', True), set_clickthrough(CFG['locked']))
    if BW.win: BW.win.withdraw() if HIDDEN else (BW.win.deiconify(), BW.win.attributes('-topmost', True), set_clickthrough(CFG['locked'], BW.win))

HINT = ['', 0]
def toggle_lock():
    CFG['locked'] = not CFG['locked']; save_cfg(); set_clickthrough(CFG['locked'])
    if BW.win: set_clickthrough(CFG['locked'], BW.win)
    HINT[:] = ['ปลดล็อก: Ctrl+Alt+L' if CFG['locked'] else 'ปลดล็อกแล้ว', time.time() + 4]; _last['sig'] = None

def apply_size():
    w, h = SIZES.get(CFG['size'], SIZES['m'])
    vw, vh = root.winfo_vrootwidth() or root.winfo_screenwidth(), root.winfo_vrootheight() or root.winfo_screenheight()
    if not (-w < int(CFG['x']) < vw - 20 and 0 <= int(CFG['y']) < vh - 20): CFG['x'], CFG['y'] = 40, 40
    root.geometry('%dx%d+%d+%d' % (w, h, int(CFG['x']), int(CFG['y'])))

# ลากย้าย
_drag = {}
def on_press(e): _drag.update(x=e.x_root - root.winfo_x(), y=e.y_root - root.winfo_y())
def on_move(e):
    if CFG['locked']: return
    CFG['x'], CFG['y'] = e.x_root - _drag.get('x', 0), e.y_root - _drag.get('y', 0)
    root.geometry('+%d+%d' % (CFG['x'], CFG['y']))
def on_release(e): save_cfg()
cv.bind('<ButtonPress-1>', on_press); cv.bind('<B1-Motion>', on_move); cv.bind('<ButtonRelease-1>', on_release)

def resync():
    def job():
        fetch_settings(); sync_clock(); root.after(0, lambda: draw(force=True))
    threading.Thread(target=job, daemon=True).start()

menu = tk.Menu(root, tearoff=0)
def build_menu():
    menu.delete(0, 'end')
    menu.add_command(label=('ปลดล็อก' if CFG['locked'] else 'ล็อก (คลิกทะลุไปที่เกม)') + '   Ctrl+Alt+L', command=toggle_lock)
    menu.add_command(label='ซ่อน   Ctrl+Alt+V', command=toggle_hide)
    sub = tk.Menu(menu, tearoff=0)
    for a in (1.0, 0.88, 0.7, 0.5):
        sub.add_radiobutton(label='%d%%' % (a * 100), command=lambda a=a: (CFG.update(alpha=a), root.attributes('-alpha', a), save_cfg()))
    menu.add_cascade(label='ความทึบ', menu=sub)
    sz = tk.Menu(menu, tearoff=0)
    for k, n in (('s', 'เล็ก'), ('m', 'กลาง'), ('l', 'ใหญ่')):
        sz.add_radiobutton(label=n, command=lambda k=k: (CFG.update(size=k), save_cfg(), apply_size(), draw(force=True)))
    menu.add_cascade(label='ขนาด', menu=sz)
    menu.add_command(label=('✓ ' if CFG['beep'] else '    ') + 'เสียงเตือน 1 นาทีก่อนเริ่ม', command=lambda: (CFG.update(beep=not CFG['beep']), save_cfg()))
    menu.add_command(label='การ์ดบิ้ว: เปิดจากลิงก์ที่ก๊อปไว้', command=build_from_clipboard)
    if BW.win: menu.add_command(label='ปิดการ์ดบิ้ว', command=build_card_close)
    menu.add_command(label='ซิงก์เวลา + โหลดรอบใหม่', command=resync)
    menu.add_separator(); menu.add_command(label='ปิดโปรแกรม', command=quit_app)
def on_menu(e): build_menu(); menu.tk_popup(e.x_root, e.y_root)
cv.bind('<Button-3>', on_menu)

_last = {'beeped': None, 'img': None, 'sig': None}
def hhmmss(t):
    from datetime import datetime, timezone, timedelta
    return datetime.fromtimestamp(t, timezone(timedelta(hours=7))).strftime('%H:%M:%S')
def state(force):
    S = CFG['settings']; t = now(); vis, left, frac = phase(t)
    soon = (not vis) and left <= 60
    nxt = t + left if not vis else t + left + float(S['gap']) * 60
    return {'t': t, 'vis': vis, 'left': left, 'frac': frac, 'soon': soon, 'blink': int(t * 2) % 2 == 0,
            'col': C_VIS if vis else (C_SOON if soon else C_REST),
            'label': ('%s · เหลือ' if vis else '%s · เริ่มใน') % S['name'],
            'time': fmt(left), 'sub': HINT[0] if time.time() < HINT[1] else (SYNC_NOTE if force else 'ถัดไป ' + hhmmss(nxt)),
            'locked': CFG['locked'], 'off': S.get('on') == '0'}
def draw(force=False):
    w, h = SIZES.get(CFG['size'], SIZES['m']); st = state(force)
    if CFG['beep'] and st['soon'] and _last['beeped'] != int((st['t'] + st['left']) // 60):
        _last['beeped'] = int((st['t'] + st['left']) // 60); beep()
    if st['off']:
        st.update(label='ตัวจับเวลาปิดอยู่', time='--:--', sub='เปิดที่หน้าแอดมิน', col=C_MUT, frac=0)
    sig = (w, h, st['label'], st['time'], st['sub'], st['col'], st['locked'], round(st['frac'], 3), st['blink'] if st['soon'] else 0)
    if sig == _last['sig']: return
    _last['sig'] = sig
    cv.delete('all')
    global HAS_PIL
    if HAS_PIL:
        try:
            im = render(w, h, st)
            _last['img'] = ImageTk.PhotoImage(to_keyed(im) if WIN else Image.alpha_composite(Image.new('RGBA', im.size, hex2rgb(C_BG)), im))
            cv.create_image(0, 0, anchor='nw', image=_last['img']); return
        except Exception as e:
            HAS_PIL = False; log('PIL draw failed, ใช้แบบเรียบแทน: %r' % e)
    if True:   # ไม่มี Pillow: วาดแบบเรียบ
        cv.create_rectangle(0, 0, w, h, fill=C_BG, outline=st['col'], width=2)
        cv.create_rectangle(2, h - 5, 2 + (w - 4) * st['frac'], h - 2, fill=st['col'], outline='')
        cv.create_text(12, 8, anchor='nw', text=st['label'], fill=st['col'], font=(FONT_TK, max(9, h // 7), 'bold'))
        cv.create_text(12, h - 8, anchor='sw', text=st['time'], fill=C_TXT, font=(FONT_TK, h // 3, 'bold'))
        cv.create_text(w - 10, h - 10, anchor='se', text=st['sub'], fill=C_MUT, font=(FONT_TK, max(7, h // 10)))

# ── ไอคอนในถาดระบบ (มุมขวาล่างของ Windows) กดแล้วมีเมนูแยก
import queue as _q
CALLQ = _q.Queue()                      # งานจากเธรดถาด -> ทำในเธรดหน้าต่าง
def poll_calls():
    try:
        while True: CALLQ.get_nowait()()
    except _q.Empty: pass
    root.after(60, poll_calls)
TRAY = None
def start_tray():
    global TRAY
    try:
        import pystray
        from pystray import MenuItem as Item, Menu
    except Exception as e:
        log('ไม่มี pystray -> ไม่มีไอคอนในถาด (%r)' % e); return
    try: img = Image.open(os.path.join(RES, 'vision.ico'))
    except Exception: img = Image.new('RGBA', (64, 64), (180, 140, 255, 255))
    q = lambda f: (lambda icon, item: CALLQ.put(f))
    def set_size(k): CFG.update(size=k); save_cfg(); apply_size(); _last['sig'] = None
    def set_alpha(a): CFG.update(alpha=a); root.attributes('-alpha', a); save_cfg()
    def show_only():
        if HIDDEN: toggle_hide()
    menu = Menu(
        Item('แสดง / ซ่อน  (Ctrl+Alt+V)', q(toggle_hide), default=True),
        Item('ล็อก คลิกทะลุ  (Ctrl+Alt+L)', q(toggle_lock), checked=lambda i: CFG['locked']),
        Item('เสียงเตือน 1 นาทีก่อนเริ่ม', q(lambda: (CFG.update(beep=not CFG['beep']), save_cfg())), checked=lambda i: CFG['beep']),
        Item('ขนาด', Menu(*[Item(n, q(lambda k=k: set_size(k)), radio=True, checked=lambda i, k=k: CFG['size'] == k) for k, n in (('s', 'เล็ก'), ('m', 'กลาง'), ('l', 'ใหญ่'))])),
        Item('ความทึบ', Menu(*[Item('%d%%' % (a * 100), q(lambda a=a: set_alpha(a)), radio=True, checked=lambda i, a=a: abs(float(CFG['alpha']) - a) < .01) for a in (1.0, 0.88, 0.7, 0.5)])),
        Item('การ์ดบิ้ว: เปิดจากลิงก์ที่ก๊อปไว้', q(build_from_clipboard)),
        Item('ปิดการ์ดบิ้ว', q(build_card_close), enabled=lambda i: BW.win is not None),
        Item('ย้ายกลับมุมซ้ายบน', q(lambda: (show_only(), CFG.update(x=40, y=40), save_cfg(), apply_size()))),
        Item('ซิงก์เวลา + โหลดรอบใหม่', q(resync)),
        Menu.SEPARATOR,
        Item('ปิดโปรแกรม', q(quit_app)))
    TRAY = pystray.Icon('OH-Vision', img, 'OH-Vision Time Tracker v' + VERSION, menu)
    TRAY.run_detached()
    def tip():
        try:
            st = state(False); TRAY.title = 'OH-Vision · %s %s' % (st['label'].replace(' · ', ' '), st['time'])
        except Exception: pass
        root.after(5000, tip)
    tip()


# ── การ์ดบิ้ว: วางลิงก์บิ้วจาก hub แล้วโชว์อุปกรณ์ลอยบนจอเกม
import re, io, html as _html
ICON_DIR = os.path.join(CFG_DIR, 'icons')
def _icon_url(key): return 'https://hub.mrsmitety.com/oh/icons/' + re.sub(r'[^A-Za-z0-9_/\-]', '_', key).strip('/') + '.webp'
def _icon(key, size):
    if not key or not HAS_PIL: return None
    fn = os.path.join(ICON_DIR, re.sub(r'[^A-Za-z0-9_\-]', '_', key) + '.webp')
    try:
        if not os.path.exists(fn):
            os.makedirs(ICON_DIR, exist_ok=True)
            with urllib.request.urlopen(urllib.request.Request(_icon_url(key), headers={'User-Agent': 'OH-Vision'}), timeout=6) as r: data = r.read()
            with open(fn, 'wb') as f: f.write(data)
        im = Image.open(fn).convert('RGBA'); im.thumbnail(size, Image.LANCZOS); return im
    except Exception as e:
        log('icon %s: %r' % (key, e)); return None
def _strip(h): return re.sub(r'\s+', ' ', _html.unescape(re.sub(r'<[^>]+>', ' ', h or ''))).strip()
def fetch_build(bid):
    req = urllib.request.Request(SB_URL + '/rest/v1/creations_gallery?select=title,data,display_name&id=eq.' + bid,
                                 headers={'apikey': SB_KEY, 'Authorization': 'Bearer ' + SB_KEY})
    with urllib.request.urlopen(req, timeout=8) as r: rows = json.load(r)
    return rows[0] if rows else None

def render_build(b, scale=1.0):
    k = 3; W = int(400 * scale); u = lambda v: int(v * scale * k)
    S, T = (b.get('data') or {}).get('slots', {}), (b.get('data') or {}).get('text', {})
    lines = []
    big = Image.new('RGBA', (W * k, u(900)), (0, 0, 0, 0)); d = ImageDraw.Draw(big)
    y = u(14); x0 = u(16)
    d.text((x0, y), 'บิ้วที่ใช้อยู่', font=F('tb', u(13)), fill=hex2rgb(C_REST)); y += u(20)
    title = b.get('title') or 'บิ้ว'; ft = F('tb', u(19))
    while d.textlength(title, font=ft) > W * k - 2 * x0 and len(title) > 4: title = title[:-2]
    if title != (b.get('title') or 'บิ้ว'): title = title.rstrip() + '…'
    d.text((x0, y), title, font=ft, fill=hex2rgb(C_TXT)); y += u(27)
    d.text((x0, y), 'โดย ' + (b.get('display_name') or ''), font=F('t', u(12)), fill=hex2rgb(C_MUT)); y += u(22)
    for wk in ('w0', 'w1'):
        w = S.get(wk); m = S.get(wk + 'm')
        if not w: continue
        d.line((x0, y, W * k - x0, y), fill=(255, 255, 255, 22), width=k); y += u(6)
        wi = _icon(w.get('icon'), (u(104), u(46)))
        if wi: big.alpha_composite(wi, (x0 + (u(104) - wi.width) // 2, y + (u(46) - wi.height) // 2))
        tx = x0 + u(116)
        d.text((tx, y + u(2)), w.get('name', ''), font=F('tb', u(15)), fill=hex2rgb(C_TXT))
        if m:
            mi = _icon(m.get('icon'), (u(20), u(20)))
            if mi: big.alpha_composite(mi, (tx, y + u(24)))
            d.text((tx + u(26), y + u(25)), m.get('name', '') + ('  <%s>' % m['suf'] if m.get('suf') else ''), font=F('t', u(13)), fill=(231, 220, 255, 255))
        y += u(54)
    cal = _strip(T.get('w0.calib')).upper()
    if cal: d.text((x0, y + u(2)), cal[:48], font=F('tb', u(12)), fill=hex2rgb(C_SOON)); y += u(24)
    def row(keys, sz=44):
        nonlocal y
        xx = x0; any_ = False
        for kk in keys:
            if kk == '|': xx += u(8); continue
            it = S.get(kk); ii = _icon(it and it.get('icon'), (u(sz), u(sz)))
            if not it: continue
            d.rounded_rectangle((xx, y, xx + u(sz), y + u(sz)), radius=u(7), fill=(255, 255, 255, 14))
            if ii: big.alpha_composite(ii, (xx + (u(sz) - ii.width) // 2, y + (u(sz) - ii.height) // 2))
            xx += u(sz + 6); any_ = True
        if any_: y += u(sz + 8)
    row(['a0', 'a1', 'a2', 'a3', 'a4', 'a5'])
    sets = []
    for i in range(6):
        t = _strip(T.get('a%d.lb' % i))
        if t and t not in sets: sets.append(t)
    if sets:
        xx = x0; fs = F('t', u(11))
        for t in sets:
            tw = d.textlength(t, font=fs) + u(14)
            if xx + tw > W * k - x0: xx = x0; y += u(22)
            d.rounded_rectangle((xx, y, xx + tw, y + u(18)), radius=u(9), fill=(255, 255, 255, 22)); d.text((xx + u(7), y + u(2)), t, font=fs, fill=(207, 216, 227, 255)); xx += tw + u(5)
        y += u(26)
    row(['f0', 'f1', 'f2', 'f3', '|', 'd0', 'd1', 'd2'], 38)
    d.text((W * k - x0, y + u(2)), 'hub.mrsmitety.com', font=F('tb', u(11)), fill=hex2rgb(C_REST), anchor='ra'); y += u(24)
    H = y
    card = Image.new('RGBA', (W * k, H), (0, 0, 0, 0)); cd = ImageDraw.Draw(card)
    cd.rounded_rectangle((0, 0, W * k - 1, H - 1), radius=u(18), fill=hex2rgb(C_BG, 242), outline=(58, 69, 96, 255), width=u(2))
    card.alpha_composite(big.crop((0, 0, W * k, H)))
    return card.resize((W, H // k), Image.LANCZOS)

class _BW: win = None; cv = None; img = None; data = None; bid = None
BW = _BW()
def build_card_open(bid):
    def job():
        try:
            b = fetch_build(bid)
            if not b: raise ValueError('ไม่พบบิ้ว หรือบิ้วไม่ได้เปิดสาธารณะ')
            img = render_build(b, {'s': .85, 'm': 1.0, 'l': 1.25}.get(CFG['size'], 1.0))
            CALLQ.put(lambda: _bw_show(bid, img))
        except Exception as e:
            log('build card: %r' % e); CALLQ.put(lambda: (HINT.__setitem__(slice(None), ['โหลดบิ้วไม่ได้', time.time() + 5]), _last.__setitem__('sig', None)))
    HINT[:] = ['กำลังโหลดบิ้ว…', time.time() + 4]; _last['sig'] = None
    threading.Thread(target=job, daemon=True).start()
def _bw_show(bid, img):
    BW.bid = bid; CFG['build_id'] = bid; save_cfg()
    if not BW.win:
        BW.win = tk.Toplevel(root); BW.win.overrideredirect(True); BW.win.attributes('-topmost', True)
        try: BW.win.attributes('-alpha', float(CFG['alpha']))
        except Exception: pass
        if WIN:
            BW.win.configure(bg=KEY)
            try: BW.win.attributes('-transparentcolor', KEY)
            except Exception: pass
        BW.cv = tk.Canvas(BW.win, bg=KEY if WIN else C_BG, highlightthickness=0, bd=0); BW.cv.pack(fill='both', expand=True)
        dr = {}
        BW.cv.bind('<ButtonPress-1>', lambda e: dr.update(x=e.x_root - BW.win.winfo_x(), y=e.y_root - BW.win.winfo_y()))
        def mv(e):
            if CFG['locked']: return
            CFG['bx'], CFG['by'] = e.x_root - dr.get('x', 0), e.y_root - dr.get('y', 0); BW.win.geometry('+%d+%d' % (CFG['bx'], CFG['by']))
        BW.cv.bind('<B1-Motion>', mv); BW.cv.bind('<ButtonRelease-1>', lambda e: save_cfg())
        bm = tk.Menu(BW.win, tearoff=0)
        bm.add_command(label='โหลดบิ้วใหม่ (ถ้าแก้บนเว็บ)', command=lambda: build_card_open(BW.bid))
        bm.add_command(label='ปิดการ์ดบิ้ว', command=build_card_close)
        BW.cv.bind('<Button-3>', lambda e: bm.tk_popup(e.x_root, e.y_root))
    BW.img = ImageTk.PhotoImage(to_keyed(img) if WIN else Image.alpha_composite(Image.new('RGBA', img.size, hex2rgb(C_BG)), img))
    BW.cv.delete('all'); BW.cv.config(width=img.width, height=img.height); BW.cv.create_image(0, 0, anchor='nw', image=BW.img)
    bx = CFG.get('bx', CFG['x']); by = CFG.get('by', CFG['y'] + SIZES.get(CFG['size'], SIZES['m'])[1] + 10)
    BW.win.geometry('%dx%d+%d+%d' % (img.width, img.height, bx, by)); BW.win.update_idletasks(); set_clickthrough(CFG['locked'], BW.win)
    if HIDDEN: BW.win.withdraw()
    HINT[:] = ['เปิดการ์ดบิ้วแล้ว', time.time() + 3]; _last['sig'] = None
def build_card_close():
    if BW.win: BW.win.destroy()
    BW.win = None; CFG.pop('build_id', None); save_cfg()
def build_from_clipboard():
    try: txt = root.clipboard_get()
    except Exception: txt = ''
    m = re.search(r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', txt or '', re.I)
    if not m:
        HINT[:] = ['ก๊อปลิงก์บิ้วจากเว็บก่อน', time.time() + 5]; _last['sig'] = None; return
    build_card_open(m.group(0).lower())

_note_until = [0]
def loop():
    show_note = time.time() < _note_until[0]
    draw(force=show_note)
    root.after(250, loop)

def server():
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(('127.0.0.1', PORT)); srv.listen(2)
    while True:
        c, _ = srv.accept()
        try:
            if c.recv(16) == b'quit': root.after(0, quit_app)
        finally: c.close()

def quit_app():
    save_cfg()
    try:
        if TRAY: TRAY.stop()
    except Exception: pass
    root.destroy(); os._exit(0)

def periodic_sync():
    resync(); _note_until[0] = time.time() + 6
    root.after(30 * 60 * 1000, periodic_sync)

threading.Thread(target=server, daemon=True).start()
apply_size(); root.update_idletasks(); root.deiconify(); root.lift(); set_clickthrough(CFG['locked'])
# โชว์ทันทีด้วยค่าที่จำไว้ แล้วซิงก์เวลา/โหลดรอบในเบื้องหลัง (ได้ผลภายในไม่กี่วินาที)
SYNC_NOTE = 'กำลังซิงก์…'; resync(); _note_until[0] = time.time() + 8
log('window at %s,%s size %s pil=%s' % (CFG['x'], CFG['y'], CFG['size'], HAS_PIL))
poll_hotkeys(); poll_calls(); loop();
if HAS_PIL: start_tray()
if HAS_PIL and CFG.get('build_id'): build_card_open(CFG['build_id'])
root.after(30 * 60 * 1000, periodic_sync)
try:                                       # แจ้งว่ามี OH Companion แล้ว (เลือกย้ายหรือไม่ก็ได้)
    import oc_notice
    oc_notice.check(root, 'OH-Vision Time Tracker', CFG_DIR, quit_app, lambda *a: log(' '.join(str(x) for x in a)))
except Exception as e:
    log('notice %r' % e)
root.mainloop()
