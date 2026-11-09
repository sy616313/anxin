'use strict';

/**
 * 「安芯」规则引擎 v1
 *
 * 纯函数模块：不读文件、不读全局、不发请求。所有数据由调用方通过 dataset 注入。
 *   dataset = { reagents: [], groups: [], matrix: { pairs: [] }, rules: [] }
 *
 * 契约：docs/data-contract.md §6
 * 聚合规则：docs/05_五天开发任务书 §6.3（逐对定档 → 柜级聚合）
 *
 * 判定优先级（§6.4）：
 *   reagentPair 特例（high） > groupPair 组级（medium） > 无规则（uncovered，不下结论）
 */

const VERSION = '1.0.0';

/** 组对的无序键。分组顺序与它无关，只用来做稳定去重。 */
function key2(a, b) {
  return a <= b ? a + '\u0001' + b : b + '\u0001' + a;
}

/** 把 dataset 预处理成查找表。每次调用都重建——纯函数不缓存跨调用的状态。 */
function buildIndex(dataset) {
  const reagentById = new Map();
  (dataset.reagents || []).forEach(function (r) { reagentById.set(r.id, r); });

  const groupRules = new Map();
  const reagentRules = [];
  (dataset.rules || []).forEach(function (rule) {
    if (rule.enabled === false || !rule.trigger) return;
    const t = rule.trigger;
    if (t.type === 'groupPair') groupRules.set(key2(t.a, t.b), rule);
    else if (t.type === 'reagentPair') reagentRules.push(rule);
  });

  return { reagentById: reagentById, groupRules: groupRules, reagentRules: reagentRules };
}

function hitsReagentPair(trigger, id1, id2) {
  return (trigger.a === id1 && trigger.b === id2) || (trigger.a === id2 && trigger.b === id1);
}

/**
 * 对一对已分类试剂下定论。
 * @returns {{kind:'conflict', rule:object, confidence:string}
 *          |{kind:'ok'}
 *          |{kind:'uncovered', a:string, b:string}}
 */
function evaluatePair(ra, rb, idx) {
  // 1. 特例优先：针对具体两种物质的规定，置信度 high
  for (let i = 0; i < idx.reagentRules.length; i++) {
    const rule = idx.reagentRules[i];
    if (hitsReagentPair(rule.trigger, ra.id, rb.id)) {
      return { kind: 'conflict', rule: rule, confidence: 'high' };
    }
  }

  const ga = ra.storageGroup;
  const gb = rb.storageGroup;

  // 2. 组级规则：类别级判断，置信度 medium
  const groupRule = idx.groupRules.get(key2(ga, gb));
  if (groupRule) {
    return { kind: 'conflict', rule: groupRule, confidence: 'medium' };
  }

  // 3. 同组默认可同柜；OTHER 为兜底组，缺省相容
  if (ga === gb || ga === 'OTHER' || gb === 'OTHER') return { kind: 'ok' };

  // 4. 既无特例也无组级规则 —— 不猜，标记为未覆盖
  return { kind: 'uncovered', a: ga, b: gb };
}

function toConflict(res, ra, rb) {
  const rule = res.rule;
  return {
    ruleId: rule.id,
    level: rule.effect.level,
    confidence: res.confidence,
    title: rule.effect.title,
    a: { reagentId: ra.id, name: ra.name },
    b: { reagentId: rb.id, name: rb.name },
    clause: rule.clause,
    advice: rule.advice
  };
}

/**
 * 检查一个柜子。
 * @param {object} cabinet 单个柜子对象（§5.6）
 * @param {object} dataset { reagents, groups, matrix, rules }
 */
function checkCabinet(cabinet, dataset) {
  const idx = buildIndex(dataset || {});
  const items = (cabinet && cabinet.items) || [];
  const result = {
    cabinetId: (cabinet && cabinet.id) || null,
    level: 'unknown',
    confidence: 'refuse',
    conflicts: [],
    uncoveredPairs: [],
    unclassified: []
  };

  // 空柜：无任何可判定对象
  if (items.length === 0) return result;

  // 分类：storageGroup 为空的试剂不参与两两判定
  const classified = [];
  const seen = new Set();
  for (let i = 0; i < items.length; i++) {
    const r = idx.reagentById.get(items[i].reagentId);
    if (!r || !r.storageGroup) {
      result.unclassified.push({
        reagentId: items[i].reagentId,
        name: r ? r.name : '（台账未收录）'
      });
      continue;
    }
    if (seen.has(r.id)) continue; // 同一试剂多瓶只算一次，避免自己跟自己比
    seen.add(r.id);
    classified.push(r);
  }

  // 全部未分类：给不出任何结论
  if (classified.length === 0) return result;

  // 两两判定
  const uncoveredKeys = new Set();
  for (let i = 0; i < classified.length; i++) {
    for (let j = i + 1; j < classified.length; j++) {
      const ra = classified[i];
      const rb = classified[j];
      const res = evaluatePair(ra, rb, idx);
      if (res.kind === 'conflict') {
        result.conflicts.push(toConflict(res, ra, rb));
      } else if (res.kind === 'uncovered') {
        const k = key2(res.a, res.b);
        if (uncoveredKeys.has(k)) continue; // 同一组对只报一次
        uncoveredKeys.add(k);
        result.uncoveredPairs.push({ a: res.a, b: res.b, note: '该组对未收录，需专业人员确认' });
      }
    }
  }

  // 柜级 level 聚合
  const hasRed = result.conflicts.some(function (c) { return c.level === 'red'; });
  const hasYellow = result.conflicts.some(function (c) { return c.level === 'yellow'; });
  const hasGap = result.uncoveredPairs.length > 0 || result.unclassified.length > 0;

  if (hasRed) result.level = 'red';
  else if (hasGap) result.level = 'unknown';
  else if (hasYellow) result.level = 'yellow';
  else result.level = 'green';

  // 柜级 confidence 聚合：缺口只降级、不拒答
  if (hasGap) {
    result.confidence = 'medium';
  } else if (result.conflicts.length === 0) {
    result.confidence = 'high';
  } else {
    const anyMedium = result.conflicts.some(function (c) { return c.confidence === 'medium'; });
    result.confidence = anyMedium ? 'medium' : 'high';
  }

  return result;
}

/**
 * 按名称或别名查试剂。
 * @param {string} keyword
 * @param {object} dataset
 */
function classifyReagent(keyword, dataset) {
  const kw = String(keyword == null ? '' : keyword).trim().toLowerCase();
  if (!kw) return { matches: [], confidence: 'refuse', note: '未输入关键词' };

  const reagents = (dataset && dataset.reagents) || [];
  const exact = [];
  const partial = [];

  for (let i = 0; i < reagents.length; i++) {
    const r = reagents[i];
    const names = [r.name].concat(r.aliases || []);
    let isExact = false;
    let isPartial = false;
    for (let n = 0; n < names.length; n++) {
      const s = String(names[n]).toLowerCase();
      if (s === kw) isExact = true;
      else if (s.indexOf(kw) !== -1) isPartial = true;
    }
    if (isExact) exact.push(r);
    else if (isPartial) partial.push(r);
  }

  const picked = exact.length ? exact : partial;
  if (picked.length === 0) {
    return { matches: [], confidence: 'refuse', note: '未收录，请手动录入或询问安全员' };
  }

  const matches = picked.map(function (r) {
    return { reagentId: r.id, name: r.name, storageGroup: r.storageGroup || null };
  });

  if (exact.length === 1) return { matches: matches, confidence: 'high', note: null };
  return { matches: matches, confidence: 'medium', note: '命中 ' + matches.length + ' 条，请确认是哪一个' };
}

module.exports = {
  VERSION: VERSION,
  checkCabinet: checkCabinet,
  classifyReagent: classifyReagent
};
