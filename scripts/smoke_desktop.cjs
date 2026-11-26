const {spawn} = require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const root=path.resolve(__dirname,'..');
const temp=fs.mkdtempSync(path.join(os.tmpdir(),'yingbo-smoke-'));
const report=path.join(temp,'report.json');
const packaged=!!process.argv[2] && process.argv[2]!=='--dev';
const target=packaged?process.argv[2]:require('electron');
const {ELECTRON_RUN_AS_NODE,...env}=process.env;
const cardIndex=process.argv.indexOf('--card');const card=cardIndex>=0?process.argv[cardIndex+1]:null;
const scene=process.argv[3]&&process.argv[3]!=='--card'?process.argv[3]:null;
if(scene){const source=path.resolve(scene);fs.mkdirSync(path.join(temp,'data','scenes'),{recursive:true});fs.cpSync(source,path.join(temp,'data','scenes',path.basename(source)),{recursive:true});}
if(card){const source=path.resolve(card);fs.mkdirSync(path.join(temp,'data','characters'),{recursive:true});fs.cpSync(source,path.join(temp,'data','characters',path.basename(source)),{recursive:true});}
const proc=spawn(target,packaged?[]:[root],{cwd:root,env:{...env,YINGBO_SMOKE_REPORT:report,YINGBO_DATA_DIR:path.join(temp,'data'),JIBO_DATA_DIR:path.join(temp,'data'),YINGBO_PORT:'0',...(scene?{YINGBO_SMOKE_SCENE:'1'}:{}),...(card?{JIBO_SMOKE_CARD:'1'}:{})},stdio:'inherit'});
const timer=setTimeout(()=>{proc.kill();console.error('Desktop smoke timeout: '+temp);process.exitCode=1;},card?150000:90000);
proc.on('error',e=>{clearTimeout(timer);console.error(e);process.exitCode=1;});
proc.on('exit',()=>{
  clearTimeout(timer);
  if(!fs.existsSync(report)){console.error('Missing smoke report: '+temp);process.exitCode=1;return;}
  const r=JSON.parse(fs.readFileSync(report,'utf8'));
  console.log(JSON.stringify(r,null,2));
  if(r.error || !r.main?.bridge || r.main.cards<5) process.exitCode=1;
  if(!r.localTts?.option||!r.localTts.settingsVisible||!r.localTts.apiHidden||!r.localTts.progressVisible||!r.localTts.indeterminate||!r.localTts.voiceImport||!r.localTts.testDisabled)process.exitCode=1;
  if(!r.characters?.bridge || r.characters.rows!==7 || !r.characters.importer || !r.characters.rehearsal || r.characters.detachedMouth || !r.characters.title.includes('极播')) process.exitCode=1;
  if(!r.characters?.optionalFallback || !r.characters.retiredAbsent || !r.characters.optionalLabel)process.exitCode=1;
  if(!scene && !card && (!r.noSceneBlocked || !r.noLegacyRenderer)) process.exitCode=1;
  if(card&&(!r.characterCards?.alphaDecoded||!r.characterCards.applied||!r.characterCards.imported||!r.characterCards.switched||!r.characterCards.actualVoice||!r.characterCards.workbenchVoice||!r.characterCards.giftVoice||!r.nativeCardStage?.ready||!r.nativeCardStage.previewPaused||r.runtime?.owner_role!=='obs'))process.exitCode=1;
  if(card&&(!r.characterCards?.legacyNodRemoved||!r.characterCards.giftVideoSource||!r.characterCards.stoppedVideoPreview||r.characterCards.workbenchActions?.join(',')!=='thanks,greeting,present'||!r.characterCards.giftAnimation))process.exitCode=1;
  if(scene && !card && (!r.sceneMigration || r.stage?.scene?.ready!=='true' || r.stage?.scene?.hidden || !r.stage?.audioButtonHidden || !r.runtime?.active || r.runtime?.owner_role!=='obs' || r.workbench?.sceneReady!=='true' || r.workbench?.legacyMouth || !r.workbench?.selector || r.pixels?.legacyNodPixels!==0 || r.pixels?.changedLegPixels!==0 || !r.pixels?.changedClothPixels || r.pixels?.independentMouthElements!==0)) process.exitCode=1;
  if(process.env.YINGBO_SMOKE_CLIP&&(!r.actions?.naturalMotion||!r.actions?.sawClip||!r.actions?.sawSpeechAfter||r.actions?.overlap||!r.actions?.entryAlpha||!r.actions?.exitAlpha||!r.actions?.cancelled||r.actions?.glError!==0))process.exitCode=1;
});
