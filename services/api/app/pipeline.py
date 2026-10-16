"""One ingestion path for uploaded images, videos and camera frames."""
import asyncio
from collections import deque
from datetime import datetime
import json
from pathlib import Path
import subprocess
import time
import uuid
import cv2
import httpx
import yaml
from td_contracts import EventOut, FrameResult
from . import database as db
from .security import now
from .settings import ROOT, STORAGE, INFERENCE_URL, INTERNAL_TOKEN

TASKS = {}
LIVE = {}
ACTIVE = {}  # camera id -> running source record (latest detections for live overlays)
BROADCAST = None
SLOTS = asyncio.Semaphore(2)
HTTP = None


async def publish(kind, data):
    if BROADCAST:
        await BROADCAST({'v':1,'type':kind,'sent_at':now(),'data':data})


def save_source(source):
    return db.put('source', source)


async def detector(data, stream_id=None):
    global HTTP
    if HTTP is None:
        HTTP = httpx.AsyncClient(timeout=60)
    for attempt in range(8):
        response = await HTTP.post(f'{INFERENCE_URL}/predict', params={'source_id':stream_id} if stream_id else None, headers={'Authorization':f'Bearer {INTERNAL_TOKEN}'}, files={'file':('frame.jpg', data, 'image/jpeg')})
        if response.status_code != 429:
            response.raise_for_status()
            return FrameResult.model_validate(response.json())
        await asyncio.sleep(.15*(attempt+1))
    raise RuntimeError('Detector busy; try again')


def temporal_policy():
    path = ROOT/'config/worker.yaml'
    try:
        policy = yaml.safe_load(path.read_text()).get('temporal_filter', {})
    except (OSError, yaml.YAMLError):
        policy = {}
    return int(policy.get('k_hits', 2)), int(policy.get('n_window', 4)), float(policy.get('immediate_confidence', 0.85))


PENDING = {}


async def process_frame(data, source, offset_ms=0, clip_url=None):
    streaming = source['kind'] != 'image'
    result = await detector(data, source['id'] if streaming else None)
    result.source_id = source['id']
    grouped = {}
    for box in result.detections:
        if box.category:
            grouped.setdefault(box.category, []).append(box)
    k_hits, n_window, immediate = temporal_policy()
    window = PENDING.setdefault(source['id'], {})
    for category in list(window):
        if category not in grouped:
            window[category].append(None)
            del window[category][:-n_window]
    for category, detections in grouped.items():
        timestamp = now()
        confidence = max(x.confidence for x in detections)
        existing = None
        if streaming:
            for ident in reversed(source['event_ids']):
                candidate = db.get('event', ident)
                last_offset = candidate.get('_last_offset_ms', 0) if candidate else 0
                if candidate and candidate['category']['key'] == category and offset_ms-last_offset <= 10000:
                    existing = candidate
                    break
        if existing:
            window.pop(category, None)
            existing.update(last_seen_at=timestamp,peak_confidence=max(confidence,existing['peak_confidence']),updated_at=timestamp,_last_offset_ms=offset_ms)
            db.save_event(existing)
            result.created_event_ids.append(existing['id'])
            await publish('event.updated', {'event':EventOut.model_validate(existing).model_dump(mode='json',by_alias=True)})
            continue
        if streaming:
            # A candidate must persist (k of n sampled frames) unless a single frame is already very confident.
            hits = window.setdefault(category, [])
            hits.append({'conf':confidence,'data':data,'offset':offset_ms,'result':result.model_dump_json(),'detections':detections})
            del hits[:-n_window]
            present = [h for h in hits if h]
            if confidence < immediate and len(present) < k_hits:
                continue
            peak = max(present, key=lambda h: h['conf'])
            window.pop(category, None)
            data_peak, offset_peak, result_json, detections, confidence = peak['data'], peak['offset'], peak['result'], peak['detections'], peak['conf']
        else:
            data_peak, offset_peak, result_json = data, offset_ms, result.model_dump_json()
        ident = 'evt_'+uuid.uuid4().hex
        media_dir = STORAGE/'media'/ident
        media_dir.mkdir(parents=True)
        (media_dir/'frame.jpg').write_bytes(data_peak)
        # Save inference evidence alongside source pixels; annotations are rendered by clients.
        (media_dir/'detections.json').write_text(result_json)
        media = [{'id':uuid.uuid4().hex,'kind':'KEYFRAME','role':'peak','url':f'/api/v1/events/{ident}/media/frame.jpg','width':result.width,'height':result.height,'offset_ms':offset_peak}]
        if clip_url:
            media.append({'id':uuid.uuid4().hex,'kind':'CLIP','role':'context','url':clip_url,'width':result.width,'height':result.height,'offset_ms':max(0,offset_peak-3000)})
        camera = db.get('camera',source.get('camera_id')) if source.get('camera_id') else None
        names = ', '.join(sorted({x.class_name for x in detections}))
        event = EventOut(id=ident,camera={'id':source.get('camera_id') or source['id'],'name':camera['name'] if camera else source['filename']},category={'key':category,'label':category.replace('_',' ').title()},status='NEEDS_REVIEW',status_reason='Model candidate; operator review required',verified_by='NONE',severity='CRITICAL' if any(x.severity=='CRITICAL' for x in detections) else 'HIGH',yolo_confidence=confidence,peak_confidence=confidence,summary=f'{names} detected at {confidence:.1%} confidence. Intent and context require review.',first_seen_at=timestamp,last_seen_at=timestamp,media_offset_ms=offset_peak,media=media,models={'yolo':{'name':', '.join(sorted({x.model for x in detections}))}},change_seq=0,created_at=timestamp,updated_at=timestamp).model_dump(mode='json',by_alias=True)
        event['_source_id'] = source['id']
        event['_last_offset_ms'] = offset_ms
        db.save_event(event)
        source['event_ids'].append(ident)
        result.created_event_ids.append(ident)
        await publish('event.created', {'event':EventOut.model_validate(event).model_dump(mode='json',by_alias=True)})
    source['frames_analyzed']+=1
    source['result']=result.model_dump(mode='json')
    save_source(source)
    return result


async def release(source_id):
    PENDING.pop(source_id, None)
    if HTTP is not None:
        try:
            await HTTP.delete(f'{INFERENCE_URL}/streams/{source_id}', headers={'Authorization':f'Bearer {INTERNAL_TOKEN}'})
        except httpx.HTTPError:
            pass


def transcode(path, target):
    import imageio_ffmpeg
    completed=subprocess.run([imageio_ffmpeg.get_ffmpeg_exe(),'-y','-v','error','-i',str(path),'-an','-c:v','libx264','-preset','veryfast','-crf','25','-pix_fmt','yuv420p','-movflags','+faststart',str(target)],capture_output=True,timeout=600,creationflags=getattr(subprocess,'CREATE_NO_WINDOW',0))
    if completed.returncode:
        raise ValueError('Video could not be decoded. Use an MP4, WebM, MOV or AVI recording.')


async def process_source(source, path):
    async with SLOTS:
        source['status']='RUNNING'
        save_source(source)
        cap=None
        try:
            if source['kind']=='image':
                await process_frame(path.read_bytes(),source)
            else:
                playback=path.parent/'playback.mp4'
                await asyncio.to_thread(transcode,path,playback)
                source['media_url']=f"/api/v1/sources/{source['id']}/media"
                save_source(source)
                cap=await asyncio.to_thread(cv2.VideoCapture,str(playback))
                if not cap.isOpened():
                    raise ValueError('Video cannot be opened')
                fps=cap.get(cv2.CAP_PROP_FPS) or 25
                total=int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
                stride=max(1,int(fps/2))
                index=0
                while True:
                    ok,frame=await asyncio.to_thread(cap.read)
                    if not ok:
                        break
                    if index%stride==0:
                        encoded=cv2.imencode('.jpg',frame,[cv2.IMWRITE_JPEG_QUALITY,85])[1].tobytes()
                        await process_frame(encoded,source,round(index/fps*1000),source['media_url'])
                        source['progress_pct']=min(99,round(index/max(1,total)*100,1))
                        save_source(source)
                    index+=1
                if not source['frames_analyzed']:
                    raise ValueError('No readable frames in video')
            source.update(status='DONE',progress_pct=100)
        except asyncio.CancelledError:
            source.update(status='CANCELED',error='Stopped')
            raise
        except Exception as exc:
            source.update(status='FAILED',error='Detector unavailable. Check System and retry.' if isinstance(exc,httpx.HTTPError) else str(exc)[:250])
        finally:
            if cap:
                cap.release()
            save_source(source)
            await release(source['id'])
            await publish('source.updated',{'source':source})


def start_source(source,path):
    task=asyncio.create_task(process_source(source,path))
    TASKS[source['id']]=task
    task.add_done_callback(lambda _:TASKS.pop(source['id'],None))


class CameraCapture:
    """Dedicated capture thread drops stale frames; inference consumes only the newest."""
    def __init__(self,uri):
        import threading
        self.uri=uri
        self.lock=threading.Lock()
        self.frames=deque(maxlen=48)
        self.latest=None
        self.sequence=0
        self.stopped=False
        self.error=None
        self.thread=threading.Thread(target=self.run,daemon=True)
        self.thread.start()

    def run(self):
        cap=cv2.VideoCapture(int(self.uri) if self.uri.isdigit() else self.uri)
        if not cap.isOpened():
            self.error='Camera could not be opened. Check address and camera permissions.'
        last=0
        while not self.stopped and cap.isOpened():
            ok,frame=cap.read()
            if not ok:
                self.error='Camera stream ended or disconnected'
                break
            stamp=time.monotonic()
            if stamp-last<1/6:
                continue
            last=stamp
            h,w=frame.shape[:2]
            if w>1280:
                frame=cv2.resize(frame,(1280,int(h*1280/w)))
            with self.lock:
                self.latest=frame
                self.sequence+=1
                self.frames.append(frame.copy())
        cap.release()

    def snapshot(self):
        with self.lock:
            return self.sequence,self.latest.copy() if self.latest is not None else None

    def clip(self,path):
        with self.lock:
            frames=list(self.frames)
        if len(frames)<2:
            return False
        raw=path.with_suffix('.avi')
        h,w=frames[0].shape[:2]
        writer=cv2.VideoWriter(str(raw),cv2.VideoWriter_fourcc(*'MJPG'),6,(w,h))
        if not writer.isOpened():
            return False
        for frame in frames:
            writer.write(cv2.resize(frame,(w,h)))
        writer.release()
        transcode(raw,path)
        raw.unlink(missing_ok=True)
        return True


async def camera_loop(camera,source):
    capture=CameraCapture(camera['connection_uri'])
    LIVE[camera['id']]=capture
    ACTIVE[camera['id']]=source
    started=time.monotonic()
    last=-1
    try:
        while not capture.stopped:
            if capture.error:
                raise RuntimeError(capture.error)
            seq,frame=capture.snapshot()
            if frame is None or seq==last:
                await asyncio.sleep(.1)
                continue
            last=seq
            camera['is_online']=True
            db.put('camera',camera)
            data=cv2.imencode('.jpg',frame)[1].tobytes()
            result=await process_frame(data,source,round((time.monotonic()-started)*1000))
            for ident in result.created_event_ids:
                event=db.get('event',ident)
                if not any(m['kind']=='CLIP' for m in event['media']):
                    target=STORAGE/'media'/ident/'clip.mp4'
                    if await asyncio.to_thread(capture.clip,target):
                        event['media'].append({'id':uuid.uuid4().hex,'kind':'CLIP','role':'context','url':f'/api/v1/events/{ident}/media/clip.mp4','width':result.width,'height':result.height,'offset_ms':0})
                        db.save_event(event)
                        await publish('event.updated',{'event':EventOut.model_validate(event).model_dump(mode='json',by_alias=True)})
            await asyncio.sleep(.5)
    except asyncio.CancelledError:
        source['status']='CANCELED'
    except Exception as exc:
        source.update(status='FAILED',error=str(exc)[:200])
    finally:
        capture.stopped=True
        await release(source['id'])
        LIVE.pop(camera['id'],None)
        ACTIVE.pop(camera['id'],None)
        camera['is_online']=False
        db.put('camera',camera)
        save_source(source)
        await publish('source.updated',{'source':source})


async def shutdown():
    for capture in LIVE.values():
        capture.stopped=True
    for task in list(TASKS.values()):
        task.cancel()
    await asyncio.gather(*TASKS.values(),return_exceptions=True)
    if HTTP:
        await HTTP.aclose()
