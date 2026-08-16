## ADDED Requirements

### Requirement: A ranking question asks for a strict total order

A `ranking` question SHALL present its items and let the respondent arrange them into an order in
which every rank is used exactly once. The respondent SHALL be able to reorder items with a
pointer and with the keyboard.

#### Scenario: Items are presented in the creator's order

- **WHEN** a respondent opens a ranking question they have not answered
- **THEN** the items appear in the order the creator defined, each showing its current rank

#### Scenario: Reordering changes the ranks

- **WHEN** the respondent moves an item to the top
- **THEN** that item is ranked 1 and every other item's rank shifts accordingly

### Requirement: The stored answer is the respondent's permutation

A ranking answer SHALL be stored in `Answer.selected_choices` as the item codes in the
respondent's order — first element ranked 1. Navigating back to the section SHALL restore that
order.

#### Scenario: Order round-trips

- **WHEN** a respondent submits the order C, A, B and later returns to the section
- **THEN** the stored answer is `[C, A, B]` and the question renders in that order

### Requirement: Only a permutation is accepted

A submission SHALL be stored only when it uses every one of the question's items exactly once. A
submission with a repeated item, a missing item, an unknown item or an extra item SHALL store no
answer, and SHALL NOT error the section.

#### Scenario: Repeated item stores nothing

- **WHEN** a submission ranks the same item twice
- **THEN** no answer is stored for that question and the section submits normally

#### Scenario: Missing item stores nothing

- **WHEN** a submission omits one of the question's items
- **THEN** no answer is stored for that question

#### Scenario: Unknown item stores nothing

- **WHEN** a submission contains a code the question does not define
- **THEN** no answer is stored for that question

### Requirement: Ranks export as one column per item

A ranking question SHALL export one column per item, whose value is that item's rank for the
respondent. A respondent who did not answer SHALL leave those columns empty.

#### Scenario: Three items export as three columns

- **WHEN** a survey with a three-item ranking question is exported
- **THEN** the CSV carries one column per item, each holding that respondent's rank for it

#### Scenario: Ranks are numbers, not labels

- **WHEN** a respondent ranked an item second
- **THEN** that item's column holds `2`
