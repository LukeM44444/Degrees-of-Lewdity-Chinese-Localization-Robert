/**
 * RobertNPC —— 自愿遭遇战行动表修正
 * ===========================================================================
 * 为什么需要这个模块
 * ---------------------------------------------------------------------------
 * 玩家反馈：本 mod 的【摸回去】自愿遭遇战里出现了「击打」和「防狼喷雾」，
 * 这两个只该出现在**非自愿**遭遇战里。
 *
 * 排查结论：**不是本 mod 造成的，是原版存档数据的问题。**
 *
 *   1. 原版 DefaultActions.setDefaults()（03-JavaScript/ingame.js:876-907）
 *      为两套场景分别定义行动分组：
 *          type = "rape"        → Defiant.leftaction = ["lefthit", "leftstruggle"]
 *          type = "consensual"  → Defiant.leftaction = [0]      ← 本该为空
 *   2. 这份结果存在**存档变量** $actionDefaults 里（variables-start2.twee:368）。
 *   3. 版本更新时只在「结构性损坏」时才重建它
 *      （variables-versionUpdate.twee:2549-2559 只检查 rape.regrab[0] 是否为对象）。
 *      所以旧存档会一直保留旧版的 consensual.Defiant 列表。
 *   4. 战斗行动分组由 getCombatDefaultsType（actionsGeneration.twee:70）决定：
 *          $consensual == 1  →  $defaultsCombatType = "consensual"
 *      于是这些旧列表被当成「自愿可用的反抗行动」显示出来。
 *
 * 本模块做什么
 * ---------------------------------------------------------------------------
 * **只**从 $actionDefaults.consensual.Defiant 的左右手列表里移除攻击类行动。
 * 不改 rape 组（非自愿遭遇战需要它们），不动任何原版 widget，不重建整张表。
 * 纯增量：只删明确列出的少数几项，其他 mod 往里加的东西一律保留。
 *
 * 调用时机
 * ---------------------------------------------------------------------------
 * 在入场页调 <<maninit>> **之前**调用 RB.sanitizeConsensualActions()。
 * 也可以手动调用 RB.consensualActionsReport() 查看改了什么。
 */

(function () {
    'use strict';

    var RB = window.RobertNPC = window.RobertNPC || {};

    /**
     * 只该出现在**非自愿**遭遇战里的手部行动。
     * 依据 ingame.js 的 rape 组定义：
     *   leftaction  : lefthit, leftstruggle
     *   rightaction : penwhack, righthit, rightstruggle, hypnosiswhack
     * 以及 spray（防狼喷雾）—— 它由 <<leftspraynew>>/<<rightspraynew>>
     * 在 $consensual isnot 1 时才生成（actions-hands.twee:130 / 518）。
     *
     * 这份清单是**允许删除**的白名单：只有列在这里的行动会被移除，
     * 其他一切（包括其他 mod 添加的）都保持原样。
     */
    var AGGRESSIVE = [
        'lefthit', 'righthit',
        'leftstruggle', 'rightstruggle',
        'spray',
        'penwhack', 'hypnosiswhack',
        'stopchokenoncon'
    ];

    /**
     * 从自愿遭遇战的 Defiant 左右手列表里移除攻击类行动。
     * @returns {{removed: string[], scanned: boolean, reason?: string}}
     */
    RB.sanitizeConsensualActions = function () {
        var result = { removed: [], scanned: false };

        var V = (typeof window.V !== 'undefined') ? window.V : null;
        if (!V || !V.actionDefaults) {
            result.reason = 'V.actionDefaults 不存在（可能还没进入游戏）';
            return result;
        }

        var cons = V.actionDefaults.consensual;
        if (!cons || !cons.Defiant) {
            result.reason = 'actionDefaults.consensual.Defiant 不存在，无需处理';
            return result;
        }

        result.scanned = true;

        ['leftaction', 'rightaction'].forEach(function (part) {
            var list = cons.Defiant[part];
            if (!Array.isArray(list)) return;

            for (var i = list.length - 1; i >= 0; i--) {
                var v = list[i];
                if (typeof v === 'string' && AGGRESSIVE.indexOf(v) !== -1) {
                    list.splice(i, 1);
                    result.removed.push(part + ':' + v);
                }
            }

            // 列表不能为空，否则「切换到反抗行动」页签会没有内容。
            // 只在**我们确实删过东西**且列表被清空时补一个占位。
            if (list.length === 0) {
                list.push('rest');
                result.removed.push(part + ':(empty→rest)');
            }
        });

        if (result.removed.length && RB.log) {
            RB.log('自愿遭遇战行动表已修正，移除：' + result.removed.join(', '));
        }
        return result;
    };

    /** 返回当前自愿/非自愿两套 Defiant 手部列表的快照，便于排障。 */
    RB.consensualActionsReport = function () {
        var V = (typeof window.V !== 'undefined') ? window.V : null;
        if (!V || !V.actionDefaults) return null;
        var out = {};
        ['consensual', 'rape'].forEach(function (t) {
            var d = (V.actionDefaults[t] || {}).Defiant || {};
            out[t] = {
                leftaction: (d.leftaction || []).slice(),
                rightaction: (d.rightaction || []).slice()
            };
        });
        return out;
    };
})();
