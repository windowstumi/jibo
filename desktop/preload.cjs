const {contextBridge, ipcRenderer} = require('electron');

// A narrow bridge; no filesystem, process execution, or general IPC exposed.
contextBridge.exposeInMainWorld('yingboDesktop', {
  info: () => ipcRenderer.invoke('desktop:info'),
  openStage: () => ipcRenderer.invoke('desktop:stage'),
  exportProject: () => ipcRenderer.invoke('desktop:export'),
  importProject: () => ipcRenderer.invoke('desktop:import'),
  openData: () => ipcRenderer.invoke('desktop:data'),
  copyStageUrl: () => ipcRenderer.invoke('desktop:copy-stage')
});
