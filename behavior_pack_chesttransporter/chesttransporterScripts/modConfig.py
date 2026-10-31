# -*- coding: utf-8 -*-
"""ChestTransporter 全局配置。

所有"可调整"的东西都放这里，脚本其它文件不要写死常量。
"""

# ---------------------------------------------------------------- 命名空间
MOD_NAME = "chesttransporter"
MOD_VERSION = "1.0.0"
SERVER_SYSTEM_NAME = "ChestTransporterServer"
SERVER_SYSTEM_CLS = "chesttransporterScripts.chestTransporterServer.ChestTransporterServer"
CLIENT_SYSTEM_NAME = "ChestTransporterClient"
CLIENT_SYSTEM_CLS = "chesttransporterScripts.chestTransporterClient.ChestTransporterClient"

# ---------------------------------------------------------------- 物品
# 材质 key -> 耐久上限
DURABILITY = {
    "wood": 10,
    "copper": 20,
    "iron": 50,
    "gold": 90,
    "diamond": 100,
    "obsidian": 300,
}

# 材质 key 的升级顺序（黑曜石不在链里，只能单独合成）
UPGRADE_CHAIN = ["wood", "copper", "iron", "gold", "diamond"]

# 中文名（仅用于提示消息，界面名走 lang 文件）
DISPLAY_NAME = {
    "wood": u"木质搬箱器",
    "copper": u"铜质搬箱器",
    "iron": u"铁质搬箱器",
    "gold": u"金质搬箱器",
    "diamond": u"钻石质搬箱器",
    "obsidian": u"黑曜石质搬箱器",
}


def item_id(tier, filled=False):
    """材质 key -> 完整物品 identifier。

    filled=True 是「已装进容器」的变体，只有贴图不同，其它完全一致。
    """
    suffix = "_full" if filled else ""
    return "%s:chesttransporter_%s%s" % (MOD_NAME, tier, suffix)


# 反查表：identifier -> tier（空的和装满的都收）
ITEM_TO_TIER = {}
for _t in DURABILITY:
    ITEM_TO_TIER[item_id(_t, False)] = _t
    ITEM_TO_TIER[item_id(_t, True)] = _t

# ---------------------------------------------------------------- 可搬运方块
# 只收录"有存储界面"的容器 + 刷怪笼
SUPPORTED_BLOCKS = {
    # 原版容器
    "minecraft:chest": "chest",
    "minecraft:trapped_chest": "chest",
    "minecraft:barrel": "barrel",
    "minecraft:ender_chest": "ender_chest",
    "minecraft:furnace": "furnace",
    "minecraft:lit_furnace": "furnace",
    "minecraft:blast_furnace": "furnace",
    "minecraft:lit_blast_furnace": "furnace",
    "minecraft:smoker": "furnace",
    "minecraft:lit_smoker": "furnace",
    "minecraft:hopper": "hopper",
    "minecraft:dispenser": "dispenser",
    "minecraft:dropper": "dropper",
    "minecraft:brewing_stand": "brewing_stand",
    # 1.21 铜箱子（8 种氧化 / 打蜡状态）
    "minecraft:copper_chest": "chest",
    "minecraft:exposed_copper_chest": "chest",
    "minecraft:weathered_copper_chest": "chest",
    "minecraft:oxidized_copper_chest": "chest",
    "minecraft:waxed_copper_chest": "chest",
    "minecraft:waxed_exposed_copper_chest": "chest",
    "minecraft:waxed_weathered_copper_chest": "chest",
    "minecraft:waxed_oxidized_copper_chest": "chest",
    # 刷怪笼
    "minecraft:mob_spawner": "spawner",
}

# 潜影盒（含 16 种染色变体）单独拼
_SHULKER_COLORS = [
    "white", "orange", "magenta", "light_blue", "yellow", "lime", "pink",
    "gray", "light_gray", "cyan", "purple", "blue", "brown", "green", "red",
    "black",
]
for _c in _SHULKER_COLORS:
    SUPPORTED_BLOCKS["minecraft:%s_shulker_box" % _c] = "shulker_box"
SUPPORTED_BLOCKS["minecraft:shulker_box"] = "shulker_box"
SUPPORTED_BLOCKS["minecraft:undyed_shulker_box"] = "shulker_box"

# 放下时允许被覆盖的方块（空气 / 水 / 草 等）
REPLACEABLE_BLOCKS = set([
    "minecraft:air",
    "minecraft:water",
    "minecraft:flowing_water",
    "minecraft:tallgrass",
    "minecraft:short_grass",
    "minecraft:double_plant",
    "minecraft:snow_layer",
    "minecraft:vine",
    "minecraft:deadbush",
    "minecraft:fire",
    "minecraft:structure_void",
])

# 刷怪笼是否允许搬运
ALLOW_PICKUP_SPAWNER = True

# ---------------------------------------------------------------- 耐久
# 每次搬 / 放 消耗多少耐久
DURABILITY_COST = 1

# 剩余耐久 <= 这个值时提示玩家「快用完了」
DURABILITY_WARN_AT = 2

# 升级时按"剩余比例"换算到新上限
def inherited_durability(remain, old_max, new_max):
    """按比例继承耐久，向上取整；至少保留 1 点（0 会直接损坏）"""
    if old_max <= 0:
        return new_max
    if remain <= 0:
        return 0
    if remain >= old_max:
        return new_max
    val = int(round(float(remain) * float(new_max) / float(old_max) + 0.5))
    if val < 1:
        val = 1
    if val > new_max:
        val = new_max
    return val


# ---------------------------------------------------------------- 黑曜石特性
# 掉落物形态具备下界之星级防爆 + 岩浆不销毁
OBSIDIAN_IMMUNE_FIRE = True
OBSIDIAN_BLAST_PROOF = True

# ---------------------------------------------------------------- 减益
# 抱着箱子时的 debuff（与原 Java 版一致）
DEBUFF_ENABLED = {
    "slowness": True,        # 缓慢
    "mining_fatigue": True,  # 挖掘疲劳
    "jump_boost": True,      # 跳跃下降（负等级）
    "hunger": True,          # 饥饿
}
DEBUFF_INTERVAL_SEC = 1.0
DEBUFF_DURATION_TICK = 60   # 每次给的持续时间（游戏刻，20/秒 -> 3 秒）

# ---------------------------------------------------------------- 附魔
# 白名单：只允许这 3 种，其余一律清除
ENCHANT_UNBREAKING = "unbreaking"
ENCHANT_MENDING = "mending"
ENCHANT_VANISHING = "vanishing"

ALLOWED_ENCHANTS = set([ENCHANT_UNBREAKING, ENCHANT_MENDING, ENCHANT_VANISHING])

# 附魔英文名 -> 可能的数字 id 回退表
# 运行时优先用 GetAllEnchantsInfo() 动态解析，解析失败才用这张表。
# 数字 id 若与你当前版本不符，改这里即可。
ENCHANT_ID_FALLBACK = {
    ENCHANT_UNBREAKING: [22],
    ENCHANT_MENDING: [37],
    ENCHANT_VANISHING: [38],
}

# 互斥规则（有向）：
#   有耐久  -> 禁止 加经验修补
#   有经验修补 -> 禁止 加耐久
#   有消失诅咒 -> 禁止 加耐久
#   有耐久  -> 允许 加消失诅咒
BLOCK_RULES = {
    # 已有 -> 不允许再出现的附魔集合
    ENCHANT_UNBREAKING: set([ENCHANT_MENDING]),
    ENCHANT_MENDING: set([ENCHANT_UNBREAKING]),
    ENCHANT_VANISHING: set([ENCHANT_UNBREAKING]),
}

# 是否禁止附魔台（只走铁砧）
DISABLE_ENCHANT_TABLE = True

# ---------------------------------------------------------------- 调试
DEBUG_LOG = False

# 本地调试桥：127.0.0.1:14531，可在游戏内执行任意 Python
# 发布前必须改成 False
DEBUG_BRIDGE = False


# ---------------------------------------------------------------- 朝向
# 用 minecraft:cardinal_direction 表示朝向的方块：aux 0南 1西 2北 3东
CARDINAL_BLOCKS = set([
    "minecraft:chest", "minecraft:trapped_chest",
    "minecraft:ender_chest",
    "minecraft:furnace", "minecraft:lit_furnace",
    "minecraft:blast_furnace", "minecraft:lit_blast_furnace",
    "minecraft:smoker", "minecraft:lit_smoker",
    "minecraft:copper_chest",
    "minecraft:exposed_copper_chest",
    "minecraft:weathered_copper_chest",
    "minecraft:oxidized_copper_chest",
    "minecraft:waxed_copper_chest",
    "minecraft:waxed_exposed_copper_chest",
    "minecraft:waxed_weathered_copper_chest",
    "minecraft:waxed_oxidized_copper_chest",
])
# 木桶单独处理：aux 直接等于 facing_direction（0下 1上 2北 3南 4西 5东）
FACING_DIRECTION_BLOCKS = set([
    "minecraft:barrel",
    "minecraft:hopper",
    "minecraft:dispenser",
    "minecraft:dropper",
])

CARDINAL_TO_AUX = {"south": 0, "west": 1, "north": 2, "east": 3}
FACING_TO_AUX = {"north": 2, "south": 3, "west": 4, "east": 5}
OPPOSITE = {"north": "south", "south": "north",
            "west": "east", "east": "west"}


def yaw_to_direction(yaw):
    """把玩家 yaw 角度转成朝向。yaw 0 朝 +Z（南），90 朝 -X（西）。"""
    yaw = float(yaw) % 360.0
    if yaw < 45.0 or yaw >= 315.0:
        return "south"
    if yaw < 135.0:
        return "west"
    if yaw < 225.0:
        return "north"
    return "east"


def facing_aux(block_name, player_yaw, keep_vertical=False):
    """根据玩家朝向算出放置时该用的 aux。方块没有朝向就返回 None。"""
    front = OPPOSITE[yaw_to_direction(player_yaw)]
    if block_name in FACING_DIRECTION_BLOCKS:
        if keep_vertical:
            return None
        return FACING_TO_AUX.get(front)
    if block_name in CARDINAL_BLOCKS:
        return CARDINAL_TO_AUX.get(front)
    return None
