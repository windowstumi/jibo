const $ = (id) => document.getElementById(id);
const desktop = window.yingboDesktop;
let state, eventKind = 'comment', rules = [], editingId = null;
const esc = (s) => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const statuses = {pending:'等待处理',processing:'处理中',ready:'等待播出',speaking:'正在播出',done:'已播出',skipped:'已跳过',error:'处理失败'};

function toast(message, error = false) {
  $('toast').textContent = message;
  $('toast').className = 'show' + (error ? ' error' : '');
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => $('toast').className = '', error ? 6500 : 3500);
}
async function api(path, options = {}) {
  const headers = options.body instanceof FormData ? {} : {'Content-Type':'application/json'};
  const response = await fetch(path, {headers, ...options});
  let data;
  try { data = await response.json(); } catch { throw new Error('服务返回异常，请检查本地工作台是否运行'); }
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : '内容格式不正确，请检查输入');
  return data;
}
function send(path, body, method = 'POST') { return api(path, {method, body:JSON.stringify(body)}); }
async function busy(button, label, fn) {
  if (button.disabled) return;
  const original = button.textContent;
  button.disabled = true; button.textContent = label;
  try { return await fn(); } catch(e) { toast(e.message, true); }
  finally { button.disabled = false; button.textContent = original; }
}
function navigate(view) {
  document.querySelectorAll('.view').forEach(e => e.classList.toggle('active', e.id === 'view-' + view));
  document.querySelectorAll('.nav-item').forEach(e => e.classList.toggle('active', e.dataset.view === view));
  $('page-name').textContent = document.querySelector(`[data-view="${view}"]`).textContent.trim().slice(1).trim();

  history.replaceState(null, '', '#' + view);
}
document.querySelectorAll('[data-view]').forEach(e => e.onclick = () => navigate(e.dataset.view));
document.querySelectorAll('[data-goto]').forEach(e => e.onclick = () => navigate(e.dataset.goto));

function renderProducts() {
  const selected = $('active-product').value || state.runtime.product_id;
  const enabled = state.products.filter(p => p.enabled);
  $('active-product').innerHTML = enabled.length ? enabled.map(p => `<option value="${esc(p.id)}">${esc(p.name)}</option>`).join('') : '<option value="">请先添加并启用商品</option>';
  if (enabled.some(p => p.id === selected)) $('active-product').value = selected;
  $('product-list').innerHTML = state.products.length ? state.products.map(p => `<button class="product-item${p.id === editingId ? ' selected' : ''}" data-product="${esc(p.id)}">${esc(p.name)}<small>${esc(p.price || '未填写价格')} · ${p.enabled ? '已启用' : '已停用'}</small></button>`).join('') : '<div class="empty">还没有商品</div>';
  $('product-count').textContent = state.products.length;
  $('product-list').querySelectorAll('[data-product]').forEach(e => e.onclick = () => editProduct(e.dataset.product));
}
function editProduct(id) {
  editingId = id;
  const p = state.products.find(p => p.id === id) || {id:'', name:'',price:'',description:'',faq:'',script:'',enabled:true};
  ['id','name','price','description','faq','script'].forEach(f => $('product-' + f).value = p[f]);
  $('product-enabled').checked = p.enabled;
  $('product-editor-title').textContent = p.id ? '编辑商品' : '新建商品';
  $('delete-product').hidden = !p.id;
  renderProducts();
}
function productForm() {
  const p = {enabled:$('product-enabled').checked};
  ['name','price','description','faq','script'].forEach(f => p[f] = $('product-' + f).value.trim());
  if ($('product-id').value) p.id = $('product-id').value;
  return p;
}
function renderEvents(events) {
  $('event-count').textContent = events.length + ' 条';
  $('events-body').innerHTML = events.length ? events.map(e => `<tr><td>${esc(e.username)}<small>${new Date(e.created*1000).toLocaleTimeString('zh-CN',{hour12:false})} · ${e.kind === 'gift' ? '礼物' : '弹幕'}</small></td><td>${esc(e.content)}</td><td><span class="event-status ${esc(e.status)}">${statuses[e.status] || esc(e.status)}</span></td><td>${esc(e.reply || e.reason || '等待处理')} ${e.reply && e.reason ? '<small>' + esc(e.reason) + '</small>' : ''}${e.sources?.length ? '<small>依据：' + esc(e.sources.join('、')) + '</small>' : ''}</td></tr>`).join('') : '<tr><td colspan="4" class="empty">还没有互动记录。发送一条测试弹幕，看看主播如何回应。</td></tr>';
}
function renderRuntime(runtime) {
  state.runtime = runtime;
  $('studio-status').textContent = runtime.active ? '彩排进行中' : '准备就绪';
  $('studio-detail').textContent = runtime.current ? (runtime.current.kind === 'gift' ? '正在答谢礼物' : runtime.current.kind === 'comment' ? '正在回答商品问题' : '正在讲解商品') : runtime.active ? '等待音频播放器连接' : '先选择商品，开始本地彩排';
  $('queue-badge').textContent = runtime.queue_length + ' 条待播';
}
function renderRules() {
  $('rule-count').textContent = rules.filter(r => r.enabled).length + ' 条生效';
  $('rules-list').innerHTML = rules.map(r => `<div class="rule-row"><input type="checkbox" data-rule-toggle="${esc(r.id)}" ${r.enabled ? 'checked' : ''} aria-label="启用 ${esc(r.pattern)}"><span class="rule-text">${esc(r.pattern)}</span><span class="tag">${esc(r.category)}</span><button class="remove-rule" data-rule-remove="${esc(r.id)}" aria-label="删除 ${esc(r.pattern)}">×</button></div>`).join('') || '<div class="empty">没有屏蔽词，添加后保存即可生效。</div>';
  $('rules-list').querySelectorAll('[data-rule-toggle]').forEach(e => e.onchange = () => {rules.find(r => r.id === e.dataset.ruleToggle).enabled = e.checked; $('rule-count').textContent = rules.filter(r => r.enabled).length + ' 条生效';});
  $('rules-list').querySelectorAll('[data-rule-remove]').forEach(e => e.onclick = () => {rules = rules.filter(r => r.id !== e.dataset.ruleRemove); renderRules();});
}
function renderAvatar() {
  const a = state.settings.avatar;
  $('avatar-name').textContent = a.name;
  $('avatar-image').src = a.original || a.image;
}
function renderStudioScenes() {
  const current=state.settings.avatar.scene_id;
  const selected=$('active-scene').value || current;
  const scenes=(state.scene_jobs||[]).filter(j=>['review','accepted'].includes(j.status));
  $('active-scene').innerHTML=scenes.length?scenes.map(j=>`<option value="${esc(j.id)}">${new Date(j.created*1000).toLocaleString('zh-CN')} · ${j.id===current?'当前模型':'可用场景'}</option>`).join(''):'<option value="">请先到形象工坊生成场景模型</option>';
  if(scenes.some(j=>j.id===selected))$('active-scene').value=selected;
  $('active-scene-hint').textContent=scenes.length?'开始彩排将使用所选场景的完整面部表情。':'未生成场景时不能开播，不使用静态图片嘴型替代。';
}
function renderSettings() {
  const s = state.settings;
  for (const section of ['llm','image','tts']) {
    const c = s[section];
    $(section + '-url').value = c.base_url;
    $(section + '-model').value = c.model;
    $(section + '-key').value = '';
    $(section + '-clear').checked = false;
    $(section + '-key-state').textContent = c.has_key ? '· 已保存' : '· 未配置';
  }
  $('tts-provider').value = s.tts.provider;
  $('tts-voice').value = s.tts.voice;
  $('tts-rate').value = s.tts.rate;
  $('event-url').value = location.origin + '/api/events';
  $('event-token').value = s.event_token;
  $('gift-template').value = s.gift_template;
  $('tts-api-fields').hidden = s.tts.provider === 'windows';
  $('image-proxy-mode').value = s.image.proxy_mode || 'system';
  $('image-proxy-url').value = s.image.proxy_url || '';
  $('image-proxy-fields').hidden = $('image-proxy-mode').value !== 'manual';
}
async function refresh() {
  state = await api('/api/state');
  renderProducts(); renderStudioScenes(); renderEvents(state.events); renderRuntime(state.runtime);
}
async function copy(text, message) {
  try { await navigator.clipboard.writeText(text); toast(message); }
  catch { toast('浏览器不允许自动复制，请手动复制：' + text, true); }
}

$('new-product').onclick = () => editProduct(null);
$('product-form').onsubmit = async e => {
  e.preventDefault();
  await busy(e.submitter, '保存中…', async () => {
    const result = await send('/api/products', productForm());
    await refresh(); editProduct(result.product.id); toast('商品知识已保存');
  });
};
$('delete-product').onclick = async () => {
  if (!editingId || !confirm('确定删除这个商品及其知识资料？')) return;
  await busy($('delete-product'), '删除中…', async () => {
    await api('/api/products/' + encodeURIComponent(editingId), {method:'DELETE'});
    await refresh(); editProduct(state.products[0]?.id || null); toast('商品已删除');
  });
};
$('organize-product').onclick = () => {
  if (!$('product-name').value.trim() || !$('product-description').value.trim()) return toast('先填写商品名称和真实介绍', true);
  if (($('product-faq').value.trim() || $('product-script').value.trim()) && !confirm('AI 将重写当前 FAQ 和讲解稿，生成后仍需你核对。继续吗？')) return;
  busy($('organize-product'), '整理中…', async () => {
    const result = await send('/api/products/organize', productForm());
    $('product-faq').value = result.faq; $('product-script').value = result.script;
    toast('已整理，请核对事实后保存商品');
  });
};
$('knowledge-file').onchange = async e => {
  const f = e.target.files[0]; if (!f) return;
  if (f.size > 100000 || !/\.(txt|md)$/i.test(f.name)) return toast('请选择不超过100KB的 UTF-8 TXT 或 MD 文件', true);
  const text = await f.text();
  if (text.length > 15000) return toast('资料最多15000字，请分商品整理', true);
  $('product-description').value = text; e.target.value = ''; toast('资料已导入，请核对后保存');
};
$('rule-form').onsubmit = e => {
  e.preventDefault(); const pattern = $('new-rule').value.trim();
  if (!pattern) return;
  if (rules.some(r => r.pattern === pattern)) return toast('已有这条规则', true);
  rules.push({id:crypto.randomUUID(),pattern,enabled:true,category:'自定义'});
  $('new-rule').value = ''; renderRules();
};
$('save-rules').onclick = () => busy($('save-rules'), '保存中…', async () => {
  await send('/api/rules', rules, 'PUT'); toast('屏蔽规则已生效');
});
$('save-gift').onclick = () => busy($('save-gift'), '保存中…', async () => {
  await send('/api/settings', {gift_template:$('gift-template').value}, 'PUT'); toast('答谢文案已保存');
});
document.querySelectorAll('[data-event-kind]').forEach(e => e.onclick = () => {
  eventKind = e.dataset.eventKind;
  document.querySelectorAll('[data-event-kind]').forEach(x => x.classList.toggle('selected', x === e));
  $('gift-count-field').hidden = eventKind !== 'gift';
  $('sim-text-label').textContent = eventKind === 'gift' ? '礼物名称' : '弹幕内容';
  $('sim-text').value = eventKind === 'gift' ? '鲜花' : '可以放洗碗机吗？';
  document.querySelector('.suggestions').hidden = eventKind === 'gift';
});
document.querySelectorAll('[data-sample]').forEach(e => e.onclick = () => $('sim-text').value = e.dataset.sample);
$('simulate-form').onsubmit = e => {
  e.preventDefault(); busy(e.submitter, '发送中…', async () => {
    const event = {kind:eventKind, username:$('sim-user').value.trim(), count:Number($('sim-count').value)};
    event[eventKind === 'gift' ? 'gift' : 'text'] = $('sim-text').value.trim();
    await send('/api/simulate', event);
    toast(state.runtime.active ? '已发送，处理结果将出现在互动记录' : '已发送；开始彩排后可播出通过的互动');
  });
};
$('start-studio').onclick = () => {
  if (!$('active-product').value) return toast('请先添加并启用商品', true);
  if (!$('active-scene').value) return toast('请先生成并选择直播场景模型', true);
  $('studio-preview').contentWindow.postMessage({type:'activate-audio'}, location.origin);
  busy($('start-studio'), '准备讲解配音…', async () => {
    await send('/api/studio/start', {product_id:$('active-product').value,scene_id:$('active-scene').value});
    await refresh();
    toast('彩排已开始。首次使用请允许播放声音');
  });
};
$('stop-studio').onclick = () => busy($('stop-studio'), '停止中…', async () => {
  await send('/api/studio/stop', {}); toast('已停止播出');
});
$('copy-obs').onclick = async () => {
  if (desktop) {try {await desktop.copyStageUrl(); toast('OBS 地址已复制，请勿公开其中的本机访问凭据');} catch(e) {toast(e.message,true);}}
  else copy(location.origin + '/stage?mode=obs', 'OBS 地址已复制，建议浏览器源宽1080、高1920');
};
$('open-stage').onclick = () => busy($('open-stage'), '打开中…', async () => {
  if (desktop) await desktop.openStage();
  else window.open('/stage?mode=obs', '_blank', 'noopener');
});
$('export-project').onclick = () => busy($('export-project'), '导出中…', async () => {
  if (desktop) {const result=await desktop.exportProject();if(result.ok)toast('项目已导出，不包含服务密钥');}
  else {const a=document.createElement('a');a.href='/api/export';a.download='yingbo-project.zip';a.click();}
});
$('import-project').onclick = () => busy($('import-project'), '导入中…', async () => {
  const result=await desktop.importProject();if(result.ok)toast('项目已导入');
});
$('open-data').onclick = () => busy($('open-data'), '打开中…', () => desktop.openData());
$('copy-token').onclick = () => copy($('event-token').value, '事件接入密钥已复制');
$('avatar-file').onchange = async e => {
  const file = e.target.files[0]; if (!file) return;
  if (file.size > 10000000) return toast('图片不能超过10MB', true);
  const form = new FormData(); form.append('file', file);
  const zone = document.querySelector('.upload-zone');
  zone.style.pointerEvents = 'none';
  try {
    const a = await api('/api/avatar/upload', {method:'POST', body:form});
    state.settings.avatar = a; renderAvatar(); toast('参考图已上传，当前直播模型保持不变');
  } catch(e) { toast(e.message, true); }
  finally { zone.style.pointerEvents = ''; $('avatar-file').value = ''; }
};
$('tts-provider').onchange = () => $('tts-api-fields').hidden = $('tts-provider').value === 'windows';
$('image-proxy-mode').onchange = () => $('image-proxy-fields').hidden = $('image-proxy-mode').value !== 'manual';
function imageSettings() {
  return {base_url:$('image-url').value.trim(),model:$('image-model').value.trim(),key:$('image-key').value.trim(),clear_key:$('image-clear').checked,
    proxy_mode:$('image-proxy-mode').value,proxy_url:$('image-proxy-url').value.trim()};
}
$('test-image-connection').onclick = () => busy($('test-image-connection'),'测试连接中…',async()=>{
  $('image-connection-result').textContent='正在测试连接，不会生成图片或消耗生成额度…';
  try {
    await send('/api/settings',{image:imageSettings()},'PUT');
    $('image-key').value='';
    const result=await send('/api/image/test',{});
    $('image-connection-result').textContent=(result.via_proxy?'本次请求：经过代理。':'本次请求：未配置应用代理，使用系统路由。')+result.message;
    toast(result.message,!result.model_found);
  } catch(e) {
    $('image-connection-result').textContent=e.message;
    throw e;
  }
});
$('settings-form').onsubmit = e => {
  e.preventDefault(); busy(e.submitter, '保存中…', async () => {
    const body = {};
    for (const section of ['llm','tts','image']) body[section] = {base_url:$(section+'-url').value.trim(), model:$(section+'-model').value.trim(), key:$(section+'-key').value.trim(), clear_key:$(section+'-clear').checked};
    Object.assign(body.tts, {provider:$('tts-provider').value, voice:$('tts-voice').value.trim(), rate:Number($('tts-rate').value)});
    body.image=imageSettings();
    await send('/api/settings', body, 'PUT'); await refresh(); renderSettings(); toast('接入设置已保存');
  });
};
window.addEventListener('message', e => {
  if (e.origin === location.origin && e.data?.type === 'player-error') toast(e.data.message, true);
});

(async () => {
  try {
    await refresh(); rules = structuredClone(state.rules); renderRules(); renderAvatar(); renderSettings();
    if (state.platform !== 'win32') {
      $('tts-provider').querySelector('option[value="windows"]').disabled = true;
      $('voice-platform-hint').textContent = '此系统不支持 Windows 配音，请配置本地或云端兼容语音服务。';
    }
    if (desktop) {
      const info=await desktop.info();
      $('client-label').textContent='桌面客户端';$('app-version').textContent='v'+info.version;
      $('import-project').hidden=false;$('desktop-storage').hidden=false;
      $('data-directory').textContent=info.dataDir;
      $('platform-detail').textContent=(info.portable?'便携模式 · 数据保存在程序旁':'用户模式 · 数据与安装包分离')+' · '+info.platform;
    }
    editProduct(state.products[0]?.id || null);
    const view = location.hash.slice(1);
    if (['studio','avatar','knowledge','rules','settings'].includes(view)) navigate(view);
    const stream = new EventSource('/api/stream');
    stream.onmessage = e => {
      const m = JSON.parse(e.data);
      if (m.type === 'events') renderEvents(m.data);
      if (m.type === 'runtime') renderRuntime(m.data);
      if (m.type === 'settings') {state.settings.avatar = m.data.avatar; renderAvatar(); renderStudioScenes();}
      if (m.type === 'scene_job') {state.scene_jobs=[m.data,...(state.scene_jobs||[]).filter(j=>j.id!==m.data.id)];renderStudioScenes();}
    };
    stream.onerror = () => {$('studio-status').textContent = '连接中断'; $('studio-detail').textContent = '正在尝试连接本地服务';};
  } catch(e) { toast(e.message, true); }
})();
