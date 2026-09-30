#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
源仓库健康巡检脚本 v2
用途: 检查 yangmi2026 仓库所有配置里的站点/源可达性, 生成健康报告
由 GitHub Actions 每天定时运行
"""
import json
import re
import sys
import time
import urllib.request
import urllib.error
import ssl
import os
from urllib.parse import urlparse

TIMEOUT = 8
SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

CONFIG_FILES = [
    "tvbox.json", "tvbox_2.json", "tvbox_py.json",
    "tingshu.json", "tingshu_2.json",
    "music.json", "live.json", "short.json",
]

# 明显不该直接探测的目标
SKIP_PATTERNS = [
    "127.0.0.1", "localhost", "wget.la", "raw.githubusercontent",
    "githubusercontent", "mpimg.cn",  # 下载站
]

def fetch(url, timeout=TIMEOUT):
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Linux; Android 13) AppleWebKit/537.36",
        "Accept": "*/*",
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as resp:
            body = resp.read(2048)
            return resp.status, resp.geturl(), len(body)
    except urllib.error.HTTPError as e:
        return e.code, url, 0
    except Exception:
        return None


def skip_target(url):
    return any(p in url for p in SKIP_PATTERNS)


def extract_hosts_from_ext(ext):
    hosts = []
    if isinstance(ext, str):
        if ext.startswith("http"):
            hosts.append(ext)
    elif isinstance(ext, dict):
        for k, v in ext.items():
            if isinstance(v, str) and v.startswith("http"):
                hosts.append(v)
    return hosts


def extract_api_url(api):
    if isinstance(api, str) and api.startswith("http"):
        return api
    return None


def probe(url):
    parsed = urlparse(url)
    if not parsed.scheme:
        url = "https://" + url
    result = fetch(url)
    if result is None:
        return "❌ 超时/无法连接"
    status, final_url, body_len = result
    if status == 200:
        return f"✅ 200 (body {body_len}B)"
    return f"⚠️ HTTP {status}"


def scan_py_js_domains():
    """从 js/ py/ 目录源码里提取 http(s) 域名, 供 csp 源参考"""
    domains = {}
    for folder in ["js", "py"]:
        if not os.path.isdir(folder):
            continue
        for fname in os.listdir(folder):
            fpath = os.path.join(folder, fname)
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    text = f.read()
                found = set(re.findall(r"https?://([\w.-]+\.[a-z]{2,})", text))
                # 过滤明显无关的
                found = {d for d in found if not any(
                    x in d for x in ["github", "wget", "example", "127.", "localhost", "schema"])}
                if found:
                    domains[fname] = sorted(found)[:5]
            except Exception:
                pass
    return domains


def main():
    report_lines = []
    report_lines.append("# 源仓库健康巡检报告\n")
    report_lines.append(f"> 自动生成时间: {time.strftime('%Y-%m-%d %H:%M:%S')} UTC")
    report_lines.append("> 由 GitHub Actions 每天定时运行, 检测各配置文件的站点/源可达性\n")

    rows = []
    dead_rows = []
    checked = 0
    skipped = 0

    for cfg in CONFIG_FILES:
        try:
            with open(cfg, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            dead_rows.append((cfg, "-", "-", f"配置解析失败: {e}"))
            continue

        sites = data.get("sites", []) if isinstance(data, dict) else []
        if not sites:
            continue
        for s in sites:
            key = s.get("key", "?")
            name = s.get("name", key)
            api = s.get("api", "")
            ext = s.get("ext", "")

            targets = []
            api_url = extract_api_url(api)
            if api_url:
                targets.append(("api脚本", api_url))
            for h in extract_hosts_from_ext(ext):
                targets.append(("ext域名", h))

            # 过滤要跳过的
            real_targets = [(l, t) for l, t in targets if not skip_target(t)]
            skipped += len(targets) - len(real_targets)

            if not real_targets:
                rows.append((cfg, name, "内置/跳过", "-", "⚪ 内置蜘蛛/无公网目标"))
                continue

            checked += 1
            results = []
            has_bad = False
            for label, t in real_targets:
                r = probe(t)
                results.append(f"{label}:{r}")
                if "❌" in r or "⚠️" in r:
                    has_bad = True
            joined = "; ".join(results)
            rows.append((cfg, name, str(s.get("type", "")), real_targets[0][1][:55], joined))
            if has_bad:
                dead_rows.append((cfg, name, str(s.get("type", "")), real_targets[0][1][:55], joined))

    # 汇总
    report_lines.append("## 📊 汇总\n")
    report_lines.append(f"- 探测站点数: **{checked}**")
    report_lines.append(f"- 有异常站点数: **{len(dead_rows)}**")
    report_lines.append(f"- 跳过本地/代理目标数: {skipped}")
    report_lines.append(f"- 巡检时间: {time.strftime('%Y-%m-%d %H:%M:%S')} UTC\n")

    if dead_rows:
        report_lines.append("## ⚠️ 异常站点\n")
        report_lines.append("| 配置文件 | 站点 | 类型 | 目标 | 结果 |")
        report_lines.append("|---|---|---|---|---|")
        for row in dead_rows:
            report_lines.append("| " + " | ".join(str(x) for x in row) + " |")
        report_lines.append("")

    report_lines.append("## 📋 全部站点\n")
    report_lines.append("| 配置文件 | 站点 | 类型 | 目标 | 结果 |")
    report_lines.append("|---|---|---|---|---|")
    for row in rows:
        report_lines.append("| " + " | ".join(str(x) for x in row) + " |")

    # 附加: js/py 源码里的域名(供人工参考)
    py_js_domains = scan_py_js_domains()
    if py_js_domains:
        report_lines.append("\n## 🔍 js/py 源码内含域名(供参考)\n")
        for fname, doms in py_js_domains.items():
            report_lines.append(f"- **{fname}**: {' '.join(doms)}")

    report = "\n".join(report_lines)
    with open("HEALTH_REPORT.md", "w", encoding="utf-8") as f:
        f.write(report)
    print(report[:3500])
    print("\n... (报告已写入 HEALTH_REPORT.md)")
    sys.exit(1 if dead_rows else 0)


if __name__ == "__main__":
    main()
