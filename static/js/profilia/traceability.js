import { animate, spring, stagger } from "../motion.js";

const SVG_NS = "http://www.w3.org/2000/svg";

const STATUS_STYLES = {
    completed: {
        pill: "bg-emerald-100 text-[#008736] border border-emerald-200",
        darkPill: "bg-[#00d461]/20 text-[#00d461] border border-[#00d461]/40",
        dot: "bg-[#00d461]",
    },
    in_progress: {
        pill: "bg-amber-100 text-amber-800 border border-amber-200",
        darkPill: "bg-amber-400/20 text-amber-300 border border-amber-400/40",
        dot: "bg-amber-400",
    },
    preview: {
        pill: "bg-sky-100 text-sky-800 border border-sky-200",
        darkPill: "bg-sky-400/20 text-sky-300 border border-sky-400/40",
        dot: "bg-sky-400",
    },
    pending: {
        pill: "bg-slate-200 text-slate-600 border border-slate-300",
        darkPill: "bg-slate-800 text-slate-400 border border-slate-700",
        dot: "bg-slate-500",
    },
};

const TONE_STYLES = {
    emerald: {
        box: "bg-emerald-950/40 border-emerald-500/30 text-emerald-300",
        icon: "bg-[#00d461]/15 text-[#00d461]",
        badge: "bg-[#00d461]/20 text-[#00d461]",
    },
    amber: {
        box: "bg-amber-950/35 border-amber-500/30 text-amber-200",
        icon: "bg-amber-400/15 text-amber-300",
        badge: "bg-amber-400/20 text-amber-300",
    },
    sky: {
        box: "bg-sky-950/35 border-sky-500/30 text-sky-200",
        icon: "bg-sky-400/15 text-sky-300",
        badge: "bg-sky-400/20 text-sky-300",
    },
    slate: {
        box: "bg-slate-900/90 border-slate-800 text-slate-300",
        icon: "bg-slate-800 text-slate-400",
        badge: "bg-slate-800 text-slate-400",
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
    const nodesContainer = document.getElementById("traceability-nodes-container");
    const sceneCanvas = document.getElementById("traceability-scene-canvas");
    const sceneNodeBadge = document.getElementById("scene-node-badge");

    const stageStepPill = document.getElementById("graph-stage-step-pill");
    const stageTitle = document.getElementById("graph-stage-title");
    const stageStatusBadge = document.getElementById("graph-stage-status-badge");
    const stageSummary = document.getElementById("graph-stage-summary");

    const playBtn = document.getElementById("traceability-play-btn");
    const playIcon = document.getElementById("traceability-play-icon");
    const playLabel = document.getElementById("traceability-play-label");
    const playAllBtn = document.getElementById("traceability-play-all-btn");
    const nextStepBtn = document.getElementById("traceability-next-step-btn");
    const speedBtn = document.getElementById("traceability-speed-btn");
    const speedLabel = document.getElementById("traceability-speed-label");

    const liveStatus = document.getElementById("traceability-live-status");
    const stepCounter = document.getElementById("traceability-step-counter");
    const playbackBar = document.getElementById("traceability-playback-bar");

    const inspectorCard = document.getElementById("traceability-inspector-card");
    const inspectorIcon = document.getElementById("inspector-icon");
    const inspectorStepLabel = document.getElementById("inspector-step-label");
    const inspectorStatusPill = document.getElementById("inspector-status-pill");
    const inspectorTitle = document.getElementById("inspector-title");
    const inspectorWhat = document.getElementById("inspector-what");
    const inspectorWhy = document.getElementById("inspector-why");
    const inspectorItems = document.getElementById("inspector-items");
    const inspectorActionLink = document.getElementById("inspector-action-link");
    const inspectorActionLabel = document.getElementById("inspector-action-label");

    const reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    let currentStageId = payload.active_stage_id || stages[0].id;
    let currentNodeIndex = 0;
    let speedMultiplier = 1;
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

    playAllBtn?.addEventListener("click", () => {
        if (isPlaying) {
            stopPlayback();
            return;
        }
        playAllStages();
    });

    nextStepBtn?.addEventListener("click", () => {
        stopPlayback();
        const stage = getStage(currentStageId);
        const nextIndex = (currentNodeIndex + 1) % stage.nodes.length;
        const targetNode = stage.nodes[nextIndex];
        selectNode(nextIndex, { animateIncomingTo: targetNode?.id });
    });

    speedBtn?.addEventListener("click", () => {
        speedMultiplier = speedMultiplier === 1 ? 1.5 : (speedMultiplier === 1.5 ? 2 : 1);
        speedLabel.textContent = `${speedMultiplier}x`;
    });

    window.addEventListener("resize", () => {
        drawGraphEdges(getStage(currentStageId), currentNodeIndex);
    });

    selectStage(currentStageId, false);
    if (!reducedMotion) {
        animate(stageTabs, {
            opacity: [0, 1],
            transform: ["translateY(8px)", "translateY(0px)"],
        }, {
            delay: stagger(0.05),
            duration: 0.34,
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
            tab.classList.toggle("bg-emerald-50/50", active);
            tab.classList.toggle("shadow-sm", active);
            tab.classList.toggle("border-slate-200", !active);
            tab.classList.toggle("bg-slate-50/70", !active);

            const iconBox = tab.querySelector("[data-stage-icon-box]");
            if (iconBox) {
                iconBox.className = `w-7 h-7 rounded-lg flex items-center justify-center shrink-0 text-xs font-bold transition ${
                    active ? "bg-[#13223a] text-[#00d461]" : "bg-slate-200 text-slate-700"
                }`;
            }
        });

        graphPanel?.setAttribute("aria-labelledby", `stage-tab-${stage.id}`);
        stageStepPill.textContent = `Etapa ${stage.step}`;
        stageTitle.textContent = stage.full_title || stage.title;
        stageStatusBadge.textContent = stage.status_label;
        if (stageSummary) {
            stageSummary.textContent = stage.summary;
        }

        renderNodes(stage);
        selectNode(0, { animateIncomingTo: null, silentBanner: true });
        liveStatus.textContent = stage.nodes[0]?.live_action || stage.summary;

        requestAnimationFrame(() => {
            drawGraphEdges(stage, currentNodeIndex);
            if (shouldAnimateNodes && !reducedMotion) {
                const cards = nodesContainer.querySelectorAll("[data-node-card]");
                animate(cards, {
                    opacity: [0, 1],
                }, {
                    delay: stagger(0.06),
                    duration: 0.28,
                });
            }
        });
    }

    function renderNodes(stage) {
        const cards = stage.nodes.map((node, index) => {
            const styles = STATUS_STYLES[node.status] || STATUS_STYLES.pending;
            const button = createElement(
                "button",
                "traceability-node-2d group text-left p-2.5 sm:p-3 rounded-2xl border transition-all min-h-[44px] flex flex-col justify-between gap-2 bg-slate-900/95 border-slate-700/90 hover:border-[#00d461] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#00d461]",
            );
            button.type = "button";
            button.dataset.nodeCard = node.id;
            button.dataset.nodeIndex = String(index);
            button.style.setProperty("--node-x", `${node.x ?? 50}%`);
            button.style.setProperty("--node-y", `${node.y ?? 50}%`);

            const pulseRing = createElement(
                "span",
                "pointer-events-none absolute -inset-1 rounded-2xl border-2 border-[#00d461] opacity-0",
            );
            pulseRing.dataset.nodeRing = node.id;

            const topRow = createElement("div", "flex items-center justify-between gap-1.5 w-full relative z-10");
            const iconWrap = createElement(
                "div",
                "w-8 h-8 rounded-xl bg-slate-800 border border-slate-700 text-[#00d461] flex items-center justify-center shrink-0 transition",
            );
            iconWrap.dataset.nodeIconWrap = node.id;
            iconWrap.append(createElement("i", `fa-solid ${node.icon} text-xs`));

            const stepBadge = createElement(
                "span",
                `text-[9px] font-extrabold px-1.5 py-0.5 rounded-md whitespace-nowrap ${styles.darkPill}`,
                node.step_label,
            );
            stepBadge.dataset.nodeStatusBadge = node.id;
            topRow.append(iconWrap, stepBadge);

            const body = createElement("div", "space-y-0.5 relative z-10");
            body.append(
                createElement("p", "text-xs font-extrabold text-white leading-tight truncate", node.title),
                createElement("p", "text-[10px] text-slate-400 leading-tight truncate", node.caption),
            );

            const footer = createElement(
                "div",
                "pt-1.5 border-t border-slate-800/90 flex items-center justify-between gap-1.5 w-full text-[10px] relative z-10",
            );
            const statusDot = createElement("span", `w-1.5 h-1.5 rounded-full shrink-0 ${styles.dot}`);
            const badgeText = createElement("span", "font-bold text-[#00d461] truncate flex-1", node.badge);
            footer.append(statusDot, badgeText);

            button.append(pulseRing, topRow, body, footer);
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
            card.classList.toggle("border-[#00d461]", isSelected);
            card.classList.toggle("bg-slate-900", isSelected);
            card.classList.toggle("shadow-lg", isSelected);
            card.classList.toggle("shadow-[#02bc4d]/25", isSelected);
            card.classList.toggle("z-20", isSelected);
            card.classList.toggle("border-emerald-500/45", !isSelected && isPast);
            card.classList.toggle("border-slate-700/90", !isSelected && !isPast);

            const iconWrap = card.querySelector("[data-node-icon-wrap]");
            if (iconWrap) {
                iconWrap.className = `w-8 h-8 rounded-xl flex items-center justify-center shrink-0 transition ${
                    isSelected
                        ? "bg-[#02bc4d] text-[#0b1526] shadow-md shadow-[#02bc4d]/30"
                        : "bg-slate-800 border border-slate-700 text-[#00d461]"
                }`;
            }
        });

        stepCounter.textContent = `${currentNodeIndex + 1} / ${nodes.length}`;
        const progressPercent = ((currentNodeIndex + 1) / nodes.length) * 100;
        animate(playbackBar, { width: `${progressPercent}%` }, { duration: 0.3 });

        if (!options.silentBanner) {
            liveStatus.textContent = activeNode.live_action;
        }

        updateInspector(stage, activeNode);
        renderLiveScene(stage, activeNode);
        drawGraphEdges(stage, currentNodeIndex, options.animateIncomingTo);
    }

    function updateInspector(stage, node) {
        const styles = STATUS_STYLES[node.status] || STATUS_STYLES.pending;
        inspectorIcon.className = `fa-solid ${node.icon} text-sm`;
        inspectorStepLabel.textContent = `Nodo ${node.step_label}`;
        inspectorStatusPill.className = `text-[10px] font-bold px-2 py-0.5 rounded-full ${styles.pill}`;
        inspectorStatusPill.textContent = node.status_label;
        inspectorTitle.textContent = node.title;
        inspectorWhat.textContent = node.what_did;
        inspectorWhy.textContent = node.why_did;
        inspectorActionLink.href = stage.action_url;
        inspectorActionLabel.textContent = stage.action_label;

        if (sceneNodeBadge) {
            sceneNodeBadge.textContent = `${node.step_label} · ${node.title}`;
        }

        const visualData = Array.isArray(node.visual_items) && node.visual_items.length
            ? node.visual_items
            : (node.items || []).map(text => ({
                label: text,
                value: node.badge || "",
                tone: "emerald",
                icon: "fa-check",
            }));

        const listElements = visualData.slice(0, 4).map(item => {
            const tone = TONE_STYLES[item.tone] || TONE_STYLES.slate;
            const li = createElement(
                "li",
                `p-2 rounded-xl border flex flex-col justify-between gap-1.5 ${tone.box}`,
            );

            const top = createElement("div", "flex items-center justify-between gap-2 min-w-0");
            const left = createElement("div", "flex items-center gap-2 min-w-0");
            const iconBox = createElement(
                "span",
                `w-6 h-6 rounded-lg flex items-center justify-center shrink-0 text-[10px] ${tone.icon}`,
            );
            iconBox.append(createElement("i", `fa-solid ${item.icon || "fa-circle-check"}`));
            const labelEl = createElement("span", "text-[11px] font-bold text-white truncate", item.label);
            left.append(iconBox, labelEl);

            const valBadge = createElement(
                "span",
                `text-[10px] font-extrabold px-1.5 py-0.5 rounded-md whitespace-nowrap shrink-0 ${tone.badge}`,
                item.value,
            );
            top.append(left, valBadge);
            li.append(top);

            if (typeof item.score === "number") {
                const track = createElement("div", "w-full bg-slate-950/70 rounded-full h-1 overflow-hidden");
                const fill = createElement("div", "bg-[#00d461] h-full rounded-full");
                fill.style.width = `${Math.max(8, Math.min(100, item.score))}%`;
                track.append(fill);
                li.append(track);
            }

            return li;
        });

        inspectorItems.replaceChildren(...listElements);

        if (!reducedMotion && inspectorCard) {
            animate(listElements, {
                opacity: [0.2, 1],
                transform: ["translateY(4px)", "translateY(0px)"],
            }, {
                delay: stagger(0.04),
                duration: 0.25,
            });
        }
    }

    function renderLiveScene(stage, node) {
        if (!sceneCanvas) {
            return;
        }
        const scene = node.scene || { kind: "default" };
        sceneCanvas.replaceChildren();

        const wrapper = createElement("div", "w-full space-y-2");

        if (scene.kind === "scanner") {
            const box = createElement(
                "div",
                "relative p-3 rounded-xl bg-slate-900/95 border border-slate-800 overflow-hidden h-32 flex items-center justify-between gap-3",
            );
            const beam = createElement(
                "div",
                "trace-scan-beam pointer-events-none absolute left-2 right-2 top-0 h-0.5 bg-gradient-to-r from-transparent via-[#00d461] to-transparent shadow-[0_0_12px_#00d461]",
            );

            const docCard = createElement(
                "div",
                "w-24 h-24 rounded-lg bg-slate-950 border border-slate-700 p-2 flex flex-col justify-between shrink-0 relative",
            );
            docCard.append(
                createElement("div", "flex items-center justify-between text-[10px] text-[#00d461] font-bold", "CV / Perfil"),
                createElement("div", "space-y-1.5", ""),
                createElement(
                    "span",
                    "text-[9px] font-bold px-1.5 py-0.5 rounded bg-[#00d461]/20 text-[#00d461] text-center",
                    scene.has_cv ? "PDF activo" : (scene.has_profile ? "Manual" : "En espera"),
                ),
            );
            const linesWrap = docCard.children[1];
            [85, 65, 92].forEach(w => {
                const line = createElement("div", "h-1.5 rounded bg-slate-700");
                line.style.width = `${w}%`;
                linesWrap.append(line);
            });

            const tokensCol = createElement("div", "flex-1 flex flex-wrap gap-1.5 content-center");
            (scene.tokens || []).forEach((tok, idx) => {
                const chip = createElement(
                    "span",
                    "trace-float-chip px-2 py-1 rounded-lg bg-[#00d461]/15 border border-[#00d461]/40 text-[#00d461] text-[10px] font-bold flex items-center gap-1",
                );
                chip.style.animationDelay = `${idx * 0.18}s`;
                chip.append(createElement("i", "fa-solid fa-wand-magic-sparkles text-[9px]"), createElement("span", "", tok));
                tokensCol.append(chip);
            });

            box.append(beam, docCard, tokensCol);
            wrapper.append(box);
        } else if (scene.kind === "structure") {
            const grid = createElement("div", "grid grid-cols-2 gap-2");
            (scene.blocks || []).forEach(block => {
                const cell = createElement("div", "p-2.5 rounded-xl bg-slate-900/95 border border-slate-800 space-y-1.5");
                const top = createElement("div", "flex items-center justify-between");
                top.append(
                    createElement("span", "text-[10px] text-slate-400 font-semibold", block.label),
                    createElement("span", "text-xs font-extrabold text-[#00d461]", String(block.count)),
                );
                const barBg = createElement("div", "w-full h-1.5 bg-slate-950 rounded-full overflow-hidden");
                const barFill = createElement("div", "h-full bg-gradient-to-r from-[#02bc4d] to-[#00d461] rounded-full");
                const pct = Math.min(100, Math.max(12, block.count * 22));
                barFill.style.width = `${pct}%`;
                barBg.append(barFill);
                cell.append(top, barBg);
                grid.append(cell);
            });
            wrapper.append(grid);
        } else if (scene.kind === "evidence") {
            const radarBox = createElement(
                "div",
                "p-3 rounded-xl bg-slate-900/95 border border-slate-800 flex items-center gap-3 h-32",
            );
            const shieldOrb = createElement(
                "div",
                "w-18 h-18 p-4 rounded-full border-2 border-[#00d461]/40 bg-[#00d461]/10 flex items-center justify-center relative shrink-0",
            );
            const sweep = createElement(
                "div",
                "trace-radar-sweep absolute inset-1 rounded-full border-t-2 border-[#00d461]",
            );
            shieldOrb.append(sweep, createElement("i", "fa-solid fa-shield-halved text-lg text-[#00d461]"));

            const chipWrap = createElement("div", "flex-1 flex flex-wrap gap-1.5");
            const verifiedList = scene.verified?.length ? scene.verified : ["Pendiente de CV"];
            verifiedList.forEach(skill => {
                const pill = createElement(
                    "span",
                    "px-2 py-1 rounded-lg bg-emerald-950/70 border border-emerald-500/40 text-emerald-300 text-[10px] font-bold flex items-center gap-1",
                );
                pill.append(createElement("i", "fa-solid fa-check text-[#00d461] text-[9px]"), createElement("span", "", skill));
                chipWrap.append(pill);
            });
            radarBox.append(shieldOrb, chipWrap);
            wrapper.append(radarBox);
        } else if (scene.kind === "decision_gate") {
            const gateBox = createElement("div", "grid grid-cols-2 gap-2");
            const yesCol = createElement("div", "p-2.5 rounded-xl bg-emerald-950/35 border border-emerald-500/30 space-y-1");
            yesCol.append(
                createElement("p", "text-[10px] font-extrabold text-[#00d461] uppercase", "Confirmadas"),
            );
            (scene.confirmed?.length ? scene.confirmed : ["Sin confirmaciones"]).slice(0, 3).forEach(item => {
                yesCol.append(createElement("div", "text-[10px] text-emerald-200 bg-slate-950/60 px-2 py-0.5 rounded truncate", `✓ ${item}`));
            });

            const gapCol = createElement("div", "p-2.5 rounded-xl bg-amber-950/30 border border-amber-500/30 space-y-1");
            gapCol.append(
                createElement("p", "text-[10px] font-extrabold text-amber-300 uppercase", "Por aclarar / reforzar"),
            );
            const gapList = [...(scene.pending || []), ...(scene.strengthen || [])];
            (gapList.length ? gapList : ["Sin preguntas pendientes"]).slice(0, 3).forEach(item => {
                gapCol.append(createElement("div", "text-[10px] text-amber-200 bg-slate-950/60 px-2 py-0.5 rounded truncate", `? ${item}`));
            });
            gateBox.append(yesCol, gapCol);
            wrapper.append(gateBox);
        } else if (scene.kind === "catalog_grid") {
            const catBox = createElement("div", "p-3 rounded-xl bg-slate-900/95 border border-slate-800 space-y-2.5");
            const dotsRow = createElement("div", "grid grid-cols-6 gap-1.5");
            const totalDots = Math.min(12, scene.total || 12);
            for (let i = 0; i < totalDots; i += 1) {
                const cell = createElement(
                    "div",
                    "trace-float-chip h-5 rounded-md bg-[#00d461]/15 border border-[#00d461]/40 flex items-center justify-center text-[9px] font-bold text-[#00d461]",
                    `#${i + 1}`,
                );
                cell.style.animationDelay = `${i * 0.08}s`;
                dotsRow.append(cell);
            }
            const tagsRow = createElement("div", "flex flex-wrap gap-1.5");
            (scene.titles || []).slice(0, 3).forEach(title => {
                tagsRow.append(
                    createElement("span", "px-2 py-0.5 rounded bg-slate-950 border border-slate-800 text-[10px] text-slate-300 truncate", title),
                );
            });
            catBox.append(dotsRow, tagsRow);
            wrapper.append(catBox);
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

            const list = createElement("div", "space-y-1.5");
            (rows.length ? rows : [{ title: "Completa tu perfil", sub: "Para ver afinidad en vivo", pct: 20 }]).slice(0, 3).forEach(row => {
                const item = createElement("div", "p-2 rounded-xl bg-slate-900/95 border border-slate-800 space-y-1");
                const top = createElement("div", "flex items-center justify-between gap-2 text-[11px]");
                top.append(
                    createElement("span", "font-bold text-white truncate", row.title),
                    createElement("span", "font-extrabold text-[#00d461] shrink-0", `${row.pct}%`),
                );
                const barTrack = createElement("div", "w-full h-1.5 bg-slate-950 rounded-full overflow-hidden");
                const barFill = createElement("div", "h-full bg-gradient-to-r from-[#02bc4d] to-[#00d461] rounded-full");
                barFill.style.width = `${row.pct}%`;
                barTrack.append(barFill);
                item.append(top, barTrack);
                list.append(item);
            });
            wrapper.append(list);
        } else if (scene.kind === "normalizer") {
            const list = createElement("div", "space-y-1.5");
            (scene.pairs || []).forEach(pair => {
                const row = createElement(
                    "div",
                    "p-2 rounded-xl bg-slate-900/95 border border-slate-800 flex items-center justify-between gap-2 text-[11px]",
                );
                row.append(
                    createElement("span", "px-2 py-0.5 rounded bg-slate-800 text-slate-400 font-mono text-[10px] truncate", pair.raw),
                    createElement("i", "fa-solid fa-arrow-right-long text-[#00d461] text-xs shrink-0"),
                    createElement("span", "px-2 py-0.5 rounded bg-[#00d461]/20 text-[#00d461] font-bold text-[10px]", pair.clean),
                );
                list.append(row);
            });
            wrapper.append(list);
        } else if (scene.kind === "filter_gate") {
            const funnel = createElement("div", "p-3 rounded-xl bg-slate-900/95 border border-slate-800 space-y-2");
            const badges = createElement("div", "grid grid-cols-3 gap-1.5 text-center");
            [
                { label: "Modalidad", val: scene.modality },
                { label: "Ciudad", val: scene.city },
                { label: "Salario", val: scene.salary },
            ].forEach(f => {
                const pill = createElement("div", "p-1.5 rounded-lg bg-slate-950 border border-slate-800");
                pill.append(
                    createElement("p", "text-[9px] text-slate-400", f.label),
                    createElement("p", "text-[10px] font-bold text-[#00d461] truncate mt-0.5", f.val),
                );
                badges.append(pill);
            });
            const meter = createElement("div", "flex items-center justify-between pt-1.5 border-t border-slate-800 text-xs");
            meter.append(
                createElement("span", "text-slate-300 font-semibold", "Acordes a tus preferencias"),
                createElement("span", "text-[#00d461] font-extrabold", `${scene.passed} / ${scene.total}`),
            );
            funnel.append(badges, meter);
            wrapper.append(funnel);
        } else if (scene.kind === "letter_composer" || scene.kind === "package_validator" || scene.kind === "submission_dispatch") {
            const dispatchBox = createElement(
                "div",
                "p-3 rounded-xl bg-slate-900/95 border border-slate-800 flex items-center justify-between gap-3 h-32",
            );
            const leftOrb = createElement(
                "div",
                "w-16 h-16 rounded-2xl bg-[#00d461]/15 border border-[#00d461]/40 flex flex-col items-center justify-center shrink-0 text-[#00d461]",
            );
            leftOrb.append(
                createElement(
                    "i",
                    `fa-solid ${scene.kind === "letter_composer" ? "fa-envelope-open-text" : (scene.kind === "package_validator" ? "fa-box-archive" : "fa-paper-plane")} text-lg`,
                ),
            );

            const rightCol = createElement("div", "flex-1 space-y-1.5 min-w-0");
            const items = scene.letters || scene.sent || [];
            if (items.length) {
                items.slice(0, 3).forEach((entry, idx) => {
                    const row = createElement(
                        "div",
                        "trace-float-chip px-2.5 py-1 rounded-lg bg-slate-950 border border-emerald-500/30 flex items-center justify-between gap-2 text-[10px]",
                    );
                    row.style.animationDelay = `${idx * 0.15}s`;
                    row.append(
                        createElement("span", "font-bold text-white truncate", `${entry.title} · ${entry.company}`),
                        createElement("span", "font-extrabold text-[#00d461] shrink-0", `${entry.score}%`),
                    );
                    rightCol.append(row);
                });
            } else {
                rightCol.append(
                    createElement(
                        "div",
                        "px-2.5 py-2 rounded-lg bg-slate-950 border border-slate-800 text-[11px] text-slate-300",
                        scene.kind === "package_validator"
                            ? `${scene.applied_count || 0} paquete(s) validados · ${scene.warnings_count || 0} aviso(s)`
                            : "Selecciona y confirma vacantes para activar este flujo",
                    ),
                );
            }
            dispatchBox.append(leftOrb, rightCol);
            wrapper.append(dispatchBox);
        } else {
            const grid = createElement("div", "space-y-1.5");
            const previewItems = (node.visual_items || []).slice(0, 3);
            previewItems.forEach(item => {
                const row = createElement(
                    "div",
                    "p-2 rounded-xl bg-slate-900/95 border border-slate-800 flex items-center justify-between gap-2",
                );
                const left = createElement("div", "flex items-center gap-2 min-w-0");
                left.append(
                    createElement("i", `fa-solid ${item.icon || "fa-circle-nodes"} text-[#00d461] text-xs`),
                    createElement("span", "text-xs font-bold text-white truncate", item.label),
                );
                row.append(
                    left,
                    createElement("span", "text-[10px] font-extrabold px-2 py-0.5 rounded bg-[#00d461]/20 text-[#00d461] shrink-0", item.value),
                );
                grid.append(row);
            });
            wrapper.append(grid);
        }

        sceneCanvas.append(wrapper);
        if (!reducedMotion) {
            animate(wrapper, {
                opacity: [0, 1],
                transform: ["scale(0.96)", "scale(1)"],
            }, {
                easing: spring({ stiffness: 280, damping: 24 }),
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

        const linesGroup = document.createElementNS(SVG_NS, "g");
        const particlesGroup = document.createElementNS(SVG_NS, "g");
        const labelsGroup = document.createElementNS(SVG_NS, "g");
        svgLayer.append(linesGroup, particlesGroup, labelsGroup);

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
            baseTrack.setAttribute("stroke", "#1e293b");
            baseTrack.setAttribute("stroke-width", "2.5");
            baseTrack.setAttribute("stroke-dasharray", "4 5");
            linesGroup.appendChild(baseTrack);

            const toIdx = nodeIndexMap.get(edge.to) ?? 0;
            const fromIdx = nodeIndexMap.get(edge.from) ?? 0;
            const isEdgeVisited = toIdx <= activeNodeIdx && fromIdx <= activeNodeIdx;
            const isEdgeEnabled = edge.active !== false;

            const activePath = document.createElementNS(SVG_NS, "path");
            activePath.setAttribute("d", d);
            activePath.setAttribute("fill", "none");
            activePath.setAttribute("stroke", isEdgeEnabled ? "#00d461" : "#475569");
            activePath.setAttribute("stroke-width", isEdgeVisited ? "2.75" : "1.75");
            activePath.setAttribute("stroke-linecap", "round");
            if (isEdgeVisited && isEdgeEnabled) {
                activePath.classList.add("trace-edge-stream");
                activePath.style.opacity = "0.95";
            } else {
                activePath.style.opacity = isEdgeEnabled ? "0.28" : "0.12";
            }
            linesGroup.appendChild(activePath);

            [
                { cx: x1, cy: y1 },
                { cx: x2, cy: y2 },
            ].forEach(pt => {
                const port = document.createElementNS(SVG_NS, "circle");
                port.setAttribute("cx", String(pt.cx));
                port.setAttribute("cy", String(pt.cy));
                port.setAttribute("r", "3.5");
                port.setAttribute("fill", isEdgeVisited ? "#00d461" : "#334155");
                port.setAttribute("stroke", "#0b1526");
                port.setAttribute("stroke-width", "1.5");
                linesGroup.appendChild(port);
            });

            if (edge.label && isDesktop2D && typeof activePath.getTotalLength === "function") {
                const totalLen = activePath.getTotalLength();
                const midPt = activePath.getPointAtLength(totalLen * 0.5);
                const pillWidth = Math.max(58, edge.label.length * 5.6 + 14);
                const pillHeight = 18;

                const pillRect = document.createElementNS(SVG_NS, "rect");
                pillRect.setAttribute("x", String(midPt.x - pillWidth / 2));
                pillRect.setAttribute("y", String(midPt.y - pillHeight / 2));
                pillRect.setAttribute("width", String(pillWidth));
                pillRect.setAttribute("height", String(pillHeight));
                pillRect.setAttribute("rx", "9");
                pillRect.setAttribute("fill", "#0f172a");
                pillRect.setAttribute("stroke", isEdgeVisited ? "#00d461" : "#334155");
                pillRect.setAttribute("stroke-width", "1");
                labelsGroup.appendChild(pillRect);

                const labelText = document.createElementNS(SVG_NS, "text");
                labelText.setAttribute("x", String(midPt.x));
                labelText.setAttribute("y", String(midPt.y + 0.5));
                labelText.setAttribute("text-anchor", "middle");
                labelText.setAttribute("dominant-baseline", "middle");
                labelText.setAttribute("fill", isEdgeVisited ? "#00d461" : "#94a3b8");
                labelText.setAttribute("font-size", "9.5");
                labelText.setAttribute("font-weight", "700");
                labelText.textContent = edge.label;
                labelsGroup.appendChild(labelText);
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
        const durationMs = Math.round(520 / speedMultiplier);

        const pulseDot = document.createElementNS(SVG_NS, "circle");
        pulseDot.setAttribute("r", "5");
        pulseDot.setAttribute("fill", "#00d461");
        pulseDot.setAttribute("stroke", "#ffffff");
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

    async function playAllStages() {
        const runId = ++playbackRunId;
        setPlayingState(true);
        for (const stage of stages) {
            if (runId !== playbackRunId) {
                break;
            }
            selectStage(stage.id, true);
            await waitMs(reducedMotion ? 40 : Math.round(240 / speedMultiplier));
            await runStageSequence(stage, runId);
            await waitMs(reducedMotion ? 40 : Math.round(300 / speedMultiplier));
        }
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
            const statusBadge = card?.querySelector("[data-node-status-badge]");
            const originalText = statusBadge?.textContent || "";

            if (statusBadge) {
                statusBadge.textContent = "Activo";
            }

            let ringAnim = null;
            if (ring && !reducedMotion && typeof ring.animate === "function") {
                ringAnim = ring.animate(
                    [
                        { opacity: 0.95, transform: "scale(0.98)" },
                        { opacity: 0.2, transform: "scale(1.05)" },
                        { opacity: 0.95, transform: "scale(0.98)" },
                    ],
                    {
                        duration: Math.round(560 / speedMultiplier),
                        iterations: 2,
                        easing: "ease-in-out",
                    },
                );
                activeWaapiAnimations.push(ringAnim);
            }

            await waitMs(reducedMotion ? 60 : Math.round(840 / speedMultiplier));

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
            if (statusBadge) {
                statusBadge.textContent = originalText;
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
        playIcon.className = playing ? "fa-solid fa-stop" : "fa-solid fa-play";
        playLabel.textContent = playing ? "Detener" : "Simular grafo";
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
