import { animate, spring, stagger } from "../motion.js";

const SVG_NS = "http://www.w3.org/2000/svg";

const STATUS_STYLES = {
    completed: {
        pill: "bg-emerald-100 text-[#008736] border border-emerald-200",
        darkPill: "bg-[#00d461]/20 text-[#00d461] border border-[#00d461]/40",
        icon: "fa-circle-check text-[#00d461]",
    },
    in_progress: {
        pill: "bg-amber-100 text-amber-800 border border-amber-200",
        darkPill: "bg-amber-400/20 text-amber-300 border border-amber-400/40",
        icon: "fa-clock text-amber-300",
    },
    preview: {
        pill: "bg-sky-100 text-sky-800 border border-sky-200",
        darkPill: "bg-sky-400/20 text-sky-300 border border-sky-400/40",
        icon: "fa-eye text-sky-300",
    },
    pending: {
        pill: "bg-slate-200 text-slate-600 border border-slate-300",
        darkPill: "bg-slate-800 text-slate-400 border border-slate-700",
        icon: "fa-hourglass-start text-slate-400",
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
    const stepList = document.getElementById("traceability-step-list");

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
        selectNode(nextIndex, { animateEdgeFrom: nextIndex > 0 ? nextIndex - 1 : null });
    });

    speedBtn?.addEventListener("click", () => {
        speedMultiplier = speedMultiplier === 1 ? 1.5 : 1;
        speedLabel.textContent = `${speedMultiplier}x`;
    });

    window.addEventListener("resize", () => {
        drawGraphEdges(getStage(currentStageId), currentNodeIndex);
    });

    selectStage(currentStageId, false);
    if (!reducedMotion) {
        animate(stageTabs, {
            opacity: [0, 1],
            transform: ["translateY(10px)", "translateY(0px)"],
        }, {
            delay: stagger(0.06),
            duration: 0.38,
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
            tab.classList.toggle("border-slate-200", !active);
            tab.classList.toggle("bg-slate-50/70", !active);

            const iconBox = tab.querySelector("[data-stage-icon-box]");
            if (iconBox) {
                iconBox.className = `w-8 h-8 rounded-lg flex items-center justify-center shrink-0 text-xs font-bold transition ${
                    active ? "bg-[#13223a] text-[#00d461]" : "bg-slate-200 text-slate-700"
                }`;
            }
        });

        graphPanel?.setAttribute("aria-labelledby", `stage-tab-${stage.id}`);
        stageStepPill.textContent = `Etapa ${stage.step}`;
        stageTitle.textContent = stage.title;
        stageStatusBadge.textContent = stage.status_label;
        stageSummary.textContent = stage.summary;

        renderNodes(stage);
        renderStepList(stage);
        selectNode(0, { animateEdgeFrom: null, silentBanner: true });
        liveStatus.textContent = stage.nodes[0]?.live_action || stage.summary;

        requestAnimationFrame(() => {
            drawGraphEdges(stage, currentNodeIndex);
            if (shouldAnimateNodes && !reducedMotion) {
                const cards = nodesContainer.querySelectorAll("[data-node-card]");
                animate(cards, {
                    opacity: [0, 1],
                    transform: ["translateY(12px) scale(0.97)", "translateY(0px) scale(1)"],
                }, {
                    delay: stagger(0.07),
                    easing: spring({ stiffness: 280, damping: 24 }),
                });
            }
        });
    }

    function renderNodes(stage) {
        const cards = stage.nodes.map((node, index) => {
            const styles = STATUS_STYLES[node.status] || STATUS_STYLES.pending;
            const button = createElement(
                "button",
                "traceability-node-card group relative text-left p-4 rounded-2xl border transition-all min-h-[44px] flex flex-col justify-between gap-3 bg-slate-900/90 border-slate-700/90 hover:border-[#00d461]/70 focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#00d461]",
            );
            button.type = "button";
            button.dataset.nodeCard = node.id;
            button.dataset.nodeIndex = String(index);

            const pulseRing = createElement(
                "span",
                "pointer-events-none absolute -inset-0.5 rounded-2xl border-2 border-[#00d461] opacity-0",
            );
            pulseRing.dataset.nodeRing = node.id;

            const topRow = createElement("div", "flex items-start justify-between gap-2 w-full relative z-10");
            const iconWrap = createElement(
                "div",
                "w-10 h-10 rounded-xl bg-slate-800 border border-slate-700 text-[#00d461] flex items-center justify-center shrink-0 transition",
            );
            iconWrap.dataset.nodeIconWrap = node.id;
            iconWrap.append(createElement("i", `fa-solid ${node.icon} text-sm`));

            const statusBadge = createElement(
                "span",
                `text-[10px] font-bold px-2 py-0.5 rounded-full whitespace-nowrap ${styles.darkPill}`,
                node.status_label,
            );
            statusBadge.dataset.nodeStatusBadge = node.id;
            topRow.append(iconWrap, statusBadge);

            const body = createElement("div", "space-y-1 relative z-10");
            body.append(
                createElement("p", "text-[10px] font-extrabold uppercase tracking-wider text-[#00d461]", node.step_label),
                createElement("p", "text-xs sm:text-sm font-extrabold text-white leading-snug", node.title),
                createElement("p", "text-[11px] text-slate-300 leading-relaxed", node.caption),
            );

            const footer = createElement(
                "div",
                "pt-2.5 border-t border-slate-800 flex items-center justify-between gap-2 w-full text-[10px] relative z-10",
            );
            footer.append(
                createElement("span", "font-semibold text-slate-300 truncate", node.badge),
                createElement("span", "text-[#00d461] font-bold flex items-center gap-1 shrink-0", "Ver detalle →"),
            );

            button.append(pulseRing, topRow, body, footer);
            button.addEventListener("click", () => {
                stopPlayback();
                selectNode(index, { animateEdgeFrom: index > 0 ? index - 1 : null });
            });
            return button;
        });

        nodesContainer.replaceChildren(...cards);
    }

    function renderStepList(stage) {
        const rows = stage.nodes.map((node, index) => {
            const styles = STATUS_STYLES[node.status] || STATUS_STYLES.pending;
            const li = createElement("li", "");
            const btn = createElement(
                "button",
                "w-full text-left p-3 rounded-xl border border-slate-200 hover:border-[#02bc4d] bg-slate-50 hover:bg-white transition flex items-start justify-between gap-3 min-h-[44px] focus-visible:outline focus-visible:outline-2 focus-visible:outline-[#008736]",
            );
            btn.type = "button";
            btn.dataset.stepListIndex = String(index);

            const left = createElement("div", "flex items-start gap-2.5 min-w-0");
            const num = createElement(
                "span",
                "w-6 h-6 rounded-lg bg-[#13223a] text-[#00d461] text-[11px] font-extrabold flex items-center justify-center shrink-0 mt-0.5",
                String(index + 1),
            );
            const textWrap = createElement("div", "min-w-0");
            textWrap.append(
                createElement("p", "text-xs font-bold text-[#13223a] truncate", node.title),
                createElement("p", "text-[11px] text-slate-500 line-clamp-2 mt-0.5", node.what_did),
            );
            left.append(num, textWrap);

            const badge = createElement(
                "span",
                `text-[10px] font-bold px-2 py-0.5 rounded-full whitespace-nowrap shrink-0 ${styles.pill}`,
                node.status_label,
            );

            btn.append(left, badge);
            btn.addEventListener("click", () => {
                stopPlayback();
                selectNode(index, { animateEdgeFrom: index > 0 ? index - 1 : null });
            });
            li.append(btn);
            return li;
        });

        stepList.replaceChildren(...rows);
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
            card.classList.toggle("shadow-[#02bc4d]/20", isSelected);
            card.classList.toggle("border-emerald-500/40", !isSelected && isPast);
            card.classList.toggle("border-slate-700/90", !isSelected && !isPast);

            const iconWrap = card.querySelector("[data-node-icon-wrap]");
            if (iconWrap) {
                iconWrap.className = `w-10 h-10 rounded-xl flex items-center justify-center shrink-0 transition ${
                    isSelected
                        ? "bg-[#02bc4d] text-[#13223a] shadow-md shadow-[#02bc4d]/30"
                        : "bg-slate-800 border border-slate-700 text-[#00d461]"
                }`;
            }
        });

        const stepButtons = Array.from(stepList.querySelectorAll("[data-step-list-index]"));
        stepButtons.forEach((btn, idx) => {
            const isSelected = idx === currentNodeIndex;
            btn.classList.toggle("border-[#02bc4d]", isSelected);
            btn.classList.toggle("bg-emerald-50/50", isSelected);
            btn.classList.toggle("border-slate-200", !isSelected);
            btn.classList.toggle("bg-slate-50", !isSelected);
        });

        stepCounter.textContent = `Paso ${currentNodeIndex + 1} de ${nodes.length}`;
        const progressPercent = ((currentNodeIndex + 1) / nodes.length) * 100;
        animate(playbackBar, { width: `${progressPercent}%` }, { duration: 0.35 });

        if (!options.silentBanner) {
            liveStatus.textContent = activeNode.live_action;
        }

        updateInspector(stage, activeNode);
        drawGraphEdges(stage, currentNodeIndex, options.animateEdgeFrom);
    }

    function updateInspector(stage, node) {
        const styles = STATUS_STYLES[node.status] || STATUS_STYLES.pending;
        inspectorIcon.className = `fa-solid ${node.icon}`;
        inspectorStepLabel.textContent = node.step_label;
        inspectorStatusPill.className = `text-[10px] font-bold px-2 py-0.5 rounded-full ${styles.pill}`;
        inspectorStatusPill.textContent = node.status_label;
        inspectorTitle.textContent = node.title;
        inspectorWhat.textContent = node.what_did;
        inspectorWhy.textContent = node.why_did;
        inspectorActionLink.href = stage.action_url;
        inspectorActionLabel.textContent = stage.action_label;

        const listElements = (node.items || []).map(text => {
            const li = createElement(
                "li",
                "flex items-start gap-2.5 p-2.5 rounded-xl bg-slate-50 border border-slate-200/80",
            );
            li.append(
                createElement("i", "fa-solid fa-check text-[#02bc4d] mt-1 shrink-0 text-[11px]"),
                createElement("span", "leading-relaxed", text),
            );
            return li;
        });
        inspectorItems.replaceChildren(...listElements);

        if (!reducedMotion && inspectorCard) {
            animate(
                [inspectorWhat, inspectorWhy, ...listElements],
                {
                    opacity: [0.25, 1],
                    transform: ["translateY(5px)", "translateY(0px)"],
                },
                {
                    delay: stagger(0.045),
                    duration: 0.3,
                },
            );
        }
    }

    function drawGraphEdges(stage, activeUpToIndex, animateSingleEdgeIndex = null) {
        if (!svgLayer || !graphBoard) {
            return;
        }
        const boardRect = graphBoard.getBoundingClientRect();
        if (!boardRect.width || !boardRect.height) {
            return;
        }

        svgLayer.setAttribute("viewBox", `0 0 ${boardRect.width} ${boardRect.height}`);
        svgLayer.replaceChildren();

        const cards = Array.from(nodesContainer.querySelectorAll("[data-node-card]"));
        if (cards.length < 2) {
            return;
        }

        const isHorizontal = window.innerWidth >= 1024;

        for (let i = 0; i < cards.length - 1; i += 1) {
            const fromRect = cards[i].getBoundingClientRect();
            const toRect = cards[i + 1].getBoundingClientRect();
            const edgeMeta = stage.edges?.[i] || { label: "" };

            let x1;
            let y1;
            let x2;
            let y2;
            let d;

            if (isHorizontal) {
                x1 = fromRect.right - boardRect.left;
                y1 = fromRect.top - boardRect.top + fromRect.height / 2;
                x2 = toRect.left - boardRect.left;
                y2 = toRect.top - boardRect.top + toRect.height / 2;
                const cx = (x1 + x2) / 2;
                d = `M ${x1} ${y1} C ${cx} ${y1}, ${cx} ${y2}, ${x2} ${y2}`;
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
            baseTrack.setAttribute("stroke", "#334155");
            baseTrack.setAttribute("stroke-width", "2.5");
            baseTrack.setAttribute("stroke-dasharray", "5 5");
            svgLayer.appendChild(baseTrack);

            const isEdgeActive = i < activeUpToIndex;
            const activePath = document.createElementNS(SVG_NS, "path");
            activePath.setAttribute("d", d);
            activePath.setAttribute("fill", "none");
            activePath.setAttribute("stroke", "#00d461");
            activePath.setAttribute("stroke-width", "3");
            activePath.setAttribute("stroke-linecap", "round");
            activePath.style.opacity = isEdgeActive ? "1" : "0";
            svgLayer.appendChild(activePath);

            if (edgeMeta.label) {
                const midX = (x1 + x2) / 2;
                const midY = isHorizontal ? (y1 + y2) / 2 - 14 : (y1 + y2) / 2;
                const labelText = document.createElementNS(SVG_NS, "text");
                labelText.setAttribute("x", String(midX));
                labelText.setAttribute("y", String(midY));
                labelText.setAttribute("text-anchor", "middle");
                labelText.setAttribute("dominant-baseline", "middle");
                labelText.setAttribute("fill", isEdgeActive ? "#00d461" : "#94a3b8");
                labelText.setAttribute("font-size", "10");
                labelText.setAttribute("font-weight", "700");
                labelText.textContent = edgeMeta.label;
                svgLayer.appendChild(labelText);
            }

            if (animateSingleEdgeIndex === i && !reducedMotion) {
                animateSvgEdge(activePath);
            }
        }
    }

    function animateSvgEdge(pathEl) {
        if (typeof pathEl.getTotalLength !== "function") {
            return null;
        }
        const length = Math.max(24, pathEl.getTotalLength());
        pathEl.style.opacity = "1";
        pathEl.setAttribute("stroke-dasharray", String(length));
        pathEl.setAttribute("stroke-dashoffset", String(length));

        const durationMs = Math.round(520 / speedMultiplier);

        if (typeof pathEl.animate === "function") {
            const lineAnim = pathEl.animate(
                [
                    { strokeDashoffset: length, opacity: 0.5 },
                    { strokeDashoffset: 0, opacity: 1 },
                ],
                {
                    duration: durationMs,
                    easing: "cubic-bezier(0.22, 1, 0.36, 1)",
                    fill: "forwards",
                },
            );
            activeWaapiAnimations.push(lineAnim);
        }

        const pulseDot = document.createElementNS(SVG_NS, "circle");
        pulseDot.setAttribute("r", "5.5");
        pulseDot.setAttribute("fill", "#00d461");
        pulseDot.setAttribute("stroke", "#ffffff");
        pulseDot.setAttribute("stroke-width", "2");
        svgLayer.appendChild(pulseDot);

        const sampleSteps = 16;
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
            await waitMs(reducedMotion ? 40 : Math.round(260 / speedMultiplier));
            await runStageSequence(stage, runId);
            await waitMs(reducedMotion ? 40 : Math.round(350 / speedMultiplier));
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

            selectNode(i, { animateEdgeFrom: i > 0 ? i - 1 : null });
            const card = cards[i];
            const ring = card?.querySelector("[data-node-ring]");
            const statusBadge = card?.querySelector("[data-node-status-badge]");
            const originalText = statusBadge?.textContent || "";

            if (statusBadge) {
                statusBadge.textContent = "Procesando ahora…";
            }

            if (card && !reducedMotion) {
                animate(
                    card,
                    { transform: ["scale(1)", "scale(1.035)", "scale(1)"] },
                    { easing: spring({ stiffness: 300, damping: 18 }) },
                );
            }

            let ringAnim = null;
            if (ring && !reducedMotion && typeof ring.animate === "function") {
                ringAnim = ring.animate(
                    [
                        { opacity: 0.9, transform: "scale(0.99)" },
                        { opacity: 0.25, transform: "scale(1.03)" },
                        { opacity: 0.9, transform: "scale(0.99)" },
                    ],
                    {
                        duration: Math.round(620 / speedMultiplier),
                        iterations: 2,
                        easing: "ease-in-out",
                    },
                );
                activeWaapiAnimations.push(ringAnim);
            }

            await waitMs(reducedMotion ? 60 : Math.round(920 / speedMultiplier));

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
        playLabel.textContent = playing ? "Detener animación" : "Reproducir proceso";
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
