(() => {
  const library = window.CH_CHARACTER_PALETTES;
  if (!library) return;
  const familySelect = document.getElementById('paletteFamily');
  const swatches = document.getElementById('swatches');
  const color = document.getElementById('color');
  if (!familySelect || !swatches || !color) return;

  const labels = {
    skin:'Pele', hair:'Cabelo', neutral:'Neutros', vivid:'Vivas', pastel:'Pastéis',
    earth:'Terra', deep:'Profundas', metal:'Metais', fantasy:'Fantasia'
  };

  function renderFamily() {
    swatches.innerHTML = '';
    const family = library.families[familySelect.value] || [];
    for (const entry of family) {
      const button = document.createElement('button');
      button.className = 'swatch';
      button.style.background = entry.hex;
      button.title = `${entry.id} · ${entry.hex}`;
      button.dataset.colorId = entry.id;
      button.addEventListener('click', () => {
        color.value = entry.hex.toLowerCase();
        [...swatches.children].forEach(node => node.classList.remove('active'));
        button.classList.add('active');
      });
      swatches.appendChild(button);
    }
  }

  familySelect.innerHTML = '';
  for (const family of Object.keys(library.families)) {
    const option = document.createElement('option');
    option.value = family;
    option.textContent = `${labels[family] || family} (${library.families[family].length})`;
    familySelect.appendChild(option);
  }
  familySelect.value = 'vivid';
  familySelect.addEventListener('change', renderFamily);
  renderFamily();
})();
