# -*- coding: utf-8 -*-
"""ChestTransporter 服务端主逻辑。

入口事件：
  ServerItemUseOnEvent                     -> 收箱 / 放箱
  ServerBlockUseEvent                      -> 兜底拦掉"打开箱子界面"
  InventoryItemChangedServerEvent           -> 附魔白名单清扫
  CraftItemOutputChangeServerEvent          -> 升级时继承耐久与附魔
  OnItemPutInEnchantingModelServerEvent     -> 禁止附魔台
  OnScriptTickServer                        -> 抱着箱子时的减益
"""

import math

import modConfig
import chestDataHelper
import enchantHelper

import mod.server.extraServerApi as serverApi

ServerSystem = serverApi.GetServerSystemCls()

# 射线会穿过的"不算方块"的东西
NON_SOLID = set([
    "minecraft:air",
    "minecraft:short_grass",
    "minecraft:grass",
    "minecraft:tall_grass",
    "minecraft:fern",
    "minecraft:large_fern",
    "minecraft:snow_layer",
    "minecraft:torch",
    "minecraft:water",
    "minecraft:flowing_water",
    "minecraft:lava",
    "minecraft:flowing_lava",
    "minecraft:rail",
    "minecraft:vine",
    "minecraft:deadbush",
    "minecraft:yellow_flower",
    "minecraft:red_flower",
])


class ChestTransporterServer(ServerSystem):

    def __init__(self, namespace, systemName):
        ServerSystem.__init__(self, namespace, systemName)

        self.mLevelId = serverApi.GetLevelId()
        self.mFactory = serverApi.GetEngineCompFactory()

        # 常用组件缓存（不要放在循环里反复 Create）
        self.mItemComp = self.mFactory.CreateItem(self.mLevelId)
        self.mGameComp = self.mFactory.CreateGame(self.mLevelId)

        self.mPlayerCompCache = {}
        self.mTickCounter = 0
        # 去重用：ServerItemTryUseEvent 与 ServerItemUseOnEvent 可能同时来
        self.mLastUseTick = {}

        enchantHelper.resolveEnchantIds(self.mFactory, self.mLevelId)

        self._startDebugBridge()

        self._listenEvents()
        self._registerBlockWhitelist()
        self._checkItems()
        self._log("server system ready")

    # ------------------------------------------------------------- 调试桥
    def _startDebugBridge(self):
        """内嵌 mod-debug-bridge 的执行监听器，本机 127.0.0.1:14531。

        只要本 mod 在跑，端口就是开的，不依赖任何额外的行为包注册。
        发布前把 modConfig.DEBUG_BRIDGE 设成 False 即可关闭。
        """
        self.mBridge = None
        if not getattr(modConfig, "DEBUG_BRIDGE", False):
            return
        try:
            import dbgConfig
            self.mBridge = dbgConfig.ExecListener(
                dbgConfig.SERVER_PORT, "CT-Server", globals())
            self.mBridge.start()
            self._log("debug bridge started on %d" % dbgConfig.SERVER_PORT)
        except Exception, e:
            self._log("debug bridge failed: %s" % e)
            self.mBridge = None

    # ------------------------------------------------------------- 自检
    def _checkItems(self):
        """确认 6 个物品真的注册进引擎了，没注册 /give 会失败。"""
        if not modConfig.DEBUG_LOG:
            return
        try:
            for tier in modConfig.DURABILITY.keys():
                name = modConfig.item_id(tier)
                info = self.mItemComp.GetItemBasicInfo(name)
                if info is None:
                    self._log("ITEM MISSING: %s" % name)
                else:
                    self._log("item ok: %s name=%s dur=%s stack=%s cat=%s" % (
                        name,
                        info.get("itemName"),
                        info.get("maxDurability"),
                        info.get("maxStackSize"),
                        info.get("itemCategory")))
        except Exception, e:
            self._log("checkItems failed: %s" % e)

    # ------------------------------------------------------------- 初始化
    def _listenEvents(self):
        # 主入口：右键使用物品（不管对着什么方块都会触发）
        self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
                            "ServerItemTryUseEvent", self, self.OnItemTryUse)
        self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
                            "ServerItemUseOnEvent", self, self.OnItemUseOn)
        self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
                            "ServerBlockUseEvent", self, self.OnBlockUse)
        self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
                            "OnScriptTickServer", self, self.OnScriptTick)
        self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
                            "InventoryItemChangedServerEvent", self, self.OnInventoryChanged)
        self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
                            "CraftItemOutputChangeServerEvent", self, self.OnCraftOutput)
        self.ListenForEvent(serverApi.GetEngineNamespace(), serverApi.GetEngineSystemName(),
                            "OnItemPutInEnchantingModelServerEvent", self, self.OnEnchantingTable)

    def _registerBlockWhitelist(self):
        """把可搬运方块登记到方块使用事件白名单，否则 ServerBlockUseEvent 不会触发。"""
        try:
            whitelist = self.mFactory.CreateBlockUseEventWhiteList(self.mLevelId)
            for blockName in modConfig.SUPPORTED_BLOCKS:
                whitelist.AddBlockItemListenForUseEvent(blockName)
            self._log("block whitelist registered: %d" % len(modConfig.SUPPORTED_BLOCKS))
        except Exception, e:
            self._log("register block whitelist failed: %s" % e)

    # ------------------------------------------------------------- 工具
    def _trace_add(self, msg):
        """把关键动作记到内存，方便外部调试时读取。"""
        try:
            buf = getattr(self, "mTrace", None)
            if buf is None:
                buf = []
                self.mTrace = buf
            buf.append(str(msg))
            if len(buf) > 200:
                del buf[0:100]
        except Exception:
            pass

    def _log(self, msg):
        if modConfig.DEBUG_LOG:
            print "[ChestTransporter] " + str(msg)

    def _brief(self, args):
        """把事件参数压成一行，方便看日志。"""
        try:
            parts = []
            for k in sorted(args.keys()):
                s = repr(args.get(k))
                if len(s) > 140:
                    s = s[:140] + "..."
                parts.append("%s=%s" % (k, s))
            return "{" + ", ".join(parts) + "}"
        except Exception, e:
            return "<brief failed: %s>" % e

    def _playerComp(self, playerId):
        comp = self.mPlayerCompCache.get(playerId)
        if comp is None:
            comp = self.mFactory.CreatePlayer(playerId)
            self.mPlayerCompCache[playerId] = comp
        return comp

    def _isSneaking(self, playerId):
        try:
            return bool(self._playerComp(playerId).isSneaking())
        except Exception, e:
            self._log("isSneaking failed: %s" % e)
            return False

    def _tierOf(self, itemDict):
        if not isinstance(itemDict, dict):
            return None
        name = itemDict.get("newItemName") or itemDict.get("itemName")
        if not name:
            return None
        return modConfig.ITEM_TO_TIER.get(name)

    def _isTransporter(self, itemDict):
        return self._tierOf(itemDict) is not None

    def _maxDurability(self, tier):
        return modConfig.DURABILITY.get(tier, 1)

    def _userData(self, itemDict):
        if not isinstance(itemDict, dict):
            return {}
        data = itemDict.get("userData")
        if not isinstance(data, dict):
            data = {}
        return data

    def _readCarried(self, playerId):
        """读主手物品（带 userData）。"""
        try:
            itemType = serverApi.GetMinecraftEnum().ItemPosType.CARRIED
            return self.mItemComp.GetPlayerItem(itemType, 0, True)
        except Exception, e:
            self._log("GetPlayerItem failed: %s" % e)
            return None

    def _writeCarried(self, playerId, itemDict):
        try:
            self.mItemComp.SpawnItemToPlayerCarried(itemDict, playerId)
            return True
        except Exception, e:
            self._log("SpawnItemToPlayerCarried failed: %s" % e)
            return False

    # ------------------------------------------------------------- 耐久
    def _getDamage(self, itemDict, tier=None):
        """返回当前已消耗的耐久值 = 上限 - 剩余。

        引擎物品字典里的 durability 是「剩余耐久」，满耐久时等于上限，
        不是 0。以前按已消耗值理解，导致新物品第一次使用就被判定损坏。
        """
        maxDur = self._maxDurability(tier)
        remain = self._getRemaining(itemDict, tier)
        return max(0, maxDur - remain)

    def _getRemaining(self, itemDict, tier=None):
        """返回剩余耐久值。"""
        maxDur = self._maxDurability(tier)
        if not isinstance(itemDict, dict):
            return maxDur
        val = itemDict.get("durability")
        if val is None:
            val = self._userData(itemDict).get("ct_dur")
        try:
            val = int(val) if val is not None else maxDur
        except (TypeError, ValueError):
            val = maxDur
        if val <= 0:
            return maxDur
        if maxDur > 0:
            return min(val, maxDur)
        return val

    def _unbreakingSkip(self, itemDict):
        """耐久的免消耗概率：等级 / (等级 + 1)。"""
        try:
            lvl = enchantHelper.getEnchantLevel(itemDict.get("enchantData"),
                                                modConfig.ENCHANT_UNBREAKING)
        except Exception:
            lvl = 0
        if lvl <= 0:
            return False
        import random
        return random.random() < (float(lvl) / float(lvl + 1))

    def _damageItem(self, playerId, itemDict, tier):
        """消耗一点耐久。返回 (newItemDict or None, broken)"""
        if self._isCreative(playerId):
            return dict(itemDict), False
        if self._unbreakingSkip(itemDict):
            self._log("unbreaking saved durability")
            return itemDict, False

        maxDur = self._maxDurability(tier)
        remain = self._getRemaining(itemDict, tier) - modConfig.DURABILITY_COST

        if remain <= 0:
            return None, True

        itemDict = dict(itemDict)
        itemDict["durability"] = remain
        ud = dict(self._userData(itemDict))
        ud["ct_dur"] = remain
        itemDict["userData"] = ud
        return itemDict, False

    # ------------------------------------------------------------- 收箱 / 放箱
    def OnItemTryUse(self, args):
        """主入口。右键使用物品时必定触发，不依赖方块白名单。

        用射线找出准星指的方块，然后自己算坐标，绕开 ServerItemUseOnEvent /
        ServerBlockUseEvent 对方块类型和 aux 的各种限制。
        """
        try:
            playerId = args.get("playerId")
            itemDict = args.get("itemDict")
            if not playerId:
                return
            if not self._isTransporter(itemDict):
                return
            if not self._isSneaking(playerId):
                self._log("TryUse: 手持搬箱器但未下蹲，放行")
                return
            if not self._claim(args):
                return

            hit = self._raycastBlock(playerId)
            if not hit:
                self._log("TryUse: 射线没打到方块")
                return
            pos, face, blockName = hit
            self._log("TryUse: hit=%s face=%s name=%s" % (pos, face, blockName))

            tier = self._tierOf(itemDict)
            dimensionId = self._dimensionOf(playerId)
            payload = self._userData(itemDict).get("ct")

            if payload:
                self._tryPlace(playerId, itemDict, tier, pos, dimensionId, face, payload)
            else:
                self._tryGrab(playerId, itemDict, tier, pos, dimensionId)
        except Exception, e:
            self._log("OnItemTryUse error: %s" % e)

    def _raycastBlock(self, playerId):
        """手算射线，不依赖 getEntitiesOrBlockFromRay / GetDirFromRot。

        从眼睛位置沿视线每 0.05 格采样一次，找第一个非空气方块。
        """
        try:
            feet = self.mFactory.CreatePos(playerId).GetFootPos()
            rot = self.mFactory.CreateRot(playerId).GetRot()
            if not feet or not rot:
                self._log("raycast: GetFootPos/GetRot 拿不到")
                return None

            eye = (float(feet[0]), float(feet[1]) + 1.62, float(feet[2]))
            d = self._dirFromRot(rot)
            dimensionId = self._dimensionOf(playerId)
            blockInfo = self.mFactory.CreateBlockInfo(self.mLevelId)

            prev = None
            last = None
            steps = 0
            t = 0.0
            while t <= 6.0:
                bx = int(math.floor(eye[0] + d[0] * t))
                by = int(math.floor(eye[1] + d[1] * t))
                bz = int(math.floor(eye[2] + d[2] * t))
                cur = (bx, by, bz)
                if cur != last:
                    block = blockInfo.GetBlockNew(cur, dimensionId)
                    name = block.get("name") if isinstance(block, dict) else None
                    if name and name not in NON_SOLID:
                        face = self._faceFromStep(prev, cur)
                        return cur, face, name
                    last = cur
                    steps += 1
                prev = cur
                t += 0.05
            self._log("raycast: 6 格内没有方块（采样 %d 格）" % steps)
            return None
        except Exception, e:
            self._log("raycast failed: %s" % e)
            return None

    def _dirFromRot(self, rot):
        """(pitch, yaw) 角度 -> 单位方向向量。yaw 0 朝 +Z，90 朝 -X。"""
        pitch = float(rot[0])
        yaw = float(rot[1])
        rad = math.pi / 180.0
        cp = math.cos(pitch * rad)
        return (-math.sin(yaw * rad) * cp,
                -math.sin(pitch * rad),
                math.cos(yaw * rad) * cp)

    def _faceFromStep(self, prev, cur):
        """根据从上一格进入当前格的方向，推断命中的面。
        0下 1上 2北(-Z) 3南(+Z) 4西(-X) 5东(+X)
        """
        if not prev:
            return 1
        if cur[1] > prev[1]:
            return 0
        if cur[1] < prev[1]:
            return 1
        if cur[2] > prev[2]:
            return 2
        if cur[2] < prev[2]:
            return 3
        if cur[0] > prev[0]:
            return 4
        if cur[0] < prev[0]:
            return 5
        return 1

    def _dimensionOf(self, playerId):
        try:
            return self.mFactory.CreateDimension(playerId).GetEntityDimensionId()
        except Exception:
            return 0

    def OnItemUseOn(self, args):
        """对方块使用物品。事件自带方块坐标，直接用它，不靠射线。"""
        try:
            self._log("RAW OnItemUseOn: %s" % self._brief(args))
            if not self._takeOver(args, "ServerItemUseOnEvent"):
                return
            args["ret"] = True
            if self._claim(args):
                self._runWithArgs(args, "ServerItemUseOnEvent")
        except Exception, e:
            self._log("OnItemUseOn error: %s" % e)

    def OnBlockUse(self, args):
        """方块交互。事件自带方块坐标，直接用它，不靠射线。"""
        try:
            self._log("RAW OnBlockUse: %s" % self._brief(args))
            if not self._takeOver(args, "ServerBlockUseEvent"):
                return
            args["cancel"] = True
            if self._claim(args):
                self._runWithArgs(args, "ServerBlockUseEvent")
        except Exception, e:
            self._log("OnBlockUse error: %s" % e)

    def _claim(self, args):
        """同一个玩家的多个事件只执行一次。每个事件都要单独 cancel，所以 cancel
        放在 _claim 外面。"""
        playerId = args.get("entityId") or args.get("playerId")
        last = self.mLastUseTick.get(playerId, -999)
        if self.mTickCounter - last < 5:
            self._log("  -> 已有事件处理本 tick，跳过执行")
            return False
        self.mLastUseTick[playerId] = self.mTickCounter
        return True

    def _runWithArgs(self, args, source):
        """用事件自带的坐标执行收箱 / 放箱。"""
        playerId = args.get("entityId") or args.get("playerId")
        itemDict = args.get("itemDict")
        tier = self._tierOf(itemDict)
        dimensionId = args.get("dimensionId", 0)
        pos = (args.get("x", 0), args.get("y", 0), args.get("z", 0))
        face = args.get("face", 0)
        payload = self._userData(itemDict).get("ct")

        self._log("%s: tier=%s pos=%s face=%s payload=%s" % (
            source, tier, pos, face, "有" if payload else "无"))

        if payload:
            return self._tryPlace(playerId, itemDict, tier, pos, dimensionId, face, payload)
        return self._tryGrab(playerId, itemDict, tier, pos, dimensionId)

    def _takeOver(self, args, source):
        """判断这次右键是否该由我们接管（手持搬箱器 + 下蹲）。"""
        playerId = args.get("entityId") or args.get("playerId")
        itemDict = args.get("itemDict")
        if not playerId:
            self._log("%s: 无 playerId" % source)
            return False
        if not self._isTransporter(itemDict):
            self._log("%s: 手持物不是搬箱器 -> %s" % (
                source, itemDict.get("newItemName") if isinstance(itemDict, dict) else itemDict))
            return False
        if not self._isSneaking(playerId):
            self._log("%s: 未下蹲，放行" % source)
            return False
        return True

    def _tryGrab(self, playerId, itemDict, tier, pos, dimensionId):
        blockInfo = self.mFactory.CreateBlockInfo(self.mLevelId)
        block = blockInfo.GetBlockNew(pos, dimensionId)
        if not isinstance(block, dict):
            self._log("grab: GetBlockNew 返回 %r" % (block,))
            return False

        blockName = block.get("name")
        kind = modConfig.SUPPORTED_BLOCKS.get(blockName)
        self._log("grab: block=%s aux=%s kind=%s" % (blockName, block.get("aux"), kind))
        if not kind:
            self._notify(playerId, u"§c这个方块搬不了")
            return False

        if kind == "spawner" and not modConfig.ALLOW_PICKUP_SPAWNER:
            self._notify(playerId, u"§c刷怪笼已被禁止搬运")
            return True

        data = chestDataHelper.buildChestData(
            self.mFactory, self.mLevelId, dimensionId, pos,
            blockName, block.get("aux", 0), kind)
        if not data:
            self._log("grab: buildChestData 返回空")
            self._notify(playerId, u"§c读取容器数据失败")
            return True
        self._log("grab: data keys=%s" % sorted(data.keys()))

        newItem, broken = self._damageItem(playerId, itemDict, tier)
        if broken:
            # 手里有东西时提示去放下，空的时候直按说耐久不够
            if self._userData(itemDict).get("ct"):
                self._notify(playerId, u"§c耐久不够了，先把里面的东西放下再用")
            else:
                self._notify(playerId, u"§c耐久不够了，这个搬箱器快报废了")
            return True

        # 收起来了，换成「装着东西」的贴图变体
        newItem["newItemName"] = modConfig.item_id(tier, filled=True)

        ud = dict(self._userData(newItem))
        ud["ct"] = data
        newItem["userData"] = ud

        # 先扣耐久与写数据，再删方块，避免数据丢了方块也没了
        if not self._writeCarried(playerId, newItem):
            self._notify(playerId, u"§c写入物品失败，已取消")
            return True

        chestDataHelper.clearBlock(self.mFactory, self.mLevelId, dimensionId, pos)

        self._playBlockSound(playerId, pos, blockName)
        self._notify(playerId, u"§a已搬起：%s" % self._blockLabel(data))
        self._warnLowDurability(playerId, tier, newItem)
        return True

    def _tryPlace(self, playerId, itemDict, tier, pos, dimensionId, face, payload):
        blockInfo = self.mFactory.CreateBlockInfo(self.mLevelId)

        target = pos
        here = blockInfo.GetBlockNew(pos, dimensionId)
        hereName = here.get("name") if isinstance(here, dict) else None

        if hereName not in modConfig.REPLACEABLE_BLOCKS:
            target = self._offset(pos, face)
            there = blockInfo.GetBlockNew(target, dimensionId)
            thereName = there.get("name") if isinstance(there, dict) else None
            self._log("place: here=%s offset->%s there=%s" % (hereName, target, thereName))
            if thereName not in modConfig.REPLACEABLE_BLOCKS:
                self._notify(playerId, u"§c这里放不下")
                return False
        else:
            self._log("place: here=%s 可直接替换" % (hereName,))

        # 放下永远优先：即使耐久到底也先把箱子放下来，
        # 不让玩家卡在「有东西却放不下」的死局里
        newItem, broken = self._damageItem(playerId, itemDict, tier)

        # 朝向跟玩家面朝：放下的容器正面朝向玩家背后
        try:
            yaw = self.mFactory.CreateRot(playerId).GetRot()[1]
        except Exception, e:
            yaw = 0.0
            self._log("place: GetRot failed: %s" % e)
        blockName = chestDataHelper.unwrap(payload.get("blockName"))
        aux = modConfig.facing_aux(blockName, yaw)
        self._log("place: block=%s yaw=%s aux=%r" % (blockName, yaw, aux))

        ok = chestDataHelper.restoreChestData(
            self.mFactory, self.mLevelId, dimensionId, target, payload, aux)
        self._log("place: restoreChestData -> %s @%s" % (ok, target))
        if not ok:
            self._notify(playerId, u"§c放置失败")
            return True

        if broken or not isinstance(newItem, dict):
            # 箱子已经放下，搬箱器碎掉（newItem 会是 None）
            self._writeCarried(playerId, {"newItemName": "minecraft:air", "count": 0})
            self._notify(playerId, u"§c搬箱器用完了，已碎裂")
        else:
            # 关键：把里面的东西从手持物上抹掉，否则可以无限刷容器
            ud = dict(self._userData(newItem))
            ud.pop("ct", None)
            newItem["userData"] = ud
            newItem["newItemName"] = modConfig.item_id(tier, filled=False)
            ok_write = self._writeCarried(playerId, newItem)
            self._trace_add("place cleared ct=%s write=%s" % (not ud.get("ct"), ok_write))
            self._warnLowDurability(playerId, tier, newItem)

        self._playBlockSound(playerId, target,
                                      chestDataHelper.unwrap(payload.get("blockName")))
        self._notify(playerId, u"§a已放下：%s" % self._blockLabel(payload))
        return True

    def _offset(self, pos, face):
        x, y, z = pos
        # Bedrock face: 0 down, 1 up, 2 north, 3 south, 4 west, 5 east
        if face == 0:
            return (x, y - 1, z)
        if face == 1:
            return (x, y + 1, z)
        if face == 2:
            return (x, y, z - 1)
        if face == 3:
            return (x, y, z + 1)
        if face == 4:
            return (x - 1, y, z)
        if face == 5:
            return (x + 1, y, z)
        return (x, y + 1, z)

    def _blockLabel(self, data):
        name = chestDataHelper.unwrap(data.get("blockName")) or "?"
        kind = chestDataHelper.unwrap(data.get("kind")) or ""
        if kind == "spawner":
            nbt = data.get("nbt") or {}
            ent = nbt.get("EntityIdentifier") or nbt.get("id") or ""
            return u"刷怪笼(%s)" % ent
        return name

    def _playBlockSound(self, playerId, pos, blockName):
        try:
            self.mGameComp.PlaySound(blockName, pos, 1.0, 1.0)
        except Exception:
            pass

    def _notify(self, playerId, msg):
        """物品栏上方的 tip 提示。

        坑：SetOneTipMessage 只接受 utf-8 字节串，传 unicode 会静默返回 False。
        """
        if isinstance(msg, unicode):
            msg = msg.encode("utf-8")
        try:
            if self.mGameComp.SetOneTipMessage(playerId, msg):
                return
            self._log("SetOneTipMessage returned False, fallback to chat")
        except Exception, e:
            self._log("SetOneTipMessage failed: %s" % e)
        try:
            self.mFactory.CreateMsg(playerId).NotifyOneMessage(playerId, msg)
        except Exception, e2:
            self._log("notify fallback failed: %s" % e2)

    def _warnLowDurability(self, playerId, tier, itemDict):
        """剩余耐久不多时提醒玩家，免得把东西卡在手里。"""
        remain = self._getRemaining(itemDict, tier)
        if remain > getattr(modConfig, "DURABILITY_WARN_AT", 2):
            return
        self._notify(playerId, u"§e搬箱器剩余耐久 %d，快用完了" % remain)

    def _isCreative(self, playerId):
        """创造模式不消耗耐久。"""
        try:
            return int(self.mFactory.CreatePlayer(playerId).GetPlayerGameType()) == 1
        except Exception:
            pass
        try:
            return int(self.mGameComp.GetPlayerGameType(playerId)) == 1
        except Exception, e:
            self._log("GetPlayerGameType failed: %s" % e)
            return False

    # ------------------------------------------------------------- 附魔清扫
    def _applyWantedDurability(self, playerId, item, slot):
        """如果物品带 wantDur 标记，拿到手里时把耐久设成它。

        NBT 里的 Damage 不一定被引擎采用，所以用这个方式精确控制。
        """
        ud = self._userData(item)
        want = ud.get("wantDur")
        if want is None:
            return
        want = chestDataHelper.unwrap(want)
        try:
            want = int(want)
        except (TypeError, ValueError):
            return
        fixed = dict(item)
        fixed["durability"] = want
        newUd = dict(ud)
        newUd.pop("wantDur", None)
        fixed["userData"] = newUd
        self.mItemComp.SpawnItemToPlayerInv(fixed, playerId, slot)
        self._trace_add("wantDur applied slot=%s -> %s" % (slot, want))

    def OnInventoryChanged(self, args):
        """实时清理铁砧弄上去的附魔：只保留白名单内且不互斥的。"""
        try:
            playerId = args.get("playerId")
            newItem = args.get("newItemDict")
            if not self._isTransporter(newItem):
                return

            self._applyWantedDurability(playerId, newItem, args.get("slot"))

            filtered, changed = enchantHelper.filterIllegal(newItem)
            if not changed:
                return

            fixed = dict(newItem)
            if filtered:
                fixed["enchantData"] = filtered
            else:
                fixed.pop("enchantData", None)

            slot = args.get("slot")
            itemType = serverApi.GetMinecraftEnum().ItemPosType.INVENTORY
            ok = self.mItemComp.SpawnItemToPlayerInv(fixed, playerId, slot)
            if ok is False:
                # 槽位不对就全盘扫一遍
                ok = self._sweepInventory(playerId)
            self._log("enchant sweep slot=%r ok=%r kept=%r"
                      % (slot, ok, [p[0] for p in (filtered or [])]))
            self._notify(playerId, u"§e已清除不合规的附魔")
        except Exception, e:
            self._log("OnInventoryChanged error: %s" % e)

    def _sweepInventory(self, playerId):
        """扫一遍背包，把所有带附魔的搬箱器洗一遍。"""
        enum = serverApi.GetMinecraftEnum()
        slots = self.mItemComp.GetPlayerAllItems(enum.ItemPosType.INVENTORY, True)
        fixedCount = 0
        for slot, item in enumerate(slots or []):
            if not self._isTransporter(item):
                continue
            filtered, changed = enchantHelper.filterIllegal(item)
            if not changed:
                continue
            fixed = dict(item)
            if filtered:
                fixed["enchantData"] = filtered
            else:
                fixed.pop("enchantData", None)
            self.mItemComp.SpawnItemToPlayerInv(fixed, playerId, slot)
            fixedCount += 1
        return fixedCount

    def OnEnchantingTable(self, args):
        if not modConfig.DISABLE_ENCHANT_TABLE:
            return
        try:
            playerId = args.get("playerId")
            current = self._readCarried(playerId)
            if self._isTransporter(current):
                args["change"] = False
                self._notify(playerId, u"§e搬箱器不能用附魔台，请使用铁砧")
        except Exception, e:
            self._log("OnEnchantingTable error: %s" % e)

    # ------------------------------------------------------------- 升级继承
    def OnCraftOutput(self, args):
        """工作台产出时处理两种情况：

        1. 修补：同级搬箱器 + 材料 -> 满耐久，必须保留里面的物品
        2. 升级：上一级搬箱器 + 4 材料 -> 按比例继承耐久
        """
        try:
            playerId = args.get("playerId")
            output = args.get("itemDict")
            tier = self._tierOf(output)
            if not tier:
                return

            old = self._findOldTransporter(playerId, tier)
            if not old:
                return

            oldTier = self._tierOf(old)
            if not oldTier:
                return

            oldMax = self._maxDurability(oldTier)
            newMax = self._maxDurability(tier)
            remain = self._getRemaining(old, oldTier)
            newRemain = modConfig.inherited_durability(remain, oldMax, newMax)

            fixed = output if isinstance(output, dict) else {}
            fixed["durability"] = newRemain
            ud = dict(self._userData(fixed))
            ud["ct_dur"] = newRemain
            ud["upgraded_from"] = oldTier
            fixed["userData"] = ud

            if old.get("enchantData"):
                fixed["enchantData"] = old["enchantData"]

            args["itemDict"] = fixed
            self._log("craft upgrade %s -> %s, remain %d/%d" % (oldTier, tier, newRemain, newMax))
        except Exception, e:
            self._log("OnCraftOutput error: %s" % e)

    def _findTransporterOfTier(self, playerId, tier):
        """在合成格里找同一级的搬箱器（修补用）。"""
        targetIds = set([modConfig.item_id(tier, False),
                         modConfig.item_id(tier, True)])
        for it in self._craftGridItems(playerId):
            name = it.get("newItemName") or it.get("itemName")
            if name in targetIds:
                return it
        return None

    def _findOldTransporter(self, playerId, newTier):
        """在工作台格子里找上一阶段的搬箱器。找不到就返回 None（回退为满耐久）。"""
        try:
            idx = modConfig.UPGRADE_CHAIN.index(newTier)
        except ValueError:
            return None
        if idx <= 0:
            return None
        prevTier = modConfig.UPGRADE_CHAIN[idx - 1]
        prevIds = set([modConfig.item_id(prevTier, False),
                       modConfig.item_id(prevTier, True)])
        for it in self._craftGridItems(playerId):
            name = it.get("newItemName") or it.get("itemName")
            if name in prevIds:
                return it
        return None

    # ------------------------------------------------------------- Tick 减益
    def OnScriptTick(self):
        self.mTickCounter += 1

        if self.mBridge is not None:
            try:
                self.mBridge.update()
            except Exception, e:
                self._log("bridge update error: %s" % e)

        # 每 40 tick 打一次瞄准自检：手持搬箱器且下蹲时，看射线能不能打到方块。
        # 这跟事件是否触发无关，用来单独验证射线本身是否正常。
        if modConfig.DEBUG_LOG and self.mTickCounter % 40 == 0:
            self._logAim()

        interval = int(modConfig.DEBUFF_INTERVAL_SEC * 30)
        if interval <= 0:
            interval = 30
        if self.mTickCounter % interval != 0:
            return
        try:
            players = serverApi.GetPlayerList()
        except Exception:
            return
        if not players:
            return
        for playerId in players:
            try:
                self._applyDebuff(playerId)
            except Exception, e:
                self._log("applyDebuff error: %s" % e)

    def _logAim(self):
        try:
            players = serverApi.GetPlayerList()
        except Exception:
            return
        if not players:
            return
        for playerId in players:
            try:
                itemDict = self._readCarried(playerId)
                if not self._isTransporter(itemDict):
                    continue
                sneaking = self._isSneaking(playerId)
                hit = self._raycastBlock(playerId)
                self._log("AIM sneak=%s hit=%s" % (sneaking, hit))
            except Exception, e:
                self._log("AIM error: %s" % e)

    def _applyDebuff(self, playerId):
        itemDict = self._readCarried(playerId)
        if not self._isTransporter(itemDict):
            return
        if not self._userData(itemDict).get("ct"):
            return
        # 创造模式不罚
        try:
            if self._playerComp(playerId).GetPlayerGameType() == 1:
                return
        except Exception:
            pass

        effectComp = self.mFactory.CreateEffect(playerId)
        table = modConfig.DEBUFF_ENABLED
        if table.get("slowness"):
            self._addEffect(effectComp, "slowness", 2)
        if table.get("mining_fatigue"):
            self._addEffect(effectComp, "mining_fatigue", 3)
        if table.get("jump_boost"):
            self._addEffect(effectComp, "jump_boost", -2)
        if table.get("hunger"):
            self._addEffect(effectComp, "hunger", 0)

    def _addEffect(self, effectComp, name, amplifier):
        try:
            effectComp.AddEffectToEntity(name, modConfig.DEBUFF_DURATION_TICK, amplifier, True)
        except Exception, e:
            self._log("AddEffectToEntity(%s) failed: %s" % (name, e))
