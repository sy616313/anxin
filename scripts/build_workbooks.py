#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""生成 data/ 下的两个工作簿：

  data/reagents.xlsx   —— C 的录入工作表，与 reagents.json 对应
  data/checklist.xlsx  —— 检查项目表转录本，规则 clause 的唯一出处

**默认只补缺失的文件，不覆盖已有文件** —— 因为这两个表会被人工编辑，
盲目重生成会丢掉转录成果。需要从 JSON 重新生成时显式加 --force。

  python scripts/build_workbooks.py            # 只补缺失
  python scripts/build_workbooks.py --force    # 覆盖重生成

真源约定：JSON 是唯一真源。reagents.xlsx 是 JSON 的视图；checklist.xlsx 是
人工转录件（其种子内容在本脚本的 CHECKLIST_ROWS，一经转录后以 xlsx 为准）。
"""

import json
import sys
from pathlib import Path

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

try:
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

HEAD_FILL = PatternFill("solid", fgColor="DCE6F1")
HEAD_FONT = Font(name="微软雅黑", size=10, bold=True)
BODY_FONT = Font(name="微软雅黑", size=10)
TITLE_FONT = Font(name="微软雅黑", size=14, bold=True)
NOTE_FONT = Font(name="微软雅黑", size=9, color="555555")
THIN = Side(style="thin", color="B0B0B0")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
WRAP = Alignment(vertical="top", wrap_text=True)


def style_header(ws, widths):
    for i, w in enumerate(widths, start=1):
        ws.column_dimensions[get_column_letter(i)].width = w
    for cell in ws[1]:
        cell.fill = HEAD_FILL
        cell.font = HEAD_FONT
        cell.border = BORDER
        cell.alignment = Alignment(vertical="center", horizontal="center", wrap_text=True)
    ws.freeze_panes = "A2"
    ws.auto_filter.ref = ws.dimensions
    ws.row_dimensions[1].height = 26


def style_body(ws):
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.font = BODY_FONT
            cell.border = BORDER
            cell.alignment = WRAP


def build_reagents():
    reagents = json.loads((DATA / "reagents.json").read_text(encoding="utf-8"))
    groups = {g["id"]: g["name"] for g in json.loads((DATA / "groups.json").read_text(encoding="utf-8"))}

    wb = Workbook()

    # ---- 说明页
    ws = wb.active
    ws.title = "说明"
    lines = [
        ("「安芯」试剂台账（录入工作表）", TITLE_FONT),
        ("", None),
        ("用途：数据岗按本表录入，导出后即为 data/reagents.json。", NOTE_FONT),
        ("真源：data/reagents.json 是唯一真源。本表由 scripts/build_workbooks.py 从 JSON 反向生成。", NOTE_FONT),
        ("", None),
        ("列说明", HEAD_FONT),
        ("ID            必须形如 R-0001，全局唯一，不得复用。", NOTE_FONT),
        ("别名          俗名与分子式，用中文分号「；」分隔。", NOTE_FONT),
        ("CAS           查不到填 null；填了就一定要对。", NOTE_FONT),
        ("GHS类别       至少 1 条，用「；」分隔，写法如「氧化性液体-类别3」。", NOTE_FONT),
        ("存储组        必须是附录 B 的 10 个组之一；尚未分类填 null（该试剂将不参与组对判定）。", NOTE_FONT),
        ("危害描述      一句话，写学生看得懂的那个风险，不要抄 SDS 全文。", NOTE_FONT),
        ("数据来源      写清依据，供答辩追溯。", NOTE_FONT),
        ("已复核        第二人核对后填 TRUE。未复核的条目不会参与 G1 抽查。", NOTE_FONT),
        ("", None),
        ("红线：GHS 分类与 CAS 号必须能指到公开 SDS 或《危险化学品目录》，不确定就留 null 并在备注写明。", Font(name="微软雅黑", size=9, color="C00000")),
    ]
    for i, (text, font) in enumerate(lines, start=1):
        c = ws.cell(row=i, column=1, value=text)
        if font:
            c.font = font
    ws.column_dimensions["A"].width = 110

    # ---- 台账页
    ws2 = wb.create_sheet("台账")
    headers = ["ID", "名称", "别名（；分隔）", "CAS", "GHS类别（；分隔）",
               "存储组", "存储组名称", "危害描述", "数据来源", "已复核"]
    ws2.append(headers)
    for r in reagents:
        ws2.append([
            r["id"], r["name"], "；".join(r.get("aliases") or []), r.get("cas") or "null",
            "；".join(r.get("ghs") or []), r.get("storageGroup") or "null",
            groups.get(r.get("storageGroup") or "", "（未分类）"),
            r.get("hazardNote", ""), r.get("source", ""), bool(r.get("verified")),
        ])
    style_header(ws2, [10, 14, 22, 14, 38, 9, 14, 46, 30, 8])
    style_body(ws2)

    out = DATA / "reagents.xlsx"
    wb.save(out)
    print(f"[build] {out.relative_to(ROOT)}  ({len(reagents)} 条试剂)")


# ---------------------------------------------------------------- checklist
# 以下条目均为已核对的公开版本原文（2024 年版，多个高校镜像一致）。
# 化学安全章原文未能取得，故不录入 —— 不得凭印象补条款号。
CHECKLIST_ROWS = [
    ("5.1.1", "5.1 危险源辨识", "学校、院系、实验室层面建立危险源分布清单",
     "(36)清单内容须包括单位、房间、类别、数量、分级分类、责任人等信息", "A 可自动判定",
     "台账字段直接对应"),
    ("5.1.2", "5.1 危险源辨识", "涉及危险源的实验场所，须有明确的警示标识",
     "(37)涉及重要危险源的场所，有显著的警示标识", "B 半自动", "需现场拍照"),
    ("5.1.3", "5.1 危险源辨识", "建立针对重要危险源的风险管理和应急预案",
     "(38)建立风险分级分类管控方案……建立本单位实验室安全分级分类管理台账", "C 人工核查", "制度类"),
    ("6.1.1", "6.1 场所环境", "实验场所应张贴安全信息牌",
     "(47)每个房间门口挂有安全信息牌，信息包括：实验室分级分类结果、安全风险点的警示标识、安全责任人、涉及危险类别、防护措施和有效的应急联系电话等，并及时更新",
     "B 半自动", "应急电话可结构化"),
    ("6.2.1", "6.2 卫生与日常管理", "实验室分区应相对独立，布局合理",
     "(65)有毒有害实验区与学习区明确分开，合理布局", "C 人工核查", ""),
    ("6.3.2", "6.3 场所其他安全", "危险性实验室应配备急救物品",
     "(70)配备的药箱不得上锁，并定期检查药品是否在保质期内", "B 半自动", ""),
    ("7.2.1", "7.2 应急喷淋与洗眼装置", "存在燃烧、腐蚀等风险的实验区域，须配置应急喷淋和洗眼装置",
     "(77)应急喷淋和洗眼装置的区域有显著标志", "A 可自动判定", "对应应急卡「洗眼器位置」"),
    ("7.2.2", "7.2 应急喷淋与洗眼装置", "应急喷淋与洗眼装置安装合理，并能正常使用",
     "(78)应急喷淋安装地点与工作区域之间畅通，距离不超过30m……(80)洗眼装置接入生活用水管道，应至少以1.5L/min的流量供水",
     "A 可自动判定", "对应应急卡「最近洗眼器」"),
    ("7.2.3", "7.2 应急喷淋与洗眼装置", "定期对应急喷淋与洗眼装置进行维护",
     "(81)经常对应急喷淋与洗眼装置进行维护，无锈水、脏水，有检查记录", "B 半自动", ""),
    ("7.1.1", "7.1 消防设施", "实验室应配备合适的灭火设备，并定期开展使用训练",
     "(72)烟感报警器、灭火器、灭火毯、消防砂、消防喷淋等，应正常有效、方便取用", "B 半自动", "应急卡可列位置"),
    ("7.4.1", "7.4 门禁监控", "重点场所须安装门禁和监控设施，并有专人管理",
     "(88)关注重点场所，如剧毒品、病原微生物、放射源存放点、核材料等危险源的管理", "C 人工核查", ""),
    ("5.3.1", "5.3 安全隐患整改", "检查中发现的问题应以正式形式通知到相关负责人",
     "(43)通知的方式包括校网上公告、实验室安全简报、书面或电子的整改通知书等形式", "A 可自动判定",
     "对应隐患记录的「通知」环节"),
    ("5.3.2", "5.3 安全隐患整改", "院系须及时组织隐患整改",
     "(44)整改报告应在规定时间内提交学校管理部门。(45)如存在重大隐患，实验室应立即停止实验活动", "A 可自动判定",
     "对应隐患四态流转"),
]


def build_checklist():
    wb = Workbook()

    ws = wb.active
    ws.title = "说明"
    lines = [
        ("「安芯」检查项目表转录本说明", TITLE_FONT),
        ("", None),
        ("用途：为 rules.json / matrix.json 的 clause 字段提供唯一出处。", NOTE_FONT),
        ("", None),
        ("来源与版本", HEAD_FONT),
        ("依据文件：教育部《高等学校实验室安全检查项目表》。", NOTE_FONT),
        ("本表录入的是 2024 年版原文，取自多所高校实验室管理部门公开镜像，交叉比对一致：", NOTE_FONT),
        ("  https://sbc.qust.edu.cn/info/1067/7841.htm", NOTE_FONT),
        ("  https://www.lmyy.cn 系列镜像（黎明职业大学 2024-05-14 发布）", NOTE_FONT),
        ("  https://zcc.hbeu.edu.cn/info/1201/4932.htm", NOTE_FONT),
        ("版本提示：已有 2026 年版（2026-05 发布）。正式提交前应换成官方 2026 年版并重新核对条目编号。", Font(name="微软雅黑", size=9, color="C00000")),
        ("", None),
        ("已知缺口（必须补齐才能进 G1）", HEAD_FONT),
        ("「化学安全」整章原文未取得 —— 公开页面在第六章附近即被截断，无法取到该章条目。", Font(name="微软雅黑", size=9, color="C00000")),
        ("本表因此只录入第 5、6、7 章中与台账、标识、应急处置直接相关的条目，共 13 条。", NOTE_FONT),
        ("化学安全章的「危险化学品分类存放、禁止混存」类条目，是 C-01/C-02/C-03 三条规则的真正出处，", NOTE_FONT),
        ("需在 D2 结束前由内容岗从官方 PDF 补录，随后替换 rules.json 中的 TODO-占位。", NOTE_FONT),
        ("", None),
        ("一条重要更正", HEAD_FONT),
        ("经核对，2024 年版 8.1.1 是「实验室用电安全」（第 102 目），并非化学安全。", Font(name="微软雅黑", size=9, color="C00000")),
        ("因此不得按「第 8 章 = 化学安全」推断条目编号 —— 这正是规则里必须保留 TODO-占位的原因。", NOTE_FONT),
        ("", None),
        ("填写规则", HEAD_FONT),
        ("1. 必须逐字复制检查要点原文，不得改写、不得缩写。", NOTE_FONT),
        ("2. 序号列必须是原文的章节号（如 7.2.1），括号内数字是原文的检查要点序号（如 (78)）。", NOTE_FONT),
        ("3. 归入类别只填三种：A 可自动判定 / B 半自动 / C 人工核查。", NOTE_FONT),
        ("4. 拿不准的条目宁可留空，也不要凭印象填写 —— 编造条款号比留空危险得多。", NOTE_FONT),
    ]
    for i, (text, font) in enumerate(lines, start=1):
        c = ws.cell(row=i, column=1, value=text)
        if font:
            c.font = font
    ws.column_dimensions["A"].width = 118

    ws2 = wb.create_sheet("检查项目")
    ws2.append(["序号", "章节", "检查项目", "检查要点（原文）", "归入类别", "可用于", "备注"])
    for row in CHECKLIST_ROWS:
        ws2.append([row[0], row[1], row[2], row[3], row[4], row[5], ""])
    style_header(ws2, [10, 22, 40, 78, 14, 26, 18])
    style_body(ws2)

    out = DATA / "checklist.xlsx"
    wb.save(out)
    print(f"[build] {out.relative_to(ROOT)}  ({len(CHECKLIST_ROWS)} 条已核对条目；化学安全章待补)")


if __name__ == "__main__":
    force = "--force" in sys.argv[1:]
    for name, builder in (("reagents.xlsx", build_reagents), ("checklist.xlsx", build_checklist)):
        target = DATA / name
        if target.exists() and not force:
            print(f"[build] 跳过 {name}（已存在；要覆盖请加 --force）")
            continue
        builder()
