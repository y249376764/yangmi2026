# -*- coding: utf-8 -*-
"""通用作用域检查：回调内不得引用页面顶层定义的 var/function

v11 增强（第 12 次栽在同一个坑之后）：
  1. 覆盖范围加入 `be(list, {func: function(...){}})` 和 task 的 `func: function(obj){...}`
     —— 旧版只查 .lazyRule/.rule/.select/.confirm/.input，漏掉了 be 回调，
        导致 zplay 页「0.4s 扫完 398 站零结果」一直没被发现。
  2. 顶层变量收集改为「任意缩进」—— 旧版只认 ^var，
     而海阔页面里大量变量定义在 try{} 块内（缩进 8 空格），全部漏掉。
"""
import json, re, sys

def scan(rule, path):
    body = rule[3:] if rule.startswith('js:') else rule
    # 顶层 var / function
    # 任意缩进都要收（海阔页面里变量常定义在 try{} 块内，是缩进的）
    top = set(re.findall(r'^[ \t]*var\s+([A-Za-z_$][\w$]*)\s*=', body, re.M))
    top |= set(re.findall(r'^[ \t]*function\s+([A-Za-z_$][\w$]*)\s*\(', body, re.M))
    bad = []
    # 覆盖：.lazyRule( / .rule( / .select( / .confirm( / .input( / be 的 func: function
    CB = r'(?:\.(?:lazyRule|rule|select|confirm|input)\(\s*|func:\s*)function[^{]*\{'
    for m in re.finditer(CB, body):
        st = m.end(); dp = 1; i = st
        while i < len(body) and dp > 0:
            if body[i] == '{': dp += 1
            elif body[i] == '}': dp -= 1
            i += 1
        cb = body[st:i]
        # 剥离字符串字面量与行注释再匹配，避免把 URL 里的 "raw"/"txt" 当成标识符误报
        cbc = re.sub(r'"(?:[^"\\]|\\.)*"', '""', cb)
        cbc = re.sub(r"'(?:[^'\\]|\\.)*'", "''", cbc)
        cbc = re.sub(r'//[^\n]*', '', cbc)
        cb = cbc
        inner = st
        # 回调内自身声明
        loc = set(re.findall(r'function\s+([A-Za-z_$][\w$]*)\s*\(', cb))
        loc |= set(re.findall(r'\bvar\s+([A-Za-z_$][\w$]*)\s*=', cb))
        loc |= set(re.findall(r'\bfunction\s+([A-Za-z_$][\w$]*)\s*\(', cb))
        # 回调自身形参（已在 m.group 里，保守：找出所有 function(...) 的括号内标识符）
        for fm in re.finditer(r'function\s*\(([^)]*)\)', body[max(0, m.start()-20):st]):
            for p in fm.group(1).split(','):
                p = p.strip()
                if p: loc.add(p)
        for v in top:
            if v in loc: continue
            # 前面不能是 . 或单词字符 → 排除 cc.s 这类属性名误报
            if re.search(r'(?<![\w$.])' + re.escape(v) + r'\b', cb):
                ln = body[:m.start()].count('\n') + 1
                bad.append((path, v, ln))
    return bad

if __name__ == '__main__':
    f = sys.argv[1]
    j = json.load(open(f, encoding='utf-8'))
    pages = json.loads(j['pages'])
    allb = []
    for p in pages: allb += scan(p['rule'], p['path'])
    allb += scan(j['find_rule'], 'find_rule')
    if allb:
        print("❌ 回调内引用顶层标识符：")
        for b in allb: print("   ", b)
        sys.exit(1)
    print("✅ 回调作用域检查通过")
