#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
上游规则源监控脚本
=================
每个周期只做三件事：
1. 用 Firecrawl 逐个抓取 targets.json 里的上游分类文件
   （v2fly/domain-list-community 的 data/<分类>，
   正是 streaming-cn / loc-cn / douyin 三个标签构建时依赖的上游）；
2. 给抓到的正文算 SHA256 指纹，和 hashes.json 里存的上次指纹对比；
3. 输出中文报告 report.md，并把新指纹写回 hashes.json。

只用 Python 标准库，runner 上零依赖、不用装任何包。
"""

import hashlib
import json
import os
import sys
import time
import urllib.request

# --- 路径约定 ---
# 脚本放在 .github/scripts/，监控数据放在 .github/upstream-monitor/，
# 这样仓库根目录保持干净。
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MONITOR_DIR = os.path.join(BASE_DIR, "upstream-monitor")
TARGETS_FILE = os.path.join(MONITOR_DIR, "targets.json")
HASHES_FILE = os.path.join(MONITOR_DIR, "hashes.json")
REPORT_FILE = os.path.join(MONITOR_DIR, "report.md")

FIRECRAWL_API = "https://api.firecrawl.dev/v1/scrape"
MAX_RETRIES = 2   # 每个目标失败时最多重试 2 次：过滤网络抖动造成的误报
SLEEP_BETWEEN = 6  # 目标之间歇 6 秒：Firecrawl 免费档约每分钟限流 20 次，
                   # 歇太短会吃 429（2026-09-30 第一次运行已踩过坑）
RETRY_429_WAIT = 30  # 吃到 429（限流）时重试前等待的基数：30 秒 × 第几次重试


def log(msg):
    """打印日志：Actions 页面里每一步的输出就是从这里看的，排错全靠它。"""
    print(msg, flush=True)


def sha256_hex(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def scrape(api_key, url):
    """调 Firecrawl 抓一个 URL，返回正文字符串；失败时抛异常。"""
    payload = json.dumps({
        "url": url,
        "formats": ["markdown"],
        # Firecrawl 会缓存同一 URL 约两天；maxAge=0 让它每次都抓最新，
        # 否则"每日监控"可能连续两天拿到同一份缓存。
        "maxAge": 0,
    }).encode("utf-8")

    last_err = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            req = urllib.request.Request(
                FIRECRAWL_API,
                data=payload,
                headers={
                    "Authorization": "Bearer " + api_key,
                    "Content-Type": "application/json",
                },
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=120) as resp:
                body = json.loads(resp.read().decode("utf-8"))
            if not body.get("success"):
                raise RuntimeError("Firecrawl 返回 success=false：%s" % body.get("error"))
            data = body.get("data") or {}
            meta = data.get("metadata") or {}
            # 坑点：源站 404 时 Firecrawl 照样 success=true（照常扣 1 点），
            # 只是 metadata.statusCode 是 404。必须看源站状态码，
            # 不然会把 GitHub 的 404 页面当成"上游更新了"。
            status = meta.get("statusCode")
            if status != 200:
                raise RuntimeError("源站返回 HTTP %s，目标 URL 可能写错或被移动" % status)
            markdown = (data.get("markdown") or "").strip()
            if not markdown:
                raise RuntimeError("抓到的正文是空的")
            return markdown
        except Exception as e:  # noqa: BLE001 —— 监控脚本里单个目标失败要记下来、继续抓下一个
            last_err = e
            log("    第 %d 次尝试失败：%s" % (attempt, e))
            if "429" in str(e):
                # 429 是 Firecrawl 的限流：硬撞只会被继续拦，
                # 按 30 秒 × 次数退避等待，让配额恢复后再试
                wait = RETRY_429_WAIT * attempt
                log("    触发限流，等待 %d 秒后再试……" % wait)
                time.sleep(wait)
            else:
                time.sleep(3)
    raise last_err


def main():
    api_key = os.environ.get("FIRECRAWL_API_KEY", "").strip()
    if not api_key:
        # 工作流里用 ${{ secrets.FIRECRAWL_API_KEY }} 传入；
        # 看到这条报错，先去仓库 Settings → Secrets 里把密钥加上。
        log("❌ 没读到 FIRECRAWL_API_KEY，请在仓库 Settings → Secrets and variables → Actions 里添加。")
        return 2

    with open(TARGETS_FILE, encoding="utf-8") as f:
        targets = json.load(f)
    old_hashes = {}
    if os.path.exists(HASHES_FILE):
        with open(HASHES_FILE, encoding="utf-8") as f:
            old_hashes = json.load(f)
    baseline = not old_hashes  # 指纹文件是空的 = 第一次跑，只建基线、不发 Issue

    log("共 %d 个监控目标，开始抓取……" % len(targets))
    results = []  # 每个目标的检查结果
    new_hashes = dict(old_hashes)
    failed = 0

    for t in targets:
        name, url = t["name"], t["url"]
        feeds = "、".join(t.get("feeds", []))
        log("  [%s] 抓取 %s" % (name, url))
        try:
            text = scrape(api_key, url)
        except Exception as e:  # noqa: BLE001
            log("  [%s] ❌ 抓取失败：%s" % (name, e))
            results.append({"name": name, "feeds": feeds, "status": "抓取失败", "detail": str(e)})
            failed += 1
            continue
        digest = sha256_hex(text)
        old = old_hashes.get(name)
        if old is None:
            log("  [%s] 🆕 新目标，记录基线指纹" % name)
            results.append({"name": name, "feeds": feeds, "status": "新建基线", "detail": ""})
        elif old != digest:
            log("  [%s] 🔄 内容变了！上游有更新" % name)
            results.append({"name": name, "feeds": feeds, "status": "有更新", "detail": ""})
        else:
            log("  [%s] ✅ 无变化" % name)
            results.append({"name": name, "feeds": feeds, "status": "无变化", "detail": ""})
        new_hashes[name] = digest
        time.sleep(SLEEP_BETWEEN)

    changed = [r for r in results if r["status"] == "有更新"]

    # --- 写中文报告：既是 Issue 正文，也是排错时先看的东西 ---
    date_str = time.strftime("%Y-%m-%d")
    lines = [
        "# 上游规则源监控报告（%s）" % date_str,
        "",
        "监控目标：v2fly/domain-list-community 的 data/<分类> 文件，",
        "正是你 `streaming-cn` / `loc-cn` / `douyin` 三个标签构建时依赖的上游。",
        "",
        "| 上游分类 | 影响本地标签 | 状态 |",
        "|---|---|---|",
    ]
    icon = {"无变化": "✅", "有更新": "🔄", "新建基线": "🆕", "抓取失败": "❌"}
    for r in results:
        lines.append("| %s | %s | %s %s |" % (r["name"], r["feeds"], icon[r["status"]], r["status"]))
    if changed:
        lines.append("")
        lines.append("以下上游有更新，下次每日构建会自动拉取最新内容：")
        for r in changed:
            lines.append("- %s（影响：%s）" % (r["name"], r["feeds"]))
    if failed:
        lines.append("")
        lines.append("⚠️ 有 %d 个目标抓取失败，详情看本次运行的日志。" % failed)
    with open(REPORT_FILE, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    # --- 存新指纹：只有抓成功的才更新，失败的目标保留旧指纹 ---
    with open(HASHES_FILE, "w", encoding="utf-8") as f:
        json.dump(new_hashes, f, indent=2, ensure_ascii=False)
        f.write("\n")

    # --- 告诉工作流"有没有变化"：下游步骤靠这两个输出决定要不要提交/发 Issue ---
    gh_out = os.environ.get("GITHUB_OUTPUT")
    if gh_out:
        with open(gh_out, "a", encoding="utf-8") as f:
            f.write("changed=%s\n" % ("true" if changed else "false"))
            f.write("baseline=%s\n" % ("true" if baseline else "false"))

    log("检查完毕：%d 个有更新，%d 个抓取失败。" % (len(changed), failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
