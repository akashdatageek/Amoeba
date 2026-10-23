import numpy as np, matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from PIL import Image
a=np.loadtxt('ndvi_values.csv',delimiter=','); print(a.shape,np.nanmin(a),np.nanmax(a))
fig,ax=plt.subplots(figsize=(6,5.5))
im=ax.imshow(a,cmap='RdYlGn',vmin=-1,vmax=1,origin='upper')
cb=fig.colorbar(im,ax=ax); cb.set_label('NDVI')
ax.axvline(19.5,color='k',ls='--',lw=1.5)
ax.text(19.5,-1.2,'West | East',ha='center',va='bottom',fontsize=9)
ax.set_xlabel('Column (west → east)'); ax.set_ylabel('Row (north → south)')
ax.set_title('NDVI map, 40x40 field (vmin=-1, vmax=1)',pad=18)
fig.tight_layout(); fig.savefig('ndvi.png',dpi=150); 
print(im.get_clim(), im.get_cmap().name)
i=Image.open('ndvi.png'); print(i.format,i.size,i.mode)
