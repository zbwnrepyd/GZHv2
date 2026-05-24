// Markdown → 卡片数据解析器
// 解析 Module 2 输出的 Markdown，按 ## 卡片N 标题分割为7个卡片数据对象

function parseCardMarkdown(markdown) {
  const sections = [];
  const lines = markdown.split('\n');
  let currentSection = null;
  let currentLines = [];

  for (const line of lines) {
    const h2Match = line.match(/^##\s*卡片(\d+)/);
    if (h2Match) {
      if (currentSection !== null) {
        sections.push({ index: currentSection, content: currentLines.join('\n') });
      }
      currentSection = parseInt(h2Match[1]);
      currentLines = [line];
    } else if (currentSection !== null) {
      currentLines.push(line);
    }
  }
  if (currentSection !== null && currentLines.length > 0) {
    sections.push({ index: currentSection, content: currentLines.join('\n') });
  }

  return sections;
}

/**
 * 从 Markdown 段落中提取键值对
 * 支持的格式：
 *   **标签**：值
 *   # 标题
 *   - 列表项
 *   ![图片](path)
 */
function extractCardData(section, cardIndex) {
  const data = {};
  const lines = section.content.split('\n');

  // 提取卡片标题
  const titleMatch = lines[0]?.match(/卡片\d+：(.+)/);
  if (titleMatch) {
    data._title = titleMatch[1].trim();
  }

  // 提取键值对
  for (const line of lines) {
    const kvMatch = line.match(/\*\*(.+?)\*\*[：:]\s*(.*)/);
    if (kvMatch) {
      const key = kvMatch[1].trim();
      const value = kvMatch[2].trim();
      data[key] = value;
    }

    // 提取图片
    const imgMatch = line.match(/!\[.*?\]\((.+?)\)/);
    if (imgMatch) {
      const imgPath = imgMatch[1].trim();
      if (!imgPath.startsWith('http')) {
        data._image = imgPath;
      }
    }

    // 提取一级标题（公司名）
    const h1Match = line.match(/^#\s+(.+)/);
    if (h1Match && cardIndex === 1) {
      data['公司名'] = h1Match[1].trim();
    }
  }

  return data;
}

/**
 * 解析完整 Markdown，返回 { 1: {...data}, 2: {...data}, ... }
 */
function parseFullMarkdown(markdown) {
  const sections = parseCardMarkdown(markdown);
  const result = {};
  for (const section of sections) {
    result[section.index] = extractCardData(section, section.index);
  }
  return result;
}
