from decimal import Decimal
import random

def fast_pow_mod(base, exponent, modulus):
    """高速な冪剗余演算"""
    result = Decimal(1)
    base = Decimal(base) % modulus
    exponent = int(exponent)  # Decimalのまま使うと遅くなるため
    
    while exponent > 0:
        if exponent & 1:
            result = (result * base) % modulus
        base = (base * base) % modulus
        exponent >>= 1
    return result

def divmod(a, b, n):
    """モジュラ逆数を計算"""
    t, newt = Decimal(0), Decimal(1)
    r, newr = n, b % n
    
    while newr != 0:
        quotient = r // newr
        t, newt = newt, t - quotient * newt
        r, newr = newr, r - quotient * newr
    
    if r > 1:
        return Decimal(0)
    if t < 0:
        t = t + n
    return (a * t) % n

def polynomial(x, a, q):
    """多項式の計算"""
    value = Decimal(a[0])
    for i in range(1, len(a)):
        value = (value + fast_pow_mod(x, i, q) * a[i]) % q
    return value

def split(secret, n, k, p, q, generator):
    """秘密を分散"""
    if not isinstance(secret, str) or not secret.startswith('0x'):
        raise TypeError("secret must be a hex string starting with 0x")
    
    S = Decimal(int(secret, 16))
    g = Decimal(generator)
    p = Decimal(p)
    q = Decimal(q)
    
    if S > q or g > p:
        raise ValueError("Invalid parameters")
    
    # 係数の生成
    a = [S]
    D = []  # シェア
    C = [{'i': Decimal(0), 'c': fast_pow_mod(g, S, p)}]  # コミットメント
    
    # ランダム係数の生成
    for i in range(1, k):
        coeff = Decimal(random.randrange(1, int(q)))
        a.append(coeff)
        C.append({
            'i': Decimal(i),
            'c': fast_pow_mod(g, coeff, p)
        })
    
    # シェアの生成
    for i in range(n):
        x = Decimal(i + 1)
        D.append({
            'x': x,
            'y': polynomial(x, a, q)
        })
    
    return {'D': D, 'C': C}

def lagrange_basis(data, j, q):
    """ラグランジュ基底多項式の計算"""
    denominator = Decimal(1)
    numerator = Decimal(1)
    
    for i in range(len(data)):
        if data[j]['x'] != data[i]['x']:
            denominator = (denominator * (data[i]['x'] - data[j]['x'])) % q
            numerator = (numerator * data[i]['x']) % q
    
    return {'numerator': numerator, 'denominator': denominator}

def combine(shares, prime):
    """シェアの結合"""
    S = Decimal(0)
    
    for i in range(len(shares)):
        basis = lagrange_basis(shares, i, prime)
        S = (S + shares[i]['y'] * divmod(basis['numerator'], 
             basis['denominator'], prime)) % prime
    
    return S

def verify(share, C, prime, generator):
    """シェアの検証"""
    p = Decimal(prime)
    g = Decimal(generator)
    lG = fast_pow_mod(g, share['y'], p)
    rG = Decimal(1)
    
    for i, commitment in enumerate(C):
        e = fast_pow_mod(share['x'], i, p)
        basis = fast_pow_mod(commitment['c'], e, p)
        rG = (rG * basis) % p
    
    return rG == lG 