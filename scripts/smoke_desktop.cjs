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
const scene=process.argv[3];
if(scene){const source=path.resolve(scene);fs.mkdirSync(path.join(temp,'data','scenes'),{recursive:true});fs.cpSync(source,path.join(temp,'data','scenes',path.basename(source)),{recursive:true});}
const proc=spawn(target,packaged?[]:[root],{cwd:root,env:{...env,YINGBO_SMOKE_REPORT:report,YINGBO_DATA_DIR:path.join(temp,'data'),YINGBO_PORT:'0',...(scene?{YINGBO_SMOKE_SCENE:'1'}:{})},stdio:'inherit'});
const timer=setTimeout(()=>{proc.kill();console.error('Desktop smoke timeout: '+temp);process.exitCode=1;},90000);
proc.on('error',e=>{clearTimeout(timer);console.error(e);process.exitCode=1;});
proc.on('exit',()=>{
  clearTimeout(timer);
  if(!fs.existsSync(report)){console.error('Missing smoke report: '+temp);process.exitCode=1;return;}
  const r=JSON.parse(fs.readFileSync(report,'utf8'));
  console.log(JSON.stringify(r,null,2));
  if(r.error || !r.main?.bridge || r.main.cards<5) process.exitCode=1;
  if(!scene && (!r.noSceneBlocked || !r.noLegacyRenderer)) process.exitCode=1;
  if(scene && (!r.sceneMigration || r.stage?.scene?.ready!=='true' || r.stage?.scene?.hidden || !r.stage?.audioButtonHidden || !r.runtime?.active || r.runtime?.owner_role!=='obs' || r.workbench?.sceneReady!=='true' || r.workbench?.legacyMouth || !r.workbench?.selector || r.pixels?.changedLegPixels!==0 || !r.pixels?.changedClothPixels || r.pixels?.independentMouthElements!==0)) process.exitCode=1;
});
