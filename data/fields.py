"""The field dictionary and the private-field rule (change data-metadata, #669).

A dataset's `fields` is `[{name, label, type, description, private}]`. A PRIVATE field never
leaves the dataset's own editor (the dataset page and the object editor's detail panel): every
other output of object properties goes through this module — the derived layer GeoJSON
(`survey.layers._object_props`), REST/MCP object reads, the ZIP export, the editor's pickers, the
map metadata, budgets, the dataset download. Labels replace raw names where people read them.
"""
FIELD_TYPES = ('text', 'number', 'date', 'boolean')


def _layer_dataset_fields(layer_id):
    from data.models import Dataset
    row = Dataset.objects.filter(layer_id=layer_id).values_list('fields', flat=True).first()
    return row if isinstance(row, list) else []


def hidden_names(layer_or_id):
    """Names of the private fields of a layer's dataset (empty for a layer without one)."""
    layer_id = getattr(layer_or_id, 'pk', layer_or_id)
    if layer_id is None:
        return frozenset()
    return frozenset(f['name'] for f in _layer_dataset_fields(layer_id)
                     if isinstance(f, dict) and f.get('private') and isinstance(f.get('name'), str))


def public_properties(properties, hidden):
    """An object's properties without the hidden names (a new dict; never the stored one)."""
    props = properties if isinstance(properties, dict) else {}
    if not hidden:
        return dict(props)
    return {k: v for k, v in props.items() if k not in hidden}


def merge_private(existing, new, hidden):
    """A `properties` replacement that keeps the private values the writer could not see."""
    kept = {k: v for k, v in (existing or {}).items() if k in hidden} if hidden else {}
    return {**kept, **(new or {})}


def dictionary(dataset):
    """The editable dictionary of a layer dataset: the stored entries, then the layer's property
    names nobody documented yet (label = name, type text). A private name is always stored, so
    the union is complete although `property_names` leaves private names out."""
    stored = [dict(f) for f in (dataset.fields or []) if isinstance(f, dict) and isinstance(f.get('name'), str)]
    known = {f['name'] for f in stored}
    for f in stored:
        f.setdefault('label', f['name'])
        f.setdefault('type', 'text')
        f.setdefault('description', '')
        f['private'] = bool(f.get('private'))
    if dataset.layer_id:
        for name in dataset.layer.property_names or []:
            if name not in known:
                stored.append({'name': name, 'label': name, 'type': 'text', 'description': '', 'private': False})
                known.add(name)
    return stored


def labels(layer_id):
    """{name: label} of a layer's public documented fields, in dictionary order."""
    return {f['name']: (f.get('label') or f['name']) for f in _layer_dataset_fields(layer_id)
            if isinstance(f, dict) and isinstance(f.get('name'), str) and not f.get('private')}


def card_fields(obj, label_map=None, only=None):
    """`[{label, value}]` for the respondent's object card: the layer's public documented fields
    with a non-empty value, in dictionary order. Nothing for an undocumented layer."""
    label_map = labels(obj.layer_id) if label_map is None else label_map
    props = obj.properties if isinstance(obj.properties, dict) else {}
    out = []
    for name, label in label_map.items():
        if only is not None and name not in only:
            continue
        value = props.get(name)
        if value is None or value == '':
            continue
        out.append({'label': str(label), 'value': str(value)})
    return out
