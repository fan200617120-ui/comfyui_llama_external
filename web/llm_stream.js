import { app } from "../../scripts/app.js";

app.registerExtension({
    name: "LLM.StreamUI",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "LLMStreamUI") {
            const origOnNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const result = origOnNodeCreated?.apply(this, arguments);

                // 创建自定义 DOM 容器（聊天窗口）
                const container = document.createElement("div");
                container.className = "llm-stream-window";

                Object.assign(container.style, {
                    maxHeight: "800px",
                    minHeight: "100px",
                    overflowY: "auto",
                    whiteSpace: "pre-wrap",
                    background: "#1e1e1e",
                    color: "#d4d4d4",
                    padding: "10px",
                    borderRadius: "6px",
                    fontSize: "12px",
                    lineHeight: "1.5",
                    fontFamily: "monospace",
                    border: "1px solid #3c3c3c",
                    marginTop: "8px",
                    marginBottom: "4px",
                });

                container.innerText = "等待输出...";

                // 将容器添加为自定义 widget
                this.addDOMWidget("stream_output", "custom", container, {
                    serialize: false,
                });

                // 保存引用，方便事件更新
                this.streamContainer = container;

                // 宽度保持原有，高度至少 800px（可根据需要调整）
                this.setSize([this.size[0], Math.max(this.size[1], 800)]);

                return result;
            };
        }
    },

    setup() {
        app.api.addEventListener("llm_stream_update", (event) => {
            const { node_id, text } = event.detail;

            const node = app.graph._nodes.find(
                (n) => String(n.id) === String(node_id)
            );

            if (!node || !node.streamContainer) return;

            // 更新文字并自动滚动到底部
            node.streamContainer.innerText = text || "等待输出...";
            node.streamContainer.scrollTop = node.streamContainer.scrollHeight;

            // 轻微刷新画布
            app.graph.setDirtyCanvas(true);
        });
    },
});
