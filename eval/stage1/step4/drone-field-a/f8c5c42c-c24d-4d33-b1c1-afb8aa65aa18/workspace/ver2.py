import warnings; warnings.filterwarnings('ignore')
from PIL import Image
import json, itertools, math, csv
def px(n):
    im=Image.open('inputs/%s.png'%n); w,h=im.size; d=list(im.getdata()); return w,h,[d[r*w:(r+1)*w] for r in range(h)]
w,h,R=px('red'); _,_,N=px('nir')
print(w,h)
nd=[[ (N[r][c]-R[r][c])/(N[r][c]+R[r][c]) if N[r][c]+R[r][c] else None for c in range(w)] for r in range(h)]
print('zero den',sum(1 for r in range(h) for c in range(w) if N[r][c]+R[r][c]==0))
M={}
for i in range(6):
    r0=30*(i//3); c0=30*(i%3); s=0
    for r in range(r0,r0+30):
        for c in range(c0,c0+30): s+=nd[r][c]
    M['Z%d'%(i+1)]=s/900
tot=sum(v for row in nd for v in row)/5400
print({k:round(v,6) for k,v in M.items()},round(tot,6))
print(open('zones.csv').read())
rows=list(csv.DictReader(open('zones.csv')))
for x in rows:
    assert abs(float(x['mean_ndvi'])-round(M[x['zone']],4))<1e-9,x
    assert (x['stressed'].lower()=='true')==(M[x['zone']]<0.35)
print('csv ok',len(rows),[x['zone'] for x in rows])
print('near thr',[k for k,v in M.items() if abs(v-0.35)<=0.0005])
j=json.load(open('results.json')); print(j['zone_means_4dp'],j['field_mean_4dp'],j['stressed'])
# png
im=Image.open('ndvi_map.png').convert('RGB'); print(im.size,len(set(im.getdata())))
# orientation: sample map pixels; axes extent unknown -> find Z1 vs Z4 mean colour in axes region
W,H=im.size
# find axes bbox: non-white big region
px_=im.load()
# locate gridlines (black) : search dark pixels
import collections
dark=[(x,y) for y in range(H) for x in range(W) if sum(px_[x,y])<60]
xs=collections.Counter(x for x,y in dark); ys=collections.Counter(y for x,y in dark)
print('dark cols',[x for x,c in xs.items() if c>300][:20]); print('dark rows',[y for y,c in ys.items() if c>300][:20])
# route
C={'Z2':(45,15),'Z4':(15,45),'Z6':(75,45)}
res=[]
for p in itertools.permutations(C):
    pts=[(0,0)]+[C[z] for z in p]+[(0,0)]
    res.append((sum(math.dist(pts[i],pts[i+1]) for i in range(len(pts)-1)),p))
res.sort(); print(res)
rj=json.load(open('route.json')); print({k:v for k,v in rj.items() if k!='legs'})
