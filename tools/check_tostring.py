# -*- coding: utf-8 -*-
"""检查 lazyRule/$.toString 回调：形参 vs 传参个数、跨层形参引用、未声明变量。"""
import json, re, sys

def split_top(txt):
    out=[]; depth=0; cur=''
    for ch in txt:
        if ch in '([{': depth+=1
        elif ch in ')]}': depth-=1
        if ch==',' and depth==0:
            out.append(cur.strip()); cur=''
        else: cur+=ch
    if cur.strip(): out.append(cur.strip())
    return [a for a in out if a]

def extract_args(s, pos):
    """pos 指向 '{...}' 之后，返回 (参数文本, 是否找到)。扫描到顶层 ')' 为止。"""
    i=pos
    while i<len(s) and s[i] in ' \t\r\n': i+=1
    if i>=len(s) or s[i]!=',': return None
    i+=1
    depth=0; start=i
    while i<len(s):
        ch=s[i]
        if ch in '([': depth+=1
        elif ch in ')]':
            if depth==0:
                return s[start:i]
            depth-=1
        i+=1
    return None

def match_brace(s, start):
    """从 start(指向'{') 返回配对 '}' 的索引"""
    depth=0; k=start
    while k < len(s):
        if s[k]=='{': depth+=1
        elif s[k]=='}':
            depth-=1
            if depth==0: return k
        k+=1
    return -1

def analyze(rule, tag):
    errs=[]; s=rule
    # 收集 lazyRule 回调：形参 + 体 + 传参
    cbs=[]
    for m in re.finditer(r'\.lazyRule\(function\s*\(([^)]*)\)', s):
        params=[p.strip() for p in m.group(1).split(',') if p.strip()]
        bi=s.index('{', m.end()-1)
        be=match_brace(s, bi)
        if be<0: continue
        body=s[bi:be]
        at=extract_args(s, be+1)
        args=split_top(at) if at is not None else []
        cbs.append({'params':params,'body':body,'args':args,'start':m.start()})
        if params:
            if at is None:
                errs.append("%s: lazyRule 有形参%s 但末尾无传参"%(tag,params))
            elif len(args)!=len(params):
                errs.append("%s: lazyRule 形参%d%s 但传参%d个 <%s>"%(tag,len(params),params,len(args),at[:50]))
    outer=set()
    for c in cbs: outer.update(c['params'])
    # $.toString 传参引用外层形参
    for m in re.finditer(r'\$\.toString\(function\s*\(([^)]*)\)', s):
        bi=s.index('{', m.end()-1)
        be=match_brace(s, bi)
        if be<0: continue
        at=extract_args(s, be+1)
        if at is not None:
            for a in split_top(at):
                if a in outer:
                    errs.append("%s: $.toString 传参 '%s' 是外层 lazyRule 形参（跨层会 undefined）"%(tag,a))
    # 回调体用了未声明的 tags/cats/paths/names
    for c in cbs:
        for name in ('tags','cats','cats2','paths','names'):
            if re.search(r'\b'+name+r'\b', c['body']) and name not in c['params']:
                if not re.search(r'var\s+'+name+r'\b', c['body']):
                    errs.append("%s: lazyRule 体用了 '%s' 但非形参也未声明"%(tag,name))
    return errs

if __name__=="__main__":
    f=sys.argv[1] if len(sys.argv)>1 else 'acc_v31.json'
    j=json.load(open(f,encoding='utf-8'))
    pages=json.loads(j['pages'])
    allerr=[]
    for p in pages: allerr+=analyze(p['rule'],p['path'])
    allerr+=analyze(j['find_rule'],'find_rule')
    seen=set(); out=[]
    for e in allerr:
        if e not in seen: seen.add(e); out.append(e)
    if out:
        print("❌ 发现 %d 个问题："%len(out))
        for e in out: print("   "+e)
        sys.exit(1)
    print("✅ 回调形参/传参检查通过（含跨层 $.toString 引用）")
