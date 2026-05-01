"""
Sweden Job Market — PRIMARY filtering (v4).

Lessons from v3:
- hard_blacklist was too aggressive. IT-tekniker / Drifttekniker get
  mis-tagged onto real Data Engineer roles at Klarna, ICA Bank, etc.
- HEADLINE is the cleanest signal — even "100% not data" occupations
  should yield to clear data wording in headline.
- Regex was too strict — missed AI-Engineer (hyphen), " ai ", AI Lead, etc.

New stage order (HEADLINE always wins):
  Stage 1: HEADLINE has data wording → KEEP no matter what occupation says
  Stage 2: OCCUPATION has data token → KEEP
  Stage 3: HARD blacklist (genuine non-data professions) → DROP
  Stage 4: SOFT blacklist (occupation says non-data, but mis-tagging happens) → DROP
  Stage 5: catch-all → KEEP + review flag
"""

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

today = datetime.now().strftime("%Y-%m-%d")
INPUT_PATH = RAW_DIR / f"{today}_jobtech_all.json"


# =====================================================================
# HEADLINE patterns — be generous; this is the primary keep signal
# =====================================================================

HEADLINE_DATA_PATTERNS = [
    # Core English data titles
    r"\bdata scientist\b",
    r"\bdata engineer\b",
    r"\bdata analyst\b",
    r"\bdata architect\b",
    r"\bdata platform\b",
    r"\bdata warehouse\b",
    r"\bdata steward\b",
    r"\bdata manager\b",
    r"\bdata\s*&\s*ai\b",
    r"\bdata och ai\b",
    r"\bdata\s*&\s*analytics\b",
    r"\bdata och analytics\b",
    r"\bdata-?driven\b",
    r"\bdatadrivna?\b",                  # Swedish "data-driven"
    
    # Swedish data titles
    r"\bdataingenjör\b",
    r"\bdataanalytiker\b",
    r"\bdatabasutvecklare\b",
    r"\bdatabasdesigner\b",
    
    # Analytics
    r"\banalytics engineer\b",
    r"\banalytical engineer\b",
    r"\banalytics architect\b",
    r"\banalytics specialist\b",
    r"\banalys(?:omr|av|för|drivn)",     # Swedish 'analys' word stems (analysförmåga, analysavdelning)
    r"\banalys\b",                       # standalone "analys"
    
    # ML / AI titles
    r"\bml engineer\b",
    r"\bml scientist\b",
    r"\bml/ai\b",
    r"\bai/ml\b",
    r"\bml/data\b",
    r"\bai/data\b",
    r"\bmachine learning\b",
    r"\bmaskininlärning\b",
    r"\bmlops\b",
    r"\bai\s*[-/]?\s*engineer\b",        # AI Engineer, AI-Engineer, AI/Engineer
    r"\bai\s*[-/]?\s*architect\b",
    r"\bai\s*[-/]?\s*specialist\b",
    r"\bai\s*[-/]?\s*expert\b",
    r"\bai\s*[-/]?\s*developer\b",
    r"\bai\s*[-/]?\s*lead\b",
    r"\bai product lead\b",
    r"\bai\s*[-/]?\s*pioneer\b",
    r"\bai-pionjär\b",
    r"\bgenai\b",
    r"\bllm\b",
    r"\binriktning mot ai\b",            # "[role] inriktning mot AI" common SE phrasing
    r"\bmot ai\b",
    r"\bmed ai\b",
    r"\bai-?kompetens\b",
    
    # BI
    r"\bbi developer\b",
    r"\bbi-?utvecklare\b",
    r"\bbi analyst\b",
    r"\bbi-?specialist\b",
    r"\bpower bi\b",
    
    # Stats
    r"\bstatistiker\b",
    r"\bbiostatistiker\b",
    
    # Variants
    r"\bdecision scientist\b",
    r"\bresearch scientist\b",
    r"\bquantitative\b",
    r"\bdatavetenskap\b",
    
    # Data platform technologies (when in headline, signals data role)
    r"\bmicrosoft fabric\b",
    r"\bdatabricks\b",
    r"\bsnowflake\b",
]
HEADLINE_DATA_RE = re.compile("|".join(HEADLINE_DATA_PATTERNS), re.IGNORECASE)


# =====================================================================
# Occupation-based fallback signals
# =====================================================================

DATA_OCCUPATION_TOKENS = (
    "data", "scientist", "analytik", "statistik", "databas",
)

# HARD blacklist — occupations that are GENUINELY not data work,
# regardless of mis-tagging. Be very conservative here.
# When in doubt, put it in soft blacklist instead.
OCCUPATION_HARD_BLACKLIST = {
    # HR / recruiting
    "rekryterare/rekryteringskonsult",
    "personal- och hr-specialister",
    "researcher, rekrytering",
    "marknads- och försäljningsassistenter",
    # Pure physics / chemistry / hardware research
    "fysiker",
    "partikelfysiker",
    # Hardware / mechanical / energy engineering
    "ingenjörer och tekniker inom maskinteknik",
    "civilingenjörsyrken inom elektroteknik",
    "ingenjörer och tekniker inom elektroteknik",
    "energiingenjör",
    "forskningsingenjör, el-tele",
    "civilingenjör, produktion, elektronik",
    # Academia (per user decision)
    "universitets- och högskolelektor",
    "universitets- och högskoleadjunkt",
    "professor",
}

# SOFT blacklist — occupations where mis-tagging is common.
# DROP only if headline ALSO has no data wording.
OCCUPATION_SOFT_BLACKLIST = {
    "applikationskonsult",
    "affärskonsult, it",
    "verksamhetskonsult, it",
    "projektledare, it",
    "systemutvecklare/programmerare",
    "mjukvaruutvecklare",
    "civilingenjör, systemutveckling",
    "backend-utvecklare",
    "frontend-utvecklare",
    "systemanalytiker/systemutredare",
    "molntekniker/cloudutvecklare",
    "devops utvecklare",
    "it-säkerhetschef",
    "it-strateg",
    "it-arkitekt/lösningsarkitekt",
    "processansvarig, itil",
    "säljassistent",
    "informationsassistent",
    "applikationsingenjör",
    "forskare, it",
    "systemansvarig",
    "systemförvaltare",
    "interaktionsdesigner",
    # Moved from hard → soft (these get mis-tagged onto data roles)
    "it-tekniker/datatekniker",
    "drifttekniker, data",
}


# =====================================================================
# Role-type tagging
# =====================================================================

LEADERSHIP_RE = re.compile(
    r"\blead\b|\bhead of\b|\bchef\b|\bansvarig\b|\bdirector\b|"
    r"\bmanager\b|\bprincipal\b|\barchitect\b|\bproduct lead\b|"
    r"\btech lead\b",
    re.IGNORECASE,
)
DEVOPS_CLOUD_RE = re.compile(
    r"\bdevops\b|\bcloud\b|\bplatform engineer\b|\bsre\b|"
    r"\binfrastructure\b|\binfrastruktur\b|\bsysops\b|"
    r"\bmolntekniker\b|\bcloudutvecklare\b",
    re.IGNORECASE,
)


# =====================================================================
# Helpers
# =====================================================================

def _occ_label(ad: dict) -> str:
    return (ad.get("occupation") or {}).get("label", "").lower()


def _headline(ad: dict) -> str:
    return (ad.get("headline") or "").lower()


def _has_data_in_headline(ad: dict) -> bool:
    return bool(HEADLINE_DATA_RE.search(_headline(ad)))


def _has_data_in_occupation(ad: dict) -> bool:
    occ = _occ_label(ad)
    return any(tok in occ for tok in DATA_OCCUPATION_TOKENS)


# =====================================================================
# Filter pipeline
# =====================================================================

def classify(ad: dict) -> tuple[bool, str | None, str]:
    """Returns (passed, drop_reason_or_None, stage_label)."""
    occ = _occ_label(ad)

    # STAGE 1 — headline says data → KEEP no matter what
    if _has_data_in_headline(ad):
        return True, None, "stage1_headline_data"

    # STAGE 2 — occupation says data → KEEP
    if _has_data_in_occupation(ad):
        return True, None, "stage2_occupation_data"

    # STAGE 3 — hard blacklist → DROP
    if occ in OCCUPATION_HARD_BLACKLIST:
        return False, f"hard_blacklist: {occ!r}", "stage3_hard_drop"

    # STAGE 4 — soft blacklist (no data signal anywhere) → DROP
    if occ in OCCUPATION_SOFT_BLACKLIST:
        return False, f"soft_blacklist_no_data_signal: {occ!r}", "stage4_soft_drop"

    # STAGE 5 — unknown occupation, no signals → KEEP cautiously
    return True, None, "stage5_review"


# =====================================================================
# Tagging (unchanged)
# =====================================================================

PUBLIC_SECTOR_MARKERS = (
    "kommun", "region ", "regionen", "universitet", "högskola",
    "myndighet", "verket", "polisen", "regeringskansliet",
    "karolinska", "sjukhus", "totalförsvarets", "försvarsmakten",
    "skolan", "institutet", "inspektionen", "länsstyrelsen",
)

CONSULTANCY_KNOWN = {
    "academic work sweden ab", "veritaz ab", "incluso ab", "techrytera ab",
    "knowit ab (publ)", "knowit", "alten sverige ab", "semicon service nordic ab",
    "professional galaxy ab", "friday väst ab", "framtiden i sverige ab",
    "infosys technologies (sweden) ab", "doer bemanning ab", "bytespoke ab",
    "wrknest ab", "tng group ab", "skill kompetenspartner ab",
    "multimind holding ab", "ants akademiskt nätverk av tekniska studenter ab",
    "oddwork sweden ab", "bravura sverige ab", "studentconsulting sweden ab (publ)",
    "kraftsam rekrytering & bemanning ab", "quattro bemanning & rekrytering ab",
    "2complete ab", "tech talents consulting i sverige ab", "hays ab",
    "devotum ab", "logikfabriken ab", "digitalenta ab", "nexer ab",
    "maxitech ab", "swedq ab", "redeploy ab", "qrios ab", "auticon ab",
    "effektify ab", "enhanza ab", "eghed göteborg ab", "sway sourcing sweden ab",
    "happy group ab", "lynqa ab", "iver accelerate ab", "justera group ab",
    "ats sweden hr ab",
}

CONSULTANCY_PATTERNS = ("bemanning", "rekrytering", "konsult", "consulting", "sourcing")


def tag_employer_type(ad: dict) -> str:
    employer = (ad.get("employer") or {}).get("name", "") or ""
    e = employer.lower()
    if any(m in e for m in PUBLIC_SECTOR_MARKERS):
        return "public"
    if e in CONSULTANCY_KNOWN:
        return "consultancy"
    if any(p in e for p in CONSULTANCY_PATTERNS):
        return "consultancy"
    return "company"


def tag_role_type(ad: dict) -> str:
    headline = _headline(ad)
    if LEADERSHIP_RE.search(headline):
        return "leadership"
    if DEVOPS_CLOUD_RE.search(headline):
        return "devops_cloud"
    return "ic"


# =====================================================================
# Main
# =====================================================================

def main():
    print(f"Loading from {INPUT_PATH}")
    raw = json.load(INPUT_PATH.open())
    ads = list(raw.values())
    print(f"Loaded {len(ads)} ads\n")

    drop_reasons: Counter = Counter()
    stage_counts: Counter = Counter()

    for ad in ads:
        passed, reason, stage = classify(ad)
        ad["_filter_pass"] = passed
        ad["_drop_reason"] = reason
        ad["_filter_stage"] = stage
        ad["_employer_type"] = tag_employer_type(ad)
        ad["_role_type"] = tag_role_type(ad)
        if not passed:
            drop_reasons[reason.split(":")[0]] += 1
        stage_counts[stage] += 1

    kept = [ad for ad in ads if ad["_filter_pass"]]
    dropped = [ad for ad in ads if not ad["_filter_pass"]]

    full_path = PROCESSED_DIR / f"{today}_filtered.json"
    with full_path.open("w", encoding="utf-8") as f:
        json.dump({ad["id"]: ad for ad in ads}, f, ensure_ascii=False, indent=2)
    clean_path = PROCESSED_DIR / f"{today}_clean.json"
    with clean_path.open("w", encoding="utf-8") as f:
        json.dump({ad["id"]: ad for ad in kept}, f, ensure_ascii=False, indent=2)

    print("=" * 70)
    print(f"FILTER RESULTS (v4)")
    print("=" * 70)
    print(f"  Input:   {len(ads)}")
    print(f"  Kept:    {len(kept)} ({100*len(kept)/len(ads):.0f}%)")
    print(f"  Dropped: {len(dropped)}")

    print(f"\n--- Stage breakdown ---")
    for stage, count in stage_counts.most_common():
        print(f"  {count:4d}  {stage}")

    print(f"\n--- Drop reasons ---")
    for reason, count in drop_reasons.most_common():
        print(f"  {count:4d}  {reason}")

    print(f"\n--- Employer type (kept only) ---")
    for t, count in Counter(ad["_employer_type"] for ad in kept).most_common():
        print(f"  {count:4d}  {t}")

    print(f"\n--- Role type (kept only) ---")
    for t, count in Counter(ad["_role_type"] for ad in kept).most_common():
        print(f"  {count:4d}  {t}")

    print(f"\n--- ALL DROPPED ads ({len(dropped)}) ---")
    for ad in dropped:
        occ = (ad.get("occupation") or {}).get("label", "")
        emp = (ad.get("employer") or {}).get("name", "")
        print(f"  [{ad['_drop_reason'][:55]}]")
        print(f"     {ad.get('headline')}  @  {emp}  (occ={occ!r})")

    review = [ad for ad in kept if ad["_filter_stage"] == "stage5_review"]
    if review:
        print(f"\n--- KEPT via stage5 review ({len(review)} ads) ---")
        for ad in review:
            occ = (ad.get("occupation") or {}).get("label", "")
            emp = (ad.get("employer") or {}).get("name", "")
            print(f"  [occ={occ!r}]  {ad.get('headline')}  @  {emp}")

    print(f"\n--- Target company coverage (kept ads) ---")
    targets = ["klarna", "spotify", "storytel", "king", "embark", "kry",
               "sana", "mentimeter", "tink", "voi", "epidemic sound",
               "qasa", "bankid", "hexagon", "tacton", "neko", "alva",
               "swedbank", "seb", "handelsbanken", "avanza", "lendo",
               "schibsted", "ica", "volvo", "stena", "stegra",
               "lovable", "stravito", "wolt", "apotea"]
    for t in sorted(targets):
        matches = [ad for ad in kept
                   if ad.get("employer") and t in (ad["employer"].get("name") or "").lower()]
        if matches:
            print(f"  {t:20s}: {len(matches)}")

    print(f"\n--- Saved files ---")
    print(f"  Full tagged: {full_path}")
    print(f"  Clean only:  {clean_path}")


if __name__ == "__main__":
    main()