"""Create a 10-second 30-fps sticker-test sample; never overwrite."""
from pathlib import Path
import csv, math, random

FIELDS=['trial_id','animal_id','frame','time_s','fps','coordinate_unit']+[f'{p}_{a}' for p in ('nose_tip','left_paw_tip','right_paw_tip','trunk_center') for a in ('x','y','z','likelihood')]
def main():
    out=Path(r'C:\Users\33913\Desktop\StickerTest_10s_Simulated.csv')
    if out.exists(): raise FileExistsError(f'拒绝覆盖：{out}')
    rng=random.Random(20260921)
    with out.open('w',newline='',encoding='utf-8') as h:
        w=csv.DictWriter(h,fieldnames=FIELDS); w.writeheader()
        for f in range(300):
            t=f/30; nose=(0.,0.,62.); trunk=(0.,0.,36.); left=(-30.,12.,38.); right=(30.,-12.,38.)
            # Three sustained grooming contacts, then no contact after 7 s: cessation candidate.
            if 60<=f<=92 or 120<=f<=152 or 180<=f<=210: left=(1.5*math.sin(f),1.5*math.cos(f),61.)
            if 215<=f<=225: right=(2.*math.sin(f),2.*math.cos(f),61.)
            row={'trial_id':'sticker_demo_10s_001','animal_id':'simulated_mouse_001','frame':f,'time_s':round(t,6),'fps':30,'coordinate_unit':'mm'}
            for name,p in [('nose_tip',nose),('left_paw_tip',left),('right_paw_tip',right),('trunk_center',trunk)]:
                for a,v in zip(('x','y','z'),p): row[f'{name}_{a}']=v+rng.gauss(0,.2)
                row[f'{name}_likelihood']=.99
            w.writerow(row)
    print(out)
if __name__=='__main__': main()
