"""Non-clinical reference data (countries, species, units, forms). No doses or product facts."""

COUNTRIES = [
    # iso2, name, currency, regulator, sort
    ("PK", "Pakistan", "PKR", "Drug Regulatory Authority of Pakistan (DRAP)", 1),
    ("IN", "India", "INR", "CDSCO / Department of Animal Husbandry and Dairying", 2),
    ("AE", "United Arab Emirates", "AED", "", 50),
    ("US", "United States", "USD", "FDA Center for Veterinary Medicine", 60),
    ("GB", "United Kingdom", "GBP", "Veterinary Medicines Directorate", 61),
]

# slug, name, parent slug, food producing
SPECIES = [
    ("cattle", "Cattle", None, True),
    ("buffalo", "Buffalo", None, True),
    ("sheep", "Sheep", None, True),
    ("goat", "Goat", None, True),
    ("camel", "Camel", None, True),
    ("horse", "Horse", None, False),
    ("dog", "Dog", None, False),
    ("cat", "Cat", None, False),
    ("poultry", "Poultry", None, True),
    ("broiler", "Broiler", "poultry", True),
    ("layer", "Layer", "poultry", True),
    ("turkey", "Turkey", "poultry", True),
    ("rabbit", "Rabbit", None, True),
    ("fish", "Fish", None, True),
    ("swine", "Swine", None, True),
]

# code, name, dimension, factor to the dimension's base unit
UNITS = [
    ("mcg", "microgram", "mass", "0.000001"),
    ("mg", "milligram", "mass", "0.001"),
    ("g", "gram", "mass", "1"),
    ("kg", "kilogram", "mass", "1000"),
    ("mL", "millilitre", "volume", "0.001"),
    ("L", "litre", "volume", "1"),
    ("mg/mL", "milligram per millilitre", "concentration", "1"),
    ("mg/L", "milligram per litre", "concentration", "0.001"),
    ("%", "percent (w/v)", "percent", "1"),
    ("mg/kg", "milligram per kilogram", "dose_rate", "1"),
    ("mcg/kg", "microgram per kilogram", "dose_rate", "0.001"),
    ("IU", "international unit", "activity", "1"),
    ("kg_bw", "kilogram body weight", "body_weight", "1"),
    ("lb", "pound", "body_weight", "0.45359237"),
    ("h", "hour", "time", "1"),
    ("d", "day", "time", "24"),
    ("tablet", "tablet", "count", "1"),
    ("dose", "dose", "count", "1"),
]

DOSAGE_FORMS = [
    ("injection", "Injection"),
    ("tablet", "Tablet"),
    ("bolus", "Bolus"),
    ("oral-solution", "Oral solution"),
    ("water-soluble-powder", "Water-soluble powder"),
    ("premix", "Premix"),
    ("suspension", "Suspension"),
    ("pour-on", "Pour-on"),
    ("ointment", "Ointment"),
    ("intramammary", "Intramammary infusion"),
    ("vaccine", "Vaccine"),
]
