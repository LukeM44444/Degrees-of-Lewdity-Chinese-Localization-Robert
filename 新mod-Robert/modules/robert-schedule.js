/*
 * RobertNPC —— 日程 / 出现地点模块
 * ---------------------------------------------------------------------------
 * 被 framework.js 的 RB.init() 调用。
 *
 * 框架的日程接口：npc.addSchedule(npcName, config | ScheduleBuilder)
 * 具体字段以框架版本文档为准（docs/CN/NamedNPC/NamedNPCSchedule.md）。
 * 这里给出的是最小可用骨架，并把所有调用包在 try/catch 里：
 * 即使日程配置字段和框架版本不匹配，也只会让「日程」这一项失效，
 * 不会影响 NPC 本体注册和其他 mod。
 */

(function () {
	'use strict';

	if (typeof maplebirch === 'undefined' || !maplebirch) return;
	window.RobertNPC ??= {};
	const RB = window.RobertNPC;

	RB.initSchedule = function () {
		try {
			// 示例：让罗伯特在特定时段出现在特定地点。
			// 先用最保守的写法，等确认框架版本文档后再补全时段/地点。
			maplebirch.npc.addSchedule(RB.NPC_NAME, {
				// 留空表示使用框架默认日程；真正排班时按框架文档填写
			});
			RB.log('日程注册完成（骨架，尚未排班）', 'INFO');
		} catch (e) {
			RB.log(`日程注册跳过: ${e?.message || e}`, 'WARN');
		}
	};

	/**
	 * 当前是否应该让罗伯特出现在场景里。
	 * twee 里用 <<if RobertNPC.canAppear()>> 判断。
	 */
	RB.canAppear = function () {
		try {
			const vars = RB.ensureVars();
			if (!vars.met) return false; // 还没认识就不要冒出来
			return true;
		} catch (e) {
			RB.log(`canAppear 判断失败: ${e?.message || e}`, 'WARN');
			return false;
		}
	};

	/**
	 * 首次见面的标记。剧情里调用一次，之后：
	 *   - canAppear 放行；
	 *   - 社交页面开始显示罗伯特这一格。
	 *
	 * ⚠️ 社交页面的显示开关是 NPC 对象上的 `init` 字段，不是 important。
	 *    原版 <<widget "relation-box">>（base-system/widgets.twee:3380）第一行就是
	 *      <<if _npcData and _npcData.init is 1>>
	 *    ，init 不为 1 时整格直接不渲染。框架只负责把 Robert 注入 V.NPCName
	 *    并把 init 设为 0，**不会**帮你置 1 —— 那是剧情作者的责任。
	 *    所以这里显式置 1，这就是「初次遇到罗伯特后才出现在社交页面」的实现方式。
	 */
	RB.markMet = function () {
		const vars = RB.ensureVars();
		if (vars.met) return false; // 幂等：重复调用不再改动

		vars.met = 1;

		const npc = RB.npcObject?.();
		if (npc) {
			npc.init = 1;
			// 四个属性在初次相遇时归零初始化（老存档 / 被改坏的存档也一并修正）
			RB.ensureNpcStats?.();
			RB.log(`罗伯特首次登场：已置 init=1，社交页面将开始显示（属性 ${RB.STATS?.join('/')}）`);
		} else {
			// 正常情况下不会走到这里：剧情段落运行时 NPC 一定已经注入。
			// 真走到这里也不报错，下一次 :passageinit 的 ensureNpcStats 会补齐属性，
			// 但 init 需要重新触发一次 markMet 才会置 1。
			RB.log('罗伯特首次登场：暂未找到 NPC 对象，init 未置位（稍后重试）', 'WARN');
		}

		return true;
	};
})();
