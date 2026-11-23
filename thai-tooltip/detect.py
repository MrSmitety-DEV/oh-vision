# -*- coding: utf-8 -*-
"""หากล่องรายละเอียดไอเทม (tooltip) จากภาพหน้าจอ
หลักการ: tooltip ของ Once Human มีแถบหัวสีตามระดับไอเทม (ทอง/ม่วง/ฟ้า/เขียว) กว้างเต็มกล่อง
ใต้แถบหัวคือเนื้อหาสีเทาเข้ม -> ใช้แถบหัวเป็นจุดยึด"""
import numpy as np

DEBUG = False
LAST_HEAD = 0
S = 4   # ย่อภาพ 4 เท่าก่อนหา (เร็ว)


def find_tooltip(img, cursor=None, ignore=None):
    """img: numpy HxWx3 (RGB) ทั้งจอ  คืน (x0,y0,x1,y1) ของกล่อง หรือ None"""
    H, W = img.shape[:2]
    a = img[::S, ::S, :3].astype(np.int16)
    mx = a.max(2); mn = a.min(2)
    m = (((mx - mn) > 28) & (mx > 55) & (mx < 245)) | ((mx > 110) & (mn < 235))
    if ignore:
        x0, y0, x1, y1 = [v // S for v in ignore]
        m[max(0, y0):y1, max(0, x0):x1] = False
    # ปิดรูเล็กๆ ที่ตัวหนังสือในแถบหัวทำให้ขาด
    k = 1
    pad = np.pad(m, ((0, 0), (k, k)))
    mm = np.zeros_like(m)
    for d in range(-k, k + 1):
        mm |= pad[:, k + d:k + d + m.shape[1]]
    # ขยายแนวตั้งอีกนิด กันแถวตัวหนังสือในแถบหัวทำให้ขาด
    mv = mm.copy()
    mv[1:] |= mm[:-1]; mv[:-1] |= mm[1:]
    mm = mv
    h, w = mm.shape
    minw = int(W * 0.13 / S); maxw = int(W * 0.40 / S)
    minh = max(6, int(H * 0.035 / S)); maxh = int(H * 0.16 / S)
    groups = []          # [y0, y1, xs, xe, rows]
    openg = []
    for y in range(h):
        row = mm[y]
        runs = []
        if row.sum() >= minw:
            d = np.diff(np.concatenate(([0], row.view(np.int8), [0])))
            st = np.where(d == 1)[0]; en = np.where(d == -1)[0]
            runs = [(a_, b_) for a_, b_ in zip(st, en) if b_ - a_ >= minw]
        nxt = []
        used = set()
        for g in openg:
            hit = None
            for j, (a_, b_) in enumerate(runs):
                if j in used:
                    continue
                ov = min(b_, g[3]) - max(a_, g[2])
                if ov >= 0.8 * min(b_ - a_, g[3] - g[2]):
                    hit = j; break
            if hit is None:
                g[5] += 1
                if g[5] > 4:          # ขาดเกิน 4 แถวติดกัน = จบกลุ่ม
                    groups.append(g)
                else:
                    nxt.append(g)
            else:
                used.add(hit); a_, b_ = runs[hit]
                g[1] = y + 1; g[4].append((a_, b_)); g[5] = 0; nxt.append(g)
        for j, (a_, b_) in enumerate(runs):
            if j not in used:
                nxt.append([y, y + 1, a_, b_, [(a_, b_)], 0])
        openg = nxt
    groups += openg
    best = []
    for y0, y1, _, _, rr, _m in groups:
        xs = int(np.median([r[0] for r in rr])); xe = int(np.median([r[1] for r in rr]))
        bw = xe - xs
        if DEBUG:
            print('grp', y0 * S, y1 * S, xs * S, xe * S, y1 - y0, bw)
        if minh <= (y1 - y0) <= maxh and minw <= bw <= maxw and dark_below(a, y1, xs + k, xe - k):
            best.append(((xs + k) * S, y0 * S, (xe - k) * S, y1 * S))
    best = [b for b in best if valid_panel(img, *b)]
    if not best:
        return None
    if cursor:
        best.sort(key=lambda b: abs((b[0] + b[2]) / 2 - cursor[0]) + abs(b[1] - cursor[1]) * 0.5)
    x0, y0, x1, y1 = best[0]
    x0, x1 = refine_x(img, x0, y1, x1, y0)
    global LAST_HEAD
    LAST_HEAD = y1
    return (x0, y0, x1, body_bottom(img, x0, y1, x1))


def body_bottom(img, x0, y_head, x1):
    """ไล่ลงจากใต้แถบหัว: แถวที่เป็นพื้นกล่อง = ส่วนใหญ่สีเข้ม (ตัวหนังสือมีแค่ส่วนน้อย)"""
    H = img.shape[0]
    a = img[y_head:H, x0 + 8:x1 - 8:4, :3].max(2)
    frac = (a < 100).mean(1)
    miss = 0; last = y_head
    for i, f in enumerate(frac):
        if f > 0.6:
            miss = 0; last = y_head + i
        else:
            miss += 1
            if miss > 30:
                break
    return min(H, last + 4)


def dark_below(a, y, x0, x1):
    """ใต้แถบหัวต้องเป็นพื้นกล่องสีเข้ม"""
    blk = a[y + 1:y + 8, x0:x1]
    if blk.size == 0:
        return False
    return float((blk.max(2) < 95).mean()) > 0.6


def valid_panel(img, x0, y0, x1, y1):
    """ตรวจละเอียดเต็มความละเอียด: แถบหัวสีเรียบ + ใต้หัวเป็นพื้นกล่องสีเข้มเรียบ (กันผนัง/ฉากในเกม)"""
    H = img.shape[0]
    if y1 + 50 > H:
        return False
    body = img[y1 + 6:y1 + 46:2, x0 + 10:x1 - 10:2, :3].astype(np.int16)
    head = img[y0 + 2:y1 - 2:2, x0 + 6:x1 - 6:2, :3].astype(np.int16)
    if body.size == 0 or head.size == 0:
        return False
    bl = body.mean(2); hl = head.mean(2)
    bm = float(np.median(bl)); hm = float(np.median(hl))
    smooth_body = float((np.abs(bl - bm) < 14).mean())
    # แถบหัวเป็นสีไล่เรียบ (ทอง/ม่วง/เงิน/รุ้ง): สีแทบไม่ต่างจากจุดข้างๆ ต่างจากผนัง/ฉากที่มีลาย
    smooth_head = float((np.abs(head[:, 2:] - head[:, :-2]).sum(2) < 30).mean())
    ok = bm < 75 and smooth_body > 0.7 and smooth_head > 0.62 and hm - bm > 25
    if DEBUG:
        print('valid', (x0, y0, x1, y1), round(bm), round(smooth_body, 2), round(smooth_head, 2), round(hm - bm), ok)
    return ok


def refine_x(img, x0, y1, x1, y0=None):
    """ขอบจริงของกล่อง: ไล่จากกลางแถบหัว (แถวบนสุด เหนือชื่อไอเทม ที่เป็นสีไล่เรียบๆ)
    ออกไปซ้าย/ขวา จนเจอจุดที่สีกระโดด = ขอบกล่อง (ช่องไอเทมข้างๆ ที่ติดกันจะถูกตัดออก)"""
    W = img.shape[1]
    if y0 is None:
        return x0, x1
    band = img[y0 + 3:y0 + 10, :, :3].astype(np.int16)
    if band.shape[0] < 3:
        return x0, x1
    row = np.median(band, 0)                       # (W,3)
    jump = np.abs(np.diff(row, axis=0)).sum(1)      # สีต่างจากคอลัมน์ข้างๆ
    cx = (x0 + x1) // 2
    w = x1 - x0
    nx0 = x0
    for x in range(cx, max(1, x0 - 12), -1):
        if jump[x - 1] > 45 or row[x - 1].max() < 45:
            nx0 = x; break
    nx1 = x1
    for x in range(cx, min(W - 1, x1 + 12)):
        if jump[x] > 45 or row[x + 1].max() < 45:
            nx1 = x + 1; break
    if nx1 - nx0 < w * 0.55:                        # ตัดแคบเกิน = เจอของในแถบหัว ใช้ค่าเดิม
        nx0, nx1 = x0, x1
    return calm_x(img, nx0, y1, nx1)


def calm_x(img, x0, y1, x1):
    """ชั้นที่ 2: ขอบต้องตรงกับพื้นกล่องสีเข้มเรียบใต้แถบหัว (กันช่องไอเทมสีรุ้งที่ติดแถบหัว)"""
    H = img.shape[0]
    rows = img[y1 + 6:min(H, y1 + 90), :, :3].astype(np.int16)
    if rows.shape[0] < 20:
        return x0, x1
    mx = rows.max(2)
    def calm(x):
        c = mx[:, x]
        return c.mean() < 75 and (c.max() - c.min()) < 70
    w = x1 - x0
    nx0 = x0
    for x in range(x0, x0 + w // 3):
        if all(calm(x + d) for d in range(0, 6, 2)):
            nx0 = x; break
    nx1 = x1
    for x in range(x1 - 1, x1 - w // 3, -1):
        if all(calm(x - d) for d in range(0, 6, 2)):
            nx1 = x + 1; break
    return nx0, nx1
