"""Sticker test visual exports."""
from pathlib import Path
import numpy as np
import pandas as pd
from .analysis import StickerAnalysisResult

def write_visuals(folder, data: pd.DataFrame, result: StickerAnalysisResult):
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    root=Path(folder); root.mkdir(parents=True,exist_ok=True); stem=root/'figure1'; paths={k:stem.with_suffix('.'+k) for k in ('png','pdf','svg')}
    if any(p.exists() for p in paths.values()): raise FileExistsError('拒绝覆盖已有贴纸图。')
    q=result.frame_quality; fig,axes=plt.subplots(1,2,figsize=(7.2,3.1),constrained_layout=True); ax=axes[0]
    ax.plot(q.time_s,q.minimum_distance,color='#0072B2',lw=1,label='Nearest effector'); ax.axhline(result.config.contact_distance,color='#D55E00',ls='--',label='Threshold')
    for _,e in result.events[result.events.included].iterrows(): ax.axvspan(e.start_time_s,e.end_time_s,color='#009E73',alpha=.25)
    if result.summary['cessation_candidate_time_s'] is not None: ax.axvline(result.summary['cessation_candidate_time_s'],color='#CC79A7',label='Cessation candidate')
    ax.set(xlabel='Time (s)',ylabel='Distance',title='A | Contact distance'); ax.legend(frameon=False,fontsize=7); ax.spines[['top','right']].set_visible(False)
    ax=axes[1]; ax.plot(q.time_s,q.smoothed_intensity,color='#6A3D9A'); ax.set(xlabel='Time (s)',ylabel='Interaction intensity (a.u.)',title='B | Interaction intensity'); ax.spines[['top','right']].set_visible(False)
    for p in paths.values(): fig.savefig(p,dpi=600 if p.suffix=='.png' else None,bbox_inches='tight')
    plt.close(fig); return paths

def write_3d_video(folder, data: pd.DataFrame, result: StickerAnalysisResult, fps=10):
    import imageio.v2 as imageio
    import matplotlib; matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    root=Path(folder); root.mkdir(parents=True,exist_ok=True); path=root/'keypoints_3d.mp4'
    if path.exists(): raise FileExistsError('拒绝覆盖已有贴纸视频。')
    points=[result.config.target_point,*result.config.effector_points]; coords={p:data[[f'{p}_{a}' for a in 'xyz']].apply(pd.to_numeric,errors='coerce').to_numpy(float) for p in points}; allv=np.vstack(list(coords.values())); lo=np.nanmin(allv,0); hi=np.nanmax(allv,0); pad=np.maximum((hi-lo)*.2,1)
    fig=plt.figure(figsize=(6,5.5)); ax=fig.add_subplot(111,projection='3d'); artists=[ax.plot([],[],[],'o',ms=6,label=p)[0] for p in points]; title=ax.text2D(.03,.94,'',transform=ax.transAxes); ax.set(xlim=(lo[0]-pad[0],hi[0]+pad[0]),ylim=(lo[1]-pad[1],hi[1]+pad[1]),zlim=(lo[2]-pad[2],hi[2]+pad[2]),xlabel='X',ylabel='Y',zlabel='Z'); ax.legend(frameon=False,fontsize=7)
    step=max(1,round(float(data.fps.iloc[0])/fps))
    with imageio.get_writer(path,fps=fps,codec='libx264',quality=8,macro_block_size=1) as out:
        for i in range(0,len(data),step):
            for p,a in zip(points,artists): a.set_data_3d([coords[p][i,0]],[coords[p][i,1]],[coords[p][i,2]])
            title.set_text(f'Sticker test keypoints | t={float(data.time_s.iloc[i]):.2f}s'); fig.canvas.draw(); out.append_data(np.asarray(fig.canvas.buffer_rgba())[:,:,:3])
    plt.close(fig); return path
