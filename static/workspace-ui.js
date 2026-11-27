/* Workspace navigation and readiness; native controls reuse the existing API forms. */
let settingsGroup='voice';
const settingGroups=new Set(['voice','brain','image','generation','output','data']);
function selectSettingsGroup(group){
  if(!settingGroups.has(group))group='voice';
  settingsGroup=group;
  document.querySelectorAll('[data-settings-panel]').forEach(panel=>panel.hidden=panel.dataset.settingsPanel!==group);
  document.querySelectorAll('[data-settings-tab]').forEach(tab=>{
    const selected=tab.dataset.settingsTab===group;
    tab.setAttribute('aria-selected',String(selected));tab.tabIndex=selected?0:-1;
    tab.id='settings-tab-'+tab.dataset.settingsTab;
  });
  document.getElementById('settings-pane').setAttribute('aria-labelledby','settings-tab-'+group);
  document.getElementById('settings-form').hidden=!['voice','brain','image'].includes(group);
  document.getElementById('character-config').hidden=!['generation','output'].includes(group);
}
function workspaceRoute(view,focus){
  navigate(view);
  if(view==='settings')selectSettingsGroup(focus||settingsGroup);
  if(view==='characters'&&focus==='materials')document.getElementById('character-local-materials').open=true;
  if(view==='characters'&&focus==='generation')document.getElementById('character-generation').open=true;
  const target=focus==='voice-test'?'character-test-text':focus==='materials'?'character-local-materials':focus==='generation'&&view==='characters'?'character-generation':null;
  if(target)document.getElementById(target).scrollIntoView({block:'center',behavior:'smooth'});
}
document.addEventListener('click',event=>{
  const tab=event.target.closest('[data-settings-tab]');
  if(tab){selectSettingsGroup(tab.dataset.settingsTab);return;}
  const route=event.target.closest('[data-route]');
  if(route)workspaceRoute(route.dataset.route,route.dataset.focus);
});
document.querySelector('.brand').onclick=event=>{event.preventDefault();workspaceRoute('home');};
document.addEventListener('invalid',event=>{
  const panel=event.target.closest('[data-settings-panel]');
  if(panel?.hidden)selectSettingsGroup(panel.dataset.settingsPanel);
},true);
document.querySelector('.settings-nav').addEventListener('keydown',event=>{
  if(!['ArrowDown','ArrowUp','ArrowLeft','ArrowRight','Home','End'].includes(event.key))return;
  const tabs=[...document.querySelectorAll('[data-settings-tab]')],index=tabs.indexOf(event.target);
  if(index<0)return;
  event.preventDefault();
  const next=event.key==='Home'?0:event.key==='End'?tabs.length-1:(index+(['ArrowDown','ArrowRight'].includes(event.key)?1:tabs.length-1))%tabs.length;
  selectSettingsGroup(tabs[next].dataset.settingsTab);tabs[next].focus();
});
selectSettingsGroup('voice');
function readiness(snapshot,localStatus){
  const cfg=snapshot.settings,card=(snapshot.character_cards||[]).find(item=>item.id===cfg.avatar?.character_id&&cfg.avatar.mode==='character');
  const roleReady=!!card?.accepted;
  const provider=cfg.tts.provider;
  const voiceReady=provider==='windows'?snapshot.platform==='win32'&&!!cfg.tts.voice:
    provider==='local'?localStatus?.phase==='ready'&&localStatus.loaded_voice===cfg.local_tts.voice_id:
    !!cfg.tts.base_url&&!!cfg.tts.model;
  let voiceNote=provider==='windows'?'已选系统配音，进入预览试听':provider==='compatible'?'已填写接口，进入预览试听':'请安装组件、导入音色并加载';
  if(provider==='local'&&localStatus)voiceNote=localStatus.error||localStatus.message;
  const realProducts=snapshot.products.filter(p=>p.enabled&&p.id!=='sample-cup');
  const rulesEnabled=snapshot.rules.filter(rule=>rule.enabled).length;
  return [
    {title:'准备你的角色',description:roleReady?'当前角色：'+card.name:card?'角色已导入，预览后确认并应用':'导入角色卡最快；也可使用图片与视频制作。',ready:roleReady,action:roleReady?'查看角色':'准备角色',view:'characters'},
    {title:'让角色开口',description:voiceNote,ready:voiceReady,action:voiceReady?'试听声音':'配置声音',view:voiceReady?'characters':'settings',focus:voiceReady?'voice-test':'voice'},
    {title:'添加商品资料',description:realProducts.length?realProducts.length+' 个启用商品，检查参数与讲解稿':'当前仅有示例或未启用商品，请添加真实资料。',ready:realProducts.length>0,action:'管理商品',view:'knowledge'},
    {title:'设定互动范围',description:rulesEnabled+' 条屏蔽规则生效 · '+(cfg.interaction?.allow_chat?'允许云端聊天':'商品问答与基础招呼'),ready:rulesEnabled>0,action:'检查守则',view:'rules'}
  ];
}
function renderWorkspace(localStatus){
  if(typeof state==='undefined'||!state)return;
  const current=localStatus||(typeof localSpeechStatus==='undefined'?null:localSpeechStatus);
  const steps=readiness(state,current),count=steps.filter(step=>step.ready).length;
  const signature=JSON.stringify([steps,state.settings.avatar,state.settings.tts.provider,state.settings.llm.model,state.settings.llm.has_key]);
  if(document.getElementById('setup-steps').dataset.signature===signature)return;
  document.getElementById('setup-steps').dataset.signature=signature;
  document.getElementById('setup-steps').innerHTML=steps.map((step,index)=>`<button class="setup-step ${step.ready?'complete':''}" data-route="${step.view}" ${step.focus?'data-focus="'+step.focus+'"':''}><div class="step-top"><span class="step-number">0${index+1}</span><span class="step-status">${step.ready?'已配置':'待准备'}</span></div><h3>${esc(step.title)}</h3><p>${esc(step.description)}</p><span class="step-action">${step.action} <span>↗</span></span></button>`).join('');
  document.getElementById('home-prepared').textContent=count+' / 4 已配置';
  document.getElementById('home-progress-label').textContent=count===4?'准备配置已齐全 · 下一步进行实际彩排':count+' 项已配置 · 继续完成准备';
  const next=steps.find(step=>!step.ready);
  document.getElementById('home-next-title').textContent=next?next.title:'进入工作台，开始一次彩排。';
  document.getElementById('home-next-description').textContent=next?next.description:'先发送一条测试弹幕，检查声音、字幕和动作，再连接直播软件。';
  const button=document.getElementById('home-next');button.textContent=next?next.action+' →':'进入直播工作台 →';
  button.dataset.route=next?.view||'studio';button.dataset.focus=next?.focus||'';
  const cfg=state.settings;
  document.getElementById('home-summary').innerHTML=[['当前角色',cfg.avatar.mode==='character'?cfg.avatar.name:'尚未应用角色'],['语音方式',({windows:'Windows 系统配音',local:'本地克隆音色',compatible:'兼容语音接口'})[cfg.tts.provider]],['商品资料',state.products.filter(p=>p.enabled&&p.id!=='sample-cup').length+' 个真实启用商品'],['AI 问答',cfg.llm.has_key?cfg.llm.model:'知识库摘录直答']].map(([label,value])=>`<div><span>${esc(label)}</span><strong>${esc(value)}</strong></div>`).join('');
}
window.addEventListener('studio-event',event=>{if(event.detail.type==='local-tts')renderWorkspace(event.detail.data);});
if(typeof module==='object')module.exports={readiness};
