# 数据与接口契约 v1（冻结）

> 冻结日期：2026-11-09（D1）
> 依据：《05_五天开发任务书》§5、§6
> 状态：**已冻结**。此后任何字段增删、类型变更、枚举扩充，必须走 ADR（AGENTS.md §7）。
> 本文是实现与校验的唯一依据：`scripts/validate_data.py` 逐条实现下列约束。

---

## 0. 总则

- `data/*.json` 是**唯一真源**。小程序里的数据是构建产物，不得手改。
- 编码 UTF-8 无 BOM，两空格缩进，顶层顺序即展示顺序（`groups.json` 的数组顺序还额外承担"组序"职责）。
- 任何字段**不得为空字符串**；未知填 `null`（仅限标记为可空的字段）。
- 无出处（`clause` 为空）的规则不得入库；未核实的填 `"TODO-占位"` 并在交接文档登记。

### 0.1 ID 规范

| 类型 | 格式 | 示例 |
|---|---|---|
| 试剂 | `R-` + 4 位 | `R-0001` |
| 分组 | 大写英文短码 | `OX` |
| 矩阵对 | `P-` + 3 位 | `P-001` |
| 规则 | `C-` + 2 位 | `C-01` |
| 柜子 | `CAB-` + 编号 | `CAB-B3` |
| 隐患 | `F-` + 8 位日期 + `-` + 3 位序号 | `F-20261113-001` |

---

## 1. `groups.json` — 存储相容组

**数组顺序即组序**，是矩阵去重与规则引用的权威顺序：

```
OX(0) < FLAM(1) < ACID_IN(2) < ACID_ORG(3) < BASE(4)
     < WATER_REACT(5) < TOX(6) < HALA(7) < GAS(8) < OTHER(9)
```

| 字段 | 类型 | 必填 | 可空 | 说明 |
|---|---|---|---|---|
| `id` | string | ✔ | ✘ | 10 个组之一 |
| `name` | string | ✔ | ✘ | 中文名 |
| `definition` | string | ✔ | ✘ | 一句话定义，以句号结尾，可直接展示 |
| `examples` | string[] | ✔ | ✘ | 3 个代表物质，可为空数组 |

> `GAS` 为占位组，**不参与组对判定**；试剂台账中不得出现 `storageGroup: "GAS"`。

## 2. `reagents.json` — 试剂台账

| 字段 | 类型 | 必填 | 可空 | 说明 |
|---|---|---|---|---|
| `id` | string | ✔ | ✘ | `R-0001` |
| `name` | string | ✔ | ✘ | 中文正名，与标签一致 |
| `aliases` | string[] | ✔ | ✘ | 俗名与分子式；无别名填 `[]` |
| `cas` | string | ✔ | ✔ | 查不到填 `null`；填了必须正确 |
| `ghs` | string[] | ✔ | ✘ | 至少 1 条，写法如 `氧化性液体-类别3` |
| `storageGroup` | string | ✔ | ✔ | 10 组之一；`null` = 已入台账但未分类 |
| `hazardNote` | string | ✔ | ✘ | 一句话，学生看得懂的表述 |
| `source` | string | ✔ | ✘ | 数据依据，答辩可追溯 |
| `verified` | boolean | ✔ | ✘ | 是否经第二人复核 |

**`storageGroup` 为 `null` 的语义**：键必须存在，值可为 `null`。该试剂不参与两两判定，进入 `unclassified`。

**没有 `formula` 字段**。分子式写进 `aliases`。新增字段须走 ADR。

## 3. `matrix.json` — 组间相容矩阵

```json
{ "version": "1.0", "updated": "2026-11-09", "pairs": [ ... ] }
```

| 字段 | 类型 | 必填 | 可空 | 说明 |
|---|---|---|---|---|
| `id` | string | ✔ | ✘ | `P-001` |
| `a` | string | ✔ | ✘ | 组 id，**组序必须早于 `b`** |
| `b` | string | ✔ | ✘ | 组 id，不得等于 `a` |
| `verdict` | string | ✔ | ✘ | `forbidden` / `caution` / `compatible` |
| `reason` | string | ✔ | ✘ | 为什么不能混存，一句话 |
| `clause` | string | ✔ | ✘ | 条款出处，未核实填 `TODO-占位` |
| `ref` | string | ✔ | ✔ | 上位标准引用，如 GB 编号 |

**矩阵无向**：`(OX,FLAM)` 与 `(FLAM,OX)` 视为同一对，重复即校验失败。

## 4. `rules.json` — 规则库

| 字段 | 类型 | 必填 | 可空 | 说明 |
|---|---|---|---|---|
| `id` | string | ✔ | ✘ | `C-01` |
| `name` | string | ✔ | ✘ | 规则名 |
| `scope` | string | ✔ | ✘ | 本版固定 `cabinet` |
| `trigger` | object | ✔ | ✘ | 见下 |
| `effect` | object | ✔ | ✘ | `{ level, title }`，level ∈ red/yellow/green |
| `advice` | string | ✔ | ✘ | 整改建议（产品里就叫"整改建议"，无优化算法） |
| `clause` | string | ✔ | ✘ | 条款出处 |
| `enabled` | boolean | ✔ | ✘ | `false` 表示停用但保留 |

`trigger.type` 仅三种：

| type | 参数 | 含义 | 互斥校验 |
|---|---|---|---|
| `groupPair` | `a`, `b` | 两存储组同柜 | 该组对**必须存在于 matrix.json** |
| `reagentPair` | `a`, `b` | 两个具体试剂同柜（特例，优先级最高） | `a`/`b` 必须是真实试剂 id |
| `itemMissing` | `field` | 试剂缺必填字段 | — |

### 4.1 matrix 与 rules 的分工

| 文件 | 是什么 | 谁维护 | 能否直接产生结论 |
|---|---|---|---|
| `matrix.json` | 化学事实 | C（数据） | **不能**，不含级别与建议 |
| `rules.json` | 检查逻辑 | C 起草 / **B 审核合入** | **能**，所有 conflicts 由规则产生 |

**引擎不得绕过规则直接读矩阵下结论。**

## 5. `cabinets.json` — 柜位

| 字段 | 类型 | 必填 | 可空 | 说明 |
|---|---|---|---|---|
| `id` | string | ✔ | ✘ | `CAB-B3` |
| `name` | string | ✔ | ✘ | 展示名 |
| `room` | string | ✔ | ✘ | 房间 |
| `floor` | string | ✔ | ✘ | 楼层 |
| `ownerRole` | string | ✔ | ✘ | **写岗位不写人名** |
| `items` | object[] | ✔ | ✘ | `{ reagentId, amount, slot }` |

## 6. `findings.json` — 隐患记录

| 字段 | 类型 | 必填 | 可空 | 说明 |
|---|---|---|---|---|
| `id` | string | ✔ | ✘ | 客户端生成：`F-YYYYMMDD-序号` |
| `cabinetId` | string | ✔ | ✘ | 必须存在于 cabinets.json |
| `ruleId` | string | ✔ | ✘ | 必须存在于 rules.json |
| `level` | string | ✔ | ✘ | red / yellow / green |
| `status` | string | ✔ | ✘ | `open` → `fixed` → `verified`，可转 `ignored` |
| `foundAt` | string | ✔ | ✘ | ISO8601 带时区 |
| `foundByRole` | string | ✔ | ✘ | 岗位，不写人名 |
| `photo` | string | ✔ | ✔ | 本版固定 `null`（无对象存储） |
| `fixNote` | string | ✔ | ✔ | `ignored` 时必填 |
| `verifiedAt` | string | ✔ | ✔ | 复核时间 |

**本版落盘方式**：运行时数据存 `wx.setStorageSync('findings', [...])`，仓库里的这个文件只放结构与样例。导出靠复制 JSON 到剪贴板。

---

## 7. 接口契约

### 7.1 为什么必须带 `dataset`

引擎是纯函数，**不读文件、不读全局、不发请求**（AGENTS.md §4.1）。
只传 `cabinetId` 会逼引擎自己去读 JSON —— 既不是纯函数，小程序里也根本读不到仓库路径。

### 7.2 `checkCabinet(cabinet, dataset)`

```js
// dataset = { reagents, groups, matrix, rules }
{
  "cabinetId": "CAB-B3",
  "level": "red",              // red | yellow | green | unknown
  "confidence": "medium",      // high | medium | refuse
  "conflicts": [{
    "ruleId": "C-01",
    "level": "red",
    "confidence": "medium",    // high=特例命中，medium=组级命中
    "title": "...",
    "a": { "reagentId": "R-0001", "name": "硝酸" },
    "b": { "reagentId": "R-0011", "name": "乙醇" },
    "clause": "...",
    "advice": "..."
  }],
  "uncoveredPairs": [{ "a": "TOX", "b": "HALA", "note": "该组对未收录，需专业人员确认" }],
  "unclassified": [{ "reagentId": "R-0042", "name": "某未分类试剂" }]
}
```

**`suggestions` 字段已删除**，整改建议走 `advice`。

### 7.3 `classifyReagent(keyword, dataset)`

| 档位 | 条件 |
|---|---|
| `high` | 按 `name` 或 `aliases` 精确命中且只命中一条 |
| `medium` | 命中多条，或仅"包含"匹配 |
| `refuse` | 无命中 |

```js
{ "matches": [{ "reagentId": "R-0001", "name": "硝酸", "storageGroup": "OX" }],
  "confidence": "high", "note": null }
```

### 7.4 逐对定档 → 柜级聚合

**逐对**：

| 档位 | 条件 |
|---|---|
| `high` | 命中 `reagentPair` 特例 |
| `medium` | 命中 `groupPair` 组级规则 |
| `uncovered` | 两者都无（且非同组、非 OTHER）→ 列入 `uncoveredPairs`，不下结论 |
| `unclassified` | 试剂 `storageGroup` 为 `null` |

**聚合**：

```
level      = red      存在 red 冲突
           = unknown  无 red，但存在 uncovered/unclassified
           = yellow   无 red 无缺口，但有 yellow
           = green    其余

confidence = refuse   空柜，或全部试剂未分类
           = medium   存在 uncovered/unclassified（只降级、不拒答）
           = medium   命中的冲突里有 medium
           = high     其余
```

**同组默认可同柜；`OTHER` 为兜底组，缺省相容。**

---

## 8. 构建与校验

```bash
# 校验 data/*.json（含跨文件引用）；不通过则以非零退出码结束，且不会同步
python scripts/validate_data.py

# 只做打包（一般不需要单独跑，validate 成功后会自动调用）
python scripts/sync_data.py

# 跑引擎单测与规则夹具
node engine/test/run.js
```

### 8.1 校验通过后自动同步

`validate_data.py` 成功后会自动执行 `scripts/sync_data.py`，产出两个**构建产物**：

| 产物 | 来源 | 是否入库 |
|---|---|---|
| `miniprogram/data/dataset.js` | `data/*.json` | 否（.gitignore） |
| `miniprogram/engine/index.js` | `engine/index.js` | 否（.gitignore） |

**为什么要拷贝引擎**：小程序不能 require 工程根目录之外的文件，`engine/index.js` 必须复制到 `miniprogram/engine/` 才能被页面引用。两个产物都由脚本生成，因此不存在手改不同步的问题。

**为什么产物不入库**：入库的副本会静默过期。不入库则文件缺失会立刻报错——响亮的失败优于安静的陈旧（任务书 R-04）。

> 因此：**clone 之后、打开微信开发者工具之前，必须先跑一次 `python scripts/validate_data.py`。**

### 8.2 校验器覆盖的交叉引用

- 试剂 `storageGroup` ∈ 分组 id（或 `null`）
- 矩阵 `a`/`b` ∈ 分组 id，且组序正确、无重复对
- 组级规则的组对必须存在于矩阵
- 特例规则的试剂 id 必须存在
- 柜内 `reagentId` 必须存在
- 隐患的 `cabinetId`/`ruleId` 必须存在
- `ignored` 状态必须填 `fixNote`

---

## 9. 变更流程

任何字段增删 → 新建 `docs/adr/ADR-00X-<标题>.md` → 更新本文件 → 更新 `scripts/validate_data.py` → 全量重校验 → 在当日交接文档记录。

**没有 ADR 的契约变更 = 破坏性变更，直接回退。**
