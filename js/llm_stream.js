import { app } from "../../scripts/app.js";

// ============================================
// 极简 Markdown 解析器（纯本地，无依赖）
// ============================================
function markdownToHtml(text) {
    if (!text) return "";
    
    const escapeHtml = (str) => {
        return str
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;");
    };

    const safeUrl = (url) => {
        const decoded = url.replace(/&amp;/g, '&');
        if (/^\s*(javascript|data|vbscript):/i.test(decoded)) {
            return "#";
        }
        return url;
    };

    const parseInlineMarkdown = (str) => {
        return str
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            .replace(/__(.*?)__/g, '<strong>$1</strong>')
            .replace(/\*([^\*]+?)\*/g, '<em>$1</em>')
            .replace(/_([^_]+?)_/g, '<em>$1</em>')
            .replace(/`([^`]+?)`/g, '<code>$1</code>')
            .replace(/\[(.*?)\]\((.*?)\)/g, (_, t, u) => 
                `<a href="${safeUrl(u)}" target="_blank" rel="noopener">${escapeHtml(t)}</a>`);
    };

    let html = escapeHtml(text).replace(/\r\n/g, '\n');

    const codeBlocks = [];
    let blockIndex = 0;
    html = html.replace(/```(?:[ \t]*([a-zA-Z0-9_\-\+]+)\n)?([\s\S]*?)```/g, (_, lang, code) => {
        codeBlocks[blockIndex] = code.replace(/^\n/, '');
        return `%%CODEBLOCK${blockIndex++}%%`;
    });

    html = html.replace(/^###### (.*?)$/gm, '<h6>$1</h6>');
    html = html.replace(/^##### (.*?)$/gm, '<h5>$1</h5>');
    html = html.replace(/^#### (.*?)$/gm, '<h4>$1</h4>');
    html = html.replace(/^### (.*?)$/gm, '<h3>$1</h3>');
    html = html.replace(/^## (.*?)$/gm, '<h2>$1</h2>');
    html = html.replace(/^# (.*?)$/gm, '<h1>$1</h1>');

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
            processedLines.push(`<li>${parseInlineMarkdown(ulMatch[1])}</li>`);
        } else if (olMatch) {
            if (!inList || inList !== 'ol') {
                if (inList) processedLines.push('</ol>');
                processedLines.push('<ol>');
                inList = 'ol';
            }
            processedLines.push(`<li>${parseInlineMarkdown(olMatch[1])}</li>`);
        } else {
            if (inList) {
                processedLines.push(inList === 'ul' ? '</ul>' : '</ol>');
                inList = false;
            }
            processedLines.push(parseInlineMarkdown(line));
        }
    }
    
    if (inList) processedLines.push(inList === 'ul' ? '</ul>' : '</ol>');
    html = processedLines.join('\n');
    html = html.replace(/\n/g, '<br>');

    for (let i = 0; i < codeBlocks.length; i++) {
        html = html.replace(`%%CODEBLOCK${i}%%`, `<pre><code>${codeBlocks[i]}</code></pre>`);
    }

    // 清理块级元素周围多余的 <br>
    html = html.replace(/(?:<br>\s*)+(<\/?(?:h[1-6]|ul|ol|li|pre)[^>]*>)/gi, '$1');
    html = html.replace(/(<\/?(?:h[1-6]|ul|ol|li|pre)[^>]*>)(?:\s*<br>)+/gi, '$1');
    html = html.replace(/(?:<br>\s*)+$/g, '');

    return html;
}

// ============================================
// 注册 ComfyUI 扩展（同时支持文本和图像流式节点）
// ============================================
app.registerExtension({
    name: "LLM.StreamUI.Pro",
    
    async beforeRegisterNodeDef(nodeType, nodeData) {
        // 精确匹配支持的节点名称（已清理所有空格）
        const SUPPORTED_NODES = ["LLMStreamUI", "LLMStreamImageToPrompt"];
        if (!SUPPORTED_NODES.includes(nodeData.name)) return;

        const origOnNodeCreated = nodeType.prototype.onNodeCreated;

        nodeType.prototype.onNodeCreated = function () {
            const result = origOnNodeCreated?.apply(this, arguments);

            if (!this.streamContainer) {
                // 创建输出容器
                const div = document.createElement("div");
                Object.assign(div.style, {
                    width: "100%",
                    minHeight: "150px",
                    maxHeight: "500px",
                    overflowY: "auto",
                    background: "#111",
                    color: "#eee",
                    padding: "12px 16px",
                    fontSize: "12px",
                    fontFamily: "'Segoe UI', 'Helvetica Neue', Arial, sans-serif",
                    lineHeight: "1.6",
                    borderRadius: "8px",
                    border: "1px solid #333",
                    boxSizing: "border-box"
                });

                // 全局注入深色主题样式（仅注入一次）
                if (!document.getElementById('llm-stream-ui-pro-styles')) {
                    const style = document.createElement('style');
                    style.id = 'llm-stream-ui-pro-styles';
                    style.textContent = `
                        .llm-markdown-content h1, 
                        .llm-markdown-content h2, 
                        .llm-markdown-content h3, 
                        .llm-markdown-content h4, 
                        .llm-markdown-content h5, 
                        .llm-markdown-content h6 { 
                            color: #fff; 
                            margin: 0.5em 0 0.2em; 
                        }
                        .llm-markdown-content h1 { font-size: 1.4em; }
                        .llm-markdown-content h2 { font-size: 1.2em; }
                        .llm-markdown-content h3 { font-size: 1.1em; }
                        .llm-markdown-content code { 
                            background: #2d2d2d; 
                            color: #f8f8f2; 
                            padding: 2px 4px; 
                            border-radius: 3px; 
                            font-family: monospace; 
                            font-size: 0.9em; 
                        }
                        .llm-markdown-content pre { 
                            background: #1e1e1e; 
                            padding: 8px; 
                            border-radius: 5px; 
                            overflow-x: auto; 
                            margin: 8px 0; 
                            border: 1px solid #333;
                        }
                        .llm-markdown-content pre code { 
                            background: none; 
                            padding: 0; 
                            color: #f8f8f2;
                        }
                        .llm-markdown-content a { 
                            color: #6ab0f3; 
                            text-decoration: none; 
                        }
                        .llm-markdown-content a:hover { 
                            text-decoration: underline; 
                        }
                        .llm-markdown-content ul, 
                        .llm-markdown-content ol { 
                            margin: 0.5em 0; 
                            padding-left: 1.5em; 
                            color: #eee;
                        }
                        .llm-markdown-content li { 
                            margin: 0.2em 0; 
                        }
                        .llm-markdown-content strong { 
                            color: #fff; 
                        }
                        .llm-markdown-content em { 
                            color: #ddd; 
                        }
                        .llm-markdown-content p { 
                            margin: 0.5em 0; 
                        }
                    `;
                    document.head.appendChild(style);
                }
                
                div.classList.add('llm-markdown-content');
                div.innerText = "等待输出...";
                this.addDOMWidget("stream_output", "custom", div, { serialize: false });
                this.streamContainer = div;
                this.fullText = "";

                // 设置节点最小高度
                if (this.size[1] < 300) this.setSize([this.size[0], 300]);
            }
            return result;
        };
    },

    setup() {
        // 监听后端推送的流式事件（已清理空格）
        app.api.addEventListener("llm_stream_update", (event) => {
            const { node_id, delta } = event.detail || {};
            if (!node_id || !delta) return;

            // 使用 ComfyUI 标准 API 查找节点
            const node = app.graph.getNodeById(node_id);
            if (!node || !node.streamContainer) {
                console.warn(`[LLM.StreamUI.Pro] 未找到节点 ${node_id} 或其容器`);
                return;
            }

            if (node.fullText === undefined) node.fullText = "";
            node.fullText += delta;

            const el = node.streamContainer;
            // 清除初始占位符
            if (el.innerText === "等待输出..." && node.fullText === delta) {
                el.innerText = "";
            }

            try {
                // 渲染 Markdown 并自动滚动
                el.innerHTML = markdownToHtml(node.fullText);
                el.scrollTop = el.scrollHeight;
                app.graph.setDirtyCanvas(true, false);
            } catch (err) {
                console.error("[LLM.StreamUI.Pro] 渲染错误:", err);
                el.innerText = node.fullText; // 降级显示纯文本
            }
        });
    }
});