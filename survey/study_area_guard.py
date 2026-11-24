"""Refusing map answers outside the study area on the server (change map-layers-study-area, spec
survey-study-area "Map answers outside the study area can be refused", design D7).

The browser refuses first (`study_area.js`); this is the check a scripted or tampered POST meets.
Rules: a point must lie in the area; a line or a polygon must be covered by the area buffered 5 m
(snapping tolerance, so a corner drawn on the boundary passes); a spray cloud keeps only its dots
inside. A refused mark is skipped like an unreadable chunk — the section POST has no error-render
path — logged with the question code, and counted on `StudyArea.refused_marks`. Answers about a
layer's objects are never checked: the creator placed those objects.

The buffered area is computed once per POST in PostGIS (on the spheroid) and checked with a
prepared GEOS geometry per mark.
"""
import logging

from django.contrib.gis.geos import GEOSGeometry, MultiPoint

logger = logging.getLogger(__name__)

TOLERANCE_M = 5


class Guard:
    def __init__(self, area):
        self.area = area
        self.refused = 0
        self._exact = area.geometry.prepared
        self._tolerant = _buffered(area.geometry, TOLERANCE_M).prepared

    def accepts(self, geom):
        """Whether one placed mark (point, line, polygon) may be stored."""
        if geom.geom_type in ('Point', 'MultiPoint'):
            return self._exact.covers(geom)
        return self._tolerant.covers(geom)

    def clip_cloud(self, cloud):
        """A spray cloud without its dots outside the area (None when none is left)."""
        kept = [p for p in cloud if self._exact.covers(p)]
        if len(kept) != len(cloud):
            self.refused += 1
        if not kept:
            return None
        return MultiPoint(*kept, srid=cloud.srid or 4326)

    def refuse(self, question_code):
        self.refused += 1
        logger.info('study area: refused a mark outside the area for %s', question_code)

    def finish(self, survey):
        """Add this POST's refusals to the survey's counter."""
        if self.refused:
            from .services.study_area import count_refused
            count_refused(survey, self.refused)


def _buffered(geometry, metres):
    from django.db import connection
    with connection.cursor() as cursor:
        cursor.execute('SELECT ST_AsEWKT(ST_Buffer(ST_GeomFromEWKT(%s)::geography, %s)::geometry)',
                       [geometry.ewkt, float(metres)])
        row = cursor.fetchone()
    return GEOSGeometry(row[0])


def for_section(section):
    """The guard for a section POST, or None when nothing is refused there (no study area, the
    rule is off, or the section has no map)."""
    if not section.has_map:
        return None
    from .services.study_area import get
    area = get(section.survey_header)
    if area is None or not area.refuse_outside:
        return None
    return Guard(area)
