"""Files read as features for a workspace dataset (change data-upload, #668).

`open_source(path, original_name)` returns a `Source` with two passes over the file: `profile()`
(feature count, rows without a location, the coordinate system read, the field dictionary) and
`features()` (GeoJSON Feature dicts in WGS 84, fed to `survey.layers.objects_from_features`). Two
passes instead of a list in memory: a Pro dataset may hold 100,000 features.

GeoPackage, zipped shapefile, KML and GeoJSON are read with GDAL (`DataSource`); a file's own
coordinate system is reprojected to EPSG:4326. CSV is read with `csv`: coordinate columns by name,
values that fit longitude/latitude are WGS 84, values in the British National Grid envelope are
EPSG:27700, anything else is refused.
"""
import csv
import io
import json
import os
import re
import tempfile
import zipfile

LAT_NAMES = ('lat', 'latitude', 'y', 'lat_wgs84')
LON_NAMES = ('lon', 'lng', 'long', 'longitude', 'x', 'lon_wgs84')
EASTING_NAMES = ('easting', 'eastings', 'x_coord', 'xcoord', 'east', 'e')
NORTHING_NAMES = ('northing', 'northings', 'y_coord', 'ycoord', 'north', 'n')
BNG_ENVELOPE = (0, 0, 700000, 1300000)

PRIVATE_NAME = re.compile(r'(e[-_ ]?mail|\bmail\b|phone|\btel\b|telephone|mobile|first[-_ ]?name|last[-_ ]?name|'
                          r'surname|full[-_ ]?name|person|owner[-_ ]?name|contact)', re.I)
EMAIL_VALUE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')
PHONE_VALUE = re.compile(r'^\+?[\d\s().-]{7,}$')
KEY_NAMES = re.compile(r'^(id|fid|key|code|ref|uid|uuid|objectid|.*_id|.*id)$', re.I)
DATE_VALUE = re.compile(r'^\d{4}-\d{2}-\d{2}')
SAMPLE = 2000


class ImportRefused(Exception):
    """A creator-facing reason the file cannot become a dataset."""


def _norm(name):
    return re.sub(r'[^a-z0-9_]', '', (name or '').strip().lower())


def _number(value):
    if value is None or value == '':
        return None
    try:
        return float(str(value).replace(',', '.') if str(value).count(',') == 1 and '.' not in str(value) else value)
    except (TypeError, ValueError):
        return None


class _Profile:
    def __init__(self):
        self.count = 0
        self.no_location = 0
        self.order = []
        self.values = {}

    def add(self, props):
        for k, v in props.items():
            if k not in self.values:
                self.order.append(k)
                self.values[k] = []
            if v not in (None, '') and len(self.values[k]) < SAMPLE:
                self.values[k].append(v)

    def fields(self):
        out = []
        for name in self.order:
            vals = [str(v) for v in self.values[name]]
            if vals and all(_number(v) is not None for v in vals):
                ftype = 'number'
            elif vals and all(DATE_VALUE.match(v) for v in vals):
                ftype = 'date'
            else:
                ftype = 'text'
            looks_personal = bool(vals) and (
                sum(1 for v in vals if EMAIL_VALUE.match(v) or (ftype == 'text' and PHONE_VALUE.match(v)))
                > len(vals) / 2)
            out.append({'name': name, 'label': name, 'type': ftype,
                        'private': bool(PRIVATE_NAME.search(name)) or looks_personal,
                        'unique': bool(vals) and len(set(vals)) == len(vals)})
        return out

    def key_field(self, fields):
        for f in fields:
            if f['unique'] and KEY_NAMES.match(_norm(f['name'])) and not f['private']:
                return f['name']
        return ''


class Source:
    crs = 'EPSG:4326'

    def profile(self):
        p = _Profile()
        for props, geometry in self._rows():
            p.count += 1
            p.add(props)
            if geometry is None:
                p.no_location += 1
        fields = p.fields()
        return {'count': p.count, 'no_location': p.no_location, 'crs': self.crs,
                'fields': [{k: v for k, v in f.items() if k != 'unique'} for f in fields],
                'key_field': p.key_field(fields)}

    def features(self):
        for props, geometry in self._rows():
            if geometry is None:
                continue
            yield {'type': 'Feature', 'properties': props, 'geometry': geometry}

    def close(self):
        pass


class GdalSource(Source):
    def __init__(self, path):
        from django.contrib.gis.gdal import DataSource, GDALException
        try:
            self.ds = DataSource(path)
        except GDALException:
            raise ImportRefused('This file could not be read. Upload a GeoPackage, a zipped shapefile, '
                                'KML, GeoJSON or a CSV with coordinate columns.')
        if not len(self.ds):
            raise ImportRefused('The file has no layer.')
        self.layer = self.ds[0]
        srs = self.layer.srs
        self.transform = None
        if srs is not None:
            name = (srs.name or '').strip()
            epsg = srs.srid
            self.crs = f'EPSG:{epsg}' if epsg else (name or 'unknown')
            if epsg != 4326:
                from django.contrib.gis.gdal import CoordTransform, SpatialReference
                self.transform = CoordTransform(srs, SpatialReference(4326))
        else:
            self.crs = 'none (read as WGS 84)'

    def _rows(self):
        names = list(self.layer.fields)
        for feat in self.layer:
            props = {}
            for n in names:
                try:
                    v = feat.get(n)
                except Exception:  # noqa: BLE001 — a malformed cell is skipped, not fatal
                    v = None
                if hasattr(v, 'isoformat'):
                    v = v.isoformat()
                props[n] = v
            geom = feat.geom if feat.geom_type is not None else None
            geometry = None
            if geom is not None and not geom.empty:
                g = geom.clone()
                if self.transform is not None:
                    g.transform(self.transform)
                elif self.crs.startswith('none'):
                    x0, y0, x1, y1 = g.extent
                    if not (-180 <= x0 <= 180 and -180 <= x1 <= 180 and -90 <= y0 <= 90 and -90 <= y1 <= 90):
                        raise ImportRefused('The file has no coordinate system and its coordinates are not '
                                            'longitude/latitude. Re-export it as WGS 84 (EPSG:4326).')
                geometry = json.loads(g.json)
            yield props, geometry


class CsvSource(Source):
    def __init__(self, path):
        with open(path, 'rb') as fh:
            raw = fh.read()
        try:
            text = raw.decode('utf-8-sig')
        except UnicodeDecodeError:
            text = raw.decode('latin-1')
        try:
            dialect = csv.Sniffer().sniff(text[:4096], delimiters=',;\t')
        except csv.Error:
            dialect = csv.excel
        self.rows = list(csv.DictReader(io.StringIO(text), dialect=dialect))
        if not self.rows:
            raise ImportRefused('The CSV has no rows.')
        headers = {_norm(h): h for h in self.rows[0].keys() if h}
        pick = lambda names: next((headers[n] for n in names if n in headers), None)  # noqa: E731
        lat, lon = pick(LAT_NAMES), pick(LON_NAMES)
        east, north = pick(EASTING_NAMES), pick(NORTHING_NAMES)
        if lat and lon:
            self.xcol, self.ycol = lon, lat
        elif east and north:
            self.xcol, self.ycol = east, north
        else:
            raise ImportRefused('No coordinate columns found. Name them latitude and longitude, or '
                                'easting and northing.')
        xs = [v for v in (_number(r.get(self.xcol)) for r in self.rows) if v is not None]
        ys = [v for v in (_number(r.get(self.ycol)) for r in self.rows) if v is not None]
        if not xs:
            raise ImportRefused('The coordinate columns are empty.')
        if all(-180 <= x <= 180 for x in xs) and all(-90 <= y <= 90 for y in ys):
            self.crs, self.transform = 'EPSG:4326', None
        elif all(BNG_ENVELOPE[0] <= x <= BNG_ENVELOPE[2] for x in xs) and \
                all(BNG_ENVELOPE[1] <= y <= BNG_ENVELOPE[3] for y in ys):
            from django.contrib.gis.gdal import CoordTransform, SpatialReference
            self.crs = 'EPSG:27700 (British National Grid)'
            self.transform = CoordTransform(SpatialReference(27700), SpatialReference(4326))
        else:
            raise ImportRefused('The coordinates are neither longitude/latitude nor British National Grid. '
                                'Re-export the file as WGS 84 (EPSG:4326) with latitude and longitude columns.')

    def _rows(self):
        from django.contrib.gis.geos import Point
        for r in self.rows:
            props = {k: v for k, v in r.items() if k and k not in (self.xcol, self.ycol)}
            x, y = _number(r.get(self.xcol)), _number(r.get(self.ycol))
            geometry = None
            if x is not None and y is not None:
                if self.transform is not None:
                    p = Point(x, y, srid=27700)
                    p.transform(self.transform)
                    x, y = p.x, p.y
                geometry = {'type': 'Point', 'coordinates': [round(x, 7), round(y, 7)]}
            yield props, geometry


def open_source(path, original_name):
    """A Source for the uploaded file, or ImportRefused with a creator-facing reason."""
    ext = os.path.splitext(original_name or '')[1].lower()
    if ext == '.csv':
        return CsvSource(path)
    if ext == '.zip':
        workdir = tempfile.mkdtemp(prefix='data-import-')
        with zipfile.ZipFile(path) as zf:
            for member in zf.namelist():
                if member.startswith('/') or '..' in member:
                    raise ImportRefused('The ZIP contains unsafe paths.')
            zf.extractall(workdir)
        shp = None
        for root, _dirs, files in os.walk(workdir):
            for f in files:
                if f.lower().endswith('.shp'):
                    shp = os.path.join(root, f)
                    break
        if shp is None:
            raise ImportRefused('The ZIP holds no .shp file.')
        return GdalSource(shp)
    if ext in ('.gpkg', '.kml', '.geojson', '.json'):
        return GdalSource(path)
    raise ImportRefused('Upload a GeoPackage (.gpkg), a zipped shapefile (.zip), KML, GeoJSON or a CSV '
                        'with coordinate columns.')
