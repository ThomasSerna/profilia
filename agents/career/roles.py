from .schemas import RoleProfile

def get_role_by_name(name: str) -> RoleProfile | None:
    for role in ROLE_CATALOG:
        if role.name.lower() == name.lower():
            return role

    return None

ROLE_CATALOG = [

    RoleProfile(
        name="Backend Developer",
        required_skills=[
            "Python",
            "Java",
            "REST APIs",
            "SQL",
            "Git",
        ],
        preferred_skills=[
            "Docker",
            "Cloud",
            "CI/CD",
            "Spring Boot",
            "Django",
        ],
        experience_areas=[
            "backend",
            "databases",
            "apis",
        ],
    ),

    RoleProfile(
        name="Frontend Developer",
        required_skills=[
            "HTML",
            "CSS",
            "JavaScript",
            "Git",
        ],
        preferred_skills=[
            "React",
            "TypeScript",
            "Vue",
            "Angular",
        ],
        experience_areas=[
            "frontend",
            "web development",
            "user interfaces",
        ],
    ),

    RoleProfile(
        name="Full Stack Developer",
        required_skills=[
            "JavaScript",
            "REST APIs",
            "SQL",
            "Git",
        ],
        preferred_skills=[
            "React",
            "Python",
            "Java",
            "Docker",
            "Cloud",
        ],
        experience_areas=[
            "frontend",
            "backend",
            "databases",
            "web development",
        ],
    ),

    RoleProfile(
        name="Mobile Developer",
        required_skills=[
            "Git",
            "REST APIs",
            "Mobile Development",
        ],
        preferred_skills=[
            "Kotlin",
            "Swift",
            "Flutter",
            "React Native",
        ],
        experience_areas=[
            "mobile",
            "android",
            "ios",
        ],
    ),

    RoleProfile(
        name="Data Analyst",
        required_skills=[
            "SQL",
            "Excel",
            "Data Analysis",
        ],
        preferred_skills=[
            "Python",
            "Power BI",
            "Tableau",
            "Statistics",
        ],
        experience_areas=[
            "data analysis",
            "reporting",
            "business intelligence",
        ],
    ),

    RoleProfile(
        name="Data Scientist",
        required_skills=[
            "Python",
            "Statistics",
            "Machine Learning",
            "SQL",
        ],
        preferred_skills=[
            "Pandas",
            "NumPy",
            "Scikit-learn",
            "Data Visualization",
        ],
        experience_areas=[
            "data science",
            "machine learning",
            "statistical analysis",
        ],
    ),

    RoleProfile(
        name="Data Engineer",
        required_skills=[
            "Python",
            "SQL",
            "Databases",
        ],
        preferred_skills=[
            "Spark",
            "Kafka",
            "Cloud",
            "ETL",
            "Docker",
        ],
        experience_areas=[
            "data engineering",
            "data pipelines",
            "databases",
        ],
    ),

    RoleProfile(
        name="Machine Learning Engineer",
        required_skills=[
            "Python",
            "Machine Learning",
            "Git",
        ],
        preferred_skills=[
            "Docker",
            "Cloud",
            "Scikit-learn",
            "TensorFlow",
            "PyTorch",
        ],
        experience_areas=[
            "machine learning",
            "artificial intelligence",
            "model deployment",
        ],
    ),

    RoleProfile(
        name="DevOps Engineer",
        required_skills=[
            "Git",
            "Linux",
            "Docker",
            "CI/CD",
        ],
        preferred_skills=[
            "Kubernetes",
            "AWS",
            "Azure",
            "Terraform",
        ],
        experience_areas=[
            "devops",
            "cloud",
            "deployment",
            "infrastructure",
        ],
    ),

    RoleProfile(
        name="Cloud Engineer",
        required_skills=[
            "Cloud",
            "Linux",
            "Networking",
        ],
        preferred_skills=[
            "AWS",
            "Azure",
            "Docker",
            "Kubernetes",
            "Terraform",
        ],
        experience_areas=[
            "cloud",
            "infrastructure",
            "networking",
        ],
    ),

    RoleProfile(
        name="QA Automation Engineer",
        required_skills=[
            "Software Testing",
            "Git",
            "Automation",
        ],
        preferred_skills=[
            "Selenium",
            "Python",
            "Java",
            "CI/CD",
        ],
        experience_areas=[
            "testing",
            "quality assurance",
            "test automation",
        ],
    ),

    RoleProfile(
        name="Cybersecurity Analyst",
        required_skills=[
            "Cybersecurity",
            "Networking",
            "Linux",
        ],
        preferred_skills=[
            "Python",
            "SIEM",
            "Cloud Security",
            "Security Testing",
        ],
        experience_areas=[
            "cybersecurity",
            "network security",
            "security analysis",
        ],
    ),

]