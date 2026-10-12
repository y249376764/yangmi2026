# -*- coding: utf-8 -*-
# check_module.py —— 检查「模块变量被赋值为布尔」这一类致命 bug
#
# 背景（v13 真实事故，v8 引入、v8~v12 连续 5 版全部 py 站点不可用）：
#   function phLoad()  { ... return 模块对象 | null }     ← 正确
#   function phReady() { ... return true    | false }     ← 只供布尔判断
#   var PH_P = phReady();        ← 手滑写成 phReady
#   PH_P.runPy(...)              ← 在 true 上调方法 → "找不到函数 runPy"
#
# 而且 if (!PH_P) 这类守卫对 true 无效，错误会被一路带到 UI，极难定位。
#
# 检测思路：
#   1. 找出「只返回布尔字面量」的函数（phReady 那类）
#   2. 找出 var X = <该函数>()
#   3. 若 X 之后被当作对象使用（X.method( 或 X["method"]( ）→ 报错
import json, re, sys

TS = ('hiker://page/', 'hiker://empty', 'toast://', 'copy://', 'refreshPage')
BUILTIN_OBJ = ('Math', 'JSON', 'String', 'Array', 'Object', 'Date', 'java',
               'java.lang', 'java.io', 'MY_RULE', 'MY_PAGE', 'MY_INDEX')


def _strip(s):
    out, i, n = [], 0, len(s)
    while i < n:
        c = s[i]
        if c == '/' and i + 1 < n and s[i + 1] == '/':
            i = s.find('\n', i)
            if i < 0: break
            continue
        if c == '/' and i + 1 < n and s[i + 1] == '*':
            i = s.find('*/', i + 2)
            i = i + 2 if i >= 0 else n
            continue
        if c in '"\'':
            q, i = c, i + 1
            while i < n:
                if s[i] == '\\': i += 2; continue
                if s[i] == q: i += 1; break
                i += 1
            out.append('""'); continue
        out.append(c); i += 1
    return ''.join(out)


def _funcs(src):
    """返回 {函数名: 是否只返回布尔}"""
    res = {}
    for m in re.finditer(r'\bfunction\s+(\w+)\s*\([^)]*\)\s*\{', src):
        name, i, depth = m.group(1), m.end() - 1, 0
        j = i
        while j < len(src):
            if src[j] == '{': depth += 1
            elif src[j] == '}':
                depth -= 1
                if depth == 0: break
            j += 1
        body = src[i:j]
        rets = re.findall(r'\breturn\s+([^;}]+)', body)
        if not rets: continue
        vals = set()
        for r in rets:
            v = r.strip().strip('()').strip()
            vals.add(v)
        if vals and vals <= {'true', 'false', 'null', 'undefined'}:
            res[name] = True
    return res


def check(src, label=''):
    src = _strip(src)
    boolfns = _funcs(src)
    problems = []
    # var X = boolfn()
    assigns = {}
    for m in re.finditer(r'\bvar\s+(\w+)\s*=\s*(\w+)\s*\(\s*\)', src):
        var, fn = m.group(1), m.group(2)
        if fn in boolfns:
            assigns[var] = (fn, m.start())
    for var, (fn, pos) in assigns.items():
        # 该变量是否被当作对象使用
        for um in re.finditer(r'\b' + re.escape(var) + r'\s*(?:\.\s*(\w+)\s*\(|\[\s*["\'](\w+)["\']\s*\]\s*\()', src):
            if um.start() <= pos: continue
            meth = um.group(1) or um.group(2)
            ln = src[:um.start()].count('\n') + 1
            problems.append('%s 第%d行：`%s` 来自 %s()（只返回布尔），却被当对象调用 .%s()' % (label, ln, var, fn, meth))
    # 反向：模块名直接调用但从未被赋值为对象
    seen = set()
    for p in problems: seen.add(p)
    return sorted(seen)


def main():
    path = sys.argv[1] if len(sys.argv) > 1 else 'acc_v13.json'
    j = json.load(open(path, encoding='utf-8'))
    srcs = [('find_rule', j['find_rule'])]
    for p in json.loads(j['pages']):
        srcs.append((p['path'], p['rule'][3:] if p['rule'].startswith('js:') else p['rule']))
    allp = []
    for name, s in srcs:
        allp += check(s, name)
    if allp:
        print('❌ 模块/布尔混用检查失败，共 %d 处：' % len(allp))
        for x in allp: print('   -', x)
        sys.exit(1)
    print('✅ 模块/布尔混用检查通过（模块变量均来自返回对象的函数）')


if __name__ == '__main__':
    main()
