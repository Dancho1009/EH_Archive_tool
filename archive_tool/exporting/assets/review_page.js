(function() {
  let qtBridge = null;
  if (window.qt && window.QWebChannel) {
    try {
      new QWebChannel(qt.webChannelTransport, function(channel) {
        qtBridge = channel.objects && channel.objects.reviewBridge ? channel.objects.reviewBridge : null;
      });
    } catch (e) {
      qtBridge = null;
    }
  }

  const tip = document.getElementById("copy-tip");
  function showTip(text) {
    if (!tip) return;
    tip.textContent = text;
    tip.classList.add("show");
    setTimeout(() => tip.classList.remove("show"), 1300);
  }

  async function copyText(text) {
    if (!text) return false;
    try {
      await navigator.clipboard.writeText(text);
      return true;
    } catch (e) {
      const ta = document.createElement("textarea");
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      const ok = document.execCommand("copy");
      ta.remove();
      return ok;
    }
  }

  function pathToFileUri(path) {
    if (!path) return "";
    const normalized = String(path).replace(/\\/g, "/");
    if (/^[a-zA-Z]:[/]/.test(normalized)) {
      return "file:///" + encodeURI(normalized);
    }
    if (normalized.startsWith("/")) {
      return "file://" + encodeURI(normalized);
    }
    return "file://" + encodeURI(normalized);
  }

  const loadedSections = new Set();
  function getSection(sectionId) {
    return document.querySelector(`.panel[data-section="${sectionId}"]`);
  }
  function getTbody(sectionId) {
    return document.getElementById(`tbody-${sectionId}`);
  }
  function getTemplate(sectionId) {
    return document.getElementById(`tpl-${sectionId}`);
  }

  function setToggleState(sectionId, open) {
    const btn = document.querySelector(`.section-toggle[data-section="${sectionId}"]`);
    if (!btn) return;
    btn.setAttribute("data-open", open ? "1" : "0");
    btn.textContent = open ? "收起" : "展开";
  }

  function loadSectionRows(sectionId) {
    if (loadedSections.has(sectionId)) return;
    const tbody = getTbody(sectionId);
    const tpl = getTemplate(sectionId);
    if (!tbody || !tpl) return;
    tbody.innerHTML = tpl.innerHTML;
    loadedSections.add(sectionId);
  }

  function unloadSectionRows(sectionId) {
    if (!loadedSections.has(sectionId)) return;
    const tbody = getTbody(sectionId);
    if (tbody) tbody.textContent = "";
    loadedSections.delete(sectionId);
  }

  function setSectionOpen(sectionId, open, closeOthers=true) {
    const sec = getSection(sectionId);
    if (!sec) return;
    if (open && closeOthers) {
      document.querySelectorAll(".panel.open[data-section]").forEach((other) => {
        const sid = other.getAttribute("data-section");
        if (sid && sid !== sectionId) setSectionOpen(sid, false, false);
      });
    }
    if (open) {
      loadSectionRows(sectionId);
      sec.classList.add("open");
      updateSectionBadge(sectionId);
    } else {
      sec.classList.remove("open");
      unloadSectionRows(sectionId);
    }
    setToggleState(sectionId, open);
    updateCount(sectionId);
  }

  function getRows(sectionId) {
    const sec = getSection(sectionId);
    if (!sec || !sec.classList.contains("open")) return [];
    return Array.from(sec.querySelectorAll(".row-select"));
  }

  function getSelectedRows(sectionId) {
    return getRows(sectionId).filter(x => x.checked);
  }

  function updateCount(sectionId) {
    const el = document.getElementById(`count-${sectionId}`);
    if (!el) return;
    el.textContent = `已选 ${getSelectedRows(sectionId).length}`;
  }

  function updateSectionBadge(sectionId) {
    const sec = getSection(sectionId);
    if (!sec) return;
    const tbody = getTbody(sectionId);
    if (!tbody) return;
    const rows = Array.from(tbody.querySelectorAll("tr"));
    const works = rows.length;
    const strict = rows.filter(r => r.classList.contains("row-dup")).length;
    const suspect = rows.filter(r => r.classList.contains("row-suspect")).length;
    const series = rows.filter(r => r.classList.contains("row-series")).length;
    const missing = rows.filter(r => r.classList.contains("row-missing")).length;
    const risk = rows.filter(r => r.classList.contains("row-risk")).length;

    sec.setAttribute("data-strict", String(strict));
    sec.setAttribute("data-suspect", String(suspect));
    sec.setAttribute("data-series", String(series));
    sec.setAttribute("data-missing", String(missing));
    sec.setAttribute("data-risk", String(risk));

    const worksEl = sec.querySelector(".works-count");
    if (worksEl) worksEl.textContent = `(${works} 作品)`;

    const strictChip = sec.querySelector('.dup-chip[data-chip="strict"]');
    const suspectChip = sec.querySelector('.dup-chip[data-chip="suspect"]');
    const seriesChip = sec.querySelector('.dup-chip[data-chip="series"]');
    const missingChip = sec.querySelector('.dup-chip[data-chip="missing"]');
    const riskChip = sec.querySelector('.dup-chip[data-chip="risk"]');
    if (strictChip) strictChip.textContent = `严格 ${strict}`;
    if (suspectChip) suspectChip.textContent = `疑似 ${suspect}`;
    if (seriesChip) seriesChip.textContent = `系列相关 ${series}`;
    if (missingChip) missingChip.textContent = `缺失 ${missing}`;
    if (riskChip) riskChip.textContent = `风险 ${risk}`;
  }

  function collectDeleteRisks(sectionId, selected) {
    const sec = getSection(sectionId);
    if (!sec) return [];
    const rows = Array.from(sec.querySelectorAll("tbody tr"));
    const selectedRows = selected.map((box) => box.closest("tr")).filter(Boolean);
    const selectedIds = new Set(selectedRows.map((tr) => tr.getAttribute("data-record-id") || ""));
    const risks = [];

    // Risk 1: deleting whole duplicate group
    const byGroup = new Map();
    for (const tr of rows) {
      const g = (tr.getAttribute("data-dup-group") || "").trim();
      if (!g) continue;
      if (!byGroup.has(g)) byGroup.set(g, []);
      byGroup.get(g).push(tr);
    }
    for (const [gid, groupRows] of byGroup.entries()) {
      const selectedInGroup = groupRows.filter((tr) => selectedIds.has(tr.getAttribute("data-record-id") || ""));
      if (selectedInGroup.length > 0 && selectedInGroup.length === groupRows.length) {
        risks.push(`将删除完整重复组 ${gid}（共 ${groupRows.length} 条）`);
      }
    }

    // Risk 2: deleting a master while children remain
    for (const tr of selectedRows) {
      const rid = (tr.getAttribute("data-record-id") || "").trim();
      if (!rid) continue;
      const hasChildren = rows.some((x) => (x.getAttribute("data-master-id") || "").trim() === rid && !selectedIds.has((x.getAttribute("data-record-id") || "").trim()));
      if (hasChildren) {
        risks.push(`将删除主本 ${rid}，但仍有重复项未删`);
      }
    }

    return Array.from(new Set(risks));
  }

  function openUris(uris) {
    let ok = 0;
    uris.forEach((uri, idx) => {
      if (!uri) return;
      setTimeout(() => {
        const win = window.open(uri, "_blank");
        if (win) ok += 1;
      }, idx * 60);
    });
    return ok;
  }

  function exportTextFile(filename, content) {
    const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = filename;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  }

  async function requestDelete(paths) {
    if (qtBridge && typeof qtBridge.deletePaths === "function") {
      return await new Promise((resolve) => {
        try {
          qtBridge.deletePaths(JSON.stringify(paths), function(ret) {
            try {
              resolve(JSON.parse(ret || "{}"));
            } catch (e) {
              resolve({ ok: false, failed: [{ path: "", error: "bridge_parse_error" }] });
            }
          });
        } catch (e) {
          resolve({ ok: false, failed: [{ path: "", error: String(e) }] });
        }
      });
    }
    if (String(window.location.protocol || "").toLowerCase() === "file:") {
      return { ok: false, failed: [{ path: "", error: "NO_BRIDGE_ON_FILE_SCHEME" }] };
    }
    const resp = await fetch("/api/delete", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ paths })
    });
    if (!resp.ok) {
      return { ok: false, failed: [{ path: "", error: `HTTP_${resp.status}` }] };
    }
    return await resp.json();
  }

  document.querySelectorAll(".section-actions").forEach((sec) => {
    const sid = sec.getAttribute("data-section");
    if (sid) updateCount(sid);
  });
  document.querySelectorAll(".section-toggle").forEach((btn) => {
    const sid = btn.getAttribute("data-section");
    if (sid) setToggleState(sid, false);
  });

  const authorRows = Array.from(document.querySelectorAll(".author-stat-row"));
  const authorFilterSelects = Array.from(document.querySelectorAll(".author-type-filter"));
  const pageSizeSelects = Array.from(document.querySelectorAll(".page-size-filter"));
  const mainEl = document.querySelector("main[data-current-page]");
  const defaultSize = Number((mainEl ? mainEl.getAttribute("data-default-size") : "50") || 50);
  const totalAuthors = Number((mainEl ? mainEl.getAttribute("data-total-authors") : "0") || 0);

  let activeTypeFilter = "all";
  let currentPage = 0;
  let pageSize = defaultSize;

  const params = new URLSearchParams(window.location.search || "");
  function toInt(value, fallback) {
    const n = Number(value);
    return Number.isFinite(n) && n > 0 ? Math.floor(n) : fallback;
  }
  function getPageCount(total, size) {
    return Math.max(1, Math.ceil(total / Math.max(1, size)));
  }

  function filterRows(mode) {
    if (!mode || mode === "all") return authorRows.slice();
    return authorRows.filter((row) => {
      const strict = Number(row.getAttribute("data-strict") || 0);
      const suspect = Number(row.getAttribute("data-suspect") || 0);
      const series = Number(row.getAttribute("data-series") || 0);
      const missing = Number(row.getAttribute("data-missing") || 0);
      const risk = Number(row.getAttribute("data-risk") || 0);
      if (mode === "strict") return strict > 0;
      if (mode === "suspect") return suspect > 0;
      if (mode === "series") return series > 0;
      if (mode === "missing") return missing > 0;
      if (mode === "risk") return risk > 0;
      return true;
    });
  }

  function setQueryState() {
    const qs = new URLSearchParams();
    if (pageSize && pageSize !== defaultSize) qs.set("ps", String(pageSize));
    if (currentPage > 0) qs.set("p", String(currentPage + 1));
    if (activeTypeFilter && activeTypeFilter !== "all") qs.set("af", activeTypeFilter);
    const newUrl = `${window.location.pathname}${qs.toString() ? "?" + qs.toString() : ""}`;
    history.replaceState(null, "", newUrl);
  }

  function renderPager(total, size, pageIndex) {
    const totalPages = getPageCount(total, size);
    const pages = new Set([0, totalPages - 1]);
    for (let p = Math.max(0, pageIndex - 2); p < Math.min(totalPages, pageIndex + 3); p += 1) {
      pages.add(p);
    }
    const ordered = Array.from(pages).filter(p => p >= 0 && p < totalPages).sort((a, b) => a - b);

    document.querySelectorAll(".pager-wrap").forEach((wrap) => {
      const meta = wrap.querySelector(".pager-meta");
      const pager = wrap.querySelector(".pager");
      if (!meta || !pager) return;
      const start = total ? pageIndex * size + 1 : 0;
      const end = total ? Math.min(total, (pageIndex + 1) * size) : 0;
      meta.textContent = `${start} - ${end} / ${total}`;

      const parts = [];
      if (totalPages <= 1) {
        parts.push('<span class="pager-btn disabled">|&lt;</span>');
        parts.push('<span class="pager-btn disabled">&lt;</span>');
        parts.push('<span class="pager-btn disabled">&gt;</span>');
        parts.push('<span class="pager-btn disabled">&gt;|</span>');
      } else {
        if (pageIndex > 0) {
          parts.push(`<a class="pager-btn" data-page="0" href="#">|&lt;</a>`);
          parts.push(`<a class="pager-btn" data-page="${pageIndex - 1}" href="#">&lt;</a>`);
        } else {
          parts.push('<span class="pager-btn disabled">|&lt;</span>');
          parts.push('<span class="pager-btn disabled">&lt;</span>');
        }
        let prev = null;
        for (const p of ordered) {
          if (prev !== null && p - prev > 1) parts.push('<span class="pager-ellipsis">...</span>');
          const cls = p === pageIndex ? "pager-num current" : "pager-num";
          parts.push(`<a class="${cls}" data-page="${p}" href="#">${p + 1}</a>`);
          prev = p;
        }
        if (pageIndex < totalPages - 1) {
          parts.push(`<a class="pager-btn" data-page="${pageIndex + 1}" href="#">&gt;</a>`);
          parts.push(`<a class="pager-btn" data-page="${totalPages - 1}" href="#">&gt;|</a>`);
        } else {
          parts.push('<span class="pager-btn disabled">&gt;</span>');
          parts.push('<span class="pager-btn disabled">&gt;|</span>');
        }
      }
      pager.innerHTML = parts.join("");
    });
  }

  function applyPageView() {
    const filtered = filterRows(activeTypeFilter);
    const total = filtered.length;
    const totalPages = getPageCount(total, pageSize);
    if (currentPage >= totalPages) currentPage = totalPages - 1;
    if (currentPage < 0) currentPage = 0;

    const start = currentPage * pageSize;
    const end = Math.min(total, (currentPage + 1) * pageSize);
    const pageInfo = document.getElementById("page-info");
    if (pageInfo) {
      pageInfo.textContent = `第 ${currentPage + 1}/${totalPages} 页`;
    }
    const visibleRows = new Set(filtered.slice(start, end).map(row => row.getAttribute("data-section")));

    document.querySelectorAll(".panel[data-section]").forEach((sec) => {
      const sid = sec.getAttribute("data-section") || "";
      const visible = visibleRows.has(sid);
      sec.classList.toggle("is-hidden", !visible);
      if (!visible && sec.classList.contains("open")) {
        sec.classList.remove("open");
        unloadSectionRows(sid);
        setToggleState(sid, false);
      }
    });

    renderPager(total, pageSize, currentPage);
    setQueryState();
  }

  function initFromQuery() {
    const ps = toInt(params.get("ps"), defaultSize);
    pageSize = ps > 0 ? ps : defaultSize;
    const p = toInt(params.get("p"), 1);
    currentPage = Math.max(0, p - 1);
    const af = (params.get("af") || "all").trim();
    activeTypeFilter = af || "all";
  }

  initFromQuery();

  if (authorFilterSelects.length) {
    for (const sel of authorFilterSelects) {
      sel.value = activeTypeFilter;
      sel.addEventListener("change", () => {
        activeTypeFilter = sel.value || "all";
        currentPage = 0;
        applyPageView();
      });
    }
  }

  if (pageSizeSelects.length) {
    for (const sel of pageSizeSelects) {
      sel.value = String(pageSize);
      sel.addEventListener("change", () => {
        pageSize = Number(sel.value || defaultSize) || defaultSize;
        currentPage = 0;
        applyPageView();
      });
    }
  }

  document.addEventListener("click", (ev) => {
    const btn = ev.target.closest(".pager a[data-page]");
    if (!btn) return;
    ev.preventDefault();
    const p = Number(btn.getAttribute("data-page") || 0);
    if (!Number.isFinite(p)) return;
    currentPage = p;
    applyPageView();
  });

  const authorSearch = document.getElementById("author-search");
  if (authorSearch) {
    let searchTimer = null;
    let composing = false;
    const scheduleFilter = () => {
      if (searchTimer) clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        const q = (authorSearch.value || "").trim().toLowerCase();
        for (const row of authorRows) {
          const name = row.getAttribute("data-author") || "";
          const hide = !!q && !name.includes(q);
          row.classList.toggle("is-hidden", hide);
        }
      }, 220);
    };
    authorSearch.addEventListener("compositionstart", () => {
      composing = true;
    });
    authorSearch.addEventListener("compositionend", () => {
      composing = false;
      scheduleFilter();
    });
    authorSearch.addEventListener("input", () => {
      if (composing) return;
      scheduleFilter();
    });
  }

  document.addEventListener("click", (ev) => {
    const jump = ev.target.closest(".author-jump");
    if (!jump) return;
    const href = jump.getAttribute("href") || "";
    const sid = href.startsWith("#") ? href.slice(1) : "";
    if (!sid) return;
    ev.preventDefault();
    if (activeTypeFilter !== "all") {
      activeTypeFilter = "all";
      for (const sel of authorFilterSelects) sel.value = activeTypeFilter;
    }
    const row = authorRows.find(r => r.getAttribute("data-section") === sid);
    if (row) {
      const idx = Number(row.getAttribute("data-index") || 0) || 0;
      currentPage = Math.floor(idx / pageSize);
      applyPageView();
    }
    setSectionOpen(sid, true, true);
    const sec = getSection(sid);
    if (sec) sec.scrollIntoView({ behavior: "smooth", block: "start" });
  });

  let dragPending = null;
  let dragSelecting = false;
  let dragJustEnded = false;
  let dragSectionId = "";
  let dragStartBox = null;
  let dragStartX = 0;
  let dragStartY = 0;
  let dragLastY = 0;
  const DRAG_THRESHOLD = 4;

  function setCheckedAndCount(box, checked) {
    if (!box) return;
    box.checked = checked;
    const sid = box.getAttribute("data-section") || "";
    if (sid) updateCount(sid);
  }

  function brushSelectByY(sectionId, y1, y2) {
    if (!sectionId) return;
    const sec = getSection(sectionId);
    if (!sec) return;
    const boxes = Array.from(sec.querySelectorAll(".row-select"));
    if (!boxes.length) return;
    const lo = Math.min(y1, y2);
    const hi = Math.max(y1, y2);
    for (const box of boxes) {
      const rect = box.getBoundingClientRect();
      if (rect.bottom >= lo && rect.top <= hi) {
        if (!box.checked) setCheckedAndCount(box, true);
      }
    }
  }

  document.addEventListener("mousedown", (ev) => {
    if (ev.button !== 0) return;
    const box = ev.target.closest(".row-select");
    if (!box) return;
    dragPending = box;
    dragStartBox = box;
    dragStartX = ev.clientX;
    dragStartY = ev.clientY;
    dragLastY = ev.clientY;
    dragSectionId = box.getAttribute("data-section") || "";
  });

  document.addEventListener("mousemove", (ev) => {
    if ((ev.buttons & 1) !== 1) return;
    if (!dragPending && !dragSelecting) return;

    if (!dragSelecting) {
      const dx = Math.abs(ev.clientX - dragStartX);
      const dy = Math.abs(ev.clientY - dragStartY);
      if (Math.max(dx, dy) < DRAG_THRESHOLD) return;
      dragSelecting = true;
      const box = dragStartBox;
      if (box) setCheckedAndCount(box, true);
    }

    brushSelectByY(dragSectionId, dragLastY, ev.clientY);
    dragLastY = ev.clientY;
  });

  document.addEventListener("mouseup", () => {
    dragJustEnded = dragSelecting;
    dragPending = null;
    dragSelecting = false;
    dragStartBox = null;
    dragSectionId = "";
    dragLastY = 0;
  });

  document.addEventListener("dragend", () => {
    dragJustEnded = false;
    dragPending = null;
    dragSelecting = false;
    dragStartBox = null;
    dragSectionId = "";
    dragLastY = 0;
  });

  document.addEventListener("click", (ev) => {
    if (!dragJustEnded) return;
    const box = ev.target.closest(".row-select");
    if (!box) return;
    ev.preventDefault();
    ev.stopPropagation();
    dragJustEnded = false;
  }, true);

  document.addEventListener("change", (ev) => {
    const box = ev.target.closest(".row-select");
    if (!box) return;
    updateCount(box.getAttribute("data-section"));
  });

  document.addEventListener("click", (ev) => {
    const tg = ev.target.closest(".section-toggle");
    if (!tg) return;
    const sid = tg.getAttribute("data-section");
    if (!sid) return;
    ev.preventDefault();
    const willOpen = tg.getAttribute("data-open") !== "1";
    setSectionOpen(sid, willOpen, true);
  });

  document.addEventListener("click", async (ev) => {
    const btn = ev.target.closest(".btn-op");
    if (!btn) return;
    if (btn.classList.contains("section-toggle")) return;
    const sectionId = btn.getAttribute("data-section");
    if (!sectionId) return;

    const rows = getRows(sectionId);
    const selected = getSelectedRows(sectionId);

    if (btn.classList.contains("act-select-all")) {
      rows.forEach(x => x.checked = true);
      updateCount(sectionId);
      return;
    }
    if (btn.classList.contains("act-clear")) {
      rows.forEach(x => x.checked = false);
      updateCount(sectionId);
      return;
    }
    if (btn.classList.contains("act-invert")) {
      rows.forEach(x => x.checked = !x.checked);
      updateCount(sectionId);
      return;
    }
    if (btn.classList.contains("act-delete")) {
      if (!selected.length) {
        showTip("请先勾选要删除的作品");
        return;
      }
      const paths = Array.from(new Set(selected.map(x => x.getAttribute("data-path") || "").filter(Boolean)));
      if (!paths.length) {
        showTip("选中的条目没有路径");
        return;
      }
      const risks = collectDeleteRisks(sectionId, selected);
      const riskText = risks.length ? `\n\n风险提示：\n- ${risks.join("\n- ")}` : "";
      const okConfirm = window.confirm(`确认删除选中的 ${paths.length} 个文件/文件夹？此操作不可撤销。${riskText}`);
      if (!okConfirm) return;
      try {
        const ret = await requestDelete(paths);
        const failed = Array.isArray(ret.failed) ? ret.failed : [];
        const deleted = Array.isArray(ret.deleted) ? ret.deleted : [];
        if (!deleted.length && failed.length && String((failed[0] || {}).error || "").includes("NO_BRIDGE_ON_FILE_SCHEME")) {
          showTip("当前通过 file:// 打开，无法删除。请在 GUI 内嵌预览中操作删除。");
          return;
        }
        if (deleted.length) {
          selected.forEach((box) => {
            const tr = box.closest("tr");
            if (tr) tr.remove();
          });
          updateCount(sectionId);
          updateSectionBadge(sectionId);
        }
        const sync = ret.state_sync || {};
        const rex = ret.reexport || {};
        const msg = `已删除 ${deleted.length} 项，失败 ${failed.length} 项。状态同步 entries=${sync.removed_entries || 0}, records=${sync.removed_records || 0}，重导出${rex.ok ? "成功" : "失败"}`;
        showTip(msg);
      } catch (err) {
        showTip("删除失败，请在 GUI 内嵌预览中操作，或检查权限。");
      }
      return;
    }

    if (!selected.length) {
      showTip("请先勾选要操作的作品");
      return;
    }

    if (btn.classList.contains("act-open-file")) {
      const uris = selected.map(x => pathToFileUri(x.getAttribute("data-path") || ""));
      openUris(uris);
      showTip(`已请求打开 ${selected.length} 项`);
      return;
    }
    if (btn.classList.contains("act-open-parent")) {
      const uris = selected.map(x => pathToFileUri(x.getAttribute("data-parent-path") || ""));
      openUris(uris);
      showTip(`已请求打开 ${selected.length} 个所在目录`);
      return;
    }
    if (btn.classList.contains("act-copy")) {
      const text = selected.map(x => x.getAttribute("data-path") || "").join("\n");
      const ok = await copyText(text);
      showTip(ok ? `已复制 ${selected.length} 条路径` : "复制失败，请检查权限");
      return;
    }
    if (btn.classList.contains("act-export")) {
      const text = selected.map(x => x.getAttribute("data-path") || "").join("\n");
      exportTextFile(`selected_paths_${sectionId}.txt`, text + "\n");
      showTip(`已导出 ${selected.length} 条路径`);
    }
  });

  applyPageView();
})();


