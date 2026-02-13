# Manual Testing Plan: WYSIWYG Survey Editor

## Pre-requisites

- Server running (`source env/bin/activate && python manage.py runserver`)
- PostGIS running (`docker compose up -d db`)
- User created and logged in
- Migrations applied

---

## 1. Survey Creation (`/editor/surveys/new/`)

| # | Step | Expected Result |
|---|------|-----------------|
| 1.1 | Open `/editor/surveys/new/` without auth | Redirect to login page |
| 1.2 | Log in and open `/editor/surveys/new/` | Creation form renders |
| 1.3 | Fill name, select org, click "Create" | Redirect to editor, default section created |
| 1.4 | Create survey with duplicate name (same user) | Validation error, form re-renders |
| 1.5 | Submit form with empty name | Validation error |
| 1.6 | Select multiple languages (en, ru) via language picker | Tags display, saved as `["en", "ru"]` |
| 1.7 | Don't select any languages | Single-language survey created |
| 1.8 | Set visibility = public | Value persisted |

---

## 2. Editor Layout (`/editor/surveys/<uuid>/`)

| # | Step | Expected Result |
|---|------|-----------------|
| 2.1 | Open editor for created survey | 3-column layout: sections sidebar, main panel, preview |
| 2.2 | Navbar | Survey name and "Settings" button visible |
| 2.3 | Sidebar | Lists sections in linked-list order |
| 2.4 | Preview iframe | Shows current section as respondent sees it |

---

## 3. Section Management

### 3.1. Creation

| # | Step | Expected Result |
|---|------|-----------------|
| 3.1.1 | Click "New Section" | New section appears at end of sidebar |
| 3.1.2 | Check auto-generated title/code | `Section N` / `SN` |
| 3.1.3 | Create several sections in a row | Each appended to end of linked list |

### 3.2. Editing

| # | Step | Expected Result |
|---|------|-----------------|
| 3.2.1 | Click section in sidebar | Main panel loads section form |
| 3.2.2 | Change title, wait ~1 sec | Auto-save: data persisted (no visible feedback) |
| 3.2.3 | Change subheading | Saved via auto-save |
| 3.2.4 | Change code (max 8 chars) | Length validation |
| 3.2.5 | Refresh page | All changes persisted |

### 3.3. Section Translations (if languages selected)

| # | Step | Expected Result |
|---|------|-----------------|
| 3.3.1 | Expand "Translations" | Title/subheading fields for each language |
| 3.3.2 | Fill ru translation for title | SurveySectionTranslation record created |
| 3.3.3 | Clear ru translation | Record deleted |
| 3.3.4 | Single-language survey — check for translations | Translations section absent |

### 3.4. Deletion

| # | Step | Expected Result |
|---|------|-----------------|
| 3.4.1 | Click "Delete" on a section | Confirmation dialog |
| 3.4.2 | Confirm deletion | Section removed from sidebar, linked list rebuilt |
| 3.4.3 | Delete head section | Next section becomes head (`is_head=True`) |
| 3.4.4 | Delete the only section | "No sections" message shown |

### 3.5. Drag-and-Drop Reorder

| # | Step | Expected Result |
|---|------|-----------------|
| 3.5.1 | Drag section B above section A | Order becomes [B, A, C], linked list rebuilt |
| 3.5.2 | Drag section to end | Becomes tail (`next_section=None`) |
| 3.5.3 | Drag section to beginning | Becomes head (`is_head=True`) |
| 3.5.4 | Refresh page | Order persisted |

### 3.6. Map Position

| # | Step | Expected Result |
|---|------|-----------------|
| 3.6.1 | Click "Map Position" | Modal with Leaflet map |
| 3.6.2 | Click on map | Marker moves, coordinates update |
| 3.6.3 | Change zoom | Zoom value updates |
| 3.6.4 | Click "Save" | Position persisted |
| 3.6.5 | Open picker again | Shows saved position |
| 3.6.6 | New section — open picker | Default position (59.945, 30.317) |

---

## 4. Question Management

### 4.1. Creation

| # | Step | Expected Result |
|---|------|-----------------|
| 4.1.1 | Click "New Question" | Modal with form |
| 4.1.2 | Fill name, select input_type=text, click Save | Question appears in list |
| 4.1.3 | Create question without name | Saved, displayed as "(unnamed)" |
| 4.1.4 | Create question with input_type=choice | Choices editor appears |
| 4.1.5 | Create questions of each type: text, text_line, number, choice, multichoice, range, rating, datetime, point, line, polygon, image, html | Each type created correctly, type badge shown |
| 4.1.6 | Set required=True | Required flag persisted |
| 4.1.7 | Pick a color via color picker | Saved |

### 4.2. Editing

| # | Step | Expected Result |
|---|------|-----------------|
| 4.2.1 | Click "Edit" on a question | Modal with pre-filled form + preview on right |
| 4.2.2 | Change name, click "Apply" | Preview updates, modal stays open |
| 4.2.3 | Click "Save" | Modal closes, question updated in list |
| 4.2.4 | Change input_type from text to choice | Choices editor appears |
| 4.2.5 | Change input_type from choice to text | Choices editor hidden |
| 4.2.6 | Check translations | Name/subtext fields per language, pre-filled |

### 4.3. Deletion

| # | Step | Expected Result |
|---|------|-----------------|
| 4.3.1 | Click "Delete" on a question | Confirmation dialog |
| 4.3.2 | Confirm | Question removed from list |
| 4.3.3 | Delete question with sub-questions | Sub-questions also deleted (cascade) |

### 4.4. Drag-and-Drop Reorder

| # | Step | Expected Result |
|---|------|-----------------|
| 4.4.1 | Drag Q3 above Q1 | Order updated: Q3(0), Q1(1), Q2(2) |
| 4.4.2 | Refresh page | Order persisted |
| 4.4.3 | Sub-questions not part of main drag-and-drop | Sub-questions not draggable in main list |

---

## 5. Choices Editor

| # | Step | Expected Result |
|---|------|-----------------|
| 5.1 | Select input_type=choice | Table with Code / Name fields |
| 5.2 | Single-language survey | One Name column |
| 5.3 | Multilingual survey (en, ru) | Name column per language |
| 5.4 | Add row | Empty row appended to table |
| 5.5 | Remove row | Row removed |
| 5.6 | Fill code=1, name="Yes"; code=2, name="No" | Saved as `[{"code":1,"name":"Yes"},{"code":2,"name":"No"}]` |
| 5.7 | Multilingual: code=1, en="Yes", ru="Da" | `[{"code":1,"name":{"en":"Yes","ru":"Da"}}]` |
| 5.8 | Row without code | Skipped on serialization |
| 5.9 | Remove all rows | choices becomes None |
| 5.10 | Edit existing choice question | Rows pre-populated |

---

## 6. Sub-questions

| # | Step | Expected Result |
|---|------|-----------------|
| 6.1 | Point/line/polygon question | "Add Sub-question" button visible |
| 6.2 | Text/number/choice question | "Add Sub-question" button absent |
| 6.3 | Add sub-question to point question | Sub-question nested under parent with indent |
| 6.4 | Edit sub-question | Same modal as regular questions |
| 6.5 | Delete sub-question | Removed from nested list |
| 6.6 | Delete parent question | Cascade deletes sub-questions |
| 6.7 | Drag parent | Sub-questions move with it |

---

## 7. Icon Picker

| # | Step | Expected Result |
|---|------|-----------------|
| 7.1 | Open question form, click icon picker | Dropdown with Font Awesome icons |
| 7.2 | Type "map" in search | Filters to map-related icons |
| 7.3 | Click an icon | Field populated, dropdown closes |
| 7.4 | Edit question with icon | Selected icon displayed |
| 7.5 | Clear field | Icon removed |

---

## 8. Live Preview

| # | Step | Expected Result |
|---|------|-----------------|
| 8.1 | Add question | Preview updates (~500ms) |
| 8.2 | Change question name | Preview reflects change |
| 8.3 | Delete question | Preview updates |
| 8.4 | Switch language in preview (if multilingual) | Shows translations |
| 8.5 | Submit button in preview | Absent / disabled (preview=True) |
| 8.6 | Rapid edits (3 changes in 1 sec) | Single preview update after debounce |

---

## 9. Panel Resize & Collapse

| # | Step | Expected Result |
|---|------|-----------------|
| 9.1 | Drag sidebar resize handle | Sidebar width changes (min 140px) |
| 9.2 | Drag preview resize handle | Preview width changes (min 200px) |
| 9.3 | Click sidebar collapse chevron | Sidebar hidden, expand tab visible |
| 9.4 | Click expand tab | Sidebar restored to previous width |
| 9.5 | Collapse preview | Main content expands |
| 9.6 | Close browser, reopen | Panel state restored from localStorage |
| 9.7 | Different surveys | Each has its own saved state |

---

## 10. Settings Modal

| # | Step | Expected Result |
|---|------|-----------------|
| 10.1 | Click "Settings" | Modal opens with form |
| 10.2 | Change visibility | Persisted |
| 10.3 | Add language | available_languages updated |
| 10.4 | Change thanks_html | JSON saved |
| 10.5 | Click "Save" | Modal closes, no page reload |
| 10.6 | Click "Cancel" | Modal closes without saving |

---

## 11. Data Integrity

| # | Step | Expected Result |
|---|------|-----------------|
| 11.1 | Create survey -> sections -> questions -> close -> reopen | All data persisted |
| 11.2 | Reorder sections -> refresh page | Order persisted, linked list correct |
| 11.3 | Multilingual choices -> refresh | Values persisted |
| 11.4 | Delete section from middle of linked list | Neighbors' prev/next pointers fixed |
| 11.5 | Open `/surveys/<slug>/` (public URL) | Survey shows sections and questions created in editor |

---

## 12. Cross-Browser Checks

| # | Step | Expected Result |
|---|------|-----------------|
| 12.1 | Chrome (latest) | All features work |
| 12.2 | Firefox (latest) | All features work |
| 12.3 | Safari | Drag-and-drop, HTMX, iframe preview work |

---

## 13. Edge Cases

| # | Step | Expected Result |
|---|------|-----------------|
| 13.1 | Add 10+ sections | Sidebar scrolls |
| 13.2 | Add 20+ questions to section | List scrolls, no lag |
| 13.3 | Rapidly create and delete 5 questions | No race conditions |
| 13.4 | Network loss during auto-save | Silent failure (network tab) |
| 13.5 | Two users editing same survey | Last write wins, no errors |
| 13.6 | Question with very long name | Truncated with ellipsis in list |
