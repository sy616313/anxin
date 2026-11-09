#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""把 data/ 与 engine/ 打包进小程序。

小程序运行时读不到仓库路径，也不能 require 工程根目录之外的文件，因此必须：
  1. 把 data/*.json 编译成 miniprogram/data/dataset.js（可被 require 的 JS 模块）
  2. 把 engine/index.js 拷贝到 miniprogram/engine/index.js

改完数据必须跑一次，否则小程序读到的还是旧数据（任务书 R-04）。
validate_data.py 校验通过后会自动调用本脚本。

产物：
  miniprogram/data/dataset.js
  miniprogram/engine/index.js
"""

import hashlib
import json
import shutil
import sys
from pathlib import Path

try:  # Windows 控制台默认 GBK，强制 UTF-8 以免中文乱码
    sys.stdout.reconfigure(encoding="utf-8", line_buffering=True)
except (AttributeError, OSError):
    pass

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
MP = ROOT / "miniprogram"
OUT_DATA = MP / "data" / "dataset.js"
OUT_ENGINE = MP / "engine" / "index.js"
SRC_ENGINE = ROOT / "engine" / "index.js"

FILES = {
    "reagents": "reagents.json",
    "groups": "groups.json",
    "matrix": "matrix.json",
    "rules": "rules.json",
    "cabinets": "cabinets.json",
    "findings": "findings.json",
}

BANNER = (
    "// 由 scripts/sync_data.py 自动生成，请勿手改。\n"
    "// 改动请改仓库中的源文件，然后运行 python scripts/validate_data.py\n"
)


def main() -> int:
    payload = {}
    digest = hashlib.sha256()

    for key, filename in FILES.items():
        path = DATA / filename
        if not path.exists():
            print(f"[sync] 缺少 {filename}", file=sys.stderr)
            return 1
        raw = path.read_bytes()
        digest.update(filename.encode("utf-8"))
        digest.update(raw)
        payload[key] = json.loads(raw.decode("utf-8"))

    if not SRC_ENGINE.exists():
        print(f"[sync] 缺少 {SRC_ENGINE.relative_to(ROOT)}", file=sys.stderr)
        return 1
    digest.update(SRC_ENGINE.read_bytes())

    version = digest.hexdigest()[:12]

    # 1) 数据模块
    body = dict(payload)
    body_ordered = {"dataVersion": version}
    body_ordered.update(body)
    OUT_DATA.parent.mkdir(parents=True, exist_ok=True)
    OUT_DATA.write_text(
        BANNER
        + f"// dataVersion: {version}\n"
        + "module.exports = "
        + json.dumps(body_ordered, ensure_ascii=False, separators=(",", ":"))
        + ";\n",
        encoding="utf-8",
    )

    # 2) 引擎拷贝（小程序不能 require 工程根目录之外的文件）
    OUT_ENGINE.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(SRC_ENGINE, OUT_ENGINE)

    counts = ", ".join(
        f"{k}={len(v) if isinstance(v, list) else len(v.get('pairs', []))}"
        for k, v in payload.items()
    )
    print(f"[sync] miniprogram/data/dataset.js    版本 {version}")
    print(f"[sync] miniprogram/engine/index.js    已同步")
    print(f"[sync] 内容：{counts}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
