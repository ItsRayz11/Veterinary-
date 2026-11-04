"""Pharmacological class tree and the exact-substance mapping used to file generics under it.

Non-clinical classification only: no doses, indications or safety claims. A generic is filed
under a
class only when it is a single substance whose name (without salt words and strengths)
exactly matches an entry below; combinations and unknown names stay unclassified.
Classes follow standard textbook pharmacological groupings. The generics keep their own review
status, so a filed generic is still labelled "Imported, not reviewed" until a reviewer signs off.
"""

import re

# (parent, name)
CLASS_TREE: list[tuple[str | None, str]] = [
    (None, "Antibacterials"),
    ("Antibacterials", "Penicillins"),
    ("Antibacterials", "Cephalosporins"),
    ("Antibacterials", "Aminoglycosides"),
    ("Antibacterials", "Tetracyclines"),
    ("Antibacterials", "Fluoroquinolones"),
    ("Antibacterials", "Macrolides"),
    ("Antibacterials", "Sulfonamides"),
    ("Antibacterials", "Lincosamides"),
    ("Antibacterials", "Phenicols"),
    (None, "Antiparasitics"),
    ("Antiparasitics", "Macrocyclic lactones"),
    ("Antiparasitics", "Benzimidazoles"),
    ("Antiparasitics", "Salicylanilides"),
    ("Antiparasitics", "Imidazothiazoles"),
    ("Antiparasitics", "Antiprotozoals and anticoccidials"),
    ("Antiparasitics", "Ectoparasiticides"),
    (None, "Anti-inflammatories"),
    ("Anti-inflammatories", "NSAIDs"),
    ("Anti-inflammatories", "Corticosteroids"),
    (None, "Antihistamines"),
    (None, "Reproductive hormones"),
    (None, "Anaesthetics and sedatives"),
    (None, "Diuretics"),
]

_MEMBERS = {
    "Penicillins": ["amoxicillin", "amoxycillin", "ampicillin", "benzylpenicillin", "cloxacillin"],
    "Cephalosporins": [
        "ceftiofur",
        "cefquinome",
        "cefalexin",
        "cephalexin",
        "ceftriaxone",
        "cefazolin",
        "cefotaxime",
        "cefixime",
        "cefoperazone",
    ],
    "Aminoglycosides": [
        "gentamicin",
        "streptomycin",
        "neomycin",
        "kanamycin",
        "amikacin",
        "gentamycin",
        "apramycin",
    ],
    "Tetracyclines": ["oxytetracycline", "tetracycline", "doxycycline", "chlortetracycline"],
    "Fluoroquinolones": [
        "enrofloxacin",
        "ciprofloxacin",
        "norfloxacin",
        "danofloxacin",
        "marbofloxacin",
        "levofloxacin",
        "ofloxacin",
        "sarafloxacin",
        "pefloxacin",
    ],
    "Macrolides": [
        "tylosin",
        "erythromycin",
        "tilmicosin",
        "azithromycin",
        "tulathromycin",
        "gamithromycin",
    ],
    "Sulfonamides": [
        "sulfadimidine",
        "sulphadimidine",
        "sulfadiazine",
        "sulphadiazine",
        "sulfamethoxazole",
        "sulphamethoxazole",
    ],
    "Lincosamides": ["lincomycin", "clindamycin"],
    "Phenicols": ["florfenicol", "chloramphenicol", "thiamphenicol"],
    "Macrocyclic lactones": ["ivermectin", "doramectin", "eprinomectin", "abamectin", "moxidectin"],
    "Benzimidazoles": [
        "albendazole",
        "fenbendazole",
        "oxfendazole",
        "mebendazole",
        "triclabendazole",
    ],
    "Salicylanilides": ["closantel", "oxyclozanide", "rafoxanide"],
    "Imidazothiazoles": ["levamisole"],
    "Antiprotozoals and anticoccidials": ["toltrazuril", "amprolium", "diclazuril"],
    "Ectoparasiticides": ["deltamethrin", "cypermethrin", "amitraz"],
    "NSAIDs": [
        "meloxicam",
        "diclofenac",
        "flunixin",
        "ketoprofen",
        "aceclofenac",
        "carprofen",
        "phenylbutazone",
        "piroxicam",
        "tolfenamic acid",
    ],
    "Corticosteroids": ["dexamethasone", "prednisolone", "betamethasone", "hydrocortisone"],
    "Antihistamines": ["chlorpheniramine", "pheniramine", "diphenhydramine"],
    "Reproductive hormones": ["oxytocin", "cloprostenol", "dinoprost"],
    "Anaesthetics and sedatives": ["xylazine", "ketamine", "lidocaine"],
    "Diuretics": ["furosemide", "frusemide"],
}
SUBSTANCE_CLASS = {s: c for c, subs in _MEMBERS.items() for s in subs}

_NOISE = re.compile(
    r"\b(as|eq|equivalent|to|base|trihydrate|dihydrate|monohydrate|hydrochloride|hcl|sodium|"
    r"potassium|sulphate|sulfate|phosphate|acetate|meglumine|maleate|tartrate|oxime|mesylate|methanesulfonate|thiocyanate|hyclate|mesilate|"
    r"injection|usp|bp|ip|vet)\b|\d+(\.\d+)?\s*(mg|g|ml|%|iu)?",
    re.I,
)


def class_for(name: str) -> str | None:
    """Class name for a single-substance generic name, else None."""
    if "+" in name or "," in name or " and " in name.lower():
        return None
    text = re.sub(r"\([^)]*\)", " ", name)
    words = re.sub(r"\s+", " ", _NOISE.sub(" ", text)).strip().lower()
    return SUBSTANCE_CLASS.get(words)
