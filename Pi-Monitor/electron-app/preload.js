'use strict';

const { contextBridge, ipcRenderer } = require('electron');

// Minimal, explicit bridge — the renderer never touches Node or the network directly.
contextBridge.exposeInMainWorld('api', {
  onMetrics: (cb) => ipcRenderer.on('metrics', (_e, payload) => cb(payload)),
  onConfig: (cb) => ipcRenderer.on('config', (_e, c) => cb(c)),
  getConfig: () => ipcRenderer.invoke('get-config'),
  setConfig: (partial) => ipcRenderer.invoke('set-config', partial),
});
