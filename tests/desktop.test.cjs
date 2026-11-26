const test = require('node:test');
const assert = require('node:assert/strict');
const path = require('node:path');
const {backendCommand,chooseDataRoot,isLocalUrl} = require('../desktop/platform.cjs');

test('bundled sidecar resolves independently of working directory',()=>{
  for (const platform of ['win32','darwin','linux']) {
    const result=backendCommand({packaged:true,resourcesPath:'/app/resources',root:'/unused',platform});
    assert.equal(result.command,path.join('/app/resources','backend','jibo-backend'+(platform==='win32'?'.exe':'')));
    assert.deepEqual(result.args,[]);
  }
});
test('development interpreter changes on each platform',()=>{
  assert.equal(backendCommand({packaged:false,root:'/code',platform:'win32'}).command,path.join('/code','.venv','Scripts/python.exe'));
  assert.equal(backendCommand({packaged:false,root:'/code',platform:'linux'}).command,path.join('/code','.venv','bin/python'));
});
test('portable storage is beside original executable, not temporary extraction',()=>{
  assert.equal(chooseDataRoot({env:{PORTABLE_EXECUTABLE_DIR:'/usb/yingbo'},userData:'/user'}),path.join('/usb/yingbo','JiboData'));
  assert.equal(chooseDataRoot({env:{},userData:'/user'}),path.join('/user','data'));
  assert.equal(chooseDataRoot({env:{YINGBO_DATA_DIR:'/custom'},userData:'/user'}),path.resolve('/custom'));
});
test('desktop navigation and bridge reject external origins',()=>{
  assert.equal(isLocalUrl('http://127.0.0.1:123/a','http://127.0.0.1:123'),true);
  for(const url of ['file:///etc/passwd','https://example.com','http://127.0.0.1:124','javascript:alert(1)']) assert.equal(isLocalUrl(url,'http://127.0.0.1:123'),false);
});
