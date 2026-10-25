import json
import pandas as pd
import streamlit as st
from pipeline import validate,wilson,report,FIELDS,warnings
st.set_page_config(page_title='GA4 Conversion Diagnostics',layout='wide')
st.title('GA4 Conversion Diagnostics')
st.caption('Historical sample · Ordered session funnel · Descriptive comparisons')
upload=st.file_uploader('Import pipeline snapshot.json',type='json')
if not upload:
    st.info('No data loaded. Run pipeline.py against BigQuery, then import the validated snapshot. No business results have been computed yet.')
    st.code('python pipeline.py --project YOUR_PROJECT --dry-run\npython pipeline.py --project YOUR_PROJECT')
    st.stop()
try: s=validate(json.load(upload))
except Exception as e:
    st.error(str(e)); st.stop()
df=pd.DataFrame(s['rows'])
a,b=st.columns(2)
dev=a.multiselect('Device',sorted(df.device.unique()),default=sorted(df.device.unique()))
src=b.multiselect('First-user acquisition source',sorted(df.acquisition_source.unique()),default=sorted(df.acquisition_source.unique()))
f=df[df.device.isin(dev)&df.acquisition_source.isin(src)]
if f.empty: st.info('No matching rows'); st.stop()
tot=f[list(FIELDS)].sum(); cols=st.columns(3)
cols[0].metric('Sessions',f'{tot.sessions:,}'); cols[1].metric('Product-view sessions',f'{tot.views:,}'); cols[2].metric('Ordered purchases',f'{tot.purchases:,}')
st.bar_chart(tot[['views','carts','checkouts','purchases']])
for dim in ('device','acquisition_source'):
    g=f.groupby(dim)[list(FIELDS)].sum(); g['completion_rate']=g.purchases/g.views.replace(0,float('nan'))
    st.subheader('Comparison by '+dim.replace('_',' ')); st.dataframe(g)
st.caption('Purchase completion = ordered purchasing sessions / product-view sessions. Acquisition source is first-user source. Observational differences do not establish causes.')
st.subheader('Source-wide data quality')
for issue in warnings(s): st.warning(issue)
st.json(s['quality'])
st.download_button('Download source-wide HTML brief',report(s),'report.html','text/html')
