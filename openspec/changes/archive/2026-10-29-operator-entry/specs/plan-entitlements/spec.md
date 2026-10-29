# plan-entitlements — delta for operator-entry

## MODIFIED Requirements

### Requirement: Features are declared in a registry, not in columns
Pro capabilities SHALL be declared in `billing/features.py` as named entries mapping a feature
key to the plans that include it and a human label. Adding a feature SHALL require only a new
registry entry. The registry SHALL contain `unbranded`, `pro_help`, `api` and `operator_entry`,
all for plan `pro`.

#### Scenario: Registry drives the feature set
- **WHEN** a new key `custom_domain` is added to the registry for plan `pro`
- **THEN** `for_organization(pro_org).features` contains `custom_domain` without any migration or model change

#### Scenario: Operator entry is a Pro feature
- **WHEN** entitlements are computed for a Pro organisation and for a Free one
- **THEN** `operator_entry` is in the Pro organisation's features and absent from the Free one's
