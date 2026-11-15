"""New versions of a layer dataset (change data-versions, #671).

A file is matched to the dataset's objects by the layer's key field, keys derived exactly as the
import derives them. `diff` counts what would change; `apply` updates matched objects IN PLACE (same
row: answers about them stay attached), adds new keys and removes missing ones, all in one
transaction, then rebuilds the layer and records a `DatasetVersion`.
"""
import json

from django.utils.translation import gettext as _


class VersionRefused(Exception):
    def __init__(self, message):
        super().__init__(message)
        self.message = message


def incoming(layer, source):
    """{key: {'title', 'properties', 'geometry' (GeoJSON dict)}} from the file, plus counts of
    rows skipped for having no key value or a repeated key."""
    from survey.layers import RESERVED_PROPS, derive_key, derive_title, explode_geometry
    key_field = layer.key_field
    out, no_key, repeated = {}, 0, []
    for index, feature in enumerate(source.features(), start=1):
        props = feature.get('properties') if isinstance(feature.get('properties'), dict) else {}
        parts = explode_geometry(feature.get('geometry'))
        if not parts:
            continue
        key, from_field = derive_key(props, key_field, index, set())
        if not from_field:
            no_key += 1
            continue
        clean = {k: v for k, v in props.items() if isinstance(k, str) and k not in RESERVED_PROPS}
        for n, part in enumerate(parts, start=1):
            part_key = key if len(parts) == 1 else f'{key}-{n}'
            if part_key in out:
                repeated.append(part_key)
                continue
            out[part_key] = {'title': derive_title(props, layer.label_field, part_key),
                             'properties': clean, 'geometry': part}
    return out, no_key, repeated


def _same_geometry(stored, part):
    from django.contrib.gis.geos import GEOSGeometry
    try:
        return stored.equals_exact(GEOSGeometry(json.dumps(part), srid=4326), 1e-9)
    except Exception:  # noqa: BLE001 — an unreadable part is a change
        return False


def diff(layer, rows):
    """(added keys, changed keys, removed keys, unchanged count) of `rows` against the layer."""
    added, changed, removed, unchanged = [], [], [], 0
    seen = set()
    for o in layer.items.values('key', 'title', 'properties', 'geometry').iterator(chunk_size=500):
        new = rows.get(o['key'])
        if new is None:
            removed.append(o['key'])
            continue
        seen.add(o['key'])
        if (new['title'] == o['title'] and new['properties'] == (o['properties'] or {})
                and _same_geometry(o['geometry'], new['geometry'])):
            unchanged += 1
        else:
            changed.append(o['key'])
    added = [k for k in rows if k not in seen]
    return added, changed, removed, unchanged


def check(dataset, source, rows):
    """Refusals before a preview or an apply: no key field, workspace limit, survey caps while linked."""
    from data.tasks import limits_for
    from survey.layers import MAX_LAYER_FEATURES
    layer = dataset.layer
    if not layer.key_field:
        raise VersionRefused(_('This dataset has no key field, so rows cannot be matched. Re-upload it with a key column (an ID per row).'))
    profile = source.profile()
    if layer.key_field not in {f['name'] for f in profile['fields']}:
        raise VersionRefused(_('The file has no column “%(key)s”, the key of this dataset.') % {'key': layer.key_field})
    _bytes, max_features = limits_for(dataset.organization)
    if len(rows) > max_features:
        raise VersionRefused(_('The file has %(n)s features; the limit for this workspace is %(max)s.')
                             % {'n': len(rows), 'max': max_features})
    if dataset.links.filter(survey__isnull=False).exists() and len(rows) > MAX_LAYER_FEATURES:
        raise VersionRefused(_('The dataset is shown in a survey, and a survey map takes up to %(max)s objects. Unlink it first or upload fewer rows.')
                             % {'max': MAX_LAYER_FEATURES})
    return profile


def preview(dataset, source):
    """The report a preview card shows."""
    from survey.models import Answer
    rows, no_key, repeated = incoming(dataset.layer, source)
    check(dataset, source, rows)
    added, changed, removed, unchanged = diff(dataset.layer, rows)
    answers = Answer.objects.filter(layer_object__layer=dataset.layer, layer_object__key__in=removed).count()
    return {'added': len(added), 'changed': len(changed), 'removed': len(removed), 'unchanged': unchanged,
            'removed_answers': answers, 'no_key': no_key, 'repeated': len(repeated),
            'removed_keys': removed[:20], 'added_keys': added[:20]}


def _merge_fields(stored, profiled):
    """Known names keep their labels, types and private flags; new columns come in as profiled."""
    by_name = {f['name']: f for f in stored or [] if isinstance(f, dict) and 'name' in f}
    out = []
    for f in profiled:
        out.append(by_name.get(f['name'], f))
    return out


def apply(dataset, source, user=None, note=''):
    """Write the version; returns the DatasetVersion. Raises VersionRefused."""
    from django.contrib.gis.geos import GEOSGeometry
    from django.db import transaction
    from django.db.models import Max
    from data.models import Dataset, DatasetVersion
    from survey.layers import MAX_LAYER_BYTES, rebuild_layer
    from survey.models import LayerObject, SurveyMapLayer
    layer = dataset.layer
    rows, _no_key, _repeated = incoming(layer, source)
    profile = check(dataset, source, rows)
    with transaction.atomic():
        layer = SurveyMapLayer.objects.select_for_update().get(pk=layer.pk)
        added, changed, removed, unchanged = diff(layer, rows)
        LayerObject.objects.filter(layer=layer, key__in=removed).delete()
        changed_set = set(changed)
        for obj in LayerObject.objects.filter(layer=layer, key__in=changed_set):
            new = rows[obj.key]
            obj.title = new['title']
            obj.properties = new['properties']
            obj.geometry = GEOSGeometry(json.dumps(new['geometry']), srid=4326)
            obj.save(update_fields=['title', 'properties', 'geometry'])
        start = (layer.items.aggregate(m=Max('position'))['m'] or 0) + 1
        LayerObject.objects.bulk_create([
            LayerObject(layer=layer, key=k, title=rows[k]['title'], properties=rows[k]['properties'],
                        geometry=GEOSGeometry(json.dumps(rows[k]['geometry']), srid=4326), position=start + i)
            for i, k in enumerate(added)], batch_size=500)
        # The dictionary first: the rebuild reads it to leave private columns out of the cache.
        Dataset.objects.filter(pk=dataset.pk).update(fields=_merge_fields(dataset.fields, profile['fields']))
        rebuild_layer(layer)
        if dataset.links.filter(survey__isnull=False).exists() and layer.size_bytes > MAX_LAYER_BYTES:
            raise VersionRefused(_('The dataset is shown in a survey, and a survey map takes up to %(mb)s MB.')
                                 % {'mb': MAX_LAYER_BYTES // (1024 * 1024)})
        number = (dataset.versions.aggregate(m=Max('number'))['m'] or 1) + 1
        version = DatasetVersion.objects.create(
            dataset=dataset, number=number, note=note[:300], created_by=user,
            added=len(added), changed=len(changed), removed=len(removed), unchanged=unchanged)
    return version
