import json, itertools, math
from PIL import Image
C={'Z2':(45,15),'Z4':(15,45),'Z6':(75,45)}
res=[]
for p in itertools.permutations(C):
    pts=[(0,0)]+[C[z] for z in p]+[(0,0)]
    res.append((sum(math.hypot(a[0]-b[0],a[1]-b[1]) for a,b in zip(pts,pts[1:])),p))
for r in sorted(res): print(round(r[0],4),r[1])
print('margin',260-min(res)[0])
print(open('route.json').read()[:900])
r=json.load(open('results.json'));print(r['stressed'],r['field_mean_4dp'],r['zone_means_4dp'])
im=Image.open('ndvi_map.png').convert('RGB')
for y in range(100,700,60): print(y,[im.getpixel((x,y)) for x in (150,300,420,560,800)])
# ground truth NDVI at a few pixels vs map: top-left pixel of data
red=Image.open('inputs/red.png').convert('L');nir=Image.open('inputs/nir.png').convert('L')
for (r_,c) in [(2,2),(57,2),(2,87),(57,87)]:
    a=red.getpixel((c,r_));b=nir.getpixel((c,r_));print('data',r_,c,(b-a)/(b+a))
