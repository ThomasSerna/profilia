/**
 * Local Motion engine powered by the Web Animations API (WAAPI).
 * Provides animate(), stagger(), spring(), and timeline() primitives
 * for declarative and physics-based UI animations in Profilia.
 */

function resolveElements(target) {
    if (!target) {
        return [];
    }
    if (typeof target === "string") {
        return Array.from(document.querySelectorAll(target));
    }
    if (target instanceof Element || target instanceof SVGElement) {
        return [target];
    }
    if (Array.isArray(target) || target instanceof NodeList || target instanceof HTMLCollection) {
        return Array.from(target).filter(Boolean);
    }
    return [];
}

/**
 * Stagger delay generator for multi-element animations.
 * @param {number} intervalSeconds - Delay step in seconds between items.
 * @param {{ start?: number, from?: "first" | "last" | "center" }} [options]
 */
export function stagger(intervalSeconds = 0.08, options = {}) {
    const start = options.start || 0;
    const from = options.from || "first";
    return (index, total) => {
        let stepIndex = index;
        if (from === "last") {
            stepIndex = Math.max(0, total - 1 - index);
        } else if (from === "center") {
            stepIndex = Math.abs((total - 1) / 2 - index);
        }
        return start + stepIndex * intervalSeconds;
    };
}

/**
 * Generates an approximate spring easing curve and duration for WAAPI.
 * @param {{ stiffness?: number, damping?: number, mass?: number }} [options]
 */
export function spring(options = {}) {
    const stiffness = options.stiffness ?? 260;
    const damping = options.damping ?? 22;
    const mass = options.mass ?? 1;
    const ratio = damping / (2 * Math.sqrt(stiffness * mass));
    const duration = Math.min(0.95, Math.max(0.28, (4.2 / Math.sqrt(stiffness / mass)) * (ratio < 1 ? 1.15 : 0.9)));
    const easing = ratio < 0.85
        ? "cubic-bezier(0.22, 1.32, 0.36, 1)"
        : "cubic-bezier(0.16, 1, 0.3, 1)";
    return { type: "spring", duration, easing };
}

function buildKeyframes(keyframes) {
    if (Array.isArray(keyframes)) {
        return keyframes;
    }
    const entries = Object.entries(keyframes || {});
    const maxSteps = entries.reduce((max, [, value]) => (Array.isArray(value) ? Math.max(max, value.length) : max), 1);

    if (maxSteps <= 1) {
        const frame = {};
        for (const [prop, value] of entries) {
            frame[prop] = value;
        }
        return [frame];
    }

    const frames = [];
    for (let step = 0; step < maxSteps; step += 1) {
        const frame = {};
        for (const [prop, value] of entries) {
            if (Array.isArray(value)) {
                frame[prop] = value[Math.min(step, value.length - 1)];
            } else {
                frame[prop] = value;
            }
        }
        frames.push(frame);
    }
    return frames;
}

/**
 * Animates one or more DOM/SVG elements using the Web Animations API.
 * @param {Element|Element[]|NodeList|string} target
 * @param {Object|Array} keyframes
 * @param {Object} [options]
 */
export function animate(target, keyframes, options = {}) {
    const elements = resolveElements(target);
    const reducedMotion = typeof window !== "undefined"
        && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;

    const springConfig = options.easing && typeof options.easing === "object" && options.easing.type === "spring"
        ? options.easing
        : null;

    const baseDurationSec = options.duration ?? (springConfig ? springConfig.duration : 0.42);
    const durationMs = reducedMotion ? 0 : Math.max(0, baseDurationSec * 1000);
    const easing = springConfig
        ? springConfig.easing
        : (typeof options.easing === "string" ? options.easing : "cubic-bezier(0.22, 1, 0.36, 1)");
    const fill = options.fill ?? "forwards";
    const iterations = reducedMotion ? 1 : (options.iterations ?? 1);
    const direction = options.direction ?? "normal";

    const frames = buildKeyframes(keyframes);
    const animations = [];

    elements.forEach((el, index) => {
        const rawDelay = typeof options.delay === "function"
            ? options.delay(index, elements.length)
            : (options.delay || 0);
        const delayMs = reducedMotion ? 0 : Math.max(0, rawDelay * 1000);

        if (typeof el.animate === "function" && durationMs > 0) {
            const waapi = el.animate(frames, {
                duration: durationMs,
                delay: delayMs,
                easing,
                fill,
                iterations,
                direction,
            });
            animations.push(waapi);
        } else if (frames.length > 0) {
            const finalFrame = frames[frames.length - 1];
            Object.entries(finalFrame).forEach(([prop, value]) => {
                if (prop in el.style) {
                    el.style[prop] = String(value);
                }
            });
        }
    });

    const finished = animations.length
        ? Promise.all(animations.map(anim => anim.finished.catch(() => null)))
        : Promise.resolve();

    return {
        animations,
        finished,
        stop() {
            animations.forEach(anim => {
                try {
                    anim.cancel();
                } catch {
                    // Ignore already finished animations.
                }
            });
        },
    };
}

/**
 * Executes a sequence of [target, keyframes, options] segments in order.
 * @param {Array<[Element|string, Object|Array, Object?]>} sequence
 */
export async function timeline(sequence = []) {
    const active = [];
    for (const segment of sequence) {
        const [target, keyframes, options] = segment;
        const control = animate(target, keyframes, options);
        active.push(control);
        await control.finished;
    }
    return active;
}
