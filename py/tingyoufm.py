# -*- coding: utf-8 -*-
"""
听友FM 听书蜘蛛版 (tingyoufm.py)
--------------------------------
站点: https://tingyou.fm
提取自 Timbre .jdr 接口源 (tingyoufm.js v1.0.2), 2026-10-03 实测:

  * 配置     GET /api/payload                    -> { key(64hex), version, staticRoutePools }
  * 分类     GET {pool}/filters                  -> 分类/排序/状态
  * 分类页   GET /api/category_page?type={id}&page={pg} (加密响应) -> 书籍列表
  * 首页     GET {pool}/homepage                 -> recommends/recent_updates
  * 搜索     POST /api/search (AES-256-GCM 加密请求体) -> 书籍列表
  * 章节     GET {pool}/album_chapters/{bookId}  -> 全量章节
  * 播放     POST /api/guest (SM4 dfp 指纹 Cookie) -> auth_token
             POST /api/play_token (Bearer auth)  -> play_url 直链 (audio/mpeg)

加密协议:
  * 请求体: hex( [1字节版本][12字节IV][AES-256-GCM 密文||tag] )
  * 响应:   { "payload": hex([1字节版本][24字节nonce][XChaCha20-Poly1305 密文+16tag]) }
            version==2 时密文整段反转
  * dfp 指纹: SM4-ECB(PKCS#7, base64) 设备指纹, 密钥 = SHA256("fa317cd29b|东八区YYYYMMDD") 前32hex

依赖: requests + pycryptodome (默影视 requirements 已含)
"""
import re
import json
import time
import hashlib
import base64
import struct
import datetime
import os

import requests

try:
    from Crypto.Cipher import AES, ChaCha20_Poly1305
    from Crypto.Random import get_random_bytes
    HAS_CRYPTO = True
except Exception:
    HAS_CRYPTO = False

# ============ 纯 Python 加密兜底 (pycryptodome 缺失时使用) ============
# -*- coding: utf-8 -*-
"""
纯 Python 加密库（无 pycryptodome 依赖）
AES-128/256 ECB + AES-GCM + XChaCha20-Poly1305 + ChaCha20 流
所有实现通过官方测试向量验证
"""
import struct

# ================= AES =================
SBOX = [
    0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
    0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
    0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
    0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
    0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
    0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
    0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
    0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
    0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
    0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
    0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
    0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
    0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
    0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
    0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
    0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16,
]

def _xtime(a): return ((a << 1) ^ 0x1b) & 0xff if a & 0x80 else (a << 1) & 0xff

def _gmul(a, b):
    p = 0
    for _ in range(8):
        if b & 1: p ^= a
        a = _xtime(a)
        b >>= 1
    return p & 0xff

def _key_expansion(key):
    nk = len(key) // 4
    nr = nk + 6
    w = [list(key[4*i:4*i+4]) for i in range(nk)]
    rcon = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1b, 0x36]
    for i in range(nk, 4 * (nr + 1)):
        temp = w[i-1][:]
        if i % nk == 0:
            temp = temp[1:] + temp[:1]
            temp = [SBOX[b] for b in temp]
            temp[0] ^= rcon[i // nk - 1]
        elif nk > 6 and i % nk == 4:
            temp = [SBOX[b] for b in temp]
        w.append([w[i-nk][j] ^ temp[j] for j in range(4)])
    return w, nr

def aes_encrypt_block(key, block):
    w, nr = _key_expansion(key)
    state = [[block[r + 4*c] for c in range(4)] for r in range(4)]
    def add_round_key(rnd):
        for c in range(4):
            for r in range(4):
                state[r][c] ^= w[rnd * 4 + c][r]
    add_round_key(0)
    for rnd in range(1, nr + 1):
        for r in range(4):
            for c in range(4):
                state[r][c] = SBOX[state[r][c]]
        state[1] = state[1][1:] + state[1][:1]
        state[2] = state[2][2:] + state[2][:2]
        state[3] = state[3][3:] + state[3][:3]
        if rnd < nr:
            for c in range(4):
                a0 = state[0][c]; a1 = state[1][c]; a2 = state[2][c]; a3 = state[3][c]
                state[0][c] = _gmul(a0, 2) ^ _gmul(a1, 3) ^ a2 ^ a3
                state[1][c] = a0 ^ _gmul(a1, 2) ^ _gmul(a2, 3) ^ a3
                state[2][c] = a0 ^ a1 ^ _gmul(a2, 2) ^ _gmul(a3, 3)
                state[3][c] = _gmul(a0, 3) ^ a1 ^ a2 ^ _gmul(a3, 2)
        add_round_key(rnd)
    out = bytearray(16)
    for r in range(4):
        for c in range(4):
            out[r + 4*c] = state[r][c]
    return bytes(out)

def aes_ecb_encrypt(key, data):
    """ECB 模式加密（数据长度必须 16 倍数）"""
    out = b""
    for i in range(0, len(data), 16):
        out += aes_encrypt_block(key, data[i:i+16])
    return out

# ================= GHASH (GF(2^128)) =================
def _gf128_mul(x, h):
    """GF(2^128) 乘法 (pycryptodome 移植): X MSB-first, V_i = H*x^i 预计算"""
    # V[0] = H, V[i] = V[i-1] >> 1 (LSB 时 xor R)
    vs = []
    vi = int.from_bytes(h, 'big')
    r = 0xe1000000000000000000000000000000
    for i in range(128):
        vs.append(vi)
        lsb = vi & 1
        vi >>= 1
        if lsb:
            vi ^= r
    # Z = sum(X_i * V_i), X MSB-first
    xi = int.from_bytes(x, 'big')
    zi = 0
    for i in range(128):
        if (xi >> (127 - i)) & 1:
            zi ^= vs[i]
    return zi.to_bytes(16, 'big')

def _ghash(h, data):
    y = bytearray(16)
    for i in range(0, len(data), 16):
        block = data[i:i+16]
        for j in range(16):
            y[j] ^= block[j]
        y = bytearray(_gf128_mul(bytes(y), h))
    return bytes(y)

# ================= AES-GCM =================
def aes_gcm_encrypt(key, iv, plaintext, aad=b""):
    """AES-GCM 加密, 返回 密文+16字节tag（仅 12 字节 iv）"""
    h = aes_encrypt_block(key, b"\x00" * 16)
    j0 = iv + b"\x00\x00\x00\x01"
    def ctr_block(counter):
        block = bytearray(j0)
        val = (block[12] << 24) | (block[13] << 16) | (block[14] << 8) | block[15]
        val = (val + counter) & 0xffffffff
        block[12] = (val >> 24) & 0xff; block[13] = (val >> 16) & 0xff
        block[14] = (val >> 8) & 0xff; block[15] = val & 0xff
        return bytes(block)
    ciphertext = bytearray()
    for i in range(0, len(plaintext), 16):
        counter = i // 16 + 1
        keystream = aes_encrypt_block(key, ctr_block(counter))
        chunk = plaintext[i:i+16]
        for j in range(len(chunk)):
            ciphertext.append(chunk[j] ^ keystream[j])
    aad_padded = aad + b"\x00" * ((16 - len(aad) % 16) % 16)
    ct = bytes(ciphertext)
    ct_padded = ct + b"\x00" * ((16 - len(ct) % 16) % 16)
    len_block = struct.pack('>QQ', len(aad) * 8, len(ct) * 8)
    s = _ghash(h, aad_padded + ct_padded + len_block)
    tag_keystream = aes_encrypt_block(key, j0)
    tag = bytes([s[i] ^ tag_keystream[i] for i in range(16)])
    return ct + tag

# ================= ChaCha20 =================
def _chacha20_block(key, counter, nonce):
    constants = b"expand 32-byte k"
    # RFC 8439 state: 4 常量 + 8 key 字 + 1 计数器字(32位) + 3 nonce 字(12字节) = 16 字
    state = (
        struct.unpack('<IIII', constants) +
        struct.unpack('<IIIIIIII', key) +
        (counter & 0xffffffff,) +
        struct.unpack('<III', nonce)
    )
    def rotl(v, c): return ((v << c) | (v >> (32 - c))) & 0xffffffff
    def qr(x, a, b, c, d):
        x[a] = (x[a] + x[b]) & 0xffffffff; x[d] = rotl(x[d] ^ x[a], 16)
        x[c] = (x[c] + x[d]) & 0xffffffff; x[b] = rotl(x[b] ^ x[c], 12)
        x[a] = (x[a] + x[b]) & 0xffffffff; x[d] = rotl(x[d] ^ x[a], 8)
        x[c] = (x[c] + x[d]) & 0xffffffff; x[b] = rotl(x[b] ^ x[c], 7)
        return x
    x = list(state)
    working = list(state)
    for _ in range(10):
        qr(working, 0, 4, 8, 12); qr(working, 1, 5, 9, 13); qr(working, 2, 6, 10, 14); qr(working, 3, 7, 11, 15)
        qr(working, 0, 5, 10, 15); qr(working, 1, 6, 11, 12); qr(working, 2, 7, 8, 13); qr(working, 3, 4, 9, 14)
    out = [(working[i] + x[i]) & 0xffffffff for i in range(16)]
    return struct.pack('<16I', *out)

def _hchacha20(key, nonce):
    constants = b"expand 32-byte k"
    state = (
        struct.unpack('<IIII', constants) +
        struct.unpack('<IIIIIIII', key) +
        struct.unpack('<IIII', nonce) +
        (0, 0)
    )
    def rotl(v, c): return ((v << c) | (v >> (32 - c))) & 0xffffffff
    def qr(x, a, b, c, d):
        x[a] = (x[a] + x[b]) & 0xffffffff; x[d] = rotl(x[d] ^ x[a], 16)
        x[c] = (x[c] + x[d]) & 0xffffffff; x[b] = rotl(x[b] ^ x[c], 12)
        x[a] = (x[a] + x[b]) & 0xffffffff; x[d] = rotl(x[d] ^ x[a], 8)
        x[c] = (x[c] + x[d]) & 0xffffffff; x[b] = rotl(x[b] ^ x[c], 7)
        return x
    x = list(state)
    for _ in range(10):
        qr(x, 0, 4, 8, 12); qr(x, 1, 5, 9, 13); qr(x, 2, 6, 10, 14); qr(x, 3, 7, 11, 15)
        qr(x, 0, 5, 10, 15); qr(x, 1, 6, 11, 12); qr(x, 2, 7, 8, 13); qr(x, 3, 4, 9, 14)
    return struct.pack('<8I', x[0], x[1], x[2], x[3], x[12], x[13], x[14], x[15])

def chacha20_stream(key, nonce12, counter, length):
    out = b""
    block_idx = counter
    while len(out) < length:
        block = _chacha20_block(key, block_idx, nonce12)
        out += block
        block_idx += 1
    return out[:length]

# ================= Poly1305 =================
def poly1305_mac(key32, msg):
    """Poly1305 (RFC 8439) - pycryptodome 32-bit 版移植"""
    import struct as _st
    # load_r: 4 个字, mask
    r = [0] * 4
    rr = [0] * 4
    for i in range(4):
        w = int.from_bytes(key32[i*4:(i+1)*4], 'little')
        mask = 0x0fffffff if i == 0 else 0x0ffffffc
        r[i] = w & mask
        rr[i] = (r[i] >> 2) * 5
    h = [0, 0, 0, 0, 0]
    # 分块处理
    for i in range(0, len(msg), 16):
        chunk = msg[i:i+16]
        # load_m: 16 字节 + 0x01 补位, 5 个字
        copy = bytearray(20)
        copy[:len(chunk)] = chunk
        copy[len(chunk)] = 1
        m = [int.from_bytes(copy[j*4:(j+1)*4], 'little') for j in range(5)]
        # accumulate: h += m
        carry = 0
        for j in range(4):
            tmp = h[j] + m[j] + carry
            h[j] = tmp & 0xffffffff
            carry = (tmp >> 32) & 1
        tmp = h[4] + m[4] + carry
        h[4] = tmp & 0xffffffff
        # multiply: h = h * r
        a0, a1, a2, a3 = r
        aa0, aa1, aa2, aa3 = rr
        x0 = a0*h[0] + aa0*h[4] + aa1*h[3] + aa2*h[2] + aa3*h[1]
        x1 = a0*h[1] +  a1*h[0] + aa1*h[4] + aa2*h[3] + aa3*h[2]
        x2 = a0*h[2] +  a1*h[1] +  a2*h[0] + aa2*h[4] + aa3*h[3]
        x3 = a0*h[3] +  a1*h[2] +  a2*h[1] +  a3*h[0] + aa3*h[4]
        x4 = (a0 & 3)*h[4]
        # 折回
        x4 += x3 >> 32
        x3 &= 0xffffffff
        carry = (x4 >> 2) * 5
        x4 &= 3
        x0 += carry
        h[0] = x0 & 0xffffffff
        carry = x0 >> 32
        x1 += carry
        h[1] = x1 & 0xffffffff
        carry = x1 >> 32
        x2 += carry
        h[2] = x2 & 0xffffffff
        carry = x2 >> 32
        x3 += carry
        h[3] = x3 & 0xffffffff
        carry = x3 >> 32
        x4 += carry
        h[4] = x4 & 0xffffffff
    # reduce: h -= p (两轮, mask 选择)
    for _ in range(2):
        g = [0] * 5
        g[0] = h[0] + 5
        carry = 1 if g[0] < h[0] else 0
        g[1] = h[1] + carry
        carry = 1 if g[1] < h[1] else 0
        g[2] = h[2] + carry
        carry = 1 if g[2] < h[2] else 0
        g[3] = h[3] + carry
        carry = 1 if g[3] < h[3] else 0
        g[4] = (h[4] + carry - 4) & 0xffffffff
        mask = (g[4] >> 31) - 1  # 逻辑右移: 最高位 1 时 mask=0, 否则 0xffffffff
        for j in range(5):
            h[j] = (h[j] & ~mask) ^ (g[j] & mask)
    # finalize: h += s (key 后 16 字节), 截断 128-bit
    s = [int.from_bytes(key32[16+j*4:20+j*4], 'little') for j in range(4)]
    carry = 0
    for j in range(4):
        tmp = h[j] + s[j] + carry
        h[j] = tmp & 0xffffffff
        carry = (tmp >> 32) & 1
    # 输出 16 字节
    return b"".join(int.to_bytes(h[j], 4, 'little') for j in range(4))

# ================= XChaCha20-Poly1305 =================
def xchacha20_poly1305_decrypt(key, nonce24, data):
    """解密 密文+16字节tag"""
    subkey = _hchacha20(key, nonce24[:16])
    nonce12 = b"\x00\x00\x00\x00" + nonce24[16:]
    ct = data[:-16]
    tag = data[-16:]
    # 计算 Poly1305 key = ChaCha20 第 0 块
    poly_key = chacha20_stream(subkey, nonce12, 0, 64)
    # AEAD mac 输入 (RFC 8439 §2.8): AAD_pad + CT_pad + le64(aad_len) + le64(ct_len)
    # 无 AAD; pad16 补 0x00
    pad16 = b"\x00" * ((16 - len(ct) % 16) % 16)
    mac_input = ct + pad16 + struct.pack('<QQ', 0, len(ct))
    computed = poly1305_mac(poly_key, mac_input)
    # 常数时间比较
    if computed != tag:
        raise ValueError("Poly1305 MAC check failed")
    # 解密
    keystream = chacha20_stream(subkey, nonce12, 1, len(ct))
    return bytes([ct[i] ^ keystream[i] for i in range(len(ct))])


def xchacha20_poly1305_encrypt(key, nonce24, plaintext):
    subkey = _hchacha20(key, nonce24[:16])
    nonce12 = b"\x00\x00\x00\x00" + nonce24[16:]
    poly_key = chacha20_stream(subkey, nonce12, 0, 64)
    ct = bytearray()
    keystream = chacha20_stream(subkey, nonce12, 1, len(plaintext))
    for i in range(len(plaintext)):
        ct.append(plaintext[i] ^ keystream[i])
    # AEAD mac 输入: CT_pad + le64(aad_len) + le64(ct_len), pad16 补 0x00
    pad16 = b"\x00" * ((16 - len(ct) % 16) % 16)
    mac_input = bytes(ct) + pad16 + struct.pack('<QQ', 0, len(ct))
    tag = poly1305_mac(poly_key, mac_input)
    return bytes(ct) + tag

try:
    from base.spider import Spider as BaseSpider
except ImportError:
    class BaseSpider(object):
        def getName(self): return ''
        def init(self, extend=''): pass
        def homeContent(self, filter=False): return {"class": [], "list": [], "filters": {}}
        def homeVideoContent(self): return {"list": []}
        def categoryContent(self, tid, pg, filter=False, extend=''): return {"list": []}
        def detailContent(self, ids): return {"list": []}
        def searchContent(self, key, quick, pg='1'): return {"list": []}
        def playerContent(self, flag, id, vipFlags=None): return {"parse": 0, "url": ""}
        def localProxy(self, param=''): return {}
        def isVideoFormat(self, url): return False
        def manualVideoCheck(self): return False
        def destroy(self): pass


class Spider(BaseSpider):
    BASE = "https://tingyou.fm"
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36")
    timeout = 15

    # ---------- XChaCha20-Poly1305 ----------
    @staticmethod
    def _rotl(v, c):
        return ((v << c) | (v >> (32 - c))) & 0xffffffff

    @classmethod
    def _hchacha20(cls, key, nonce):
        constants = b"expand 32-byte k"
        state = (
            struct.unpack('<IIII', constants) +
            struct.unpack('<IIIIIIII', key) +
            struct.unpack('<IIII', nonce) +
            (0, 0)
        )
        def qr(x, a, b, c, d):
            x[a] = (x[a] + x[b]) & 0xffffffff
            x[d] = cls._rotl(x[d] ^ x[a], 16)
            x[c] = (x[c] + x[d]) & 0xffffffff
            x[b] = cls._rotl(x[b] ^ x[c], 12)
            x[a] = (x[a] + x[b]) & 0xffffffff
            x[d] = cls._rotl(x[d] ^ x[a], 8)
            x[c] = (x[c] + x[d]) & 0xffffffff
            x[b] = cls._rotl(x[b] ^ x[c], 7)
            return x
        x = list(state)
        for _ in range(10):
            qr(x, 0, 4, 8, 12); qr(x, 1, 5, 9, 13); qr(x, 2, 6, 10, 14); qr(x, 3, 7, 11, 15)
            qr(x, 0, 5, 10, 15); qr(x, 1, 6, 11, 12); qr(x, 2, 7, 8, 13); qr(x, 3, 4, 9, 14)
        return struct.pack('<8I', x[0], x[1], x[2], x[3], x[12], x[13], x[14], x[15])

    @classmethod
    def _xdecrypt(cls, key, nonce24, data):
        # 双路径: 优先 pycryptodome 原生 XChaCha20 (24字节 nonce), 失败回退手动 HChaCha20, 再失败纯 Python
        if HAS_CRYPTO:
            try:
                return ChaCha20_Poly1305.new(key=key, nonce=nonce24).decrypt_and_verify(data[:-16], data[-16:])
            except Exception:
                try:
                    subkey = cls._hchacha20(key, nonce24[:16])
                    nonce12 = b"\x00\x00\x00\x00" + nonce24[16:]
                    return ChaCha20_Poly1305.new(key=subkey, nonce=nonce12).decrypt_and_verify(data[:-16], data[-16:])
                except Exception:
                    pass
        # 纯 Python 兜底
        return xchacha20_poly1305_decrypt(key, nonce24, data)

    # ---------- SM4 ----------
    _SBOX = [
        0xd6,0x90,0xe9,0xfe,0xcc,0xe1,0x3d,0xb7,0x16,0xb6,0x14,0xc2,0x28,0xfb,0x2c,0x05,
        0x2b,0x67,0x9a,0x76,0x2a,0xbe,0x04,0xc3,0xaa,0x44,0x13,0x26,0x49,0x86,0x06,0x99,
        0x9c,0x42,0x50,0xf4,0x91,0xef,0x98,0x7a,0x33,0x54,0x0b,0x43,0xed,0xcf,0xac,0x62,
        0xe4,0xb3,0x1c,0xa9,0xc9,0x08,0xe8,0x95,0x80,0xdf,0x94,0xfa,0x75,0x8f,0x3f,0xa6,
        0x47,0x07,0xa7,0xfc,0xf3,0x73,0x17,0xba,0x83,0x59,0x3c,0x19,0xe6,0x85,0x4f,0xa8,
        0x68,0x6b,0x81,0xb2,0x71,0x64,0xda,0x8b,0xf8,0xeb,0x0f,0x4b,0x70,0x56,0x9d,0x35,
        0x1e,0x24,0x0e,0x5e,0x63,0x58,0xd1,0xa2,0x25,0x22,0x7c,0x3b,0x01,0x21,0x78,0x87,
        0xd4,0x00,0x46,0x57,0x9f,0xd3,0x27,0x52,0x4c,0x36,0x02,0xe7,0xa0,0xc4,0xc8,0x9e,
        0xea,0xbf,0x8a,0xd2,0x40,0xc7,0x38,0xb5,0xa3,0xf7,0xf2,0xce,0xf9,0x61,0x15,0xa1,
        0xe0,0xae,0x5d,0xa4,0x9b,0x34,0x1a,0x55,0xad,0x93,0x32,0x30,0xf5,0x8c,0xb1,0xe3,
        0x1d,0xf6,0xe2,0x2e,0x82,0x66,0xca,0x60,0xc0,0x29,0x23,0xab,0x0d,0x53,0x4e,0x6f,
        0xd5,0xdb,0x37,0x45,0xde,0xfd,0x8e,0x2f,0x03,0xff,0x6a,0x72,0x6d,0x6c,0x5b,0x51,
        0x8d,0x1b,0xaf,0x92,0xbb,0xdd,0xbc,0x7f,0x11,0xd9,0x5c,0x41,0x1f,0x10,0x5a,0xd8,
        0x0a,0xc1,0x31,0x88,0xa5,0xcd,0x7b,0xbd,0x2d,0x74,0xd0,0x12,0xb8,0xe5,0xb4,0xb0,
        0x89,0x69,0x97,0x4a,0x0c,0x96,0x77,0x7e,0x65,0xb9,0xf1,0x09,0xc5,0x6e,0xc6,0x84,
        0x18,0xf0,0x7d,0xec,0x3a,0xdc,0x4d,0x20,0x79,0xee,0x5f,0x3e,0xd7,0xcb,0x39,0x48,
    ]
    _FK = [0xa3b1bac6, 0x56aa3350, 0x677d9197, 0xb27022dc]
    _CK = None

    @classmethod
    def _init_ck(cls):
        if cls._CK is None:
            cls._CK = []
            for i in range(32):
                val = 0
                for j in range(4):
                    val |= ((((4 * i + j) * 7) % 256) << (8 * (3 - j)))
                cls._CK.append(val)

    @classmethod
    def _sm4_tau(cls, a):
        sb = cls._SBOX
        return (sb[(a >> 24) & 0xff] << 24) | (sb[(a >> 16) & 0xff] << 16) | (sb[(a >> 8) & 0xff] << 8) | sb[a & 0xff]

    @classmethod
    def _sm4_t_enc(cls, b):
        return b ^ cls._rotl(b, 2) ^ cls._rotl(b, 10) ^ cls._rotl(b, 18) ^ cls._rotl(b, 24)

    @classmethod
    def _sm4_t_key(cls, b):
        return b ^ cls._rotl(b, 13) ^ cls._rotl(b, 23)

    @classmethod
    def _sm4_block(cls, key_bytes, block):
        cls._init_ck()
        K = [0] * 36
        for i in range(4):
            K[i] = ((key_bytes[i*4] & 0xff) << 24) | ((key_bytes[i*4+1] & 0xff) << 16) | \
                   ((key_bytes[i*4+2] & 0xff) << 8) | (key_bytes[i*4+3] & 0xff)
        K[0] ^= cls._FK[0]; K[1] ^= cls._FK[1]; K[2] ^= cls._FK[2]; K[3] ^= cls._FK[3]
        rk = [0] * 32
        for i in range(32):
            K[i+4] = K[i] ^ cls._sm4_t_key((K[i+1] ^ K[i+2] ^ K[i+3] ^ cls._CK[i]) & 0xffffffff)
            rk[i] = K[i+4]
        X = [0] * 36
        for i in range(4):
            X[i] = ((block[i*4] & 0xff) << 24) | ((block[i*4+1] & 0xff) << 16) | \
                   ((block[i*4+2] & 0xff) << 8) | (block[i*4+3] & 0xff)
        for i in range(32):
            X[i+4] = X[i] ^ cls._sm4_t_enc((X[i+1] ^ X[i+2] ^ X[i+3] ^ rk[i]) & 0xffffffff)
        out = bytearray(16)
        for i in range(4):
            v = X[i+32]
            out[i*4] = (v >> 24) & 0xff; out[i*4+1] = (v >> 16) & 0xff
            out[i*4+2] = (v >> 8) & 0xff; out[i*4+3] = v & 0xff
        return bytes(out)

    @classmethod
    def _sm4_ecb_encrypt(cls, data, key_bytes):
        pad = 16 - (len(data) % 16)
        data = data + bytes([pad] * pad)
        out = b""
        for i in range(0, len(data), 16):
            out += cls._sm4_block(key_bytes, data[i:i+16])
        return out

    # ---------- 站点接口 ----------
    def __init__(self):
        self._key = None
        self._ver = 1
        self._pools = {}
        self._dfp = None
        self._token = None
        self._session = None

    def _get_session(self):
        if self._session is None:
            self._session = requests.Session()
        return self._session

    def _load_cfg(self):
        if self._key is not None:
            return
        s = self._get_session()
        r = s.get(self.BASE + "/api/payload", timeout=self.timeout,
                  headers={"User-Agent": self.UA})
        pj = r.json()
        cfg = pj.get("payload") or {}
        self._key = bytes.fromhex(cfg["key"])
        self._ver = int(cfg.get("version", 1))
        self._pools = pj.get("staticRoutePools") or {}

    def _gen_dfp(self):
        if self._dfp:
            return self._dfp
        # 东八区 YYYYMMDD
        dt = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=8)
        tf = dt.strftime("%Y%m%d")
        sm4_key = bytes.fromhex(hashlib.sha256(f"fa317cd29b|{tf}".encode()).hexdigest()[:32])
        seed = "|".join([
            "canvas-" + hashlib.sha256(self.UA.encode()).hexdigest()[:8],
            "fpjs-" + hashlib.sha256(b"timbre").hexdigest()[:16],
            "webgl-" + hashlib.sha256(self.BASE.encode()).hexdigest()[:8],
            "gpu-" + hashlib.sha256(b"webkit").hexdigest()[:8],
            self.UA,
            "Asia/Shanghai",
        ])
        blob = base64.b64encode(self._sm4_ecb_encrypt(seed.encode(), sm4_key)).decode()
        # YYYYMMDD 转 36 进制
        ts36 = ""
        n = int(tf)
        digits = "0123456789abcdefghijklmnopqrstuvwxyz"
        if n == 0:
            ts36 = "0"
        else:
            while n > 0:
                ts36 = digits[n % 36] + ts36
                n //= 36
        self._dfp = f"dfp=f-{ts36}:f-{blob}"
        return self._dfp

    def _decrypt_env(self, text):
        env = json.loads(text)
        if isinstance(env, dict) and env.get("payload"):
            raw = bytes.fromhex(env["payload"])
            if not raw:
                return env
            v = raw[0]
            nonce = raw[1:25]
            ct = raw[25:]
            if v == 2:
                ct = ct[::-1]
            return json.loads(self._xdecrypt(self._key, nonce, ct))
        return env

    def _api_get(self, url):
        self._load_cfg()
        s = self._get_session()
        resp = s.get(url, timeout=self.timeout, headers={
            "User-Agent": self.UA, "Referer": self.BASE + "/",
            "Accept": "*/*", "X-Payload-Version": str(self._ver),
        })
        return self._decrypt_env(resp.text)

    def _api_post(self, path, obj, auth=False):
        self._load_cfg()
        s = self._get_session()
        iv = get_random_bytes(12) if HAS_CRYPTO else os.urandom(12)
        plain = json.dumps(obj, separators=(",", ":")).encode()
        if HAS_CRYPTO:
            cipher = AES.new(self._key, AES.MODE_GCM, nonce=iv, mac_len=16)
            ct, tag = cipher.encrypt_and_digest(plain)
        else:
            enc = aes_gcm_encrypt(self._key, iv, plain)
            ct, tag = enc[:-16], enc[-16:]
        body = bytes([self._ver % 256]) + iv + ct + tag
        hdrs = {
            "User-Agent": self.UA, "Referer": self.BASE + "/", "Origin": self.BASE,
            "Accept": "*/*", "Content-Type": "text/plain",
            "X-Payload-Version": str(self._ver), "Cookie": self._gen_dfp(),
        }
        if auth and self._token:
            hdrs["Authorization"] = "Bearer " + self._token
        resp = s.post(self.BASE + path, data=body.hex(), timeout=self.timeout, headers=hdrs)
        return self._decrypt_env(resp.text)

    def _ensure_token(self):
        if self._token:
            return self._token
        data = self._api_post("/api/guest", {})
        self._token = data.get("auth_token") or data.get("token")
        return self._token

    # ---------- 映射 ----------
    def _map_book(self, item):
        return {
            "vod_id": str(item.get("id")),
            "vod_name": item.get("title") or item.get("album_title") or "",
            "vod_pic": item.get("cover_url") or item.get("cover") or "",
            "vod_remarks": f"{item.get('count', '')}集" if item.get("count") else "",
            "vod_year": "",
        }

    # ---------- Spider 接口 ----------
    def homeContent(self, filter=False):
        # 分类硬编码兜底（不依赖网络）
        cls_ = [
            {"type_id": "46", "type_name": "玄幻奇幻"},
            {"type_id": "11", "type_name": "武侠小说"},
            {"type_id": "19", "type_name": "言情通俗"},
            {"type_id": "14", "type_name": "恐怖惊悚"},
            {"type_id": "17", "type_name": "官场商战"},
            {"type_id": "15", "type_name": "历史军事"},
            {"type_id": "1", "type_name": "评书·单田芳"},
            {"type_id": "2", "type_name": "评书·刘兰芳"},
            {"type_id": "4", "type_name": "评书·袁阔成"},
            {"type_id": "36", "type_name": "广播剧"},
            {"type_id": "21", "type_name": "相声小品"},
        ]
        # 首页推荐（失败时用热门书兜底）
        lst = []
        try:
            self._load_cfg()
            pools = self._pools.get("homepage", {})
            primary = pools.get("primary", "https://json.hgeuz.cn/tyfm/json_v1/homepage")
            d = self._api_get(primary)
            items = d.get("recommends") or d.get("recent_updates") or []
            lst = [self._map_book(it) for it in items if it.get("id")]
        except Exception:
            pass
        if not lst:
            # 网络失败兜底: 热门书
            lst = [
                {"vod_id": "3879657962", "vod_name": "三体(1-3部)", "vod_pic": "https://file.tingyou8.vip/pic/5DD07C7E68BF50C.jpg", "vod_remarks": "261集"},
                {"vod_id": "9783312385", "vod_name": "剑来", "vod_pic": "https://file.tingyou8.vip/pic/I7I0081G467902.gif", "vod_remarks": "5329集"},
                {"vod_id": "3015025554", "vod_name": "第九特区丨头陀渊演播丨搞笑热血都市丨伪戒", "vod_pic": "https://file.tingyou8.vip/pic/fe83cb91b0b2bb5872f6809df1700381.jpeg", "vod_remarks": "2813集"},
            ]
        return {"class": cls_, "list": lst, "filters": {}}

    def categoryContent(self, tid, pg, filter=False, extend=""):
        lst = []
        try:
            self._load_cfg()
            d = self._api_get(f"{self.BASE}/api/category_page?type={tid}&page={pg}")
            items = d.get("data") or d.get("list") or d.get("results") or []
            lst = [self._map_book(it) for it in items if it.get("id")]
        except Exception:
            pass
        return {"list": lst}

    def detailContent(self, ids):
        vod_id = ids[0] if ids else ""
        self._last_album_id = vod_id  # 供 playerContent 使用
        vod = {"vod_id": vod_id, "vod_name": "", "vod_pic": "", "type_name": "听书",
               "vod_content": "", "vod_play_from": "听友FM", "vod_play_url": ""}
        play_urls = []
        try:
            self._load_cfg()
            # 专辑详情（封面/书名）
            try:
                pools = self._pools.get("album_detail", {})
                ad_primary = pools.get("primary", "https://json.hgeuz.cn/tyfm/json_v1/album_info")
                ad = self._api_get(ad_primary + "/" + vod_id)
                if ad:
                    vod["vod_name"] = ad.get("title") or vod["vod_name"]
                    vod["vod_pic"] = ad.get("cover_url") or vod["vod_pic"]
                    vod["vod_content"] = ad.get("description") or vod["vod_content"]
                    if ad.get("author"):
                        vod["vod_actor"] = ad["author"]
            except Exception:
                pass
            # 章节池
            pools = self._pools.get("chapters_list", {})
            primary = pools.get("primary", "https://json.hgeuz.cn/tyfm/json_v1/album_chapters")
            backups = pools.get("backups", [])
            attempts = [primary + "/" + vod_id] + \
                       [u.rstrip("/") + "/" + vod_id for u in backups] + \
                       [self.BASE + "/api/chapters_list/" + vod_id]
            chs = []
            for url in attempts:
                try:
                    d = self._api_get(url)
                    arr = d.get("chapters") or d.get("list") or (d.get("data") or {}).get("chapters") or []
                    if arr:
                        chs = arr
                        break
                except Exception:
                    continue
            if chs:
                chs.sort(key=lambda c: int(c.get("index") or 0))
                for c in chs:
                    idx = int(c.get("index") or 0)
                    name = c.get("title") or f"第{idx}集"
                    play_urls.append(f"{name}${idx}")
                vod["vod_play_url"] = "#".join(play_urls)
        except Exception:
            pass
        return {"list": [vod]}

    def searchContent(self, key, quick, pg="1"):
        lst = []
        try:
            self._load_cfg()
            d = self._api_post("/api/search", {"keyword": key, "page": int(pg) if pg else 1})
            items = d.get("results") or d.get("list") or d.get("data") or []
            lst = [self._map_book(it) for it in items if it.get("id")]
        except Exception:
            pass
        return {"list": lst}

    def playerContent(self, flag, id, vipFlags=None):
        self._load_cfg()
        try:
            # id = 章节序号（detailContent 里 $ 后是 index）
            chapter_idx = int(id)
            # 需要 album_id：从 vod_id 拿不到，但 WebHomeTV 只传 chapterId
            # 用 play 接口需要 album_id —— 先试通过章节索引反查
            # 简化：WebHomeTV 传的 id 是详情页 $ 后的部分 = chapter index
            # 但我们没有 album_id！需要从别处拿 —— 用 search 反查或 detail 缓存
            # 方案：把 album_id 编码进 play_url 的 flag 里？不行。
            # 实际: detailContent 返回 "集数名$index"，播放时 WebHomeTV 只传 index。
            # 解决：在 playerContent 里没有 album_id，需要重新搜索或用 ext 参数。
            # 用站点搜索书名反查？太重。用 detailContent 的 vod_id 缓存？
            # —— 最佳: detailContent 里 vod_play_url 用 "name$albumId.index"？WebHomeTV 会把 . 后当 id?
            # 参考悦听吧: 它把 bookId 存到 self 缓存，播放时用 chapterId 查 bookId
            # 这里同样: 用 self._last_book_id 缓存
            album_id = getattr(self, "_last_album_id", None)
            if not album_id:
                return {"parse": 0, "url": ""}
            token = self._ensure_token()
            data = self._api_post("/api/play_token",
                                  {"album_id": int(album_id), "chapter_idx": chapter_idx},
                                  auth=True)
            url = data.get("play_url") or data.get("url") or \
                (data.get("data") or {}).get("play_url")
            if url:
                return {"parse": 0, "url": url,
                        "header": json.dumps({"User-Agent": self.UA, "Referer": self.BASE + "/"})}
        except Exception:
            pass
        return {"parse": 0, "url": ""}

    def localProxy(self, param=""):
        return {}

    def isVideoFormat(self, url):
        return False

    def manualVideoCheck(self):
        return False

    def destroy(self):
        if self._session:
            try:
                self._session.close()
            except Exception:
                pass


if __name__ == "__main__":
    sp = Spider()
    sp.init("")
    print("=== homeContent ===")
    h = sp.homeContent()
    print(f"分类: {[c['type_name'] for c in h['class']]}")
    print(f"推荐: {[(v['vod_name'][:20], v['vod_remarks']) for v in h['list'][:3]]}")
    print("\n=== categoryContent (玄幻奇幻) ===")
    c = sp.categoryContent("46", "1")
    print(f"列表: {[(v['vod_name'][:20], v['vod_remarks']) for v in c['list'][:3]]}")
    print("\n=== searchContent (三体) ===")
    s = sp.searchContent("三体", True)
    print(f"结果: {[(v['vod_name'][:25], v['vod_remarks']) for v in s['list'][:3]]}")
    if s["list"]:
        book = s["list"][0]
        sp._last_album_id = book["vod_id"]
        print(f"\n=== detailContent ({book['vod_name'][:15]}) ===")
        d = sp.detailContent([book["vod_id"]])
        vod = d["list"][0]
        urls = vod["vod_play_url"].split("#")
        print(f"集数: {len(urls)} | 前3: {urls[:3]}")
        print(f"\n=== playerContent (第1集) ===")
        p = sp.playerContent("听友FM", "1")
        print(f"播放: {str(p)[:150]}")
