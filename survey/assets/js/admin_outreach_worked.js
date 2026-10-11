// The "Worked" checkbox on the admin user list (spec creator-outreach-status):
// one POST per tick to the row's toggle-worked URL, no page reload. The server
// answers with the flag as stored, which is what the box shows afterwards.
(function () {
  function csrf() {
    var m = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return m ? decodeURIComponent(m[1]) : '';
  }
  document.addEventListener('change', function (ev) {
    var box = ev.target;
    if (!box.classList || !box.classList.contains('ms-worked')) return;
    box.disabled = true;
    var body = new URLSearchParams();
    body.set('worked', box.checked ? '1' : '0');
    fetch(box.dataset.url, {
      method: 'POST',
      headers: {'X-CSRFToken': csrf(), 'X-Requested-With': 'XMLHttpRequest'},
      body: body,
      credentials: 'same-origin',
    }).then(function (r) { return r.ok ? r.json() : Promise.reject(r.status); })
      .then(function (data) { box.checked = !!data.worked; box.title = data.since ? 'Worked since ' + data.since : 'Not worked yet'; })
      .catch(function () { box.checked = !box.checked; alert('Could not save the worked flag.'); })
      .finally(function () { box.disabled = false; });
  });
})();
