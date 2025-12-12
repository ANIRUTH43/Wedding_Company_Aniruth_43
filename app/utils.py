import re

def slugify(name: str) -> str:
    """
    Convert a name to a safe lowercase slug suitable for collection names.
    Example: "Acme Inc." -> "acme_inc"
    """
    s = name.lower().strip()
    # replace any sequence of non-alphanumeric chars with underscore
    s = re.sub(r'[^a-z0-9]+', '_', s)
    # trim underscores
    s = s.strip('_')
    return s
