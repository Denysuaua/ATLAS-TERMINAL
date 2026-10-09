// Обёртка Electron: то же окно, что atlas_dashboard.html в браузере. Без доступа к Node из страницы.
const { app, BrowserWindow } = require("electron");
const path = require("path");
const fs = require("fs");

function createWindow() {
  // Библиотека графиков — из node_modules рядом со страницей: пульт работает без интернета.
  const lib = path.join(__dirname, "node_modules", "lightweight-charts", "dist", "lightweight-charts.standalone.production.js");
  const local = path.join(__dirname, "lightweight-charts.standalone.production.js");
  if (fs.existsSync(lib) && !fs.existsSync(local)) fs.copyFileSync(lib, local);
  const win = new BrowserWindow({
    width: 1500, height: 900, title: "Атлас — пульт",
    webPreferences: { contextIsolation: true, nodeIntegration: false, sandbox: true }
  });
  win.setMenuBarVisibility(false);
  win.loadFile(path.join(__dirname, "atlas_dashboard.html"));
}

app.whenReady().then(createWindow);
app.on("window-all-closed", () => app.quit());
