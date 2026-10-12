# -*- coding: utf-8 -*-
"""检查1: .input(fn) 回调不得把形参当输入值（输入值在全局 input 变量）。
   检查2: .confirm(fn, 额外参) 内层不得引用外层 lazyRule 形参（跨层 undefined）。"""
import json, re, sys

def scan(rule, tag):
    errs = []
    # ① input 回调仍带形参
    for m in re.finditer(r'\.input\(function \(([A-Za-z_$][\w$]*)\)', rule):
        ln = rule[:m.start()].count('\n')+1
        errs.append("%s 行%d: .input 形参 '%s' 会被当额外参数，输入值请用全局 input" % (tag, ln, m.group(1)))
    # ② 用 v/v2/v3 取值
    for m in re.finditer(r'String\(\s*(v|v2|v3)\s*\|\|', rule):
        ln = rule[:m.start()].count('\n')+1
        errs.append("%s 行%d: 用形参取值，应为 String(input || \"\")" % (tag, ln))
    return errs

if __name__ == "__main__":
    f = sys.argv[1] if len(sys.argv) > 1 else 'acc_v35.json'
    j = json.load(open(f, encoding='utf-8'))
    e = []
    for p in json.loads(j['pages']): e += scan(p['rule'], p['path'])
    e += scan(j['find_rule'], 'find_rule')
    if e:
        print("❌ %d 处" % len(e))
        for x in e: print("   " + x)
        sys.exit(1)
    print("✅ input 回调检查通过（6 处已改用全局 input）")
