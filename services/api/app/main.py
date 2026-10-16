"""SafeSpace authenticated local server; serves the built dashboard and shared API."""
import asyncio
from collections import defaultdict, deque
from contextlib import asynccontextmanager
import json
import mimetypes
from pathlib import Path
import secrets
import time
import uuid
import httpx
import psutil
from fastapi import FastAPI, APIRouter, Depends, File, Form, HTTPException, Query, Request, Response, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from td_contracts import (LoginRequest, LoginResponse, PairDeviceRequest, PairDeviceResponse, PairingCodeCreateResponse, UserOut, WsTicketResponse, CameraCreate, CameraOut, CameraUpdate, EventOut, ChangesResponse, HumanVerificationRequest, ChatRequest, ChatResponse, SourceRecord, FrameResult, PasswordChange, RuntimeSettings, SystemSnapshot)
from . import database as db, pipeline, chat
from .security import authenticated, bootstrap, check_password, create_session, digest, now, password_hash, session_for
from .settings import ROOT, STORAGE, INFERENCE_URL, INTERNAL_TOKEN, OLLAMA_URL, COOKIE_SECURE, ALLOWED_ORIGINS, MAX_UPLOAD

SOCKETS={}
TICKETS={}
ATTEMPTS=defaultdict(deque)


async def broadcast(envelope):
    async def send(ws,token):
        try:
            if not session_for(token):
                await ws.close(code=4401)
                SOCKETS.pop(ws,None)
                return
            await asyncio.wait_for(ws.send_json(envelope),2)
        except Exception:
            SOCKETS.pop(ws,None)
    await asyncio.gather(*(send(ws,token) for ws,token in list(SOCKETS.items())))


@asynccontextmanager
async def lifespan(app):
    db.initialize()
    bootstrap()
    pipeline.BROADCAST=broadcast
    for source in db.all_objects('source'):
        if source['status'] in ('PENDING','RUNNING'):
            source.update(status='FAILED',error='Server restarted. Upload again or restart the camera.')
            db.put('source',source)
    for camera in db.all_objects('camera'):
        camera['is_online']=False
        db.put('camera',camera)
    warm = asyncio.create_task(chat.warmup())
    yield
    warm.cancel()
    await pipeline.shutdown()


app=FastAPI(title='SafeSpace API',version='2.0.0',lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=ALLOWED_ORIGINS,allow_credentials=True,allow_methods=['GET','POST','PATCH','DELETE'],allow_headers=['Content-Type','Authorization'])
api=APIRouter(prefix='/api/v1',dependencies=[Depends(authenticated)])


@app.middleware('http')
async def security_headers(request,call_next):
    response=await call_next(request)
    response.headers['X-Content-Type-Options']='nosniff'
    response.headers['Referrer-Policy']='same-origin'
    response.headers['X-Frame-Options']='DENY'
    if request.url.path.startswith('/api'):
        response.headers['Cache-Control']='no-store'
    return response


@app.get('/api/v1/health/live')
async def health_live():
    return {'status':'ok'}


def throttle(request):
    key=request.client.host if request.client else 'unknown'
    bucket=ATTEMPTS[key]
    while bucket and bucket[0]<time.time()-60:
        bucket.popleft()
    if len(bucket)>=10:
        raise HTTPException(429,'Too many attempts. Wait one minute.')
    bucket.append(time.time())


@app.post('/api/v1/auth/login',response_model=LoginResponse)
async def login(req:LoginRequest,request:Request,response:Response):
    throttle(request)
    with db.connection() as con:
        user=con.execute('SELECT * FROM users WHERE email=?',(req.username.lower().strip(),)).fetchone()
    if not user or not await asyncio.to_thread(check_password,req.password,user['password']):
        raise HTTPException(401,'Incorrect email or password')
    token,device=create_session(user['id'],req.device_name)
    if req.client_type=='web':
        response.set_cookie('safespace_session',token,httponly=True,secure=COOKIE_SECURE,samesite='strict',max_age=7*86400,path='/')
    return LoginResponse(device_id=device,device_name=req.device_name,device_token=token if req.client_type=='mobile' else None)


@api.get('/auth/me',response_model=UserOut)
async def me(request:Request):
    s=request.state.session
    return UserOut(id=s['user_id'],username=s['email'],role='admin',created_at=s['user_created'])


@api.post('/auth/logout')
async def logout(request:Request,response:Response):
    with db.connection() as con:
        con.execute('DELETE FROM sessions WHERE token=?',(request.state.session['token'],))
    response.delete_cookie('safespace_session',path='/')
    return {'ok':True}


@api.post('/auth/password')
async def change_password(req:PasswordChange,request:Request,response:Response):
    ident=request.state.session['user_id']
    with db.connection() as con:
        user=con.execute('SELECT * FROM users WHERE id=?',(ident,)).fetchone()
    if not await asyncio.to_thread(check_password,req.current_password,user['password']):
        raise HTTPException(400,'Current password is incorrect')
    hashed=await asyncio.to_thread(password_hash,req.new_password)
    with db.connection() as con:
        con.execute('UPDATE users SET password=? WHERE id=?',(hashed,ident))
        con.execute('DELETE FROM sessions WHERE user_id=?',(ident,))
    response.delete_cookie('safespace_session',path='/')
    return {'ok':True,'message':'Password changed. Sign in again on your devices.'}


@api.post('/auth/pairing-code',response_model=PairingCodeCreateResponse)
async def pairing_code(request:Request):
    code=secrets.token_hex(4).upper()
    with db.connection() as con:
        con.execute('DELETE FROM pairing WHERE expires<?',(time.time(),))
        con.execute('INSERT INTO pairing VALUES(?,?,?)',(digest(code),request.state.session['user_id'],time.time()+600))
    return PairingCodeCreateResponse(code=code,qr_payload=json.dumps({'url':str(request.base_url).rstrip('/'),'code':code}),expires_in=600)


@app.post('/api/v1/auth/pair',response_model=PairDeviceResponse)
async def pair(req:PairDeviceRequest,request:Request):
    throttle(request)
    with db.connection() as con:
        row=con.execute('DELETE FROM pairing WHERE code=? AND expires>? RETURNING user_id',(digest(req.code.upper()),time.time())).fetchone()
    if not row:
        raise HTTPException(401,'Pairing code is invalid or expired')
    token,device=create_session(row['user_id'],req.device_name)
    return PairDeviceResponse(device_id=device,device_name=req.device_name,device_token=token)


@api.get('/devices')
async def devices(request:Request):
    with db.connection() as con:
        return [dict(r) for r in con.execute('SELECT device_id AS id,name,created_at,expires FROM sessions WHERE user_id=? AND expires>?',(request.state.session['user_id'],time.time()))]


@api.delete('/devices/{ident}')
async def revoke_device(ident:str,request:Request):
    with db.connection() as con:
        con.execute('DELETE FROM sessions WHERE device_id=? AND user_id=?',(ident,request.state.session['user_id']))
    return {'ok':True}


@api.post('/ws-tickets',response_model=WsTicketResponse)
async def ws_ticket(request:Request):
    for key,(expires,_) in list(TICKETS.items()):
        if expires<time.time():
            TICKETS.pop(key,None)
    ticket=secrets.token_urlsafe(32)
    header=request.headers.get('authorization','')
    token=header[7:] if header.startswith('Bearer ') else request.cookies.get('safespace_session','')
    TICKETS[ticket]=(time.time()+30,token)
    return WsTicketResponse(ticket=ticket)


@app.websocket('/api/v1/ws')
async def websocket(ws:WebSocket,ticket:str=''):
    entry=TICKETS.pop(ticket,None)
    if not entry or entry[0]<time.time() or not session_for(entry[1]):
        await ws.close(code=4401)
        return
    await ws.accept()
    SOCKETS[ws]=entry[1]
    await ws.send_json({'v':1,'type':'hello','sent_at':now(),'data':{'head_seq':db.head(),'heartbeat_s':20}})
    try:
        while session_for(entry[1]):
            try:
                await asyncio.wait_for(ws.receive_text(),20)
                await ws.send_json({'v':1,'type':'pong','sent_at':now(),'data':{}})
            except asyncio.TimeoutError:
                await ws.send_json({'v':1,'type':'ping','sent_at':now(),'data':{}})
        await ws.close(code=4401)
    except (WebSocketDisconnect,RuntimeError):
        pass
    finally:
        SOCKETS.pop(ws,None)


@api.get('/events',response_model=list[EventOut])
async def events(camera_id:str|None=None,category:str|None=None,status:str|None=None,q:str|None=None,limit:int=Query(50,ge=1,le=200),offset:int=Query(0,ge=0)):
    rows=db.all_objects('event')
    if camera_id:
        rows=[e for e in rows if e['camera']['id']==camera_id]
    if category:
        rows=[e for e in rows if e['category']['key']==category]
    if status:
        rows=[e for e in rows if e['status']==status]
    if q:
        rows=[e for e in rows if q.lower() in json.dumps(e).lower()]
    return sorted(rows,key=lambda e:e['created_at'],reverse=True)[offset:offset+limit]


def required(kind,ident):
    item=db.get(kind,ident)
    if not item:
        raise HTTPException(404,f'{kind.title()} not found')
    return item


@api.get('/events/{ident}',response_model=EventOut)
async def event(ident:str):
    return required('event',ident)


@api.post('/events/{ident}/verification',response_model=EventOut)
async def verify(ident:str,req:HumanVerificationRequest,request:Request):
    event=required('event',ident)
    with db.connection() as con:
        old=con.execute('SELECT event_id FROM feedback WHERE action_id=?',(req.client_action_id,)).fetchone()
        if old:
            if old['event_id']!=ident:
                raise HTTPException(409,'Action id already used')
            return event
        con.execute('INSERT INTO feedback VALUES(?,?)',(req.client_action_id,ident))
    event.update(status={'CONFIRM':'CONFIRMED','MARK_FALSE_POSITIVE':'FALSE_POSITIVE','REOPEN':'NEEDS_REVIEW'}[req.action.value],verified_by='HUMAN',status_reason=req.note,updated_at=now())
    event['feedback'].append({'id':uuid.uuid4().hex,'client_action_id':req.client_action_id,'action':req.action.value,'note':req.note,'created_at':now(),'user_id':request.state.session['user_id']})
    db.save_event(event)
    await broadcast({'v':1,'type':'event.updated','sent_at':now(),'data':{'event':EventOut.model_validate(event).model_dump(mode='json',by_alias=True)}})
    return event


@api.get('/changes',response_model=ChangesResponse)
async def changes(after:int=Query(0,ge=0),limit:int=Query(50,ge=1,le=200)):
    with db.connection() as con:
        rows=con.execute('SELECT seq,body FROM changes WHERE seq>? ORDER BY seq LIMIT ?',(after,limit+1)).fetchall()
    return ChangesResponse(items=[EventOut.model_validate_json(r['body']) for r in rows[:limit]],next_after=rows[min(limit,len(rows))-1]['seq'] if rows else after,has_more=len(rows)>limit,head_seq=db.head())


@api.get('/events/{ident}/media/{filename}')
async def media(ident:str,filename:str):
    required('event',ident)
    if filename not in ('frame.jpg','clip.mp4','detections.json'):
        raise HTTPException(404,'Media not found')
    path=STORAGE/'media'/ident/filename
    if not path.is_file():
        raise HTTPException(404,'Media not found')
    return FileResponse(path,media_type=mimetypes.guess_type(filename)[0])


@api.get('/categories')
async def categories():
    import yaml
    mappings=yaml.safe_load((ROOT/'config/class_map.yaml').read_text())['mappings']
    return [{'key':key,'label':key.replace('_',' ').title()} for key in sorted({m['category'] for m in mappings.values() if m.get('category')})]


@api.post('/sources',response_model=SourceRecord,status_code=202)
async def upload(file:UploadFile=File(...),camera_id:str|None=Form(None)):
    if camera_id:
        required('camera',camera_id)
    ext=Path(file.filename or '').suffix.lower()
    if ext not in ('.jpg','.jpeg','.png','.webp','.mp4','.webm','.mov','.avi','.mkv'):
        raise HTTPException(415,'Choose a JPG, PNG, WebP, MP4, WebM, MOV, AVI or MKV file')
    if len(pipeline.TASKS)>=8:
        raise HTTPException(429,'Processing queue is full. Try again shortly.')
    ident=uuid.uuid4().hex
    folder=STORAGE/'uploads'/ident
    folder.mkdir()
    path=folder/('original'+ext)
    size=0
    with path.open('wb') as out:
        while chunk:=await file.read(1024*1024):
            size+=len(chunk)
            if size>MAX_UPLOAD:
                out.close()
                path.unlink(missing_ok=True)
                folder.rmdir()
                raise HTTPException(413,f'Upload exceeds {MAX_UPLOAD//1024//1024} MB')
            out.write(chunk)
    if size==0:
        path.unlink()
        folder.rmdir()
        raise HTTPException(422,'Empty file')
    kind='image' if ext in ('.jpg','.jpeg','.png','.webp') else 'video'
    source=SourceRecord(id=ident,filename=Path(file.filename).name,kind=kind,camera_id=camera_id,status='PENDING',created_at=now(),media_url=f'/api/v1/sources/{ident}/media' if kind=='image' else None).model_dump()
    db.put('source',source)
    pipeline.start_source(source,path)
    return source


@api.get('/sources',response_model=list[SourceRecord])
async def sources():
    return sorted(db.all_objects('source'),key=lambda s:s['created_at'],reverse=True)[:100]


@api.get('/sources/{ident}',response_model=SourceRecord)
async def source(ident:str):
    return required('source',ident)


@api.get('/sources/{ident}/media')
async def source_media(ident:str):
    source=required('source',ident)
    folder=STORAGE/'uploads'/ident
    path=folder/'playback.mp4' if source['kind']=='video' else next(folder.glob('original.*'),None)
    if not path or not path.is_file():
        raise HTTPException(404,'Media is not ready')
    return FileResponse(path,media_type=mimetypes.guess_type(str(path))[0])


@api.post('/inference/predict-frame',response_model=FrameResult)
async def predict_frame(file:UploadFile=File(...)):
    source=await upload(file,None)
    if source['kind']!='image':
        raise HTTPException(415,'Use /sources for video')
    await pipeline.TASKS[source['id']]
    result=required('source',source['id'])
    if result['status']!='DONE':
        raise HTTPException(503,result['error'])
    return result['result']


@api.get('/cameras',response_model=list[CameraOut])
async def cameras():
    return db.all_objects('camera')


@api.post('/cameras',response_model=CameraOut,status_code=201)
async def add_camera(req:CameraCreate):
    uri=req.connection_uri or '0'
    if req.source_type.value=='RTSP' and not uri.startswith('rtsp://'):
        raise HTTPException(422,'RTSP camera address must begin with rtsp://')
    if req.source_type.value=='WEBCAM' and not uri.isdigit():
        raise HTTPException(422,'Webcam source must be a numeric device index')
    if req.source_type.value=='FILE':
        raise HTTPException(422,'Use file upload to add recorded footage')
    cam=CameraOut(id='cam_'+uuid.uuid4().hex,name=req.name,source_type=req.source_type,connection_uri=uri,created_at=now()).model_dump(mode='json')
    return db.put('camera',cam)


@api.patch('/cameras/{ident}',response_model=CameraOut)
async def update_camera(ident:str,req:CameraUpdate):
    cam=required('camera',ident)
    cam.update(req.model_dump(exclude_none=True))
    return db.put('camera',cam)


@api.post('/cameras/{ident}/start',response_model=SourceRecord)
async def start_camera(ident:str):
    cam=required('camera',ident)
    if ident in pipeline.LIVE:
        raise HTTPException(409,'Camera already running')
    if not cam['enabled']:
        raise HTTPException(409,'Camera is disabled')
    source=SourceRecord(id=uuid.uuid4().hex,filename=cam['name'],kind='live',camera_id=ident,status='RUNNING',created_at=now()).model_dump()
    db.put('source',source)
    task=asyncio.create_task(pipeline.camera_loop(cam,source))
    pipeline.TASKS[source['id']]=task
    task.add_done_callback(lambda _:pipeline.TASKS.pop(source['id'],None))
    return source


@api.post('/cameras/{ident}/stop')
async def stop_camera(ident:str):
    required('camera',ident)
    if ident in pipeline.LIVE:
        pipeline.LIVE[ident].stopped=True
    return {'ok':True}


@api.get('/cameras/{ident}/live')
async def camera_live(ident:str):
    """Latest detector output for a running camera, for drawing boxes over the live preview."""
    required('camera',ident)
    source=pipeline.ACTIVE.get(ident)
    if not source:
        return {'running':False}
    return {'running':True,'frames_analyzed':source['frames_analyzed'],'result':source.get('result'),'event_ids':source['event_ids']}


@api.get('/cameras/{ident}/frame')
async def camera_frame(ident:str):
    capture=pipeline.LIVE.get(ident)
    if not capture:
        raise HTTPException(409,'Camera is not running')
    _,frame=capture.snapshot()
    if frame is None:
        raise HTTPException(503,'Waiting for camera')
    import cv2
    return Response(cv2.imencode('.jpg',frame)[1].tobytes(),media_type='image/jpeg')


@api.post('/chat/stream')
async def stream_chat(req:ChatRequest,request:Request):
    # Ownership is checked before opening the response stream.
    chat.context(req,request.state.session)
    async def lines():
        async for item in chat.stream(req,request.state.session):
            yield json.dumps(item)+'\n'
    return StreamingResponse(lines(),media_type='application/x-ndjson')


@api.post('/chat',response_model=ChatResponse)
async def ask_chat(req:ChatRequest,request:Request):
    async for item in chat.stream(req,request.state.session):
        if item['type']=='done':
            item.pop('type')
            return ChatResponse(**item)
        if item['type']=='error':
            raise HTTPException(503,item['message'])


@api.get('/settings',response_model=RuntimeSettings)
async def get_settings():
    return {k:v for k,v in chat.settings().items() if k!='id'}


@api.post('/settings',response_model=RuntimeSettings)
async def set_settings(req:RuntimeSettings):
    db.put('setting',{'id':'runtime',**req.model_dump()})
    return req


@api.get('/system',response_model=SystemSnapshot)
@api.get('/health',response_model=SystemSnapshot)
async def system():
    async with httpx.AsyncClient(timeout=3) as client:
        async def inspect(url,headers=None):
            try:
                response=await client.get(url,headers=headers)
                response.raise_for_status()
                return response.json()
            except (httpx.HTTPError,ValueError):
                return None
        inference,local=await asyncio.gather(inspect(f'{INFERENCE_URL}/health',{'Authorization':f'Bearer {INTERNAL_TOKEN}'}),inspect(f'{OLLAMA_URL}/api/tags'))
    records=db.all_objects('event')
    all_sources=db.all_objects('source')
    training_path=STORAGE/'training.json'
    try:
        training=json.loads(training_path.read_text()) if training_path.exists() else {'status':'not_started'}
    except (ValueError,OSError):
        training={'status':'unavailable'}
    import os
    benchmarks={}
    for path in sorted((STORAGE/'benchmarks').glob('*.json')):
        try:
            benchmarks[path.stem]=json.loads(path.read_text())
        except (ValueError,OSError):
            continue
    training['benchmarks']=benchmarks
    memory=psutil.virtual_memory()
    setup_path=STORAGE/'local-chat-setup.json'
    try:
        local_setup=json.loads(setup_path.read_text()) if setup_path.exists() else {'status':'not_started'}
    except (ValueError,OSError):
        local_setup={'status':'unavailable'}
    return SystemSnapshot(timestamp=now(),status='ok' if inference and inference.get('ready') else 'degraded',counts={'incidents':len(records),'needs_review':sum(e['status']=='NEEDS_REVIEW' for e in records),'confirmed':sum(e['status']=='CONFIRMED' for e in records),'sources':len(all_sources),'frames_analyzed':sum(s['frames_analyzed'] for s in all_sources),'cameras_online':sum(c['is_online'] for c in db.all_objects('camera'))},inference=inference or {'ready':False,'errors':['Detector service unavailable']},chat={'setup':local_setup,'local_available':local is not None,'installed_models':[m['name'] for m in (local or {}).get('models',[])],'groq_configured':bool(os.getenv('GROQ_API_KEY')),**{k:v for k,v in chat.settings().items() if k!='id'}},training=training,resources={'ram_used_gb':round(memory.used/1024**3,1),'ram_total_gb':round(memory.total/1024**3,1),'cpu_percent':psutil.cpu_percent(),'disk_free_gb':round(psutil.disk_usage(str(STORAGE)).free/1024**3,1)})


@api.post('/models/reload')
async def reload_models():
    async with httpx.AsyncClient(timeout=90) as client:
        try:
            result=await client.post(f'{INFERENCE_URL}/reload',headers={'Authorization':f'Bearer {INTERNAL_TOKEN}'})
            result.raise_for_status()
            return result.json()
        except httpx.HTTPError:
            raise HTTPException(503,'Detector service is unavailable')


app.include_router(api)
dashboard=ROOT/'apps/dashboard/dist'
if dashboard.exists():
    app.mount('/',StaticFiles(directory=dashboard,html=True),name='dashboard')

