'use strict';
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const {spawnSync} = require('node:child_process');
const root = path.resolve(__dirname, '..');
const versions = JSON.parse(fs.readFileSync(path.join(root, 'runtime.versions.json'), 'utf8'));
const runtime = path.join(root, '.runtime');
const python = path.join(root, '.venv', 'Scripts', 'python.exe');
const uv = path.join(runtime, `uv-${versions.uv.version}`, 'uv.exe');
const nodeRoot = path.dirname(process.execPath);
const npm = path.join(nodeRoot, 'node_modules', 'npm', 'bin', 'npm-cli.js');
const stampPath = path.join(runtime, 'ready.json');
const action = process.argv[2] || 'setup';
const args = process.argv.slice(3);
let previous = {};
try {previous=JSON.parse(fs.readFileSync(stampPath,'utf8'));} catch {}
const withLive2D = args.includes('--with-live2d') || previous.withLive2D === true;
const env = {...process.env, PYTHONUTF8:'1', PYTHONUNBUFFERED:'1', UV_PYTHON_INSTALL_DIR:path.join(runtime,'python'),
  UV_PYTHON_BIN_DIR:path.join(runtime,'bin'),
  UV_DEFAULT_INDEX:process.env.UV_DEFAULT_INDEX || process.env.UV_INDEX_URL || versions.python_index,
  YINGBO_PYTHON:python,
  UV_CACHE_DIR:path.join(runtime,'cache','uv'), UV_PYTHON_PREFERENCE:'only-managed', UV_NO_PROGRESS:'1',
  npm_config_cache:path.join(runtime,'cache','npm'), ELECTRON_CACHE:path.join(runtime,'cache','electron'),
  electron_config_cache:path.join(runtime,'cache','electron'),
  ELECTRON_MIRROR:process.env.ELECTRON_MIRROR || versions.electron_mirror,
  ELECTRON_BUILDER_BINARIES_MIRROR:process.env.ELECTRON_BUILDER_BINARIES_MIRROR || versions.electron_builder_mirror,
  ELECTRON_BUILDER_CACHE:path.join(runtime,'cache','electron-builder'),
  PATH:nodeRoot + path.delimiter + process.env.PATH};
delete env.ELECTRON_RUN_AS_NODE;
function run(command, argv, options={}) {
  const result = spawnSync(command, argv, {cwd:root, env, stdio:'inherit', windowsHide:true, ...options});
  if (result.error) throw result.error;
  if (result.status !== 0) throw new Error(`${path.basename(command)} exited with code ${result.status}`);
  return result;
}
function fingerprint() {
  const hash = crypto.createHash('sha256');
  for (const file of ['runtime.versions.json','requirements-build.lock.txt','package-lock.json', ...(withLive2D?['requirements-live2d.lock.txt']:[])]) {
    hash.update(file); hash.update(fs.readFileSync(path.join(root,file)));
  }
  return hash.update(root).digest('hex');
}
function validPython() {
  if (!fs.existsSync(python)) return false;
  const test = spawnSync(python, ['-c', 'import sys,json;print(json.dumps([sys.prefix,sys.base_prefix,list(sys.version_info[:3])]))'], {env,encoding:'utf8',windowsHide:true});
  try {
    const [prefix,base,version] = JSON.parse(test.stdout.trim());
    return test.status===0 && path.resolve(prefix).toLowerCase()===path.join(root,'.venv').toLowerCase() &&
      path.resolve(base).toLowerCase().startsWith(path.join(runtime,'python').toLowerCase()+path.sep) && version.join('.')===versions.python;
  } catch {return false;}
}
function setup() {
  const digest=fingerprint();
  const toolReady=!withLive2D || fs.existsSync(path.join(runtime,`psd2live-${versions.psd2live.version}`,'runtime','bin','java.exe'));
  if (!args.includes('--force') && previous.fingerprint===digest && validPython() && toolReady && fs.existsSync(path.join(root,'node_modules','electron','dist','electron.exe'))) return;
  if (!validPython()) {
    const venv=path.join(root,'.venv');
    if (fs.existsSync(venv)) {
      const backup=path.join(runtime,`old-venv-${Date.now()}`);
      if(fs.lstatSync(venv).isSymbolicLink() || !path.resolve(backup).startsWith(path.resolve(runtime)+path.sep)) {
        throw new Error('Refusing to move a virtual environment outside this checkout.');
      }
      fs.renameSync(venv,backup);
      console.log(`Moved an incompatible virtual environment to ${backup}`);
    }
    run(uv,['python','install','--no-bin','--no-registry',versions.python]);
    run(uv,['venv','--python',versions.python,venv]);
  }
  const localWheels=path.join(runtime,'downloads','wheels');
  run(uv,['pip','sync','--require-hashes','--python',python,
    ...(fs.existsSync(localWheels)?['--find-links',localWheels]:[]),
    'requirements-build.lock.txt',...(withLive2D?['requirements-live2d.lock.txt']:[])]);
  run(process.execPath,[npm,'ci','--no-audit','--no-fund']);
  if(withLive2D) run(python,['scripts/fetch_runtime.py','psd2live']);
  run(python,['scripts/doctor.py',...(withLive2D?['--live2d']:[])]);
  fs.writeFileSync(stampPath,JSON.stringify({fingerprint:digest,withLive2D,python:versions.python,node:versions.node.version},null,2));
  console.log('Project-local environment ready.');
}
try {
  if(process.platform!=='win32'||process.arch!=='x64') throw new Error('Automatic bootstrap currently supports Windows x64.');
  setup();
  if(action==='setup') process.exitCode=0;
  else if(action==='start') run(path.join(root,'node_modules','electron','dist','electron.exe'),[root]);
  else if(action==='check') {
    run(python,['scripts/doctor.py',...(withLive2D?['--live2d']:[])]);
    run(python,['-m','unittest','discover','-s','tests','-v']);
    run(process.execPath,[npm,'run','test:desktop']);
    run(process.execPath,[npm,'run','smoke:desktop']);
  } else if(action==='build') {
    run(python,['scripts/build_backend.py','--clean']);
    const target=args[args.indexOf('--target')+1]||'portable';
    run(process.execPath,[npm,'run',target==='directory'?'pack':'dist:win']);
  } else throw new Error(`Unknown action: ${action}`);
} catch(error) {console.error(error.message);process.exitCode=1;}
