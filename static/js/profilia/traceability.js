import { animate, stagger } from "../motion.js";

const SVG_NS = "http://www.w3.org/2000/svg";

const TONE_STYLES = {
    emerald: {
        pill: "bg-[#dcf6e6] text-[#006c2b]",
        icon: "text-[#008736]",
        bar: "bg-[#008736]",
    },
    amber: {
        pill: "bg-amber-50 text-amber-800 border border-amber-200/80",
        icon: "text-amber-600",
        bar: "bg-amber-500",
    },
    sky: {
        pill: "bg-sky-50 text-sky-800 border border-sky-200/80",
        icon: "text-sky-600",
        bar: "bg-sky-500",
    },
    slate: {
        pill: "bg-slate-100 text-slate-600",
        icon: "text-slate-400",
        bar: "bg-slate-400",
    },
};

export function initTraceability() {
    const page = document.getElementById("traceability-page");
    const dataScript = document.getElementById("traceability-data");
    if (!page || !dataScript) {
        return;
    }

    const payload = JSON.parse(dataScript.textContent || "{}");
    const stages = Array.isArray(payload.stages) ? payload.stages : [];
    if (!stages.length) {
        return;
    }

    const stageTabs = Array.from(document.querySelectorAll("[data-stage-tab]"));
    const graphPanel = document.getElementById("traceability-graph-panel");
    const graphBoard = document.getElementById("traceability-graph-board");
    const svgLayer = document.getElementById("traceability-svg-layer");
    const edgeLabelsLayer = document.getElementById("traceability-edge-labels");
    const nodesContainer = document.getElementById("traceability-nodes-container");
    const sceneCanvas = document.getElementById("traceability-scene-canvas");
    const sceneBadge = document.getElementById("scene-panel-badge");

    const stageTitle = document.getElementById("graph-stage-title");
    const stageSubtitle = document.getElementById("graph-stage-subtitle");

    const playBtn = document.getElementById("traceability-play-btn");
    const playIcon = document.getElementById("traceability-play-icon");
    const playLabel = document.getElementById("traceability-play-label");
    const nextStepBtn = document.getElementById("traceability-next-step-btn");

    const inspectorWhat = document.getElementById("inspector-what");
    const inspectorWhy = document.getElementById("inspector-why");
    const inspectorActionLink = document.getElementById("inspector-action-link");
    const inspectorActionLabel = document.getElementById("inspector-action-label");

    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    let currentStageId = payload.active_stage_id || stages[0].id;
    let currentNodeIndex = 0;
    let playbackRunId = 0;
    let isPlaying = false;
    let activeWaapiAnimations = [];

    stageTabs.forEach(tab => {
        tab.addEventListener("click", () => {
            stopPlayback();
            selectStage(tab.dataset.stageTab, true);
        });
    });

    playBtn?.addEventListener("click", () => {
        if (isPlaying) {
            stopPlayback();
            return;
        }
        playCurrentStage();
    });

    nextStepBtn?.addEventListener("click", () => {
        stopPlayback();
        const stage = getStage(currentStageId);
        const nextIndex = (currentNodeIndex + 1) % stage.nodes.length;
        const targetNode = stage.nodes[nextIndex];
        selectNode(nextIndex, { animateIncomingTo: targetNode?.id });
    });

    window.addEventListener("resize", () => {
        drawGraphEdges(getStage(currentStageId), currentNodeIndex);
    });

    if (typeof ResizeObserver !== "undefined" && graphBoard) {
        const boardObserver = new ResizeObserver(() => {
            drawGraphEdges(getStage(currentStageId), currentNodeIndex);
        });
        boardObserver.observe(graphBoard);
    }

    window.addEventListener("profilia:sidebar-change", () => {
        const start = performance.now();
        function syncDuringTransition(now) {
            drawGraphEdges(getStage(currentStageId), currentNodeIndex);
            if (now - start < 400) {
                requestAnimationFrame(syncDuringTransition);
            }
        }
        requestAnimationFrame(syncDuringTransition);
    });

    selectStage(currentStageId, false);
    if (!reducedMotion) {
        animate(stageTabs, {
            opacity: [0, 1],
            transform: ["translateY(6px)", "translateY(0px)"],
        }, {
            delay: stagger(0.04),
            duration: 0.22,
        });
    }

    function getStage(stageId) {
        return stages.find(item => item.id === stageId) || stages[0];
    }

    function selectStage(stageId, shouldAnimateNodes = true) {
        currentStageId = stageId;
        currentNodeIndex = 0;
        const stage = getStage(stageId);

        stageTabs.forEach(tab => {
            const active = tab.dataset.stageTab === stage.id;
            tab.setAttribute("aria-selected", active ? "true" : "false");
            tab.classList.toggle("border-[#02bc4d]", active);
            tab.classList.toggle("bg-emerald-50/40", active);
            tab.classList.toggle("shadow-sm", active);
            tab.classList.toggle("border-slate-200/90", !active);
            tab.classList.toggle("bg-slate-50/40", !active);

            const iconBox = tab.querySelector("[data-stage-icon-box]");
            if (iconBox) {
                iconBox.className = `w-6 h-6 rounded-lg flex items-center justify-center shrink-0 text-[11px] font-semibold transition ${
                    active ? "bg-[#13223a] text-[#00d461]" : "bg-slate-200/80 text-slate-600"
                }`;
            }
        });

        graphPanel?.setAttribute("aria-labelledby", `stage-tab-${stage.id}`);
        if (stageTitle) {
            stageTitle.textContent = stage.full_title || stage.title;
        }
        if (stageSubtitle) {
            stageSubtitle.textContent = stage.subtitle || stage.summary || "";
        }

        renderNodes(stage);
        selectNode(0, { animateIncomingTo: null });

        requestAnimationFrame(() => {
            drawGraphEdges(stage, currentNodeIndex);
            if (shouldAnimateNodes && !reducedMotion) {
                const cards = nodesContainer.querySelectorAll("[data-node-card]");
                animate(cards, {
                    opacity: [0, 1],
                }, {
                    delay: stagger(0.04),
                    duration: 0.2,
                });
            }
        });
    }

    function renderNodes(stage) {
        const isLinearStage = stage.nodes.length > 0 && stage.nodes.every(n => n.y === stage.nodes[0].y);
        const cards = stage.nodes.map((node, index) => {
            const button = createElement(
                "button",
                `traceability-node-2d${isLinearStage ? " is-linear" : ""} group text-center p-2.5 rounded-2xl border transition-all duration-200 min-h-[44px] flex flex-col items-center justify-center gap-1 bg-white border-slate-300/90 hover:border-[#008736] focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-[#008736]`,
            );
            button.type = "button";
            button.dataset.nodeCard = node.id;
            button.dataset.nodeIndex = String(index);
            button.setAttribute("aria-label", node.title);
            button.style.setProperty("--node-x", `${node.x ?? 50}%`);
            button.style.setProperty("--node-y", `${node.y ?? 50}%`);

            const pulseRing = createElement(
                "span",
                "pointer-events-none absolute -inset-1 rounded-2xl border-2 border-[#02bc4d] opacity-0",
            );
            pulseRing.dataset.nodeRing = node.id;

            const iconWrap = createElement(
                "div",
                "w-9 h-9 rounded-xl bg-slate-100 border border-slate-200 text-slate-600 flex items-center justify-center shrink-0 transition relative z-10 mb-0.5",
            );
            iconWrap.dataset.nodeIconWrap = node.id;
            iconWrap.append(createElement("i", `fa-solid ${node.icon} text-xs`));

            const titleEl = createElement(
                "p",
                `${isLinearStage ? "text-[11px]" : "text-xs"} font-bold text-[#13223a] leading-tight truncate max-w-full relative z-10`,
                node.title,
            );
            titleEl.dataset.nodeTitle = node.id;

            const badgeText = createElement(
                "p",
                "font-mono text-[10px] font-medium text-slate-500 tabular-nums truncate max-w-full relative z-10",
                node.badge,
            );
            badgeText.dataset.nodeBadge = node.id;

            button.append(pulseRing, iconWrap, titleEl, badgeText);
            button.addEventListener("click", () => {
                stopPlayback();
                selectNode(index, { animateIncomingTo: node.id });
            });
            return button;
        });

        nodesContainer.replaceChildren(...cards);
    }

    function selectNode(index, options = {}) {
        const stage = getStage(currentStageId);
        const nodes = stage.nodes;
        currentNodeIndex = Math.max(0, Math.min(index, nodes.length - 1));
        const activeNode = nodes[currentNodeIndex];

        const cards = Array.from(nodesContainer.querySelectorAll("[data-node-card]"));
        cards.forEach((card, idx) => {
            const isSelected = idx === currentNodeIndex;
            const isPast = idx < currentNodeIndex;
            card.setAttribute("aria-pressed", isSelected ? "true" : "false");
            card.classList.toggle("is-selected", isSelected);
            card.classList.toggle("border-2", isSelected);
            card.classList.toggle("border-[#02bc4d]", isSelected);
            card.classList.toggle("bg-emerald-50/70", isSelected);
            card.classList.toggle("shadow-[0_0_0_4px_#dcf6e6,0_8px_20px_-6px_rgba(2,188,77,0.28)]", isSelected);
            card.classList.toggle("z-20", isSelected);
            card.classList.toggle("border-[#81cda0]", !isSelected && isPast);
            card.classList.toggle("bg-white", !isSelected);
            card.classList.toggle("border-slate-300/90", !isSelected && !isPast);

            const iconWrap = card.querySelector("[data-node-icon-wrap]");
            if (iconWrap) {
                iconWrap.className = `w-9 h-9 rounded-xl flex items-center justify-center shrink-0 transition relative z-10 mb-0.5 ${
                    isSelected
                        ? "bg-[#02bc4d] text-[#0b1526] shadow-md shadow-[#02bc4d]/35"
                        : isPast
                            ? "bg-emerald-50 border border-emerald-200 text-[#008736]"
                            : "bg-slate-100 border border-slate-200 text-slate-600"
                }`;
            }

            const badgeEl = card.querySelector("[data-node-badge]");
            if (badgeEl) {
                badgeEl.className = `font-mono text-[10px] tabular-nums truncate max-w-full relative z-10 ${
                    isSelected ? "font-bold text-[#006c2b]" : "font-medium text-slate-500"
                }`;
            }
        });

        updateInspector(stage, activeNode);
        renderLiveScene(stage, activeNode);
        drawGraphEdges(stage, currentNodeIndex, options.animateIncomingTo);
    }

    function updateInspector(stage, node) {
        if (inspectorWhat) {
            inspectorWhat.textContent = node.what_did;
        }
        if (inspectorWhy) {
            inspectorWhy.textContent = node.why_did;
        }
        if (inspectorActionLink) {
            inspectorActionLink.href = stage.action_url;
        }
        if (inspectorActionLabel) {
            inspectorActionLabel.textContent = stage.action_label;
        }
        if (sceneBadge) {
            sceneBadge.textContent = node.badge || "";
        }
    }

    function renderLiveScene(stage, node) {
        if (!sceneCanvas) {
            return;
        }
        const scene = node.scene || { kind: "default" };
        sceneCanvas.replaceChildren();

        const wrapper = createElement("div", "w-full space-y-2");

        if (scene.kind === "structure") {
            const grid = createElement("div", "grid grid-cols-2 gap-2.5");
            (scene.blocks || []).forEach(block => {
                const cell = createElement("div", "p-3 rounded-xl bg-white border border-slate-200/90 space-y-2");
                const top = createElement("div", "flex items-baseline justify-between gap-2");
                top.append(
                    createElement("span", "text-xs font-medium text-slate-600", block.label),
                    createElement("span", "font-mono text-sm font-semibold tabular-nums text-[#13223a]", String(block.count)),
                );
                const barBg = createElement("div", "w-full h-1 bg-slate-100 rounded-full overflow-hidden");
                const barFill = createElement("div", "h-full bg-[#008736] rounded-full");
                const pct = block.count > 0 ? Math.min(100, Math.max(18, block.count * 22)) : 0;
                barFill.style.width = `${pct}%`;
                barBg.append(barFill);
                cell.append(top, barBg);
                grid.append(cell);
            });
            wrapper.append(grid);
        } else if (scene.kind === "decision_gate") {
            const gateBox = createElement("div", "grid grid-cols-1 sm:grid-cols-2 gap-2.5");
            const yesCol = createElement("div", "p-3 rounded-xl bg-white border border-slate-200/90 space-y-1.5");
            yesCol.append(
                createElement("p", "text-xs font-semibold text-[#006c2b]", "Confirmadas contigo"),
            );
            (scene.confirmed?.length ? scene.confirmed : ["Sin confirmaciones aún"]).slice(0, 3).forEach(item => {
                yesCol.append(
                    createElement("div", "text-xs text-[#13223a] bg-[#dcf6e6]/50 px-2.5 py-1 rounded-lg truncate", item),
                );
            });

            const gapCol = createElement("div", "p-3 rounded-xl bg-white border border-slate-200/90 space-y-1.5");
            gapCol.append(
                createElement("p", "text-xs font-semibold text-amber-800", "Por aclarar o reforzar"),
            );
            const gapList = [...(scene.pending || []), ...(scene.strengthen || [])];
            (gapList.length ? gapList : ["Sin preguntas pendientes"]).slice(0, 3).forEach(item => {
                gapCol.append(
                    createElement("div", "text-xs text-slate-700 bg-slate-100 px-2.5 py-1 rounded-lg truncate", item),
                );
            });
            gateBox.append(yesCol, gapCol);
            wrapper.append(gateBox);
        } else if (scene.kind === "roles_meter" || scene.kind === "ranking_bars" || scene.kind === "skill_matrix") {
            const rows = scene.roles
                ? scene.roles.map(r => ({
                    title: r.name,
                    sub: r.label,
                    pct: r.group === "high" ? 90 : (r.group === "medium" ? 65 : 38),
                }))
                : (scene.bars || scene.matches || []).map(b => ({
                    title: b.title,
                    sub: b.company || `${b.matched ?? 0} cubiertas`,
                    pct: b.score || 50,
                }));

            const list = createElement("div", "space-y-2");
            if (rows.length) {
                rows.slice(0, 3).forEach(row => {
                    const item = createElement("div", "p-3 rounded-xl bg-white border border-slate-200/90 space-y-1.5");
                    const top = createElement("div", "flex items-baseline justify-between gap-2");
                    const left = createElement("div", "min-w-0");
                    left.append(
                        createElement("p", "text-xs font-bold text-[#13223a] truncate", row.title),
                        createElement("p", "text-[11px] text-slate-500 truncate", row.sub),
                    );
                    top.append(
                        left,
                        createElement("span", "font-mono text-xs font-semibold tabular-nums text-[#006c2b] shrink-0", `${row.pct}%`),
                    );
                    const barTrack = createElement("div", "w-full h-1 bg-slate-100 rounded-full overflow-hidden");
                    const barFill = createElement("div", "h-full bg-[#008736] rounded-full");
                    barFill.style.width = `${row.pct}%`;
                    barTrack.append(barFill);
                    item.append(top, barTrack);
                    list.append(item);
                });
            } else {
                list.append(
                    createElement(
                        "div",
                        "p-3.5 rounded-xl bg-white border border-slate-200/90 text-xs text-slate-600",
                        "Completa tu perfil y elige tus cargos de interés para ver aquí tu nivel de coincidencia.",
                    ),
                );
            }
            wrapper.append(list);
        } else if (scene.kind === "normalizer") {
            const list = createElement("div", "space-y-2");
            (scene.pairs || []).forEach(pair => {
                const row = createElement(
                    "div",
                    "p-2.5 rounded-xl bg-white border border-slate-200/90 flex items-center justify-between gap-2",
                );
                row.append(
                    createElement("span", "px-2 py-0.5 rounded-md bg-slate-100 text-slate-600 font-mono text-xs truncate", pair.raw),
                    createElement("i", "fa-solid fa-arrow-right text-slate-400 text-[11px] shrink-0"),
                    createElement("span", "px-2.5 py-0.5 rounded-md bg-[#dcf6e6] text-[#006c2b] font-mono font-semibold text-xs", pair.clean),
                );
                list.append(row);
            });
            wrapper.append(list);
        } else if (scene.kind === "filter_gate") {
            const funnel = createElement("div", "p-3.5 rounded-xl bg-white border border-slate-200/90 space-y-3");
            const badges = createElement("div", "grid grid-cols-3 gap-2");
            [
                { label: "Modalidad", val: scene.modality },
                { label: "Ciudad", val: scene.city },
                { label: "Salario", val: scene.salary },
            ].forEach(f => {
                const pill = createElement("div", "p-2 rounded-lg bg-slate-50 border border-slate-200/80");
                pill.append(
                    createElement("p", "text-[11px] text-slate-500", f.label),
                    createElement("p", "text-xs font-semibold text-[#13223a] truncate mt-0.5", f.val),
                );
                badges.append(pill);
            });
            const total = Math.max(1, scene.total || 1);
            const passed = scene.passed || 0;
            const pct = Math.round((passed / total) * 100);
            const footer = createElement("div", "pt-2.5 border-t border-slate-100 space-y-1.5");
            const meter = createElement("div", "flex items-baseline justify-between text-xs");
            meter.append(
                createElement("span", "text-slate-600 font-medium", "Ofertas acordes a tus filtros"),
                createElement("span", "font-mono text-[#13223a] font-semibold tabular-nums", `${passed} de ${scene.total || 0}`),
            );
            const track = createElement("div", "w-full h-1 bg-slate-100 rounded-full overflow-hidden");
            const fill = createElement("div", "h-full bg-[#008736] rounded-full");
            fill.style.width = `${pct}%`;
            track.append(fill);
            footer.append(meter, track);
            funnel.append(badges, footer);
            wrapper.append(funnel);
        } else {
            const list = createElement("div", "space-y-2");
            const visualData = Array.isArray(node.visual_items) && node.visual_items.length
                ? node.visual_items
                : (node.items || []).map(text => ({
                    label: text,
                    value: node.badge || "",
                    tone: "emerald",
                    icon: "fa-check",
                }));

            visualData.slice(0, 4).forEach(item => {
                const tone = TONE_STYLES[item.tone] || TONE_STYLES.slate;
                const row = createElement(
                    "div",
                    "p-2.5 rounded-xl bg-white border border-slate-200/90 flex items-center justify-between gap-3",
                );
                const left = createElement("div", "flex items-center gap-2.5 min-w-0");
                left.append(
                    createElement("i", `fa-solid ${item.icon || "fa-circle-check"} ${tone.icon} text-xs shrink-0`),
                    createElement("span", "text-xs font-medium text-[#13223a] truncate", item.label),
                );
                row.append(
                    left,
                    createElement(
                        "span",
                        `font-mono text-[11px] font-semibold tabular-nums px-2 py-0.5 rounded-md shrink-0 ${tone.pill}`,
                        item.value,
                    ),
                );
                list.append(row);
            });
            wrapper.append(list);
        }

        sceneCanvas.append(wrapper);
        if (!reducedMotion) {
            animate(wrapper, {
                opacity: [0, 1],
                transform: ["translateY(4px)", "translateY(0px)"],
            }, {
                duration: 0.18,
            });
        }
    }

    function drawGraphEdges(stage, activeNodeIdx, animateTargetNodeId = null) {
        if (!svgLayer || !graphBoard) {
            return;
        }
        const boardRect = graphBoard.getBoundingClientRect();
        if (!boardRect.width || !boardRect.height) {
            return;
        }

        svgLayer.setAttribute("viewBox", `0 0 ${boardRect.width} ${boardRect.height}`);
        svgLayer.replaceChildren();
        edgeLabelsLayer?.replaceChildren();

        const linesGroup = document.createElementNS(SVG_NS, "g");
        const particlesGroup = document.createElementNS(SVG_NS, "g");
        svgLayer.append(linesGroup, particlesGroup);

        const cardMap = new Map();
        const nodeIndexMap = new Map();
        stage.nodes.forEach((n, idx) => nodeIndexMap.set(n.id, idx));
        nodesContainer.querySelectorAll("[data-node-card]").forEach(card => {
            cardMap.set(card.dataset.nodeCard, card);
        });

        const isDesktop2D = window.innerWidth >= 768;
        const edges = Array.isArray(stage.edges) ? stage.edges : [];

        edges.forEach(edge => {
            const fromCard = cardMap.get(edge.from);
            const toCard = cardMap.get(edge.to);
            if (!fromCard || !toCard) {
                return;
            }

            const fromRect = fromCard.getBoundingClientRect();
            const toRect = toCard.getBoundingClientRect();

            let x1;
            let y1;
            let x2;
            let y2;
            let d;

            if (isDesktop2D) {
                x1 = fromRect.right - boardRect.left;
                y1 = fromRect.top - boardRect.top + fromRect.height / 2;
                x2 = toRect.left - boardRect.left;
                y2 = toRect.top - boardRect.top + toRect.height / 2;
                const dx = Math.max(36, (x2 - x1) * 0.52);
                d = `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
            } else {
                x1 = fromRect.left - boardRect.left + fromRect.width / 2;
                y1 = fromRect.bottom - boardRect.top;
                x2 = toRect.left - boardRect.left + toRect.width / 2;
                y2 = toRect.top - boardRect.top;
                const cy = (y1 + y2) / 2;
                d = `M ${x1} ${y1} C ${x1} ${cy}, ${x2} ${cy}, ${x2} ${y2}`;
            }

            const baseTrack = document.createElementNS(SVG_NS, "path");
            baseTrack.setAttribute("d", d);
            baseTrack.setAttribute("fill", "none");
            baseTrack.setAttribute("stroke", "#cbd5e1");
            baseTrack.setAttribute("stroke-width", "1.75");
            baseTrack.setAttribute("stroke-dasharray", "4 5");
            linesGroup.appendChild(baseTrack);

            const toIdx = nodeIndexMap.get(edge.to) ?? 0;
            const fromIdx = nodeIndexMap.get(edge.from) ?? 0;
            const isEdgeVisited = toIdx <= activeNodeIdx && fromIdx <= activeNodeIdx;
            const isEdgeEnabled = edge.active !== false;

            const activePath = document.createElementNS(SVG_NS, "path");
            activePath.setAttribute("d", d);
            activePath.setAttribute("fill", "none");
            activePath.setAttribute("stroke", isEdgeEnabled ? "#008736" : "#94a3b8");
            activePath.setAttribute("stroke-width", isEdgeVisited ? "2.25" : "1.5");
            activePath.setAttribute("stroke-linecap", "round");
            if (isEdgeVisited && isEdgeEnabled) {
                activePath.classList.add("trace-edge-stream");
                activePath.style.opacity = "0.95";
            } else {
                activePath.style.opacity = isEdgeEnabled ? "0.35" : "0.18";
            }
            linesGroup.appendChild(activePath);

            [
                { cx: x1, cy: y1 },
                { cx: x2, cy: y2 },
            ].forEach(pt => {
                const port = document.createElementNS(SVG_NS, "circle");
                port.setAttribute("cx", String(pt.cx));
                port.setAttribute("cy", String(pt.cy));
                port.setAttribute("r", "3.25");
                port.setAttribute("fill", isEdgeVisited ? "#008736" : "#94a3b8");
                port.setAttribute("stroke", "#ffffff");
                port.setAttribute("stroke-width", "1.5");
                linesGroup.appendChild(port);
            });

            if (isDesktop2D && edge.label && edgeLabelsLayer) {
                let mid = { x: (x1 + x2) / 2, y: (y1 + y2) / 2 };
                if (typeof activePath.getTotalLength === "function" && typeof activePath.getPointAtLength === "function") {
                    const totalLen = activePath.getTotalLength();
                    if (totalLen > 0) {
                        const pt = activePath.getPointAtLength(totalLen * 0.5);
                        mid = { x: pt.x, y: pt.y };
                    }
                }
                const toneClasses = isEdgeVisited && isEdgeEnabled
                    ? "bg-white border-[#81cda0] text-[#006c2b] font-semibold"
                    : isEdgeEnabled
                        ? "bg-white/95 border-slate-300/90 text-slate-600 font-medium"
                        : "bg-slate-50/95 border-slate-200 text-slate-400 font-medium";
                const labelPill = createElement(
                    "span",
                    `absolute -translate-x-1/2 -translate-y-1/2 px-1.5 py-0.5 rounded-full text-[10px] leading-tight whitespace-nowrap border shadow-[0_1px_2px_rgba(19,34,58,0.06)] transition-colors ${toneClasses}`,
                    edge.label,
                );
                labelPill.dataset.edgeLabel = `${edge.from}->${edge.to}`;
                labelPill.style.left = `${mid.x}px`;
                labelPill.style.top = `${mid.y}px`;
                edgeLabelsLayer.appendChild(labelPill);

                const sameRow = Math.abs(y2 - y1) < 24;
                if (sameRow && labelPill.getBoundingClientRect().width + 6 > (x2 - x1)) {
                    labelPill.remove();
                }
            }

            if (animateTargetNodeId && edge.to === animateTargetNodeId && !reducedMotion) {
                animateSvgEdge(activePath, particlesGroup);
            }
        });
    }

    function animateSvgEdge(pathEl, targetGroup) {
        if (typeof pathEl.getTotalLength !== "function") {
            return null;
        }
        const length = Math.max(24, pathEl.getTotalLength());
        const durationMs = 460;

        const pulseDot = document.createElementNS(SVG_NS, "circle");
        pulseDot.setAttribute("r", "4.5");
        pulseDot.setAttribute("fill", "#008736");
        pulseDot.setAttribute("stroke", "#dcf6e6");
        pulseDot.setAttribute("stroke-width", "2");
        (targetGroup || svgLayer).appendChild(pulseDot);

        const sampleSteps = 18;
        const pointFrames = [];
        for (let step = 0; step <= sampleSteps; step += 1) {
            const point = pathEl.getPointAtLength((length * step) / sampleSteps);
            pointFrames.push({
                transform: `translate(${point.x}px, ${point.y}px)`,
                opacity: step === sampleSteps ? 0 : 1,
            });
        }

        if (typeof pulseDot.animate === "function") {
            const dotAnim = pulseDot.animate(pointFrames, {
                duration: durationMs,
                easing: "cubic-bezier(0.25, 0.9, 0.35, 1)",
                fill: "forwards",
            });
            activeWaapiAnimations.push(dotAnim);
            dotAnim.finished.catch(() => null).finally(() => {
                pulseDot.remove();
            });
            return dotAnim.finished.catch(() => null);
        }
        pulseDot.remove();
        return Promise.resolve();
    }

    async function playCurrentStage() {
        const runId = ++playbackRunId;
        setPlayingState(true);
        await runStageSequence(getStage(currentStageId), runId);
        if (runId === playbackRunId) {
            setPlayingState(false);
        }
    }

    async function runStageSequence(stage, runId) {
        const cards = Array.from(nodesContainer.querySelectorAll("[data-node-card]"));
        for (let i = 0; i < stage.nodes.length; i += 1) {
            if (runId !== playbackRunId) {
                return;
            }

            const node = stage.nodes[i];
            selectNode(i, { animateIncomingTo: i > 0 ? node.id : null });
            const card = cards[i];
            const ring = card?.querySelector("[data-node-ring]");

            let ringAnim = null;
            if (ring && !reducedMotion && typeof ring.animate === "function") {
                ringAnim = ring.animate(
                    [
                        { opacity: 0.75, transform: "scale(0.99)" },
                        { opacity: 0.15, transform: "scale(1.04)" },
                        { opacity: 0.75, transform: "scale(0.99)" },
                    ],
                    {
                        duration: 520,
                        iterations: 2,
                        easing: "ease-in-out",
                    },
                );
                activeWaapiAnimations.push(ringAnim);
            }

            await waitMs(reducedMotion ? 60 : 800);

            if (ringAnim) {
                try {
                    ringAnim.cancel();
                } catch {
                    // Ignore finished animation.
                }
            }
            if (ring) {
                ring.style.opacity = "0";
            }
        }
    }

    function stopPlayback() {
        playbackRunId += 1;
        activeWaapiAnimations.forEach(anim => {
            try {
                anim.cancel();
            } catch {
                // Ignore cancelled/completed animations.
            }
        });
        activeWaapiAnimations = [];
        nodesContainer?.querySelectorAll("[data-node-ring]").forEach(ring => {
            ring.style.opacity = "0";
        });
        setPlayingState(false);
    }

    function setPlayingState(playing) {
        isPlaying = playing;
        if (!playBtn || !playIcon || !playLabel) {
            return;
        }
        playIcon.className = playing ? "fa-solid fa-stop text-[10px]" : "fa-solid fa-play text-[10px]";
        playLabel.textContent = playing ? "Detener" : "Recorrer etapa";
    }
}

function waitMs(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}

function createElement(tag, className, text) {
    const node = document.createElement(tag);
    if (className) {
        node.className = className;
    }
    if (text !== undefined) {
        node.textContent = text;
    }
    return node;
}

if (typeof document !== "undefined") {
    document.addEventListener("DOMContentLoaded", initTraceability);
}
