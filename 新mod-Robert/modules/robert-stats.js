/*
 * RobertNPC —— 属性模块
 * ---------------------------------------------------------------------------
 * 被 framework.js 的 RB.init() 调用。
 *
 * 罗伯特的四个属性（需求指定，全部使用**原版就有的字段名**）：
 *
 *   | 字段   | 中文   | 范围    | 说明                                     |
 *   | :----- | :----- | :------ | :--------------------------------------- |
 *   | rage   | 怒气   | 0–100   | 原版 rage，显示图标 img/ui/sym-rage.png  |
 *   | lust   | 性欲   | 0–100   | 原版 lust                                |
 *   | love   | 爱意   | 0–100   | 原版 love，社交页面标题用 loveAlias      |
 *   | dom    | 支配   | 0–100   | 原版 dom                                 |
 *
 * 「原版就有」意味着不需要注册任何自定义统计项 —— 这四个字段本来就存在于
 * setup.baseNNPC 模板，也是原版 <<widget "relation-box">> 的 T.importantNpcStats
 * 前四项，所以社交页面会自动按原版样式渲染，不用自己做 UI。
 *
 * 数据存放：
 *   活数据   V.NPCName 里 nam === "Robert" 的对象上的上述四个字段。
 *            这是唯一权威来源，社交页面读的就是它。
 *   镜像     V.robert.* 只存剧情标记（met / relation），**不再镜像四个属性** ——
 *            避免两处数据不同步。取不到 NPC 对象时统一返回默认值。
 *
 * ⚠️ 不要用原版 <<npcincr>> 改罗伯特的属性 —— 原版白名单里没有 Robert，
 *    会直接抛错。原因与替代方案见 framework.js 第 4.1 节的注释。
 */

(function () {
	'use strict';

	if (typeof maplebirch === 'undefined' || !maplebirch) return;
	window.RobertNPC ??= {};
	const RB = window.RobertNPC;

	/** 属性名清单。顺序即社交页面里的显示顺序。 */
	RB.STATS = ['rage', 'lust', 'love', 'dom'];

	/** 新角色的初始值。 */
	RB.STAT_DEFAULTS = {
		rage: 0,
		lust: 0,
		love: 0,
		dom: 0
	};

	/**
	 * 确保 V.robert 与相关设置项存在。
	 * 旧存档第一次装 mod 时也需要，所以每次读写前都调。
	 * 这里只放**剧情标记**，四个属性不放这里（见文件头说明）。
	 */
	RB.ensureVars = function () {
		V.robert ??= {};
		V.robert.met ??= 0; // 是否已初次相遇（控制社交页面是否显示 + 出租车剧情分支）
		V.robert.relation ??= 0; // 关系阶段占位，留给后续剧情

		// 出租车设置项：旧存档里没有这个键，补上默认值。
		// 界面上的 <<numberStepper>> 也有 `?? 50` 兜底，这里是双保险，
		// 让不打开设置界面的玩家也用上正确默认值。
		if (V.options) {
			V.options.robertTaxiChance ??= RB.TAXI_CHANCE?.default ?? 50;
		}

		return V.robert;
	};

	/**
	 * 读取一个属性。
	 * @param {string} key rage / lust / love / dom
	 * @returns {number}
	 */
	RB.getStat = function (key) {
		if (!RB.STATS.includes(key)) {
			RB.log(`未知属性: ${key}`, 'WARN');
			return 0;
		}

		const fallback = RB.STAT_DEFAULTS[key] ?? 0;

		try {
			const npc = RB.npcObject?.();
			if (npc) {
				const n = Number(npc[key]);
				// 用 == null 同时覆盖 undefined 与 null
				if (npc[key] != null && Number.isFinite(n)) return n;
			}
		} catch (e) {
			RB.log(`读取 ${key} 失败，返回默认值: ${e?.message || e}`, 'DEBUG');
		}

		return fallback;
	};

	/**
	 * 写入一个属性。按 RB.STAT_LIMITS 钳制，防止越界数值把社交页面搞坏。
	 * @param {string} key
	 * @param {number} value
	 * @returns {boolean} 是否写入成功
	 */
	RB.setStat = function (key, value) {
		if (!RB.STATS.includes(key)) {
			RB.log(`未知属性: ${key}`, 'WARN');
			return false;
		}

		const num = Number(value);
		if (!Number.isFinite(num)) {
			RB.log(`属性 ${key} 收到非法数值: ${value}`, 'WARN');
			return false;
		}

		const range = RB.STAT_LIMITS?.[key] ?? [0, 100];
		const clamped = Math.max(range[0], Math.min(range[1], Math.round(num)));

		const npc = RB.npcObject?.();
		if (!npc) {
			// NPC 还没被框架注入（标题画面 / 旧存档首次进入）。
			// 不报错、不缓存 —— 等 :passageinit 拿到对象后由 ensureNpcStats 补齐。
			RB.log(`属性 ${key} 暂未写入：NPC 尚未注入`, 'DEBUG');
			return false;
		}

		npc[key] = clamped;
		RB.log(`属性更新: ${key} = ${clamped}`, 'DEBUG');
		return true;
	};

	/**
	 * 增减一个属性。
	 * @param {string} key
	 * @param {number} delta
	 */
	RB.addStat = function (key, delta) {
		return RB.setStat(key, RB.getStat(key) + Number(delta || 0));
	};

	/** 取属性的中文显示名。翻译键走框架语言系统。 */
	RB.statLabel = function (key) {
		return RB.t(RB.STAT_LABELS?.[key] ?? key);
	};

	/**
	 * 提示宏用的标签，形如「罗伯特的怒气」（EN: Robert's Rage）。
	 *
	 * ⚠️ 为什么需要它：原版 / ModI18N 的属性提示宏（<<glust "Robert">> 等）
	 *    自己会拼「<名字>的<属性>」，但**怒气没有原版宏**，本 mod 自建的
	 *    <<grage>> / <<lrage>> 第一版把标签硬编码成了 "Rage" ——
	 *    结果中文界面里只这一个提示块是英文（截图里那个「+ Rage」）。
	 *    这里按同一形状拼，且名字与属性名都走本 mod 的翻译表，
	 *    中英两种语言都正确。
	 *
	 * @param {string} key rage / lust / love / dom
	 * @returns {string}
	 */
	RB.chipLabel = function (key) {
		const name = RB.t('RobertNPC.name');
		const of = RB.t('RobertNPC.chip.of');
		return `${name}${of}${RB.statLabel(key)}`;
	};

	/** 供 twee 显示用的文本，例如「怒气: 0/100」。 */
	RB.statText = function (key) {
		const range = RB.STAT_LIMITS?.[key] ?? [0, 100];
		return `${RB.statLabel(key)}: ${RB.getStat(key)}/${range[1]}`;
	};

	/** 生成一个进度条 HTML（外观由 robert-style.css 控制）。 */
	RB.statBar = function (key) {
		const range = RB.STAT_LIMITS?.[key] ?? [0, 100];
		const value = RB.getStat(key);
		const pct = Math.max(0, Math.min(100, Math.round((100 * (value - range[0])) / (range[1] - range[0]))));
		return (
			`<div class="robert-statbar robert-statbar-${key}">` +
			`<span class="robert-statbar-label">${RB.statLabel(key)}</span>` +
			`<span class="robert-statbar-track"><span class="robert-statbar-fill" style="width:${pct}%;"></span></span>` +
			`<span class="robert-statbar-value">${value}</span>` +
			`</div>`
		);
	};

	/** 四个属性的一组进度条，给 <<robertStatusPanel>> 用。 */
	RB.statBars = function () {
		return RB.STATS.map((k) => RB.statBar(k)).join('');
	};

	/**
	 * 「再乘」时爱意的增量。
	 *
	 * 需求：初见不加爱意；后续剧情把爱意推到 **大于 30** 之后，
	 * 「再乘」（再次搭乘出租车）时爱意改为 +2，否则 +1。
	 *
	 * ⚠️ 门槛只在这里定义一处，所有需要发爱意的地方都调这个函数，
	 *    避免以后调整数值时漏改。
	 * @returns {number} 1 或 2
	 */
	RB.LOVE_BOOST_THRESHOLD = 30;

	RB.loveGain = function () {
		return RB.getStat('love') > RB.LOVE_BOOST_THRESHOLD ? 2 : 1;
	};

	/**
	 * 性奋的原始值换算系数。
	 *
	 * 原版 `<<arousal N>>` 里 N 是**原始值**，$arousalmax = 10000。
	 * 直接写 `<<arousal 10>>` 只加 0.1%，侧边栏完全看不出变化。
	 * 玩家（和需求）说的「点」是 0–100 的尺度，所以 1 点 = 100 原始值。
	 * 乘完之后 +10 = 1000 原始值，正好落在原版「强烈」档（1000–2000）。
	 *
	 * ⚠️ `<<stress N>>` 不需要这个系数：它内部已经乘了 40，
	 *    `<<stress 10>>` 就是 400 原始值（玩家视角的 10 点）。
	 *    这两个宏的尺度不一样，不要混。
	 */
	RB.AROUSAL_SCALE = 100;

	// ---- 淫乱判定的等级与效果文本 -----------------------------------------
	// 阈值来自原版 hasSexStat（ingame.js:1518-1544）：1 级 ≥1、2 级 ≥15、3 级 ≥35。
	//
	// ⚠️ 0 级与 1 级是**同一个判定**：
	//    原版 hasSexStat 的注释明确写着 1 级只用来判断「是否大于 0」，
	//    1 级动作本来就应当始终可用。所以游戏里 0 级也按 1 级的效果处理、
	//    显示上也统一写作「淫乱 1级」，不显示「淫乱 0级」。
	//
	// 需求规定的效果（换算成 0–100 的「点」）：
	//   0 / 1 级   → 压力 +10、性奋 +10
	//   2 级       → 性奋 +20（不加压力）
	//   3 级及以上 → 性奋 +30（不加压力）
	RB.PROMISCUITY_LEVELS = [
		{ level: 3, min: 35 },
		{ level: 2, min: 15 },
		{ level: 1, min: 1 }
	];

	/**
	 * 当前淫乱等级（0–3）。0 级与 1 级的**判定效果相同**，
	 * 需要区分的只有 2 级和 3 级。
	 */
	RB.promiscuityLevel = function () {
		for (const item of RB.PROMISCUITY_LEVELS) {
			if (RB.hasPromiscuity(item.level)) return item.level;
		}
		return 0;
	};

	/** 是否达到指定淫乱等级（用原版 hasSexStat，含醉酒/发情等修正）。 */
	RB.hasPromiscuity = function (level) {
		try {
			// hasSexStat 是原版全局函数（game/03-JavaScript/ingame.js）
			return Boolean(hasSexStat('promiscuity', level));
		} catch (e) {
			RB.log(`hasSexStat 调用失败，按未达标处理: ${e?.message || e}`, 'DEBUG');
			return false;
		}
	};

	/**
	 * 淫乱判定效果的**纯文本**提示，拼在选项名后面。
	 * 输出形如： ｜+性奋｜+压力｜淫乱 1
	 *
	 * ⚠️ 必须是纯文本：这段文字会被拼进 <<link>> 的链标，
	 *    而 DoL 的 link 宏对链标取 .textContent，HTML 标记会被剥掉。
	 *    详见 robert-tweak.twee 顶部的说明。
	 *
	 * 分隔符用全角「｜」，即使标记被剥离也不会和其他文字粘连。
	 *
	 * 等级规则（0 级与 1 级同判定）：
	 *   0 / 1 级   → +性奋｜+压力｜淫乱 1
	 *   2 级       → +性奋｜淫乱 2        （不加压力）
	 *   3 级及以上 → +性奋｜淫乱 3        （不加压力）
	 *
	 * ⚠️ 罗伯特的性欲（lust）**不**在这里显示：本判定不改它，
	 *    只在事件收尾时结算。提示里出现它会误导玩家。
	 * @returns {string}
	 */
	RB.lewdEffectShort = function () {
		const level = RB.promiscuityLevel();
		const sep = RB.t('RobertNPC.stat.sep');
		const parts = ['+' + RB.t('RobertNPC.stat.short.arousal')];
		if (level <= 1) parts.push('+' + RB.t('RobertNPC.stat.short.stress'));
		parts.push(RB.t('RobertNPC.stat.promiscuity') + ' ' + Math.max(1, level));
		return sep + parts.join(sep);
	};

	/**
	 * 当前淫乱判定的**效果标记**。
	 *
	 * 返回一组标记而不是成品文本，便于渲染端决定样式。
	 * 标记顺序 = 显示顺序，空白分隔。
	 *
	 * ⚠️ 这些标记是「行内协议」：改名字必须同步改渲染端。
	 * @returns {string}
	 */
	RB.lewdEffectTokens = function () {
		const level = RB.promiscuityLevel();
		const tokens = [];
		if (level <= 1) tokens.push('stress');
		tokens.push('arousal');
		return tokens.join(' ');
	};

	/**
	 * 显示用的淫乱等级。0 级按 1 级显示 —— 因为两者判定与效果完全一致，
	 * 游戏里不存在「淫乱 0级」这种说法。
	 */
	RB.promiscuityDisplayLevel = function () {
		return Math.max(1, RB.promiscuityLevel());
	};

	RB.initStats = function () {
		RB.ensureVars();
		RB.log(`属性模块就绪：${RB.STATS.join(' / ')}`);
	};

	// ---- 时机处理 ---------------------------------------------------------
	// 这里不用 :storyready 初始化存档变量：
	// :storyready 是「游戏引擎就绪」，此时还停留在标题画面，存档变量 V 尚未载入，
	// 在那一刻写 V.robert 要么无效、要么之后被读档覆盖。
	//
	// 正确做法：
	//   :passageinit  每次进入段落都补齐（幂等）。此时 V 已载入，若还没开局，
	//                 框架也没注入 NPC，ensureNpcStats 会安静地返回 false，不会报错。
	$(document).on(':passageinit', function () {
		try {
			RB.ensureVars();
			RB.ensureNpcStats?.();
			/* 旧存档自愈（都幂等，没坏就不动）：
			   · repairAnatomy —— penis/vagina/chest 若被写成 'human'
			     之类非法值，正文会同时印出阴茎和阴道
			   · repairRomance —— 老版本用「爱意 ≥ 60」解锁恋人资格，
			     玩家可能已经据此建立了关系；没接受过表白就撤掉 */
			RB.repairAnatomy?.();
			RB.repairRomance?.();
			/* title 若是角色名（'Robert'）会让随机路人句印出名字，
			   而 title 只在注册时从 NPC_DATA 抄一次、之后存进存档，
			   所以旧存档必须靠这里修。见 repairTitle。 */
			RB.repairTitle?.();
			/* 名字 / 职业词的汉化接入（ModI18N 的 NPC_CN_NAME 不认新 NPC）。
			   不补这一环，游戏里**所有** NPC 名字显示都会是英文 "Robert"
			   —— 战斗正文、<<glust "Robert">> 这类提示宏、恋爱提示、社交页面全都算。
			   幂等：内部先 has() 查再 set()。见 framework.js 的 ensureI18nNameFix。 */
			RB.ensureI18nNameFix?.();
			/* 把本事件的段落登记进 $map.available —— 不登记的话
			   <<map>>（widgets.twee:2848）会在事件页上抛 TypeError。
			   必须在段落正文渲染**之前**就有，所以放在这里而不是事件页里。
			   详见 modules/robert-ride.js 的 ensureMapEntries。 */
			RB.ensureMapEntries?.();
			/* 成就注册兜底：正常在 RB.init() 里已注册过。这里再试一次，
			   是为了应付「feats.js 比本 mod 晚加载」的情况 ——
			   那时 init 里的注册会因为 setup.feats 还不存在而跳过。
			   ⚠️ 必须在任何 <<earnFeat>> 之前注册好，因为 earnFeat
			      读 setup.feats[键] 时没有存在性判断。幂等。 */
			RB.registerFeats?.();
		} catch (e) {
			RB.log(`:passageinit 初始化失败: ${e?.message || e}`, 'ERROR');
		}
	});

	$(document).one(':storyready', function () {
		RB.log('游戏引擎就绪（此时还没有存档变量，属性将在进入首个段落时补齐）');
	});
})();
