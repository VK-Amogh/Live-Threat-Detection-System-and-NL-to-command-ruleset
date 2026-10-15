"""Reproducible FireNET bootstrap or custom YOLO dataset training.

python scripts/train.py --dataset firenet --epochs 40 --device 0
python scripts/train.py --data path/to/data.yaml --name custom --epochs 50
Weights are never promoted automatically; evaluate before deploying.
"""
import argparse
import hashlib
import json
import random
import shutil
import time
from pathlib import Path
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / 'storage/training.json'


def status(**values):
    tmp = STATUS.with_suffix('.tmp')
    tmp.write_text(json.dumps(values, indent=2), encoding='utf8')
    tmp.replace(STATUS)


def prepare_firenet():
    import requests
    import zipfile
    source = ROOT / 'storage/datasets/firenet/fire-dataset'
    url = 'https://github.com/OlafenwaMoses/FireNET/releases/download/v1.0/fire-dataset.zip'
    if not source.exists():
        archive = ROOT / 'storage/datasets/firenet.zip'
        archive.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(url, timeout=120)
        response.raise_for_status()
        archive.write_bytes(response.content)
        with zipfile.ZipFile(archive) as z:
            dest = archive.parent / 'firenet'
            for name in z.namelist():
                if not (dest / name).resolve().is_relative_to(dest.resolve()):
                    raise ValueError('Unsafe archive entry')
            z.extractall(dest)
    output = ROOT / 'storage/datasets/firenet-yolo'
    records, seen = [], set()
    for annotation in sorted(source.rglob('*.xml')):
        tree = ET.parse(annotation).getroot()
        stem = annotation.stem
        image = next((x for x in (annotation.parent.parent/'images').glob(stem+'.*') if x.suffix.lower() in ('.jpg','.jpeg','.png')), None)
        if not image:
            continue
        digest = hashlib.sha256(image.read_bytes()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        width, height = float(tree.findtext('size/width')), float(tree.findtext('size/height'))
        labels=[]
        for obj in tree.findall('object'):
            if obj.findtext('name').lower() != 'fire':
                continue
            b = obj.find('bndbox')
            x1,y1,x2,y2 = [float(b.findtext(k)) for k in ('xmin','ymin','xmax','ymax')]
            x1,x2 = max(0,x1),min(width,x2)
            y1,y2 = max(0,y1),min(height,y2)
            if x2>x1 and y2>y1:
                labels.append(f'0 {(x1+x2)/2/width:.6f} {(y1+y2)/2/height:.6f} {(x2-x1)/width:.6f} {(y2-y1)/height:.6f}')
        # Keep the author's test data held out; split train into train/validation.
        original_split = annotation.parent.parent.name
        records.append((image,digest,labels,original_split))
    random.Random(42).shuffle(records)
    counts = {'train':0,'val':0,'test':0}
    manifest=[]
    for i,(image,digest,labels,original) in enumerate(records):
        split = 'test' if original in ('validation','test') else ('val' if i%5==0 else 'train')
        for folder in ('images','labels'):
            (output/folder/split).mkdir(parents=True,exist_ok=True)
        shutil.copy2(image, output/'images'/split/(digest+image.suffix.lower()))
        (output/'labels'/split/(digest+'.txt')).write_text('\n'.join(labels))
        counts[split]+=1
        manifest.append({'sha256':digest,'split':split,'original':str(image.relative_to(source))})
    import yaml
    data={'path':str(output),'train':'images/train','val':'images/val','test':'images/test','names':{0:'fire'}}
    (output/'data.yaml').write_text(yaml.safe_dump(data))
    (output/'provenance.json').write_text(json.dumps({'source':url,'publisher':'OlafenwaMoses/FireNET','license_url':'https://github.com/OlafenwaMoses/FireNET/blob/master/LICENSE','seed':42,'counts':counts,'files':manifest},indent=2))
    return output/'data.yaml', counts


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--dataset', default='firenet', choices=['firenet'])
    parser.add_argument('--data')
    parser.add_argument('--name', default='fire')
    parser.add_argument('--epochs', type=int, default=40)
    parser.add_argument('--device', default='0')
    parser.add_argument('--batch', type=int, default=8)
    args=parser.parse_args()
    started=time.time()
    state={'status':'preparing','name':args.name,'started_at':started,'epoch':0,'epochs':args.epochs}
    status(**state)
    try:
        data,counts = (Path(args.data),{}) if args.data else prepare_firenet()
        state.update(dataset=str(data),counts=counts,status='training')
        status(**state)
        from ultralytics import YOLO
        model=YOLO(str(ROOT/'storage/models/best.pt'))
        def epoch_end(trainer):
            state.update(epoch=trainer.epoch+1,metrics={k:float(v) for k,v in (trainer.metrics or {}).items()})
            status(**state)
        model.add_callback('on_fit_epoch_end',epoch_end)
        run=f'{args.name}-{int(started)}'
        model.train(data=str(data),epochs=args.epochs,imgsz=640,batch=args.batch,device=args.device,workers=0,seed=42,deterministic=True,amp=True,cache=False,project=str(ROOT/'storage/training'),name=run,patience=12,plots=True,verbose=False)
        best=Path(model.trainer.best)
        evaluation=YOLO(str(best)).val(data=str(data),split='test' if counts.get('test') else 'val',device=args.device,workers=0,plots=False)
        state.update(status='completed',weights=str(best),metrics={k:float(v) for k,v in evaluation.results_dict.items()},evaluated_split='test' if counts.get('test') else 'val',elapsed_s=round(time.time()-started))
        status(**state)
    except Exception as exc:
        state.update(status='failed',error=f'{type(exc).__name__}: {exc}')
        status(**state)
        raise


if __name__=='__main__':
    main()
