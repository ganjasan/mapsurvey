/* Respondent file upload widget (openspec: respondent-file-uploads).
 *
 * Bytes leave the page the moment a file is picked or a recording stops; the
 * form only ever carries the token the endpoint returns. States: empty →
 * (recording →) uploading → uploaded | error. Voice recording is progressive
 * enhancement: no MediaRecorder, no microphone, any failure — the file input
 * is still there and nothing complains.
 *
 * A popup form can ask whether uploads are still in flight via
 * window.fileUploadsBusy(container) — Apply must wait for the token.
 */
(function () {
  'use strict';

  function getCookie(name) {
    var m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return m ? m.pop() : '';
  }

  function show(root, cls) {
    root.querySelectorAll('.fu-state').forEach(function (el) { el.hidden = true; });
    var el = root.querySelector('.' + cls);
    if (el) el.hidden = false;
  }

  function setBusy(root, busy) {
    if (busy) root.setAttribute('data-fu-busy', '1');
    else root.removeAttribute('data-fu-busy');
  }

  window.fileUploadsBusy = function (container) {
    return !!(container || document).querySelector('[data-fu-busy]');
  };

  function init(root) {
    if (root.dataset.fuInit) return;
    root.dataset.fuInit = '1';

    var tokenInput = root.querySelector('[data-fu-token]');
    var fileInput = root.querySelector('.fu-input');
    var xhr = null;

    function fail(message) {
      setBusy(root, false);
      root.querySelector('.fu-message').textContent = message;
      show(root, 'fu-error');
    }

    function upload(file, name) {
      var maxBytes = parseInt(root.dataset.maxBytes, 10) || 0;
      if (maxBytes && file.size > maxBytes) {
        fail(root.dataset.msgTooLarge || 'File is too large.');
        return;
      }
      setBusy(root, true);
      show(root, 'fu-uploading');

      var form = new FormData();
      form.append('question', root.dataset.question);
      form.append('file', file, name || file.name);

      xhr = new XMLHttpRequest();
      xhr.open('POST', root.dataset.uploadUrl);
      xhr.setRequestHeader('X-CSRFToken', getCookie('csrftoken'));
      xhr.upload.onprogress = function (e) {
        if (e.lengthComputable) {
          root.querySelector('.fu-progress').style.width =
            Math.round((e.loaded / e.total) * 100) + '%';
        }
      };
      xhr.onerror = function () { fail('Upload failed.'); };
      xhr.onload = function () {
        setBusy(root, false);
        var data = null;
        try { data = JSON.parse(xhr.responseText); } catch (e) { /* fall through */ }
        if (xhr.status !== 200 || !data || !data.token) {
          fail((data && data.message) || 'Upload failed.');
          return;
        }
        tokenInput.value = data.token;
        // Filename reaches the DOM through textContent only — never markup.
        root.querySelector('.fu-name').textContent = data.name;
        var thumb = root.querySelector('.fu-thumb');
        if (thumb) thumb.remove();
        show(root, 'fu-uploaded');
      };
      xhr.send(form);
    }

    fileInput.addEventListener('change', function () {
      if (fileInput.files.length) upload(fileInput.files[0]);
      fileInput.value = '';
    });

    root.querySelector('.fu-cancel').addEventListener('click', function () {
      if (xhr) xhr.abort();
      setBusy(root, false);
      show(root, tokenInput.value ? 'fu-uploaded' : 'fu-empty');
    });

    root.querySelector('.fu-retry').addEventListener('click', function () {
      show(root, 'fu-empty');
    });

    root.querySelector('.fu-replace').addEventListener('click', function () {
      tokenInput.value = '';
      show(root, 'fu-empty');
    });

    // ---- Voice recording (audio questions only, progressive enhancement) ----
    if (root.dataset.recorder === '1'
        && window.MediaRecorder
        && navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      var recordBtn = root.querySelector('.fu-record');
      recordBtn.hidden = false;

      var recorder = null;
      var timer = null;

      recordBtn.addEventListener('click', function () {
        navigator.mediaDevices.getUserMedia({ audio: true }).then(function (stream) {
          var mime = MediaRecorder.isTypeSupported('audio/webm') ? 'audio/webm'
                   : MediaRecorder.isTypeSupported('audio/mp4') ? 'audio/mp4' : '';
          recorder = mime ? new MediaRecorder(stream, { mimeType: mime })
                          : new MediaRecorder(stream);
          var chunks = [];
          var startedAt = Date.now();

          recorder.ondataavailable = function (e) { if (e.data.size) chunks.push(e.data); };
          recorder.onstop = function () {
            clearInterval(timer);
            stream.getTracks().forEach(function (t) { t.stop(); });
            var type = recorder.mimeType || 'audio/webm';
            var ext = type.indexOf('mp4') !== -1 ? 'm4a' : 'webm';
            upload(new Blob(chunks, { type: type }), 'recording.' + ext);
          };

          show(root, 'fu-recording');
          recorder.start();
          var timeEl = root.querySelector('.fu-rec-time');
          timer = setInterval(function () {
            var s = Math.floor((Date.now() - startedAt) / 1000);
            timeEl.textContent = Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2);
          }, 250);
        }).catch(function () {
          // Denied or unavailable: stay quiet, the file input still works.
          recordBtn.hidden = true;
          show(root, 'fu-empty');
        });
      });

      root.querySelector('.fu-stop').addEventListener('click', function () {
        if (recorder && recorder.state !== 'inactive') recorder.stop();
      });
    }
  }

  function initAll(scope) {
    (scope || document).querySelectorAll('[data-file-upload]').forEach(init);
  }

  // Required lives here: the platform enforces required client-side (HTML5),
  // and a hidden input gets no HTML5 validation — so the widget blocks submit.
  document.addEventListener('submit', function (e) {
    var missing = null;
    e.target.querySelectorAll('[data-file-upload][data-required]').forEach(function (root) {
      var token = root.querySelector('[data-fu-token]');
      if (!missing && token && !token.value) missing = root;
    });
    if (missing) {
      e.preventDefault();
      missing.querySelector('.fu-message').textContent =
        missing.dataset.msgRequired || 'Please add a file.';
      show(missing, 'fu-error');
      missing.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
  }, true);

  document.addEventListener('DOMContentLoaded', function () { initAll(); });
  // Popups render widgets after DOMContentLoaded; they call this hook.
  window.initFileUploads = initAll;
})();
