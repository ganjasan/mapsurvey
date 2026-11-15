## Decisions

1. **Scopes are the surveys'.** A dataset is what a survey's layers and answers became; a token an
   agent already holds keeps working, and the consent page gains no new switch. Reading is
   `surveys:read`, writing `surveys:write`.
2. **Rights = the editor's.** Visibility is `services.dataset_row` (the catalogue's rule), editing
   `services.can_edit`, linking needs the owner role on the survey (the layer card's rule); the Pro
   gate is checked on the dataset's workspace per request (`gates.require_pro_api`).
3. **Privacy is the editor's.** Features of a layer come from the derived GeoJSON (private fields
   already left out); the field dictionary returns names and flags, never private values; collected
   answers leave only through a grid view (`409` on their raw features).
4. **Files over MCP** arrive as `content` (text) or `content_base64`, capped by `MCP_IMPORT_MAX_BYTES`,
   then take the same job as an upload.
5. **Refusals** (`DataRefused`) map to `422 validation` or `409 conflict` with the message and fields.
