from gmpy2 import mpz, random_state, powmod, t_mod, div
import random

rand = random_state(random.randrange(2**32))

def divmod(a, b, n):
    """モジュラ逆数を計算"""
    t, newt = mpz(0), mpz(1)
    r, newr = n, b % n
    
    while newr != 0:
        quotient = r // newr
        t, newt = newt, t - quotient * newt
        r, newr = newr, r - quotient * newr
    
    if r > 1:
        return mpz(0)
    if t < 0:
        t = t + n
    return (a * t) % n

def polynomial(x, a, q):
    """多項式の計算"""
    value = a[0]
    for i in range(1, len(a)):
        value = (value + powmod(x, i, q) * a[i]) % q
    return value

def split(secret, n, k, p, q, generator):
    """秘密を分散"""
    if not isinstance(secret, str) or not secret.startswith('0x'):
        raise TypeError("secret must be a hex string starting with 0x")
    
    S = mpz(secret, 16)
    g = mpz(generator)
    
    if S > q or g > p:
        raise ValueError("Invalid parameters")
    
    # 係数の生成
    a = [S]
    D = []  # シェア
    C = [{'i': mpz(0), 'c': powmod(g, S, p)}]  # コミットメント
    
    # ランダム係数の生成
    for i in range(1, k):
        coeff = mpz(random.randrange(1, int(q)))
        a.append(coeff)
        C.append({
            'i': mpz(i),
            'c': powmod(g, coeff, p)
        })
    
    # シェアの生成
    for i in range(n):
        x = mpz(i + 1)
        D.append({
            'x': x,
            'y': polynomial(x, a, q)
        })
    
    return {'D': D, 'C': C}

def lagrange_basis(data, j, q):
    """ラグランジュ基底多項式の計算"""
    denominator = mpz(1)
    numerator = mpz(1)
    
    for i in range(len(data)):
        if data[j]['x'] != data[i]['x']:
            denominator = (denominator * (data[i]['x'] - data[j]['x'])) % q
            numerator = (numerator * data[i]['x']) % q
    
    return {'numerator': numerator, 'denominator': denominator}

def combine(shares, prime):
    """シェアの結合"""
    S = mpz(0)
    
    for i in range(len(shares)):
        basis = lagrange_basis(shares, i, prime)
        S = (S + shares[i]['y'] * divmod(basis['numerator'], 
             basis['denominator'], prime)) % prime
    
    return S

def verify(share, C, prime, generator):
    """シェアの検証"""
    p = mpz(prime)
    g = mpz(generator)
    lG = powmod(g, share['y'], p)
    rG = mpz(1)
    
    for i, commitment in enumerate(C):
        e = pow(share['x'], i)
        basis = powmod(commitment['c'], e, p)
        rG = (rG * basis) % p
    
    return rG == lG 