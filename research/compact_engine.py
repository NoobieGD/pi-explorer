"""Experimental exact Chudnovsky with cross-factor cancellation.

This is a RAM prototype, NOT a 200B-capable external-memory backend. Every merge
preserves T/Q and P/Q exactly. No rounded or unchecked digits are accepted.
Sources: Cheng et al. ISSAC 2007 (factor cancellation); see RESEARCH.txt.
"""
import sys,time,math,zlib,json
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];sys.path.insert(0,str(ROOT))
import engine
g=engine.g
A=13591409;B=545140134;C=g.mpz(640320)**3//24

def payload(value):return (value.bit_length()+7)//8 if value is not None else 0

def split(a,b,cancel=True,cutoff=32,need_product=True,stats=None,on_work=None):
    if b-a==1:
        p=g.mpz(1) if a==0 else g.mpz(6*a-5)*(2*a-1)*(6*a-1)
        q=g.mpz(1) if a==0 else g.mpz(a)**3*C
        t=p*(A+B*a)*(-1 if a&1 else 1)
        if on_work:on_work(1,'Splitting the exact series')
        return p if need_product else None,q,t
    mid=(a+b)//2
    p1,q1,t1=split(a,mid,cancel,cutoff,True,stats,on_work)
    p2,q2,t2=split(mid,b,cancel,cutoff,need_product,stats,on_work)
    observe=stats is not None and b-a>=cutoff
    before=payload(p1)+payload(q1)+payload(t1)+payload(p2)+payload(q2)+payload(t2) if observe else 0
    if cancel and b-a>=cutoff:
        if on_work:on_work(0,'Cancelling common factors')
        started=time.perf_counter();common=g.gcd(p1,q2)
        if common>1:
            p1=g.divexact(p1,common);q2=g.divexact(q2,common)
        if stats is not None:
            stats['gcdSeconds']+=time.perf_counter()-started
            stats['cancelledBits']+=common.bit_length()-1;stats['gcdCalls']+=1
    t=t1*q2+p1*t2;q=q1*q2;p=p1*p2 if need_product else None
    if observe:
        # Integer payload only: NOT RSS, a disk estimate, or GMP scratch usage.
        stats['largestMergePayloadBytes']=max(stats['largestMergePayloadBytes'],before+payload(p)+payload(q)+payload(t))
    return p,q,t

def compute(count,cancel=True,cutoff=32,inspect=False,progress=None):
    count=engine.resource_plan.digit_count(count)
    # A real resource check prevents invoking giant GMP arithmetic on this PC.
    engine.computation_plan(count,ROOT/'data','chudnovsky','ram')
    stats={'gcdSeconds':0.,'gcdCalls':0,'cancelledBits':0,'largestMergePayloadBytes':0}
    started=time.perf_counter();n=count+32;terms=n//14+1
    completed=0;last_update=0
    def on_work(amount,label):
        nonlocal completed,last_update
        completed+=amount
        now=time.perf_counter()
        if now-last_update>=.15:
            progress(.03+.61*completed/terms,'Compact · '+label+' · overall estimate');last_update=now
    if progress:progress(.02,'Compact · preparing exact arithmetic')
    _,q,t=split(0,terms,cancel,cutoff,False,stats,on_work if progress else None)
    stats.update(splitSeconds=time.perf_counter()-started,rootPayloadBytes=payload(q)+payload(t),terms=terms)
    if progress:progress(.69,'Compact · integer square root')
    root=g.isqrt(g.mpz(10005)*g.mpz(10)**(2*n))
    if progress:progress(.82,'Compact · final division and decimal conversion')
    text=str(q*426880*root//t)
    assert len(text)==n+1 and text.startswith('3141592653589793238'[:min(n+1,19)])
    stats.update(seconds=time.perf_counter()-started,digits=count,method='exact-cancelled' if cancel else 'exact-standard')
    if inspect:
        inspection=time.perf_counter();samples=[]
        for name,value in [('q',q),('t',t)]:
            raw=g.to_binary(value);packed=zlib.compress(raw,1)
            samples.append({'name':name,'binaryBytes':len(raw),'zlibBytes':len(packed),'ratio':len(packed)/len(raw)})
        stats.update(compressionSamples=samples,inspectionSeconds=time.perf_counter()-inspection)
    return text[1:count+1],stats

def plan(count,budget_gib=210):
    count=engine.resource_plan.digit_count(count);ceiling=int(budget_gib)*1024**3
    # Rational upper bound on log2(10); all storage arithmetic stays integral.
    precision_bits=((count+32)*332193+99999)//100000
    number_bytes=(precision_bits+7)//8
    return {'digits':count,'budgetBytes':ceiling,'textOutputBytes':count+2,
            'oneFullPrecisionBinaryValueBytes':number_bytes,
            'twoFullPrecisionValuesBytes':2*number_bytes,
            'threeFullPrecisionValuesBytes':3*number_bytes,
            'temporaryBudgetAfterTextBytes':ceiling-(count+2),
            'requiresOutputToBeStaged':True,
            'status':'research_only',
            'nonComputingCheck':True,
            'verifiedUnderBudget':False,
            'peakStorageUpperBoundBytes':None,
            'launchableAtRequestedScale':False,
            'reason':'The exact-cancellation prototype uses in-RAM GMP. A proven out-of-core arithmetic schedule and measured multiplication/conversion workspace are still required. The two-value calculation is an idealized floor, not a complete peak-space plan.'}

if __name__=='__main__':
    import argparse
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--plan',type=str);p.add_argument('--digits',type=int,default=100000);args=p.parse_args()
    if args.plan:print(json.dumps(plan(args.plan),indent=2))
    else:
        digits,stats=compute(args.digits,inspect=True)
        expected=engine.compute_pi(args.digits,'mpfr')
        assert digits==expected,'Independent MPFR comparison failed'
        print(json.dumps({**stats,'verifiedAgainst':'MPFR'},indent=2))
