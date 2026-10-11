/*
 * RobertNPC —— 出租车系统
 * ---------------------------------------------------------------------------
 * 被 framework.js 的 RB.init() 调用。
 *
 * 职责：决定每次搭乘时司机是不是罗伯特。
 *
 * 出现规则（按需求）：
 *   - 默认：**只在游戏内的周二 / 周五**可能出现，且这两天里概率 10%，
 *     陌生司机 90%。其余日期罗伯特**不会**出现（0%）。
 *   - 作弊开关（作弊菜单 → NPC 栏）打开后：罗伯特 100%、陌生司机 0%，
 *     且不再受星期限制。
 *
 * ⚠️ 星期用原版 Time.weekDay（time.js:338）：
 *    1 = 周日 … 7 = 周六，所以周二 = 3、周五 = 6。
 *
 * ⚠️ 旧的 $options.robertTaxiChance（0–90 的设置项）已废弃 ——
 *    需求要求删掉设置页里的调节项，改用作弊开关。
 *    这里不再读它，旧存档里残留的值会被忽略，不会报错。
 */

(function () {
	'use strict';

	if (typeof maplebirch === 'undefined' || !maplebirch) return;
	window.RobertNPC ??= {};
	const RB = window.RobertNPC;

	/** 出现规则常量。改这里就能调整日期与概率。 */
	RB.TAXI_RULE = {
		/** 可能出现罗伯特的星期（1=周日 … 7=周六） */
		weekDays: [3, 6],
		/** 在这些星期里出现的概率（%） */
		chance: 10
	};

	/**
	 * 作弊开关：罗伯特必定出现。
	 * 存在 $settings 下（与其它游戏设置同级，随存档保存），默认关闭。
	 * @returns {boolean}
	 */
	RB.alwaysRobert = function () {
		return V?.settings?.robertAlwaysDriver === true;
	};

	/** 今天是不是允许罗伯特出现的星期。作弊开关打开时恒为 true。 */
	RB.isRobertDay = function () {
		if (RB.alwaysRobert()) return true;
		let day;
		try {
			day = Time.weekDay;
		} catch (e) {
			// Time 不可用时按「不是罗伯特的日子」处理，宁可不出错也不刷人
			RB.log(`读取 Time.weekDay 失败: ${e?.message || e}`, 'WARN');
			return false;
		}
		return RB.TAXI_RULE.weekDays.includes(day);
	};

	/**
	 * 本次搭乘的司机判定。
	 * 单次掷骰；调用方负责保证一个段落只调一次。
	 * @returns {boolean} true = 司机是罗伯特
	 */
	RB.rollTaxiDriver = function () {
		if (RB.alwaysRobert()) {
			RB.log('出租车司机判定: 作弊开关开启 → 罗伯特（100%）', 'DEBUG');
			return true;
		}
		if (!RB.isRobertDay()) {
			RB.log(`出租车司机判定: 今天（weekDay=${Time?.weekDay}）不是罗伯特的日子 → 陌生司机`, 'DEBUG');
			return false;
		}
		const chance = RB.TAXI_RULE.chance;
		// random() 是 DoL / SugarCube 的全局函数，走 State.random，可被存档回放正确还原
		const roll = random(1, 100);
		const isRobert = roll <= chance;
		RB.log(`出租车司机判定: 掷出 ${roll} / 阈值 ${chance} → ${isRobert ? '罗伯特' : '陌生司机'}`, 'DEBUG');
		return isRobert;
	};

	/** 供界面显示的规则说明（作弊菜单与调试用）。走翻译键，便于汉化/英文化。 */
	RB.taxiRuleText = function () {
		const key = RB.alwaysRobert() ? 'RobertNPC.taxi.ruleAlways' : 'RobertNPC.taxi.ruleDefault';
		const text = RB.t ? RB.t(key) : key;
		// RB.t 在键缺失时会原样返回键名，那种情况下退回中文默认值，避免界面出现键名
		if (text === key) {
			return RB.alwaysRobert()
				? `罗伯特出现概率 100%，陌生司机 0%`
				: `罗伯特只在周二与周五出现，出现概率 ${RB.TAXI_RULE.chance}%，陌生司机 ${100 - RB.TAXI_RULE.chance}%`;
		}
		return text;
	};

	RB.initTaxi = function () {
		RB.log(`出租车系统就绪：${RB.taxiRuleText()}`);
	};

	/**
	 * 出租车司机判定的实时状态 —— 供作弊菜单显示。
	 *
	 * ⚠️ 纯读取，**不掷骰**，可以随便调。
	 *    用途：检查「总是出现」开关到底有没有生效。
	 *    踩过的坑：开关写法看着没问题但实际没写进去 / 读的地方不一致，
	 *    没有这个面板就只能靠猜。
	 * @returns {Array<{ok:boolean, text:string}>}
	 */
	RB.taxiGateReport = function () {
		const R = RB.TAXI_RULE;
		const out = [];
		const push = (ok, text) => out.push({ ok, text });

		const flag = V?.settings?.robertAlwaysDriver;
		const always = RB.alwaysRobert();
		push(always, `「总是出现」开关：${always ? '已开启（罗伯特 100%）' : '未开启'}（存档里的值 = ${JSON.stringify(flag)}）`);

		let day = null;
		try { day = Time.weekDay; } catch (e) { /* ignore */ }
		const isDay = RB.isRobertDay();
		push(isDay, `星期 ${day ?? '?'}（1=周日…7=周六）／ 罗伯特的日子：${R.weekDays.join('、')}${always ? '（开关开启，忽略星期）' : ''}`);

		out.push({
			ok: true,
			text: always
				? '结论：每次打车都是罗伯特'
				: `结论：只有 ${R.weekDays.join('、')} 且掷点 ≤ ${R.chance} 才是罗伯特`
		});
		return out;
	};
})();
