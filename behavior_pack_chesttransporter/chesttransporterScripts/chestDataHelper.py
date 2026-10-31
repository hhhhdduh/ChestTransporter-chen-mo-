# -*- coding: utf-8 -*-
"""容器数据 <-> 物品 userData 的序列化（精简版）。

只存这些：
  blockName  方块 id
  kind       逻辑类别
  items      箱子里的物品列表（引擎原样返回的已包裹结构）
  aux        仅用于没有朝向的方块（潜影盒颜色等）

其余 NBT（x/y/z/id/Findable/IsOpened...）全部丢弃，放回去时由引擎重建。
"""

import modConfig


def unwrap(value):
    """把引擎回读时包成 {"__type__": n, "__value__": v} 的值还原成普通值。"""
    if isinstance(value, dict):
        if "__type__" in value and "__value__" in value:
            return unwrap(value["__value__"])
    return value


def toPlain(value):
    """把 NBT 容器递归转成纯 python 结构。"""
    if isinstance(value, dict):
        out = {}
        for k in value:
            out[k] = toPlain(value[k])
        return out
    if isinstance(value, (list, tuple)):
        out = []
        for v in value:
            out.append(toPlain(v))
        return out
    return value


def buildChestData(compFactory, levelId, dimensionId, pos, blockName, auxValue, kind):
    """读取一个方块，压成可以塞进 userData 的 dict。失败返回 None。"""
    data = {
        "kind": kind,
        "blockName": blockName,
        "aux": int(auxValue or 0),
    }

    if kind == "ender_chest":
        return data

    try:
        blockInfo = compFactory.CreateBlockInfo(levelId)
        nbt = blockInfo.GetBlockEntityData(dimensionId, pos)
    except Exception, e:
        _log("buildChestData GetBlockEntityData failed: %s" % e)
        return None

    if not nbt:
        return data

    try:
        items = nbt.get("Items")
    except Exception:
        items = None
    if items:
        data["items"] = toPlain(items)

    if kind == "spawner":
        ent = nbt.get("EntityIdentifier")
        if ent is not None:
            data["entity"] = toPlain(ent)

    return data


def restoreChestData(compFactory, levelId, dimensionId, pos, data, aux=None):
    """把 userData 里的箱子数据还原成方块。成功返回 True。"""
    if not data:
        return False

    blockName = unwrap(data.get("blockName"))
    if not blockName:
        return False

    if aux is None:
        try:
            aux = int(unwrap(data.get("aux")) or 0)
        except (TypeError, ValueError):
            aux = 0

    try:
        blockInfo = compFactory.CreateBlockInfo(levelId)
        blockInfo.SetBlockNew(pos, {"name": blockName, "aux": int(aux)}, 0,
                              dimensionId, True)
    except Exception, e:
        _log("restoreChestData SetBlockNew failed: %s" % e)
        return False

    items = data.get("items")
    entity = data.get("entity")
    if not items and entity is None:
        return True

    try:
        blockInfo = compFactory.CreateBlockInfo(levelId)
        nbt = blockInfo.GetBlockEntityData(dimensionId, pos)
        if nbt is None:
            return True
        if items:
            nbt["Items"] = items
        if entity is not None:
            nbt["EntityIdentifier"] = entity
        blockInfo.SetBlockEntityData(dimensionId, pos, nbt)
    except Exception, e:
        _log("restoreChestData SetBlockEntityData failed: %s" % e)

    return True


def clearBlock(compFactory, levelId, dimensionId, pos):
    """把方块置空。"""
    try:
        blockInfo = compFactory.CreateBlockInfo(levelId)
        blockInfo.SetBlockNew(pos, {"name": "minecraft:air", "aux": 0}, 0,
                              dimensionId, True)
        return True
    except Exception, e:
        _log("clearBlock failed: %s" % e)
        return False


def _log(msg):
    if modConfig.DEBUG_LOG:
        print "[ChestTransporter] " + str(msg)
