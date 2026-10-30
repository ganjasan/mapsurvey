/* Export dialog (spec responses-export-formats).
 *
 * One #exportModal per page; the opener button carries the survey. The dialog
 * never fetches: it builds a GET URL for /surveys/<uuid>/download and keeps it
 * on the Export button's href, so the export is always a copyable link and the
 * browser shows its own download UI. The last chosen format is remembered per
 * browser only (localStorage), like every other Responses preference.
 */
(function () {
  'use strict';
  if (typeof $ === 'undefined') return;

  var STORAGE_KEY = 'exportFormat';
  var state = { uuid: null, versions: [], hasFiles: false };

  function $modal() { return $('#exportModal'); }

  function chosenFormat() {
    var picked = $modal().find('input[name="export-format"]:checked').val();
    return picked || 'xlsx';
  }

  // Versions are check-boxes (issue #496): several ticked travel as one
  // comma-separated `version` value, every one ticked sends no `version` at all
  // (today's "All versions"), and "draft" is exclusive of the rest — the server
  // never mixes preview traffic into a list either.
  function versionBoxes() { return $('#exportVersionList input[type="checkbox"]'); }
  function publishedBoxes() { return versionBoxes().not('[value="draft"]'); }

  function versionParam() {
    if (!state.versions.length) return null;
    var ticked = versionBoxes().filter(':checked');
    if (!ticked.length) return null;
    if (ticked.is('[value="draft"]')) return 'draft';
    if (ticked.length === publishedBoxes().length) return null;
    return ticked.map(function () { return encodeURIComponent(this.value); }).get().join(',');
  }

  function nothingTicked() {
    return state.versions.length > 0 && !versionBoxes().filter(':checked').length;
  }

  // The field is one line (a survey can have dozens of versions): the trigger
  // names what is ticked, the panel holds the search and the check-boxes.
  function labelOf(box) { return $('label[for="' + box.id + '"]').text(); }

  function versionSummary() {
    var ticked = versionBoxes().filter(':checked');
    var published = publishedBoxes();
    if (!ticked.length) return '—';
    if (!ticked.is('[value="draft"]') && ticked.length === published.length) {
      return $('label[for="exportVersionAll"]').text() + ' (' + published.length + ')';
    }
    var labels = ticked.map(function () { return labelOf(this); }).get();
    if (labels.length > 4) return labels.slice(0, 3).join(', ') + ' +' + (labels.length - 3);
    return labels.join(', ');
  }

  function setPanel(open) {
    $('#exportVersionPanel').prop('hidden', !open);
    $('#exportVersionTrigger').attr('aria-expanded', open ? 'true' : 'false');
    if (!open) return;
    var panel = document.getElementById('exportVersionPanel');
    // preventScroll: the panel sits low in a scrolling body; bring all of it in, not just the search box.
    $('#exportVersionSearch')[0].focus({ preventScroll: true });
    if (panel.scrollIntoView) panel.scrollIntoView({ block: 'nearest' });
  }

  function filterVersions(query) {
    var q = $.trim(query).toLowerCase();
    var shown = 0;
    $('#exportVersionList .custom-control').each(function () {
      var match = !q || $(this).find('label').text().toLowerCase().indexOf(q) !== -1;
      $(this).toggle(match);
      if (match) shown += 1;
    });
    $('#exportVersionEmpty').toggle(shown === 0);
  }

  function buildUrl() {
    var params = [];
    var fmt = chosenFormat();
    if (fmt !== 'zip') params.push('format=' + fmt);
    var version = versionParam();
    if (version) params.push('version=' + version);
    if ($('#exportIncludeAll').is(':checked')) params.push('include_all=1');
    if ($('#exportCompletedOnly').is(':checked')) params.push('completed_only=1');
    // The legacy archive always carries the files; the switch is hidden for it.
    if (fmt !== 'zip' && state.hasFiles && $('#exportFiles').is(':checked')) params.push('files=1');
    var url = '/surveys/' + state.uuid + '/download';
    if (params.length) url += '?' + params.join('&');
    return url;
  }

  function render() {
    var fmt = chosenFormat();
    $('#exportFilesGroup').toggle(state.hasFiles && fmt !== 'zip');
    var url = buildUrl();
    var blocked = nothingTicked();
    $('#exportGo').attr('href', url).toggleClass('disabled', blocked).attr('aria-disabled', blocked ? 'true' : null);
    $('#exportVersionNone').toggle(blocked);
    var published = publishedBoxes();
    $('#exportVersionAll').prop('checked', published.length > 0 && published.filter(':checked').length === published.length);
    $('#exportVersionSummary').text(versionSummary());
    $('#exportUrl').text(window.location.origin + url);
    try { window.localStorage.setItem(STORAGE_KEY, fmt); } catch (e) { /* private mode */ }
  }

  function fillVersions(versions, current) {
    var list = $('#exportVersionList').empty();
    versions.forEach(function (v, i) {
      if (v.value === 'all') return;   // the "All versions" check-box above the list
      var id = 'exportVersion_' + i;
      var box = $('<div class="custom-control custom-checkbox">')
        .toggleClass('export-version-draft', v.value === 'draft');
      box.append($('<input type="checkbox" class="custom-control-input">').attr({ id: id, value: v.value }));
      box.append($('<label class="custom-control-label">').attr('for', id).text(v.label));
      list.append(box);
    });
    // data-version is the page's scope: 'all', one value, or a list ('v11,v10').
    var wanted = String(current || 'all').toLowerCase().split(',').map(function (s) { return s.trim(); });
    var matched = versionBoxes().filter(function () { return wanted.indexOf(this.value) !== -1; });
    if (matched.is('[value="draft"]')) matched = matched.filter('[value="draft"]');
    (matched.length ? matched : publishedBoxes()).prop('checked', true);
    $('#exportVersionGroup').toggle(versions.length > 0);
  }

  function restoreFormat() {
    var wanted = null;
    try { wanted = window.localStorage.getItem(STORAGE_KEY); } catch (e) { /* ignore */ }
    var radios = $modal().find('input[name="export-format"]');
    var match = wanted ? radios.filter('[value="' + wanted + '"]') : $();
    (match.length ? match : radios.first()).prop('checked', true);
  }

  $(function () {
    var modal = $modal();
    if (!modal.length) return;

    modal.on('show.bs.modal', function (event) {
      var opener = $(event.relatedTarget);
      state.uuid = opener.data('survey-uuid');
      state.hasFiles = String(opener.data('has-files')) === '1';
      var versions = opener.data('versions');
      if (typeof versions === 'string') {
        try { versions = JSON.parse(versions); } catch (e) { versions = []; }
      }
      state.versions = Array.isArray(versions) ? versions : [];
      $('#exportSurveyName').text(opener.data('survey-name') || '');
      $('#exportIncludeAll, #exportCompletedOnly, #exportFiles').prop('checked', false);
      fillVersions(state.versions, opener.data('version'));
      $('#exportVersionSearch').val('');
      filterVersions('');
      setPanel(false);
      restoreFormat();
      render();
    });

    $('#exportVersionTrigger').on('click', function () {
      setPanel($('#exportVersionPanel').prop('hidden'));
    });
    $('#exportVersionSearch').on('input', function () { filterVersions(this.value); });
    // Escape closes the panel, not the whole dialog; a click elsewhere in the
    // dialog closes it too.
    $('#exportVersionPanel, #exportVersionTrigger').on('keydown', function (event) {
      if (event.key === 'Escape' && !$('#exportVersionPanel').prop('hidden')) {
        event.stopPropagation();
        setPanel(false);
        $('#exportVersionTrigger').trigger('focus');
      }
    });
    modal.on('mousedown', function (event) {
      if (!$(event.target).closest('#exportVersionPanel, #exportVersionTrigger').length) setPanel(false);
    });

    modal.on('change', '#exportVersionAll', function () {
      versionBoxes().prop('checked', false);
      if (this.checked) publishedBoxes().prop('checked', true);
    });
    modal.on('change', '#exportVersionList input', function () {
      if (!this.checked) return;
      if (this.value === 'draft') versionBoxes().not(this).prop('checked', false);
      else versionBoxes().filter('[value="draft"]').prop('checked', false);
    });
    modal.on('change', 'input, select', render);

    // Let the browser handle the download and close the dialog behind it.
    $('#exportGo').on('click', function (event) {
      if (nothingTicked()) { event.preventDefault(); return; }
      setTimeout(function () { modal.modal('hide'); }, 300);
    });
  });
})();
