from PIL import Image
import json, itertools, math, csv
def px(n):
    im=Image.open('inputs/%s.png'%n); w,h=im.size; d=list(im.getdata()); print(n,im.mode,w,h)
    return [d[r*w:(r+1)*w] for r in range(h)]
R=px('red'); N=px('nir')
nd=[[ (N[r][c]-R[r][c])/(N[r][c]+R[r][c]) if (N[r][c]+R[r][c]) else None for c in range(90)] for r in range(60)]
zero=sum(1 for r in nd for v in r if v is None); print('zero',zero)
names={}
k=1
for r0 in (0,30):
    for c0 in (0,30,60):
        s=0;n=0
        for r in range(r0,r0+30):
            for c in range(c0,c0+30):
                s+=nd[r][c];n+=1
        names['Z%d'%k]=s/n;k+=1
fm=sum(v for r in nd for v in r)/5400
for z,m in names.items(): print(z,round(m,6),'%.4f'%m,m<0.35,abs(m-0.35)<=0.0005)
print('field',fm,'%.4f'%fm)
res=json.load(open('results.json'))
for z in names: assert abs(res['zone_means_full'][z]-names[z])<1e-9,z
print('json ok',res['field_mean_4dp'],res['stressed'])
print(open('zones.csv').read())
rows=list(csv.DictReader(open('zones.csv')))
print(len(rows),list(rows[0].keys()))
for rw in rows:
    z=rw['zone']; print(z,rw['mean_ndvi']=='%.4f'%names[z], (rw['stressed'].lower()=='true')==(names[z]<0.35))
# png
im=Image.open('ndvi_map.png').convert('RGB'); print(im.size)
W,H=im.size
cols=set(im.getdata()); print('distinct colours',len(cols))
# find axes: sample quadrant mean colours in left 60% region
def avg(x0,y0,x1,y1):
    t=[0,0,0];n=0
    for y in range(y0,y1):
        for x in range(x0,x1):
            p=im.getpixel((x,y))
            for i in range(3):t[i]+=p[i]
            n+=1
    return [round(v/n) for v in t]
# approximate axes bbox: find via non-white scan
print('NW',avg(150,100,250,160),'SW',avg(150,560,250,620),'NE',avg(650,100,750,160),'SE',avg(650,560,750,620))
# route
C={'Z2':(45,15),'Z4':(15,45),'Z6':(75,45)}
res_r=[]
for p in itertools.permutations(C):
    pts=[(0,0)]+[C[z] for z in p]+[(0,0)]
    L=sum(math.hypot(a[0]-b[0],a[1]-b[1]) for a,b in zip(pts,pts[1:]))
    res_r.append((L,p))
for L,p in sorted(res_r): print(round(L,4),p)
best=min(res_r)[0]; print('margin',260-best)
print(open('route.json').read()[:800])
