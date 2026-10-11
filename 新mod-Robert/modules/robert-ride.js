/**
 * RobertNPC —— 表白事件（牛津街）
 * ===========================================================================
 * 被 framework.js 的 RB.init() 调用。
 *
 * 出现条件（全部满足才可能触发）：
 *   1. 罗伯特的爱意 ≥ 66
 *   2. 游戏内周一–周五（Time.weekDay 2–6；1=周日、7=周六）
 *   3. 时间 09:00–19:59（即上午 9 点到下午 8 点之间）
 *   4. 玩家在**牛津街**（由 <<robertoffersride>> 只在 Oxford Street 段落里调用保证）
 *   5. 不在「我再考虑考虑」之后的 10 天冷却里
 *   6. 概率掷点通过
 *
 * ⚠️ 时间上限写 `lt 20`（不含 20 点）而不是 `lte 20`：
 *    需求是「上午9点-下午8点」，20:00 已经不在区间内。
 *    艾弗里的写法也是这个形状（named-npc.js:199 `Time.hour >= 8 && Time.hour < 10`）。
 *
 * ⚠️ 概率「每个时段只掷一次」：掷失败了也记 RESULT_NO，否则玩家反复
 *    重进牛津街可以无限重掷，等于把概率刷到 100%。
 *    用 $robertRideChecked 记「本时段已判定过」（按时段键控）。
 *
 * 冷却用「游戏内日期」而不是时段计数：需求是「10 天内不再出现」，
 * 日期差最直观，也不受玩家睡多久影响。
 */

(function () {
	'use strict';

	if (typeof maplebirch === 'undefined' || !maplebirch) return;
	window.RobertNPC ??= {};
	const RB = window.RobertNPC;

	/** 触发规则的常量。改这里就能调整门槛。 */
	RB.RIDE = {
		/** 爱意门槛（%） */
		loveMin: 66,
		/** 允许的星期（1=周日 … 7=周六）→ 周一–周五 */
		weekDays: [2, 3, 4, 5, 6],
		/** 允许的小时区间 [起, 止)，即 09:00–19:59 */
		hourFrom: 9,
		hourTo: 20,
		/** 冷却天数（选【我再考虑考虑】之后） */
		cooldownDays: 10,
		/** 满足其余条件时，每个时段出现的概率（%） */
		chance: 25
	};

	/** 判定结果（存在 T 上，不写入存档） */
	RB.RIDE_RESULT = {
		YES: 'yes',
		NO: 'no',
		/** 本时段已判定过但没中 —— 不再重掷 */
		ROLLED: 'rolled'
	};

	/** 本时段的键（年-月-日-小时），用于「每时段只掷一次」。 */
	RB.rideSlotKey = function () {
		try {
			return `${Time.year}-${Time.month}-${Time.monthDay}-${Time.hour}`;
		} catch (e) {
			return '';
		}
	};

	/** 冷却是否已经过去。没有冷却记录时视为已过去。 */
	RB.rideCooldownOver = function () {
		const until = V?.robertRideCooldownUntil;
		if (!until || typeof until !== 'object') return true;
		try {
			const now = Time.year * 10000 + Time.month * 100 + Time.monthDay;
			const tgt = Number(until.year) * 10000 + Number(until.month) * 100 + Number(until.day);
			return now >= tgt;
		} catch (e) {
			RB.log(`冷却判定失败，按已过去处理: ${e?.message || e}`, 'WARN');
			return true;
		}
	};

	/** 本事件的段落名 —— 必须预先登记进 $map.available，见 ensureMapEntries。 */
	RB.RIDE_PASSAGES = ['Robert Ride 1', 'Robert Ride Accept', 'Robert Ride Refuse'];

	/**
	 * 把本事件的段落登记进 $map.available。
	 *
	 * ⚠️⚠️ 这一条是「地图报错」的真正修法，别再想着用 $passageOverride 绕过：
	 *
	 *    <<map>>（base-system/widgets.twee:2848）读的是
	 *        `$map.available[$passage].includes($map.arrayList[_i])`
	 *    $map.available 由 mapLocations.twee 建立，**只包含原版地名**。
	 *    本事件的段落名不在里面 → $map.available["Robert Ride 1"] 是
	 *    undefined → `.includes` 抛 TypeError，滚 17 次（就是那 17 条
	 *    `bad evaluation`）。
	 *
	 *    为什么 $passageOverride 救不了：
	 *      牛津街正文第 263 行就调了 <<map "oxford">>，那时我的钩子
	 *      （第 70 行插入）还没跑；等 <<goto>> 把 Robert Ride 1 拉起来时，
	 *      PassageHeader 已经把 $passage 设成 "Robert Ride 1"，
	 *      而我在正文里设的 $passageOverride 是**那之后**才生效的 —— 来不及。
	 *
	 *      ⚠️ 跳转用的是 <<goto "Robert Ride 1">>（= 停掉本段落剩余渲染 +
	 *      setTimeout 后再 Engine.play），**不是**直接 <<run Engine.play(...)>>；
	 *      后者会在牛津街还没渲染完时就把目标页渲染出来，随后被牛津街的输出
	 *      整页覆盖 —— 症状是「事件触发后整页空白」。详见 robert-ride-event.twee。
	 *
	 *    正解：**提前**把段落名登记进去（空数组 = 从这些页面不能在地图上移动，
	 *    正合本意）。在 :passageinit 里每次跑一遍，幂等且开销可忽略。
	 *
	 * @returns {boolean} 是否有改动
	 */
	RB.ensureMapEntries = function () {
		try {
			V.map = V.map ?? {};
			/* ⚠️ 不能在这里就把 available 建成 {} —— 那会把原版地名全抹掉。
			    原版地图还没建好时（开局前）先记个待办，等它建好再补。 */
			if (typeof V.map.available !== 'object' || V.map.available === null) {
				V.robertMapEntriesPending = true;
				return false;
			}
			let changed = false;
			RB.RIDE_PASSAGES.forEach((name) => {
				if (!Array.isArray(V.map.available[name])) {
					V.map.available[name] = [];
					changed = true;
				}
			});
			/* 兜底：万一 $passage 解析成空串，也让它有个数组可用 */
			if (!Array.isArray(V.map.available[''])) {
				V.map.available[''] = [];
				changed = true;
			}
			if (changed) {
				V.robertMapEntriesPending = false;
				RB.log(`已登记地图条目：${RB.RIDE_PASSAGES.join('、')}`);
			}
			return changed;
		} catch (e) {
			RB.log(`ensureMapEntries 失败: ${e?.message || e}`, 'WARN');
			return false;
		}
	};

	/**
	 * 玩家是不是正站在牛津街。
	 *
	 * 判据是 $passage，但**必须配合事件页里的 $passageOverride**：
	 * 事件是通过 <<goto "Robert Ride 1">>（内部 setTimeout + Engine.play）
	 * 从牛津街拉起来的，那一页 $passage 解析不出正确值
	 * （实测为空），同时还会让 <<map>> 抛 TypeError。
	 * 事件页的 <<robertRideScene>> 会把 $passageOverride 设成
	 * "Oxford Street"（原版 PassageHeader 第 5 行就是用它的），
	 * 于是本函数在两处都拿到正确值。
	 * 详见 robert-ride-event.twee 里 robertRideScene 的说明。
	 */
	RB.isOnOxfordStreet = function () {
		try {
			return $passage === 'Oxford Street';
		} catch (e) {
			return false;
		}
	};

	/**
	 * 逐条列出触发条件是否满足 —— 供作弊菜单显示。
	 *
	 * ⚠️ 这个函数**不掷点、不写存档**（纯读取），可以随便调。
	 *    之所以要做它：事件「没出现」可能是好几个条件里任意一个不满足，
	 *    盲猜没有意义，直接把状态摊开看。
	 * @returns {Array<{ok:boolean, text:string}>}
	 */
	RB.rideGateReport = function () {
		const R = RB.RIDE;
		const out = [];
		const push = (ok, text) => out.push({ ok, text });

		let day = null, hour = null, slot = '';
		try {
			day = Time.weekDay;
			hour = Time.hour;
			slot = RB.rideSlotKey();
		} catch (e) { /* Time 不可用，下面按不满足处理 */ }

		const love = RB.npcStat?.('love') ?? 0;
		push(love >= R.loveMin, `爱意 ${love} / 需要 ≥ ${R.loveMin}`);
		push(day !== null && R.weekDays.includes(day),
			`星期 ${day ?? '?'}（1=周日…7=周六）/ 需要 周一–周五`);
		push(hour !== null && hour >= R.hourFrom && hour < R.hourTo,
			`时间 ${hour ?? '?'} 点 / 需要 ${R.hourFrom}–${R.hourTo - 1} 点`);
		const cdOk = RB.rideCooldownOver();
		const until = V?.robertRideCooldownUntil;
		push(cdOk, `冷却 ${cdOk ? '已过' : `至 ${until?.year}-${until?.month}-${until?.day}`}`);
		const rolled = V.robertRideChecked === slot;
		push(!rolled, `本时段(${slot})${rolled ? '已判定过，需过一小时再来' : '尚未判定'}`);

		/* 地点：$passage 现在靠事件页的 $passageOverride 兜住了，
		   所以在事件里也能拿到正确值。 */
		let passage = '?';
		try { passage = $passage; } catch (e) { /* ignore */ }
		push(RB.isOnOxfordStreet(),
			`当前地点「${passage}」—— 事件只在「Oxford Street」触发`);

		/* 关键诊断：补丁到底有没有生效。
		   在牛津街走一圈后这里应该 >0；一直是 0 就说明
		   <<robertoffersride>> 根本没被调用（补丁没插进去或位置在 if 链里）。 */
		const hooked = V.robertRideHookCount ?? 0;
		push(hooked > 0,
			`事件钩子已被调用 ${hooked} 次${hooked > 0 ? '' : '（从未调用过 → 补丁没生效）'}`);

		/* 本次页面是否已经被普通街边事件占用 */
		const skip = V.eventskip === 1;
		push(!skip, `本次页面${skip ? '已被普通街边事件占用，下次再来' : '未被占用'}`);

		out.push({ ok: true, text: `概率 ${R.chance}%（满足上面全部条件后每时段掷一次）` });
		return out;
	};

	/**
	 * 把「当前日期 + N 天」记成冷却目标。
	 * 用原版 DateTime 做日期加法（不要手算月份天数）。
	 */
	RB.setRideCooldown = function (days) {
		try {
			const t = new window.DateTime(Time.date);
			t.addDays(days);
			V.robertRideCooldownUntil = { year: t.year, month: t.month, day: t.day };
			RB.log(`已设置表白事件冷却至 ${t.year}-${t.month}-${t.day}`);
		} catch (e) {
			RB.log(`设置冷却失败: ${e?.message || e}`, 'ERROR');
		}
	};

	/**
	 * 核心判定。只在牛津街段落里调用。
	 * @returns {string} RB.RIDE_RESULT 里的值
	 */
	RB.checkRide = function () {
		const R = RB.RIDE;

		/* ⚠️ 留痕：证明 <<robertoffersride>> **确实被调用过**。
		   补丁没插进去 / 段落名不对时，这个计数永远是 0 ——
		   有了它才能一眼区分「补丁没生效」和「概率没中」，
		   不用靠猜（踩过：地点没查导致诊断面板在别处也全绿）。 */
		V.robertRideHookCount = (V.robertRideHookCount ?? 0) + 1;

		/* ⚠️ $eventskip 是原版的「本次已经出过事件了」标记：
		   <<streeteffects>> 出过事件就会置 1，段落末尾（oxford.twee:267）
		   再清回 0。本事件压在 <<streeteffects>> 后面，所以要先看它 ——
		   不然同一个页面会连出两个事件。
		   ⚠️ 注意这一条**只跳过本次**，不影响 $robertRideChecked：
		      下次进牛津街（$eventskip 已清 0）还会正常判定。 */
		if (V.eventskip === 1) return RB.RIDE_RESULT.NO;

		/* ⚠️ 已经成为恋人之后**不再触发**本事件。
		   表白只发生一次 —— 否则每次进牛津街都可能被「表白」一遍。
		   判据用 $robertRomance，它只在【同意】那一页被设为 true，
		   与 framework.js 里 romance 的解锁条件是同一个标记。 */
		if (V.robertRomance === true) return RB.RIDE_RESULT.NO;

		if ((RB.npcStat?.('love') ?? 0) < R.loveMin) return RB.RIDE_RESULT.NO;
		if (!R.weekDays.includes(Time.weekDay)) return RB.RIDE_RESULT.NO;
		if (Time.hour < R.hourFrom || Time.hour >= R.hourTo) return RB.RIDE_RESULT.NO;
		if (!RB.rideCooldownOver()) return RB.RIDE_RESULT.NO;

		// 本时段已经掷过（无论中没中）→ 不重掷
		const slot = RB.rideSlotKey();
		if (V.robertRideChecked === slot) return RB.RIDE_RESULT.ROLLED;

		V.robertRideChecked = slot;
		const hit = random(1, 100) <= R.chance;
		RB.log(`牛津街偶遇判定: 掷点${hit ? '命中' : '未中'}（时段 ${slot}）`, 'DEBUG');
		return hit ? RB.RIDE_RESULT.YES : RB.RIDE_RESULT.ROLLED;
	};

	RB.initRide = function () {
		RB.log('表白事件模块就绪');
	};
})();
