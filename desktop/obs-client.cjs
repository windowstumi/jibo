// Reuse OBS's media engine through its official WebSocket protocol.
const OBSWebSocket=require('obs-websocket-js').default;

class ObsClient {
  constructor(client=new OBSWebSocket()){
    this.client=client;this.connected=false;this.scenes={};this.assets={};this.speaking=false;this.current=null;
    this.client.on?.('ConnectionClosed',()=>{this.connected=false;this.scenes={};this.current=null;});
    this.client.on?.('MediaInputPlaybackEnded',event=>{
      const name=this.scenes[this.current];
      if(name && event.inputName===name+'-video' && this.assets[this.current]?.loop===false)
        this.present(this.speaking?(this.speechKind||'talk'):'idle').catch(error=>{this.lastError=error.message;});
    });
  }
  async connect(config){
    const url=new URL(config.url);
    if(!['ws:','wss:'].includes(url.protocol)||!['127.0.0.1','localhost'].includes(url.hostname))throw Error('只允许连接本机OBS');
    await this.client.disconnect();this.connected=false;this.scenes={};this.current=null;this.speaking=false;
    await this.client.connect(config.url,config.password||'',{rpcVersion:1,eventSubscriptions:4095});
    this.connected=true;
    return this.client.call('GetVersion');
  }
  async setup(character,folder){
    if(!this.connected)throw Error('请先连接OBS');
    if(!character.accepted)throw Error('请先在工坊验收角色，不能将待审核素材用于播出');
    const path=require('node:path'),fs=require('node:fs');
    const list=await this.client.call('GetSceneList');
    const existing=new Set(list.scenes.map(s=>s.sceneName));this.scenes={};this.assets=character.assets;this.current=null;this.speaking=false;
    const inputs=await this.client.call('GetInputList');
    const names=new Set(inputs.inputs.map(input=>input.inputName));
    const video=await this.client.call('GetVideoSettings');
    for(const [kind,asset] of Object.entries(character.assets)){
      if(kind==='thoughtful')continue; // Old packages retain their billing history, not this retired scene.
      if(kind==='happy' && !fs.existsSync(path.join(folder,asset.file)))continue;
      if(!/^[a-z]+\.(mp4|webm)$/.test(asset.file)||!fs.existsSync(path.join(folder,asset.file)))throw Error('角色包文件缺失或路径无效');
      const name='极播-'+character.id.slice(0,8)+'-'+kind;
      const settings={is_local_file:true,local_file:path.join(folder,asset.file),looping:asset.loop===true,
        restart_on_activate:true,close_when_inactive:true,clear_on_media_end:false};
      if(!existing.has(name))await this.client.call('CreateScene',{sceneName:name});
      if(!names.has(name+'-video')){
        await this.client.call('CreateInput',{sceneName:name,inputName:name+'-video',inputKind:'ffmpeg_source',inputSettings:settings,sceneItemEnabled:true});
      }else await this.client.call('SetInputSettings',{inputName:name+'-video',inputSettings:settings,overlay:true});
      const item=await this.client.call('GetSceneItemId',{sceneName:name,sourceName:name+'-video'});
      await this.client.call('SetSceneItemTransform',{sceneName:name,sceneItemId:item.sceneItemId,
        sceneItemTransform:{positionX:0,positionY:0,boundsType:'OBS_BOUNDS_SCALE_INNER',boundsWidth:video.baseWidth,boundsHeight:video.baseHeight}});
      await this.client.call('SetInputMute',{inputName:name+'-video',inputMuted:true});
      this.scenes[kind]=name;
    }
    return {scenes:this.scenes};
  }
  async present(kind){
    const requested=kind;
    if(!this.scenes[kind] && ['happy','thoughtful'].includes(kind))kind='talk';
    if(!this.connected||!this.scenes[kind])throw Error('请先配置OBS角色场景');
    // Use OBS's built-in Fade, without changing or deleting user scenes.
    const transitions=await this.client.call('GetSceneTransitionList');
    const fade=transitions.transitions.find(t=>t.transitionKind==='fade_transition');
    if(!fade)throw Error('OBS缺少淡化过渡，请先添加淡化过渡');
    await this.client.call('SetCurrentSceneTransition',{transitionName:fade.transitionName});
    await this.client.call('SetCurrentSceneTransitionDuration',{transitionDuration:250});
    const repeat=this.current===kind;this.current=kind;
    await this.client.call('SetCurrentProgramScene',{sceneName:this.scenes[kind]});
    if(repeat && this.assets[kind]?.loop===false)await this.client.call('TriggerMediaInputAction',{
      inputName:this.scenes[kind]+'-video',mediaAction:'OBS_WEBSOCKET_MEDIA_INPUT_ACTION_RESTART'});
    return {kind,requested,fallback:kind!==requested};
  }
  async setSpeaking(value,emotion='talk'){
    this.speaking=value;this.speechKind=emotion==='happy'?'happy':'talk';
    if(!value&&this.assets[this.current]?.loop===false)return {deferred:true};
    return this.present(value?this.speechKind:'idle');
  }
  async close(){this.connected=false;await this.client.disconnect();}
}
module.exports={ObsClient};
