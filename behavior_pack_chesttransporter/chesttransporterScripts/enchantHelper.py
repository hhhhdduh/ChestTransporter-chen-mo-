# -*- coding: utf-8 -*-
"""附魔白名单与互斥规则的实现。

对外只有 3 个函数：
  filterIllegal(itemDict)    -> (新的 enchantData, 是否改动过)
  canAdd(existing, wanted)   -> bool
  hasEnchant(enchantData, name) -> bool
"""

import modConfig


# 运行时解析出来的 名字 -> id 集合
_NAME_TO_IDS = {}
_IDS_TO_NAME = {}
_RESOLVED = False


def resolveEnchantIds(compFactory=None, levelId=None):
    """优先用引擎的 GetAllEnchantsInfo() 动态解析附魔名与 id 的对应关系。

    解析失败（接口不存在 / 返回结构不同）时退回 modConfig.ENCHANT_ID_FALLBACK。
    """
    global _RESOLVED
    if _RESOLVED:
        return
    _RESOLVED = True

    infoList = None
    if compFactory is not None and levelId is not None:
        try:
            itemComp = compFactory.CreateItem(levelId)
            infoList = itemComp.GetAllEnchantsInfo()
        except Exception, e:
            _log("GetAllEnchantsInfo failed: %s" % e)
            infoList = None

    if infoList:
        for entry in infoList:
            if not isinstance(entry, dict):
                continue
            name = entry.get("enchantName") or entry.get("name")
            eid = entry.get("enchantType")
            if eid is None:
                eid = entry.get("id")
            if name is None or eid is None:
                continue
            key = str(name).lower()
            _NAME_TO_IDS.setdefault(key, set()).add(int(eid))
            _IDS_TO_NAME[int(eid)] = key

    # 补齐回退表里缺失的
    for name in modConfig.ENCHANT_ID_FALLBACK:
        if name not in _NAME_TO_IDS:
            _NAME_TO_IDS[name] = set(modConfig.ENCHANT_ID_FALLBACK[name])
        for eid in modConfig.ENCHANT_ID_FALLBACK[name]:
            if eid not in _IDS_TO_NAME:
                _IDS_TO_NAME[eid] = name


def enchantNameById(enchantId):
    resolveEnchantIds()
    return _IDS_TO_NAME.get(int(enchantId))


def hasEnchant(enchantData, name):
    """enchantData 形如 [[id, level], ...]"""
    if not enchantData:
        return False
    resolveEnchantIds()
    ids = _NAME_TO_IDS.get(name, set())
    for pair in enchantData:
        if not pair:
            continue
        try:
            eid = int(pair[0])
        except (TypeError, ValueError):
            continue
        if eid in ids:
            return True
    return False


def getEnchantLevel(enchantData, name):
    if not enchantData:
        return 0
    resolveEnchantIds()
    ids = _NAME_TO_IDS.get(name, set())
    for pair in enchantData:
        if not pair:
            continue
        try:
            eid = int(pair[0])
            lvl = int(pair[1])
        except (TypeError, ValueError, IndexError):
            continue
        if eid in ids:
            return lvl
    return 0


def _existingNames(enchantData):
    names = set()
    if not enchantData:
        return names
    resolveEnchantIds()
    for pair in enchantData:
        if not pair:
            continue
        try:
            eid = int(pair[0])
        except (TypeError, ValueError):
            continue
        name = _IDS_TO_NAME.get(eid)
        if name:
            names.add(name)
    return names


def canAdd(existingNames, wanted):
    """按 modConfig.BLOCK_RULES 判断能否把 wanted 加到已有附魔上。"""
    for have in existingNames:
        blocked = modConfig.BLOCK_RULES.get(have, set())
        if wanted in blocked:
            return False
    return True


def filterIllegal(itemDict):
    """把不符合规则的附魔清掉。

    返回 (newEnchantData, changed)
    规则：
      1. 白名单以外的附魔 -> 删
      2. 同一次检查里，按出现顺序逐个判断互斥，冲突的后出现者删
    """
    if not isinstance(itemDict, dict):
        return None, False

    enchantData = itemDict.get("enchantData")
    if not enchantData:
        return enchantData, False

    resolveEnchantIds()

    kept = []
    keptNames = set()
    changed = False

    for pair in enchantData:
        if not pair:
            changed = True
            continue
        try:
            eid = int(pair[0])
            lvl = int(pair[1])
        except (TypeError, ValueError, IndexError):
            changed = True
            continue

        name = _IDS_TO_NAME.get(eid)
        if name is None or name not in modConfig.ALLOWED_ENCHANTS:
            # 白名单外
            changed = True
            continue

        if not canAdd(keptNames, name):
            changed = True
            continue

        kept.append([eid, lvl])
        keptNames.add(name)

    if not changed:
        return enchantData, False

    return kept, True


def _log(msg):
    if modConfig.DEBUG_LOG:
        print "[ChestTransporter][Enchant] " + str(msg)
