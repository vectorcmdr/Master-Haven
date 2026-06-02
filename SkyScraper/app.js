const tabs = document.querySelectorAll('.tab-btn');
const panels = document.querySelectorAll('.panel');
tabs.forEach(tab => {
  tab.addEventListener('click', () => {
    const target = tab.dataset.tab;
    tabs.forEach(t => t.classList.remove('active'));
    panels.forEach(p => p.classList.remove('active'));
    tab.classList.add('active');
    document.getElementById('tab-' + target).classList.add('active');
    history.replaceState(null, '', '#' + target);
    window.scrollTo({ top: document.querySelector('.tabs').offsetTop - 8, behavior: 'smooth' });
  });
});
// Expandable timeline entries — click a day to reveal its deep-dive
document.querySelectorAll('#tab-timeline .timeline-entry').forEach(en => {
  if (!en.querySelector('.tl-deep')) return;
  en.classList.add('expandable');
  en.addEventListener('click', (e) => {
    if (e.target.closest('a')) return; // let inline links work normally
    en.classList.toggle('open');
  });
});

// Puzzles · Active/Solved filter
(function () {
  const pBtns = document.querySelectorAll('.pf-btn');
  const puzzles = document.querySelectorAll('#tab-puzzles .puzzle');
  if (!pBtns.length || !puzzles.length) return;
  const isSolved = p => !!p.querySelector('.status-solved');
  const total = puzzles.length;
  const solved = [...puzzles].filter(isSolved).length;
  const counts = { all: total, active: total - solved, solved: solved };
  pBtns.forEach(b => {
    const c = b.querySelector('.pf-count');
    if (c) c.textContent = counts[b.dataset.filter];
  });
  function apply(filter) {
    puzzles.forEach(p => {
      const show = filter === 'all' || (filter === 'solved' ? isSolved(p) : !isSolved(p));
      p.classList.toggle('pf-hidden', !show);
    });
    pBtns.forEach(b => b.classList.toggle('active', b.dataset.filter === filter));
  }
  pBtns.forEach(b => b.addEventListener('click', () => apply(b.dataset.filter)));
  apply('all');
})();

const hash = window.location.hash.replace('#', '');
if (hash && document.getElementById('tab-' + hash)) {
  document.querySelector(`.tab-btn[data-tab="${hash}"]`).click();
}
