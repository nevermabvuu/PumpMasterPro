/**
 * pump_selection.js — Liquid parameter switching and pump comparison logic
 */

document.addEventListener('DOMContentLoaded', () => {

  const liquidSel = document.getElementById('liquidSel');
  if (!liquidSel) return;

  // Panel switching
  function updateLiquidPanels() {
    const liquid = liquidSel.value;
    document.getElementById('waterParams').style.display   = liquid === 'water'   ? '' : 'none';
    document.getElementById('viscousParams').style.display = liquid === 'viscous' ? '' : 'none';
    document.getElementById('slurryParams').style.display  = liquid === 'slurry'  ? '' : 'none';
  }
  liquidSel.addEventListener('change', updateLiquidPanels);
  updateLiquidPanels();

  // Auto-calculate slurry density
  function calcSlurryDensity() {
    const cv       = parseFloat(document.querySelector('[name=slurry_cv]')?.value || 0);
    const rhoSolid = parseFloat(document.querySelector('[name=rho_solid]')?.value || 2650);
    const rhoSlurry = 1000 * (1 - cv) + rhoSolid * cv;
    const el = document.getElementById('rhoSlurryCalc');
    if (el) el.value = rhoSlurry.toFixed(0);
  }

  document.querySelector('[name=slurry_cv]')?.addEventListener('input', calcSlurryDensity);
  document.querySelector('[name=rho_solid]')?.addEventListener('input', calcSlurryDensity);
  calcSlurryDensity();

  // Pump comparison checkbox logic
  const compareLink  = document.getElementById('compareLink');
  const compareCount = document.getElementById('compareCount');
  const checkboxes   = document.querySelectorAll('.pump-compare-cb');

  function updateCompareLink() {
    const selected = [...document.querySelectorAll('.pump-compare-cb:checked')].map(cb => cb.value);
    if (compareCount) compareCount.textContent = selected.length;
    if (compareLink) {
      if (selected.length >= 2) {
        const liquid = document.getElementById('liquidSel')?.value || 'water';
        const qDuty  = document.querySelector('[name=q_duty]')?.value || '';
        const hDuty  = document.querySelector('[name=h_duty]')?.value || '';
        const params = selected.map(id => `ids=${id}`).join('&');
        compareLink.href = `/pump-comparison?${params}&liquid=${liquid}&q_duty=${qDuty}&h_duty=${hDuty}`;
        compareLink.classList.remove('disabled');
      } else {
        compareLink.classList.add('disabled');
        compareLink.href = '#';
      }
    }
  }

  checkboxes.forEach(cb => cb.addEventListener('change', updateCompareLink));
  updateCompareLink();
});
