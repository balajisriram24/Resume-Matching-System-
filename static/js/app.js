document.addEventListener('DOMContentLoaded', () => {
  const flashItems = document.querySelectorAll('.flash');
  flashItems.forEach((item, index) => {
    setTimeout(() => item.classList.add('is-visible'), index * 120);
  });

  const toggle = document.querySelector('.menu-toggle');
  const nav = document.querySelector('.nav-links');
  if (toggle && nav) {
    toggle.addEventListener('click', () => {
      nav.classList.toggle('nav-open');
    });

    nav.querySelectorAll('a').forEach((link) => {
      link.addEventListener('click', () => nav.classList.remove('nav-open'));
    });
  }
});
