import { useEffect, useRef, useState, type FormEvent } from 'react';
import { api, post, date, type Source, type Camera } from '../api/client';
import { Badge, Empty, ErrorNotice, Icon, Modal } from '../components';

export function Analyze({sources,cameras,refresh,onIncident,onCreateRule}:{sources:Source[];cameras:Camera[];refresh:()=>Promise<void>;onIncident:(id:string)=>void;onCreateRule:(cameraId:string)=>void}) {
  const [mode,setMode]=useState('upload');
  const [sourceFilter,setSourceFilter]=useState<'videos'|'all'>('videos');
  const [videoSearch,setVideoSearch]=useState('');
  const [error,setError]=useState<string|null>(null);
  const [busy,setBusy]=useState(false);
  const [selected,setSelected]=useState<string|null>(null);
  const [newCamera,setNewCamera]=useState(false);
  const [live,setLive]=useState(false);
  const video=useRef<HTMLVideoElement>(null);
  const stream=useRef<MediaStream>();
  const recorder=useRef<MediaRecorder>();
  const timer=useRef<number>();
  const running=useRef(false);
  const input=useRef<HTMLInputElement>(null);
  const [previewCamera,setPreviewCamera]=useState<string|null>(null);
  const [tick,setTick]=useState(Date.now());
  const [liveBoxes,setLiveBoxes]=useState<{width:number;height:number;detections:NonNullable<Source['result']>['detections']}|null>(null);
  const [media,setMedia]=useState<{title:string;url:string;video:boolean}|null>(null);
  const [recordings,setRecordings]=useState<{id:string;camera_id:string;started_at:string;status:string;url:string}[]|null>(null);
  const source=sources.find(s=>s.id===selected);
  const visibleSources=(sourceFilter==='videos'?sources.filter(s=>s.kind==='video'||s.kind==='live'):sources).filter(s=>s.filename.toLowerCase().includes(videoSearch.trim().toLowerCase()));
  useEffect(()=>{const t=setInterval(()=>setTick(Date.now()),500);return()=>clearInterval(t);},[]);
  useEffect(()=>{
    if(!previewCamera){setLiveBoxes(null);return;}
    let cancelled=false;
    const load=async()=>{try{const live=await api<{running:boolean;result?:{width:number;height:number;detections:NonNullable<Source['result']>['detections']}}>(`/cameras/${previewCamera}/live`);if(!cancelled)setLiveBoxes(live.running&&live.result?live.result:null);}catch{if(!cancelled)setLiveBoxes(null);}};
    void load();const t=setInterval(load,1000);return()=>{cancelled=true;clearInterval(t);};
  },[previewCamera]);
  function stop(){running.current=false;clearTimeout(timer.current);if(recorder.current?.state==='recording')recorder.current.stop();stream.current?.getTracks().forEach(t=>t.stop());setLive(false);}
  useEffect(()=>()=>{running.current=false;clearTimeout(timer.current);if(recorder.current?.state==='recording')recorder.current.stop();stream.current?.getTracks().forEach(t=>t.stop());},[]);
  async function upload(file:File,background=false){
    if(!background)setBusy(true);setError(null);
    try{const form=new FormData();form.append('file',file);const item=await api<Source>('/sources',{method:'POST',body:form});setSelected(item.id);await refresh();}
    catch(e){setError((e as Error).message);if(background)stop();}finally{if(!background)setBusy(false);}
  }
  async function startBrowser(){
    try{
      if(!navigator.mediaDevices?.getUserMedia)throw new Error('Browser camera needs localhost or HTTPS. Use the native mobile app on your phone, or add a PC camera below.');
      stream.current=await navigator.mediaDevices.getUserMedia({video:{width:1280,height:720},audio:false});
      running.current=true;setLive(true);setError(null);
      if(video.current){video.current.srcObject=stream.current;await video.current.play();}
      const record=()=>{
        if(!running.current||!stream.current)return;
        const mime=MediaRecorder.isTypeSupported('video/webm;codecs=vp8')?'video/webm;codecs=vp8':'video/webm';
        const chunks:BlobPart[]=[];
        const current=new MediaRecorder(stream.current,{mimeType:mime});recorder.current=current;
        current.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
        current.onstop=async()=>{if(chunks.length)await upload(new File(chunks,`Camera ${new Date().toISOString().replaceAll(':','-')}.webm`,{type:mime}),true);if(running.current)record();};
        current.start();timer.current=window.setTimeout(()=>{if(current.state==='recording')current.stop();},5000);
      };record();
    }catch(e){setError((e as Error).message);stop();}
  }
  async function addCamera(e:FormEvent<HTMLFormElement>){
    e.preventDefault();setBusy(true);const f=new FormData(e.currentTarget);
    try{await post('/cameras',{name:f.get('name'),source_type:f.get('type'),connection_uri:f.get('uri')});setNewCamera(false);await refresh();}catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  async function snapshot(camera:Camera){
    try{const item=await post<{url:string}>(`/cameras/${camera.id}/snapshots`,{});setMedia({title:`${camera.name} · Screenshot saved on laptop`,url:item.url,video:false});}
    catch(e){setError((e as Error).message);}
  }
  async function openRecordings(camera:Camera){
    try{setRecordings(await api(`/cameras/${camera.id}/recordings`));}
    catch(e){setError((e as Error).message);}
  }
  return <><ErrorNotice message={error}/><div className="actions tabs"><button aria-pressed={mode==='upload'} onClick={()=>{stop();setMode('upload');}}><Icon name="upload-02"/>Upload media</button><button aria-pressed={mode==='live'} onClick={()=>setMode('live')}><Icon name="video-on"/>Live sources</button></div>
    <div className="analysis-grid"><section className="panel viewer-panel">
      {mode==='upload'?<><input ref={input} hidden type="file" accept="image/jpeg,image/png,image/webp,video/mp4,video/webm,video/quicktime,video/x-msvideo,video/x-matroska" onChange={e=>{const f=e.target.files?.[0];if(f)void upload(f);e.target.value='';}}/><button className={`drop-zone ${source?'compact':''}`} disabled={busy} onClick={()=>input.current?.click()} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();const f=e.dataTransfer.files[0];if(f)void upload(f);}}><div className="empty-icon"><Icon name="upload-02" size={source?24:40}/></div><div className="drop-copy"><h2>{busy?'Uploading video…':'Upload a video to analyze'}</h2><p>Drop a recording here or choose one from your device.</p></div><span className="badge">Videos and images · Up to 500 MB</span></button></>:<><div className="section-head"><h2>This device’s camera</h2><Badge>{live?'Recording':'Stopped'}</Badge></div><video className={live?'live-preview':'live-preview hidden-preview'} style={{width:'100%',aspectRatio:'16 / 9',objectFit:'cover',background:'#000',borderRadius:16}} ref={video} muted playsInline/>{!live&&<Empty title="Ready when you are" icon="video-on">Camera access starts only when you press Start. Short recordings are sent to your PC for detection and playback.</Empty>}<div className="actions"><button className="primary" onClick={()=>live?stop():void startBrowser()}><Icon name={live?'pause-01':'play-01'}/>{live?'Stop camera':'Start camera'}</button></div><p className="caption">5-second clips share the upload detection pipeline. Live recording pauses between submissions to avoid a growing processing queue.</p></>}
      {source?.media_url&&!source.result&&source.kind!=='image'&&<div className="result"><h3>Selected video</h3><div className="media-stage" style={{width:'100%',aspectRatio:'16 / 9'}}><video controls preload="metadata" src={source.media_url} style={{width:'100%',height:'100%',aspectRatio:'16 / 9',objectFit:'cover'}}/></div><p className="caption">Analysis is {source.status.toLowerCase()}. Results will appear below when ready.</p></div>}
      {source&&<div className="result"><div className="section-head"><h3>{source.filename}</h3><Badge>{source.status.toLowerCase()}</Badge></div>{source.error?<ErrorNotice message={source.error}/>:source.result?<><p className="result-verdict">{(source.event_ids||[]).length?'Detection needs your attention.':'No supported threat detected.'}</p>{source.result.detections.filter(d=>d.model==='violence').map(d=><Badge key="violence">Violence likelihood {Math.round(d.confidence*100)}%</Badge>)}<p className="caption">{source.result.inference_ms.toFixed(0)} ms last-frame inference · {source.frames_analyzed} analyzed frames · {source.result.models.join(', ')}</p><div className="media-stage" style={{width:'100%',aspectRatio:'16 / 9'}}>{source.media_url&&(source.kind==='image'?<><img className="evidence" src={source.media_url} alt={source.filename} style={{width:'100%',height:'100%',aspectRatio:'16 / 9',objectFit:'cover'}}/><svg viewBox={`0 0 ${source.result.width} ${source.result.height}`} preserveAspectRatio="none" aria-label="Detection boxes">{source.result.detections.filter(box=>box.model!=='violence').map((box,i)=><g key={i}><rect x={box.box[0]} y={box.box[1]} width={box.box[2]-box.box[0]} height={box.box[3]-box.box[1]}/><text x={box.box[0]+4} y={Math.max(18,box.box[1]-6)}>{box.class_name} {Math.round(box.confidence*100)}%</text></g>)}</svg></>:<video controls src={source.media_url} style={{width:'100%',height:'100%',aspectRatio:'16 / 9',objectFit:'cover'}}/> )}</div><div className="actions">{(source.event_ids||[]).map(id=><button key={id} onClick={()=>onIncident(id)}>Review incident <Icon name="link-external"/></button>)}</div><p className="caption">Coverage: {source.result.covered_classes.join(', ')}. This is a model observation, not a guarantee of safety.</p></>:<p className="muted">Your source is queued for the detector. Results appear here when ready.</p>}</div>}
      {source?.camera_id&&source.result&&<button className="analysis-rule-link" type="button" onClick={()=>onCreateRule(source.camera_id!)}><Icon name="shield-check"/>Set an alert rule for this camera <Icon name="chevron-right" size={16}/></button>}
    </section><aside className="panel analyze-library"><div className="section-head"><h2>Existing videos</h2><Badge>{visibleSources.length}</Badge></div><input className="source-search" type="search" value={videoSearch} onChange={e=>setVideoSearch(e.target.value)} placeholder="Search videos" aria-label="Search existing videos"/><div className="actions source-filters"><button type="button" aria-pressed={sourceFilter==='videos'} onClick={()=>setSourceFilter('videos')}>Videos</button><button type="button" aria-pressed={sourceFilter==='all'} onClick={()=>setSourceFilter('all')}>All media</button></div>{visibleSources.length?<div className="history">{visibleSources.map(s=><button key={s.id} className={selected===s.id?'selected':''} onClick={()=>setSelected(s.id)}><Icon name={s.kind==='image'?'upload-02':'video-on'}/><div><strong>{s.filename}</strong><small>{date(s.created_at)}</small><span>{s.status.toLowerCase()} · {(s.event_ids||[]).length} {(s.event_ids||[]).length===1?'incident':'incidents'}</span></div></button>)}</div>:<Empty title={videoSearch?'No matching videos':sourceFilter==='videos'?'No videos yet':'No media yet'}>{videoSearch?'Try another filename.':'Upload a recording to see it here.'}</Empty>}</aside></div>
    {mode==='live'&&<section className="panel"><div className="section-head"><h2>Live cameras</h2><button onClick={()=>setNewCamera(true)}><Icon name="plus-01"/>Add PC camera</button></div>
      <p className="caption">Paired phones appear here when Camera station is running. The laptop records every phone feed and evaluates its selected rules.</p>
      {cameras.length?<div className="camera-grid">{cameras.map(c=><article className="source-card" key={c.id}>
        <div className="section-head"><strong>{c.name}</strong><Badge>{c.is_online?'Live':'Offline'}</Badge></div>
        {c.is_online?<div className="media-stage" style={{width:'100%',aspectRatio:'16 / 9'}}><img className="evidence" alt={`${c.name} live feed`} src={`/api/v1/cameras/${c.id}/frame?t=${tick}`} style={{width:'100%',height:'100%',aspectRatio:'16 / 9',objectFit:'cover'}}/>
          {previewCamera===c.id&&liveBoxes&&<svg viewBox={`0 0 ${liveBoxes.width} ${liveBoxes.height}`} preserveAspectRatio="none" aria-label="Live detection boxes">{liveBoxes.detections.filter(b=>b.model!=='violence').map((box,i)=><g key={i}><rect x={box.box[0]} y={box.box[1]} width={box.box[2]-box.box[0]} height={box.box[3]-box.box[1]}/><text x={box.box[0]+4} y={Math.max(18,box.box[1]-6)}>{box.class_name} {Math.round(box.confidence*100)}%</text></g>)}</svg>}
        </div>:<div className="media-stage" style={{width:'100%',aspectRatio:'16 / 9',display:'grid',placeItems:'center'}}><div className="empty-icon"><Icon name="video-on" size={40}/></div><p>Waiting for this camera</p></div>}
        <p className="caption">{c.source_type==='PHONE'?'Paired phone camera':c.source_type.toLowerCase()}</p>
        {previewCamera===c.id&&liveBoxes?.detections.some(d=>d.model==='violence')&&<Badge>Possible violence</Badge>}
        <div className="actions">
          <button onClick={()=>onCreateRule(c.id)}><Icon name="shield-check"/>Create rule</button>
          {c.source_type!=='PHONE'&&<button onClick={async()=>{try{await post(`/cameras/${c.id}/${c.is_online?'stop':'start'}`);await refresh();}catch(e){setError((e as Error).message);}}}>{c.is_online?'Stop':'Start'}</button>}
          {c.is_online&&<button onClick={()=>setPreviewCamera(previewCamera===c.id?null:c.id)}>{previewCamera===c.id?'Hide boxes':'Show boxes'}</button>}
          {c.is_online&&<button onClick={()=>void snapshot(c)}><Icon name="video-on"/>Screenshot</button>}
          <button onClick={()=>void openRecordings(c)}><Icon name="play-01"/>Recordings</button>
        </div>
      </article>)}</div>:<Empty title="Connect your first camera" icon="video-on">Use a paired phone as a camera, a PC webcam, or an RTSP camera.</Empty>}
    </section>}
    {media&&<Modal title={media.title} close={()=>setMedia(null)}><div className="media-stage" style={{width:'100%',aspectRatio:'16 / 9'}}>{media.video?<video controls autoPlay style={{width:'100%',height:'100%',aspectRatio:'16 / 9',objectFit:'cover'}} src={media.url}/>:<img className="evidence" src={media.url} alt={media.title} style={{width:'100%',height:'100%',aspectRatio:'16 / 9',objectFit:'cover'}}/>}</div></Modal>}
    {recordings&&<Modal title="Laptop recordings" close={()=>setRecordings(null)}><div className="history">{recordings.length?recordings.map(item=><button key={item.id} disabled={item.status!=='READY'} onClick={()=>{setRecordings(null);setMedia({title:`Recording · ${date(item.started_at)}`,url:item.url,video:true});}}><Icon name="play-01"/><div><strong>{date(item.started_at)}</strong><span>{item.status.toLowerCase()}</span></div></button>):<p>No recordings yet.</p>}</div></Modal>}
    {newCamera&&<Modal title="Add a server camera" close={()=>setNewCamera(false)}><form onSubmit={addCamera}><label>Name<input name="name" required placeholder="Entrance camera"/></label><label>Camera type<select name="type"><option value="WEBCAM">PC webcam</option><option value="RTSP">RTSP network camera</option></select></label><label>Device index or RTSP address<input name="uri" required placeholder="0 or rtsp://camera-address/stream"/></label><p className="caption">Device 0 is usually the PC’s default webcam. Camera addresses are stored only on this server.</p><button className="primary" disabled={busy}>Save camera</button></form></Modal>}
  </>;
}

