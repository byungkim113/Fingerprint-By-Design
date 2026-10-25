"""Compare the actual notebook's plotted data with independently selected JSON values."""
import json
import os
from pathlib import Path
import contextlib
import io

ROOT = Path(__file__).resolve().parents[1]
os.environ['MPLBACKEND'] = 'Agg'
import matplotlib.pyplot as plt
import numpy as np

def load(name):
    return json.loads((ROOT / 'notebook/data' / (name + '.json')).read_text())

checks = []
figures = 0
manifest = []
def equal(name, actual, expected):
    np.testing.assert_allclose(actual, expected, rtol=1e-12, atol=1e-12, err_msg=name)
    checks.append(name)

def show(*args, **kwargs):
    global figures
    for fig_id in plt.get_fignums():
        figures += 1
        fig = plt.figure(fig_id)
        axes = fig.axes
        manifest.append(dict(figure=figures, axes=[dict(title=a.get_title(), xlabel=a.get_xlabel(),
            ylabel=a.get_ylabel(), lines=[dict(label=l.get_label(), x=np.asarray(l.get_xdata()).tolist(),
            y=np.asarray(l.get_ydata()).tolist()) for l in a.lines],
            bars=[dict(width=float(p.get_width()), height=float(p.get_height())) for p in a.patches]) for a in axes]))
        heights = lambda ax: [p.get_height() for p in axes[ax].patches]
        line = lambda ax, n: axes[ax].lines[n].get_ydata()
        if figures == 3:
            d = load('live_reference')
            for i, c in enumerate(('nominal','1','2')):
                equal('live I-real '+c, line(0,i), 100*np.array(d['chips'][c]['fingerprint']['I_real']))
            equal('live pair difference', line(1,0), 100*(np.array(d['chips']['1']['fingerprint']['I_real'])-np.array(d['chips']['2']['fingerprint']['I_real'])))
        elif figures == 4:
            d, a = load('tx_more_chips'), load('tx_auth')
            for i,n in enumerate(('16','32','64')):
                equal('population '+n, line(0,i), [100*d[n][f'{s}dB'] for s in (30,20,15,10)])
            equal('authentication EER', heights(1), [100*a[f'{s}dB']['180_BASE'] for s in (30,20)])
        elif figures == 5:
            a, s = load('tx_attrib_aligned')['27']['increments'], load('tx_split')['split']
            vals = [a['DAC unit currents'],a['LO imbalance'],a['switches/quads/load'],s['PA increment'],s['buffer increment']]
            equal('signed attribution increments', [p.get_width() for p in axes[0].patches], 100*np.array(vals[::-1]))
            equal('stage energy ratios', heights(1), [1,s['energy_pa_over_mix'],s['energy_pa_over_mix']*s['energy_rf_over_pa']])
        elif figures == 6:
            d = load('tx_variants_mc'); keys=('base','palin','bigdac')
            equal('variant sizes', heights(0), [d[k][m]/d['base'][m] for m in ('S_mix','S_rf') for k in keys])
            equal('variant accuracy', heights(1), [100*d[k]['acc_20dB']['27'] for k in keys])
        elif figures == 7:
            d=load('tx_pex')
            equal('PEX fingerprint size',heights(0),[1,d['post-layout']['S_rf']/d['schematic']['S_rf']])
            equal('PEX accuracy',heights(1),[100*d[k]['acc_20dB'][t] for k in ('schematic','post-layout') for t in ('-40','27','85')])
        elif figures == 8:
            d=load('tx_supply')['30dB']['BASE']; t=load('tx_temp_supply')['30dB']['BASE']
            equal('supply baseline',line(0,0),[100*d[v] for v in ('162','171','1764','180','1836','189','198')])
            equal('combined drift',heights(1),[100*t[c] for c in ('-40C_162','-40C_198','85C_162','85C_198')])
        elif figures == 9:
            d=load('tx_bv2')['30dB']; t=load('tx_temp_supply')['30dB']
            for i,k in enumerate(('BASE','B')):
                equal('supply compensation '+k,line(0,i),[100*d[k][v] for v in ('162','171','1764','180','1836','189','198')])
            equal('2D compensation',heights(1),[100*t[k][c] for k in ('BASE','B2D') for c in ('27C_180','-40C_162','-40C_180','-40C_198','85C_162','85C_180','85C_198')])
        elif figures == 10:
            s=load('tx_supply')['30dB']['BASE']; a=load('tx_ldo_L1')['30dB']; b=load('tx_ldo_L2')['30dB']; t=load('tx_temp_supply')['30dB']['BASE']
            equal('LDO supply baseline',line(0,0),[100*s[v] for v in ('162','171','1764','180','1836','189','198')])
            equal('LDO supply accuracy',line(0,1),[100*a[v] for v in ('297','3135','3234','330','3366','3465','363')])
            equal('LDO combined drift',heights(1),[100*t[c] for c in ('-40C_162','-40C_198','85C_162','85C_198')]+[100*b[c] for c in ('-40C_297','-40C_363','85C_297','85C_363')])
        elif figures == 11:
            a=load('tx_modelrx_stage3')['30dB']['MRX']; b=load('tx_ldo_L3')['30dB']
            equal('arbitrary data comparison',heights(0),[100*a[c] for c in ('27C_180','27C_162','27C_198','85C_180','-40C_162')]+[100*b[c] for c in ('27C_330','27C_297','27C_363','85C_330','-40C_297')])
    plt.close('all')

plt.show=show
nb=json.loads((ROOT/'notebook/fingerprint_by_design.ipynb').read_text(encoding='utf-8'))
os.chdir(ROOT/'notebook')
env={'__name__':'__main__'}
with contextlib.redirect_stdout(io.StringIO()):
    for i,c in enumerate(nb['cells']):
        if c['cell_type']=='code':
            exec(compile(''.join(c['source']),f'notebook-cell-{i}','exec'),env)
assert figures==11
(ROOT/'review/notebook-graph-data.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
print('PASS:',len(checks),'series/bar-group comparisons across 9 quantitative figures; 2 layout figures rendered')
for check in checks:
    print('PASS:',check)
