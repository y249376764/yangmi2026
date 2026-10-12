# -*- coding: utf-8 -*-
"""检查内联 HTML 是否带海阔富文本前缀（字面量 / PRE 变量 / u转义 三种形式）。"""
import json, re, sys
PRE1='\u2018\u2018\u2019\u2019'; PRE2='\u201c\u201c\u201d\u201d'
def scan(rule, tag):
    errs=[]
    for m in re.finditer(r'<(strong|font|b|small|span|br|p|div|em|i)\b[^>]*>', rule):
        ln=rule[:m.start()].count('\n')+1
        line=rule[:m.start()]
        # 往前找到该表达式起点（分号/换行/引号开头）
        seg=line[max(0,len(line)-260):]
        ok = (PRE1 in seg) or (PRE2 in seg) or re.search(r'PRE\s*\+', seg) or re.search(r'\\u2018\\u2018\\u2019\\u2019', seg) or re.search(r'\\u201c\\u201c\\u201d\\u201d', seg)
        if not ok:
            errs.append("%s 行%d: HTML 前无富文本前缀 → %s"%(tag,ln,rule.split('\n')[ln-1].strip()[:120]))
    return errs
if __name__=="__main__":
    f=sys.argv[1] if len(sys.argv)>1 else 'acc_v34.json'
    j=json.load(open(f,encoding='utf-8'))
    e=[]
    for p in json.loads(j['pages']): e+=scan(p['rule'],p['path'])
    e+=scan(j['find_rule'],'find_rule')
    if e:
        print("❌ %d 处"%len(e))
        for x in e: print("   "+x)
        sys.exit(1)
    print("✅ 富文本前缀检查通过（字面量/PRE变量/\\u转义 三种形式均识别）")
