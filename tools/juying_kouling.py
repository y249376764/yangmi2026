# -*- coding: utf-8 -*-
"""聚影「云口令」打包器 —— 把一段 py 蜘蛛源码打成一条可粘贴的口令

口令格式（与「云帧享-py聚影口令」完全一致，已反解校验逐字节相同）：

    云口令：聚影接口￥<密文>￥<名称>()@import=js:$.require("hiker://page/import?rule=聚影");

    密文 = base64( AES-256-ECB/PKCS7(
               key   = b"Juying2" + b"0"*25  ，
               plain = base64( gzip( JSON数组 utf-8, mtime=0 ) ) 的 ASCII 文本
           ) )
    JSON数组 = [{"name","type":"py","url","oldurl","ext","extstr","searchable","quickSearch","filterable"}]
    url      = hiker://files/rules/Src/Juying2/jiekou/py_<落地名>.py   ← 导入时聚影 writeFile 落地
    extstr   = py 源码全文（自包含，不依赖网络文件）
    明文里不许出现 http 链接，否则 App 走云剪贴板分支 → 0 条 → 导入空白

用法：
    python3 juying_kouling.py 蜘蛛.py                 # 名称取文件名，落地名同名
    python3 juying_kouling.py 蜘蛛.py 云帧享 yunzhenxiang
    python3 juying_kouling.py --unpack 口令.txt        # 反向解密，自检用

输出：/workspace/outputs/<名称>-聚影口令.txt（单行、无空行、无 BOM、不夹说明文字）
"""
import base64
import gzip
import json
import os
import re
import sys

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

KEY = b'Juying2' + b'0' * 25          # 7 + 25 = 32 字节
PREFIX = '云口令：聚影接口￥'
SUFFIX = '()@import=js:$.require("hiker://page/import?rule=聚影");'
SRC_DIR = 'hiker://files/rules/Src/Juying2/jiekou/'
OUT_DIR = '/workspace/outputs'


def _encrypt(plain_text):
    pad = 16 - len(plain_text.encode('utf-8')) % 16
    data = plain_text.encode('utf-8') + bytes([pad]) * pad
    enc = Cipher(algorithms.AES(KEY), modes.ECB()).encryptor()
    return base64.b64encode(enc.update(data) + enc.finalize()).decode('ascii')


def _decrypt(b64):
    ct = base64.b64decode(b64 + '=' * (-len(b64) % 4))
    dec = Cipher(algorithms.AES(KEY), modes.ECB()).decryptor()
    pt = dec.update(ct) + dec.finalize()
    return pt[:-pt[-1]].decode('utf-8')


def pack(name, src, slug=None, extra=None):
    """源码 → 口令整行"""
    slug = slug or name
    item = {
        'name': name,
        'type': 'py',
        'url': SRC_DIR + ('py_%s.py' % slug),
        'oldurl': '',
        'ext': '',
        'extstr': src,
        'searchable': 1,
        'quickSearch': 1,
        'filterable': 1,
    }
    if extra:
        item.update(extra)
    payload = base64.b64encode(
        gzip.compress(json.dumps([item], ensure_ascii=False).encode('utf-8'), mtime=0)
    ).decode('ascii')
    return PREFIX + _encrypt(payload) + '￥' + name + SUFFIX


def unpack(text):
    """口令整行 → (名称, py源码)；顺带校验密文完整性"""
    text = text.strip()
    seg = text.split('￥')
    if len(seg) < 2:
        raise SystemExit('不是聚影口令：找不到 ￥ 分隔符')
    inner = _decrypt(seg[1])
    raw = gzip.decompress(base64.b64decode(inner)).decode('utf-8')
    data = json.loads(raw)
    it = data[0]
    return it, raw


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        return 1
    if args[0] in ('--unpack', '-u'):
        it, raw = unpack(open(args[1], encoding='utf-8', errors='ignore').read())
        print('name :', it.get('name'))
        print('type :', it.get('type'))
        print('url  :', it.get('url'))
        print('extstr bytes:', len(it.get('extstr') or ''))
        out = os.path.splitext(os.path.basename(args[1]))[0] + '.unpacked.py'
        open(out, 'w', encoding='utf-8').write(it.get('extstr') or '')
        print('源码已写出:', out)
        return 0

    path = args[0]
    src = open(path, encoding='utf-8').read()
    name = args[1] if len(args) > 1 else os.path.splitext(os.path.basename(path))[0]
    slug = args[2] if len(args) > 2 else None
    line = pack(name, src, slug)
    if not os.path.isdir(OUT_DIR):
        os.makedirs(OUT_DIR)
    out = os.path.join(OUT_DIR, '%s-聚影口令.txt' % name)
    with open(out, 'w', encoding='utf-8', newline='\n') as f:
        f.write(line)
    # 自检：重新解密，口令里的源码必须与入参逐字节相同
    it, _ = unpack(line)
    ok = (it['extstr'] == src) and (it['name'] == name)
    print('源码 %d 字节 → 口令 %d 字符' % (len(src), len(line)))
    print('落地路径: %s' % it['url'])
    print('自检(反解源码一致):', 'PASS' if ok else 'FAIL')
    print('已写出:', out)
    return 0 if ok else 2


if __name__ == '__main__':
    sys.exit(main())
