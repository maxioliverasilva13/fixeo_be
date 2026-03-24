# Guía Frontend — Métodos de pago por empresa

Cada empresa puede configurar qué métodos de pago acepta:
**efectivo** y/o **tarjeta (MercadoPago)**.

Esto impacta en dos lugares del frontend:
1. Pantalla de configuración de la empresa (perfil del vendedor)
2. Pantalla de checkout (experiencia del comprador)

---

## 1. Datos que devuelve el backend

Al consultar una empresa (`GET /api/empresas/{id}/`), la respuesta ahora incluye:

```json
{
  "ok": true,
  "data": {
    "id": 5,
    "nombre": "Panadería Don Juan",
    "acepta_efectivo": true,
    "acepta_tarjeta": true,
    "efectivo_disponible": false,
    "metodos_pago_disponibles": ["mercadopago"],
    ...
  }
}
```

### Campos clave

| Campo | Tipo | Descripción |
|---|---|---|
| `acepta_efectivo` | bool | El vendedor activó la opción de efectivo |
| `acepta_tarjeta` | bool | El vendedor activó la opción de tarjeta |
| `efectivo_disponible` | bool | `acepta_efectivo` **Y** tiene suscripción activa |
| `metodos_pago_disponibles` | string[] | Lista real de métodos que se pueden usar (`"mercadopago"`, `"efectivo"`) |

**Diferencia importante**: `acepta_efectivo` puede ser `true` pero `efectivo_disponible` ser `false` si el vendedor no tiene suscripción activa. El frontend debe usar `efectivo_disponible` para saber si realmente se puede pagar en efectivo.

---

## 2. Pantalla de configuración (perfil del vendedor)

### Ruta sugerida

`/empresa/metodos-pago` o dentro de `/empresa/configuracion`

### Endpoint para actualizar

```
PATCH /api/empresas/{empresa_id}/metodos-pago/
Authorization: Bearer <token>
Content-Type: application/json

{
  "acepta_efectivo": true,
  "acepta_tarjeta": false
}
```

Los dos campos son opcionales — podés enviar solo el que cambia.

### Respuesta

```json
{
  "ok": true,
  "data": {
    "id": 5,
    "acepta_efectivo": true,
    "acepta_tarjeta": false,
    "efectivo_disponible": true,
    "metodos_pago_disponibles": ["efectivo"],
    ...
  }
}
```

### Error si no tiene suscripción

Si el vendedor intenta activar `acepta_efectivo` sin suscripción:

```json
{
  "ok": false,
  "message": "Necesitás una suscripción activa para habilitar pagos en efectivo"
}
```

### Diseño sugerido

```
┌─────────────────────────────────────────────┐
│  Métodos de pago                            │
│                                             │
│  Configurá cómo pueden pagarte              │
│  tus clientes.                              │
│                                             │
│  ┌────────────────────────────────────────┐ │
│  │  💳 Pago con tarjeta                   │ │
│  │                                        │ │
│  │  Tus clientes pagan con tarjeta de     │ │
│  │  crédito o débito via MercadoPago.     │ │
│  │  Fixeo retiene un 10% de comisión      │ │
│  │  por cada venta.                       │ │
│  │                                        │ │
│  │  El dinero se deposita en tu cuenta    │ │
│  │  de Fixeo cuando la orden se           │ │
│  │  finaliza.                             │ │
│  │                                [ON/OFF]│ │
│  └────────────────────────────────────────┘ │
│                                             │
│  ┌────────────────────────────────────────┐ │
│  │  💵 Pago en efectivo                   │ │
│  │                                        │ │
│  │  Tus clientes pagan en persona al      │ │
│  │  retirar o recibir el pedido.          │ │
│  │  Sin comisión por transacción.         │ │
│  │                                        │ │
│  │  ⚠️ Requiere suscripción activa        │ │ ← si no tiene sub
│  │  [Ver planes]                          │ │ ← link a planes
│  │                                        │ │
│  │                          [DESHABILITADO]│ │ ← switch gris
│  └────────────────────────────────────────┘ │
│                                             │
│  ℹ️  Debés tener al menos un método         │
│     de pago activo.                         │
│                                             │
└─────────────────────────────────────────────┘
```

### Lógica del componente

```tsx
function MetodosPagoConfig({ empresa, tieneSubscripcion }) {
  const [aceptaEfectivo, setAceptaEfectivo] = useState(empresa.acepta_efectivo);
  const [aceptaTarjeta, setAceptaTarjeta] = useState(empresa.acepta_tarjeta);

  const handleToggle = async (campo: string, valor: boolean) => {
    // No permitir desactivar ambos
    if (!valor) {
      const otroActivo = campo === 'acepta_tarjeta' ? aceptaEfectivo : aceptaTarjeta;
      if (!otroActivo) {
        Alert.alert('Error', 'Debés tener al menos un método de pago activo');
        return;
      }
    }

    // Para efectivo, verificar suscripción (el back también valida)
    if (campo === 'acepta_efectivo' && valor && !tieneSubscripcion) {
      Alert.alert(
        'Suscripción requerida',
        'Necesitás una suscripción activa para aceptar pagos en efectivo.',
        [
          { text: 'Cancelar' },
          { text: 'Ver planes', onPress: () => navigation.navigate('Planes') },
        ]
      );
      return;
    }

    try {
      const res = await api.patch(
        `/api/empresas/${empresa.id}/metodos-pago/`,
        { [campo]: valor }
      );

      if (campo === 'acepta_efectivo') setAceptaEfectivo(valor);
      if (campo === 'acepta_tarjeta') setAceptaTarjeta(valor);
    } catch (err) {
      Alert.alert('Error', err.response?.data?.message || 'No se pudo actualizar');
    }
  };

  return (
    <View>
      {/* Tarjeta */}
      <Card>
        <Text style={styles.title}>Pago con tarjeta</Text>
        <Text style={styles.desc}>
          Tus clientes pagan con tarjeta via MercadoPago.
          Fixeo retiene un 10% de comisión por cada venta.
        </Text>
        <Switch
          value={aceptaTarjeta}
          onValueChange={(v) => handleToggle('acepta_tarjeta', v)}
        />
      </Card>

      {/* Efectivo */}
      <Card>
        <Text style={styles.title}>Pago en efectivo</Text>
        <Text style={styles.desc}>
          Tus clientes pagan en persona. Sin comisión por transacción.
        </Text>
        {!tieneSubscripcion && (
          <View style={styles.badge}>
            <Text style={styles.badgeText}>Requiere suscripción</Text>
          </View>
        )}
        <Switch
          value={aceptaEfectivo}
          onValueChange={(v) => handleToggle('acepta_efectivo', v)}
          disabled={!tieneSubscripcion}
          trackColor={{ false: '#ccc', true: '#4CAF50' }}
        />
      </Card>
    </View>
  );
}
```

---

## 3. Pantalla de checkout (comprador)

### Cómo obtener los métodos disponibles

Al cargar el checkout, ya tenés los datos de la empresa (del carrito).
Usá `metodos_pago_disponibles` para decidir qué mostrar.

```tsx
// Los datos de la empresa vienen del carrito
const empresa = carrito.empresa;

// Esto te dice qué puede usar el comprador REALMENTE
const metodos = empresa.metodos_pago_disponibles; // ["mercadopago", "efectivo"]
```

### Diseño del selector de método de pago

```
┌─────────────────────────────────────────────┐
│  ¿Cómo querés pagar?                       │
│                                             │
│  ┌────────────────────────────────────────┐ │
│  │  💳 Tarjeta de crédito/débito         │ │
│  │  Via MercadoPago                    ◉  │ │  ← seleccionable
│  └────────────────────────────────────────┘ │
│                                             │
│  ┌────────────────────────────────────────┐ │
│  │  💵 Efectivo                           │ │
│  │  Pagás al recibir          No disponible│ │  ← gris + badge
│  └────────────────────────────────────────┘ │
│                                             │
└─────────────────────────────────────────────┘
```

### Lógica del selector

```tsx
function SelectorMetodoPago({ empresa, onSelect, selected }) {
  const metodosDisponibles = empresa.metodos_pago_disponibles || [];

  const opciones = [
    {
      id: 'mercadopago',
      label: 'Tarjeta de crédito/débito',
      sublabel: 'Via MercadoPago',
      icon: '💳',
      disponible: metodosDisponibles.includes('mercadopago'),
    },
    {
      id: 'efectivo',
      label: 'Efectivo',
      sublabel: 'Pagás al recibir',
      icon: '💵',
      disponible: metodosDisponibles.includes('efectivo'),
      // Mostrar siempre si acepta_efectivo=true, aunque no esté disponible
      mostrar: empresa.acepta_efectivo,
    },
  ];

  return (
    <View>
      <Text style={styles.title}>¿Cómo querés pagar?</Text>
      {opciones
        .filter(o => o.disponible || o.mostrar)
        .map(opcion => (
          <TouchableOpacity
            key={opcion.id}
            style={[
              styles.opcion,
              selected === opcion.id && styles.opcionSelected,
              !opcion.disponible && styles.opcionDisabled,
            ]}
            onPress={() => opcion.disponible && onSelect(opcion.id)}
            disabled={!opcion.disponible}
          >
            <View style={styles.opcionContent}>
              <Text style={styles.icon}>{opcion.icon}</Text>
              <View>
                <Text style={[
                  styles.label,
                  !opcion.disponible && styles.labelDisabled
                ]}>
                  {opcion.label}
                </Text>
                <Text style={styles.sublabel}>{opcion.sublabel}</Text>
              </View>
            </View>

            {!opcion.disponible ? (
              <View style={styles.badge}>
                <Text style={styles.badgeText}>No disponible</Text>
              </View>
            ) : (
              <View style={[
                styles.radio,
                selected === opcion.id && styles.radioSelected
              ]} />
            )}
          </TouchableOpacity>
        ))}
    </View>
  );
}
```

### Hacer el checkout

```tsx
async function handleCheckout(carritoId, metodoPago, tipoEntrega) {
  const res = await api.post(`/api/carritos/${carritoId}/checkout/`, {
    metodo_pago: metodoPago,  // "mercadopago" o "efectivo"
    tipo_entrega: tipoEntrega,
  });

  const orden = res.data.data;

  if (metodoPago === 'mercadopago') {
    // Navegar al flujo de pago con tarjeta
    navigation.navigate('PagarOrden', {
      ordenId: orden.id,
      total: orden.total,
    });
  } else {
    // Efectivo: la orden ya está creada, mostrar confirmación
    navigation.navigate('OrdenConfirmada', { orden });
  }
}
```

### Errores que puede devolver el checkout

| Error | Causa | Acción en UI |
|---|---|---|
| `"Esta empresa no acepta pagos con tarjeta"` | `acepta_tarjeta=false` | No debería pasar si filtrás bien en el selector |
| `"Esta empresa no acepta pagos en efectivo"` | `acepta_efectivo=false` | Ídem |
| `"La empresa necesita una suscripción activa para aceptar efectivo"` | Venció la suscripción entre que cargó y pagó | Mostrar mensaje, volver al selector |

---

## 4. Resumen de flujos

### Vendedor configura métodos de pago

```
1. Vendedor va a Configuración → Métodos de pago
2. Ve dos switches: Tarjeta y Efectivo
3. Si quiere activar Efectivo y no tiene suscripción:
   → Se muestra aviso + link a planes
   → El switch queda deshabilitado (gris)
4. Si tiene suscripción, puede activar/desactivar ambos
5. PATCH /api/empresas/{id}/metodos-pago/
```

### Comprador hace checkout

```
1. Comprador llega al checkout
2. El frontend lee empresa.metodos_pago_disponibles
3. Muestra las opciones:
   - "mercadopago" → seleccionable si está en la lista
   - "efectivo" → seleccionable si está en la lista,
     gris con "No disponible" si no está
4. Comprador selecciona método y confirma
5. POST /api/carritos/{id}/checkout/ con metodo_pago
6. Si "mercadopago" → flujo de pago con tarjeta
   Si "efectivo" → orden confirmada directamente
```

---

## 5. Referencia de endpoints

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/api/empresas/{id}/` | Datos de empresa con `acepta_efectivo`, `acepta_tarjeta`, `efectivo_disponible`, `metodos_pago_disponibles` |
| PATCH | `/api/empresas/{id}/metodos-pago/` | Actualizar `acepta_efectivo` y/o `acepta_tarjeta` |
| POST | `/api/carritos/{id}/checkout/` | Checkout con `metodo_pago: "mercadopago"` o `"efectivo"` |

---

## 6. Reglas de negocio

1. **Tarjeta (MercadoPago)**: siempre disponible. No requiere suscripción. Fixeo cobra 10% de comisión.
2. **Efectivo**: requiere suscripción activa del vendedor. Sin comisión por transacción (el vendedor cobra directo).
3. **Al menos uno** debe estar activo. El frontend debe impedir desactivar el último activo.
4. **Valores por defecto**: ambos en `true` al crear la empresa. El efectivo no va a funcionar hasta que el vendedor tenga suscripción.
