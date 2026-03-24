# Guía Frontend — Integración MercadoPago en Fixeo

Esta guía cubre todo lo que el frontend (React / React Native) necesita
implementar para pagos con MercadoPago **sin salir de la app**.

---

## Índice

1. [Arquitectura general](#1-arquitectura-general)
2. [Instalación del SDK](#2-instalación-del-sdk)
3. [Inicialización](#3-inicialización)
4. [Gestión de tarjetas](#4-gestión-de-tarjetas)
5. [Flujo de pago inline](#5-flujo-de-pago-inline)
6. [Pagar con tarjeta nueva](#6-pagar-con-tarjeta-nueva)
7. [Pagar con tarjeta guardada](#7-pagar-con-tarjeta-guardada)
8. [Cuotas](#8-cuotas)
9. [Integración en checkout de orden](#9-integración-en-checkout-de-orden)
10. [Integración en creación de trabajo](#10-integración-en-creación-de-trabajo)
11. [Estados de pago y polling](#11-estados-de-pago-y-polling)
12. [Pantallas sugeridas](#12-pantallas-sugeridas)
13. [Referencia de endpoints](#13-referencia-de-endpoints)
14. [Testing con tarjetas de prueba](#14-testing-con-tarjetas-de-prueba)
15. [Errores comunes](#15-errores-comunes)

---

## 1. Arquitectura general

```
┌──────────────────────────┐
│      App React Native    │
│                          │
│  1. Formulario tarjeta   │
│  2. MercadoPago SDK      │
│     → genera card_token  │
│  3. Envía token al back  │
└───────────┬──────────────┘
            │ POST /api/pagos/pagar/
            ▼
┌──────────────────────────┐
│      Backend Django      │
│                          │
│  Recibe card_token       │
│  → sdk.payment().create  │
│  → Retorna status        │
└───────────┬──────────────┘
            │
            ▼
┌──────────────────────────┐
│     MercadoPago API      │
│  Procesa el cobro        │
│  Envía webhook           │
└──────────────────────────┘
```

El pago se procesa **en tiempo real**. No hay redirección.
El frontend recibe el resultado inmediatamente.

---

## 2. Instalación del SDK

### React Native (Expo o bare)

No existe SDK nativo oficial de MercadoPago para React Native.
Usamos un **WebView** con MercadoPago.js para tokenizar tarjetas, o
la API REST directamente con un formulario custom.

**Opción A — WebView con MercadoPago.js (recomendada)**

```bash
npm install react-native-webview
```

**Opción B — Formulario custom + API de tokenización**

No requiere dependencias extra. Se usa `fetch` directo contra la API de MP.

### React Web

```bash
npm install @mercadopago/sdk-react
```

---

## 3. Inicialización

### Obtener la public key

```
GET /api/pagos/public-key/
Authorization: Bearer <token>

Respuesta:
{
  "ok": true,
  "data": { "public_key": "TEST-xxxx-xxxx-xxxx" }
}
```

### React Web

```tsx
import { initMercadoPago } from "@mercadopago/sdk-react";

// Al montar la app o el módulo de pagos
const { data } = await api.get("/api/pagos/public-key/");
initMercadoPago(data.public_key, { locale: "es-AR" });
```

### React Native (WebView)

Crear un archivo HTML que se carga en el WebView:

```html
<!DOCTYPE html>
<html>
<head>
  <script src="https://sdk.mercadopago.com/js/v2"></script>
</head>
<body>
  <div id="cardForm"></div>
  <script>
    // La public_key se inyecta desde React Native via postMessage
    window.addEventListener("message", function(event) {
      const data = JSON.parse(event.data);

      if (data.action === "init") {
        const mp = new MercadoPago(data.publicKey, { locale: "es-AR" });
        window.mpInstance = mp;
        window.ReactNativeWebView.postMessage(JSON.stringify({ type: "ready" }));
      }

      if (data.action === "createToken") {
        window.mpInstance.createCardToken({
          cardNumber: data.cardNumber,
          cardholderName: data.cardholderName,
          cardExpirationMonth: data.expirationMonth,
          cardExpirationYear: data.expirationYear,
          securityCode: data.securityCode,
          identificationType: data.identificationType,
          identificationNumber: data.identificationNumber,
        }).then(function(result) {
          window.ReactNativeWebView.postMessage(JSON.stringify({
            type: "cardToken",
            token: result.id,
          }));
        }).catch(function(error) {
          window.ReactNativeWebView.postMessage(JSON.stringify({
            type: "error",
            error: error.message || JSON.stringify(error),
          }));
        });
      }
    });
  </script>
</body>
</html>
```

---

## 4. Gestión de tarjetas

### 4.1 Listar tarjetas guardadas

```
GET /api/pagos/tarjetas/
Authorization: Bearer <token>

Respuesta:
{
  "ok": true,
  "data": [
    {
      "id": 1,
      "mp_card_id": "123456789",
      "last_four": "4242",
      "brand": "Visa",
      "expiration_month": 12,
      "expiration_year": 2028,
      "payment_method_id": "visa",
      "issuer_id": "310"
    }
  ]
}
```

### 4.2 Guardar una tarjeta nueva

**Paso 1**: Tokenizar la tarjeta en el frontend con MercadoPago SDK.

```tsx
// React Web con @mercadopago/sdk-react
const cardToken = await mp.createCardToken({
  cardNumber: "4509953566233704",
  cardholderName: "APRO TEST",
  cardExpirationMonth: "12",
  cardExpirationYear: "2028",
  securityCode: "123",
  identificationType: "DNI",
  identificationNumber: "12345678",
});
```

Para React Native, usar el WebView (ver sección 3) y el message `createToken`.

**Paso 2**: Enviar el token al backend.

```
POST /api/pagos/tarjetas/guardar/
Authorization: Bearer <token>
Content-Type: application/json

{
  "card_token": "el_card_token_de_mp"
}

Respuesta:
{
  "ok": true,
  "data": {
    "id": 1,
    "mp_card_id": "123456789",
    "last_four": "4242",
    "brand": "Visa",
    "expiration_month": 12,
    "expiration_year": 2028,
    "payment_method_id": "visa",
    "issuer_id": "310"
  }
}
```

### 4.3 Eliminar una tarjeta

```
DELETE /api/pagos/tarjetas/{id}/
Authorization: Bearer <token>

Respuesta:
{
  "ok": true,
  "message": "Tarjeta eliminada"
}
```

---

## 5. Flujo de pago inline

El flujo completo para pagar sin salir de la app:

```
1. Usuario llega a pantalla de pago
2. Se muestran tarjetas guardadas + opción "Nueva tarjeta"
3. Usuario elige tarjeta o ingresa datos de nueva
4. Frontend tokeniza la tarjeta → obtiene card_token
5. Frontend llama POST /api/pagos/pagar/ con el token
6. Backend procesa con MercadoPago y responde el resultado
7. Frontend muestra resultado (aprobado / rechazado / pendiente)
```

---

## 6. Pagar con tarjeta nueva

### Paso 1: Tokenizar

Usando MercadoPago.js (en WebView o web):

```javascript
const cardTokenResult = await mp.createCardToken({
  cardNumber: "4509953566233704",
  cardholderName: "APRO TEST",
  cardExpirationMonth: "12",
  cardExpirationYear: "2028",
  securityCode: "123",
  identificationType: "DNI",
  identificationNumber: "12345678",
});

const cardToken = cardTokenResult.id;
```

### Paso 2: Enviar pago al backend

```
POST /api/pagos/pagar/
Authorization: Bearer <token>
Content-Type: application/json

{
  "card_token": "el_card_token",
  "payment_method_id": "visa",
  "issuer_id": "310",
  "installments": 1,
  "tipo": "orden",
  "orden_id": 42
}
```

**Campos:**

| Campo              | Tipo   | Requerido | Descripción                                    |
|--------------------|--------|-----------|------------------------------------------------|
| card_token         | string | sí        | Token generado por MercadoPago.js              |
| payment_method_id  | string | sí        | ID del medio de pago (visa, master, etc)       |
| issuer_id          | string | no        | ID del emisor de la tarjeta                    |
| installments       | int    | no        | Cantidad de cuotas (default: 1)                |
| tipo               | string | sí        | `"orden"` o `"trabajo"`                        |
| orden_id           | int    | si tipo=orden    | ID de la orden a pagar                  |
| trabajo_id         | int    | si tipo=trabajo  | ID del trabajo a pagar                  |

### Paso 3: Interpretar respuesta

```json
{
  "ok": true,
  "data": {
    "pago_id": 15,
    "status": "aprobado",
    "mp_status": "approved",
    "mp_status_detail": "accredited",
    "mp_payment_id": "123456789"
  }
}
```

**Posibles valores de `status`:**

| status      | Significado                        | Acción en UI                   |
|-------------|------------------------------------|--------------------------------|
| `aprobado`  | Pago procesado exitosamente        | Mostrar éxito, continuar flujo |
| `pendiente` | Esperando confirmación             | Mostrar "procesando"           |
| `en_proceso`| El pago se está verificando        | Mostrar "procesando"           |
| `rechazado` | Tarjeta rechazada                  | Mostrar error, reintentar      |

**Posibles `mp_status_detail` cuando es rechazado:**

| mp_status_detail          | Mensaje para el usuario                        |
|---------------------------|------------------------------------------------|
| `cc_rejected_call_for_authorize` | Llamá a tu banco para autorizar el pago   |
| `cc_rejected_insufficient_amount` | Fondos insuficientes                    |
| `cc_rejected_bad_filled_security_code` | Código de seguridad incorrecto    |
| `cc_rejected_bad_filled_date`    | Fecha de vencimiento incorrecta           |
| `cc_rejected_bad_filled_other`   | Revisá los datos de la tarjeta            |
| `cc_rejected_other_reason`       | No pudimos procesar tu pago               |

---

## 7. Pagar con tarjeta guardada

Para pagar con una tarjeta ya guardada, se necesita generar un nuevo `card_token`
usando el `mp_card_id` de la tarjeta guardada y el CVV.

### Paso 1: Tokenizar tarjeta guardada

```javascript
const cardTokenResult = await mp.createCardToken({
  cardId: tarjeta.mp_card_id,        // de GET /api/pagos/tarjetas/
  securityCode: "123",               // el usuario ingresa solo el CVV
});

const cardToken = cardTokenResult.id;
```

### Paso 2: Pagar (igual que con tarjeta nueva)

```
POST /api/pagos/pagar/
{
  "card_token": "el_nuevo_token",
  "payment_method_id": "visa",            // de la tarjeta guardada
  "issuer_id": "310",                     // de la tarjeta guardada
  "installments": 1,
  "tipo": "orden",
  "orden_id": 42
}
```

### Ejemplo componente React Native (simplificado)

```tsx
function PagarConTarjetaGuardada({ tarjeta, ordenId }) {
  const [cvv, setCvv] = useState("");
  const [loading, setLoading] = useState(false);

  const handlePagar = async () => {
    setLoading(true);

    // 1. Tokenizar con WebView o API
    const cardToken = await tokenizarTarjetaGuardada(
      tarjeta.mp_card_id,
      cvv,
    );

    // 2. Enviar al backend
    const response = await api.post("/api/pagos/pagar/", {
      card_token: cardToken,
      payment_method_id: tarjeta.payment_method_id,
      issuer_id: tarjeta.issuer_id,
      installments: 1,
      tipo: "orden",
      orden_id: ordenId,
    });

    setLoading(false);

    if (response.data.data.status === "aprobado") {
      // Éxito
    } else if (response.data.data.status === "rechazado") {
      // Mostrar error según mp_status_detail
    }
  };

  return (
    <View>
      <Text>**** {tarjeta.last_four} ({tarjeta.brand})</Text>
      <TextInput
        placeholder="CVV"
        secureTextEntry
        keyboardType="numeric"
        maxLength={4}
        value={cvv}
        onChangeText={setCvv}
      />
      <Button title="Pagar" onPress={handlePagar} loading={loading} />
    </View>
  );
}
```

---

## 8. Cuotas

### Consultar cuotas disponibles

```
GET /api/pagos/cuotas/?payment_method_id=visa&amount=5000&issuer_id=310
Authorization: Bearer <token>

Respuesta:
{
  "ok": true,
  "data": [
    {
      "payment_method_id": "visa",
      "payment_type_id": "credit_card",
      "issuer": { "id": "310", "name": "Banco Nación" },
      "payer_costs": [
        {
          "installments": 1,
          "installment_rate": 0,
          "recommended_message": "1 cuota de $5.000,00",
          "total_amount": 5000
        },
        {
          "installments": 3,
          "installment_rate": 15.5,
          "recommended_message": "3 cuotas de $1.925,83",
          "total_amount": 5775
        },
        {
          "installments": 6,
          "installment_rate": 28.0,
          "recommended_message": "6 cuotas de $1.066,67",
          "total_amount": 6400
        }
      ]
    }
  ]
}
```

### Mostrar selector de cuotas

```tsx
function SelectorCuotas({ paymentMethodId, amount, issuerId, onSelect }) {
  const [cuotas, setCuotas] = useState([]);

  useEffect(() => {
    api.get(`/api/pagos/cuotas/`, {
      params: { payment_method_id: paymentMethodId, amount, issuer_id: issuerId },
    }).then(res => {
      const payerCosts = res.data.data?.[0]?.payer_costs || [];
      setCuotas(payerCosts);
    });
  }, [paymentMethodId, amount, issuerId]);

  return (
    <View>
      {cuotas.map(c => (
        <TouchableOpacity key={c.installments} onPress={() => onSelect(c.installments)}>
          <Text>{c.recommended_message}</Text>
        </TouchableOpacity>
      ))}
    </View>
  );
}
```

---

## 9. Integración en checkout de orden

El checkout de órdenes con `mercadopago` es **atómico**: se cobra primero
y la orden solo se crea si el pago es exitoso. Si el pago falla, no queda
ninguna orden pendiente.

### Flujo

```
1. El usuario completa el carrito y elige "Pagar con tarjeta".
2. El frontend tokeniza la tarjeta (cardForm / createCardToken).
3. POST /api/carritos/{id}/checkout/
   body: {
     metodo_pago: "mercadopago",
     tipo_entrega: "retiro" | "domicilio",
     card_token: "...",             // obligatorio
     payment_method_id: "visa",     // opcional (recomendado)
     issuer_id: "310",              // opcional
     installments: 1                // opcional, default 1
   }
   → Si el pago es EXITOSO: crea la orden + registra el pago.
     Respuesta: la orden completa con pago_info.
   → Si el pago FALLA: retorna error 400, NO se crea orden.
4. Mostrar resultado al usuario.
```

### Diferencia con el flujo anterior

| Antes (2 pasos)                     | Ahora (1 paso atómico)              |
|--------------------------------------|---------------------------------------|
| `POST checkout/` → crea orden       | `POST checkout/` con `card_token`     |
| `POST /api/pagos/pagar/` → cobra    | → cobra + crea orden en una sola call |
| Si pago falla → orden huérfana      | Si pago falla → no se crea orden      |

### Ejemplo

```tsx
async function handleCheckout(carritoId, tipoEntrega) {
  // 1. Tokenizar la tarjeta (ya lo tenés de pasos anteriores)
  const cardToken = await getCardToken(); // desde cardForm o createCardToken
  const paymentMethodId = getPaymentMethodId(); // desde mp.getPaymentMethods({ bin })

  // 2. Checkout atómico: paga + crea orden
  try {
    const res = await api.post(`/api/carritos/${carritoId}/checkout/`, {
      metodo_pago: "mercadopago",
      tipo_entrega: tipoEntrega,
      card_token: cardToken,
      payment_method_id: paymentMethodId, // recomendado
      installments: 1,
    });

    const orden = res.data.data;

    // Pago aprobado, orden creada
    navigation.navigate("OrdenExitosa", {
      ordenId: orden.id,
      numeroOrden: orden.numero_orden,
    });
  } catch (error) {
    // Pago rechazado — no se creó orden
    const msg = error.response?.data?.error || "Error procesando el pago";
    Alert.alert("Pago rechazado", msg);
  }
}
```

### Para pagos en efectivo

Si `metodo_pago` es `"efectivo"`, el checkout funciona igual que antes
(no se necesita `card_token`):

```tsx
await api.post(`/api/carritos/${carritoId}/checkout/`, {
  metodo_pago: "efectivo",
  tipo_entrega: "retiro",
});
```

> **Nota**: el endpoint `/api/pagos/pagar/` sigue disponible para pagos
> de **trabajos**, que tienen un ciclo de vida diferente (el trabajo se
> crea primero y se paga después).

---

## 10. Integración en creación de trabajo

Cuando el usuario crea un trabajo con método de pago `mercadopago`:

### Flujo

```
1. POST /api/trabajos/
   body: { ..., metodo_pago: "mercadopago" }
   → Crea el trabajo. Si metodo_pago=mercadopago, la respuesta
     incluye datos de MercadoPago.
   → Guardá el trabajo_id y precio_final.

2. Mostrar pantalla de pago.

3. Tokenizar tarjeta → POST /api/pagos/pagar/
   body: { card_token, payment_method_id, tipo: "trabajo", trabajo_id }

4. Mostrar resultado.
```

### Ejemplo

```tsx
async function handleCrearTrabajo(trabajoData) {
  const res = await api.post("/api/trabajos/", {
    ...trabajoData,
    metodo_pago: "mercadopago",
  });

  const trabajo = res.data.data;

  // Navegar a pago
  navigation.navigate("PagarTrabajo", {
    trabajoId: trabajo.id,
    total: trabajo.precio_final,
  });
}
```

---

## 11. Estados de pago y polling

Algunos pagos quedan en `pendiente` o `en_proceso`. Para esos casos,
hacé polling del estado:

```tsx
function usePagoStatus(pagoId) {
  const [pago, setPago] = useState(null);

  useEffect(() => {
    if (!pagoId) return;

    const interval = setInterval(async () => {
      const res = await api.get(`/api/pagos/${pagoId}/`);
      const p = res.data.data;
      setPago(p);

      if (["aprobado", "rechazado", "devuelto", "liberado"].includes(p.status)) {
        clearInterval(interval);
      }
    }, 3000); // cada 3 segundos

    return () => clearInterval(interval);
  }, [pagoId]);

  return pago;
}
```

---

## 12. Pantallas sugeridas

### 12.1 Mis Tarjetas (`/perfil/tarjetas`)

```
┌─────────────────────────────┐
│  Mis tarjetas               │
│                             │
│  ┌────────────────────────┐ │
│  │ VISA **** 4242         │ │
│  │ Vence 12/28      [🗑️] │ │
│  └────────────────────────┘ │
│                             │
│  ┌────────────────────────┐ │
│  │ MASTER **** 8890       │ │
│  │ Vence 06/27      [🗑️] │ │
│  └────────────────────────┘ │
│                             │
│  [+ Agregar tarjeta]        │
│                             │
└─────────────────────────────┘
```

### 12.2 Agregar tarjeta

```
┌─────────────────────────────┐
│  Agregar tarjeta            │
│                             │
│  Número de tarjeta          │
│  ┌────────────────────────┐ │
│  │ 4509 9535 6623 3704    │ │
│  └────────────────────────┘ │
│                             │
│  Nombre del titular         │
│  ┌────────────────────────┐ │
│  │ JUAN PEREZ              │ │
│  └────────────────────────┘ │
│                             │
│  Vencimiento      CVV       │
│  ┌──────────┐ ┌──────────┐ │
│  │ 12/28    │ │ 123      │ │
│  └──────────┘ └──────────┘ │
│                             │
│  Tipo doc.    Nro doc.      │
│  ┌──────────┐ ┌──────────┐ │
│  │ DNI    ▼ │ │ 12345678 │ │
│  └──────────┘ └──────────┘ │
│                             │
│  [Guardar tarjeta]          │
│                             │
└─────────────────────────────┘
```

### 12.3 Pantalla de pago (checkout)

```
┌─────────────────────────────┐
│  Pagar orden #ORD-A1B2      │
│  Total: $5.000,00           │
│                             │
│  Seleccioná tu tarjeta      │
│                             │
│  ○ VISA **** 4242           │
│  ○ MASTER **** 8890         │
│  ○ Nueva tarjeta            │
│                             │
│  ┌────────────────────────┐ │
│  │ CVV: [___]             │ │
│  └────────────────────────┘ │
│                             │
│  Cuotas                     │
│  ┌────────────────────────┐ │
│  │ 1 cuota de $5.000   ▼  │ │
│  └────────────────────────┘ │
│                             │
│  [Confirmar pago $5.000]    │
│                             │
└─────────────────────────────┘
```

### 12.4 Resultado de pago

```
Éxito:
┌─────────────────────────────┐
│         ✓                   │
│  Pago aprobado              │
│  $5.000,00                  │
│                             │
│  Tu orden está confirmada   │
│                             │
│  [Ver orden]                │
└─────────────────────────────┘

Rechazo:
┌─────────────────────────────┐
│         ✗                   │
│  Pago rechazado             │
│                             │
│  Fondos insuficientes.      │
│  Intentá con otra tarjeta.  │
│                             │
│  [Reintentar]               │
└─────────────────────────────┘
```

---

## 13. Referencia de endpoints

Todos los endpoints usan `Authorization: Bearer <jwt_token>` excepto el webhook.

### Tarjetas

| Método | Endpoint                         | Descripción                   |
|--------|----------------------------------|-------------------------------|
| GET    | `/api/pagos/tarjetas/`           | Listar tarjetas del usuario   |
| POST   | `/api/pagos/tarjetas/guardar/`   | Guardar tarjeta (card_token)  |
| DELETE | `/api/pagos/tarjetas/{id}/`      | Eliminar tarjeta              |

### Pagos

| Método | Endpoint                          | Descripción                            |
|--------|-----------------------------------|----------------------------------------|
| POST   | `/api/pagos/pagar/`               | Pago directo con card_token (inline)   |
| GET    | `/api/pagos/`                     | Listar pagos del usuario               |
| GET    | `/api/pagos/{id}/`                | Detalle de un pago                     |
| GET    | `/api/pagos/por-orden/{id}/`      | Pagos de una orden                     |
| GET    | `/api/pagos/por-trabajo/{id}/`    | Pagos de un trabajo                    |
| POST   | `/api/pagos/{id}/reembolsar/`     | Solicitar reembolso                    |

### Utilidades

| Método | Endpoint                          | Descripción                            |
|--------|-----------------------------------|----------------------------------------|
| GET    | `/api/pagos/public-key/`          | Public key de MP para el SDK frontend  |
| GET    | `/api/pagos/medios-de-pago/`      | Medios de pago disponibles en MP       |
| GET    | `/api/pagos/cuotas/?payment_method_id=visa&amount=5000` | Cuotas disponibles |

### Preferencias (alternativa con redirección)

| Método | Endpoint                                    | Descripción                    |
|--------|---------------------------------------------|--------------------------------|
| POST   | `/api/pagos/crear-preferencia-orden/`       | Crear preferencia para orden   |
| POST   | `/api/pagos/crear-preferencia-trabajo/`     | Crear preferencia para trabajo |

---

## 14. Testing con tarjetas de prueba

Usá estas tarjetas en entorno **sandbox** (con access token de TEST):

### Tarjetas que aprueban

| Marca       | Número           | CVV | Vencimiento | Titular    |
|-------------|------------------|-----|-------------|------------|
| Visa        | 4509953566233704 | 123 | 11/25       | APRO       |
| Mastercard  | 5031755734530604 | 123 | 11/25       | APRO       |
| Amex        | 3711803254580685 | 1234| 11/25       | APRO       |

### Tarjetas que rechazan

| Nombre titular | Resultado                    |
|----------------|------------------------------|
| OTHE           | Rechazado - otro motivo      |
| CALL           | Rechazado - llamar banco     |
| FUND           | Rechazado - fondos insuf.    |
| SECU           | Rechazado - código seguridad |
| EXPI           | Rechazado - fecha vencimiento|
| FORM           | Rechazado - error formulario |

### Documento para testing

- Tipo: `DNI`
- Número: `12345678`

---

## 15. Errores comunes

### "card_token is required"
No se envió el `card_token` en el body. Asegurate de tokenizar
la tarjeta primero con MercadoPago.js.

### "invalid card_token"
El token ya fue usado o expiró. Los tokens de MercadoPago son de
**un solo uso** y vencen a los 7 días. Hay que generar uno nuevo
para cada pago.

### "cc_rejected_insufficient_amount"
La tarjeta de prueba fue configurada para rechazar. Usá el titular
`APRO` para aprobar.

### "payment_method_id is not valid"
El `payment_method_id` no corresponde con la tarjeta. Usá `visa` para
Visa, `master` para Mastercard, `amex` para American Express.

### La tarjeta guardada no genera token
Al tokenizar una tarjeta guardada, se necesita el `cardId` (que es
el `mp_card_id` del backend) y el `securityCode` (CVV).
No se necesitan los demás datos.

---

## Ejemplo completo: Hook `useMercadoPago` para React Native

```tsx
import { useRef, useState, useCallback } from "react";
import { WebView } from "react-native-webview";

const MP_HTML = `
<!DOCTYPE html>
<html>
<head><script src="https://sdk.mercadopago.com/js/v2"></script></head>
<body>
<script>
  let mp;
  window.addEventListener("message", function(e) {
    const data = JSON.parse(e.data);

    if (data.action === "init") {
      mp = new MercadoPago(data.publicKey, { locale: "es-AR" });
      window.ReactNativeWebView.postMessage(JSON.stringify({ type: "ready" }));
    }

    if (data.action === "createCardToken") {
      mp.createCardToken(data.cardData).then(function(r) {
        window.ReactNativeWebView.postMessage(JSON.stringify({
          type: "cardToken", token: r.id
        }));
      }).catch(function(err) {
        window.ReactNativeWebView.postMessage(JSON.stringify({
          type: "error", error: err.message || JSON.stringify(err)
        }));
      });
    }
  });
</script>
</body>
</html>
`;

export function useMercadoPago(publicKey) {
  const webviewRef = useRef(null);
  const [ready, setReady] = useState(false);
  const resolveRef = useRef(null);

  const onMessage = useCallback((event) => {
    const data = JSON.parse(event.nativeEvent.data);

    if (data.type === "ready") {
      setReady(true);
    }

    if (data.type === "cardToken" && resolveRef.current) {
      resolveRef.current.resolve(data.token);
      resolveRef.current = null;
    }

    if (data.type === "error" && resolveRef.current) {
      resolveRef.current.reject(new Error(data.error));
      resolveRef.current = null;
    }
  }, []);

  const initWebView = useCallback(() => {
    webviewRef.current?.postMessage(JSON.stringify({
      action: "init",
      publicKey,
    }));
  }, [publicKey]);

  const createCardToken = useCallback((cardData) => {
    return new Promise((resolve, reject) => {
      resolveRef.current = { resolve, reject };
      webviewRef.current?.postMessage(JSON.stringify({
        action: "createCardToken",
        cardData,
      }));
    });
  }, []);

  const HiddenWebView = () => (
    <WebView
      ref={webviewRef}
      source={{ html: MP_HTML }}
      onMessage={onMessage}
      onLoad={initWebView}
      style={{ height: 0, width: 0, opacity: 0 }}
      javaScriptEnabled
    />
  );

  return { ready, createCardToken, HiddenWebView };
}
```

### Uso del hook

```tsx
function PantallaPago({ ordenId, total }) {
  const { ready, createCardToken, HiddenWebView } = useMercadoPago(MP_PUBLIC_KEY);
  const [tarjetas, setTarjetas] = useState([]);
  const [selectedCard, setSelectedCard] = useState(null);
  const [cvv, setCvv] = useState("");

  useEffect(() => {
    api.get("/api/pagos/tarjetas/").then(r => setTarjetas(r.data.data));
  }, []);

  const handlePagar = async () => {
    let token;

    if (selectedCard) {
      // Tarjeta guardada: solo necesita cardId + CVV
      token = await createCardToken({
        cardId: selectedCard.mp_card_id,
        securityCode: cvv,
      });
    } else {
      // Tarjeta nueva: necesita todos los datos
      token = await createCardToken({
        cardNumber: "...",
        cardholderName: "...",
        cardExpirationMonth: "...",
        cardExpirationYear: "...",
        securityCode: "...",
        identificationType: "DNI",
        identificationNumber: "...",
      });
    }

    const res = await api.post("/api/pagos/pagar/", {
      card_token: token,
      payment_method_id: selectedCard?.payment_method_id || "visa",
      issuer_id: selectedCard?.issuer_id || "",
      installments: 1,
      tipo: "orden",
      orden_id: ordenId,
    });

    const resultado = res.data.data;
    // Manejar resultado...
  };

  return (
    <View>
      <HiddenWebView />
      {/* UI de selección de tarjeta, CVV, botón pagar */}
    </View>
  );
}
```
