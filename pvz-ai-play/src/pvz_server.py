"""PvZ1 bridge: read state + act, no vision, no mouse.

Actions use pvztools' **remote call** (executes the game's own functions inside
the process).  Verified working on 1.0.0.1051 for plant; shovel likewise.

Run:  python pvz_server.py [port]      default 15580

Coordinates in this API: **0-based** (rows 0..4, cols 0..8).
pvztools is 1-based internally; the bridge converts.

GET  /health
GET  /state
POST /plant  {"row":0,"col":2,"plant":"向日葵","wait":10}
POST /shovel {"row":0,"col":2}
"""
from __future__ import annotations

import ctypes
import ctypes.wintypes as wt
import json
import struct
import subprocess
import sys
import threading
import time
import traceback
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, List, Optional

# pvztools 依赖：优先用已安装的包；否则读环境变量 PVZTOOLS_VENDOR 指向的目录；
# 再否则读同目录下的 vendor/（便于开源分发时随包附带）。
import os

_vendor = os.environ.get('PVZTOOLS_VENDOR', '').strip()
if _vendor:
    sys.path.insert(0, _vendor)

try:
    import pvztools as pvz  # noqa: E402

except ImportError:
    _local = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'vendor')
    sys.path.insert(0, _local)
    import pvztools as pvz  # noqa: E402

_lock = threading.Lock()
_spin_lock = threading.Lock()
_game = None
_game_pid = None

# 阳光成本（按 PlantType id，标准 1.0.0.1051 数值）
PLANT_COST = {
    0: 100,   # 豌豆射手
    1: 50,    # 向日葵
    2: 150,   # 樱桃炸弹
    3: 50,    # 坚果
    4: 25,    # 土豆雷
    5: 175,   # 寒冰射手
    6: 150,   # 大嘴花
    7: 200,   # 双发射手
    8: 0,     # 小喷菇
    9: 25,    # 阳光菇
    10: 75,   # 大喷菇
    11: 75,   # 墓碑吞噬者
    12: 75,   # 魅惑菇
    13: 25,   # 胆小菇
    14: 75,   # 寒冰菇
    15: 125,  # 毁灭菇
    16: 25,   # 睡莲
    17: 50,   # 窝瓜
    18: 325,  # 三线射手
    19: 25,   # 缠绕水草
    20: 125,  # 火爆辣椒
    21: 100,  # 地刺
    22: 175,  # 火炬树桩
    23: 125,  # 高坚果
    24: 0,    # 海蘑菇
    25: 25,   # 路灯花
    26: 125,  # 仙人掌
    27: 100,  # 三叶草
    28: 125,  # 裂荚射手
    29: 125,  # 杨桃
    30: 125,  # 南瓜头
    31: 100,  # 磁力菇
    32: 100,  # 卷心菜投手
    33: 25,   # 花盆
    34: 100,  # 玉米投手
    35: 75,   # 咖啡豆
    36: 50,   # 大蒜
    37: 100,  # 叶子保护伞
    38: 50,   # 金盏花
    39: 300,  # 西瓜投手
    40: 250,  # 机枪射手
    41: 150,  # 双子向日葵
    42: 150,  # 忧郁菇
    43: 225,  # 香蒲
    44: 200,  # 冰西瓜
    45: 50,   # 吸金磁
    46: 125,  # 地刺王
    47: 500,  # 玉米加农炮
    48: 0,    # 模仿者
}

# 卡片冷却（毫秒）。游戏里 cd_total 在卡片「第一次使用」前是 0，
# 所以这里按 PlantType 给一张标准表兜底；用过一次后游戏会给出真实值。
LONG_50S = (2, 14, 15, 20, 40, 41, 42, 43, 44, 47)      # 樱桃/寒冰菇/毁灭菇/辣椒/机枪/双子葵/忧郁菇/香蒲/冰西瓜/加农炮
MID_30S = (3, 4, 12, 17, 19, 23, 25, 27, 30, 45, 46)    # 坚果/土豆雷/魅惑菇/窝瓜/水草/高坚果/路灯/三叶草/南瓜/吸金磁/地刺王
PLANT_CD_MS = {}
for _t in range(49):
    PLANT_CD_MS[_t] = 7500
for _t in LONG_50S:
    PLANT_CD_MS[_t] = 50000
for _t in MID_30S:
    PLANT_CD_MS[_t] = 30000

# 本地冷却账本：slot -> ready_at(monotonic)
_seed_ready_at: Dict[int, float] = {}


# 结算/主菜单 的候选点击点（进关卡/继续），实测校准后收紧
# 卡槽不满时用来补齐的默认卡（按优先级，跳过已选的）
DEFAULT_DECK_FILL = ('向日葵', '豌豆射手', '坚果', '寒冰射手', '土豆雷', '小喷菇',
                     '双发射手', '大嘴花', '樱桃炸弹', '窝瓜', '三线射手', '南瓜头')

AWARD_CLICK_CANDIDATES = ([(x, y) for y in (500, 530, 555, 575) for x in range(240, 700, 55)])
MENU_CLICK_CANDIDATES = [(200, 300), (150, 340), (250, 340), (180, 260)]

_pid_cache = {'pid': None, 'ts': 0.0}
PID_CACHE_TTL = 3.0


def _query_pid() -> Optional[int]:
    out = subprocess.run(['tasklist', '/FI', 'IMAGENAME eq PlantsVsZombies.exe', '/FO', 'CSV'],
                         capture_output=True, text=True, encoding='gbk', errors='replace').stdout
    for line in out.splitlines():
        parts = [p.strip('"') for p in line.split('","')]
        if len(parts) >= 2 and parts[0].lower().startswith('plantsvszombies'):
            return int(parts[1])
    return None


def current_pid() -> Optional[int]:
    """查进程很慢（tasklist 约 1.5s），缓存 3 秒。"""
    now = time.monotonic()
    if _pid_cache['pid'] is not None and now - _pid_cache['ts'] < PID_CACHE_TTL:
        return _pid_cache['pid']
    pid = _query_pid()
    _pid_cache['pid'] = pid
    _pid_cache['ts'] = now
    return pid


def invalidate_pid_cache() -> None:
    _pid_cache['ts'] = 0.0


def get_game():
    global _game, _game_pid
    pid = current_pid()
    if pid is None:
        raise RuntimeError('PlantsVsZombies.exe 未运行')
    if _game is None or _game_pid != pid:
        _game = pvz.attach(pid=pid, write=True, remote=True, input=True)
        _game_pid = pid
    return _game


def chooser_picked_count() -> int:
    """选卡界面已选数量：*(app+0x774) + 0xD24。"""
    try:
        app = _u32(0x6A9EC0)
        ch = _u32(app + 0x774)
        if not ch:
            return -1
        return int.from_bytes(_read(ch + 0xD24, 4), 'little', signed=True)
    except Exception:
        return -1


def ui_now(g) -> int:
    """当前 game_ui（1 主菜单 / 2 选卡 / 3 关卡 / 5 结算）。"""
    try:
        return int(g.ui)
    except Exception:
        return -1


def name_of(obj: Any) -> str:
    for attr in ('name', 'cn_name', 'text'):
        try:
            v = getattr(obj, attr)
            if isinstance(v, str) and v:
                return v
        except Exception:
            pass
    return str(obj)


def safe_attr(obj: Any, attr: str) -> Any:
    try:
        return getattr(obj, attr)
    except Exception:
        return None


# 同一株植物的不同叫法（pvztools 用「荷叶」，玩家常说「睡莲」）
PLANT_ALIASES = {
    '睡莲': '荷叶', '荷叶': '睡莲',
    '缠绕水草': '缠绕海草', '缠绕海草': '缠绕水草',
    '海蘑菇': '小海菇', '小海菇': '海蘑菇',
}


def find_seed(g, plant: Any) -> Optional[Dict[str, Any]]:
    want = str(plant).strip()
    want_alt = PLANT_ALIASES.get(want)
    for s in (g.seeds or []):
        try:
            nm = name_of(s)
            if nm == want or str(int(s.type)) == want or (want_alt and nm == want_alt):
                return {'slot': s.slot, 'type': int(s.type), 'name': name_of(s),
                        'usable': bool(s.usable), 'cd_elapsed': s.cd_elapsed,
                        'cd_total': s.cd_total}
        except Exception:
            continue
    return None


def cooldown_left_ms(slot: int) -> int:
    """Remaining local cooldown for a seed slot, in ms (0 = ready)."""
    ready = _seed_ready_at.get(int(slot))
    if not ready:
        return 0
    left = ready - time.monotonic()
    return max(0, int(left * 1000))


def seed_view(seed: Dict[str, Any], sun: Optional[int]) -> Dict[str, Any]:
    """Enrich a seed with the economy state the bridge enforces."""
    left = cooldown_left_ms(seed['slot'])
    cost = PLANT_COST.get(int(seed['type']), 0)
    affordable = sun is None or int(sun) >= cost
    return {'slot': seed['slot'], 'type': seed['type'], 'name': seed['name'],
            'cost': cost,
            'game_usable': seed['usable'],
            'cooldown_left_ms': left,
            'affordable': affordable,
            'usable': bool(seed['usable']) and left == 0 and affordable}


def plant_list(g) -> List[Dict[str, Any]]:
    return [{'row': int(p.row), 'col': int(p.col), 'type': int(p.type),
             'name': name_of(p), 'hp': safe_attr(p, 'hp'),
             'index': safe_attr(p, 'index')} for p in g.plants]


def state_dict() -> Dict[str, Any]:
    g = get_game()
    out: Dict[str, Any] = {'ok': True, 'pid': _game_pid, 'version': safe_attr(g, 'version')}
    try:
        out['in_level'] = bool(g.in_level)
        out['ui'] = g.ui_name
    except Exception as e:
        out.update(ok=False, error='%s: %s' % (type(e).__name__, e))
        return out
    if not out['in_level']:
        return out

    try:
        if ui_now(g) == 2:
            out['chooser_picked'] = chooser_picked_count()
    except Exception:
        pass
    out['sun'] = safe_attr(g, 'sun')
    out['wave'] = safe_attr(g, 'wave')
    out['paused'] = safe_attr(g, 'paused')

    seeds = []
    for s in (g.seeds or []):
        try:
            base = {'slot': s.slot, 'type': int(s.type), 'name': name_of(s),
                    'usable': bool(s.usable), 'cd_elapsed': s.cd_elapsed,
                    'cd_total': s.cd_total}
            seeds.append(seed_view(base, out.get('sun')))
        except Exception:
            pass
    out['seeds'] = seeds
    try:
        out['conveyor'] = conveyor_active()
        if out['conveyor']:
            # 传送带关卡没有阳光经济：能否种只看"带子上有没有这张卡"
            for sd in out['seeds']:
                sd['cost'] = 0
                sd['affordable'] = True
                sd['cooldown_left_ms'] = 0
                sd['game_usable'] = int(sd.get('type', -1)) >= 0
                sd['usable'] = int(sd.get('type', -1)) >= 0
                sd['on_belt'] = int(sd.get('type', -1)) >= 0
        out['belt'] = read_belt() if out['conveyor'] else []
        out['belt_ready'] = sorted({b['name'] for b in out['belt']})
    except Exception:
        out['conveyor'] = False
        out['belt'] = []
    try:
        out['plants'] = plant_list(g)
    except Exception:
        out['plants'] = []
    try:
        out['grid_items'] = read_grid_items()
        out['blocked'] = [[it['row'], it['col']] for it in out['grid_items'] if it['blocking']]
    except Exception:
        out['grid_items'] = []
        out['blocked'] = []
    # 池塘关信息：水面格子 + 已有睡莲的格子
    try:
        _scene = board_scene()
        out['scene'] = _scene
        out['is_pool'] = _scene in POOL_SCENES
        out['water'] = water_cells()
        out['lily'] = [[p['row'], p['col']] for p in out['plants']
                       if int(p['type']) == LILY_PAD_TYPE]
        out['pots'] = [[p['row'], p['col']] for p in out['plants']
                       if int(p['type']) == POT_TYPE]
        out['ice'] = icy_cells()
        out['ice_rows'] = ice_state()
        out['vases'] = [{k: it.get(k) for k in
                         ('row', 'col', 'vase_kind', 'plant', 'zombie', 'vase_tag')
                         if k in it}
                        for it in out['grid_items'] if it.get('type') == VASE_ITEM_TYPE]
    except Exception:
        out['scene'] = -1
        out['is_pool'] = False
        out['water'] = []
        out['lily'] = []

    zombies = []
    try:
        for z in g.zombies:
            zombies.append({'row': int(z.row), 'x': round(float(z.x), 1),
                            'type': int(z.type), 'name': name_of(z),
                            'hp': safe_attr(z, 'hp'),
                            'helmet_hp': safe_attr(z, 'helmet_hp'),
                            'max_hp': safe_attr(z, 'max_hp'),
                            'status': safe_attr(z, 'status'),
                            'altitude': safe_attr(z, 'altitude'),
                            'has_object': safe_attr(z, 'has_object'),
                            'in_pool': safe_attr(z, 'in_pool'),
                            'speed': safe_attr(z, 'speed'),
                            'shield_hp': safe_attr(z, 'shield_hp'),
                            'mind_controlled': safe_attr(z, 'mind_controlled'),
                            'target_row': safe_attr(z, 'target_row'),
                            'target_col': safe_attr(z, 'target_col'),
                            'flying': bool((safe_attr(z, 'altitude') or 0) > 5)})
    except Exception:
        pass
    out['zombies'] = zombies

    coins = []
    try:
        coins = [{'type': int(c.type), 'x': round(float(c.pos[0]), 1),
                  'y': round(float(c.pos[1]), 1), 'collecting': c.collecting,
                  'seed_type': int(getattr(c, 'usable_seed_type', -1) or -1),
                  'seed_name': plant_name_by_type(int(getattr(c, 'usable_seed_type', -1) or -1))
                  if int(getattr(c, 'usable_seed_type', -1) or -1) >= 0 else None}
                 for c in g.observer.coins(include_dead=False) if not c.dead]
    except Exception:
        pass
    out['coins'] = coins
    try:
        _cha = _u32(_u32(_u32(0x6A9EC0) + 0x768) + 0x160)
        if _cha:
            out['challenge'] = {
                'state': int.from_bytes(_read(_cha + 0x54, 4), 'little', signed=True),
                'counter': int.from_bytes(_read(_cha + 0x58, 4), 'little', signed=True),
                'score': int.from_bytes(_read(_cha + 0x60, 4), 'little', signed=True),
                'sel_flag': _read(_cha + 8, 1)[0],
                'sel_x': int.from_bytes(_read(_cha + 0xC, 4), 'little', signed=True),
                'sel_y': int.from_bytes(_read(_cha + 0x10, 4), 'little', signed=True),
            }
    except Exception as _e:
        out['challenge_error'] = repr(_e)
    return out


class Handler(BaseHTTPRequestHandler):
    protocol_version = 'HTTP/1.1'

    def log_message(self, fmt, *args):
        sys.stderr.write('%s %s\n' % (time.strftime('%H:%M:%S'), fmt % args))

    def send_json(self, code: int, body: Dict[str, Any]) -> None:
        data = json.dumps(body, ensure_ascii=False).encode('utf-8')
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(data)))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.close_connection = True
        self.wfile.write(data)

    def read_body(self) -> Dict[str, Any]:
        try:
            n = int(self.headers.get('Content-Length') or 0)
            return json.loads(self.rfile.read(n).decode('utf-8') or '{}') if n > 0 else {}
        except Exception:
            return {}

    def do_GET(self):
        path = self.path.split('?')[0]
        if path == '/health':
            return self.send_json(200, {'ok': True, 'service': 'pvz-bridge', 'port': PORT})
        if path == '/state':
            try:
                with _lock:
                    return self.send_json(200, state_dict())
            except Exception as e:
                traceback.print_exc()
                return self.send_json(500, {'ok': False,
                                            'error': '%s: %s' % (type(e).__name__, e)})
        return self.send_json(404, {'ok': False, 'error': 'not found'})

    def do_POST(self):
        path = self.path.split('?')[0]
        body = self.read_body()
        try:
            with _lock:
                g = get_game()
                if path == '/continue':
                    # 通关结算(ui=5) / 主菜单(ui=1) → 点按钮进下一关
                    ui = ui_now(g)
                    if ui not in (1, 5):
                        return self.send_json(200, {'ok': True, 'ui': ui,
                                                    'note': 'no_action_needed'})
                    cands = AWARD_CLICK_CANDIDATES if ui == 5 else MENU_CLICK_CANDIDATES
                    hit = None
                    for (x, y) in cands:
                        ui_click(g, x, y, gap=0.55)
                        time.sleep(0.35)
                        now = ui_now(g)
                        if now != ui:
                            hit = [x, y]
                            ui = now
                            break
                    return self.send_json(200, {'ok': hit is not None, 'ui': ui,
                                                'clicked': hit,
                                                'tried': len(cands)})
                if path == '/spin':
                    # 老虎机拉杆：远程调用游戏自己的 Board::MouseDown(0x411F20)。
                    # 游戏内部会走完整点击流程（扣 25 阳光、启动滚轮、状态置 4），
                    # 不写内存、不注入鼠标，所以不会破坏状态机。
                    app = _u32(0x6A9EC0)
                    bd = _u32(app + 0x768)
                    if not bd:
                        return self.send_json(503, {'ok': False, 'error': 'not in level'})
                    mode = int.from_bytes(_read(app + 0x7F8, 4), 'little', signed=True)
                    if mode != 18:
                        return self.send_json(409, {'ok': False,
                                                    'reason': 'not_slot_machine',
                                                    'game_mode': mode})
                    bk = _u32(bd + 0x144)
                    ch = _u32(bd + 0x160)
                    if not bk or not ch:
                        return self.send_json(503, {'ok': False, 'error': 'no seed bank'})

                    def rd_i(addr):
                        return int.from_bytes(_read(addr, 4), 'little', signed=True)

                    # 把手矩形 = (seed_bank+8 + 0x1D9, seed_bank+0xC, 55, 80)
                    bank_x = rd_i(bk + 8)
                    bank_y = rd_i(bk + 0xC)
                    cx = bank_x + 0x1D9 + 27
                    cy = bank_y + 40

                    sun_before = rd_i(bd + 0x5560)
                    state_before = rd_i(ch + 0x54)
                    if state_before != 0:
                        return self.send_json(409, {'ok': False, 'reason': 'spinning',
                                                    'state': state_before})
                    if sun_before < 25:
                        return self.send_json(409, {'ok': False, 'reason': 'no_sun',
                                                    'sun': sun_before, 'cost': 25})

                    try:
                        from pvztools.control.asm import Asm
                        ex = g.actions.executor
                        code = Asm()
                        code.push_imm32(1)        # clickCount
                        code.push_imm32(cy)       # y
                        code.push_imm32(cx)       # x
                        code.mov_reg_imm32('ecx', bd)
                        code.call_abs(0x411F20)   # Board::MouseDown
                        ex.run(code, timeout_ms=2000)
                    except Exception as _e:
                        return self.send_json(500, {'ok': False, 'error': repr(_e)})

                    # 等这一转结束：状态 4 -> 0
                    deadline = time.time() + float(body.get('wait', 10))
                    saw = False
                    while time.time() < deadline:
                        st = rd_i(ch + 0x54)
                        if st == 4:
                            saw = True
                        elif st == 0 and saw:
                            break
                        time.sleep(0.05)

                    reels = [rd_i(bk + 0x28 + 0x50 * k + 0x34) for k in range(3)]
                    sun_after = rd_i(bd + 0x5560)
                    ok = (sun_before - sun_after) >= 25 or saw
                    return self.send_json(200 if ok else 409, {
                        'ok': ok, 'saw_spin': saw,
                        'click': [cx, cy],
                        'sun_before': sun_before, 'sun': sun_after,
                        'cost': sun_before - sun_after,
                        'reels': reels,
                        'reel_names': [plant_name_by_type(t) for t in reels]})

                if path == '/force_plant':
                    # 调试：直接 Board::AddPlant 指定类型（不查卡槽、不扣费）
                    row0 = int(body.get('row', 0))
                    col0 = int(body.get('col', 0))
                    ptype = int(body.get('type', 0))
                    here = raw_plants_at(row0, col0)
                    if here and not body.get('stack'):
                        return self.send_json(409, {'ok': False, 'reason': 'occupied',
                                                    'row': row0, 'col': col0,
                                                    'plant': here[0]['name']})
                    try:
                        idx = plant_remote(g, ptype, row0, col0)
                    except Exception as _e:
                        return self.send_json(500, {'ok': False, 'error': repr(_e)})
                    return self.send_json(200 if idx is not None else 409,
                                          {'ok': idx is not None, 'row': row0, 'col': col0,
                                           'type': ptype, 'index': idx})

                if path == '/belt_compact':
                    # 传送带补位（按游戏规则）：左移 N 格 -> offset += 50*N，index=新槽位
                    app_ = _u32(0x6A9EC0)
                    bd = _u32(app_ + 0x768)
                    bank = _u32(bd + 0x144)
                    if not bank:
                        return self.send_json(503, {'ok': False, 'error': 'no seed bank'})
                    maxs = int(body.get('slots', 10))
                    base = int.from_bytes(_read(bank + 0x28 + 0x08, 4),
                                          'little', signed=True)  # 槽0 的基础X

                    def rd_i(addr):
                        return int.from_bytes(_read(addr, 4), 'little', signed=True)

                    before, cards = [], []
                    for i in range(maxs):
                        p = bank + 0x28 + 0x50 * i
                        t = rd_i(p + 0x34)
                        before.append(t)
                        if t >= 0:
                            cards.append((i, rd_i(p + 0x30), _read(p, 0x50)))
                    moved = 0
                    for new_i, (old_i, old_off, blob) in enumerate(cards):
                        if new_i == old_i:
                            continue
                        dst = bank + 0x28 + 0x50 * new_i
                        _write(dst, blob)
                        _write(dst + 0x2C, new_i.to_bytes(4, 'little', signed=True))
                        _write(dst + 0x08, (base + 50 * new_i).to_bytes(4, 'little', signed=True))
                        shift = old_i - new_i
                        _write(dst + 0x30, (old_off + 50 * shift).to_bytes(4, 'little', signed=True))
                        moved += 1
                    for i in range(len(cards), maxs):
                        p = bank + 0x28 + 0x50 * i
                        if rd_i(p + 0x34) >= 0:
                            _write(p + 0x34, (-1).to_bytes(4, 'little', signed=True))
                    after = []
                    for i in range(maxs):
                        after.append(rd_i(bank + 0x28 + 0x50 * i + 0x34))
                    return self.send_json(200, {'ok': True, 'moved': moved,
                                                'before': before, 'after': after})

                if path == '/twist_rotate':
                    # 宝石迷阵 Twist：调用 0x420280(challenge, x, y) 旋转该格所在的 2x2
                    app_ = _u32(0x6A9EC0)
                    bd = _u32(app_ + 0x768)
                    ch_ = _u32(bd + 0x160)
                    if not bd or not ch_:
                        return self.send_json(503, {'ok': False, 'error': 'not in level'})
                    mode_ = int.from_bytes(_read(app_ + 0x7F8, 4), 'little', signed=True)
                    row = int(body.get('row', 0))
                    col = int(body.get('col', 0))
                    # 点击锚点是 2x2 块的右下角（实测）
                    # 点击锚点是 2x2 的右上角（实测）
                    row_click = row
                    col_click = col + 1
                    x = int(40 + (col_click + 0.5) * (620.0 / 8))
                    y = int(80 + (row_click + 0.5) * (480.0 / 5))
                    sun_before = int.from_bytes(_read(bd + 0x5560, 4), 'little', signed=True)
                    try:
                        from pvztools.control.asm import Asm
                        ex = g.actions.executor
                        code = Asm()
                        code.push_imm32(y)
                        code.push_imm32(x)
                        code.push_imm32(ch_)
                        code.call_abs(0x420280)
                        ex.run(code, timeout_ms=2000)
                    except Exception as _e:
                        return self.send_json(500, {'ok': False, 'error': repr(_e)})
                    time.sleep(float(body.get('wait', 0.6)))
                    sun_after = int.from_bytes(_read(bd + 0x5560, 4), 'little', signed=True)
                    return self.send_json(200, {'ok': True, 'row': row, 'col': col,
                                                'game_mode': mode_, 'click': [x, y],
                                                'sun_before': sun_before, 'sun': sun_after,
                                                'sun_gain': sun_after - sun_before})

                if path == '/begh_swap':
                    # 宝石迷阵交换：写选中状态 + 投递 WM_MOUSEMOVE（不动真实光标）
                    a = body.get('a')
                    b = body.get('b')
                    if not a or not b:
                        return self.send_json(400, {'ok': False, 'error': 'a/b 需要 [row, col]'})
                    app_ = _u32(0x6A9EC0)
                    bd = _u32(app_ + 0x768)
                    ch_ = _u32(bd + 0x160)
                    wm_ = _u32(app_ + 0x320)
                    if not bd or not ch_ or not wm_:
                        return self.send_json(503, {'ok': False, 'error': 'not in level'})
                    mode_ = int.from_bytes(_read(app_ + 0x7F8, 4), 'little', signed=True)
                    if mode_ != 20:
                        return self.send_json(409, {'ok': False, 'reason': 'not_beghouled',
                                                    'game_mode': mode_})

                    def cpx(rc):
                        r_, c_ = int(rc[0]), int(rc[1])
                        return (int(40 + (c_ + 0.5) * (620.0 / 8)),
                                int(80 + (r_ + 0.5) * (480.0 / 5)))

                    ax, ay = cpx(a)
                    bx, by = cpx(b)
                    sun_before = int.from_bytes(_read(bd + 0x5560, 4), 'little', signed=True)
                    _write(ch_ + 8, b'\x01')
                    _write(ch_ + 0xC, int(ax).to_bytes(4, 'little', signed=True))
                    _write(ch_ + 0x10, int(ay).to_bytes(4, 'little', signed=True))
                    time.sleep(0.05)
                    try:
                        px, py = g.window.logical_to_physical(bx, by)
                        lparam = (int(py) << 16) | (int(px) & 0xFFFF)
                        ctypes.windll.user32.PostMessageW(g.window.hwnd, 0x0200, 0, lparam)
                    except Exception as _e:
                        return self.send_json(500, {'ok': False, 'error': repr(_e)})
                    deadline = time.time() + float(body.get('wait', 1.2))
                    while time.time() < deadline:
                        time.sleep(0.05)
                    sun_after = int.from_bytes(_read(bd + 0x5560, 4), 'little', signed=True)
                    return self.send_json(200, {'ok': True, 'a': a, 'b': b,
                                                'pixel_a': [ax, ay], 'pixel_b': [bx, by],
                                                'sun_before': sun_before, 'sun': sun_after,
                                                'sun_gain': sun_after - sun_before})

                if path == '/vase_plant':
                    # 破罐者：点地上的植物卡片 -> 点目标格（两步都用 Board::MouseDown）
                    row = int(body.get('row', 0))
                    col = int(body.get('col', 0))
                    app_ = _u32(0x6A9EC0)
                    bd = _u32(app_ + 0x768)
                    if not bd:
                        return self.send_json(503, {'ok': False, 'error': 'not in level'})
                    cards = []
                    try:
                        for c in g.observer.coins(include_dead=False):
                            if c.dead:
                                continue
                            st = int(getattr(c, 'usable_seed_type', -1) or -1)
                            if int(c.type) == 16 and st >= 0:
                                cards.append((c, st))
                    except Exception as _e:
                        return self.send_json(500, {'ok': False, 'error': repr(_e)})
                    if not cards:
                        return self.send_json(409, {'ok': False, 'reason': 'no_card'})
                    want = body.get('type')
                    pick = next(((c, st) for c, st in cards if want is None or st == int(want)), None)
                    if pick is None:
                        return self.send_json(409, {'ok': False, 'reason': 'type_not_found',
                                                    'available': [st for _, st in cards]})
                    coin, st = pick
                    cx, cy = int(coin.pos[0]), int(coin.pos[1])
                    scene = board_scene()
                    step = 85 if scene in (2, 3) else 100
                    px, py = 80 + 80 * col, 40 + step * row + step // 2
                    try:
                        board_mousedown(g, bd, cx, cy)     # 点卡片
                        time.sleep(0.3)
                        board_mousedown(g, bd, px, py)     # 点格子
                        time.sleep(0.4)
                    except Exception as _e:
                        return self.send_json(500, {'ok': False, 'error': repr(_e)})
                    here = raw_plants_at(row, col)
                    placed = next((p for p in here if int(p['type']) == st), None)
                    return self.send_json(200 if placed else 409, {
                        'ok': placed is not None, 'row': row, 'col': col,
                        'type': st, 'name': plant_name_by_type(st),
                        'card_click': [cx, cy], 'cell_click': [px, py],
                        'planted': placed})

                if path == '/break_vase':
                    # 破罐者：点碎指定格子的罐子
                    row = int(body.get('row', 0))
                    col = int(body.get('col', 0))
                    scene = board_scene()
                    before = [v for v in (state_dict().get('vases') or [])
                              if int(v.get('row', -1)) == row and int(v.get('col', -1)) == col]
                    if not before:
                        return self.send_json(404, {'ok': False, 'reason': 'no_vase',
                                                    'row': row, 'col': col})
                    info = before[0]
                    step = 85 if scene in (2, 3) else 100
                    x = 80 + 80 * col
                    y = 40 + step * row + step // 2
                    bd = _u32(_u32(0x6A9EC0) + 0x768)
                    try:
                        board_mousedown(g, bd, x, y)
                    except Exception as _e:
                        return self.send_json(500, {'ok': False, 'error': repr(_e)})
                    time.sleep(0.5)
                    after = [v for v in (state_dict().get('vases') or [])
                             if int(v.get('row', -1)) == row and int(v.get('col', -1)) == col]
                    return self.send_json(200 if not after else 409, {
                        'ok': not after, 'row': row, 'col': col, 'click': [x, y],
                        'content': info.get('vase_kind'), 'detail': info.get('plant') or info.get('zombie')})

                if path == '/next_wave':
                    # Last Stand「继续猛攻」按钮：屏幕底部中间 (400,570)
                    s0 = state_dict()
                    z0 = len(s0.get('zombies') or [])
                    try:
                        _bd = _u32(_u32(0x6A9EC0) + 0x768)
                        board_mousedown(g, _bd, 400, 570)
                    except Exception as _e:
                        try:
                            post_click(g, 400, 570, gap=0.5)
                        except Exception as _e2:
                            return self.send_json(500, {'ok': False, 'error': repr(_e2)})
                    time.sleep(0.6)
                    s1 = state_dict()
                    z1 = len(s1.get('zombies') or [])
                    return self.send_json(200, {'ok': True,
                                                'zombies_before': z0, 'zombies_after': z1,
                                                'wave_after': s1.get('wave'),
                                                'clicked': [400, 570]})

                if path == '/debug_click':
                    # 调试：远程调用 Board::MouseDown(x,y,1)（走游戏自己的点击流程）
                    bd = _u32(_u32(0x6A9EC0) + 0x768)
                    if not bd:
                        return self.send_json(503, {'ok': False, 'error': 'not in level'})
                    x = int(body.get('x', 0))
                    y = int(body.get('y', 0))
                    try:
                        from pvztools.control.asm import Asm
                        ex = g.actions.executor
                        code = Asm()
                        code.push_imm32(1)
                        code.push_imm32(y)
                        code.push_imm32(x)
                        code.mov_reg_imm32('ecx', bd)
                        code.call_abs(0x411F20)
                        ex.run(code, timeout_ms=2000)
                    except Exception as _e:
                        return self.send_json(500, {'ok': False, 'error': repr(_e)})
                    return self.send_json(200, {'ok': True, 'clicked': [x, y]})

                if path == '/plant_prize':
                    # 老虎机奖品：点弹出的卡片(硬币) -> 点格子
                    bd = _u32(_u32(0x6A9EC0) + 0x768)
                    if not bd:
                        return self.send_json(503, {'ok': False, 'error': 'not in level'})
                    app_ = _u32(0x6A9EC0)
                    mode = int.from_bytes(_read(app_ + 0x7F8, 4), 'little', signed=True)
                    row0 = int(body.get('row', 0))
                    col0 = int(body.get('col', 0))
                    want = body.get('type')
                    scene = board_scene()
                    prizes = []
                    try:
                        for c in g.observer.coins(include_dead=False):
                            if c.dead:
                                continue
                            st = int(getattr(c, 'usable_seed_type', -1) or -1)
                            if int(c.type) == 16 and st >= 0:
                                prizes.append((c, st))
                    except Exception as _e:
                        return self.send_json(500, {'ok': False, 'error': repr(_e)})
                    if not prizes:
                        return self.send_json(409, {'ok': False, 'reason': 'no_prize'})
                    if want is not None:
                        picked = next(((c, st) for c, st in prizes if st == int(want)), None)
                    else:
                        picked = prizes[0]
                    if picked is None:
                        return self.send_json(409, {'ok': False, 'reason': 'prize_type_not_found',
                                                    'available': [st for _, st in prizes]})
                    coin, st = picked
                    # 水生植物只能种水里（雨关/老虎机都由我们用 AddPlant 落地，需自己把关）
                    if st in WATER_ONLY_PLANTS and scene in POOL_SCENES and row0 not in WATER_ROWS:
                        return self.send_json(409, {'ok': False, 'reason': 'water_only',
                                                    'row': row0, 'col': col0,
                                                    'plant': plant_name_by_type(st)})
                    cx, cy = int(coin.pos[0]), int(coin.pos[1])
                    px, py = cell_pixel(row0, col0, scene)
                    try:
                        if mode == 19:
                            # 雨关：远程点击对种子卡不生效，改为
                            # AddPlant 种下 + 把这张卡片标记为已销毁（游戏自己也是这么收尾的）
                            plant_remote(g, st, row0, col0)
                            time.sleep(0.25)
                            coin_arr = _u32(bd + 0xE4)
                            if coin_arr:
                                _write(coin_arr + 0xD8 * int(coin.index) + 0x38, b'\x01')
                            time.sleep(0.35)
                        else:
                            board_mousedown(g, bd, cx, cy)   # 点卡片
                            time.sleep(0.35)
                            board_mousedown(g, bd, px, py)   # 点格子
                            time.sleep(0.5)
                    except Exception as _e:
                        return self.send_json(500, {'ok': False, 'error': repr(_e)})
                    here = raw_plants_at(row0, col0)
                    placed = next((p for p in here if int(p['type']) == st), None)
                    return self.send_json(200 if placed else 409, {
                        'ok': placed is not None,
                        'reason': None if placed else 'not_placed',
                        'row': row0, 'col': col0,
                        'prize_click': [cx, cy], 'cell_click': [px, py],
                        'type': st, 'name': plant_name_by_type(st),
                        'planted': placed})

                if path == '/recalibrate':
                    # 窗口/全屏变化后重新校准坐标映射
                    info = {}
                    try:
                        g.window.calibrate()
                        info['calibrated'] = True
                    except Exception as _e:
                        info['calibrated'] = False
                        info['error'] = repr(_e)
                    for attr in ('client_w', 'client_h', 'scale_x', 'scale_y',
                                 'origin_x', 'origin_y', 'letterbox_x', 'letterbox_y'):
                        try:
                            info[attr] = getattr(g.window, attr)
                        except Exception:
                            pass
                    return self.send_json(200, dict(info, ok=True))

                if path == '/click':
                    # 通用点击：投递给游戏窗口（不需要前台）
                    lx = float(body.get('x', 0))
                    ly = float(body.get('y', 0))
                    gap = float(body.get('gap', 0.35))
                    method = str(body.get('method', 'board'))
                    try:
                        if method == 'board':
                            _bd = _u32(_u32(0x6A9EC0) + 0x768)
                            board_mousedown(g, _bd, int(lx), int(ly))
                        else:
                            post_click(g, lx, ly, gap=gap)
                    except Exception as _e:
                        return self.send_json(500, {'ok': False, 'error': repr(_e)})
                    return self.send_json(200, {'ok': True, 'x': lx, 'y': ly})
                if path == '/pick':
                    # 选卡：先清空卡槽，再逐张点选（真实鼠标）
                    from pvztools.control.chooser import chooser_card_xy, bank_packet_xy
                    from pvztools.control.actions import resolve_plant
                    ch = g.chooser
                    if ch.ui() != 2:
                        return self.send_json(409, {'ok': False, 'error': '不在选卡界面',
                                                    'ui': ch.ui()})
                    names = body.get('seeds') or []
                    if not names:
                        return self.send_json(400, {'ok': False, 'error': 'seeds 为空'})
                    try:                                     # 刷新校准（窗口缩放/移动后仍准）
                        g.window.calibrate()
                    except Exception:
                        pass
                    size = ch.bank_size()
                    # 卡槽比传入多时要补齐（不满则 Let's Rock 不可用）
                    names = list(names)
                    if len(names) < size:
                        for cand in DEFAULT_DECK_FILL:
                            if len(names) >= size:
                                break
                            if cand not in names:
                                names.append(cand)
                        while len(names) < size:
                            names.append(names[len(names) % max(1, len(names))])
                    # 清空：点卡槽第 0 格，直到已选数变 0（最多点 size+2 次）
                    for _ in range(size + 2):
                        if chooser_picked_count() <= 0:
                            break
                        ui_click(g, *bank_packet_xy(0, size))
                    cleared = chooser_picked_count()
                    picked, failed = [], []
                    for name in names[:size]:
                        try:
                            pid = int(resolve_plant(name))
                        except Exception:
                            failed.append(name)
                            continue
                        cnt0 = chooser_picked_count()
                        ui_click(g, *chooser_card_xy(pid, ch.has7rows))
                        cnt1 = chooser_picked_count()
                        if cnt1 <= cnt0:                     # 没点上，重试一次
                            post_click(g, *chooser_card_xy(pid, ch.has7rows), gap=0.45)
                            cnt1 = chooser_picked_count()
                        (picked if cnt1 > cnt0 else failed).append(name)
                    final = chooser_picked_count()
                    return self.send_json(200, {'ok': not failed and final == min(len(names), size),
                                                'picked': picked, 'failed': failed,
                                                'picked_count': final, 'bank_size': size,
                                                'cleared_ok': cleared <= 0})
                if path == '/start':
                    from pvztools.control.chooser import LETS_ROCK_XY
                    ch = g.chooser
                    if ch.ui() != 2:
                        return self.send_json(200, {'ok': ch.ui() == 3, 'ui': ch.ui(),
                                                    'already_in_level': ch.ui() == 3})
                    ui_click(g, *LETS_ROCK_XY, gap=0.5)
                    deadline = time.time() + float(body.get('wait', 12))
                    while time.time() < deadline:
                        try:
                            if ch.ui() == 3:
                                return self.send_json(200, {'ok': True, 'ui': 3})
                        except Exception:
                            pass
                        time.sleep(0.4)
                    return self.send_json(200, {'ok': False, 'ui': ch.ui(),
                                                'error': '界面未切换（可能缺必需卡/警告框）'})
                if path == '/plant' and conveyor_active():
                    # 传送带关卡：不扣阳光、不记冷却，改用掉一张带上的卡
                    row0 = int(body.get('row', 0))
                    col0 = int(body.get('col', 0))
                    plant = str(body.get('plant'))
                    belt = read_belt()
                    pkt = next((b for b in belt if b['name'] == plant or str(b['type']) == plant), None)
                    if pkt is None:
                        return self.send_json(404, {'ok': False, 'reason': 'not_on_belt',
                                                    'plant': plant, 'belt': belt})
                    # 同样的占位/墓碑检查（墓碑吞噬者除外）
                    # 占位/池塘检查（传送带分支）
                    chk = placement_check(g, row0, col0, int(pkt['type']))
                    if not chk.get('ok'):
                        return self.send_json(409, dict(chk, row=row0, col=col0))
                    blocker = next((it for it in read_grid_items()
                                    if it['row'] == row0 and it['col'] == col0 and it['blocking']), None)
                    is_buster = int(pkt['type']) == 11
                    if blocker and not (is_buster and blocker['type'] == 1):
                        return self.send_json(409, {'ok': False, 'reason': 'blocked',
                                                    'row': row0, 'col': col0,
                                                    'item': blocker['name']})
                    if is_buster and not blocker:
                        return self.send_json(409, {'ok': False, 'reason': 'buster_needs_grave',
                                                    'row': row0, 'col': col0})
                    bd = _u32(_u32(0x6A9EC0) + 0x768)
                    # 优先走游戏自己的「点卡 -> 点格子」流程：
                    # 这样用卡、传送带左移补位、滑动动画都由游戏处理（不会卡位）
                    scene_ = board_scene()
                    instant = int(pkt['type']) in INSTANT_PLANTS
                    ok = False
                    idx = None
                    try:
                        slot_ = int(pkt['slot'])
                        _bank = _u32(bd + 0x144)
                        _pk = _bank + 0x28 + 0x50 * slot_
                        _base = int.from_bytes(_read(_pk + 0x08, 4), 'little', signed=True)
                        _off = int.from_bytes(_read(_pk + 0x30, 4), 'little', signed=True)
                        _click_x = _base + _off + 39   # 卡片中心（绘制X + 19..59）
                        board_mousedown(g, bd, _click_x, 40)           # 点传送带卡片
                        time.sleep(0.25)
                        px, py = cell_pixel(row0, col0, scene_)
                        board_mousedown(g, bd, px, py)                 # 点格子
                        time.sleep(0.35)
                        got = raw_plants_at(row0, col0)
                        matched = any(int(p['type']) == int(pkt['type']) for p in got)
                        if instant:
                            # 瞬发植物：看卡片是否被消耗
                            after = read_belt()
                            ok = not any(b['slot'] == slot_ and b['type'] == int(pkt['type'])
                                         for b in after)
                        else:
                            ok = matched
                        if ok:
                            compact_belt()      # 种下瞬间立刻补位（防止新卡穿过去填坑）
                    except Exception as _e:
                        sys.stderr.write('conveyor ui plant failed: %r\n' % (_e,))
                    if not ok:
                        # 兜底：直接 AddPlant + 清槽
                        idx = plant_remote(g, int(pkt['type']), row0, col0)
                        time.sleep(0.15)
                        got = raw_plants_at(row0, col0)
                        matched = any(int(p['type']) == int(pkt['type']) for p in got)
                        ok = idx is not None and (matched or instant)
                        if ok:
                            consume_belt_packet(pkt['slot'])
                    return self.send_json(200 if ok else 409, {
                        'ok': ok, 'conveyor': True, 'row': row0, 'col': col0,
                        'placed': next((p['name'] for p in got if str(p['type']) == str(pkt['type'])), (got[0]['name'] if got else None)), 'index': idx,
                        'from_belt_slot': pkt['slot'], 'belt_left': len(read_belt())})
                if path == '/plant':
                    row0 = int(body.get('row', 0))
                    col0 = int(body.get('col', 0))
                    plant = body.get('plant')
                    seed_early = find_seed(g, plant)
                    # 前置校验：格子被植物或场地物品占着就不种
                    # 占位/池塘检查
                    if seed_early is not None:
                        chk = placement_check(g, row0, col0, int(seed_early['type']))
                        if not chk.get('ok'):
                            return self.send_json(409, dict(chk, row=row0, col=col0))
                    blocker = next((it for it in read_grid_items()
                                    if it['row'] == row0 and it['col'] == col0 and it['blocking']), None)
                    # 墓碑吞噬者(11) 必须种在墓碑(1)上，放行
                    if blocker and not (seed_early is not None and int(seed_early['type']) == 11 and blocker['type'] == 1):
                        return self.send_json(409, {'ok': False, 'reason': 'blocked',
                                                    'row': row0, 'col': col0,
                                                    'item': blocker['name']})
                    wait = float(body.get('wait', 0) or 0)
                    deadline = time.time() + wait
                    while True:
                        seed = find_seed(g, plant)
                        if seed is None:
                            return self.send_json(404, {'ok': False,
                                                        'error': '卡槽里没有 %r' % (plant,)})
                        sun_now = safe_attr(g, 'sun')
                        view = seed_view(seed, sun_now)
                        if view['usable'] or time.time() >= deadline:
                            break
                        time.sleep(0.2)
                    sun_before = safe_attr(g, 'sun')
                    view = seed_view(seed, sun_before)
                    if not view['usable']:
                        why = ('cooldown' if view['cooldown_left_ms'] > 0
                               else ('no_sun' if not view['affordable'] else 'card_not_usable'))
                        return self.send_json(409, {'ok': False, 'reason': why,
                                                    'seed': view, 'sun': sun_before})
                    # 统一用表：游戏 cd_total 可能是旧值/0，导致两边时间不一致
                    cd_ms = PLANT_CD_MS.get(int(seed['type']), 7500)
                    charged = PLANT_COST.get(int(seed['type']), 0)
                    # 老虎机模式：赢来的植物是奖品，免费种，并且种完要消耗掉那张卡
                    _app = _u32(0x6A9EC0)
                    _slot_mode = int.from_bytes(_read(_app + 0x7F8, 4),
                                                'little', signed=True) == 18
                    if _slot_mode:
                        charged = 0
                    idx = plant_remote(g, int(seed['type']), row0, col0)
                    # 种下就立刻记账 + 写回冷却，不要等校验（否则玩家能看到延迟）
                    if idx is not None:
                        try:
                            g.sun = int(sun_before) - charged
                        except Exception:
                            pass
                        _seed_ready_at[int(seed['slot'])] = time.monotonic() + cd_ms / 1000.0
                        try:
                            write_seed_cooldown(int(seed['slot']), int(cd_ms / 10))
                        except Exception as _e:
                            sys.stderr.write('write_seed_cooldown failed: %r\n' % (_e,))
                        try:
                            fix_plant_init(row0, col0, int(seed['type']))
                        except Exception as _e:
                            sys.stderr.write('fix_plant_init failed: %r\n' % (_e,))
                    time.sleep(0.05)
                    got = raw_plants_at(row0, col0)
                    _pt = int(seed['type'])
                    ok = idx is not None and (any(int(p['type']) == _pt for p in got)
                                              or _pt in INSTANT_PLANTS)
                    return self.send_json(200 if ok else 409, {
                        'ok': ok, 'row': row0, 'col': col0, 'wanted': seed['name'],
                        'placed': got[0]['name'] if got else None, 'index': idx,
                        'charged': charged,
                        'sun_before': sun_before, 'sun': safe_attr(g, 'sun'),
                        'cooldown_left_ms': cooldown_left_ms(seed['slot'])})
                if path == '/shovel':
                    row0 = int(body.get('row', 0))
                    col0 = int(body.get('col', 0))
                    here = [p for p in plant_list(g)
                            if p['row'] == row0 and p['col'] == col0]
                    if not here:
                        return self.send_json(404, {'ok': False, 'error': '该格没有植物'})
                    n = g.shovel(row0 + 1, col0 + 1)
                    time.sleep(0.15)
                    left = [p for p in plant_list(g)
                            if p['row'] == row0 and p['col'] == col0]
                    return self.send_json(200, {'ok': not left, 'removed': here[0]['name'],
                                                'count': n, 'left': left})
        except Exception as e:
            traceback.print_exc()
            return self.send_json(500, {'ok': False,
                                        'error': '%s: %s' % (type(e).__name__, e)})
        return self.send_json(404, {'ok': False, 'error': 'not found'})


PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 15580

# ---- 真实鼠标（选卡界面只认硬件输入，投递消息无效） ----
_u32w = ctypes.WinDLL('user32', use_last_error=True)
_u32w.ClientToScreen.argtypes = [wt.HWND, ctypes.POINTER(wt.POINT)]
_u32w.SetCursorPos.argtypes = [ctypes.c_int, ctypes.c_int]
_u32w.GetCursorPos.argtypes = [ctypes.POINTER(wt.POINT)]
_u32w.mouse_event.argtypes = [wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, ctypes.c_size_t]
_u32w.GetForegroundWindow.restype = wt.HWND

LEFTDOWN, LEFTUP = 0x0002, 0x0004


def real_click(g, lx: float, ly: float, hold: float = 0.10, gap: float = 0.30) -> None:
    """按逻辑坐标(800x600)真实点击：移光标 → 按下 → 松开。"""
    w = g.window
    px, py = w.logical_to_physical(lx, ly)
    pt = wt.POINT(int(px), int(py))
    _u32w.ClientToScreen(w.hwnd, ctypes.byref(pt))
    _u32w.SetCursorPos(pt.x, pt.y)
    time.sleep(0.20)
    _u32w.mouse_event(LEFTDOWN, 0, 0, 0, 0)
    time.sleep(hold)
    _u32w.mouse_event(LEFTUP, 0, 0, 0, 0)
    time.sleep(gap)


def post_click(g, lx: float, ly: float, gap: float = 0.35) -> None:
    """投递消息点击（不需要前台，坐标走 DPI 校准）。"""
    g.window.click_logical(int(lx), int(ly), move=True)
    time.sleep(gap)


def save_cursor():
    p = wt.POINT()
    _u32w.GetCursorPos(ctypes.byref(p))
    return p.x, p.y


def restore_cursor(pos) -> None:
    try:
        _u32w.SetCursorPos(int(pos[0]), int(pos[1]))
    except Exception:
        pass

# ---- 直接写游戏内存：把冷却写回种子槽，让卡片 UI 也显示冷却 ----
import ctypes
import ctypes.wintypes as wt

_k32 = ctypes.WinDLL('kernel32', use_last_error=True)
_k32.OpenProcess.restype = wt.HANDLE
_k32.OpenProcess.argtypes = [wt.DWORD, wt.BOOL, wt.DWORD]
_k32.ReadProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                   ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
_k32.WriteProcessMemory.argtypes = [wt.HANDLE, ctypes.c_void_p, ctypes.c_void_p,
                                    ctypes.c_size_t, ctypes.POINTER(ctypes.c_size_t)]
_hproc = None
_hproc_pid = None


def _mem_handle():
    global _hproc, _hproc_pid
    pid = current_pid()
    if pid is None:
        raise RuntimeError('PlantsVsZombies.exe 未运行')
    if _hproc is None or _hproc_pid != pid:
        _hproc = _k32.OpenProcess(0x0010 | 0x0020 | 0x0008 | 0x0400, False, pid)
        _hproc_pid = pid
    return _hproc


def _read(addr: int, n: int) -> bytes:
    buf = ctypes.create_string_buffer(n)
    got = ctypes.c_size_t(0)
    if not _k32.ReadProcessMemory(_mem_handle(), ctypes.c_void_p(addr), buf, n, ctypes.byref(got)):
        return b''
    return buf.raw[:got.value]


def _write(addr: int, data: bytes) -> bool:
    got = ctypes.c_size_t(0)
    return bool(_k32.WriteProcessMemory(_mem_handle(), ctypes.c_void_p(addr), data, len(data),
                                        ctypes.byref(got)))


def _u32(addr: int) -> int:
    b = _read(addr, 4)
    return int.from_bytes(b, 'little') if len(b) == 4 else 0


def seed_packet_addr(slot: int) -> int:
    """绝对地址：board -> seed_bank -> packets + slot*0x50（1.0.0.1051 布局）。"""
    app = _u32(0x6A9EC0)
    board = _u32(app + 0x768)
    bank = _u32(board + 0x144)
    return bank + 0x28 + 0x50 * int(slot)


def write_seed_cooldown(slot: int, cd_cs: int) -> bool:
    """把冷却写进种子槽：cd_elapsed=0, cd_total=cd_cs, usable=0, refreshing=1。"""
    p = seed_packet_addr(slot)
    return all([
        _write(p + 0x24, (0).to_bytes(4, 'little', signed=True)),
        _write(p + 0x28, int(cd_cs).to_bytes(4, 'little', signed=True)),
        _write(p + 0x48, b'\x00'),
        _write(p + 0x49, b'\x01'),
    ])


def conveyor_active() -> bool:
    """传送带关卡判定：seed_bank.conveyor_belt_counter(0x34c) != 0。"""
    try:
        app = _u32(0x6A9EC0)
        board = _u32(app + 0x768)
        bank = _u32(board + 0x144)
        if not bank:
            return False
        b = _read(bank + 0x34C, 4)
        return len(b) == 4 and int.from_bytes(b, 'little', signed=True) != 0
    except Exception:
        return False


def read_belt() -> List[Dict[str, Any]]:
    """传送带上现有的卡（type >= 0 的槽）。"""
    out: List[Dict[str, Any]] = []
    try:
        app = _u32(0x6A9EC0)
        board = _u32(app + 0x768)
        bank = _u32(board + 0x144)
        if not bank:
            return out
        cnt = int.from_bytes(_read(bank + 0x24, 4), 'little', signed=True)
        for i in range(max(0, min(cnt, 10))):
            p = bank + 0x28 + 0x50 * i
            t = int.from_bytes(_read(p + 0x34, 4), 'little', signed=True)
            if t >= 0:
                out.append({'slot': i, 'type': t, 'name': plant_name_by_type(t)})
    except Exception:
        pass
    return out


def compact_belt(slots: int = 10) -> Dict[str, Any]:
    """按游戏规则补位：左移 N 格 -> offset += 50*N，index = 新槽位。

    飞行中的卡：index 减 N、offset 加 50*N，绘制 X 不变（不会穿过别的卡）。
    已到位的卡：offset 从 0 变 50*N，产生左移动画。
    """
    app = _u32(0x6A9EC0)
    board = _u32(app + 0x768)
    bank = _u32(board + 0x144)
    if not bank:
        return {'ok': False, 'error': 'no seed bank'}
    base = int.from_bytes(_read(bank + 0x28 + 0x08, 4), 'little', signed=True)

    def rd_i(addr: int) -> int:
        return int.from_bytes(_read(addr, 4), 'little', signed=True)

    before, cards = [], []
    for i in range(slots):
        p = bank + 0x28 + 0x50 * i
        t = rd_i(p + 0x34)
        before.append(t)
        if t >= 0:
            cards.append((i, rd_i(p + 0x30), _read(p, 0x50)))
    moved = 0
    for new_i, (old_i, old_off, blob) in enumerate(cards):
        if new_i == old_i:
            continue
        dst = bank + 0x28 + 0x50 * new_i
        _write(dst, blob)
        _write(dst + 0x2C, new_i.to_bytes(4, 'little', signed=True))
        _write(dst + 0x08, (base + 50 * new_i).to_bytes(4, 'little', signed=True))
        shift = old_i - new_i
        _write(dst + 0x30, (old_off + 50 * shift).to_bytes(4, 'little', signed=True))
        moved += 1
    for i in range(len(cards), slots):
        p = bank + 0x28 + 0x50 * i
        if rd_i(p + 0x34) >= 0:
            _write(p + 0x34, (-1).to_bytes(4, 'little', signed=True))
    return {'ok': True, 'moved': moved, 'before': before,
            'after': [rd_i(bank + 0x28 + 0x50 * i + 0x34) for i in range(slots)]}


def consume_belt_packet(slot: int) -> bool:
    """用掉传送带上第 slot 张卡：只把该格清空，**不搬位**。

    实测（2026-11-08）：游戏自己的传送带不会让后面的卡左移，
    而是过一会（约 10 秒）在空位补一张新卡。
    早期「手动左移补位」会破坏腰带数据（index 全变 9、usable 全变 0），
    导致卡片灰掉、"重新装填中"、还赖在带子上。
    """
    try:
        app = _u32(0x6A9EC0)
        board = _u32(app + 0x768)
        bank = _u32(board + 0x144)
        if not bank:
            return False
        cnt = int.from_bytes(_read(bank + 0x24, 4), 'little', signed=True)
        if cnt <= 0:
            return False
        slot = max(0, min(int(slot), cnt - 1))
        p = bank + 0x28 + 0x50 * slot
        return all([
            _write(p + 0x34, (-1).to_bytes(4, 'little', signed=True)),   # type = 空
            _write(p + 0x38, (-1).to_bytes(4, 'little', signed=True)),   # imitater
            _write(p + 0x30, (0).to_bytes(4, 'little', signed=True)),    # offset_x
            _write(p + 0x24, (0).to_bytes(4, 'little', signed=True)),    # cd_elapsed
            _write(p + 0x28, (0).to_bytes(4, 'little', signed=True)),    # cd_total
            _write(p + 0x48, b'\x01'),                                   # usable
            _write(p + 0x49, b'\x00'),                                   # refreshing
        ])
    except Exception:
        return False


# ---- 池塘关（Pool / Fog）种植限制 ----
LILY_PAD_TYPE = 16                     # 睡莲
WATER_ONLY_PLANTS = frozenset({16, 19, 24, 43})  # 睡莲 / 缠绕水草 / 海蘑菇 / 香蒲
POOL_SCENES = frozenset({2, 3})        # 2=池塘 3=浓雾（都有水面）
POT_TYPE = 33                          # 花盆
ROOF_SCENES = frozenset({4})           # 4=屋顶（必须踩花盆才能种）
WATER_ROWS = frozenset({2, 3})         # 5 行棋盘里第 2、3 行是水


def board_scene() -> int:
    """Board.mScene（board+0x554C）：0 白天 / 1 夜晚 / 2 池塘 / 3 浓雾 / 4 屋顶。"""
    try:
        board = _u32(_u32(0x6A9EC0) + 0x768)
        if not board:
            return -1
        return int.from_bytes(_read(board + 0x554C, 4), 'little', signed=True)
    except Exception:
        return -1


def water_cells() -> List[List[int]]:
    """当前关卡的水面格子（非池塘关返回空）。"""
    if board_scene() not in POOL_SCENES:
        return []
    return [[r, c] for r in sorted(WATER_ROWS) for c in range(9)]


# ---- 雪橇车冰面 ----
# Board 里按行存的三个数组（stride 4，长度 6）：
#   +0x60C 冰面左边界（x 像素，默认 800 = 无冰，雪橇车开过时向左推进）
#   +0x624 冰面剩余时间（>0 表示这一行有冰）
ICE_MINX_OFF = 0x60C
ICE_TIMER_OFF = 0x624
ICE_ROWS = 6
GRID_X0 = 40      # 第 0 列左边界
GRID_W = 80       # 每列宽


def ice_state() -> List[Dict[str, Any]]:
    """每一行的冰面状态：[{row, timer, min_x}]（timer>0 才代表有冰）。"""
    out: List[Dict[str, Any]] = []
    try:
        board = _u32(_u32(0x6A9EC0) + 0x768)
        if not board:
            return out
        for r in range(ICE_ROWS):
            minx = int.from_bytes(_read(board + ICE_MINX_OFF + 4 * r, 4),
                                  'little', signed=True)
            timer = int.from_bytes(_read(board + ICE_TIMER_OFF + 4 * r, 4),
                                   'little', signed=True)
            out.append({'row': r, 'min_x': minx, 'timer': timer})
    except Exception:
        pass
    return out


def icy_cells() -> List[List[int]]:
    """被冰覆盖的格子（雪橇车开过的那一片）。"""
    cells: List[List[int]] = []
    for st in ice_state():
        if st['timer'] <= 0:
            continue
        for col in range(9):
            x0 = GRID_X0 + GRID_W * col
            x1 = x0 + GRID_W
            if x1 > st['min_x']:          # 该格与 [min_x, 右边界] 有重叠
                cells.append([st['row'], col])
    return cells


def raw_plants_at(row: int, col: int) -> List[Dict[str, Any]]:
    """直读 Board.mPlants（stride 0x14C）取某格植物，避免 pvztools 列表滞后。"""
    out: List[Dict[str, Any]] = []
    try:
        board = _u32(_u32(0x6A9EC0) + 0x768)
        arr = _u32(board + 0xAC)
        cap = int.from_bytes(_read(board + 0xB0, 4), 'little', signed=True)
        if not arr or cap <= 0:
            return out
        cap = min(cap, 512)
        blob = _read(arr, 0x14C * cap)
        for i in range(cap):
            b = 0x14C * i
            if b + 0x48 > len(blob):
                break
            hp = int.from_bytes(blob[b + 0x40:b + 0x44], 'little', signed=True)
            if hp <= 0:
                continue
            r = int.from_bytes(blob[b + 0x1C:b + 0x20], 'little', signed=True)
            c = int.from_bytes(blob[b + 0x28:b + 0x2C], 'little', signed=True)
            if r != row or c != col:
                continue
            t = int.from_bytes(blob[b + 0x24:b + 0x28], 'little', signed=True)
            out.append({'row': r, 'col': c, 'type': t,
                        'name': plant_name_by_type(t), 'hp': hp, 'index': i})
    except Exception:
        pass
    return out


def placement_check(g, row: int, col: int, ptype: int) -> Dict[str, Any]:
    """种植前校验：占位 + 池塘规则（水/陆 + 睡莲）。"""
    if [row, col] in icy_cells():
        return {'ok': False, 'reason': 'ice', 'row': row, 'col': col}
    here = raw_plants_at(row, col)
    scene = board_scene()
    lily = any(int(p['type']) == LILY_PAD_TYPE for p in here)
    pot = any(int(p['type']) == POT_TYPE for p in here)
    # 荷叶和花盆是"底座"，不算占用
    others = [p for p in here
              if int(p['type']) not in (LILY_PAD_TYPE, POT_TYPE)]
    in_water = scene in POOL_SCENES and row in WATER_ROWS
    ptype = int(ptype)

    # 屋顶：没有花盆的格子只能种花盆
    if scene in ROOF_SCENES and not in_water:
        if ptype == POT_TYPE:
            if here:
                return {'ok': False, 'reason': 'occupied', 'plant': here[0]['name']}
            return {'ok': True}
        if others:
            return {'ok': False, 'reason': 'occupied', 'plant': others[0]['name']}
        if not pot:
            return {'ok': False, 'reason': 'needs_flowerpot', 'row': row, 'col': col}
        return {'ok': True}

    if in_water:
        if ptype == LILY_PAD_TYPE:
            if here:
                return {'ok': False, 'reason': 'occupied', 'plant': here[0]['name']}
            return {'ok': True}
        if others:
            return {'ok': False, 'reason': 'occupied', 'plant': others[0]['name']}
        if ptype in WATER_ONLY_PLANTS:
            return {'ok': True}
        if not lily:
            return {'ok': False, 'reason': 'needs_lilypad', 'row': row, 'col': col}
        return {'ok': True}

    # 陆地
    if ptype in WATER_ONLY_PLANTS:
        return {'ok': False, 'reason': 'water_only', 'row': row, 'col': col,
                'plant_type': ptype}
    if here:
        return {'ok': False, 'reason': 'occupied', 'plant': here[0]['name']}
    return {'ok': True}


# 瞬发植物：放下就爆，不能靠"格子还在"判断成功
INSTANT_PLANTS = frozenset({2, 14, 15, 20})   # 樱桃炸弹 / 寒冰菇 / 毁灭菇 / 火爆辣椒

PLANT_NAME_BY_TYPE = {
    0: '豌豆射手', 1: '向日葵', 2: '樱桃炸弹', 3: '坚果', 4: '土豆雷', 5: '寒冰射手',
    6: '大嘴花', 7: '双发射手', 8: '小喷菇', 9: '阳光菇', 10: '大喷菇', 11: '墓碑吞噬者',
    12: '魅惑菇', 13: '胆小菇', 14: '寒冰菇', 15: '毁灭菇', 16: '睡莲', 17: '窝瓜',
    18: '三线射手', 19: '缠绕水草', 20: '火爆辣椒', 21: '地刺', 22: '火炬树桩',
    23: '高坚果', 24: '海蘑菇', 25: '路灯花', 26: '仙人掌', 27: '三叶草',
    28: '裂荚射手', 29: '杨桃', 30: '南瓜头', 31: '磁力菇', 32: '卷心菜投手',
    33: '花盆', 34: '玉米投手', 35: '咖啡豆', 36: '大蒜', 37: '叶子保护伞',
    38: '金盏花', 39: '西瓜投手', 40: '机枪射手', 41: '双子向日葵', 42: '忧郁菇',
    43: '香蒲', 44: '冰西瓜', 45: '吸金磁', 46: '地刺王', 47: '玉米加农炮', 48: '模仿者',
}


def plant_name_by_type(t: int) -> str:
    return PLANT_NAME_BY_TYPE.get(int(t), 'type:%d' % int(t))


# 场地物品（墓碑/弹坑/梯子/钉耙）：占着格子就不能种
GRID_ITEM_NAMES = {1: '墓碑', 2: '弹坑', 3: '梯子', 4: '传送门', 5: '传送门',
                   7: '罐子', 10: '蜗牛', 11: '钉耙', 12: '脑子'}
ZOMBIE_NAME_BY_TYPE = {
    0: '普通僵尸', 1: '旗帜僵尸', 2: '路障僵尸', 3: '撑杆僵尸', 4: '铁桶僵尸',
    5: '读报僵尸', 6: '铁门僵尸', 7: '橄榄球僵尸', 8: '舞王僵尸', 9: '伴舞僵尸',
    10: '鸭子僵尸', 11: '潜水僵尸', 12: '冰车僵尸', 13: '雪橇僵尸', 14: '海豚僵尸',
    15: '小丑僵尸', 16: '气球僵尸', 17: '矿工僵尸', 18: '跳跳僵尸', 19: '雪人僵尸',
    20: '蹦极僵尸', 21: '梯子僵尸', 22: '投篮僵尸', 23: '白眼巨人', 24: '小鬼僵尸',
    25: '僵王博士', 26: '豌豆僵尸', 27: '坚果僵尸', 28: '辣椒僵尸', 29: '机枪僵尸',
    30: '窝瓜僵尸', 31: '高坚果僵尸', 32: '红眼巨人'}
VASE_ITEM_TYPE = 7
LEVER_XY = (660, 200)   # 老虎机把手（逻辑坐标 800x600，实测命中）
BLOCKING_GRID_ITEMS = frozenset({1, 2, 3, 7})   # 墓碑/弹坑/梯子/罐子 都不能种；钉耙不影响


# 远程调用 AddPlant 会跳过部分初始化：阳光菇(9) 的 state_countdown 被写成 1，
# 下一帧就"长大"。种下后补成 2500（25 秒），和其它植物一致。
PLANT_INIT_STATE_COUNTDOWN = {9: 12000}   # 阳光菇：小形态持续 120 秒（游戏原生值，实测 11993）


PLANT_INIT_STATE = {9: 23}   # 阳光菇：小形态


def ui_click(g: Any, x: float, y: float, gap: float = 0.35) -> str:
    """界面点击：优先直接调 WidgetManager::MouseDown，失败再投递。返回使用的方式。"""
    try:
        widget_mousedown(g, int(x), int(y))
        time.sleep(gap)
        return 'widget'
    except Exception:
        post_click(g, x, y, gap=gap)
        return 'post'


def widget_mousedown(g: Any, x: int, y: int, button: int = 1) -> Any:
    """直接调 WidgetManager::MouseDown(0x539390)：传逻辑坐标，不依赖窗口模式。"""
    from pvztools.control.asm import Asm
    app = _u32(0x6A9EC0)
    wm = _u32(app + 0x320)
    if not wm:
        raise RuntimeError('no widget manager')
    ex = g.actions.executor
    code = Asm()
    code.push_imm32(int(button))
    code.mov_reg_imm32('eax', int(x))
    code.mov_reg_imm32('edi', int(y))
    # MouseDown(this=ECX=wm, x=EAX, y=stack? ) —— 实测签名: ecx=wm, eax=x, push y, ebx=button
    code2 = Asm()
    code2.push_imm32(int(y))
    code2.mov_reg_imm32('eax', int(x))
    code2.mov_reg_imm32('ebx', int(button))
    code2.mov_reg_imm32('ecx', wm)
    code2.call_abs(0x539390)
    return ex.run(code2, timeout_ms=2000)


def board_mousedown(g: Any, board: int, x: int, y: int, click_count: int = 1) -> Any:
    """远程调用 Board::MouseDown(0x411F20)：走游戏自己的点击流程。"""
    from pvztools.control.asm import Asm
    ex = g.actions.executor
    code = Asm()
    code.push_imm32(int(click_count))
    code.push_imm32(int(y))
    code.push_imm32(int(x))
    code.mov_reg_imm32('ecx', int(board))
    code.call_abs(0x411F20)
    return ex.run(code, timeout_ms=2000)


def cell_pixel(row: int, col: int, scene: int) -> tuple:
    """格子中心像素（与游戏一致：日/夜/屋顶行高 100，池塘/浓雾 85）。"""
    x = 80 + 80 * int(col)
    step = 85 if int(scene) in (2, 3) else 100
    y = 40 + step * int(row) + (step // 2)
    return x, y


def plant_remote(g: Any, ptype: int, row: int, col: int) -> Any:
    """远程 AddPlant；对需要特殊初始化的植物，在**同一个远程调用内**写完字段。

    为什么不能种完再写：AddPlant 会把 state_countdown 初始化成 1，
    游戏在下一帧就判定"长大"，动画也按大形态建好；事后再改字段只会
    出现"逻辑是小形态、模型是大形态且动画停止"的鬼样子。
    放在同一次调用里，游戏线程还没走下一帧，动画会按小形态建立。
    """
    from pvztools.control.asm import Asm
    ex = g.actions.executor
    va = ex.function_va('put_plant')
    board = _u32(_u32(0x6A9EC0) + 0x768)
    code = Asm()
    code.push_imm32(0xFFFFFFFF)      # imitater type = -1
    code.push_imm32(int(ptype))
    code.mov_reg_imm32('eax', int(row))
    code.push_imm32(int(col))
    code.mov_reg_imm32('ebp', int(board))
    code.push_reg('ebp')
    code.call_abs(va)
    countdown = PLANT_INIT_STATE_COUNTDOWN.get(int(ptype))
    if countdown is not None:
        code.mov_regdisp_imm32('eax', 0x54, int(countdown))
        code.mov_regdisp_imm32('eax', 0x3C, PLANT_INIT_STATE.get(int(ptype), 23))
    return ex.run(code, timeout_ms=3000)


def fix_plant_init(row: int, col: int, ptype: int) -> bool:
    """按格子找到刚种下的植物，修正需要补初始化的字段。"""
    want = PLANT_INIT_STATE_COUNTDOWN.get(int(ptype))
    if want is None:
        return False
    try:
        app = _u32(0x6A9EC0)
        board = _u32(app + 0x768)
        if not board:
            return False
        arr = _u32(board + 0xAC)
        cap = int.from_bytes(_read(board + 0xB0, 4), 'little', signed=True)
        if not arr or cap <= 0:
            return False
        for i in range(min(cap, 256)):
            e = arr + 0x14C * i
            if (int.from_bytes(_read(e + 0x1C, 4), 'little', signed=True) == int(row)
                    and int.from_bytes(_read(e + 0x28, 4), 'little', signed=True) == int(col)
                    and int.from_bytes(_read(e + 0x24, 4), 'little', signed=True) == int(ptype)
                    and int.from_bytes(_read(e + 0x40, 4), 'little', signed=True) > 0):
                ok1 = _write(e + 0x54, int(want).to_bytes(4, 'little', signed=True))   # 倒计时
                ok2 = _write(e + 0x3C, (23).to_bytes(4, 'little', signed=True))        # 小形态
                return bool(ok1 and ok2)
    except Exception:
        pass
    return False


def read_grid_items() -> List[Dict[str, Any]]:
    """读 Board.mGridItems（stride 0xEC：type +0x8, col +0x10, row +0x14, dead +0x20）。"""
    out: List[Dict[str, Any]] = []
    try:
        app = _u32(0x6A9EC0)
        board = _u32(app + 0x768)
        if not board:
            return out
        arr = _u32(board + 0x11C)
        cap = int.from_bytes(_read(board + 0x120, 4), 'little', signed=True)
        if not arr or cap <= 0:
            return out
        cap = min(cap, 256)
        blob = _read(arr, 0xEC * cap)
        if len(blob) < 0xEC:
            return out
        for i in range(cap):
            b = 0xEC * i
            if b + 0x24 > len(blob):
                break
            dead = blob[b + 0x20]
            if dead:
                continue
            t = int.from_bytes(blob[b + 0x8:b + 0xC], 'little', signed=True)
            if t <= 0:
                continue
            col = int.from_bytes(blob[b + 0x10:b + 0x14], 'little', signed=True)
            row = int.from_bytes(blob[b + 0x14:b + 0x18], 'little', signed=True)
            if not (0 <= row <= 5 and 0 <= col <= 12):   # 传送门可能出现在第 9 列
                continue
            rec = {'row': row, 'col': col, 'type': t,
                   'name': GRID_ITEM_NAMES.get(t, 'type:%d' % t),
                   'blocking': t in BLOCKING_GRID_ITEMS}
            if t == VASE_ITEM_TYPE:
                # 罐子内容：0x3C 僵尸类型 / 0x40 植物类型 / 0x44 罐子种类(1植物 2僵尸)
                zt = int.from_bytes(blob[b + 0x3C:b + 0x40], 'little', signed=True)
                pt = int.from_bytes(blob[b + 0x40:b + 0x44], 'little', signed=True)
                kind = int.from_bytes(blob[b + 0x44:b + 0x48], 'little', signed=True)
                if zt >= 0:
                    rec['vase_kind'] = 'zombie'
                    rec['zombie_type'] = zt
                    rec['zombie'] = ZOMBIE_NAME_BY_TYPE.get(zt, 'zombie:%d' % zt)
                elif pt >= 0:
                    rec['vase_kind'] = 'plant'
                    rec['plant_type'] = pt
                    rec['plant'] = plant_name_by_type(pt)
                else:
                    rec['vase_kind'] = 'unknown'
                rec['vase_tag'] = kind
            out.append(rec)
    except Exception:
        pass
    return out

if __name__ == '__main__':
    srv = ThreadingHTTPServer(('127.0.0.1', PORT), Handler)
    print('pvz-bridge listening on http://127.0.0.1:%d' % PORT, flush=True)
    srv.serve_forever()
