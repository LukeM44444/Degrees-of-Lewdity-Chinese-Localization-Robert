# RobertNPC（罗伯特）— 汉化说明与开发备忘

本文件记录两件事：

1. **本 mod 的汉化做法**（为什么文本这么写、和其他汉化 mod 怎么共存）；
2. **给后续开发的备忘**（冲突雷区、验证清单、踩过的坑）。

详细的文件结构与用法见 [README.md](README.md)。

> 📌 **写新页面之前先读** [dol-sugarcube-mod-SKILL.md](../dol-sugarcube-mod-SKILL.md)
> （也安装为 DSH skill `dol-sugarcube-mod`）。那里固化了：
> 选项与颜色提示的**正确形状**（照抄哈珀 mod：`<<link>>` 单独一行 + 颜色宏作兄弟节点，
> **不用 `<ul>`/`<li>`**、颜色**不能**放进链标）、宏/HTML 的硬约束、
> 跨段落变量必须用 `$`、数值尺度（`<<arousal>>` 与 `<<stress>>` 不同）、
> 高潮的正确调法，以及**一次只写一页、写完按【页面N】/【选项M】提问**的协作流程。
> 这些全部是踩过坑之后确认的结论，别重新发明。

---

## 一、汉化做法

### 1. 文本全部走翻译键，不硬编码

本 mod **没有**把中文写死在 twee 里，而是：

- 中文放 `translations/CN.json`，英文放 `translations/EN.json`；
- `boot.json` 的 `maplebirchAddon` → `params.language` 声明这两个文件；
- 代码里统一用 `window.RobertNPC.t('翻译键')` 取文本。

框架的语言管理器会按 `navigator.language` 自动选 `CN` / `EN`
（见框架 `LanguageManager.setLanguage`）。取不到键时本 mod 会降级返回键名而不是 `[key]`，
这样漏翻的条目在界面上一眼就能看出来。

### 2. 与 ModI18N（官方汉化 mod）的关系

`ModI18N` 的工作方式是往原版 passage 里做**整段文本替换**（`i18n.json` 是它的词典，
按 `pos` 定位原文件偏移）。它**不会**翻译第三方 mod 自己的段落和翻译键，所以：

- 本 mod 自己的段落 → 由本 mod 的 `translations/*.json` 负责；
- 本 mod 需要引用**原版段落文本**时 → 必须引用**汉化后**的中文，因为 ModI18N 的替换先执行。

### 3. NPC 名字用标准译名

`Robert → 罗伯特`。名字同时登记在**四处**，改的时候要一起改：

| 位置 | 字段 | 作用 |
| :--- | :--- | :--- |
| `framework.js` | `RB.NPC_NAME_CN`（兜底常量）、`RB.NPC_TITLE_CN`、`RB.NPC_DESC_CN` | 翻译表取不到时的兜底值 |
| `framework.js` | `RB.NPC_CONFIG.loveAlias` | 社交页面关系格的名字 |
| `translations/CN.json` | `RobertNPC.name` / `.title` / `.desc` | 本 mod 自己的 `<<robertName>>` 等显示 |
| `translations/CN.json` | **平铺键 `"Robert"` / `"taxi driver"` / 描述句** | **让原版正文里的名字变中文**，见下 |

#### ⚠️⚠️ 为什么必须有「平铺键」（踩过的坑：名字全是英文）

ModI18N 把原版里**所有** NPC 名字显示都改写成 `setup.NPC_CN_NAME(...)`，例如：

- 遭遇正文：`<<set _text_output to setup.NPC_CN_NAME($NPCList[$index].fullDescription)>>`
- **状态提示宏**：`statDisplay.create("glust", npc => statDisplay.statChange(\`${setup.NPC_CN_NAME(npc)}的性欲\`, 1, "lewd"))`
  —— 所以 `<<glust "Robert">>` 会印出「**Robert**的性欲」
- 恋爱对象提示：`<<= setup.NPC_CN_NAME($_LI)>>现在是你的恋爱对象了！`
- 社交页面、童贞记录、怀孕记录……

而 ModI18N 自己的名字表里**没有** Robert，于是 `NPC_CN_NAME('Robert')` **原样返回英文** ——
表现就是「名字全是英文，其他文字都正常」（其他文字走的是 ModI18N 的普通文本替换）。

框架（maplebirch）给这个函数打过补丁：

```js
setup.NPC_CN_NAME = t => {
    let n = 原实现(t);
    return n !== t ? n : (lang.has(t) ? lang.auto(t) : t);
};
```

**只要框架语言表里存在「键名 === 英文原文」的条目**，它就会接管并输出中文。
所以要写的是这种形状的键：

```json
"Robert": "罗伯特",
"taxi driver": "出租车司机",
"a young man who works near the orphanage": "一个在孤儿院附近活动的年轻男人"
```

`framework.js` 的 `RB.ensureI18nNameFix()`（在 `:passageinit` 里跑，幂等）会做同样的写入，
并额外把 `"taxi driver,出租车司机"` 补进 `setup.NPCTitleList_cn_name` ——
因为职业词 `$description` 走的是 ModI18N 自己那张字符串表（查不到会**退回英文**）。

自检：作弊菜单 → NPC 栏 → 「名字显示」那一块，四条全绿即为正常。

> 注意：`NPC_DATA.nam` **必须**保持英文 `Robert`。框架会用它作索引，并把它当作 DoL 的
> NPC 名参与 `$NPC` 判定；改成中文会让 `<<npcincr>>` 之类的原版宏找不到人。
> 中文显示名只在翻译键、平铺键和 `loveAlias` 里出现。

---

## 二、名字冲突核查结论

创建本 mod 前已经核查过：

- **原版**：`Robert` 只出现在两处随机取名表里——`game/base-system/name-list.twee:50`
  和 `game/03-JavaScript/04-Pregnancy/pregnancy.js:20`。它是**路人随机名**，
  不是具名 NPC，原版 `globals.d.ts` 的 `NpcNames` 联合类型里也没有它。
  所以新增 `Robert` 具名 NPC **不会**和原版冲突。
- **象牙怨灵 mod**：NPC 是 `Ivory Wraith`，变量前缀 `V.WraithsReflection`，段落前缀
  `WraithsReflection*` / `*WR`，widget 前缀 `speechWraith` / `Wraith*`。与 `Robert*` 无交集。
- **哈珀 mod**：NPC 是 `Harper`，段落前缀 `harper-*`，宏前缀 `harper*`，
  变量 `$harper_*`。与 `Robert*` 无交集。
- **框架 mod**：自有数据放在 `V.maplebirch.*` 下，本 mod 的 `V.robert.*` 与之无交集。

**唯一需要留意的点**：本 mod 的 `RB.NPC_CONFIG.loveInterest = true` 会让框架把罗伯特接进
恋爱对象系统。象牙怨灵 mod 用 `ReplacePatcher` 改过 `ingame.js` 里的恋爱对象设置菜单
（`case "Robin":` 前插入 `case 'Ivory Wraith':`）。如果本 mod 也去改同一处，两个补丁会互相
脱锚。**因此本 mod 的 README §5 做法 B 里给出的 `from` 锚点与它不同**；真要改这一处时，
请确认两个补丁的 `from` 字符串互不重叠，并在游戏里实际点开「恋爱对象设置」菜单验证一次。

---

## 三、冲突雷区清单（改代码前先看）

### 1. 已被其他 mod 改过的段落（不要拿这些段落里的文本当补丁锚点）

来自象牙怨灵 mod（`Wraith'sReflection` `boot.json`）：

```
Start                     Widgets Attitudes        Bedroom
Town Hall Wait            Town Hall                Mirror Locket
Mirror Locket 2           Lake Ruin Plinth         Widgets Wraith
```

它不是直接改这些段落，而是通过 `TweeReplacer` 的 `findString` 锚点插入内容；
本 mod 若在同一段落用同一段文本做锚点，会因为插入顺序不同而找不到。

来自哈珀 mod（`ClaimableHarper`，共 **542 条**补丁）覆盖范围很广，重点包括：

```
Widgets                   Widgets Named Npcs       Social
speech-SYDNEY             speech-Harper            speech-Gwylan
AsylumHypnosisCommon      及其相关 Asylum* 段落
Street Private Photoshoot Sex                     Widgets School Events
```

另外哈珀 mod 还**覆盖重定义**了原版 widget `willpowerdifficulty`
（在 `harper-widgets.twee` 里）。本 mod 不要重复定义它。

### 2. 原版宏/字段的两个已知坑（哈珀 mod 的实际故障记录）

- `random(min, max)` 的 `max` 必须是**有限整数**。传入 `NaN` / `Infinity` / 非数字字符串会报
  `random max parameter must be an integer`；小数会被 fork 的 `Math.trunc` 静默截断。
  本 mod 的所有数值运算都在 JS 侧用 `Math.round` + `Number.isFinite` 做了净化（见
  `modules/robert-stats.js` 的 `setStat`）。
- `<<npcincr>>` 的 `lust` 等属性有**白名单**，白名单里的 NPC 名必须是英文原名。
  本 mod 若要给罗伯特加数值，用 `maplebirch.npc.addStats` 加自定义项，
  或在 `<<relationshipclamp>>` 里加钳制，不要指望原版白名单自动放行新 NPC。

### 3. 宏完整性自检

游戏源码里带了官方的宏检查脚本 `游戏源代码-degrees-of-lewdity-master/devTools/macro_check.py`
和 `devTools/check.py`。新增 twee 段落前后跑一次，可以提前发现"宏不存在"这类运行时错误
（哈珀 mod 的第五、六轮修复全是这类问题）。

---

## 四、发布前验证清单

- [ ] `python build_mod.py` 通过（引用文件齐全、zip 条目名全是正斜杠）。
- [ ] ModLoader 加载日志里搜 `[RobertNPC]`，确认「初始化完成」且**没有红色错误**。
- [ ] 加载日志里确认 `TweeReplacer` 的 `okCount / errorCount`，本 mod 的 2 条补丁必须
      `errorCount: 0`。
- [ ] 游戏里能看到罗伯特的立绘（占位图能显示 = `ImageLoaderAddon` 配置正确）。
- [ ] 打开「恋爱对象设置」菜单一次（象牙怨灵 mod 的补丁在这里，最容易冲突）。
- [ ] 用旧存档进一次游戏，确认 `V.robert` 能正常初始化，没有 undefined 报错。
- [ ] 反过来调整加载顺序（本 mod 放在象牙怨灵之后）再进一次，确认依然 0 报错。
      两个参照 mod 之间就是靠"顺序无关化"来保证兼容的，本 mod 也照做。

### 出租车专项验证（§5.4 的功能）
- [ ] 走到任意有公交站的街道，确认行动列表里【等公交】和【消磨时间】**之间**出现了
      【等待出租车 (0:02)】，且【等公交】本身还在（覆盖 `buswait` 最容易犯的错就是把它弄丢）。
- [ ] 点【等待出租车】，确认等待了 2 分钟、显示「你上了出租车。价£5。」且列出的目的地
      分组（住宅区 / 商业区 / 工业区 / 森林）与原版公交一致。
- [ ] 点一个目的地，确认：扣了 £5、走了 5 分钟、正常到达该地点。
- [ ] 把设置里的「罗伯特出现概率」分别设成 **0** 和 **90**，各坐几次车：
      - 0 → 应该只出现陌生司机；
      - 90 → 绝大多数是罗伯特；
      - 设成 0 时不会出现「两者概率加起来不足 100%」的情况（陌生司机补足）。
- [ ] 身上钱不足 £5 时点【等待出租车】，确认显示「你的钱不够付车费。」且**不报红字异常**
      （原版 `<<money>>` 在余额不足时会 throw，本 mod 已先做余额判断）。
- [ ] 连着坐两次车，第二次的目的地列表不应残留上一次的选择。
- [ ] 第一次坐罗伯特的车：**性欲 +1、爱意不变**（爱意要靠后续剧情推动）。
- [ ] 第二次坐罗伯特的车：**性欲 +1、爱意 +1**（爱意 > 30 时为 +2，提示会自动变成两个 +）。

### 副驾驶事件专项验证（§5.3 的功能）

- [ ] 罗伯特当司机时**只有**两个选项：【坐副驾驶】【坐后座】。
      **不应**出现「峭壁街 (0:05) (咖啡馆)」这类目的地链接或多余按钮。
- [ ] 选【坐后座】→ **还不是恋人时**与陌生司机流程一致（无事发生、正常到达），
      **不进入**后座事件；是恋人时约 10% 触发「他最近有些火大」。
- [ ] 后座事件【为其口交】只在**淫乱 ≥4 级**时出现；选它 → 进入口部遭遇战，
      且罗伯特的**支配 +2、性欲 −2**（提示为两个 `+ 罗伯特的支配` / 两个 `- 罗伯特的性欲`）。
- [ ] 后座事件【无事发生】→ 进入「只剩不爽」那一页，罗伯特的
      **支配 −2、性欲 +2、怒气 +2**；点【继续】到达目的地，事件结束。
- [ ] **没触发**「他最近有些火大」时（含还不是恋人的情况）→ 必进后座事件（二）：
      感到座位上有什么东西，出现【摸索一下】【无事发生】。
- [ ] 【无事发生】→ 一句过渡后到达目的地，**不加不减任何数值**。
- [ ] 【摸索一下】→ 「你摸到了：」；约 80% 显示「你什么都没有摸到」，
      约 20% 显示金色的 `£N`（N 在 1–50 之间）并**同时增加**同额现金。
      多试几次，确认侧边栏的钱数与提示金额一致（单位是英镑，不是便士）。
- [ ] 该事件末尾的按钮文字是【下车】（其它路线的到达按钮是【继续】）。
- [ ] 陌生司机的到达页**只有**【继续】一个选项，
      **不应**同时出现「牛津街 (0:05) (学校)」这类旅行链接。
- [ ] 点【继续】能正常到达对应街道，且**不再重复扣时间**。
- [ ] 选【坐副驾驶】→ 出现「你在副驾驶座位坐下…」+【继续】。
- [ ] 继续 → 罗伯特的右手放到你腿上，出现【摆动腿部远离罗伯特的手】【保持不动】。
- [ ] 【摆动腿部远离】→ 直接到达，且**不**加反抗值。
- [ ] 【保持不动】→ 出现「罗伯特粗鲁的触碰…」；**0 级与 1 级效果相同**
      （压力 +10、性奋 +10），不是「0 级无变化」。
- [ ] 选项名与正文都要带效果提示，且**按等级正确分支**：
      - 0 级 / 1 级 → `继续｜+性奋｜+压力｜淫乱 1级`（0 级也显示，且写「1级」）；
      - 2 级 → `继续｜+性奋｜淫乱 2级`（**不能出现 +压力**）；
      - 3 级及以上 → `继续｜+性奋｜淫乱 3级`（**不能出现 +压力**）。
- [ ] **点【继续】后侧边栏的「性奋」要能明显看出增加**（约 10%）。
      如果几乎看不出变化，说明 `<<arousal>>` 少了 ×100 换算
      （见 README §5.3 的「`<<arousal>>` 的数值必须乘 100」）。
- [ ] 「性奋」是 PC 的，**不是**罗伯特的性欲 —— 社交页面里罗伯特的性欲不应因淫乱判定而变。
- [ ] 继续 → 「罗伯特渐渐的将车速减慢下来…」+【抵抗】【无视】。
- [ ] 【抵抗】→ **反抗值 +1**（应有 Defiance 提示），到达目的地，并按性欲/爱意区间结算。
- [ ] 【无视】→ 进入循环页；每次点【继续】都会再判定一次淫乱。
- [ ] **点【继续】4 次后，【继续】应消失，只剩【结束】**（该页共出现 5 次）。
      注意数的是**点击次数**，不是页面出现次数。
- [ ] 新开一次坐车，循环上限应重新从 4 开始（不是接着上次）。
- [ ] 两个收尾分支的数值都要核对：
      - 保持不动结束 → 罗伯特性欲 +2、爱意 +1（爱意 > 30 时 +2）；
      - 摆动腿部/抵抗结束 → 按性欲、爱意区间加怒气/减爱意（对照 §5.3 表）。
- [ ] 属性变化**只影响罗伯特**，PC 的性欲/怒气等不受影响。
- [ ] 各页面文字已扩写，不再是干巴巴的一句话。

### 社交页面专项验证（§5.2 的功能）

- [ ] **初次遇到罗伯特之前**打开社交页面 → 主要关系分组里**不应**出现罗伯特。
- [ ] **初次遇到罗伯特之后**（初见段落或第一次坐他的车）再打开社交页面 →
      主要关系分组里出现「罗伯特」，副标题显示 loveAlias 文本（「好感」）。
- [ ] 那一格里能看到四个属性：怒气 / 性欲 / 爱意 / 支配。
      新档四个都是 0，所以**四格都是空的**（原版规则：`> 0` 才显示）——
      这是正常现象。第一次坐他的车后**性欲应为 1**（爱意仍为 0，
      因为需求规定爱意只能由后续剧情推动）。
- [ ] 社交页面**不报红字异常**。重点看有没有
      `setup.loveAlias[...] is not a function` —— 出现这个说明 `loveAlias` 丢了。
- [ ] **名字全部显示为中文「罗伯特」**，不出现英文 `Robert`：
      - 社交页面里罗伯特那一格的名字；
      - 后座事件选项旁的 `+罗伯特支配度`/`−罗伯特性欲` 这类提示宏
        （它们走 `setup.NPC_CN_NAME`，是这个名字问题最容易被看到的地方）；
      - 手部/口部遭遇战的正文（不应出现 `Robert` 或 `taxi driver`）；
      - 作弊菜单 → NPC 栏 → 「名字显示」四条全绿。
      若仍是英文，先看那四条里哪条是红的：
      「框架语言」为 EN 时要去框架控制面板把语言改成 CN；
      「框架语言表里有 'Robert' 这条键」为红说明翻译表没载入或没重编包。
- [ ] 罗伯特的「爱意」达到 60 后，`isPossibleLoveInterest('Robert')` 应为 true
      （恋爱对象设置菜单里能选他）。

---

## 五、待办（骨架 → 完整 mod）1. **正式立绘**：替换 `img/npc/robert/占位图片.png`（见 README §4）。
2. **出租车图标**：`img/占位图片.png` 目前被 `<<robertTaxiIcon>>` 当作出租车图标用。
   画好正式图标后替换它，并同步 `boot.json` 的 `imgFileList` 与 `framework.js` 的 `RB.IMG.icon`
   （或新建 `img/misc/icon/robert-taxi.png` 再改用 `<<icon "robert-taxi.png">>`）。
3. **入口接入**：按 README §5 在孤儿院卧室挂 `<<link [[去找罗伯特|Robert Menu]]>>`。
4. **日程排班**：`modules/robert-schedule.js` 里的 `addSchedule` 目前是空配置，
   需要按框架文档 `docs/CN/NamedNPC/NamedNPCSchedule.md` 补全时段/地点。
5. **剧情内容**：`robert-passages.twee` 目前只有初见 / 菜单 / 交谈占位，
   正式剧情按 `Robert ` 前缀继续加段落。
6. **出租车上的罗伯特剧情**：副驾驶事件已按需求实现（见 README §5.3）。
   后座事件（恋人专属、10% 触发）也已实现：Robert Taxi Back Anger 1 / 2，
   触发判定在 `Robert Taxi Seat` 的后座分支（按 `$robertTaxiSeat is "back"` 分岔）。
7. **属性增减点现状**（改动前先读 README §5.2「符号个数 = 数值幅度」）：
   - 性欲：初次见面 +1、再次搭乘 +1、副驾驶「保持不动」收尾 +2、
     副驾驶「为其口交」到达收尾 +2、遭遇战结算 −2（手部）/−3（口部）、
     后座事件【为其口交】−2 /【无事发生】+2；
   - 爱意：**只能由后续剧情推动**（再次搭乘 +1，爱意 > 30 时 +2；
     两条收尾路线 +1/+2；摆动/抵抗收尾按区间 −1/−2/−3；
     表白【同意】+3、【我再考虑考虑】−3）；
   - 怒气：副驾驶「摆动腿部/抵抗」收尾按性欲区间 +1/+2/+3、
     后座事件【无事发生】+2；
   - 支配：后座事件【为其口交】+2 /【无事发生】−2。
   - ⚠️ 全部为 1–3 档，且**提示宏的符号个数必须等于数值幅度**（守卫脚本强制）。
   - ⚠️ 淫乱判定加的是 **PC 的性奋/压力**，不是罗伯特的属性 —— 两者不要混
     （见 README §5.3 的对照表）。
   增减一律走 `window.RobertNPC.addStat('rage'|'lust'|'love'|'dom', N)`，
   **不要**用原版 `<<npcincr>>`（原因见 README §5.1）。
