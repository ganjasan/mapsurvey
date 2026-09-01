"""Split every FD-1 reference layer into LayerObject rows (overlay-features, D-4).

Key: the layer's `key_field` when set and unique in the file, else `f-<index>`.
Title: `label_field`, then name-style columns, then the key. Multi-part
geometries become one object per part (`<key>-<n>`). Raw properties are kept.
The original FeatureCollection is preserved in `geojson_legacy` for one release
and the derived collection is verified against it (feature count + bbox);
mismatches are logged and never block the migration.

Reverse restores `geojson` from `geojson_legacy` and deletes the objects.
"""
import json
import logging

from django.db import migrations

from survey.layers import (
    derive_key, derive_title, explode_geometry, bbox_of_collection, RESERVED_PROPS,
)

log = logging.getLogger('survey.migrations')


def _feature(obj):
    props = dict(obj.properties or {})
    for reserved in RESERVED_PROPS:
        props.pop(reserved, None)
    props.update({'_key': obj.key, '_title': obj.title, '_category': obj.category,
                  '_has_content': bool(obj.description or obj.link), '_cover': ''})
    return {'type': 'Feature', 'id': obj.key, 'properties': props,
            'geometry': json.loads(obj.geometry.geojson)}


def forwards(apps, schema_editor):
    from django.contrib.gis.geos import GEOSGeometry
    SurveyMapLayer = apps.get_model('survey', 'SurveyMapLayer')
    LayerObject = apps.get_model('survey', 'LayerObject')

    for layer in SurveyMapLayer.objects.all().iterator():
        if LayerObject.objects.filter(layer=layer).exists() or not layer.geojson:
            continue
        try:
            features = json.loads(layer.geojson).get('features') or []
        except ValueError:
            log.warning('layer %s: stored geojson is not JSON, left untouched', layer.pk)
            continue

        # A key field whose values repeat cannot identify objects; fall back to
        # generated keys for the whole layer so a file is not half-keyed.
        key_field = layer.key_field
        if key_field:
            seen = [f.get('properties', {}).get(key_field) for f in features
                    if isinstance(f.get('properties'), dict)]
            seen = [v for v in seen if v not in (None, '')]
            if len(seen) != len(set(seen)) or len(seen) != len(features):
                log.warning('layer %s: key_field %r not unique/complete, using f-<index>',
                            layer.pk, key_field)
                key_field = ''

        taken = set()
        rows = []
        for index, feature in enumerate(features, start=1):
            props = feature.get('properties') if isinstance(feature.get('properties'), dict) else {}
            parts = explode_geometry(feature.get('geometry'))
            if not parts:
                log.warning('layer %s: feature %s has no usable geometry, skipped', layer.pk, index)
                continue
            key, _from_field = derive_key(props, key_field, index, taken)
            for n, part in enumerate(parts, start=1):
                part_key = key if len(parts) == 1 else f'{key}-{n}'
                if part_key in taken:
                    part_key = f'{part_key}-{index}'
                taken.add(part_key)
                rows.append(LayerObject(
                    layer=layer, key=part_key,
                    title=derive_title(props, layer.label_field, part_key),
                    geometry=GEOSGeometry(json.dumps(part), srid=4326),
                    position=len(rows) + 1,
                    properties={k: v for k, v in props.items() if isinstance(k, str)},
                ))
        LayerObject.objects.bulk_create(rows, batch_size=500)

        derived = json.dumps(
            {'type': 'FeatureCollection',
             'features': [_feature(o) for o in LayerObject.objects.filter(layer=layer).order_by('position', 'id')]},
            ensure_ascii=False, separators=(',', ':'))

        original_bbox = bbox_of_collection(layer.geojson)
        derived_bbox = bbox_of_collection(derived)
        exploded = len(rows) - len(features)
        if exploded < 0 or (original_bbox and derived_bbox and any(
                abs(a - b) > 1e-6 for a, b in zip(original_bbox, derived_bbox))):
            log.error('layer %s: derived geojson differs from original (features %s→%s, bbox %s→%s)',
                      layer.pk, len(features), len(rows), original_bbox, derived_bbox)

        layer.geojson_legacy = layer.geojson
        layer.geojson = derived
        layer.feature_count = len(rows)
        layer.size_bytes = len(derived.encode('utf-8'))
        layer.save(update_fields=['geojson', 'geojson_legacy', 'feature_count', 'size_bytes'])


def backwards(apps, schema_editor):
    SurveyMapLayer = apps.get_model('survey', 'SurveyMapLayer')
    LayerObject = apps.get_model('survey', 'LayerObject')
    for layer in SurveyMapLayer.objects.exclude(geojson_legacy='').iterator():
        layer.geojson = layer.geojson_legacy
        layer.feature_count = len((json.loads(layer.geojson).get('features') or []))
        layer.size_bytes = len(layer.geojson.encode('utf-8'))
        layer.geojson_legacy = ''
        layer.save(update_fields=['geojson', 'geojson_legacy', 'feature_count', 'size_bytes'])
        LayerObject.objects.filter(layer=layer).delete()


class Migration(migrations.Migration):

    dependencies = [
        ('survey', '0067_layer_objects'),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
