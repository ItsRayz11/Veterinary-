from collections import defaultdict

from django.contrib.contenttypes.models import ContentType

from .models import SourceLink


def sources_map(objects) -> dict[int, list]:
    """Sources for many same-model objects in ONE query: {object_pk: [Source, ...]}."""
    objects = list(objects)
    if not objects:
        return {}
    ct = ContentType.objects.get_for_model(objects[0])
    links = SourceLink.objects.filter(
        content_type=ct, object_id__in=[o.pk for o in objects]
    ).select_related("source")
    out: dict[int, list] = defaultdict(list)
    for link in links:
        out[link.object_id].append((link.source, link.locator))
    return out
