"""Constant identities and exact, certified high-precision GMP algorithms."""
import math
from pathlib import Path

CONSTANTS={
 'pi':dict(label='Pi',symbol='π',integer=3,prefix='14159265358979323846264338327950288419716939937510',native='pi',algorithm='chudnovsky'),
 'e':dict(label="Euler's number",symbol='e',integer=2,prefix='71828182845904523536028747135266249775724709369995',native='e',algorithm='exp(1)'),
 'sqrt2':dict(label='Square root of 2',symbol='√2',integer=1,prefix='41421356237309504880168872420969807856967187537694',native='sqrt:2',algorithm='newton',radicand=2),
 'sqrt3':dict(label='Square root of 3',symbol='√3',integer=1,prefix='73205080756887729352744634150587236694280525381038',native='sqrt:3',algorithm='newton',radicand=3),
 'sqrt5':dict(label='Square root of 5',symbol='√5',integer=2,prefix='23606797749978969640917366873127623544061835961152',native='sqrt:5',algorithm='newton',radicand=5),
 'phi':dict(label='Golden ratio',symbol='φ',integer=1,prefix='61803398874989484820458683436563811772030917980576',native='phi',algorithm='newton'),
}

def identify(value='pi'):
    if not isinstance(value,str) or value not in CONSTANTS:raise ValueError('Choose pi, e, sqrt2, sqrt3, sqrt5 or phi')
    return value

def infer(path,value=None):
    if value is not None:return identify(value)
    name=Path(path).stem.split('-',1)[0]
    return name if name in CONSTANTS else 'pi'

def describe(value='pi'):return {'id':identify(value),**CONSTANTS[value]}

def decimal_digits(integer,count,value):
    raw=str(integer);spec=CONSTANTS[identify(value)]
    if len(raw)!=count+1 or int(raw[0])!=spec['integer']:raise ArithmeticError('Invalid integer part or decimal output length')
    digits=raw[1:]
    if not digits.startswith(spec['prefix'][:min(count,50)]):raise ArithmeticError('Constant prefix verification failed')
    return digits

def mpfr_digits(count,value,progress=None):
    import gmpy2 as g
    # Directed lower/upper bounds must have the same truncated decimal integer.
    # Precision retries make rounding near a decimal boundary explicit.
    for extra in (48,96,192):
        precision=math.ceil((count+extra)*math.log2(10))+32;bounds=[];scale=g.mpz(10)**count
        for rounding in (g.RoundDown,g.RoundUp):
            with g.context(precision=precision,round=rounding):
                if value=='pi':number=g.const_pi()
                elif value=='e':number=g.exp(g.mpfr(1))
                elif value=='phi':number=(g.sqrt(g.mpfr(5))+1)/2
                else:number=g.sqrt(g.mpfr(CONSTANTS[value]['radicand']))
                bounds.append(g.floor(number*scale))
        if bounds[0]==bounds[1]:return decimal_digits(bounds[0],count,value)
        if progress:progress(.75,'Refining directed MPFR bounds')
    raise ArithmeticError('Directed MPFR bounds did not certify the requested digits')

def compute(count,value='pi',method='exact',progress=None):
    import gmpy2 as g
    import resource_plan
    count=resource_plan.digit_count(count);value=identify(value)
    if value=='pi':
        from engine import compute_pi
        return compute_pi(count,'chudnovsky' if method in ('exact','auto') else method,progress)
    if method not in ('auto','exact','chudnovsky','mpfr'):raise ValueError('This engine is pi-only; choose Auto, Exact GMP or MPFR')
    if count>20_000_000:
        from engine import computation_plan,ROOT
        computation_plan(count,ROOT/'data','mpfr' if method=='mpfr' else 'exact','ram',constant=value)
    if progress:progress(.02,'Preparing '+CONSTANTS[value]['label'])
    if method=='mpfr':return mpfr_digits(count,value,progress)
    if value!='e':
        if progress:progress(.15,'Exact GMP integer square root')
        scale=g.mpz(10)**count
        radicand=5 if value=='phi' else CONSTANTS[value]['radicand']
        root=g.isqrt(radicand*scale*scale)
        # These integer operations certify truncation; no floating arithmetic.
        result=(root+scale)//2 if value=='phi' else root
        if progress:progress(.9,'Converting certified integer to decimal')
        return decimal_digits(result,count,value)
    # Sum 1/k! using a balanced product/sum tree, not sequential big divisions.
    target=count+32;n=max(8,int(target/max(1,math.log10(max(10,target)))*1.3))
    while math.lgamma(n+1)/math.log(10)<target:n=max(n+1,int(n*1.1))
    scale=g.mpz(10)**count
    for attempt in range(4):
        completed=0;update=max(1,n//40)
        def split(a,b):
            nonlocal completed
            if b-a==1:
                completed+=1
                if progress and completed%update==0:progress(.05+.70*completed/n,'Factorial series · balanced binary splitting')
                return g.mpz(1),g.mpz(a)
            middle=(a+b)//2;p,q=split(a,middle);r,s=split(middle,b)
            return p*s+r,q*s
        p,q=split(1,n+1)
        if progress:progress(.80,'Certifying factorial-series remainder')
        lower=scale*(p+q)//q
        # 0 < e - sum(0..n)1/k! < 1/(n*n!). Both bounds are exact rationals.
        upper=(scale*(n*(p+q)+1)-1)//(n*q)
        if lower==upper:
            if progress:progress(.95,'All requested digits certified')
            return decimal_digits(lower,count,value)
        n+=max(32,n//10)
    raise ArithmeticError('Factorial remainder did not certify all digits')
