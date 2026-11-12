const { contextBridge, ipcRenderer } = require('electron');

contextBridge.exposeInMainWorld('electronAPI', {
  selectMboxFile: () => ipcRenderer.invoke('dialog:selectMboxFile'),
  openExternal: (url) => ipcRenderer.invoke('shell:openExternal', url)
});
