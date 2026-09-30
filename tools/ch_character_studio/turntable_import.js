(() => {
  const api = window.CH_STUDIO_API;
  const baseInput = document.getElementById("baseFile");
  const directionSelect = document.getElementById("direction");
  const frameSelect = document.getElementById("frame");
  const status = document.getElementById("status");
  if (!api || !baseInput || !directionSelect || !frameSelect || !status) return;

  const CONTRACT = "CH_CHARACTER_STUDIO_TURNTABLE_IMPORT_V1";
  const DIRECTIONS = ["S", "E", "N", "W"];

  function normalizedPath(file) {
    return String(file.webkitRelativePath || file.name || "")
      .replaceAll("\\", "/")
      .toLowerCase();
  }

  function findBySuffix(files, suffix) {
    const expected = suffix.toLowerCase();
    return files.find(file => {
      const path = normalizedPath(file);
      return path === expected || path.endsWith(`/${expected}`);
    }) || null;
  }

  async function readTurntableReport(files) {
    const reportFile = files.find(file => normalizedPath(file).endsWith("turntable_report.json"));
    if (!reportFile) return null;
    const report = JSON.parse(await reportFile.text());
    if (Array.isArray(report.frameSize) && (report.frameSize[0] !== 48 || report.frameSize[1] !== 64)) {
      throw new Error(`turntable usa ${report.frameSize.join("×")}; o Studio V0 exige 48×64`);
    }
    if (Array.isArray(report.groundAnchor) && (report.groundAnchor[0] !== 24 || report.groundAnchor[1] !== 60)) {
      throw new Error(`ground anchor ${report.groundAnchor.join(",")} incompatível; esperado 24,60`);
    }
    const declared = Array.isArray(report.directions) ? report.directions.map(String) : [];
    if (declared.length && !DIRECTIONS.every(direction => declared.includes(direction))) {
      throw new Error("turntable_report.json não declara as quatro direções S/E/N/W");
    }
    return report;
  }

  function waitForBaseImport(fileName, timeoutMs = 8000) {
    return new Promise((resolve, reject) => {
      const success = () => status.textContent.includes("Passe base carregado") && status.textContent.includes(fileName);
      if (success()) { resolve(); return; }
      const observer = new MutationObserver(() => {
        if (!success()) return;
        clearTimeout(timer);
        observer.disconnect();
        resolve();
      });
      observer.observe(status, {childList:true, characterData:true, subtree:true});
      const timer = setTimeout(() => {
        observer.disconnect();
        reject(new Error(`timeout ao carregar ${fileName}`));
      }, timeoutMs);
    });
  }

  async function importViaBaseInput(file) {
    if (typeof DataTransfer === "undefined") {
      throw new Error("importação de pacote requer DataTransfer; use Edge/Chrome ou carregue os PNGs manualmente");
    }
    const loaded = waitForBaseImport(file.name);
    const transfer = new DataTransfer();
    transfer.items.add(file);
    baseInput.files = transfer.files;
    baseInput.dispatchEvent(new Event("change", {bubbles:true}));
    await loaded;
  }

  async function activate(direction) {
    if (frameSelect.value !== "idle") {
      frameSelect.value = "idle";
      frameSelect.dispatchEvent(new Event("change", {bubbles:true}));
    }
    if (directionSelect.value !== direction) {
      directionSelect.value = direction;
      directionSelect.dispatchEvent(new Event("change", {bubbles:true}));
    }
    await new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)));
  }

  async function importTurntable(filesLike) {
    const files = [...filesLike];
    if (!files.length) return;
    api.saveFrame();
    const report = await readTurntableReport(files);
    const underlays = new Map();
    for (const direction of DIRECTIONS) {
      const file = findBySuffix(files, `${direction.toLowerCase()}/underlay.png`);
      if (!file) throw new Error(`faltando ${direction.toLowerCase()}/underlay.png`);
      underlays.set(direction, file);
    }

    for (const direction of DIRECTIONS) {
      await activate(direction);
      await importViaBaseInput(underlays.get(direction));
    }

    await activate("S");
    const contract = report?.contract || "sem turntable_report.json";
    api.setStatus(`Pacote CH Blender importado: S/E/N/W → idle · ${contract} · 48×64 / anchor 24,60.`);
    window.dispatchEvent(new CustomEvent("ch-studio-turntable-imported", {
      detail:{contract:CONTRACT, sourceContract:report?.contract || null, directions:[...DIRECTIONS]}
    }));
  }

  function installUi() {
    if (document.getElementById("turntablePackage")) return;
    const label = document.createElement("label");
    label.textContent = "Pacote CH Blender S/E/N/W ";
    const input = document.createElement("input");
    input.id = "turntablePackage";
    input.type = "file";
    input.multiple = true;
    input.setAttribute("webkitdirectory", "");
    input.setAttribute("directory", "");
    label.appendChild(input);
    const baseLabel = baseInput.closest("label");
    if (baseLabel) baseLabel.after(label);

    const hint = document.createElement("div");
    hint.className = "hint";
    hint.textContent = "Selecione a pasta extraída do artifact CH Blender; o Studio encontra S/E/N/W e preenche os quatro idles sem alterar caminhada.";
    label.after(hint);

    input.addEventListener("change", async event => {
      input.disabled = true;
      try {
        api.setStatus("Importando turntable CH Blender…");
        await importTurntable(event.target.files || []);
      } catch (error) {
        api.setStatus(`Falha ao importar pacote CH Blender: ${error.message}`);
      } finally {
        input.disabled = false;
        input.value = "";
      }
    });
  }

  window.CH_TURNTABLE_IMPORT = {contract:CONTRACT, importTurntable};
  installUi();
})();
