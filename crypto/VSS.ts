import { Decimal } from "decimal.js";
// rounding
// Decimal.set({ crypto: true }); // 予測不可能なランダム生成
Decimal.set({ precision: 1e7 }); // 小数点
Decimal.set({ toExpPos: 0 }); //指数部を指定
Decimal.set({ modulo: Decimal.ROUND_FLOOR }); // mod 記号の指定
Decimal.set({ rounding: 5 }); //丸目モードの指定、

// DSA key generator
// from cryptography.hazmat.primitives.asymmetric by python3
// https://nvlpubs.nist.gov/nistpubs/FIPS/NIST.FIPS.186-4.pdf

function divmod(a: Decimal, b: Decimal, n: Decimal) {
	let aCopy = Decimal.isDecimal(a) ? a : new Decimal(a);
	let bCopy = Decimal.isDecimal(b) ? b : new Decimal(b);
	let nCopy = Decimal.isDecimal(n) ? n : new Decimal(n);
	let t = new Decimal("0");
	let nt = new Decimal("1");
	let r = nCopy;
	let nr = bCopy.mod(n);
	let tmp;
	while (!nr.isZero()) {
		let quot = Decimal.floor(r.div(nr));
		tmp = nt;
		nt = t.sub(quot.times(nt));
		t = tmp;
		tmp = nr;
		nr = r.sub(quot.times(nr));
		r = tmp;
	}
	if (r.greaterThan(1)) return new Decimal(0);
	if (t.isNegative()) t = t.add(n);
	return aCopy.times(t).mod(n);
}

function expmod(x: Decimal, n: Decimal, mod: Decimal): Decimal {
	let ret = new Decimal(1);
	while (n.greaterThan(0)) {
		if (!n.mod(2).equals(0)) ret = ret.mul(x).mod(mod); // n の最下位bitが 1 ならば x^(2^i) をかける
		x = x.mul(x).mod(mod);
		n = n.div(2).floor(); // n を1bit 左にずらす
	}
	return ret;
}

function pow(x: Decimal, n: Decimal): Decimal {
	let ret = new Decimal(1);
	while (n.greaterThan(0)) {
		if (!n.mod(2).equals(0)) ret = ret.mul(x); // n の最下位bitが 1 ならば x^(2^i) をかける
		x = x.mul(x);
		n = n.div(2).floor(); // n を1bit 左にずらす
	}
	return ret;
}

export interface DecimalShare {
	x: Decimal;
	y: Decimal;
}
export interface DecimalCommitment {
	i: Decimal;
	c: Decimal;
}

function random(lower: Decimal, upper: Decimal) {
	if (lower > upper) {
		const temp = lower;
		lower = upper;
		upper = temp;
	}

	return lower.add(
		Decimal.random()
			.times(upper.sub(lower.add(1)))
			.floor()
	);
}

// Polynomial function where `a` is the coefficients
function polynomial(x: Decimal, a: Decimal[], q: Decimal) {
	let value = a[0];
	for (let i = 1; i < a.length; i++) {
		// value = value.add(x.pow(i).times(a[i]));
		value = value.add(expmod(x, new Decimal(i), q).times(a[i])).mod(q);
	}
	return value;
}

function split(
	secret: string,
	n: number,
	k: number,
	p: Decimal,
	q: Decimal,
	generator: Decimal
) {
	if (
		Number.isInteger(secret) ||
		Number.isInteger(p) ||
		Number.isInteger(generator)
	) {
		throw new TypeError(
			"The shamir.split() function must be called with a String<secret>" +
				"but got Number<secret>."
		);
	}

	if (Number.isInteger(p)) {
		throw new TypeError(
			"The shamir.split() function must be called with a Decimal<prime>" +
				"but got Number<prime>."
		);
	}

	if (secret.substring(0, 2) !== "0x") {
		throw new TypeError(
			"The shamir.split() function must be called with a" + "Decimal<secret>"
		);
	}

	if (!Decimal.isDecimal(p)) {
		throw new TypeError(
			"The shamir.split() function must be called with a" + "Decimal<prime>"
		);
	}

	if (!Decimal.isDecimal(generator)) {
		throw new TypeError(
			"The shamir.split() function must be called with a" + "Decimal<generator>"
		);
	}

	const S = new Decimal(secret);
	const g = new Decimal(generator);

	if (S.greaterThan(q)) {
		throw new RangeError(
			"The String<secret> must be less than the Decimal<prime>."
		);
	}

	if (g.greaterThan(p)) {
		throw new RangeError(
			"The Decimal<generator> must be less than the Decimal<prime>."
		);
	}

	let a: Decimal[] = [S];
	let D: DecimalShare[] = [];
	let C: DecimalCommitment[] = [
		{
			i: new Decimal("0"),
			// c: g.pow(S).mod(p)
			c: expmod(g, S, p),
		},
	];

	for (let i = 1; i < k; i++) {
		let coeff = random(new Decimal(1), q.sub(1));
		a.push(coeff);
		C.push({
			i: new Decimal(i),
			c: expmod(g, coeff, p),
		});
	}
	for (let i = 0; i < n; i++) {
		let x = new Decimal(i + 1);
		D.push({
			x,
			y: polynomial(x, a, q),
		});
	}
	return { D, C };
}

function lagrangeBasis(data: DecimalShare[], j: number, q: Decimal) {
	// Lagrange basis evaluated at 0, i.e. L(0).
	// You don't need to interpolate the whole polynomial to get the secret, you
	// only need the constant term.
	let denominator = new Decimal(1);
	let numerator = new Decimal(1);
	for (let i = 0; i < data.length; i++) {
		if (!data[j].x.equals(data[i].x)) {
			denominator = denominator.times(data[i].x.minus(data[j].x)).mod(q);
		}
	}

	for (let i = 0; i < data.length; i++) {
		if (!data[j].x.equals(data[i].x)) {
			numerator = numerator.times(data[i].x).mod(q);
		}
	}

	return {
		numerator,
		denominator,
	};
}

function lagrangeInterpolate(data: DecimalShare[], q: Decimal) {
	let S = new Decimal(0);

	for (let i = 0; i < data.length; i++) {
		let basis = lagrangeBasis(data, i, q);
		S = S.add(
			data[i].y.times(divmod(basis.numerator, basis.denominator, q))
		).mod(q);
	}

	// const rest = S.mod(q);
	const rest = S;

	return rest;
}

function combine(shares: DecimalShare[], prime: Decimal) {
	const p = prime;

	// Wrap with Decimal on the input shares
	const decimalShares = shares.map((share) => ({
		x: new Decimal(share.x),
		y: new Decimal(share.y),
	}));

	return lagrangeInterpolate(decimalShares, p);
}

function verify(
	share: DecimalShare,
	C: DecimalCommitment[],
	prime: Decimal,
	generator: Decimal
) {
	const p = new Decimal(prime);
	const g = new Decimal(generator);
	let lG = expmod(g, new Decimal(share.y), p);
	let rG = new Decimal(1);
	console.log("init rG: ", rG.toHex());
	for (let i = 0; i < C.length; i++) {
		console.log("++++++++ com " + i);
		let commitment = C[i];
		let e = pow(share.x, new Decimal(i));
		let basis = expmod(commitment.c, e, p);
		rG = rG.mul(basis).mod(p);
		console.log("share.x: ", share.x.toHex());
		console.log("share.y: ", share.y.toHex());
		console.log("commitment: ", commitment.c.toHex());
		console.log("e: ", e.toHex());
		console.log("basis: ", basis.toHex());
		console.log("c rg: ", rG.toHex());
	}
	console.log("rg: " + rG.toHex());
	console.log("lg: " + lG.toHex());
	return rG.equals(lG);
}

export default { split, combine, verify, pow, expmod, divmod, random };
