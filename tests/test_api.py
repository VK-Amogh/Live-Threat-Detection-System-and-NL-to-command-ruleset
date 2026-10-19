import io
import json
import sys
import time
from pathlib import Path
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

ROOT=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(ROOT/'services/api'),str(ROOT/'contracts/src')]
from app import main, database, pipeline
from td_contracts import FrameResult, Detection


@pytest.fixture
def client(tmp_path,monkeypatch):
    monkeypatch.setattr(database,'DB_PATH',tmp_path/'test.db')
    monkeypatch.setattr(main,'STORAGE',tmp_path)
    monkeypatch.setattr(pipeline,'STORAGE',tmp_path)
    for folder in ('media','uploads'):
        (tmp_path/folder).mkdir()
    monkeypatch.setenv('INITIAL_ADMIN_USERNAME','admin@gmail.com')
    monkeypatch.setenv('INITIAL_ADMIN_PASSWORD','admin123')
    main.ATTEMPTS.clear()
    main.TICKETS.clear()
    with TestClient(main.app) as client:
        yield client


def login(client,mobile=False):
    result=client.post('/api/v1/auth/login',json={'username':'admin@gmail.com','password':'admin123','device_name':'test','client_type':'mobile' if mobile else 'web'})
    assert result.status_code==200
    return result


def image_bytes():
    out=io.BytesIO()
    Image.new('RGB',(32,32)).save(out,format='JPEG')
    return out.getvalue()


def result(threat=True):
    return FrameResult(detections=[Detection(class_name='gun' if threat else 'person',confidence=.9,box=[1,1,25,25],model='test-fixture',category='WEAPON_DETECTED' if threat else None,severity='CRITICAL' if threat else None)],threat_detected=threat,inference_ms=1,width=32,height=32,models=['test-fixture'],covered_classes=['gun','person'])


def test_authentication_and_cookie(client):
    assert client.get('/api/v1/events').status_code==401
    assert client.get('/api/v1/cameras').status_code==401
    assert client.post('/api/v1/auth/login',json={'username':'admin@gmail.com','password':'wrong','device_name':'test'}).status_code==401
    response=login(client)
    assert response.json()['device_token'] is None
    assert 'HttpOnly' in response.headers['set-cookie']
    assert 'SameSite=strict' in response.headers['set-cookie']
    assert client.get('/api/v1/events').json()==[]
    assert client.get('/api/v1/cameras').json()==[]
    client.post('/api/v1/auth/logout')
    assert client.get('/api/v1/auth/me').status_code==401


def test_mobile_token_pairing_and_revocation(client):
    response=login(client,True)
    token=response.json()['device_token']
    client.headers['Authorization']='Bearer '+token
    code=client.post('/api/v1/auth/pairing-code').json()['code']
    pair=client.post('/api/v1/auth/pair',json={'code':code,'device_name':'paired'})
    assert pair.status_code==200
    assert client.post('/api/v1/auth/pair',json={'code':code,'device_name':'again'}).status_code==401
    assert client.post('/api/v1/auth/pair',json={'code':'SAFE-9821','device_name':'bypass'}).status_code==401
    client.delete('/api/v1/devices/'+response.json()['device_id'])
    assert client.get('/api/v1/events').status_code==401


def test_websocket_rejects_invalid_and_replayed_tickets(client):
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('/api/v1/ws?ticket=invalid'):
            pass
    login(client)
    ticket=client.post('/api/v1/ws-tickets').json()['ticket']
    with client.websocket_connect('/api/v1/ws?ticket='+ticket) as ws:
        assert ws.receive_json()['type']=='hello'
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect('/api/v1/ws?ticket='+ticket):
            pass


def test_cross_origin_cookie_mutation_blocked(client):
    login(client)
    assert client.post('/api/v1/ws-tickets',headers={'Origin':'https://attacker.example'}).status_code==403


def test_detection_review_media_and_persistence(client,monkeypatch):
    async def predict(_, *args):
        return result()
    monkeypatch.setattr(pipeline,'detector',predict)
    login(client)
    ticket=client.post('/api/v1/ws-tickets').json()['ticket']
    with client.websocket_connect('/api/v1/ws?ticket='+ticket) as ws:
        ws.receive_json()
        response=client.post('/api/v1/inference/predict-frame',files={'file':('gun.jpg',image_bytes(),'image/jpeg')})
        assert response.status_code==200,response.text
        assert ws.receive_json()['type']=='event.created'
    ident=response.json()['created_event_ids'][0]
    event=client.get('/api/v1/events/'+ident).json()
    assert event['verified_by']=='NONE'
    assert event['status']=='NEEDS_REVIEW'
    assert client.get(event['media'][0]['url']).status_code==200
    action={'client_action_id':'action-1','action':'CONFIRM'}
    update=client.post(f'/api/v1/events/{ident}/verification',json=action).json()
    duplicate=client.post(f'/api/v1/events/{ident}/verification',json=action).json()
    assert update['change_seq']==duplicate['change_seq']
    assert update['status']=='CONFIRMED'
    assert len(update['feedback'])==1
    page1=client.get('/api/v1/changes?limit=1').json()
    assert page1['has_more'] is True
    page2=client.get('/api/v1/changes',params={'after':page1['next_after'],'limit':1}).json()
    assert page2['items'][0]['status']=='CONFIRMED'
    database.initialize()
    assert database.get('event',ident)['status']=='CONFIRMED'
    client.post('/api/v1/auth/logout')
    assert client.get(event['media'][0]['url']).status_code==401


def test_person_is_not_a_threat(client,monkeypatch):
    async def predict(_, *args):
        return result(False)
    monkeypatch.setattr(pipeline,'detector',predict)
    login(client)
    response=client.post('/api/v1/inference/predict-frame',files={'file':('person.jpg',image_bytes(),'image/jpeg')})
    assert response.status_code==200,response.text
    assert response.json()['threat_detected'] is False
    assert client.get('/api/v1/events').json()==[]
    assert client.get('/api/v1/sources').json()[0]['frames_analyzed']==1


def test_upload_failures_are_not_clear_results(client,monkeypatch):
    async def predict(_, *args):
        raise RuntimeError('Invalid image')
    monkeypatch.setattr(pipeline,'detector',predict)
    login(client)
    assert client.post('/api/v1/sources',files={'file':('evil.exe',b'text')}).status_code==415
    assert client.post('/api/v1/inference/predict-frame',files={'file':('corrupt.jpg',b'not an image')}).status_code==503
    source=client.get('/api/v1/sources').json()[0]
    assert source['status']=='FAILED'
    assert source['result'] is None
    assert client.get('/api/v1/events').json()==[]


def test_password_change_revokes_all_sessions(client):
    login(client)
    mobile=login(client,True).json()['device_token']
    assert client.post('/api/v1/auth/password',json={'current_password':'incorrect','new_password':'new-test-password'}).status_code==400
    assert client.post('/api/v1/auth/password',json={'current_password':'admin123','new_password':'new-test-password'}).status_code==200
    assert client.get('/api/v1/events',headers={'Authorization':'Bearer '+mobile}).status_code==401


def test_chat_is_owned_and_grounded_in_records(client):
    from app.chat import context
    from td_contracts import ChatRequest
    login(client)
    with database.connection() as con:
        user=con.execute('SELECT id FROM users').fetchone()['id']
        con.execute('INSERT INTO conversations VALUES(?,?,?)',('private','someone-else','[]'))
    response=client.post('/api/v1/chat/stream',json={'message':'hello','conversation_id':'private'})
    assert response.status_code==404
    info,history,records,prompt=context(ChatRequest(message='Is everything safe?'),{'user_id':user})
    assert records==[] and history==[]
    assert info['counts']['matched']==0
    assert 'does not prove' in info['coverage']['note']


def test_chat_answers_when_ollama_is_unavailable(client, monkeypatch):
    from app import chat
    monkeypatch.setattr(chat, 'OLLAMA_URL', 'http://127.0.0.1:1')
    login(client)
    response = client.post('/api/v1/chat', json={'message': 'Summarize the latest incidents.'})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body['provider'] == 'records'
    assert body['answer']
    assert 'could not find' in body['answer'].lower()

    stream = client.post('/api/v1/chat/stream', json={'message': 'What do the cameras show?'})
    items = [json.loads(line) for line in stream.text.splitlines() if line]
    assert items[-1]['type'] == 'done'
    assert items[-1]['answer']
    assert not any(item['type'] == 'error' for item in items)


def test_incident_review_summarizes_metadata_without_visual_model(monkeypatch):
    import asyncio
    from app import review

    event = {
        'id': 'evt_test', 'category': {'label': 'Weapon detected'},
        'peak_confidence': 0.84, 'status': 'NEEDS_REVIEW', 'models': {},
    }
    saved = []
    monkeypatch.setattr(review.db, 'get', lambda kind, ident: event)
    monkeypatch.setattr(review.db, 'all_objects', lambda kind: [])
    monkeypatch.setattr(review.db, 'save_event', lambda item: saved.append(item.copy()))
    monkeypatch.setattr(review, 'annotated_keyframe', lambda item: None)
    monkeypatch.setattr(review, 'sample_clip_frames', lambda item, count: [])
    monkeypatch.setattr(review, 'detector_classes', lambda item: ['gun'])

    result = asyncio.run(review.review('evt_test'))
    assert result['reasoning']['evidence_insufficient'] is True
    assert result['reasoning']['visible_facts'] == []
    assert '84%' in result['reasoning']['uncertainty']
    assert result['models']['vlm']['version'] == 'records'
    assert saved


def test_background_review_finishes_with_detector_summary_when_model_fails(monkeypatch, tmp_path):
    from services.reasoner import loop

    class Response:
        def __init__(self, data):
            self.data = data
        def raise_for_status(self):
            pass
        def json(self):
            return self.data

    class Client:
        calls = []
        def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            if url.endswith('/claim'):
                return Response({'job': {'claim_token': 42.0, 'event': {
                    'id': 'evt_test', 'category': {'label': 'Weapon detected'},
                    'camera': {'name': 'Front door'}, 'peak_confidence': 0.81,
                    'track_refs': [], 'first_seen_at': '2026-10-17T00:00:00Z',
                    'last_seen_at': '2026-10-17T00:00:01Z',
                }}})
            return Response({})

    class BrokenModel:
        def describe(self, *args):
            raise RuntimeError('model unavailable')

    monkeypatch.setattr(loop, 'selected_frames', lambda *args: [b'frame'])
    client = Client()
    assert loop.review_once(client, 'http://localhost', 'test', BrokenModel(), tmp_path)
    url, kwargs = client.calls[-1]
    assert url.endswith('/evt_test/complete')
    assert 'Detector reported Weapon detected' in kwargs['json']['result']['visible_evidence']
    assert 'unconfirmed' in kwargs['json']['result']['uncertainty']


def test_system_uses_real_storage_and_reports_unavailable_dependencies(client):
    login(client)
    response=client.get('/api/v1/system')
    assert response.status_code==200,response.text
    body=response.json()
    assert body['counts']['incidents']==0
    assert body['resources']['disk_free_gb']>0
    assert 'status' in body['training']


def make_video(path,seconds=6,fps=10):
    import cv2
    import numpy as np
    writer=cv2.VideoWriter(str(path),cv2.VideoWriter_fourcc(*'MJPG'),fps,(64,48))
    for i in range(seconds*fps):
        writer.write(np.full((48,64,3),(i*3)%255,np.uint8))
    writer.release()


def scripted_detector(confidences,raw=None):
    """Detector double that returns a weapon detection with the given confidence (None = clear frame) per call."""
    calls=iter(confidences)
    async def predict(_, *args):
        conf=next(calls,None)
        if conf is None:
            return result(False)
        out=result()
        out.detections[0].confidence=conf
        out.detections[0].detector_confidence=conf if raw is None else raw
        return out
    return predict


def run_video(client,tmp_path):
    video=tmp_path/'clip.avi'
    make_video(video)
    response=client.post('/api/v1/sources',files={'file':('clip.avi',video.read_bytes(),'video/x-msvideo')})
    assert response.status_code==202,response.text
    ident=response.json()['id']
    for _ in range(200):
        source=client.get('/api/v1/sources/'+ident).json()
        if source['status'] in ('DONE','FAILED'):
            return source
        time.sleep(.1)
    raise AssertionError('video did not finish')


def test_video_candidate_needs_persistence(client,monkeypatch,tmp_path):
    # Uploaded video needs three low-confidence hits in four sampled frames.
    monkeypatch.setattr(pipeline,'detector',scripted_detector([.5]+[None]*40))
    login(client)
    assert run_video(client,tmp_path)['event_ids']==[]
    monkeypatch.setattr(pipeline,'detector',scripted_detector([.5,.55]+[None]*40))
    assert run_video(client,tmp_path)['event_ids']==[]
    monkeypatch.setattr(pipeline,'detector',scripted_detector([.5,.55,.6]+[None]*40))
    source=run_video(client,tmp_path)
    assert source['frames_analyzed'] >= 25  # six seconds at the configured 5 fps
    assert len(source['event_ids'])==1
    event=client.get('/api/v1/events/'+source['event_ids'][0]).json()
    assert event['media_offset_ms'] is not None
    assert any(m['kind']=='CLIP' for m in event['media'])


def test_video_single_confident_frame_alerts_immediately(client,monkeypatch,tmp_path):
    monkeypatch.setattr(pipeline,'detector',scripted_detector([.95]+[None]*40))
    login(client)
    assert len(run_video(client,tmp_path)['event_ids'])==1


def test_chat_dossier_contains_detector_output_and_cites_footage(client,monkeypatch,tmp_path):
    from app import chat
    from td_contracts import ChatRequest
    monkeypatch.setattr(chat,'STORAGE',tmp_path)
    monkeypatch.setattr(pipeline,'detector',scripted_detector([.95]+[None]*40))
    login(client)
    source=run_video(client,tmp_path)
    ident=source['event_ids'][0]
    with database.connection() as con:
        user=con.execute('SELECT id FROM users').fetchone()['id']
    info,history,records,prompt=chat.context(ChatRequest(message='What happened with the weapon?'),{'user_id':user})
    assert info['event_ids']==[ident]
    assert 'detections_in_keyframe' in prompt and '"gun"' in prompt and 'frame_area_pct' in prompt
    assert '"by_category"' in prompt
    cited=chat.cited_media(f'See {ident} for details.',records,False)
    assert cited[0]['event_id']==ident and cited[0]['clip_url']
    assert chat.cited_media('No ids here.',records,True)[0]['event_id']==ident
    assert chat.cited_media('No ids here.',records,False)==[]
    frames=chat.sample_clip_frames(records[0])
    assert 1<=len(frames)<=chat.CLIP_FRAMES


def test_system_reports_published_benchmarks(client,tmp_path,monkeypatch):
    login(client)
    (tmp_path/'benchmarks').mkdir()
    (tmp_path/'benchmarks'/'weapons.json').write_text(json.dumps({'overall':{'mAP50':.5}}))
    body=client.get('/api/v1/system').json()
    assert body['training']['benchmarks']['weapons']['overall']['mAP50']==.5


def test_verified_but_weak_detector_score_does_not_skip_persistence(client,monkeypatch,tmp_path):
    # Verifier probabilities saturate near 1.0; a single frame whose raw detector score is weak must still need k-of-n.
    monkeypatch.setattr(pipeline,'detector',scripted_detector([.999]+[None]*40,raw=.4))
    login(client)
    assert run_video(client,tmp_path)['event_ids']==[]
    monkeypatch.setattr(pipeline,'detector',scripted_detector([.999,.999,.999]+[None]*40,raw=.4))
    assert len(run_video(client,tmp_path)['event_ids'])==1


def test_ai_second_opinion_is_advisory_and_stored(client,monkeypatch,tmp_path):
    from app import chat, review
    monkeypatch.setattr(chat,'STORAGE',tmp_path)
    async def predict(_, *args):
        return result()
    monkeypatch.setattr(pipeline,'detector',predict)
    login(client)
    ident=client.post('/api/v1/inference/predict-frame',files={'file':('gun.jpg',image_bytes(),'image/jpeg')}).json()['created_event_ids'][0]
    async def fake_model(prompt,images):
        assert images and 'Decide whether the images visibly support' in prompt
        return '{"supports_detection": false, "confidence": 0.9, "visible_facts": ["a dark phone handset"], "cannot_determine": [], "explanation": "A phone, not a weapon."}', 'test-vlm', 'ollama'
    monkeypatch.setattr(review,'ask_model',fake_model)
    response=client.post(f'/api/v1/events/{ident}/ai-review')
    assert response.status_code==200,response.text
    event=response.json()
    assert event['ai_disagrees'] is True
    assert event['reasoning']['visible_facts']==['a dark phone handset'] and event['models']['vlm']['name']=='test-vlm'
    # advisory only: the AI never confirms or dismisses; the incident still awaits a human
    assert event['status']=='NEEDS_REVIEW' and event['verified_by']=='NONE'
    assert client.post('/api/v1/events/evt_missing/ai-review').status_code==404
