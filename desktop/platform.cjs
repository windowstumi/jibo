const path = require('node:path');

function backendCommand({packaged, resourcesPath, root, platform = process.platform, python}) {
  if (packaged) return {command:path.join(resourcesPath, 'backend', 'yingbo-backend' + (platform === 'win32' ? '.exe' : '')), args:[]};
  return {command:python || path.join(root, '.venv', platform === 'win32' ? 'Scripts/python.exe' : 'bin/python'), args:[path.join(root, 'backend_entry.py')]};
}

function chooseDataRoot({env = process.env, userData}) {
  if (env.YINGBO_DATA_DIR) return path.resolve(env.YINGBO_DATA_DIR);
  if (env.PORTABLE_EXECUTABLE_DIR) return path.join(env.PORTABLE_EXECUTABLE_DIR, 'YingboData');
  return path.join(userData, 'data');
}

function isLocalUrl(url, origin) {
  try {return new URL(url).origin === origin;} catch {return false;}
}

module.exports = {backendCommand, chooseDataRoot, isLocalUrl};
