# 搬箱器 · Chest Transporter（网易基岩版）

蹲下右键，把箱子连同里面的东西一起搬走。

![封面](docs/cover_1000.png)

移植自 Java 版 **Chest Transporter**（作者 **CubeX2**），使用网易 ModSDK（Python 2.7）完整重写，非直接复用原作代码。

---

## 玩法

| 操作 | 结果 |
| --- | --- |
| 下蹲 + 右键容器 | 搬起，容器进入手持状态 |
| 下蹲 + 右键地面 | 放下，物品、数量、朝向完整还原 |

箱内物品**一个不少**，NBT 数据完整保留。

## 六种材质

| 材质 | 耐久上限 |
| --- | --- |
| 木质 | 10 |
| 铜质 | 20 |
| 铁质 | 50 |
| 金质 | 90 |
| 钻石 | 100 |
| 黑曜石 | 300 |

## 合成

- **木质**：5 根木棍（`S S / SSS / S `）
- **升级**：工作台放「上一级 + 对应材料」
  - 木 → 铜：4 铜锭
  - 铜 → 铁：4 铁锭
  - 铁 → 金：4 金锭
  - 金 → 钻：左右各 1 钻石
- **黑曜石**：5 根木棍 + 1 黑曜石（不可升级）

## 支持的容器

普通箱子、陷阱箱、木桶、末影箱、熔炉、高炉、烟熏炉、漏斗、发射器、投掷器、酿造台、全部 16 色潜影盒、1.21 全部 8 种铜箱、刷怪笼。

## 细节

- 放下时容器正面朝向玩家背后
- 提示显示在物品栏上方，不刷聊天栏
- 耐久见底也不会卡死：放下永远优先，放完才碎
- 黑曜石款不怕岩浆和火焰
- 创造模式不消耗耐久
- 收 / 放切换物品贴图（`_full` 变体）

## 目录结构

```
behavior_pack_chesttransporter/
  chesttransporterScripts/
    modMain.py                Mod 入口
    modConfig.py              全部可调参数
    chestTransporterServer.py 服务端主逻辑
    chestTransporterClient.py 客户端（附魔台拦截）
    chestDataHelper.py        容器数据序列化
    enchantHelper.py          附魔白名单
  netease_items_beh/          12 个物品定义
  netease_recipes/            6 个配方
resource_pack_chesttransporter/
  netease_items_res/          12 个物品外观
  textures/items/             24 张贴图
  texts/                      中英文语言文件
tools/                        自检与打包脚本
docs/                         商店用宣传图
```

## 在 MCStudio 中使用

1. MCStudio → 基岩版组件 → 本地导入 → 使用文件夹导入
2. 选择本仓库根目录
3. 开发测试 → 使用功能组件 → 勾选「搬箱器」
4. 进入存档测试

## 构建发布包

```bash
python tools/pack.py
```

输出 `dist/ChestTransporter.zip`，已自动剔除调试文件与 `.pyc`。

## 自检

```bash
python tools/selfcheck.py
```

会校验 JSON 结构、物品与贴图互引、配方产物、以及 7 个脚本的 Python 2.7 语法。

校验 JSON 结构、物品与贴图互相引用、配方结果、附魔规则。

## 发布前检查

`modConfig.py` 里两个调试开关必须为 `False`：

```python
DEBUG_LOG = False
DEBUG_BRIDGE = False
```

## 已知问题

- 附魔台不支持（客户端拦截），附魔只走铁砧
- 铁砧白名单的实时清扫行为待更多反馈验证

## 致谢

- 原作：[Chest Transporter](https://www.curseforge.com/minecraft/mc-mods/chest-transporter) by **CubeX2**
- 移植：本仓库维护者

## 许可

本项目以 **GNU General Public License v3.0** 发布，详见 [LICENSE](LICENSE)。

原作 Chest Transporter（作者 CubeX2）同样以 GPL-3.0 发布，因此本移植作品
必须沿用同一许可，不能改为更宽松或更严格的授权。

这意味着：任何人拿到本项目的代码，都可以自由使用、修改、再发布，
但如果再发布，也必须同样以 GPL-3.0 开放源代码。
