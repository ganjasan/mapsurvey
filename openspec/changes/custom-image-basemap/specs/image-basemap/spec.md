## ADDED Requirements

### Requirement: A survey can use an uploaded image as its basemap
A creator with editor rights SHALL be able to upload one image (PNG, JPEG or WebP) for a survey and
switch the survey's basemap mode between `tiles` and `image`. The image basemap SHALL be active only
when the mode is `image` and a processed image exists. Surveys that never upload an image SHALL
behave exactly as before.

#### Scenario: Creator uploads an image and switches to it
- **WHEN** an editor uploads a valid PNG in the survey settings and processing finishes
- **THEN** the settings card shows a preview of the image and offers the `image` basemap mode
- **AND** after the editor selects `image`, the survey's maps show the image instead of tiles

#### Scenario: Switching back keeps the image
- **WHEN** an editor switches an image-basemap survey back to `tiles`
- **THEN** the maps show the enabled tile basemaps again
- **AND** the uploaded image stays stored and can be re-selected without uploading again

#### Scenario: Existing surveys are unaffected
- **WHEN** a survey created before this change is opened by a respondent
- **THEN** its basemap mode is `tiles` and its maps render exactly as before

#### Scenario: Viewer cannot upload
- **WHEN** a collaborator with the `viewer` role posts an image to the upload endpoint
- **THEN** the request is refused and the survey is unchanged

### Requirement: Uploads are validated off the web worker and never public before validation
The upload endpoint SHALL check only content type and size (at most 20 MB) and SHALL NOT decode the
image. It SHALL store the raw file on the private media tier and hand it to a background task. The
task SHALL refuse images above 64 megapixels before allocating them, apply EXIF orientation,
downscale so the long side is at most 8192 px, re-encode to WebP, store the result on the public
tier under a random key, record the pixel size, and delete the raw file whether it succeeds or not.

#### Scenario: Oversized upload refused in the request
- **WHEN** an editor uploads a 25 MB file
- **THEN** the endpoint refuses it with a message naming the 20 MB limit and nothing is stored

#### Scenario: Non-image refused
- **WHEN** an editor uploads a PDF renamed to `.png`
- **THEN** the survey's image state becomes `failed` with a message that the file is not a supported image
- **AND** no file remains on either media tier

#### Scenario: Decompression bomb refused
- **WHEN** the task receives a small file that declares 100 000 × 100 000 pixels
- **THEN** it fails with a message about the pixel limit without decoding the pixels
- **AND** the raw file is deleted

#### Scenario: Large image downscaled
- **WHEN** a valid 12 000 × 6 000 JPEG is processed
- **THEN** the stored image is WebP of 8192 × 4096 px and the recorded width and height match it

#### Scenario: Processing state is visible
- **WHEN** an upload has been accepted and the task has not finished
- **THEN** the settings card shows a processing indicator and refreshes itself until the state is done or failed

#### Scenario: A newer upload supersedes an older one
- **WHEN** an editor uploads image A and then image B before A's task finishes
- **THEN** only B becomes the survey's image and A's files are deleted

#### Scenario: Raw upload is never publicly readable
- **WHEN** an unauthenticated client requests the raw upload's storage key while processing is pending
- **THEN** the request is denied

### Requirement: The image is placed on a fixed rectangle at 0°, 0°
The image SHALL be displayed in the map's default CRS on a rectangle centred on latitude 0,
longitude 0, whose longer side spans 1 degree and whose shorter side follows the image's aspect
ratio. The bounds SHALL be computed on the server from the stored pixel size and passed to the
browser as data. Answer geometry SHALL continue to be stored as SRID 4326 geometry in these
coordinates.

#### Scenario: Landscape image bounds
- **WHEN** the stored image is 4000 × 2000 px
- **THEN** its bounds are latitude −0.25…0.25 and longitude −0.5…0.5

#### Scenario: Portrait image bounds
- **WHEN** the stored image is 1000 × 2000 px
- **THEN** its bounds are latitude −0.5…0.5 and longitude −0.25…0.25

#### Scenario: Point answer lands on the picture
- **WHEN** a respondent places a point on the centre of the image and submits
- **THEN** the stored answer is a point at approximately 0°, 0°
- **AND** reopening the section shows the point at the centre of the image

### Requirement: Every map surface renders the image through one renderer
When the image basemap is active, every map of the survey SHALL show the image and no tile layer:
the respondent map, the editor section map picker, the layer object editor, the settings-panel map
previews, the Responses map pane, the Responses Overview thumbnail, the per-response map modal, and
map blocks on the public results page. All of them SHALL use the same client-side renderer, fed by
the same server-built configuration. The layers control SHALL list no base layers and SHALL still
list reference overlays.

#### Scenario: Respondent map shows only the image
- **WHEN** a respondent opens a section of an image-basemap survey
- **THEN** the map shows the image and requests no map tiles

#### Scenario: Public results ignore the block basemap
- **WHEN** a public results map block configured with `satellite` belongs to an image-basemap survey
- **THEN** the block shows the image, not satellite tiles

#### Scenario: Reference overlays still switchable
- **WHEN** an image-basemap survey has two reference layers
- **THEN** the layers control lists the two overlays and no base layers

#### Scenario: No surface hard-codes tiles past the renderer
- **WHEN** the template guard test scans the templates
- **THEN** every template that creates a tile layer also handles the image basemap configuration

### Requirement: The view is confined to the image
On an image-basemap map the view SHALL NOT pan beyond the image bounds plus a 10 % margin, SHALL NOT
zoom out further than one level below the zoom that fits the whole image, and SHALL NOT zoom in more
than one level beyond the image's native resolution. A start position inside the image bounds SHALL
be honoured; a start position outside them, or none, SHALL fit the whole image.

#### Scenario: No start position fits the image
- **WHEN** a section with no start position opens on an image-basemap survey
- **THEN** the whole image is visible

#### Scenario: Start position inside the image is honoured
- **WHEN** a section's start position lies inside the image bounds with zoom 12
- **THEN** the map opens centred there at zoom 12

#### Scenario: Stale real-world start position ignored
- **WHEN** a survey switched from tiles still stores a start position in Bishkek
- **THEN** the map fits the whole image instead

#### Scenario: Panning stops at the edge
- **WHEN** a respondent drags the map far past the image's right edge
- **THEN** the view springs back so that the image stays in view

### Requirement: Real-world features are disabled on an image survey
While the image basemap is active, the respondent map SHALL NOT show place search and SHALL NOT
centre on the device location, and section basemap overrides SHALL be ignored. The editor SHALL hide
the tile basemap choices, the default basemap, "use geolocation", the section basemap override and
the section map picker's search, while keeping their stored values so they apply again after switching
back to `tiles`.

#### Scenario: No search box for respondents
- **WHEN** a respondent opens an image-basemap survey whose settings had place search available
- **THEN** no place search control is shown

#### Scenario: Geolocation not requested
- **WHEN** an image-basemap survey has `use_geolocation` enabled
- **THEN** the respondent's browser is not asked for its location

#### Scenario: Stored values survive a round trip
- **WHEN** an editor switches a survey to `image` and back to `tiles`
- **THEN** its enabled basemaps, default basemap, geolocation setting and section overrides are as they were

### Requirement: Draft copies carry the image and publish it
Creating a draft copy SHALL copy the basemap mode, the image reference and its size. Publishing the
draft SHALL copy them back to the canonical survey. A stored file SHALL be deleted only when no survey
header references it any more.

#### Scenario: Draft replaces the image without affecting respondents
- **WHEN** an editor uploads a new image in the draft copy of a published survey
- **THEN** respondents of the published survey still see the old image
- **AND** after publishing the draft they see the new one

#### Scenario: Shared file survives a draft's replacement
- **WHEN** the draft replaces the image it shares with the canonical survey
- **THEN** the old file is not deleted while the canonical survey still references it

#### Scenario: Purge deletes the file
- **WHEN** a survey family using an image basemap is purged from the trash
- **THEN** the image file is deleted from storage

#### Scenario: Duplicated survey shows the same image
- **WHEN** an editor duplicates an image-basemap survey
- **THEN** the copy uses the image basemap with the same picture

### Requirement: Replacing or switching warns when answers would not line up
The settings card SHALL ask for confirmation before (a) replacing the image with one whose aspect
ratio differs by more than 1 % while the survey family has geo answers, and (b) switching a survey
with geo answers from `tiles` to `image`, stating that existing marks will not line up with the
picture. Replacing with an image of the same aspect ratio SHALL NOT ask.

#### Scenario: Different aspect ratio with answers
- **WHEN** a survey with point answers on a 2:1 image receives a 1:1 upload
- **THEN** the editor is asked to confirm before the upload is processed

#### Scenario: Same aspect ratio without prompt
- **WHEN** a survey with answers on a 4000 × 2000 image receives an 8000 × 4000 upload
- **THEN** the upload proceeds without confirmation and existing points keep their place on the picture

### Requirement: Data exports state that coordinates belong to the image
When an image-basemap survey's data is downloaded, every GeoJSON file SHALL include a top-level
`mapsurvey_image_basemap` member with the image file name, its bounds and a note that coordinates are
positions on the image, not on Earth. The ZIP SHALL include the image file.

#### Scenario: GeoJSON carries the note
- **WHEN** an editor downloads the data of an image-basemap survey with a point question
- **THEN** the point GeoJSON has `mapsurvey_image_basemap` with `image`, `bounds` and `note`
- **AND** the ZIP contains the image named in `image`

#### Scenario: Tile surveys unchanged
- **WHEN** the data of a tiles survey is downloaded
- **THEN** no GeoJSON contains `mapsurvey_image_basemap` and no basemap image is added
