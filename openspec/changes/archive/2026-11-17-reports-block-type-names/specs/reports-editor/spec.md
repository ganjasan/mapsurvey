## ADDED Requirements

### Requirement: A block's row names its type
In the editor's block list a block's row SHALL show the name of its type in the interface language under the block's title, and SHALL NOT show the type's internal key. A row whose title is the type's name, because the block has no title of its own, SHALL show the name once.

#### Scenario: A titled block
- **WHEN** an editor whose interface is German opens a report with a Key numbers block titled "Who took part"
- **THEN** the block's row reads "Who took part" with "Kennzahlen" under it, and nowhere "numbers"

#### Scenario: A block with no title of its own
- **WHEN** the report has a Quotes block without a title
- **THEN** its row reads the type's name once
