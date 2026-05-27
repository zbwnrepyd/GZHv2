const PromptBar = {
  getCompanyName: () => '',
  getCurrentCard: () => 1,
  getCardData: () => ({}),
  refreshPreview: () => {},
  setStatus: () => {},
  runtimeApiKey: '',

  init({ getCompanyName, getCurrentCard, getCardData, refreshPreview, setStatus }) {
    this.getCompanyName = getCompanyName;
    this.getCurrentCard = getCurrentCard;
    this.getCardData = getCardData;
    this.refreshPreview = refreshPreview;
    this.setStatus = setStatus;

    document.getElementById('btn-reset-prompt')?.addEventListener('click', () => this.resetPrompt());
    document.getElementById('btn-generate-image')?.addEventListener('click', () => this.generateImage());
    document.getElementById('prompt-input')?.addEventListener('change', () => this.savePrompt());
    document.getElementById('image-api-key')?.addEventListener('input', (event) => {
      this.runtimeApiKey = event.target.value;
    });
  },

  promptKey() {
    return `aistartups.cardPrompts.${this.getCompanyName() || 'default'}`;
  },

  imageKey() {
    return `aistartups.cardImages.${this.getCompanyName() || 'default'}`;
  },

  apiUrlKey() {
    return `aistartups.imageApiUrl.${this.getCompanyName() || 'default'}`;
  },

  loadMap(key) {
    try {
      return JSON.parse(localStorage.getItem(key) || '{}');
    } catch {
      return {};
    }
  },

  saveMap(key, value) {
    localStorage.setItem(key, JSON.stringify(value));
  },

  syncApiConfig() {
    const urlInput = document.getElementById('image-api-url');
    if (!urlInput) return;
    if (!urlInput.value) {
      urlInput.value = localStorage.getItem(this.apiUrlKey()) || '';
    }
  },

  saveApiConfig() {
    const apiUrl = document.getElementById('image-api-url')?.value.trim() || '';
    if (apiUrl) {
      localStorage.setItem(this.apiUrlKey(), apiUrl);
    }
    return {
      image_api_url: apiUrl,
      image_api_key: this.runtimeApiKey,
    };
  },

  defaultPrompt() {
    const cardIndex = this.getCurrentCard();
    const cardData = this.getCardData();
    const title = cardData._title || cardData['公司名'] || `卡片${cardIndex}`;
    const values = Object.entries(cardData)
      .filter(([key, value]) => !key.startsWith('_') && value)
      .slice(0, 3)
      .map(([key, value]) => `${key}：${String(value).slice(0, 36)}`)
      .join('；');
    return `极简 iOS 毛玻璃边框内的抽象插图，主题：${title} ${values}，白色背景，低饱和青蓝色，矢量插画，无文字，无水印，适合知识卡片。`;
  },

  getPrompt() {
    const prompts = this.loadMap(this.promptKey());
    return prompts[this.getCurrentCard()] || this.defaultPrompt();
  },

  savePrompt() {
    const prompts = this.loadMap(this.promptKey());
    prompts[this.getCurrentCard()] = document.getElementById('prompt-input').value.trim();
    this.saveMap(this.promptKey(), prompts);
  },

  resetPrompt() {
    const prompts = this.loadMap(this.promptKey());
    delete prompts[this.getCurrentCard()];
    this.saveMap(this.promptKey(), prompts);
    this.syncPromptInput();
    this.setStatus(`卡片 ${this.getCurrentCard()} 的提示词已恢复预设。`, 'success');
  },

  syncPromptInput() {
    const input = document.getElementById('prompt-input');
    if (input) input.value = this.getPrompt();
    this.syncApiConfig();
  },

  getImageForCard(cardIndex) {
    const images = this.loadMap(this.imageKey());
    return images[cardIndex || this.getCurrentCard()] || '';
  },

  async generateImage() {
    const prompt = document.getElementById('prompt-input').value.trim();
    if (!prompt) {
      this.setStatus('提示词为空。', 'error');
      return;
    }
    this.savePrompt();
    const cardIndex = this.getCurrentCard();
    try {
      this.setStatus(`正在生成卡片 ${cardIndex} 图片...`, 'info');
      const response = await fetch('/api/generate-image', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          company_name: this.getCompanyName(),
          field_name: `card_${cardIndex}_image`,
          prompt,
          ...this.saveApiConfig(),
        }),
      });
      if (!response.ok) throw new Error(await response.text());
      const result = await response.json();
      const images = this.loadMap(this.imageKey());
      images[cardIndex] = result.img_path;
      this.saveMap(this.imageKey(), images);
      this.setStatus(`卡片 ${cardIndex} 图片已生成。`, 'success');
      await this.refreshPreview();
    } catch (error) {
      this.setStatus(`图片生成失败：${error.message}`, 'error');
    }
  },
};
