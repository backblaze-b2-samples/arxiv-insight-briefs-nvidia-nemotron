"""Bundled arxiv subject taxonomy — used to validate router output.

This is a curated subset of the arxiv category list. Hallucinated codes from
the router (e.g. "cs.AGI") get dropped before the search step. If your sample
needs a category that isn't here, add it — the validation is a static check.
Source: https://arxiv.org/category_taxonomy
"""

# (code, human label). Order doesn't matter — looked up as a set.
ARXIV_CATEGORIES: dict[str, str] = {
    # Computer Science
    "cs.AI": "Artificial Intelligence",
    "cs.AR": "Hardware Architecture",
    "cs.CC": "Computational Complexity",
    "cs.CE": "Computational Engineering, Finance, and Science",
    "cs.CG": "Computational Geometry",
    "cs.CL": "Computation and Language",
    "cs.CR": "Cryptography and Security",
    "cs.CV": "Computer Vision and Pattern Recognition",
    "cs.CY": "Computers and Society",
    "cs.DB": "Databases",
    "cs.DC": "Distributed, Parallel, and Cluster Computing",
    "cs.DL": "Digital Libraries",
    "cs.DM": "Discrete Mathematics",
    "cs.DS": "Data Structures and Algorithms",
    "cs.ET": "Emerging Technologies",
    "cs.FL": "Formal Languages and Automata Theory",
    "cs.GL": "General Literature",
    "cs.GR": "Graphics",
    "cs.GT": "Computer Science and Game Theory",
    "cs.HC": "Human-Computer Interaction",
    "cs.IR": "Information Retrieval",
    "cs.IT": "Information Theory",
    "cs.LG": "Machine Learning",
    "cs.LO": "Logic in Computer Science",
    "cs.MA": "Multiagent Systems",
    "cs.MM": "Multimedia",
    "cs.MS": "Mathematical Software",
    "cs.NA": "Numerical Analysis",
    "cs.NE": "Neural and Evolutionary Computing",
    "cs.NI": "Networking and Internet Architecture",
    "cs.OH": "Other Computer Science",
    "cs.OS": "Operating Systems",
    "cs.PF": "Performance",
    "cs.PL": "Programming Languages",
    "cs.RO": "Robotics",
    "cs.SC": "Symbolic Computation",
    "cs.SD": "Sound",
    "cs.SE": "Software Engineering",
    "cs.SI": "Social and Information Networks",
    "cs.SY": "Systems and Control",
    # Statistics
    "stat.AP": "Applications",
    "stat.CO": "Computation",
    "stat.ME": "Methodology",
    "stat.ML": "Machine Learning",
    "stat.OT": "Other Statistics",
    "stat.TH": "Statistics Theory",
    # Electrical Engineering and Systems Science
    "eess.AS": "Audio and Speech Processing",
    "eess.IV": "Image and Video Processing",
    "eess.SP": "Signal Processing",
    "eess.SY": "Systems and Control",
    # Mathematics (a small slice — extend if needed)
    "math.OC": "Optimization and Control",
    "math.IT": "Information Theory",
    "math.PR": "Probability",
    "math.ST": "Statistics Theory",
}


def is_valid_category(code: str) -> bool:
    """Treat both fully-qualified codes ('cs.NI') and archive prefixes ('cs') as valid."""
    if code in ARXIV_CATEGORIES:
        return True
    # Allow the archive-level prefix so a router can say "anything in cs.*"
    return code in {c.split(".", 1)[0] for c in ARXIV_CATEGORIES}


def filter_valid(codes: list[str]) -> tuple[list[str], list[str]]:
    """Return (valid, dropped) given a list of category codes."""
    valid: list[str] = []
    dropped: list[str] = []
    for raw in codes:
        code = raw.strip()
        if is_valid_category(code):
            valid.append(code)
        else:
            dropped.append(code)
    return valid, dropped
