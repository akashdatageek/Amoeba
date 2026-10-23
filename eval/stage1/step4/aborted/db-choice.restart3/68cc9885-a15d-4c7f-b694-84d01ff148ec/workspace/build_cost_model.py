from openpyxl import Workbook
from openpyxl.styles import Font
wb=Workbook(); wa=wb.active; wa.title='Assumptions'; wp=wb.create_sheet('Prices'); wm=wb.create_sheet('Model'); ws=wb.create_sheet('Summary')
# ---- Assumptions: key,label,low,base,high,note
AS=[('tenants','Tenants',50,50,50,'Given in task'),
('gb','GB raw per tenant',200,200,200,'Given in task (50 x 200 = 10,000 GB raw)'),
('qpm','Peak queries per minute, all tenants',5000,5000,5000,'Given in task (combined peak)'),
('qps','Peak queries per second','={qpm}/60','=B{qps}','=B{qps}','5,000 / 60 = 83.3'),
('hours','Hours per month',730,730,730,'ASSUMPTION: 730 h/month'),
('cpu','vCPU-seconds per analytic query',0.2,0.4,0.8,'ASSUMPTION [unverified]: no engine test exists (step 7 was proxy only), so widened 4x'),
('util','Target peak CPU utilisation',0.6,0.6,0.5,'ASSUMPTION [unverified]'),
('R','Read replicas / read-serving secondaries (beyond primary)',1,2,3,'ASSUMPTION: hot set 10-20% of footprint is spread over primary + replicas'),
('pgfoot','PostgreSQL storage footprint factor (x raw)',1.25,1.375,1.5,'Role-card range 1.25-1.5x (indexes, bloat, WAL headroom)'),
('mfoot','MongoDB footprint factor before indexes (x raw)',0.5,0.75,1.0,'Role-card range 0.5-1.0x (compression). No real-engine ratio exists, proxy sizes NOT used'),
('idxadd','MongoDB index add-on (fraction of data)',0.10,0.15,0.25,'ASSUMPTION [unverified]'),
('backup','Backup storage held (x data footprint)',0.5,1.0,1.5,'ASSUMPTION [unverified]: retention/incrementals; no free allowance assumed'),
('eu_prem','EU region price premium vs US list (applied x EU share)',0.0,0.08,0.15,'ASSUMPTION [unverified]; Atlas backup rows in [S113] show 0% (eu-west-1) to 6.5% (eu-central-1)'),
('ovh','Two-region overhead (share of compute) when EU share < 100%',0.05,0.10,0.15,'ASSUMPTION: separate EU and non-EU deployments duplicate standby/min sizes'),
('egress','Dashboard egress GB per month',1000,2000,5000,'ASSUMPTION [unverified]'),
('inter','Inter-region transfer GB per month (only if EU share < 100%)',0,500,2000,'ASSUMPTION [unverified]'),
('fill','Max fill of Atlas 4 TB shard storage',0.8,0.8,0.8,'ASSUMPTION: headroom'),
('cfg','Atlas sharded-cluster config server/mongos overhead (share of compute)',0.10,0.10,0.10,'ASSUMPTION [unverified]'),
('gcpf','Atlas on GCP price factor vs AWS tier price',1.0,1.0,1.05,'ASSUMPTION: S70 grid does not split AWS/GCP'),
('extra','Atlas storage billed beyond tier-included, USD per GB-month per node copy',0.0,0.0,0.03,'ASSUMPTION [unverified]: base assumes storage included in tier price'),
('memcs','Cloud SQL GiB memory per vCPU',6,6,6,'ASSUMPTION'),
('memal','AlloyDB GiB memory per vCPU',8,8,8,'ASSUMPTION (AlloyDB 8 GB/vCPU ratio)')]
AR={k:i+4 for i,(k,*_) in enumerate(AS)}
wa['A1']='Assumptions - all figures are ESTIMATES from public list prices, not quotes. Scenario columns: Low / Base / High. Edit blue cells.'
for j,h in enumerate(['Parameter','Low','Base','High','Source / note']): wa.cell(3,j+1,h)
for k,l,lo,ba,hi,n in AS:
    r=AR[k]; wa.cell(r,1,l)
    for c,v in zip((2,3,4),(lo,ba,hi)):
        wa.cell(r,c,v.format(**AR) if isinstance(v,str) else v)
    wa.cell(r,5,n)
    if not (isinstance(lo,str)):
        for c in (2,3,4): wa.cell(r,c).font=Font(name='Arial',color='0000FF')
# ---- Prices
U='https://www.mongodb.com/pricing'
PR=[('atlas_m50','Atlas (AWS/GCP)','Dedicated M50 8 vCPU 32 GB, 160 GB-4 TB','USD/hour',2.00,'[S113] S70 tier table; cloud/region of base price not stated',U),
('atlas_m60','Atlas (AWS/GCP)','Dedicated M60 16 vCPU 64 GB, 320 GB-4 TB','USD/hour',3.95,'[S113] S70 tier table',U),
('atlas_m80','Atlas (AWS/GCP)','Dedicated M80 32 vCPU 128 GB, 750 GB-4 TB','USD/hour',7.30,'[S113] S70 tier table',U),
('atlas_max','Atlas','Max dedicated-cluster storage (forces sharding for >4 TB)','GB',4000,'[S74] S70 page: 10 GB to 4 TB',U),
('atlas_bk','Atlas (AWS)','Per-GB-month row for eu-west-1/us-east-1 (column heading not confirmed; used as backup storage)','USD/GB-month',0.048,'[S113] S70 region table; meaning UNVERIFIED',U),
('rds_v','AWS RDS PostgreSQL','Memory-optimised instance, single-AZ, per vCPU','USD/vCPU-hour',0.125,'ASSUMPTION [unverified]: hourly table not found [S57]; replace from AWS calculator','https://aws.amazon.com/rds/postgresql/pricing/'),
('rds_s','AWS RDS PostgreSQL','gp3 storage, single-AZ','USD/GB-month',0.115,'ASSUMPTION [unverified]: not found for eu-west-1 [S57]','https://aws.amazon.com/rds/postgresql/pricing/'),
('rds_b','AWS RDS PostgreSQL','Backup storage beyond allowance','USD/GB-month',0.095,'ASSUMPTION [unverified]: not found [S57]','https://aws.amazon.com/rds/postgresql/pricing/'),
('au_v','AWS Aurora PostgreSQL','Memory-optimised instance, Standard, per vCPU','USD/vCPU-hour',0.145,'ASSUMPTION [unverified]: not found [S61]','https://aws.amazon.com/rds/aurora/pricing/'),
('au_p','AWS Aurora PostgreSQL','I/O-Optimized instance premium (x)','factor',1.30,'ASSUMPTION [unverified]; $0.225 storage below assumed to be I/O-Optimized, so no per-request I/O line','https://aws.amazon.com/rds/aurora/pricing/'),
('au_s','AWS Aurora PostgreSQL','Storage (shared by all nodes)','USD/GB-month',0.225,'[S63] page worked example (80 GB = $18.00); region/config not stated','https://aws.amazon.com/rds/aurora/pricing/'),
('au_b','AWS Aurora PostgreSQL','Backup storage','USD/GB-month',0.021,'ASSUMPTION [unverified]: not found [S61]','https://aws.amazon.com/rds/aurora/pricing/'),
('cs_vha','GCP Cloud SQL PG Enterprise','HA vCPU on-demand','USD/vCPU-hour',0.0826,'[S67] region not confirmed (likely us-central1)','https://cloud.google.com/sql/pricing'),
('cs_v','GCP Cloud SQL PG Enterprise','vCPU on-demand (replicas)','USD/vCPU-hour',0.0413,'[S67]','https://cloud.google.com/sql/pricing'),
('cs_mha','GCP Cloud SQL PG Enterprise','HA memory','USD/GiB-hour',0.014,'ASSUMPTION: 2 x $0.007 [S69] (HA vCPU is 2x single in [S67])','https://cloud.google.com/sql/pricing'),
('cs_m','GCP Cloud SQL PG Enterprise','Memory on-demand','USD/GiB-hour',0.007,'[S69] (a second table shows $0.009; series unidentified)','https://cloud.google.com/sql/pricing'),
('cs_s','GCP Cloud SQL PG','SSD storage, single zone','USD/GB-month',0.17,'ASSUMPTION [unverified]: not found [S65]','https://cloud.google.com/sql/pricing'),
('cs_b','GCP Cloud SQL PG','Backup storage','USD/GB-month',0.08,'ASSUMPTION [unverified]: not found [S65]','https://cloud.google.com/sql/pricing'),
('al_v','GCP AlloyDB','vCPU','USD/vCPU-hour',0.066,'ASSUMPTION [unverified]: S69 vCPU columns unlabelled (second = 2x first)','https://cloud.google.com/alloydb/pricing'),
('al_m','GCP AlloyDB','Memory','USD/GiB-hour',0.0112,'ASSUMPTION [unverified]: not captured [S66]','https://cloud.google.com/alloydb/pricing'),
('al_s','GCP AlloyDB','Regional cluster storage = 0.0004109 x 730','USD/GiB-month','=0.0004109*730','[S69] region not confirmed','https://cloud.google.com/alloydb/pricing'),
('al_b','GCP AlloyDB','Backup storage = 0.000137 x 730','USD/GiB-month','=0.000137*730','[S69]','https://cloud.google.com/alloydb/pricing'),
('eg','AWS and GCP','Internet egress to dashboard users','USD/GB',0.09,'ASSUMPTION [unverified]: not found on any fetched page',''),
('ir','AWS and GCP','Inter-region transfer','USD/GB',0.02,'ASSUMPTION [unverified]: not found on any fetched page','')]
PRw={k:i+4 for i,(k,*_) in enumerate(PR)}
for j,h in enumerate(['Provider','Item','Unit','USD price','Source / status','URL','Date retrieved']): wp.cell(3,j+1,h)
wp['A1']='Prices - public list prices, retrieved 2026-10-22 (America/Chicago). Estimates, not quotes.'
# note: columns shift: price in D -> reference col D
for k,p,i,u,v,s,url in PR:
    r=PRw[k]
    for c,x in zip(range(1,8),(p,i,u,v,s,url,'2026-10-22')): wp.cell(r,c,x)
def A(k,r): return f"INDEX(Assumptions!$B${AR[k]}:$D${AR[k]},$C{r})"
def P(k): return f"Prices!$D${PRw[k]}"
# ---- Model
hd=['Combination','Scenario','Scenario idx (1=Low,2=Base,3=High)','EU share','Total vCPU needed','Read-serving nodes','vCPU per node','Storage footprint GB','Shards','Compute USD/mo (US list)','Storage USD/mo','Backup USD/mo','Egress+transfer USD/mo','Region factor','Two-region overhead USD','TOTAL USD/mo','USD per tenant']
wm['A1']='Model - every cell is a formula over Assumptions and Prices; D (EU share) is the sensitivity input. Estimates, not quotes.'
for j,h in enumerate(hd): wm.cell(3,j+1,h)
combos=['AWS RDS PostgreSQL','AWS Aurora PostgreSQL','GCP Cloud SQL PostgreSQL','GCP AlloyDB','MongoDB Atlas on AWS','MongoDB Atlas on GCP']
cases=[('Low',1,.5),('Base',2,.5),('High',3,.5),('Base EU20%',2,.2),('Base EU100%',2,1.0)]
row=4; MR=[]
for cb in combos:
    for sn,idx,eu in cases:
        r=row; a=lambda k:A(k,r)
        wm.cell(r,1,cb); wm.cell(r,2,sn); wm.cell(r,3,idx); wm.cell(r,4,eu)
        f={}
        f['E']=f"={a('qps')}*{a('cpu')}/{a('util')}"
        atlas='Atlas' in cb
        if not atlas:
            f['F']=f"=1+{a('R')}"; f['G']=f"=CEILING(MAX(E{r}/F{r},8),8)"
            f['H']=f"={a('tenants')}*{a('gb')}*{a('pgfoot')}"; f['I']=1
            if 'RDS' in cb:
                f['J']=f"=G{r}*{P('rds_v')}*(2+{a('R')})*{a('hours')}"; f['K']=f"=H{r}*{P('rds_s')}*(2+{a('R')})"; f['L']=f"=H{r}*{a('backup')}*{P('rds_b')}"
            elif 'Aurora' in cb:
                f['J']=f"=G{r}*{P('au_v')}*{P('au_p')}*(1+{a('R')})*{a('hours')}"; f['K']=f"=H{r}*{P('au_s')}"; f['L']=f"=H{r}*{a('backup')}*{P('au_b')}"
            elif 'Cloud SQL' in cb:
                f['J']=f"=G{r}*(({P('cs_vha')}+{a('memcs')}*{P('cs_mha')})+{a('R')}*({P('cs_v')}+{a('memcs')}*{P('cs_m')}))*{a('hours')}"; f['K']=f"=H{r}*{P('cs_s')}*(2+{a('R')})"; f['L']=f"=H{r}*{a('backup')}*{P('cs_b')}"
            else:
                f['J']=f"=G{r}*(2+{a('R')})*({P('al_v')}+{a('memal')}*{P('al_m')})*{a('hours')}"; f['K']=f"=H{r}*{P('al_s')}"; f['L']=f"=H{r}*{a('backup')}*{P('al_b')}"
        else:
            f['H']=f"={a('tenants')}*{a('gb')}*{a('mfoot')}*(1+{a('idxadd')})"
            f['I']=f"=ROUNDUP(H{r}/({P('atlas_max')}*{a('fill')}),0)"; f['F']=f"=I{r}*3"
            f['G']=f"=CEILING(MAX(E{r}/F{r},8),8)"
            gf=f"*{a('gcpf')}" if 'GCP' in cb else ''
            f['J']=f"=F{r}*IF(G{r}<=8,{P('atlas_m50')},IF(G{r}<=16,{P('atlas_m60')},{P('atlas_m80')}))*{a('hours')}*(1+{a('cfg')}){gf}"
            f['K']=f"=H{r}*3*{a('extra')}"; f['L']=f"=H{r}*{a('backup')}*{P('atlas_bk')}"
        f['M']=f"={a('egress')}*{P('eg')}+IF(D{r}<1,{a('inter')}*{P('ir')},0)"
        f['N']=f"=1+D{r}*{a('eu_prem')}"
        f['O']=f"=IF(D{r}<1,{a('ovh')}*J{r}*N{r},0)"
        f['P']=f"=(J{r}+K{r}+L{r})*N{r}+O{r}+M{r}"
        f['Q']=f"=P{r}/{a('tenants')}"
        for c,v in f.items(): wm[f"{c}{r}"]=v
        MR.append((cb,sn,eu,r)); row+=1
# ---- Summary
ws['A1']='Summary - monthly cost, 50 tenants x 200 GB, 5,000 queries/min peak, HA. ESTIMATES from public list prices, not quotes.'
for j,h in enumerate(['Provider','Database','Scenario','EU share','Monthly USD','USD per tenant','Price rows / assumptions']): ws.cell(3,j+1,h)
for i,(cb,sn,eu,r) in enumerate(MR):
    s=4+i; prov='AWS' if cb.startswith('AWS') or 'on AWS' in cb else 'GCP'
    db=cb.replace('AWS ','').replace('GCP ','')
    ws.cell(s,1,prov); ws.cell(s,2,db); ws.cell(s,3,sn); ws.cell(s,4,f"=Model!D{r}"); ws.cell(s,5,f"=Model!P{r}"); ws.cell(s,6,f"=Model!Q{r}"); ws.cell(s,7,'See Prices rows (source/status col) and Assumptions')
    ws.cell(s,5).number_format='#,##0'; ws.cell(s,6).number_format='#,##0.0'; ws.cell(s,4).number_format='0%'
n=4+len(MR)+1
ws.cell(n,1,'Check: sum of Summary monthly USD'); ws.cell(n,5,f"=SUM(E4:E{3+len(MR)})")
for sh in wb:
    for rw in sh.iter_rows():
        for c in rw:
            if c.value is not None and not (c.font and c.font.color and c.font.color.rgb=='000000FF'): c.font=Font(name='Arial',bold=(c.row==3))
    sh.column_dimensions['A'].width=34
    for col in 'BCDEFGHIJKLMNOPQ': sh.column_dimensions[col].width=16
wb.save('cost_model.xlsx')
import json; json.dump(MR,open('mr.json','w'))
