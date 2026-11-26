/* Cloud production workshop. OBS owns playback; the existing renderer stays isolated. */
let characterConfig,characterQuote,characterJob,characterJobs=[];
const characterLabels={idle:'自然待机',talk:'平静说话',thanks:'点头答谢',greeting:'微笑招手',present:'介绍手势',happy:'开心说话'};
const optionalCharacterKinds=new Set(['happy']);
const coreCharacterKinds=Object.keys(characterLabels).filter(kind=>!optionalCharacterKinds.has(kind));
const priceInputs={analysis_cny:'price-analysis',standard_image_cny:'price-image',video_std_cny_second:'price-std',video_pro_cny_second:'price-pro',retry_allowance:'price-retry'};
const characterStatuses={waiting:'等待',submitted:'已提交，禁止重复',unknown:'结果不明，需查账',pending:'云端排队',assembling:'本地整理中',running:'处理中',done:'已完成',failed:'失败',interrupted:'已暂停',review:'待验收',accepted:'已验收'};

function previewMessage(message){$('character-preview').contentWindow.postMessage(message,location.origin);}
function renderCharacterCards(){
  const active=state?.settings?.avatar;
  $('character-cards').innerHTML=characterJobs.length?characterJobs.map(card=>`<article class="character-card ${active?.mode==='character'&&active.character_id===card.id?'applied':''}"><button class="character-card-select" data-card-id="${esc(card.id)}"><img src="/media/characters/${card.id}/standard.png" alt="${esc(card.name)}"><strong>${esc(card.name)}</strong><small>${characterStatuses[card.status]||esc(card.status)}${active?.mode==='character'&&active.character_id===card.id?' · 当前应用':''}</small></button><button class="button secondary" data-card-apply="${esc(card.id)}">${card.accepted?'应用此角色':'预览与验收'}</button></article>`).join(''):'<p class="small-note">尚无角色卡。现有视频已准备好时，点击“使用现有视频创建角色卡”，或导入角色卡ZIP。</p>';
  document.querySelectorAll('[data-card-id]').forEach(button=>button.onclick=()=>selectCharacter(button.dataset.cardId).catch(error=>toast(error.message,true)));
  document.querySelectorAll('[data-card-apply]').forEach(button=>button.onclick=()=>busy(button,'载入中…',async()=>{
    await selectCharacter(button.dataset.cardApply);
    if(characterJob.accepted)await applyCharacter();else toast('请先检查预览与语音，再勾选确认并应用');
  }));
}
async function selectCharacter(id){
  $('character-select').value=id;renderCharacter(await api('/api/characters/'+id));
}
async function applyCharacter(){
  if(!characterJob)throw Error('请先选择角色卡');
  const reviewed=characterJob.accepted||$('character-reviewed').checked;
  if(!reviewed)throw Error('请先检查预览和语音，并勾选确认');
  characterJob=await send('/api/characters/'+characterJob.id,{background_visible:characterJob.background_visible!==false},'PATCH');
  if(!characterJob.accepted){
    renderCharacter(await send('/api/characters/'+characterJob.id+'/review',{accepted:true}));
  }
  previewMessage({type:'stop-preview'});
  await send('/api/characters/'+characterJob.id+'/activate',{});await refresh();
  $('active-scene').value='character:'+characterJob.id;renderCharacterCards();
  renderStudioActions();navigate('studio');
  toast('角色卡已应用，直播工作台已同步。开始彩排即可使用。');
}

async function refreshCharacterQuote(){
  characterQuote=await api('/api/characters/quote');
  $('character-quote').innerHTML=`<strong>单次制作约 ¥${characterQuote.total_cny.toFixed(2)}</strong> · 含视频重做预留约 ¥${characterQuote.with_retry_allowance_cny.toFixed(2)}<p>${esc(characterQuote.note)}</p>`+
    '<table><tbody>'+characterQuote.rows.map(r=>`<tr><td>${esc(r.label)}</td><td>${r.seconds?esc(r.seconds)+'秒 × ¥'+r.rate_cny+'/秒':'一次'}</td><td>¥${r.cost_cny.toFixed(2)}</td></tr>`).join('')+'</tbody></table>'+
    (characterQuote.missing.length?'<p class="scene-quality-warning">首次配置未完成：'+esc(characterQuote.missing.join('、'))+'</p>':'<p>基础动作已配置，可提交任务。情绪说话选填，缺少时使用平静说话。</p>');
  $('build-character').disabled=characterQuote.missing.length>0||characterJobs.some(j=>j.status==='running');
}
async function loadCharacterConfig(){
  characterConfig=await api('/api/characters/config');
  for(const section of ['vision','video']){
    $(section+'-url').value=characterConfig[section].base_url;$(section+'-model').value=characterConfig[section].model;
    $(section+'-key').value='';$(section+'-key-state').textContent=characterConfig[section].has_key?'已保存':'未配置';
    $(section+'-clear').checked=false;
  }
  $('video-mode').value=characterConfig.video.mode;
  $('obs-url').value=characterConfig.obs.url;$('obs-password').value='';
  $('pipeline-proxy-mode').value=characterConfig.vision.proxy_mode;$('pipeline-proxy-url').value=characterConfig.vision.proxy_url;
  for(const [key,id] of Object.entries(priceInputs))$(id).value=characterConfig.pricing[key];
  $('character-references').innerHTML=Object.entries(characterLabels).map(([kind,label])=>{
    const ref=characterConfig.video.references[kind]||{};
    return `<div class="reference-row"><strong>${esc(label)}${optionalCharacterKinds.has(kind)?'<small>选填 · 无视频使用平静说话</small>':''}</strong><input data-ref-url="${kind}" type="url" placeholder="${optionalCharacterKinds.has(kind)?'选填，不配置则使用平静说话':'公网MP4地址，或在右侧上传本地文件'}" value="${esc(ref.url||'')}"><input data-ref-duration="${kind}" type="number" min="2" max="8" step=".01" value="${ref.duration||3}" aria-label="${label}时长"><label class="button secondary">${ref.file?'已上传，替换':'上传MP4'}<input data-ref-file="${kind}" type="file" accept="video/mp4" hidden></label>${optionalCharacterKinds.has(kind)?`<button type="button" class="text-button" data-clear-ref="${kind}">不配置此情绪</button>`:''}</div>`;
  }).join('');
  document.querySelectorAll('[data-ref-file]').forEach(input=>input.onchange=async()=>{
    if(!input.files[0])return;
    const form=new FormData();form.append('file',input.files[0]);input.disabled=true;
    try{
      const result=await api('/api/characters/references/'+input.dataset.refFile,{method:'POST',body:form});
      characterConfig.video.references[input.dataset.refFile]=result.reference;
      document.querySelector(`[data-ref-duration="${input.dataset.refFile}"]`).value=result.reference.duration;
      input.parentElement.firstChild.textContent='已上传，替换';toast('参考表演已保存并读取实际时长');await refreshCharacterQuote();
    }catch(error){toast(error.message,true);}finally{input.disabled=false;input.value='';}
  });
  document.querySelectorAll('[data-clear-ref]').forEach(button=>button.onclick=()=>busy(button,'保存中…',async()=>{
    const refs={...characterConfig.video.references};delete refs[button.dataset.clearRef];
    await send('/api/characters/config',{video:{references:refs}},'PUT');
    await loadCharacterConfig();await refreshCharacterQuote();toast('情绪素材已取消，使用平静说话');
  }));
}
$('character-config').onsubmit=event=>{
  event.preventDefault();busy(event.submitter,'保存中…',async()=>{
    const config={};
    for(const section of ['vision','video'])config[section]={base_url:$(section+'-url').value.trim(),model:$(section+'-model').value.trim(),key:$(section+'-key').value.trim(),clear_key:$(section+'-clear').checked,
      proxy_mode:$('pipeline-proxy-mode').value,proxy_url:$('pipeline-proxy-url').value.trim()};
    config.video.mode=$('video-mode').value;config.video.references={...characterConfig.video.references};
    document.querySelectorAll('[data-ref-url]').forEach(input=>{
      if(input.value.trim())config.video.references[input.dataset.refUrl]={url:input.value.trim(),duration:Number(document.querySelector(`[data-ref-duration="${input.dataset.refUrl}"]`).value)};
    });
    config.pricing=Object.fromEntries(Object.entries(priceInputs).map(([key,id])=>[key,Number($(id).value)]));
    config.obs={url:$('obs-url').value.trim(),password:$('obs-password').value};
    await send('/api/characters/config',config,'PUT');await loadCharacterConfig();await refreshCharacterQuote();
    $('character-config-status').textContent='配置已保存，密钥不会回显。';toast('首次配置已保存');
  });
};
$('character-source').onchange=async()=>{
  const file=$('character-source').files[0];if(!file)return;
  try{const form=new FormData();form.append('file',file);await api('/api/avatar/upload',{method:'POST',body:form});toast('角色参考图已上传');}
  catch(error){toast(error.message,true);}
};
async function refreshCharacters(preferred){
  characterJobs=(await api('/api/characters')).jobs;
  const id=preferred||$('character-select').value;
  $('character-select').innerHTML=characterJobs.length?characterJobs.map(j=>`<option value="${esc(j.id)}">${esc(j.name)} · ${characterStatuses[j.status]||esc(j.status)}</option>`).join(''):'<option value="">尚无制作记录</option>';
  if(characterJobs.some(j=>j.id===id))$('character-select').value=id;
  await refreshCharacterQuote();
  const selected=$('character-product').value;
  const products=(await api('/api/state')).products.filter(p=>p.enabled);
  $('character-product').innerHTML=products.map(p=>`<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('');
  if(products.some(p=>p.id===selected))$('character-product').value=selected;
  renderCharacterCards();
}
function renderCharacter(job){
  if(characterJob?.id!==job.id)$('character-name').value=job.name;
  characterJob=job;
  previewMessage({type:'character-title',name:job.name});
  const costs=job.costs||{};
  $('character-progress').innerHTML=`<strong>${esc(job.name)} · ${characterStatuses[job.status]||esc(job.status)}</strong><p>已完成估算 ¥${Number(costs.estimated_completed_cny||0).toFixed(2)} · 待确认估算 ¥${Number(costs.uncertain_reserved_cny||0).toFixed(2)} · 预算 ¥${job.budget_cny}</p><p>${esc(costs.note||'')}</p>`+
    Object.entries(job.steps).filter(([kind])=>kind!=='thoughtful').map(([kind,step])=>`<div class="scene-step"><span>${esc(characterLabels[kind]||{analysis:'GPT角色分析',standard:'标准角色图'}[kind])}</span><span>${esc(characterStatuses[step.status]||step.status)} · ¥${step.estimated_cny.toFixed(2)}${step.task_id?' · 任务 '+esc(step.task_id):''}</span></div>`).join('')+
    (job.error?'<p class="scene-error">'+esc(job.error)+'</p>':'');
  $('character-analysis').textContent=job.analysis?'服装分析：'+job.analysis.clothing+'；运动约束：'+job.analysis.motion_constraints.join('；')+'；需检查：'+job.analysis.risks.join('；'):'';
  const current=Object.keys(job.assets||{}).join(',');
  if($('character-videos').dataset.signature!==job.id+current){
    $('character-videos').dataset.signature=job.id+current;
    $('character-videos').innerHTML=Object.entries(job.assets||{}).filter(([kind])=>characterLabels[kind]).map(([kind,asset])=>`<div><strong>${esc(characterLabels[kind])}</strong><video src="/media/characters/${job.id}/${esc(asset.file)}" controls muted playsinline preload="none" ${asset.loop?'loop':''}></video><small>${asset.duration.toFixed(2)}秒 · ${asset.width}×${asset.height}</small></div>`).join('')+
      Object.keys(characterLabels).filter(kind=>optionalCharacterKinds.has(kind)&&!job.assets?.[kind]).map(kind=>`<p class="small-note">${esc(characterLabels[kind])}未配置，使用平静说话。</p>`).join('');
  }
  $('character-reviewed').checked=job.accepted===true;
  $('accept-character').disabled=!['review','accepted'].includes(job.status);
  $('download-character').disabled=!coreCharacterKinds.every(kind=>job.assets?.[kind]);
  $('continue-character').disabled=['running','review','accepted'].includes(job.status);
  $('apply-character').disabled=!coreCharacterKinds.every(kind=>job.assets?.[kind]);
  const signature=job.id+Object.keys(job.assets||{}).join(',');
  if(job.assets?.idle && $('character-preview').dataset.signature!==signature){
    $('character-preview').dataset.signature=signature;
    $('character-preview').src='/stage?mode=inspect&character_id='+job.id;
    $('character-preview-status').textContent='正在载入 '+job.name+'…';
  }
}
$('create-existing-character').onclick=()=>busy($('create-existing-character'),'本地整理中…',async()=>{
  const job=await send('/api/characters/from-existing',{name:$('character-name').value.trim()||'我的极播主播'});
  renderCharacter(job);await refreshCharacters(job.id);toast('正在本地打包现有视频，不调用生成服务');
});
$('save-character-name').onclick=()=>busy($('save-character-name'),'保存中…',async()=>{
  if(!characterJob)throw Error('请先选择角色卡');
  renderCharacter(await send('/api/characters/'+characterJob.id,{name:$('character-name').value.trim()},'PATCH'));
  await refreshCharacters(characterJob.id);await refresh();toast('角色卡名称已保存');
});
$('apply-character').onclick=()=>busy($('apply-character'),'应用中…',applyCharacter);
$('character-select').onchange=()=>selectCharacter($('character-select').value).catch(error=>toast(error.message,true));
$('character-preview-actions').innerHTML=Object.entries(characterLabels).map(([kind,label])=>`<button class="button secondary" data-preview-kind="${kind}">${label}</button>`).join('');
document.querySelectorAll('[data-preview-kind]').forEach(button=>button.onclick=()=>previewMessage({type:'scene-action',action:button.dataset.previewKind}));
$('character-preview-background').onclick=()=>{
  if(!characterJob)return;
  characterJob.background_visible=characterJob.background_visible===false;
  previewMessage({type:'scene-background'});
};
$('stop-character-preview').onclick=()=>previewMessage({type:'stop-preview'});
window.addEventListener('message',event=>{
  if(event.origin!==location.origin||event.source!==$('character-preview').contentWindow)return;
  if(event.data?.type==='player-error'){$('character-preview-status').textContent=event.data.message;toast(event.data.message,true);}
  if(event.data?.type==='character-preview-state')$('character-preview-status').textContent=(characterJob?.name||'角色')+' · '+(characterLabels[event.data.kind]||event.data.kind)+(event.data.fallback?'（使用平静说话）':'');
});
$('refresh-character-quote').onclick=()=>busy($('refresh-character-quote'),'刷新中…',refreshCharacterQuote);
$('build-character').onclick=()=>busy($('build-character'),'提交中…',async()=>{
  await refreshCharacterQuote();
  if(characterQuote.missing.length)throw Error('请先完成服务和参考表演配置');
  if(!confirm(`预计单次 ¥${characterQuote.total_cny.toFixed(2)}，含重做预留预算 ¥${characterQuote.with_retry_allowance_cny.toFixed(2)}。将上传角色图和表演素材到云服务。不自动重试收费请求。确认生成？`))return;
  const job=await send('/api/characters/build',{name:$('character-name').value.trim(),quote_fingerprint:characterQuote.fingerprint,
    budget_cny:characterQuote.with_retry_allowance_cny,confirmed:true});
  renderCharacter(job);await refreshCharacters(job.id);toast('角色制作已开始，逐步保存任务编号和费用记录');
});
$('load-character').onclick=()=>busy($('load-character'),'载入中…',async()=>{if(!$('character-select').value)throw Error('尚无角色');renderCharacter(await api('/api/characters/'+$('character-select').value));});
$('continue-character').onclick=()=>busy($('continue-character'),'查询中…',async()=>{renderCharacter(await send('/api/characters/'+characterJob.id+'/continue',{}));toast('已继续，已有任务只查询原编号');});
$('accept-character').onclick=()=>busy($('accept-character'),'保存中…',async()=>{
  if(!$('character-reviewed').checked)throw Error('请先检查素材并勾选验收确认');
  renderCharacter(await send('/api/characters/'+characterJob.id+'/review',{accepted:true}));toast('角色已确认验收，可用于OBS测试');
});
$('download-character').onclick=()=>{
  if(!characterJob)return;const a=document.createElement('a');a.href='/api/characters/'+characterJob.id+'/package';a.download='极播角色.zip';a.click();
};
$('import-character').onchange=async event=>{
  const file=event.target.files[0];if(!file)return;
  if(file.size>300_000_000){toast('角色包不能超过300MB',true);return;}
  event.target.disabled=true;
  try{const form=new FormData();form.append('file',file);const job=await api('/api/characters/import',{method:'POST',body:form});
    renderCharacter(job);await refreshCharacters(job.id);toast('角色已导入，请在本机重新验收，不产生生成费用');
  }catch(error){toast(error.message,true);}finally{event.target.disabled=false;event.target.value='';}
};
$('connect-character-obs').onclick=()=>busy($('connect-character-obs'),'连接中…',async()=>{
  if(!desktop?.obsConnect)throw Error('请使用极播桌面客户端连接本机OBS');
  const result=await desktop.obsConnect();$('character-obs-status').textContent='已连接OBS '+result.version;
});
$('setup-character-obs').onclick=()=>busy($('setup-character-obs'),'配置中…',async()=>{
  if(!characterJob?.accepted)throw Error('请先完成角色验收');
  if(!desktop?.obsSetup)throw Error('请使用桌面客户端');
  await desktop.obsSetup(characterJob.id);await desktop.obsPresent('idle');
  $('character-obs-status').textContent='已建立极播专用场景，未启动平台推流。点击下方按钮检查切换。';
});
$('character-obs-actions').innerHTML=Object.entries(characterLabels).map(([kind,label])=>`<button class="button secondary" data-obs-kind="${kind}">${label}</button>`).join('');
document.querySelectorAll('[data-obs-kind]').forEach(button=>button.onclick=()=>busy(button,'切换中…',async()=>{
  if(!desktop?.obsPresent)throw Error('请使用桌面客户端');
  const result=await desktop.obsPresent(button.dataset.obsKind);if(result.fallback)toast('未配置该情绪视频，已使用平静说话');
}));
let characterTestAudio;
const characterRehearsal=desktop?.obsSpeaking?new ObsRehearsal({request:send,desktop,audio:new Audio(),
  onStatus:text=>$('character-obs-status').textContent=text}):null;
$('start-character-rehearsal').onclick=()=>busy($('start-character-rehearsal'),'准备彩排…',async()=>{
  if(!characterRehearsal)throw Error('请使用极播桌面客户端');
  if(!characterJob?.accepted)throw Error('请先完成当前角色验收');
  if(!$('character-product').value)throw Error('请先添加启用的商品，再刷新制作记录');
  characterTestAudio?.pause();characterRehearsal.assets=characterJob.assets;
  await characterRehearsal.start(characterJob.id,$('character-product').value);
  toast('互动彩排已开始，可到直播工作台发送弹幕或礼物测试');
});
$('stop-character-rehearsal').onclick=()=>busy($('stop-character-rehearsal'),'停止中…',async()=>{
  await characterRehearsal?.stop();await send('/api/studio/stop',{});toast('彩排已停止');
});
$('test-character-voice').onclick=()=>busy($('test-character-voice'),'生成测试配音…',async()=>{
  if(!characterJob?.assets?.talk)throw Error('请先创建或载入包含平静说话视频的角色卡');
  if(characterRehearsal?.active)throw Error('请先停止互动彩排，再单独测试配音');
  const result=await send('/api/scenes/test-voice',{text:$('character-test-text').value.trim()});
  previewMessage({type:'scene-audio',url:result.audio,text:result.text,action:$('character-test-action').value});
});
window.addEventListener('studio-event',event=>{
  const m=event.detail;
  if(m.type==='runtime' && characterRehearsal?.active && (!m.data.active||m.data.character_id!==characterRehearsal.characterId))
    characterRehearsal.stop().catch(error=>toast(error.message,true));
  if(m.type==='settings'){renderCharacterCards();return;}
  if(m.type!=='character_job')return;
  if(characterJob?.id===m.data.id||!characterJob)renderCharacter(m.data);
  const known=characterJobs.some(j=>j.id===m.data.id);
  characterJobs=[m.data,...characterJobs.filter(j=>j.id!==m.data.id)];renderCharacterCards();
  if(!known||['review','interrupted'].includes(m.data.status))refreshCharacters(m.data.id).catch(error=>toast(error.message,true));
});
(async()=>{try{await loadCharacterConfig();await refreshCharacters();if($('character-select').value)renderCharacter(await api('/api/characters/'+$('character-select').value));}catch(error){toast(error.message,true);}})();

$('open-character-config').onclick=()=>{const panel=$('character-config-panel');panel.open=true;panel.scrollIntoView({behavior:'smooth',block:'start'});};
