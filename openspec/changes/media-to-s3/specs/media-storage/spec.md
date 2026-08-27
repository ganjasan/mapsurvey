## ADDED Requirements

### Requirement: Uploaded media is stored outside the instance filesystem

When `USE_S3` is enabled, creator-uploaded media SHALL be written to and read from an S3 bucket rather
than a path on the instance filesystem, so that no uploaded file depends on a particular running
container.

#### Scenario: An upload survives instance replacement

- **WHEN** a creator uploads a survey cover image and the web service is then redeployed
- **THEN** the image is still readable after the new instance starts
- **AND** no file was copied between instances

#### Scenario: Media URLs address the bucket's regional endpoint

- **WHEN** a page renders a stored image while `USE_S3` is enabled
- **THEN** the URL host is the bucket's Region-qualified S3 endpoint
- **AND** fetching that URL returns the object without an HTTP redirect

#### Scenario: Uploads do not rely on object ACLs

- **WHEN** the application stores a file in a bucket whose object ownership is bucket-owner-enforced
- **THEN** the upload succeeds
- **AND** the request carries no object ACL

### Requirement: The filesystem remains the default for local work

When `USE_S3` is not enabled, media SHALL be written under `MEDIA_ROOT` and served by the application
itself, so that local development and the test suite require no AWS account, no credentials and no
network access.

#### Scenario: Test suite runs with no AWS configuration

- **WHEN** the test suite runs with `USE_S3` unset and no AWS credentials in the environment
- **THEN** tests that save an image pass
- **AND** no request is made to any AWS endpoint

#### Scenario: Local server serves its own media

- **WHEN** the development server runs with `USE_S3` unset
- **THEN** `MEDIA_URL` is served by the application
- **AND** an uploaded file is retrievable immediately after upload

### Requirement: Environments are isolated by key prefix

Every environment SHALL write media under its own key prefix, so that a preview environment cannot
read, overwrite or delete an object belonging to production.

#### Scenario: A preview writes outside the production prefix

- **WHEN** a PR preview environment stores an image
- **THEN** the object key begins with that preview's own prefix
- **AND** no object under the production prefix is created, modified or deleted

#### Scenario: Production keys are stable across the migration

- **WHEN** a file that existed on the disk is requested after the move to S3
- **THEN** it resolves under the production prefix using the same relative path the database already
  stores
- **AND** no database rows were rewritten to complete the move

### Requirement: Creator artwork is publicly readable

Images a creator authors — survey covers, question images, story covers, results-page images — SHALL be
anonymously readable by URL, because they are already shown openly on every survey and public results
page.

#### Scenario: Artwork is publicly readable

- **WHEN** an unauthenticated client requests a stored creator image by URL
- **THEN** the object is returned

#### Scenario: A key outside the artwork prefixes is not publicly readable

- **WHEN** an unauthenticated client requests an object stored outside the creator-artwork prefixes
- **THEN** the request is denied

### Requirement: Respondent submissions are private

Files submitted by respondents SHALL NOT be retrievable by URL alone. They SHALL be stored outside every
publicly readable prefix and served only through a signed URL that expires.

#### Scenario: A respondent's file cannot be fetched anonymously

- **WHEN** an unauthenticated client requests a respondent-submitted file at its object URL
- **THEN** the request is denied

#### Scenario: An authorised viewer receives a working link

- **WHEN** the application generates a signed URL for a respondent-submitted file
- **THEN** fetching that URL returns the file
- **AND** the URL stops working once it expires

#### Scenario: Submissions never land in a public prefix

- **WHEN** the application stores a respondent-submitted file
- **THEN** its key falls under the private prefix for the current environment
- **AND** no bucket policy grants anonymous read to that key

### Requirement: Application credentials are scoped to the media bucket

The credentials the application uses SHALL grant object access to the media bucket only, and SHALL NOT
grant access to other buckets, to bucket creation, or to identity management.

#### Scenario: Credentials cannot reach the rest of the account

- **WHEN** the application's credentials are used to list all buckets in the account, create a bucket,
  or read IAM users
- **THEN** each of those requests is denied

#### Scenario: Credentials can do the application's own work

- **WHEN** the application's credentials are used to write, read and delete an object in the media
  bucket
- **THEN** each of those operations succeeds

### Requirement: Preview media is removed when its environment is gone

Media belonging to a preview environment SHALL be deleted once that environment no longer exists, so
that closed pull requests do not accumulate objects indefinitely.

#### Scenario: A closed preview's objects are reclaimed

- **WHEN** a PR preview service has been destroyed and the reconcile job runs
- **THEN** every object under that preview's prefix is deleted

#### Scenario: An open preview is left alone

- **WHEN** the reconcile job runs while a preview service still exists
- **THEN** objects under that preview's prefix are retained
