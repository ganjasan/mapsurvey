"""Paper forms from photos (change paper-photo-entry, #495; epic #350 item 3).

A batch of uploads becomes pages, pages become sheets, a sheet becomes a
prefilled operator entry the creator's team checks against the picture:

  ingest   — one upload → N normalised page JPEGs (PDF split, HEIC converted),
             in the Celery worker only; the web process never decodes a byte.
  codes    — the form code off a page: the QR locally, the footer text by the
             model when the QR will not read.
  sheets   — pages → sheets by upload order and page number; the operator can
             move a page by hand and it stays moved.
  extract  — one vision call per page, bounded by the items printed on it
             (`PrintedForm.layout[page]["items"]`), typed values + confidence.
  review   — the sheet's extraction in the dialect the entry form's `initial`
             dict speaks, and which fields deserve a second look.
"""
