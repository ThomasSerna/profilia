const careerResultsSection = document.getElementById("career-results-section");
const careerResultsTitle = document.getElementById("career-results-title");
const careerResults = document.getElementById("career-results");
const careerRoleTemplate = document.getElementById("career-role-template");
const careerRequirementTemplate = document.getElementById("career-requirement-template");

export function renderAssessments(assessments, moveFocus = true) {
    careerResults.replaceChildren();

    for (const assessment of assessments) {
        const article = careerRoleTemplate.content.firstElementChild.cloneNode(true);
        article.querySelector("[data-role-name]").textContent = assessment.role_name;

        for (const requirement of assessment.requirements) {
            const row = careerRequirementTemplate.content.firstElementChild.cloneNode(true);
            row.querySelector("[data-skill-name]").textContent = requirement.skill;

            const styles = {
                evidencia_en_perfil: [
                    "Con evidencia",
                    "bg-emerald-50",
                    "text-emerald-800",
                ],
                cumple: [
                    "Compatible según Kev",
                    "bg-emerald-50",
                    "text-emerald-800",
                ],
                incumple: [
                    "Contradicción según Kev",
                    "bg-rose-50",
                    "text-rose-800",
                ],
                sin_evidencia: [
                    "Sin evidencia suficiente",
                    "bg-slate-100",
                    "text-slate-600",
                ],
            };

            const [label, background, color] = styles[requirement.status];
            const badge = row.querySelector("[data-skill-status]");
            badge.textContent = label;
            badge.classList.add(background, color);

            const mentions = requirement.evidence.map(item => {
                const origin = item.source.startsWith("skills[")
                    ? "Habilidades"
                    : "Experiencia";

                return `${origin}: ${item.value}`;
            });

            const evidenceText = row.querySelector("[data-skill-evidence]");
            evidenceText.textContent = mentions.join(" · ");
            evidenceText.hidden = mentions.length === 0;

            const probabilitiesText = row.querySelector("[data-skill-probabilities]");
            const probabilities = requirement.probabilities;
            probabilitiesText.hidden = !probabilities;

            if (probabilities) {
                probabilitiesText.textContent =
                    `Opciones de Kev: compatible ${Math.round(probabilities.cumple * 100)}% · ` +
                    `contradicción ${Math.round(probabilities.incumple * 100)}% · ` +
                    `sin evidencia ${Math.round(probabilities.sin_evidencia * 100)}%`;
            }

            const selector = requirement.category === "required"
                ? "[data-required-skills]"
                : "[data-preferred-skills]";

            article.querySelector(selector).append(row);
        }

        careerResults.append(article);
    }

    careerResultsSection.classList.toggle("hidden", assessments.length === 0);

    if (moveFocus && assessments.length > 0) {
        careerResultsTitle.focus({ preventScroll: true });
        careerResultsSection.scrollIntoView({ block: "start" });
    }
}
