// Minimal, framework-free waitlist submit + footer year
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('waitlist-form');
  const email = document.getElementById('email');
  const hp = document.getElementById('hp');
  const msg = document.getElementById('form-msg');
  const year = document.getElementById('year');
  if (year) year.textContent = String(new Date().getFullYear());

  // Smooth-scroll CTAs to top and focus the email input
  document.querySelectorAll('a.cta[href="#"]').forEach((a) => {
    a.addEventListener('click', (e) => {
      e.preventDefault();
      // Scroll to top smoothly
      window.scrollTo({ top: 0, behavior: 'smooth' });
      // After a short delay, focus the email input
      // Use requestAnimationFrame for a couple frames to ensure layout has settled
      let frames = 0;
      function focusSoon() {
        frames++;
        if (frames > 6) { // ~100ms at 60fps
          email?.focus();
          return;
        }
        requestAnimationFrame(focusSoon);
      }
      requestAnimationFrame(focusSoon);
    });
  });

  if (!form) return;

  // If a data-endpoint is provided, submit via fetch; else let the form submit normally (Netlify/static).
  const endpoint = form.getAttribute('data-endpoint');
  if (!endpoint) return;

  function setMsg(text, ok = false) {
    if (!msg) return;
    msg.textContent = text;
    msg.style.color = ok ? '#16a34a' : '#b91c1c';
  }

  form.addEventListener('submit', async (e) => {
    e.preventDefault();
    const value = (email?.value || '').trim();
    if (!value || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
      setMsg('Please enter a valid email address.');
      email?.focus();
      return;
    }
    setMsg('Submitting…', true);

    try {
      const res = await fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email: value, hp: hp?.value || '' }),
      });
      if (res.ok) {
        const data = await res.json().catch(() => ({}));
        if (data?.pending === true) {
          setMsg('Check your inbox to confirm your subscription.', true);
        } else {
          setMsg("You're on the list. Thank you!", true);
        }
        form.reset();
      } else {
        const data = await res.json().catch(() => ({}));
        setMsg(data?.error || 'Something went wrong. Please try again later.');
      }
    } catch (err) {
      setMsg('Network error. Please try again.');
    }
  });

  // Lottie hydration: lazy-load local vendor script and animations
  const slots = Array.from(document.querySelectorAll('.lottie-slot[data-animation]'));
  if (slots.length) {
    const io = new IntersectionObserver(async (entries, obs) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        const el = entry.target;
        obs.unobserve(el);
        try {
          // Load lottie-web if not already loaded
          if (!window.lottie) {
            await loadScript('/vendor/lottie.min.js');
          }
          const file = el.getAttribute('data-animation');
          if (!file) continue;
          const path = `/animations/${file}`;
          window.lottie.loadAnimation({
            container: el,
            renderer: 'svg',
            loop: true,
            autoplay: true,
            path,
          });
          const ph = el.querySelector('.placeholder');
          if (ph) ph.remove();
        } catch (e) {
          // Silent fail; placeholder stays visible
        }
      }
    }, { rootMargin: '100px' });
    slots.forEach((el) => io.observe(el));
  }
});

function loadScript(src) {
  return new Promise((resolve, reject) => {
    const s = document.createElement('script');
    s.src = src;
    s.async = true;
    s.onload = () => resolve();
    s.onerror = reject;
    document.head.appendChild(s);
  });
}
