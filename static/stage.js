const el = id => document.getElementById(id);
const sceneParams = new URLSearchParams(location.search);
const inspecting = sceneParams.get('mode') === 'inspect';
let sceneRenderer=null,sceneDemo='idle',sceneLoadVersion=0,sceneLoading=Promise.resolve(),sceneReady=false;
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
let playSerial=0;
const actionPlayer=new ActionPlayer({onError:report});
audio.preload = 'auto';
let ctx, analyser, samples, ready = false, active = false, isOwner = false, currentId = '', completed = '', failed = '', avatar, lastTick = 0, tickBusy = false, currentJob = null, tickTimer;

function configure(a) {
  stopAudio();
  avatar = a; el('portrait').src = a.image;
  const characterId=inspecting?sceneParams.get('character_id'):a.mode==='character'?a.character_id:null;
  const id=inspecting?sceneParams.get('scene_id'):a.scene_id;
  const version=++sceneLoadVersion;
  sceneLoading=sceneLoading.then(async()=>{
    if(version!==sceneLoadVersion)return;
    sceneReady=false;
    if(characterId){
      try{
        const response=await fetch('/api/characters/'+encodeURIComponent(characterId));const card=await response.json();
        if(!response.ok)throw Error(card.detail||'角色卡不存在');
        if(version!==sceneLoadVersion)return;
        if(sceneRenderer){sceneRenderer.destroy();sceneRenderer=null;}
        el('scene-canvas').hidden=true;el('character-wrap').hidden=true;el('character-videos').hidden=false;
        if(!videoCharacter)videoCharacter=new CharacterPlayer(el('character-videos'),{onError:report,onState:data=>{
          if(parent!==window)parent.postMessage({type:'character-preview-state',...data},location.origin);
        }});
        await videoCharacter.load(card,'/media/characters/'+characterId+'/');
        if(version!==sceneLoadVersion)return;
        cardBackground=card.background_visible!==false&&!!card.background;el('card-background').src=card.background?'/media/characters/'+characterId+'/'+card.background:'';
        el('card-background').hidden=!cardBackground;
        sceneReady=true;el('no-scene').hidden=true;el('enable-audio').hidden=ready||inspecting;
        el('scene-badge').textContent=card.name;return;
      }catch(error){report(error.message);return;}
    }
    if(videoCharacter){videoCharacter.destroy();videoCharacter=null;}
    el('character-videos').hidden=true;el('card-background').hidden=true;
    if(!id){
      stopAudio();
      if(sceneRenderer){sceneRenderer.destroy();sceneRenderer=null;}
      el('scene-canvas').hidden=true;el('character-wrap').hidden=false;
      el('no-scene').hidden=false;el('enable-audio').hidden=true;
      return;
    }
    try{
      const response=await fetch('/api/scenes/'+encodeURIComponent(id));
      const data=await response.json();if(!response.ok||!data.model)throw Error('场景模型尚未完成');
      if(version!==sceneLoadVersion)return;
      if(!sceneRenderer)sceneRenderer=new SceneRenderer(el('scene-canvas'));
      await sceneRenderer.load(data.model,data.base_url);
      if(version!==sceneLoadVersion)return;
      sceneReady=true;el('no-scene').hidden=true;
      el('scene-canvas').hidden=false;el('character-wrap').hidden=true;
      el('enable-audio').hidden=ready||inspecting;
      el('scene-badge').textContent=inspecting?'场景验收预览':'动态角色场景';
    }catch(e){stopAudio();el('scene-canvas').hidden=true;el('character-wrap').hidden=true;report(e.message);}
  });
  return sceneLoading;
}
async function enable() {
  try {
    if (!ctx) {
      ctx = new AudioContext();
      const source = ctx.createMediaElementSource(audio);
      analyser = ctx.createAnalyser(); analyser.fftSize = 256; analyser.smoothingTimeConstant = .3;
      samples = new Uint8Array(analyser.fftSize);
      source.connect(analyser); analyser.connect(ctx.destination);
    }
    await ctx.resume(); ready = true; el('enable-audio').hidden = true;
    if(inspecting)return;
    if (!tickTimer) tickTimer = setInterval(tick, 650);
    await tick();
  } catch { el('enable-audio').hidden = false; }
}
el('enable-audio').onclick = enable;
window.addEventListener('message', e => {
  if (e.origin !== location.origin)return;
  if(e.source===parent&&!inspecting&&!active&&e.data?.type==='preview-avatar'){
    configure(e.data.avatar);return;
  }
  if (e.data?.type === 'activate-audio') enable();
  if(inspecting&&e.data?.type==='character-title')el('scene-badge').textContent=String(e.data.name||'角色卡');
  if(inspecting&&e.data?.type==='stop-preview'){stopAudio();active=false;sceneDemo='idle';}
  if((inspecting||(!active&&e.source===parent))&&e.data?.type==='scene-action'){
    sceneDemo=e.data.action;
    const version=sceneLoadVersion;
    sceneLoading.then(()=>{
      if(version!==sceneLoadVersion||!videoCharacter||(!inspecting&&active))return;
      stopAudio();const kind=e.data.action==='speaking'?'talk':e.data.action;
      return videoCharacter.show(kind);
    }).catch(error=>report(error.message));
  }
  if(inspecting&&e.data?.type==='preview-clip'){
    stopAudio();sceneDemo='idle';
    const clip=sceneRenderer?.model.actions?.[e.data.kind];
    if(clip){
      const id=sceneRenderer.model.id,kind=e.data.kind;
      actionPlayer.play({...clip,url:'/media/scenes/'+id+'/'+clip.file}).then(ok=>{
        if(window.parent!==window)parent.postMessage({type:'action-preview-done',scene_id:id,kind,file:clip.file,ok},location.origin);
      });
    }
  }
  if(inspecting&&e.data?.type==='scene-background'){
    if(sceneRenderer)sceneRenderer.transparent=!sceneRenderer.transparent;
    if(videoCharacter){cardBackground=!cardBackground;el('card-background').hidden=!cardBackground||!el('card-background').getAttribute('src');}
  }
  if(inspecting&&e.data?.type==='scene-rig'&&sceneRenderer)Object.assign(sceneRenderer.rig,e.data.rig);
  if(inspecting&&e.data?.type==='scene-audio'){
    enable().then(()=>{active=true;isOwner=true;sceneDemo='audio';play({id:'test',kind:'narration',text:e.data.text,audio:e.data.url,
      gesture:['thanks','greeting','present'].includes(e.data.action)?e.data.action:null,emotion:e.data.action==='happy'?'happy':'talk'});});
  }
});
audio.onended = () => {completed = currentId;videoCharacter?.endSpeech().catch(error=>report(error.message));el('subtitle').classList.add('hidden'); el('stage').classList.remove('thank'); if(inspecting){active=false;sceneDemo='idle';}else tick();};
audio.onerror = () => {if(!currentId)return;failed = currentId; report('音频加载失败，请检查本地服务和语音设置');if(inspecting){stopAudio();active=false;}else tick();};
function report(message) {
  if (window.parent !== window) parent.postMessage({type:'player-error', message}, location.origin);
  else {el('output-note').textContent = message; el('output-note').hidden = false;}
}
function stopAudio() {
  playSerial++;actionPlayer.cancel();
  audio.pause(); audio.currentTime = 0;
  el('subtitle').classList.add('hidden'); el('stage').classList.remove('thank');
  currentId = ''; currentJob = null;
  videoCharacter?.reset().catch(()=>{});
}
async function play(job) {
  const serial=++playSerial;
  currentId = job.id; currentJob = job;
  if(videoCharacter){
    try{
      if(job.kind==='action'){
        await videoCharacter.gesture(job.action);
        if(serial===playSerial){completed=job.id;tick();}return;
      }
      await videoCharacter.beginSpeech(job.gesture||(job.kind==='gift'?'thanks':null),job.emotion||'talk');
    }catch(error){if(serial===playSerial){failed=job.id;report(error.message);tick();}return;}
  }
  if(job.clip){
    el('subtitle').classList.add('hidden');
    await actionPlayer.play(job.clip);
    if(serial!==playSerial)return;
  }
  if(job.kind==='action') {completed=job.id;tick();return;}
  if(serial!==playSerial)return;
  el('subtitle-label').textContent = job.kind === 'gift' ? '✦ 感谢支持 · ' + (job.username || '') : job.kind === 'comment' ? '回答 ' + (job.username || '观众') : '商品讲解';
  el('subtitle-text').textContent = job.text;
  el('subtitle').classList.remove('hidden');
  el('stage').classList.toggle('thank', job.kind === 'gift');
  audio.src = job.audio;
  try {await audio.play();}
  catch {
    // Autoplay policy requires a real click in some browsers / OBS.
    ready = false; el('enable-audio').hidden = false;
    el('enable-hint').textContent = '请点击启用，浏览器阻止了自动播放。';
    currentId = '';
    report('浏览器阻止了声音，请在预览或 OBS“交互”中点击启用播出声音');
  }
}
async function tick() {
  if (!ready || !sceneReady || tickBusy) return;
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
    // Keep heartbeats running while a silent action precedes the utterance.
    if (job && job.id !== currentId) void play(job);
  } catch {
    if (Date.now()-lastTick > 5000 && currentId) stopAudio();
  } finally { tickBusy = false; }
}
function visualLoop() {
  requestAnimationFrame(visualLoop);
  const action=actionPlayer.update();
  el('stage').dataset.actionPhase=action.phase;
  el('stage').dataset.actionMix=action.mix.toFixed(3);
  let rms = 0;
  if (analyser && !audio.paused && !audio.ended && isOwner && active) {
    analyser.getByteTimeDomainData(samples);
    rms = Math.sqrt(samples.reduce((sum,v) => sum + ((v-128)/128)**2, 0)/samples.length);
  }
  const openness = Math.min(1, rms*8);
  if(sceneRenderer&&sceneReady){
    const demo=inspecting&&sceneDemo==='speaking'?(Math.sin(performance.now()/110)*.5+.5)*.85:openness;
    sceneRenderer.draw(performance.now(),demo,action);
    el('scene-canvas').dataset.ready=String(sceneRenderer.ready);
    el('scene-canvas').dataset.fps=String(sceneRenderer.fps);
    el('scene-canvas').dataset.openness=String(sceneRenderer.open);
    if(inspecting&&sceneRenderer.diagnostics)el('scene-badge').textContent='场景预览 · '+sceneRenderer.diagnostics.fps+' FPS';
  }
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
    visualLoop();
    if (role === 'obs'&&!inspecting) await enable();
  } catch { report('无法连接工作台，请确认本地服务正在运行'); }
})();
