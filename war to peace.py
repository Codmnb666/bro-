# -*- coding: utf-8 -*-
"""
钢铁雄心 · 简化版 v7.1 —— 抗战 + 军/流派 + 补给 + 天气 + 历史事件 + 空军/海军 + 将领培养 + 跨省编军 + 战略轰炸 + 防御工事

v7.0:
 A. 跨省编军: Shift+左键 追加多选, 可在任意省份组建集团军
 B. 多选省份淡黄高亮显示
 C. 「军」标签新增清空选择按钮, ESC 一键清空多选
 D. 原单省编军方式完整保留

v7.1 新增:
 A. 战略轰炸可对驻守敌军造成兵力/组织伤害, 兵力 ≤5 直接歼灭
 B. 防御工事 Lv1~Lv5, 每级 +12% 防御; 山脉/要塞削弱空袭
 C. 地图右下角竖条显示工事等级; AI 也会在边境修建工事
"""
import sys, math, random, pickle, heapq, os
from dataclasses import dataclass, field
from collections import defaultdict, deque
import pygame

# ============ 基础 ============
MAP_W, MAP_H = 40, 26
TILE = 26
MAP_PX_W, MAP_PX_H = MAP_W * TILE, MAP_H * TILE
PANEL_W = 340
SCREEN_W = MAP_PX_W + PANEL_W
SCREEN_H = MAP_PX_H
FPS = 60
SEA_COLOR = (26, 44, 72)
NEUTRAL_COLOR = (108, 108, 116)
BORDER_COLOR = (18, 20, 26)
SPEED_HOURS = [0, 8, 24, 72, 240]
DIV_UPKEEP_EQUIP = 1.2
COMBAT_WIDTH = 4
SUPPLY_BASE = 4.0
SUPPLY_LOSS_ORG = 1.6
SUPPLY_LOSS_STR = 0.9
SAVE_VERSION = 7
SAVE_FMT = "hoi_lite_save_slot{}.pkl"

# ---- 天气 ----
WEATHER_DEFS = {
    'clear': {'name': '晴朗', 'move': 1.00, 'attack': 1.00, 'color': (200, 220, 240)},
    'rain':  {'name': '降雨', 'move': 0.75, 'attack': 0.92, 'color': (140, 170, 200)},
    'snow':  {'name': '降雪', 'move': 0.55, 'attack': 0.80, 'color': (230, 240, 250)},
    'storm': {'name': '风暴', 'move': 0.60, 'attack': 0.86, 'color': (100, 120, 150)},
}

# ============ 地图 ============
OWNER_MAP = [
    ".............#####......................",
    "........2222222222...##.......33...33...",
    "..11100000000.####...3333333333333333333",
    "..11100000000..###...3333333333333333333",
    ".1111000000000..##.##.443333333333333333",
    "....1111111111......44333333333333355555",
    "....1111111111.....443333333335555555555",
    "....111111111......22222222..0000000055.",
    "....11111111.......22222222.0000000055..",
    ".....######........2222222222222222.55..",
    "......#####.........2222222.2222222.....",
    ".........#####......2222222..22222......",
    ".........######.....2222222.....22222...",
    ".........######......222222.....2222....",
    ".........######......222222....2222222..",
    ".........#######.....222222....2222222..",
    "..........######.....222222....222222...",
    "..........######.....22222.....222222...",
    "..........#####......222........2222.22.",
    "..........####..........................",
    "..........##............................",
    "........................................",
    "........................................",
    "........................................",
    "........................................",
    "........................................",
]
CAPITAL_POSITIONS = {0: (33, 7), 1: (10, 7), 2: (19, 4), 3: (26, 4), 4: (22, 4), 5: (37, 5)}
NATION_DEFS = [
    ("中国",   (195, 75, 70)),
    ("美利坚", (70, 110, 180)),
    ("不列颠", (140, 90, 180)),
    ("苏联",   (200, 60, 60)),
    ("德意志", (130, 135, 145)),
    ("东瀛",   (222, 150, 150)),
]
TERRAIN_INFO = {
    'plains':   {'cost': 1.0, 'def': 1.00, 'label': '平原'},
    'forest':   {'cost': 1.5, 'def': 1.20, 'label': '森林'},
    'mountain': {'cost': 2.2, 'def': 1.42, 'label': '山地'},
    'city':     {'cost': 1.2, 'def': 1.32, 'label': '城市'},
}
UNIT_TYPES = {
    'infantry':  {'name': '步兵师', 'atk': 1.00, 'def': 1.00, 'org': 100, 'speed': 1.00,
                  'equip': 600,  'manpower': 12000, 'days': 2, 'color': (210, 210, 220)},
    'motorized': {'name': '摩步师', 'atk': 1.10, 'def': 1.10, 'org': 110, 'speed': 1.85,
                  'equip': 900,  'manpower': 10000, 'days': 3, 'color': (180, 210, 150)},
    'armor':     {'name': '装甲师', 'atk': 1.70, 'def': 1.25, 'org': 80,  'speed': 1.45,
                  'equip': 1500, 'manpower': 8000,  'days': 5, 'color': (240, 200, 120)},
    'artillery': {'name': '炮兵师', 'atk': 1.55, 'def': 0.75, 'org': 90,  'speed': 0.70,
                  'equip': 900,  'manpower': 6000,  'days': 3, 'color': (220, 160, 140)},
    'airforce':  {'name': '空军联队', 'atk': 0.0, 'def': 0.0, 'org': 60, 'speed': 2.0,
                  'equip': 800,  'manpower': 3000,  'days': 4, 'color': (200, 180, 240),
                  'is_special': 'airforce'},
    'navy':      {'name': '海军舰队', 'atk': 0.0, 'def': 0.0, 'org': 60, 'speed': 1.5,
                  'equip': 1200, 'manpower': 5000,  'days': 6, 'color': (130, 180, 220),
                  'is_special': 'navy'},
}
DOCTRINES = {
    'regular':    {'name': '正规军',   'short': '正规', 'color': (180, 200, 230),
                   'desc': '均衡编制', 'max_size': 25,
                   'attack': 0.00, 'defense': 0.00, 'move': 0.00, 'extra': {}},
    'guerrilla':  {'name': '游击战',   'short': '游击', 'color': (120, 210, 130),
                   'desc': '敌后渗透·无视补给', 'max_size': 25,
                   'attack': -0.25, 'defense': 0.35, 'move': 0.40,
                   'extra': {'ignore_supply': True, 'behind_lines': True,
                             'retreat_bonus': 0.5, 'org_recovery': 0.5}},
    'blitz':      {'name': '闪电战',   'short': '闪击', 'color': (250, 210, 90),
                   'desc': '高攻高速·装甲至上', 'max_size': 25,
                   'attack': 0.30, 'defense': -0.10, 'move': 0.45,
                   'extra': {'armor_bonus': 0.5}},
    'trench':     {'name': '堑壕战',   'short': '堑壕', 'color': (170, 170, 195),
                   'desc': '固若金汤', 'max_size': 25,
                   'attack': -0.15, 'defense': 0.55, 'move': -0.35,
                   'extra': {'org_recovery': 0.3}},
    'mass':       {'name': '人海战术', 'short': '人海', 'color': (220, 130, 130),
                   'desc': '以量取胜·上限 40', 'max_size': 40,
                   'attack': 0.05, 'defense': -0.05, 'move': 0.0,
                   'extra': {'recruit_discount': 0.35}},
    'amphibious': {'name': '海陆两栖', 'short': '两栖', 'color': (100, 190, 230),
                   'desc': '登陆专精', 'max_size': 25,
                   'attack': 0.10, 'defense': 0.0, 'move': 0.10,
                   'extra': {'landing_bonus': 0.5, 'navy_cost': -0.4}},
}

# ---- 科技 ----
@dataclass(frozen=True)
class TechDef:
    id: str; name: str; category: str; cost: float
    requires: tuple; effect: dict; desc: str = ""

TECHS = [
    TechDef('inf_w1', '步兵武器 I',  '陆军', 60,  (),          {'attack': 0.10}, '全军攻击 +10%'),
    TechDef('inf_w2', '步兵武器 II', '陆军', 140, ('inf_w1',),  {'attack': 0.15}, '全军攻击 +15%'),
    TechDef('inf_d1', '防御工事 I',  '陆军', 60,  (),          {'defense': 0.10}, '全军防御 +10%'),
    TechDef('inf_d2', '防御工事 II', '陆军', 140, ('inf_d1',),  {'defense': 0.18}, '全军防御 +18%'),
    TechDef('art_1',  '炮兵支援',    '陆军', 180, ('inf_w2',),  {'attack': 0.12, 'org': 5}, '攻击 +12%，组织 +5'),
    TechDef('arm_1',  '装甲战术',    '陆军', 200, ('inf_w2',),  {'attack': 0.15}, '装甲单位攻击 +15%'),
    TechDef('ind_1',  '机械化采矿',  '工业', 80,  (),          {'industry': 0.15}, '工业产出 +15%'),
    TechDef('ind_2',  '流水线生产',  '工业', 180, ('ind_1',),   {'industry': 0.25}, '工业产出 +25%'),
    TechDef('man_1',  '义务兵役法',  '工业', 90,  (),          {'manpower': 0.20}, '人力产出 +20%'),
    TechDef('man_2',  '总动员',      '工业', 200, ('man_1',),   {'manpower': 0.35}, '人力产出 +35%'),
    TechDef('log_1',  '摩托化运输',  '后勤', 100, (),           {'move': 0.20}, '移动速度 +20%'),
    TechDef('log_2',  '铁路网',      '后勤', 200, ('log_1',),   {'supply': 0.30, 'move': 0.15}, '补给 +30%，移动 +15%'),
    TechDef('nav_1',  '海军运输船',  '后勤', 120, (),           {'navy': 1.0}, '海军 +1/日'),
    TechDef('air_1',  '战略轰炸机',  '后勤', 150, (),           {'airforce': 1.0}, '空军 +1/日'),
]
TECH_BY_ID = {t.id: t for t in TECHS}

@dataclass
class EventDef:
    id: str; name: str; weight: float; effect: dict; desc: str = ""

EVENTS = [
    EventDef('boom',    '工业跃进', 1.0, {'industry': 1, 'pp': 10},   '工厂落成'),
    EventDef('harvest', '农业丰收', 1.0, {'manpower': 40000},         '人力 +40000'),
    EventDef('graft',   '贪腐丑闻', 0.8, {'pp': -15},                 '政治点 -15'),
    EventDef('rally',   '爱国集会', 1.0, {'pp': 25, 'manpower': 15000}, '政治点 +25'),
    EventDef('strike',  '工人罢工', 0.7, {'equipment': -400},         '装备 -400'),
    EventDef('donate',  '民间捐助', 0.8, {'equipment': 800, 'pp': 5},  '装备 +800'),
]

POLICIES = {
    'conscript': {'name': '征兵法案', 'levels': [
        {'name': '志愿兵役', 'manpower': 0.00, 'cost': 0},
        {'name': '义务兵役', 'manpower': 0.25, 'cost': 50},
        {'name': '全民动员', 'manpower': 0.55, 'cost': 130}]},
    'economy': {'name': '经济法案', 'levels': [
        {'name': '民用经济', 'industry': 0.00, 'cost': 0},
        {'name': '部分动员', 'industry': 0.20, 'cost': 70},
        {'name': '战时经济', 'industry': 0.45, 'cost': 160}]},
}

# ---- 将领名字池 ----
GENERAL_NAMES = {
    0: ['朱绍良','李宗仁','白崇禧','傅作义','陈诚','薛岳','卫立煌','孙立人','杜聿明','廖耀湘'],
    1: ['巴顿','马歇尔','艾森豪威尔','布莱德雷','尼米兹','麦克阿瑟','哈尔西','史迪威','克拉克','李奇微'],
    2: ['蒙哥马利','亚历山大','韦维尔','奥金莱克','坎宁安','蒙巴顿','斯利姆','布鲁克','哈里斯','道丁'],
    3: ['朱可夫','罗科索夫斯基','科涅夫','华西列夫斯基','崔可夫','瓦图京','马利诺夫斯基','戈沃罗夫','叶廖缅科','巴格拉米扬'],
    4: ['古德里安','隆美尔','曼施坦因','伦德施泰特','莫德尔','博克','克莱斯特','哈尔德','邓尼茨','凯塞林'],
    5: ['东乡','山田','田中','松本','冈部','山下','冈村','板垣','土肥原','南云'],
}

# ---- 历史事件链 ----
HISTORICAL_EVENTS = [
    {'id': 'marco_polo', 'date': (1937, 7, 7), 'name': '卢沟桥事变',
     'desc': '日军借口士兵失踪炮击宛平城，中日全面战争爆发。',
     'run': lambda g: (g.declare_war(5, 0),
                       g.nations[5].manpower.__iadd__(30000) if 5 in g.nations else None)},
    {'id': 'shanghai',   'date': (1937, 8, 13), 'name': '淞沪会战',
     'desc': '中日双方在上海投入重兵，血战三个月。',
     'run': lambda g: g.spawn_divisions_at(5, 5, 4, 'infantry')},
    {'id': 'nanjing',    'date': (1937, 12, 13), 'name': '南京保卫战',
     'desc': '首都南京陷入危机，全国军民誓死抵抗。',
     'run': lambda g: (g.give_pp(0, 40), g.toast("南京告急！", (240, 120, 100)))},
    {'id': 'wuhan',      'date': (1938, 6, 11), 'name': '武汉会战',
     'desc': '抗战进入相持阶段。',
     'run': lambda g: g.give_manpower(0, 50000)},
    {'id': 'barbarossa', 'date': (1941, 6, 22), 'name': '巴巴罗萨行动',
     'desc': '德国发动对苏全面进攻。',
     'run': lambda g: g.declare_war(4, 3)},
    {'id': 'pearl',      'date': (1941, 12, 7), 'name': '珍珠港事件',
     'desc': '日本偷袭珍珠港，太平洋战争爆发。',
     'run': lambda g: (g.declare_war(5, 1), g.declare_war(5, 2),
                       g.declare_war(1, 5), g.declare_war(2, 5))},
    {'id': 'stalingrad', 'date': (1942, 8, 23), 'name': '斯大林格勒战役',
     'desc': '苏德两军在伏尔加河畔殊死搏斗。',
     'run': lambda g: g.give_pp(3, 30)},
    {'id': 'dday',       'date': (1944, 6, 6), 'name': '诺曼底登陆',
     'desc': '盟军在西欧开辟第二战场。',
     'run': lambda g: (g.give_pp(1, 40), g.give_pp(2, 40))},
]

# ============ 数据结构 ============
@dataclass
class Province:
    x: int; y: int
    land: bool = False
    owner: int = -1
    terrain: str = 'plains'
    vp: int = 0
    capital_of: int = -1
    divisions: list = field(default_factory=list)
    industry: int = 1
    resource: int = 1
    supply_cap: float = SUPPLY_BASE
    original_owner: int = -1
    fort: int = 0

@dataclass(eq=False)
class Division:
    owner: int; x: int; y: int
    unit_type: str = 'infantry'
    strength: float = 100.0
    org: float = 100.0
    max_org: float = 100.0
    tx: int = -1; ty: int = -1
    move_progress: float = 0.0
    path: list = field(default_factory=list)
    in_combat: bool = False
    army_id: int = -1
    experience: float = 0.0

    @property
    def has_target(self): return self.tx >= 0
    @property
    def info(self): return UNIT_TYPES.get(self.unit_type, UNIT_TYPES['infantry'])

@dataclass(eq=False)
class Army:
    id: int; owner: int; name: str
    doctrine: str = 'regular'
    divisions: list = field(default_factory=list)
    general_id: int = -1
    def size(self): return len(self.divisions)
    def max_size(self): return DOCTRINES[self.doctrine].get('max_size', 25)

@dataclass(eq=False)
class TrainOrder:
    x: int; y: int; days: int; unit_type: str = 'infantry'

@dataclass
class General:
    id: int; name: str; level: int
    attack: float; defense: float; logistics: float
    assigned_army: int = -1
    experience: float = 0.0
    kills: int = 0

@dataclass
class Nation:
    id: int; name: str; color: tuple
    pp: float = 60.0; civ: int = 5; mil: int = 3
    manpower: float = 60000.0; equipment: float = 4000.0
    navy: float = 3.0; airforce: float = 3.0
    is_ai: bool = True; alive: bool = True
    surrendered: bool = False
    build_type: str = ""; build_progress: float = 0.0
    train_queue: list = field(default_factory=list)
    research_points: float = 0.0; active_research: str = ""
    completed_techs: tuple = (); bonuses: dict = field(default_factory=dict)
    wars: set = field(default_factory=set)
    relations: dict = field(default_factory=dict)
    policies: dict = field(default_factory=lambda: {'conscript': 0, 'economy': 0})
    generals: list = field(default_factory=list)
    active_general_id: int = -1
    war_score: float = 0.0
    @property
    def active_general(self):
        for g in self.generals:
            if g.id == self.active_general_id: return g
        return None

# ============ 字体 ============
_font_cache = {}
def load_font(size, bold=False):
    key = (size, bold)
    if key in _font_cache: return _font_cache[key]
    candidates = ['microsoftyaheiui','microsoftyahei','simhei','simsun','msyh',
                  'pingfangsc','hiraginosansgb','notosanscjksc','wenquanyimicrohei',
                  'arialunicodems','dejavusans']
    font = None
    for name in candidates:
        try: path = pygame.font.match_font(name, bold=bold)
        except Exception: path = None
        if path:
            try: font = pygame.font.Font(path, size); break
            except Exception: continue
    if font is None: font = pygame.font.SysFont(None, size, bold=bold)
    _font_cache[key] = font
    return font

# ============================================================
#                        GAME
# ============================================================
class Game:
    def __init__(self):
        random.seed(1937)
        self.prov = [[Province(x, y) for y in range(MAP_H)] for x in range(MAP_W)]
        self.nations = {}
        self.capitals = {}
        self.year, self.month, self.day, self.hour = 1937, 1, 1, 0
        self.speed = 1
        self.hour_accum = 0.0
        self.ai_timer = 0
        self.event_timer = 0
        self.selected = None
        self.selected_divs = []
        self.hover = None
        self.buttons = {}
        self.log = []
        self.toasts = []
        self.map_dirty = True
        self.map_surface = None
        self.total_destroyed = 0
        self.cheat_open = False
        self.cheats = {'infinite_res': False, 'instant_build': False, 'instant_train': False,
                       'god_mode': False, 'fast_move': False}
        self.cheat_rows = []
        self.cheat_panel_rect = pygame.Rect(20, 20, 340, 400)
        self.ui_tab = 'overview'
        self.recruit_type = 'infantry'
        self.target_mode = None
        self.research_buttons = {}
        self.policy_buttons = {}
        self.general_buttons = {}
        self.diplomacy_buttons = {}
        self.army_buttons = {}
        self.armies = {}
        self.next_army_id = 1
        self.selected_army = -1
        self.wars = set()
        self.cut_off_provs = defaultdict(set)
        self.weather = 'clear'
        self.weather_timer = 0
        self.fired_events = set()
        self.save_slot = 1
        self.panel_scroll = 0
        self.panel_max_scroll = 0
        self.panel_content_top = 100
        self.effects = []
        self.setup_world()

    # ---------------- 世界生成 ----------------
    def setup_world(self):
        self.generate_terrain()
        self.assign_owners()
        self.pick_capitals()
        self.setup_nations()
        self.compute_supply_caps()
        self.spawn_initial_units()
        self.init_diplomacy()
        self.update_weather(force=True)
        self.log_msg("1937 年，六大强国逐鹿世界。")
        self.log_msg("提示: 按 ~ 或 G 打开作弊控制台。")
        if 5 in self.nations and 0 in self.nations:
            self.declare_war(5, 0)
            self.log_msg("边境冲突升级，东瀛向中国发动全面进攻！")
            self.toast("抗战爆发！", (255, 120, 100))

    def generate_terrain(self):
        for y in range(MAP_H):
            row = OWNER_MAP[y] if y < len(OWNER_MAP) else "." * MAP_W
            for x in range(MAP_W):
                p = self.prov[x][y]
                ch = row[x] if x < len(row) else "."
                p.land = (ch != '.')
        for y in range(MAP_H):
            for x in range(MAP_W):
                p = self.prov[x][y]
                if not p.land: continue
                r = random.random()
                if r < 0.10: p.terrain = 'mountain'
                elif r < 0.38: p.terrain = 'forest'
                else: p.terrain = 'plains'
                p.vp = random.choice([1,1,1,2,2,3])
                p.industry = random.choice([1,1,2,2,3])
                p.resource = random.choice([1,2,2,3])

    def assign_owners(self):
        for y in range(MAP_H):
            row = OWNER_MAP[y] if y < len(OWNER_MAP) else "." * MAP_W
            for x in range(MAP_W):
                p = self.prov[x][y]
                if not p.land: continue
                ch = row[x] if x < len(row) else "."
                if ch == '#': p.owner = random.randint(0, 4)
                elif ch in '012345': p.owner = int(ch)
                else: p.owner = 0
                p.original_owner = p.owner

    def pick_capitals(self):
        for i, (cx, cy) in CAPITAL_POSITIONS.items():
            p = None
            if 0 <= cx < MAP_W and 0 <= cy < MAP_H:
                cand = self.prov[cx][cy]
                if cand.land and cand.owner == i: p = cand
            if p is None:
                best, bd = None, 1e9
                for y in range(MAP_H):
                    for x in range(MAP_W):
                        q = self.prov[x][y]
                        if q.land and q.owner == i:
                            dd = (x-cx)**2 + (y-cy)**2
                            if dd < bd: bd, best = dd, q
                p = best
            if p is None: continue
            p.capital_of = i; p.terrain = 'city'; p.vp += 5; p.fort = 3
            self.capitals[i] = (p.x, p.y)

    def setup_nations(self):
        for i, (name, color) in enumerate(NATION_DEFS):
            provs = self.provinces_of(i)
            if not provs: continue
            n = Nation(i, name, color)
            n.civ = 3 + len(provs)//8
            n.mil = 2 + len(provs)//12
            n.is_ai = (i != 0)
            n.generals = self.make_generals(i)
            if i == 5:
                n.civ += 3; n.mil += 3; n.equipment += 3000
                n.manpower += 60000; n.navy += 8.0; n.airforce += 6.0
            self.nations[i] = n

    def make_generals(self, nid):
        names = GENERAL_NAMES.get(nid, [])
        pool = random.sample(names, min(3, len(names))) if names else [f"将领{nid}-{i}" for i in range(3)]
        out = []
        for k, nm in enumerate(pool):
            lv = random.randint(1, 4)
            out.append(General(nid*100+k, nm, lv,
                round(0.05*lv*random.uniform(0.8,1.2),3),
                round(0.05*lv*random.uniform(0.8,1.2),3),
                round(0.04*lv*random.uniform(0.8,1.2),3)))
        return out

    def init_diplomacy(self):
        ids = list(self.nations.keys())
        for a in ids: self.nations[a].relations = {}
        for i in ids:
            for j in ids:
                if i != j:
                    self.nations[i].relations[j] = random.randint(-20, 20)

    def compute_supply_caps(self):
        for y in range(MAP_H):
            for x in range(MAP_W):
                p = self.prov[x][y]
                if not p.land: continue
                cap = SUPPLY_BASE + p.industry*0.6
                if p.capital_of >= 0: cap += 4.0
                if p.terrain == 'city': cap += 2.0
                if p.owner >= 0 and p.owner in self.capitals:
                    cx, cy = self.capitals[p.owner]
                    cap -= (abs(p.x-cx) + abs(p.y-cy)) * 0.10
                p.supply_cap = max(1.5, cap)

    def spawn_initial_units(self):
        for i in self.nations:
            provs = self.provinces_of(i)
            if not provs: continue
            cx, cy = self.capitals.get(i, (provs[0].x, provs[0].y))
            for _ in range(4): self.add_division(i, cx, cy, 'infantry')
            for p in provs:
                if (p.x, p.y) == (cx, cy): continue
                if random.random() < 0.22: self.add_division(i, p.x, p.y, 'infantry')
            if i == 5:
                for _ in range(4): self.add_division(i, cx, cy, 'infantry')
                for _ in range(2): self.add_division(i, cx, cy, 'motorized')
                self.add_division(i, cx, cy, 'armor')
                extra = [(p.x, p.y) for p in provs if p.y <= 6 and random.random() < 0.4]
                for (px, py) in extra[:4]:
                    self.add_division(i, px, py, random.choice(['infantry', 'motorized']))

    # ---------------- 工具 ----------------
    def add_division(self, owner, x, y, unit_type='infantry'):
        d = Division(owner=owner, x=x, y=y, unit_type=unit_type)
        n = self.nations.get(owner)
        base_org = UNIT_TYPES.get(unit_type, UNIT_TYPES['infantry'])['org']
        d.max_org = base_org + (n.bonuses.get('org', 0.0) if n else 0.0)
        d.org = d.max_org
        self.prov[x][y].divisions.append(d)
        return d

    def all_divisions(self):
        for row in self.prov:
            for p in row:
                for d in p.divisions: yield d

    def provinces_of(self, nid):
        return [p for row in self.prov for p in row if p.owner == nid]

    def neighbors(self, x, y):
        for dx, dy in ((1,0), (-1,0), (0,1), (0,-1)):
            nx, ny = x+dx, y+dy
            if 0 <= nx < MAP_W and 0 <= ny < MAP_H:
                yield nx, ny

    def log_msg(self, msg):
        self.log.append(msg)
        if len(self.log) > 12: self.log.pop(0)

    def toast(self, msg, color=(240, 220, 130)):
        self.toasts.append({'msg': msg, 'color': color, 't': 0.0})

    # ---------------- 战争 ----------------
    def at_war(self, a, b):
        if a == b: return False
        return frozenset((a, b)) in self.wars

    def declare_war(self, a, b):
        if a == b: return
        na, nb = self.nations.get(a), self.nations.get(b)
        if not na or not nb: return
        key = frozenset((a, b))
        if key in self.wars: return
        self.wars.add(key)
        na.wars.add(b); nb.wars.add(a)
        na.relations[b] = -80
        nb.relations[a] = -80
        self.log_msg(f"{na.name} 向 {nb.name} 宣战！")
        self.toast(f"{na.name} → {nb.name}  宣战", (240, 120, 100))

    def make_peace(self, a, b):
        na, nb = self.nations.get(a), self.nations.get(b)
        if not na or not nb: return
        self.wars.discard(frozenset((a, b)))
        na.wars.discard(b); nb.wars.discard(a)
        na.relations[b] = max(na.relations.get(b, 0), -20)
        nb.relations[a] = max(nb.relations.get(a, 0), -20)
        self.log_msg(f"{na.name} 与 {nb.name} 达成停战。")

    # ---------------- 寻路 ----------------
    def find_path(self, sx, sy, gx, gy):
        if (sx, sy) == (gx, gy): return []
        if not (0 <= gx < MAP_W and 0 <= gy < MAP_H): return []
        if not self.prov[gx][gy].land: return []
        open_set = [(0.0, (sx, sy))]
        came = {}; g_score = {(sx, sy): 0.0}; closed = set()
        while open_set:
            _, cur = heapq.heappop(open_set)
            if cur in closed: continue
            closed.add(cur)
            if cur == (gx, gy):
                path = []
                while cur in came:
                    path.append(cur); cur = came[cur]
                path.reverse(); return path
            cx, cy = cur
            for nx, ny in self.neighbors(cx, cy):
                if (nx, ny) in closed: continue
                q = self.prov[nx][ny]
                if not q.land: continue
                cost = TERRAIN_INFO[q.terrain]['cost']
                tentative = g_score[cur] + cost
                if (nx, ny) not in g_score or tentative < g_score[(nx, ny)]:
                    came[(nx, ny)] = cur
                    g_score[(nx, ny)] = tentative
                    h = abs(nx-gx) + abs(ny-gy)
                    heapq.heappush(open_set, (tentative+h, (nx, ny)))
        return []

    def sea_route(self, sx, sy, gx, gy, max_steps=14):
        if not self.coastal(sx, sy) or not self.coastal(gx, gy): return None
        starts = [(nx, ny) for nx, ny in self.neighbors(sx, sy) if not self.prov[nx][ny].land]
        goals  = set((nx, ny) for nx, ny in self.neighbors(gx, gy) if not self.prov[nx][ny].land)
        if not starts or not goals: return None
        visited = set(starts)
        q = deque([(s, [s]) for s in starts])
        while q:
            cur, path = q.popleft()
            if cur in goals: return path
            if len(path) > max_steps: continue
            cx, cy = cur
            for nx, ny in self.neighbors(cx, cy):
                if (nx, ny) in visited: continue
                if self.prov[nx][ny].land: continue
                visited.add((nx, ny))
                q.append(((nx, ny), path + [(nx, ny)]))
        return None

    def coastal(self, x, y):
        p = self.prov[x][y]
        if not p.land: return False
        return any(not self.prov[nx][ny].land for nx, ny in self.neighbors(x, y))

    def prune_selected(self):
        if not self.selected_divs: return
        alive = set(self.all_divisions())
        self.selected_divs = [d for d in self.selected_divs if d in alive]

    # ---------------- 军 / 流派 ----------------
    def get_doctrine_effects(self, d):
        if d.army_id < 0: return None
        a = self.armies.get(d.army_id)
        if not a: return None
        return DOCTRINES.get(a.doctrine)

    def create_army_from_selected(self, owner=0, divs=None):
        if divs is None: divs = self.selected_divs
        free = [d for d in divs if d.owner == owner and d.army_id < 0]
        if not free:
            if owner == 0: self.toast("没有可编组的师", (240, 120, 100))
            return None
        aid = self.next_army_id; self.next_army_id += 1
        cnt = sum(1 for a in self.armies.values() if a.owner == owner) + 1
        cap = DOCTRINES['regular']['max_size']
        army = Army(id=aid, owner=owner, name=f"第{cnt}集团军", divisions=list(free[:cap]))
        for d in army.divisions: d.army_id = aid
        self.armies[aid] = army
        if owner == 0:
            self.selected_army = aid
            self.selected_divs = list(army.divisions)
            tiles = len({(d.x, d.y) for d in army.divisions})
            if tiles > 1:
                self.toast(f"编成 {army.name}（{army.size()} 师 / 跨 {tiles} 省）", (150, 230, 150))
            else:
                self.toast(f"编成 {army.name}（{army.size()} 师）", (150, 230, 150))
        return army

    def disband_army(self, aid):
        a = self.armies.get(aid)
        if not a: return
        for d in a.divisions: d.army_id = -1
        if a.general_id >= 0:
            for g in self.nations[a.owner].generals:
                if g.id == a.general_id: g.assigned_army = -1
        del self.armies[aid]
        if self.selected_army == aid:
            self.selected_army = -1; self.selected_divs = []
        self.toast(f"{a.name} 已解散", (200, 200, 200))

    def set_army_doctrine(self, aid, doctrine):
        a = self.armies.get(aid)
        if not a or doctrine not in DOCTRINES: return
        new_max = DOCTRINES[doctrine]['max_size']
        a.doctrine = doctrine
        if a.size() > new_max:
            for d in a.divisions[new_max:]: d.army_id = -1
            a.divisions = a.divisions[:new_max]
        if a.owner == 0:
            self.toast(f"{a.name} → {DOCTRINES[doctrine]['name']}", DOCTRINES[doctrine]['color'])

    def assign_general(self, aid, gid):
        a = self.armies.get(aid)
        n = self.nations.get(a.owner) if a else None
        if not a or not n: return
        for g in n.generals:
            if g.assigned_army == aid: g.assigned_army = -1
        a.general_id = gid
        for g in n.generals:
            if g.id == gid:
                g.assigned_army = aid
                if a.owner == 0:
                    self.toast(f"{g.name} 就任 {a.name}", (240, 220, 140))
                return

    def select_army(self, aid):
        a = self.armies.get(aid)
        if not a: return
        self.selected_army = aid
        self.selected_divs = list(a.divisions)

    def cleanup_armies(self):
        alive = set(self.all_divisions())
        for aid, a in list(self.armies.items()):
            a.divisions = [d for d in a.divisions if d in alive]
            if not a.divisions:
                del self.armies[aid]

    # ---------------- 将领培养 ----------------
    def recruit_general(self, nation):
        if nation is None: return None
        cost = 100
        if nation.pp < cost:
            if nation.id == 0: self.toast("政治点不足 (需 100)", (240, 120, 100))
            return None
        nation.pp -= cost
        used = {g.name for g in nation.generals}
        pool = [n for n in GENERAL_NAMES.get(nation.id, []) if n not in used]
        if pool:
            name = random.choice(pool)
        else:
            name = f"将领{nation.id}-{len(nation.generals)+1}"
        seq = len(nation.generals)
        g = General(
            id=nation.id*100 + 100 + seq, name=name, level=1,
            attack=round(0.03*random.uniform(0.8, 1.2), 3),
            defense=round(0.03*random.uniform(0.8, 1.2), 3),
            logistics=round(0.02*random.uniform(0.8, 1.2), 3),
        )
        nation.generals.append(g)
        if nation.id == 0:
            self.log_msg(f"招募新将领: {g.name}")
            self.toast(f"新将领就任: {g.name}", (170, 220, 255))
        return g

    def tick_general_xp(self):
        for aid, a in self.armies.items():
            if a.general_id < 0 or not a.divisions: continue
            if not any(d.in_combat for d in a.divisions): continue
            n = self.nations.get(a.owner)
            if not n: continue
            for g in n.generals:
                if g.id != a.general_id: continue
                g.experience += 0.6
                need = 60.0 * g.level
                while g.experience >= need:
                    g.experience -= need
                    g.level += 1
                    g.attack = round(g.attack + 0.03, 3)
                    g.defense = round(g.defense + 0.03, 3)
                    g.logistics = round(g.logistics + 0.02, 3)
                    if n.id == 0:
                        self.toast(f"★ {g.name} 晋升 Lv.{g.level}", (255, 220, 120))
                        self.log_msg(f"{g.name} 晋升 Lv.{g.level}")
                    need = 60.0 * g.level
                break
            if n.id == 0: self.recompute_bonuses(n)

    def draw_effects(self, screen):
        for ef in self.effects:
            if ef['type'] != 'explosion': continue
            px = ef['x']*TILE + TILE//2
            py = ef['y']*TILE + TILE//2
            t = ef['t']
            if t < 0.12:
                s = pygame.Surface((TILE*2, TILE*2), pygame.SRCALPHA)
                a = int(220 * (1 - t/0.12))
                s.fill((255, 255, 210, a))
                screen.blit(s, (px - TILE, py - TILE))
            for r_off, color in ((0, (255, 220, 100)), (6, (255, 130, 60)), (12, (170, 50, 40))):
                radius = int(6 + t * 26 + r_off)
                alpha = max(0, int(255 * (1 - t/1.2)))
                if alpha <= 0 or radius <= 0: continue
                surf = pygame.Surface((radius*2+4, radius*2+4), pygame.SRCALPHA)
                pygame.draw.circle(surf, (*color, alpha), (radius+2, radius+2), radius, 3)
                screen.blit(surf, (px - radius - 2, py - radius - 2))

    # ---------------- 科技 ----------------
    def recompute_bonuses(self, nation):
        b = {'attack':0.0,'defense':0.0,'org':0.0,'industry':0.0,'manpower':0.0,
             'move':0.0,'supply':0.0,'navy':0.0,'airforce':0.0}
        for tid in nation.completed_techs:
            t = TECH_BY_ID.get(tid)
            if not t: continue
            for k, v in t.effect.items(): b[k] = b.get(k, 0.0) + v
        for pk, pdef in POLICIES.items():
            lv = max(0, min(nation.policies.get(pk, 0), len(pdef['levels'])-1))
            for k, v in pdef['levels'][lv].items():
                if k in ('name', 'cost'): continue
                b[k] = b.get(k, 0.0) + v
        g = nation.active_general
        if g:
            b['attack'] += g.attack; b['defense'] += g.defense; b['move'] += g.logistics
        nation.bonuses = b
        for row in self.prov:
            for p in row:
                for d in p.divisions:
                    if d.owner == nation.id:
                        base_org = UNIT_TYPES.get(d.unit_type, UNIT_TYPES['infantry'])['org']
                        d.max_org = base_org + b.get('org', 0.0)
                        if d.org > d.max_org: d.org = d.max_org

    def available_techs(self, nation):
        done = set(nation.completed_techs)
        return [t for t in TECHS
                if t.id not in done and t.id != nation.active_research
                and all(r in done for r in t.requires)]

    def start_research(self, nation, tech_id):
        if nation.active_research: return
        t = TECH_BY_ID.get(tech_id)
        if not t: return
        if any(r not in nation.completed_techs for r in t.requires): return
        if t.id in nation.completed_techs: return
        nation.active_research = t.id
        nation.research_points = 0.0

    def cancel_research(self, nation):
        if nation.active_research:
            nation.active_research = ""
            nation.research_points = 0.0
            if nation.id == 0: self.toast("研究已取消", (200, 200, 200))

    def tick_research(self, nation):
        if not nation.active_research:
            if nation.is_ai:
                opts = self.available_techs(nation)
                if opts: self.start_research(nation, random.choice(opts).id)
            return
        t = TECH_BY_ID.get(nation.active_research)
        if not t:
            nation.active_research = ""; return
        nation.research_points += nation.civ * 0.6
        if nation.research_points >= t.cost:
            nation.completed_techs = tuple(list(nation.completed_techs) + [t.id])
            nation.active_research = ""; nation.research_points = 0.0
            self.recompute_bonuses(nation)
            if nation.id == 0:
                self.log_msg(f"研究完成: {t.name}")
                self.toast(f"研究完成: {t.name}", (150, 230, 150))

    # ---------------- 历史事件 ----------------
    def tick_historical(self):
        for ev in HISTORICAL_EVENTS:
            if ev['id'] in self.fired_events: continue
            y, m, d = ev['date']
            if (self.year, self.month, self.day) >= (y, m, d):
                self.fired_events.add(ev['id'])
                try: ev['run'](self)
                except Exception as e: self.log_msg(f"[事件错误] {e}")
                self.log_msg(f"[{y}年] {ev['name']} —— {ev['desc']}")
                if ev['id'] not in ('barbarossa', 'pearl'):
                    self.toast(ev['name'], (255, 200, 120))

    def spawn_divisions_at(self, nid, x, y, n, ut='infantry'):
        for _ in range(n): self.add_division(nid, x, y, ut)
    def give_pp(self, nid, amount):
        n = self.nations.get(nid)
        if n: n.pp = max(0, n.pp + amount)
    def give_manpower(self, nid, amount):
        n = self.nations.get(nid)
        if n: n.manpower += amount

    # ---------------- 天气 ----------------
    def update_weather(self, force=False):
        if self.month in (12, 1, 2):   pool = ['snow', 'snow', 'clear', 'storm']
        elif self.month in (6, 7, 8):  pool = ['clear', 'clear', 'rain', 'storm']
        else:                          pool = ['clear', 'clear', 'rain']
        new = random.choice(pool)
        if force or new != self.weather:
            self.weather = new
            if not force and self.year >= 1937:
                self.log_msg(f"天气转{WEATHER_DEFS[new]['name']}")

    # ---------------- 时间推进 ----------------
    def update(self, dt):
        for t in self.toasts: t['t'] += dt
        self.toasts = [t for t in self.toasts if t['t'] < 2.6]
        for ef in self.effects: ef['t'] += dt
        self.effects = [ef for ef in self.effects if ef['t'] < 1.5]
        if self.speed <= 0: return
        self.hour_accum += dt * SPEED_HOURS[self.speed]
        guard = 0
        while self.hour_accum >= 1.0 and guard < 400:
            self.hour_accum -= 1.0
            self.tick_hour()
            guard += 1

    def tick_hour(self):
        self.hour += 1
        if self.hour >= 24:
            self.hour = 0; self.day += 1
            if self.day > 30:
                self.day = 1; self.month += 1
                if self.month > 12:
                    self.month = 1; self.year += 1
            self.tick_day()
        for d in self.all_divisions(): d.in_combat = False
        self.tick_supply()
        self.tick_supply_lines()
        self.tick_combat()
        self.tick_movement()
        self.tick_general_xp()
        self.ai_timer += 1
        if self.ai_timer >= 24:
            self.ai_timer = 0; self.tick_ai()
        self.event_timer += 1
        if self.event_timer >= 24*8:
            self.event_timer = 0; self.tick_events()
        self.prune_selected()
        self.cleanup_armies()

    def tick_day(self):
        for i, n in list(self.nations.items()):
            if not n.alive: continue
            provs = self.provinces_of(i)
            if not provs:
                self.eliminate(i); continue
            man_sum = sum(p.resource*400 for p in provs)
            ind_bonus = 1.0 + n.bonuses.get('industry', 0.0)
            man_bonus = 1.0 + n.bonuses.get('manpower', 0.0)
            n.pp += 1.4
            n.manpower += man_sum * 0.15 * man_bonus
            n.equipment += n.mil * 8.0 * ind_bonus
            n.navy += 0.2 + n.bonuses.get('navy', 0.0) * 0.4
            n.airforce += 0.2 + n.bonuses.get('airforce', 0.0) * 0.4
            self.tick_research(n)
            if n.id == 0 and self.cheats['infinite_res']:
                n.pp = 9999.0; n.manpower = 9_999_999.0; n.equipment = 999_999.0
            if n.build_type:
                n.build_progress += n.civ * 3.5 * ind_bonus
                if n.id == 0 and self.cheats['instant_build']: n.build_progress += 10000.0
                if n.build_progress >= 120.0:
                    if n.build_type == 'mil': n.mil += 1
                    else: n.civ += 1
                    n.build_type = ""; n.build_progress = 0.0
                    if n.id == 0: self.toast("建造完成", (150, 230, 150))
            if n.id == 0 and self.cheats['instant_train']:
                for item in n.train_queue: item.days = 0
            for item in list(n.train_queue):
                item.days -= 1
                if item.days <= 0:
                    n.train_queue.remove(item)
                    ut_def = UNIT_TYPES.get(item.unit_type, {})
                    spec = ut_def.get('is_special')
                    if spec == 'airforce':
                        n.airforce += 1.0
                        if n.id == 0: self.toast(f"空军联队 +1 (现 {n.airforce:.1f})", (200, 180, 240))
                    elif spec == 'navy':
                        n.navy += 1.0
                        if n.id == 0: self.toast(f"海军舰队 +1 (现 {n.navy:.1f})", (130, 180, 220))
                    else:
                        q = self.prov[item.x][item.y]
                        if q.land and q.owner == i:
                            self.add_division(i, item.x, item.y, item.unit_type)
                        else:
                            cap = self.capitals.get(i)
                            if cap and self.prov[cap[0]][cap[1]].owner == i:
                                self.add_division(i, cap[0], cap[1], item.unit_type)
                            else:
                                own = self.provinces_of(i)
                                if own: self.add_division(i, own[0].x, own[0].y, item.unit_type)
            for j in list(n.relations.keys()):
                if j == i: continue
                if self.at_war(i, j): n.relations[j] = max(-100, n.relations[j] - 0.5)
                else: n.relations[j] = max(-100, min(100, n.relations[j] + random.uniform(-0.6, 0.6)))
        self.recover_divisions()
        self.compute_supply_caps()
        self.update_weather()
        self.tick_historical()
        for i in list(self.nations.keys()):
            self.check_surrender(i)

    def recover_divisions(self):
        for d in self.all_divisions():
            p = self.prov[d.x][d.y]
            if any(o.owner != d.owner for o in p.divisions): continue
            n = self.nations.get(d.owner)
            if not n or not n.alive: continue
            eff = self.get_doctrine_effects(d)
            rec = 12.0
            if eff: rec *= (1.0 + eff['extra'].get('org_recovery', 0.0))
            d.org = min(d.max_org, d.org + rec)
            if d.strength < 100.0:
                need = min(6.0, 100.0 - d.strength)
                cost = need * 6.0
                if n.equipment >= cost or (d.owner == 0 and self.cheats['infinite_res']):
                    if not (d.owner == 0 and self.cheats['infinite_res']): n.equipment -= cost
                    d.strength += need
                    n.manpower = max(0, n.manpower - need * 100)

    def eliminate(self, nid):
        n = self.nations.get(nid)
        if not n or not n.alive: return
        n.alive = False; n.surrendered = True
        for row in self.prov:
            for p in row:
                p.divisions = [d for d in p.divisions if d.owner != nid]
        to_reassign = [p for row in self.prov for p in row if p.owner == nid]
        for p in to_reassign:
            nb = defaultdict(int)
            for nx, ny in self.neighbors(p.x, p.y):
                q = self.prov[nx][ny]
                if q.land and q.owner != -1 and q.owner != nid:
                    oth = self.nations.get(q.owner)
                    if oth and oth.alive: nb[q.owner] += 1
            p.owner = max(nb, key=nb.get) if nb else -1
        for oth in self.nations.values():
            self.wars.discard(frozenset((nid, oth.id)))
            oth.wars.discard(nid); oth.relations.pop(nid, None)
        n.wars.clear(); n.relations.clear()
        for aid in [aid for aid, a in self.armies.items() if a.owner == nid]: del self.armies[aid]
        self.map_dirty = True
        self.log_msg(f"{n.name} 已被彻底征服！")
        self.toast(f"{n.name} 已被征服", (240, 120, 100))

    def check_surrender(self, nid):
        n = self.nations.get(nid)
        if not n or not n.alive or n.surrendered: return
        cap = self.capitals.get(nid)
        if not cap: return
        cap_lost = self.prov[cap[0]][cap[1]].owner != nid
        cur_vp = sum(p.vp for row in self.prov for p in row if p.owner == nid)
        orig_vp = sum(p.vp for row in self.prov for p in row if p.original_owner == nid)
        if orig_vp == 0: return
        ratio = cur_vp / orig_vp
        if (cap_lost and ratio < 0.35) or ratio < 0.10:
            n.surrendered = True
            self.log_msg(f"{n.name} 宣布无条件投降！")
            self.toast(f"{n.name} 投降", (240, 160, 100))
            for row in self.prov:
                for p in row:
                    if p.owner == nid:
                        nbrs = defaultdict(int)
                        for nx, ny in self.neighbors(p.x, p.y):
                            q = self.prov[nx][ny]
                            if q.land and q.owner != nid and q.owner != -1:
                                oth = self.nations.get(q.owner)
                                if oth and oth.alive: nbrs[q.owner] += 1
                        p.owner = max(nbrs, key=nbrs.get) if nbrs else -1
            n.alive = False
            for row in self.prov:
                for p in row:
                    p.divisions = [d for d in p.divisions if d.owner != nid]
            self.map_dirty = True

    # ---------------- 补给 ----------------
    def tick_supply(self):
        for row in self.prov:
            for p in row:
                if not p.divisions: continue
                groups = defaultdict(list)
                for d in p.divisions: groups[d.owner].append(d)
                for owner, divs in groups.items():
                    n = self.nations.get(owner)
                    if not n or not n.alive: continue
                    eff = self.get_doctrine_effects(divs[0])
                    if eff and eff['extra'].get('ignore_supply'): continue
                    cap = p.supply_cap * (1.0 + n.bonuses.get('supply', 0.0))
                    load = len(divs)
                    if load <= cap: continue
                    per = (load - cap) / max(1, load)
                    for d in divs:
                        d.org = max(0.0, d.org - SUPPLY_LOSS_ORG * per * 6)
                        d.strength = max(1.0, d.strength - SUPPLY_LOSS_STR * per * 4)

    def tick_supply_lines(self):
        if self.ai_timer != 0: return
        self.cut_off_provs.clear()
        for nid, n in self.nations.items():
            if not n.alive or n.surrendered: continue
            cap = self.capitals.get(nid)
            if not cap: continue
            if self.prov[cap[0]][cap[1]].owner != nid: continue
            visited = {cap}
            q = deque([cap])
            while q:
                x, y = q.popleft()
                for nx, ny in self.neighbors(x, y):
                    if (nx, ny) in visited: continue
                    p = self.prov[nx][ny]
                    if not p.land or p.owner != nid: continue
                    visited.add((nx, ny)); q.append((nx, ny))
            for row in self.prov:
                for p in row:
                    if p.owner == nid and (p.x, p.y) not in visited:
                        self.cut_off_provs[nid].add((p.x, p.y))
        for d in self.all_divisions():
            if (d.x, d.y) in self.cut_off_provs.get(d.owner, ()):
                eff = self.get_doctrine_effects(d)
                if eff and eff['extra'].get('ignore_supply'): continue
                d.org = max(0.0, d.org - 1.2)
                d.strength = max(1.0, d.strength - 0.15)

    # ---------------- 战斗 ----------------
    def tick_combat(self):
        for y in range(MAP_H):
            for x in range(MAP_W):
                p = self.prov[x][y]
                if len(p.divisions) < 2: continue
                if len(set(d.owner for d in p.divisions)) < 2: continue
                self.resolve_combat(p)

    def resolve_combat(self, p):
        owners = defaultdict(list)
        for d in p.divisions: owners[d.owner].append(d)
        if len(owners) < 2: return
        if p.owner in owners: def_owner = p.owner
        else:
            def_owner = max(owners, key=lambda k: len(owners[k]))
            p.owner = def_owner; self.map_dirty = True
        defenders = owners[def_owner]
        attackers = []
        for o, lst in owners.items():
            if o != def_owner: attackers.extend(lst)
        if not attackers or not defenders: return
        active_attackers = [d for d in attackers if self.at_war(d.owner, def_owner)]
        if not active_attackers: return
        for d in defenders + active_attackers: d.in_combat = True
        # v7.1: 地形 + 防御工事共同决定防御强度
        tdef = TERRAIN_INFO[p.terrain]['def'] * (1.0 + p.fort * 0.12)
        atk_pool = sorted(active_attackers, key=lambda d: -d.strength)[:COMBAT_WIDTH]
        def_pool = sorted(defenders, key=lambda d: -d.strength)[:COMBAT_WIDTH]
        god = self.cheats['god_mode']
        weather = WEATHER_DEFS[self.weather]
        w_atk = weather['attack']

        def atk_bonus(d):
            n = self.nations.get(d.owner)
            base = 1.0 + (n.bonuses.get('attack', 0.0) if n else 0.0)
            eff = self.get_doctrine_effects(d)
            if eff:
                base *= (1.0 + eff['attack'])
                if d.unit_type == 'armor':
                    base *= (1.0 + eff['extra'].get('armor_bonus', 0.0))
            base *= (1.0 + d.experience * 0.005)
            return base * d.info['atk']

        def def_bonus(d):
            n = self.nations.get(d.owner)
            base = 1.0 + (n.bonuses.get('defense', 0.0) if n else 0.0)
            eff = self.get_doctrine_effects(d)
            if eff: base *= (1.0 + eff['defense'])
            base *= (1.0 + d.experience * 0.005)
            return base * d.info['def']

        atk = sum(d.strength*0.10*atk_bonus(d)*random.uniform(0.85,1.15) for d in atk_pool) * w_atk
        dfn = sum(d.strength*0.10*def_bonus(d)*random.uniform(0.85,1.15) for d in def_pool)

        for d in atk_pool:
            if god and d.owner == 0: continue
            d.org -= dfn / max(1, len(atk_pool)) * 0.40 / max(0.6, d.info['def'])
            d.strength -= dfn / max(1, len(atk_pool)) * 0.08 / max(0.6, d.info['def'])
        for d in def_pool:
            if god and d.owner == 0: continue
            d.org -= atk / max(1, len(def_pool)) * 0.40 / tdef / max(0.6, d.info['def'])
            d.strength -= atk / max(1, len(def_pool)) * 0.08 / tdef / max(0.6, d.info['def'])

        for d in atk_pool + def_pool:
            d.experience = min(100.0, d.experience + 0.25)

        for d in list(active_attackers) + list(defenders):
            d.org = max(0.0, d.org); d.strength = max(1.0, d.strength)
            if d.org <= 0.0: self.retreat_or_destroy(d)

        still_def = [d for d in p.divisions if d.owner == def_owner]
        if not still_def and p.divisions:
            rem = defaultdict(int)
            for d in p.divisions: rem[d.owner] += 1
            new_owner = max(rem, key=rem.get)
            if p.owner != new_owner:
                p.owner = new_owner; self.map_dirty = True

    def retreat_or_destroy(self, d):
        src = self.prov[d.x][d.y]
        d.strength = max(0.0, d.strength - 15.0)
        candidates = []
        for nx, ny in self.neighbors(d.x, d.y):
            q = self.prov[nx][ny]
            if not q.land or q.owner != d.owner: continue
            if any(o.owner != d.owner for o in q.divisions): continue
            candidates.append(q)
        if d in src.divisions: src.divisions.remove(d)
        if not candidates or d.strength <= 5.0:
            self.total_destroyed += 1
            if d.owner == 0:
                self.toast("我方 1 个师被歼灭", (240, 120, 100))
            else:
                nm = self.nations.get(d.owner)
                if nm and random.random() < 0.45:
                    self.toast(f"歼灭 {nm.name} 1 个师", (150, 230, 150))
            return
        q = random.choice(candidates)
        d.x, d.y = q.x, q.y
        d.tx = d.ty = -1; d.path = []; d.move_progress = 0.0
        eff = self.get_doctrine_effects(d)
        retreat_org = 8.0
        if eff: retreat_org += eff['extra'].get('retreat_bonus', 0.0) * 20.0
        d.org = retreat_org; d.in_combat = False
        q.divisions.append(d)

    # ---------------- 移动 ----------------
    def tick_movement(self):
        weather = WEATHER_DEFS[self.weather]
        for d in list(self.all_divisions()):
            if not d.has_target: continue
            if d.in_combat: continue
            if (d.tx, d.ty) == (d.x, d.y):
                d.tx = d.ty = -1; d.path = []; continue
            if not d.path:
                d.path = self.find_path(d.x, d.y, d.tx, d.ty)
                if not d.path: d.tx = d.ty = -1; continue
            nx, ny = d.path[0]
            q = self.prov[nx][ny]
            if not q.land:
                d.path = []; d.tx = d.ty = -1; continue

            eff = self.get_doctrine_effects(d)
            is_guerrilla = bool(eff and eff['extra'].get('behind_lines'))

            if q.owner != -1 and q.owner != d.owner and not self.at_war(d.owner, q.owner):
                if is_guerrilla:
                    adjacent_own = any(
                        self.prov[ax][ay].owner == d.owner
                        for ax, ay in self.neighbors(nx, ny)
                    )
                    if not adjacent_own:
                        d.path = []; d.tx = d.ty = -1; continue
                else:
                    d.path = []; d.tx = d.ty = -1; continue

            cost = TERRAIN_INFO[q.terrain]['cost']
            n = self.nations.get(d.owner)
            speed_bonus = 1.0 + (n.bonuses.get('move', 0.0) if n else 0.0)
            if eff: speed_bonus *= (1.0 + eff['move'])
            unit_speed = d.info['speed']
            mult = 6.0 if (d.owner == 0 and self.cheats['fast_move']) else 1.0
            d.move_progress += (1.0/24.0)/cost*speed_bonus*unit_speed*mult*weather['move']
            if d.move_progress >= 1.0:
                d.move_progress = 0.0
                src = self.prov[d.x][d.y]
                if d in src.divisions: src.divisions.remove(d)
                d.x, d.y = nx, ny
                q.divisions.append(d)
                d.path.pop(0)
                enemy_present = any(o.owner != d.owner for o in q.divisions)
                if not enemy_present and q.owner != d.owner:
                    if q.owner == -1 or self.at_war(d.owner, q.owner) or is_guerrilla:
                        q.owner = d.owner; self.map_dirty = True
                if not d.path and (d.tx, d.ty) == (d.x, d.y):
                    d.tx = d.ty = -1

    # ---------------- 登陆 ----------------
    def try_landing(self, divs, tx, ty):
        if not divs: return False
        p = self.prov[tx][ty]
        if not p.land: return False
        src = self.prov[divs[0].x][divs[0].y]
        if not self.coastal(src.x, src.y):
            if divs[0].owner == 0: self.toast("出发省不沿海", (240, 120, 100))
            return False
        if not self.coastal(tx, ty):
            if divs[0].owner == 0: self.toast("目标省不沿海", (240, 120, 100))
            return False
        route = self.sea_route(src.x, src.y, tx, ty)
        if not route:
            if divs[0].owner == 0: self.toast("海路不通", (240, 120, 100))
            return False
        owner = divs[0].owner
        n = self.nations.get(owner)
        if not n: return False
        if p.owner != -1 and p.owner != owner and not self.at_war(owner, p.owner):
            if divs[0].owner == 0: self.toast("未与该国交战", (240, 120, 100))
            return False
        eff = self.get_doctrine_effects(divs[0])
        cost_navy = 0.5 * len(divs) * (1 + len(route) * 0.05)
        if eff: cost_navy *= (1.0 + eff['extra'].get('navy_cost', 0.0))
        if n.navy < cost_navy:
            if owner == 0: self.toast(f"海军不足 (需 {cost_navy:.1f})", (240, 120, 100))
            return False
        n.navy -= cost_navy
        keep_org = 0.55
        if eff: keep_org += eff['extra'].get('landing_bonus', 0.0) * 0.3
        for d in divs:
            d.tx = d.ty = -1; d.path = []; d.move_progress = 0.0
            sp = self.prov[d.x][d.y]
            if d in sp.divisions: sp.divisions.remove(d)
            d.x, d.y = tx, ty
            d.org = max(1.0, d.org * keep_org)
            d.strength = max(1.0, d.strength * 0.85)
            p.divisions.append(d)
        enemy_present = any(o.owner != owner for o in p.divisions)
        if not enemy_present and p.owner != owner:
            p.owner = owner
            self.map_dirty = True
        if owner == 0:
            self.log_msg(f"登陆成功: ({src.x},{src.y}) → ({tx},{ty})")
            self.toast("登陆成功", (150, 230, 150))
        return True

    # ---------------- 战略轰炸 (v7.1: 附带杀伤) ----------------
    def do_bomb(self, tx, ty):
        p = self.prov[tx][ty]
        if not p.land:
            self.toast("目标不是陆地", (240, 120, 100)); return
        n = self.nations.get(0)
        if not n or not n.alive: return
        if p.owner == 0 or p.owner == -1:
            self.toast("目标必须是敌国省份", (240, 120, 100)); return
        if not self.at_war(0, p.owner):
            self.toast("未与该国交战", (240, 120, 100)); return
        if n.airforce < 0.5:
            self.toast("空军力量不足 (需 0.5)", (240, 120, 100)); return

        victim = self.nations.get(p.owner)
        intercept_chance = 0.25
        if victim and victim.airforce >= 1.0:
            intercept_chance = min(0.75, 0.25 + victim.airforce * 0.03)

        if random.random() < intercept_chance and victim:
            n.airforce = max(0.0, n.airforce - 1.0)
            victim.airforce = max(0.0, victim.airforce - 0.5)
            self.log_msg(f"✕ 轰炸 ({tx},{ty}) 被拦截！空军 -1")
            self.toast(f"✕ 轰炸被拦截 @({tx},{ty})", (240, 120, 100))
            self.effects.append({'x': tx, 'y': ty, 'type': 'explosion', 't': 0.0})
            return

        n.airforce -= 0.5
        old_ind = p.industry
        p.industry = max(0, p.industry - 1)
        if victim: victim.equipment = max(0.0, victim.equipment - 250)

        # ===== v7.1: 轰炸对驻守敌方师造成兵力/组织伤害, 兵力 ≤5 直接歼灭 =====
        enemy_divs = [d for d in p.divisions
                      if d.owner != 0 and self.at_war(0, d.owner)]
        dmg_total = 0.0
        killed = 0
        if enemy_divs:
            base_str = random.uniform(10.0, 18.0)
            base_org = random.uniform(20.0, 30.0)
            # 要塞/山地削弱空袭
            mitigation = 1.0 - min(0.5, p.fort * 0.08 + (0.10 if p.terrain == 'mountain' else 0.0))
            for d in enemy_divs:
                dmg_s = base_str * random.uniform(0.8, 1.2) * mitigation
                dmg_o = base_org * random.uniform(0.8, 1.2) * mitigation
                d.strength = max(0.0, d.strength - dmg_s)
                d.org      = max(0.0, d.org - dmg_o)
                dmg_total += dmg_s
            for d in list(enemy_divs):
                if d.strength <= 5.0 and d in p.divisions:
                    p.divisions.remove(d)
                    killed += 1
                    self.total_destroyed += 1
            if killed:
                self.cleanup_armies()
        # =====================================================================

        self.effects.append({'x': tx, 'y': ty, 'type': 'explosion', 't': 0.0})

        extra = ""
        if enemy_divs:
            extra = f"  杀伤 {dmg_total:.0f}"
            if killed: extra += f"  歼灭 {killed} 个师"
        self.log_msg(
            f"★ 战略轰炸 ({tx},{ty}) 工业 {old_ind}→{p.industry}，敌方装备 -250{extra}"
        )
        self.toast(
            f"★ 轰炸 @({tx},{ty}) 工业-1 装备-250 空军-0.5{extra}",
            (255, 200, 120),
        )

    def tick_naval(self):
        if self.hour != 0: return
        for i, n in self.nations.items():
            if not n.alive or n.navy <= 0: continue
            for j in list(n.wars):
                m = self.nations.get(j)
                if not m or not m.alive: continue
                if i > j: continue
                if n.navy > 0:
                    n.navy = max(0, n.navy - m.navy * 0.05)
                if m.navy > 0:
                    m.navy = max(0, m.navy - n.navy * 0.05)

    # ---------------- 事件 ----------------
    def tick_events(self):
        for n in self.nations.values():
            if not n.alive: continue
            if random.random() > 0.35: continue
            total = sum(e.weight for e in EVENTS)
            r = random.uniform(0, total); acc = 0.0; chosen = EVENTS[0]
            for e in EVENTS:
                acc += e.weight
                if r <= acc: chosen = e; break
            self.apply_event(n, chosen)

    def apply_event(self, nation, ev):
        eff = ev.effect
        if 'pp' in eff: nation.pp = max(0.0, nation.pp + eff['pp'])
        if 'manpower' in eff: nation.manpower = max(0.0, nation.manpower + eff['manpower'])
        if 'equipment' in eff: nation.equipment = max(0.0, nation.equipment + eff['equipment'])
        if 'industry' in eff and eff['industry'] > 0:
            provs = self.provinces_of(nation.id)
            if provs: random.choice(provs).industry += eff['industry']
        if nation.id == 0:
            self.log_msg(f"[事件] {ev.name} —— {ev.desc}")
            self.toast(f"[事件] {ev.name}", (170, 220, 255))

    # ---------------- AI ----------------
    def tick_ai(self):
        for n in self.nations.values():
            if not n.alive or not n.is_ai: continue
            if random.random() < 0.15: self.ai_diplomacy(n)
            self.ai_nation(n)
            if random.random() < 0.25: self.ai_manage_armies(n)

    def ai_diplomacy(self, n):
        for j, other in self.nations.items():
            if j == n.id or not other.alive: continue
            if self.at_war(n.id, j):
                if n.id == 5 and j == 0: continue
                if n.relations.get(j, 0) > -60 and random.random() < 0.3:
                    my = sum(1 for d in self.all_divisions() if d.owner == n.id)
                    en = sum(1 for d in self.all_divisions() if d.owner == j)
                    if en > my * 1.5: self.make_peace(n.id, j)
                continue
            rel = n.relations.get(j, 0)
            if rel < -30 and random.random() < 0.15:
                my = sum(1 for d in self.all_divisions() if d.owner == n.id)
                en = sum(1 for d in self.all_divisions() if d.owner == j)
                if my > en * 0.9: self.declare_war(n.id, j)

    def ai_manage_armies(self, n):
        my_divs = [d for d in self.all_divisions() if d.owner == n.id and d.army_id < 0]
        if len(my_divs) < 3: return
        by_prov = defaultdict(list)
        for d in my_divs: by_prov[(d.x, d.y)].append(d)
        for pos, divs in by_prov.items():
            if len(divs) >= 3:
                a = self.create_army_from_selected(n.id, divs)
                if a:
                    at_war = bool(n.wars)
                    if n.id == 0 and random.random() < 0.35: doc = 'guerrilla'
                    elif at_war and random.random() < 0.4: doc = 'blitz'
                    elif not at_war: doc = 'trench'
                    elif random.random() < 0.2: doc = 'mass'
                    else: doc = 'regular'
                    self.set_army_doctrine(a.id, doc)
                    if n.generals:
                        free = [g for g in n.generals if g.assigned_army < 0]
                        if free:
                            best = max(free, key=lambda g: g.attack + g.defense)
                            self.assign_general(a.id, best.id)

    def ai_nation(self, n):
        provs = self.provinces_of(n.id)
        if not provs: return
        my_divs = [d for d in self.all_divisions() if d.owner == n.id]
        cap = self.capitals.get(n.id)
        if cap and n.equipment >= 600 and n.manpower >= 12000:
            limit = max(4, int(len(provs) * 0.30))
            if len(my_divs) + len(n.train_queue) < limit:
                ut = random.choice(['infantry','infantry','motorized','armor','artillery'])
                ut_info = UNIT_TYPES[ut]
                if n.equipment >= ut_info['equip'] and n.manpower >= ut_info['manpower']:
                    n.equipment -= ut_info['equip']; n.manpower -= ut_info['manpower']
                    n.train_queue.append(TrainOrder(cap[0], cap[1], ut_info['days'], ut))
        if not n.build_type:
            n.build_type = 'mil' if n.mil <= n.civ else 'civ'; n.build_progress = 0.0
        if random.random() < 0.1 and n.pp >= 80:
            if n.policies.get('conscript', 0) < 2 and random.random() < 0.5:
                n.policies['conscript'] += 1; n.pp -= 50; self.recompute_bonuses(n)
            elif n.policies.get('economy', 0) < 2:
                n.policies['economy'] += 1; n.pp -= 50; self.recompute_bonuses(n)
        if n.active_general_id < 0 and n.generals:
            best = max(n.generals, key=lambda g: g.attack + g.defense)
            n.active_general_id = best.id; self.recompute_bonuses(n)

        # v7.1: AI 修建边境防御工事
        if n.equipment >= 400 and n.pp >= 60 and random.random() < 0.06:
            own_provs = self.provinces_of(n.id)
            border = []
            for pr in own_provs:
                if pr.fort >= 4: continue
                for nx, ny in self.neighbors(pr.x, pr.y):
                    q = self.prov[nx][ny]
                    if q.land and q.owner != n.id and q.owner != -1:
                        border.append(pr); break
            if border:
                pr = random.choice(border)
                n.equipment -= 200
                n.pp -= 30
                pr.fort += 1
                self.map_dirty = True

        enemy_provs = []
        for row in self.prov:
            for p in row:
                if not p.land: continue
                if p.owner != n.id and p.owner != -1 and self.at_war(n.id, p.owner):
                    enemy_provs.append(p)
                elif p.owner == -1: enemy_provs.append(p)
        if not enemy_provs:
            for d in my_divs:
                if d.in_combat or d.has_target: continue
                if cap and (d.x, d.y) != cap: d.tx, d.ty = cap; d.path = []
            return
        def prio(p, cx, cy): return p.vp * 3.0 - (abs(p.x-cx) + abs(p.y-cy)) * 0.4
        cap_pos = cap if cap else ((my_divs[0].x, my_divs[0].y) if my_divs else (0, 0))
        sorted_enemy = sorted(enemy_provs, key=lambda p: -prio(p, *cap_pos))
        for d in my_divs:
            if d.in_combat or d.has_target: continue
            best_p, best_score = None, -1e9
            for p in sorted_enemy[:20]:
                dist = abs(p.x-d.x) + abs(p.y-d.y)
                score = prio(p, *cap_pos) - dist * 0.5
                if score > best_score: best_score, best_p = score, p
            if best_p: d.tx, d.ty = best_p.x, best_p.y; d.path = []

    # ---------------- 作弊 ----------------
    def toggle_cheat(self, key):
        if key in self.cheats:
            self.cheats[key] = not self.cheats[key]
            self.log_msg(f"[作弊] {key} {'开' if self.cheats[key] else '关'}")
            if key == 'infinite_res' and not self.cheats[key]:
                p = self.nations.get(0)
                if p:
                    p.pp = min(p.pp, 500.0); p.manpower = min(p.manpower, 200_000.0)
                    p.equipment = min(p.equipment, 20_000.0)
    def cheat_add_res(self):
        p = self.nations.get(0)
        if not p: return
        p.pp += 10000; p.manpower += 1_000_000; p.equipment += 100_000
        p.navy += 50; p.airforce += 50
        self.log_msg("[作弊] 资源已注入")
    def cheat_heal_all(self):
        cnt = 0
        for d in self.all_divisions():
            if d.owner == 0:
                d.strength = 100.0; d.org = d.max_org; d.in_combat = False; cnt += 1
        self.log_msg(f"[作弊] 全军满编恢复 ({cnt})")
    def cheat_conquer_all(self):
        for row in self.prov:
            for p in row:
                if p.land:
                    p.owner = 0
                    p.divisions = [d for d in p.divisions if d.owner == 0]
        self.map_dirty = True; self.log_msg("[作弊] 世界已被征服！")
    def cheat_instant_win(self):
        for i, n in self.nations.items():
            if i != 0: n.alive = False; n.wars.clear()
        for row in self.prov:
            for p in row:
                if p.land: p.owner = 0
        for d in list(self.all_divisions()):
            if d.owner != 0: self.prov[d.x][d.y].divisions.remove(d)
        self.map_dirty = True; self.log_msg("[作弊] 直接胜利！")

    def cheat_panel_layout(self):
        row_h, gap = 30, 5; num_rows = 9
        pad_x, pad_top = 14, 10
        header_h, divider_h, tip_h, pad_bottom = 30, 8, 22, 14
        panel_w = 340
        panel_h = pad_top + header_h + divider_h + num_rows*(row_h+gap) + tip_h + pad_bottom
        rect = pygame.Rect(20, 20, panel_w, panel_h)
        x0 = rect.x + pad_x
        y = rect.y + pad_top + header_h + divider_h
        bw = rect.w - pad_x * 2
        rows = []
        def add_row(key, label, kind):
            nonlocal y
            rows.append((key, pygame.Rect(x0, y, bw, row_h), kind, label)); y += row_h + gap
        add_row('infinite_res', '无限资源', 'toggle')
        add_row('instant_build', '瞬间建造', 'toggle')
        add_row('instant_train', '瞬间训练', 'toggle')
        add_row('god_mode', '无敌模式', 'toggle')
        add_row('fast_move', '极速移动', 'toggle')
        add_row('add_res', '资源 +10000', 'btn')
        add_row('heal_all', '全军满编恢复', 'btn')
        add_row('conquer_all', '征服全部领土', 'btn')
        add_row('instant_win', '直接胜利', 'btn')
        return rect, rows

    def handle_cheat_click(self, pos):
        rect, rows = self.cheat_panel_layout()
        for key, r, kind, label in rows:
            if r.collidepoint(pos):
                if kind == 'toggle': self.toggle_cheat(key)
                elif key == 'add_res': self.cheat_add_res()
                elif key == 'heal_all': self.cheat_heal_all()
                elif key == 'conquer_all': self.cheat_conquer_all()
                elif key == 'instant_win': self.cheat_instant_win()
                return

    # ---------------- 存档 ----------------
    def _save_clean(self):
        tmp = self.map_surface; self.map_surface = None
        self.buttons = {}; self.cheat_rows = []
        self.research_buttons = {}; self.policy_buttons = {}
        self.general_buttons = {}; self.diplomacy_buttons = {}; self.army_buttons = {}
        return tmp

    def _save_restore(self, tmp):
        self.map_surface = tmp; self.map_dirty = True

    def save_game(self, slot=None):
        if slot is None: slot = self.save_slot
        path = SAVE_FMT.format(slot)
        try:
            tmp = self._save_clean()
            self.save_slot = slot
            with open(path, 'wb') as f:
                pickle.dump({'version': SAVE_VERSION, 'game': self}, f)
            self._save_restore(tmp)
            self.log_msg(f"已保存到槽位 {slot}")
            self.toast(f"已保存 (槽位 {slot})", (150, 230, 150))
        except Exception as e:
            self.log_msg(f"保存失败: {e}"); self.toast("保存失败", (240, 120, 100))

    def load_game(self, slot=None):
        if slot is None: slot = self.save_slot
        path = SAVE_FMT.format(slot)
        if not os.path.exists(path):
            self.log_msg(f"槽位 {slot} 无存档"); self.toast("无存档", (240, 120, 100)); return
        try:
            with open(path, 'rb') as f:
                payload = pickle.load(f)
            if isinstance(payload, dict) and 'game' in payload:
                g = payload['game']
                if g.__dict__.get('save_slot') is None: g.__dict__['save_slot'] = slot
                if g.__dict__.get('wars') is None:
                    g.__dict__['wars'] = set()
                    for n in g.nations.values():
                        for j in n.wars: g.wars.add(frozenset((n.id, j)))
                self.__dict__.update(g.__dict__)
            else:
                self.__dict__.update(payload.__dict__)
                if 'wars' not in self.__dict__:
                    self.wars = set()
                    for n in self.nations.values():
                        for j in n.wars: self.wars.add(frozenset((n.id, j)))
                if 'cut_off_provs' not in self.__dict__:
                    self.cut_off_provs = defaultdict(set)
                if 'weather' not in self.__dict__:
                    self.weather = 'clear'
                if 'fired_events' not in self.__dict__:
                    self.fired_events = set()
            if 'effects' not in self.__dict__:
                self.effects = []
            for _n in self.nations.values():
                for _g in getattr(_n, 'generals', []):
                    if not hasattr(_g, 'experience'): _g.experience = 0.0
                    if not hasattr(_g, 'kills'): _g.kills = 0
            # v7.1 兼容: 老存档可能没有 fort
            for row in self.prov:
                for p in row:
                    if not hasattr(p, 'fort'): p.fort = 0
            self.map_surface = None; self.map_dirty = True
            self.buttons = {}; self.cheat_rows = []
            self.research_buttons = {}; self.policy_buttons = {}
            self.general_buttons = {}; self.diplomacy_buttons = {}; self.army_buttons = {}
            self.selected_divs = []; self.selected = None; self.selected_army = -1
            self.toasts = []
            self.panel_scroll = 0
            self.log_msg(f"已读取槽位 {slot}")
            self.toast(f"已读取 (槽位 {slot})", (150, 230, 150))
        except Exception as e:
            self.log_msg(f"读取失败: {e}"); self.toast("读取失败", (240, 120, 100))

    # ---------------- 输入 ----------------
    def handle_event(self, e):
        mods = pygame.key.get_mods()
        if e.type == pygame.KEYDOWN:
            if e.key == pygame.K_SPACE:
                self.speed = 0 if self.speed > 0 else 1
            elif pygame.K_1 <= e.key <= pygame.K_4:
                self.speed = e.key - pygame.K_0
            elif e.key in (pygame.K_BACKQUOTE, pygame.K_g):
                self.cheat_open = not self.cheat_open
            elif e.key == pygame.K_b:
                self.target_mode = None if self.target_mode == 'bomb' else 'bomb'
                if self.target_mode == 'bomb': self.toast("战略轰炸: 点击敌方省", (255, 200, 120))
            elif e.key == pygame.K_F5:
                if mods & pygame.KMOD_CTRL: self.save_game(1)
                else: self.save_game()
            elif e.key == pygame.K_F9:
                if mods & pygame.KMOD_CTRL: self.load_game(1)
                else: self.load_game()
            elif e.key == pygame.K_F6 and mods & pygame.KMOD_CTRL: self.save_game(2)
            elif e.key == pygame.K_F7 and mods & pygame.KMOD_CTRL: self.save_game(3)
            elif e.key == pygame.K_F10 and mods & pygame.KMOD_CTRL: self.load_game(2)
            elif e.key == pygame.K_F11 and mods & pygame.KMOD_CTRL: self.load_game(3)
            elif e.key == pygame.K_ESCAPE:
                if self.target_mode: self.target_mode = None
                elif self.cheat_open: self.cheat_open = False
                elif len({(d.x, d.y) for d in self.selected_divs}) > 1:
                    self.selected_divs = []; self.selected_army = -1
                    self.toast("已清空选择", (200, 200, 200))
                else: pygame.event.post(pygame.event.Event(pygame.QUIT))

        elif e.type == pygame.MOUSEWHEEL:
            mx, my = pygame.mouse.get_pos()
            if mx >= MAP_PX_W and my >= self.panel_content_top:
                self.panel_scroll = max(0, self.panel_scroll - e.y * 40)
                if self.panel_scroll > self.panel_max_scroll:
                    self.panel_scroll = self.panel_max_scroll

        elif e.type == pygame.MOUSEMOTION:
            mx, my = e.pos
            if mx < MAP_PX_W:
                x, y = mx // TILE, my // TILE
                self.hover = (x, y) if (0 <= x < MAP_W and 0 <= y < MAP_H) else None
            else: self.hover = None

        elif e.type == pygame.MOUSEBUTTONDOWN:
            mx, my = e.pos
            if self.cheat_open and self.cheat_panel_rect.collidepoint(mx, my):
                if e.button == 1: self.handle_cheat_click(e.pos)
                return
            if mx >= MAP_PX_W:
                if e.button == 1: self.handle_panel_click(e.pos)
                return
            x, y = mx // TILE, my // TILE
            if not (0 <= x < MAP_W and 0 <= y < MAP_H): return

            if e.button == 1:
                if self.target_mode == 'bomb':
                    self.do_bomb(x, y); self.target_mode = None; return
                if mods & pygame.KMOD_CTRL:
                    pr = self.prov[x][y]
                    if pr.land and pr.owner != 0:
                        old = pr.owner
                        pr.divisions = [d for d in pr.divisions if d.owner == 0]
                        pr.owner = 0; self.map_dirty = True
                        self.log_msg(f"[作弊] 已占领 ({x},{y})")
                        if old >= 0 and self.nations.get(old) and not self.provinces_of(old):
                            self.eliminate(old)
                    return
                pr = self.prov[x][y]
                if mods & pygame.KMOD_SHIFT and pr.land:
                    existing = {id(d) for d in self.selected_divs}
                    added = 0
                    for d in pr.divisions:
                        if d.owner == 0 and id(d) not in existing:
                            self.selected_divs.append(d); added += 1
                    self.selected = (x, y)
                    self.selected_army = -1
                    if added:
                        tiles = len({(dd.x, dd.y) for dd in self.selected_divs})
                        self.toast(f"多选 +{added} 师（共 {len(self.selected_divs)} 师 / {tiles} 省）",
                                   (170, 220, 255))
                    else:
                        self.toast("该省无可追加的己方师", (200, 180, 140))
                else:
                    self.selected = (x, y)
                    self.selected_divs = [d for d in pr.divisions if d.owner == 0]
                    self.selected_army = -1
            elif e.button == 3:
                self.prune_selected()
                if not self.prov[x][y].land: return
                if not self.selected_divs: return
                d0 = self.selected_divs[0]
                can_reach = bool(self.find_path(d0.x, d0.y, x, y)) or (d0.x, d0.y) == (x, y)
                tgt_owner = self.prov[x][y].owner
                if can_reach:
                    for d in self.selected_divs:
                        if tgt_owner != -1 and tgt_owner != d.owner:
                            if not self.at_war(d.owner, tgt_owner): continue
                        d.tx, d.ty = x, y; d.path = []
                else:
                    self.try_landing(list(self.selected_divs), x, y)

    def handle_panel_click(self, pos):
        for key, rect in self.buttons.items():
            if key.startswith('tab_') and rect.collidepoint(pos):
                self.ui_tab = key[4:]
                self.panel_scroll = 0
                return
        if pos[1] < self.panel_content_top:
            return
        for key, rect in self.buttons.items():
            if key.startswith('tab_'): continue
            if rect.collidepoint(pos):
                self.do_action(key); return
        if self.ui_tab == 'research':
            for tid, rect in self.research_buttons.items():
                if rect.collidepoint(pos):
                    if tid == '__cancel__':
                        self.cancel_research(self.nations.get(0))
                    else:
                        p = self.nations.get(0)
                        if p: self.start_research(p, tid)
                    return
        elif self.ui_tab == 'policy':
            for key, rect in self.policy_buttons.items():
                if rect.collidepoint(pos): self.apply_policy(key); return
        elif self.ui_tab == 'generals':
            for key, rect in self.general_buttons.items():
                if rect.collidepoint(pos):
                    if key == '__recruit__':
                        self.recruit_general(self.nations.get(0))
                    else:
                        p = self.nations.get(0)
                        if p:
                            p.active_general_id = -1 if p.active_general_id == key else key
                            self.recompute_bonuses(p)
                    return
        elif self.ui_tab == 'diplomacy':
            for key, rect in self.diplomacy_buttons.items():
                if rect.collidepoint(pos): self.do_diplomacy(key); return
        elif self.ui_tab == 'armies':
            for key, rect in self.army_buttons.items():
                if rect.collidepoint(pos):
                    if key == 'create': self.create_army_from_selected()
                    elif key == '__clear_sel__':
                        self.selected_divs = []; self.selected_army = -1
                        self.toast("已清空选择", (200, 200, 200))
                    elif key == 'cancel_move':
                        for d in self.selected_divs:
                            d.tx = d.ty = -1; d.path = []; d.move_progress = 0.0
                        self.toast("已取消移动", (200, 200, 200))
                    elif key.startswith('sel:'): self.select_army(int(key.split(':')[1]))
                    elif key.startswith('doc:'):
                        _, aid, dk = key.split(':'); self.set_army_doctrine(int(aid), dk)
                    elif key.startswith('dismiss:'): self.disband_army(int(key.split(':')[1]))
                    elif key.startswith('gen:'):
                        _, aid, gid = key.split(':')
                        self.assign_general(int(aid), int(gid))
                    return

    def do_action(self, key):
        p = self.nations.get(0)
        if not p or not p.alive: return
        if key == 'build_mil':
            if not p.build_type: p.build_type = 'mil'; p.build_progress = 0.0
        elif key == 'build_civ':
            if not p.build_type: p.build_type = 'civ'; p.build_progress = 0.0
        elif key == 'cycle_unit':
            keys = list(UNIT_TYPES.keys())
            idx = keys.index(self.recruit_type) if self.recruit_type in keys else 0
            self.recruit_type = keys[(idx+1) % len(keys)]
        elif key == 'recruit':
            ut = UNIT_TYPES.get(self.recruit_type, UNIT_TYPES['infantry'])
            disc = 1.0
            if self.selected_army >= 0:
                a = self.armies.get(self.selected_army)
                if a: disc = 1.0 - DOCTRINES[a.doctrine]['extra'].get('recruit_discount', 0.0)
            ce = int(ut['equip']*disc); cm = int(ut['manpower']*disc)

            spec = ut.get('is_special')
            if spec:
                if p.equipment < ce or p.manpower < cm:
                    self.toast("装备或人力不足", (240, 120, 100)); return
                p.equipment -= ce; p.manpower -= cm
                if spec == 'airforce':
                    p.airforce += 1.0
                    self.toast(f"空军联队 +1 (现 {p.airforce:.1f})", (200, 180, 240))
                    self.log_msg(f"组建空军联队，空军 {p.airforce:.1f}")
                else:
                    p.navy += 1.0
                    self.toast(f"海军舰队 +1 (现 {p.navy:.1f})", (130, 180, 220))
                    self.log_msg(f"组建海军舰队，海军 {p.navy:.1f}")
                return

            loc = None
            if self.selected:
                x, y = self.selected
                pr = self.prov[x][y]
                if pr.land and pr.owner == 0: loc = (x, y)
            if loc is None: loc = self.capitals.get(0)
            if loc and p.equipment >= ce and p.manpower >= cm:
                p.equipment -= ce; p.manpower -= cm
                days = 0 if self.cheats['instant_train'] else ut['days']
                p.train_queue.append(TrainOrder(loc[0], loc[1], days, self.recruit_type))
        elif key == 'cancel_move':
            for d in self.selected_divs:
                d.tx = d.ty = -1; d.path = []; d.move_progress = 0.0
            self.toast("已取消移动", (200, 200, 200))
        elif key == 'build_fort':
            if not self.selected: return
            sx, sy = self.selected
            pr = self.prov[sx][sy]
            if not pr.land or pr.owner != 0:
                self.toast("只能在本国省份修建", (240, 120, 100)); return
            if pr.fort >= 5:
                self.toast("防御工事已达上限 Lv5", (240, 120, 100)); return
            if p.pp < 30 or p.equipment < 200:
                self.toast("政治点(30)或装备(200)不足", (240, 120, 100)); return
            p.pp -= 30
            p.equipment -= 200
            pr.fort += 1
            self.map_dirty = True
            self.toast(f"防御工事建成 Lv{pr.fort}", (150, 230, 150))
            self.log_msg(f"在 ({sx},{sy}) 修建防御工事 Lv{pr.fort}")

    def apply_policy(self, key):
        if ':' not in key: return
        pk, lv = key.split(':'); lv = int(lv)
        p = self.nations.get(0)
        if not p: return
        pdef = POLICIES.get(pk)
        if not pdef or lv < 0 or lv >= len(pdef['levels']): return
        if p.policies.get(pk, 0) == lv: return
        cost = pdef['levels'][lv]['cost']
        if p.pp < cost: self.toast("政治点不足", (240, 120, 100)); return
        p.pp -= cost; p.policies[pk] = lv; self.recompute_bonuses(p)
        self.toast(f"{pdef['name']} → {pdef['levels'][lv]['name']}", (170, 220, 255))

    def do_diplomacy(self, key):
        if ':' not in key: return
        action, nid = key.split(':'); nid = int(nid)
        if nid == 0: return
        if action == 'war': self.declare_war(0, nid)
        elif action == 'peace': self.make_peace(0, nid)

    # ---------------- 渲染 ----------------
    def rebuild_map(self):
        surf = pygame.Surface((MAP_PX_W, MAP_PX_H))
        surf.fill(SEA_COLOR)
        for y in range(MAP_H):
            for x in range(MAP_W):
                p = self.prov[x][y]
                if not p.land: continue
                rect = pygame.Rect(x*TILE, y*TILE, TILE, TILE)
                base = self.nations[p.owner].color if p.owner in self.nations else NEUTRAL_COLOR
                col = (int(base[0]*0.72), int(base[1]*0.72), int(base[2]*0.72))
                surf.fill(col, rect)
                if p.terrain == 'forest':
                    for k in range(4):
                        rx = x*TILE+4 + ((x*7+y*13+k*29) % (TILE-8))
                        ry = y*TILE+4 + ((x*11+y*5+k*17) % (TILE-8))
                        dark = (max(0,col[0]-28), max(0,col[1]-22), max(0,col[2]-28))
                        pygame.draw.circle(surf, dark, (rx, ry), 2)
                elif p.terrain == 'mountain':
                    cx = x*TILE+TILE//2; cy = y*TILE+TILE//2
                    dark = (max(0,col[0]-48), max(0,col[1]-48), max(0,col[2]-48))
                    pygame.draw.polygon(surf, dark, [(cx-8,cy+7), (cx,cy-8), (cx+8,cy+7)])
                elif p.terrain == 'city':
                    pygame.draw.rect(surf, (238,228,196), (x*TILE+9, y*TILE+9, TILE-18, TILE-18))
                # v7.1: 防御工事可视化（右下角盾牌点阵，每点 = Lv1）
                if p.fort > 0:
                    lv = min(5, p.fort)
                    fx = x*TILE + TILE - 4
                    fy = y*TILE + TILE - 4
                    pygame.draw.rect(surf, (35,28,20), (fx-9, fy-7, 11, 9))
                    for k in range(lv):
                        pygame.draw.rect(surf, (235, 205, 120),
                                         (fx - 1 - k*2, fy - 6, 2, 7))
        for y in range(MAP_H):
            for x in range(MAP_W):
                p = self.prov[x][y]
                if not p.land: continue
                if x+1 < MAP_W:
                    q = self.prov[x+1][y]
                    if q.land and q.owner != p.owner:
                        pygame.draw.line(surf, BORDER_COLOR, (x*TILE+TILE-1, y*TILE),
                                         (x*TILE+TILE-1, y*TILE+TILE), 2)
                if y+1 < MAP_H:
                    q = self.prov[x][y+1]
                    if q.land and q.owner != p.owner:
                        pygame.draw.line(surf, BORDER_COLOR, (x*TILE, y*TILE+TILE-1),
                                         (x*TILE+TILE, y*TILE+TILE-1), 2)
        for nid, (cx, cy) in self.capitals.items():
            n = self.nations.get(nid)
            if not n or not n.alive: continue
            px = cx*TILE+TILE//2; py = cy*TILE+TILE//2
            pygame.draw.circle(surf, (250,230,120), (px, py), 5)
            pygame.draw.circle(surf, (60,50,20), (px, py), 5, 1)
        self.map_surface = surf
        self.map_dirty = False

    def draw_selection(self, screen):
        if self.hover:
            x, y = self.hover
            if self.prov[x][y].land:
                s = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
                s.fill((255, 255, 255, 40)); screen.blit(s, (x*TILE, y*TILE))
        sel_tiles = {(d.x, d.y) for d in self.selected_divs}
        if len(sel_tiles) > 1:
            for (tx, ty) in sel_tiles:
                s = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
                s.fill((255, 240, 100, 65))
                screen.blit(s, (tx*TILE, ty*TILE))
        if self.selected:
            x, y = self.selected
            pygame.draw.rect(screen, (255,255,255), (x*TILE, y*TILE, TILE, TILE), 2)
        for d in self.selected_divs:
            if d.has_target:
                pygame.draw.line(screen, (255,235,120),
                    (d.x*TILE+TILE//2, d.y*TILE+TILE//2),
                    (d.tx*TILE+TILE//2, d.ty*TILE+TILE//2), 2)
        if self.selected_army >= 0:
            a = self.armies.get(self.selected_army)
            if a:
                col = DOCTRINES[a.doctrine]['color']
                for d in a.divisions:
                    pygame.draw.circle(screen, col,
                        (d.x*TILE+TILE//2, d.y*TILE+TILE//2), TILE//2-1, 2)

    @staticmethod
    def _dot_positions(n):
        return {1: [(0,0)], 2: [(-4,-3),(4,3)], 3: [(-5,-3),(5,-3),(0,4)],
                4: [(-5,-5),(5,-5),(-5,5),(5,5)]}.get(n, [(-5,-5),(5,-5),(-5,5),(5,5)])

    def draw_divisions(self, screen, font_tiny):
        for y in range(MAP_H):
            for x in range(MAP_W):
                p = self.prov[x][y]
                if not p.divisions: continue
                groups = defaultdict(list)
                for d in p.divisions: groups[d.owner].append(d)
                main = max(groups, key=lambda k: len(groups[k]))
                n = self.nations.get(main)
                col = n.color if n else (220, 220, 220)
                cx = x*TILE+TILE//2; cy = y*TILE+TILE//2
                cnt = len(groups[main])
                if cnt <= 4:
                    for dx, dy in self._dot_positions(cnt):
                        pygame.draw.circle(screen, col, (cx+dx, cy+dy), 4)
                        pygame.draw.circle(screen, (245,245,245), (cx+dx, cy+dy), 4, 1)
                else:
                    for dx, dy in self._dot_positions(4):
                        pygame.draw.circle(screen, col, (cx+dx, cy+dy), 3)
                        pygame.draw.circle(screen, (245,245,245), (cx+dx, cy+dy), 3, 1)
                    t = font_tiny.render(str(cnt), True, (255,255,255))
                    bg = pygame.Surface((t.get_width()+4, t.get_height()+2), pygame.SRCALPHA)
                    bg.fill((20,20,20,180))
                    screen.blit(bg, (cx-bg.get_width()//2, cy-bg.get_height()//2))
                    screen.blit(t, (cx-t.get_width()//2, cy-t.get_height()//2))
                if len(groups) > 1:
                    blink = math.sin(pygame.time.get_ticks()/125.0) > 0
                    color = (255,80,60) if blink else (255,200,80)
                    pygame.draw.rect(screen, color, (cx-11, cy-11, 22, 22), 2)
                if (x, y) in self.cut_off_provs.get(main, ()):
                    pygame.draw.line(screen, (255,60,60), (cx-8,cy-8), (cx+8,cy+8), 2)

    def draw_panel(self, screen, f_big, f_mid, f_small):
        px = MAP_PX_W
        pygame.draw.rect(screen, (32,36,48), (px, 0, PANEL_W, SCREEN_H))
        pygame.draw.line(screen, (70,78,96), (px, 0), (px, SCREEN_H), 2)
        x0 = px + 14; y = 10
        date_str = f"{self.year}年{self.month}月{self.day}日  {self.hour:02d}:00"
        screen.blit(f_big.render(date_str, True, (235,238,245)), (x0, y)); y += 26
        wdef = WEATHER_DEFS[self.weather]
        speed_txt = "暂停" if self.speed == 0 else f"x{self.speed}"
        screen.blit(f_small.render(f"空格暂停 | 1-4 速度 | B 轰炸 | Shift+左键多选", True, (150,160,180)), (x0, y)); y += 18
        screen.blit(f_small.render(f"选中己方省可在概览标签修建防御工事", True, (150,160,180)), (x0, y)); y += 18
        screen.blit(f_small.render(f"{speed_txt}   天气: {wdef['name']}", True, wdef['color']), (x0, y)); y += 22
        tabs = [('overview','概览'),('research','科研'),('policy','政策'),
                ('generals','将领'),('armies','军'),('diplomacy','外交')]
        tw = (PANEL_W-28)//len(tabs)
        for i, (key, label) in enumerate(tabs):
            r = pygame.Rect(x0+i*tw, y, tw-2, 24)
            active = (self.ui_tab == key)
            base = (70,110,170) if active else (46,52,66)
            mx, my = pygame.mouse.get_pos()
            if r.collidepoint((mx,my)) and not active: base = (60,78,108)
            pygame.draw.rect(screen, base, r, border_radius=3)
            t = f_small.render(label, True, (240,244,250))
            screen.blit(t, (r.x+(r.w-t.get_width())//2, r.y+(r.h-t.get_height())//2))
            self.buttons[f'tab_{key}'] = r
        y += 30
        pygame.draw.line(screen, (60,68,84), (x0, y), (px+PANEL_W-14, y)); y += 8

        content_top = y
        self.panel_content_top = content_top
        view_h = SCREEN_H - content_top
        old_clip = screen.get_clip()
        screen.set_clip(pygame.Rect(px, content_top, PANEL_W, view_h))

        y = content_top - self.panel_scroll

        if   self.ui_tab == 'overview':  y = self.draw_tab_overview(screen, x0, y, f_big, f_mid, f_small)
        elif self.ui_tab == 'research':  y = self.draw_tab_research(screen, x0, y, f_big, f_mid, f_small)
        elif self.ui_tab == 'policy':    y = self.draw_tab_policy(screen, x0, y, f_big, f_mid, f_small)
        elif self.ui_tab == 'generals':  y = self.draw_tab_generals(screen, x0, y, f_big, f_mid, f_small)
        elif self.ui_tab == 'armies':    y = self.draw_tab_armies(screen, x0, y, f_big, f_mid, f_small)
        elif self.ui_tab == 'diplomacy': y = self.draw_tab_diplomacy(screen, x0, y, f_big, f_mid, f_small)

        y += 6
        pygame.draw.line(screen, (60,68,84), (x0, y), (px+PANEL_W-14, y)); y += 8

        if self.selected:
            sx, sy = self.selected
            sp = self.prov[sx][sy]
            if sp.land:
                oname = self.nations[sp.owner].name if sp.owner in self.nations else "无主"
                screen.blit(f_small.render(
                    f"省 ({sx},{sy}) {oname} | {TERRAIN_INFO[sp.terrain]['label']}",
                    True, (200,210,225)), (x0, y)); y += 16
                screen.blit(f_small.render(
                    f"VP {sp.vp} 工业 {sp.industry} 补给上限 {sp.supply_cap:.1f} 要塞 Lv{sp.fort}",
                    True, (200,210,225)), (x0, y)); y += 18
                if sp.divisions:
                    screen.blit(f_small.render("驻军:", True, (230,230,240)), (x0, y)); y += 15
                    for d in sp.divisions[:6]:
                        dn = self.nations.get(d.owner)
                        dc = dn.color if dn else (200,200,200)
                        etxt = f" Lv{d.experience:.0f}" if d.experience > 1 else ""
                        ln = f"  {d.info['name']}  str{d.strength:.0f} org{d.org:.0f}{etxt}"
                        screen.blit(f_small.render(ln, True, dc), (x0, y)); y += 14
                    if len(sp.divisions) > 6:
                        screen.blit(f_small.render(f"  ...还有 {len(sp.divisions)-6} 个", True, (180,180,180)), (x0, y)); y += 14
                else:
                    screen.blit(f_small.render("（无敌军驻扎）", True, (150,150,160)), (x0, y)); y += 15
            else:
                screen.blit(f_small.render("海洋", True, (140,170,210)), (x0, y)); y += 18

        if len({(d.x, d.y) for d in self.selected_divs}) > 1:
            tiles = len({(d.x, d.y) for d in self.selected_divs})
            screen.blit(f_small.render(
                f"★ 多选中: {len(self.selected_divs)} 师 / {tiles} 省",
                True, (255, 240, 100)), (x0, y)); y += 16
            screen.blit(f_small.render(
                f"  打开「军」标签 → 点击「＋ 编军」组建集团军",
                True, (200, 210, 230)), (x0, y)); y += 16

        y += 4
        pygame.draw.line(screen, (60,68,84), (x0, y), (px+PANEL_W-14, y)); y += 6
        for msg in self.log[-6:]:
            screen.blit(f_small.render(msg, True, (180,188,200)), (x0, y)); y += 16

        content_h = (y + self.panel_scroll) - content_top + 10
        self.panel_max_scroll = max(0, content_h - view_h)
        if self.panel_scroll > self.panel_max_scroll:
            self.panel_scroll = self.panel_max_scroll

        if self.panel_max_scroll > 0:
            bar_x = px + PANEL_W - 6
            bar_top = content_top + 4
            bar_h = view_h - 8
            pygame.draw.rect(screen, (48,54,68), (bar_x, bar_top, 4, bar_h), border_radius=2)
            frac = self.panel_scroll / self.panel_max_scroll
            knob_h = max(24, int(bar_h * view_h / content_h))
            knob_y = bar_top + int((bar_h - knob_h) * frac)
            pygame.draw.rect(screen, (140,160,190), (bar_x, knob_y, 4, knob_h), border_radius=2)

        screen.set_clip(old_clip)
        return y

    def draw_tab_overview(self, screen, x0, y, f_big, f_mid, f_small):
        p = self.nations.get(0)
        if not p or not p.alive:
            screen.blit(f_mid.render("国家已灭亡", True, (220,90,90)), (x0, y)); return y+30
        screen.blit(f_mid.render(f"◤ {p.name}", True, p.color), (x0, y)); y += 22
        lines = [f"政治点 {p.pp:6.1f}", f"人力 {int(p.manpower):,}", f"装备 {int(p.equipment):,}",
                 f"海军 {p.navy:5.1f}   空军 {p.airforce:5.1f}",
                 f"民用 {p.civ}  军用 {p.mil}",
                 f"省份 {len(self.provinces_of(0))}  现役师 {sum(1 for d in self.all_divisions() if d.owner==0)}"]
        for ln in lines:
            screen.blit(f_small.render(ln, True, (200,208,222)), (x0, y)); y += 18
        if p.build_type:
            name = "军用工厂" if p.build_type=='mil' else "民用工厂"
            pct = min(100, int(p.build_progress/120.0*100))
            screen.blit(f_small.render(f"建造中: {name} {pct}%", True, (240,210,120)), (x0, y)); y += 18
        if p.active_research:
            t = TECH_BY_ID.get(p.active_research)
            if t:
                pct = min(100, int(p.research_points/t.cost*100))
                screen.blit(f_small.render(f"研究中: {t.name} {pct}%", True, (150,220,255)), (x0, y)); y += 18
        y += 6
        bw = PANEL_W-28; bh = 28
        def make_btn(key, label, enabled=True):
            nonlocal y
            rect = pygame.Rect(x0, y, bw, bh)
            mx, my = pygame.mouse.get_pos()
            hover = rect.collidepoint((mx,my)) and enabled
            base = (58,96,148) if enabled else (58,62,72)
            if hover: base = (78,122,180)
            pygame.draw.rect(screen, base, rect, border_radius=4)
            pygame.draw.rect(screen, (100,112,132), rect, 1, border_radius=4)
            t = f_small.render(label, True, (240,244,250) if enabled else (140,145,155))
            screen.blit(t, (rect.x+10, rect.y+(bh-t.get_height())//2))
            self.buttons[key] = rect
            y += bh + 5
        make_btn('build_mil', "建造 军用工厂", not p.build_type)
        make_btn('build_civ', "建造 民用工厂", not p.build_type)
        ut = UNIT_TYPES[self.recruit_type]
        make_btn('cycle_unit', f"切换兵种: {ut['name']}")
        disc = 0.0
        if self.selected_army >= 0:
            a = self.armies.get(self.selected_army)
            if a: disc = DOCTRINES[a.doctrine]['extra'].get('recruit_discount', 0.0)
        ce = int(ut['equip']*(1-disc)); cm = int(ut['manpower']*(1-disc))
        can = p.equipment >= ce and p.manpower >= cm
        tag = f" (-{int(disc*100)}%)" if disc > 0 else ""
        if ut.get('is_special') == 'airforce':
            lbl = f"招募 空军联队 (+1 空军, {ce}装备/{cm}人力)"
        elif ut.get('is_special') == 'navy':
            lbl = f"招募 海军舰队 (+1 海军, {ce}装备/{cm}人力)"
        else:
            lbl = f"招募 {ut['name']} ({ce}装备/{cm}人力){tag}"
        make_btn('recruit', lbl, can)
        make_btn('cancel_move', "取消选中师移动", bool(self.selected_divs))

        # ===== v7.1: 修建防御工事按钮 =====
        sp = None
        if self.selected:
            sx, sy = self.selected
            sp_cand = self.prov[sx][sy]
            if sp_cand.land: sp = sp_cand
        if sp is not None and sp.owner == 0:
            if sp.fort >= 5:
                make_btn('build_fort', f"防御工事 Lv{sp.fort} (已满级)", False)
            else:
                can_fort = (p.pp >= 30 and p.equipment >= 200)
                make_btn('build_fort',
                         f"修建防御工事 Lv{sp.fort}→{sp.fort+1} (30政/200装)",
                         can_fort)
        else:
            make_btn('build_fort', "修建防御工事 (需选中本国省)", False)
        # ===================================

        if p.train_queue:
            screen.blit(f_small.render(f"训练中: {len(p.train_queue)} 个师", True, (200,180,120)), (x0, y)); y += 18
        return y

    def draw_tab_research(self, screen, x0, y, f_big, f_mid, f_small):
        self.research_buttons = {}
        p = self.nations.get(0)
        if not p: return y
        screen.blit(f_small.render(f"研究点 {p.research_points:.0f}  民用工厂 {p.civ}", True, (200,210,225)), (x0, y)); y += 20
        if p.active_research:
            t = TECH_BY_ID.get(p.active_research)
            row = pygame.Rect(x0, y, PANEL_W-28, 26)
            pygame.draw.rect(screen, (140,70,70), row, border_radius=4)
            tt = f_small.render(f"✕ 取消 {t.name if t else '?'}", True, (250,240,240))
            screen.blit(tt, (row.x+8, row.y+(row.h-tt.get_height())//2))
            self.research_buttons['__cancel__'] = row
            y += 30
        by_cat = defaultdict(list)
        for t in TECHS: by_cat[t.category].append(t)
        for cat in ("陆军","工业","后勤"):
            screen.blit(f_mid.render(f"── {cat} ──", True, (240,220,160)), (x0, y)); y += 22
            for t in by_cat.get(cat, []):
                done = t.id in p.completed_techs
                active = (p.active_research == t.id)
                can = (not done) and (not active) and all(r in p.completed_techs for r in t.requires) and (not p.active_research)
                row = pygame.Rect(x0, y, PANEL_W-28, 36)
                mx, my = pygame.mouse.get_pos()
                hover = row.collidepoint((mx,my)) and can
                if done: base = (40,90,60)
                elif active: base = (120,90,40)
                elif can: base = (58,96,148)
                else: base = (50,54,64)
                if hover: base = (78,122,180)
                pygame.draw.rect(screen, base, row, border_radius=4)
                pygame.draw.rect(screen, (110,120,140), row, 1, border_radius=4)
                status = "已完成" if done else ("进行中" if active else f"花费 {int(t.cost)}")
                screen.blit(f_small.render(f"{t.name}  [{status}]", True, (240,244,250)), (row.x+8, row.y+2))
                screen.blit(f_small.render(t.desc, True, (200,210,225)), (row.x+8, row.y+18))
                if can: self.research_buttons[t.id] = row
                y += 40
            y += 4
        return y

    def draw_tab_policy(self, screen, x0, y, f_big, f_mid, f_small):
        self.policy_buttons = {}
        p = self.nations.get(0)
        if not p: return y
        screen.blit(f_small.render(f"政治点 {p.pp:.1f}", True, (200,210,225)), (x0, y)); y += 20
        for pk, pdef in POLICIES.items():
            screen.blit(f_mid.render(pdef['name'], True, (240,220,160)), (x0, y)); y += 22
            cur = p.policies.get(pk, 0)
            for idx, lv in enumerate(pdef['levels']):
                row = pygame.Rect(x0, y, PANEL_W-28, 28)
                mx, my = pygame.mouse.get_pos()
                is_cur = (cur == idx); can = (not is_cur) and (p.pp >= lv['cost'])
                hover = row.collidepoint((mx,my)) and can
                if is_cur: base = (40,90,60)
                elif can: base = (58,96,148)
                else: base = (50,54,64)
                if hover: base = (78,122,180)
                pygame.draw.rect(screen, base, row, border_radius=4)
                pygame.draw.rect(screen, (110,120,140), row, 1, border_radius=4)
                tag = "◀ 当前" if is_cur else f"花费 {lv['cost']}"
                screen.blit(f_small.render(f"{lv['name']}  [{tag}]", True, (240,244,250)),
                            (row.x+8, row.y+(row.h-15)//2))
                if can: self.policy_buttons[f'{pk}:{idx}'] = row
                y += 32
            y += 4
        return y

    def draw_tab_generals(self, screen, x0, y, f_big, f_mid, f_small):
        self.general_buttons = {}
        p = self.nations.get(0)
        if not p: return y
        screen.blit(f_small.render("点击激活/取消(全局加成) — 军内指派在「军」标签", True, (150,160,180)), (x0, y))
        y += 22

        bw = PANEL_W - 28
        btn = pygame.Rect(x0, y, bw, 28)
        can = (p.pp >= 100)
        mx, my = pygame.mouse.get_pos()
        base = (58,96,148) if can else (50,54,64)
        if can and btn.collidepoint((mx,my)): base = (78,122,180)
        pygame.draw.rect(screen, base, btn, border_radius=4)
        pygame.draw.rect(screen, (110,120,140), btn, 1, border_radius=4)
        t = f_small.render(f"＋ 招募新将领  (消耗 100 政治点)", True,
                           (240,244,250) if can else (140,145,155))
        screen.blit(t, (btn.x + (btn.w - t.get_width())//2,
                        btn.y + (btn.h - t.get_height())//2))
        if can: self.general_buttons['__recruit__'] = btn
        y += 36

        for g in p.generals:
            row = pygame.Rect(x0, y, PANEL_W-28, 58)
            is_active = (p.active_general_id == g.id)
            hover = row.collidepoint((mx,my))
            base = (40,90,60) if is_active else (58,96,148)
            if hover: base = (78,122,180)
            pygame.draw.rect(screen, base, row, border_radius=4)
            pygame.draw.rect(screen, (110,120,140), row, 1, border_radius=4)
            star = " ★" if is_active else ""
            army_tag = f"  → {self.armies[g.assigned_army].name}" if g.assigned_army in self.armies else ""
            screen.blit(f_small.render(f"{g.name}  Lv.{g.level}{star}{army_tag}",
                                       True, (240,244,250)), (row.x+8, row.y+3))
            screen.blit(f_small.render(
                f"攻+{g.attack*100:.0f}%  防+{g.defense*100:.0f}%  后勤+{g.logistics*100:.0f}%",
                True, (200,210,225)), (row.x+8, row.y+22))
            need = 60.0 * g.level
            frac = min(1.0, (g.experience or 0.0) / max(1.0, need))
            bar = pygame.Rect(row.x+8, row.y+44, row.w-16, 7)
            pygame.draw.rect(screen, (30,34,44), bar, border_radius=3)
            if frac > 0:
                pygame.draw.rect(screen, (160,220,255),
                                 (bar.x, bar.y, int(bar.w*frac), bar.h), border_radius=3)
            xp_txt = f_small.render(f"{int(g.experience or 0)}/{int(need)}", True, (200,215,235))
            screen.blit(xp_txt, (bar.right - xp_txt.get_width(), bar.y - 14))
            self.general_buttons[g.id] = row
            y += 62
        return y

    def draw_tab_armies(self, screen, x0, y, f_big, f_mid, f_small):
        self.army_buttons = {}
        p = self.nations.get(0)
        if not p: return y
        bw = PANEL_W-28
        screen.blit(f_small.render("以军为单位编组 | Shift+左键 追加多选", True, (150,160,180)), (x0, y)); y += 22
        free = [d for d in self.selected_divs if d.owner == 0 and d.army_id < 0]
        can = len(free) > 0
        btn = pygame.Rect(x0, y, bw, 26)
        mx, my = pygame.mouse.get_pos()
        base = (58,96,148) if can else (50,54,64)
        if can and btn.collidepoint((mx,my)): base = (78,122,180)
        pygame.draw.rect(screen, base, btn, border_radius=4)
        if can:
            tiles = len({(d.x, d.y) for d in free})
            if tiles > 1:
                label = f"＋ 编军 ({len(free)} 师 / 跨 {tiles} 省)"
            else:
                label = f"＋ 从选中省份编军 ({len(free)} 空闲师)"
        else:
            label = "先选中己方省份 (Shift+左键 可多选)"
        t = f_small.render(label, True, (240,244,250) if can else (140,145,155))
        screen.blit(t, (btn.x+8, btn.y+(btn.h-t.get_height())//2))
        if can: self.army_buttons['create'] = btn
        y += 32
        if self.selected_divs:
            clr = pygame.Rect(x0, y, bw, 22)
            hov = clr.collidepoint((mx, my))
            bg = (100, 70, 70) if not hov else (140, 90, 90)
            pygame.draw.rect(screen, bg, clr, border_radius=4)
            tt = f_small.render(f"✕ 清空当前选择 ({len(self.selected_divs)} 师)", True, (240,240,245))
            screen.blit(tt, (clr.x+8, clr.y+(clr.h-tt.get_height())//2))
            self.army_buttons['__clear_sel__'] = clr
            y += 26
        my_armies = [a for a in self.armies.values() if a.owner == 0]
        if not my_armies:
            screen.blit(f_small.render("（暂未编成任何军）", True, (160,160,170)), (x0, y))
            return y+20
        for army in my_armies:
            doc = DOCTRINES[army.doctrine]
            row = pygame.Rect(x0, y, bw, 50)
            mx, my = pygame.mouse.get_pos()
            is_sel = (self.selected_army == army.id); hover = row.collidepoint((mx,my))
            bg = tuple(int(c*0.42) for c in doc['color'])
            if is_sel: bg = tuple(int(c*0.65) for c in doc['color'])
            if hover: bg = tuple(min(255, int(c*1.25)) for c in bg)
            pygame.draw.rect(screen, bg, row, border_radius=4)
            pygame.draw.rect(screen, doc['color'], row, 1, border_radius=4)
            screen.blit(f_small.render(army.name, True, (250,250,250)), (row.x+8, row.y+3))
            dt = f_small.render(f"[{doc['name']}]", True, doc['color'])
            screen.blit(dt, (row.right-dt.get_width()-8, row.y+3))
            size_col = (250,200,120) if army.size() >= army.max_size() else (220,225,235)
            screen.blit(f_small.render(f"{army.size()}/{army.max_size()} 师", True, size_col),
                        (row.x+8, row.y+26))
            if army.divisions:
                tiles = len({(d.x, d.y) for d in army.divisions})
                ax = int(sum(d.x for d in army.divisions)/len(army.divisions))
                ay = int(sum(d.y for d in army.divisions)/len(army.divisions))
                pos = f"@({ax},{ay})" if tiles == 1 else f"@({ax},{ay})·{tiles}省"
            else: pos = "@—"
            screen.blit(f_small.render(pos, True, (200,210,225)), (row.right-90, row.y+26))
            self.army_buttons[f'sel:{army.id}'] = row
            y += 54
            if is_sel:
                if p.generals:
                    screen.blit(f_small.render("指派将领:", True, (200,210,225)), (x0, y)); y += 16
                    for g in p.generals:
                        gbtn = pygame.Rect(x0+6, y, bw-12, 20)
                        active = (army.general_id == g.id)
                        base2 = (60,120,80) if active else (55,70,95)
                        if gbtn.collidepoint((mx,my)): base2 = tuple(min(255, c+25) for c in base2)
                        pygame.draw.rect(screen, base2, gbtn, border_radius=3)
                        tt = f_small.render(f"{g.name} Lv.{g.level}", True, (240,240,245))
                        screen.blit(tt, (gbtn.x+6, gbtn.y+(gbtn.h-tt.get_height())//2))
                        self.army_buttons[f'gen:{army.id}:{g.id}'] = gbtn
                        y += 22
                    y += 4
                screen.blit(f_small.render("切换流派:", True, (200,210,225)), (x0, y)); y += 16
                for dk, dd in DOCTRINES.items():
                    dbtn = pygame.Rect(x0+6, y, bw-12, 22)
                    active = (army.doctrine == dk)
                    db = tuple(int(c*0.55) for c in dd['color']) if not active else tuple(int(c*0.85) for c in dd['color'])
                    if dbtn.collidepoint((mx,my)): db = tuple(min(255, int(c*1.3)) for c in db)
                    pygame.draw.rect(screen, db, dbtn, border_radius=3)
                    pygame.draw.rect(screen, dd['color'], dbtn, 1, border_radius=3)
                    tt = f_small.render(f"{dd['name']} · {dd['desc']}", True, (240,240,245))
                    screen.blit(tt, (dbtn.x+6, dbtn.y+(dbtn.h-tt.get_height())//2))
                    self.army_buttons[f'doc:{army.id}:{dk}'] = dbtn
                    y += 24
                dbtn = pygame.Rect(x0+6, y, bw-12, 20)
                pygame.draw.rect(screen, (130,55,55), dbtn, border_radius=3)
                tt = f_small.render("解散该军", True, (250,240,240))
                screen.blit(tt, (dbtn.x+6, dbtn.y+(dbtn.h-tt.get_height())//2))
                self.army_buttons[f'dismiss:{army.id}'] = dbtn
                y += 26
        return y

    def draw_tab_diplomacy(self, screen, x0, y, f_big, f_mid, f_small):
        self.diplomacy_buttons = {}
        p = self.nations.get(0)
        if not p: return y
        screen.blit(f_small.render("外交关系", True, (150,160,180)), (x0, y)); y += 20
        for nid, other in self.nations.items():
            if nid == 0 or not other.alive: continue
            row = pygame.Rect(x0, y, PANEL_W-28, 44)
            pygame.draw.rect(screen, (40,46,58), row, border_radius=4)
            pygame.draw.rect(screen, (80,90,110), row, 1, border_radius=4)
            war = self.at_war(0, nid); rel = p.relations.get(nid, 0)
            col = (220,100,100) if war else (200,210,225)
            screen.blit(f_small.render(f"{other.name}   关系 {rel:.0f}", True, col), (row.x+8, row.y+2))
            bw = 100; bh = 22
            btn = pygame.Rect(row.right-bw-6, row.y+12, bw, bh)
            mx, my = pygame.mouse.get_pos()
            if war:
                base = (100,80,140)
                if btn.collidepoint((mx,my)): base = (130,110,180)
                pygame.draw.rect(screen, base, btn, border_radius=3)
                t = f_small.render("提议停战", True, (240,244,250))
                self.diplomacy_buttons[f'peace:{nid}'] = btn
            else:
                base = (140,70,70)
                if btn.collidepoint((mx,my)): base = (180,90,90)
                pygame.draw.rect(screen, base, btn, border_radius=3)
                t = f_small.render("宣战", True, (240,244,250))
                self.diplomacy_buttons[f'war:{nid}'] = btn
            screen.blit(t, (btn.x+(btn.w-t.get_width())//2, btn.y+(btn.h-t.get_height())//2))
            y += 48
        return y

    def draw_cheat_panel(self, screen, f_mid, f_small):
        if not self.cheat_open:
            self.cheat_rows = []; return
        rect, rows = self.cheat_panel_layout()
        self.cheat_panel_rect = rect
        self.cheat_rows = [(k, r) for k, r, _, _ in rows]
        overlay = pygame.Surface((rect.w, rect.h), pygame.SRCALPHA)
        overlay.fill((16,18,26,238)); screen.blit(overlay, rect.topleft)
        pygame.draw.rect(screen, (255,200,80), rect, 2, border_radius=6)
        pad_x = 14; x0 = rect.x+pad_x; y = rect.y+10
        screen.blit(f_mid.render("⚙ 作弊控制台", True, (255,210,100)), (x0, y))
        hint = f_small.render("按 ~ / G 关闭", True, (150,160,180))
        screen.blit(hint, (rect.right-pad_x-hint.get_width(), y+4))
        y += 30
        pygame.draw.line(screen, (80,88,104), (x0, y), (rect.right-pad_x, y))
        mx, my = pygame.mouse.get_pos()
        for key, r, kind, label in rows:
            hover = r.collidepoint((mx,my))
            if kind == 'toggle':
                enabled = self.cheats.get(key, False)
                base = (46,120,78) if enabled else (70,58,62)
                if hover: base = tuple(min(255, c+26) for c in base)
                txt = f"{label} 【{'开' if enabled else '关'}】"
            else:
                base = (62,88,140)
                if hover: base = (86,116,176)
                txt = label
            pygame.draw.rect(screen, base, r, border_radius=4)
            pygame.draw.rect(screen, (110,120,140), r, 1, border_radius=4)
            t = f_small.render(txt, True, (238,242,250))
            screen.blit(t, (r.x+10, r.y+(r.h-t.get_height())//2))
        tip = f_small.render("Ctrl+左键 直接占领 | Ctrl+F5/F6/F7 存档1/2/3", True, (255,210,100))
        screen.blit(tip, (x0, y+12))

    def draw_toasts(self, screen, f_mid):
        y = 20; x = MAP_PX_W//2
        for t in self.toasts:
            alpha = max(0, int(255*(1 - t['t']/2.6)))
            surf = f_mid.render(t['msg'], True, t['color'])
            w, h = surf.get_size()
            bg = pygame.Surface((w+20, h+10), pygame.SRCALPHA)
            bg.fill((20,24,34, min(200, alpha)))
            bg.blit(surf, (10, 5)); bg.set_alpha(alpha)
            screen.blit(bg, (x - bg.get_width()//2, y)); y += h+16

    def draw_target_mode_hint(self, screen, f_mid):
        if self.target_mode == 'bomb':
            msg = "战略轰炸模式: 点击敌方省份 (ESC 取消)"
            surf = f_mid.render(msg, True, (255,200,120))
            bg = pygame.Surface((surf.get_width()+20, surf.get_height()+10), pygame.SRCALPHA)
            bg.fill((20,20,30,220)); bg.blit(surf, (10, 5))
            screen.blit(bg, (20, MAP_PX_H-40))

    def draw(self, screen, fonts):
        f_big, f_mid, f_small, f_tiny = fonts
        if self.map_dirty or self.map_surface is None: self.rebuild_map()
        screen.blit(self.map_surface, (0, 0))
        self.draw_selection(screen)
        self.draw_divisions(screen, f_tiny)
        self.draw_effects(screen)
        self.buttons = {}
        self.draw_panel(screen, f_big, f_mid, f_small)
        self.draw_cheat_panel(screen, f_mid, f_small)
        self.draw_target_mode_hint(screen, f_mid)
        self.draw_toasts(screen, f_mid)

# ============ 主程序 ============
def main():
    pygame.init()
    screen = pygame.display.set_mode((SCREEN_W, SCREEN_H))
    pygame.display.set_caption("钢铁雄心 v7.1 · 1937  [Shift+左键多选 | ~作弊 | B轰炸 | F5/F9 存档]")
    clock = pygame.time.Clock()
    fonts = (load_font(19, True), load_font(15, True), load_font(13), load_font(11, True))
    game = Game()
    running = True
    while running:
        dt = clock.tick(FPS) / 1000.0
        for e in pygame.event.get():
            if e.type == pygame.QUIT:
                running = False
            else:
                game.handle_event(e)
        if not running: break
        game.update(dt)
        game.tick_naval()
        screen.fill((0, 0, 0))
        game.draw(screen, fonts)
        pygame.display.flip()
    pygame.quit()

if __name__ == "__main__":
    main()