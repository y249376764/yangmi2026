#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
小五 v2.0 — TVBox 配置抓取/转换/聚合工具(升级版)
==============================================
对标 "TVBox 全能一体化工具" 的本地命令行实现。

v2.0 升级:
  ★ 多形态解码器 v3:破解 7+ 种非标准源
    - 标准 JSON / UTF-8 BOM
    - 伪装图片(PNG头但内容是JSON)
    - JS 注释头(// 或 /* */,含中部注释)
    - 未加引号键 {副标题: "x"} / 键名尾部残留引号 "副标题":
    - 键名后多余引号 "副标题"":
    - 字符串内裸控制字符(真实换行)
    - base64 编码 / 加密头 SWKYkz1W**base64
    - 真图片(1x1水印等)识别为坏源
  ★ localize 命令:对标原工具 D 任务(全量本地化)
    - 把远程 spider jar 下载到本地,spider 字段改本地路径
    - 把远程 JS api 源下载到本地
    - 生成离线可用配置

用法:
  python3 xiaowu.py fetch   <url> [--name 名字]     # 抓取单个源并转换(多形态)
  python3 xiaowu.py check   <urls.txt>              # 批量健康检查
  python3 xiaowu.py merge   <src1.json> <src2.json> # 去重合并
  python3 xiaowu.py run     <list.txt> --base old.json --out out.json  # 抓取+合并
  python3 xiaowu.py localize <config.json> --out-dir local/  # 全量本地化
"""
import sys, os, json, re, base64, ssl, argparse, hashlib
import urllib.request, concurrent.futures
try:
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import unpad
    HAS_AES = True
except ImportError:
    HAS_AES = False

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
        return data, r.geturl()

# ================= v3 多形态解码器 =================

def strip_line_comments(s):
    """剥掉字符串外的 // 行注释(不会误伤 http://)"""
    out = []; in_str = False; esc = False; i = 0; n = len(s)
    while i < n:
        ch = s[i]
        if esc: out.append(ch); esc = False; i += 1; continue
        if in_str:
            if ch == '\\': out.append(ch); esc = True; i += 1; continue
            if ch == '"': in_str = False
            out.append(ch); i += 1; continue
        if ch == '"': in_str = True; out.append(ch); i += 1; continue
        if ch == '/' and i+1 < n and s[i+1] == '/':
            while i < n and s[i] != '\n': i += 1
            out.append('\n'); continue
        out.append(ch); i += 1
    return ''.join(out)

def fix_json_quirks(s):
    """修复 TVBox 源常见非标准 JSON:
    1. 未加引号键 {副标题: "x"} -> {"副标题": "x"}
    2. 键名尾部残留引号 {副标题": -> {"副标题":
    3. 键名后多余引号 "副标题"": -> "副标题":
    """
    out = []; in_str = False; esc = False; i = 0; n = len(s)
    while i < n:
        ch = s[i]
        if esc: out.append(ch); esc = False; i += 1; continue
        if in_str:
            if ch == '\\': out.append(ch); esc = True; i += 1; continue
            if ch == '"':
                in_str = False; out.append(ch)
                j = i + 1
                while j < n and s[j] in ' \t\r\n': j += 1
                if j < n and s[j] == '"':
                    k = j + 1
                    while k < n and s[k] in ' \t\r\n': k += 1
                    if k < n and s[k] == ':':
                        i = j + 1; continue
                i += 1; continue
            out.append(ch); i += 1; continue
        if ch == '"': in_str = True; out.append(ch); i += 1; continue
        if ch in '{,':
            j = i + 1
            while j < n and s[j] in ' \t\r\n': j += 1
            if j < n and s[j] not in '"}],{[ ':
                k = j
                while k < n and s[k] != ':' and s[k] not in '\n\r\t ,]}': k += 1
                if k < n and s[k] == ':':
                    key = s[j:k]
                    if key.endswith('"'): key = key[:-1]
                    out.append(ch); out.append(s[i+1:j])
                    out.append('"'); out.append(key); out.append('"')
                    i = k; continue
        out.append(ch); i += 1
    return ''.join(out)

def clean_ctrl_chars(s):
    """字符串值内的裸控制字符(真实换行等)替换为空格"""
    out = []; in_str = False; esc = False
    for ch in s:
        if esc: out.append(ch); esc = False; continue
        if ch == '\\' and in_str: out.append(ch); esc = True; continue
        if ch == '"': in_str = not in_str; out.append(ch); continue
        if in_str and ch in '\n\r\t': out.append(' '); continue
        out.append(ch)
    return ''.join(out)

def smart_decode(data):
    """终极解码 v3: BOM/注释/控制字符/裸键/多余引号/base64/加密头 全处理。
    返回 (config_dict, 识别方式) 或 (None, None)"""
    raw = data
    if raw[:3] == b'\xef\xbb\xbf': raw = raw[3:]
    txt = raw.decode('utf-8', 'ignore')
    # 先试魔数加密格式 $#xxx#$ (南风/潇洒 的 AES-CBC 配置加密)
    d, info = decode_magic_encrypted(txt)
    if d:
        return d, info
    txt = strip_line_comments(txt)
    txt = re.sub(r'/\*.*?\*/', '', txt, flags=re.S)
    txt = txt.strip()
    for t in (txt, fix_json_quirks(txt), clean_ctrl_chars(fix_json_quirks(txt))):
        try:
            d = json.loads(t)
            if isinstance(d, dict):
                return d, 'json'
        except Exception:
            pass
    # 加密头 `SWKYkz1W**base64`
    m2 = re.search(r'^([A-Za-z0-9_]+)\*\*(.{100,})', txt, re.M)
    if m2:
        try:
            d, info = smart_decode(base64.b64decode(m2.group(2)))
            if d: return d, 'enc-b64->' + info
        except Exception:
            pass
    # 纯 base64
    m3 = re.search(r'([A-Za-z0-9+/=]{200,})', txt)
    if m3:
        try:
            d, info = smart_decode(base64.b64decode(m3.group(1)))
            if d: return d, 'b64->' + info
        except Exception:
            pass
    return None, None

def decode_magic_encrypted(content):
    """破解魔数加密格式: `$#KEY#$ + hex密文 + 尾部时间戳`
    算法(源自 @whyun/tv-tools + 南风XQ.json 逆向):
    - 内容以 '2423'(= '$#') 开头
    - 密文 = 第一个 '2324'(= '#$') 之后 到 末尾-26 的 hex
    - key = 魔数中间文本(如 '367') 右补 '0' 到 16 字节
    - iv  = 尾部 13 位时间戳 右补 '0' 到 16 字节
    - AES-128-CBC 解密
    返回 (config_dict, 'magic-aes-cbc') 或 (None, None)"""
    if not HAS_AES or not content.strip().startswith('2423'):
        return None, None
    try:
        content = content.strip()
        idx = content.index('2324')
        data_hex = content[idx+4 : len(content)-26]
        # 魔数中间文本(明文部分)
        decoded = bytes.fromhex(content).decode('utf-8', 'ignore').lower()
        if '$#' not in decoded or '#$' not in decoded:
            return None, None
        key_raw = decoded[decoded.index('$#')+2 : decoded.index('#$')]
        iv_raw = decoded[len(decoded)-13:]
        key = (key_raw + '0'*16)[:16]
        iv = (iv_raw + '0'*16)[:16]
        cipher = AES.new(key.encode(), AES.MODE_CBC, iv.encode())
        dec = cipher.decrypt(bytes.fromhex(data_hex))
        plain = unpad(dec, 16)
        txt = plain.decode('utf-8', 'ignore')
        # 剥注释 + 修复非标准 JSON 后解析
        clean = strip_line_comments(txt).strip()
        for t in (clean, fix_json_quirks(clean), clean_ctrl_chars(fix_json_quirks(clean))):
            try:
                js = t.index('{')
                cfg = json.loads(t[js:])
                if isinstance(cfg, dict) and cfg.get('sites'):
                    return cfg, 'magic-aes-cbc(key=' + key_raw + ')'
            except Exception:
                continue
    except Exception:
        pass
    return None, None

def classify(data):
    """分类抓取内容"""
    if data[:8] == b'\x89PNG\r\n\x1a\n' or data[:3] == b'\xff\xd8\xff' or data[:6] in (b'GIF87a', b'GIF89a'):
        d, info = smart_decode(data)
        if d: return 'img-json', d, info
        return 'binary-img', None, 'real image'
    d, info = smart_decode(data)
    if d: return 'json', d, info
    head = data[:200].decode('utf-8', 'ignore').lower()
    if '<html' in head or '<!doctype' in head:
        return 'html-block', None, 'anti-bot html'
    return 'text', None, 'unknown text (maybe custom encrypted)'

def is_valid_tvbox(d):
    if not isinstance(d, dict): return False
    sites = d.get('sites')
    return isinstance(sites, list) and bool(sites)

# ---------------- 聚合/去重 ----------------

def normalize_site(s):
    api = s.get('api', '')
    key = s.get('key', '')
    if isinstance(api, str) and api.startswith('csp_'):
        api = 'csp_' + api[4:].lower()
    return (api, key)

def merge_configs(configs, base=None):
    merged = {'sites': [], 'parses': [], 'ads': [], 'rules': []}
    seen_sites, seen_parses, seen_ads, seen_rules = set(), set(), set(), set()
    spider = None
    all_cfgs = ([base] if base else []) + configs
    for cfg in all_cfgs:
        if not cfg: continue
        if not spider and cfg.get('spider'): spider = cfg['spider']
        for s in cfg.get('sites', []):
            if not isinstance(s, dict): continue
            uid = normalize_site(s)
            if uid in seen_sites: continue
            seen_sites.add(uid); merged['sites'].append(s)
        for p in cfg.get('parses', []):
            if isinstance(p, dict):
                uid = (p.get('name'), p.get('type'), p.get('url'))
                if uid not in seen_parses:
                    seen_parses.add(uid); merged['parses'].append(p)
        for a in cfg.get('ads', []):
            if a not in seen_ads: seen_ads.add(a); merged['ads'].append(a)
        for r in cfg.get('rules', []):
            key = json.dumps(r, ensure_ascii=False) if isinstance(r, (dict, list)) else str(r)
            if key not in seen_rules: seen_rules.add(key); merged['rules'].append(r)
        for k in ('doh', 'flags', 'ijk', 'wallpaper', 'logo'):
            if cfg.get(k) and k not in merged: merged[k] = cfg[k]
    if spider: merged['spider'] = spider
    return {k: v for k, v in merged.items() if v}

# ---------------- 单源抓取 ----------------

def fetch_one(url, name=None, timeout=TIMEOUT):
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

# ---------------- 本地化 ----------------

def localize(config, out_dir='localize'):
    """全量本地化: 下载 spider jar + 远程 JS api 到本地,配置改本地路径。
    返回 (新配置, 下载文件清单)"""
    os.makedirs(out_dir, exist_ok=True)
    downloaded = []

    def grab(url, subdir=''):
        """下载 url 到 out_dir/subdir, 返回本地相对路径"""
        try:
            # 处理 TVBox 常见 `;md5;xxx` 后缀
            clean_url = re.sub(r';md5;[0-9a-fA-F]+$', '', url)
            data, _ = http_get(clean_url, timeout=30)
            fname = clean_url.split('?')[0].rstrip('/').split('/')[-1]
            if not fname or '.' not in fname:
                fname = hashlib.md5(clean_url.encode()).hexdigest()[:12] + '.bin'
            fpath = os.path.join(subdir, fname)
            full = os.path.join(out_dir, fpath)
            os.makedirs(os.path.dirname(full), exist_ok=True)
            with open(full, 'wb') as f:
                f.write(data)
            downloaded.append({'url': url, 'local': fpath, 'size': len(data)})
            return fpath
        except Exception as e:
            print(f'  ⚠️ 下载失败 {url}: {e}')
            return url

    cfg = json.loads(json.dumps(config))
    if cfg.get('spider') and cfg['spider'].startswith('http'):
        print(f'下载 spider: {cfg["spider"][:60]}...')
        local = grab(cfg['spider'])
        if not local.startswith('http'):
            cfg['spider'] = local
    for s in cfg.get('sites', []):
        api = s.get('api', '')
        if isinstance(api, str) and api.startswith('http') and ('.js' in api or '.jar' in api):
            print(f'下载 api: {api[:60]}...')
            local = grab(api)
            if not local.startswith('http'):
                s['api'] = local
    for s in cfg.get('sites', []):
        ext = s.get('ext')
        if isinstance(ext, dict):
            for k, v in list(ext.items()):
                if isinstance(v, str) and v.startswith('http'):
                    local = grab(v)
                    if not local.startswith('http'):
                        ext[k] = local
    return cfg, downloaded

# ---------------- CLI ----------------

def cmd_fetch(args):
    r = fetch_one(args.url, args.name)
    print(json.dumps({k: v for k, v in r.items() if k != 'config'}, ensure_ascii=False, indent=1, default=str)[:1500])
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
        try: cfgs.append(json.load(open(p, encoding='utf-8')))
        except Exception as e: print(f'⚠️ 无法读取 {p}: {e}')
    base = json.load(open(args.base, encoding='utf-8')) if args.base else None
    merged = merge_configs(cfgs, base)
    json.dump(merged, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'✅ 合并完成: {len(merged.get("sites",[]))} sites | {len(merged.get("parses",[]))} parses')
    print(f'   已保存 {args.out}')

def cmd_run(args):
    lines = [l.strip() for l in open(args.list, encoding='utf-8') if l.strip() and not l.startswith('#')]
    cfgs = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as ex:
        results = list(ex.map(lambda u: fetch_one(u), lines))
    ok = [r for r in results if r.get('ok')]
    for r in ok:
        cfgs.append(r['config'])
        print(f"  ✅ {r['name']} | {r['sites']}站 | {r.get('info','')}")
    for r in [x for x in results if not x.get('ok')]:
        print(f"  ❌ {r['name']} | {r.get('info') or r.get('error','')}")
    if not cfgs:
        print('没有可用源,退出'); sys.exit(1)
    base = json.load(open(args.base, encoding='utf-8')) if args.base else None
    merged = merge_configs(cfgs, base)
    json.dump(merged, open(args.out, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'\n✅ 聚合完成: {len(merged.get("sites",[]))} sites | {len(merged.get("parses",[]))} parses')
    print(f'   已保存 {args.out}')

def cmd_localize(args):
    cfg = json.load(open(args.config, encoding='utf-8'))
    print(f'开始本地化: {args.config} -> {args.out_dir}/')
    new_cfg, dl = localize(cfg, args.out_dir)
    out_json = os.path.join(args.out_dir, 'config.json')
    json.dump(new_cfg, open(out_json, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)
    print(f'✅ 下载 {len(dl)} 个文件:')
    for f in dl:
        print(f'   {f["local"]} ({f["size"]}B) <- {f["url"][:60]}')
    print(f'✅ 本地化配置: {out_json}')

def main():
    p = argparse.ArgumentParser(description='小五 v2.0 — TVBox 配置抓取/转换/聚合/本地化工具')
    sub = p.add_subparsers(dest='cmd')
    pf = sub.add_parser('fetch', help='抓取单个源(多形态)')
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
    pl = sub.add_parser('localize', help='全量本地化:下载jar/js到本地')
    pl.add_argument('config'); pl.add_argument('--out-dir', default='localize')
    pl.set_defaults(fn=cmd_localize)
    args = p.parse_args()
    if not args.cmd: p.print_help(); sys.exit(0)
    args.fn(args)

if __name__ == '__main__':
    main()
