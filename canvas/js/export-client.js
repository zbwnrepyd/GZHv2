const ExportClient = {
  safeName(value) {
    return String(value || 'company').replace(/[/\\?%*:|"<>]/g, '_');
  },

  exportCurrent(workbench) {
    const url = workbench.cardUrl();
    window.open(url, '_blank');
    workbench.setStatus('已打开单张卡片页面，可用 Puppeteer 或浏览器截图导出。', 'info');
  },

  exportAll(workbench) {
    const company = this.safeName(workbench.companyName);
    const command = `node canvas/screenshot.js --company ${company} --base-url ${window.location.origin} --out output/cards/${company}`;
    navigator.clipboard?.writeText(command);
    workbench.setStatus(`导出命令已准备：${command}`, 'info');
  },
};
