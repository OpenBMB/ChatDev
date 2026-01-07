<script setup>
import { ref, onMounted, nextTick } from 'vue'
import MarkdownIt from 'markdown-it'
import markdownItAnchor from 'markdown-it-anchor'

const renderedContent = ref('')
const currentLang = ref('en') // 'zh' for Chinese, 'en' for English
const markdownBody = ref(null)
const md = new MarkdownIt({
  html: true,
  linkify: true,
  typographer: true
})
md.use(markdownItAnchor, {
  permalink: markdownItAnchor.permalink.ariaHidden({
    placement: 'before',
    symbol: '#',
    space: true,
    class: 'header-anchor'
  }),
  slugify: s =>
    s
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9\u4e00-\u9fa5\s-]/g, '')
      .replace(/\s+/g, '-')
})

const getTutorialFile = () => (currentLang.value === 'en' ? '/tutorial-en.md' : '/tutorial-zh.md')

const addCopyButtons = () => {
  nextTick(() => {
    const container = markdownBody.value
    if (!container) return
    const blocks = container.querySelectorAll('pre')
    blocks.forEach((block) => {
      if (block.querySelector('.copy-code-btn')) return
      const button = document.createElement('button')
      button.type = 'button'
      button.className = 'copy-code-btn'
      button.textContent = 'Copy'
      button.addEventListener('click', async () => {
        const code = block.querySelector('code')
        const text = code ? code.innerText : block.innerText
        try {
          await navigator.clipboard.writeText(text)
          button.textContent = 'Copied'
          setTimeout(() => {
            button.textContent = 'Copy'
          }, 1200)
        } catch (error) {
          console.error('Failed to copy code: ', error)
        }
      })
      block.classList.add('has-copy-button')
      block.appendChild(button)
    })
  })
}

const loadTutorial = async () => {
  try {
    const response = await fetch(getTutorialFile())
    if (response.ok) {
      let text = await response.text()
      // Fix media paths to point to /media/ (absolute path from public root)
      // For markdown images: ![alt](media/file.png) -> ![alt](/media/file.png)
      text = text.replace(/\]\(media\//g, '](/media/')
      // For HTML image tags: src="media/file.gif" -> src="/media/file.gif"
      text = text.replace(/src="media\//g, 'src="/media/')
      
      renderedContent.value = md.render(text)
      addCopyButtons()
    } else {
      console.error('Failed to fetch tutorial markdown')
    }
  } catch (error) {
    console.error('Failed to load tutorial:', error)
  }
}

const switchLang = (lang) => {
  if (currentLang.value !== lang) {
    currentLang.value = lang
    loadTutorial()
  }
}

onMounted(() => {
  loadTutorial()
})
</script>

<template>
  <div class="tutorial-view">
    <div class="lang-switch">
      <button :class="{ active: currentLang === 'zh' }" @click="switchLang('zh')">中文</button>
      <button :class="{ active: currentLang === 'en' }" @click="switchLang('en')">English</button>
    </div>
    <div ref="markdownBody" class="markdown-body" v-html="renderedContent"></div>
  </div>
</template>

<style scoped>
.tutorial-view {
  padding: 40px;
  width: 100%;
  max-width: 100%;
  margin: 0 auto;
  height: 100vh;
  background: linear-gradient(135deg, #232526 0%, #1e1e1e 100%);
  overflow-y: auto;
  overflow-x: hidden;
  box-sizing: border-box;
  /* Glowing border and card shadow */
  border-radius: 18px;
  box-shadow: 0 4px 32px 0 rgba(0, 255, 255, 0.08), 0 0 0 2px #00eaff33;
  border: 1.5px solid #00eaff33;
  transition: box-shadow 0.3s;
}

.lang-switch {
  position: absolute;
  top: 80px; /* Move down from 32px to 80px */
  right: 48px;
  z-index: 10;
  display: flex;
  gap: 12px;
}
.lang-switch button {
  background: linear-gradient(90deg, #232526 60%, #00eaff22 100%);
  color: #00eaff;
  border: 1.5px solid #00eaff33;
  border-radius: 8px;
  padding: 6px 18px;
  font-size: 1em;
  font-family: inherit;
  cursor: pointer;
  transition: background 0.2s, color 0.2s, border 0.2s, box-shadow 0.2s;
  box-shadow: 0 2px 8px #00eaff11;
}
.lang-switch button.active,
.lang-switch button:hover {
  background: linear-gradient(90deg, #00eaff 0%, #232526 100%);
  color: #fff;
  border: 1.5px solid #00eaff;
  box-shadow: 0 0 12px #00eaff44;
}

:deep(.markdown-body) {
  max-width: 980px;
  margin: 0 auto;
  color: #e0e0e0;
  font-family: 'JetBrains Mono', 'Fira Mono', 'Consolas', 'Menlo', 'Monaco', 'monospace', -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial, sans-serif;
  line-height: 1.7;
  letter-spacing: 0.01em;
  background: rgba(30,34,40,0.85);
  border-radius: 14px;
  box-shadow: 0 2px 16px 0 rgba(0,255,255,0.04);
  padding: 32px 36px 32px 36px;
  border: 1px solid #00eaff22;
  backdrop-filter: blur(2px);
}

:deep(.markdown-body h1),
:deep(.markdown-body h2),
:deep(.markdown-body h3),
:deep(.markdown-body h4),
:deep(.markdown-body h5),
:deep(.markdown-body h6) {
  margin-top: 24px;
  margin-bottom: 16px;
  font-weight: 700;
  line-height: 1.25;
  color: #00eaff;
  text-shadow: 0 0 8px #00eaff44;
  letter-spacing: 0.02em;
}

:deep(.markdown-body h1) { font-size: 2.2em; border-bottom: 1px solid #00eaff33; padding-bottom: 0.3em; }
:deep(.markdown-body h2) { font-size: 1.6em; border-bottom: 1px solid #00eaff22; padding-bottom: 0.3em; }
:deep(.markdown-body h3) { font-size: 1.3em; }

:deep(.markdown-body p) {
  margin-top: 0;
  margin-bottom: 16px;
  color: #b8eaff;
  font-size: 1.08em;
}

:deep(.markdown-body a) {
  color: #00eaff;
  text-decoration: none;
  border-bottom: 1px dashed #00eaff99;
  transition: color 0.2s, border-bottom 0.2s;
}
:deep(.markdown-body a:hover) {
  color: #fff;
  border-bottom: 1px solid #00eaff;
  text-shadow: 0 0 6px #00eaff99;
}

:deep(.markdown-body img) {
  width: 100%;
  max-width: 100%;
  box-sizing: border-box;
  background-color: transparent;
  border-radius: 10px;
  border: 1.5px solid #00eaff33;
  box-shadow: 0 2px 16px 0 #00eaff22;
  margin: 16px 0;
  transition: box-shadow 0.2s;
}
:deep(.markdown-body img:hover) {
  box-shadow: 0 0 24px 2px #00eaff88;
}

:deep(.markdown-body video) {
  max-width: 100%;
  border-radius: 10px;
  border: 1.5px solid #00eaff33;
  margin-bottom: 16px;
  box-shadow: 0 2px 16px 0 #00eaff22;
}

:deep(.markdown-body code) {
  padding: 0.2em 0.5em;
  margin: 0;
  font-size: 90%;
  background: linear-gradient(90deg, #232526 60%, #00eaff22 100%);
  border-radius: 6px;
  color: #00eaff;
  font-family: 'JetBrains Mono', 'Fira Mono', 'Consolas', 'Menlo', 'Monaco', 'monospace';
  border: 1px solid #00eaff33;
  box-shadow: 0 0 8px #00eaff22;
}

:deep(.markdown-body pre) {
  padding: 18px 20px;
  overflow: auto;
  font-size: 95%;
  line-height: 1.55;
  background: linear-gradient(90deg, #161b22 80%, #00eaff11 100%);
  border-radius: 10px;
  margin-bottom: 18px;
  border: 1.5px solid #00eaff33;
  box-shadow: 0 0 16px #00eaff11;
  position: relative;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

:deep(.markdown-body pre code) {
  display: inline;
  padding: 0;
  margin: 0;
  overflow: visible;
  line-height: inherit;
  word-wrap: normal;
  background: transparent;
  border: 0;
  color: #00eaff;
  white-space: pre-wrap;
  overflow-wrap: anywhere;
}

:deep(.markdown-body pre.has-copy-button) {
  padding-top: 44px;
}

:deep(.markdown-body .copy-code-btn) {
  position: absolute;
  top: 10px;
  right: 10px;
  background: linear-gradient(90deg, #232526 60%, #00eaff22 100%);
  color: #00eaff;
  border: 1px solid #00eaff44;
  border-radius: 6px;
  padding: 4px 10px;
  font-size: 0.85em;
  cursor: pointer;
  transition: background 0.2s, color 0.2s, border 0.2s, box-shadow 0.2s;
  box-shadow: 0 2px 8px #00eaff11;
}

:deep(.markdown-body .copy-code-btn:hover) {
  background: linear-gradient(90deg, #00eaff 0%, #232526 100%);
  color: #fff;
  border: 1px solid #00eaff;
  box-shadow: 0 0 12px #00eaff44;
}

:deep(.markdown-body blockquote) {
  padding: 0 1em;
  color: #8bffe6;
  border-left: 0.25em solid #00eaff99;
  margin: 0 0 16px 0;
  background: rgba(0,234,255,0.04);
  border-radius: 6px;
}

:deep(.markdown-body hr) {
  height: 0.25em;
  padding: 0;
  margin: 24px 0;
  background: linear-gradient(90deg, #00eaff33 0%, #232526 100%);
  border: 0;
  border-radius: 2px;
}

:deep(.markdown-body table) {
  border-spacing: 0;
  border-collapse: collapse;
  margin-top: 0;
  margin-bottom: 16px;
  width: 100%;
  overflow: auto;
  background: rgba(0,234,255,0.02);
  border-radius: 8px;
}

:deep(.markdown-body table th),
:deep(.markdown-body table td) {
  padding: 8px 15px;
  border: 1px solid #00eaff22;
}

:deep(.markdown-body table th) {
  font-weight: 700;
  background: rgba(0,234,255,0.08);
  color: #00eaff;
}

:deep(.markdown-body table tr) {
  background: rgba(30,34,40,0.7);
  border-top: 1px solid #00eaff11;
}

:deep(.markdown-body table tr:nth-child(2n)) {
  background: rgba(0,234,255,0.03);
}

/* Custom Scrollbar */
.tutorial-view::-webkit-scrollbar {
  width: 10px;
  background: #232526;
}
.tutorial-view::-webkit-scrollbar-thumb {
  background: linear-gradient(135deg, #00eaff 0%, #232526 100%);
  border-radius: 8px;
}

:deep(.markdown-body::-webkit-scrollbar) {
  height: 8px;
  background: #232526;
}
:deep(.markdown-body::-webkit-scrollbar-thumb) {
  background: linear-gradient(90deg, #00eaff 0%, #232526 100%);
  border-radius: 8px;
}
</style>
