/* Story picture lightbox (change story-image-lightbox).
 *
 * Every <img> inside .story-detail — the cover and the body figures, phone frames
 * included — opens large with its caption (the figure's <figcaption>, else the alt
 * text), a counter and previous/next within the same story. Authors write plain
 * figures; nothing in a story body knows about this script. The credit logo in the
 * byline is not a story picture.
 */
(function () {
    'use strict';

    var root = document.querySelector('.story-detail');
    var lb = document.getElementById('storyLightbox');
    if (!root || !lb) return;

    var pictures = Array.prototype.filter.call(root.querySelectorAll('img'), function (img) {
        return !img.closest('.sd-org') && !img.closest('#storyLightbox') && img.getAttribute('src');
    });
    if (!pictures.length) return;

    var lbImg = lb.querySelector('.story-lightbox__img');
    var lbCaption = lb.querySelector('.story-lightbox__caption');
    var lbCounter = lb.querySelector('.story-lightbox__counter');
    var closeBtn = lb.querySelector('.story-lightbox__close');
    var prevBtn = lb.querySelector('[data-dir="-1"]');
    var nextBtn = lb.querySelector('[data-dir="1"]');
    var current = -1;
    var opener = null;

    function captionOf(img) {
        var fig = img.closest('figure');
        var cap = fig && fig.querySelector('figcaption');
        return (cap && cap.textContent.trim()) || img.getAttribute('alt') || '';
    }

    function show(index) {
        current = (index + pictures.length) % pictures.length;
        var img = pictures[current];
        lbImg.src = img.currentSrc || img.src;
        lbImg.alt = img.getAttribute('alt') || '';
        lbCaption.textContent = captionOf(img);
        lbCounter.textContent = (current + 1) + ' / ' + pictures.length;
        var single = pictures.length < 2;
        prevBtn.hidden = single;
        nextBtn.hidden = single;
        lbCounter.hidden = single;
    }

    function open(index, source) {
        opener = source || null;
        show(index);
        lb.hidden = false;
        document.body.style.overflow = 'hidden';
        closeBtn.focus();
    }

    function close() {
        lb.hidden = true;
        lbImg.removeAttribute('src');
        document.body.style.overflow = '';
        if (opener && typeof opener.focus === 'function') opener.focus();
        opener = null;
    }

    pictures.forEach(function (img, i) {
        img.classList.add('story-picture');
        img.setAttribute('tabindex', '0');
        img.setAttribute('role', 'button');
        img.addEventListener('click', function (e) {
            if (img.closest('a')) return;  // a linked picture keeps its link
            e.preventDefault();
            open(i, img);
        });
        img.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); open(i, img); }
        });
    });

    prevBtn.addEventListener('click', function () { show(current - 1); });
    nextBtn.addEventListener('click', function () { show(current + 1); });
    closeBtn.addEventListener('click', close);
    lb.addEventListener('click', function (e) {
        if (e.target === lb || e.target.classList.contains('story-lightbox__stage')) close();
    });
    document.addEventListener('keydown', function (e) {
        if (lb.hidden) return;
        if (e.key === 'Escape') close();
        else if (e.key === 'ArrowLeft') show(current - 1);
        else if (e.key === 'ArrowRight') show(current + 1);
    });
})();
