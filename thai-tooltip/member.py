# -*- coding: utf-8 -*-
"""OH Thai Tooltip — ระบบ Member: ล็อกอิน Discord ผ่านเว็บ hub แล้วโหลดคำแปลมือของ MrSmitety
- โปรแกรมไม่เห็นรหัสผ่าน: ผู้ใช้ล็อกอินในเบราว์เซอร์ หน้าเว็บส่ง refresh token กลับมาที่ 127.0.0.1 เท่านั้น
- ตรวจยศสดทุกครั้งที่เปิดโปรแกรม (ฝั่งเซิร์ฟเวอร์ใช้บอท Discord เช็ก) · ไม่มีเน็ตใช้ของเดิมได้ถึงเวลาที่เซิร์ฟเวอร์กำหนด
- token และคำแปลเก็บในเครื่องแบบเข้ารหัสผูกกับบัญชี Windows (DPAPI)"""
import os, sys, json, time, secrets, threading, webbrowser, urllib.request, urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import parse_qs

SUPA = 'https://ejletwoddaqdnjjqjwun.supabase.co'
KEY = 'sb_publishable_uLX_CLa1meE1FxNGOaYm7g_RnvZ83u6'      # publishable key (สาธารณะ)
LOGIN_PAGE = 'https://hub.mrsmitety.com/addons/thai-tooltip/login.html'
ORIGINS = ('https://hub.mrsmitety.com',)
IS_WIN = sys.platform == 'win32'

REASONS = {
    'login': 'ยังไม่ได้ล็อกอิน',
    'no_discord': 'บัญชีนี้ยังไม่ได้เชื่อม Discord',
    'not_in_server': 'ยังไม่ได้อยู่ในเซิร์ฟเวอร์ Discord ของช่อง',
    'no_role': 'ไม่พบยศ YouTube Member ใน Discord (ถ้าเพิ่งสมัคร รอ Discord ซิงก์สักครู่)',
    'not_configured': 'ระบบ Member ยังตั้งค่าไม่เสร็จ (แจ้งแอดมิน)',
    'bad_token': 'ระบบตรวจยศขัดข้อง (แจ้งแอดมิน)',
    'rate_limited': 'Discord ให้รอสักครู่ ลองใหม่อีกที',
    'too_often': 'เปิดโปรแกรมถี่เกินไป รอสักครู่แล้วลองใหม่',
    'session': 'ต้องล็อกอินใหม่',
}


# ───────── เข้ารหัสไฟล์ในเครื่อง (DPAPI: ถอดได้เฉพาะบัญชี Windows เดียวกัน) ─────────
if IS_WIN:
    import ctypes
    from ctypes import wintypes

    class _BLOB(ctypes.Structure):
        _fields_ = [('cbData', wintypes.DWORD), ('pbData', ctypes.POINTER(ctypes.c_char))]

    _ENT = b'OHThaiTooltip-member-v1'

    def _dp(data, protect):
        inb = _BLOB(len(data), ctypes.cast(ctypes.create_string_buffer(data, len(data)), ctypes.POINTER(ctypes.c_char)))
        ent = _BLOB(len(_ENT), ctypes.cast(ctypes.create_string_buffer(_ENT, len(_ENT)), ctypes.POINTER(ctypes.c_char)))
        out = _BLOB()
        fn = ctypes.windll.crypt32.CryptProtectData if protect else ctypes.windll.crypt32.CryptUnprotectData
        ok = fn(ctypes.byref(inb), None, ctypes.byref(ent), None, None, 0x1, ctypes.byref(out))
        if not ok:
            raise OSError('DPAPI failed')
        try:
            return ctypes.string_at(out.pbData, out.cbData)
        finally:
            ctypes.windll.kernel32.LocalFree(out.pbData)

    def seal(b): return _dp(b, True)
    def unseal(b): return _dp(b, False)
else:                                   # ใช้ทดสอบนอก Windows เท่านั้น
    def seal(b): return b'PLAIN' + b
    def unseal(b):
        if not b.startswith(b'PLAIN'):
            raise ValueError('bad blob')
        return b[5:]


class Member:
    def __init__(self, data_dir, version='0', log=print):
        self.dir = data_dir
        self.tok_path = os.path.join(data_dir, 'member.key')
        self.pack_path = os.path.join(data_dir, 'member_pack.bin')
        self.ua = {'User-Agent': f'OHThaiTooltip/{version}'}
        self.log = log
        self.status = {'ok': False, 'reason': 'login'}
        self.pack = None
        self.lock = threading.Lock()

    # ── ไฟล์ ──
    def _read(self, p):
        try:
            return json.loads(unseal(open(p, 'rb').read()).decode('utf-8'))
        except Exception:
            return None

    def _write(self, p, obj):
        tmp = p + '.tmp'
        open(tmp, 'wb').write(seal(json.dumps(obj, ensure_ascii=False).encode('utf-8')))
        os.replace(tmp, p)

    def has_login(self):
        return bool((self._read(self.tok_path) or {}).get('rt'))

    def logout(self):
        for p in (self.tok_path, self.pack_path):
            try:
                os.remove(p)
            except OSError:
                pass
        self.pack = None
        self.status = {'ok': False, 'reason': 'login'}

    # ── HTTP ──
    def _post(self, url, body, token=None):
        h = dict(self.ua, apikey=KEY, **{'Content-Type': 'application/json'})
        if token:
            h['Authorization'] = 'Bearer ' + token
        req = urllib.request.Request(url, data=json.dumps(body).encode('utf-8'), headers=h, method='POST')
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                return r.status, json.loads(r.read().decode('utf-8') or 'null')
        except urllib.error.HTTPError as e:
            try:
                return e.code, json.loads(e.read().decode('utf-8') or 'null')
            except Exception:
                return e.code, None

    # ── ล็อกอินผ่านเบราว์เซอร์ ──
    def login(self, timeout=300):
        """เปิดหน้า login.html แล้วรอให้หน้าเว็บส่ง refresh token กลับมาที่ 127.0.0.1 (คืน True ถ้าสำเร็จ)"""
        state = secrets.token_urlsafe(24).replace('-', 'a').replace('_', 'b')
        got = {}

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _page(self, code, msg):
                html = ('<!doctype html><meta charset="utf-8"><title>OH Thai Tooltip</title>'
                        '<body style="background:#0d1117;color:#e8ecf3;font:18px system-ui,sans-serif;display:grid;place-items:center;height:90vh">'
                        f'<div style="text-align:center">{msg}<p style="color:#9aa6b8;font-size:15px">ปิดหน้านี้แล้วกลับไปที่เกมได้เลย</p></div>')
                b = html.encode('utf-8')
                self.send_response(code); self.send_header('Content-Type', 'text/html; charset=utf-8')
                self.send_header('Content-Length', str(len(b))); self.end_headers(); self.wfile.write(b)

            def do_POST(self):
                if self.path != '/cb' or (self.headers.get('Origin') or '') not in ORIGINS:
                    return self._page(403, 'คำขอไม่ถูกต้อง')
                n = min(int(self.headers.get('Content-Length') or 0), 20000)
                f = {k: v[0] for k, v in parse_qs(self.rfile.read(n).decode('utf-8')).items()}
                if not secrets.compare_digest(f.get('state', ''), state) or not f.get('rt'):
                    return self._page(400, 'คำขอไม่ถูกต้อง')
                got.update(f)
                self._page(200, '✅ เชื่อมบัญชีกับ OH Thai Tooltip แล้ว')

            def do_GET(self):
                self._page(404, 'OH Thai Tooltip')

        srv = HTTPServer(('127.0.0.1', 0), H)
        srv.timeout = 1
        port = srv.server_address[1]
        webbrowser.open(f'{LOGIN_PAGE}#p={port}&s={state}')
        end = time.time() + timeout
        try:
            while not got and time.time() < end:
                srv.handle_request()
        finally:
            srv.server_close()
        if not got:
            return False
        self._write(self.tok_path, {'rt': got['rt'], 'name': got.get('name', '')})
        return True

    # ── ตรวจยศ + โหลดคำแปล ──
    def check(self):
        """คืน status dict: ok, reason, name, offline, changed"""
        with self.lock:
            cache = self._read(self.pack_path)
            tok = self._read(self.tok_path) or {}
            if not tok.get('rt'):
                self.status = {'ok': False, 'reason': 'login'}
                return self.status
            try:
                code, j = self._post(SUPA + '/auth/v1/token?grant_type=refresh_token', {'refresh_token': tok['rt']})
                if code in (400, 401) or (code == 200 and not (j or {}).get('access_token')):
                    self.log('member: session expired', code)
                    try:
                        os.remove(self.tok_path)
                    except OSError:
                        pass
                    self.status = {'ok': False, 'reason': 'session'}
                    return self.status
                if code != 200:
                    raise OSError('auth %s' % code)
                tok['rt'] = j['refresh_token']           # token หมุนทุกครั้ง ต้องเก็บตัวใหม่
                self._write(self.tok_path, tok)
                code, r = self._post(SUPA + '/rest/v1/rpc/tt_member_pack', {'p_have': (cache or {}).get('ver')}, j['access_token'])
                if code != 200 or not isinstance(r, dict):
                    raise OSError('pack %s' % code)
            except (OSError, ValueError) as e:              # เน็ตหลุด/เซิร์ฟเวอร์ล่ม: ใช้ของเดิมได้ถึงเวลาหมดอายุ
                self.log('member: offline', e)
                if cache and cache.get('until', 0) > time.time():
                    self.pack = cache
                    self.status = {'ok': True, 'reason': 'member', 'name': cache.get('name') or tok.get('name', ''), 'offline': True}
                else:
                    self.status = {'ok': False, 'reason': 'offline'}
                return self.status
            if not r.get('ok'):
                if r.get('reason') in ('no_role', 'not_in_server', 'no_discord'):
                    try:
                        os.remove(self.pack_path)                # หมดสิทธิ์ = ลบคำแปลมือออกจากเครื่อง
                    except OSError:
                        pass
                    self.pack = None
                self.status = {'ok': False, 'reason': r.get('reason', 'error')}
                return self.status
            changed = not r.get('same') or not cache
            if r.get('same') and cache:
                cache['until'] = r['until']
                pack = cache
            else:
                pack = {'ver': r['ver'], 'until': r['until'], 'tmpl': r.get('tmpl') or {}, 'terms': r.get('terms') or {},
                        'uid': r.get('uid'), 'name': r.get('name')}
            self._write(self.pack_path, pack)
            self.pack = pack
            self.status = {'ok': True, 'reason': 'member', 'name': r.get('name') or tok.get('name', ''), 'changed': changed}
            return self.status


def reason_text(s):
    if s.get('ok'):
        return 'Member: ' + (s.get('name') or '') + (' (ออฟไลน์)' if s.get('offline') else '')
    if s.get('reason') == 'offline':
        return 'เชื่อมต่อเซิร์ฟเวอร์ไม่ได้ และไม่มีข้อมูลที่ยังไม่หมดอายุ'
    return REASONS.get(s.get('reason'), 'ตรวจสิทธิ์ไม่ผ่าน (' + str(s.get('reason')) + ')')
