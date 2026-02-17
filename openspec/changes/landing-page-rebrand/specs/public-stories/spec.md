## REMOVED Requirements

### Requirement: Stories section on landing page
**Reason**: Stories section is removed from the landing page. The new product-focused landing page replaces editorial content with features, comparison, and demo sections. Stories are deferred to a future `/blog` route.
**Migration**: Story model and detail pages at `/stories/<slug>/` remain intact in the codebase. The stories section will be re-introduced when the `/blog` route is built.

### Requirement: Story card content
**Reason**: Removed from landing page along with stories section.
**Migration**: Story cards will be reused in the future `/blog` route.
