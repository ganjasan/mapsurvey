## ADDED Requirements

### Requirement: A file becomes a workspace dataset in one step
The system SHALL turn an uploaded GeoPackage, zipped shapefile, KML, GeoJSON or CSV with coordinate
columns into a workspace dataset through a background job started from the Data catalogue with one
click. Geometries SHALL be stored in WGS 84: a file's own coordinate system SHALL be reprojected; a
CSV whose values fit longitude/latitude SHALL be read as WGS 84 and one whose values fit the British
National Grid as EPSG:27700; any other projected CSV SHALL be refused with a message saying how to
export it. The new dataset SHALL need no survey and SHALL be `private` until its owner releases it.

#### Scenario: A GeoPackage in a national grid is reprojected
- **WHEN** a member uploads a GeoPackage whose layer is in EPSG:27700
- **THEN** a private dataset is created whose objects lie at the matching WGS 84 positions

#### Scenario: A CSV with eastings and northings
- **WHEN** a member uploads a CSV with `easting` and `northing` columns in British National Grid
- **THEN** its rows become points at the matching WGS 84 positions

#### Scenario: An unknown projected CSV is refused
- **WHEN** a CSV's coordinates fit neither longitude/latitude nor the British National Grid
- **THEN** the job fails with a message asking to re-export the file as WGS 84

### Requirement: The import report lists problems without failing
The job's result SHALL state the number of objects created, the coordinate system read, the rows
skipped for having no location, duplicate keys, and the columns marked private. Rows without a
location and duplicate keys SHALL NOT fail the import.

#### Scenario: Rows without a location
- **WHEN** a CSV has 10 rows of which 2 have empty coordinates
- **THEN** 8 objects are created and the report says 2 rows were skipped for having no location

### Requirement: Personal columns are private on arrival
The system SHALL mark private, in the dataset's field dictionary, every column whose name says
email, phone or a person's name, or whose values are mostly emails or phone numbers.

#### Scenario: An inspector's email column
- **WHEN** an uploaded file has a column `INSP_EMAIL` holding email addresses
- **THEN** the field dictionary marks it private and the report names it

### Requirement: Uploads respect the workspace's limits
Uploads SHALL be refused above 10 MB or 5,000 features on Free and above 50 MB or 100,000 features
on Pro, with a message naming the limit.

#### Scenario: Too large for Free
- **WHEN** a Free workspace uploads a 12 MB file
- **THEN** the upload is refused before any job runs and the message names the 10 MB limit
