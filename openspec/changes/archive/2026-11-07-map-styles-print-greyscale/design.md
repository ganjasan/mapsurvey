## Decisions

- **Grey by default, colour on request.** CSS `filter: grayscale(1)` uses Rec. 709 luminance, the
  same weights as the generator's greyscale and the contrast warnings, so the tab, the warnings and
  a black-and-white copier agree.
- **The PDF is not greyed.** A creator with a colour printer keeps a colour form; only the preview
  changes its default.
- The toggle state is not remembered: the default is the honest answer for most forms.
