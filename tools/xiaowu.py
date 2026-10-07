#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小五 v1.0 — TVBox 配置抓取/转换/聚合工具
========================================
对标 "TVBox 全能一体化工具" 的本地命令行实现。

功能:
  抓取: 从 URL 抓取远程配置(支持多形态:JSON / UTF-8 BOM / 伪装图片 / base64 / 加密头)
  转换: 统一转换为标准 TVBox JSON 配置
  校验: 识别失败源(HTML反爬 / 真图片 / 坏JSON),输出健康报告
  聚合: 去重合并多个源的 sites/parses/ads,生成聚合配置

用法:
  python3 xiaowu.py fetch   <url> [--name 名字]     # 抓取单个源并转换
  python3 xiaowu.py check   <urls.txt>              # 批量健康检查
  python3 xiaowu.py merge   <src1.json> <src2.json> # 去重合并
  python3 xiaowu.py run     <list.txt> --out out.json  # 一条龙:抓取+合并+输出
"""
import sys, os, json, re, base64, ssl, argparse
import urllib.request, concurrent.futures

SSL_CTX = ssl.create_default_context()
SSL_CTX.check_hostname = False
SSL_CTX.verify_mode = ssl.CERT_NONE

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120 Safari/537.36'
HEADERS = {'User-Agent': UA, 'Referer': 'https://www.baidu.com/'}
TIMEOUT = 15

# ---------------- 抓取 ----------------

def http_get(url, timeout=TIMEOUT):
    """抓取 URL 内容,自动处理 UA/跳转"""
    req = urllib.request.Request(url, headers=HEADERS)
    with urllib.request.urlopen(req, timeout=timeout, context=SSL_CTX) as r:
        data = r.read()
        final_url = r.geturl()
        return data, final_url

# ---------------- 转换/识别 ----------------

def looks_like_png(data):
    return data[:8] == b'\x89PNG\r\n\x1a\n'

def looks_like_jpg(data):
    return data[:3] == b'\xff\xd8\xff'

def looks_like_gif(data):
    return data[:6] in (b'GIF87a', b'GIF89a')

def strip_bom(data):
    if data[:3] == b'\xef\xbb\xbf':
        return data[3:]
    return data

def try_decode_json(data):
    """尝试把字节解析为标准 TVBox JSON。返回 (config_dict, info) 或 (None, 原因)"""
    raw = strip_bom(data)
    # 形态1: 纯 JSON
    for enc in ('utf-8', 'gbk', 'latin-1'):
        try:
            d = json.loads(raw.decode(enc))
            if isinstance(d, dict):
                return d, 'json'
        except Exception:
            pass
    # 形态2: base64 编码的 JSON(头部可能有前缀如 SWKYkz1W**)
    text = raw.decode('utf-8', 'ignore').strip()
    m = re.search(r'([A-Za-z0-9+/=]{100,})', text)
    if m:
        try:
            b = base64.b64decode(m.group(1))
            d = json.loads(b.decode('utf-8'))
            if isinstance(d, dict):
                return d, 'base64'
        except Exception:
            pass
    # 形态3: 加密头 `xxx**base64`(如东篱的 SWKYkz1W**ewogICJsb2dv...)
    m2 = re.search(r'^([A-Za-z0-9]+)\*\*(.{100,})$', text, re.M)
    if m2:
        try:
            b = base64.b64decode(m2.group(2))
            d = json.loads(b.decode('utf-8'))
            if isinstance(d, dict):
                return d, 'encrypted-base64'
        except Exception:
            pass
    return None, 'not-json'

def classify(data):
    """分类抓取内容:json / png-json / binary-img / html / text"""
    if looks_like_png(data) or looks_like_jpg(data) or looks_like_gif(data):
        d, info = try_decode_json(data)
        if d:
            return 'img-json', d, info
        return 'binary-img', None, 'real image'
    d, info = try_decode_json(data)
    if d:
        return 'json', d, info
    head = data[:200].decode('utf-8', 'ignore').lower()
    if '<html' in head or '<!doctype' in head:
        return 'html-block', None, 'anti-bot html'
    return 'text', None, 'unknown text'

def is_valid_tvbox(d):
    """判断是不是可用的 TVBox 配置(必须含 sites 且非空)"""
    if not isinstance(d, dict):
        return False
    sites = d.get('sites')
    if not isinstance(sites, list) or not sites:
        return False
    return True

# ---------------- 聚合/去重 ----------------

def normalize_site(s):
    """归一化 site:以 (api, key) 为唯一键"""
    api = s.get('api', '')
    key = s.get('key', '')
    if isinstance(api, str) and api.startswith('csp_'):
        api = 'csp_' + api[4:].lower()
    return (api, key)

def merge_configs(configs, base=None):
    """合并多个配置:去重 sites/parses,合并 ads/rules 去重。返回新配置"""
    merged = {
        'spider': None,
        'sites': [],
        'parses': [],
        'ads': [],
        'rules': [],
    }
    seen_sites, seen_parses, seen_ads, seen_rules = set(), set(), set(), set()
    spider = None

    all_cfgs = ([base] if base else []) + configs
    for cfg in all_cfgs:
        if not cfg:
            continue
        if not spider and cfg.get('spider'):
            spider = cfg['spider']
        for s in cfg.get('sites', []):
            if not isinstance(s, dict):
                continue
            uid = normalize_site(s)
            if uid in seen_sites:
                continue
            seen_sites.add(uid)
            merged['sites'].append(s)
        for p in cfg.get('parses', []):
            if isinstance(p, dict):
                uid = (p.get('name'), p.get('type'), p.get('url'))
                if uid not in seen_parses:
                    seen_parses.add(uid)
                    merged['parses'].append(p)
        for a in cfg.get('ads', []):
            if a not in seen_ads:
                seen_ads.add(a)
                merged['ads'].append(a)
        for r in cfg.get('rules', []):
            key = json.dumps(r, ensure_ascii=False) if isinstance(r, (dict, list)) else str(r)
            if key not in seen_rules:
                seen_rules.add(key)
                merged['rules'].append(r)
        # 保留额外字段
        for k in ('doh', 'flags', 'ijk', 'wallpaper', 'logo'):
            if cfg.get(k) and k not in merged:
                merged[k] = cfg[k]

    if spider:
        merged['spider'] = spider
    # 只保留非空数组
    merged = {k: v for k, v in merged.items() if v}
    return merged

# ---------------- 单源抓取 ----------------

def fetch_one(url, name=None, timeout=TIMEOUT):
    """抓取+转换+校验单个源,返回报告 dict"""
    report = {'name': name or url, 'url': url, 'ok': False}
    try:
        data, final = http_get(url, timeout)
        report['size'] = len(data)
        report['final_url'] = final
        kind, cfg, info = classify(data)
        report['kind'] = kind
        report['info'] = info
        if kind in ('json', 'img-json'):
            if is_valid_tvbox(cfg):
                report['ok'] = True
                report['sites'] = len(cfg.get('sites', []))
                report['config'] = cfg
            else:
                report['info'] = 'json but no valid sites'
        elif kind == 'binary-img':
            report['info'] = 'real image (bad source)'
        elif kind == 'html-block':
            report['info'] = 'anti-bot page (need UA/JS)'
    except Exception as e:
        report['error'] = str(e)[:100]
    return report

# ---------------- CLI ----------------

def cmd_fetch(args):
    r = fetch_one(args.url, args.name)
    print(json.dumps(r, ensure_ascii=False, indent=1, default=str)[:2000])
    if r.get('ok') and r.get('config'):
        out = args.out or (args.name + '.json' if args.name else 'out.json')
        json.dump(r['config'], open(out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
        print(f'\n✅ 已保存 {out}')

def cmd_check(args):
    urls = [l.strip() for l in open(args.urls, encoding='utf-8') if l.strip() and not l.startswith('#')]
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(lambda u: fetch_one(u), urls))
    ok = [r for r in results if r.get('ok')]
    bad = [r for r in results if not r.get('ok')]
    print(f'总 {len(results)} | 可用 {len(ok)} | 失败 {len(bad)}\n')
    for r in ok:
        print(f"  ✅ {r['name']} | {r['kind']} | {r['sites']}站 | {r['size']}B")
    for r in bad:
        print(f"  ❌ {r['name']} | {r.get('kind','?')} | {r.get('info') or r.get('error','')}")
    json.dump(results, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, default=str, indent=1)

def cmd_merge(args):
    cfgs = []
    for p in args.srcs:
        try:
            cfgs.append(json.load(open(p, encoding='utf-8')))
        except Exception as e:
            print(f'⚠️ 无法读取 {p}: {e}')
    base = None
    if args.base:
        base = json.load(open(args.base, encoding='utf-8'))
    merged = merge_configs(cfgs, base)
    json.dump(merged, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'✅ 合并完成: {len(merged.get("sites",[]))} sites, {len(merged.get("parses",[]))} parses, {len(merged.get("ads",[]))} ads')
    print(f'   已保存 {args.out}')

def cmd_run(args):
    """一条龙:抓取列表所有源 -> 合并 -> 输出"""
    lines = [l.strip() for l in open(args.list, encoding='utf-8') if l.strip() and not l.startswith('#')]
    cfgs = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(lambda u: fetch_one(u), lines))
    ok = [r for r in results if r.get('ok')]
    fail = [r for r in results if not r.get('ok')]
    for r in ok:
        cfgs.append(r['config'])
        print(f"  ✅ {r['name']} | {r['sites']}站")
    for r in fail:
        print(f"  ❌ {r['name']} | {r.get('info') or r.get('error','')}")
    if not cfgs:
        print('没有可用源,退出')
        sys.exit(1)
    base = None
    if args.base:
        base = json.load(open(args.base, encoding='utf-8'))
    merged = merge_configs(cfgs, base)
    json.dump(merged, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\n✅ 聚合完成: {len(merged.get("sites",[]))} sites | {len(merged.get("parses",[]))} parses | {len(merged.get("ads",[]))} ads')
    print(f'   已保存 {args.out}')

def main():
    p = argparse.ArgumentParser(description='小五 — TVBox 配置抓取/转换/聚合工具')
    sub = p.add_subparsers(dest='cmd')

    pf = sub.add_parser('fetch', help='抓取单个源')
    pf.add_argument('url'); pf.add_argument('--name'); pf.add_argument('--out')
    pf.set_defaults(fn=cmd_fetch)

    pc = sub.add_parser('check', help='批量健康检查')
    pc.add_argument('urls'); pc.add_argument('--out', default='health.json'); pc.add_argument('--workers', type=int, default=10)
    pc.set_defaults(fn=cmd_check)

    pm = sub.add_parser('merge', help='合并多个本地配置')
    pm.add_argument('srcs', nargs='+'); pm.add_argument('--base'); pm.add_argument('--out', default='merged.json')
    pm.set_defaults(fn=cmd_merge)

    pr = sub.add_parser('run', help='一条龙:抓取+合并')
    pr.add_argument('list'); pr.add_argument('--base'); pr.add_argument('--out', default='tvbox_new.json'); pr.add_argument('--workers', type=int, default=10)
    pr.set_defaults(fn=cmd_run)

    args = p.parse_args()
    if not args.cmd:
        p.print_help(); sys.exit(0)
    args.fn(args)

if __name__ == '__main__':
    main()
