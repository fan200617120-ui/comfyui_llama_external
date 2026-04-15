import { app } from "../scripts/app.js";

app.registerExtension({
    name: "LLM.StreamUI",

    async beforeRegisterNodeDef(nodeType, nodeData, app) {
        if (nodeData.name === "LLMStreamUI") {
            const origOnNodeCreated = nodeType.prototype.onNodeCreated;
            nodeType.prototype.onNodeCreated = function () {
                const result = origOnNodeCreated
                    ? origOnNodeCreated.apply(this, arguments)
                    : undefined;

                const widget = this.addWidget(
                    "text",
                    "stream_output",
                    "",
                    () => {},
                    {
                        multiline: true,
                        readonly: true,
                        placeholder: "流式输出将显示在这里...",
                    }
                );
                widget.inputEl.style.height = "200px";
                widget.inputEl.style.resize = "vertical";

                return result;
            };
        }
    },

    setup() {
        app.api.addEventListener("llm_stream_update", (event) => {
            const { node_id, text } = event.detail;

            const node = app.graph._nodes_by_id
                ? app.graph._nodes_by_id[node_id]
                : app.graph._nodes.find((n) => String(n.id) === String(node_id));

            if (!node) return;

            const widget = node.widgets.find((w) => w.name === "stream_output");
            if (widget) {
                widget.value = text;
                node.onResize?.(node.size);
            }
        });
    },
});
