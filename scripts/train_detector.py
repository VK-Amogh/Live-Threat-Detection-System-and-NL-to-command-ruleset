"""Train one YOLO detector domain (weapons) and publish live progress.

python scripts/train_detector.py --name weapons --data storage/datasets/weapons/data.yaml --epochs 40
python scripts/train_detector.py --name weapons --data ... --fraction 0.05 --epochs 1   # timing pass

Status for every run lives in storage/training.json (read by the API/System screen). Weights are
never deployed here; scripts/benchmark_detector.py decides promotion against the incumbent.
"""
import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / 'storage/training.json'


def write_status(name, **fields):
    try:
        state = json.loads(STATUS.read_text())
        if 'runs' not in state:
            state = {'runs': {}}
    except (OSError, ValueError):
        state = {'runs': {}}
    run = state['runs'].setdefault(name, {})
    run.update(fields)
    run['updated_at'] = time.time()
    statuses = {r.get('status') for r in state['runs'].values()}
    state['status'] = 'training' if 'training' in statuses else 'preparing' if 'preparing' in statuses else 'failed' if 'failed' in statuses else 'completed'
    tmp = STATUS.with_suffix('.tmp')
    tmp.write_text(json.dumps(state, indent=2))
    tmp.replace(STATUS)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--name', required=True)
    p.add_argument('--data', required=True)
    p.add_argument('--model', default='weights/yolo26s.pt')
    p.add_argument('--epochs', type=int, default=40)
    p.add_argument('--batch', type=int, default=16)
    p.add_argument('--imgsz', type=int, default=640)
    p.add_argument('--workers', type=int, default=4)
    p.add_argument('--fraction', type=float, default=1.0)
    p.add_argument('--patience', type=int, default=10)
    p.add_argument('--time', type=float, default=None, help='hard wall-clock budget in hours (overrides epochs)')
    p.add_argument('--device', default='0')
    p.add_argument('--resume', action='store_true')
    p.add_argument('--finetune', action='store_true', help='low learning rate and mild augmentation for an existing domain checkpoint')
    a = p.parse_args()

    from ultralytics import YOLO
    started = time.time()
    run_name = f'{a.name}-{int(started)}'
    write_status(a.name, status='training', run=run_name, model=a.model, data=a.data, epoch=0, epochs=a.epochs, started_at=started, fraction=a.fraction)
    try:
        model = YOLO(str(ROOT / a.model) if not Path(a.model).is_absolute() else a.model)

        def on_epoch(trainer):
            metrics = {k: float(v) for k, v in (trainer.metrics or {}).items()}
            write_status(a.name, epoch=trainer.epoch + 1, epochs=trainer.epochs, metrics=metrics, elapsed_s=round(time.time() - started), epoch_s=round(trainer.epoch_time or 0, 1))

        model.add_callback('on_fit_epoch_end', on_epoch)
        model.train(
            data=a.data, epochs=a.epochs, imgsz=a.imgsz, batch=a.batch, device=a.device, workers=a.workers, fraction=a.fraction,
            project=str(ROOT / 'storage/training'), name=run_name, patience=a.patience, seed=42, deterministic=False, amp=True,
            cache=False, plots=False, verbose=False, time=a.time, close_mosaic=2 if a.finetune else 5,
            cos_lr=True, mosaic=0.2 if a.finetune else 1.0, mixup=0.0 if a.finetune else 0.05,
            optimizer='AdamW' if a.finetune else 'auto', lr0=0.0005 if a.finetune else 0.01,
            warmup_epochs=0.0 if a.finetune else 3.0,
            hsv_h=0.015, hsv_s=0.6, hsv_v=0.4, degrees=3.0, translate=0.1, scale=0.5, fliplr=0.5,
        )
        best = Path(model.trainer.best)
        write_status(a.name, status='completed', weights=str(best), elapsed_s=round(time.time() - started))
    except Exception as exc:  # noqa: BLE001
        write_status(a.name, status='failed', error=f'{type(exc).__name__}: {exc}')
        raise


if __name__ == '__main__':
    main()
