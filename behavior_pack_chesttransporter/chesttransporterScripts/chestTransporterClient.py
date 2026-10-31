# -*- coding: utf-8 -*-
"""客户端 System。

职责：
  1. 把搬箱器的附魔台入口/出口拦掉（附魔台只做铁砧以外的事情，本 mod 不支持）
  2. 收箱 / 放箱时播放反馈音效
真正的方块数据操作全在服务端。
"""

import modConfig
import mod.client.extraClientApi as clientApi

ClientSystem = clientApi.GetClientSystemCls()

EVENTS = (
    "OnItemPutInEnchantingModelClientEvent",
    "ClientItemTryUseEvent",
    "ClientItemUseOnEvent",
)


class ChestTransporterClient(ClientSystem):

    def __init__(self, namespace, systemName):
        ClientSystem.__init__(self, namespace, systemName)
        self.mLevelId = clientApi.GetLevelId()
        self.mFactory = clientApi.GetEngineCompFactory()
        self.mLocalId = self._localPlayerId()
        self._listenEvents()
        print "[ChestTransporter] client system ready"

    # ------------------------------------------------------------- 初始化
    def _listenEvents(self):
        ns = clientApi.GetEngineNamespace()
        sn = clientApi.GetEngineSystemName()
        self.ListenForEvent(ns, sn, "OnItemPutInEnchantingModelClientEvent", self,
                            self.OnEnchantingTable)
        self.ListenForEvent(ns, sn, "ClientItemTryUseEvent", self,
                            self.OnItemTryUse)
        self.ListenForEvent(ns, sn, "ClientItemUseOnEvent", self,
                            self.OnItemUseOn)

    def _localPlayerId(self):
        try:
            return clientApi.GetLocalPlayerId()
        except Exception:
            return None

    # ------------------------------------------------------------- 工具
    def _log(self, msg):
        if modConfig.DEBUG_LOG:
            print "[ChestTransporter][Client] " + str(msg)

    def _isTransporter(self, itemDict):
        if not isinstance(itemDict, dict):
            return False
        name = itemDict.get("newItemName") or itemDict.get("itemName")
        return name in modConfig.ITEM_TO_TIER

    def _isSneaking(self):
        pid = self.mLocalId
        if not pid:
            return False
        try:
            return bool(self.mFactory.CreatePlayer(pid).IsSneaking())
        except Exception, e:
            self._log("IsSneaking failed: %s" % e)
            return False

    # ------------------------------------------------------------- 附魔台
    def OnEnchantingTable(self, args):
        """把搬箱器从附魔台里弹出来。"""
        try:
            itemDict = args.get("itemDict") or args.get("newItem")
            if self._isTransporter(itemDict):
                args["change"] = False
                self._log("blocked enchanting table")
        except Exception, e:
            self._log("OnEnchantingTable error: %s" % e)

    def OnItemTryUse(self, args):
        """下蹲右键时把手持物品的使用取消，避免原版逻辑介入。"""
        try:
            if not self._isSneaking():
                return
            if self._isTransporter(args.get("itemDict")):
                self._log("suppress item use (sneaking)")
        except Exception, e:
            self._log("OnItemTryUse error: %s" % e)

    def OnItemUseOn(self, args):
        try:
            if not self._isSneaking():
                return
            if self._isTransporter(args.get("itemDict")):
                self._log("item use on block, client side")
        except Exception, e:
            self._log("OnItemUseOn error: %s" % e)
