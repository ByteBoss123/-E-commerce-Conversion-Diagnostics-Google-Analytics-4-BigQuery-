"""GA4 extraction and atomic report generation. No row-level identities leave BigQuery."""
import argparse, datetime as dt, hashlib, html, json, math, os, pathlib, tempfile
ROOT=pathlib.Path(__file__).parent
FIELDS=('sessions','views','carts','checkouts','purchases','purchasing_sessions')
QUALITY=('raw_events','observed_days','excluded_identity_events','purchase_events','missing_transaction_events','missing_revenue_events','negative_revenue_events','duplicate_transaction_events')
def wilson(k,n):
    if not n: return None
    z=1.959963984540054; p=k/n; d=1+z*z/n
    centre=(p+z*z/(2*n))/d; half=z*math.sqrt(p*(1-p)/n+z*z/(4*n*n))/d
    return [max(0,centre-half),min(1,centre+half)]
def validate(snapshot):
    if snapshot.get('schema_version')!=1: raise ValueError('Unsupported schema_version')
    if snapshot.get('classification')!='historical_obfuscated_sample': raise ValueError('Expected GA4 historical sample classification')
    if not isinstance(snapshot.get('rows'),list) or not snapshot['rows']: raise ValueError('No aggregate rows')
    start=dt.date.fromisoformat(snapshot['start_date']); end=dt.date.fromisoformat(snapshot['end_date'])
    if not dt.date(2020,11,1)<=start<=end<=dt.date(2021,1,31): raise ValueError('Dates outside sample coverage')
    keys=set()
    for row in snapshot['rows']:
        day=dt.date.fromisoformat(row['date'])
        if not start<=day<=end: raise ValueError('Row outside requested dates')
        if not all(isinstance(row.get(k),str) and row[k] for k in ('device','acquisition_source')): raise ValueError('Missing dimensions')
        key=(row['date'],row['device'],row['acquisition_source'])
        if key in keys: raise ValueError('Duplicate aggregate grain')
        keys.add(key)
        for f in FIELDS:
            if type(row.get(f)) is not int or row[f]<0: raise ValueError('Invalid count: '+f)
        if not row['sessions']>=row['views']>=row['carts']>=row['checkouts']>=row['purchases']: raise ValueError('Funnel counts are not nested')
        if not row['purchases']<=row['purchasing_sessions']<=row['sessions']: raise ValueError('Purchasing sessions out of bounds')
    q=snapshot.get('quality',{})
    for f in QUALITY:
        if type(q.get(f)) is not int or q[f]<0: raise ValueError('Invalid quality count: '+f)
    if not q['raw_events'] or q['excluded_identity_events']>q['raw_events']: raise ValueError('Invalid event coverage')
    if q['observed_days']>(end-start).days+1: raise ValueError('Invalid day coverage')
    if sum(r['sessions'] for r in snapshot['rows'])>q['raw_events']-q['excluded_identity_events']: raise ValueError('Sessions exceed eligible events')
    if sum(r['purchasing_sessions'] for r in snapshot['rows'])>q['purchase_events']: raise ValueError('Purchasing sessions exceed events')
    if any(q[f]>q['purchase_events'] for f in QUALITY[4:]): raise ValueError('Quality count exceeds purchase events')
    return snapshot

def warnings(s):
    q=s['quality']; out=[]
    for f in QUALITY[2:]:
        if f!='purchase_events' and q[f]: out.append(f.replace('_',' ')+': '+str(q[f]))
    expected=(dt.date.fromisoformat(s['end_date'])-dt.date.fromisoformat(s['start_date'])).days+1
    if q['observed_days']!=expected: out.append(f"Observed {q['observed_days']} of {expected} requested days; investigate missing partitions or event coverage")
    return out

def atomic_write(path,text):
    path=pathlib.Path(path); path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix='.pending-')
    try:
        with os.fdopen(fd,'w') as f: f.write(text)
        os.replace(tmp,path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def report(s):
    totals={k:sum(r[k] for r in s['rows']) for k in FIELDS}
    n=totals['views']; k=totals['purchases']; ci=wilson(k,n)
    rate=f'{100*k/n:.2f}%' if n else 'Unavailable'
    interval=f'{ci[0]*100:.2f}%–{ci[1]*100:.2f}%' if ci else 'Unavailable'
    issues=warnings(s)
    return '<!doctype html><meta charset="utf-8"><title>Conversion diagnostic brief</title><style>body{max-width:850px;margin:48px auto;font:17px/1.6 system-ui;padding:20px}td,th{text-align:left;padding:8px 24px 8px 0}</style><h1>Conversion diagnostic brief</h1>'+f'<p>{s["start_date"]} to {s["end_date"]} · Historical, obfuscated GA4 sample</p><p>Generated {html.escape(s["generated_at"])}</p><h2>Ordered funnel</h2><table>'+''.join(f'<tr><th>{f}</th><td>{totals[f]:,}</td></tr>' for f in FIELDS)+f'</table><p>View-to-purchase completion: {rate}. Descriptive 95% Wilson interval: {interval}.</p><h2>Data quality</h2><ul>'+''.join('<li>'+html.escape(x)+'</li>' for x in issues or ['No flagged checks in this extraction; this does not certify tracking completeness.'])+'</ul><h2>Next action</h2><p>Review quality exceptions first. Compare device and acquisition-source segments, inspect checkout instrumentation, and design a randomized test before claiming an improvement.</p><p>Ordered stages must occur within the same session at strictly increasing timestamps. Acquisition source is first-user source, not session campaign attribution. Wilson intervals assume independent sessions; repeated users may invalidate that assumption. Differences are descriptive, not causal. Revenue and ROAS are deliberately excluded.</p>'

def main():
    p=argparse.ArgumentParser(); p.add_argument('--project'); p.add_argument('--start',default='2020-11-01'); p.add_argument('--end',default='2020-11-07'); p.add_argument('--input'); p.add_argument('--output',default='output'); p.add_argument('--dry-run',action='store_true'); p.add_argument('--max-bytes',type=int,default=2_000_000_000); a=p.parse_args()
    if a.input:
        s=validate(json.loads(pathlib.Path(a.input).read_text()))
    else:
        start=dt.date.fromisoformat(a.start); end=dt.date.fromisoformat(a.end)
        if not dt.date(2020,11,1)<=start<=end<=dt.date(2021,1,31): p.error('Use dates within 2020-11-01 through 2021-01-31')
        if not a.project: p.error('--project is required for BigQuery')
        from google.cloud import bigquery
        client=bigquery.Client(project=a.project); results={}; jobs=[]
        for name in ('funnel','quality'):
            sql=(ROOT/'sql'/f'{name}.sql').read_text()
            config=bigquery.QueryJobConfig(query_parameters=[bigquery.ScalarQueryParameter('start_date','STRING',start.strftime('%Y%m%d')),bigquery.ScalarQueryParameter('end_date','STRING',end.strftime('%Y%m%d'))],dry_run=a.dry_run,use_query_cache=not a.dry_run,maximum_bytes_billed=a.max_bytes)
            job=client.query(sql,job_config=config,location='US')
            if a.dry_run:
                print(json.dumps({'query':name,'estimated_bytes':job.total_bytes_processed})); continue
            results[name]=[dict(row) for row in job.result()]
            jobs.append({'query':name,'job_id':job.job_id,'bytes_processed':job.total_bytes_processed,'sql_sha256':hashlib.sha256(sql.encode()).hexdigest()})
        if a.dry_run: return
        for row in results['funnel']: row['date']=row['date'].isoformat()
        s=validate({'schema_version':1,'classification':'historical_obfuscated_sample','start_date':a.start,'end_date':a.end,'generated_at':dt.datetime.now(dt.timezone.utc).isoformat(),'source':'bigquery-public-data.ga4_obfuscated_sample_ecommerce.events_*','jobs':jobs,'rows':results['funnel'],'quality':results['quality'][0]})
    out=pathlib.Path(a.output); brief=report(s)
    atomic_write(out/'snapshot.json',json.dumps(s,indent=2)); atomic_write(out/'report.html',brief)
    print(json.dumps({'status':'validated','aggregate_rows':len(s['rows']),'warnings':warnings(s),'output':str(out)}))
if __name__=='__main__': main()
