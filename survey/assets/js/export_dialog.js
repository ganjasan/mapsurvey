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

  function buildUrl() {
    var params = [];
    var fmt = chosenFormat();
    if (fmt !== 'zip') params.push('format=' + fmt);
    var version = $('#exportVersion').val();
    if (state.versions.length && version && version !== 'all') params.push('version=' + encodeURIComponent(version));
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
    $('#exportGo').attr('href', url);
    $('#exportUrl').text(window.location.origin + url);
    try { window.localStorage.setItem(STORAGE_KEY, fmt); } catch (e) { /* private mode */ }
  }

  function fillVersions(versions, current) {
    var select = $('#exportVersion').empty();
    versions.forEach(function (v) {
      select.append($('<option>').attr('value', v.value).text(v.label));
    });
    if (current && select.find('option[value="' + current + '"]').length) {
      select.val(current);
    } else {
      select.val('all');
    }
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
      restoreFormat();
      render();
    });

    modal.on('change', 'input, select', render);

    // Let the browser handle the download and close the dialog behind it.
    $('#exportGo').on('click', function () {
      setTimeout(function () { modal.modal('hide'); }, 300);
    });
  });
})();
