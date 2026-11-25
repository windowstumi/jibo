const el = id => document.getElementById(id);
const sceneParams = new URLSearchParams(location.search);
const inspecting = sceneParams.get('mode') === 'inspect';
let sceneRenderer=null,sceneDemo='idle',sceneLoadVersion=0,sceneLoading=Promise.resolve(),sceneReady=false;
const role = new URLSearchParams(location.search).get('mode') === 'obs' ? 'obs' : 'preview';
if(new URLSearchParams(location.search).get('desktop')==='1') {
  el('desktop-stage-bar').hidden=false;
  el('close-stage').onclick=()=>window.close();
}
document.body.classList.toggle('obs', role === 'obs');
const clientId = crypto.randomUUID();
const audio = new Audio();
audio.preload = 'auto';
let ctx, analyser, samples, ready = false, active = false, isOwner = false, currentId = '', completed = '', failed = '', avatar, lastTick = 0, tickBusy = false, currentJob = null, tickTimer;

function configure(a) {
  avatar = a; el('portrait').src = a.image;
  const id=inspecting?sceneParams.get('scene_id'):a.scene_id;
  const version=++sceneLoadVersion;
  sceneLoading=sceneLoading.then(async()=>{
    if(version!==sceneLoadVersion)return;
    sceneReady=false;
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
  if (e.data?.type === 'activate-audio') enable();
  if(inspecting&&e.data?.type==='scene-action')sceneDemo=e.data.action;
  if(inspecting&&e.data?.type==='scene-background'&&sceneRenderer)sceneRenderer.transparent=!sceneRenderer.transparent;
  if(inspecting&&e.data?.type==='scene-rig'&&sceneRenderer)Object.assign(sceneRenderer.rig,e.data.rig);
  if(inspecting&&e.data?.type==='scene-audio'){
    enable().then(()=>{active=true;isOwner=true;sceneDemo='audio';play({id:'test',kind:'narration',text:e.data.text,audio:e.data.url});});
  }
});
audio.onended = () => {completed = currentId; el('subtitle').classList.add('hidden'); el('stage').classList.remove('thank'); if(inspecting){active=false;sceneDemo='idle';}else tick();};
audio.onerror = () => {failed = currentId; report('音频加载失败，请检查本地服务和语音设置'); tick();};
function report(message) {
  if (window.parent !== window) parent.postMessage({type:'player-error', message}, location.origin);
  else {el('output-note').textContent = message; el('output-note').hidden = false;}
}
function stopAudio() {
  audio.pause(); audio.currentTime = 0;
  el('subtitle').classList.add('hidden'); el('stage').classList.remove('thank');
  currentId = ''; currentJob = null;
}
async function play(job) {
  currentId = job.id; currentJob = job;
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
    if (job && job.id !== currentId) await play(job);
  } catch {
    if (Date.now()-lastTick > 5000 && currentId) stopAudio();
  } finally { tickBusy = false; }
}
function visualLoop() {
  requestAnimationFrame(visualLoop);
  let rms = 0;
  if (analyser && !audio.paused && !audio.ended && isOwner && active) {
    analyser.getByteTimeDomainData(samples);
    rms = Math.sqrt(samples.reduce((sum,v) => sum + ((v-128)/128)**2, 0)/samples.length);
  }
  const openness = Math.min(1, rms*8);
  if(sceneRenderer&&sceneReady){
    const demo=inspecting&&sceneDemo==='speaking'?(Math.sin(performance.now()/110)*.5+.5)*.85:openness;
    sceneRenderer.draw(performance.now(),demo,inspecting?sceneDemo:currentJob?.kind||'idle');
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
    visualLoop();
    if (role === 'obs'&&!inspecting) await enable();
  } catch { report('无法连接工作台，请确认本地服务正在运行'); }
})();
