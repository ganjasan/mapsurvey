---
title: File is larger than 10 MB
description: A GeoJSON reference layer was refused on upload because of its size, the number of layers, or its contents.
sidebar:
  order: 50
---

You dropped a `.geojson` file onto **Reference layers** in the survey settings and got a red message instead of a new layer: **File is larger than 10 MB. Simplify the geometry (e.g. in QGIS or mapshaper.org) and try again.**, **A survey can hold 10 reference layers.**, or one of the messages about the file's contents below.

## Why it happens

A reference layer is sent to every respondent's browser, often on a phone, so each file is checked before it is accepted.

- **File is larger than 10 MB.** Boundaries and routes exported straight from a GIS have far more vertices than a survey map can show.
- **The file has N features; the limit is 5000.** One layer holds at most 5,000 features.
- **A survey can hold 10 reference layers.** The survey already has ten, counting layers that no section shows.
- **File is not valid JSON**, **not UTF-8 text**, **Unrecognized GeoJSON type**, **Expected a GeoJSON object at the top level.** The file is not GeoJSON: a zipped Shapefile, a KML, a GeoPackage, or a GeoJSON saved in another text encoding.
- **Coordinates fall outside longitude/latitude ranges … re-export it as WGS84 (EPSG:4326).** The file is in a projected coordinate system such as UTM or a national grid.
- **The file contains no features.** or **No coordinates found in the file.** The export produced an empty collection, or features without geometry.

Elevation values in coordinates are not an error; they are dropped.

## What to do

1. If the file is too large, simplify it in QGIS (**Vector › Geometry Tools › Simplify**) or at [mapshaper.org](https://mapshaper.org), then export as GeoJSON.
2. Remove properties you will not use; attribute tables with dozens of columns can be most of the file.
3. If the file has more than 5,000 features, split it into several layers by theme or area.
4. If the file is in another format or projection, re-export it from your GIS as GeoJSON in WGS84 (EPSG:4326).
5. If the survey already has ten layers, delete one you no longer show; a layer hidden by every section still counts.
6. Upload the file again. [Add a reference layer](/how-to/add-a-reference-layer/) describes the full flow.

## If it keeps happening

[Contact support](https://mapsurvey.org/?support=1) with the exact message, the size of the file, how many features it holds and the tool that exported it. If the file is under 10 MB and still refused, attach it.
