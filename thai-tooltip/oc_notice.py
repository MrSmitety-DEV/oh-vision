# -*- coding: utf-8 -*-
"""แจ้งผู้ใช้โปรแกรมแยก (OH-Vision / OH Thai Tooltip / OH Build Overlay) ว่าตอนนี้มี OH Companion แล้ว
ใช้ร่วมกันทั้ง 3 โปรแกรม: เช็คไฟล์ addons/oh-companion.json บนเว็บ hub แล้วเด้งหน้าต่างให้เลือก
  • โหลดและเปลี่ยนไปใช้เลย  → โหลด OH-Companion.exe ไว้โฟลเดอร์เดียวกัน ตรวจ SHA-256 เปิดขึ้นมา แล้วปิดตัวเดิม
  • ไว้ทีหลัง              → ถามใหม่ครั้งหน้าที่เปิด (เว้นอย่างน้อย 1 วัน)
  • ไม่ต้องแจ้งอีก          → ไม่ถามอีก
ไม่บังคับย้าย ใช้ตัวเดิมต่อได้ตามปกติ · สร้างโดย MrSmitety"""
import os, sys, json, time, threading, hashlib, subprocess, urllib.request, webbrowser, io

HUB = 'https://hub.mrsmitety.com'
DL_PREFIX = 'https://github.com/MrSmitety-DEV/oh-vision/releases/download/'   # โหลดได้จากที่นี่เท่านั้น
BG = '#0d1318'; CARD = '#151d25'; LINE = '#2a3644'; FG = '#e9eef2'; DIM = '#8a96a3'; TEAL = '#00dcd2'; BAD = '#ff7a45'
FONT = 'Leelawadee UI' if sys.platform == 'win32' else 'DejaVu Sans'
FROZEN = getattr(sys, 'frozen', False)


def _get(url, timeout=10):
    return urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'OH-addon-notice'}), timeout=timeout).read()


def check(root, app, data_dir, quit_fn, log=print, delay_ms=6000):
    """เรียกครั้งเดียวตอนโปรแกรมเปิด (ต้องเรียกจากเธรดหน้าต่าง) · quit_fn = ฟังก์ชันปิดโปรแกรมเดิม"""
    st_path = os.path.join(data_dir, 'companion_notice.json')
    try:
        st = json.load(open(st_path, encoding='utf-8'))
    except Exception:
        st = {}
    if st.get('never') or time.time() - st.get('later', 0) < 20 * 3600:
        return

    def save():
        try:
            os.makedirs(data_dir, exist_ok=True)
            json.dump(st, open(st_path, 'w', encoding='utf-8'))
        except Exception:
            pass

    def job():
        try:
            j = json.loads(_get(HUB + '/addons/oh-companion.json?t=%d' % time.time()).decode('utf-8'))
            if not j.get('url'):
                return
            logo = None
            try:
                logo = _get(HUB + '/addons/oh-companion.png', 8)
            except Exception:
                pass
            root.after(0, lambda: _Dialog(root, app, j, logo, st, save, quit_fn, log))
        except Exception as e:
            log('companion notice', e)

    root.after(delay_ms, lambda: threading.Thread(target=job, daemon=True).start())


class _Dialog:
    def __init__(self, root, app, j, logo, st, save, quit_fn, log):
        import tkinter as tk
        self.tk = tk; self.root = root; self.j = j; self.st = st; self.save = save; self.quit_fn = quit_fn; self.log = log
        self.busy = False
        d = self.d = tk.Toplevel(root); d.title('OH Companion'); d.configure(bg=BG); d.resizable(False, False)
        d.attributes('-topmost', True); d.protocol('WM_DELETE_WINDOW', self.later)
        self.img = None
        if logo:
            try:
                from PIL import Image, ImageTk
                self.img = ImageTk.PhotoImage(Image.open(io.BytesIO(logo)).convert('RGBA').resize((56, 56), Image.LANCZOS))
            except Exception:
                pass
        top = tk.Frame(d, bg=BG); top.pack(fill='x', padx=22, pady=(20, 8))
        if self.img:
            tk.Label(top, image=self.img, bg=BG).pack(side='left')
        tt = tk.Frame(top, bg=BG); tt.pack(side='left', padx=12)
        tk.Label(tt, text='ตอนนี้มี OH Companion แล้ว', bg=BG, fg=FG, font=(FONT, -20, 'bold')).pack(anchor='w')
        tk.Label(tt, text=f'เวอร์ชัน {j.get("ver", "")} · ฟรี · สร้างโดย MrSmitety', bg=BG, fg=DIM, font=(FONT, -13)).pack(anchor='w')
        box = tk.Frame(d, bg=CARD, highlightthickness=1, highlightbackground=LINE); box.pack(fill='x', padx=22, pady=6)
        lines = [
            f'{app} ที่ใช้อยู่ ถูกรวมเข้าไปใน OH Companion แล้ว พร้อมอีก 2 โปรแกรม:',
            '•  Vision Timer · Thai Tooltip · Build Overlay ในไฟล์เดียว',
            '•  ไอคอนในถาดอันเดียว เปิด/ปิดแต่ละส่วนได้จากหน้าหลัก',
            '•  มีเวอร์ชันใหม่ แจ้งเตือนพร้อมรายการเปลี่ยนแปลง กดอัปเดตในโปรแกรมได้เลย',
            f'•  การตั้งค่าเดิมของ {app} ใช้ต่อได้ทันที ไม่ต้องตั้งใหม่',
        ]
        for i, t in enumerate(lines):
            tk.Label(box, text=t, bg=CARD, fg=FG if i else TEAL, font=(FONT, -14, 'bold' if not i else 'normal'),
                     justify='left', anchor='w', wraplength=470).pack(fill='x', padx=14, pady=(10 if i == 0 else 1, 10 if i == len(lines) - 1 else 1))
        tk.Label(d, text=f'ไม่บังคับย้าย ถ้ายังอยากใช้ {app} ตัวเดิมก็ใช้ต่อได้ตามปกติ', bg=BG, fg=DIM,
                 font=(FONT, -12)).pack(anchor='w', padx=22)
        self.msg = tk.Label(d, text='', bg=BG, fg=DIM, font=(FONT, -13)); self.msg.pack(anchor='w', padx=22, pady=(6, 0))
        self.bar = tk.Canvas(d, width=480, height=8, bg=CARD, highlightthickness=0)
        bf = self.bf = tk.Frame(d, bg=BG); bf.pack(fill='x', padx=22, pady=(8, 20))
        self.b_go = tk.Button(bf, text='โหลดและเปลี่ยนไปใช้เลย', command=self.go, bg=TEAL, fg='#052322', relief='flat',
                              font=(FONT, -14, 'bold'), padx=14, pady=4, cursor='hand2', activebackground='#33e6de')
        self.b_go.pack(side='right')
        self.b_later = tk.Button(bf, text='ไว้ทีหลัง', command=self.later, bg=CARD, fg=FG, relief='flat', font=(FONT, -13),
                                 padx=12, pady=4, cursor='hand2', activebackground=LINE)
        self.b_later.pack(side='right', padx=6)
        self.b_never = tk.Button(bf, text='ไม่ต้องแจ้งอีก', command=self.never, bg=BG, fg=DIM, relief='flat', font=(FONT, -12),
                                 cursor='hand2', activebackground=BG, activeforeground=FG)
        self.b_never.pack(side='left')
        d.update_idletasks()
        sw, sh = d.winfo_screenwidth(), d.winfo_screenheight()
        d.geometry('+%d+%d' % ((sw - d.winfo_reqwidth()) // 2, (sh - d.winfo_reqheight()) // 3))
        d.lift(); d.focus_force()

    def later(self):
        if self.busy:
            return
        self.st['later'] = time.time(); self.save(); self.d.destroy()

    def never(self):
        self.st['never'] = True; self.save(); self.d.destroy()

    def prog(self, f, t):
        self.msg.config(text=t, fg=DIM)
        self.bar.delete('all'); self.bar.create_rectangle(0, 0, int(480 * max(0, min(1, f))), 8, fill=TEAL, outline='')

    def go(self):
        if self.busy:
            return
        url = self.j.get('url', '')
        if not (FROZEN and sys.platform == 'win32' and url.startswith(DL_PREFIX) and '..' not in url
                and len(self.j.get('sha256') or '') == 64):
            webbrowser.open(HUB + '/#oh-addons'); self.later(); return
        self.busy = True
        for b in (self.b_go, self.b_later, self.b_never):
            b.config(state='disabled')
        self.bar.pack(padx=22, pady=(4, 0), before=self.bf)
        self.prog(0, 'กำลังดาวน์โหลด OH Companion…')
        threading.Thread(target=self.download, args=(url,), daemon=True).start()

    def download(self, url):
        out = os.path.join(os.path.dirname(sys.executable), 'OH-Companion.exe')
        tmp = out + '.part'
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': 'OH-addon-notice'}), timeout=30)
            total = int(r.headers.get('Content-Length') or self.j.get('size') or 0)
            h = hashlib.sha256(); got = 0; last = 0
            with open(tmp, 'wb') as f:
                while True:
                    b = r.read(1 << 18)
                    if not b:
                        break
                    f.write(b); h.update(b); got += len(b)
                    if time.time() - last > 0.15:
                        last = time.time(); fr = got / total if total else 0
                        self.root.after(0, lambda fr=fr, got=got: self.prog(fr, f'กำลังดาวน์โหลด… {got / 1048576:.0f} / {total / 1048576:.0f} MB'))
            want = (self.j.get('sha256') or '').lower()
            if h.hexdigest() != want:
                os.remove(tmp); raise ValueError('ไฟล์ที่โหลดมาไม่ตรงกับต้นฉบับ ลองใหม่อีกครั้ง')
            os.replace(tmp, out)
            self.log('companion downloaded', out)
            self.root.after(0, lambda: self.prog(1, 'โหลดเสร็จ กำลังเปิด OH Companion…'))
            self.root.after(700, lambda: self.launch(out))
        except PermissionError:
            self.root.after(0, lambda: self.fail('โฟลเดอร์นี้ไม่ให้เขียนไฟล์ · โหลดจากหน้าเว็บแทน', True))
        except Exception as e:
            self.log('companion download', e)
            self.root.after(0, lambda e=e: self.fail(f'โหลดไม่สำเร็จ: {e}', False))

    def fail(self, t, web):
        self.busy = False
        self.msg.config(text=t, fg=BAD)
        for b in (self.b_go, self.b_later, self.b_never):
            b.config(state='normal')
        if web:
            self.b_go.config(text='เปิดหน้าดาวน์โหลด', command=lambda: (webbrowser.open(HUB + '/#oh-addons'), self.later()))

    def launch(self, path):
        try:
            subprocess.Popen([path], close_fds=True, creationflags=0x00000008, cwd=os.path.dirname(path))
        except Exception as e:
            self.fail(f'เปิด OH Companion ไม่ได้: {e}', False); return
        self.st['never'] = True; self.save()
        try:
            self.quit_fn()
        except Exception:
            os._exit(0)
