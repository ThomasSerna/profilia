export function calculateRoleScore(role, profile) {
    if (!profile) {
        return 0;
    }

    const requiredSkills = splitDataAttribute(role.requiredSkills);
    const preferredSkills = splitDataAttribute(role.preferredSkills);
    const experienceAreas = splitDataAttribute(role.experienceAreas);
    const profileSkills = collectProfileSkills(profile);
    const experienceText = collectExperienceText(profile);
    let score = 0;

    requiredSkills.forEach(skill => {
        if (profileHasSkill(profileSkills, skill)) {
            score += 4;
        }
    });

    preferredSkills.forEach(skill => {
        if (profileHasSkill(profileSkills, skill)) {
            score += 2;
        }
    });

    experienceAreas.forEach(area => {
        const normalizedArea = normalizeText(area);

        if (normalizedArea && experienceText.includes(normalizedArea)) {
            score += 1;
        }
    });

    return score;
}

function collectProfileSkills(profile) {
    const skills = [];

    if (Array.isArray(profile.skills)) {
        skills.push(...profile.skills);
    }

    if (Array.isArray(profile.experience)) {
        profile.experience.forEach(experience => {
            if (Array.isArray(experience.technologies)) {
                skills.push(...experience.technologies);
            }
        });
    }

    return new Set(skills.map(canonicalSkill).filter(Boolean));
}

function collectExperienceText(profile) {
    if (!Array.isArray(profile.experience)) {
        return "";
    }

    const parts = [];

    profile.experience.forEach(experience => {
        if (experience.role) {
            parts.push(experience.role);
        }

        if (experience.description) {
            parts.push(experience.description);
        }

        if (Array.isArray(experience.technologies)) {
            parts.push(...experience.technologies);
        }
    });

    return normalizeText(parts.join(" "));
}

function profileHasSkill(profileSkills, targetSkill) {
    const target = canonicalSkill(targetSkill);
    return Boolean(target) && profileSkills.has(target);
}

function canonicalSkill(value) {
    const normalized = normalizeText(value);
    const aliases = {
        "springboot": "spring boot",
        "spring boot framework": "spring boot",
        "rest api": "rest apis",
        "restful api": "rest apis",
        "restful apis": "rest apis",
        "api rest": "rest apis",
        "apis rest": "rest apis",
        "js": "javascript",
        "ts": "typescript",
        "postgres": "postgresql",
    };

    if (normalized.includes("rest") && normalized.includes("api")) {
        return "rest apis";
    }

    return aliases[normalized] || normalized;
}

function normalizeText(value) {
    return String(value || "")
        .toLowerCase()
        .normalize("NFD")
        .replace(/[\u0300-\u036f]/g, "")
        .replace(/[^a-z0-9+#.]+/g, " ")
        .trim();
}

function splitDataAttribute(value) {
    return value ? value.split("|").map(item => item.trim()).filter(Boolean) : [];
}
