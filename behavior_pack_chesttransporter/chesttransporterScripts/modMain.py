# -*- coding: utf-8 -*-
"""ChestTransporter Mod 入口。

注意（踩过的坑）：
  1. @Mod.Binding 的 name / version 只写"裸名字"或字符串字面量，
     不要写成 modConfig.MOD_NAME 这种属性访问 —— 引擎解析装饰器时
     会把属性表达式的模块名当成可调用对象，报
     TypeError: 'module' object is not callable
  2. RegisterSystem 的第三个参数（类路径）也用字符串字面量。
  3. behavior_pack 的 entities/ 目录里不能放 __init__.py，
     引擎会把 entities/ 下每个文件当实体 JSON 解析并报 parse error。
"""

from mod.common.mod import Mod
import mod.server.extraServerApi as serverApi
import mod.client.extraClientApi as clientApi

MOD_NAME = "chesttransporter"
MOD_VERSION = "1.0.0"

SERVER_SYSTEM_NAME = "ChestTransporterServer"
SERVER_SYSTEM_CLS = "chesttransporterScripts.chestTransporterServer.ChestTransporterServer"

CLIENT_SYSTEM_NAME = "ChestTransporterClient"
CLIENT_SYSTEM_CLS = "chesttransporterScripts.chestTransporterClient.ChestTransporterClient"


@Mod.Binding(name=MOD_NAME, version=MOD_VERSION)
class ModMain(object):

    def __init__(self):
        pass

    @Mod.InitServer()
    def init_server(self):
        serverApi.RegisterSystem(MOD_NAME, SERVER_SYSTEM_NAME, SERVER_SYSTEM_CLS)
        print "[ChestTransporter] server inited"

    @Mod.DestroyServer()
    def destroy_server(self):
        pass

    @Mod.InitClient()
    def init_client(self):
        clientApi.RegisterSystem(MOD_NAME, CLIENT_SYSTEM_NAME, CLIENT_SYSTEM_CLS)
        print "[ChestTransporter] client inited"

    @Mod.DestroyClient()
    def destroy_client(self):
        pass
