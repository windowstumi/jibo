const {contextBridge, ipcRenderer} = require('electron');

// A narrow bridge; no filesystem, process execution, or general IPC exposed.
const bridge={
  info: () => ipcRenderer.invoke('desktop:info'),
  openStage: () => ipcRenderer.invoke('desktop:stage'),
  exportProject: () => ipcRenderer.invoke('desktop:export'),
  importProject: () => ipcRenderer.invoke('desktop:import'),
  openData: () => ipcRenderer.invoke('desktop:data'),
  copyStageUrl: () => ipcRenderer.invoke('desktop:copy-stage'),
  obsConnect:()=>ipcRenderer.invoke('desktop:obs-connect'),
  obsSetup:id=>ipcRenderer.invoke('desktop:obs-setup',id),
  obsPresent:kind=>ipcRenderer.invoke('desktop:obs-present',kind),
  obsSpeaking:value=>ipcRenderer.invoke('desktop:obs-speaking',value),
  obsStatus:()=>ipcRenderer.invoke('desktop:obs-status')
};
contextBridge.exposeInMainWorld('jiboDesktop',bridge);
contextBridge.exposeInMainWorld('yingboDesktop',bridge); // Existing renderer integrations remain readable.
