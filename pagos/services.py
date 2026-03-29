import logging
import uuid
from decimal import Decimal, ROUND_HALF_UP

import mercadopago
import requests as req
from django.conf import settings
from django.utils import timezone

from .models import MercadoPagoCustomer, Pago, Tarjeta

logger = logging.getLogger(__name__)

# Status mapping: Orders API order-level status → internal status
ORDERS_STATUS_MAP = {
    'processed': 'aprobado',
    'processing': 'en_proceso',
    'action_required': 'pendiente',
    'created': 'pendiente',
    'cancelled': 'cancelado',
    'refunded': 'devuelto',
    'charged_back': 'devuelto',
    'expired': 'cancelado',
    'failed': 'rechazado',
}

# Keep the old map for backward compatibility with existing Pago records
MP_STATUS_MAP = {
    'approved': 'aprobado',
    'pending': 'pendiente',
    'in_process': 'en_proceso',
    'rejected': 'rechazado',
    'refunded': 'devuelto',
    'cancelled': 'cancelado',
    'charged_back': 'devuelto',
}


def get_sdk():
    return mercadopago.SDK(settings.MP_ACCESS_TOKEN)


def _is_test_mode() -> bool:
    return getattr(settings, 'MP_TEST_MODE', False)


def _mp_headers(idempotency_key: str = '') -> dict:
    return {
        "Authorization": f"Bearer {settings.MP_ACCESS_TOKEN}",
        "Content-Type": "application/json",
        "X-Idempotency-Key": idempotency_key or str(uuid.uuid4()),
    }


def calcular_comision(monto: Decimal) -> tuple[Decimal, Decimal]:
    """Retorna (comision_plataforma, monto_vendedor)."""
    porcentaje = Decimal(str(settings.PLATFORM_COMMISSION_PERCENT)) / Decimal('100')
    comision = (monto * porcentaje).quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)
    vendedor = monto - comision
    return comision, vendedor


def crear_preferencia_orden(orden, request=None):
    """Crea una preferencia de MercadoPago para una orden de productos."""
    sdk = get_sdk()
    comision, monto_vendedor = calcular_comision(orden.total)

    items = []
    for item in orden.items.select_related('producto').all():
        items.append({
            "title": item.producto.nombre,
            "quantity": item.cantidad,
            "unit_price": float(item.precio_unitario),
            "currency_id": "UYU",
        })

    base_url = settings.MP_WEBHOOK_BASE_URL
    preference_data = {
        "items": items,
        "payer": {
            "email": orden.usuario.correo,
        },
        "back_urls": {
            "success": f"{settings.FRONTEND_URL}/pagos/exito",
            "failure": f"{settings.FRONTEND_URL}/pagos/error",
            "pending": f"{settings.FRONTEND_URL}/pagos/pendiente",
        },
        "notification_url": f"{base_url}/api/pagos/webhook/",
        "external_reference": f"orden_{orden.id}",
        "auto_return": "approved",
        "marketplace_fee": float(comision),
        "statement_descriptor": "FIXEO",
    }

    result = sdk.preference().create(preference_data)
    response = result.get("response", {})

    if result.get("status") not in (200, 201):
        logger.error("MP preference creation failed: %s", result)
        raise Exception(f"Error al crear preferencia MP: {result}")

    pago = Pago.objects.create(
        tipo='orden',
        orden=orden,
        usuario=orden.usuario,
        monto=orden.total,
        comision_plataforma=comision,
        monto_vendedor=monto_vendedor,
        mp_preference_id=response.get("id", ""),
        status='pendiente',
    )

    return {
        "preference_id": response.get("id"),
        "init_point": response.get("init_point"),
        "sandbox_init_point": response.get("sandbox_init_point"),
        "pago_id": pago.id,
    }


def crear_preferencia_trabajo(trabajo, request=None):
    """Crea una preferencia de MercadoPago para un trabajo/servicio."""
    sdk = get_sdk()
    monto = trabajo.precio_final
    comision, monto_vendedor = calcular_comision(monto)

    servicios = trabajo.trabajo_servicios.select_related('servicio').all()
    items = []
    for ts in servicios:
        items.append({
            "title": ts.servicio.nombre,
            "quantity": 1,
            "unit_price": float(ts.precio),
            "currency_id": "UYU",
        })

    if not items:
        items.append({
            "title": f"Trabajo #{trabajo.id}",
            "quantity": 1,
            "unit_price": float(monto),
            "currency_id": "UYU",
        })

    base_url = settings.MP_WEBHOOK_BASE_URL
    preference_data = {
        "items": items,
        "payer": {
            "email": trabajo.usuario.correo,
        },
        "back_urls": {
            "success": f"{settings.FRONTEND_URL}/pagos/exito",
            "failure": f"{settings.FRONTEND_URL}/pagos/error",
            "pending": f"{settings.FRONTEND_URL}/pagos/pendiente",
        },
        "notification_url": f"{base_url}/api/pagos/webhook/",
        "external_reference": f"trabajo_{trabajo.id}",
        "auto_return": "approved",
        "marketplace_fee": float(comision),
        "statement_descriptor": "FIXEO",
    }

    result = sdk.preference().create(preference_data)
    response = result.get("response", {})

    if result.get("status") not in (200, 201):
        logger.error("MP preference creation failed: %s", result)
        raise Exception(f"Error al crear preferencia MP: {result}")

    pago = Pago.objects.create(
        tipo='trabajo',
        trabajo=trabajo,
        usuario=trabajo.usuario,
        monto=monto,
        comision_plataforma=comision,
        monto_vendedor=monto_vendedor,
        mp_preference_id=response.get("id", ""),
        status='pendiente',
    )

    return {
        "preference_id": response.get("id"),
        "init_point": response.get("init_point"),
        "sandbox_init_point": response.get("sandbox_init_point"),
        "pago_id": pago.id,
    }


# ---------------------------------------------------------------------------
# Webhook processing (Orders API)
# ---------------------------------------------------------------------------

def procesar_webhook(data: dict):
    """
    Procesa un webhook de MercadoPago.
    Soporta tanto el nuevo tipo "order" (Orders API) como el legacy "payment".
    """
    topic = data.get("type") or data.get("topic")
    mp_data = data.get("data", {})
    resource_id = str(mp_data.get("id", ""))

    if topic == "order":
        return _procesar_webhook_order(resource_id)
    elif topic == "payment":
        return _procesar_webhook_payment_legacy(resource_id)
    else:
        logger.info("Webhook ignorado: topic=%s", topic)
        return None


def _procesar_webhook_order(order_id: str):
    """Procesa webhook de tipo 'order' (Orders API)."""
    if not order_id:
        logger.warning("Webhook order sin order_id")
        return None

    order_data = _get_order(order_id)
    if not order_data:
        return None

    order_status = order_data.get("status", "")
    order_status_detail = order_data.get("status_detail", "")
    external_reference = order_data.get("external_reference", "")

    payments = order_data.get("transactions", {}).get("payments", [])
    mp_payment_id = ""
    if payments:
        mp_payment_id = str(payments[0].get("id", ""))

    pago = _buscar_pago(external_reference, mp_order_id=order_id, mp_payment_id=mp_payment_id)
    if not pago:
        logger.warning(
            "No se encontró Pago para order_id=%s ref=%s", order_id, external_reference
        )
        return None

    nuevo_status = ORDERS_STATUS_MAP.get(order_status, 'pendiente')

    if pago.status == 'liberado':
        pago.mp_order_id = order_id
        pago.mp_payment_id = mp_payment_id or pago.mp_payment_id
        pago.mp_status = order_status
        pago.mp_status_detail = order_status_detail
        pago.save(update_fields=[
            'mp_order_id', 'mp_payment_id', 'mp_status', 'mp_status_detail', 'updated_at'
        ])
        return pago

    pago.mp_order_id = order_id
    pago.mp_payment_id = mp_payment_id or pago.mp_payment_id
    pago.mp_status = order_status
    pago.mp_status_detail = order_status_detail
    pago.status = nuevo_status
    pago.save(update_fields=[
        'mp_order_id', 'mp_payment_id', 'mp_status', 'mp_status_detail', 'status', 'updated_at'
    ])

    if nuevo_status == 'aprobado':
        _actualizar_entidad_pago_aprobado(pago)

    return pago


def _procesar_webhook_payment_legacy(payment_id: str):
    """Procesa webhook legacy de tipo 'payment' (Payments API)."""
    if not payment_id:
        logger.info("Webhook payment sin payment_id")
        return None

    sdk = get_sdk()
    result = sdk.payment().get(payment_id)

    if result.get("status") != 200:
        logger.error("Error consultando pago MP %s: %s", payment_id, result)
        return None

    payment_info = result["response"]
    mp_status = payment_info.get("status", "")
    mp_status_detail = payment_info.get("status_detail", "")
    external_reference = payment_info.get("external_reference", "")

    pago = _buscar_pago(external_reference, mp_payment_id=payment_id)
    if not pago:
        logger.warning("No se encontró Pago para payment_id=%s ref=%s", payment_id, external_reference)
        return None

    nuevo_status = MP_STATUS_MAP.get(mp_status, 'pendiente')

    if pago.status == 'liberado':
        pago.mp_payment_id = payment_id
        pago.mp_status = mp_status
        pago.mp_status_detail = mp_status_detail
        pago.save(update_fields=['mp_payment_id', 'mp_status', 'mp_status_detail', 'updated_at'])
        return pago

    pago.mp_payment_id = payment_id
    pago.mp_status = mp_status
    pago.mp_status_detail = mp_status_detail
    pago.status = nuevo_status
    pago.save(update_fields=[
        'mp_payment_id', 'mp_status', 'mp_status_detail', 'status', 'updated_at'
    ])

    if nuevo_status == 'aprobado':
        _actualizar_entidad_pago_aprobado(pago)

    return pago


def _get_order(order_id: str) -> dict:
    """Consulta GET /v1/orders/{order_id} para obtener detalles."""
    try:
        resp = req.get(
            f"https://api.mercadopago.com/v1/orders/{order_id}",
            headers={"Authorization": f"Bearer {settings.MP_ACCESS_TOKEN}"},
            timeout=15,
        )
        if resp.status_code == 200:
            return resp.json()
        logger.error("GET /v1/orders/%s failed: %s %s", order_id, resp.status_code, resp.text[:300])
    except Exception as e:
        logger.error("Error consultando order %s: %s", order_id, e)
    return {}


def _buscar_pago(external_reference: str, mp_order_id: str = '',
                 mp_payment_id: str = ''):
    """Busca un registro Pago por external_reference o IDs de MP."""
    pago = None
    if external_reference.startswith("orden_"):
        orden_id = external_reference.replace("orden_", "")
        pago = Pago.objects.filter(orden_id=orden_id, tipo='orden').order_by('-created_at').first()
    elif external_reference.startswith("trabajo_"):
        trabajo_id = external_reference.replace("trabajo_", "")
        pago = Pago.objects.filter(trabajo_id=trabajo_id, tipo='trabajo').order_by('-created_at').first()
    elif external_reference.startswith("carrito_"):
        carrito_id = external_reference.replace("carrito_", "")
        pago = Pago.objects.filter(
            orden__isnull=False, tipo='orden'
        ).order_by('-created_at').first()

    if not pago and mp_order_id:
        pago = Pago.objects.filter(mp_order_id=mp_order_id).first()

    if not pago and mp_payment_id:
        pago = Pago.objects.filter(mp_payment_id=mp_payment_id).first()

    return pago


def _actualizar_entidad_pago_aprobado(pago):
    """Actualiza la entidad (orden/trabajo) cuando el pago se aprueba."""
    if pago.tipo == 'orden' and pago.orden:
        orden = pago.orden
        if orden.status == 'en_proceso':
            orden.status = 'aceptada'
            orden.save(update_fields=['status', 'updated_at'])


def _obtener_empresa_de_pago(pago):
    """Obtiene la empresa asociada al pago (vía orden o trabajo)."""
    try:
        if pago.tipo == 'orden' and pago.orden:
            # Orden tiene FK directo a empresa
            return pago.orden.empresa
        elif pago.tipo == 'trabajo' and pago.trabajo:
            # El profesional (vendedor) del trabajo administra la empresa
            profesional = pago.trabajo.profesional
            if profesional:
                return profesional.empresas_administradas.first()
    except Exception as e:
        logger.warning("No se pudo obtener empresa del pago %s: %s", pago.id, e)
    return None


def transferir_al_vendedor(empresa, monto_vendedor: Decimal) -> bool:
    """
    Transfiere monto_vendedor a la cuenta MP del vendedor.
    Requiere que la empresa tenga mp_access_token y mp_user_id configurados.
    NOTA: Requiere cuenta Marketplace aprobada por Mercado Pago.
    """
    if not empresa or not empresa.mp_user_id:
        logger.info("Empresa sin MP vinculado — sin transferencia automática")
        return False

    try:
        headers = {
            "Authorization": f"Bearer {settings.MP_ACCESS_TOKEN}",
            "Content-Type": "application/json",
            "X-Idempotency-Key": str(uuid.uuid4()),
        }
        payload = {
            "amount": float(monto_vendedor),
            "receiver_id": int(empresa.mp_user_id),
            "money_release_days": 0,
        }
        resp = req.post(
            "https://api.mercadopago.com/v1/account/bank_transfers",
            json=payload,
            headers=headers,
            timeout=15,
        )
        if resp.status_code in (200, 201):
            logger.info(
                "Transferencia exitosa a empresa_id=%s mp_user_id=%s monto=%s",
                empresa.id, empresa.mp_user_id, monto_vendedor,
            )
            return True
        else:
            logger.error(
                "Error en transferencia MP a empresa_id=%s: %s %s",
                empresa.id, resp.status_code, resp.text[:300],
            )
    except Exception as e:
        logger.error("Excepción en transferencia MP empresa_id=%s: %s", empresa.id, e)

    return False


def liberar_pago(pago):
    """
    Marca un pago como liberado y transfiere el monto al vendedor si tiene MP vinculado.
    """
    if pago.status != 'aprobado':
        return False

    pago.status = 'liberado'
    pago.liberado_at = timezone.now()
    pago.save(update_fields=['status', 'liberado_at', 'updated_at'])

    empresa = _obtener_empresa_de_pago(pago)
    if empresa and empresa.is_mercadopago_vinculado and empresa.mp_user_id:
        transferir_al_vendedor(empresa, pago.monto_vendedor)

    return True


def liberar_pagos_entidad(tipo: str, entidad_id: int):
    """Libera todos los pagos aprobados de una entidad (orden o trabajo)."""
    filtro = {'tipo': tipo, 'status': 'aprobado'}
    if tipo == 'orden':
        filtro['orden_id'] = entidad_id
    elif tipo == 'trabajo':
        filtro['trabajo_id'] = entidad_id

    pagos = Pago.objects.filter(**filtro)\
        .select_related('orden__empresa', 'trabajo__profesional')\
        .prefetch_related('trabajo__profesional__empresas_administradas')
    liberados = 0
    for pago in pagos:
        if liberar_pago(pago):
            liberados += 1
    return liberados


def reembolsar_pago(pago):
    """Solicita un reembolso en MercadoPago."""
    if not pago.mp_payment_id:
        return False

    sdk = get_sdk()
    result = sdk.refund().create(pago.mp_payment_id)

    if result.get("status") in (200, 201):
        pago.status = 'devuelto'
        pago.mp_status = 'refunded'
        pago.save(update_fields=['status', 'mp_status', 'updated_at'])
        return True

    logger.error("Error al reembolsar pago %s: %s", pago.id, result)
    return False


# ---------------------------------------------------------------------------
# Customer & Tarjetas
# ---------------------------------------------------------------------------

def obtener_o_crear_customer(usuario):
    """Obtiene o crea un Customer de MercadoPago para el usuario."""
    try:
        mp_customer = MercadoPagoCustomer.objects.get(usuario=usuario)
        return mp_customer
    except MercadoPagoCustomer.DoesNotExist:
        pass

    sdk = get_sdk()
    email = usuario.correo

    search = sdk.customer().search({"email": email})
    if search.get("status") == 200:
        results = search.get("response", {}).get("results", [])
        if results:
            mp_id = results[0]["id"]
            mp_customer = MercadoPagoCustomer.objects.create(
                usuario=usuario,
                mp_customer_id=mp_id,
            )
            return mp_customer

    result = sdk.customer().create({
        "email": email,
        "first_name": usuario.nombre,
        "last_name": usuario.apellido,
    })

    if result.get("status") not in (200, 201):
        logger.error("Error creando customer MP: %s", result)
        raise Exception(f"Error al crear customer en MercadoPago: {result.get('response', {})}")

    mp_id = result["response"]["id"]
    mp_customer = MercadoPagoCustomer.objects.create(
        usuario=usuario,
        mp_customer_id=mp_id,
    )
    return mp_customer


def guardar_tarjeta(usuario, card_token: str):
    """Guarda una tarjeta del usuario en MercadoPago y en la base local."""
    mp_customer = obtener_o_crear_customer(usuario)
    sdk = get_sdk()

    result = sdk.card().create(mp_customer.mp_customer_id, {"token": card_token})

    if result.get("status") not in (200, 201):
        logger.error("Error guardando tarjeta MP: %s", result)
        raise Exception(f"Error al guardar tarjeta: {result.get('response', {})}")

    card_data = result["response"]

    tarjeta, _ = Tarjeta.objects.update_or_create(
        usuario=usuario,
        mp_card_id=str(card_data.get("id", "")),
        defaults={
            "last_four": str(card_data.get("last_four_digits", "")),
            "brand": card_data.get("payment_method", {}).get("name", ""),
            "expiration_month": card_data.get("expiration_month", 0),
            "expiration_year": card_data.get("expiration_year", 0),
            "payment_method_id": card_data.get("payment_method", {}).get("id", ""),
            "payment_type": card_data.get("payment_method", {}).get("payment_type_id", "credit_card"),
            "issuer_id": str(card_data.get("issuer", {}).get("id", "")),
        },
    )

    return tarjeta


def listar_tarjetas(usuario):
    """Lista las tarjetas guardadas del usuario."""
    return Tarjeta.objects.filter(usuario=usuario, is_deleted=False)


def eliminar_tarjeta(usuario, tarjeta_id: int):
    """Elimina una tarjeta del usuario en MP y localmente."""
    try:
        tarjeta = Tarjeta.objects.get(id=tarjeta_id, usuario=usuario)
    except Tarjeta.DoesNotExist:
        return False

    try:
        mp_customer = MercadoPagoCustomer.objects.get(usuario=usuario)
        sdk = get_sdk()
        sdk.card().delete(mp_customer.mp_customer_id, tarjeta.mp_card_id)
    except (MercadoPagoCustomer.DoesNotExist, Exception) as e:
        logger.warning("Error eliminando tarjeta de MP (continúa eliminación local): %s", e)

    tarjeta.delete()
    return True


# ---------------------------------------------------------------------------
# Pago directo con card_token — Payments API (POST /v1/payments)
# ---------------------------------------------------------------------------

def _resolver_pm_desde_bin(bin_digits: str) -> dict:
    """
    Dado un BIN (primeros 6-8 dígitos de la tarjeta), consulta
    GET /v1/payment_methods/search?public_key=...&bins=...
    Retorna {"payment_method_id": "...", "issuer_id": "...", "payment_type": "..."} o {}.
    """
    if not bin_digits or len(bin_digits) < 6:
        return {}

    try:
        resp = req.get(
            "https://api.mercadopago.com/v1/payment_methods/search",
            params={
                "public_key": settings.MP_PUBLIC_KEY,
                "bins": bin_digits[:6],
            },
            timeout=10,
        )
        logger.info("payment_methods/search BIN=%s status=%s", bin_digits[:6], resp.status_code)
        if resp.status_code != 200:
            logger.error("payment_methods/search failed: %s", resp.text[:300])
            return {}

        results = resp.json().get("results", [])
        if not results:
            logger.error("No PM results for BIN %s", bin_digits[:6])
            return {}

        pm = results[0]
        pm_id = pm.get("id", "")
        payment_type = pm.get("payment_type_id", "credit_card")
        issuer = pm.get("issuer", {})
        issuer_id = str(issuer.get("id", "")) if isinstance(issuer, dict) else ""
        logger.info("BIN %s → pm=%s type=%s issuer_id=%s", bin_digits[:6], pm_id, payment_type, issuer_id)
        return {"payment_method_id": pm_id, "issuer_id": issuer_id, "payment_type": payment_type}
    except Exception as e:
        logger.error("Error buscando PM para BIN %s: %s", bin_digits[:6], e)

    return {}


def _obtener_bin_desde_token(card_token: str) -> str:
    """Intenta obtener los primeros 6 dígitos del card_token via API."""
    headers = {"Authorization": f"Bearer {settings.MP_ACCESS_TOKEN}"}
    try:
        resp = req.get(
            f"https://api.mercadopago.com/v1/card_tokens/{card_token}",
            headers=headers, timeout=10,
        )
        logger.info("card_tokens/%s... status=%s", card_token[:12], resp.status_code)
        if resp.status_code == 200:
            data = resp.json()
            first_six = data.get("first_six_digits", "")
            logger.info("Token first_six=%s", first_six)
            return first_six
        else:
            logger.error("card_tokens lookup failed: %s %s", resp.status_code, resp.text[:200])
    except Exception as e:
        logger.error("Error obteniendo card_token info: %s", e)
    return ""


def ejecutar_pago_mp(*, email: str, monto, card_token: str,
                     payment_method_id: str = '', issuer_id: str = '',
                     installments: int = 1, descripcion: str = '',
                     external_ref: str = '', bin_tarjeta: str = '',
                     mp_customer_id: str = '',
                     payment_method_type: str = '') -> dict:
    """
    Ejecuta el pago contra la Payments API de MercadoPago (POST /v1/payments).
    NO crea registros en la BD — eso queda a cargo del caller.
    Lanza Exception si MP rechaza el pago.

    Retorna el response completo del pago creado, incluyendo:
      - id: Payment ID
      - status / status_detail
    """
    if not payment_method_id or not issuer_id:
        bin_digits = bin_tarjeta
        if not bin_digits:
            bin_digits = _obtener_bin_desde_token(card_token)
        if bin_digits:
            resolved = _resolver_pm_desde_bin(bin_digits)
            if resolved:
                payment_method_id = resolved.get("payment_method_id", "") or payment_method_id
                issuer_id = resolved.get("issuer_id", "") or issuer_id

    logger.info("PM final: pm=%s issuer=%s", payment_method_id, issuer_id)

    if not payment_method_id:
        raise ValueError(
            "No se pudo determinar el payment_method_id. "
            "El frontend debe enviarlo usando mp.getPaymentMethods({ bin })."
        )

    if mp_customer_id:
        payer = {"type": "customer", "id": mp_customer_id}
    else:
        payer = {"email": email}

    payment_data = {
        "transaction_amount": float(monto),
        "token": card_token,
        "description": descripcion,
        "installments": installments,
        "payment_method_id": payment_method_id,
        "external_reference": external_ref,
        "payer": payer,
    }

    if issuer_id:
        payment_data["issuer_id"] = issuer_id

    logger.info(
        "Payments API request: amount=%s pm=%s installments=%s email=%s",
        float(monto), payment_method_id, installments, email,
    )

    sdk = get_sdk()
    result = sdk.payment().create(payment_data)

    response = result.get("response", {})
    status_code = result.get("status", 0)
    logger.info("Payments API response status=%s body=%s", status_code, response)

    if status_code not in (200, 201):
        logger.error("Error creando pago MP: status=%s body=%s", status_code, response)
        error_msg = response.get("message", str(response))
        cause = response.get("cause", [])
        if cause:
            error_msg = cause[0].get("description", error_msg)
        raise Exception(f"Error al procesar pago: {error_msg}")

    mp_status = response.get("status", "")
    if mp_status == "rejected":
        if _is_test_mode():
            logger.warning(
                "MP_TEST_MODE: pago rechazado por '%s', se trata como aprobado para testing",
                response.get("status_detail", ""),
            )
            response["status"] = "approved"
            response["status_detail"] = "accredited"
            return response
        detail = response.get("status_detail", "rejected")
        raise Exception(f"El pago fue rechazado: {detail}")

    return response


def crear_pago_directo(usuario, card_token: str, payment_method_id: str,
                       issuer_id: str, installments: int, tipo: str,
                       orden=None, trabajo=None, bin_tarjeta: str = '',
                       mp_customer_id: str = '', payment_method_type: str = ''):
    """
    Wrapper completo: ejecuta pago via Payments API + crea registro Pago en BD.
    Usado desde el endpoint genérico /api/pagos/pagar/ (ej. para trabajos).
    """
    if tipo == 'orden' and orden:
        monto = orden.total
        external_ref = f"orden_{orden.id}"
        descripcion = f"Orden #{orden.numero_orden}"
    elif tipo == 'trabajo' and trabajo:
        monto = trabajo.precio_final
        external_ref = f"trabajo_{trabajo.id}"
        descripcion = f"Trabajo #{trabajo.id}"
    else:
        raise ValueError("Debe especificar orden o trabajo")

    response = ejecutar_pago_mp(
        email=usuario.correo,
        monto=monto,
        card_token=card_token,
        payment_method_id=payment_method_id,
        issuer_id=issuer_id,
        installments=installments,
        descripcion=descripcion,
        bin_tarjeta=bin_tarjeta,
        external_ref=external_ref,
        mp_customer_id=mp_customer_id,
        payment_method_type=payment_method_type,
    )

    comision, monto_vendedor = calcular_comision(monto)

    mp_status = response.get("status", "")
    mp_status_detail = response.get("status_detail", "")
    mp_payment_id = str(response.get("id", ""))

    nuevo_status = MP_STATUS_MAP.get(mp_status, 'pendiente')

    pago = Pago.objects.create(
        tipo=tipo,
        orden=orden,
        trabajo=trabajo,
        usuario=usuario,
        monto=monto,
        comision_plataforma=comision,
        monto_vendedor=monto_vendedor,
        mp_payment_id=mp_payment_id,
        mp_status=mp_status,
        mp_status_detail=mp_status_detail,
        status=nuevo_status,
    )

    if nuevo_status == 'aprobado':
        _actualizar_entidad_pago_aprobado(pago)

    return {
        "pago_id": pago.id,
        "status": pago.status,
        "mp_status": mp_status,
        "mp_status_detail": mp_status_detail,
        "mp_payment_id": mp_payment_id,
    }


def obtener_medios_pago():
    """Obtiene los medios de pago disponibles en MP."""
    sdk = get_sdk()
    result = sdk.payment_methods().list_all()
    if result.get("status") == 200:
        return result.get("response", [])
    return []


def obtener_cuotas(payment_method_id: str, amount: float, issuer_id: str = ""):
    """Consulta las cuotas disponibles para un monto y medio de pago."""
    params = {
        "payment_method_id": payment_method_id,
        "amount": str(amount),
    }
    if issuer_id:
        params["issuer.id"] = issuer_id

    url = "https://api.mercadopago.com/v1/payment_methods/installments"
    headers = {"Authorization": f"Bearer {settings.MP_ACCESS_TOKEN}"}
    resp = req.get(url, params=params, headers=headers)

    if resp.status_code == 200:
        return resp.json()
    logger.error("Error consultando cuotas: %s", resp.text)
    return []
