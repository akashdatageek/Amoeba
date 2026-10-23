import itertools, json
from fractions import Fraction
W=[18000,12500,22000,9000,15500,7000,20500,11000,14000,8500]
M=[220,340,150,410,95,280,190,365,120,255]
T={'A':(45000,1100,35000,210),'B':(45000,1100,35000,210),'C':(30000,1100,50000,185),'D':(26000,900,27500,245)}  # cost in cents
names=list(T); caps=[T[n][0] for n in names]; lim=[T[n][1] for n in names]; fx=[T[n][2] for n in names]; rt=[T[n][3] for n in names]
feas=0; best=None; nopt=0; costs={}; opts=[]
for a in itertools.product(range(4),repeat=10):
    w=[0]*4; m=[0]*4
    for i,t in enumerate(a):
        w[t]+=W[i]; m[t]+=M[i]
    ok=True
    for t in range(4):
        if w[t]>caps[t] or m[t]>lim[t]: ok=False;break
    if not ok: continue
    feas+=1
    c=sum(fx[t]+rt[t]*m[t] for t in range(4) if m[t]>0)
    costs[c]=costs.get(c,0)+1
    if best is None or c<best: best=c; nopt=1; opts=[a]
    elif c==best: nopt+=1; opts.append(a)
def fmt(c): return f"{c//100}.{c%100:02d}"
top5=sorted(costs)[:5]
# canonical optimum: A/B-symmetric twins
def detail(a):
    d={}
    for t,n in enumerate(names):
        L=[i+1 for i in range(10) if a[i]==t]
        w=sum(W[i-1] for i in L); m=sum(M[i-1] for i in L)
        d[n]=dict(loads=[f"L{i}" for i in L],weight_lb=w,miles=m,fixed=fmt(fx[t]) if L else "0.00",variable=fmt(rt[t]*m),cost=fmt(fx[t]*(1 if L else 0)+rt[t]*m),
                  cap=caps[t],limit=lim[t])
    return d
out=dict(optimal_assignment=detail(opts[0]),total_cost=fmt(best),feasible_count=feas,optimal_count=nopt,
 top5_distinct_costs=[dict(cost=fmt(c),num_assignments=costs[c]) for c in top5],
 all_optimal_assignments=[{n:[f"L{i+1}" for i in range(10) if a[i]==t] for t,n in enumerate(names)} for a in opts],
 total_weight=sum(W),sum_capacity=sum(caps),fixed_all_four=fmt(sum(fx)))
json.dump(out,open('solution.json','w'),indent=1)
print(json.dumps(out,indent=1))
# 3-truck check
import itertools as it
print("max cap any 3 trucks",max(sum(c) for c in it.combinations(caps,3)))
