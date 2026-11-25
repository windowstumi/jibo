/* Workbench for reviewing generated models before they are used on air. */
let selectedScene=null,sceneModel=null,lastSceneJobs=[];
const rigLabels={head_x:'头部水平位置',head_y:'头部中心高度',neck_y:'颈部高度',eye_y:'眼睛高度',mouth_y:'嘴部高度',face_width:'面部宽度',waist_y:'腰部高度',skirt_y:'裙摆起点',skirt_end:'裙摆末端',wind:'风动强度',breath:'呼吸强度',motion:'头部动作',background_motion:'背景变化',particles:'背景粒子'};
function sceneMessage(message){$('scene-preview').contentWindow.postMessage(message,location.origin);}
function renderSceneJobs(jobs){
  lastSceneJobs=jobs;const current=$('scene-select').value||selectedScene;
  $('scene-select').innerHTML=jobs.length?jobs.map(j=>`<option value="${esc(j.id)}">${new Date(j.created*1000).toLocaleString('zh-CN')} · ${{pending:'准备',running:'生成中',review:'待验收',accepted:'已启用',failed:'失败',interrupted:'中断'}[j.status]||j.status}</option>`).join(''):'<option value="">尚无场景</option>';
  if(jobs.some(j=>j.id===current))$('scene-select').value=current;
  renderSceneProgress(jobs.find(j=>j.id===$('scene-select').value));
}
function renderSceneProgress(job){
  if(!job)return;
  const names={neutral:'标准正面角色',speaking:'说话表情',blink:'闭眼表情',background:'独立背景'};
  $('scene-progress').innerHTML=Object.entries(job.steps).map(([k,v])=>`<div class="scene-step"><span>${names[k]}</span><span>${{pending:'等待',submitted:'已提交，等待图片服务',done:'已保存'}[v.status]||v.status}</span></div>`).join('')+(job.error?'<div class="scene-error">'+esc(job.error)+'</div>':'');
  $('build-scene').disabled=lastSceneJobs.some(j=>j.status==='running'||j.status==='pending');
}
async function loadScene(id){
  if(!id)return toast('请先选择一个场景',true);
  const data=await api('/api/scenes/'+id);selectedScene=id;renderSceneProgress(data.job);
  if(!data.model){$('scene-quality').textContent='生成尚未完成。已提交任务不会自动重试。';return;}
  sceneModel=data.model;
  loadClothEditor(data.model,data.base_url);
  $('scene-preview').src='/stage?mode=inspect&scene_id='+encodeURIComponent(id);
  const warnings=data.model.quality.warnings||[];
  $('scene-quality').innerHTML='<span class="scene-label-ok">✓ 角色已抠图 · 3张表情贴图 · 2240个网格三角形 · 独立背景</span>'+warnings.map(w=>'<p class="scene-quality-warning">'+esc(w)+'</p>').join('')+'<p>请检查角色身份、头部／口型对齐、头发边缘和裙摆，确认后再用于直播。</p>';
  $('scene-rig-fields').innerHTML=Object.entries(rigLabels).map(([key,label])=>`<div class="rig-control"><label for="rig-${key}">${label}<output id="rig-value-${key}">${sceneModel.rig[key].toFixed(3)}</output></label><input id="rig-${key}" type="range" min="${key==='face_width'?.03:0}" max="1" step=".002" value="${sceneModel.rig[key]}"></div>`).join('');
  Object.keys(rigLabels).forEach(key=>$('rig-'+key).oninput=()=>{sceneModel.rig[key]=Number($('rig-'+key).value);$('rig-value-'+key).textContent=sceneModel.rig[key].toFixed(3);sceneMessage({type:'scene-rig',rig:sceneModel.rig});});
}
$('build-scene').onclick=()=>{
  if(!confirm('将调用4次图片生成服务，产生相应费用。不自动重试失败请求。继续生成？'))return;
  busy($('build-scene'),'提交中…',async()=>{const job=await send('/api/scenes/build',{description:$('scene-description').value});selectedScene=job.id;renderSceneJobs([job,...lastSceneJobs]);toast('生成已开始，请保持客户端打开。');});
};
$('load-scene').onclick=()=>busy($('load-scene'),'载入中…',()=>loadScene($('scene-select').value));
$('scene-select').onchange=()=>{selectedScene=$('scene-select').value;renderSceneProgress(lastSceneJobs.find(j=>j.id===selectedScene));};
$('compile-scene').onclick=()=>busy($('compile-scene'),'绑定中…',async()=>{if(!$('scene-select').value)throw Error('请先选择场景');await send('/api/scenes/'+$('scene-select').value+'/compile',{});await loadScene($('scene-select').value);toast('已使用保存的图片重新绑定，未调用图片服务');});
$('activate-scene').onclick=()=>busy($('activate-scene'),'启用中…',async()=>{
  if(!selectedScene||!sceneModel||sceneModel.id!==$('scene-select').value)throw Error('请先载入并检查所选场景');
  await send('/api/scenes/'+selectedScene+'/activate',{});await refresh();renderAvatar();toast('已启用场景模型，可到直播工作台开始彩排');
});
$('save-scene-rig').onclick=()=>busy($('save-scene-rig'),'保存中…',async()=>{
  if(!selectedScene||!sceneModel)throw Error('请先载入场景');
  const rig={};Object.keys(rigLabels).forEach(k=>rig[k]=sceneModel.rig[k]);
  await send('/api/scenes/'+selectedScene+'/rig',rig,'PUT');toast('自动绑定参数已更新');
});
document.querySelectorAll('[data-scene-action]').forEach(b=>b.onclick=()=>sceneMessage({type:'scene-action',action:b.dataset.sceneAction}));
$('scene-transparent').onclick=()=>sceneMessage({type:'scene-background'});
$('scene-voice-test').onclick=()=>busy($('scene-voice-test'),'生成配音…',async()=>{
  if(!sceneModel)throw Error('请先载入场景');
  const result=await send('/api/scenes/test-voice',{});sceneMessage({type:'scene-audio',url:result.audio,text:result.text});
});
const sceneStream=new EventSource('/api/stream');
sceneStream.onmessage=e=>{const m=JSON.parse(e.data);if(m.type==='scene_job'){const jobs=[m.data,...lastSceneJobs.filter(j=>j.id!==m.data.id)].sort((a,b)=>b.created-a.created);renderSceneJobs(jobs);if(m.data.status==='review'&&m.data.id===selectedScene)loadScene(selectedScene).catch(err=>toast(err.message,true));}};
api('/api/state').then(data=>{renderSceneJobs(data.scene_jobs||[]);const active=data.settings.avatar.scene_id||(data.scene_jobs||[]).find(j=>j.status==='review'||j.status==='accepted')?.id;if(active){selectedScene=active;$('scene-select').value=active;loadScene(active).catch(err=>toast(err.message,true));}}).catch(()=>{});

let clothPoints=[],dragPoint=-1;
const clothCanvas=$('cloth-canvas'),clothImage=$('cloth-source');
function loadClothEditor(model,base){
  clothPoints=structuredClone(model.cloth.polygon);
  clothImage.onload=drawCloth;
  clothImage.src=base+model.textures.neutral+'?v='+model.revision;
}
function drawCloth(){
  if(!clothImage.naturalWidth)return;
  clothCanvas.width=clothImage.naturalWidth;clothCanvas.height=clothImage.naturalHeight;
  const ctx=clothCanvas.getContext('2d'),w=clothCanvas.width,h=clothCanvas.height;
  ctx.clearRect(0,0,w,h);ctx.beginPath();
  clothPoints.forEach(([x,y],i)=>i?ctx.lineTo(x*w,y*h):ctx.moveTo(x*w,y*h));ctx.closePath();
  ctx.fillStyle='rgba(67,153,129,.23)';ctx.fill();ctx.strokeStyle='#3b9279';ctx.lineWidth=3;ctx.stroke();
  for(const [x,y] of clothPoints){ctx.beginPath();ctx.arc(x*w,y*h,7,0,Math.PI*2);ctx.fillStyle='#fff';ctx.fill();ctx.stroke();}
}
function clothPosition(e){const r=clothCanvas.getBoundingClientRect();return [Math.max(0,Math.min(1,(e.clientX-r.left)/r.width)),Math.max(0,Math.min(1,(e.clientY-r.top)/r.height))];}
clothCanvas.onpointerdown=e=>{
  const point=clothPosition(e),r=clothCanvas.getBoundingClientRect();let distance=Infinity;
  clothPoints.forEach((p,i)=>{const d=Math.hypot((p[0]-point[0])*r.width,(p[1]-point[1])*r.height);if(d<distance){distance=d;dragPoint=i;}});
  if(distance>22){dragPoint=-1;return;}
  clothCanvas.setPointerCapture(e.pointerId);
};
clothCanvas.onpointermove=e=>{if(dragPoint<0)return;clothPoints[dragPoint]=clothPosition(e);drawCloth();};
clothCanvas.onpointerup=()=>dragPoint=-1;clothCanvas.onpointercancel=()=>dragPoint=-1;
$('save-cloth').onclick=()=>busy($('save-cloth'),'保存中…',async()=>{
  if(!selectedScene||!sceneModel)throw Error('请先载入场景');
  await send('/api/scenes/'+selectedScene+'/cloth',{polygon:clothPoints},'PUT');
  await loadScene(selectedScene);toast('已更新衣料范围；范围外的腿和手不再参与布料变形');
});
