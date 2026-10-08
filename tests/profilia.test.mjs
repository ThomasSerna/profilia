// Run with: node tests/profilia.test.mjs
import assert from "node:assert/strict";
import { calculateRoleScore } from "../static/js/profilia/role-recommendations.js";

const profile = {
    skills: ["JS", "RESTful API", "TS", "Postgres", "C++", "C#"],
    experience: [{
        role: "Ingeniero de Software",
        description: "Análisis de datos y backend.",
        technologies: ["SpringBoot", "Python"],
    }],
};

assert.equal(calculateRoleScore({}, null), 0);
assert.equal(calculateRoleScore({}, profile), 0);
assert.equal(calculateRoleScore({ requiredSkills: "Python" }, {}), 0);
assert.equal(calculateRoleScore({ requiredSkills: "javascript | rest apis | " }, profile), 8);
assert.equal(calculateRoleScore({ preferredSkills: "TypeScript|PostgreSQL" }, profile), 4);
assert.equal(calculateRoleScore({ requiredSkills: "Spring Boot|Python" }, profile), 8);
assert.equal(calculateRoleScore({ experienceAreas: "analisis de datos|BACKEND" }, profile), 2);
assert.equal(calculateRoleScore({ requiredSkills: "Java|C" }, profile), 0);
assert.equal(calculateRoleScore({ requiredSkills: "C++|C#" }, profile), 8);
assert.equal(calculateRoleScore({
    requiredSkills: "JavaScript|REST APIs",
    preferredSkills: "TypeScript|PostgreSQL",
    experienceAreas: "análisis de datos",
}, profile), 13);
assert.equal(calculateRoleScore({ requiredSkills: "JavaScript" }, {
    skills: ["JS", "JavaScript"],
    experience: [{ technologies: ["JS"] }],
}), 4);

console.log("Profilia: recomendaciones verificadas.");
