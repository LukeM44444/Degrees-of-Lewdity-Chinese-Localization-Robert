/**
 * RobertNPC —— 罗伯特的性别配置
 * ===========================================================================
 * 被 framework.js 的 RB.init() 调用。
 *
 * 需求：罗伯特本身可男可女，做成可配置。
 *
 * ⚠️ 不要自己去写 penis / vagina / breastdesc / penissize 这些字段 ——
 *    它们是**性别驱动的派生字段**。maplebirch 框架的 NamedNPC 类上已经有
 *    成套的现成方法（见 inject_early.js 的 NamedNPC 实现）：
 *
 *      setBodyTraits({})    按 this.gender 重算全部身体字段：
 *                             m → penis "clothed" / vagina "none" / penisdesc "penis" …
 *                             f → penis "none"   / vagina "clothed" / breastdesc "breasts" …
 *                             h → 两套都有
 *                           只覆盖你传进去的键，其余按性别取默认值。
 *      setPronouns()        按 this.pronoun 重算 this.pronouns（他/她/它…）
 *      bodyPartdescription() 重算那些依赖性别的描述文本
 *
 * ⚠️ 顺序很重要：**先设 gender，再设 pronoun，最后才调这三个方法**。
 *    反过来会把旧性别算出来的值留在身上。
 *
 * ⚠️ setBodyTraits 传**空对象**，不要展开现有字段（{...npc}）：
 *    展开会把旧的 penis:"none" 当成「用户指定的值」再塞回去，
 *    结果换成男性后依然没有阴茎 —— 这正是它 ?? 默认值语义的坑。
 *
 * ⚠️ 改完要重新 <<npc Robert>>（或 initNNPCClothes）让 $NPCList 那份生效：
 *    社交页面、战斗里读的是 $NPCList 的副本，不是 $NPCName 里这份。
 *
 * 性别取值与原版一致：m = 男、f = 女、h = 双性、n = 无性。
 */

(function () {
	'use strict';

	if (typeof maplebirch === 'undefined' || !maplebirch) return;
	window.RobertNPC ??= {};
	const RB = window.RobertNPC;

	/** 可配置的性别选项。默认 'm'（与 framework.js 的 NPC_DATA 一致）。 */
	RB.GENDERS = [
		{ value: 'm', cn: '男', en: 'Male' },
		{ value: 'f', cn: '女', en: 'Female' },
		{ value: 'h', cn: '双性', en: 'Hermaphrodite' },
		{ value: 'n', cn: '无性', en: 'Genderless' }
	];

	/**
	 * 按**性器官**划分的三种选项 —— 作弊菜单用这个，而不是列四种性别。
	 *
	 * 需求：像原版「身体」设置那样，用「阴茎 / 阴道 / 两者都有」三个单选项
	 *      来决定男 / 女 / 双性。
	 * 对应原版 settings.twee:869-871：
	 *      <label>Penis  <<radiobutton "$player.sex" "m" autocheck>></label> |
	 *      <label>Vagina <<radiobutton "$player.sex" "f" autocheck>></label> |
	 *      <label>Both   <<radiobutton "$player.sex" "h" autocheck>></label>
	 * 值直接复用原版的 'm' / 'f' / 'h'，正好也就是本 mod setGender 的入参。
	 *
	 * ⚠️ 这里**不列 'n'（无性）**：原版那三个选项也没有它，
	 *    而且罗伯特是恋爱对象，无性会让所有性相关剧情失去意义。
	 *    setGender 仍然接受 'n'，只是界面上不提供。
	 */
	RB.GENITAL_OPTIONS = [
		{ value: 'm', cn: '阴茎', en: 'Penis' },
		{ value: 'f', cn: '阴道', en: 'Vagina' },
		{ value: 'h', cn: '两者都有', en: 'Both' }
	];

	/** 界面语言是不是中文。 */
	RB.isCN = function () {
		try {
			return window.maplebirch?.settings?.language === 'CN';
		} catch (e) {
			return false;
		}
	};

	/** 当前性别的显示名（跟随语言）。 */
	RB.genderLabel = function () {
		const g = RB.gender();
		const item = RB.GENDERS.find((x) => x.value === g);
		if (!item) return g;
		return RB.isCN() ? item.cn : item.en;
	};

	/**
	 * 把 $robertGenitals 应用到罗伯特身上。
	 *
	 * 用法（作弊菜单）：先用 <<radiobutton "$robertGenitals" "m|f|h" autocheck>>
	 * 让按钮写变量，再用 jQuery 的 change 处理器调本函数 —— 与原版
	 * settings.twee:877-885 对「生殖器」那一组按钮的做法完全一致：
	 *     $('#genitals input[type="radio"]').on('change', () => { ... })
	 *
	 * ⚠️ 为什么不用回调：原版 <<radiobutton>>（SugarCube 的 format.js）
	 *    **没有**回调钩子（只有 <<numberStepper>> 有 callback）。
	 *    所以「写变量之后要顺带干点别的」只能靠自己挂 change 处理器 ——
	 *    原版自己也是这么写的，不要另想办法。
	 *
	 * 幂等（值没变就不做事）。
	 * @param {string} value 'm' | 'f' | 'h'
	 * @returns {boolean} 是否改动了性别
	 */
	RB.applyGenitals = function (value) {
		if (!RB.GENITAL_OPTIONS.some((x) => x.value === value)) {
			RB.log(`applyGenitals: 非法值 ${value}`, 'WARN');
			return false;
		}
		if (RB.gender() === value) return false;
		const ok = RB.setGender(value);
		RB.syncGenderToEncounter();
		return ok;
	};

	/** 当前性别。读的是活数据（$NPCName 里那份）。 */
	RB.gender = function () {
		return RB.npcObject?.()?.gender ?? 'm';
	};

	/**
	 * 把罗伯特改成指定性别。
	 *
	 * @param {string} gender 'm' | 'f' | 'h' | 'n'
	 * @returns {boolean} 是否成功
	 */
	RB.setGender = function (gender) {
		const npc = RB.npcObject?.();
		if (!npc) {
			RB.log('setGender: NPC 尚未注入', 'WARN');
			return false;
		}
		if (!RB.GENDERS.some((x) => x.value === gender)) {
			RB.log(`setGender: 非法性别 ${gender}`, 'WARN');
			return false;
		}

		const before = npc.gender;
		npc.gender = gender;
		/* 人称代词默认跟随性别；原版 'i' 是「它」那类特殊值，这里不用。 */
		npc.pronoun = gender;

		/* 顺序见文件头的 ⚠️：先 gender/pronoun，再重算派生字段。 */
		try {
			if (typeof npc.setBodyTraits === 'function') {
				npc.setBodyTraits({});
			} else {
				RB.log('setBodyTraits 不可用，身体字段可能没跟着变', 'ERROR');
			}
			if (typeof npc.setPronouns === 'function') npc.setPronouns();
			if (typeof npc.bodyPartdescription === 'function') npc.bodyPartdescription();
		} catch (e) {
			RB.log(`重算性别相关字段失败: ${e?.message || e}`, 'ERROR');
			return false;
		}

		RB.log(`罗伯特性别 ${before} → ${gender}（${RB.genderLabel()}）`);
		return true;
	};

	/**
	 * 让 $NPCList 那份副本跟着更新。
	 * 改完性别后由界面调用 —— 与 <<npc Robert>> 里做的是同一件事，
	 * 抽出来是为了在「不在事件里」的地方（比如作弊菜单）也能刷新。
	 * @returns {boolean}
	 */
	RB.syncGenderToEncounter = function () {
		if (typeof initNNPCClothes !== 'function') return false;
		try {
			initNNPCClothes(RB.NPC_NAME);
			return true;
		} catch (e) {
			RB.log(`同步性别到 $NPCList 失败: ${e?.message || e}`, 'WARN');
			return false;
		}
	};

	/**
	 * 身体字段修复 —— 旧存档与配置写错时的兜底。
	 *
	 * ⚠️ 为什么需要：penis / vagina 的合法值是
	 *    "clothed" / 0 / "none"（衣物暴露状态）。老版本的 NPC_DATA 里
	 *    penis 写成了 'human'，而 <<npcGenitals>>（text.twee:6109）判的是
	 *    `penis isnot "none" and vagina isnot "none"` —— 'human' 让第一个
	 *    条件成立，于是正文会同时印出「阴茎和阴道」（踩过）。
	 *
	 * 判据：penis 既不是 "none" 也不是 "clothed" 也不是 0，就说明它坏了
	 *（可能是 'human' 之类的旧值）。这时按 gender 重算一遍。
	 *
	 * 幂等，可以在 :passageinit 里反复调。
	 * @returns {boolean} 是否做了修复
	 */
	RB.repairAnatomy = function () {
		const npc = RB.npcObject?.();
		if (!npc) return false;

		const ok = (v) => v === 'none' || v === 'clothed' || v === 0;
		const num = (v) => typeof v === 'number' && Number.isFinite(v);
		const broken =
			!ok(npc.penis) || !ok(npc.vagina) || !ok(npc.chest) ||
			!num(npc.penissize) || !num(npc.breastsize) || !num(npc.ballssize);
		if (!broken) return false;

		RB.log(
			`检测到非法身体字段（penis=${npc.penis} / vagina=${npc.vagina} / chest=${npc.chest}`
			+ ` / penissize=${npc.penissize} / breastsize=${npc.breastsize}），按性别重算`,
			'WARN'
		);
		try {
			if (typeof npc.setBodyTraits === 'function') {
				/* 传空对象 = 全部按 gender 取默认值，见 setGender 的说明 */
				npc.setBodyTraits({});
				if (typeof npc.bodyPartdescription === 'function') npc.bodyPartdescription();
				RB.syncGenderToEncounter();
				return true;
			}
			RB.log('setBodyTraits 不可用，无法修复身体字段', 'ERROR');
		} catch (e) {
			RB.log(`修复身体字段失败: ${e?.message || e}`, 'ERROR');
		}
		return false;
	};

	/**
	 * 修正 `title` —— 旧存档自愈。
	 *
	 * ⚠️ 为什么需要：`title` 在框架里是**只在注册/首次创建 NPC 时**从
	 *    NPC_DATA 抄一次，之后存在存档里。所以光改 framework.js 的
	 *    NPC_DATA 对**已有存档无效** —— 存档里仍然是旧值。
	 *
	 * 为什么 title 不能是角色名：
	 *    <<personselect>>（base-system/text.twee:1909-1912）对具名 NPC
	 *    会 `$description to $NPCName[...].title`，
	 *    而 <<person>>（:1811）在具名时直接 `_text_output to $description`。
	 *    所以 title 写成 'Robert' 会让随机路人句输出
	 *    「一个路过的 Robert 偷偷看了一眼你的胸部。」
	 *    原版用的是职业词（Avery "businessman"、Eden "hunter"）。
	 *
	 * 这里把「title 等于角色名」这种明显写错的情况改成职业词。
	 * 判据保守：**只有 title 恰好等于 nam 时才动**，不覆盖玩家/其它 mod
	 * 有意设置的其它 title。
	 *
	 * 幂等，可在 :passageinit 里反复调。
	 * @returns {boolean} 是否做了修复
	 */
	RB.repairTitle = function () {
		const npc = RB.npcObject?.();
		if (!npc) return false;
		if (npc.title !== RB.NPC_NAME) return false;

		npc.title = RB.NPC_TITLE;
		RB.log(`已修正 title：'${RB.NPC_NAME}' → '${RB.NPC_TITLE}'（旧存档自愈）`, 'WARN');
		return true;
	};

	RB.initGender = function () {
		RB.log(`性别模块就绪，当前：${RB.genderLabel()}`);
		RB.repairAnatomy();
		RB.repairTitle();
	};
})();
