# -*- coding: utf-8 -*-
"""OH Companion — เครื่องมือเสริม Once Human จากช่อง MrSmitety รวมไว้ในโปรแกรมเดียว
  • Vision Timer   นับถอยหลังช่วง Vision ⇄ ช่วงพัก (แสดงตลอด แม้ไม่ได้เปิดเกม)
  • Thai Tooltip   ชี้ไอเทมในเกมแล้วขึ้นคำแปลไทย (ทำงานเฉพาะตอนเกมอยู่หน้าจอ)
  • Build Overlay  เช็คของที่ใส่ในหน้า Gear เทียบกับบิ้วจากเว็บ (ทำงานเฉพาะตอนเกมอยู่หน้าจอ)
ทุกโมดูลอ่านจากภาพหน้าจออย่างเดียว: ไม่อ่านหน่วยความจำเกม ไม่แก้ไฟล์เกม ไม่ส่งปุ่มเข้าเกม
สร้างโดย MrSmitety · hub.mrsmitety.com"""
VERSION = '1.0.4'
APP = 'OH Companion'
PORT = 47618
HUB = 'https://hub.mrsmitety.com'
SB_URL = 'https://ejletwoddaqdnjjqjwun.supabase.co'
SB_KEY = 'sb_publishable_uLX_CLa1meE1FxNGOaYm7g_RnvZ83u6'      # คีย์สาธารณะ (anon) ของเว็บ hub

import os, sys, json, time, threading, queue, socket, traceback, urllib.request, webbrowser, hashlib, subprocess, shutil

IS_WIN = sys.platform == 'win32'
FROZEN = getattr(sys, 'frozen', False)
if sys.stdout is None:
    sys.stdout = open(os.devnull, 'w')
if sys.stderr is None:
    sys.stderr = open(os.devnull, 'w')
BASE = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE)
DATA = os.path.join(os.environ.get('APPDATA', os.path.expanduser('~')), 'OHCompanion')
os.makedirs(DATA, exist_ok=True)
LOG = os.path.join(DATA, 'OH Companion.log')


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
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass

import tkinter as tk
from PIL import Image, ImageTk
import oc_ctx

# ───────────── ตั้งค่า ─────────────
SET_PATH = os.path.join(DATA, 'settings.json')
DEFAULT = {'mods': {'vision': True, 'thai': True, 'build': True}, 'first': True, 'new_seen': False,
           'autostart': False, 'flags': {}, 'home_xy': None, 'home_on_start': False}


def load_set():
    s = json.loads(json.dumps(DEFAULT))
    try:
        d = json.load(open(SET_PATH, encoding='utf-8'))
        s.update({k: v for k, v in d.items() if k != 'mods'})
        s['mods'].update(d.get('mods', {}))
    except Exception:
        pass
    return s


SET = load_set()


def save_set():
    try:
        json.dump(SET, open(SET_PATH, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    except Exception:
        pass


# ───────────── โมดูล ─────────────
MODS = [
    {'key': 'vision', 'mod': 'mod_vision', 'name': 'Vision Timer', 'logo': 'vision_logo.png', 'color': '#aa82ff', 'old_port': 47615,
     'desc': 'นับถอยหลังช่วง Vision ⇄ ช่วงพัก ลอยบนจอตลอดเวลา แม้ยังไม่ได้เปิดเกม · มีการ์ดบิ้วไว้ดูระหว่างเล่น',
     'keys': 'Ctrl+Alt+V ซ่อน/แสดง · Ctrl+Alt+L ล็อกให้คลิกทะลุ · คลิกขวาที่การ์ด = เมนู'},
    {'key': 'thai', 'mod': 'mod_thai', 'name': 'Thai Tooltip', 'logo': 'thai_tooltip.png', 'color': '#ff3c8c', 'old_port': 47616,
     'desc': 'ชี้ปืน เกราะ ม็อดในเกม แล้วขึ้นคำแปลไทยข้างกล่องรายละเอียด · ทำงานเฉพาะตอนเกมอยู่หน้าจอ',
     'keys': 'Ctrl+Alt+T เปิด/ปิดการแปล'},
    {'key': 'build', 'mod': 'mod_build', 'name': 'Build Overlay', 'logo': 'build_overlay.png', 'color': '#3cd26e', 'old_port': 47617, 'new': True,
     'desc': 'เลือกบิ้วจากเว็บ hub แล้วโชว์แถบเช็คในหน้า Gear ชิ้นไหนใส่ตรงบิ้วขึ้น ✓ · ทำงานเฉพาะตอนเกมอยู่หน้าจอ',
     'keys': 'Ctrl+Alt+B ซ่อน/แสดงแถบ · คลิกชื่อ MOD = คัดลอกไปค้นในเกม'},
]
BYKEY = {m['key']: m for m in MODS}

BG = '#0d1318'; CARD = '#151d25'; LINE = '#2a3644'; FG = '#e9eef2'; DIM = '#8a96a3'; TEAL = '#00dcd2'
OKC = '#3ddc84'; BAD = '#ff7a45'; WARN = '#ffd54a'
FONT = 'Leelawadee UI' if IS_WIN else 'DejaVu Sans'
SCOL = {'ok': OKC, 'bad': BAD, 'warn': WARN, 'dim': DIM}


def flag(key):
    return (SET.get('flags') or {}).get(key, 'public')


def vtuple(v):
    try:
        return tuple(int(x) for x in str(v).split('.'))
    except Exception:
        return (0,)


# ───────────── เปิดพร้อม Windows ─────────────
RUN_KEY = r'Software\Microsoft\Windows\CurrentVersion\Run'


def set_autostart(on):
    if not (IS_WIN and FROZEN):
        return False
    try:
        import winreg
        k = winreg.OpenKey(winreg.HKEY_CURRENT_USER, RUN_KEY, 0, winreg.KEY_SET_VALUE)
        if on:
            winreg.SetValueEx(k, APP, 0, winreg.REG_SZ, f'"{sys.executable}" --tray')
        else:
            try:
                winreg.DeleteValue(k, APP)
            except FileNotFoundError:
                pass
        winreg.CloseKey(k)
        return True
    except Exception as e:
        log('autostart', e)
        return False


def make_shortcut():
    """สร้างทางลัด "OH Companion" บนเดสก์ท็อป (ชื่อมีช่องว่าง Windows จึงแสดงชื่อเต็มสองบรรทัด)"""
    if not (IS_WIN and FROZEN):
        return False
    ps = ("$d=[Environment]::GetFolderPath('Desktop');"
          "$s=(New-Object -ComObject WScript.Shell).CreateShortcut((Join-Path $d 'OH Companion.lnk'));"
          "$s.TargetPath=$env:OC_EXE;$s.WorkingDirectory=$env:OC_DIR;$s.IconLocation=$env:OC_EXE+',0';"
          "$s.Description='OH Companion by MrSmitety';$s.Save()")
    env = dict(os.environ, OC_EXE=sys.executable, OC_DIR=os.path.dirname(sys.executable))
    try:
        r = subprocess.run(['powershell', '-NoProfile', '-ExecutionPolicy', 'Bypass', '-Command', ps], env=env,
                           creationflags=0x08000000, timeout=20, capture_output=True)
        log('shortcut', r.returncode, r.stderr[-300:])
        return r.returncode == 0
    except Exception as e:
        log('shortcut', e)
        return False


# ───────────── ตัวควบคุมหลัก ─────────────
class Host:
    def __init__(self, root):
        self.root = root
        self.q = queue.Queue()
        self.ctl = {}          # key -> ตัวควบคุมโมดูลที่เริ่มแล้ว
        self.err = {}          # key -> ข้อความเมื่อเริ่มไม่ได้
        self.locks = {}        # จองพอร์ตของโปรแกรมตัวเดิม กันเปิดซ้อน
        self.tray = None
        self.home = None
        self.update = None     # {'ver', 'url'} เมื่อมีเวอร์ชันใหม่
        self.main_thread = threading.get_ident()
        self._toast_init()

    # ── เรียกได้จากทุกเธรด
    def call(self, fn):
        self.q.put(('call', fn))

    def toast(self, msg, ms=4000):
        if threading.get_ident() == self.main_thread:
            self._toast(msg, ms)
        else:
            self.q.put(('call', lambda: self._toast(msg, ms)))

    def refresh(self):
        self.q.put(('refresh', None))

    def show_home(self):
        self.q.put(('call', self._show_home))

    def quit(self):
        self.q.put(('call', self._quit))

    def set_enabled(self, key, on):
        if threading.get_ident() != self.main_thread:
            self.q.put(('call', lambda: self.set_enabled(key, on)))
            return
        m = BYKEY[key]
        if on and flag(key) == 'off':
            self.toast(f'{m["name"]} ปิดใช้งานชั่วคราวจากเว็บ hub'); return
        SET['mods'][key] = bool(on); save_set()
        if on and key not in self.ctl:
            self.start_mod(key)
        c = self.ctl.get(key)
        if c:
            c.set_enabled(bool(on))
        self._refresh()

    # ── ภายใน (เธรดหน้าต่าง)
    def _toast_init(self):
        w = self.toast_w = tk.Toplevel(self.root)
        w.overrideredirect(True); w.attributes('-topmost', True); w.withdraw()
        w.configure(bg=BG, highlightthickness=1, highlightbackground=TEAL)
        self.toast_l = tk.Label(w, bg=BG, fg=FG, font=(FONT, -15), padx=16, pady=10, justify='left')
        self.toast_l.pack()
        self.toast_job = None

    def _toast(self, msg, ms):
        w = self.toast_w
        self.toast_l.config(text=msg); w.update_idletasks()
        w.geometry(f'+{self.root.winfo_screenwidth() - w.winfo_reqwidth() - 24}+24')
        w.deiconify(); w.lift()
        clickthrough(w)
        if self.toast_job:
            self.root.after_cancel(self.toast_job)
        self.toast_job = self.root.after(ms, w.withdraw)

    def lock_port(self, key):
        """จองพอร์ตของโปรแกรมตัวเดิม: ถ้าจองไม่ได้ = ตัวเดิมยังเปิดอยู่"""
        if key in self.locks:
            return True
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.bind(('127.0.0.1', BYKEY[key]['old_port'])); s.listen(4)
            self.locks[key] = s
            if key == 'vision':           # ตัวเดิมเปิด → ส่ง quit มาหาเรา แล้วปิดตัวเอง: รับแล้วทิ้ง
                def eat():
                    while True:
                        try:
                            c, _ = s.accept(); c.close()
                        except Exception:
                            return
                threading.Thread(target=eat, daemon=True).start()
            return True
        except OSError:
            return False

    def start_mod(self, key):
        m = BYKEY[key]
        self.err.pop(key, None)
        try:
            if key == 'vision':
                import mod_vision as V
                for _ in range(15):            # mod_vision สั่งปิดตัวเดิมตอนโหลด รอให้ปล่อยพอร์ต
                    if self.lock_port(key):
                        break
                    time.sleep(0.1)
                V.start(self)

                class VC:
                    name = 'vision'
                    enabled = lambda s: V.ENABLED[0]
                    set_enabled = lambda s, on: V.set_enabled(on)
                    actions = lambda s: V.actions()
                    shutdown = lambda s: V.save_cfg()

                    def status(s):
                        if not V.ENABLED[0]:
                            return 'ปิดอยู่', 'dim'
                        try:
                            t = V.tip_text()
                        except Exception:
                            t = ''
                        return (t + (' · ซ่อนอยู่ (Ctrl+Alt+V)' if V.HIDDEN else ''), 'dim' if V.HIDDEN else 'ok')
                self.ctl[key] = VC()
            else:
                if not self.lock_port(key):
                    self.err[key] = (f'โปรแกรม OH {m["name"]} ตัวเดิมยังเปิดอยู่ · ปิดตัวเดิมก่อน '
                                     '(คลิกขวาไอคอนในถาด → ออก) แล้วกดสวิตช์ใหม่')
                    SET['mods'][key] = False; save_set()
                    return
                mod = __import__(m['mod'])
                self.ctl[key] = mod.start(self.root, self)
            log('started', key)
        except Exception:
            log('start', key, traceback.format_exc())
            self.err[key] = 'เปิดไม่สำเร็จ · ดูรายละเอียดใน log (หน้าเกี่ยวกับ → เปิดโฟลเดอร์ข้อมูล)'
            SET['mods'][key] = False; save_set()

    def _refresh(self):
        for k, c in self.ctl.items():          # ซิงก์กับปุ่มลัดของแต่ละโมดูล
            try:
                SET['mods'][k] = bool(c.enabled())
            except Exception:
                pass
        if self.home:
            self.home.update_cards()
        if self.tray:
            try:
                self.tray.update_menu()
            except Exception:
                pass

    def _show_home(self):
        if not self.home:
            self.home = Home(self)
        self.home.show()

    def _quit(self):
        for c in self.ctl.values():
            try:
                c.shutdown()
            except Exception:
                pass
        save_set()
        try:
            if self.tray:
                self.tray.stop()
        except Exception:
            pass
        try:
            self.root.destroy()
        finally:
            os._exit(0)

    def pump(self):
        try:
            for _ in range(200):
                k, v = self.q.get_nowait()
                try:
                    if k == 'call':
                        v()
                    elif k == 'refresh':
                        self._refresh()
                except Exception:
                    log('host', traceback.format_exc())
        except queue.Empty:
            pass
        self.root.after(40, self.pump)

    # ── ถาด
    def start_tray(self):
        try:
            import pystray
        except Exception as e:
            log('no pystray', e); return
        I, M = pystray.MenuItem, pystray.Menu

        def run(fn):
            return lambda icon, item: self.call(fn)

        def conv(acts):
            out = []
            for a in acts:
                if a is None:
                    out.append(M.SEPARATOR)
                elif isinstance(a[1], list):
                    out.append(I(a[0], M(*conv(a[1]))))
                else:
                    lab, fn, chk = a
                    out.append(I(lab, run(fn), checked=(lambda item, chk=chk: bool(chk())) if chk else None))
            return out

        def items():
            it = [I(f'{APP} v{VERSION}', None, enabled=False),
                  I('เปิดหน้าหลัก', run(self._show_home), default=True), M.SEPARATOR]
            for m in MODS:
                k = m['key']
                if flag(k) == 'off':
                    continue
                sub = [I('เปิดใช้งาน', run(lambda k=k: self.set_enabled(k, not SET['mods'].get(k))),
                         checked=lambda item, k=k: bool(SET['mods'].get(k)))]
                c = self.ctl.get(k)
                if c:
                    try:
                        sub += [M.SEPARATOR] + conv(c.actions())
                    except Exception:
                        log('menu', k, traceback.format_exc())
                it.append(I(m['name'] + ('  (ปิด)' if not SET['mods'].get(k) else ''), M(*sub)))
            it += [M.SEPARATOR,
                   I('เปิดเว็บ MrSmitety Hub', lambda i, t: webbrowser.open(HUB + '/#oh-addons')),
                   I('ออกจาก OH Companion', run(self._quit))]
            return it

        try:
            img = Image.open(os.path.join(BASE, 'oh_companion.png')).convert('RGBA').resize((64, 64), Image.LANCZOS)
            self.tray = pystray.Icon('ohcompanion', img, APP, M(items))
            self.tray.run_detached()
        except Exception:
            log('tray', traceback.format_exc())

        def tip():
            try:
                t = APP
                v = self.ctl.get('vision')
                if v and SET['mods'].get('vision'):
                    t += ' · ' + v.status()[0][:50]
                self.tray.title = t
            except Exception:
                pass
            self.root.after(5000, tip)
        tip()

    # ── ค่าจากเว็บ: เวอร์ชันใหม่ + สวิตช์ฟีเจอร์ (companion_flags)
    def web_check(self):
        def job():
            try:
                r = urllib.request.urlopen(urllib.request.Request(
                    HUB + '/addons/oh-companion.json?t=%d' % time.time(), headers={'User-Agent': f'OHCompanion/{VERSION}'}), timeout=10)
                j = json.loads(r.read().decode('utf-8'))
                if vtuple(j.get('ver')) > vtuple(VERSION):
                    first = self.update is None
                    self.update = j
                    self.call(self._refresh)
                    if first and SET.get('skip_ver') != j.get('ver'):
                        self.call(lambda: UpdateDialog(self, j))
            except Exception as e:
                log('update check', e)
            try:
                req = urllib.request.Request(SB_URL + '/rest/v1/app_settings?select=value&key=eq.companion_flags',
                                             headers={'apikey': SB_KEY, 'Authorization': 'Bearer ' + SB_KEY})
                rows = json.load(urllib.request.urlopen(req, timeout=10))
                fl = json.loads(rows[0]['value']) if rows and rows[0].get('value') else {}
                if isinstance(fl, dict) and fl != SET.get('flags'):
                    SET['flags'] = {k: str(v) for k, v in fl.items() if k in BYKEY}; save_set()

                    def apply():
                        for k in BYKEY:
                            if flag(k) == 'off' and k in self.ctl:
                                self.ctl[k].set_enabled(False)
                        self._refresh()
                    self.call(apply)
            except Exception as e:
                log('flags', e)
        threading.Thread(target=job, daemon=True).start()
        self.root.after(6 * 3600 * 1000, self.web_check)


def clickthrough(win):
    if not IS_WIN:
        return
    try:
        u = ctypes.windll.user32
        h = u.GetParent(win.winfo_id()) or win.winfo_id()
        u.SetWindowLongW(h, -20, u.GetWindowLongW(h, -20) | 0x80000 | 0x20 | 0x80 | 0x08000000)
    except Exception:
        pass


# ───────────── หน้าหลัก ─────────────
class Switch(tk.Canvas):
    def __init__(self, parent, color, command):
        super().__init__(parent, width=52, height=28, bg=CARD, highlightthickness=0, bd=0, cursor='hand2')
        self.color = color; self.on = False; self.command = command
        self.bind('<Button-1>', lambda e: self.command(not self.on))

    def set(self, on, enabled=True):
        self.on = on
        self.delete('all')
        c = (self.color if on else '#3a4654') if enabled else '#262f38'
        self.create_oval(2, 2, 26, 26, fill=c, outline=c); self.create_oval(26, 2, 50, 26, fill=c, outline=c)
        self.create_rectangle(14, 2, 38, 26, fill=c, outline=c)
        x = 38 if on else 14
        self.create_oval(x - 10, 4, x + 10, 24, fill='#ffffff' if enabled else '#5b6672', outline='')


class Home:
    def __init__(self, host):
        self.host = host
        root = host.root
        w = self.w = tk.Toplevel(root)
        w.title(APP); w.configure(bg=BG); w.resizable(False, False)
        try:
            w.iconbitmap(os.path.join(BASE, 'oh_companion.ico'))
        except Exception:
            pass
        w.protocol('WM_DELETE_WINDOW', self.close)
        w.bind('<Unmap>', self.on_unmap)          # กดย่อ (_) = ซ่อนไปที่ถาด ไม่ค้างใน Taskbar
        self.imgs = []
        pad = dict(padx=18)

        top = tk.Frame(w, bg=BG); top.pack(fill='x', pady=(16, 8), **pad)
        lg = self.logo('oh_companion.png', 48)
        if lg:
            tk.Label(top, image=lg, bg=BG).pack(side='left')
        tt = tk.Frame(top, bg=BG); tt.pack(side='left', padx=12)
        tk.Label(tt, text=APP, bg=BG, fg=FG, font=(FONT, -22, 'bold')).pack(anchor='w')
        tk.Label(tt, text=f'เครื่องมือเสริม Once Human · เวอร์ชัน {VERSION}', bg=BG, fg=DIM, font=(FONT, -13)).pack(anchor='w')

        self.upd = tk.Frame(w, bg='#2a2410', highlightthickness=1, highlightbackground=WARN)
        self.upd_l = tk.Label(self.upd, bg='#2a2410', fg=WARN, font=(FONT, -14), anchor='w')
        self.upd_l.pack(side='left', padx=10, pady=6)
        tk.Button(self.upd, text='ดูรายละเอียด / อัปเดต', command=lambda: self.host.update and UpdateDialog(self.host, self.host.update), bg=WARN, fg='#1a1400',
                  relief='flat', font=(FONT, -13, 'bold'), padx=10, cursor='hand2').pack(side='right', padx=8, pady=6)

        self.box = tk.Frame(w, bg=BG); self.box.pack(fill='x', **pad)
        self.cards = {}
        for m in MODS:
            self.cards[m['key']] = self.card(m)

        bot = tk.Frame(w, bg=BG); bot.pack(fill='x', pady=(6, 4), **pad)
        self.auto = tk.BooleanVar(value=bool(SET.get('autostart')))
        cb = tk.Checkbutton(bot, text='เปิด OH Companion พร้อม Windows', variable=self.auto, command=self.toggle_auto,
                            bg=BG, fg=FG, selectcolor=CARD, activebackground=BG, activeforeground=FG, font=(FONT, -13))
        cb.pack(side='left')
        tk.Button(bot, text='สร้างทางลัดบนเดสก์ท็อป', command=self.shortcut, bg=CARD, fg=FG, relief='flat', font=(FONT, -12),
                  padx=10, cursor='hand2', activebackground=LINE).pack(side='right')
        if not FROZEN:
            cb.config(state='disabled')
        self.hos = tk.BooleanVar(value=bool(SET.get('home_on_start')))
        tk.Checkbutton(w, text='เปิดหน้านี้ทุกครั้งที่เปิดโปรแกรม (ไม่ติ๊ก = เปิดแล้วไปอยู่ในถาดเลย)', variable=self.hos,
                       command=lambda: (SET.update(home_on_start=bool(self.hos.get())), save_set()),
                       bg=BG, fg=FG, selectcolor=CARD, activebackground=BG, activeforeground=FG,
                       font=(FONT, -13)).pack(anchor='w', **pad)
        tk.Label(w, text='ปิดหน้าต่างนี้ได้ โปรแกรมยังทำงานอยู่ที่ไอคอนในถาด (มุมขวาล่างของ Taskbar)', bg=BG, fg=DIM,
                 font=(FONT, -12)).pack(anchor='w', **pad)

        ft = tk.Frame(w, bg=BG); ft.pack(fill='x', pady=(8, 14), **pad)
        tk.Label(ft, text='สร้างโดย MrSmitety', bg=BG, fg=DIM, font=(FONT, -13)).pack(side='left')
        lk = tk.Label(ft, text='hub.mrsmitety.com', bg=BG, fg=TEAL, font=(FONT, -13, 'underline'), cursor='hand2')
        lk.pack(side='left', padx=8); lk.bind('<Button-1>', lambda e: webbrowser.open(HUB))
        tk.Button(ft, text='ออกจากโปรแกรม', command=host._quit, bg=CARD, fg=DIM, relief='flat', font=(FONT, -12),
                  padx=10, cursor='hand2', activebackground=LINE).pack(side='right')
        tk.Button(ft, text='ซ่อนไปที่ถาด', command=self.close, bg=TEAL, fg='#052322', relief='flat', font=(FONT, -12, 'bold'),
                  padx=10, cursor='hand2', activebackground='#33e6de').pack(side='right', padx=(6, 0))
        tk.Button(ft, text='เกี่ยวกับ', command=self.about, bg=CARD, fg=FG, relief='flat', font=(FONT, -12),
                  padx=10, cursor='hand2', activebackground=LINE).pack(side='right', padx=6)
        self.update_cards()

    def logo(self, fn, sz):
        try:
            im = ImageTk.PhotoImage(Image.open(os.path.join(BASE, fn)).convert('RGBA').resize((sz, sz), Image.LANCZOS))
            self.imgs.append(im); return im
        except Exception:
            return None

    def card(self, m):
        k = m['key']
        f = tk.Frame(self.box, bg=CARD, highlightthickness=1, highlightbackground=LINE)
        f.pack(fill='x', pady=5)
        lg = self.logo(m['logo'], 52)
        if lg:
            tk.Label(f, image=lg, bg=CARD).pack(side='left', padx=12, pady=12, anchor='n')
        mid = tk.Frame(f, bg=CARD); mid.pack(side='left', fill='both', expand=True, pady=10)
        hd = tk.Frame(mid, bg=CARD); hd.pack(anchor='w')
        tk.Label(hd, text=m['name'], bg=CARD, fg=FG, font=(FONT, -17, 'bold')).pack(side='left')
        badge = tk.Label(hd, text='', bg=CARD, fg='#052322', font=(FONT, -11, 'bold'), padx=7)
        tk.Label(mid, text=m['desc'], bg=CARD, fg=DIM, font=(FONT, -13), wraplength=330, justify='left').pack(anchor='w', pady=(2, 0))
        tk.Label(mid, text=m['keys'], bg=CARD, fg='#66727f', font=(FONT, -12), wraplength=330, justify='left').pack(anchor='w')
        stl = tk.Label(mid, text='', bg=CARD, fg=DIM, font=(FONT, -13), wraplength=330, justify='left')
        stl.pack(anchor='w', pady=(4, 0))
        right = tk.Frame(f, bg=CARD); right.pack(side='right', padx=12, pady=12, anchor='n')
        sw = Switch(right, m['color'], lambda on, k=k: self.host.set_enabled(k, on)); sw.pack(anchor='e')
        b1 = tk.Button(right, text='ตั้งค่า ▾', bg=LINE, fg=FG, relief='flat', font=(FONT, -12), padx=8, cursor='hand2',
                       activebackground='#36475a', activeforeground=FG)
        b1.config(command=lambda k=k, b=b1: self.menu(k, b))
        b1.pack(anchor='e', pady=(10, 0))
        b2 = None
        if k == 'build':
            b2 = tk.Button(right, text='เลือกบิ้ว', bg=m['color'], fg='#062012', relief='flat', font=(FONT, -12, 'bold'),
                           padx=8, cursor='hand2', command=lambda: self.pick())
            b2.pack(anchor='e', pady=(6, 0))
        return {'f': f, 'sw': sw, 'st': stl, 'badge': badge, 'b1': b1, 'b2': b2}

    def pick(self):
        if 'build' not in self.host.ctl:
            self.host.set_enabled('build', True)
        c = self.host.ctl.get('build')
        if c:
            c.pick()

    def menu(self, k, btn):
        c = self.host.ctl.get(k)
        mn = tk.Menu(self.w, tearoff=0, font=(FONT, -13))
        if not c:
            mn.add_command(label='เปิดสวิตช์ก่อนถึงจะตั้งค่าได้', state='disabled')
        else:
            def fill(menu, acts):
                for a in acts:
                    if a is None:
                        menu.add_separator()
                    elif isinstance(a[1], list):
                        sub = tk.Menu(menu, tearoff=0, font=(FONT, -13)); fill(sub, a[1]); menu.add_cascade(label=a[0], menu=sub)
                    else:
                        lab, fn, chk = a
                        on = bool(chk()) if chk else False
                        menu.add_command(label=('✓  ' if on else '     ') + lab if chk else '     ' + lab,
                                         command=lambda fn=fn: (fn(), self.host.refresh()))
            fill(mn, c.actions())
        mn.tk_popup(btn.winfo_rootx(), btn.winfo_rooty() + btn.winfo_height())

    def update_cards(self):
        h = self.host
        for m in MODS:
            k = m['key']; c = self.cards[k]
            if flag(k) == 'off':
                c['f'].pack_forget(); continue
            if not c['f'].winfo_manager():
                c['f'].pack(fill='x', pady=5)
            on = bool(SET['mods'].get(k))
            c['sw'].set(on)
            if k in h.err:
                txt, tone = h.err[k], 'bad'
            elif not on:
                txt, tone = 'ปิดอยู่ · กดสวิตช์เพื่อเปิด', 'dim'
            elif k in h.ctl:
                try:
                    txt, tone = h.ctl[k].status()
                except Exception:
                    txt, tone = '', 'dim'
            else:
                txt, tone = 'กำลังเปิด…', 'dim'
            c['st'].config(text=('● ' + txt) if txt else '', fg=SCOL.get(tone, DIM))
            fl = flag(k)
            if fl == 'beta':
                c['badge'].config(text='ทดลอง', bg=WARN); c['badge'].pack(side='left', padx=8)
            elif m.get('new') and not SET.get('new_seen'):
                c['badge'].config(text='ใหม่', bg=TEAL); c['badge'].pack(side='left', padx=8)
            else:
                c['badge'].pack_forget()
        if h.update:
            self.upd_l.config(text=f'มีเวอร์ชันใหม่ {h.update.get("ver")} (ตอนนี้ใช้ {VERSION})')
            if not self.upd.winfo_manager():
                self.upd.pack(fill='x', padx=18, pady=(0, 6), before=self.box)

    def tick(self):
        if self.w.winfo_viewable():
            self.update_cards()
            self.w.after(1000, self.tick)

    def show(self):
        w = self.w
        w.deiconify()
        xy = SET.get('home_xy')
        w.update_idletasks()
        sw, sh = w.winfo_screenwidth(), w.winfo_screenheight()
        if not xy or not (0 <= xy[0] < sw - 80 and 0 <= xy[1] < sh - 80):
            xy = [(sw - w.winfo_reqwidth()) // 2, max(20, (sh - w.winfo_reqheight()) // 2)]
        w.geometry('+%d+%d' % tuple(xy))
        w.lift(); w.focus_force()
        self.update_cards()
        w.after(1000, self.tick)

    def close(self):
        try:
            SET['home_xy'] = [self.w.winfo_x(), self.w.winfo_y()]
        except Exception:
            pass
        SET['new_seen'] = True; save_set()
        self.w.withdraw()
        if not SET.get('tray_tip_shown'):
            SET['tray_tip_shown'] = True; SET['first'] = False; save_set()
            self.host.toast('OH Companion ซ่อนไปที่ถาดแล้ว (มุมขวาล่าง ถ้าไม่เห็นดูในลูกศร ^)\nคลิกไอคอน OH เพื่อเปิดหน้านี้อีกครั้ง', 6000)

    def shortcut(self):
        if not FROZEN:
            self.host.toast('ใช้ได้เฉพาะตอนเปิดจากไฟล์ .exe'); return

        def job():
            ok = make_shortcut()
            self.host.toast('สร้างทางลัด "OH Companion" บนเดสก์ท็อปแล้ว\nไฟล์ .exe ตัวจริงย้ายไปเก็บที่อื่นได้ แต่ต้องสร้างทางลัดใหม่' if ok
                            else 'สร้างทางลัดไม่สำเร็จ · ลองคลิกขวาไฟล์ .exe → Show more options → Send to → Desktop', 7000)
        threading.Thread(target=job, daemon=True).start()

    def on_unmap(self, e):
        if e.widget is not self.w:
            return

        def chk():
            try:
                if self.w.state() == 'iconic':
                    self.close()
            except Exception:
                pass
        self.w.after(60, chk)

    def toggle_auto(self):
        on = bool(self.auto.get())
        if set_autostart(on):
            SET['autostart'] = on; save_set()
        else:
            self.auto.set(not on)

    def about(self):
        d = tk.Toplevel(self.w); d.title('เกี่ยวกับ ' + APP); d.configure(bg=BG); d.resizable(False, False)
        d.transient(self.w)
        d.geometry('+%d+%d' % (self.w.winfo_rootx() + 20, self.w.winfo_rooty() + 40))
        lg = self.logo('oh_companion.png', 72)
        if lg:
            tk.Label(d, image=lg, bg=BG).pack(pady=(18, 6))
        tk.Label(d, text=f'{APP}  v{VERSION}', bg=BG, fg=FG, font=(FONT, -20, 'bold')).pack()
        tk.Label(d, text='สร้างโดย MrSmitety', bg=BG, fg=TEAL, font=(FONT, -15, 'bold')).pack(pady=(2, 10))
        txt = ('รวม Vision Timer · Thai Tooltip · Build Overlay ไว้ในโปรแกรมเดียว\n'
               'ทุกส่วนอ่านจากภาพหน้าจออย่างเดียว ไม่แก้ไฟล์เกม ไม่อ่านหน่วยความจำ\n'
               'และไม่กดปุ่มแทนผู้เล่น · ทีมงานเกมเป็นผู้ตัดสินเรื่องโปรแกรมภายนอกเสมอ\n\n'
               'การตั้งค่าแต่ละส่วนเก็บไว้ที่ %APPDATA% (MrSmitetyVision, OHThaiTooltip,\n'
               'OHBuildOverlay, OHCompanion) · ใช้ค่าเดิมจากโปรแกรมตัวเดิมต่อได้เลย')
        tk.Label(d, text=txt, bg=BG, fg=DIM, font=(FONT, -13), justify='center').pack(padx=24)
        bf = tk.Frame(d, bg=BG); bf.pack(pady=16)
        for t, fn in (('เปิดเว็บ hub', lambda: webbrowser.open(HUB)),
                      ('แจ้งปัญหา / สอบถาม', lambda: webbrowser.open(HUB + '/#oh-addons')),
                      ('เปิดโฟลเดอร์ข้อมูล', lambda: os.startfile(DATA) if IS_WIN else None)):
            tk.Button(bf, text=t, command=fn, bg=CARD, fg=FG, relief='flat', font=(FONT, -12), padx=10,
                      cursor='hand2', activebackground=LINE).pack(side='left', padx=4)


# ───────────── อัปเดต ─────────────
def changes_since(j):
    """รายการเปลี่ยนแปลงทุกเวอร์ชันที่ใหม่กว่าตัวที่ใช้อยู่ (จาก oh-companion.json ช่อง changes)"""
    out = []
    for c in j.get('changes') or []:
        if vtuple(c.get('ver')) > vtuple(VERSION):
            out.append(c)
    out.sort(key=lambda c: vtuple(c.get('ver')), reverse=True)
    return out


class UpdateDialog:
    OPEN = None

    def __init__(self, host, j):
        if UpdateDialog.OPEN:
            try:
                UpdateDialog.OPEN.d.lift(); return
            except Exception:
                pass
        UpdateDialog.OPEN = self
        self.host = host; self.j = j; self.busy = False
        d = self.d = tk.Toplevel(host.root); d.title('อัปเดต ' + APP); d.configure(bg=BG); d.resizable(False, False)
        d.attributes('-topmost', True)
        try:
            d.iconbitmap(os.path.join(BASE, 'oh_companion.ico'))
        except Exception:
            pass
        d.protocol('WM_DELETE_WINDOW', self.later)
        self.img = None
        try:
            self.img = ImageTk.PhotoImage(Image.open(os.path.join(BASE, 'oh_companion.png')).convert('RGBA').resize((48, 48), Image.LANCZOS))
        except Exception:
            pass
        top = tk.Frame(d, bg=BG); top.pack(fill='x', padx=20, pady=(18, 8))
        if self.img:
            tk.Label(top, image=self.img, bg=BG).pack(side='left')
        tt = tk.Frame(top, bg=BG); tt.pack(side='left', padx=12)
        tk.Label(tt, text=f'มีเวอร์ชันใหม่ {j.get("ver")}', bg=BG, fg=FG, font=(FONT, -20, 'bold')).pack(anchor='w')
        mb = (j.get('size') or 0) / 1048576
        tk.Label(tt, text=f'ตอนนี้ใช้ {VERSION}' + (f' · ขนาดไฟล์ {mb:.0f} MB' if mb else ''), bg=BG, fg=DIM, font=(FONT, -13)).pack(anchor='w')

        box = tk.Frame(d, bg=CARD, highlightthickness=1, highlightbackground=LINE); box.pack(fill='both', padx=20, pady=4)
        t = tk.Text(box, bg=CARD, fg=FG, font=(FONT, -14), wrap='word', width=58, height=min(14, max(5, 2 + sum(1 + len(c.get('items') or []) for c in changes_since(j)))), relief='flat', bd=0,
                    padx=12, pady=10, cursor='arrow')
        t.tag_config('h', font=(FONT, -15, 'bold'), foreground=TEAL, spacing1=6, spacing3=4)
        t.tag_config('i', lmargin1=8, lmargin2=26, spacing3=3)
        tag = {'new': ('ใหม่', OKC), 'fix': ('แก้', WARN), 'change': ('ปรับ', '#8fb4ff')}
        for k, (lab, col) in tag.items():
            t.tag_config(k, foreground=col, font=(FONT, -13, 'bold'))
        ch = changes_since(j)
        if not ch:
            t.insert('end', 'ปรับปรุงและแก้ไขข้อผิดพลาดเล็กน้อย', 'i')
        for c in ch:
            t.insert('end', f'เวอร์ชัน {c.get("ver")}' + (f'  ·  {c["date"]}' if c.get('date') else '') + '\n', 'h')
            for it in c.get('items') or []:
                if isinstance(it, str):
                    kind, txt = 'change', it
                else:
                    kind, txt = it.get('type', 'change'), it.get('text', '')
                lab = tag.get(kind, tag['change'])[0]
                t.insert('end', '• ', 'i'); t.insert('end', f'[{lab}] ', kind); t.insert('end', txt + '\n', 'i')
        t.config(state='disabled')
        sb = tk.Scrollbar(box, command=t.yview); t.config(yscrollcommand=sb.set)
        t.pack(side='left', fill='both', expand=True)
        if len(ch) > 1 or sum(len(c.get('items') or []) for c in ch) > 9:
            sb.pack(side='right', fill='y')

        self.msg = tk.Label(d, text='', bg=BG, fg=DIM, font=(FONT, -13)); self.msg.pack(anchor='w', padx=20, pady=(8, 0))
        self.bar = tk.Canvas(d, width=500, height=8, bg=CARD, highlightthickness=0)
        bf = tk.Frame(d, bg=BG); bf.pack(fill='x', padx=20, pady=(8, 18))
        self.b_up = tk.Button(bf, text='อัปเดตเลย', command=self.go, bg=TEAL, fg='#052322', relief='flat',
                              font=(FONT, -14, 'bold'), padx=16, pady=4, cursor='hand2', activebackground='#33e6de')
        self.b_up.pack(side='right')
        self.b_later = tk.Button(bf, text='ไว้ทีหลัง', command=self.later, bg=CARD, fg=FG, relief='flat', font=(FONT, -13),
                                 padx=12, pady=4, cursor='hand2', activebackground=LINE)
        self.b_later.pack(side='right', padx=6)
        self.b_skip = tk.Button(bf, text='ข้ามเวอร์ชันนี้', command=self.skip, bg=BG, fg=DIM, relief='flat', font=(FONT, -12),
                                cursor='hand2', activebackground=BG, activeforeground=FG)
        self.b_skip.pack(side='left')
        d.update_idletasks()
        sw, sh = d.winfo_screenwidth(), d.winfo_screenheight()
        d.geometry('+%d+%d' % ((sw - d.winfo_reqwidth()) // 2, (sh - d.winfo_reqheight()) // 3))
        d.lift(); d.focus_force()

    def close(self):
        UpdateDialog.OPEN = None
        self.d.destroy()

    def later(self):
        if not self.busy:
            self.close()

    def skip(self):
        SET['skip_ver'] = self.j.get('ver'); save_set()
        self.host.toast(f'ข้ามเวอร์ชัน {self.j.get("ver")} แล้ว · อัปเดตได้ทุกเมื่อจากแถบในหน้าหลัก', 5000)
        self.close()

    def set_prog(self, f, text):
        self.msg.config(text=text)
        self.bar.delete('all')
        self.bar.create_rectangle(0, 0, int(500 * max(0, min(1, f))), 8, fill=TEAL, outline='')

    def go(self):
        if self.busy:
            return
        url = self.j.get('url') or ''
        if not (FROZEN and IS_WIN and url.startswith('https://')):
            webbrowser.open(HUB + '/#oh-addons'); self.close(); return
        self.busy = True
        for b in (self.b_up, self.b_later, self.b_skip):
            b.config(state='disabled')
        self.bar.pack(padx=20, pady=(4, 0), before=self.b_up.master)
        self.set_prog(0, 'กำลังดาวน์โหลด…')
        threading.Thread(target=self.download, args=(url,), daemon=True).start()

    def download(self, url):
        exe = sys.executable
        new = os.path.join(os.path.dirname(exe), 'OH-Companion.update.exe')
        try:
            req = urllib.request.Request(url, headers={'User-Agent': f'OHCompanion/{VERSION}'})
            r = urllib.request.urlopen(req, timeout=30)
            total = int(r.headers.get('Content-Length') or self.j.get('size') or 0)
            h = hashlib.sha256(); got = 0; last = 0
            with open(new, 'wb') as f:
                while True:
                    b = r.read(1 << 18)
                    if not b:
                        break
                    f.write(b); h.update(b); got += len(b)
                    if time.time() - last > 0.15:
                        last = time.time()
                        fr = got / total if total else 0
                        self.host.call(lambda fr=fr, got=got: self.set_prog(fr, f'กำลังดาวน์โหลด… {got / 1048576:.0f} / {total / 1048576:.0f} MB'))
            want = (self.j.get('sha256') or '').lower()
            if want and h.hexdigest() != want:
                os.remove(new)
                raise ValueError('ไฟล์ที่โหลดมาไม่ตรงกับต้นฉบับ (SHA-256) ลองใหม่อีกครั้ง')
            log('update downloaded', self.j.get('ver'))
            self.host.call(lambda: self.set_prog(1, 'โหลดเสร็จ กำลังเปิดเวอร์ชันใหม่…'))
            self.host.call(lambda: self.host.root.after(600, lambda: self.swap(new, exe)))
        except PermissionError:
            log('update perm', traceback.format_exc())
            self.host.call(lambda: self.fail('โฟลเดอร์ที่วางโปรแกรมไม่ให้เขียนไฟล์ · โหลดเวอร์ชันใหม่จากหน้าเว็บแทน', True))
        except Exception as e:
            log('update', traceback.format_exc())
            self.host.call(lambda e=e: self.fail(f'อัปเดตไม่สำเร็จ: {e}', False))

    def fail(self, text, web):
        self.busy = False
        self.msg.config(text=text, fg=BAD)
        for b in (self.b_up, self.b_later, self.b_skip):
            b.config(state='normal')
        if web:
            self.b_up.config(text='เปิดหน้าดาวน์โหลด', command=lambda: (webbrowser.open(HUB + '/#oh-addons'), self.close()))

    def swap(self, new, exe):
        """เปิดไฟล์ใหม่ในโหมด --finish-update: รอตัวนี้ปิด แล้วก๊อปตัวเองทับไฟล์เดิม เปิดไฟล์เดิมขึ้นมาใหม่"""
        try:
            subprocess.Popen([new, '--finish-update', exe, str(os.getpid())], close_fds=True,
                             creationflags=0x00000008 | 0x00000200)   # DETACHED_PROCESS | NEW_PROCESS_GROUP
        except Exception as e:
            log('swap', traceback.format_exc()); self.fail(f'เปิดเวอร์ชันใหม่ไม่ได้: {e}', True); return
        self.host._quit()


def finish_update(target, pid):
    """รันจากไฟล์ OH-Companion.update.exe: รอเวอร์ชันเก่าปิด → ก๊อปทับ → เปิดใหม่ → ไฟล์ใหม่จะลบตัว .update.exe ทิ้งเอง"""
    me = sys.executable
    log('finish update', me, '->', target)
    for _ in range(90):                      # ไฟล์เดิมยังถูกล็อกจนกว่าโปรแกรมเก่าปิดสนิท
        try:
            shutil.copyfile(me, target)
            break
        except Exception:
            time.sleep(0.5)
    else:
        log('finish update: copy failed, run from update file')
        subprocess.Popen([me], close_fds=True, creationflags=0x00000008); return
    subprocess.Popen([target, '--updated', me], close_fds=True, creationflags=0x00000008)


def cleanup_update(path):
    def job():
        for _ in range(40):
            try:
                if os.path.basename(path).lower() == 'oh-companion.update.exe' and os.path.exists(path):
                    os.remove(path)
                return
            except Exception:
                time.sleep(0.5)
    threading.Thread(target=job, daemon=True).start()


# ───────────── main ─────────────
def main():
    if '--finish-update' in sys.argv:
        i = sys.argv.index('--finish-update')
        finish_update(sys.argv[i + 1], sys.argv[i + 2] if len(sys.argv) > i + 2 else '')
        return
    if '--updated' in sys.argv:
        i = sys.argv.index('--updated')
        if len(sys.argv) > i + 1:
            cleanup_update(sys.argv[i + 1])
        for _ in range(20):                  # เวอร์ชันเก่าอาจยังปล่อยพอร์ตไม่ทัน
            try:
                t = socket.socket(); t.bind(('127.0.0.1', PORT)); t.close(); break
            except OSError:
                time.sleep(0.3)
    try:
        lock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        lock.bind(('127.0.0.1', PORT)); lock.listen(2)
    except OSError:
        try:                                    # เปิดอยู่แล้ว → ให้ตัวที่เปิดอยู่โชว์หน้าหลัก
            s = socket.create_connection(('127.0.0.1', PORT), timeout=1); s.sendall(b'show'); s.close()
        except OSError:
            pass
        return

    log('start', VERSION, sys.version.split()[0])
    root = tk.Tk(); root.withdraw()
    root.report_callback_exception = lambda et, ev, tb: log('callback', ''.join(traceback.format_exception(et, ev, tb)))
    host = Host(root)
    oc_ctx.MASTER = root; oc_ctx.HOST = host

    def listen():
        while True:
            try:
                c, _ = lock.accept()
                if c.recv(16) == b'show':
                    host.show_home()
                c.close()
            except Exception:
                time.sleep(0.5)
    threading.Thread(target=listen, daemon=True).start()

    root.after(40, host.pump)
    host.start_tray()
    tray_only = '--tray' in sys.argv or '--updated' in sys.argv
    if '--updated' in sys.argv:
        root.after(1500, lambda: host.toast(f'อัปเดต OH Companion เป็นเวอร์ชัน {VERSION} แล้ว', 6000))
    if SET.get('first') or (SET.get('home_on_start') and not tray_only):
        host._show_home()
        SET['first'] = False; save_set()
    else:
        host.toast('OH Companion ทำงานแล้ว · คลิกไอคอนในถาดเพื่อเปิดหน้าหลัก', 4000)

    def boot():                                 # เปิดทีละโมดูล (Vision ก่อน เพราะต้องโชว์ตลอด)
        for m in MODS:
            k = m['key']
            if SET['mods'].get(k) and flag(k) != 'off':
                host.set_enabled(k, True)
        host._refresh()
    root.after(150, boot)
    root.after(3000, host.web_check)
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
