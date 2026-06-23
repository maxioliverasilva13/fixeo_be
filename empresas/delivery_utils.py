def normalizar_modalidad(acepta_domicilio, acepta_retiro):
    return bool(acepta_domicilio), bool(acepta_retiro)


def modalidad_desde_usuario(usuario):
    acepta_domicilio = bool(getattr(usuario, 'trabajo_domicilio', False))
    acepta_retiro = bool(getattr(usuario, 'trabajo_local', False))
    if not acepta_domicilio and not acepta_retiro:
        acepta_domicilio = True
    return acepta_domicilio, acepta_retiro


def aplicar_limites_modalidad(usuario, acepta_domicilio, acepta_retiro):
    max_domicilio, max_retiro = modalidad_desde_usuario(usuario)
    acepta_domicilio = bool(acepta_domicilio) and max_domicilio
    acepta_retiro = bool(acepta_retiro) and max_retiro
    if not acepta_domicilio and not acepta_retiro:
        if max_domicilio:
            acepta_domicilio = True
        elif max_retiro:
            acepta_retiro = True
    return acepta_domicilio, acepta_retiro


def productos_comparten_modalidad(productos):
    productos = list(productos)
    if not productos:
        return True, True, True

    puede_domicilio = all(getattr(p, 'acepta_domicilio', True) for p in productos)
    puede_retiro = all(getattr(p, 'acepta_retiro', True) for p in productos)
    compatible = puede_domicilio or puede_retiro
    return compatible, puede_domicilio, puede_retiro


def validar_tipo_entrega_productos(productos, tipo_entrega):
    _, puede_domicilio, puede_retiro = productos_comparten_modalidad(productos)
    if tipo_entrega == 'domicilio' and not puede_domicilio:
        return 'Uno o más productos del carrito no admiten envío a domicilio'
    if tipo_entrega == 'retiro' and not puede_retiro:
        return 'Uno o más productos del carrito no admiten retiro en local'
    return None
