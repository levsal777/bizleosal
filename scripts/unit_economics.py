import pandas as pd
import json
import sys

INPUT = sys.argv[1] if len(sys.argv)>1 else 'data/sample_campaign.csv'

def run(input_csv=INPUT):
    df = pd.read_csv(input_csv)
    cols = ['impressions','clicks','installs','purchases','revenue','cost']
    for c in cols:
        if c not in df.columns:
            df[c]=0
    agg = df.groupby('channel')[cols].sum().reset_index()
    agg['ctr'] = agg.apply(lambda r: (r.clicks / r.impressions) if r.impressions>0 else 0, axis=1)
    agg['cpc'] = agg.apply(lambda r: (r.cost / r.clicks) if r.clicks>0 else 0, axis=1)
    agg['cac'] = agg.apply(lambda r: (r.cost / r.purchases) if r.purchases>0 else 0, axis=1)
    agg['aov'] = agg.apply(lambda r: (r.revenue / r.purchases) if r.purchases>0 else 0, axis=1)
    agg['roas'] = agg.apply(lambda r: (r.revenue / r.cost) if r.cost>0 else 0, axis=1)

    # Simple recommendation
    def reco(row):
        if row.roas>2 and row.cac < row.aov:
            return 'Scale up'
        if row.roas>1 and row.cac<=row.aov:
            return 'Monitor / optimize'
        return 'Pause or revisit creative'

    agg['recommendation'] = agg.apply(reco, axis=1)

    out_json = agg.to_dict(orient='records')
    with open('methods/unit-economics/report_sample.json','w') as f:
        json.dump(out_json,f,indent=2)
    # simple markdown report
    with open('methods/unit-economics/report_sample.md','w') as f:
        f.write('# Unit Economics - sample report\n\n')
        for r in out_json:
            f.write(f"## Channel: {r['channel']}\n")
            f.write(f"- Impressions: {r['impressions']}\n")
            f.write(f"- Clicks: {r['clicks']} (CTR {r['ctr']:.2%})\n")
            f.write(f"- Purchases: {r['purchases']}\n")
            f.write(f"- Revenue: {r['revenue']:.2f}\n")
            f.write(f"- Cost: {r['cost']:.2f}\n")
            f.write(f"- CAC: {r['cac']:.2f}\n")
            f.write(f"- AOV: {r['aov']:.2f}\n")
            f.write(f"- ROAS: {r['roas']:.2f}\n")
            f.write(f"- Recommendation: {r['recommendation']}\n\n")

    print('Report generated: methods/unit-economics/report_sample.json and .md')

if __name__=='__main__':
    run()
