import { useState, type FormEvent } from 'react';
import type { Incident, System } from '../api/client';
import { Badge, Empty, ErrorNotice, Icon, Media } from '../components';

type Message={role:'user'|'assistant';text:string;eventIds:string[]};
export function Investigation({events,scope,setScope,onOpen,system}:{events:Incident[];scope:string|null;setScope:(id:string|null)=>void;onOpen:(e:Incident)=>void;system:System|null}) {
  const [messages,setMessages]=useState<Message[]>([]);
  const [input,setInput]=useState('');
  const [provider,setProvider]=useState('ollama');
  const [images,setImages]=useState(false);
  const [conversation,setConversation]=useState<string|null>(null);
  const [busy,setBusy]=useState(false);
  const [error,setError]=useState<string|null>(null);
  const [refs,setRefs]=useState<string[]>([]);
  async function send(e:FormEvent){
    e.preventDefault();if(!input.trim()||busy)return;
    const question=input.trim();setInput('');setBusy(true);setError(null);
    setMessages(old=>[...old,{role:'user',text:question,eventIds:[]},{role:'assistant',text:'',eventIds:[]}]);
    try{
      const response=await fetch('/api/v1/chat/stream',{method:'POST',credentials:'include',headers:{'Content-Type':'application/json'},body:JSON.stringify({message:question,conversation_id:conversation,provider,event_ids:scope?[scope]:[],include_images:images&&provider==='ollama'})});
      if(!response.ok)throw new Error(`Chat request failed (${response.status})`);
      const reader=response.body!.getReader();const decoder=new TextDecoder();let buffer='';
      while(true){const {value,done}=await reader.read();if(done)break;buffer+=decoder.decode(value,{stream:true});const lines=buffer.split('\n');buffer=lines.pop()||'';
        for(const line of lines){if(!line)continue;const item=JSON.parse(line);
          if(item.type==='error')throw new Error(item.message);
          if(item.type==='context'){setRefs(item.event_ids);setConversation(item.conversation_id);setMessages(old=>old.map((m,i)=>i===old.length-1?{...m,eventIds:item.event_ids}:m));}
          if(item.type==='delta')setMessages(old=>old.map((m,i)=>i===old.length-1?{...m,text:m.text+item.text}:m));
        }
      }
    }catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  return <div className="chat-layout"><section className="panel chat-panel"><div className="chat-toolbar"><select aria-label="Chat provider" value={provider} onChange={e=>setProvider(e.target.value)}><option value="ollama">Local · Gemma</option><option value="groq" disabled={!system?.chat.groq_configured}>Groq · Cloud</option></select><select aria-label="Incident scope" value={scope||''} onChange={e=>{setScope(e.target.value||null);setConversation(null);setMessages([]);}}><option value="">Recent matching incidents</option>{events.map(e=><option key={e.id} value={e.id}>{e.category.label} · {e.camera.name}</option>)}</select></div><p className="caption">{provider==='groq'?'Selected incident metadata and your question will be sent to Groq. Video stays on your PC.':'Questions, metadata, and optional evidence frames stay on your PC.'}</p>{provider==='ollama'&&<label className="checkbox"><input type="checkbox" checked={images} onChange={e=>setImages(e.target.checked)}/>Include up to 2 evidence frames for visual context</label>}<div className="messages" aria-live="polite">{messages.length?messages.map((m,i)=><div className={`message ${m.role}`} key={i}><span className="eyebrow">{m.role==='user'?'YOU':'SAFESPACE'}</span><p>{m.text||(busy?'Connecting to the model…':'No response received.')}</p>{m.role==='assistant'&&m.eventIds.length>0&&<div className="citation-links">{m.eventIds.slice(0,5).map(id=>{const ev=events.find(e=>e.id===id);return ev?<button key={id} onClick={()=>onOpen(ev)}>{ev.category.label} <Icon name="link-external" size={16}/></button>:null;})}</div>}</div>):<Empty title="The story is in the evidence." icon="search-01">Ask what happened, which detections need review, or show the recording for an incident. Answers cite the records used.</Empty>}</div><ErrorNotice message={error}/><form className="chat-composer" onSubmit={send}><textarea aria-label="Ask about incidents" rows={2} placeholder="What happened in the most recent incident?" value={input} maxLength={4000} onChange={e=>setInput(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();e.currentTarget.form?.requestSubmit();}}}/><button className="primary" disabled={busy||!input.trim()} aria-label="Send question"><Icon name="search-01"/>{busy?'Answering…':'Ask'}</button></form></section><aside className="panel"><div className="section-head"><h2>Evidence desk</h2><Badge>{refs.length}</Badge></div>{refs.length?refs.map(id=>{const e=events.find(e=>e.id===id);return e?<article className="evidence-card" key={id}><Media incident={e}/><h3>{e.category.label}</h3><p>{e.camera.name}</p><button onClick={()=>onOpen(e)}>Open incident<Icon name="link-external"/></button></article>:null;}):<Empty title="Sources appear here" icon="video-on">Referenced images and recordings stay beside the conversation.</Empty>}</aside></div>;
}
