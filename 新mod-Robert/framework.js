/*
 * RobertNPC —— 模组入口脚本
 * ---------------------------------------------------------------------------
 * 由 boot.json 的 maplebirchAddon 参数 "script" 加载，加载时机在
 * 汉化 / 图包 / 框架 全部就绪之后（见 boot.json 的 ConflictChecker 声明）。
 *
 * 命名空间约定（务必遵守，见 README.md §3「命名空间预留」）：
 *   - 全局对象      : window.RobertNPC   （唯一自有全局量；注意不是 setup.RobertNPC）
 *   - 存档变量      : V.robert.*（剧情标记）、$robertTaxiDriver、$settings.robertAlwaysDriver
 *                     ⚠️ $options.robertTaxiChance 已废弃（需求改为作弊菜单里的开关 + 周二/周五规则）
 *   - 角色属性      : 直接写在 V.NPCName 的 Robert 对象上，用原版字段名 rage/lust/love/dom
 *   - 临时变量      : T.robertXxx / _robertXxx / _rbXxx
 *   - 段落名前缀    : Robert
 *   - widget 名前缀 : robert
 *   - CSS class     : robert-*
 *   - 翻译键前缀    : RobertNPC. 打头（例如 RobertNPC.intro.title）
 * 不要使用裸的 $robert / window.Robert / 无前缀段落名，避免与
 * 象牙怨灵 mod（Ivory Wraith / WraithsReflection）和
 * 哈珀 mod（ClaimableHarper）撞车。
 */

(function () {
	'use strict';

	// ---- 0. 前置检查 -------------------------------------------------------
	// 框架没起来就直接退出，避免抛异常污染其他 mod 的加载日志。
	if (typeof maplebirch === 'undefined' || !maplebirch) {
		console.error('[RobertNPC] maplebirch 框架未加载，模组跳过初始化。请确认框架已安装并排在本 mod 之前。');
		return;
	}

	// ---- 1. 建立全局命名空间 ----------------------------------------------
	window.RobertNPC ??= {};
	const RB = window.RobertNPC;

	RB.MOD_NAME = 'RobertNPC';
	RB.VERSION = '1.0.0';
	// 构建号：每次改动页面/作战逻辑时 +1，便于排查「跑的到底是哪一版」
	RB.BUILD = 20261001;

	/**
	 * 模组自己的日志器。前缀统一为 [RobertNPC]，
	 * 出问题时可以在 ModLoader 日志里直接过滤。
	 */
	RB.log = (function () {
		const base = typeof createlog === 'function' ? createlog('RobertNPC') : null;
		return function (msg, level, ...objs) {
			if (base) return base('[RobertNPC] ' + msg, level ?? 'INFO', ...objs);
			// eslint-disable-next-line no-console
			console.log('[RobertNPC]', msg, ...objs);
		};
	})();

	/**
	 * 取翻译。框架的 t() 在键不存在时会返回 `[key]`，这里统一降级为键名本身，
	 * 便于在界面上直接看出漏翻的条目。
	 */
	RB.t = function (key, space) {
		try {
			const text = maplebirch.t(key, space);
			return typeof text === 'string' && text.charAt(0) === '[' ? key : text;
		} catch (e) {
			RB.log(`翻译取值失败: ${key} - ${e?.message || e}`, 'WARN');
			return key;
		}
	};

	// ---- 2. 图片路径 -------------------------------------------------------
	// DoL 的图片一律以 img/ 开头，由 ImageLoaderHook 从 mod 的 zip 中取。
	//
	// 目前两张都是「新占位图片.png」（32×32）的副本，只是放在不同目录以便区分用途：
	//   img/npc/robert/占位图片.png  立绘占位
	//   img/占位图片.png             图标占位（出租车图标等）
	//
	// 换成正式素材时：改掉文件名，并同步 boot.json 的 imgFileList 与本处的 RB.IMG。
	RB.IMG = {
		portrait: 'img/npc/robert/占位图片.png',
		icon: 'img/占位图片.png'
	};

	/**
	 * 生成一个被 ImageLoaderHook 正确接管的 <img> 标签。
	 * 不要直接写 <img src="img/...">——除了 DoL 自己注入的标签，
	 * 只有经过 HTML 渲染管线的 img 才会被 ModLoader 拦下来换成 zip 里的图。
	 */
	RB.img = function (src, alt, cls) {
		return (
			`<img src="${src}" alt="${alt || ''}"` +
			(cls ? ` class="${cls}"` : '') +
			` style="max-width:100%;height:auto;">`
		);
	};

	// ---- 3. 角色数据 -------------------------------------------------------
	// 注意：nam 会被框架转成小写存进 V.maplebirch.npc.robert，
	// 同时也会成为 DoL 的 NPC 名。'Robert' 在原版里只是随机的路人名
	// （name-list.twee / pregnancy.js 的取名表），不是已存在的具名 NPC，
	// 因此不会与原版或其他 mod 的 NPC 冲突。
	RB.NPC_NAME = 'Robert';
	RB.NPC_NAME_CN = '罗伯特';
	/** 身份/职业名词（= NPC_DATA.title）。**不要**写成角色名，见下面的说明。 */
	RB.NPC_TITLE = 'taxi driver';
	/** 职业词的中文。同时写进 ModI18N 的职业词表，见 RB.ensureI18nNameFix。 */
	RB.NPC_TITLE_CN = '出租车司机';
	/** NPC_DATA.description 的中文（少数不走 title 的路径会用到）。 */
	RB.NPC_DESC_CN = '一个在孤儿院附近活动的年轻男人';

	RB.NPC_DATA = {
		nam: RB.NPC_NAME,
		gender: 'm',
		pronoun: 'm',
		/* ⚠️⚠️ `title` 是**身份/职业名词**，不是角色名！踩过的坑：
		      这里原来写 'Robert'，结果街头随机事件里出现
		      「你注意到一个路过的 **Robert** 偷偷看了一眼你的胸部。」
		      原因链：
		        <<personselect>>（base-system/text.twee:1909-1912）
		          具名 NPC 时 `$description to $NPCName[...].title`、`$npc_named to 1`
		        <<person>>（:1811-1812）
		          `<<if $npc_named is 1>><<set _text_output to $description>>`
		      于是 <<person>>（「一个路过的<<person>>」这类随机路人句）会**直接印出名字**。
		      原版具名 NPC 的 title 全是职业词：
		        Avery "businessman" / Eden "hunter" / Jordan "priest"
		        / Leighton "headmaster"
		      所以这里也必须是职业词，印出来才是
		      「一个路过的出租车司机……」。
		      角色名走 `nam`（= 'Robert'，由 <<robertName>> 显示），两者不要混。 */
		title: RB.NPC_TITLE,
		description: 'a young man who works near the orphanage',
		type: 'robert',
		adult: 1,
		teen: 0,
		age: 24,
		insecurity: 'none',
		chastity: {
			penis: 'normal',
			vagina: 'none',
			anus: 'normal'
		},
		virginity: {
			penis: false,
			vagina: false,
			anus: false
		},
		hair_side_type: 'straight',
		hair_fringe_type: 'straight',
		hair_position: 'short',
		hairlength: 200,
		eyeColour: 'brown',
		hairColour: 'brown',
		bottomsize: 3,
		skincolour: 1,
		init: 0,
		intro: 0,
		/* ⚠️⚠️ penis / vagina 是「衣物暴露状态」字段，合法值只有
		      "clothed" / 0 / "none"。
		      这里原来写的是 penis: 'human' —— 那是**错的**：
		      <<npcGenitals>>（base-system/text.twee:6109）判的是
		        `penis isnot "none" and vagina isnot "none"`
		      'human' 不等于 "none"，于是与 vagina（同样是 "none" 以外的值）
		      同时成立，正文就会印出「阴茎和阴道」两个器官（踩过）。
		      正确值由 setBodyTraits 按 gender 给：男性 = penis "clothed" /
		      vagina "none"。这里只补一个兜底，免得配置里再写错。
		      另见 modules/robert-gender.js 的 repairAnatomy。 */
		penis: 'clothed',
		penissize: 2,
		penisdesc: 'normal',
		vagina: 'none',
		breastsize: 0,
		breastdesc: 'none',
		ballssize: 2,
		outfits: ['naked'],
		pregnancyAvoidance: 50
	};

	// 角色的关系设定。
	//
	// important: true
	//   让框架把 "Robert" 推进 T.importantNpcOrder —— 也就是社交页面的
	//   「Primary Relationships（主要关系）」分组。
	//   注意：能不能显示出来**不取决于这个开关**，而取决于该 NPC 的 `init` 字段
	//   （原版 <<widget "relation-box">> 第一行就是 `<<if _npcData.init is 1>>`）。
	//   所以「初次遇到之前不显示」是靠 init 控制的，见 markMet()。
	//
	// loveInterest: true
	//   框架会做三件事（见 maplebirch inject_early.js 的 NamedNPC.setup）：
	//     1. 把 "Robert" 加进内部 type.loveInterestNpcs；
	//     2. 启动时执行 setup.loveInterestNpc = [...new Set([...原数组, ...loveInterestNpcs])]
	//        —— 是「合并去重」而不是整体重写，所以不会和象牙怨灵 / 哈珀的
	//        setup.loveInterestNpc 补丁互相覆盖；
	//     3. 把 "Robert" 自动加进 setup.NPCNameList / V.NPCNameList / C.npc，
	//        不需要自己改原版白名单。
	//
	// loveAlias: ['Robert', '罗伯特']
	//   框架会生成 setup.loveAlias.Robert = () => lanSwitch('Robert', '罗伯特')。
	//   ⚠️ 原版 <<widget "relation-box">> 里有一行 `setup.loveAlias[T.npcData.nam]()`，
	//      对没有别名的 NPC 会直接抛异常。本 mod 之所以必须写 loveAlias，
	//      就是为了让社交页面能安全渲染罗伯特这一格。
	//
	// romance: [ ... ]
	//   ⚠️ 必须显式写，而且必须写成「返回布尔的函数数组」。
	//
	//   坑 1：不要写 "romance": []。框架会用这个空数组覆盖默认条件，而
	//         [].every(...) === true，结果是 isPossibleLoveInterest('Robert')
	//         恒为 true，恋爱对象无条件解锁。
	//   坑 2：也不要省略。框架的默认条件是
	//         [() => (V.robertSeen ?? []).includes('romance')]，
	//         即依赖 robertSeen 这个数组 —— 它只有在本 mod 自己的代码往里
	//         写东西时才会存在。省略就等于「永远解锁不了」，而且不会报错。
	//
	//   下面这个条件不依赖任何可能不存在的变量，明确以「已认识 + 爱意达到 60」解锁。
	//   坑 3（实际踩到）：条件不要写成「爱意 ≥ 某值」。
	//         框架把 romance 数组存进 romanceConditions[nam]，
	//         而 isPossibleLoveInterest(nam) = 「数组里每个函数都返回真」。
	//         于是玩家只要把爱意练到 60，**在态度菜单里就能直接把罗伯特
	//         选成恋人** —— 表白事件还没发生、甚至还没见过面，
	//         关系却已经成立了。
	//
	//   正解：**把「已接受表白」当成唯一解锁条件**。
	//         表白事件（robert-ride-event.twee 的 Robert Ride Accept）
	//         会写 $robertRomance = true，所以关系只能由事件产生。
	//         爱意 66 的门槛留在 checkRide 里，那是**事件触发**条件，
	//         与「能不能在菜单里选」是两件事，不要混。
	RB.NPC_CONFIG = {
		love: {
			maxValue: 100
		},
		loveAlias: ['Robert', '罗伯特'],
		important: true,
		special: false,
		loveInterest: true,
		romance: [
			function () {
				return window.V?.robertRomance === true;
			}
		]
	};

	/**
	 * 旧存档修复：把「靠爱意刷出来的」恋人资格收回去。
	 *
	 * ⚠️ 老版本的条件是「爱意 ≥ 60」，玩家可能已经用它把罗伯特设成恋人
	 *    （甚至设成 $loveInterest.primary）。改条件不会自动撤销**已经写进存档**
	 *    的关系，所以这里主动清理：没接受过表白就把关系撤掉。
	 *    在 :passageinit 里调一次即可，幂等。
	 */
	RB.repairRomance = function () {
		if (V?.robertRomance === true) return false;      // 已经接受过表白，保留
		let changed = false;
		try {
			['primary', 'secondary', 'tertiary'].forEach((slot) => {
				if (V?.loveInterest?.[slot] === RB.NPC_NAME) {
					V.loveInterest[slot] = 'None';
					changed = true;
				}
			});
			if (changed) RB.log('已撤销未通过表白事件取得的恋人关系（旧存档修复）', 'WARN');
		} catch (e) {
			RB.log(`repairRomance 失败: ${e?.message || e}`, 'WARN');
		}
		return changed;
	};

	// ---- 3.05 名字 / 职业词的汉化接入 ---------------------------------------
	/* 症状：**罗伯特的名字在所有地方都显示成英文 "Robert"，而其他文字都是中文。**
	 *
	 * 原因链（都核对过源码）：
	 *   1. ModI18N 把原版里**所有** NPC 名字显示都改写成 setup.NPC_CN_NAME(...)，例如
	 *        · 遭遇正文：<<set _text_output to setup.NPC_CN_NAME($NPCList[$index].fullDescription)>>
	 *        · 状态提示宏：statDisplay.create("glust", npc =>
	 *              statDisplay.statChange(`${setup.NPC_CN_NAME(npc)}的性欲`, 1, "lewd"))
	 *          —— 所以 <<glust "Robert">> 会印出「Robert的性欲」
	 *        · 恋爱对象提示：<<= setup.NPC_CN_NAME($_LI)>>现在是你的恋爱对象了！
	 *        · 社交页面、童贞记录、怀孕记录……
	 *   2. ModI18N 自己的名字表（setup.NPCNameList_cn_name）里没有 Robert，
	 *      于是 setup.NPC_CN_NAME('Robert') **原样返回英文**。
	 *   3. 框架（maplebirch）给这个函数打过补丁（compatibleModI18N）：
	 *          setup.NPC_CN_NAME = t => { let n = 原实现(t);
	 *              return n !== t ? n : (lang.has(t) ? lang.auto(t) : t) }
	 *      也就是说：**只要框架语言表里存在「键名 === 英文原文」的条目**，
	 *      它就会接管、输出中文。缺的正是这一条。
	 *
	 * 所以本函数把三条平铺键写进框架语言表（translations/CN.json 里也有同样三条，
	 * 数据 + 运行期双保险）：
	 *      'Robert'                                  → '罗伯特'
	 *      'taxi driver'                             → '出租车司机'
	 *      'a young man who works near the orphanage' → 描述句中文
	 *
	 * 另有一条**不走 NPC_CN_NAME** 的路径 —— 职业词 $description：
	 *   ModI18N 把 `<<set _text_output to $description>>` 换成
	 *      (setup.NPCTitleList_cn_name.split('|').find(i => i.split(',')[0] === $description) || '')
	 *          .split(',')[1] || $description
	 *   即查 setup.NPCTitleList_cn_name 这个 "英文,中文|英文,中文" 串，**查不到就退回英文**。
	 *   所以这里把这个串补上 "taxi driver,出租车司机"（幂等）。
	 *   ⚠️ 这条只影响 $description 的显示；NPC_CN_TITLE() 走的是框架补丁那条路，
	 *      由上面的 'taxi driver' 键覆盖。
	 *
	 * ⚠️ 必须在 :passageinit 里调用：脚本顶层（params.script 阶段）SugarCube 还没启动，
	 *    setup 与框架语言表都可能还不存在。
	 * ⚠️ 幂等：先用 has() 查再 set()。lang.set() 内部会清 textCache，
	 *    所以不要每页无条件调用（has() 命中就直接跳过）。
	 *
	 * @returns {boolean} 是否有改动
	 */
	RB.ensureI18nNameFix = function () {
		let changed = false;

		/* 取中文名的顺序：翻译表 → 常量兜底。
		   这样 translations/CN.json 是唯一权威，改文案不用再改 JS 常量；
		   翻译表还没载入时（返回的是键名本身）才退回常量。 */
		const pick = (key, fallback) => {
			const text = RB.t(key);
			return typeof text === 'string' && text && text.indexOf('RobertNPC.') !== 0 ? text : fallback;
		};

		const pairs = [
			[RB.NPC_NAME, pick('RobertNPC.name', RB.NPC_NAME_CN)],
			[RB.NPC_TITLE, pick('RobertNPC.title', RB.NPC_TITLE_CN)],
			[RB.NPC_DATA.description, RB.NPC_DESC_CN]
		];

		try {
			const lang = window.maplebirch?.lang;
			if (!lang || typeof lang.set !== 'function' || typeof lang.has !== 'function') {
				RB.log('框架语言表不可用，名字汉化回退到 ModI18N（会显示英文名）', 'WARN');
			} else {
				for (const [en, cn] of pairs) {
					if (!en || !cn || lang.has(en)) continue;      // 已有条目：不覆盖
					if (lang.set(en, { EN: en, CN: cn })) {
						changed = true;
						RB.log(`已写入名字翻译: '${en}' → '${cn}'`);
					}
				}
			}
		} catch (e) {
			RB.log(`写入名字翻译失败: ${e?.message || e}`, 'WARN');
		}

		try {
			const entry = `${RB.NPC_TITLE},${pick('RobertNPC.title', RB.NPC_TITLE_CN)}`;
			if (typeof setup !== 'undefined' && setup && typeof setup.NPCTitleList_cn_name === 'string'
				&& !setup.NPCTitleList_cn_name.includes(entry)) {
				setup.NPCTitleList_cn_name += `|${entry}`;
				changed = true;
				RB.log(`已补充职业词翻译: ${entry}`);
			}
		} catch (e) {
			RB.log(`补充职业词翻译失败: ${e?.message || e}`, 'WARN');
		}

		return changed;
	};

	/**
	 * 名字解析状态 —— 供作弊菜单显示，一眼看出名字为什么是英文。
	 * 纯读取，不写任何东西。
	 * @returns {Array<{ok:boolean, text:string}>}
	 */
	RB.nameReport = function () {
		const out = [];
		const push = (ok, text) => out.push({ ok, text });
		let lang = '?';
		try {
			lang = window.maplebirch?.lang?.language ?? '?';
		} catch (e) { /* ignore */ }
		push(lang === 'CN', `框架语言：${lang}（名字/属性标签走这张表，不是 CN 就会是英文）`);

		let resolved = null;
		try {
			resolved = typeof setup !== 'undefined' && setup && typeof setup.NPC_CN_NAME === 'function'
				? setup.NPC_CN_NAME(RB.NPC_NAME) : null;
		} catch (e) { /* ignore */ }
		/* 判据用「不等于英文名」而不是「等于某个常量」：
		   中文名以 translations/*.json 为准，常量只是兜底，两者可以不同。 */
		push(Boolean(resolved) && resolved !== RB.NPC_NAME,
			`NPC_CN_NAME('${RB.NPC_NAME}') = ${resolved ?? '（不可用）'}`);

		let hasKey = false;
		try {
			hasKey = Boolean(window.maplebirch?.lang?.has?.(RB.NPC_NAME));
		} catch (e) { /* ignore */ }
		push(hasKey, `框架语言表里有 '${RB.NPC_NAME}' 这条键`);

		let titleOk = false;
		try {
			titleOk = typeof setup !== 'undefined' && setup
				&& typeof setup.NPCTitleList_cn_name === 'string'
				&& setup.NPCTitleList_cn_name.includes(RB.NPC_TITLE);
		} catch (e) { /* ignore */ }
		push(titleOk, `ModI18N 职业词表里有 '${RB.NPC_TITLE}'（$description 那条路用它）`);
		return out;
	};

	// ---- 3.1 角色属性 -------------------------------------------------------
	// 需求指定罗伯特的四个属性：怒气 / 性欲 / 爱意 / 支配。
	// 这四个都是原版就有的字段名（rage / lust / love / dom），
	// 正好对应原版 <<widget "relation-box">> 里 T.importantNpcStats 的前几项，
	// 所以不需要注册任何自定义统计项，直接用原版字段即可。
	//
	// 范围（与原版重要 NPC 一致，也留给未来剧情调整的空间）：
	//   love 0–100   lust 0–100   dom 0–100   rage 0–100
	RB.NPC_STATS = ['rage', 'lust', 'love', 'dom'];

	RB.STAT_LIMITS = {
		rage: [0, 100],
		lust: [0, 100],
		love: [0, 100],
		dom: [0, 100]
	};

	/** 属性名 → 中文显示名（社交页面里由原版皮肤显示英文名，这里供本 mod 自己的面板用） */
	RB.STAT_LABELS = {
		rage: 'RobertNPC.stat.rage',
		lust: 'RobertNPC.stat.lust',
		love: 'RobertNPC.stat.love',
		dom: 'RobertNPC.stat.dom'
	};

	/**
	 * 注册本 mod 的成就。
	 *
	 * ⚠️ 为什么放在 JS 而不是 Twee 段落里：
	 *    `setup.feats` 由 04-Variables/feats.js 建立。若写在 Twee 段落中，
	 *    该段落加载顺序一旦早于 feats.js，`setup.feats` 还是 undefined，
	 *    注册就会**静默失败**，之后 <<earnFeat>> 一调就抛异常。
	 *    放在 RB.init() 里并允许重试，才能保证游戏就绪后它一定存在。
	 *
	 * ⚠️ 必须先注册再授予：<<earnFeat>>（feats.js:2165）内部读
	 *    `setup.feats[featName]` 而**没有存在性判断**。
	 *
	 * ⚠️ 界面上显示的就是 title / desc（feats-ui.twee:120-121），
	 *    没有运行时翻译层，所以这里直接写中文。
	 */
	RB.FEAT_LOVER = '恋人罗伯特';
	RB.registerFeats = function () {
		if (typeof setup === 'undefined' || !setup || !setup.feats) return false;
		if (setup.feats[RB.FEAT_LOVER]) return true;      // 幂等

		setup.feats[RB.FEAT_LOVER] = {
			title: RB.FEAT_LOVER,
			desc: '把你的第一次交给对方。',
			/* difficulty / filter 照抄原版同类成就「Robin the Lover」
			   （feats.js:438-444）：同样是「把第一次给了某个恋爱对象」，
			   difficulty 2、归 Social 分类。 */
			difficulty: 2,
			series: '',
			filter: ['All', 'Social']
		};
		RB.log(`已注册成就「${RB.FEAT_LOVER}」`);
		return true;
	};

	/**
	 * 授予成就「恋人罗伯特」。
	 *
	 * 条件（需求）：**为罗伯特失去童贞**，且**先与罗伯特建立恋爱关系**。
	 *   · 童贞那一条由调用点保证 —— 本函数只被原版
	 *     <<awardVirginityFeat>>（base-combat/widgets.twee:120）在确认
	 *     失去童贞之后调到（由 boot.json 补丁 5 接进来）。
	 *   · 恋爱关系用 $robertRomance 判断：它只在表白事件【同意】那一页
	 *     被设为 true。**不要**改用「爱意 ≥ 某值」—— 那样刷爱意就能拿成就，
	 *     与「需要先建立恋爱关系」不符。
	 *
	 * ⚠️ earnFeat 有一串前置条件（feats.js:2166）：V.feats.locked /
	 *    V.cheatsEnabled / V.debug / V.gamemode "soft" / allureModifier < 1 /
	 *    V.statFreeze —— 命中任意一条就**静默不授予**。
	 *    开过作弊的存档拿不到成就是原版行为，不要试图绕过。
	 *
	 * 幂等：earnFeat 自己按 V.feats.currentSave 判重。
	 * @returns {boolean} 是否走到授予（不代表一定授予成功）
	 */
	RB.earnLoverFeat = function () {
		if (V?.robertRomance !== true) return false;
		RB.registerFeats();
		try {
			if (typeof earnFeat === 'function') {
				earnFeat(RB.FEAT_LOVER);
				return true;
			}
			RB.log('earnFeat 不可用，成就未授予', 'ERROR');
		} catch (e) {
			RB.log(`授予成就失败: ${e?.message || e}`, 'ERROR');
		}
		return false;
	};

	// ---- 4. 注册给框架 -----------------------------------------------------
	// 框架会在「处理 boot 配置」阶段（beforePatchModToGame）调用 npc.add()，
	// 这里只是提前登记。注册失败只警告，不抛异常，保证其他 mod 不受影响。
	RB.registerNPC = function () {
		// 框架的 npc 模块属于 meta.early，正常情况一定已挂载；
		// 这里仍然检查一次，避免框架版本差异导致整个 mod 抛异常。
		if (!maplebirch.npc || typeof maplebirch.npc.add !== 'function') {
			RB.log('maplebirch.npc 不可用，跳过 NPC 注册', 'ERROR');
			return false;
		}
		try {
			const ok = maplebirch.npc.add(RB.NPC_DATA, RB.NPC_CONFIG);
			RB.log(`NPC 注册${ok ? '成功' : '失败'}: ${RB.NPC_NAME}`, ok ? 'INFO' : 'ERROR');
			return ok;
		} catch (e) {
			RB.log(`NPC 注册异常: ${e?.message || e}`, 'ERROR');
			return false;
		}
	};

	// 关于「自定义状态值」：本 mod **不需要**注册任何自定义统计项。
	// 罗伯特的四个属性（怒气 / 性欲 / 爱意 / 支配）用的都是原版就有的字段名
	// rage / lust / love / dom，它们本来就存在于原版 baseNNPC 模板里，
	// 也在原版 <<widget "relation-box">> 的 T.importantNpcStats 里，
	// 所以社交页面会自动按原版样式渲染，不必调用 maplebirch.npc.addStats。
	//
	// （早期版本注册过 robertTrust / robertMood 两个自定义统计项，已废弃并改名 —— 见 README §8。）

	// ---- 4.1 NPC 数值读写 --------------------------------------------------
	// 这一步必须等到框架把 NPC 注入进 V.NPCName 之后才能做：
	// 框架的注入发生在它自己的 NPCManager.Init()（即游戏第一个 passage 时），
	// 也就是本脚本（afterRegisterMod2Addon 阶段）之后。
	//
	// ⚠️ 关于 <<npcincr>>：不要用它改罗伯特的数值。
	//    原版 `<<widget "npcincr">>` 里有一张硬编码白名单 _validNNPCNames
	//    （game/base-system/named-npcs.twee:1229），列表里没有 Robert，
	//    调用会直接抛 "NNPC 'Robert' is not whitelisted for use with <<npcincr>>"。
	//    把 Robert 加进那张表需要 TweeReplacer 补丁，而且哈珀 mod 已经在同一段
	//    文本上打过补丁（anchors 重叠 → 加载顺序一变就互相脱锚）。
	//    所以本 mod 改用下面这个 JS 接口，直接改 V.NPCName 里的对象，
	//    零补丁、零锚点、和其他 mod 完全无关。
	//
	//    代价：原版 <<relationshipclamp>>（widgets.twee）不会钳制这四个字段，
	//    所以钳制在 modules/robert-stats.js 里自己做（RB.STAT_LIMITS）。
	//    STAT_LIMITS / NPC_STATS / STAT_LABELS 都定义在上面第 3.1 节。

	/** 取 V.NPCName 里属于本 mod 的角色对象；还没注入时返回 null。 */
	RB.npcObject = function () {
		if (!Array.isArray(V.NPCName)) return null;
		return V.NPCName.find((n) => n && n.nam === RB.NPC_NAME) ?? null;
	};

	/**
	 * 读一个属性。直接读活数据；NPC 未注入时返回该属性的默认值。
	 * @param {string} key rage / lust / love / dom
	 */
	RB.npcStat = function (key) {
		const fallback = RB.STAT_DEFAULTS?.[key] ?? 0;
		const npc = RB.npcObject();
		if (!npc || npc[key] == null) return fallback;
		const n = Number(npc[key]);
		return Number.isFinite(n) ? n : fallback;
	};

	/**
	 * 写一个属性，按 STAT_LIMITS 钳制。
	 * @param {string} key
	 * @param {number} value
	 */
	RB.npcSetStat = function (key, value) {
		const num = Number(value);
		if (!Number.isFinite(num)) {
			RB.log(`npcSetStat(${key}) 收到非法数值: ${value}`, 'WARN');
			return false;
		}
		const range = RB.STAT_LIMITS[key] ?? [0, 100];
		const clamped = Math.max(range[0], Math.min(range[1], Math.round(num)));

		const npc = RB.npcObject();
		if (!npc) return false;
		npc[key] = clamped;
		return true;
	};

	/** 相对增减。 */
	RB.npcAddStat = function (key, delta) {
		return RB.npcSetStat(key, RB.npcStat(key) + Number(delta || 0));
	};

	// ---- 4.2 对外的统一入口 -------------------------------------------------
	// modules/robert-stats.js 里的 RB.getStat / RB.setStat / RB.addStat 负责
	// 「保护性钳制 + 中文显示」，对外是主入口。这里保留一层 npc* 别名，
	// 方便以后从别处直接操作活数据。调用方向固定为 stats -> framework（单向）。
	RB.applyStatToNpc = function (key, value) {
		return RB.npcSetStat(key, value);
	};

	RB.readStatFromNpc = function (key) {
		return RB.npcStat(key);
	};

	/**
	 * 幂等补齐模组 NPC 的四个属性字段（含旧存档）。
	 * 字段不存在或不是有限数字时，填成该属性的默认值并夹进合法范围。
	 * 调用点：每次 :passageinit（拿到 NPC 对象后才真正生效）。
	 * @returns {boolean} 是否找到了 NPC 对象
	 */
	RB.ensureNpcStats = function () {
		const npc = RB.npcObject();
		if (!npc) return false;
		let touched = false;
		for (const key of RB.NPC_STATS) {
			const range = RB.STAT_LIMITS[key] ?? [0, 100];
			let value = Number(npc[key]);
			if (npc[key] == null || !Number.isFinite(value)) {
				value = RB.STAT_DEFAULTS?.[key] ?? range[0];
			}
			value = Math.max(range[0], Math.min(range[1], Math.round(value)));
			if (npc[key] !== value) {
				npc[key] = value;
				touched = true;
			}
		}
		if (touched) RB.log('已补齐罗伯特的属性字段', 'DEBUG');
		return true;
	};

	// ---- 5. 模组初始化 -----------------------------------------------------
	// modules/ 下的文件已经注册了各自的 init，这里只负责按顺序调用。
	RB.init = function () {
		RB.log(`初始化开始 (v${RB.VERSION})`);

		RB.registerNPC();

		RobertNPC.initStats?.();
		RobertNPC.initSchedule?.();
		RobertNPC.initTaxi?.();
		RB.registerFeats();

		RB.log('初始化完成');
	};

	RB.init();

	// ---- 6. 对外接口 -------------------------------------------------------
	// 其他 mod 可以通过 modUtils.getMod('RobertNPC').modRef 拿到这个对象。
	try {
		const selfInfo = maplebirch.modUtils.getMod(RB.MOD_NAME);
		if (selfInfo) {
			selfInfo.modRef = {
				version: RB.VERSION,
				npcName: RB.NPC_NAME,
				img: RB.IMG,
				t: RB.t,
				log: RB.log
			};
		}
	} catch (e) {
		RB.log(`modRef 暴露失败: ${e?.message || e}`, 'WARN');
	}
})();
