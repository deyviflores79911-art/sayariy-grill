/* Pantalla de venta – Sayariy Grill POS */
(function () {
  'use strict';
  const $ = id => document.getElementById(id);
  const PRODUCTOS = JSON.parse($('datos-productos').textContent);
  const CFG = window.POS;

  // Dinero en centavos (enteros) para evitar errores de redondeo
  const cent = s => Math.round(parseFloat(s) * 100);
  const bs = c => 'Bs ' + (c / 100).toLocaleString('es-BO', { minimumFractionDigits: 2, maximumFractionDigits: 2 });
  const esc = s => String(s).replace(/[&<>"']/g, ch => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[ch]));

  const estado = { lineas: [], tipo: 'llevar', mesa: null, cat: '', metodo: null, notaIdx: null };

  // ---------- Catálogo ----------
  function pintarProductos() {
    const lista = PRODUCTOS.filter(p => !estado.cat || String(p.cat) === estado.cat);
    $('prods').innerHTML = lista.map(p => {
      const cant = estado.lineas.filter(l => l.id === p.id).reduce((a, l) => a + l.cantidad, 0);
      const img = p.foto
        ? `<div class="img" style="background-image:url('${encodeURI(p.foto)}')"></div>`
        : `<div class="img sin">${esc(p.nombre.charAt(0).toUpperCase())}</div>`;
      return `<button type="button" class="prod" data-id="${p.id}">
        ${img}${cant ? `<span class="badge">${cant}</span>` : ''}
        <div class="info"><div class="n">${esc(p.nombre)}</div><div class="p">${bs(cent(p.precio))}</div></div>
      </button>`;
    }).join('');
  }

  $('cats').addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return;
    estado.cat = b.dataset.cat;
    document.querySelectorAll('#cats button').forEach(x => x.classList.toggle('activo', x === b));
    pintarProductos();
  });

  $('prods').addEventListener('click', e => {
    const b = e.target.closest('.prod'); if (!b) return;
    const p = PRODUCTOS.find(x => x.id === Number(b.dataset.id));
    // Suma a la línea existente sin nota; si todas tienen nota, crea una nueva
    const linea = estado.lineas.find(l => l.id === p.id && !l.nota);
    if (linea) linea.cantidad++;
    else estado.lineas.push({ id: p.id, nombre: p.nombre, precio: cent(p.precio), cantidad: 1, nota: '' });
    if (navigator.vibrate) navigator.vibrate(15);
    pintar();
  });

  // ---------- Pedido ----------
  const total = () => estado.lineas.reduce((a, l) => a + l.precio * l.cantidad, 0);
  const numItems = () => estado.lineas.reduce((a, l) => a + l.cantidad, 0);

  function pintarPedido() {
    $('lineas').innerHTML = estado.lineas.length ? estado.lineas.map((l, i) => `
      <div class="linea">
        <div class="fila"><span>${l.cantidad} × ${esc(l.nombre)}</span><span>${bs(l.precio * l.cantidad)}</span></div>
        ${l.nota ? `<div class="nota">📝 ${esc(l.nota)}</div>` : ''}
        <div class="ctrl">
          <button type="button" data-acc="menos" data-i="${i}" class="${l.cantidad === 1 ? 'quitar' : ''}">${l.cantidad === 1 ? '🗑' : '−'}</button>
          <span class="cant">${l.cantidad}</span>
          <button type="button" data-acc="mas" data-i="${i}">+</button>
          <button type="button" data-acc="nota" data-i="${i}" class="btn-nota">📝 Nota</button>
        </div>
      </div>`).join('') : '<div class="vacio">Toque un producto para agregarlo al pedido</div>';

    const t = total();
    $('total').textContent = bs(t);
    $('bm-total').textContent = bs(t);
    const n = numItems();
    $('bm-items').textContent = n + (n === 1 ? ' producto' : ' productos');
    $('cobrar').disabled = !estado.lineas.length;
    $('btn-llevar').classList.toggle('activo', estado.tipo === 'llevar');
    $('btn-mesa').classList.toggle('activo', estado.tipo === 'mesa');
    $('btn-mesa').textContent = estado.tipo === 'mesa' ? `🍽 Mesa ${estado.mesa}` : '🍽 Mesa';
  }

  function pintar() { pintarProductos(); pintarPedido(); }

  $('lineas').addEventListener('click', e => {
    const b = e.target.closest('button[data-acc]'); if (!b) return;
    const i = Number(b.dataset.i), l = estado.lineas[i];
    if (b.dataset.acc === 'mas') l.cantidad++;
    if (b.dataset.acc === 'menos') { l.cantidad--; if (l.cantidad <= 0) estado.lineas.splice(i, 1); }
    if (b.dataset.acc === 'nota') return abrirNota(i);
    pintar();
  });

  $('vaciar').onclick = () => {
    if (estado.lineas.length && confirm('¿Vaciar todo el pedido?')) { reiniciar(); }
  };

  function reiniciar() {
    estado.lineas = []; estado.tipo = 'llevar'; estado.mesa = null; estado.metodo = null;
    $('cliente').value = ''; $('nota-pedido').value = '';
    pintar();
  }

  // Carrito en pantallas pequeñas
  $('ver-pedido').onclick = () => { $('carrito').classList.add('abierto'); $('cerrar-carrito').style.display = ''; };
  $('cerrar-carrito').onclick = () => { $('carrito').classList.remove('abierto'); };

  // ---------- Diálogos ----------
  document.querySelectorAll('dialog [data-cerrar]').forEach(b => b.addEventListener('click', () => b.closest('dialog').close()));

  // Mesa
  $('mesas').innerHTML = Array.from({ length: CFG.mesas }, (_, i) => `<button type="button" data-m="${i + 1}">${i + 1}</button>`).join('');
  $('btn-llevar').onclick = () => { estado.tipo = 'llevar'; estado.mesa = null; pintarPedido(); };
  $('btn-mesa').onclick = () => {
    document.querySelectorAll('#mesas button').forEach(b => b.classList.toggle('activo', Number(b.dataset.m) === estado.mesa));
    $('dlg-mesa').showModal();
  };
  $('mesas').addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return;
    estado.tipo = 'mesa'; estado.mesa = Number(b.dataset.m);
    $('dlg-mesa').close(); pintarPedido();
  });

  // Nota
  $('chips-nota').innerHTML = CFG.notas.map(n => `<button type="button">${esc(n)}</button>`).join('');
  $('chips-nota').addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return;
    const t = $('nota-txt');
    t.value = t.value ? t.value + ', ' + b.textContent : b.textContent;
  });
  function abrirNota(i) {
    estado.notaIdx = i;
    $('nota-prod').textContent = estado.lineas[i].nombre;
    $('nota-txt').value = estado.lineas[i].nota;
    $('dlg-nota').showModal();
  }
  function guardarNota(texto) {
    const l = estado.lineas[estado.notaIdx];
    texto = texto.trim().slice(0, 200);
    // Si hay varias unidades, la nota se aplica a una sola y el resto queda aparte
    if (texto && l.cantidad > 1 && !l.nota &&
        confirm(`¿La nota es para las ${l.cantidad} unidades?\n\nAceptar = para todas\nCancelar = solo para 1`) === false) {
      l.cantidad--;
      estado.lineas.splice(estado.notaIdx + 1, 0, { ...l, cantidad: 1, nota: texto });
    } else {
      l.nota = texto;
    }
    $('dlg-nota').close(); pintar();
  }
  $('nota-ok').onclick = () => guardarNota($('nota-txt').value);
  $('nota-borrar').onclick = () => guardarNota('');

  // ---------- Cobro ----------
  $('cobrar').onclick = () => {
    if (!estado.lineas.length) return;
    $('carrito').classList.remove('abierto');
    estado.metodo = null;
    $('cobro-total').textContent = bs(total());
    $('cobro-destino').textContent = estado.tipo === 'mesa' ? `Mesa ${estado.mesa}` : 'Para llevar';
    $('recibido').value = '';
    $('cobro-error').classList.add('oculto');
    setTimeout(() => $('cliente').focus(), 50);
    // Billetes sugeridos: exacto + billetes mayores al total
    const t = total() / 100;
    const opciones = [t, ...[10, 20, 50, 100, 200].filter(b => b > t)].slice(0, 6);
    $('billetes').innerHTML = opciones.map((v, i) =>
      `<button type="button" data-v="${v}">${i === 0 ? 'Exacto' : 'Bs ' + v}</button>`).join('');
    pintarCobro();
    $('dlg-cobro').showModal();
  };

  $('metodos').addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return;
    estado.metodo = b.dataset.m; pintarCobro();
    if (estado.metodo === 'efectivo') setTimeout(() => $('recibido').focus(), 50);
  });
  $('billetes').addEventListener('click', e => {
    const b = e.target.closest('button'); if (!b) return;
    $('recibido').value = Number(b.dataset.v).toFixed(2); pintarCobro();
  });
  $('recibido').addEventListener('input', pintarCobro);

  function pintarCobro() {
    document.querySelectorAll('#metodos button').forEach(b => b.classList.toggle('activo', b.dataset.m === estado.metodo));
    const ef = estado.metodo === 'efectivo';
    $('zona-efectivo').classList.toggle('oculto', !ef);
    let ok = !!estado.metodo;
    if (ef) {
      const rec = $('recibido').value === '' ? 0 : cent($('recibido').value);
      const cambio = rec - total();
      ok = $('recibido').value !== '' && cambio >= 0;
      $('cambio-caja').classList.toggle('falta', cambio < 0);
      $('cambio-caja').firstElementChild.textContent = cambio < 0 ? 'FALTA' : 'CAMBIO';
      $('cambio').textContent = bs(Math.abs(cambio));
    }
    $('confirmar').disabled = !ok;
  }

  let enviando = false;
  $('confirmar').onclick = async () => {
    if (enviando) return;
    enviando = true; $('confirmar').disabled = true; $('confirmar').textContent = 'Guardando…';
    try {
      const r = await fetch(CFG.urlConfirmar, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': CFG.csrf },
        body: JSON.stringify({
          items: estado.lineas.map(l => ({ id: l.id, cantidad: l.cantidad, nota: l.nota })),
          tipo: estado.tipo, mesa: estado.mesa, metodo: estado.metodo,
          cliente: $('cliente').value, nota: $('nota-pedido').value,
          recibido: estado.metodo === 'efectivo' ? $('recibido').value : null,
        }),
      });
      const data = await r.json().catch(() => ({ ok: false, error: 'Error del servidor.' }));
      if (data.ok) { window.location.href = data.url; return; }
      mostrarError(data.error || 'No se pudo guardar la venta.');
    } catch (err) {
      mostrarError('Sin conexión con el servidor. Revise el WiFi e intente de nuevo.');
    }
    enviando = false; $('confirmar').textContent = '✔ Confirmar venta'; pintarCobro();
  };
  function mostrarError(msg) { $('cobro-error').textContent = msg; $('cobro-error').classList.remove('oculto'); }

  // Avisar si intenta salir con un pedido sin cobrar
  window.addEventListener('beforeunload', e => { if (estado.lineas.length && !enviando) { e.preventDefault(); e.returnValue = ''; } });

  pintar();
})();
