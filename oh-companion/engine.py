# -*- coding: utf-8 -*-
"""OH Thai Tooltip – ส่วนอ่าน/จับคู่/แปล (ไม่มี GUI ทดสอบบน Linux ได้)"""
import re, json
from rapidfuzz import process, fuzz

NUMRE = re.compile(r'\d+(?:[.,]\d+)*')

def squash(s):
    """ตัดช่องว่าง/เครื่องหมายที่ OCR ชอบเพี้ยน ใช้เทียบเท่านั้น"""
    s = s.lower().replace('’', "'").replace('–', '-').replace('—', '-')
    s = NUMRE.sub('#', s)
    return re.sub(r'[^a-z#%+\-\[\]]', '', s)


class DB:
    def __init__(self, path):
        d = json.load(open(path, encoding='utf-8'))
        self.tm = d['tmpl']                     # [[en_with_#, th_or_None], ...]
        self.terms = d['terms']                 # {"Crit Rate": "อัตราคริ", ...}
        self.keys = [squash(e) for e, _ in self.tm]
        self.tkeys = {squash(k): v for k, v in self.terms.items()}
        self.user = {}

    def apply_pairs(self, pairs):
        """คำแปลจากเว็บ (อังกฤษ -> ไทย) ทับของเดิม/เพิ่มใหม่ — ใช้ตอนอัปเดตข้อมูลอัตโนมัติ"""
        idx = {k: i for i, k in enumerate(self.keys)}
        tm = list(self.tm); keys = list(self.keys)
        for en, t in (pairs or {}).items():
            q = squash(en)
            if len(q) < 6:
                continue
            if q in idx:
                tm[idx[q]] = [tm[idx[q]][0], t]
            else:
                idx[q] = len(tm); tm.append([en, t]); keys.append(q)
        self.tm, self.keys = tm, keys                     # สลับทีเดียว (thread-safe พอสำหรับการอ่าน)

    def set_terms(self, terms):
        """คำ/หัวข้อแปลมือ (Member) ทับของเดิม"""
        if not terms:
            return
        t = dict(self.terms); t.update(terms)
        self.terms, self.tkeys = t, {squash(k): v for k, v in t.items()}

    def add_user(self, path):
        try:
            u = json.load(open(path, encoding='utf-8'))
            for e, t in u.items():
                self.user[squash(e)] = t
        except Exception:
            pass

    def term(self, text, loose=False):
        if re.search(r'\d', text):
            return None                                     # มีตัวเลข = ไม่ใช่ชื่อหัวข้อ/ค่า
        text = re.sub(r'\s+\S{1,2}$', '', text.strip()) if re.search(r'\s\S{1,2}$', text.strip()) and len(text.strip()) > 8 else text
        k = squash(text)
        if k in self.tkeys:
            return self.tkeys[k]
        if len(k) >= 7:
            r = process.extractOne(k, list(self.tkeys), scorer=fuzz.ratio, score_cutoff=88)
            if r:
                return self.tkeys[r[0]]
        if len(k) >= 6:                                   # คำถูกตัด เช่น 'Pollution R'
            c = [t for t in self.tkeys if t.startswith(k) and len(t) - len(k) <= 8]
            if len(c) == 1:
                return self.tkeys[c[0]]
        for wd in (sorted(re.findall(r'[A-Za-z]{6,}', text), key=len, reverse=True) if loose else []):   # ข้อความเลื่อน/ถูกตัด เช่น 'esist Pollutior'
            wq = wd.lower()[:-1]
            c = {t for t in self.tkeys if wq in t and len(t) <= len(wq) + 10}
            if len(c) == 1:
                return self.tkeys[c.pop()]
        return None

    def best(self, text):
        q = squash(text)
        if len(q) < 6:
            return None, 0
        r = process.extractOne(q, self.keys, scorer=fuzz.ratio, score_cutoff=80)
        if not r:
            return None, 0
        return r[2], r[1]


def lines_from_ocr(res):
    """รวมกล่อง OCR ที่อยู่แถวเดียวกันเป็นบรรทัด (เช่น 'Crit Rate' ... '5%')"""
    items = []
    for box, txt, sc in res or []:
        x0 = min(p[0] for p in box); x1 = max(p[0] for p in box)
        y0 = min(p[1] for p in box); y1 = max(p[1] for p in box)
        txt = re.sub(r'[^\x20-\x7e×℃°]', '', txt).strip()
        txt = re.sub(r'^[|lI]\s?(?=[A-Z][a-z])', '', txt).strip()   # แถบสีหน้าหัวข้อ เช่น |Basic Stats
        txt = re.sub(r'^[1-9]\s?(?=[A-Z][a-z]{2})', '', txt)   # เลขข้อ 1-4 ในกล่องเซ็ต
        if not re.search(r'[A-Za-z0-9]', txt):
            continue                                              # ดาว/ไอคอน
        items.append([x0, y0, x1, y1, txt])
    items.sort(key=lambda a: (a[1] + a[3]) / 2)
    rows = []
    for it in items:
        cy = (it[1] + it[3]) / 2; h = it[3] - it[1]
        if rows:
            r = rows[-1]
            rcy = (r['y0'] + r['y1']) / 2
            if abs(cy - rcy) < max(h, r['y1'] - r['y0']) * 0.45:
                r['parts'].append(it); r['y0'] = min(r['y0'], it[1]); r['y1'] = max(r['y1'], it[3])
                continue
        rows.append({'parts': [it], 'y0': it[1], 'y1': it[3]})
    out = []
    rows2 = []
    for r in rows:                                           # ชื่อม็อดยาวตัดบรรทัดกลาง <...>
        if rows2:
            prev = ' '.join(p[4] for p in sorted(rows2[-1]['parts'], key=lambda a: a[0]))
            if '<' in prev and '>' not in prev:
                rows2[-1]['parts'] += [[1e6 + p[0], p[1], 1e6 + p[2], p[3], p[4]] for p in r['parts']]
                rows2[-1]['y1'] = r['y1']; rows2[-1]['merged'] = True
                continue
        rows2.append(r)
    rows = rows2
    for r in rows:
        ps = sorted(r['parts'], key=lambda a: a[0])
        gap = len(ps) > 1 and (ps[1][0] - ps[0][2]) > 60 and not r.get('merged')   # ป้าย ... ค่า (คอลัมน์ห่างกัน)
        out.append({'x': ps[0][0], 'y0': r['y0'], 'y1': r['y1'],
                    'text': ' '.join(p[4] for p in ps), 'split': gap,
                    'label': ps[0][4], 'value': ' '.join(p[4] for p in ps[1:]), 'vals': [p[4] for p in ps[1:]],
                    'parts': [((p[0] + p[2]) / 2, p[4]) for p in ps]})
    return out


def fill(th, nums):
    def rep(m):
        i = int(m.group(1))
        return nums[i] if i < len(nums) else '?'
    return re.sub(r'\{(\d+)\}', rep, th)


def is_heading(db, lines, j):
    """บรรทัดนี้เป็นหัวข้อ/ชื่อค่าจริง หรือเป็นท้ายประโยคที่ตัดบรรทัดมา (เช่น '... of 42%' / 'Psi Intensity.')"""
    t = lines[j]['text'].strip()
    if len(t) > 30 or t.endswith('.') or not db.term(t):
        return False
    if j > 0:
        p = lines[j - 1]['text'].strip()
        if len(p) > 30 and not re.search(r'[.:!?)\]>]$', p):
            return False                                   # บรรทัดก่อนหน้ายังไม่จบประโยค
    return True


def translate_lines(db, lines, maxwin=9):
    """จับคู่บรรทัดต่อเนื่องกับประโยคในเกม คืน [(kind, thai, english)]
    kind: 'ok' แปลจากคลัง, 'term' ป้ายสั้น, 'raw' ไม่เจอ (ส่งต่อไปแปลเครื่อง)"""
    out = []; i = 0; n = len(lines)
    while i < n:
        L = lines[i]
        # ป้าย + ค่า เช่น Crit Rate | 5%
        t0 = L['text'].strip()
        if re.fullmatch(r'\d{1,2}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}', t0):
            out.append(('title', t0, t0)); i += 1; continue          # ระดับซัฟฟิกซ์ม็อด เช่น '14 Rhythm'
        if i + 1 < n and len(L.get('parts', [])) >= 2 and not re.search(r'\d', t0):
            N = lines[i + 1]
            nums = [p for p in N.get('parts', []) if re.fullmatch(r'[+\-]?[\d.,/]+%?', p[1].strip())]
            if len(nums) >= 2 and len(nums) == len(N.get('parts', [])):
                labs = []
                for xc, tx in L['parts']:
                    tl = db.term(tx) or db.term(re.sub(r'^\S{1,2}\s+', '', tx)) or db.term(tx, loose=True)
                    if tl:
                        labs.append((xc, tl))
                if labs:
                    cells = []
                    for xc, v in nums:                      # จับคู่ค่ากับชื่อที่อยู่ตรงกันในแนวตั้ง
                        lab = min(labs, key=lambda a: abs(a[0] - xc))
                        cells.append(f'{lab[1]} {v.strip()}')
                    out.append(('term', '   ·   '.join(cells), t0 + ' ' + N['text'])); i += 2; continue

        m = re.fullmatch(r'(.{3,30}?)\s*\[([^\[\]]{2,40})\]?', t0)
        if m and db.term(m.group(1)):
            out.append(('term', db.term(m.group(1)), m.group(1)))
            out.append(('title', '[' + m.group(2) + ']', t0)); i += 1; continue
        m = re.fullmatch(r'\[?([^\[\]]{2,40})\]', t0) or re.fullmatch(r'\[([^\[\]]{2,40})\]?', t0)
        if m and re.search(r'[A-Za-z]{2}', m.group(1)):
            out.append(('title', '[' + m.group(1) + ']', t0)); i += 1; continue
        if m:
            i += 1; continue                                  # เช่น [6/1874] กระสุน
        if not L['split'] and is_heading(db, lines, i):
            out.append(('term', db.term(t0), t0)); i += 1; continue
        if L['split'] or not re.search(r'[A-Za-z]{3}', L['text']):
            k = squash(L['label'])
            if db.term(L['label']):
                vs = []
                for p in L['vals']:
                    tp = db.term(p) or db.term(re.sub(r'^\S{1,3}\s+', '', p)) or db.term(p, loose=True)
                    if tp:
                        vs.append(tp)
                    elif re.fullmatch(r'[+\-]?[\d.,/]+%?', p.strip()):
                        vs.append(p.strip())
                out.append(('term', '   '.join([db.term(L['label'])] + vs), L['text']))
            else:
                out.append(('keep', L['text'], L['text']))
            i += 1; continue
        best = None
        txt = ''
        for j in range(i, min(n, i + maxwin)):
            if j > i and (lines[j]['split'] or is_heading(db, lines, j)
                          or re.fullmatch(r'\d{1,2}\s+[A-Z][a-z]+(?:\s+[A-Z][a-z]+){0,3}', lines[j]['text'].strip())
                          or re.fullmatch(r'\[?[^\[\]]{2,40}\]', lines[j]['text'].strip())):
                break
            if j > i and lines[j]['y0'] - lines[j - 1]['y1'] > (lines[j - 1]['y1'] - lines[j - 1]['y0']) * 1.6:
                break                                     # ช่องว่างใหญ่ = คนละย่อหน้า
            txt = (txt + ' ' + lines[j]['text']).strip()
            q = squash(txt)
            if q in db.user:
                best = (j, 101, None, txt); continue
            idx, sc = db.best(txt)
            if idx is not None and (best is None or sc >= best[1] - 1):
                best = (j, sc, idx, txt)
        if best and best[1] >= 86:
            j, sc, idx, txt = best
            nums = NUMRE.findall(txt)
            if idx is None:
                th = db.user[squash(txt)]
                out.append(('ok', th, txt))
            else:
                en, th = db.tm[idx]
                if th:
                    out.append(('ok', fill(th, nums), txt))
                else:
                    e2 = fill_en(en, nums)
                    st = stat_list(db, e2)
                    out.append(('ok', st, e2) if st else ('raw', None, e2))
            i = j + 1; continue
        k = squash(L['text'])
        m = re.match(r'^([A-Za-z ]{3,25}):\s*(.{4,})$', L['text'])
        sub = None
        if m:
            r = translate_lines(db, [dict(L, text=m.group(2), split=False)], maxwin=1)
            if r and r[0][0] == 'ok':
                sub = r[0][1]
            elif r:
                sub = stat_list(db, m.group(2))
        if sub:
            out.append(('ok', db.tkeys.get(squash(m.group(1)), m.group(1)) + ': ' + sub, L['text']))
        elif k in db.tkeys:
            out.append(('term', db.tkeys[k], L['text']))
        elif stat_list(db, L['text']):
            out.append(('ok', stat_list(db, L['text']), L['text']))
        elif not re.search(r'[a-z]{3}', L['text']) or len(L['text']) < 4:
            out.append(('keep', L['text'], L['text']))
        else:
            out.append(('raw', None, L['text']))
        i += 1
    # รวมบรรทัด raw ที่ติดกันเป็นย่อหน้าเดียว
    merged = []
    for k, th, en in out:
        if k == 'raw' and merged and merged[-1][0] == 'raw' and len(merged[-1][2]) > 32 \
                and not re.search(r'[.:!?)>]$', merged[-1][2]):
            merged[-1] = ('raw', None, merged[-1][2] + ' ' + en)
        else:
            merged.append((k, th, en))
    return merged


def fill_en(en, nums):
    it = iter(nums)
    return re.sub('#', lambda m: next(it, '#'), en)


STAT_PART = re.compile(r"^\s*(?:and\s+)?([A-Za-z][A-Za-z' ()/\-]*?)\s*([+\-−]\s?\d+(?:\.\d+)?%?|\d+(?:\.\d+)?%)(.*)$")


def stat_list(db, en):
    """'Crit Rate +5%, Weapon DMG +10%' -> แปลทีละคำจากคลังศัพท์"""
    parts = re.split(r'[,;]\s*', en.strip().rstrip('.'))
    out = []
    for p in parts:
        m = STAT_PART.match(p)
        if not m:
            return None
        k = squash(m.group(1))
        if k not in db.tkeys:
            return None
        rest = m.group(3).strip()
        if rest and not re.fullmatch(r'(for )?\d+s?', rest):
            return None
        out.append(f"{db.tkeys[k]} {m.group(2).replace(' ', '')}" + (f" {rest.replace('for ', 'นาน ')}" if rest else ''))
    return ' · '.join(out) if out else None
