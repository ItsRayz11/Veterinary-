from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import ValidationError
from rest_framework.permissions import AllowAny
from rest_framework.response import Response

from . import engine

# Whitelist: only these pure functions are callable through the API.
CALCULATORS = {
    name: getattr(engine, name)
    for name in (
        "percent_to_mg_per_ml",
        "mg_to_ml",
        "ml_to_mg",
        "dose_calc",
        "dilution",
        "dehydration_deficit",
        "daily_fluid_need",
        "infusion_rate",
        "drip_rate",
        "cri_rate",
        "drinking_water_dose",
    )
}


@api_view(["POST"])
@permission_classes([AllowAny])
def run(request, name):
    fn = CALCULATORS.get(name)
    if fn is None:
        raise ValidationError({"calculator": f"Unknown calculator '{name}'."})
    try:
        result = fn(**request.data)
    except engine.CalcError as exc:
        raise ValidationError({"input": str(exc)}) from exc
    except TypeError as exc:
        raise ValidationError({"input": "Missing or unexpected input fields."}) from exc
    return Response(
        {
            "formula": result.formula,
            "values": {k: str(v) for k, v in result.values.items()},
            "steps": result.steps,
            "warnings": result.warnings,
        }
    )
