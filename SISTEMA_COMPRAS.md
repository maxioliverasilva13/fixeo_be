# Sistema de Compras - Carritos y Órdenes

## Resumen de Cambios

Se ha implementado un sistema completo de compras con carritos y órdenes para empresas. Los usuarios pueden agregar productos a carritos, proceder a checkout y crear órdenes que pueden ser gestionadas por las empresas.

### Nuevas Entidades
- **Carrito**: Un usuario puede tener un carrito activo por empresa
- **CarritoItem**: Items dentro de cada carrito con cantidad y precio
- **Orden**: Órdenes de compra con estados y método de pago
- **OrdenItem**: Productos incluidos en cada orden

### Cambios en Entidades Existentes
- **Producto**: Nuevo campo `agotado` (boolean, default: false)
- Los productos agotados siempre se listan al final automáticamente

---

## Endpoints Disponibles

### 1. Productos

#### GET `/api/empresas/productos/`
Lista productos de empresas.

**Query params:**
- `empresa_id`: Filtrar por empresa
- `categoria_id`: Filtrar por categoría

**Respuesta:**
```json
{
  "ok": true,
  "message": "Operación exitosa",
  "data": [
    {
      "id": 1,
      "nombre": "Laptop HP",
      "descripcion": "Laptop HP Core i5",
      "precio": "850000.00",
      "codigo": "LAP-001",
      "agotado": false,
      "empresa": 1,
      "categoria": 1,
      "categoria_nombre": "Electrónica",
      "created_at": "2026-02-03T10:00:00Z",
      "updated_at": "2026-02-03T10:00:00Z"
    }
  ]
}
```

**Nota:** Los productos agotados (`agotado: true`) se listan automáticamente al final.

#### PATCH `/api/empresas/productos/{id}/`
Actualiza un producto (solo admin de la empresa).

**Body para marcar como agotado:**
```json
{
  "agotado": true
}
```

---

### 2. Carritos

#### GET `/api/carritos/`
Lista carritos activos del usuario.

**Respuesta:**
```json
{
  "ok": true,
  "message": "Operación exitosa",
  "data": [
    {
      "id": 1,
      "usuario": 39,
      "empresa": 1,
      "empresa_nombre": "Mi Tienda",
      "activo": true,
      "items": [
        {
          "id": 1,
          "producto": 5,
          "producto_nombre": "Laptop HP",
          "producto_precio": "850000.00",
          "producto_agotado": false,
          "cantidad": 2,
          "precio_unitario": "850000.00",
          "subtotal": "1700000.00"
        }
      ],
      "total": "1700000.00",
      "cantidad_items": 2,
      "created_at": "2026-02-03T10:00:00Z"
    }
  ]
}
```

#### GET `/api/carritos/empresa/{empresa_id}/`
Obtiene o crea el carrito activo para una empresa específica.

**Respuesta:** Igual que arriba, pero un solo carrito.

#### POST `/api/carritos/{carrito_id}/agregar-item/`
Agrega o actualiza un producto en el carrito.

**Body:**
```json
{
  "producto_id": 5,
  "cantidad": 2
}
```

**Respuesta:**
```json
{
  "ok": true,
  "message": "Operación exitosa",
  "data": {
    "id": 1,
    "producto": 5,
    "producto_nombre": "Laptop HP",
    "producto_precio": "850000.00",
    "producto_agotado": false,
    "cantidad": 2,
    "precio_unitario": "850000.00",
    "subtotal": "1700000.00"
  }
}
```

**Notas:**
- Si el producto ya existe en el carrito, suma la cantidad
- No permite agregar productos agotados
- El producto debe pertenecer a la misma empresa del carrito

#### POST `/api/carritos/{carrito_id}/actualizar-item/`
Actualiza la cantidad de un item del carrito.

**Body:**
```json
{
  "producto_id": 5,
  "cantidad": 3
}
```

**Notas:**
- Si `cantidad` es 0 o negativo, elimina el item

#### DELETE `/api/carritos/{carrito_id}/eliminar-item/{producto_id}/`
Elimina un producto específico del carrito.

**Respuesta:**
```json
{
  "ok": true,
  "message": "Item eliminado del carrito",
  "data": null
}
```

#### DELETE `/api/carritos/{carrito_id}/vaciar/`
Vacía el carrito eliminando todos los items.

**Respuesta:**
```json
{
  "ok": true,
  "message": "Carrito vaciado exitosamente",
  "data": null
}
```

#### POST `/api/carritos/{carrito_id}/checkout/`
**FLUJO PRINCIPAL: Crea una orden a partir del carrito**

**Body:**
```json
{
  "metodo_pago": "efectivo",
  "tipo_entrega": "domicilio",
  "notas": "Llamar al llegar"
}
```

**Opciones de `metodo_pago`:**
- `"efectivo"`
- `"tarjeta"`
- `"transferencia"`
- `"app"`

**Opciones de `tipo_entrega`:**
- `"retiro"` - Retiro en el local de la empresa (usa la localización de la empresa)
- `"domicilio"` - Envío a domicilio (usa la dirección principal del usuario)

**Lógica automática de direcciones:**
- Si `tipo_entrega` es `"retiro"`: El backend usa automáticamente la localización de la empresa
- Si `tipo_entrega` es `"domicilio"`: El backend usa automáticamente la dirección marcada como principal del usuario

**Validaciones:**
- Para `"retiro"`: La empresa debe tener una localización configurada
- Para `"domicilio"`: El usuario debe tener una dirección marcada como principal

**Respuesta:**
```json
{
  "ok": true,
  "message": "Recurso creado exitosamente",
  "data": {
    "id": 1,
    "numero_orden": "ORD-A1B2C3D4",
    "usuario": 39,
    "usuario_nombre": "Juan Pérez",
    "empresa": 1,
    "empresa_nombre": "Mi Tienda",
    "status": "en_proceso",
    "metodo_pago": "efectivo",
    "tipo_entrega": "domicilio",
    "localizacion_entrega": 5,
    "localizacion_info": {
      "address": "Calle 123, Barrio X",
      "city": "Buenos Aires",
      "country": "Argentina",
      "interior_door": "Apto 4B",
      "notas": "Portón negro"
    },
    "total": "1700000.00",
    "notas": "Llamar al llegar",
    "fecha_entrega": null,
    "items": [
      {
        "id": 1,
        "producto": 5,
        "producto_nombre": "Laptop HP",
        "producto_codigo": "LAP-001",
        "cantidad": 2,
        "precio_unitario": "850000.00",
        "subtotal": "1700000.00"
      }
    ],
    "created_at": "2026-02-03T10:30:00Z",
    "updated_at": "2026-02-03T10:30:00Z"
  }
}
```

**Notas:**
- Valida que no haya productos agotados antes de crear la orden
- El carrito se marca como inactivo (`activo: false`)
- Genera un número de orden único automáticamente
- Crea la orden en estado `"en_proceso"`
- Asigna automáticamente la localización según el tipo de entrega

---

### 3. Órdenes

#### GET `/api/ordenes/`
Lista las órdenes del usuario autenticado.

**Query params:**
- `status`: Filtrar por estado (`en_proceso`, `aceptada`, `entregada`, `finalizada`, `cancelada`)
- `empresa_id`: Filtrar por empresa

**Ejemplos:**
```
GET /api/ordenes/
GET /api/ordenes/?status=en_proceso
GET /api/ordenes/?status=aceptada&empresa_id=1
```

**Respuesta:**
```json
{
  "ok": true,
  "message": "Operación exitosa",
  "data": [
    {
      "id": 1,
      "numero_orden": "ORD-A1B2C3D4",
      "usuario": 39,
      "usuario_nombre": "Juan Pérez",
      "empresa": 1,
      "empresa_nombre": "Mi Tienda",
      "status": "aceptada",
      "metodo_pago": "efectivo",
      "tipo_entrega": "domicilio",
      "localizacion_entrega": 5,
      "localizacion_info": {
        "address": "Calle 123, Barrio X",
        "city": "Buenos Aires",
        "country": "Argentina",
        "interior_door": "Apto 4B",
        "notas": "Portón negro"
      },
      "total": "1700000.00",
      "notas": "Llamar al llegar",
      "fecha_entrega": "2026-02-04T15:00:00Z",
      "items": [...],
      "created_at": "2026-02-03T10:30:00Z",
      "updated_at": "2026-02-03T11:00:00Z"
    }
  ]
}
```

#### GET `/api/ordenes/{id}/`
Obtiene el detalle de una orden específica.

#### GET `/api/ordenes/mis-ordenes-empresa/`
**Para administradores de empresas:** Lista las órdenes recibidas en sus empresas.

**Query params:**
- `status`: Filtrar por estado

**Ejemplos:**
```
GET /api/ordenes/mis-ordenes-empresa/
GET /api/ordenes/mis-ordenes-empresa/?status=en_proceso
```

#### POST `/api/ordenes/{id}/cambiar-estado/`
**Solo para admin de la empresa:** Cambia el estado de una orden.

**Body:**
```json
{
  "status": "aceptada"
}
```

**Estados permitidos:**
- `"en_proceso"` - Estado inicial cuando se crea la orden
- `"aceptada"` - La empresa acepta la orden
- `"entregada"` - Orden entregada o retirada
- `"finalizada"` - Orden completada
- `"cancelada"` - Orden cancelada

**Respuesta:**
```json
{
  "ok": true,
  "message": "Operación exitosa",
  "data": {
    "id": 1,
    "numero_orden": "ORD-A1B2C3D4",
    "status": "aceptada",
    ...
  }
}
```

---

## Flujo Completo de Compra

### 1. Cliente navega productos
```
GET /api/empresas/productos/?empresa_id=1
```

### 2. Cliente obtiene/crea su carrito
```
GET /api/carritos/empresa/1/
```

### 3. Cliente agrega productos al carrito
```
POST /api/carritos/{carrito_id}/agregar-item/
{
  "producto_id": 5,
  "cantidad": 2
}
```

### 4. Cliente actualiza cantidades (opcional)
```
POST /api/carritos/{carrito_id}/actualizar-item/
{
  "producto_id": 5,
  "cantidad": 3
}
```

### 5. Cliente procede al checkout
```
POST /api/carritos/{carrito_id}/checkout/
{
  "metodo_pago": "efectivo",
  "tipo_entrega": "domicilio",
  "notas": "Llamar al llegar"
}
```

**Para retiro en local:**
```json
{
  "metodo_pago": "efectivo",
  "tipo_entrega": "retiro",
  "notas": "Retirar por la tarde"
}
```

### 6. Cliente consulta sus órdenes
```
GET /api/ordenes/?status=en_proceso
```

### 7. Empresa gestiona la orden
```
POST /api/ordenes/{orden_id}/cambiar-estado/
{
  "status": "aceptada"
}
```

### 8. Empresa marca como entregada
```
POST /api/ordenes/{orden_id}/cambiar-estado/
{
  "status": "entregada"
}
```

### 9. Orden se finaliza
```
POST /api/ordenes/{orden_id}/cambiar-estado/
{
  "status": "finalizada"
}
```

---

## Estados de Orden

| Estado | Descripción | Quién lo cambia |
|--------|-------------|-----------------|
| `en_proceso` | Orden creada, esperando aceptación | Sistema (al crear) |
| `aceptada` | Empresa aceptó la orden | Admin empresa |
| `entregada` | Producto entregado/retirado | Admin empresa |
| `finalizada` | Orden completada | Admin empresa |
| `cancelada` | Orden cancelada | Admin empresa |

---

## Sistema de Direcciones de Entrega

El sistema de órdenes usa **localizaciones existentes** en lugar de texto libre. El backend determina automáticamente qué dirección usar según el tipo de entrega.

### Tipos de Entrega

#### 1. Retiro en Local (`tipo_entrega: "retiro"`)
- Usa automáticamente la **localización de la empresa**
- La empresa debe tener configurada su localización
- El cliente retira el pedido en el local de la empresa

**Ejemplo:**
```json
{
  "metodo_pago": "efectivo",
  "tipo_entrega": "retiro",
  "notas": "Retirar por la tarde"
}
```

#### 2. Envío a Domicilio (`tipo_entrega: "domicilio"`)
- Usa automáticamente la **dirección principal del usuario**
- El usuario debe tener una dirección marcada como principal
- Se entrega en la dirección del cliente

**Ejemplo:**
```json
{
  "metodo_pago": "tarjeta",
  "tipo_entrega": "domicilio",
  "notas": "Llamar antes de llegar"
}
```

### Configuración Previa Requerida

**Para que funcione el checkout, asegúrate de:**

1. **Para retiro en local:**
   - La empresa debe tener una localización configurada en `empresas.localizacion`

2. **Para envío a domicilio:**
   - El usuario debe tener al menos una dirección registrada
   - Una de sus direcciones debe estar marcada como `es_principal = true` en `usuario_localizacion`

### Errores Posibles

```json
// Error si empresa no tiene localización y se selecciona "retiro"
{
  "ok": false,
  "message": "La empresa no tiene localización configurada para retiro",
  "data": null
}

// Error si usuario no tiene dirección principal y se selecciona "domicilio"
{
  "ok": false,
  "message": "No tienes una dirección principal configurada para envío a domicilio",
  "data": null
}
```

---

## Validaciones Importantes

- ✅ No se pueden agregar productos agotados al carrito
- ✅ No se puede hacer checkout con productos agotados
- ✅ Solo el admin de la empresa puede cambiar estados de órdenes
- ✅ Los productos deben pertenecer a la empresa del carrito
- ✅ Un usuario solo puede tener un carrito activo por empresa
- ✅ Los productos agotados se listan al final automáticamente

---

## Migraciones

Para aplicar los cambios en la base de datos:

```bash
docker-compose exec web python manage.py migrate
```
