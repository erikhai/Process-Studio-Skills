"""Client-specific settings for the process dependency graph skill.

This is the only file a new client normally needs to edit.
"""

# --- Which strings count as document IDs -----------------------------------

# Prefixes that are known document types, mapped to a document type.
# Matching is case-insensitive for these (so "sop-mnt-14" is repaired to "SOP-MNT-014").
PREFIX_TYPES = {
    "SOP": "procedure",
    "WI": "procedure",
    "PRC": "procedure",
    "PROC": "procedure",
    "STD": "procedure",
    "WP": "procedure",
    "JSA": "procedure",
    "FRM": "form",
    "FORM": "form",
    "TMP": "form",
    "CHK": "form",
    "POL": "policy",
    "REG": "policy",
    "MAN": "document",
    "GDL": "document",
    "RPT": "document",
    "SPC": "document",
}

# True: an all-uppercase prefix that is not listed above is also accepted (type "document").
# False: strict mode, only the prefixes listed above are accepted.
ACCEPT_UNLISTED_PREFIXES = True

# Uppercase prefixes that look like IDs but are not documents.
PREFIX_STOPLIST = {
    "ISO", "IEC", "IEEE", "ANSI", "ASTM", "DIN", "RFC", "UTF", "HTTP", "HTTPS",
    "PDF", "COVID", "REV", "STEP", "FIG", "TABLE", "PAGE", "SEC", "NO", "ID",
    "ISBN", "USB", "CVE", "TOP", "OSHA", "CFR", "EN", "GDPR",
}

# An unlisted prefix needs at least this many digits ("UTF-8" is rejected, "ABC-12" accepted).
MIN_DIGITS_UNLISTED = 2

# Numbers are zero-padded to this width so "SOP-MNT-14" and "SOP-MNT-014" are one ID.
# Set to 0 to switch padding off (for clients whose IDs are not zero-padded).
PAD_NUMBERS_TO = 3

# --- Systems of record -----------------------------------------------------

# alias (matched case-insensitively as whole words) -> canonical name
SYSTEMS = {
    "SAP PM": "SAP PM",
    "SAP S/4HANA": "SAP S/4HANA",
    "SAP ERP": "SAP ERP",
    "SAP": "SAP",
    "IBM Maximo": "Maximo",
    "Maximo": "Maximo",
    "ServiceNow": "ServiceNow",
    "Salesforce": "Salesforce",
    "Workday": "Workday",
    "Oracle EBS": "Oracle EBS",
    "SharePoint": "SharePoint",
    "SCADA": "SCADA",
    "CMMS": "CMMS",
}

# --- Phrases that change the direction or meaning of a reference -------------

# "Used by SOP-X" means SOP-X depends on this page, not the other way round.
DEPENDED_ON_BY_PHRASES = [
    "used by", "referenced by", "cited by", "required by", "called by",
    "invoked by", "linked from", "backlinks",
]

# References like these are version lineage, not dependencies. They are recorded but get no edge.
LINEAGE_PHRASES = [
    "supersedes", "superseded by", "replaces", "replaced by", "obsoletes",
    "obsoleted by", "previous version", "formerly",
]

# --- Section headings --------------------------------------------------------

# References under these headings are counted but do not create edges.
CHANGE_LOG_HEADINGS = [
    "revision history", "change log", "changelog", "change history",
    "document history", "version history", "amendment record", "amendments",
]

# Headings that open a list of related documents (still dependencies unless the heading is a
# DEPENDED_ON_BY phrase, in which case the whole section is read as "depended on by").
RELATED_HEADINGS = [
    "related documents", "references", "see also", "referenced documents",
    "associated documents", "related procedures",
]

# --- Limits ------------------------------------------------------------------

# The platform keeps roughly the first 32k characters of converted text on a wiki page.
# A page at or beyond this length may have lost references.
TRUNCATION_SUSPECT_CHARS = 31500

# How many lines at the top of a page are searched for the page's own ID.
OWN_ID_SEARCH_LINES = 30

# Maximum length of a context snippet stored with a reference.
CONTEXT_CHARS = 160

# Mermaid diagram size.
MERMAID_TOP_DOCS = 25
MERMAID_MAX_EXTRA_NODES = 10

# The full graph JSON is embedded in the report only up to this many nodes plus edges.
EMBED_JSON_MAX_ITEMS = 4000

# Also write dependency_graph.json and dependency_graph.mmd next to the report.
# Off by default: the report alone is the guaranteed deliverable.
WRITE_SIDECARS = False

# Rows shown in ranked tables.
TOP_RANKED_ROWS = 25

# Maximum contextual relationship-evidence rows embedded in the Markdown report. Keep this
# bounded so large batch reports remain usable; the report says when rows are omitted.
EVIDENCE_MAX_ROWS = 200
