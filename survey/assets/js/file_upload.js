/* Respondent file upload widget (openspec: respondent-file-uploads).
 *
 * Several files per question. Each uploaded file becomes one .fu-item with a
 * hidden token input (inputs share the field name, so the POST carries a
 * list), a thumbnail/chip preview, and a remove button. Bytes leave the page
 * the moment a file is picked or a recording stops. Voice recording is
 * progressive enhancement over the file input.
 *
 * The popup form asks whether uploads are still in flight via
 * window.fileUploadsBusy(container) — Apply waits for tokens.
 */
(function () {
  'use strict';

  function getCookie(name) {
    var m = document.cookie.match('(^|;)\\s*' + name + '\\s*=\\s*([^;]+)');
    return m ? m.pop() : '';
  }

  function setBusy(root, busy) {
    if (busy) root.setAttribute('data-fu-busy', '1');
    else root.removeAttribute('data-fu-busy');
  }

  window.fileUploadsBusy = function (container) {
    return !!(container || document).querySelector('[data-fu-busy]');
  };

  function itemCount(root) {
    return root.querySelectorAll('.fu-item').length;
  }

  function refreshControls(root) {
    var max = parseInt(root.dataset.maxFiles, 10) || 1;
    var controls = root.querySelector('.fu-controls');
    if (controls) controls.hidden = itemCount(root) >= max;
  }

  function addItem(root, token, name, localUrl) {
    var isImage = root.dataset.inputType === 'photo';
    var item = document.createElement('div');
    item.className = 'fu-item';
    item.style.cssText = 'position:relative;';

    var hidden = document.createElement('input');
    hidden.type = 'hidden';
    hidden.name = root.dataset.question;
    hidden.setAttribute('data-fu-token', '');
    hidden.value = token;
    item.appendChild(hidden);

    var inputType = root.dataset.inputType;
    if (inputType === 'photo' && localUrl) {
      // Fresh uploads preview from the local blob — instant, and exactly the
      // bytes the respondent picked. Signed URLs take over on re-render.
      var link = document.createElement('a');
      link.href = localUrl;
      link.target = '_blank';
      link.rel = 'noopener';
      link.title = name;
      link.setAttribute('data-fu-lightbox', '');
      var img = document.createElement('img');
      img.className = 'fu-thumb';
      img.src = localUrl;
      img.alt = name;
      img.style.cssText = 'width:72px;height:72px;object-fit:cover;border-radius:8px;border:1px solid #dee2e6;';
      link.appendChild(img);
      item.appendChild(link);
    } else if (inputType === 'audio' && localUrl) {
      // Recorded or picked audio is replayable right here.
      var player = document.createElement('audio');
      player.controls = true;
      player.preload = 'metadata';
      player.src = localUrl;
      player.title = name;
      player.style.cssText = 'max-width:220px;height:36px;';
      item.appendChild(player);
    } else {
      var chip;
      if (localUrl) {
        chip = document.createElement('a');
        chip.href = localUrl;
        chip.setAttribute('download', name);
      } else {
        chip = document.createElement('span');
      }
      chip.className = 'fu-file-chip';
      chip.style.cssText = 'display:inline-block;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;padding:8px 12px;border:1px solid #dee2e6;border-radius:8px;font-size:0.8rem;';
      chip.textContent = name; // text only, never markup
      item.appendChild(chip);
    }

    var remove = document.createElement('button');
    remove.type = 'button';
    remove.className = 'fu-remove';
    remove.title = 'Remove';
    remove.setAttribute('aria-label', 'Remove file ' + name);
    remove.textContent = '×';
    remove.style.cssText = 'position:absolute;top:-10px;right:-10px;width:28px;height:28px;line-height:1;border-radius:50%;border:1px solid #dee2e6;background:#fff;padding:0;';
    item.appendChild(remove);

    root.querySelector('.fu-items').appendChild(item);
    refreshControls(root);
  }

  function init(root) {
    if (root.dataset.fuInit) return;
    root.dataset.fuInit = '1';

    var fileInputs = root.querySelectorAll('.fu-input');
    var xhr = null;

    function show(cls, on) {
      var el = root.querySelector('.' + cls);
      if (el) el.hidden = !on;
    }

    function fail(message) {
      setBusy(root, false);
      show('fu-uploading', false);
      root.querySelector('.fu-message').textContent = message;
      show('fu-error', true);
    }

    function upload(file, name) {
      var maxBytes = parseInt(root.dataset.maxBytes, 10) || 0;
      if (maxBytes && file.size > maxBytes) {
        fail(root.dataset.msgTooLarge || 'File is too large.');
        return;
      }
      setBusy(root, true);
      show('fu-error', false);
      show('fu-uploading', true);

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
        show('fu-uploading', false);
        var data = null;
        try { data = JSON.parse(xhr.responseText); } catch (e) { /* fall through */ }
        if (xhr.status !== 200 || !data || !data.token) {
          fail((data && data.message) || 'Upload failed.');
          return;
        }
        var localUrl = null;
        try { localUrl = URL.createObjectURL(file); } catch (e) { /* preview only */ }
        addItem(root, data.token, data.name, localUrl);
      };
      xhr.send(form);
    }

    fileInputs.forEach(function (fileInput) {
      fileInput.addEventListener('change', function () {
        if (fileInput.files.length) upload(fileInput.files[0]);
        fileInput.value = '';
      });
    });

    root.querySelector('.fu-cancel').addEventListener('click', function () {
      if (xhr) xhr.abort();
      setBusy(root, false);
      show('fu-uploading', false);
    });

    root.querySelector('.fu-retry').addEventListener('click', function () {
      show('fu-error', false);
    });

    root.addEventListener('click', function (e) {
      var btn = e.target.closest('.fu-remove');
      if (!btn) return;
      btn.closest('.fu-item').remove();
      refreshControls(root);
    });

    refreshControls(root);

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
            show('fu-recording', false);
            stream.getTracks().forEach(function (t) { t.stop(); });
            var type = recorder.mimeType || 'audio/webm';
            var ext = type.indexOf('mp4') !== -1 ? 'm4a' : 'webm';
            upload(new Blob(chunks, { type: type }), 'recording.' + ext);
          };

          show('fu-recording', true);
          recorder.start();
          var timeEl = root.querySelector('.fu-rec-time');
          timer = setInterval(function () {
            var s = Math.floor((Date.now() - startedAt) / 1000);
            timeEl.textContent = Math.floor(s / 60) + ':' + ('0' + (s % 60)).slice(-2);
          }, 250);
        }).catch(function () {
          // Denied or unavailable: stay quiet, the file input still works.
          recordBtn.hidden = true;
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
  // and hidden inputs get no HTML5 validation — so the widget blocks submit.
  document.addEventListener('submit', function (e) {
    var missing = null;
    e.target.querySelectorAll('[data-file-upload][data-required]').forEach(function (root) {
      if (!missing && !root.querySelector('[data-fu-token]')) missing = root;
    });
    if (missing) {
      e.preventDefault();
      missing.querySelector('.fu-message').textContent =
        missing.dataset.msgRequired || 'Please add a file.';
      missing.querySelector('.fu-error').hidden = false;
      missing.scrollIntoView({ block: 'center', behavior: 'smooth' });
    }
  }, true);

  // Lightbox: photos open in an in-page modal instead of a new tab. Esc or a
  // click anywhere closes it. The anchor href stays as the no-JS fallback.
  function openLightbox(src, alt) {
    var overlay = document.createElement('div');
    overlay.className = 'fu-lightbox';
    overlay.style.cssText = 'position:fixed;inset:0;z-index:20000;background:rgba(0,0,0,0.82);display:flex;align-items:center;justify-content:center;cursor:zoom-out;';
    var img = document.createElement('img');
    img.src = src;
    img.alt = alt || '';
    img.style.cssText = 'max-width:92vw;max-height:92vh;border-radius:6px;box-shadow:0 8px 40px rgba(0,0,0,0.5);';
    overlay.appendChild(img);
    function close() {
      overlay.remove();
      document.removeEventListener('keydown', onKey);
    }
    function onKey(e) { if (e.key === 'Escape') close(); }
    overlay.addEventListener('click', close);
    document.addEventListener('keydown', onKey);
    document.body.appendChild(overlay);
  }

  document.addEventListener('click', function (e) {
    var link = e.target.closest('[data-fu-lightbox]');
    if (!link) return;
    e.preventDefault();
    var img = link.querySelector('img');
    openLightbox(link.href, img ? img.alt : '');
  });

  document.addEventListener('DOMContentLoaded', function () { initAll(); });
  // Popups render widgets after DOMContentLoaded; they call this hook.
  window.initFileUploads = initAll;
})();
