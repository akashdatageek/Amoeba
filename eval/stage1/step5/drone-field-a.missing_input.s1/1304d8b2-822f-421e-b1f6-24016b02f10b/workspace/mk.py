import json,numpy as np,csv
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
r=json.load(open('results.json'));a=np.load('ndvi.npy')
print(a.shape,a.dtype,np.isnan(a).sum())
st=set(r['stressed'])
with open('zones.csv','w',newline='') as f:
    w=csv.writer(f);w.writerow(['zone','mean_ndvi','stressed'])
    for i in range(1,7):
        z=f'Z{i}';w.writerow([z,f"{r['zone_means_4dp'][z]:.4f}",z in st])
fig,ax=plt.subplots(figsize=(10,7.5),dpi=100)
im=ax.imshow(a,cmap='RdYlGn',vmin=-0.1,vmax=0.8,origin='upper',extent=[0,90,60,0],interpolation='nearest')
for x in (30,60):ax.axvline(x,color='white',lw=2)
ax.axhline(30,color='white',lw=2)
for i in range(1,7):
    cx,cy=r['centres_m_xy'][f'Z{i}']
    ax.text(cx,cy,f'Z{i}',color='black',ha='center',va='center',fontsize=16,fontweight='bold',bbox=dict(fc='white',alpha=.6,ec='none'))
ax.set_xlabel('x (m, east from west edge)');ax.set_ylabel('y (m, south from north edge)')
ax.set_title('NDVI map (north at top)')
plt.colorbar(im,ax=ax,label='NDVI')
fig.savefig('ndvi_map.png');
from PIL import Image
print(Image.open('ndvi_map.png').size)
print(open('zones.csv').read())
rows=list(csv.DictReader(open('zones.csv')))
print(len(rows),all(float(x['mean_ndvi'])==r['zone_means_4dp'][x['zone']] and (x['stressed']=='True')==(x['zone'] in st) for x in rows))
