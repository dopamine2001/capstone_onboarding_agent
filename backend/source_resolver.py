"""
Fuzzy matching and synonym resolution for source types.

Runs alongside the LLM as a deterministic backstop, so typos and
abbreviations ("pg", "postge", "mssql", "ms sql") reliably resolve to the
right source type even if the LLM's own guess is imperfect — and genuinely
ambiguous phrasing ("a SQL database", "an API") is flagged instead of
silently guessed.
"""
import difflib

SYNONYMS = {
    "postgresql": ["postgres", "postgre", "postgress", "postge", "pg", "postgresql"],
    "mysql": ["mysql", "maria", "mariadb"],
    "sqlserver": ["sql server", "sqlserver", "mssql", "ms sql", "microsoft sql", "msssql"],
    "rest_api": ["rest api", "rest", "webservice", "web service", "http api", "api"],
}

# Broad/ambiguous phrasing that should trigger a clarifying question instead
# of a guess. Only applies to "SQL database" style phrasing, since that
# genuinely spans multiple engines we support (Postgres/MySQL/SQL Server).
# A bare mention of "API" isn't ambiguous in this system since REST API is
# our only API-like category — it resolves directly instead.
AMBIGUOUS_PHRASES = ["sql database", "sql db", "a database", "the database"]

CANONICAL_TYPES = list(SYNONYMS.keys())
ALL_SYNONYMS = [syn for syns in SYNONYMS.values() for syn in syns]


def _canonical_for_synonym(synonym):
    for canonical, synonyms in SYNONYMS.items():
        if synonym in synonyms:
            return canonical
    return None


def resolve_source_type(text):
    """
    Returns (source_type_or_None, is_ambiguous).
    """
    text_lower = text.lower()

    # 1. Exact synonym containment match (checked first, most reliable)
    for canonical, synonyms in SYNONYMS.items():
        for syn in synonyms:
            if syn in text_lower:
                return canonical, False

    # 2. Explicit ambiguous phrasing with no specific engine mentioned
    for phrase in AMBIGUOUS_PHRASES:
        if phrase in text_lower:
            return None, True

    # 3. Fuzzy match against individual words (catches typos like "postge")
    words = text_lower.replace(",", " ").replace(".", " ").split()
    for word in words:
        matches = difflib.get_close_matches(word, ALL_SYNONYMS, n=1, cutoff=0.75)
        if matches:
            canonical = _canonical_for_synonym(matches[0])
            if canonical:
                return canonical, False

    return None, False