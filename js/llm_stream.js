import { app } from "../../scripts/app.js";

// ============================================
// 极简 Markdown 解析器（纯本地，无依赖）
// ============================================
function markdownToHtml(text) {
    if (!text) return "";

    // 转义 HTML 特殊字符（防止 XSS）
    const escapeHtml = (str) => {
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    };

    // 先转义全文
    let html = escapeHtml(text);

    // 1. 标题 (# 到 ######)
    html = html.replace(/^###### (.*?)$/gm, '<h6>$1</h6>');
    html = html.replace(/^##### (.*?)$/gm, '<h5>$1</h5>');
    html = html.replace(/^#### (.*?)$/gm, '<h4>$1</h4>');
    html = html.replace(/^### (.*?)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.*?)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.*?)$/gm, '<h1>$1</h1>');

    // 2. 粗体 **bold** 或 __bold__
    html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    html = html.replace(/__(.*?)__/g, '<strong>$1</strong>');

    // 3. 斜体 *italic* 或 _italic_
    html = html.replace(/\*(.*?)\*/g, '<em>$1</em>');
    html = html.replace(/_(.*?)_/g, '<em>$1</em>');

    // 4. 行内代码 `code`
    html = html.replace(/`(.*?)`/g, '<code>$1</code>');

    // 5. 代码块 ```code```
    html = html.replace(/```(.*?)```/gs, '<pre><code>$1</code></pre>');

    // 6. 链接 [text](url)
    html = html.replace(/\[(.*?)\]\((.*?)\)/g, '<a href="$2" target="_blank" rel="noopener">$1</a>');

    // 7. 无序列表 - item 或 * item
    let inList = false;
    const lines = html.split('\n');
    const processedLines = [];
    for (let line of lines) {
        const ulMatch = line.match(/^[\-\*] (.*)$/);
        const olMatch = line.match(/^\d+\. (.*)$/);
        if (ulMatch) {
            if (!inList || inList !== 'ul') {
                if (inList) processedLines.push('</ul>');
                processedLines.push('<ul>');
                inList = 'ul';
            }
            processedLines.push(`<li>${ulMatch[1]}</li>`);
        } else if (olMatch) {
            if (!inList || inList !== 'ol') {
                if (inList) processedLines.push('</ol>');
                processedLines.push('<ol>');
                inList = 'ol';
            }
            processedLines.push(`<li>${olMatch[1]}</li>`);
        } else {
            if (inList) {
                processedLines.push(inList === 'ul' ? '</ul>' : '</ol>');
                inList = false;
            }
            processedLines.push(line);
        }
    }
    if (inList) processedLines.push(inList === 'ul' ? '</ul>' : '</ol>');
    html = processedLines.join('\n');

    // 8. 换行转 <br>（保留空行）
    html = html.replace(/\n/g, '<br>');

    // 9. 清理多余的 <br> 紧邻块级标签
    html = html.replace(/<br>\s*(<\/[hH]|<\/[pP]|<\/[uU]|<\/[oO]|<\/[lL])/g, '$1');

    return html;
}

// ============================================
// 注册 ComfyUI 扩展
// ============================================
app.registerExtension({
    name: "LLM.StreamUI.Pro",

    async beforeRegisterNodeDef(nodeType, nodeData) {
        if (nodeData.name !== "LLMStreamUI") return;

        const origOnNodeCreated = nodeType.prototype.onNodeCreated;

        nodeType.prototype.onNodeCreated = function () {
            const result = origOnNodeCreated?.apply(this, arguments);

            if (!this.streamContainer) {
                // 创建容器
                const div = document.createElement("div");
                Object.assign(div.style, {
                    width: "100%",
                    minHeight: "150px",
                    maxHeight: "500px",
                    overflowY: "auto",
                    background: "#fafafa",
                    color: "#1e1e1e",
                    padding: "12px 16px",
                    fontSize: "13px",
                    fontFamily: "'Segoe UI', 'Helvetica Neue', Arial, sans-serif",
                    lineHeight: "1.6",
                    borderRadius: "8px",
                    border: "1px solid #ddd",
                    boxSizing: "border-box"
                });

                // 添加内置样式（让代码块好看）
                const style = document.createElement('style');
                style.textContent = `
                    .llm-markdown-content h1 { font-size: 1.4em; margin: 0.5em 0; }
                    .llm-markdown-content h2 { font-size: 1.2em; margin: 0.5em 0; }
                    .llm-markdown-content h3 { font-size: 1.1em; margin: 0.4em 0; }
                    .llm-markdown-content code { background: #eee; padding: 2px 4px; border-radius: 3px; font-family: monospace; font-size: 0.9em; }
                    .llm-markdown-content pre { background: #f0f0f0; padding: 8px; border-radius: 5px; overflow-x: auto; margin: 8px 0; }
                    .llm-markdown-content pre code { background: none; padding: 0; }
                    .llm-markdown-content a { color: #0366d6; text-decoration: none; }
                    .llm-markdown-content a:hover { text-decoration: underline; }
                    .llm-markdown-content ul, .llm-markdown-content ol { margin: 0.5em 0; padding-left: 1.5em; }
                    .llm-markdown-content li { margin: 0.2em 0; }
                `;
                div.appendChild(style);
                div.classList.add('llm-markdown-content');

                div.innerText = "等待输出...";
                this.addDOMWidget("stream_output", "custom", div, { serialize: false });
                this.streamContainer = div;
                this.fullText = "";

                // 设置节点最小高度
                if (this.size[1] < 300) this.setSize([this.size[0], 300]);

                console.log(`[LLM.StreamUI.Pro] 节点已创建: ID=${this.id}`);
            }
            return result;
        };
    },

    setup() {
        console.log("[LLM.StreamUI.Pro] 扩展已加载，等待流式更新...");

        app.api.addEventListener("llm_stream_update", (event) => {
            const { node_id, delta } = event.detail || {};
            if (!node_id || !delta) {
                console.warn("[LLM.StreamUI.Pro] 收到无效事件", event.detail);
                return;
            }

            const node = app.graph.getNodeById(node_id);
            if (!node || !node.streamContainer) {
                console.warn(`[LLM.StreamUI.Pro] 未找到节点 ${node_id} 或其容器`);
                return;
            }

            // 累积全文
            if (node.fullText === undefined) node.fullText = "";
            node.fullText += delta;

            const el = node.streamContainer;
            // 清除初始占位符
            if (el.innerText === "等待输出..." && node.fullText === delta) {
                el.innerText = "";
            }

            try {
                // 渲染 Markdown
                const html = markdownToHtml(node.fullText);
                el.innerHTML = html;
                // 自动滚动到底部
                el.scrollTop = el.scrollHeight;
                // 轻微刷新画布
                app.graph.setDirtyCanvas(true, false);
            } catch (err) {
                console.error("[LLM.StreamUI.Pro] 渲染错误:", err);
                el.innerText = node.fullText; // 降级显示纯文本
            }
        });
    }
});