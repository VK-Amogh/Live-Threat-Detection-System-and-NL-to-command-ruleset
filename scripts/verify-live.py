"""Exercise real GPU inference and API media using isolated validation storage.

Run an API process with SAFESPACE_STORAGE=storage/validation and port 8002 first.
No fixtures or test incidents are inserted into the operator database.
"""
import json
from pathlib import Path
import statistics
import time
import cv2
import httpx
from dotenv import dotenv_values

ROOT=Path(__file__).resolve().parents[1]
config=dotenv_values(ROOT/'.env')


def main():
    files=sorted((ROOT/'storage/datasets/firenet-yolo/images/test').glob('*.jpg'))
    detector=httpx.Client(base_url='http://127.0.0.1:8001',headers={'Authorization':'Bearer '+config['INTERNAL_SERVICE_TOKEN']},timeout=60)
    positives=[]
    latency=[]
    for file in files[:12]:
        response=detector.post('/predict',files={'file':(file.name,file.read_bytes(),'image/jpeg')})
        response.raise_for_status()
        body=response.json()
        latency.append(body['inference_ms'])
        if body['threat_detected']:
            positives.append(file)
    if not positives:
        raise RuntimeError('No positive fire detections among the validation inputs')
    client=httpx.Client(base_url='http://127.0.0.1:8002',timeout=180)
    login=client.post('/api/v1/auth/login',json={'username':config['INITIAL_ADMIN_USERNAME'],'password':config['INITIAL_ADMIN_PASSWORD'],'device_name':'Real model validation'})
    login.raise_for_status()
    image=positives[0]
    start=time.perf_counter()
    response=client.post('/api/v1/inference/predict-frame',files={'file':('FireNET held-out validation.jpg',image.read_bytes(),'image/jpeg')})
    response.raise_for_status()
    image_result=response.json()
    assert image_result['threat_detected']
    image_end_to_end=(time.perf_counter()-start)*1000
    ident=image_result['created_event_ids'][0]
    event=client.get('/api/v1/events/'+ident).json()
    assert client.get(event['media'][0]['url']).status_code==200
    # A known labeled frame repeated in a short test video verifies video plumbing,
    # not temporal threat accuracy. Kept exclusively in validation storage.
    work=ROOT/'storage/validation'
    work.mkdir(exist_ok=True)
    video=work/'pipeline-validation.avi'
    frame=cv2.imread(str(image))
    frame=cv2.resize(frame,(640,480))
    writer=cv2.VideoWriter(str(video),cv2.VideoWriter_fourcc(*'MJPG'),10,(640,480))
    for _ in range(30):
        writer.write(frame)
    writer.release()
    response=client.post('/api/v1/sources',files={'file':('Pipeline validation.avi',video.read_bytes(),'video/x-msvideo')})
    response.raise_for_status()
    source=response.json()
    for _ in range(120):
        source=client.get('/api/v1/sources/'+source['id']).json()
        if source['status'] in ('DONE','FAILED'):
            break
        time.sleep(.5)
    assert source['status']=='DONE',source
    assert source['frames_analyzed']==6,source
    clip=client.get(source['media_url'],headers={'Range':'bytes=0-1023'})
    assert clip.status_code==206,clip.status_code
    assert len(clip.content)==1024
    answer=client.post('/api/v1/chat',json={'message':'Summarize this incident and identify its recorded evidence. Do not infer intent.','event_ids':[ident],'provider':'groq'})
    answer.raise_for_status()
    assert ident in answer.json()['event_ids']
    report={'real_model_inference_samples':len(latency),'warm_median_ms':round(statistics.median(latency[1:]),1),'cold_ms':latency[0],'image_end_to_end_ms':round(image_end_to_end,1),'positive_images':len(positives),'video_frames_analyzed':source['frames_analyzed'],'video_incidents':len(source['event_ids']),'range_playback_status':clip.status_code,'grounded_chat_provider':answer.json()['provider'],'grounded_chat_answer':answer.json()['answer'],'scope':'Held-out FireNET images; repeated-frame video tests pipeline only, not behavior recognition.'}
    (work/'verification.json').write_text(json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))
    client.post('/api/v1/auth/logout')


if __name__=='__main__':
    main()
