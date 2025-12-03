import { app } from "../../scripts/app.js";

// AE Timeline dialog singleton
let aeTimelineDialog = null;

// 静态目录 WEB_DIRECTORY = "./js"，对外路径无需再带 /js 前缀
const ASSET_BASE = "/extensions/ComfyUI-AE-Animation/vue-dist";

async function ensureVueTimelineLoaded() {
  // Always ensure CSS is present (even if createTimelineApp already exists)
  if (!document.querySelector('link[data-ae-timeline-css="1"]')) {
    const link = document.createElement("link");
    link.rel = "stylesheet";
    link.href = `${ASSET_BASE}/assets/timeline.css`;
    link.dataset.aeTimelineCss = "1";
    document.head.appendChild(link);
  }

  if (!document.querySelector('link[data-ae-mask-css="1"]')) {
    const maskLink = document.createElement("link");
    maskLink.rel = "stylesheet";
    maskLink.href = `${ASSET_BASE}/assets/mask-editor.css`;
    maskLink.dataset.aeMaskCss = "1";
    document.head.appendChild(maskLink);
  }

  // Load entry module only if not already present
  if (!window.createTimelineApp) {
    const script = document.createElement("script");
    script.type = "module";
    script.src = `${ASSET_BASE}/timeline.js`;

    await new Promise((resolve, reject) => {
      script.onload = resolve;
      script.onerror = reject;
      document.head.appendChild(script);
    });

    // Give the module a brief moment to initialize
    await new Promise((resolve) => setTimeout(resolve, 200));
  }
}

async function openAETimelineForNode(node) {
  await ensureVueTimelineLoaded();

  // Close existing dialog if present
  if (aeTimelineDialog) {
    try {
      aeTimelineDialog.close();
    } catch {
      // ignore
    }
    aeTimelineDialog.remove();
    aeTimelineDialog = null;
  }

  const dialog = document.createElement("dialog");
  dialog.className = "ae-timeline-dialog";
  Object.assign(dialog.style, {
    position: "fixed",
    top: "50%",
    left: "50%",
    transform: "translate(-50%, -50%)",
    width: "min(98vw, 2400px)",
    height: "min(96vh, 1400px)",
    maxWidth: "98vw",
    maxHeight: "96vh",
    padding: "0",
    margin: "0",
    border: "1px solid #444",
    borderRadius: "8px",
    background: "#1a1a1a",
    zIndex: "10000",
    boxSizing: "border-box",
    display: "flex",
    flexDirection: "column",
    overflow: "hidden",
  });

  const container = document.createElement("div");
  container.className = "ae-vue-timeline-root";
  Object.assign(container.style, {
    width: "100%",
    height: "100%",
    minWidth: "0",
    minHeight: "0",
    overflow: "hidden",
    position: "relative",
    boxSizing: "border-box",
    display: "flex",
    flexDirection: "column",
  });

  dialog.appendChild(container);
  document.body.appendChild(dialog);

  if (!window.createTimelineApp) {
    container.innerHTML = '<div style="padding:20px;color:#f44">Failed to load AE Timeline Vue app. Please check console.</div>';
    dialog.showModal();
    return;
  }

  const vueApp = window.createTimelineApp(container, { node });

  dialog.addEventListener("close", () => {
    try {
      vueApp.unmount && vueApp.unmount();
    } catch {
      // ignore
    }
    dialog.remove();
    if (aeTimelineDialog === dialog) {
      aeTimelineDialog = null;
    }
  });

  dialog.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      dialog.close();
    }
  });

  aeTimelineDialog = dialog;
  dialog.showModal();
}

function getSelectedAEAnimationNode() {
  const canvas = window.LGraphCanvas && window.LGraphCanvas.active_canvas;
  if (!canvas) return null;
  const selected = canvas.selected_nodes || {};
  const nodes = Object.values(selected);
  return nodes.find((n) => n && n.constructor && n.constructor.comfyClass === "AEAnimationCore") || null;
}

app.registerExtension({
  name: "ComfyUI.AEAnimation.TimelineExt",
  setup() {
    const comfyAPI = window.comfyAPI;
    const ComfyButton = comfyAPI && comfyAPI.button && comfyAPI.button.ComfyButton;
    if (!ComfyButton || !app.menu || !app.menu.settingsGroup) return;

    app.menu.settingsGroup.append(
      new ComfyButton({
        icon: "timeline",
        tooltip: "AE Animation Timeline",
        content: "AE Timeline",
        action: async () => {
          const node = getSelectedAEAnimationNode();
          if (!node) {
            alert("请先选中一个 AEAnimationCore 节点再打开 AE Timeline");
            return;
          }
          await openAETimelineForNode(node);
        },
      }),
    );
  },
  getNodeMenuItems(node) {
    const nodeClass = node && node.constructor && node.constructor.comfyClass;
    if (nodeClass !== "AEAnimationCore") return [];

    return [
      null,
      {
        content: "Open AE Timeline",
        callback: () => {
          openAETimelineForNode(node);
        },
      },
    ];
  },
});
