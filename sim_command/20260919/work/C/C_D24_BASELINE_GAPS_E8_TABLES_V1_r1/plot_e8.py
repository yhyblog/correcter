"""Standalone paper figure, using only the reviewed E8 table."""
import csv
import json
import os
from pathlib import Path

W=Path(__file__).resolve().parent
R=W.parents[2]/'results/C/C_D24_BASELINE_GAPS_E8_TABLES_V1'
os.environ.setdefault('MPLCONFIGDIR','/tmp/corrector_C_N_gaps/matplotlib')
os.environ['XDG_CACHE_HOME']='/tmp/corrector_C_N_gaps/plot_cache'
Path(os.environ['XDG_CACHE_HOME']).mkdir(parents=True,exist_ok=True)
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Patch


def main():
    rows=list(csv.DictReader((R/'E8_TABLE.csv').open()))
    styles={'N':('#CDD4DC',''), 'Post':('#81B8D8','//'), 'Velocity':('#EDB968','..')}
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.labelsize':10,
                         'axes.titlesize':12,'pdf.fonttype':42,'svg.fonttype':'none',
                         'axes.spines.top':False,'axes.spines.right':False,
                         'axes.edgecolor':'#9A9FA7','text.color':'#252A31','hatch.linewidth':.35})
    fig,axes=plt.subplots(2,1,figsize=(10.4,8.5),gridspec_kw={'height_ratios':[2.1,3.8]})
    fig.subplots_adjust(left=.18,right=.77,top=.82,bottom=.17,hspace=.45)
    fig.suptitle('E8: success rates across models and suites',x=.18,y=.97,ha='left',fontsize=16)
    fig.text(.18,.932,'Fixed source sets; valid episode denominators shown at each mark',fontsize=10,color='#5B626B')
    fig.legend(handles=[Patch(facecolor=color,edgecolor='#697580',hatch=hatch,label=name)
                        for name,(color,hatch) in styles.items()],loc='upper left',bbox_to_anchor=(.172,.915),
               ncol=3,frameon=False,handlelength=2)
    panels=[(['SmolVLA 050000 / MT50','X-VLA 030000 / MT50'],['SmolVLA\n050000','X-VLA\n030000'],
             'MetaWorld: Full mechanism with frozen pi05 head transfer'),
            (['pi05 official / '+s for s in ['libero_spatial','libero_object','libero_goal','libero_10']],
             ['Spatial','Object','Goal','Long (LIBERO-10)'],
             'LIBERO: operator transfer only (no D/G0)')]
    for ax,(settings,labels,title) in zip(axes,panels):
        for group,setting in enumerate(settings):
            for offset,(method,(color,hatch)) in zip([-.24,0,.24],styles.items()):
                row=next(r for r in rows if r['setting']==setting and r['method']==method)
                n=int(row['valid']);s=int(row['successes']);rate=float(row['success_rate_pct'])
                lo=float(row['descriptive_wilson95_low_pct']);hi=float(row['descriptive_wilson95_high_pct'])
                y=group+offset
                ax.barh(y,rate,height=.21,color=color,edgecolor='#697580',linewidth=.45,hatch=hatch,zorder=2)
                ax.errorbar(rate,y,xerr=[[rate-lo],[hi-rate]],fmt='none',ecolor='#343B44',capsize=2,lw=.85,zorder=3)
                ax.annotate(f'{rate:.1f}%  ({s}/{n})',(hi,y),xytext=(5,0),textcoords='offset points',
                            va='center',fontsize=9,annotation_clip=False)
        ax.set_yticks(range(len(labels)),labels)
        ax.set_ylim(len(labels)-.5,-.5)
        ax.set_xlim(0,100);ax.set_xticks([0,20,40,60,80,100],[f'{x}%' for x in [0,20,40,60,80,100]])
        ax.set_xlabel('Episode success rate')
        ax.set_title(title,loc='left',pad=12)
        ax.grid(axis='x',color='#E4E7EC',lw=.65,zorder=0)
        ax.tick_params(axis='y',length=0,pad=9)
    fig.text(.18,.102,'Whiskers: descriptive Wilson 95% intervals among valid episodes. Missing outcomes are excluded.',fontsize=8.6)
    fig.text(.18,.077,'LIBERO uses original random-reset seeds, not the official fixed-initial-state benchmark.',fontsize=8.6)
    fig.text(.18,.052,'Paired effects and their original uncertainty methods are in E8_PAIRED.csv; no universal gain claim.',fontsize=8.6)
    outputs=[]
    for suffix in ('pdf','svg','png'):
        p=R/('E8_SUCCESS_RATES.'+suffix)
        fig.savefig(p,dpi=180,facecolor='white')
        outputs.append(dict(path=str(p),bytes=p.stat().st_size))
    plt.close(fig)
    (R/'FIGURE_MANIFEST.json').write_text(json.dumps(dict(source=str(R/'E8_TABLE.csv'),
        methods=list(styles),axis_domain_pct=[0,100],interval='descriptive Wilson95; not paired-difference inference',
        outputs=outputs),indent=2)+'\n')
    print(json.dumps(outputs))


if __name__=='__main__':main()
