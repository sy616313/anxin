#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""「安芯」数据契约校验器。

按 docs/data-contract.md 校验 data/ 下六个 JSON 文件，并检查跨文件引用。
任何 ERROR 都以非零退出码结束；WARNING 只提示，不阻断。

用法：python scripts/validate_data.py
校验通过后会自动调用 scripts/sync_data.py（任务书 R-04）。
"""

import json
import re
import subprocess
import sys
from pathlib import Path

try:  # Windows 控制台默认 GBK，强制 UTF-8 以免中文报错信息乱码
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

ERRORS: list[str] = []
WARNINGS: list[str] = []


def err(where: str, msg: str) -> None:
    ERRORS.append(f"{where}  {msg}")


def warn(where: str, msg: str) -> None:
    WARNINGS.append(f"{where}  {msg}")


def load(filename: str):
    path = DATA / filename
    if not path.exists():
        err(filename, "文件不存在")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        err(filename, f"JSON 解析失败：第 {exc.lineno} 行 {exc.msg}")
        return None


# ---------------------------------------------------------------- 字段规格
# name -> (python type, nullable, allow_empty)
REAGENT = {
    "id": (str, False, False),
    "name": (str, False, False),
    "aliases": (list, False, True),
    "cas": (str, True, False),
    "ghs": (list, False, False),
    "storageGroup": (str, True, False),
    "hazardNote": (str, False, False),
    "source": (str, False, False),
    "verified": (bool, False, False),
}
GROUP = {"id": (str, False, False), "name": (str, False, False),
         "definition": (str, False, False), "examples": (list, False, True)}
MATRIX_PAIR = {"id": (str, False, False), "a": (str, False, False), "b": (str, False, False),
               "verdict": (str, False, False), "reason": (str, False, False),
               "clause": (str, False, False), "ref": (str, True, False)}
RULE = {"id": (str, False, False), "name": (str, False, False), "scope": (str, False, False),
        "trigger": (dict, False, False), "effect": (dict, False, False),
        "advice": (str, False, False), "clause": (str, False, False),
        "enabled": (bool, False, False)}
CABINET = {"id": (str, False, False), "name": (str, False, False), "room": (str, False, False),
           "floor": (str, False, False), "ownerRole": (str, False, False), "items": (list, False, True)}
FINDING = {"id": (str, False, False), "cabinetId": (str, False, False), "ruleId": (str, False, False),
           "level": (str, False, False), "status": (str, False, False),
           "foundAt": (str, False, False), "foundByRole": (str, False, False),
           "photo": (str, True, False), "fixNote": (str, True, False),
           "verifiedAt": (str, True, False)}

VERDICTS = {"forbidden", "caution", "compatible"}
LEVELS = {"red", "yellow", "green"}
STATUSES = {"open", "fixed", "verified", "ignored"}
TRIGGER_TYPES = {"groupPair", "reagentPair", "itemMissing"}

ID_PATTERNS = {
    "试剂": ("id", re.compile(r"^R-\d{4}$")),
    "规则": ("id", re.compile(r"^C-\d{2}$")),
    "矩阵": ("id", re.compile(r"^P-\d{3}$")),
    "柜子": ("id", re.compile(r"^CAB-[A-Za-z0-9-]+$")),
    "隐患": ("id", re.compile(r"^F-\d{8}-\d{3}$")),
}


def check_obj(where: str, obj, spec: dict) -> bool:
    """检查一个对象的必备字段、类型、空值规则。返回是否可用。"""
    if not isinstance(obj, dict):
        err(where, "应为对象")
        return False
    ok = True
    for field, (ftype, nullable, allow_empty) in spec.items():
        if field not in obj:
            err(where, f"缺少字段 `{field}`")
            ok = False
            continue
        value = obj[field]
        if value is None:
            if not nullable:
                err(where, f"`{field}` 不允许为 null")
                ok = False
            continue
        if not isinstance(value, ftype) or (ftype is bool and not isinstance(value, bool)):
            err(where, f"`{field}` 类型应为 {ftype.__name__}，实际 {type(value).__name__}")
            ok = False
            continue
        if ftype is str and not allow_empty and value.strip() == "":
            err(where, f"`{field}` 不得为空字符串")
            ok = False
    unknown = set(obj) - set(spec)
    if unknown:
        warn(where, f"存在契约外字段 {sorted(unknown)}（新增字段须走 ADR）")
    return ok


def main() -> int:
    reagents = load("reagents.json")
    groups = load("groups.json")
    matrix = load("matrix.json")
    rules = load("rules.json")
    cabinets = load("cabinets.json")
    findings = load("findings.json")
    if any(v is None for v in (reagents, groups, matrix, rules, cabinets, findings)):
        return report()

    for name, value in (("reagents.json", reagents), ("groups.json", groups),
                        ("rules.json", rules), ("cabinets.json", cabinets),
                        ("findings.json", findings)):
        if not isinstance(value, list):
            err(name, "顶层必须是数组")
            return report()
    if not isinstance(matrix, dict) or not isinstance(matrix.get("pairs"), list):
        err("matrix.json", "顶层必须是对象且含 pairs 数组")
        return report()

    # ------------------------------------------------------------ groups
    group_ids = []
    for i, g in enumerate(groups):
        w = f"groups[{i}]"
        if check_obj(w, g, GROUP):
            gid = g["id"]
            if gid in group_ids:
                err(w, f"分组 id 重复：{gid}")
            group_ids.append(gid)
            if not g.get("definition", "").strip().endswith(("。", "；")):
                warn(w, "definition 建议以句号结尾，便于直接展示")
    order = {gid: i for i, gid in enumerate(group_ids)}

    # ------------------------------------------------------------ reagents
    reagent_ids = []
    for i, r in enumerate(reagents):
        w = f"reagents[{i}]"
        if not check_obj(w, r, REAGENT):
            continue
        rid = r["id"]
        if not ID_PATTERNS["试剂"][1].match(rid):
            err(w, f"id 格式应为 R-0001，实际 {rid}")
        if rid in reagent_ids:
            err(w, f"试剂 id 重复：{rid}")
        reagent_ids.append(rid)

        sg = r.get("storageGroup")
        if sg is None:
            warn(w, f"{r['name']} 未分类（storageGroup 为 null），不参与组对判定")
        elif sg not in group_ids:
            err(w, f"storageGroup=`{sg}` 不在 groups.json 中")
        elif sg == "GAS":
            err(w, "GAS 组本版不纳入判定，不应出现在试剂台账中")

        ghs = r.get("ghs") or []
        if not ghs:
            err(w, "ghs 至少需要 1 条")
        if not r.get("verified", False):
            warn(w, f"{r['name']} 尚未复核（verified=false）")

    if len(set(reagent_ids)) != len(reagent_ids):
        pass  # 已在循环内报告

    # ------------------------------------------------------------ matrix
    seen_pairs = set()
    matrix_pairs = set()
    for i, p in enumerate(matrix["pairs"]):
        w = f"matrix.pairs[{i}]"
        if not check_obj(w, p, MATRIX_PAIR):
            continue
        pid, a, b = p["id"], p["a"], p["b"]
        if not ID_PATTERNS["矩阵"][1].match(pid):
            err(w, f"id 格式应为 P-001，实际 {pid}")
        if p["verdict"] not in VERDICTS:
            err(w, f"verdict=`{p['verdict']}` 不在 {sorted(VERDICTS)} 中")
        if a not in order:
            err(w, f"a=`{a}` 不在 groups.json 中")
        if b not in order:
            err(w, f"b=`{b}` 不在 groups.json 中")
        if a == b:
            err(w, "a 与 b 不能相同")
        if a in order and b in order:
            if order[a] >= order[b]:
                err(w, f"组序错误：a(`{a}`) 必须早于 b(`{b}`)，组序见 groups.json 数组顺序")
            key = (a, b) if order[a] < order[b] else (b, a)
            if key in seen_pairs:
                err(w, f"重复组对：{key}")
            seen_pairs.add(key)
            matrix_pairs.add(key)
        if p.get("clause", "").startswith("TODO"):
            warn(w, "clause 仍为占位，须在 D2 前用 data/checklist.xlsx 核对替换（R-08）")

    # ------------------------------------------------------------ rules
    rule_ids = []
    for i, r in enumerate(rules):
        w = f"rules[{i}]"
        if not check_obj(w, r, RULE):
            continue
        rid = r["id"]
        if not ID_PATTERNS["规则"][1].match(rid):
            err(w, f"id 格式应为 C-01，实际 {rid}")
        if rid in rule_ids:
            err(w, f"规则 id 重复：{rid}")
        rule_ids.append(rid)

        trigger = r["trigger"]
        ttype = trigger.get("type")
        if ttype not in TRIGGER_TYPES:
            err(w, f"trigger.type=`{ttype}` 不在 {sorted(TRIGGER_TYPES)} 中")
            continue

        if ttype in ("groupPair", "reagentPair"):
            a, b = trigger.get("a"), trigger.get("b")
            if not a or not b:
                err(w, "groupPair/reagentPair 必须同时提供 a 与 b")
                continue
            if ttype == "groupPair":
                if a not in group_ids:
                    err(w, f"trigger.a=`{a}` 不在 groups.json 中")
                if b not in group_ids:
                    err(w, f"trigger.b=`{b}` 不在 groups.json 中")
                if a in order and b in order:
                    key = (a, b) if order[a] < order[b] else (b, a)
                    if key not in matrix_pairs:
                        err(w, f"组级规则引用的组对 {key} 不在 matrix.json 中（§5.5：规则必须引用矩阵事实）")
            else:
                if a not in reagent_ids:
                    err(w, f"trigger.a=`{a}` 不在 reagents.json 中")
                if b not in reagent_ids:
                    err(w, f"trigger.b=`{b}` 不在 reagents.json 中")
        elif ttype == "itemMissing":
            if not trigger.get("field"):
                err(w, "itemMissing 必须提供 field")

        effect = r["effect"]
        if effect.get("level") not in LEVELS:
            err(w, f"effect.level=`{effect.get('level')}` 不在 {sorted(LEVELS)} 中")
        if not str(effect.get("title", "")).strip():
            err(w, "effect.title 不得为空")

        if str(r.get("clause", "")).startswith("TODO"):
            warn(w, "clause 仍为占位，须在 D2 前用 data/checklist.xlsx 核对替换（R-08）")

    # 矩阵里有事实但没有对应规则的组对 → 提示（不阻断）
    rule_pairs = set()
    for r in rules:
        t = r.get("trigger") or {}
        if t.get("type") == "groupPair" and t.get("a") in order and t.get("b") in order:
            a, b = t["a"], t["b"]
            rule_pairs.add((a, b) if order[a] < order[b] else (b, a))
    for pair in sorted(matrix_pairs - rule_pairs):
        warn("matrix.json", f"组对 {pair} 有事实但无对应规则，引擎不会产生该冲突")

    # ------------------------------------------------------------ cabinets
    cabinet_ids = []
    for i, c in enumerate(cabinets):
        w = f"cabinets[{i}]"
        if not check_obj(w, c, CABINET):
            continue
        cid = c["id"]
        if not ID_PATTERNS["柜子"][1].match(cid):
            err(w, f"id 格式应为 CAB-B3，实际 {cid}")
        if cid in cabinet_ids:
            err(w, f"柜子 id 重复：{cid}")
        cabinet_ids.append(cid)
        for j, item in enumerate(c["items"]):
            wi = f"{w}.items[{j}]"
            if not isinstance(item, dict):
                err(wi, "应为对象")
                continue
            if "reagentId" not in item:
                err(wi, "缺少 reagentId")
            elif item["reagentId"] not in reagent_ids:
                err(wi, f"reagentId=`{item['reagentId']}` 不在 reagents.json 中")

    # ------------------------------------------------------------ findings
    for i, f in enumerate(findings):
        w = f"findings[{i}]"
        if not check_obj(w, f, FINDING):
            continue
        if not ID_PATTERNS["隐患"][1].match(f["id"]):
            err(w, f"id 格式应为 F-20261113-001，实际 {f['id']}")
        if f["status"] not in STATUSES:
            err(w, f"status=`{f['status']}` 不在 {sorted(STATUSES)} 中")
        if f["level"] not in LEVELS:
            err(w, f"level=`{f['level']}` 不在 {sorted(LEVELS)} 中")
        if cabinet_ids and f["cabinetId"] not in cabinet_ids:
            err(w, f"cabinetId=`{f['cabinetId']}` 不在 cabinets.json 中")
        if rule_ids and f["ruleId"] not in rule_ids:
            err(w, f"ruleId=`{f['ruleId']}` 不在 rules.json 中")
        if f["status"] == "ignored" and not f.get("fixNote"):
            err(w, "status=ignored 时必须填写 fixNote 说明理由")

    return report(len(reagents), len(groups), len(matrix["pairs"]), len(rules),
                  len(cabinets), len(findings))


def report(n_r=0, n_g=0, n_p=0, n_rule=0, n_c=0, n_f=0) -> int:
    print("[validate] 统计：试剂 %d 条，分组 %d 个，矩阵 %d 对，规则 %d 条，柜子 %d 个，隐患 %d 条"
          % (n_r, n_g, n_p, n_rule, n_c, n_f))

    if WARNINGS:
        print(f"\n[validate] 警告 {len(WARNINGS)} 条（不阻断）：")
        for w in WARNINGS:
            print("  ! " + w)

    if ERRORS:
        print(f"\n[validate] 错误 {len(ERRORS)} 条：")
        for e in ERRORS:
            print("  x " + e)
        print("\n[validate] 校验未通过\n")
        return 1

    print("\n[validate] 校验通过")
    return 0


if __name__ == "__main__":
    code = main()
    if code == 0:
        # 校验通过后自动同步进小程序（任务书 R-04：防数据同步漏跑）
        sync = ROOT / "scripts" / "sync_data.py"
        if sync.exists():
            print("")
            code = subprocess.call([sys.executable, str(sync)])
    sys.exit(code)
