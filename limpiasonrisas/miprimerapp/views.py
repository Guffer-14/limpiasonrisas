from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import authenticate, login, logout
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.db import transaction
from django.urls import reverse
from django.http import JsonResponse
from django.utils import timezone
from django.db.models import Sum, Q
from .forms import LoginForm, RegistroForm, ContactoAvanzadoForm, ClinicaForm
from .models import (Producto, Categoria, ConsultaContacto, Clinica,
                     Pedido, DetallePedido, HistorialEstado, CarritoItem,
                     PersonalClinica, StockMinimo, VentaStock,
                     AjusteInventario, ProductoSugerido,
                     CarritoItemPublico, SolicitudPublico,
                     DetalleSolicitudPublico, PerfilUsuario,
                     DireccionDespacho, HistorialPrecio, NotaSeguimiento,
                     CompraProveedor, LoteCompra,
                     descontar_stock_fifo, verificar_stock, DetalleLoteVenta)
from django.contrib.auth.tokens import default_token_generator
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.models import User
from django.core.mail import send_mail
import secrets
from urllib.parse import urlencode
IVA = 0.19


def es_staff(user):
    return user.is_staff or user.is_superuser


# ── Helpers carrito ───────────────────────────────────────────────────────────
def _carrito_context(clinica):
    items  = clinica.carrito_items.select_related('producto').all()
    total  = sum(i.subtotal for i in items)
    return items, total, round(total * IVA), round(total * (1 + IVA))


# ── Páginas públicas ──────────────────────────────────────────────────────────
def index(request):
    categorias = Categoria.objects.all()
    destacados = Producto.objects.filter(activo=True, destacado=True)[:8]
    return render(request, 'index.html', {'categorias': categorias, 'destacados': destacados})

def asesoria_inicio(request):
    """
    Punto de entrada al flujo de asesoría guiada.
    TODO: por ahora es una pantalla "Próximamente". Acá se deberá resolver:
      - si el usuario tiene asesoría disponible (gratis / por referido)
      - si debe pagar el depósito de $3.000 para continuar
      - mostrar el cuestionario y armar el carrito sugerido
    """
    return render(request, 'asesoria_proximamente.html')


def catalogo(request):
    categorias = Categoria.objects.prefetch_related('productos').all()
    cat_id    = request.GET.get('categoria')
    busqueda  = request.GET.get('q', '').strip()
    productos = Producto.objects.filter(activo=True, precio__gt=0)
    if cat_id:
        productos = productos.filter(categoria_id=cat_id)
    if busqueda:
        productos = productos.filter(
            Q(nombre__icontains=busqueda) | Q(marca__icontains=busqueda)
        )

    if request.method == 'POST':
        if not request.user.is_authenticated:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'ok': False, 'redirect': True, 'url': str(reverse('login'))}, status=401)
            return redirect('login')
        prod_id = request.POST.get('producto_id')
        es_ajax = request.headers.get('X-Requested-With') == 'XMLHttpRequest'
        try:
            cantidad = int(request.POST.get('cantidad', 1))
        except (TypeError, ValueError):
            cantidad = 1
        if cantidad < 1:
            cantidad = 1
        if cantidad > 99:
            cantidad = 99
        try:
            prod = Producto.objects.get(pk=prod_id, activo=True)
            if hasattr(request.user, 'clinica'):
                clinica = request.user.clinica
                precio_b2d = prod.get_precio_b2d()
                item, created = CarritoItem.objects.get_or_create(
                    clinica=clinica, producto=prod,
                    defaults={'cantidad': 0, 'precio_unitario': precio_b2d}
                )
                cantidad_total = item.cantidad + cantidad if not created else cantidad
                ok, disponible, msg_stock = verificar_stock(prod, cantidad_total)
                if not ok:
                    if es_ajax:
                        return JsonResponse({'ok': False, 'mensaje': msg_stock, 'disponible': disponible})
                    messages.warning(request, msg_stock)
                    return redirect('catalogo')
                item.cantidad = cantidad_total
                item.save()
                nuevo_count = clinica.carrito_items.count()
            else:
                item, created = CarritoItemPublico.objects.get_or_create(
                    usuario=request.user, producto=prod,
                    defaults={'cantidad': 0, 'precio_unitario': prod.precio}
                )
                cantidad_total = item.cantidad + cantidad if not created else cantidad
                ok, disponible, msg_stock = verificar_stock(prod, cantidad_total)
                if not ok:
                    if es_ajax:
                        return JsonResponse({'ok': False, 'mensaje': msg_stock, 'disponible': disponible})
                    messages.warning(request, msg_stock)
                    return redirect('catalogo')
                item.cantidad = cantidad_total
                item.save()
                nuevo_count = CarritoItemPublico.objects.filter(usuario=request.user).count()

            if es_ajax:
                return JsonResponse({
                    'ok': True,
                    'mensaje': f'"{prod.nombre}" agregado al carrito 🛒',
                    'carrito_count': nuevo_count,
                })
            messages.success(request, f'"{prod.nombre}" agregado al carrito 🛒')
        except Exception:
            if es_ajax:
                return JsonResponse({'ok': False, 'mensaje': 'Error al agregar al carrito.'}, status=400)
            messages.error(request, 'Error al agregar al carrito.')
        return redirect('catalogo')

    return render(request, 'catalogo.html', {
        'productos': productos, 'categorias': categorias,
        'cat_id': cat_id, 'busqueda': busqueda,
    })


def detalle_producto(request, pk):
    producto     = get_object_or_404(Producto, pk=pk, activo=True, precio__gt=0)
    relacionados = Producto.objects.filter(categoria=producto.categoria, activo=True, precio__gt=0).exclude(pk=pk)[:4]

    # Clínica logueada puede agregar al carrito desde aquí
    if request.method == 'POST' and request.user.is_authenticated:
        try:
            clinica    = request.user.clinica
            cantidad   = int(request.POST.get('cantidad', 1))
            precio_b2d = producto.get_precio_b2d()
            item, created = CarritoItem.objects.get_or_create(
                clinica=clinica, producto=producto,
                defaults={'cantidad': 0, 'precio_unitario': precio_b2d}
            )
            cantidad_total = item.cantidad + cantidad if not created else cantidad
            ok, disponible, msg_stock = verificar_stock(producto, cantidad_total)
            if not ok:
                messages.warning(request, msg_stock)
                return redirect('detalle_producto', pk=pk)
            item.cantidad = cantidad_total
            item.save()
            messages.success(request, f'"{producto.nombre}" agregado al carrito 🛒')
            return redirect('detalle_producto', pk=pk)
        except Clinica.DoesNotExist:
            messages.warning(request, 'Debes inscribir tu clínica para agregar productos al carrito.')
            return redirect('inscripcion_clinica')

    es_clinica = False
    precio_b2d = 0
    if request.user.is_authenticated:
        try:
            request.user.clinica
            es_clinica = True
            precio_b2d = producto.get_precio_b2d()
        except Clinica.DoesNotExist:
            pass

    return render(request, 'detalle_producto.html', {
        'producto':     producto,
        'relacionados': relacionados,
        'es_clinica':   es_clinica,
        'precio_b2d':   precio_b2d,
    })


def contacto(request):
    if request.method == 'POST':
        form = ContactoAvanzadoForm(request.POST, request.FILES)
        if form.is_valid():
            form.save()
            messages.success(request, '¡Mensaje enviado! Te contactaremos pronto 😊')
            return redirect('contacto')
    else:
        form = ContactoAvanzadoForm()
    return render(request, 'contacto.html', {'form': form})


# ── Inscripción de clínica ────────────────────────────────────────────────────
@login_required
def inscripcion_clinica(request):
    try:
        request.user.clinica
        return redirect('dashboard_clinica')
    except Clinica.DoesNotExist:
        pass
    if request.method == 'POST':
        form = ClinicaForm(request.POST)
        if form.is_valid():
            clinica = form.save(commit=False)
            clinica.usuario = request.user
            clinica.save()
            form.save_m2m()
            messages.success(request,
                '¡Tu solicitud de inscripción fue guardada exitosamente! '
                'Nuestro equipo se contactará contigo dentro de las próximas 24 horas. 🦷')
            return redirect('dashboard_clinica')
    else:
        form = ClinicaForm()
    
    return render(request, 'inscripcion_clinica.html', {
        'form': form,
        'dias_choices': [
            ('lunes',        'Lunes'),
            ('martes',       'Martes'),
            ('miercoles',    'Miércoles'),
            ('jueves',       'Jueves'),
            ('viernes',      'Viernes'),
            ('sabado',       'Sábado'),
            ('domingo',      'Domingo'),
            ('cualquier_dia','Cualquier día'),
        ],
    })


# ── API: precio B2D de un producto ───────────────────────────────────────────
@login_required
def api_precio_producto(request, pk):
    try:
        prod = Producto.objects.get(pk=pk, activo=True)
        return JsonResponse({'precio_b2d': prod.get_precio_b2d(), 'nombre': prod.nombre})
    except Producto.DoesNotExist:
        return JsonResponse({'error': 'No encontrado'}, status=404)


# ── API: búsqueda de productos (autocomplete) ─────────────────────────────────

def api_buscar_productos(request):
    q       = request.GET.get('q', '').strip()
    results = []
    if q:
        productos = Producto.objects.filter(
            activo=True
        ).filter(
            Q(nombre__icontains=q) | Q(marca__icontains=q)
        )[:10]
        results = [{'id': p.pk, 'nombre': p.nombre, 'marca': p.marca,
                    'precio': p.precio, 'precio_b2d': p.get_precio_b2d()} for p in productos]
                    
    return JsonResponse({'results': results})


# ── Dashboard de clínica ──────────────────────────────────────────────────────
@login_required
def dashboard_clinica(request):
    try:
        clinica = request.user.clinica
    except Clinica.DoesNotExist:
        messages.info(request, 'Primero debes inscribir tu clínica.')
        return redirect('inscripcion_clinica')

    # Total gastado este mes
    hoy   = timezone.now()
    total_mes = DetallePedido.objects.filter(
        pedido__clinica=clinica,
        pedido__fecha_creacion__year=hoy.year,
        pedido__fecha_creacion__month=hoy.month,
        pedido__estado__in=['en_preparacion', 'enviado', 'entregado']
    ).aggregate(total=Sum('precio_unitario'))['total'] or 0

    # Pedidos activos (no entregados ni cancelados)
    pedidos_activos_count = clinica.pedidos.exclude(
        estado__in=['entregado', 'cancelado']
    ).count()

    # Carrito inline
    carrito_items, carrito_neto, carrito_iva, carrito_total = _carrito_context(clinica)
    productos = Producto.objects.filter(activo=True).select_related('categoria')

    
    # Agregar al carrito
    if request.method == 'POST' and request.POST.get('action') == 'agregar_carrito':
        prod_id  = request.POST.get('producto_id')
        cantidad = request.POST.get('cantidad', 1)
        obs      = request.POST.get('observaciones', '')
        try:
            prod      = Producto.objects.get(pk=prod_id, activo=True)
            nueva_cant = int(cantidad)
            item_existente = CarritoItem.objects.filter(clinica=clinica, producto=prod).first()
            cantidad_previa = item_existente.cantidad if item_existente else 0
            ok, disponible, msg_stock = verificar_stock(prod, cantidad_previa + nueva_cant)
            if not ok:
                messages.warning(request, msg_stock)
                return redirect('dashboard_clinica')
            # Calcular precio B2D considerando volumen
            precio_b2d = prod.get_precio_b2d()
            item, created = CarritoItem.objects.get_or_create(
                clinica=clinica, producto=prod,
                defaults={'cantidad': nueva_cant, 'precio_unitario': precio_b2d, 'observaciones': obs}
            )
            if not created:
                item.cantidad += nueva_cant
                if obs:
                    item.observaciones = obs
                item.save()
            # Recalcular precio según volumen total acumulado
            total_cant = item.cantidad
            if (prod.precio_volumen and prod.cantidad_minima_volumen
                    and total_cant >= prod.cantidad_minima_volumen):
                margen = 1.20
                item.precio_unitario = round((prod.costo or prod.precio_volumen) * margen) if prod.costo else prod.precio_volumen
            else:
                item.precio_unitario = prod.get_precio_b2d()
            item.save()
            messages.success(request, f'"{prod.nombre}" agregado al carrito 🛒')
        except (Producto.DoesNotExist, ValueError):
            messages.error(request, 'Error al agregar al carrito.')
        return redirect('dashboard_clinica')

    # Actualizar cantidad desde carrito inline
    if request.method == 'POST' and request.POST.get('action') == 'actualizar_item':
        item_id  = request.POST.get('item_id')
        cantidad = request.POST.get('cantidad', 1)
        try:
            item = CarritoItem.objects.get(pk=item_id, clinica=clinica)
            nueva = int(cantidad)
            if nueva > 0:
                ok, disponible, msg_stock = verificar_stock(item.producto, nueva)
                if not ok:
                    messages.warning(request, msg_stock)
                    return redirect('dashboard_clinica')
                item.cantidad = nueva
                item.save()
            else:
                item.delete()
        except (CarritoItem.DoesNotExist, ValueError):
            pass
        return redirect('dashboard_clinica')

    # Eliminar ítem del carrito inline
    if request.method == 'POST' and request.POST.get('action') == 'eliminar_item':
        item_id = request.POST.get('item_id')
        CarritoItem.objects.filter(pk=item_id, clinica=clinica).delete()
        return redirect('dashboard_clinica')

    return render(request, 'dashboard_clinica.html', {
        'clinica':              clinica,
        'productos':            productos,
        'carrito_items':        carrito_items,
        'carrito_neto':         carrito_neto,
        'carrito_iva':          carrito_iva,
        'carrito_total':        carrito_total,
        'total_mes':            total_mes,
        'pedidos_activos_count': pedidos_activos_count,
        'pedidos_count':        clinica.pedidos.count(),
    })


# ── Finalizar pedido (checkout placeholder) ───────────────────────────────────
@login_required
def finalizar_pedido(request):
    try:
        clinica = request.user.clinica
    except Clinica.DoesNotExist:
        return redirect('inscripcion_clinica')

    carrito_items, carrito_neto, carrito_iva, carrito_total = _carrito_context(clinica)

    if not carrito_items:
        messages.warning(request, 'Tu carrito está vacío.')
        return redirect('dashboard_clinica')

    if request.method == 'POST' and request.POST.get('action') == 'confirmar':
        # 1) Validar TODO el carrito antes de crear nada
        errores_stock = []
        for item in carrito_items:
            ok, disponible, msg_stock = verificar_stock(item.producto, item.cantidad)
            if not ok:
                errores_stock.append(msg_stock)

        if errores_stock:
            for msg_stock in errores_stock:
                messages.error(request, msg_stock)
            messages.warning(request, 'Ajusta las cantidades en tu carrito antes de continuar. Para ir al carrito aprieta "← Volver".')
            return redirect('finalizar_pedido')

        # 2) Si todo tiene stock, recién ahí se crea el pedido
        with transaction.atomic():
            pedido = Pedido.objects.create(clinica=clinica, total=carrito_neto)
            for item in carrito_items:
                detalle = DetallePedido.objects.create(
                    pedido=pedido,
                    producto=item.producto,
                    cantidad=item.cantidad,
                    precio_unitario=item.precio_unitario,
                    observaciones=item.observaciones,
                )
                # Descontar stock usando FIFO (el lote que vence primero, se usa primero)
                uso_lotes, faltante = descontar_stock_fifo(item.producto, item.cantidad)
                for lote, cant_usada in uso_lotes:
                    DetalleLoteVenta.objects.create(
                        lote=lote, cantidad=cant_usada, detalle_pedido=detalle,
                    )
                if faltante > 0:
                    # No debería pasar porque ya validamos arriba, pero queda como red de seguridad
                    messages.warning(request,
                        f'Atención: "{item.producto.nombre}" tuvo una diferencia de stock '
                        f'(faltaron {faltante} unidades). Revisa el inventario.')

            HistorialEstado.objects.create(pedido=pedido, estado='pendiente')
            carrito_items.delete()

        messages.success(request, f'¡Pedido #{pedido.pk} enviado correctamente! 🎉 Lo verás en "Pedidos activos".')
        return redirect('pedidos_activos')

    # Marcar cada item con su estado de stock y avisar de inmediato si falta algo
    hay_problema_stock = False
    for item in carrito_items:
        ok, disponible, msg_stock = verificar_stock(item.producto, item.cantidad)
        item.sin_stock_suficiente = not ok
        item.stock_disponible = disponible
        if not ok:
            hay_problema_stock = True
            messages.error(request, msg_stock)

    if hay_problema_stock:
        messages.warning(request, 'Ajusta las cantidades en tu carrito antes de continuar. Para ir al carrito aprieta "← Volver".')

    return render(request, 'finalizar_pedido.html', {
        'clinica':       clinica,
        'carrito_items': carrito_items,
        'carrito_neto':  carrito_neto,
        'carrito_iva':   carrito_iva,
        'carrito_total': carrito_total,
    })


# ── Pedidos activos ───────────────────────────────────────────────────────────
@login_required
def pedidos_activos(request):
    try:
        clinica = request.user.clinica
    except Clinica.DoesNotExist:
        return redirect('inscripcion_clinica')

    pedidos = clinica.pedidos.exclude(
        estado__in=['entregado', 'cancelado']
    ).prefetch_related('detalles__producto', 'historial')

    return render(request, 'pedidos_activos.html', {
        'clinica': clinica,
        'pedidos': pedidos,
    })


# ── Mis pedidos (historial completo) ─────────────────────────────────────────
@login_required
def mis_pedidos(request):
    try:
        clinica = request.user.clinica
    except Clinica.DoesNotExist:
        return redirect('inscripcion_clinica')

    pedidos = clinica.pedidos.prefetch_related('detalles__producto', 'historial').all()

    return render(request, 'mis_pedidos.html', {
        'clinica': clinica,
        'pedidos': pedidos,
    })


# ── Login / Logout / Registro ─────────────────────────────────────────────────
def login_view(request):
    if request.user.is_authenticated:
        return redirect('index')
    if request.method == 'POST':
        form = LoginForm(request.POST)
        if form.is_valid():
            user = authenticate(request,
                username=form.cleaned_data['username'],
                password=form.cleaned_data['password'])
            if user:
                login(request, user)
                return redirect(request.GET.get('next', 'index'))
            messages.error(request, 'Usuario o contraseña incorrectos.')
    else:
        form = LoginForm()
    return render(request, 'registration/login.html', {'form': form})


def logout_view(request):
    if request.method == 'POST':
        logout(request)
    return redirect('index')


def verificar_disponibilidad(request):
    """
    Endpoint AJAX para el formulario de registro: revisa en vivo si un
    username o email ya están en uso, sin necesidad de enviar el formulario.
    Se usa para no perder lo que la persona ya escribió (ej. la contraseña)
    cuando hay un error de este tipo.
    """
    campo = request.GET.get('campo', '')
    valor = request.GET.get('valor', '').strip()
    disponible = True
    if campo == 'username' and valor:
        disponible = not User.objects.filter(username__iexact=valor).exists()
    elif campo == 'email' and valor:
        disponible = not User.objects.filter(email__iexact=valor).exists()
    return JsonResponse({'disponible': disponible})


def registro(request):
    if request.user.is_authenticated:
        return redirect('index')
    if request.method == 'POST':
        form = RegistroForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, f'¡Bienvenida/o, {user.first_name or user.username}!')
            return redirect('index')
    else:
        form = RegistroForm()
    return render(request, 'registro.html', {'form': form})



def password_reset(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        usuarios = User.objects.filter(email=email)

        if usuarios.exists():
            for user in usuarios:
                token = default_token_generator.make_token(user)
                uid = urlsafe_base64_encode(force_bytes(user.pk))
                reset_link = request.build_absolute_uri(
                    f'/accounts/reset/{uid}/{token}/'
                )
                asunto = 'Recupera tu contraseña - Limpiasonrisas'
                mensaje = (
                    f'Hola {user.username},\n\n'
                    f'Haz clic en el siguiente link para restablecer tu contraseña:\n'
                    f'{reset_link}\n\n'
                    f'Si no solicitaste este cambio, ignora este correo.'
                )
                send_mail(asunto, mensaje, None, [user.email])

        # Por seguridad, siempre mostramos el mismo mensaje
        # (así no revelamos si el correo existe o no en el sistema)
        messages.success(request, 'Si el correo existe en nuestro sistema, recibirás instrucciones para recuperar tu contraseña.')
        return redirect('login')

    return render(request, 'registration/password_reset_form.html')

# ── Panel admin ───────────────────────────────────────────────────────────────
@login_required
@user_passes_test(es_staff)
def panel_admin(request):
    clinicas  = Clinica.objects.all().order_by('-fecha_inscripcion')
    pedidos   = Pedido.objects.select_related('clinica').order_by('-fecha_creacion')[:20]
    mensajes  = ConsultaContacto.objects.filter(leido=False).order_by('-fecha')[:10]
    return render(request, 'panel_admin.html', {
        'clinicas': clinicas, 'pedidos': pedidos, 'mensajes': mensajes,
    })


def contacto_modelform(request):
    return redirect('contacto')

# ── MI STOCK ──────────────────────────────────────────────────────────────────
@login_required
def mi_stock(request):
    try:
        clinica = request.user.clinica
    except Clinica.DoesNotExist:
        return redirect('inscripcion_clinica')

    from django.utils import timezone
    from django.db.models import Sum, Max
    import datetime

    periodo = request.GET.get('periodo', 'semana')
    hoy = timezone.now()

    if periodo == 'semana':
        fecha_desde = hoy - datetime.timedelta(days=7)
    elif periodo == 'mes':
        fecha_desde = hoy.replace(day=1)
    else:
        fecha_desde = hoy.replace(month=1, day=1)

    persona_id = request.GET.get('persona', 'todos')
    es_todos = persona_id == 'todos'

    productos_comprados = DetallePedido.objects.filter(
        pedido__clinica=clinica
    ).values('producto').annotate(
        total_comprado=Sum('cantidad'),
        ultimo_pedido=Max('pedido__fecha_creacion')
    ).order_by('producto__nombre')

    stock_data = []
    for item in productos_comprados:
        prod = Producto.objects.get(pk=item['producto'])

        ventas_qs = VentaStock.objects.filter(
            clinica=clinica, producto=prod, fecha__gte=fecha_desde
        )
        if persona_id != 'todos':
            ventas_qs = ventas_qs.filter(personal_id=persona_id)

        vendidos = ventas_qs.aggregate(total=Sum('cantidad'))['total'] or 0

        ventas_personal = []
        for venta in VentaStock.objects.filter(
            clinica=clinica, producto=prod, fecha__gte=fecha_desde
        ).select_related('personal').order_by('personal__nombre'):
            encontrado = False
            for vp in ventas_personal:
                if vp['personal__nombre'] == (venta.personal.nombre if venta.personal else 'Sin registro'):
                   vp['total'] += venta.cantidad
                   encontrado = True
                   break
            if not encontrado:
               ventas_personal.append({
                   'personal__nombre':       venta.personal.nombre if venta.personal else 'Sin registro',
                   'personal__especialidad': venta.personal.especialidad if venta.personal else '',
                   'total':                  venta.cantidad,
                   'venta_id':               venta.pk,
                })

        ventas_detalle = list(
            VentaStock.objects.filter(
                clinica=clinica, producto=prod, fecha__gte=fecha_desde
            ).select_related('personal').order_by('-fecha')
        )

        top = ventas_personal[0] if ventas_personal else None

        stock_min_obj, _ = StockMinimo.objects.get_or_create(
            clinica=clinica, producto=prod, defaults={'minimo': 0}
        )

        ajuste_obj, _ = AjusteInventario.objects.get_or_create(
            clinica=clinica, producto=prod, defaults={'cantidad': 0}
        )
        ajuste = ajuste_obj.cantidad

        stock_estimado = item['total_comprado'] + ajuste - vendidos
        minimo = stock_min_obj.minimo

        if minimo == 0:
            estado = 'sin_definir'
        elif stock_estimado <= 0:
            estado = 'reponer'
        elif stock_estimado <= minimo:
            estado = 'bajo'
        else:
            estado = 'ok'

        stock_data.append({
            'producto':        prod,
            'total_comprado':  item['total_comprado'],
            'ultimo_pedido':   item['ultimo_pedido'],
            'vendidos':        vendidos,
            'stock_estimado':  max(stock_estimado, 0),
            'minimo':          minimo,
            'ajuste':          ajuste,
            'estado':          estado,
            'top_vendedor':    top,
            'ventas_personal': list(ventas_personal),
            'ventas_detalle':  ventas_detalle,
        })

    personal_list = clinica.personal.filter(activo=True)
    carrito_items, carrito_neto, carrito_iva, carrito_total = _carrito_context(clinica)

    return render(request, 'mi_stock.html', {
        'clinica':          clinica,
        'stock_data':       stock_data,
        'periodo':          periodo,
        'persona_id':       persona_id,
        'es_todos':         es_todos,
        'personal_list':    personal_list,
        'carrito_items':    carrito_items,
        'carrito_total':    carrito_total,
        'periodo_opciones': [('semana','Semana'),('mes','Mes'),('anio','Año')],
    })


def api_registrar_venta(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        import json
        import datetime
        data         = json.loads(request.body)
        clinica      = request.user.clinica
        quien        = data.get('quien', '').strip()
        especialidad = data.get('especialidad', 'otro')
        fecha        = data.get('fecha') or None
        items        = data.get('items', [])

        if not fecha:
            return JsonResponse({'error': 'Debes indicar la fecha de la venta'}, status=400)

        fecha_venta = datetime.date.fromisoformat(fecha)
        if fecha_venta > datetime.date.today():
            return JsonResponse({'error': 'La fecha de venta no puede ser futura'}, status=400)

        personal = None
        if quien:
            personal, _ = PersonalClinica.objects.get_or_create(
                clinica=clinica, nombre=quien,
                defaults={'especialidad': especialidad}
            )

        for item in items:
            prod    = Producto.objects.get(pk=item['producto_id'])
            cantidad = int(item['cantidad'])
            VentaStock.objects.create(
                clinica=clinica,
                producto=prod,
                personal=personal,
                cantidad=cantidad,
                fecha=fecha_venta,
            )

        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def api_actualizar_minimo(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        import json
        data    = json.loads(request.body)
        clinica = request.user.clinica
        prod    = Producto.objects.get(pk=data['producto_id'])
        minimo  = int(data['minimo'])
        obj, _  = StockMinimo.objects.update_or_create(
            clinica=clinica, producto=prod,
            defaults={'minimo': minimo}
        )
        return JsonResponse({'ok': True, 'minimo': obj.minimo})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)



@login_required
def api_agregar_carrito_stock(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        import json
        data      = json.loads(request.body)
        clinica   = request.user.clinica
        prod      = Producto.objects.get(pk=data['producto_id'])
        cantidad  = int(data['cantidad'])
        precio_b2d = prod.get_precio_b2d()

        item_existente = CarritoItem.objects.filter(clinica=clinica, producto=prod).first()
        cantidad_previa = item_existente.cantidad if item_existente else 0
        ok, disponible, msg_stock = verificar_stock(prod, cantidad_previa + cantidad)
        if not ok:
            return JsonResponse({'error': msg_stock, 'disponible': disponible}, status=400)

        item, created = CarritoItem.objects.get_or_create(
            clinica=clinica, producto=prod,
            defaults={'cantidad': cantidad, 'precio_unitario': precio_b2d}
        )
        if not created:
            item.cantidad += cantidad
            item.save()

        total_carrito = sum(i.subtotal for i in clinica.carrito_items.all())
        return JsonResponse({
            'ok': True,
            'nombre': prod.nombre,
            'carrito_count': clinica.carrito_items.count(),
            'carrito_total': total_carrito,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def api_ajuste_inventario(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        import json
        data     = json.loads(request.body)
        clinica  = request.user.clinica
        prod     = Producto.objects.get(pk=data['producto_id'])
        cantidad = int(data['cantidad'])
        nota     = data.get('nota', '')
        obj, _   = AjusteInventario.objects.update_or_create(
            clinica=clinica, producto=prod,
            defaults={'cantidad': cantidad, 'nota': nota}
        )
        return JsonResponse({'ok': True, 'cantidad': obj.cantidad})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def api_sugerir_producto(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        import json
        data    = json.loads(request.body)
        clinica = request.user.clinica
        ProductoSugerido.objects.create(
            clinica=clinica,
            nombre_producto=data.get('nombre', ''),
            marca=data.get('marca', ''),
            uso=data.get('uso', ''),
            cantidad_mensual=data.get('cantidad_mensual') or None,
        )
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def api_eliminar_venta(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        import json
        data    = json.loads(request.body)
        clinica = request.user.clinica
        venta   = VentaStock.objects.get(pk=data['venta_id'], clinica=clinica)
        venta.delete()
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    
    # ── MI CUENTA (público general) ───────────────────────────────────────────────
@login_required
def mi_cuenta(request):
    try:
        # Si tiene clínica, redirigir al dashboard de clínica
        request.user.clinica
        return redirect('dashboard_clinica')
    except:
        pass

    carrito_items = CarritoItemPublico.objects.filter(
        usuario=request.user
    ).select_related('producto')
    
    carrito_neto  = sum(i.subtotal for i in carrito_items)
    carrito_iva   = round(carrito_neto * 0.19)
    carrito_total = round(carrito_neto * 1.19)

    # Total gastado este año
    from django.utils import timezone
    from django.db.models import Sum
    hoy = timezone.now()
    total_anio = DetalleSolicitudPublico.objects.filter(
        solicitud__usuario=request.user,
        solicitud__fecha_creacion__year=hoy.year,
        solicitud__estado__in=['en_proceso','enviado','entregado']
    ).aggregate(total=Sum('precio_unitario'))['total'] or 0

    # Historial de compras
    solicitudes = SolicitudPublico.objects.filter(
        usuario=request.user
    ).prefetch_related('detalles__producto')[:5]

    return render(request, 'mi_cuenta.html', {
        'carrito_items': carrito_items,
        'carrito_neto':  carrito_neto,
        'carrito_iva':   carrito_iva,
        'carrito_total': carrito_total,
        'total_anio':    total_anio,
        'solicitudes':   solicitudes,
    })


@login_required
def mis_datos(request):
    """
    Pantalla independiente para que el cliente público vea y edite sus
    datos personales, datos de contacto/entrega y direcciones de despacho,
    sin necesidad de pasar por el checkout para hacerlo.
    """
    try:
        request.user.clinica
        return redirect('dashboard_clinica')
    except Clinica.DoesNotExist:
        pass

    perfil, _ = PerfilUsuario.objects.get_or_create(usuario=request.user)
    direcciones = DireccionDespacho.objects.filter(usuario=request.user)

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'guardar_datos':
            user = request.user
            user.first_name = request.POST.get('first_name', '').strip()
            user.last_name  = request.POST.get('last_name', '').strip()
            nuevo_email     = request.POST.get('email', '').strip()
            if nuevo_email:
                user.email = nuevo_email
            user.save()

            perfil.rut = request.POST.get('rut', '').strip()
            perfil.telefono = request.POST.get('telefono', '').strip()
            perfil.horario_preferido = request.POST.get('horario', 'cualquiera')
            dias_seleccionados = request.POST.getlist('dias')
            perfil.dias_disponibles = ','.join(dias_seleccionados) if dias_seleccionados else 'cualquier_dia'
            perfil.observaciones_entrega = request.POST.get('observaciones', '')
            perfil.save()
            messages.success(request, 'Tus datos se actualizaron correctamente.')
            return redirect('mis_datos')

        elif accion == 'agregar_direccion':
            nueva_dir = request.POST.get('nueva_direccion', '').strip()
            nueva_ciudad = request.POST.get('nueva_ciudad', '').strip()
            nueva_region = request.POST.get('nueva_region', '').strip()
            if nueva_dir and nueva_ciudad:
                DireccionDespacho.objects.create(
                    usuario=request.user,
                    alias=request.POST.get('alias', 'Casa') or 'Casa',
                    direccion=nueva_dir,
                    ciudad=nueva_ciudad,
                    region=nueva_region,
                    principal=not direcciones.exists(),
                )
                messages.success(request, 'Dirección agregada correctamente.')
            else:
                messages.warning(request, 'Completa al menos la dirección y la ciudad.')
            return redirect('mis_datos')

        elif accion == 'marcar_principal':
            dir_id = request.POST.get('direccion_id')
            DireccionDespacho.objects.filter(usuario=request.user).update(principal=False)
            DireccionDespacho.objects.filter(pk=dir_id, usuario=request.user).update(principal=True)
            messages.success(request, 'Dirección principal actualizada.')
            return redirect('mis_datos')

        elif accion == 'eliminar_direccion':
            dir_id = request.POST.get('direccion_id')
            direccion = DireccionDespacho.objects.filter(pk=dir_id, usuario=request.user).first()
            if direccion:
                era_principal = direccion.principal
                direccion.delete()
                if era_principal:
                    siguiente = DireccionDespacho.objects.filter(usuario=request.user).first()
                    if siguiente:
                        siguiente.principal = True
                        siguiente.save()
                messages.success(request, 'Dirección eliminada.')
            return redirect('mis_datos')

    return render(request, 'mis_datos.html', {
        'perfil': perfil,
        'direcciones': direcciones,
    })

# ── APIs CARRITO PÚBLICO ──────────────────────────────────────────────────────

@login_required
def api_carrito_publico_agregar(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        import json
        data     = json.loads(request.body)
        prod     = Producto.objects.get(pk=data['producto_id'])
        cantidad = int(data['cantidad'])
        item, created = CarritoItemPublico.objects.get_or_create(
            usuario=request.user, producto=prod,
            defaults={'cantidad': 0, 'precio_unitario': prod.precio}
        )
        cantidad_total = item.cantidad + cantidad if not created else cantidad
        ok, disponible, msg_stock = verificar_stock(prod, cantidad_total)
        if not ok:
            return JsonResponse({'error': msg_stock, 'disponible': disponible}, status=400)
        item.cantidad = cantidad_total
        item.save()
        return JsonResponse({'ok': True, 'nombre': prod.nombre})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)



@login_required
def api_carrito_publico_actualizar(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        import json
        data     = json.loads(request.body)
        item     = CarritoItemPublico.objects.get(pk=data['item_id'], usuario=request.user)
        cantidad = int(data['cantidad'])
        if cantidad > 0:
            ok, disponible, msg_stock = verificar_stock(item.producto, cantidad)
            if not ok:
                return JsonResponse({'error': msg_stock, 'disponible': disponible}, status=400)
            item.cantidad = cantidad
            item.save()
        else:
            item.delete()
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def api_carrito_publico_eliminar(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        import json
        data = json.loads(request.body)
        CarritoItemPublico.objects.filter(
            pk=data['item_id'], usuario=request.user
        ).delete()
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)


@login_required
def api_volver_a_pedir(request):
    if request.method != 'POST':
        return JsonResponse({'error': 'Método no permitido'}, status=405)
    try:
        import json
        data     = json.loads(request.body)
        sol      = SolicitudPublico.objects.get(
            pk=data['solicitud_id'], usuario=request.user
        )
        for det in sol.detalles.all():
            item, created = CarritoItemPublico.objects.get_or_create(
                usuario=request.user, producto=det.producto,
                defaults={'cantidad': det.cantidad, 'precio_unitario': det.producto.precio}
            )
            if not created:
                item.cantidad += det.cantidad
                item.save()
        return JsonResponse({'ok': True})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)
    

    # ── FINALIZAR PEDIDO PÚBLICO ──────────────────────────────────────────────────
@login_required
def finalizar_pedido_publico(request):
    try:
        request.user.clinica
        return redirect('finalizar_pedido')
    except:
        pass

    carrito_items = CarritoItemPublico.objects.filter(
        usuario=request.user
    ).select_related('producto')

    if not carrito_items:
        return redirect('mi_cuenta')

    carrito_neto  = sum(i.subtotal for i in carrito_items)
    carrito_iva   = round(carrito_neto * 0.19)
    carrito_total = round(carrito_neto * 1.19)

    # Obtener perfil y direcciones
    perfil, _ = PerfilUsuario.objects.get_or_create(usuario=request.user)
    direcciones = DireccionDespacho.objects.filter(usuario=request.user)

    if request.method == 'POST':
        import json
        # Guardar o actualizar RUT en perfil
        rut = request.POST.get('rut', '').strip()
        if rut:
            perfil.rut = rut
        perfil.horario_preferido    = request.POST.get('horario', 'cualquiera')
        dias_seleccionados = request.POST.getlist('dias') 
        perfil.dias_disponibles = ','.join(dias_seleccionados) if dias_seleccionados else 'cualquier_dia'
        perfil.observaciones_entrega = request.POST.get('observaciones', '')
        perfil.save()

        # Dirección
        dir_id = request.POST.get('direccion_id')
        direccion = None
        if dir_id:
            try:
                direccion = DireccionDespacho.objects.get(pk=dir_id, usuario=request.user)
            except:
                pass
        else:
            # Nueva dirección
            nueva_dir = request.POST.get('nueva_direccion', '').strip()
            nueva_ciudad = request.POST.get('nueva_ciudad', '').strip()
            nueva_region = request.POST.get('nueva_region', '').strip()
            if nueva_dir and nueva_ciudad:
                direccion = DireccionDespacho.objects.create(
                    usuario=request.user,
                    alias=request.POST.get('alias', 'Casa'),
                    direccion=nueva_dir,
                    ciudad=nueva_ciudad,
                    region=nueva_region,
                    principal=not direcciones.exists()
                )

        
        # Validar RUT y preferencias de entrega antes de continuar
        if not rut:
            messages.error(request, 'Debes ingresar tu RUT para continuar con el pedido.')
            return redirect('finalizar_pedido_publico')

        if not dias_seleccionados:
            messages.error(request, 'Debes seleccionar al menos un día disponible para la entrega.')
            return redirect('finalizar_pedido_publico')

        # Validar TODO el carrito antes de crear la solicitud
        errores_stock = []
        for item in carrito_items:
            ok, disponible, msg_stock = verificar_stock(item.producto, item.cantidad)
            if not ok:
                errores_stock.append(msg_stock)

        if errores_stock:
            for msg_stock in errores_stock:
                messages.error(request, msg_stock)
            messages.warning(request, 'Ajusta las cantidades en tu carrito antes de continuar. Para ir al carrito aprieta "← Volver".')
            return redirect('finalizar_pedido_publico')

        # Crear solicitud (solo si todo tiene stock)
        with transaction.atomic():
            solicitud = SolicitudPublico.objects.create(
                usuario=request.user,
                direccion=direccion,
                horario=perfil.horario_preferido,
                dias=perfil.dias_disponibles,
                observaciones=perfil.observaciones_entrega,
                total=carrito_neto,
            )
            for item in carrito_items:
                detalle = DetalleSolicitudPublico.objects.create(
                    solicitud=solicitud,
                    producto=item.producto,
                    cantidad=item.cantidad,
                    precio_unitario=item.precio_unitario,
                )
                # Descontar stock usando FIFO
                uso_lotes, faltante = descontar_stock_fifo(item.producto, item.cantidad)
                for lote, cant_usada in uso_lotes:
                    DetalleLoteVenta.objects.create(
                        lote=lote, cantidad=cant_usada, detalle_solicitud=detalle,
                    )
                if faltante > 0:
                    # Red de seguridad; no debería ocurrir tras la validación previa
                    messages.warning(request,
                        f'Atención: "{item.producto.nombre}" tuvo una diferencia de stock '
                        f'(faltaron {faltante} unidades). Revisa el inventario.')

            carrito_items.delete()

        # Redirige a la pantalla de selección de medio de pago (Webpay, Mercado Pago, etc.)
        return redirect('seleccionar_medio_pago', solicitud_id=solicitud.pk)

    
    # Marcar cada item con su estado de stock y avisar de inmediato si falta algo
    hay_problema_stock = False
    for item in carrito_items:
        ok, disponible, msg_stock = verificar_stock(item.producto, item.cantidad)
        item.sin_stock_suficiente = not ok
        item.stock_disponible = disponible
        if not ok:
            hay_problema_stock = True
            messages.error(request, msg_stock)

    if hay_problema_stock:
        messages.warning(request, 'Ajusta las cantidades en tu carrito antes de continuar. Para ir al carrito aprieta "← Volver".')


    return render(request, 'finalizar_pedido_publico.html', {
        'carrito_items': carrito_items,
        'carrito_neto':  carrito_neto,
        'carrito_iva':   carrito_iva,
        'carrito_total': carrito_total,
        'perfil':        perfil,
        'direcciones':   direcciones,
    })
   
# ── Selección de medio de pago ────────────────────────────────────────────────
@login_required
def seleccionar_medio_pago(request, solicitud_id):
    solicitud = get_object_or_404(
        SolicitudPublico, pk=solicitud_id, usuario=request.user
    )

    if request.method == 'POST':
        medio = request.POST.get('medio')

        if medio == 'webpay':
            # ── Generar token único para identificar esta solicitud al volver del pago ──
            token = secrets.token_hex(16)
            solicitud.token_pago = token
            solicitud.save()

            # ── Armar la URL de retorno (donde la API de pago nos devuelve al cliente) ──
            return_url = request.build_absolute_uri(
                reverse('confirmar_pago_publico')
            )

            # ── Armar la URL de la API de pago (puerto 8001) con los datos necesarios ──
            params = {
                'monto':      solicitud.total_con_iva,
                'token':      token,
                'return_url': return_url,
            }
            url_pago = 'http://127.0.0.1:8001/pagar/?' + urlencode(params)
            return redirect(url_pago)

        # Otros medios de pago: todavía no implementados
        messages.info(request, 'Ese medio de pago estará disponible pronto. Por ahora puedes pagar con Webpay.')
        return redirect('seleccionar_medio_pago', solicitud_id=solicitud.pk)

    return render(request, 'seleccionar_medio_pago.html', {
        'solicitud': solicitud,
    })

# ── Confirmación de pago (retorno desde la API de pago simulada) ─────────────
@login_required
def confirmar_pago_publico(request):
    token = request.GET.get('token')
    resultado = request.GET.get('resultado')  # 'aprobado' o 'rechazado'

    solicitud = get_object_or_404(
        SolicitudPublico, token_pago=token, usuario=request.user
    )

    if resultado == 'aprobado':
        solicitud.pago_estado = 'aprobado'
        solicitud.save()
        messages.success(
            request,
            f'¡Pago aprobado! Tu pedido #{solicitud.pk} fue confirmado. 🎉'
        )
    else:
        solicitud.pago_estado = 'rechazado'
        solicitud.estado = 'cancelado'
        solicitud.save()
        messages.error(
            request,
            f'El pago de tu pedido #{solicitud.pk} fue rechazado y el pedido fue cancelado. '
            'Puedes volver a pedirlo desde "Mi historial de compras".'
        )

    return redirect('mi_cuenta')

# ── HELPERS DE ROL ────────────────────────────────────────────────────────────
def es_adm(user):
    return user.is_authenticated and (
        user.is_superuser or user.groups.filter(name='ADM').exists()
    )

def es_gestor(user):
    return user.is_authenticated and user.groups.filter(name='Gestor').exists()


# ── PANEL ADM ─────────────────────────────────────────────────────────────────
from django.contrib.auth.models import User, Group

@login_required
def adm_dashboard(request):
    if not es_adm(request.user):
        return redirect('index')
    total_usuarios  = User.objects.count()
    total_productos = Producto.objects.count()
    total_pedidos   = Pedido.objects.count() + SolicitudPublico.objects.count()
    pendientes      = Pedido.objects.filter(estado='pendiente').count()
    return render(request, 'adm/dashboard.html', {
        'total_usuarios':  total_usuarios,
        'total_productos': total_productos,
        'total_pedidos':   total_pedidos,
        'pendientes':      pendientes,
    })


@login_required
def adm_lista_usuarios(request):
    if not es_adm(request.user):
        return redirect('index')
    clinicas = User.objects.filter(clinica__isnull=False).select_related('clinica')
    publico  = User.objects.filter(clinica__isnull=True, is_superuser=False)
    grupos   = Group.objects.all()
    return render(request, 'adm/lista_usuarios.html', {
        'clinicas': clinicas,
        'publico':  publico,
        'grupos':   grupos,
    })


@login_required
def adm_crear_usuario(request):
    if not es_adm(request.user):
        return redirect('index')
    if request.method == 'POST':
        username  = request.POST['username']
        email     = request.POST['email']
        password  = request.POST['password']
        first_name = request.POST.get('first_name', '')
        last_name  = request.POST.get('last_name', '')
        grupo_id   = request.POST.get('grupo')
        user = User.objects.create_user(
            username=username, email=email, password=password,
            first_name=first_name, last_name=last_name
        )
        if grupo_id:
            grupo = get_object_or_404(Group, id=grupo_id)
            user.groups.add(grupo)
        messages.success(request, f'Usuario {username} creado exitosamente.')
        return redirect('adm_lista_usuarios')
    grupos = Group.objects.all()
    return render(request, 'adm/crear_usuario.html', {'grupos': grupos})


@login_required
def adm_editar_usuario(request, id):
    if not es_adm(request.user):
        return redirect('index')
    usuario = get_object_or_404(User, id=id)
    if request.method == 'POST':
        usuario.first_name = request.POST.get('first_name', '')
        usuario.last_name  = request.POST.get('last_name', '')
        usuario.email      = request.POST.get('email', '')
        usuario.is_active  = request.POST.get('is_active') == 'on'
        grupo_id = request.POST.get('grupo')
        usuario.groups.clear()
        if grupo_id:
            grupo = get_object_or_404(Group, id=grupo_id)
            usuario.groups.add(grupo)
        usuario.save()
        messages.success(request, f'Usuario {usuario.username} actualizado.')
        return redirect('adm_lista_usuarios')
    grupos = Group.objects.all()
    return render(request, 'adm/editar_usuario.html', {
        'usuario': usuario,
        'grupos':  grupos,
    })


@login_required
def adm_eliminar_usuario(request, id):
    if not es_adm(request.user):
        return redirect('index')
    usuario = get_object_or_404(User, id=id)
    usuario.delete()
    messages.success(request, 'Usuario eliminado.')
    return redirect('adm_lista_usuarios')

# ── MANTENEDOR DE PRODUCTOS (ADM) ─────────────────────────────────────────────
@login_required
def adm_lista_productos(request):
    if not es_adm(request.user):
        return redirect('index')
    
    categoria_id = request.GET.get('categoria', '')
    productos_qs = Producto.objects.all().select_related('categoria')
    
    if categoria_id:
        productos_qs = productos_qs.filter(categoria_id=categoria_id)
    
    productos = []
    for p in productos_qs:
        p.utilidad_pub = p.precio - p.costo
        p.utilidad_b2d = p.get_precio_b2d() - p.costo
        productos.append(p)
    
    categorias = Categoria.objects.filter(activo=True).order_by('nombre')
    categoria_seleccionada = get_object_or_404(Categoria, id=categoria_id) if categoria_id else None
    
    return render(request, 'adm/lista_productos.html', {
        'productos':             productos,
        'categorias':            categorias,
        'categoria_id':          categoria_id,
        'categoria_seleccionada': categoria_seleccionada,
    })


def adm_crear_producto(request):
    if not es_adm(request.user):
        return redirect('index')
    if request.method == 'POST':
        nombre      = request.POST['nombre']
        marca       = request.POST.get('marca', '')
        categoria_id = request.POST.get('categoria')
        descripcion = request.POST.get('descripcion', '')
        activo      = request.POST.get('activo') == 'on'
        destacado   = request.POST.get('destacado') == 'on'

        if not categoria_id:
            messages.error(request, 'Debes seleccionar una categoría para el producto.')
            return redirect('adm_crear_producto')

        categoria = get_object_or_404(Categoria, id=categoria_id)

        Producto.objects.create(
            nombre=nombre, marca=marca, precio=0,
            costo=0, categoria=categoria,
            descripcion=descripcion, stock=0,
            activo=activo, destacado=destacado
        )
        messages.success(request, f'Producto "{nombre}" creado. Recuerda asignarle un precio en "Precios" y registrar su stock con una compra.')
        return redirect('adm_lista_productos')

    categorias = Categoria.objects.all()
    return render(request, 'adm/crear_producto.html', {'categorias': categorias})
     

@login_required
def adm_editar_producto(request, id):
    if not es_adm(request.user):
        return redirect('index')
    producto = get_object_or_404(Producto, id=id)
    if request.method == 'POST':

        # ── Validación precio ─────────────────────────────────────────
        try:
            nuevo_precio = int(request.POST.get('precio', producto.precio))
        except ValueError:
            messages.error(request, 'El precio debe ser un número válido.')
            categorias = Categoria.objects.all()
            historial  = producto.historial_precios.all()[:5]
            return render(request, 'adm/editar_producto.html', {
                'producto': producto, 'categorias': categorias, 'historial': historial
            })

        if nuevo_precio <= 0:
            messages.error(request, 'El precio debe ser mayor a 0.')
            categorias = Categoria.objects.all()
            historial  = producto.historial_precios.all()[:5]
            return render(request, 'adm/editar_producto.html', {
                'producto': producto, 'categorias': categorias, 'historial': historial
            })
        # ─────────────────────────────────────────────────────────────

        nuevo_costo  = int(request.POST.get('costo', producto.costo))

        # Guardar historial si cambia precio o costo
        if nuevo_precio != producto.precio or nuevo_costo != producto.costo:
            HistorialPrecio.objects.create(
                producto        = producto,
                precio_anterior = producto.precio,
                precio_nuevo    = nuevo_precio,
                costo_anterior  = producto.costo,
                costo_nuevo     = nuevo_costo,
                cambiado_por    = request.user,
                motivo          = request.POST.get('motivo', '')
            )

        producto.nombre          = request.POST['nombre']
        producto.marca           = request.POST.get('marca', '')
        producto.precio          = nuevo_precio
        producto.costo           = nuevo_costo
        producto.descripcion     = request.POST.get('descripcion', '')
        producto.activo          = request.POST.get('activo') == 'on'
        producto.destacado       = request.POST.get('destacado') == 'on'
        producto.pronto_a_vencer = request.POST.get('pronto_a_vencer') == 'on'
        cat_id = request.POST.get('categoria')
        producto.categoria = get_object_or_404(Categoria, id=cat_id) if cat_id else None
        if 'imagen' in request.FILES:
            producto.imagen = request.FILES['imagen']
        producto.save()
        messages.success(request, f'Producto "{producto.nombre}" actualizado.')
        return redirect('adm_lista_productos')

    categorias = Categoria.objects.all()
    historial  = producto.historial_precios.all()[:5]
    return render(request, 'adm/editar_producto.html', {
        'producto':   producto,
        'categorias': categorias,
        'historial':  historial,
    })


@login_required
def adm_eliminar_producto(request, id):
    if not es_adm(request.user):
        return redirect('index')
    producto = get_object_or_404(Producto, id=id)

    if request.method == 'POST':
        nombre = producto.nombre
        producto.delete()
        messages.success(request, f'Producto "{nombre}" eliminado.')
        return redirect('adm_lista_productos')

    return render(request, 'adm/eliminar_producto.html', {'producto': producto})

# ── GESTIÓN DE PRECIOS ────────────────────────────────────────────────────────

@login_required
def adm_precios_productos(request):
    if not es_adm(request.user):
        return redirect('index')

    productos = Producto.objects.filter(stock__gt=0).select_related('categoria').order_by('nombre')

    # Para cada producto, calculamos el costo del lote FIFO vigente
    # y el costo promedio ponderado de todos los lotes con stock.
    for p in productos:
        lotes_vivos = list(
            p.lotes.filter(cantidad_disponible__gt=0).order_by('fecha_vencimiento')
        )
        if lotes_vivos:
            # El primer lote (el que vence antes) es el que se vende ahora (FIFO)
            p.costo_lote_fifo = lotes_vivos[0].costo_unitario_con_iva

            # Promedio ponderado por cantidad disponible
            total_unidades = sum(l.cantidad_disponible for l in lotes_vivos)
            total_costo    = sum(l.costo_unitario_con_iva * l.cantidad_disponible for l in lotes_vivos)
            p.costo_promedio = round(total_costo / total_unidades) if total_unidades else None
        else:
            p.costo_lote_fifo  = None
            p.costo_promedio   = None

    return render(request, 'adm/precios_productos.html', {'productos': productos})


@login_required
def adm_editar_precio(request, id):
    if not es_adm(request.user):
        return redirect('index')
    producto = get_object_or_404(Producto, id=id)
    if request.method == 'POST':
        nuevo_precio  = int(request.POST.get('precio', producto.precio))
        nuevo_costo   = int(request.POST.get('costo', producto.costo))
        nuevo_b2d     = request.POST.get('precio_b2d')
        nuevo_volumen = request.POST.get('precio_volumen')
        nueva_cant    = request.POST.get('cantidad_minima_volumen')
        motivo        = request.POST.get('motivo', '')

        if nuevo_precio != producto.precio or nuevo_costo != producto.costo:
            HistorialPrecio.objects.create(
                producto        = producto,
                precio_anterior = producto.precio,
                precio_nuevo    = nuevo_precio,
                costo_anterior  = producto.costo,
                costo_nuevo     = nuevo_costo,
                cambiado_por    = request.user,
                motivo          = motivo,
            )

        producto.precio                  = nuevo_precio
        producto.costo                   = nuevo_costo
        producto.precio_b2d              = int(nuevo_b2d) if nuevo_b2d else None
        producto.precio_volumen          = int(nuevo_volumen) if nuevo_volumen else None
        producto.cantidad_minima_volumen = int(nueva_cant) if nueva_cant else None
        producto.save()
        messages.success(request, f'Precios de "{producto.nombre}" actualizados.')
        return redirect('adm_precios_productos')

    # Costo del lote FIFO vigente y promedio ponderado (referencia, igual que en la tabla)
    lotes_vivos = list(
        producto.lotes.filter(cantidad_disponible__gt=0).order_by('fecha_vencimiento')
    )
    if lotes_vivos:
        costo_lote_fifo = lotes_vivos[0].costo_unitario_con_iva
        total_unidades  = sum(l.cantidad_disponible for l in lotes_vivos)
        total_costo     = sum(l.costo_unitario_con_iva * l.cantidad_disponible for l in lotes_vivos)
        costo_promedio  = round(total_costo / total_unidades) if total_unidades else None
    else:
        costo_lote_fifo = None
        costo_promedio  = None

    precio_pav = round(producto.costo * 1.19) if producto.costo else None

    historial = producto.historial_precios.all()[:10]
    return render(request, 'adm/editar_precio.html', {
        'producto':        producto,
        'historial':       historial,
        'costo_lote_fifo': costo_lote_fifo,
        'costo_promedio':  costo_promedio,
        'precio_pav':      precio_pav,
    })

# ── MANTENEDOR DE CATEGORÍAS (ADM) ────────────────────────────────────────────
@login_required
def adm_lista_categorias(request):
    if not es_adm(request.user):
        return redirect('index')
    categorias = Categoria.objects.all().order_by('nombre')
    return render(request, 'adm/lista_categorias.html', {'categorias': categorias})


@login_required
def adm_crear_categoria(request):
    if not es_adm(request.user):
        return redirect('index')
    if request.method == 'POST':
        nombre      = request.POST['nombre']
        descripcion = request.POST.get('descripcion', '')
        orden       = request.POST.get('orden', 0)
        activo      = request.POST.get('activo') == 'on'
        Categoria.objects.create(
            nombre=nombre,
            descripcion=descripcion,
            orden=orden,
            activo=activo
        )
        messages.success(request, f'Categoría "{nombre}" creada exitosamente.')
        return redirect('adm_lista_categorias')
    return render(request, 'adm/crear_categoria.html')


@login_required
def adm_editar_categoria(request, id):
    if not es_adm(request.user):
        return redirect('index')
    categoria = get_object_or_404(Categoria, id=id)
    if request.method == 'POST':
        categoria.nombre      = request.POST['nombre']
        categoria.descripcion = request.POST.get('descripcion', '')
        categoria.orden       = request.POST.get('orden', 0)
        categoria.activo      = request.POST.get('activo') == 'on'
        categoria.save()
        messages.success(request, f'Categoría "{categoria.nombre}" actualizada.')
        return redirect('adm_lista_categorias')
    return render(request, 'adm/editar_categoria.html', {'categoria': categoria})


@login_required
def adm_eliminar_categoria(request, id):
    if not es_adm(request.user):
        return redirect('index')
    categoria = get_object_or_404(Categoria, id=id)
    nombre = categoria.nombre
    categoria.delete()
    messages.success(request, f'Categoría "{nombre}" eliminada.')
    return redirect('adm_lista_categorias') 

# ── MANTENEDOR DE MENSAJES (ADM) ──────────────────────────────────────────────
@login_required
def adm_lista_mensajes(request):
    if not es_adm(request.user) and not es_gestor(request.user):
        return redirect('index')
    estado = request.GET.get('estado', 'todos')
    busqueda = request.GET.get('q', '').strip()
    fecha_desde = request.GET.get('desde', '')
    fecha_hasta = request.GET.get('hasta', '')

    mensajes = ConsultaContacto.objects.select_related('tomado_por', 'resuelto_por').order_by('-fecha')

    if estado == 'pendiente':
        mensajes = mensajes.filter(estado_caso='pendiente')
    elif estado == 'en_proceso':
        mensajes = mensajes.filter(estado_caso='en_proceso')
    elif estado == 'resuelto':
        mensajes = mensajes.filter(estado_caso='resuelto')

    if busqueda:
        mensajes = mensajes.filter(
            Q(nombre__icontains=busqueda) |
            Q(email__icontains=busqueda) |
            Q(mensaje__icontains=busqueda) |
            Q(tomado_por__username__icontains=busqueda) |
            Q(tomado_por__first_name__icontains=busqueda) |
            Q(resuelto_por__username__icontains=busqueda) |
            Q(resuelto_por__first_name__icontains=busqueda)
        )

    if fecha_desde:
        mensajes = mensajes.filter(fecha__date__gte=fecha_desde)
    if fecha_hasta:
        mensajes = mensajes.filter(fecha__date__lte=fecha_hasta)

    return render(request, 'adm/lista_mensajes.html', {
        'mensajes':    mensajes,
        'estado':      estado,
        'busqueda':    busqueda,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
    })


@login_required
def adm_tomar_mensaje(request, id):
    if not es_adm(request.user) and not es_gestor(request.user):
        return redirect('index')
    mensaje = get_object_or_404(ConsultaContacto, id=id)
    if request.method == 'POST':
        mensaje.estado_caso  = 'en_proceso'
        mensaje.tomado_por   = request.user
        mensaje.fecha_tomado = timezone.now()
        mensaje.save()
    return redirect('adm_resolver_mensaje', id=id)


@login_required
def adm_resolver_mensaje(request, id):
    if not es_adm(request.user) and not es_gestor(request.user):
        return redirect('index')
    mensaje = get_object_or_404(ConsultaContacto, id=id)
    notas   = mensaje.notas.all()

    bloqueado = (
        mensaje.estado_caso == 'en_proceso' and
        mensaje.tomado_por and
        mensaje.tomado_por != request.user
    )

    if request.method == 'POST':
        accion = request.POST.get('accion')

        if accion == 'tomar':
            mensaje.estado_caso  = 'en_proceso'
            mensaje.tomado_por   = request.user
            mensaje.fecha_tomado = timezone.now()
            mensaje.save()
            messages.success(request, 'Caso asignado. Se abrirá el email.')
            bloqueado = False

        elif accion == 'nota':
            canal = request.POST.get('canal', 'email')
            nota  = request.POST.get('nota', '').strip()
            if nota:
                NotaSeguimiento.objects.create(
                    mensaje = mensaje,
                    autor   = request.user,
                    canal   = canal,
                    nota    = nota,
                )
                messages.success(request, 'Nota agregada. ✅')

        elif accion == 'resolver':
            mensaje.estado_caso      = 'resuelto'
            mensaje.leido            = True
            mensaje.resuelto_por     = request.user
            mensaje.fecha_resolucion = timezone.now()
            mensaje.nota_resolucion  = request.POST.get('nota_resolucion', '')
            mensaje.save()
            # Guardar nota final
            NotaSeguimiento.objects.create(
                mensaje = mensaje,
                autor   = request.user,
                canal   = 'otro',
                nota    = f"Caso resuelto. {mensaje.nota_resolucion}",
            )
            messages.success(request, f'Caso de {mensaje.nombre} resuelto.')
            return redirect('adm_lista_mensajes')

    return render(request, 'adm/resolver_mensaje.html', {
        'mensaje':   mensaje,
        'notas':     notas,
        'bloqueado': bloqueado,
    })


# ── PANEL GESTOR ──────────────────────────────────────────────────────────────
def es_gestor_o_adm(user):
    return es_adm(user) or es_gestor(user)


@login_required
def gestor_dashboard(request):
    if not es_gestor_o_adm(request.user):
        return redirect('index')
    total_productos  = Producto.objects.count()
    total_categorias = Categoria.objects.count()
    total_mensajes   = ConsultaContacto.objects.filter(estado_caso='pendiente').count()
    return render(request, 'gestor/dashboard.html', {
        'total_productos':  total_productos,
        'total_categorias': total_categorias,
        'total_mensajes':   total_mensajes,
    })


@login_required
def gestor_lista_productos(request):
    if not es_gestor_o_adm(request.user):
        return redirect('index')
    categoria_id = request.GET.get('categoria', '')
    productos_qs = Producto.objects.all().select_related('categoria')
    if categoria_id:
        productos_qs = productos_qs.filter(categoria_id=categoria_id)
    categorias = Categoria.objects.filter(activo=True).order_by('nombre')
    categoria_seleccionada = get_object_or_404(Categoria, id=categoria_id) if categoria_id else None
    return render(request, 'gestor/lista_productos.html', {
        'productos':              productos_qs,
        'categorias':             categorias,
        'categoria_id':           categoria_id,
        'categoria_seleccionada': categoria_seleccionada,
    })


@login_required
def gestor_crear_producto(request):
    if not es_gestor_o_adm(request.user):
        return redirect('index')
    if request.method == 'POST':
        nombre      = request.POST['nombre']
        marca       = request.POST.get('marca', '')
        descripcion = request.POST.get('descripcion', '')
        activo      = request.POST.get('activo') == 'on'
        destacado   = request.POST.get('destacado') == 'on'
        cat_id      = request.POST.get('categoria')
        categoria   = get_object_or_404(Categoria, id=cat_id) if cat_id else None
        Producto.objects.create(
            nombre=nombre, marca=marca, descripcion=descripcion,
            activo=activo, destacado=destacado,
            categoria=categoria, precio=0, costo=0
        )
        messages.success(request, f'Producto "{nombre}" creado. Recuerda agregar el precio.')
        return redirect('gestor_lista_productos')
    categorias = Categoria.objects.all()
    return render(request, 'gestor/crear_producto.html', {'categorias': categorias})


@login_required
def gestor_editar_producto(request, id):
    if not es_gestor_o_adm(request.user):
        return redirect('index')
    producto = get_object_or_404(Producto, id=id)
    if request.method == 'POST':
        producto.nombre         = request.POST['nombre']
        producto.marca          = request.POST.get('marca', '')
        producto.descripcion    = request.POST.get('descripcion', '')
        producto.destacado      = request.POST.get('destacado') == 'on'
        producto.pronto_a_vencer = request.POST.get('pronto_a_vencer') == 'on'
        cat_id = request.POST.get('categoria')
        producto.categoria = get_object_or_404(Categoria, id=cat_id) if cat_id else None
        if 'imagen' in request.FILES:
            producto.imagen = request.FILES['imagen']
        producto.save()
        messages.success(request, f'Producto "{producto.nombre}" actualizado.')
        return redirect('gestor_lista_productos')
    categorias = Categoria.objects.all()
    return render(request, 'gestor/editar_producto.html', {
        'producto':   producto,
        'categorias': categorias,
    })


@login_required
def gestor_eliminar_producto(request, id):
    if not es_gestor_o_adm(request.user):
        return redirect('index')
    producto = get_object_or_404(Producto, id=id)
    producto.delete()
    messages.success(request, 'Producto eliminado.')
    return redirect('gestor_lista_productos')


@login_required
def gestor_lista_categorias(request):
    if not es_gestor_o_adm(request.user):
        return redirect('index')
    categorias = Categoria.objects.all().order_by('nombre')
    return render(request, 'gestor/lista_categorias.html', {'categorias': categorias})


@login_required
def gestor_crear_categoria(request):
    if not es_gestor_o_adm(request.user):
        return redirect('index')
    if request.method == 'POST':
        nombre      = request.POST['nombre']
        descripcion = request.POST.get('descripcion', '')
        orden       = request.POST.get('orden', 0)
        activo      = request.POST.get('activo') == 'on'
        Categoria.objects.create(nombre=nombre, descripcion=descripcion,
                                  orden=orden, activo=activo)
        messages.success(request, f'Categoría "{nombre}" creada.')
        return redirect('gestor_lista_categorias')
    return render(request, 'gestor/crear_categoria.html')


@login_required
def gestor_editar_categoria(request, id):
    if not es_gestor_o_adm(request.user):
        return redirect('index')
    categoria = get_object_or_404(Categoria, id=id)
    if request.method == 'POST':
        categoria.nombre      = request.POST['nombre']
        categoria.descripcion = request.POST.get('descripcion', '')
        categoria.orden       = request.POST.get('orden', 0)
        categoria.activo      = request.POST.get('activo') == 'on'
        categoria.save()
        messages.success(request, f'Categoría "{categoria.nombre}" actualizada.')
        return redirect('gestor_lista_categorias')
    return render(request, 'gestor/editar_categoria.html', {'categoria': categoria})


@login_required
def gestor_eliminar_categoria(request, id):
    if not es_gestor_o_adm(request.user):
        return redirect('index')
    categoria = get_object_or_404(Categoria, id=id)
    categoria.delete()
    messages.success(request, 'Categoría eliminada.')
    return redirect('gestor_lista_categorias')


@login_required
def gestor_mensajes(request):
    if not es_gestor_o_adm(request.user):
        return redirect('index')
    estado   = request.GET.get('estado', 'todos')
    mensajes = ConsultaContacto.objects.all().order_by('-fecha')
    if estado == 'pendiente':
        mensajes = mensajes.filter(estado_caso='pendiente')
    elif estado == 'en_proceso':
        mensajes = mensajes.filter(estado_caso='en_proceso')
    elif estado == 'resuelto':
        mensajes = mensajes.filter(estado_caso='resuelto')
    return render(request, 'adm/lista_mensajes.html', {
        'mensajes': mensajes,
        'estado':   estado,
    })

# ── COMPRAS A PROVEEDORES (ADM) ───────────────────────────────────────────────
@login_required
def adm_lista_compras(request):
    if not es_adm(request.user):
        return redirect('index')
    compras = CompraProveedor.objects.all().prefetch_related('lotes__producto')
    return render(request, 'adm/compras/lista_compras.html', {'compras': compras})


@login_required
def adm_detalle_compra(request, id):
    if not es_adm(request.user):
        return redirect('index')
    compra = get_object_or_404(CompraProveedor, id=id)
    lotes  = compra.lotes.all().select_related('producto')
    return render(request, 'adm/compras/detalle_compra.html', {
        'compra': compra, 'lotes': lotes,
    })


@login_required
def adm_nueva_compra(request):
    if not es_adm(request.user):
        return redirect('index')

    productos = Producto.objects.all().order_by('nombre')

    # Lista de proveedores ya usados, para el autocompletado
    proveedores = (CompraProveedor.objects
                   .exclude(proveedor='')
                   .values_list('proveedor', flat=True)
                   .distinct())

    if request.method == 'POST':
        tipo           = request.POST.get('tipo', 'compra')
        proveedor      = request.POST.get('proveedor', '')
        numero_factura = request.POST.get('numero_factura', '')
        fecha_compra   = request.POST.get('fecha_compra')
        flete_total    = int(request.POST.get('flete_total') or 0)
        motivo         = request.POST.get('motivo', '')

        # Validación: stock inicial / ajuste requiere motivo
        if tipo == 'inicial' and not motivo.strip():
            messages.error(request, 'Debes indicar un motivo para el stock inicial o ajuste.')
            return render(request, 'adm/compras/nueva_compra.html', {
                'productos': productos, 'proveedores': proveedores,
            })

        # Validación: compra con factura requiere número de factura
        if tipo == 'compra' and not numero_factura.strip():
            messages.error(request, 'Debes indicar el número de factura para una compra.')
            return render(request, 'adm/compras/nueva_compra.html', {
                'productos': productos, 'proveedores': proveedores,
            })

        
        # Recoger las filas de productos (llegan como listas paralelas)
        producto_ids = request.POST.getlist('producto_id[]')
        lotes_nums   = request.POST.getlist('numero_lote[]')
        vencimientos = request.POST.getlist('fecha_vencimiento[]')
        no_vences    = request.POST.getlist('no_vence[]')
        cantidades   = request.POST.getlist('cantidad[]')
        costos       = request.POST.getlist('costo_unitario[]')

        if not producto_ids:
            messages.error(request, 'Debes agregar al menos un producto.')
            return render(request, 'adm/compras/nueva_compra.html', {
                'productos': productos, 'proveedores': proveedores,
            })

        # ── Validación: cada fila con datos completos necesita un producto_id válido ──
        nombres_producto = request.POST.getlist('nombre_producto_texto[]')
        for i in range(len(nombres_producto)):
            texto_escrito = nombres_producto[i].strip() if i < len(nombres_producto) else ''
            prod_id_fila = producto_ids[i] if i < len(producto_ids) else ''
            cantidad_fila_check = cantidades[i] if i < len(cantidades) else ''
            # Si escribiste algo en el buscador o una cantidad, pero no se resolvió un producto real
            if (texto_escrito or cantidad_fila_check) and not prod_id_fila:
                messages.error(request, f'El producto "{texto_escrito}" de la fila {i + 1} no existe en el catálogo. Crea el producto primero (botón "+ Producto nuevo") y vuelve a intentar.')
                return render(request, 'adm/compras/nueva_compra.html', {
                    'productos': productos, 'proveedores': proveedores,
                })

        # ── Validación: cada fila necesita N° de lote y (fecha de vencimiento O "no vence") ──
        for i, prod_id in enumerate(producto_ids):
            if not prod_id:
                continue
            cantidad_fila = int(cantidades[i] or 0) if i < len(cantidades) and cantidades[i] else 0
            if cantidad_fila <= 0:
                continue

            lote_num_fila = lotes_nums[i].strip() if i < len(lotes_nums) else ''
            if not lote_num_fila:
                messages.error(request, f'Falta el número de lote en la fila {i + 1}. Si no tienes uno, escribe "SIN_LOTE".')
                return render(request, 'adm/compras/nueva_compra.html', {
                    'productos': productos, 'proveedores': proveedores,
                })

            vencimiento_fila = vencimientos[i] if i < len(vencimientos) else ''
            no_vence_fila = no_vences[i] == '1' if i < len(no_vences) else False
            if not vencimiento_fila and not no_vence_fila:
                messages.error(request, f'Falta indicar la fecha de vencimiento en la fila {i + 1}, o marca la casilla "No vence" si el producto no vence.')
                return render(request, 'adm/compras/nueva_compra.html', {
                    'productos': productos, 'proveedores': proveedores,
                })

        compra = CompraProveedor.objects.create(
            tipo=tipo, proveedor=proveedor, numero_factura=numero_factura,
            fecha_compra=fecha_compra, flete_total=flete_total,
            motivo=motivo, registrado_por=request.user,
        )

        avisos_precio = []

        for i, prod_id in enumerate(producto_ids):
            if not prod_id:
                continue
            producto = get_object_or_404(Producto, id=prod_id)
            cantidad = int(cantidades[i] or 0)
            costo    = int(costos[i] or 0)
            if cantidad <= 0:
                continue

            no_vence_lote = no_vences[i] == '1' if i < len(no_vences) else False

            lote = LoteCompra.objects.create(
                compra=compra, producto=producto,
                numero_lote=lotes_nums[i] if i < len(lotes_nums) else '',
                fecha_vencimiento=vencimientos[i] if i < len(vencimientos) and vencimientos[i] else None,
                no_vence=no_vence_lote,
                cantidad=cantidad, costo_unitario=costo,
            )

            # Actualizar stock del producto
            producto.stock += cantidad

            # Aviso si el costo cambió respecto al costo actual del producto
            costo_con_iva = lote.costo_unitario_con_iva
            if costo > 0 and producto.costo and costo_con_iva != producto.costo:
                avisos_precio.append({
                    'producto': producto.nombre,
                    'costo_anterior': producto.costo,
                    'costo_nuevo': costo_con_iva,
                    'lote_id': lote.id,
                })
            producto.save()

        if avisos_precio:
            request.session['avisos_precio_compra'] = avisos_precio
            messages.warning(request, 'Algunos costos cambiaron. Revisa si quieres actualizar los precios de venta.')
        else:
            messages.success(request, 'Compra registrada correctamente. Stock actualizado.')

        return redirect('adm_detalle_compra', id=compra.id)

    return render(request, 'adm/compras/nueva_compra.html', {
        'productos': productos, 'proveedores': proveedores,
    })


@login_required
def adm_editar_compra(request, id):
    if not es_adm(request.user):
        return redirect('index')

    compra = get_object_or_404(CompraProveedor, id=id)
    productos = Producto.objects.all().order_by('nombre')
    proveedores = (CompraProveedor.objects
                   .exclude(proveedor='')
                   .values_list('proveedor', flat=True)
                   .distinct())
    lotes_actuales = compra.lotes.all().select_related('producto')

    if request.method == 'POST':
        compra.tipo           = request.POST.get('tipo', compra.tipo)
        compra.proveedor       = request.POST.get('proveedor', '')
        compra.numero_factura  = request.POST.get('numero_factura', '')
        compra.fecha_compra    = request.POST.get('fecha_compra')
        compra.flete_total     = int(request.POST.get('flete_total') or 0)
        compra.motivo          = request.POST.get('motivo', '')

        if compra.tipo == 'inicial' and not compra.motivo.strip():
            messages.error(request, 'Debes indicar un motivo para el stock inicial o ajuste.')
            return render(request, 'adm/compras/editar_compra.html', {
                'compra': compra, 'lotes_actuales': lotes_actuales,
                'productos': productos, 'proveedores': proveedores,
            })

        if compra.tipo == 'compra' and not compra.numero_factura.strip():
            messages.error(request, 'Debes indicar el número de factura para una compra.')
            return render(request, 'adm/compras/editar_compra.html', {
                'compra': compra, 'lotes_actuales': lotes_actuales,
                'productos': productos, 'proveedores': proveedores,
            })

        lote_ids     = request.POST.getlist('lote_id[]')
        producto_ids = request.POST.getlist('producto_id[]')
        lotes_nums   = request.POST.getlist('numero_lote[]')
        vencimientos = request.POST.getlist('fecha_vencimiento[]')
        no_vences    = request.POST.getlist('no_vence[]')
        cantidades   = request.POST.getlist('cantidad[]')
        costos       = request.POST.getlist('costo_unitario[]')

        # ── Validación: cada fila necesita N° de lote y (fecha O "no vence") ──
        for i, prod_id in enumerate(producto_ids):
            if not prod_id:
                continue
            cantidad_fila = int(cantidades[i] or 0) if i < len(cantidades) and cantidades[i] else 0
            if cantidad_fila <= 0:
                continue

            lote_num_fila = lotes_nums[i].strip() if i < len(lotes_nums) else ''
            if not lote_num_fila:
                messages.error(request, f'Falta el número de lote en la fila {i + 1}. Si no tienes uno, escribe "SIN_LOTE".')
                return render(request, 'adm/compras/editar_compra.html', {
                    'compra': compra, 'lotes_actuales': lotes_actuales,
                    'productos': productos, 'proveedores': proveedores,
                })

            vencimiento_fila = vencimientos[i] if i < len(vencimientos) else ''
            no_vence_fila = no_vences[i] == '1' if i < len(no_vences) else False
            if not vencimiento_fila and not no_vence_fila:
                messages.error(request, f'Falta indicar la fecha de vencimiento en la fila {i + 1}, o marca "No vence".')
                return render(request, 'adm/compras/editar_compra.html', {
                    'compra': compra, 'lotes_actuales': lotes_actuales,
                    'productos': productos, 'proveedores': proveedores,
                })

        compra.save()

        # ── Actualizar cada lote existente ──
        for i, lote_id in enumerate(lote_ids):
            if not lote_id:
                continue
            lote = get_object_or_404(LoteCompra, id=lote_id, compra=compra)
            producto = lote.producto

            tenia_ventas = lote.cantidad_disponible < lote.cantidad
            cantidad_vieja = lote.cantidad

            lote.numero_lote = lotes_nums[i] if i < len(lotes_nums) else lote.numero_lote
            lote.fecha_vencimiento = vencimientos[i] if i < len(vencimientos) and vencimientos[i] else None
            lote.no_vence = no_vences[i] == '1' if i < len(no_vences) else False
            lote.costo_unitario = int(costos[i] or 0) if i < len(costos) and costos[i] else lote.costo_unitario

            if not tenia_ventas:
                # Sin ventas: se puede ajustar cantidad libremente
                cantidad_nueva = int(cantidades[i] or 0) if i < len(cantidades) and cantidades[i] else cantidad_vieja
                diferencia = cantidad_nueva - cantidad_vieja
                lote.cantidad = cantidad_nueva
                lote.cantidad_disponible = cantidad_nueva
                producto.stock = max(0, producto.stock + diferencia)
                producto.save()
            # Si ya tenía ventas, la cantidad no se toca (el campo viene deshabilitado en el form)

            lote.save()

        messages.success(request, 'Compra actualizada correctamente.')
        return redirect('adm_detalle_compra', id=compra.id)

    return render(request, 'adm/compras/editar_compra.html', {
        'compra': compra, 'lotes_actuales': lotes_actuales,
        'productos': productos, 'proveedores': proveedores,
    })




# ── GESTIÓN DE PEDIDOS (ADM) ──────────────────────────────────────────────────
@login_required
def adm_lista_pedidos(request):
    if not es_adm(request.user):
        return redirect('index')

    import datetime
    pedidos_clinica = Pedido.objects.select_related('clinica').prefetch_related('detalles__producto')
    pedidos_publico = SolicitudPublico.objects.select_related('usuario', 'direccion').prefetch_related('detalles__producto')

    estado_filtro = request.GET.get('estado', '')
    busqueda      = request.GET.get('q', '').strip().lower()
    fecha_desde   = request.GET.get('desde', '')
    fecha_hasta   = request.GET.get('hasta', '')
    orden         = request.GET.get('orden', '-fecha')

    # Unificamos ambos tipos en una sola lista con info común
    lista_unificada = []

    for p in pedidos_clinica:
        if estado_filtro and p.estado != estado_filtro:
            continue
        lista_unificada.append({
            'tipo': 'clinica',
            'id': p.id,
            'cliente': p.clinica.nombre_clinica,
            'ciudad': p.clinica.ciudad,
            'total': p.total,
            'estado': p.estado,
            'estado_display': p.get_estado_display(),
            'fecha': p.fecha_creacion,
            'pago_estado': None,  # Clínicas: consignación, no aplica pago con tarjeta
        })

    for s in pedidos_publico:
        # Normalizamos 'en_proceso' a 'en_preparacion' solo para el filtro visual
        estado_normalizado = 'en_preparacion' if s.estado == 'en_proceso' else s.estado
        if estado_filtro and estado_normalizado != estado_filtro:
            continue
        ciudad = s.direccion.ciudad if s.direccion else '—'
        lista_unificada.append({
            'tipo': 'publico',
            'id': s.id,
            'cliente': s.usuario.get_full_name() or s.usuario.username,
            'ciudad': ciudad,
            'total': s.total,
            'estado': s.estado,
            'estado_display': s.get_estado_display(),
            'fecha': s.fecha_creacion,
            'pago_estado': s.pago_estado,
        })

    # Búsqueda de texto libre: tipo, cliente o ciudad
    if busqueda:
        lista_unificada = [
            x for x in lista_unificada
            if busqueda in x['cliente'].lower()
            or busqueda in x['ciudad'].lower()
            or busqueda in x['tipo'].lower()
        ]

    # Filtro por rango de fechas (solo el día, sin hora)
    if fecha_desde:
        lista_unificada = [x for x in lista_unificada if x['fecha'].date() >= datetime.date.fromisoformat(fecha_desde)]
    if fecha_hasta:
        lista_unificada = [x for x in lista_unificada if x['fecha'].date() <= datetime.date.fromisoformat(fecha_hasta)]

    # Ordenamiento según columna elegida
    campo = orden.lstrip('-')
    descendente = orden.startswith('-')
    if campo in ('tipo', 'cliente', 'ciudad', 'fecha', 'total'):
        lista_unificada.sort(key=lambda x: x[campo], reverse=descendente)
    else:
        lista_unificada.sort(key=lambda x: x['fecha'], reverse=True)

    return render(request, 'adm/lista_pedidos.html', {
        'pedidos': lista_unificada,
        'estado_filtro': estado_filtro,
        'estados': Pedido.ESTADO_CHOICES,
        'busqueda': busqueda,
        'fecha_desde': fecha_desde,
        'fecha_hasta': fecha_hasta,
        'orden': orden,
    })


@login_required
def adm_detalle_pedido(request, tipo, id):
    if not es_adm(request.user):
        return redirect('index')

    if tipo == 'clinica':
        pedido = get_object_or_404(Pedido, id=id)
        detalles = pedido.detalles.select_related('producto')
        cliente_nombre = pedido.clinica.nombre_clinica
        ciudad = pedido.clinica.ciudad
        estados_disponibles = Pedido.ESTADO_CHOICES
        historial = pedido.historial.select_related('cambiado_por').all()
    else:
        pedido = get_object_or_404(SolicitudPublico, id=id)
        detalles = pedido.detalles.select_related('producto')
        cliente_nombre = pedido.usuario.get_full_name() or pedido.usuario.username
        ciudad = pedido.direccion.ciudad if pedido.direccion else '—'
        estados_disponibles = SolicitudPublico.ESTADO_CHOICES
        historial = pedido.historial.select_related('cambiado_por').all()

    if request.method == 'POST':
        nuevo_estado = request.POST.get('estado')
        nota = request.POST.get('nota', '')
        pedido.estado = nuevo_estado
        pedido.save()

        if tipo == 'clinica':
            HistorialEstado.objects.create(
                pedido=pedido, estado=nuevo_estado, nota=nota,
                cambiado_por=request.user,
            )
        else:
            HistorialEstado.objects.create(
                solicitud=pedido, estado=nuevo_estado, nota=nota,
                cambiado_por=request.user,
            )

        messages.success(request, f'Estado actualizado a "{pedido.get_estado_display()}".')
        return redirect('adm_detalle_pedido', tipo=tipo, id=id)

    return render(request, 'adm/detalle_pedido.html', {
        'pedido': pedido, 'detalles': detalles, 'tipo': tipo,
        'cliente_nombre': cliente_nombre, 'ciudad': ciudad,
        'estados_disponibles': estados_disponibles, 'historial': historial,
    })

