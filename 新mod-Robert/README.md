# RobertNPC — 罗伯特（新增恋爱对象）

Degrees of Lewdity 模组骨架。通过 **秋枫白桦框架（maplebirch）** 注册一名新的具名 NPC
「罗伯特 / Robert」，并把他接进恋爱对象系统。

- 适用游戏版本：**0.5.11.9**（ModLoader 2.101.1）
- 依赖框架版本：**maplebirch >= 4.1.0**
- 模组版本：1.0.0

> 当前状态：**可加载的骨架**。NPC 注册、状态数值、日程占位、页面入口、图片占位都已就位；
> 剧情内容和正式立绘待补。

---

## 1. 加载顺序（必须遵守）

```
1) 汉化 mod   ModI18N-0.5.11.9-chs-1.0.0a.mod
2) 图包 mod   GameOriginalImagePack-0.5.11.9.mod      ← 必须最后提供图片
3) 框架 mod   maplebirch-0.5.10.12-v4.1.14.mod
4) 本 mod     RobertNPC.mod                            ← 本 mod
5) 其他 mod   象牙怨灵 / 哈珀 等（顺序无关）
```

`boot.json` 里已经用 `ConflictChecker` 声明了这个顺序约束，加载顺序不对时会在 ModLoader
日志里给出提示，而不是静默出错。

**为什么必须在图包之后**：`GameOriginalImagePack` 会提供 `img/**` 下的全部原版图片，
ModLoader 查找图片时按加载顺序取第一个命中的 mod。本 mod 用的是
`img/npc/robert/占位图片1.png` 这种图包不存在的路径，所以理论上不会冲突；
但把本 mod 放在图包之后可以保证万一将来路径撞车时以本 mod 为准。

---

## 2. 文件结构

```
新mod-Robert/                      ← 源文件夹（不要直接给 ModLoader 加载这个）
├─ boot.json                       ← 模组清单，ModLoader 的入口（含 3 条 TweeReplacer 补丁）
├─ build_mod.py                    ← 打包脚本（见 §7）
├─ check_conflicts.py              ← 命名冲突 / 锚点自检（见 §6）
├─ check_macros.py                 ← 宏完整性 / 脚本顶层自检（见 §6）
├─ framework.js                    ← 入口脚本：NPC 注册、四属性接口、图片路径、modRef
├─ modules/
│  ├─ robert-stats.js              ← 四个属性（怒气/性欲/爱意/支配）读写与显示
│  ├─ robert-schedule.js           ← 出现条件、markMet（置 init=1 开启社交页面显示）
│  └─ robert-taxi.js               ← 出租车：司机概率读取、净化与判定
├─ robert-tweak.twee               ← widget 定义（robertName / robertPortrait / robertStat …）
├─ robert-storyinit.twee           ← StoryInit 初始化（带 try/catch 兜底）
├─ robert-passages.twee            ← 本 mod 自己的段落（初见 / 菜单 / 交谈）
├─ robert-taxi.twee                ← 出租车：上车、目的地、司机判定、座位选择、widget
├─ robert-taxi-event.twee          ← 副驾驶事件链（手 / 淫乱判定 / 循环 / 结算）
├─ robert-style.css                ← 样式，全部 .robert-* 前缀
├─ translations/
│  ├─ CN.json                      ← 中文翻译键
│  └─ EN.json                      ← 英文翻译键
├─ img/
│  ├─ 占位图片.png                  ← 图标占位（当前作出租车图标）
│  └─ npc/robert/占位图片.png       ← 立绘占位
└─ RobertNPC.mod                   ← 打包产物，把这个给 ModLoader
```

---

## 3. 命名空间预留（改代码前务必先读）

为了与 **象牙怨灵 mod（Wraith'sReflection）** 和 **哈珀 mod（ClaimableHarper）** 零冲突，
本 mod 独占以下命名空间。新增内容请沿用同样的前缀。
下表右列是已由原版 / 两个参照 mod / 框架占用的名字，**不要使用**。

| 类型 | 本 mod 使用 | 已被占用，不要使用 |
| :--- | :--- | :--- |
| 全局对象 | `window.RobertNPC` | `window.maplebirch`、`window.DOL`、`window.Time`、`window.Renderer`、`window.Utils`、`window.statDisplay` 等约 100 个原版全局名 |
| 存档变量 | `V.robert.*`（剧情标记）、`$robertTaxiDriver`、`$options.robertTaxiChance` | `$harper*`（59 个）、`$WraithsReflection`、`$HelpAsk`、`$wraith*`、`$necklace*`、`$SilverConch*`、`$stockholm_harper`、`$harperMeds.*` |
| 角色属性 | 罗伯特的 `rage` / `lust` / `love` / `dom`（**原版字段名，直接用**） | `$wraith.state`、`$necklaceThief`（都被象牙怨灵扩过语义） |
| NPC 字段 | `V.NPCName` 里 Robert 对象的 `init`（控制社交页面是否显示） | — |
| 临时变量 | `T.robertXxx` / `_robertXxx` / `_rbXxx` | `$_LI`、`$_stage`、`$_harper*` 及其它无前缀的 `_` 临时变量 |
| 段落名 | `Robert ...`（**必须带空格**） | `Wraith*` / `*WR` / `*MR`（象牙怨灵）、`Harper *` / `Asylum *` / `Hospital *` / `Estate *` / `Widgets Xxx-HARPER`（哈珀）、全部 15629 个原版段落名 |
| widget | `robertName` / `robertStat` / `robertPortrait` / `robertStatusPanel` / `robertTaxiIcon` / `robertTaxiRobertDrive` / `robertTaxiStrangerDrive` | **`willpowerdifficulty`（哈珀已覆盖重定义原版同名 widget）**、`ChatWR`、`streetWraithLookWR`、`healthcheckup`、`hospitalShop-main`、`cheats-harper`、`ejaculation-harper`、`claimableHarperCredits`、`gggharperinterest` 等 58 个 `harper*` 名 |
| 有意覆盖的原版 widget | **`buswait`**（唯一一个，见 §5.4） | 其它任何原版 widget |
| CSS class | `robert-*` | `.harper-stockholm`、`.harper-purple`、`.claimable-harper-*`、`.maplebirch-*`；**不要用 `!important` 覆写 `#homeDescPillContainer` / `#hpi_*` / `#base-characteristics`**（哈珀已覆写）。原版 `.wraith` 可以安全使用（象牙怨灵并不拥有它） |
| 翻译键 | `RobertNPC.*` | 无前缀的键 |
| 图片路径 | `img/npc/robert/*` | `img/ui/condom/modded010~025.png`、`img/ui/pepper-spray/modded0*.png`、`img/misc/icon/harper*`、`img/ui/harper_interest.png`、`img/skindetail/1~8.png`、`img/ui备用/wraith-forgive.png`、`img/misc/icon/-silver-conch-icon.png` |
| BeautySelector type | （本 mod 未用） | `ClaimableHarper_base`、`GameOriginalImagePack` |
| 服装 type tag | （本 mod 未用） | `nurse`（哈珀独占，`setup.clothingTraits` 里已注册） |
| 全局 JS 函数名 | 全部包在 IIFE 内，**不新增全局函数**（`window.RobertNPC` 是唯一的自有全局量） | 哈珀的 21 个全局函数（`registerHarperStatMacros`、`harperStatChange`、`syncHarperDom`…）、`isPossibleLoveInterest`、`onTakeClick`、`initPillContextButtons`、`effects` |

### ⚠️ 为什么命名空间是 `window.RobertNPC` 而不是 `setup.RobertNPC`

**这不是风格选择，是硬性约束。** 参见 §7「已知故障」。

`maplebirchAddon` 的 `params.script` 在 ModLoader 的 **`afterRegisterMod2Addon`** 阶段执行，
而这个阶段**早于 SugarCube2 引擎启动** —— 此时 `setup`、`V`、`T`、`State` 全都还不存在。
第一版用了 `setup.RobertNPC ??= {}`，结果四个脚本全部报 `setup is not defined` 而中止，
整个 mod 的 JS 侧（NPC 注册、状态数值、概率判定）一点都没跑起来。

所以：

- **命名空间挂在 `window.RobertNPC`**（与框架自己用 `window.maplebirch`、`window.lanSwitch`
  的做法一致）；
- **脚本顶层不得触碰 `setup` / `V` / `T` / `State`**。这些只能在
  `$(document).on(':passageinit', ...)` 之类的运行时回调里用 —— 那时引擎已经启动。
- 唯一例外是 `robert-tweak.twee` 之类的 **twee/widget**：它们由 SugarCube 渲染，
  天然在引擎启动之后，可以安全使用 `V`。

对照记忆点：**script = 引擎启动前（只有 window）；twee = 引擎启动后（有 setup/V）。**

**绝不能包装（wrap）的 4 个原版全局函数** —— 哈珀已经包装过，再包一层会把它覆盖掉：

| 函数 | 哈珀的标记 |
| :--- | :--- |
| `window.onTakeClick` | `.harperMedsPatched = true` |
| `window.initPillContextButtons` | `.harperMedsPatched = true` |
| `window.effects` | `.harperMedsPatched = true` |
| `window.isPossibleLoveInterest` | 框架（maplebirch）在 `NPCManager.Init()` 里**整体替换**为它的实现 |

真要改这些函数，先检测 `<fn>.harperMedsPatched` 标记，再在哈珀的版本之上叠加。

**三条硬规则**

1. **绝不覆盖原版段落。** 本 mod 只新增段落；要给原版加东西，用 §5 的补丁方式。
2. **绝不重定义原版 widget。** 需要改行为时用 `ReplacePatcher` 改 JS。
   特别地，`willpowerdifficulty` 已被哈珀 mod 覆盖过——再覆盖一次会让两者的参数净化同时失效。
3. **新增的文件名都要带 mod 前缀。** 不同 mod 的同名 JS/CSS 会被 ModLoader **拼接**而不是覆盖，
   同名 twee 会被后加载的 mod 覆盖——两种情况都很难查。

---

## 3.1 框架的恋爱对象接入做了什么（重要）

`RB.NPC_CONFIG.loveInterest = true` 会让框架（`inject_early.js` 的 `NamedNPC.setup`）做三件事：

1. 把 `"Robert"` 加进内部 `type.loveInterestNpcs`；
2. 启动时执行 `setup.loveInterestNpc = [...new Set([...原数组, ...loveInterestNpcs])]`
   ——**是合并去重，不是整体重写**，所以不会和象牙怨灵 / 哈珀对 `setup.loveInterestNpc`
   的补丁互相覆盖（这正是三方共存的关键：谁都不许整体重写这个数组）；
3. 为 `"Robert"` 生成默认解锁条件
   `romanceConditions['Robert'] = [() => (V.robertSeen ?? []).includes('romance')]`。

同时 `loveAlias: ['Robert', '罗伯特']` 会生成
`setup.loveAlias.Robert = () => lanSwitch('Robert', '罗伯特')`，自动跟随游戏语言。
**这一项不只是为了显示中文 —— 原版 `relation-box` 会调用 `setup.loveAlias[名字]()`，
缺了它社交页面渲染罗伯特时会直接抛异常。不要删。**（详见 §5.2）

`important: true` 则让框架把 `"Robert"` 推进 `T.importantNpcOrder`，
也就是社交页面的「Primary Relationships（主要关系）」分组。
但**能不能真正显示出来取决于 `init` 字段**，与 `important` 无关 —— 见 §5.2。

> **坑（已经踩过并修掉）**：不要在 `NPC_CONFIG` 里写 `"romance": []`。
> 框架会用这个空数组**覆盖**默认条件，而 `[].every(...) === true`，
> 结果是 `isPossibleLoveInterest('Robert')` 恒为 `true`，恋爱对象无条件解锁。
> `framework.js` 里对此有注释说明；要自定义条件时必须写成「返回布尔的函数数组」。
> 本 mod 当前的条件是「爱意达到 60」。

---

## 4. 图片占位怎么用

`img/` 下的两张图都是工作区根目录 `新占位图片.png`（32×32）的**逐字节副本**，
只是放在不同目录以便区分用途，文件名统一为 `占位图片.png`：

| 路径 | 用途 | 代码位置 |
| :--- | :--- | :--- |
| `img/npc/robert/占位图片.png` | 人物立绘占位 | `framework.js` 的 `RB.IMG.portrait` |
| `img/占位图片.png` | 图标占位（当前用作出租车图标） | `RB.IMG.icon` + `<<widget "robertTaxiIcon">>` |

**换成正式素材时（两步必须同步，否则图片加载不出来）：**

1. 把真实图片放进 `img/`（例如 `img/npc/robert/robert-portrait.png`）；
2. 改 `boot.json` 的 `imgFileList` 换成新路径；
3. 改 `framework.js` 的 `RB.IMG`；
4. 若换的是图标，还要改 `robert-taxi.twee` 里 `<<widget "robertTaxiIcon">>` 的 `src`；
5. 重新打包。

**注意事项**

- 图片必须是**真正的 PNG**（文件头 `89 50 4E 47`）。把 `.jpg` 改名成 `.png` 会让图片加载失败。
- 图片路径必须以 `img/` 开头，并且**同时**出现在 `boot.json` 的 `imgFileList` 里，
  否则 ModLoader 找不到它。`boot.json` 里还要有 `ImageLoaderAddon` 的声明（已经有了）。
- 在 twee 里引用本 mod 的图片时，用 `<img src="img/npc/robert/xxx.png">` 这种写法，
  渲染管线会自动把它交给 ModLoader 换成 zip 里的图；widget `<<robertPortrait>>` 已经封装好了。
- 需要更多占位图时，复制同一份 `新占位图片.png` 并起不同目录名即可 —— 不要用同名不同目录之外
  的区分方式，ModLoader 按完整路径查图。

---

## 5. 如何接入原版段落（给罗伯特加入口）

本 mod 不覆盖原版段落。要让玩家在游戏里找到入口，推荐两种做法：

### 做法 A：TweeReplacer（推荐）

在 `boot.json` 的 `addonPlugin` 里加一段。注意 **`findString` 必须写汉化后的中文原文**，
因为汉化 mod 的替换在 TweeReplacer 之前已经生效：

```json
{
  "modName": "TweeReplacer",
  "addonName": "TweeReplacerAddon",
  "modVersion": "^1.7.0",
  "params": [
    {
      "_comment": "在孤儿院卧室加一个『去找罗伯特』的入口",
      "passage": "Bedroom",
      "findString": "（这里填汉化后的原文，必须逐字一致）",
      "replace": "（这里填原文 + 你的链接）<<if window.RobertNPC?.canAppear?.()>><br><<link [[去找罗伯特|Robert Menu]]>><</link>><</if>>"
    }
  ]
}
```

同时把它加进 `dependenceInfo`：`{"modName": "TweeReplacer", "version": "^1.7.0"}`。

### 做法 B：ReplacePatcher（改 JS 时用）

用于修改 `game/03-JavaScript/**` 里的原版逻辑，例如把罗伯特加进恋爱对象名单：

```json
{
  "modName": "ReplacePatcher",
  "addonName": "ReplacePatcherAddon",
  "modVersion": "^1.3.0",
  "params": {
    "js": [
      {
        "_comment": "把罗伯特加入恋爱对象设置菜单",
        "from": "case \"Robin\":",
        "to": "case 'Robert': return V.robert && V.robert.met === 1;\n\t\tcase \"Robin\":",
        "fileName": "ingame.js"
      }
    ]
  }
}
```

> ⚠️ 上面这条只是**示例格式**。`ingame.js` 的 `case "Robin":` 这个锚点**已被象牙怨灵 mod 占用**
> （它在这里插入了 `case 'Ivory Wraith':`）。如果你也要改这一处，必须换成与它不重叠的锚点，
> 或者接受"必须排在象牙怨灵之后加载"的约束。

---

## 5.1 ⚠️ 不要用 `<<npcincr>>` 改罗伯特的属性

原版 `<<widget "npcincr">>`（`game/base-system/named-npcs.twee:1211`）里有一张**硬编码白名单**：

```
<<set _validNNPCNames to ["Avery","Bailey",…,"Ivory Wraith","Zephyr"]>>
<<if !_validNNPCNames.includes(_nam)>>
    <<error { message: "NNPC '" + _nam + "' is not whitelisted for use with <<npcincr>>"}>>
<</if>>
```

`Robert` 不在里面，所以 **`<<npcincr Robert love 1>>` 会直接抛红字错误**。

要把它加进白名单需要一条 TweeReplacer 补丁，但那段文本**哈珀 mod 已经打过补丁**
（它在同一张表的 `"Leighton", "Quinn", "Ivory Wraith", "Mason"]>>` 处追加了 Harper 与中文名）。
两个 mod 争同一个锚点，加载顺序一变就会互相脱锚 —— 这正是象牙怨灵与哈珀之间最经典的冲突模式。

**所以本 mod 改用 JS 接口，零补丁、零锚点：**

```js
window.RobertNPC.addStat('love', 5);   // 直接改，内部自己钳制到 0–100
window.RobertNPC.getStat('love');      // 读取
window.RobertNPC.setStat('rage', 80);  // 设为 80
```

在 twee 里就是：

```
<<run window.RobertNPC.addStat('love', 5)>>
```

或直接用 widget：

```
<<robertStat love "add" 5>>
```

实现见 `framework.js` 的 `npcStat / npcSetStat / npcAddStat / ensureNpcStats`。
它写入 `V.NPCName` 里名为 `Robert` 的对象，和框架的 NPC 数据是同一份。
**代价**：原版 `<<relationshipclamp>>` 不会钳制这四个字段，所以钳制在 JS 侧自己做
（`RB.STAT_LIMITS`，统一 0–100）。

---

## 5.2 社交页面与罗伯特的四个属性

### 四个属性

需求指定罗伯特拥有**怒气 / 性欲 / 爱意 / 支配**四个属性。这四个都是**原版就有的字段名**，
所以本 mod 不注册任何自定义统计项 —— 直接用原版字段，社交页面会自动按原版样式渲染。

| 字段 | 中文 | 范围 | 原版显示 |
| :--- | :--- | :--- | :--- |
| `rage` | 怒气 | 0–100 | Rage，图标 `img/ui/sym-rage.png` |
| `lust` | 性欲 | 0–100 | Lust（竖排图标） |
| `love` | 爱意 | 0–100 | 名称取 `setup.loveAlias.Robert()` → 「好感」/ Affection |
| `dom` | 支配 | 0–100 | Dominance，紫色 |

它们本来就是原版 `baseNNPC` 模板里的字段，也正是原版 `<<widget "relation-box">>`
里 `T.importantNpcStats` 的前四项（顺序恰好是 love / lust / dom / trauma / rage），
所以只要往 `T.npcConfig` 里加一条 "Robert" 配置，原版就会把它渲染成关系格。

### 「初次遇到之后才显示」是怎么实现的

**关键不是 `important`，而是 NPC 对象上的 `init` 字段。**

原版 `<<widget "relation-box">>`（`base-system/widgets.twee:3380`）第一行就是：

```
<<if _npcData and _npcData.init is 1>>
```

`init` 不为 1 时整格**直接不渲染**。框架只负责把 Robert 注入 `V.NPCName`
并把 `init` 设为 0，**不会**帮你置 1 —— 那是剧情作者的责任。

所以本 mod 在 `RB.markMet()` 里显式置位：

```js
vars.met = 1;            // 本 mod 的剧情标记
npc.init = 1;            // ← 这一行才让社交页面开始显示罗伯特
RB.ensureNpcStats();     // 顺手把四个属性补齐
```

`markMet()` 在**初次遇到罗伯特**时被调用（当前有两个入口：初见段落 `Robert Greet`、
以及第一次坐他的出租车），而且是**幂等**的 —— 重复调用不会重复加工。
配合 `important: true`（让框架把 Robert 推进 `T.importantNpcOrder`，即
「Primary Relationships 主要关系」分组），最终效果就是：

```
初次遇到之前 → 社交页面完全没有罗伯特这一格
初次遇到之后 → 出现在主要关系分组，显示四个属性
```

### 社交页面的配置来源

四个属性的显示配置写在一条 TweeReplacer 补丁里（见 §5.2 末尾的补丁 3），
插进原版 `Social` 段落的 `T.npcConfig`：

```js
"Robert" : {
    important : true,
    love : { maxValue : 100 },
    lust : { maxValue : 100 },
    dom  : { maxValue : 100 },
    rage : { maxValue : 100 }
},
```

**⚠️ 一个必须知道的陷阱**：原版 `relation-box` 里有一行

```js
name : setup.loveAlias[T.npcData.nam](),
```

对**没有别名的 NPC 会直接抛异常**（`undefined is not a function`）。
本 mod 之所以在 `NPC_CONFIG` 里必须写 `loveAlias`，不只是为了显示中文，
更是为了让社交页面能安全渲染罗伯特这一格。**不要删掉 `loveAlias`。**

### 锚点为什么选 `Zephyr`

补丁 3 锚在原版 `Social` 的 `"Zephyr" : { ... },` 区块上。原因：

- 更前面的 `"Wren"` 区块处在拼接边界上（前后都有其他条目），锚它不够稳；
- 更后面的 `"Ivory Wraith"` 被**象牙怨灵**当锚点用；
- 再后面的 `"Harper"` 区块是**哈珀**自己插入的。

`Zephyr` 是「没有任何 mod 改动过的最后一个完整区块」，锚它可保证与两个参照 mod 都不重叠。

> 顺带说明：哈珀的锚点（`"Zephyr" : {...},` **不含末尾换行**）与本 mod 的锚点
> （**含末尾换行**）构成**严格前缀嵌套** —— 本 mod 的锚点完整包住了哈珀的锚点，
> 且本 mod 的 `replace` 以哈珀的锚点原文开头。因此**两种加载顺序都能命中**，
> 只是罗伯特和哈珀在配置里的先后会随顺序变化（纯外观差异，无功能影响）。
> `check_conflicts.py` 会自动识别这种「安全嵌套」，不会误报为冲突。

### ⚠️ 新增具名 NPC 必须登记「平铺键」（否则名字在原版正文里是英文）

本 mod 的 `Robert` 是**新 NPC**，ModI18N 不认识它。而 ModI18N 把原版里所有 NPC 名字显示
都改写成 `setup.NPC_CN_NAME(...)`（遭遇正文、`<<glust "Robert">>` 这类提示宏、
恋爱对象提示、社交页面、童贞记录……），查不到就**原样返回英文**。

框架给这个函数打了补丁，会回退查框架语言表 —— 但要求表里存在
**「键名 === 英文原文」**的条目。所以两个文件里都要写这种平铺键：

```json
"Robert": "罗伯特",
"taxi driver": "出租车司机",
"a young man who works near the orphanage": "一个在孤儿院附近活动的年轻男人"
```

另外职业词 `$description` 走的是 ModI18N 自己那张 `setup.NPCTitleList_cn_name`
（`"英文,中文|英文,中文"` 串，查不到同样退回英文），由
`RB.ensureI18nNameFix()`（`framework.js`，在 `:passageinit` 幂等调用）追加。

排查入口：**作弊菜单 → NPC 栏 → 「名字显示」**（`RB.nameReport()`）。
完整来龙去脉见 §8「故障 4」。

---

## 5.3 副驾驶事件（罗伯特的车）

### 完整流程

```
Robert Taxi Seat（判定司机，车费已扣）
  ├─ 陌生司机          → <<robertTaxiStrangerDrive>> → 直接到达
  └─ 罗伯特            → <<robertTaxiRobertDrive>>：问候 + 选座位
       ├─【坐后座】     → 回到 Robert Taxi Seat，由后座分支判定（**必然**进其中一个）
       │                  · 已是恋人（$robertRomance）且掷点 ≤ 10%
       │                       → Robert Taxi Back Anger 1【后座·页面2】
       │                          ├【为其口交】（淫乱 ≥4 级）→ Robert Taxi Oral Fight
       │                          │     → Caress Back Result → Caress Back Rest → Destination
       │                          └【无事发生】→ Robert Taxi Back Anger 2【后座·页面3】→ 到达
       │                  · 其余（非恋人 100% / 恋人 90%）
       │                       → Robert Taxi Back Find 1【后座·页面4】
       │                          ├【摸索一下】→ Robert Taxi Back Find 2【后座·页面5】
       │                          │     80% 什么也没摸到 / 20% 摸到 £1–50 →【下车】到达
       │                          └【无事发生】→ Robert Taxi Back Find End → 到达
       └─【坐副驾驶】   → Robert Taxi Front Seat Intro
            └ 继续 → Robert Taxi Hand        手放到你腿上
                 ├【摆动腿部远离罗伯特的手】→ Robert Taxi Destination（结算 A）
                 └【保持不动】  → Robert Taxi Hand Aid   淫乱判定 → 继续
                      └ Robert Taxi Slow Down           淫乱判定
                           ├【抵抗】<<def 1>> → Robert Taxi Destination（结算 B）
                           └【无视】→ Robert Taxi Caress ←──────────┐
                                ├【继续】→ 回到本段落（跳转次数 +1）─┘
                                └【结束】→ Robert Taxi Destination（结算 A）
```

- **结算 A**（以「保持不动」结束）= `<<robertTaxiEndHold>>`：**性欲 +2**、爱意 +1（爱意 > 30 时 +2）
- **结算 B**（以「摆动腿部远离 / 抵抗」结束）= `<<robertTaxiEndSwing>>`：按下表对性欲、爱意分段判定

### ⚠️⚠️ 属性提示的书写规范：**符号个数 = 数值幅度**

> 这条规范由需求方在 2026-10 确定，**新增任何改罗伯特属性的选项都必须遵守**；
> 守卫脚本 `check_stat_chips.py` 会强制它（行级 + 作用域级双向核对）。

需求方以后只用「一个 +／两个 +／两个 −」描述属性变化，
**选哪个宏变体就等于把数值定下来了**：

| 需求说法 | 提示宏 | 数值 |
| :--- | :--- | ---: |
| 一个 + | `<<gdom "Robert">>` | `addStat('dom', 1)` |
| 两个 + | `<<ggdom "Robert">>` | `addStat('dom', 2)` |
| 三个 + | `<<gggdom "Robert">>` | `addStat('dom', 3)` |
| 一个 − | `<<ldom "Robert">>` | `addStat('dom', -1)` |
| 两个 − | `<<lldom "Robert">>` | `addStat('dom', -2)` |
| 三个 − | `<<llldom "Robert">>` | `addStat('dom', -3)` |

四个属性各自都有 1–3 档的正负变体（lust / love / dom 是原版宏，rage 是本 mod 自建）：

```
dom   gdom +1 / ggdom +2 / gggdom +3     ldom -1 / lldom -2 / llldom -3
lust  glust +1 / gglust +2 / ggglust +3  llust -1 / lllust -2 / llllust -3
love  glove +1 / gglove +2 / ggglove +3  llove -1 / lllove -2 / llllove -3
rage  grage +1 / ggrage +2 / gggrage +3  lrage -1 / llrage -2 / lllrage -3
```

- **单次增减控制在 1–3 档**；超过 3 档没有对应变体，先问需求方怎么拆。
- **一个属性只给一个提示块**，不要靠叠块凑幅度（`<<lldom>>` 本身就显示
  「- - 罗伯特的支配」—— 框架的 `statChange` 按幅度重复符号）。
- 改了属性就必须给提示；同一作用域里「数值集合」与「提示集合」必须相等。
- 爱意按 `loveGain()` 浮动时用 `<<robertLoveChip>>`，它自动输出对应符号数。
- 提示块只写在**选项/正文**里，且必须是 `<<link>>` 的兄弟节点（见 §5.3）。

### ⚠️ 到达只能用一个按钮（已修过的 bug）

**不要**在到达页用原版的 `<<destination5>>` / `<<destinationeventend>>`。它们会：

- `<<destination5>>` → 调 `<<domus>>` / `<<oxford>>` 这类 widget，这些 widget 通过
  `<<add_link>>` 往 `$link_table` 里塞一条旅行链接（就是玩家看到的
  「牛津街 (0:05) (学校)」），最后由 `<<displayLinks>>` 渲染出来 → **多一个按钮**；
- `<<destinationeventend>>` → 再生成一个 Next 按钮 → **又多一个按钮**。

而且它们的目标和页面里已有的【继续】**完全一样**，纯属重复。

所以本 mod 自己渲染到达：

| widget | 作用 |
| :--- | :--- |
| `<<robertTaxiArriveText>>` | 按 `$bus` 输出一句到达描写 |
| `<<robertTaxiArriveLink>>` | 按 `$bus` 输出**唯一一个**【继续】链接，指向对应街道段落 |

车程的 5 分钟已经在目的地链接的 `<<pass 5>>` 里走完了，到达时不再推进时间。

`check_macros.py` 里有常驻守卫会拦住这个写法（见 §6）。

| 性欲区间 | 怒气 | 爱意区间 | 爱意变化 |
| :--- | :--- | :--- | :--- |
| >30 且 ≤50 | **+1**（`<<grage>>`） | >30 且 ≤50 | **−1**（`<<llove>>`） |
| >50 且 ≤80 | **+2**（`<<ggrage>>`） | >50 且 ≤80 | **−2**（`<<lllove>>`） |
| >80 且 ≤100 | **+3**（`<<gggrage>>`） | >80 且 ≤100 | **−3**（`<<llllove>>`） |

（原文里爱意最后一行写的是「大于80小于等于80」，按前后文规律应为「≤100」，本 mod 按 ≤100 实现。
如果确实是要「落空」，改 `<<robertTaxiEndSwing>>` 里的条件即可。
幅度已按「符号个数 = 数值幅度」规范收进 1–3 档，见上一节。）

### 淫乱判定（`<<robertTaxiLewd 级别>>`）

用原版 `hasSexStat("promiscuity", N)`，等级阈值来自原版 `ingame.js:1518-1544`：

| 判定 | 阈值 | 效果 |
| :--- | :--- | :--- |
| 0 级 | < 1 | 无变化 |
| 1 级 | ≥ 1 | 压力 +10、性奋 +10 |
| 2 级 | ≥ 15 | 性奋 +20（**不加压力**） |
| 3 级及以上 | ≥ 35 | 性奋 +30（**不加压力**） |

提示文本用原版 `<<promiscuous1/2/3>>`，与游戏其他地方写法一致。

### 选项名里带上效果（重要）

带淫乱判定的选项，效果直接写在**选项名**里，用 `<<robertLewdOption>>`：

```
<<robertLewdOption [[继续|Robert Taxi Caress]]>>          选项
<<robertLewdOption [[继续|Robert Taxi Caress]] "count">>  选项，且点击时 $robertTaxiJump +1
```

| 淫乱等级 | 渲染出来的选项名 |
| :--- | :--- |
| 0 / 1 级 | `继续｜` + 红 `Stress +` + `｜` + 红 `Arousal +` + `｜` + 粉紫 `Robert's Lust +` + `｜` + 青 `Promiscuity 1` |
| 2 级 | `继续｜` + 红 `Arousal +` + `｜` + 粉紫 `Robert's Lust +` + `｜` + 浅蓝 `Promiscuity 2` |
| 3 级及以上 | `继续｜` + 红 `Arousal +` + `｜` + 粉紫 `Robert's Lust +` + `｜` + 蓝 `Promiscuity 3` |

#### ⚠️⚠️ 效果提示**只能出现在选项里**，绝对不要写进正文

这些数值是「**点这个选项**才会发生的变化」。
写在正文里等于宣称「读到这里数值就已经变了」—— 那是错的，
而且会和选项里那份**重复显示一遍**，看起来就像一串乱码。

所以分工是固定的：

| 位置 | 负责 | 当前实现 |
| :--- | :--- | :--- |
| 段落正文 | **只改数值、不显示任何提示** | `<<robertTaxiLewd 档位>>` 保持静默 |
| 选项 | 显示带颜色的效果提示 | `<<robertLewdOption>>` |

（早期版本两边各放了一份，结果正文里冒出
`｜+ 压力｜+ 性奋｜淫乱 1｜+ 压力｜+ 性奋｜+ Robert的性欲｜淫乱 1级` 这种重复串 —— 已修。）

#### 0 级也要显示效果，而且按 1 级处理

原版 `hasSexStat` 里 1 级的注释写得很明白：

```js
case 1:
    /* Do not use for events or checks, only for checking if value is above level 0.
       Level 1 actions should always be available. */
    return statValue >= 1;
```

也就是说**0 级与 1 级是同一个判定**，所以效果一样、显示上也统一写「淫乱 1级」，
不存在「淫乱 0级」这种说法。

#### ⚠️ 标签必须按等级分支生成，不能写死

2 级、3 级只加性奋、**不加压力**，所以标签里不能出现「压力」——写死就是骗玩家。
判定逻辑在 `window.RobertNPC.lewdEffectTokens()`（`modules/robert-stats.js`），
返回标记串 `stress arousal lust` 或 `arousal lust`。

#### 颜色必须用原版宏产生，不要自己写色值

| 宏 | 颜色 class | 定义处 |
| :--- | :--- | :--- |
| `<<gstress>>` | `red` | text.js:67 |
| `<<garousal>>` | `red` | text.js:81 |
| `<<glust "Robert">>` | `lewd`（粉紫） | text.js:261 |
| `<<promiscuous1>>` / `2` / `3` | `teal` / `lblue` / `blue` | text.twee:2488+ |

`lewd` 是原版 `01-base.css` 里的类，就是游戏里「性欲上升」的既有配色；
`<<promiscuousN>>` 按等级取色，与游戏里其他淫乱提示完全一致。
所以本 mod **不需要任何自定义样式**。

> ⚠️ 用无参变体 `<<promiscuous1>>`，**不要**用 `<<promiscuous N>>`：
> 后者会读段落临时变量 `_desperateaction` 来决定要不要追加「| Desperate Action」。
> 那个变量只在本 mod 之外的场景里设置，在出租车事件里是 `undefined` —— 没必要耦合它。

#### ⚠️ 「性奋」是 PC 的，不是罗伯特的「性欲」

这两个中文名很像，但是**完全不同的东西**，改代码时不要混：

| 名字 | 是什么 | 存在哪 | 上限 |
| :--- | :--- | :--- | :--- |
| **性奋** arousal | **玩家**自己的兴奋度 | `$arousal` | `$arousalmax = 10000` |
| **性欲** lust | **罗伯特**这个 NPC 的属性 | `V.NPCName` 的 Robert 对象 | 100 |

淫乱判定加的是 **PC 的性奋**（`<<arousal>>`）；罗伯特自己的性欲只在事件结算时
由 `<<robertTaxiEndHold>>` 等改动。

> 选项标签里显示的 `Robert's Lust +` 是**纯展示**，本判定不会真的改它 ——
> 这是需求明确要求的表现方式。罗伯特的属性仍然只在收尾时结算。

#### ⚠️ `<<arousal>>` 的数值必须乘 100

原版 `<<arousal N>>` 里 N 是**原始值**，而 `$arousalmax = 10000`。
直接写 `<<arousal 10>>` 只加 **0.1%**，侧边栏完全看不出变化 ——
这就是「点了选项但没看到性奋增加」的原因。

参照原版的尺度：轻微 200–300、明显 600、强烈 1000–2000。
需求说的「+10」是玩家视角的 10 点，乘 100 后 = 1000 原始值，正好落在「强烈」档。

**而 `<<stress N>>` 不一样**：它内部已经乘了 40，所以 N 本身就是「玩家视角的点数」，
`<<stress 10>>` = 400 原始值，**不需要**再换算。这两个宏的尺度不同，不要一起处理。

换算系数定义在 `window.RobertNPC.AROUSAL_SCALE`（= 100）。
写法上要用**反引号**包住表达式（原版惯用法，见 `base-system/promiscuity.twee:100`
的 ``<<arousal `$_n * 100`>>``）：

```
<<arousal `10 * (RobertNPC?.AROUSAL_SCALE ?? 100)`>>
```

不要写成 `<<arousal 10 * 100>>` —— 宏参数没有括号保护时可能被拆成两个参数。

#### ⚠️ `<<自定义宏>>` 后面不要接 `<</li>>`

SugarCube 会把「自定义宏 + 紧跟其后的 `<</...>>`」当成这个宏的**结束标签**。
所以这样写：

```
<li><<robertLewdOption [[继续|目标段落]]>><<set ...>><</li>>
```

会把 `<</li>` 当**纯文本原样渲染出来**，玩家就直接看到 `<</li>` 这五个字。

正确做法是把整行（含 `<li>` 包裹）都收进 widget 内部，段落里只写：

```
<<robertLewdOption [[继续|目标段落]]>>
```

选项正文里也有一份同样的提示，用 `<<robertLewdLine>>`：

```
……你的呼吸逐渐加粗，喉咙里那点声音被你咽了回去，却没能完全藏住。
｜Stress +｜Arousal +｜Robert's Lust +｜淫乱 1级
```

（`Stress +` / `Arousal +` 是红色，`Robert's Lust +` 是粉紫色 —— 见下。）
两个 widget 都不需要传参，等级由 `RB.promiscuityLevel()` 内部取。

#### 颜色必须用原版宏产生，不要自己写色值

提示的颜色全部来自原版 `statDisplay.create` 注册的宏（`base-system/text.js`）：

| 宏 | 颜色 class | 定义处 |
| :--- | :--- | :--- |
| `<<gstress>>` | `red` | text.js:67 |
| `<<garousal>>` | `red` | text.js:81 |
| `<<glust "Robert">>` | `lewd`（粉紫） | text.js:261 |

`lewd` 是原版 `01-base.css` 里的类，就是游戏里「性欲上升」的既有配色。
所以提示色与游戏其他地方**完全一致**，本 mod 不需要任何自定义样式。

标记与颜色的对应集中在 `<<robertLewdIndicators>>`（`robert-tweak.twee`），
标记本身由 `window.RobertNPC.lewdEffectTokens()` 生成（`stress arousal lust`）——
**两边名字必须一致**，改一处要同步另一处。

#### ⚠️ `<<自定义宏>>` 后面不要接 `<</li>>`

SugarCube 会把「自定义宏 + 紧跟其后的 `<</...>>`」当成这个宏的**结束标签**。
所以这样写：

```
<li><<robertLewdOption [[继续|目标段落]]>><<set ...>><</li>>
```

会把 `<</li>` 当**纯文本原样渲染出来**，玩家就直接看到 `<</li>` 这五个字。

正确做法是把整行（含 `<li>` 包裹）都收进 widget 内部，段落里只写：

```
<<robertLewdOption [[继续|目标段落]]>>
```

#### ⚠️ 实现陷阱：wiki 链接参数是 `.link` 不是 `.passage`

`<<robertLewdOption>>` 需要从传进来的 wiki 链接里取出目标段落名。
SugarCube 构造这个参数对象时用的是（见 `format.js`）：

```js
arg.link = text;                                        // 段落名
arg.text = evalText(markup.text) ?? arg.link;           // 显示文本
```

**没有 `.passage` 字段。** 早期版本写成 `_rbNode.passage`，取到 `undefined`，
`<<link>>` 拿不到目标 → 不设置 `T.link` → 段落页脚判定「没有可用链接」，
玩家看到红字：

```
The passage Robert Taxi Hand Aid has no usable links.
```

正确写法（也是 DoL 自己的惯用法，见 `overworld-town/loc-cafe/widgets.twee:320`
的 `<<link [[_linkName|Cafe Coffee]]>>`）是**把目标段落名写成字面量**，
显示文本用 `<<= >>` 在链标里拼：

```
<<link [[<<= _rbNewLabel>>|_rbNode.link]]>><</link>>
```

`[[标签|目标]]` 的目标部分可以是表达式（SugarCube 对链接参数会走
`evalPassageId` / `evalText` 求值），所以 `_rbNode.link` 放这里是合法的；
而链标里用 `<<= >>` 是原版就有的写法（工作区里另有 8 处同样的用法）。

### 循环与「跳转次数」

`Robert Taxi Caress` 是循环页，每次进入都做一次淫乱判定。
`$robertTaxiJump` 表示**已经点了几次【继续】**：

| | 值 |
| :--- | :--- |
| 从 `Robert Taxi Slow Down` 首次进入 | `0`（`Slow Down` 里 `<<set $robertTaxiJump to 0>>`） |
| 点一次【继续】 | 链接里 `<<set $robertTaxiJump += 1>>` 后跳回本页 |
| 显示条件 | `<<if $robertTaxiJump lt 4>>` |

所以页面一共出现 **5 次**，前 4 次可以点【继续】，**点了 4 次之后【继续】消失**，只剩【结束】。

#### ⚠️⚠️ 跨段落的状态必须用 `$` 存档变量，不能用 `_` 临时变量

这是踩过的坑，而且**静默失效、不报错**：

SugarCube 的 `Engine.play()` 在每次进入新段落前都会执行（见 `format.js`）：

```js
_state = States.Playing, TempState = {}, State.clearTemporary(), State.clearLocal(), ...
```

也就是说 **`_` 临时变量在每次翻页时都会被清空**。当初 `$robertTaxiJump` 写成
`_robertTaxiJump`，每次点【继续】跳回本页时它都被重置为 0，
`<<if _robertTaxiJump lt 4>>` 于是永远成立 —— **循环上限完全不生效**，
玩家可以无限点下去。改成 `$robertTaxiJump` 后正常。

**判断标准（记这一条就够了）**：
> 只要这个值需要「下一页还看得见」，就必须用 `$` 存档变量。
> 只在**同一个段落内部**用的、进了下一页就不需要的中间量，才用 `_`。

本 mod 当前的划分：

| 类型 | 变量 |
| :--- | :--- |
| 存档变量（跨段落） | `$robertTaxiJump`、`$robertTaxiEnding`、`$robertTaxiDriver`、`$robertTaxiSeat` |
| 临时变量（仅本页） | `_robertTaxiIsRobert`、`_rbNode`、`_rbSep`、`_rbLevelText` 等 |

代价：`$` 变量会被写进 `State.history` 与存档。本 mod 用的都是纯数字和短字符串
（`0` / `""` / `"front"` 等），开销可以忽略。

> `check_macros.py` 有一条守卫能抓「一个段落赋值、另一个段落读取」的临时变量，
> 但抓不到「每页都用 `<<set _x to 默认值>>` 重置」这种 —— 那在结构上和合法用法
> 完全一样。所以这条规则只能靠人记住。

### ⚠️ 收尾标记的设计（改之前请读）

结算用 `_robertTaxiEnding` 区分，取值只有两种：

| 值 | 含义 |
| :--- | :--- |
| `""`（空） | 保持不动路线 —— `Slow Down` 之后无论走哪条路离开，都算「以保持不动结束」 |
| `"swing"` | 摆动腿部远离 / 抵抗 |

`Robert Taxi Slow Down` 进入时会**先清空**这个标记，只有【抵抗】才把它设成 `"swing"`。
这样做的好处是：「保持不动」不需要单独打标记（因为它之后必然经过 `Slow Down`），
也不会把上一次坐车残留的值带进这一次。**不要**在【保持不动】的链接里直接写 `"hold"` ——
那样从 `Slow Down` 一路走到 `Caress` 再【结束】时，语义会变得含糊。

### 关于「反抗值」

【抵抗】里的 `<<def 1>>` 就是需求里的「+1 反抗值」——
原版 `def` 宏（`game/base-system/stat-changes.js:879`）是 `submissive(-amount)`，
即反抗倾向 +1。用 `<<defianttext>>` 显示变化提示。

---

## 5.4 出租车系统（罗伯特当司机）

### 玩家看到的流程

1. 在镇上任何有公交站的街道，行动列表里 **【等公交】和【消磨时间】之间** 多出一条
   **【等待出租车 (0:02)】**（等 2 分钟，与公交相同）。
2. 点进去显示：**你上了出租车。价£5。**，下面按住宅区 / 商业区 / 工业区 / 森林
   分组列出目的地（车程 5 分钟，与公交相同）。
3. 点目的地后掷一次骰子决定司机：
   - **陌生司机** —— 什么都不发生，正常送到，扣 £5、走 5 分钟。
   - **罗伯特** —— 第一次会触发「初次见面」（信任 +5、标记已认识），之后每次心情 +3。
4. 之后走的就是原版公交的到达流程，所以街外事件、地图、`<<destinationeventend>>`
   全部自动一致。

### 概率与设置

| 项 | 值 |
| :--- | :--- |
| 默认概率 | 罗伯特 50% / 陌生司机 50% |
| 可调范围 | 0% – 90%（罗伯特） |
| 补足规则 | 剩余概率全部归陌生司机，两者相加恒为 100% |
| 设置位置 | 设置 → 通用页最上方，新增「出租车」区块 |
| 存档位置 | `$options.robertTaxiChance`（与其它游戏设置同级，随存档保存） |

设置项用原版 `<<numberStepper>>` 渲染，与游戏自带设置外观一致。
概率读取统一走 `window.RobertNPC.taxiChance()`，它会把值取整并钳制到 0–90，
**即使存档被改坏也不会越界**。

### 实现要点（改之前请先读）

- **时间与车费**：等车 2 分钟（`<<pass 2>>`）、车程 5 分钟（目的地链接里的 `<<pass 5>>`），
  与公交的 `0:02` / `0:05` 完全对应。车费 £5 = **500 文**（原版公交 £1 = 100 文）。
- **余额检查**：原版 `<<money>>` 在余额不足时会 `throw`，所以进段落先判断
  `$money gte 500`，不够就只显示「你的钱不够付车费。」，不渲染目的地链接。
- **目的地系统复用原版**：`$bus` 沿用原版变量，目的地链接由原版 `<<destination>>`
  渲染、到达由 `<<destination5>>` + `<<destinationeventend>>` 完成。
  **不要另造一套目的地系统**，否则街外事件和地图会不同步。
- **`<<buswait>>` 是有意覆盖的**（也是本 mod 唯一覆盖的原版 widget）。
  原因：原版只往 `$link_table` 推一行公交链接，没有可插入的中间位置；
  而需求要求插在公交与消磨时间之间。所以 `robert-taxi.twee` 里把原版那一行
  **照抄了一遍**再加出租车那行 —— **改这个 widget 时千万不要把公交那行删掉**。
  这条覆盖已登记在 `check_conflicts.py` 的 `ALLOWED_WIDGET_OVERRIDES` 里。
- **出租车图标**：`<<icon>>` 宏会把路径固定拼成 `img/misc/icon/<名字>`，指向不了本 mod 的图片，
  所以 `<<robertTaxiIcon>>` 直接用 `<img>` 标签，交给 ModLoader 的 `HtmlTagSrcHook` 换成
  zip 里的 `img/占位图片2.png`。换正式图标时改这个文件并同步 `boot.json` 的 `imgFileList`。
- **扩展罗伯特剧情**：改 `<<robertTaxiRobertDrive>>` 这个 widget 即可；
  需要多段对话就按 `Robert ` 前缀继续加段落，再从 widget 里 `<<link>>` 过去。

### 两条补丁的锚点

| 目的 | passage | 锚点来源 |
| :--- | :--- | :--- |
| 覆盖 `buswait` | `Widgets Bus` | **汉化后**的 `game/overworld-town/loc-bus/widgets.twee:4` |
| 插入设置项 | `Options Overlay` | `game/base-system/overlays/options.twee:73-75` 的自动保存开关 |

### ⚠️⚠️ 锚点必须用「汉化后的中文」，不能用原版英文

这是本 mod 第一版踩过的坑，**改锚点前务必读完这一节**。

ModLoader 的执行顺序是：

```
原版文本 → ModI18N 汉化替换 → TweeReplacer 补丁（本 mod 在这里）
```

也就是说 **TweeReplacer 看到的已经是中文了**。第一版把 `findString` 写成原版英文：

```json
"findString": "\t<<add_link \"<<busicon>><<link [[Wait for a bus (0:02)|Bus]]>><<pass 2>><</link>><br>\">><<hideDisplay>>"
```

后果有两个，而且是叠加的：

1. **匹配失败** → 日志报 `cannot find findString ... in:[Widgets Bus]`，
   补丁根本没生效，`<<buswait>>` 没被覆盖成带出租车那版；
2. **原版 `<<buswait>>` 被 ModI18N 译成了中文**，于是街上那条链接显示为
   `Wait for a bus` —— 这正是「【等公交】变成了英文」的直接原因。

所以正确的写法是照抄**汉化后**的文本（当前为 `等待公交车`）：

```json
"findString": "\t<<add_link \"<<busicon>><<link [[等待公交车 (0:02)|Bus]]>><<pass 2>><</link>><br>\">><<hideDisplay>>"
```

**同一个中文字符串在三个地方必须逐字一致**，改一处就要同步另外两处：

| # | 位置 | 作用 |
| :--- | :--- | :--- |
| 1 | `boot.json` → 补丁 1 的 `findString` | 让补丁找得到目标行 |
| 2 | `robert-taxi.twee` → `<<widget "buswait">>` 里那行公交链接 | 覆盖后保证公交车还在、且是中文 |
| 3 | （校验用）导出目录 `passage/Widgets Bus.twee` | 判断是否真的匹配 |

**换汉化 mod 或升级 ModI18N 后，译文可能变化**，此时这三处都要跟着改。
判断方法：跑一次游戏导出错误日志，然后

```bash
python check_conflicts.py          # 会自动搜索工作区里的「错误日志*」目录
```

它会把 `findString` 与**实际打补丁后的游戏文本**逐字比对，匹配不上会直接报冲突。

### 挑锚点的安全做法

- **锚点至少 60 字符**，并且包含一个完整的 `<<宏 参数>>` 或一整句带句末标点的中文句子。
- **绝不改写锚点原文**：只在它前面或后面追加。哈珀 mod 曾经把 `lust.name` 从「痴迷」写回
  `Obsession`，直接打断了象牙怨灵以「痴迷」为锚的补丁——这是他们第四轮冲突的根因。
- **先确认锚点唯一**：在原版源码里搜一次，命中 2 处以上就加长。
- **缩进是有用的避让维度**：同一个 `<<case>>`，一边带前导 `\t`、一边不带，就不会互相锚中。
  象牙怨灵与哈珀正是靠这个让 `speech-SYDNEY` / `speech-GWYLAN` 在两种加载顺序下都命中。
- **大段补丁要在关键分支处切分**：哈珀把 `speech-Harper` 的大补丁在 `<<case "Gwylan">>` 处
  拆成两条相邻补丁，这样象牙怨灵的短锚点无论落在切分前还是之后都能命中。

### 两个 mod 共同触碰的 12 个原版段落（高危区）

以下段落被象牙怨灵与哈珀 **同时**打了补丁。整段避开是最省事的选择；
如果确实要改，请先读两边 `boot.json` 里对应的 `findString`，确保你的锚点与它们一个字符都不重叠。

| 危险度 | 段落 | 说明 |
| :--- | :--- | :--- |
| 极高 | `Widgets Actions Text` | 象牙怨灵 4 条 + 哈珀 5 条；哈珀还整段重写了 `checkforloveinterests` widget |
| 极高 | `Widgets` | 象牙怨灵 4 条（`Math.clamp($NPCName[_i].love, …)` 好感上限链）+ 哈珀 3 条（lust 钳制、`druggedcaption` 整 widget 重写） |
| 极高 | `Social` | 象牙怨灵 3 条（`T.specialNPCs` / `T.importantNpcOrder` / Ivory Wraith 块）+ 哈珀 2 条；**第四轮冲突的原始现场** |
| 极高 | `Widgets speech-Harper` | 象牙怨灵用 15 字符的 `<<case "Gwylan">>` 当锚点，而该文本就在哈珀重写的 widget 体内 |
| 高 | `Widgets Named Npcs` | 哈珀在这里维护 `<<npcincr>>` 的 NPC 白名单 |
| 高 | `Widgets Events Street` | 象牙怨灵插街头事件、哈珀插农场指认分支（`streeteffects` 被重写） |
| 高 | `Widgets speech-SYDNEY` / `Widgets speech-GWYLAN` | 两边 **findString 逐字相同**：`<<case "Black Wolf" "Great Hawk">>`，最脆弱的两点 |
| 中 | `Start` | 标题页（象牙怨灵改声明文本、哈珀加致谢按钮） |
| 中 | `Bedroom` | 象牙怨灵加「设为恋人」链接、哈珀加 `<<harperMedsDaily>>` |
| 中 | `Widgets Journal` | 象牙怨灵：`<<if $pubfame>>`；哈珀：毒贩提示 |
| 中 | `Traits` | 象牙怨灵加「怨灵的倒影」、哈珀加「斯德哥尔摩：哈珀」 |

**绝不要用作锚点的文本**（已被占用或过于脆弱）：

```
<<case "Robin">>            <<case "Gwylan">>          <<case "gwylan">>
<<case "Black Wolf" "Great Hawk">>                      <<case "Eden">>
<<case "Alex">>             <<case "Sydney">>           <<default>>
<<effects>>                 <<cleareventpool>>          <<if $pubfame>>
<<addevent "streetSeduction" 1>>
<<set $outside to …>><<set $location to …>><<effects>>   ← 所有街道/室内段落的统一页头
可访问地点                   ← 小巷段落统一标题
<<set $daily.school.attended.*>>                         ← 6 个课程段落
Math.clamp($NPCName[_i].*)                               ← 好感/lust 钳制链
T.importantNpcOrder = [      T.specialNPCs = [ …
setup.loveInterestNpc = [    ← 原版 + 框架 + 象牙怨灵 + 哈珀 四方交汇，只能 push/unshift，不能整体重写
title: "NPC特质",
<<switch $_LI>>              <<switch $carried.neck.photo>>
<<if $options.images is 1>>  <<if $hookah_plot is 1>>
<<widget "streeteffects">>   <<widget "checkforloveinterests">>
<<widget "druggedcaption">>  <<widget "speech-harper">>
<<widget "willpowerdifficulty">>
```
- 本 mod 自己的段落名统一用 `Robert ` 开头，避免和 `Wraith*`、`harper-*` 系列撞名。

---

## 6. 验证工具

自检脚本，**每次改动后都跑一遍**（`build_mod.py` 会自动跑带 ✓ 的五个）：

```bash
python check_conflicts.py           # 命名冲突 + 补丁锚点 + 规范
python check_macros.py              # 宏完整性（防 macro does not exist）
python build_mod.py                 # 校验 + 页面级检查 + 打包
```

| 脚本 | 抓什么 | 由 build 自动跑 |
| :--- | :--- | :---: |
| `check_conflicts.py` | 段落 / widget / 全局名 / 图片重名；补丁锚点 vs 真实文本 | — |
| `check_macros.py` | 未定义宏；脚本顶层误用 `setup`/`V`；跨段落临时变量 | — |
| `check_comments.py` | 注释块孤立 `*/`、嵌套 `/*` | ✓ |
| `check_expr_chars.py` | `<<=>>` 表达式里的全角字符 | ✓ |
| `check_caress_invariant.py` | 【页面1】告示不变式（选项提示 vs 页面档位） | ✓ |
| `check_combat_page.py` | 遭遇战页结构（38 项断言） | ✓ |
| `check_feat.py` | 成就注册与授予链路 | ✓ |
| `check_stat_chips.py` | **提示宏**：参数写成数量、同一属性叠提示块、标签硬编码英文、写进链标、符号个数≠数值 | ✓ |
| `check_dead_end.py` | **死路页面**：输出了正文却没有链接来源的互斥分支（「has no usable links」） | ✓ |

### `check_conflicts.py` 做四件事

1. **命名冲突**：把本 mod 的段落 / widget / 全局名 / 存档变量 / 图片路径，
   分别与**原版 15,629 段落 + 4,936 widget**、象牙怨灵（48 段落）、
   哈珀（229 段落 + 58 widget）、图包（18,433 张图）比对。
2. **补丁锚点交叉**：解析象牙怨灵 / 哈珀 `boot.json` 里的 TweeReplacer 补丁，
   检查本 mod 是否与它们在**同一段落**用了相同或互相包含的 `findString`。
3. **锚点 vs 真实文本（最关键）**：自动搜索工作区里的「错误日志*」导出目录，
   用**打完所有补丁之后**的 `passage/*.twee` 校验每条 `findString` 能否唯一匹配。
   这一步专门用来抓「汉化把原文改掉导致锚点失效」这类问题 —— 见 §5.4。
4. **前缀规范**：段落名 / widget 名 / 变量名是否带本 mod 前缀；
   有意覆盖原版 widget 的（目前只有 `buswait`）会打印登记的原因。
5. **`buswait` 一致性**：`boot.json` 的 `findString` 与本 mod widget 输出的公交链接
   必须是同一段文字（见 §5.4）。
6. **嵌套锚点判定**：若与其它 mod 的锚点构成前缀关系，会自动判断是「安全嵌套」
   （较长锚点完整包含较短锚点 → 两种加载顺序都能命中）还是需要人工确认。
7. **出租车到达守卫**：禁止在非 widget 段落里使用 `<<destination5>>` /
   `<<destinationeventend>>` —— 它们会让到达页多出一个与【继续】重复的按钮
   （见 §5.3）。注释里的说明文字不算。
8. **段落完整性**：本 mod 内部段落是否重名、是否与原有段落重名、
   每个 `[[...|目标]]` 是否真的存在。
   目标是变量或表达式时（如 `_rbNode.link`）会自动识别为「运行时求值目标」并跳过，
   不会误报 —— 但也意味着**这类写法静态查不出错**，改动时要格外小心。

> 第 3 项依赖实机导出的错误日志。**没有导出目录时它会给出提醒而不是静默跳过**，
> 因为这是唯一能证明补丁真能生效的检查。

### `check_macros.py` 做两件事

1. 把本 mod 用到的每个 `<<宏>>` 与「原版 widget 定义 + `Macro.add`/`DefineMacro` +
   SugarCube 内建宏 + 象牙怨灵 / 哈珀定义的 widget」逐一比对，报出未定义的宏调用。
2. **脚本顶层全局检查**：扫描本 mod 的 `.js`，找出在 IIFE 顶层引用了
   `setup` / `State` 的地方（解析时跳过注释与字符串内容，并按花括号层级
   区分「IIFE 顶层」与「函数内部」——只有顶层才是危险的）。
   这是专门为「故障 2」加的门禁 —— 见 §8。
3. **`findString` 与 widget 输出一致性**：本 mod 覆盖了 `buswait`，所以
   `boot.json` 的 `findString` 与本 mod widget 里那行公交链接必须是同一段文字。
   两者分叉会同时导致「补丁失效」和「公交显示错误语言」。脚本会自动比对。

两个脚本都做过**回归测试**：把当初的两个 bug 重新注入（`findString` 改回英文、
顶层改回 `setup.RobertNPC`），确认它们都会以非零退出码报错。

---

## 7. 打包

```bash
python build_mod.py                # 校验 + 打包，产出 RobertNPC.mod
python build_mod.py --check-only   # 只校验 boot.json 引用的文件是否都存在
```

脚本会：

1. 解析 `boot.json`，逐个检查引用到的文件是否真实存在（**漏打包会直接报错**，不会静默通过）；
2. 检查路径是否都是正斜杠相对路径；
3. 用 Store/Deflate + UTF-8 条目名打包，条目名一律正斜杠
   （社区最常见的故障就是 zip 条目名用了反斜杠，导致图片全部读不到）；
4. 打包后重新打开 zip 逐条自检，并打印完整清单。

打包产物 `RobertNPC.mod` 直接拖进游戏的 ModLoader 管理器即可加载。

---

## 8. 已知故障与修复记录

### 故障 1：界面文本变成英文（【等公交】显示为 `Wait for a bus`）

- **现象**：测试后街上那条链接显示英文，而不是汉化的「等待公交车」。
- **根因**：`findString` 写的是原版英文，但 ModI18N 的汉化替换**先于** TweeReplacer 执行，
  补丁阶段文本已是中文 → 匹配失败 → 覆盖 `buswait` 的补丁没生效。
- **为什么「变成英文」而不是「保持中文」**：原版 `<<buswait>>` 由 ModI18N 正常译成中文；
  但本 mod 的补丁一旦生效，输出的就是**我自己照抄的那行**——第一版照抄的是英文原文。
  两个错误叠加，最终看到英文。
- **修复**：`findString` 与 widget 输出都改用汉化后的中文 `等待公交车`。
- **防复发**：`check_conflicts.py` 新增「锚点 vs 真实文本」检查（§6 第 3 项）。

### 故障 2：4 个脚本全部未执行（`setup is not defined`）

- **现象**：ModLoader 日志 4 条红色错误，每个脚本一条：
  `[addon] 执行 Script 文件失败: framework.js (来自 RobertNPC): setup is not defined`
  —— 意味着 NPC 注册、状态数值、出租车的概率判定**全都没跑**。
- **根因**：`maplebirchAddon` 的 `params.script` 在 **`afterRegisterMod2Addon`** 阶段执行，
  早于 SugarCube2 启动，此时 `setup` / `V` / `T` 都不存在。
  第一版在脚本顶层写了 `setup.RobertNPC ??= {}`，直接抛异常终止。
- **修复**：命名空间改为 `window.RobertNPC`；脚本顶层不再触碰 `setup` / `V` / `T`。
- **防复发**：§3 末尾那节「为什么命名空间是 `window.RobertNPC`」写明了这条时机约束；
  `check_macros.py` 的「脚本顶层全局检查」会挡住同类改动。

### 故障 3：点了选项后整页空白（在段落渲染中调 `Engine.play`）

- **现象**：点【坐后座】之后**什么都看不到**，连正文都没有；用侧边栏的历史回溯
  反而能看到正确的页面，再点回溯箭头又全都消失。
- **根因**：本 mod 第一版在后座分支里写了
  `<<run Engine.play("Robert Taxi Back Find 1")>>`。
  那一刻**当前段落还在渲染中**，`Engine.play` 会立刻把目标段落渲染进 `#passages`；
  可当前段落的渲染随后收尾时，又把自己的输出写进 `#passages` ——
  于是目标页被**整页覆盖**，只剩下当前段落里跳转之后的空白。
  历史里记录的却是目标段落，所以回溯能看到内容 —— DOM 与历史不同步。
- **正确写法**：用 `<<goto "段落名">>`。SugarCube 的 `<<goto>>`（`format.js:419352`）
  内部就是为这个场景写的：

  ```js
  Config.navigation.gotohell || (Wikifier.stopWikify = 2);
  setTimeout(() => Engine.play(passage), Engine.minDomActionDelay);
  ```

  即「停掉本段落剩余渲染」+「把跳转推迟到当前 DOM 任务之后」；
  `stopWikify` 会在下一段渲染开始时由 `Passage.render` 重置为 0（`format.js:445830`），
  不会污染后续段落。
- **参考实现**：哈珀 mod 全库都用 `<<goto "…">>`，包括插进原版
  `<<widget "streeteffects">>` 的街头事件跳转（其 `boot.json` 里的
  `<<goto "Harper Estate Blame Street">>`）—— 与本 mod 的场景完全相同。
- **同一个 bug 的两处**（都已修）：
  1. `robert-taxi.twee` → `Robert Taxi Seat` 后座分支的两个出口；
  2. `robert-ride-event.twee` → `<<widget "robertRideEvent">>`（牛津街表白事件），
     它在牛津街段落渲染过程中被调用，属于同一类。
  当时误以为「`<<goto>>` 不是 SugarCube 宏（全仓库 grep 不到 `Macro.add("goto")`）」——
  其实它是 SugarCube **内建**宏，注册在引擎内部而不是故事文件里。
- **副产品**：`<<goto>>` 会停掉牛津街段落的剩余渲染，所以该段落末尾的
  `<<set $eventskip to 0>>`（`oxford.twee:267`）在事件触发那一次不会执行 ——
  这正好挡住「同一趟连出两个事件」，`checkRide` 也会因此返回 NO；
  下一次进入牛津街时正常清零。

### 故障 4：罗伯特的名字全显示成英文（`setup.NPC_CN_NAME` 不认新 NPC）

- **现象**：游戏里罗伯特的名字**在所有地方都是英文 `Robert`**，而其他文字全部正常中文。
  （最容易看到的是后座事件选项旁的 `+Robert支配度` / `−Roberts性欲` 这类提示宏。）
- **根因**（三方协作的接缝，全部核对过源码）：
  1. **ModI18N** 把原版里所有 NPC 名字显示都改写成 `setup.NPC_CN_NAME(...)`：

     | 位置 | 实际写法 |
     | :--- | :--- |
     | 遭遇正文 | `<<set _text_output to setup.NPC_CN_NAME($NPCList[$index].fullDescription)>>` |
     | 状态提示宏 | `statDisplay.create("glust", npc => statDisplay.statChange(\`${setup.NPC_CN_NAME(npc)}的性欲\`, 1, "lewd"))` |
     | 恋爱对象提示 | `<<= setup.NPC_CN_NAME($_LI)>>现在是你的恋爱对象了！` |
     | 社交页面 / 童贞 / 怀孕 | `<<NPC_CN_NAME _npcData.nam>>` 等 |

  2. ModI18N 的名字表（`setup.NPCNameList_cn_name`）里没有 Robert，
     于是 `NPC_CN_NAME('Robert')` **原样返回英文**。
  3. 框架给这个函数打过补丁（`compatibleModI18N`）：

     ```js
     setup.NPC_CN_NAME = t => {
         let n = 原实现(t);
         return n !== t ? n : (lang.has(t) ? lang.auto(t) : t);
     };
     ```

     即「查不到就走框架语言表」—— 而框架语言表里当时**没有**键名为 `Robert` 的条目，
     `lang.has('Robert')` 为假，于是继续返回英文。
- **修复**：
  1. `translations/CN.json` / `EN.json` 增加**平铺键**（键名 = 英文原文）：
     `"Robert"`、`"taxi driver"`、`"a young man who works near the orphanage"`；
     同时把 `RobertNPC.title` 从「罗伯特」改成职业词「出租车司机」。
  2. `framework.js` 新增 `RB.ensureI18nNameFix()`（在 `:passageinit` 里幂等调用）：
     往 `maplebirch.lang` 写入同样三条键（数据 + 运行期双保险），
     并把 `"taxi driver,出租车司机"` 追加进 `setup.NPCTitleList_cn_name` ——
     因为职业词 `$description` 走的是 ModI18N 自己那张表，
     写法是 `(…split('|').find(…)) .split(',')[1] || $description`，**查不到就退回英文**。
  3. `robert-guard.twee` 的 `$description` 覆盖**从只覆盖口部场景扩展到两个场景**：
     手部遭遇战的正文同样走 `<<combatPersons>>`，不覆盖就会印出职业词。
  4. 作弊菜单 → NPC 栏新增「**名字显示**」诊断块（`RB.nameReport()`），
     四条逐条显示：框架语言 / `NPC_CN_NAME('Robert')` 的结果 /
     语言表里有没有这条键 / ModI18N 职业词表里有没有。名字再出问题时先看这里。
- **防复发**：这条约束写在 §5.2 与 `README_汉化说明.md` §3
  —— **新增任何具名 NPC，都必须同时登记「平铺键」**，否则名字在原版正文里永远是英文。

### 故障 5：提示宏显示错（三个提示块 / 「+ 8的性欲」/「+ Rage」）

- **现象**（都出现在后座事件【无事发生】这一行的提示上）：
  1. 支配 −5 显示成 **三个**提示块：`- - 罗伯特的支配｜- - 罗伯特的支配｜- 罗伯特的支配`；
  2. 别处出现 **「+ 8的性欲」**；
  3. 怒气显示成英文 **`+ Rage`**。
- **根因**（三条互不相同，但都属于「提示宏」这一类）：
  1. **叠提示块**：`<<ldom>>`＝−1、`<<lldom>>`＝−2、`<<llldom>>`＝−3 本身就是**档位**，
     框架的 `statDisplay.statChange(where, amount, colour)` 会
     `("- " or "+ ").repeat(|amount|)` ——即**符号个数就是幅度**。
     旧写法把 −5 拆成 `<<lldom>><<lldom>><<ldom>>`（−2−2−1），
     于是并排渲染三个块、共 5 个减号。
  2. **参数写成数量**：这些宏的参数是 **NPC 名**（ModI18N 里为
     `statDisplay.statChange(\`${setup.NPC_CN_NAME(npc)}的性欲\`, 1, "lewd")`），
     `<<glust 8>>` 会让 `NPC_CN_NAME(8)` 原样返回 8 → 「+ 8的性欲」。
     出处：`robertTaxiEndOral`。
  3. **标签硬编码英文**：`statDisplay.statChange("Rage", 1, "gold")` 的第一个参数是
     **显示文本**。自建的 `<<grage>>` / `<<lrage>>` 原来写死 `"Rage"`，
     中文界面里就单独冒出一个英文词。
- **修复（并确立书写规范）**：需求方给出的口径是
  **「提示的符号个数 = 数值幅度」** —— 说「两个 +」就写 `<<gglust "Robert">>`
  并把数值设成 +2。于是：
  - 新增 `<<ggrage>>` / `<<gggrage>>` / `<<llrage>>` / `<<lllrage>>`（rage 补齐 1–3 档），
    标签统一走 `RobertNPC.chipLabel('rage')` → 「罗伯特的怒气」/「Robert's Rage」；
  - 新增 `<<robertLoveChip>>`：按 `loveGain()` 的**实际**幅度输出 +1 / +2 的提示；
  - **全 mod 的数值一并收进 1–3 档**，让数值与提示永远相等：

    | 位置 | 旧值 | 新值 |
    | :--- | ---: | ---: |
    | 初见（`Robert Greet` / 出租车初次） | 性欲 +5 | **+1** |
    | 再次搭乘 | 性欲 +1、爱意 +1/+2 | 不变 |
    | 保持不动收尾 | 性欲 +5 | **+2** |
    | 口交收尾（副驾驶线到达） | 性欲 +8 | **+2** |
    | 摆动/抵抗收尾 | 怒气 +4/+8/+15、爱意 −2/−5/−10 | **怒气 +1/+2/+3、爱意 −1/−2/−3** |
    | 遭遇战结算 | 性欲 净 −8 / −18 | **−2（手部）/ −3（口部）** |
    | 后座【为其口交】 | 支配 +5、性欲 −5 | **+2 / −2** |
    | 后座【无事发生】 | 支配 −5、性欲 +5、怒气 +5 | **−2 / +2 / +2** |
    | 表白【同意】 | 爱意 +10（无提示） | **+3**（`<<ggglove>>`） |
    | 表白【我再考虑考虑】 | 爱意 −3（无提示） | −3 + `<<llllove>>` |
- **防复发**：`check_stat_chips.py`（已接入 `build_mod.py` 的页面级检查）六条规则：
  参数不能是数量、同一行不能叠同一个提示宏、自建宏标签不能硬编码英文、
  提示宏不能写进链标、**行级符号=数值**、**作用域级数值集合=提示集合**。
  已用反例回归验证过（坏写法都能抓到，正常写法不误报）。

### 故障 6：钱不够时点【等待出租车】报 `The passage Robert Taxi has no usable links.`

- **现象**：PC 身上钱 < £5 时，在街上点【等待出租车 (0:02)】→
  整页只有「你的钱不够付车费。」，没有**任何**可点的选项 →
  SugarCube 抛红字 `The passage Robert Taxi has no usable links.`
- **根因**（两层叠在一起）：
  1. `Robert Taxi` 段落的结构是
     `<<if $money gte 500>>…目的地链接…<<else>>    你的钱不够付车费。<</if>>`，
     也就是**钱不够那一支本来就没有链接**；
  2. 段落末尾的 `<<destination>>` 看着像个兜底，其实它只是个
     `<<switch $bus>>` → `<<Xquick>>`（按目的地分派的快捷旅行链接）。
     本 mod 为了让「上一次的目的地」不残留，在本段落开头写了 `<<unset $bus>>`
     —— `$bus` 一空，`<<destination>>` 什么都不渲染。
     **原版 `<<Bus>>` 段落有一模一样的结构却没暴露问题**，只是因为它不 unset `$bus`，
     残留值恰好提供了几条可用链接 —— 属于「靠巧合活着」。
- **修复**（采用需求方给的方案二，改动最小、且不碰补丁锚点）：
  给「钱不够」那一支补一个【继续】链接，去向用 `$passagePrev`
  （原版 `PassageHeader` 设置的「来这一页之前在哪」，
  与 `<<link [[Confirm|$passagePrev]]>>` 同一惯用法），
  并用 `Story.has()` 兜底，免得调试跳转进来时 `$passagePrev` 是 `"none"` 又变成死路。
  > 为什么不用方案一（钱不够就不显示【等待出租车】）：那要改 `<<widget "buswait">>`，
  > 而它的那行公交链接与 `boot.json` 的 `findString` 是逐字耦合的，
  > 动它有脱锚风险；而且「藏掉入口」玩家不知道自己为什么叫不到车。
- **防复发**：新增 `check_dead_end.py`（已接入 `build_mod.py`）。它把每个会渲染的段落
  拆成「顺序执行区」与「互斥分支」，规则是：**输出了正文的分支，必须有链接来源**；
  链接来源包括 `<<link>>` / `<<goto>>` / `<<add_link>>` 与本 mod 的链接型 widget，
  而 **`<<destination>>` 不算**（它依赖 `$bus`）。
  覆盖判定有两条：顺序区里有链接，或某个**带 `<<else>>`** 的 `if` 每一支都有链接。
  `_test_dead_end.py` 是它的合成用例回归（7 例，含这个 bug 的原始形状与遭遇战页的易误报形状）。

### 变更 6：属性由自定义统计项改为原版四属性

- **背景**：初版给罗伯特注册了 `robertTrust` / `robertMood` 两个**自定义**统计项
  （通过 `maplebirch.npc.addStats`）。
- **改动**：需求确定罗伯特使用**怒气 / 性欲 / 爱意 / 支配**四个属性，
  它们都是原版既有字段名 `rage` / `lust` / `love` / `dom`，
  于是删掉了 `addStats` 调用与两个自定义统计项，直接用原版字段。
- **收益**：
  - 社交页面自动按原版样式渲染，不需要自己写 UI；
  - 不需要 `applyStatDefaults` 那套自定义统计项注入流程，少一层依赖；
  - 属性名与原版一致，将来接原版系统（恋爱、怀孕、战斗）不用转换。
- **旧存档兼容**：旧存档里残留的 `robertTrust` / `robertMood` 字段不会被读取，
  留在 NPC 对象上但无害；四个新属性由 `ensureNpcStats()` 在 `:passageinit` 时补齐为 0。

### 环境提示：`EmptyMod` 的 `Robert Taxi` 重名警告

```
CacheRecord.fillMap()    has duplicate name: [Robert Taxi] [passageDataItems RobertNPC]
CacheRecord.replaceMerge() has duplicate name: [passageDataItems EmptyMod] [passageDataItems RobertNPC] Robert Taxi
```

`EmptyMod` 是 ModLoader 自带的最小示例 mod（`src/insertTools/MyMod/boot.json`）。
它**不在** `tree.json` 里，说明没有真正加载，只是 ModLoader 的缓存残留记录。
按加载顺序，本 mod 在它之后，同名段落以本 mod 为准，**功能不受影响**。

如果不想看到这两条警告，把游戏 HTML 里内嵌的 `EmptyMod` 从 `modList.json` 去掉重编译即可。
（本 mod 侧无法消除——段落名是需求指定的。）

---

## 9. 开发约定小结

- **日志**：统一用 `window.RobertNPC.log(msg, level)`，前缀 `[RobertNPC]`，方便在 ModLoader
  日志里过滤。
- **翻译**：所有面向玩家的文本走 `window.RobertNPC.t(...)`，键统一以 `RobertNPC.` 开头
  （例如 `RobertNPC.intro.title`），不要硬编码中文，否则以后补英文要满仓库找。
- **属性增减**：一律走 `window.RobertNPC.addStat('rage'|'lust'|'love'|'dom', N)`，
  **不要**用原版 `<<npcincr>>`（白名单问题，见 §5.1）。
- **容错**：任何初始化代码都包 `try/catch`。一个 mod 抛异常会污染整个 ModLoader 加载流程，
  这也是社区里"装了新 mod 之后别的 mod 也报错"的常见原因。
- **变量初始化**：用 `V.robert ??= {}` 而不是直接赋值，保证旧存档也能安全升级。
- **改完必跑**：`check_conflicts.py` + `check_macros.py` + `build_mod.py`（见 §6 / §7）。
