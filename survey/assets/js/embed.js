/* Mapsurvey embed helper (change embed-surveys).
 *
 * Paired with the iframe snippet from the Share page. The embedded survey
 * posts {mapsurvey: "height", height: <px>} whenever its content height
 * changes; this script sets the matching iframe's height so a form-layout
 * survey never shows an inner scrollbar. Messages are matched by window
 * (event.source === iframe.contentWindow), never by origin alone, so a stray
 * message from any other frame on the page does nothing.
 *
 * Served unhashed at /embed.js so pasted snippets keep working across deploys.
 */
(function () {
  if (window.__mapsurveyEmbed) return;
  window.__mapsurveyEmbed = true;

  function onMessage(event) {
    var data = event.data;
    if (!data || typeof data !== 'object' || data.mapsurvey !== 'height') return;
    var height = parseInt(data.height, 10);
    if (!(height >= 300) || height > 20000) return;  // 300 = the smallest frame worth showing
    var frames = document.getElementsByTagName('iframe');
    for (var i = 0; i < frames.length; i++) {
      if (frames[i].contentWindow === event.source) {
        frames[i].style.height = height + 'px';
        return;
      }
    }
  }

  window.addEventListener('message', onMessage, false);
})();
