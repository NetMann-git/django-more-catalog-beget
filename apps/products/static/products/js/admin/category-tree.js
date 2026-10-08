"use strict";
document.addEventListener("DOMContentLoaded", () => {
    const table = document.querySelector("#result_list");
    const tools = document.querySelector("#category-tree-tools");
    if (!table || !tools) return;
    const nodes = Array.from(table.querySelectorAll(".category-tree-node"));
    const collapsed = new Set();
    const refresh = () => {
        nodes.forEach(node => {
            const hidden = node.dataset.ancestors.split(",").some(id => collapsed.has(id));
            node.closest("tr").classList.toggle("category-tree-hidden", hidden);
            const button = node.querySelector(".category-tree-toggle");
            if (button) {
                const expanded = !collapsed.has(node.dataset.node);
                button.setAttribute("aria-expanded", String(expanded));
                button.textContent = expanded ? "▾" : "▸";
                button.setAttribute("aria-label", `${expanded ? "Свернуть" : "Развернуть"} ветку: ${node.querySelector("a").textContent}`);
            }
        });
    };
    table.addEventListener("click", event => {
        const button = event.target.closest(".category-tree-toggle");
        if (!button) return;
        const id = button.closest(".category-tree-node").dataset.node;
        if (collapsed.has(id)) collapsed.delete(id); else collapsed.add(id);
        refresh();
    });
    tools.addEventListener("click", event => {
        const button = event.target.closest("[data-tree-action]");
        if (!button) return;
        collapsed.clear();
        if (button.dataset.treeAction === "collapse") {
            nodes.filter(node => node.querySelector(".category-tree-toggle"))
                .forEach(node => collapsed.add(node.dataset.node));
        }
        refresh();
    });
    tools.hidden = false;
    refresh();
});
