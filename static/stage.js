const el = id => document.getElementById(id);
const playerParams = new URLSearchParams(location.search);
const inspecting = playerParams.get('mode') === 'inspect';
let loadVersion=0,loading=Promise.resolve(),playerReady=false;
let videoCharacter=null,cardBackground=false;
const role = new URLSearchParams(location.search).get('mode') === 'obs' ? 'obs' : 'preview';
if(new URLSearchParams(location.search).get('desktop')==='1') {
  el('desktop-stage-bar').hidden=false;
  el('close-stage').onclick=()=>window.close();
}
document.body.classList.toggle('obs', role === 'obs');
const clientId = crypto.randomUUID();
const audio = new Audio();
audio.id='stage-audio';audio.hidden=true;document.body.append(audio);
let playSerial=0,cancelAudioLoad=null;
audio.preload = 'auto';
let ready = false, active = false, isOwner = false, currentId = '', completed = '', failed = '', avatar, lastTick = 0, tickBusy = false, currentJob = null, tickTimer;

function configure(a) {
  if(active&&playerReady&&avatar?.mode===a.mode&&avatar?.character_id===a.character_id){avatar=a;el('scene-badge').textContent=a.name;return loading;}
  stopAudio();
  avatar=a;
  const characterId=inspecting?playerParams.get('character_id'):a.mode==='character'?a.character_id:null;
  const version=++loadVersion;
  loading=loading.then(async()=>{
    if(version!==loadVersion)return;
    playerReady=false;
    if(videoCharacter){videoCharacter.destroy();videoCharacter=null;}
    el('character-videos').hidden=true;el('card-background').hidden=true;
    el('no-scene').hidden=false;el('enable-audio').hidden=true;
    if(!characterId)return;
    try{
      const response=await fetch('/api/characters/'+encodeURIComponent(characterId));const card=await response.json();
      if(!response.ok)throw Error(card.detail||'角色卡不存在');
      if(version!==loadVersion)return;
      el('character-videos').hidden=false;
      videoCharacter=new CharacterPlayer(el('character-videos'),{onError:report,onState:data=>{
        if(parent!==window)parent.postMessage({type:'character-preview-state',...data},location.origin);
      }});
      await videoCharacter.load(card,'/media/characters/'+characterId+'/');
      if(version!==loadVersion)return;
      cardBackground=card.background_visible!==false&&!!card.background;
      el('card-background').src=card.background?'/media/characters/'+characterId+'/'+card.background:'';
      el('card-background').hidden=!cardBackground;
      playerReady=true;el('no-scene').hidden=true;el('enable-audio').hidden=ready||inspecting;
      el('scene-badge').textContent=card.name;
    }catch(error){report(error.message);}
  });
  return loading;
}
async function enable(){
  ready=true;el('enable-audio').hidden=true;
  if(inspecting)return;
  if(!tickTimer)tickTimer=setInterval(tick,650);
  await tick();
}
el('enable-audio').onclick = enable;
window.addEventListener('message', e => {
  if (e.origin !== location.origin)return;
  if(e.source===parent&&!inspecting&&!active&&e.data?.type==='preview-avatar'){
    configure(e.data.avatar);return;
  }
  if (e.data?.type === 'activate-audio') enable();
  if(inspecting&&e.data?.type==='character-title')el('scene-badge').textContent=String(e.data.name||'角色卡');
  if(inspecting&&e.data?.type==='stop-preview'){stopAudio();active=false;}
  if((inspecting||(!active&&e.source===parent))&&e.data?.type==='character-action'){
    const version=loadVersion;
    loading.then(()=>{
      if(version!==loadVersion||!videoCharacter||(!inspecting&&active))return;
      stopAudio();const kind=e.data.action==='speaking'?'talk':e.data.action;
      return videoCharacter.show(kind);
    }).catch(error=>report(error.message));
  }
  if(inspecting&&e.data?.type==='character-background'){
    if(videoCharacter){cardBackground=!cardBackground;el('card-background').hidden=!cardBackground||!el('card-background').getAttribute('src');}
  }
  if(inspecting&&e.data?.type==='character-audio'){
    enable().then(()=>{active=true;isOwner=true;play({id:'test',kind:'narration',text:e.data.text,audio:e.data.url,
      gesture:['thanks','greeting','present'].includes(e.data.action)?e.data.action:null,emotion:e.data.action==='happy'?'happy':'talk'});});
  }
});
audio.onended = async () => {
  if(!currentId||currentJob?.kind==='action')return;
  const serial=playSerial,id=currentId;
  el('subtitle').classList.add('hidden');el('stage').classList.remove('thank');
  try{await videoCharacter?.endSpeech();}catch(error){report(error.message);}
  if(serial!==playSerial||id!==currentId)return;
  completed=id;if(inspecting){active=false;}else tick();
};
audio.onerror = () => {if(!currentId)return;failed = currentId; report('音频加载失败，请检查本地服务和语音设置');if(inspecting){stopAudio();active=false;}else tick();};
function report(message) {
  if (window.parent !== window) parent.postMessage({type:'player-error', message}, location.origin);
  else {el('output-note').textContent = message; el('output-note').hidden = false;}
}
function stopAudio() {
  playSerial++;
  cancelAudioLoad?.();cancelAudioLoad=null;
  audio.pause(); audio.currentTime = 0;
  el('subtitle').classList.add('hidden'); el('stage').classList.remove('thank');
  currentId = ''; currentJob = null;
  videoCharacter?.reset().catch(()=>{});
}
function prepareAudio(url){
  cancelAudioLoad?.();
  return new Promise((resolve,reject)=>{
    const cleanup=()=>{clearTimeout(timer);audio.removeEventListener('canplay',loaded);audio.removeEventListener('error',failed);if(cancelAudioLoad===cancel)cancelAudioLoad=null;};
    const loaded=()=>{cleanup();resolve(true);};
    const failed=()=>{cleanup();reject(Error('语音音频无法加载'));};
    const cancel=()=>{cleanup();resolve(false);};
    const timer=setTimeout(()=>{cleanup();reject(Error('语音音频加载超时'));},15000);
    cancelAudioLoad=cancel;audio.addEventListener('canplay',loaded,{once:true});audio.addEventListener('error',failed,{once:true});
    audio.src=url;audio.load();if(audio.readyState>=3)loaded();
  });
}
async function play(job) {
  const serial=++playSerial;
  audio.pause();el('subtitle').classList.add('hidden');
  currentId = job.id; currentJob = job;
  if(job.kind!=='action'){
    try{if(!await prepareAudio(job.audio)||serial!==playSerial)return;}
    catch(error){if(serial===playSerial){failed=job.id;report(error.message);tick();}return;}
  }
  if(videoCharacter){
    try{
      if(job.kind==='action'){
        await videoCharacter.gesture(job.action);
        if(serial===playSerial){completed=job.id;tick();}return;
      }
      await videoCharacter.beginSpeech(job.gesture||(job.kind==='gift'?'thanks':null),job.emotion||'talk');
    }catch(error){if(serial===playSerial){failed=job.id;report(error.message);tick();}return;}
  }
  if(job.kind==='action') {completed=job.id;tick();return;}
  if(serial!==playSerial)return;
  el('subtitle-label').textContent = job.kind === 'gift' ? '✦ 感谢支持 · ' + (job.username || '') : job.kind === 'comment' ? '回答 ' + (job.username || '观众') : '商品讲解';
  el('subtitle-text').textContent = job.text;
  el('stage').classList.toggle('thank', job.kind === 'gift');
  try {await audio.play();if(serial===playSerial)el('subtitle').classList.remove('hidden');}
  catch {
    // Autoplay policy requires a real click in some browsers / OBS.
    ready = false; el('enable-audio').hidden = false;
    el('enable-hint').textContent = '请点击启用，浏览器阻止了自动播放。';
    currentId = '';
    report('浏览器阻止了声音，请在预览或 OBS“交互”中点击启用播出声音');
  }
}
async function tick() {
  if (!ready || !playerReady || tickBusy) return;
  tickBusy = true;
  const sentComplete = completed, sentFailed = failed;
  try {
    const res = await fetch('/api/player/tick', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({client_id:clientId,role,completed:sentComplete,failed:sentFailed})});
    if (!res.ok) throw new Error('connection');
    const data = await res.json();
    lastTick = Date.now();
    if (completed === sentComplete) completed = '';
    if (failed === sentFailed) failed = '';
    isOwner = data.owner; active = data.runtime.active;
    if (!isOwner) {
      if (currentId) stopAudio();
      el('output-note').textContent = role === 'preview' ? '播出声音已由另一画面接管' : '另一播出画面正在使用声音';
      el('output-note').hidden = false;
      return;
    }
    el('output-note').hidden = true;
    if (!active) { if (currentId) stopAudio(); return; }
    const job = data.runtime.current;
    if(!job&&currentId)stopAudio();
    // Keep heartbeats running while a silent action precedes the utterance.
    if (job && job.id !== currentId) void play(job);
  } catch {
    if (Date.now()-lastTick > 5000 && currentId) stopAudio();
  } finally { tickBusy = false; }
}
(async () => {
  try {
    const state = await (await fetch('/api/state')).json();
    await configure(state.settings.avatar); active = state.runtime.active;
    if(inspecting)el('enable-audio').hidden=true;
    if(!inspecting){
    const stream = new EventSource('/api/stream');
    stream.onmessage = e => {
      const message = JSON.parse(e.data);
      if (message.type === 'settings') configure(message.data.avatar);
      if (message.type === 'runtime') {
        if(inspecting)return;
        active = message.data.active;
        if (!active) stopAudio();
        if (message.data.owner_role === 'obs' && role === 'preview' && isOwner) {isOwner = false; stopAudio();}
      }
    };
    stream.onerror = () => {if (Date.now()-lastTick>5000) stopAudio();};
    }
    if (role === 'obs'&&!inspecting) await enable();
  } catch { report('无法连接工作台，请确认本地服务正在运行'); }
})();
