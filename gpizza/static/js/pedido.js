// Formulario de pedido (boceto 2), compartido por el cliente y el cajero.
// Lo que calcula este archivo es solo para mostrarlo mientras se arma el pedido: al enviarlo,
// el servidor vuelve a calcular todo con los precios de la base de datos (RN-007).
(() => {
  const form = document.getElementById('form-pedido');
  if (!form) return;

  const MINIMO = Number(form.dataset.minimo);              // RN-001
  const MAX_DISTINTOS = Number(form.dataset.maxDistintos); // RN-003
  const MAX_UNIDADES = Number(form.dataset.maxUnidades);   // RN-003
  const CLAVE_BORRADOR = 'gpizza-borrador-' + form.dataset.borrador;
  const pesos = (n) => '$ ' + n.toLocaleString('es-MX', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

  const campoCantidad = (id) => form.querySelector(`[data-cantidad-de="${id}"]`);
  const cantidad = (id) => Number(campoCantidad(id)?.value || 0);
  const precios = {};
  form.querySelectorAll('.gp-tamano').forEach((b) => { precios[b.dataset.id] = Number(b.dataset.precio); });
  let descuentoCodigo = null; // {tipo, valor} si se aplicó un código válido

  // ---------------------------------------------------------------- pestañas Pizzas / Complementos
  form.querySelectorAll('[data-pestana]').forEach((boton) => boton.addEventListener('click', () => {
    form.querySelectorAll('[data-pestana]').forEach((b) => {
      b.classList.toggle('activa', b === boton);
      b.setAttribute('aria-selected', b === boton);
    });
    form.querySelectorAll('[data-categoria]').forEach((lista) => { lista.hidden = lista.dataset.categoria !== boton.dataset.pestana; });
  }));

  // ---------------------------------------------------------------- tarjetas de producto
  const tarjetas = [...form.querySelectorAll('[data-producto]')];

  function seleccionado(tarjeta) {
    return tarjeta.querySelector('.gp-tamano.activa') || tarjeta.querySelector('.gp-tamano:not([disabled])');
  }

  function pintarTarjeta(tarjeta) {
    const opcion = seleccionado(tarjeta);
    tarjeta.querySelectorAll('.gp-tamano').forEach((b) => b.classList.toggle('activa', b === opcion));
    tarjeta.querySelector('[data-precio-visible]').textContent = pesos(precios[opcion.dataset.id]);
    tarjeta.querySelector('[data-cantidad]').textContent = cantidad(opcion.dataset.id);
    tarjeta.querySelector('[data-menos]').disabled = cantidad(opcion.dataset.id) === 0;
    tarjeta.querySelector('[data-mas]').disabled = cantidad(opcion.dataset.id) >= MAX_UNIDADES;
    // "Mediana × 2 · Familiar × 1" cuando se piden varios tamaños de la misma pizza.
    const elegidos = [...tarjeta.querySelectorAll('.gp-tamano')]
      .filter((b) => cantidad(b.dataset.id) > 0)
      .map((b) => `${b.textContent.trim()} × ${cantidad(b.dataset.id)}`);
    tarjeta.querySelector('[data-resumen-producto]').textContent = elegidos.length > 1 ? elegidos.join(' · ') : '';
    tarjeta.classList.toggle('gp-producto-elegido', elegidos.length > 0);
  }

  function distintos() {
    return [...form.querySelectorAll('[data-cantidad-de]')].filter((c) => Number(c.value) > 0).length;
  }

  function cambiar(tarjeta, delta) {
    const id = seleccionado(tarjeta).dataset.id;
    const actual = cantidad(id);
    const nueva = Math.min(MAX_UNIDADES, Math.max(0, actual + delta));
    if (actual === 0 && nueva > 0 && distintos() >= MAX_DISTINTOS) {
      mostrarError(`Máximo ${MAX_DISTINTOS} productos distintos por pedido (RN-003).`);
      return;
    }
    campoCantidad(id).value = nueva;
    mostrarError('');
    actualizar();
  }

  tarjetas.forEach((tarjeta) => {
    tarjeta.querySelectorAll('.gp-tamano').forEach((b) => b.addEventListener('click', () => {
      tarjeta.querySelectorAll('.gp-tamano').forEach((x) => x.classList.toggle('activa', x === b));
      pintarTarjeta(tarjeta);
    }));
    tarjeta.querySelector('[data-mas]').addEventListener('click', () => cambiar(tarjeta, +1));
    tarjeta.querySelector('[data-menos]').addEventListener('click', () => cambiar(tarjeta, -1));
    // Si ya hay cantidades (borrador o error del servidor), se muestra el primer tamaño elegido.
    const conCantidad = [...tarjeta.querySelectorAll('.gp-tamano')].find((b) => cantidad(b.dataset.id) > 0);
    if (conCantidad) conCantidad.classList.add('activa');
  });

  function mostrarError(texto) {
    const destino = document.getElementById('error-productos');
    if (texto || !destino.dataset.servidor) destino.textContent = texto;
  }
  document.getElementById('error-productos').dataset.servidor = document.getElementById('error-productos').textContent.trim() ? '1' : '';

  // ---------------------------------------------------------------- totales
  const formaPago = () => form.querySelector('[name="forma_pago"]:checked')?.value || '';

  function totales() {
    let subtotal = 0;
    form.querySelectorAll('[data-cantidad-de]').forEach((c) => { subtotal += (precios[c.dataset.cantidadDe] || 0) * Number(c.value); });
    let descuento = 0;
    if (descuentoCodigo) {
      descuento = descuentoCodigo.tipo === 'PORCENTAJE'
        ? Math.round(subtotal * descuentoCodigo.valor) / 100
        : Math.min(descuentoCodigo.valor, subtotal);
    }
    return { subtotal, descuento, total: subtotal - descuento };
  }

  function actualizar() {
    tarjetas.forEach(pintarTarjeta);
    const { subtotal, descuento, total } = totales();
    document.getElementById('resumen-subtotal').textContent = pesos(subtotal);
    document.getElementById('resumen-descuento').textContent = '− ' + pesos(descuento);
    document.getElementById('resumen-total').textContent = pesos(total);
    const minimoOk = subtotal >= MINIMO;
    const aviso = document.getElementById('aviso-minimo');
    aviso.textContent = minimoOk ? 'Pedido mínimo $100 cubierto.' : `Pedido mínimo $100 (RN-001): te faltan ${pesos(MINIMO - subtotal)}.`;
    aviso.classList.toggle('gp-texto-alerta', !minimoOk);

    const efectivo = formaPago() === 'Efectivo';
    document.getElementById('campo-efectivo').hidden = !efectivo;
    const referencia = document.getElementById('campo-referencia');
    if (referencia) referencia.hidden = efectivo;
    const recibido = Number((document.getElementById('monto_recibido').value || '').replace(/[$,\s]/g, ''));
    const filaCambio = document.getElementById('fila-cambio');
    filaCambio.hidden = !(efectivo && recibido >= total && total > 0);
    document.getElementById('resumen-cambio').textContent = pesos(Math.max(0, recibido - total)); // RN-010
    guardarBorrador();
  }

  form.addEventListener('input', actualizar);
  form.addEventListener('change', actualizar);

  // ---------------------------------------------------------------- código de descuento (RN-008)
  document.getElementById('aplicar-codigo').addEventListener('click', async () => {
    const mensaje = document.getElementById('mensaje-codigo');
    const codigo = document.getElementById('codigo').value.trim();
    if (!codigo) { descuentoCodigo = null; mensaje.textContent = ''; actualizar(); return; }
    const datos = new FormData();
    datos.append('codigo', codigo);
    datos.append('subtotal', totales().subtotal.toFixed(2));
    try {
      const respuesta = await fetch(form.dataset.urlCodigo, {
        method: 'POST', body: datos,
        headers: { 'X-CSRFToken': document.querySelector('meta[name="csrf-token"]').content },
      });
      const r = await respuesta.json();
      descuentoCodigo = r.ok ? { tipo: r.tipo, valor: Number(r.valor) } : null;
      mensaje.textContent = r.mensaje;
      mensaje.classList.toggle('gp-texto-exito', r.ok);
    } catch {
      mensaje.textContent = 'Sin conexión: el código se revisará al enviar el pedido.';
    }
    actualizar();
  });

  // ---------------------------------------------------------------- borrador en el navegador (CU-001 FA-5)
  function guardarBorrador() {
    try {
      const datos = Object.fromEntries(new FormData(form));
      delete datos.csrf_token;
      localStorage.setItem(CLAVE_BORRADOR, JSON.stringify(datos));
    } catch { /* el navegador puede no permitir localStorage: el pedido funciona igual */ }
  }

  function restaurarBorrador() {
    if (form.dataset.hayValores === 'si') return; // el servidor ya devolvió lo que se había escrito
    let datos = null;
    try { datos = JSON.parse(localStorage.getItem(CLAVE_BORRADOR) || 'null'); } catch { return; }
    if (!datos || !Object.keys(datos).some((k) => k.startsWith('cantidad_') && Number(datos[k]) > 0)) return;
    for (const [nombre, valor] of Object.entries(datos)) {
      const campos = form.querySelectorAll(`[name="${CSS.escape(nombre)}"]`);
      campos.forEach((campo) => {
        if (campo.type === 'radio') campo.checked = campo.value === valor;
        else campo.value = valor;
      });
    }
    tarjetas.forEach((t) => {
      const conCantidad = [...t.querySelectorAll('.gp-tamano')].find((b) => cantidad(b.dataset.id) > 0);
      if (conCantidad) t.querySelectorAll('.gp-tamano').forEach((b) => b.classList.toggle('activa', b === conCantidad));
    });
    const aviso = document.getElementById('aviso-borrador');
    if (aviso) {
      aviso.textContent = 'Recuperamos el pedido que estabas armando en este dispositivo.';
      aviso.hidden = false;
    }
  }

  // ---------------------------------------------------------------- "Usar mi ubicación" (opcional, para el mapa)
  const botonUbicacion = document.getElementById('usar-ubicacion');
  if (botonUbicacion) botonUbicacion.addEventListener('click', () => {
    const estado = document.getElementById('estado-ubicacion');
    if (!('geolocation' in navigator) || !window.isSecureContext) {
      estado.textContent = 'Tu navegador no comparte la ubicación en esta conexión; tu dirección basta.';
      return;
    }
    estado.textContent = 'Buscando tu ubicación…';
    navigator.geolocation.getCurrentPosition((pos) => {
      form.querySelector('[name="latitud"]').value = pos.coords.latitude.toFixed(6);
      form.querySelector('[name="longitud"]').value = pos.coords.longitude.toFixed(6);
      estado.textContent = 'Ubicación guardada: tu casa aparecerá en el mapa.';
      guardarBorrador();
    }, () => { estado.textContent = 'No pudimos leer tu ubicación; tu dirección basta.'; });
  });

  // Sin conexión no se intenta enviar: el borrador ya quedó guardado (CU-001 FA-5).
  form.addEventListener('submit', (evento) => {
    if (!navigator.onLine) {
      evento.preventDefault();
      document.getElementById('estado-conexion').textContent =
        'Sin conexión: tu pedido quedó guardado en este dispositivo. Envíalo cuando vuelva la red.';
    }
  });

  restaurarBorrador();
  actualizar();
})();
