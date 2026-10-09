# -*- coding: utf-8 -*-
"""海阔规则 JS 精简
只删: 整行注释 / 块注释 / 空行 / 行首缩进
不删行尾注释 —— 正则里常有 // (如 /\\/vodtype\\/(\\d+)\\//i), 删了会破坏语法
"""
import re, subprocess, sys


def minify(src: str) -> str:
    # 先移除多行块注释
    src = re.sub(r'/\*[\s\S]*?\*/', '', src)
    out = []
    for ln in src.split('\n'):
        s = ln.strip()
        if s == '':
            continue
        if s.startswith('//') or s.startswith('*'):
            continue
        out.append(s)
    return '\n'.join(out)


if __name__ == '__main__':
    p = sys.argv[1]
    src = open(p, encoding='utf-8').read()
    m = minify(src)
    open('/tmp/_min_check.js', 'w', encoding='utf-8').write(m)
    r = subprocess.run(['node', '--check', '/tmp/_min_check.js'],
                       capture_output=True, text=True)
    if r.returncode != 0:
        print('语法检查失败:', r.stderr[:300])
        sys.exit(1)
    print('原始:', len(src), '-> 精简:', len(m),
          ' 减少 %.0f%%' % ((len(src) - len(m)) / len(src) * 100))
    print('语法: OK')
    open('/tmp/_minified.js', 'w', encoding='utf-8').write(m)
