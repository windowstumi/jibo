// Run against a prepared component. --data is an explicitly selected data folder.
const {spawn}=require('node:child_process');
const fs=require('node:fs');
const path=require('node:path');
const os=require('node:os');
const root=path.resolve(__dirname,'..');
const dataIndex=process.argv.indexOf('--data');
if(dataIndex<0||!process.argv[dataIndex+1])throw Error('Specify --data <prepared data folder>');
const data=path.resolve(process.argv[dataIndex+1]);
if(!fs.existsSync(path.join(data,'local-tts','installed.json')))throw Error('A real prepared component is required');
const exeIndex=process.argv.indexOf('--exe');
const exe=exeIndex>=0?path.resolve(process.argv[exeIndex+1]):require('electron');
const folder=fs.mkdtempSync(path.join(os.tmpdir(),'jibo-local-voice-'));
const report=path.join(folder,'report.json');
const {ELECTRON_RUN_AS_NODE,...env}=process.env;
const child=spawn(exe,exeIndex>=0?[]:[root],{cwd:root,env:{...env,YINGBO_SMOKE_REPORT:report,
  JIBO_SMOKE_LOCAL_TTS_ACTIVE:'1',JIBO_DATA_DIR:data,YINGBO_DATA_DIR:data,YINGBO_PORT:'0'},stdio:'inherit'});
const timer=setTimeout(()=>{child.kill();console.error('Local voice acceptance timed out:',folder);process.exitCode=1;},300000);
child.on('error',error=>{clearTimeout(timer);console.error(error);process.exitCode=1;});
child.on('exit',()=>{
  clearTimeout(timer);
  if(!fs.existsSync(report)){console.error('Missing local voice report:',folder);process.exitCode=1;return;}
  const result=JSON.parse(fs.readFileSync(report,'utf8'));console.log(JSON.stringify(result,null,2));
  if(result.error||!result.localTts?.ready||!result.localTts.played||!result.localTts.cached||
     !result.localTts.loadingDialog||result.localTts.provider!=='local')process.exitCode=1;
});
