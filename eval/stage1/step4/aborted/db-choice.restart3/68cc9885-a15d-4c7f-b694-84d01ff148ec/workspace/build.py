from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill
wb=Workbook(); F=Font(name='Arial',size=10); B=Font(name='Arial',size=10,bold=True)
wa=wb.active; wa.title='Assumptions'; wp=wb.create_sheet('Prices'); wm=wb.create_sheet('Model'); ws=wb.create_sheet('Summary')
# ---- Assumptions
wa.append(['Key','Assumption','Low','Base','High','Note / source']); R={}
def A(k,lab,lo,ba=None,hi=None,note=''):
    ba=lo if ba is None else ba; hi=ba if hi is None else hi
    wa.append([k,lab,lo,ba,hi,note]); R[k]=wa.max_row
A('tenants','Tenants',50,note='given')
A('gb','GB per tenant',200,note='given')
r=wa.max_row+1; wa.append(['raw_gb','Raw data GB (=tenants x GB)']+[f'={c}{R["tenants"]}*{c}{R["gb"]}' for c in 'CDE']+['derived: 50 x 200 = 10,000 GB']); R['raw_gb']=r
A('qpm','Peak queries per minute (all tenants combined)',5000,note='given')
r=wa.max_row+1; wa.append(['qps','Peak queries per second']+[f'={c}{R["qpm"]}/60' for c in 'CDE']+['5,000/60 = 83.3']); R['qps']=r
A('hours','Hours per month',730,note='assumption (8,760/12)')
A('vcpu','vCPU per PostgreSQL node',16,32,48,'ASSUMPTION: 83.3 qps x 0.2/0.4/0.6 CPU-s per query = 17/33/50 busy cores, split over primary + 1 read node, ~50% headroom')
A('memv','GB RAM per vCPU',8,note='ASSUMPTION: hot set 10-20% of 10 TB = 1-2 TB cannot be cached; 8 GB/vCPU memory-optimised class')
A('pgf','PostgreSQL storage footprint factor',1.25,1.4,1.5,'role-card range 1.25-1.5x raw; no real-engine ratio exists (prototype was a proxy)')
A('mcomp','MongoDB compressed data factor',0.5,0.7,1.0,'role-card range 0.5-1.0x raw')
A('midx','MongoDB index overhead factor',0.15,0.2,0.25,'ASSUMPTION')
r=wa.max_row+1; wa.append(['mfoot','MongoDB footprint factor (data + indexes)']+[f'={c}{R["mcomp"]}+{c}{R["midx"]}' for c in 'CDE']+['derived']); R['mfoot']=r
A('shardgb','Target GB per Atlas shard (limit 4 TB dedicated cluster [S74])',3000,2500,2000,'ASSUMPTION; 10 TB exceeds 4 TB cluster max, so sharding is forced')
A('anodes','Nodes per Atlas shard (replica set, HA)',3,note='Atlas replica set = 3 nodes (assumption)')
A('rdsunits','RDS compute units (Multi-AZ primary = 2 + 1 read replica)',3,note='ASSUMPTION')
A('rdscopies','RDS storage copies (Multi-AZ 2 + replica 1)',3,note='ASSUMPTION')
A('rdsiops','RDS extra provisioned IOPS',0,6000,20000,'ASSUMPTION')
A('aurnodes','Aurora instances (writer + 1 reader)',2,note='ASSUMPTION; storage shared, 1 copy billed')
A('cscopies','Cloud SQL storage copies (HA 2 + replica 1)',3,note='ASSUMPTION')
A('alnodes','AlloyDB compute nodes (primary + 1 read node; HA standby assumed not billed separately)',2,note='ASSUMPTION - unconfirmed')
A('bk','Billable backup as share of footprint (beyond free allowance)',0.3,0.6,1.0,'ASSUMPTION')
A('egr','Internet egress GB per month (dashboards)',500,1000,2000,'ASSUMPTION')
A('chg','Monthly changed share copied to second EU region (DR, stays inside EU)',0.02,0.05,0.10,'ASSUMPTION; GDPR: backups/replicas kept in EU')
A('ioq','Aurora I/O requests per query',50,100,200,'ASSUMPTION')
A('util','Average load as share of peak',0.3,note='ASSUMPTION')
A('uplift','EU region price uplift vs US-priced base',1.0,1.1,1.2,'ASSUMPTION: EU-region rates not found on fetched pages')
A('split','Overhead when tenants are split across EU and US deployments',0.1,0.15,0.2,'ASSUMPTION: two smaller deployments cost more than one')
A('pm','Multiplier on ASSUMED (unverified) prices',0.85,1.0,1.25,'widens scenario where the price was not found')
A('eu20','EU share sensitivity 1',0.2,note='given sensitivity'); A('eu50','EU share base',0.5,note='given: 50% EU'); A('eu100','EU share sensitivity 2',1.0,note='given sensitivity')
# ---- Prices
wp.append(['Key','Provider','Item','Unit','USD price','Status','Source tag','URL','Date retrieved'])
P={}
U={'rds':'https://aws.amazon.com/rds/postgresql/pricing/','aur':'https://aws.amazon.com/rds/aurora/pricing/','cs':'https://cloud.google.com/sql/pricing','al':'https://cloud.google.com/alloydb/pricing','at':'https://www.mongodb.com/pricing'}
NF='not found on fetched page; use vendor calculator before purchase'
def Pr(k,prov,item,unit,val,status,tag,url): wp.append([k,prov,item,unit,val,status,tag,url,'2026-10-22']); P[k]=(wp.max_row,status)
Pr('rds_vcpu','AWS RDS PG','Multi-AZ-unit instance rate per vCPU-hour incl. 8 GB/vCPU (single-AZ unit)','USD/vCPU-hour',0.13,'ASSUMPTION','[unverified] '+NF,U['rds'])
Pr('rds_stor','AWS RDS PG','gp3 storage','USD/GB-month',0.115,'ASSUMPTION','[unverified] '+NF,U['rds'])
Pr('rds_bk','AWS RDS PG','Backup beyond free','USD/GB-month',0.095,'ASSUMPTION','[unverified] '+NF,U['rds'])
Pr('rds_iops','AWS RDS PG','Extra provisioned IOPS','USD/IOPS-month',0.02,'ASSUMPTION','[unverified] '+NF,U['rds'])
Pr('aur_vcpu','AWS Aurora PG','Instance rate per vCPU-hour incl. memory','USD/vCPU-hour',0.145,'ASSUMPTION','[unverified] '+NF,U['aur'])
Pr('aur_stor','AWS Aurora PG','Storage (region/config not stated in excerpt)','USD/GB-month',0.225,'LIST','[S63] via [S61]',U['aur'])
Pr('aur_bk','AWS Aurora PG','Backup beyond free','USD/GB-month',0.021,'ASSUMPTION','[unverified] '+NF,U['aur'])
Pr('aur_io','AWS Aurora PG','I/O requests (Standard)','USD/million requests',0.20,'ASSUMPTION','[unverified] '+NF,U['aur'])
Pr('cs_vcpu','GCP Cloud SQL','Enterprise vCPU on-demand (region not confirmed)','USD/vCPU-hour',0.0413,'LIST','[S67]',U['cs'])
Pr('cs_vcpu_ha','GCP Cloud SQL','Enterprise HA vCPU on-demand','USD/vCPU-hour',0.0826,'LIST','[S67]',U['cs'])
Pr('cs_mem','GCP Cloud SQL','Memory on-demand','USD/GiB-hour',0.007,'LIST','[S69]',U['cs'])
Pr('cs_mem_ha','GCP Cloud SQL','HA memory (assumed 2x single, as vCPU is)','USD/GiB-hour',0.014,'ASSUMPTION','derived from [S67] ratio; unconfirmed',U['cs'])
Pr('cs_ssd','GCP Cloud SQL','SSD storage = 0.000465753 x 730','USD/GiB-month','=0.000465753*730','LIST','[S106]',U['cs'])
Pr('cs_bk','GCP Cloud SQL','Backups = 0.000109589 x 730','USD/GiB-month','=0.000109589*730','LIST','[S106]',U['cs'])
Pr('al_vcpu','GCP AlloyDB','vCPU on-demand (first table; region not confirmed)','USD/vCPU-hour',0.06608,'LIST','[S106]',U['al'])
Pr('al_mem','GCP AlloyDB','Memory on-demand','USD/GiB-hour',0.0112,'LIST','[S106]',U['al'])
Pr('al_stor','GCP AlloyDB','Regional cluster storage = 0.0004109 x 730','USD/GiB-month','=0.0004109*730','LIST','[S69]',U['al'])
Pr('al_bk','GCP AlloyDB','Backup = 0.000137 x 730','USD/GiB-month','=0.000137*730','LIST','[S69]',U['al'])
for t,v in (('m50',2.00),('m60',3.95),('m80',7.30)):
    Pr('at_'+t,'Atlas on AWS','Dedicated '+t.upper()+' node (price grid not found)','USD/node-hour',v,'ASSUMPTION','[unverified] '+NF,U['at'])
for t,v in (('m50',2.00),('m60',3.95),('m80',7.30)):
    Pr('ag_'+t,'Atlas on GCP','Dedicated '+t.upper()+' node (price grid not found)','USD/node-hour',v,'ASSUMPTION','[unverified] '+NF,U['at'])
Pr('at_stor','Atlas AWS+GCP','Extra provisioned storage per node','USD/GB-month',0.30,'ASSUMPTION','[unverified] '+NF,U['at'])
Pr('at_bk','Atlas AWS+GCP','Backup','USD/GB-month',0.14,'ASSUMPTION','[unverified] '+NF,U['at'])
Pr('egr_aws','AWS','Internet egress','USD/GB',0.09,'ASSUMPTION','[unverified] '+NF,'https://aws.amazon.com/ec2/pricing/on-demand/')
Pr('egr_gcp','GCP','Internet egress (tier/region unconfirmed)','USD/GiB',0.19,'LIST','[S106]',U['cs'])
Pr('ir_aws','AWS','Inter-region transfer','USD/GB',0.02,'ASSUMPTION','[unverified] '+NF,'https://aws.amazon.com/ec2/pricing/on-demand/')
Pr('ir_gcp','GCP','Inter-region transfer','USD/GiB',0.05,'ASSUMPTION','[unverified] '+NF,U['cs'])
Pr('ref_atlas','MongoDB Atlas','Entry dedicated price (reference only, not used)','USD/hour',0.08,'REFERENCE','[S74]',U['at'])
# ---- Model
H=['ID','Provider','Database','Scenario','EU share','Region blend factor','Compute USD','Storage USD','Backup USD','I/O + IOPS USD','Transfer USD','Total USD/month','USD per tenant','Atlas shards']
wm.append(H)
combos=[('AWS','RDS PostgreSQL'),('AWS','Aurora PostgreSQL'),('GCP','Cloud SQL PostgreSQL'),('GCP','AlloyDB'),('AWS','MongoDB Atlas'),('GCP','MongoDB Atlas')]
SC=[('Low','C'),('Base','D'),('High','E')]
eurefs=[('eu20','C'),('eu50','C'),('eu100','C')]
def mk(prov,db,scn,sc,eukey):
    r=wm.max_row+1
    a=lambda k:f"Assumptions!${sc}${R[k]}"
    def p(k):
        row,st=P[k]; return f"(Prices!$E${row}*{a('pm')})" if st=='ASSUMPTION' else f"Prices!$E${row}"
    blend=f"=(1+E{r}*({a('uplift')}-1))*IF(OR(E{r}=0,E{r}=1),1,1+{a('split')})"
    v=a('vcpu');m=a('memv');hh=a('hours');raw=a('raw_gb')
    egr='aws' if prov=='AWS' else 'gcp'
    tr=f"={a('egr')}*{p('egr_'+egr)}+{raw}*{a('pgf') if db!='MongoDB Atlas' else a('mfoot')}*{a('chg')}*{p('ir_'+egr)}"
    sh=''
    if db=='RDS PostgreSQL':
        c=f"={v}*{p('rds_vcpu')}*{hh}*{a('rdsunits')}*F{r}"; s=f"={raw}*{a('pgf')}*{p('rds_stor')}*{a('rdscopies')}*F{r}"
        b=f"={raw}*{a('pgf')}*{a('bk')}*{p('rds_bk')}*F{r}"; i=f"={a('rdsiops')}*{p('rds_iops')}*2*F{r}"
    elif db=='Aurora PostgreSQL':
        c=f"={v}*{p('aur_vcpu')}*{hh}*{a('aurnodes')}*F{r}"; s=f"={raw}*{a('pgf')}*{p('aur_stor')}*F{r}"
        b=f"={raw}*{a('pgf')}*{a('bk')}*{p('aur_bk')}*F{r}"
        i=f"={a('qps')}*{a('util')}*{hh}*3600*{a('ioq')}/1000000*{p('aur_io')}*F{r}"
    elif db=='Cloud SQL PostgreSQL':
        c=f"={v}*{hh}*(({p('cs_vcpu_ha')}+{m}*{p('cs_mem_ha')})+({p('cs_vcpu')}+{m}*{p('cs_mem')}))*F{r}"
        s=f"={raw}*{a('pgf')}*{p('cs_ssd')}*{a('cscopies')}*F{r}"; b=f"={raw}*{a('pgf')}*{a('bk')}*{p('cs_bk')}*F{r}"; i="=0"
    elif db=='AlloyDB':
        c=f"={v}*{hh}*{a('alnodes')}*({p('al_vcpu')}+{m}*{p('al_mem')})*F{r}"
        s=f"={raw}*{a('pgf')}*{p('al_stor')}*F{r}"; b=f"={raw}*{a('pgf')}*{a('bk')}*{p('al_bk')}*F{r}"; i="=0"
    else:
        pre='at_' if prov=='AWS' else 'ag_'; tier={'C':'m50','D':'m60','E':'m80'}[sc]
        sh=f"=ROUNDUP({raw}*{a('mfoot')}/{a('shardgb')},0)"
        c=f"=N{r}*{a('anodes')}*{p(pre+tier)}*{hh}*F{r}"; s=f"={raw}*{a('mfoot')}*{a('anodes')}*{p('at_stor')}*F{r}"
        b=f"={raw}*{a('mfoot')}*{a('bk')}*{p('at_bk')}*F{r}"; i="=0"
    wm.append([f'M{r-1:02d}',prov,db,scn,f"=Assumptions!$C${R[eukey]}",blend,c,s,b,i,tr,f"=SUM(G{r}:K{r})",f"=L{r}/{a('tenants')}",sh])
for eu in ('eu50',):
    for prov,db in combos:
        for scn,sc in SC: mk(prov,db,scn,sc,eu)
for eu,tag in (('eu20','Base'),('eu50','Base'),('eu100','Base')):
    for prov,db in combos: mk(prov,db,tag+' (EU sensitivity)','D',eu)
# ---- Summary
ws.append(['Provider','Database','Scenario','EU share','Monthly USD (estimate)','USD per tenant','Basis'])
for r in range(2,wm.max_row+1):
    ws.append([f'=Model!B{r}',f'=Model!C{r}',f'=Model!D{r}',f'=Model!E{r}',f'=Model!L{r}',f'=Model!M{r}','Estimate, not a quote; see Prices sheet for list vs assumed rows'])
ws.append([]); ws.append(['Note','All figures are estimates from public list prices where found and labelled assumptions where not; not vendor quotes. Prices dated 2026-10-22.'])
for w in wb:
    for row in w.iter_rows():
        for c in row: c.font=F
    for c in w[1]: c.font=B
    for col in 'ABCDEFGHIJKLMN': w.column_dimensions[col].width=22
wa.column_dimensions['B'].width=60; wa.column_dimensions['F'].width=80; wp.column_dimensions['C'].width=60
for r in range(2,ws.max_row+1):
    ws.cell(r,4).number_format='0%'; ws.cell(r,5).number_format='#,##0'; ws.cell(r,6).number_format='#,##0'
wb.save('cost_model.xlsx')
