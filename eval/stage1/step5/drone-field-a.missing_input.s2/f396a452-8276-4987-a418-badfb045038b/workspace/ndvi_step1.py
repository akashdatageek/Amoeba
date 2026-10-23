from PIL import Image
import numpy as np, csv
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
red=np.array(Image.open('inputs/red.png')).astype('float64')
nir=np.array(Image.open('inputs/nir.png')).astype('float64')
print(red.shape,nir.shape)
den=nir+red
with np.errstate(all='ignore'):
    ndvi=np.where(den>0,(nir-red)/den,np.nan)
print('NaN',int(np.isnan(ndvi).sum()))
rows=[]
for k in range(1,7):
    r=(k-1)//3;c=(k-1)%3
    m=np.nanmean(ndvi[30*r:30*r+30,30*c:30*c+30])
    s=m<0.35
    rows.append((k,m,s))
    print('Z%d %.4f %.6f %s near=%s'%(k,m,m,s,abs(m-0.35)<0.0005))
f=np.nanmean(ndvi);print('Field %.4f %.6f'%(f,f))
with open('zones.csv','w',newline='') as fh:
    w=csv.writer(fh);w.writerow(['zone','mean_ndvi','stressed'])
    for k,m,s in rows:w.writerow(['Z%d'%k,'%.4f'%m,str(bool(s)).lower()])
fig,ax=plt.subplots(figsize=(9,6.5))
im=ax.imshow(ndvi,cmap='RdYlGn',origin='upper',extent=[0,90,60,0])
plt.colorbar(im,ax=ax,label='NDVI')
for x in(30,60):ax.axvline(x,color='white')
ax.axhline(30,color='white')
for k in range(1,7):
    ax.text(30*((k-1)%3)+15,30*((k-1)//3)+15,'Z%d'%k,ha='center',va='center',fontsize=14,fontweight='bold')
ax.set_xlabel('x east (m)');ax.set_ylabel('y south (m)');ax.set_title('NDVI map (field mean %.4f)'%f)
fig.savefig('ndvi_map.png',dpi=150)
