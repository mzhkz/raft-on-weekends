from decimal import Decimal, ROUND_FLOOR
import random

def fast_pow_mod(base: Decimal, exponent: Decimal, modulus: Decimal) -> Decimal:
    """高速な冪剰余演算"""
    result = Decimal(1)
    base = base % modulus
    
    while exponent > 0:
        if int(exponent) & 1:  # Decimal型を整数に変換してビット演算
            # 大きな数値の掛け算を文字列経由で処理
            result = Decimal(str(int(result) * int(base) % int(modulus)))
        # 同様に base の計算も修正
        base = Decimal(str(int(base) * int(base) % int(modulus)))
        exponent = Decimal(int(exponent) // 2)  # exponentを整数に変換して割り算
    return result

def divmod(a: Decimal, b: Decimal, n: Decimal) -> Decimal:
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

def polynomial(x: Decimal, a: list, q: Decimal) -> Decimal:
    """多項式の計算"""
    value = Decimal(a[0])
    for i in range(1, len(a)):
        value = (value + fast_pow_mod(x, Decimal(i), q) * a[i]) % q
    return value

def split(secret: str, n: int, k: int, p: Decimal, q: Decimal, generator: Decimal) -> dict:
    """秘密を分散"""
    # ASCII文字列を16進数に変換してからDecimalに変換
    try:
        hex_value = ''.join(hex(ord(c))[2:].zfill(2) for c in secret)
        S = Decimal(int(hex_value, 16))
    except ValueError:
        raise ValueError("Failed to convert secret to decimal")
    
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
        # 1からq-1の範囲でランダムな係数を生成
        coeff = Decimal(random.randrange(1, int(q)))
        a.append(coeff)
        C.append({
            'i': Decimal(i),
            'c': fast_pow_mod(g, coeff, p)
        })
    
    # シェアの生成
    for i in range(n):
        x = str(i + 1)
        D.append({
            'x': x,
            'y': str(polynomial(x, a, q))
        })
    
    return {'D': D, 'C': C}

def lagrange_basis(data: list, j: int, q: Decimal) -> dict:
    """ラグランジュ基底多項式の計算"""
    denominator = Decimal(1)
    numerator = Decimal(1)
    
    for i in range(len(data)):
        if data[j]['x'] != data[i]['x']:
            # 文字列として保存されているx値をDecimalに変換
            x_i = Decimal(data[i]['x'])
            x_j = Decimal(data[j]['x'])
            denominator = (denominator * (x_i - x_j)) % q
            numerator = (numerator * x_i) % q
    
    return {'numerator': numerator, 'denominator': denominator}

def combine(shares: list, prime: Decimal) -> str:
    """シェアの結合"""
    S = Decimal(0)
    
    for i in range(len(shares)):
        basis = lagrange_basis(shares, i, prime)
        # 文字列として保存されているy値をDecimalに変換
        y_value = Decimal(shares[i]['y'])
        S = (S + y_value * divmod(basis['numerator'], 
             basis['denominator'], prime)) % prime
    
    # Decimalから16進数文字列に変換
    hex_str = hex(int(S))[2:]
    # 16進数文字列が奇数の長さの場合、先頭に0を追加
    if len(hex_str) % 2 != 0:
        hex_str = '0' + hex_str
    
    # 16進数文字列をASCII文字列に変換
    try:
        result = ''
        for i in range(0, len(hex_str), 2):
            result += chr(int(hex_str[i:i+2], 16))
        return result
    except ValueError:
        raise ValueError("Failed to convert decimal to string")

def verify(share: dict, C: list, prime: Decimal, generator: Decimal) -> bool:
    """シェアの検証"""
    p = Decimal(prime)
    g = Decimal(generator)
    lG = fast_pow_mod(g, share['y'], p)
    rG = Decimal(1)
    
    for i, commitment in enumerate(C):
        e = fast_pow_mod(share['x'], Decimal(i), p)
        basis = fast_pow_mod(commitment['c'], e, p)
        rG = (rG * basis) % p
    
    return rG == lG 