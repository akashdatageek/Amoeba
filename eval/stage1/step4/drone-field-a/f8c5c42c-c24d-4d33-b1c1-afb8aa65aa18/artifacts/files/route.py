import json, itertools, math
r=json.load(open('results.json'))
C={'Z1':(15,15),'Z2':(45,15),'Z3':(75,15),'Z4':(15,45),'Z5':(45,45),'Z6':(75,45)}
st=r['stressed']
H=(0,0)
def d(a,b): return math.hypot(a[0]-b[0],a[1]-b[1])
res=[]
for p in itertools.permutations(st):
    pts=[H]+[C[z] for z in p]+[H]
    L=sum(d(pts[i],pts[i+1]) for i in range(len(pts)-1))
    res.append((L,p))
res.sort()
print(len(res))
for L,p in res: print(round(L,4),p)
L,p=res[0]
pts=[H]+[C[z] for z in p]+[H]
names=['Home']+list(p)+['Home']
legs=[]
for i in range(len(pts)-1):
    legs.append({'from':names[i],'to':names[i+1],'from_xy':pts[i],'to_xy':pts[i+1],'distance_m':round(d(pts[i],pts[i+1]),1),'raw':d(pts[i],pts[i+1])})
    print(legs[-1])
print(sum(l['distance_m'] for l in legs), L, 260-L)
json.dump({'order':names,'legs':legs,'total_m':round(L,1),'within_limit':L<=260,'margin_m':round(260-L,1),'permutations':len(res),'runner_up':{'order':['Home']+list(res[1][1])+['Home'],'length_m':round(res[1][0],1)}},open('route.json','w'),indent=1)
