## ADDED Requirements

### Requirement: Concurrent writes to one layer are serialised

A request that writes objects or assets in a reference layer SHALL hold a lock on that
layer for as long as it reads the layer's contents, writes to them, and rebuilds the
derived GeoJSON. Two such requests against the same layer MUST NOT interleave those steps;
requests against different layers MUST NOT block each other.

#### Scenario: Two creates race for the same generated key

- **WHEN** two requests create an object in the same layer at the same time, and neither
  supplies a key
- **THEN** each object is stored under a distinct generated key
- **AND** neither request fails with a database integrity error

#### Scenario: The derived GeoJSON keeps every committed object

- **WHEN** two requests each add an object to the same layer and each rebuilds the layer's
  derived GeoJSON
- **THEN** the stored GeoJSON contains both objects once both requests have committed

#### Scenario: Writes to different layers do not queue

- **WHEN** two requests write to two different layers
- **THEN** neither waits for the other

### Requirement: The write lock does not load the layer's GeoJSON

Taking the lock SHALL NOT read the layer's stored GeoJSON text, which is up to 10 MB per
row and which a worker's resident memory keeps for the life of the process.

#### Scenario: Locking a layer to write an object

- **WHEN** a request locks a layer in order to write one of its objects
- **THEN** the query that takes the lock does not select the stored GeoJSON column

### Requirement: A generated object key does not collide with an existing one

When the creator supplies no key, the server SHALL generate one that is not already used in
that layer, counting against what is committed at the moment of the write.

#### Scenario: Keys already exist with gaps

- **WHEN** an object is created in a layer whose existing keys skip values in the generated
  sequence
- **THEN** the new object receives a generated key that no other object in the layer holds

#### Scenario: The creator supplies a key that is taken

- **WHEN** a create request supplies a key that already exists in the layer
- **THEN** the request is refused with a message naming the key
- **AND** the response is a client error, not a server error
