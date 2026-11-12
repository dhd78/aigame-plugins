"""Minimal PvZ self-play demo through the bridge (no vision, no mouse).

Deck-agnostic policy:
  1. 先铺「产阳光」卡（向日葵/双子向日葵/阳光菇…），最多 6 株
  2. 再补「攻击」卡（任何豌豆系/投手系/大嘴花…），最多 10 株
  3. 卡冷却或钱不够就等

Usage: python pvz_agent_demo.py [seconds]
"""
from __future__ import annotations

import json
import sys
import time
import urllib.request

B = 'http://127.0.0.1:15580'

PRODUCERS = ('向日葵', '双子向日葵', '阳光菇')
SHOOTERS = ('豌豆射手', '双发射手', '寒冰射手', '机枪射手', '三线射手',
            '卷心菜投手', '玉米投手', '西瓜投手', '冰西瓜', '杨桃',
            '大喷菇', '忧郁菇', '大嘴花', '小喷菇')
BLOCKERS = ('坚果', '高坚果', '南瓜头')

MAX_PRODUCER = 6
MAX_SHOOTER = 10


def get(path):
    with urllib.request.urlopen(B + path, timeout=15) as r:
        return json.loads(r.read().decode('utf-8'))


def post(path, body):
    req = urllib.request.Request(B + path, data=json.dumps(body).encode('utf-8'),
                                 headers={'Content-Type': 'application/json'}, method='POST')
    try:
        with urllib.request.urlopen(req, timeout=40) as r:
            return r.status, json.loads(r.read().decode('utf-8'))
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode('utf-8'))


def occupied(state):
    return {(p['row'], p['col']) for p in state['plants']}


def count_names(state, names):
    return sum(1 for p in state['plants'] if p['name'] in names)


def free_cell(state, cols):
    occ = occupied(state)
    for c in cols:
        for r in range(5):
            if (r, c) not in occ:
                return r, c
    return None


def pick_card(state, names, limit, planted_count):
    if planted_count >= limit:
        return None
    for name in names:
        seed = next((x for x in state['seeds'] if x['name'] == name), None)
        if seed and seed['usable']:
            return seed
    return None


def main(seconds: float = 45.0):
    end = time.time() + seconds
    planted = 0
    last = ''
    while time.time() < end:
        try:
            s = get('/state')
        except Exception as e:
            print('state error:', e)
            time.sleep(1)
            continue
        if not s.get('in_level'):
            print('不在关卡（%r）' % s.get('ui'))
            time.sleep(3)
            continue

        n_prod = count_names(s, PRODUCERS)
        n_shoot = count_names(s, SHOOTERS)
        line = 'sun=%-4s wave=%-3s 产=%d 攻=%d 场上=%d' % (
            s.get('sun'), s.get('wave'), n_prod, n_shoot, len(s['plants']))
        if line != last:
            print(line)
            last = line

        # 产阳光：靠左两列
        card = pick_card(s, PRODUCERS, MAX_PRODUCER, n_prod)
        if card:
            cell = free_cell(s, (1, 0))
            if cell:
                code, res = post('/plant', {'row': cell[0], 'col': cell[1],
                                            'plant': card['name'], 'wait': 0})
                print('   %s @ %s -> %s 剩阳光=%s' % (
                    card['name'], cell, 'ok' if res.get('ok') else res.get('reason'), res.get('sun')))
                if res.get('ok'):
                    planted += 1
                time.sleep(0.25)
                continue

        # 攻击：中间列
        card = pick_card(s, SHOOTERS, MAX_SHOOTER, n_shoot)
        if card:
            cell = free_cell(s, (3, 2, 4))
            if cell:
                code, res = post('/plant', {'row': cell[0], 'col': cell[1],
                                            'plant': card['name'], 'wait': 0})
                print('   %s @ %s -> %s 剩阳光=%s' % (
                    card['name'], cell, 'ok' if res.get('ok') else res.get('reason'), res.get('sun')))
                if res.get('ok'):
                    planted += 1
                time.sleep(0.25)
                continue

        time.sleep(0.7)

    s = get('/state')
    print('\n=== 结束：种植 %d 次 | 阳光 %s | 波次 %s/%s | 植物 %d | 僵尸 %d ===' % (
        planted, s.get('sun'), s.get('wave'), s.get('total_waves') or '?',
        len(s['plants']), len(s['zombies'])))
    for name in PRODUCERS + SHOOTERS + BLOCKERS:
        n = count_names(s, (name,))
        if n:
            print('   %s x%d' % (name, n))
    return 0


if __name__ == '__main__':
    sys.exit(main(float(sys.argv[1]) if len(sys.argv) > 1 else 45.0))
