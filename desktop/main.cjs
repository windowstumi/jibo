const {app, BrowserWindow, Menu, ipcMain, dialog, shell, clipboard, session} = require('electron');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const crypto = require('node:crypto');
const {spawn} = require('node:child_process');
const {backendCommand, chooseDataRoot, isLocalUrl} = require('./platform.cjs');
const {ObsClient}=require('./obs-client.cjs');
const obs=new ObsClient();

const root = path.resolve(__dirname, '..');
let backend, mainWindow, stageWindow, origin, dataRoot, token, log, stopping = false, readyFile;
const smokeFile = process.env.YINGBO_SMOKE_REPORT;
const legacyProfile=path.join(app.getPath('appData'),'Yingbo Studio');
app.setName('极播');
if(fs.existsSync(legacyProfile))app.setPath('userData',legacyProfile);
if(smokeFile) app.setPath('userData',path.join(path.dirname(smokeFile),'electron-profile'));
app.commandLine.appendSwitch('autoplay-policy', 'no-user-gesture-required');

const gotLock = app.requestSingleInstanceLock();
if (!gotLock) app.quit();
app.on('second-instance', () => {if (mainWindow) {if (mainWindow.isMinimized()) mainWindow.restore(); mainWindow.show(); mainWindow.focus();}});

function logLine(message) {if (log) fs.appendFileSync(log, `${new Date().toISOString()} ${message}\n`);}
function stageUrl() {return origin + '/stage?mode=obs&access_token=' + encodeURIComponent(token);}

async function api(route, init = {}) {
  const res = await fetch(origin + route, {...init, headers:{'X-Yingbo-Token':token, ...(init.headers || {})}, signal:AbortSignal.timeout(15000)});
  if (!res.ok) {
    let reason = `本地服务请求失败（${res.status}）`;
    try {const body = await res.json(); if (typeof body.detail === 'string') reason = body.detail;} catch {}
    throw new Error(reason);
  }
  return res;
}

async function startBackend() {
  dataRoot = chooseDataRoot({userData:app.getPath('userData'),env:!app.isPackaged && !process.env.YINGBO_DATA_DIR && !process.env.JIBO_DATA_DIR ? {...process.env,YINGBO_DATA_DIR:path.join(root,'data')} : process.env});
  fs.mkdirSync(dataRoot, {recursive:true});
  fs.mkdirSync(path.join(dataRoot,'logs'), {recursive:true});
  log = path.join(dataRoot, 'logs', 'desktop.log');
  if (fs.existsSync(log) && fs.statSync(log).size > 2_000_000) fs.renameSync(log, log + '.previous');
  const tokenPath = path.join(dataRoot,'.local-access-token');
  token = fs.existsSync(tokenPath) ? fs.readFileSync(tokenPath,'utf8').trim() : crypto.randomBytes(32).toString('hex');
  fs.writeFileSync(tokenPath,token,{mode:0o600});
  readyFile = path.join(os.tmpdir(), 'yingbo-' + crypto.randomUUID() + '.json');
  const command = backendCommand({packaged:app.isPackaged,resourcesPath:process.resourcesPath,root,python:process.env.YINGBO_PYTHON});
  if (!fs.existsSync(command.command)) throw new Error(app.isPackaged ? '安装包缺少后台程序，请重新下载完整安装包。' : '没有找到 Python 环境。请按 README 创建 .venv，或指定 YINGBO_PYTHON。');
  const {ELECTRON_RUN_AS_NODE, ...environment} = process.env;
  backend = spawn(command.command,[...command.args,'--port',process.env.YINGBO_PORT || '8765','--ready-file',readyFile], {
    cwd:app.isPackaged ? path.dirname(command.command) : root,
    env:{...environment,VTUBER_DATA_DIR:dataRoot,VTUBER_AUTH_TOKEN:token,YINGBO_DESKTOP:'1',PYTHONUTF8:'1',PYTHONUNBUFFERED:'1'},
    windowsHide:true,stdio:['pipe','pipe','pipe']
  });
  let startupError;
  backend.on('error', err => {startupError = err;});
  backend.stdout.on('data', data => logLine(String(data)));
  backend.stderr.on('data', data => logLine(String(data)));
  backend.on('exit', code => {
    logLine('Backend exited: ' + code);
    if (mainWindow && !stopping) {
      dialog.showErrorBox('后台服务已停止', '请重启极播客户端。诊断日志保存在数据目录的 logs 文件夹。');
      app.quit();
    }
  });
  const deadline = Date.now()+60_000;
  while (!fs.existsSync(readyFile)) {
    if (startupError) throw startupError;
    if (backend.exitCode !== null) throw new Error('后台启动失败。请检查：' + log);
    if (Date.now()>deadline) throw new Error('后台启动超时。请检查：' + log);
    await new Promise(resolve => setTimeout(resolve,100));
  }
  const ready = JSON.parse(fs.readFileSync(readyFile,'utf8'));
  // Windows venv launchers may create a child with a different PID.
  if (!Number.isInteger(ready.pid) || !Number.isInteger(ready.port)) throw new Error('后台启动信息不匹配');
  origin = 'http://127.0.0.1:' + ready.port;
  const health = await(await api('/api/health')).json();
  if(health.pid!==ready.pid) throw new Error('本地服务身份校验失败');
}

function secureWindow(win) {
  win.webContents.setWindowOpenHandler(({url}) => {
    if (isLocalUrl(url,origin) && new URL(url).pathname === '/stage') openStage();
    else if (/^https:\/\//.test(url)) shell.openExternal(url);
    return {action:'deny'};
  });
  win.webContents.on('will-navigate',(event,url) => {if (!isLocalUrl(url,origin)) event.preventDefault();});
  win.webContents.on('will-attach-webview', event => event.preventDefault());
  win.webContents.on('render-process-gone', () => {if (!stopping) logLine('Renderer stopped unexpectedly');});
}

async function exportProject() {
  const result = await dialog.showSaveDialog(mainWindow,{title:'导出可迁移项目',defaultPath:'极播项目.zip',filters:[{name:'极播项目',extensions:['zip']}]});
  if (result.canceled) return {canceled:true};
  const response = await api('/api/export');
  fs.writeFileSync(result.filePath, Buffer.from(await response.arrayBuffer()));
  return {ok:true};
}

async function importProject() {
  const result = await dialog.showOpenDialog(mainWindow,{title:'导入极播项目',properties:['openFile'],filters:[{name:'极播项目',extensions:['zip']}]});
  if (result.canceled) return {canceled:true};
  const confirm = await dialog.showMessageBox(mainWindow,{type:'question',title:'导入项目',message:'导入后将替换当前商品、形象和屏蔽规则。',detail:'当前项目会自动备份。服务密钥保留在本机，不从项目包导入。',buttons:['取消','备份并导入'],defaultId:0,cancelId:0});
  if (confirm.response !== 1) return {canceled:true};
  const file = result.filePaths[0];
  if (fs.statSync(file).size > 100_000_000) throw new Error('项目包不能超过100MB');
  const backup = await api('/api/export');
  const backups = path.join(dataRoot,'backups'); fs.mkdirSync(backups,{recursive:true});
  fs.writeFileSync(path.join(backups,'before-import-' + Date.now() + '.zip'),Buffer.from(await backup.arrayBuffer()));
  const form = new FormData(); form.append('file',new Blob([fs.readFileSync(file)],{type:'application/zip'}),'project.zip');
  await api('/api/import',{method:'POST',body:form});
  mainWindow.reload();
  if (stageWindow) stageWindow.reload();
  return {ok:true};
}

async function openStage() {
  if (stageWindow && !stageWindow.isDestroyed()) {stageWindow.show();stageWindow.focus();return {ok:true};}
  stageWindow = new BrowserWindow({title:'极播 · 透明播出窗口',width:450,height:800,minWidth:270,minHeight:480,transparent:true,backgroundColor:'#00000000',frame:false,resizable:true,show:false,
    webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true,backgroundThrottling:false}});
  secureWindow(stageWindow);
  stageWindow.on('ready-to-show',()=>stageWindow?.show());
  stageWindow.on('closed',()=>stageWindow=null);
  stageWindow.webContents.on('context-menu',()=>Menu.buildFromTemplate([{label:'关闭播出窗口',click:()=>stageWindow?.close()}]).popup({window:stageWindow}));
  await stageWindow.loadURL(stageUrl()+'&desktop=1');
  return {ok:true};
}

async function createMainWindow() {
  mainWindow = new BrowserWindow({title:'极播 · 虚拟人直播客户端',width:1360,height:920,minWidth:950,minHeight:680,backgroundColor:'#f6f7f9',show:false,
    webPreferences:{preload:path.join(__dirname,'preload.cjs'),nodeIntegration:false,contextIsolation:true,sandbox:true,backgroundThrottling:false}});
  secureWindow(mainWindow);
  mainWindow.on('ready-to-show',()=>mainWindow?.show());
  mainWindow.on('closed',()=>{mainWindow=null;app.quit();});
  await mainWindow.loadURL(origin);
}

function registerIpc() {
  const handler = (channel, fn) => ipcMain.handle(channel, async (event,...args) => {
    if (!mainWindow || event.sender !== mainWindow.webContents || !event.senderFrame || event.senderFrame !== mainWindow.webContents.mainFrame || !isLocalUrl(event.senderFrame.url,origin)) throw new Error('不允许的客户端操作');
    try {return await fn(...args);} catch(err) {logLine('Desktop action failed: '+err.message); throw new Error(err.message);}
  });
  handler('desktop:info',()=>({version:app.getVersion(),platform:process.platform,dataDir:dataRoot,portable:!!process.env.PORTABLE_EXECUTABLE_DIR,packaged:app.isPackaged}));
  handler('desktop:stage',openStage);
  handler('desktop:export',exportProject);
  handler('desktop:import',importProject);
  handler('desktop:data',async()=>{const error=await shell.openPath(dataRoot);if(error)throw new Error(error);return {ok:true};});
  handler('desktop:copy-stage',()=>{clipboard.writeText(stageUrl());return {ok:true};});
  handler('desktop:obs-connect',async()=>{
    const settings=await(await api('/api/obs/private-config')).json();
    const result=await obs.connect(settings);return {version:result.obsVersion};
  });
  handler('desktop:obs-setup',async ident=>{
    if(typeof ident!=='string'||!/^[a-f0-9]{32}$/.test(ident))throw Error('角色编号无效');
    const character=await(await api('/api/characters/'+ident)).json();
    return obs.setup(character,path.join(dataRoot,'characters',ident));
  });
  handler('desktop:obs-present',kind=>{
    if(!['idle','talk','happy','thoughtful','thanks','greeting','present'].includes(kind))throw Error('动作无效');
    return obs.present(kind);
  });
  handler('desktop:obs-speaking',value=>{
    if(typeof value!=='boolean')throw Error('说话状态无效');
    return obs.setSpeaking(value);
  });
  handler('desktop:obs-status',()=>({connected:obs.connected,error:obs.lastError||null}));
}

function setMenu() {
  const run = fn => () => Promise.resolve(fn()).catch(err=>dialog.showErrorBox('操作未完成',err.message));
  Menu.setApplicationMenu(Menu.buildFromTemplate([
    ...(process.platform==='darwin'?[{role:'appMenu',label:'极播'}]:[]),
    {label:'项目',submenu:[{label:'导出可迁移项目…',accelerator:'CmdOrCtrl+Shift+S',click:run(exportProject)},{label:'导入项目…',click:run(importProject)},{type:'separator'},{label:'打开数据目录',click:run(()=>shell.openPath(dataRoot))},{type:'separator'},{role:'quit',label:'退出极播'}]},
    {label:'编辑',submenu:[{role:'undo',label:'撤销'},{role:'redo',label:'重做'},{type:'separator'},{role:'cut',label:'剪切'},{role:'copy',label:'复制'},{role:'paste',label:'粘贴'},{role:'selectAll',label:'全选'}]},
    {label:'播出',submenu:[{label:'打开透明播出窗口',click:run(openStage)},{label:'关闭透明播出窗口',click:()=>stageWindow?.close()},{label:'复制 OBS 浏览器源地址',click:()=>clipboard.writeText(stageUrl())}]},
    {label:'视图',submenu:[{role:'resetZoom',label:'实际大小'},{role:'zoomIn',label:'放大'},{role:'zoomOut',label:'缩小'},{role:'togglefullscreen',label:'全屏'},...(!app.isPackaged?[{role:'toggleDevTools',label:'开发工具'}]:[])]},
    {label:'帮助',submenu:[{label:'关于极播',click:()=>dialog.showMessageBox(mainWindow,{type:'info',message:'极播 · 虚拟人直播客户端',detail:`版本 ${app.getVersion()}\n数据目录：${dataRoot}\n单图动画 · 商品知识库 · 语音互动`})}]}
  ]));
}

async function smokeTest() {
  const inspect = win => win.webContents.executeJavaScript(`({title:document.title,bridge:typeof window.yingboDesktop==='object',cards:document.querySelectorAll('.card').length,body:document.body.innerText.includes('商品知识库'),viewport:innerWidth})`);
  await new Promise(r=>setTimeout(r,800));
  const state = await (await api('/api/state')).json();
  const report = {packaged:app.isPackaged,platform:process.platform,main:await inspect(mainWindow),health:await(await api('/api/health')).json(),dataRoot};
  report.characters=await mainWindow.webContents.executeJavaScript(`(async()=>{
    navigate('characters');const quote=await api('/api/characters/quote');
    return {title:document.title,bridge:typeof window.jiboDesktop==='object',rows:quote.rows.length,total:quote.total_cny,
      missing:quote.missing.length,importer:!!document.getElementById('import-character'),rehearsal:!!document.getElementById('start-character-rehearsal'),
      optionalFallback:quote.fallbacks.happy==='talk',retiredAbsent:!document.querySelector('[data-ref-url="thoughtful"]'),
      optionalLabel:document.querySelector('[data-ref-url="happy"]')?.closest('.reference-row').textContent.includes('选填'),
      detachedMouth:!!document.querySelector('#mouth,.mouth-demo')};})()`);
  await new Promise(resolve=>setTimeout(resolve,300));
  report.characterScreenshot=path.join(path.dirname(smokeFile),'characters-ui.png');
  fs.writeFileSync(report.characterScreenshot,(await mainWindow.webContents.capturePage()).toPNG());
  await mainWindow.webContents.executeJavaScript(`navigate('studio')`);
  if(process.env.JIBO_SMOKE_CARD){
    const check=require('./card-check.cjs');report.characterCards=await mainWindow.webContents.executeJavaScript(`(${check.toString()})()`);
    report.workbenchCardScreenshot=path.join(path.dirname(smokeFile),'workbench-video-card.png');
    fs.writeFileSync(report.workbenchCardScreenshot,(await mainWindow.webContents.capturePage()).toPNG());
    report.cardScreenshot=path.join(path.dirname(smokeFile),'character-cards-ui.png');
    await mainWindow.webContents.executeJavaScript(`navigate('characters')`);await new Promise(r=>setTimeout(r,350));
    fs.writeFileSync(report.cardScreenshot,(await mainWindow.webContents.capturePage()).toPNG());
    await openStage();await new Promise(r=>setTimeout(r,2500));
    report.nativeCardStage=await stageWindow.webContents.executeJavaScript(`({ready:document.getElementById('character-videos').dataset.ready==='true',kind:document.getElementById('character-videos').dataset.kind})`);
    report.nativeCardStage.previewPaused=await mainWindow.webContents.executeJavaScript(`document.getElementById('studio-preview').contentDocument.getElementById('stage-audio').paused`);
    report.runtime=(await(await api('/api/state')).json()).runtime;
    await api('/api/studio/stop',{method:'POST'});stageWindow.close();
    fs.writeFileSync(smokeFile,JSON.stringify(report,null,2));app.quit();return;
  }
  if(process.env.YINGBO_SMOKE_SCENE){
    const job=state.scene_jobs.find(j=>j.status==='review'||j.status==='accepted');
    if(!job)throw Error('Smoke test scene was not loaded');
    await api('/api/scenes/'+job.id+'/activate',{method:'POST'});
    const exported=await(await api('/api/export')).arrayBuffer();
    const form=new FormData();form.append('file',new Blob([exported],{type:'application/zip'}),'scene.zip');
    await api('/api/import',{method:'POST',body:form});
    report.sceneMigration=true;
  } else {
    const blocked=await fetch(origin+'/api/studio/start',{method:'POST',headers:{'X-Yingbo-Token':token,'Content-Type':'application/json'},body:JSON.stringify({product_id:state.products[0].id})});
    report.noSceneBlocked=blocked.status===409;
    report.noLegacyRenderer=await mainWindow.webContents.executeJavaScript(`!document.querySelector('#test-mouth,#calibration-form,.mouth-demo')`);
    fs.writeFileSync(smokeFile,JSON.stringify(report,null,2));app.quit();return;
  }
  await api('/api/studio/start',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({product_id:state.products[0].id})});
  await mainWindow.webContents.executeJavaScript(`document.getElementById('studio-preview').contentWindow.postMessage({type:'activate-audio'},location.origin)`);
  await new Promise(r=>setTimeout(r,1500));
  report.workbench=await mainWindow.webContents.executeJavaScript(`(()=>{const d=document.getElementById('studio-preview').contentDocument;return {sceneReady:d.getElementById('scene-canvas').dataset.ready,legacyMouth:!!d.getElementById('mouth'),selector:!!document.getElementById('active-scene')};})()`);
  await openStage();
  await new Promise(r=>setTimeout(r,2500));
  report.stage = await stageWindow.webContents.executeJavaScript(`({title:document.title,role:new URLSearchParams(location.search).get('mode'),transparent:getComputedStyle(document.body).backgroundColor,independentMouthElements:document.querySelectorAll('#mouth,.mouth,.mouth-demo').length,subtitle:document.getElementById('subtitle').innerText,audioButtonHidden:document.getElementById('enable-audio').hidden,scene:{hidden:document.getElementById('scene-canvas').hidden,...document.getElementById('scene-canvas').dataset}})`);
  const active=(await(await api('/api/state')).json()).settings.avatar.scene_id;
  const loaded=await(await api('/api/scenes/'+active)).json();
  const check=require('./scene-check.cjs');
  report.pixels=await stageWindow.webContents.executeJavaScript(`(${check.toString()})(${JSON.stringify(loaded.model)},${JSON.stringify(origin+loaded.base_url)})`);
  report.runtime = (await(await api('/api/state')).json()).runtime;
  if(process.env.YINGBO_SMOKE_CLIP){
    const checkActions=require('./action-check.cjs');
    const clip=fs.readFileSync(process.env.YINGBO_SMOKE_CLIP).toString('base64');
    report.clipInspection=await mainWindow.webContents.executeJavaScript(`(async()=>{const bytes=Uint8Array.from(atob(${JSON.stringify(clip)}),c=>c.charCodeAt(0));const info=await inspectActionFile(new File([bytes],'fixture.webm',{type:'video/webm'}));return {duration:info.duration,width:info.width,height:info.height,first:info.first.size,last:info.last.size};})()`);
    report.actions=await stageWindow.webContents.executeJavaScript(`(${checkActions.toString()})(${JSON.stringify(clip)},${JSON.stringify(active)})`);
    await mainWindow.webContents.executeJavaScript(`(async()=>{navigate('avatar');await loadScene(${JSON.stringify(active)});document.querySelector('.action-library').scrollIntoView({block:'center'});})()`);
    await new Promise(resolve=>setTimeout(resolve,400));
    report.actionScreenshot=path.join(path.dirname(smokeFile),'actions-ui.png');
    fs.writeFileSync(report.actionScreenshot,(await mainWindow.webContents.capturePage()).toPNG());
  }
  await api('/api/studio/stop',{method:'POST'});
  stageWindow.close();
  fs.writeFileSync(smokeFile,JSON.stringify(report,null,2));
  app.quit();
}

async function shutdown() {
  if (stopping) return;
  stopping=true;
  await obs.close().catch(()=>{});
  if (stageWindow) stageWindow.destroy();
  if (backend && backend.exitCode===null) {
    try {if(origin) await api('/api/studio/stop',{method:'POST'});} catch {}
    backend.stdin.end();
    await Promise.race([new Promise(resolve=>backend.once('exit',resolve)),new Promise(resolve=>setTimeout(resolve,3000))]);
    if(backend.exitCode===null) backend.kill();
  }
  if (readyFile) fs.rmSync(readyFile,{force:true});
  app.exit(0);
}
app.on('before-quit',event=>{if(!stopping){event.preventDefault();shutdown();}});
app.on('window-all-closed',()=>app.quit());

if (gotLock) app.whenReady().then(async()=>{
  try {
    await startBackend();
    session.defaultSession.setPermissionRequestHandler((_wc,_permission,callback)=>callback(false));
    session.defaultSession.webRequest.onBeforeSendHeaders((details,callback)=>{
      if(isLocalUrl(details.url,origin)) details.requestHeaders['X-Yingbo-Token']=token;
      callback({requestHeaders:details.requestHeaders});
    });
    registerIpc(); setMenu(); await createMainWindow();
    if(smokeFile) await smokeTest();
  } catch(err) {
    logLine(err.stack || err.message);
    if(smokeFile) fs.writeFileSync(smokeFile,JSON.stringify({error:err.message}));
    else dialog.showErrorBox('极播启动失败',err.message);
    app.quit();
  }
});
