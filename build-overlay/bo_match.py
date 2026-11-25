# -*- coding: utf-8 -*-
"""OH Build Overlay – เทียบสิ่งที่อ่านได้จากหน้าจอกับบิ้วที่เลือก"""
import re, html
from rapidfuzz import fuzz
from bo_read import squash

ARMOR_KEYS = ['a0', 'a1', 'a2', 'a3', 'a4', 'a5']
ARMOR_TH = {'a0': 'หมวก', 'a1': 'หน้ากาก', 'a2': 'เสื้อ', 'a3': 'ถุงมือ', 'a4': 'กางเกง', 'a5': 'รองเท้า'}
ARMOR_SLOT = {'a0': 'Helmet', 'a1': 'Mask', 'a2': 'Top', 'a3': 'Gloves', 'a4': 'Bottoms', 'a5': 'Shoes'}


def plain(h):
    """ข้อความในบิ้วเป็น HTML เล็กๆ → ตัวหนังสือล้วน"""
    return html.unescape(re.sub(r'<[^>]+>', '', h or '')).strip()


def same(a, b, cut=88):
    a, b = squash(a), squash(b)
    if not a or not b:
        return False
    if a == b or fuzz.ratio(a, b) >= cut:
        return True
    # ชื่อยาวในแผงรายละเอียดเลื่อนวิ่ง (marquee) → อ่านได้ท่อนหลังต่อด้วยท่อนหน้า เช่น "etrayal Compound Bow - The"
    # เทียบกับชื่อที่ต่อกันสองรอบ: ถ้าเป็นท่อนหนึ่งของวงชื่อเดียวกัน (ยาวพอ) ถือว่าเป็นชิ้นเดียวกัน
    if len(a) >= 12 and len(b) >= 16 and len(a) <= len(b) + 4:
        bb = b + b
        if a in bb or fuzz.partial_ratio(a, bb) >= 93:
            return True
    return False


def style_same(a, b):
    a, b = squash(a), squash(b)
    a, b = (a[:-5] if a.endswith('style') else a), (b[:-5] if b.endswith('style') else b)
    return bool(a and b) and (a == b or fuzz.ratio(a, b) >= 85 or a.startswith(b) or b.startswith(a))


def suf_same(game, build):
    """Suffix ในเกม (<The Bull's Eye>) กับในบิ้ว (The Bull's Eye / Lunar Deviant Energy)"""
    g, b = squash(game), squash(build)
    if not g or not b:
        return False
    b2 = b.replace('deviantenergy', 'denergy')
    return g in (b, b2) or b.startswith(g) or g.startswith(b2) or fuzz.ratio(g, b) >= 85


class Build:
    def __init__(self, row, D):
        """row: แถวจาก creations_gallery {id,title,display_name,data}"""
        self.id = row.get('id'); self.title = row.get('title') or 'บิ้ว'; self.by = row.get('display_name') or ''
        self.D = D
        S = row.get('data') or {}
        self.S = S
        sl = S.get('slots') or {}; tx = S.get('text') or {}
        self.items = {}                 # key -> dict(label, need, icon, kind)
        for i in (0, 1):
            w = sl.get(f'w{i}')
            if w:
                self.items[f'w{i}'] = {'kind': 'weapon', 'name': w.get('name'), 'icon': w.get('icon'), 'label': f'ปืน {i + 1}'}
                cal = (S.get('calib') or {}).get(f'w{i}')
                styles = []
                if cal and cal.get('st'):
                    t = cal.get('t') or D['wtype'].get(w.get('name'), '')
                    styles = [D['calib']['types'].get(t, {}).get(sid, {}).get('name') for sid in cal['st']]
                    styles = [s for s in styles if s]
                else:
                    ct = plain(tx.get(f'w{i}.calib')).split(':')[0]
                    styles = [x.strip().title() for x in re.split(r'/|,', ct) if x.strip() and len(x.strip()) > 2]
                if styles:
                    self.items[f'w{i}c'] = {'kind': 'calib', 'styles': styles, 'ps': (cal or {}).get('ps') or [], 'q': (cal or {}).get('q') or 5,
                                            'text': plain(tx.get(f'w{i}.calib')), 'label': f'Calibration ปืน {i + 1}'}
            m = sl.get(f'w{i}m')
            if m:
                self.items[f'w{i}m'] = {'kind': 'mod', 'name': m.get('name'), 'suf': m.get('suf') or self._suf_text(tx.get(f'w{i}.title')),
                                        'icon': m.get('icon'), 'label': f'MOD ปืน {i + 1}'}
        for k in ARMOR_KEYS:
            a = sl.get(k)
            if a:
                self.items[k] = {'kind': 'armor', 'name': a.get('name'), 'icon': a.get('icon'), 'set': plain(tx.get(k + '.lb')) or a.get('name'),
                                 'label': ARMOR_TH[k]}
                hid = (S.get('hide') or {}).get(k)
                h = D['hides'].get(str(hid)) if hid else None
                if h:
                    s = h['s'].get(ARMOR_SLOT[k], {})
                    self.items[k + 'h'] = {'kind': 'hide', 'name': h['name'], 'icon': h['icon'], 'fam': h['fam'], 'th': s.get('th', ''), 'label': 'หนัง' + ARMOR_TH[k]}
            m = sl.get(k + 'm')
            if m:
                self.items[k + 'm'] = {'kind': 'mod', 'name': m.get('name'), 'suf': m.get('suf') or self._suf_text(tx.get(k + '.suf')),
                                       'icon': m.get('icon'), 'label': 'MOD ' + ARMOR_TH[k]}

        # ตัวเลือกสำรองจากโน้ตของบิ้ว: ชื่อเกราะ/Key Gear ที่พูดถึงในโน้ต นับว่าใส่ตรงบิ้วได้
        notes = ' '.join(plain(v) for v in tx.values())
        nq = squash(notes)
        SLOT2KEY = {v: k for k, v in ARMOR_SLOT.items()}
        self.kg = set(D.get('kg', [])) | set((D.get('kgalias') or {}).keys())
        self.alts = {}
        have = {squash(v['name']) for v in self.items.values() if v.get('name')}
        for nm, slot in (D.get('armor') or {}).items():
            q = squash(nm)
            if len(q) >= 6 and q in nq and q not in have and slot in SLOT2KEY:
                self.alts.setdefault(SLOT2KEY[slot], []).append(nm)
        # MOD สำรองจากโน้ต: ชื่อ MOD ที่พูดถึงในโน้ต → ช่องตามชนิด MOD (Weapon = ปืนทั้ง 2 กระบอก)
        self.mod_alts = {}
        for nm, slot in (D.get('modslot') or {}).items():
            q = squash(nm)
            if len(q) >= 6 and q in nq and q not in have:
                keys = ['w0m', 'w1m'] if slot == 'Weapon' else [SLOT2KEY[slot] + 'm'] if slot in SLOT2KEY else []
                for k in keys:
                    if k in self.items or k[:-1] in self.items:
                        self.mod_alts.setdefault(k, []).append(nm)
        # ชุดเซ็ตหลักของบิ้ว (ใช้ตอนเปลี่ยน Key Gear ไปช่องอื่น ช่องเดิมใส่ชิ้นเซ็ตแทนได้)
        cnt = {}
        for k in ARMOR_KEYS:
            if k in self.items and not self.is_kg(self.items[k]['name']):
                st_ = self.items[k].get('set') or ''
                cnt[st_] = cnt.get(st_, 0) + 1
        self.main_set = max(cnt, key=cnt.get) if cnt else ''

    def is_kg(self, name):
        return any(same(name, k, 92) for k in self.kg)

    @staticmethod
    def _suf_text(h):
        t = plain(h)
        m = re.search(r'<([^>]+)>', t)
        return (m.group(1) if m else t).strip()

    # ───── เทียบกับหน้าจอ ─────
    def weapon_key_of(self, name):
        for k in ('w0', 'w1'):
            if k in self.items and same(self.items[k]['name'], name):
                return k
        return None

    def armor_key_of(self, name):
        for k in ARMOR_KEYS:
            if k in self.items and same(self.items[k]['name'], name):
                return k
        return None

    def on_item(self, page, tab, it, equipped, status):
        """คืน (ข้อความแนะนำ, สี) และอัปเดต status {key: ('ok'|'bad', note)}"""
        if not it or not it.get('name'):
            return None
        nm = it['name']
        if page == 'weapons':
            slot = f'w{tab}' if tab in (0, 1) else None
            hit = self.weapon_key_of(nm)
            msgs = []; col = 'info'
            if equipped and hit:
                # ปืนช่อง 1/2 สลับกันได้ ไม่ถือว่าผิด: ปืนที่ใส่อยู่ตรงกับปืนไหนในบิ้วก็นับปืนนั้น
                status[hit] = ('ok', ''); col = 'ok'
                msgs.append(f'✓ {nm} ตรงบิ้ว' + (f' (ในบิ้วเป็นปืน {int(hit[1]) + 1} สลับช่องได้ไม่มีผล)' if slot and hit != slot else ''))
            elif equipped and slot:
                left = [k for k in ('w0', 'w1') if k in self.items and status.get(k, (None,))[0] != 'ok']
                want = ' หรือ '.join(self.items[k]['name'] for k in left) or '-'
                if len(left) == 1:
                    status[left[0]] = ('bad', f'ใส่ {nm} อยู่')
                col = 'bad'
                msgs.append(f'✗ {nm} ไม่ได้อยู่ในบิ้ว · บิ้วใช้ {want}')
            elif hit:
                msgs.append(f'★ ปืนนี้อยู่ในบิ้ว (ปืน {int(hit[1]) + 1}) · กด F ใส่ได้เลย'); col = 'hint'
            elif slot in self.items:
                msgs.append(f'บิ้วใช้ปืน {tab + 1}: {self.items[slot]["name"]}')
            ck = (hit + 'c') if hit else None
            if ck and ck in self.items and it.get('style'):
                want = self.items[ck]['styles']
                ok = any(style_same(it['style'], s) for s in want)
                if equipped:
                    status[ck] = ('ok', it['style']) if ok else ('bad', f'ใส่ {it["style"]} อยู่')
                msgs.append(('✓ Calibration ' + it['style']) if ok else ('✗ Calibration เป็น ' + it['style'] + ' · บิ้วใช้ ' + ' / '.join(want)))
                if not ok and col != 'bad':
                    col = 'warn'
            return ' · '.join(msgs), col
        if page == 'armor':
            from bo_read import ARMOR_TAB_TO_KEY
            slot = ARMOR_TAB_TO_KEY[tab] if tab is not None and 0 <= tab < 6 else None
            # ช่องของชิ้นที่ดูอยู่ดูจากชื่อชิ้น (ข้อมูลเกม) ก่อน แม่นกว่าแถบแท็บ ซึ่งอาจโดนแถบ overlay บัง
            ty = None
            for an, sl in (self.D.get('armor') or {}).items():
                if same(an, nm, 92):
                    ty = sl; break
            if ty:
                slot = {v: k for k, v in ARMOR_SLOT.items()}.get(ty, slot)
            hit = self.armor_key_of(nm)
            msgs = []; col = 'info'
            key = slot if (equipped and slot) else hit
            alt = slot and any(same(nm, x) for x in self.alts.get(slot, []))
            if equipped and slot and slot in self.items:
                if same(self.items[slot]['name'], nm):
                    status[slot] = ('ok', ''); msgs.append(f'✓ {ARMOR_TH[slot]}ตรงบิ้ว'); col = 'ok'
                elif alt:
                    status[slot] = ('ok', 'สำรอง: ' + nm); col = 'ok'
                    msgs.append(f'✓ {nm} = ตัวเลือกที่พูดถึงในโน้ตของบิ้ว')
                    if self.is_kg(nm):
                        # ใส่ Key Gear ได้ทีละชิ้น: Key Gear ตัวเดิมของบิ้ว (ช่องอื่น) ต้องถอด แล้วใส่ชิ้นเซ็ตหลักแทน
                        lost_set = self.main_set and squash(self.main_set) in squash(self.items[slot].get('set') or self.items[slot]['name'])
                        for k2 in ARMOR_KEYS:
                            if k2 != slot and k2 in self.items and self.is_kg(self.items[k2]['name']):
                                cur = status.get(k2, (None, ''))
                                if not (cur[0] == 'ok' and cur[1].startswith('สำรอง:')):
                                    status[k2] = ('need', f'ใส่ {self.set_piece(k2) or self.main_set.title()} แทน')
                                msgs.append(f'⚠ {ARMOR_TH[k2]}: ถอด {self.items[k2]["name"]} แล้วใส่ชิ้นเซ็ต {self.main_set.title()} แทน'
                                            + (f' (หมวกเดิมเป็นชิ้น {self.main_set.title()} เซ็ตจะได้ยังครบ)'.replace('หมวก', ARMOR_TH[slot]) if lost_set else ''))
                                col = 'hint'
                elif self.main_set and self.is_kg(self.items[slot]['name']) and squash(self.main_set) in squash(nm) and \
                        any(status.get(k2, (None, ''))[1].startswith('สำรอง:') and self.is_kg(status[k2][1][7:]) for k2 in ARMOR_KEYS):
                    status[slot] = ('ok', 'สำรอง: ' + nm); col = 'ok'
                    msgs.append(f'✓ ใส่ {nm} แทน {self.items[slot]["name"]} (ใช้ Key Gear ตัวในโน้ตอยู่ช่องอื่นแล้ว)')
                else:
                    status[slot] = ('bad', f'ใส่ {nm} อยู่'); col = 'bad'
                    extra = (' · หรือตามโน้ต: ' + ' / '.join(self.alts[slot])) if self.alts.get(slot) else ''
                    msgs.append(f'✗ {ARMOR_TH[slot]}ยังไม่ใช่ · บิ้วใช้ {self.items[slot]["name"]}' + extra)
            elif alt and not equipped:
                msgs.append(f'★ ชิ้นนี้เป็นตัวเลือกที่พูดถึงในโน้ตของบิ้ว · กด F ใส่ได้'); col = 'hint'
            elif hit:
                msgs.append(f'★ ชิ้นนี้อยู่ในบิ้ว ({ARMOR_TH[hit]}) · กด F ใส่ได้เลย'); col = 'hint'
            elif slot in (self.items or {}):
                msgs.append(f'บิ้วใช้{ARMOR_TH[slot]}: {self.items[slot]["name"]}')
            hk = (key + 'h') if key else None
            if hk and hk in self.items and (hit or equipped) and same(self.items[key]['name'], nm):
                want = self.items[hk]['name']; got = it.get('mat')
                if got:
                    ok = same(got, want, 90)
                    if equipped:
                        status[hk] = ('ok', got) if ok else ('bad', f'หนังเป็น {got}')
                    msgs.append(('✓ หนัง ' + got) if ok else (f'✗ หนังเป็น {got} · บิ้วใช้ {want}'))
                    if not ok and col != 'bad':
                        col = 'warn'
                else:
                    msgs.append(f'บิ้วใช้หนัง {want}')
            return ' · '.join(msgs), col
        return None

    def on_mod(self, mod, status):
        if not mod or not mod.get('name'):
            return None
        keys = [k for k, v in self.items.items() if v['kind'] == 'mod' and same(v['name'], mod['name'])]
        if not keys:
            alt = [k for k, L in self.mod_alts.items() if any(same(x, mod['name']) for x in L)]
            if alt:
                slot = (self.D.get('modslot') or {}).get(next((x for L in self.mod_alts.values() for x in L if same(x, mod['name'])), ''), '')
                done = []
                for k in alt:
                    if k not in self.items:
                        continue
                    if slot == 'Weapon' and status.get(k, (None,))[0] == 'ok' and not status[k][1].startswith('สำรอง:'):
                        continue                      # ปืนอีกกระบอกใส่ตัวหลักครบแล้ว ไม่ต้องทับ
                    want = self.items[k].get('suf')
                    if want and mod.get('suf') and not suf_same(mod['suf'], want):
                        status[k] = ('bad', f"สำรอง {mod['name']} แต่ Suffix เป็น {mod['suf']}")
                        return (f"✗ {mod['name']} เป็น MOD ในโน้ตของบิ้ว แต่ Suffix เป็น <{mod['suf']}> · ช่องนี้บิ้วใช้ <{want}>"), 'warn'
                    status[k] = ('ok', 'สำรอง: ' + mod['name'] + (f" <{mod['suf']}>" if mod.get('suf') else ''))
                    done.append(self.items[k]['label'])
                    if slot == 'Weapon':
                        break
                if done:
                    return (f"✓ {mod['name']}" + (f" <{mod['suf']}>" if mod.get('suf') else '') + f" = MOD ที่พูดถึงในโน้ตของบิ้ว ({', '.join(done)})"), 'ok'
            want = [f"{v['label']}: {v['name']}" for v in self.items.values() if v['kind'] == 'mod']
            return ('MOD ที่ใส่อยู่ (' + mod['name'] + ') ไม่ได้อยู่ในบิ้ว' + (' · บิ้วใช้ ' + ' / '.join(want[:3]) if want else '')), 'info'
        msgs = []; col = 'ok'
        for k in keys:
            v = self.items[k]
            if v.get('suf') and not mod.get('suf'):
                msgs.append(f"{v['label']}: MOD ถูก · ยังอ่าน Suffix ไม่เจอ (เลื่อนแผงขวาให้เห็นบรรทัด <...>)"); col = 'info'
                continue
            if not v.get('suf') or suf_same(mod['suf'], v['suf']):
                status[k] = ('ok', mod.get('suf') or ''); msgs.append(f"✓ {v['label']} ตรงบิ้ว" + (f" <{mod['suf']}>" if mod.get('suf') else ''))
            else:
                status[k] = ('bad', f"Suffix เป็น {mod['suf']}"); col = 'warn'
                msgs.append(f"✗ {v['label']}: MOD ถูก แต่ Suffix เป็น <{mod['suf']}> · บิ้วใช้ <{v['suf']}>")
        return ' · '.join(msgs), col

    def mod_rows(self, rows):
        """หัวแถว MOD ที่ตรงกับ MOD ในบิ้ว → คืนแถวพร้อมป้าย"""
        out = []
        for r in rows:
            for k, v in self.items.items():
                if v['kind'] == 'mod' and same(v['name'], r['t'], 82):
                    out.append((r, dict(v, _key=k))); break
        return out

    def on_blueprint(self, bp):
        if not bp or not bp.get('style'):
            return None
        D = self.D
        res = []
        for i in (0, 1):
            ck = f'w{i}c'; w = self.items.get(f'w{i}')
            if not w or ck not in self.items:
                continue
            c = self.items[ck]
            base = squash(re.split(r'\s+-\s+', w['name'])[0])
            ap = squash(bp.get('applies'))
            if ap and base and base not in ap:
                tname = D['calib']['typeName'].get(D['wtype'].get(w['name'], ''), '')
                if not tname or squash(tname.split('/')[0]).rstrip('s') not in ap:
                    continue
            if not any(style_same(bp['style'], s) for s in c['styles']):
                res.append((f"✗ ใบนี้ {bp['style']} · ปืน {i + 1} ({w['name']}) ใช้ " + ' / '.join(c['styles']), 'warn'))
                continue
            rank = None
            if bp.get('sub') and c['ps']:
                rank = c['ps'].index(bp['sub']['k']) + 1 if bp['sub']['k'] in c['ps'] else 0
            msg = f"✓ ใบ {bp['style']} ตรงบิ้ว ปืน {i + 1} ({w['name']})"
            if bp.get('sub'):
                s = bp['sub']; pct = 0 if s['hi'] <= s['lo'] else round((s['v'] - s['lo']) / (s['hi'] - s['lo']) * 100)
                nm = D['calib']['statName'][s['k']][0]
                if rank:
                    msg += f" · {nm} = ตัวเลือกอันดับ {rank}"
                elif c['ps']:
                    msg += f" · {nm} ไม่ใช่ตัวที่บิ้วหา"
                msg += f" ({s['v']}% · ได้ {pct}% ของช่วง)"
            if bp.get('wd'):
                wd = bp['wd']; p2 = 0 if wd['hi'] <= wd['lo'] else round((wd['v'] - wd['lo']) / (wd['hi'] - wd['lo']) * 100)
                msg += f" · Weapon DMG {wd['v']}% ({p2}% ของช่วง)"
            res.append((msg, 'ok' if rank in (None, 1) else ('hint' if rank else 'warn')))
        if not res:
            return (f"ใบ {bp['style']} ใช้กับปืนในบิ้วนี้ไม่ได้", 'info')
        best = sorted(res, key=lambda x: {'ok': 0, 'hint': 1, 'warn': 2}.get(x[1], 3))[0]
        return best

    def progress(self, status):
        keys = list(self.items)
        done = sum(1 for k in keys if status.get(k, (None,))[0] == 'ok')
        return done, len(keys)


    def pending_mods(self, status):
        """MOD ในบิ้วที่ยังไม่ได้ใส่ตรง พร้อมหมวด Keyword (เรียงปืนก่อน)"""
        out = []
        for k in ['w0m', 'w1m'] + [a + 'm' for a in ARMOR_KEYS]:
            v = self.items.get(k)
            if v and status.get(k, (None,))[0] != 'ok':
                kw = (self.D.get('modkw') or {}).get(v['name'], '')
                out.append((k, v, kw))
        return out


    def set_piece(self, key):
        """ชื่อชิ้นของเซ็ตหลักในช่องนั้น เช่น เซ็ต Bastille + หน้ากาก → Bastille Mask"""
        ms = squash(self.main_set)
        if not ms:
            return None
        for nm, (ic, st) in (self.D.get('armic') or {}).items():
            if ms in squash(st or nm) and (self.D.get('armor') or {}).get(nm) == ARMOR_SLOT.get(key):
                return nm
        return None

    def mod_keys_for_slot(self, slot):
        """ชนิด MOD (Weapon/Helmet/...) → key ช่อง MOD ในบิ้ว · None = ไม่รู้ช่อง (นำทางทุกช่อง)"""
        if not slot:
            return None
        if slot == 'Weapon':
            return {'w0m', 'w1m'}
        k = {v: k for k, v in ARMOR_SLOT.items()}.get(slot)
        return {k + 'm'} if k else None


def mod_slot_of(D, name):
    if not name:
        return None
    ms = D.get('modslot') or {}
    for n, sl in ms.items():
        if same(n, name):
            return sl
    return None
