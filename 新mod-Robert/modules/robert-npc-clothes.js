/**
 * RobertNPC —— NPC 衣物快照与恢复
 * ===========================================================================
 * 为什么需要
 * ---------------------------------------------------------------------------
 * 【页面3】的正文写着「两人将衣服重新穿好」，所以要还原的是**两个人**的衣服。
 *
 * 玩家侧用 clone($worn) 就够了（见 robert-taxi-event.twee 的注释）。
 * NPC 侧不能照搬 —— <<npc Robert>> 每次调用都会跑
 * <<npcEquipSet>>（ingame.js:1599），把整套衣服**按 outfit 重置**：
 *
 *     npc.clothes = { set: set.name };
 *     Object.entries(set.clothes).forEach(item => {
 *         if (item[1].name === "naked") { npcMakeNaked(npc, item[0]); }
 *         npc.clothes[item[0]] = { name: …, integrity: … };
 *     });
 *
 * 也就是说它只认 outfit 定义，**玩家在剧情里造成的衣物状态变化会被抹掉**。
 *
 * 具体到本 mod：【页面4】用 npcMakeNaked 脱掉罗伯特的裤子。
 * 如果快照记在「口部遭遇战入场」，那时裤子**已经脱了**，
 * 恢复出来就是「裤子脱着」——与正文矛盾。
 * 所以快照必须记在**改动发生之前**，也就是【页面1】点【为其口交】的时候。
 *
 * 覆盖的字段（NPC 身上与「衣物是否脱掉」有关的全部状态）
 * ---------------------------------------------------------------------------
 *   clothes                    整套衣物（含 set / 各槽位 name+integrity）
 *   penis / vagina / chest     暴露状态：clothed 或 0
 *   location.genitals / .head  生殖器与头部的相对位置
 *
 * ⚠️ 为什么不直接保存整个 $NPCList[0]：
 *    里面还有 pronounts / chastity / condom / 各种战斗用字段，
 *    整包覆盖会把战斗中的状态一起回滚，副作用太大。只取与衣着相关的。
 */

(function () {
    'use strict';

    var RB = window.RobertNPC = window.RobertNPC || {};

    /**
     * 记下 NPC 当前的衣着状态。
     * @param {number} idx $NPCList 槽位，默认 0
     * @param {string} key 存放快照的存档变量名（不含 $）
     */
    RB.snapshotNpcClothes = function (idx, key) {
        idx = (idx === undefined || idx === null) ? 0 : idx;
        key = key || 'robertNpcClothesBackup';

        var V = window.V;
        if (!V || !V.NPCList || !V.NPCList[idx]) return null;

        var npc = V.NPCList[idx];
        var snap = {
            clothes: JSON.parse(JSON.stringify(npc.clothes || {})),
            penis: npc.penis,
            vagina: npc.vagina,
            chest: npc.chest,
            locationGenitals: npc.location ? npc.location.genitals : undefined,
            locationHead: npc.location ? npc.location.head : undefined
        };
        V[key] = snap;
        if (RB.log) RB.log('已记录 NPC[' + idx + '] 衣着快照 → $' + key);
        return snap;
    };

    /**
     * 把 NPC 的衣着还原到快照。
     *
     * ⚠️ 会顺带把 penis / vagina / chest 按快照的 clothes 重新推算，
     *    而不是直接写快照里的值 —— 因为那三个字段的语义是
     *    「衣物是否被脱掉」，必须与 clothes 保持一致
     *    （原版就是在 npc-generation.twee:731 这么推的）。
     *
     * @returns {boolean} 是否真的做了恢复（没差别时返回 false）
     */
    RB.restoreNpcClothes = function (idx, key) {
        idx = (idx === undefined || idx === null) ? 0 : idx;
        key = key || 'robertNpcClothesBackup';

        var V = window.V;
        if (!V || !V.NPCList || !V.NPCList[idx]) return false;

        var snap = V[key];
        if (!snap) return false;

        var npc = V.NPCList[idx];
        var changed = JSON.stringify(npc.clothes || {}) !== JSON.stringify(snap.clothes || {});

        if (changed) {
            npc.clothes = JSON.parse(JSON.stringify(snap.clothes || {}));

            var lowerNaked = !(npc.clothes.lower && npc.clothes.lower.name && npc.clothes.lower.name !== 'naked');
            var upperNaked = !(npc.clothes.upper && npc.clothes.upper.name && npc.clothes.upper.name !== 'naked');

            // 与 npc-generation.twee:730-736 的推导保持一致
            if (npc.penis !== 'none') npc.penis = lowerNaked ? 0 : 'clothed';
            if (npc.vagina !== 'none') npc.vagina = lowerNaked ? 0 : 'clothed';
            npc.chest = upperNaked ? 0 : 'clothed';

            if (npc.location) {
                npc.location.genitals = snap.locationGenitals;
                npc.location.head = snap.locationHead;
            }
            if (RB.log) RB.log('已还原 NPC[' + idx + '] 的衣着');
        }

        delete V[key];
        return changed;
    };

    /** 快照是否还在（收场页用它判断「这场有没有动过衣服」）。 */
    RB.hasNpcClothesBackup = function (key) {
        var V = window.V;
        return Boolean(V && V[key || 'robertNpcClothesBackup']);
    };
})();
