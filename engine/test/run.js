'use strict';

/**
 * 最小单测运行器 —— 不引任何框架，node engine/test/run.js 直接跑。
 *
 * 两部分：
 *   1) 固定单测：red / green / uncovered / refuse 四条，覆盖 §6.3 的四种聚合结果
 *   2) 规则夹具：engine/test/fixtures/*.json，每条规则一份，G1 闸门靠它验
 *
 * 任一失败即以非零退出码结束（供 CI 与 G1 使用）。
 */

const fs = require('fs');
const path = require('path');
const engine = require('../index.js');

const ROOT = path.join(__dirname, '..', '..');
const DATA = path.join(ROOT, 'data');

function readJSON(p) {
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

const dataset = {
  reagents: readJSON(path.join(DATA, 'reagents.json')),
  groups: readJSON(path.join(DATA, 'groups.json')),
  matrix: readJSON(path.join(DATA, 'matrix.json')),
  rules: readJSON(path.join(DATA, 'rules.json'))
};

// ---------------------------------------------------------------- 断言工具
let passed = 0;
let failed = 0;
const failures = [];

function check(name, actual, expected) {
  const a = JSON.stringify(actual);
  const e = JSON.stringify(expected);
  if (a === e) {
    passed++;
    console.log('  ok   ' + name);
  } else {
    failed++;
    failures.push(name + '\n         期望 ' + e + '\n         实际 ' + a);
    console.log('  FAIL ' + name);
  }
}

function checkTrue(name, cond, detail) {
  if (cond) {
    passed++;
    console.log('  ok   ' + name);
  } else {
    failed++;
    failures.push(name + (detail ? '\n         ' + detail : ''));
    console.log('  FAIL ' + name);
  }
}

function ids(list) {
  return list.map(function (c) { return c.ruleId; }).sort();
}

// ---------------------------------------------------------------- 1. 固定单测
console.log('\n[1] 固定单测');

// 用例 1：氧化剂 + 易燃物 → 红，组级判定为 medium
(function () {
  const cabinet = {
    id: 'UT-RED',
    items: [{ reagentId: 'R-0001' }, { reagentId: 'R-0011' }]
  };
  const r = engine.checkCabinet(cabinet, dataset);
  check('红线：level', r.level, 'red');
  check('红线：confidence（组级=medium）', r.confidence, 'medium');
  check('红线：命中规则 C-01', ids(r.conflicts), ['C-01']);
  checkTrue('红线：带条款出处字段', typeof r.conflicts[0].clause === 'string' && r.conflicts[0].clause.length > 0);
}());

// 用例 2：同组两瓶易燃物 → 绿，high
(function () {
  const cabinet = {
    id: 'UT-GREEN',
    items: [{ reagentId: 'R-0011' }, { reagentId: 'R-0012' }]
  };
  const r = engine.checkCabinet(cabinet, dataset);
  check('同组：level', r.level, 'green');
  check('同组：confidence', r.confidence, 'high');
  check('同组：无冲突', r.conflicts.length, 0);
  check('同组：无未覆盖', r.uncoveredPairs.length, 0);
}());

// 用例 3：无机酸 + 易燃物（矩阵未覆盖）→ unknown，medium，且不整柜拒答
(function () {
  const cabinet = {
    id: 'UT-UNCOVERED',
    items: [{ reagentId: 'R-0002' }, { reagentId: 'R-0011' }]
  };
  const r = engine.checkCabinet(cabinet, dataset);
  check('未覆盖：level', r.level, 'unknown');
  check('未覆盖：confidence 只降级不拒答', r.confidence, 'medium');
  check('未覆盖：列出未覆盖组对', r.uncoveredPairs.length, 1);
}());

// 用例 4：全部试剂未分类 → refuse
(function () {
  const ds = {
    reagents: [{ id: 'R-TEST', name: '未分类试剂', aliases: [], storageGroup: null, ghs: ['-'] }],
    groups: dataset.groups,
    matrix: dataset.matrix,
    rules: dataset.rules
  };
  const cabinet = { id: 'UT-REFUSE', items: [{ reagentId: 'R-TEST' }] };
  const r = engine.checkCabinet(cabinet, ds);
  check('未分类：level', r.level, 'unknown');
  check('未分类：confidence', r.confidence, 'refuse');
  check('未分类：进入 unclassified', r.unclassified.length, 1);
}());

// 用例 5：部分未分类不整柜拒答（防回归——这是 §6.3 的核心取舍）
(function () {
  const ds = {
    reagents: [
      { id: 'R-0001', name: '硝酸', aliases: [], storageGroup: 'OX', ghs: ['-'] },
      { id: 'R-TEST', name: '未分类试剂', aliases: [], storageGroup: null, ghs: ['-'] }
    ],
    groups: dataset.groups,
    matrix: dataset.matrix,
    rules: dataset.rules
  };
  const cabinet = { id: 'UT-PARTIAL', items: [{ reagentId: 'R-0001' }, { reagentId: 'R-TEST' }] };
  const r = engine.checkCabinet(cabinet, ds);
  checkTrue('部分未分类：不拒答', r.confidence !== 'refuse', '实际 ' + r.confidence);
  checkTrue('部分未分类：列入 unclassified', r.unclassified.length === 1);
}());

// ---------------------------------------------------------------- 2. 规则夹具
console.log('\n[2] 规则夹具');

const fixDir = path.join(__dirname, 'fixtures');
const fixFiles = fs.existsSync(fixDir)
  ? fs.readdirSync(fixDir).filter(function (f) { return f.endsWith('.json'); }).sort()
  : [];

if (fixFiles.length === 0) {
  console.log('  (无夹具文件)');
}

fixFiles.forEach(function (file) {
  const fx = readJSON(path.join(fixDir, file));
  const r = engine.checkCabinet(fx.cabinet, dataset);
  const name = 'fixture ' + file + ' → ' + fx.ruleId;

  if (fx.expect) {
    if (fx.expect.level !== undefined) check(name + ' / level', r.level, fx.expect.level);
    if (fx.expect.confidence !== undefined) check(name + ' / confidence', r.confidence, fx.expect.confidence);
    if (fx.expect.ruleIds !== undefined) check(name + ' / ruleIds', ids(r.conflicts), fx.expect.ruleIds.slice().sort());
  }
});

// ---------------------------------------------------------------- 汇总
console.log('\n' + '-'.repeat(52));
console.log('通过 ' + passed + ' 项，失败 ' + failed + ' 项');
if (failed > 0) {
  console.log('\n失败详情：');
  failures.forEach(function (f) { console.log('  - ' + f); });
  console.log('');
  process.exit(1);
}
console.log('全部通过\n');
