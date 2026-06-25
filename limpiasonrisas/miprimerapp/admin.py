from django.contrib import admin
from django.core.mail import send_mail
from django.conf import settings
from .models import (Categoria, Producto, Clinica, Pedido,
                     DetallePedido, HistorialEstado, CarritoItem, ConsultaContacto,
                     PersonalClinica, StockMinimo, VentaStock,
                     AjusteInventario, ProductoSugerido)

EMAIL_TEMPLATES = {
    'en_preparacion': {
        'asunto': '🔧 Tu pedido está siendo preparado – LimpioSonrisas',
        'mensaje': lambda p, clinica: f"""Hola {clinica.nombre_contacto},

¡Buenas noticias! Tu pedido #{p.pk} ya está siendo preparado por nuestro equipo.

📦 Detalle del pedido:
{chr(10).join(f'  • {d.producto.nombre} x{d.cantidad} — ${d.subtotal:,}' for d in p.detalles.all())}

💰 Total sin IVA: ${p.total:,}
💰 Total con IVA: ${p.total_con_iva:,}

Te avisaremos cuando esté en camino.

Saludos,
Equipo LimpioSonrisas
limpiasonrisas.spa@gmail.com
""",
    },
    'enviado': {
        'asunto': '🚚 Tu pedido está en camino – LimpioSonrisas',
        'mensaje': lambda p, clinica: f"""Hola {clinica.nombre_contacto},

¡Tu pedido #{p.pk} ya está en camino! 🚚

📦 Detalle del pedido:
{chr(10).join(f'  • {d.producto.nombre} x{d.cantidad} — ${d.subtotal:,}' for d in p.detalles.all())}

💰 Total con IVA: ${p.total_con_iva:,}

Recibirás tu pedido pronto. Si tienes alguna duda escríbenos.

Saludos,
Equipo LimpioSonrisas
""",
    },
    'entregado': {
        'asunto': '✅ Tu pedido fue entregado – LimpioSonrisas',
        'mensaje': lambda p, clinica: f"""Hola {clinica.nombre_contacto},

Tu pedido #{p.pk} ha sido entregado exitosamente. ¡Gracias por tu confianza! 🦷

Si tienes algún problema con el pedido, contáctanos a limpiasonrisas.spa@gmail.com o al +569 6418 4917.

¡Hasta la próxima!

Equipo LimpioSonrisas
""",
    },
}


class DetallePedidoInline(admin.TabularInline):
    model  = DetallePedido
    extra  = 0
    fields = ['producto', 'cantidad', 'precio_unitario']
    readonly_fields = ['precio_unitario']


class HistorialEstadoInline(admin.TabularInline):
    model           = HistorialEstado
    extra           = 0
    readonly_fields = ['estado', 'fecha', 'nota']
    can_delete      = False


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display    = ['pk', 'clinica', 'estado', 'total', 'fecha_creacion']
    list_filter     = ['estado']
    list_editable   = ['estado']
    search_fields   = ['clinica__nombre_clinica']
    inlines         = [DetallePedidoInline, HistorialEstadoInline]
    readonly_fields = ['fecha_creacion', 'fecha_actualizacion', 'total']

    def save_model(self, request, obj, form, change):
        estado_anterior = None
        if obj.pk:
            estado_anterior = Pedido.objects.get(pk=obj.pk).estado
        super().save_model(request, obj, form, change)
        # Registrar cambio en historial y enviar email
        if estado_anterior != obj.estado and obj.estado in EMAIL_TEMPLATES:
            HistorialEstado.objects.create(pedido=obj, estado=obj.estado)
            tpl     = EMAIL_TEMPLATES[obj.estado]
            clinica = obj.clinica
            try:
                send_mail(
                    subject=tpl['asunto'],
                    message=tpl['mensaje'](obj, clinica),
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[clinica.email],
                    fail_silently=True,
                )
            except Exception:
                pass


@admin.register(Categoria)
class CategoriaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'icono', 'orden']
    ordering     = ['orden']


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display   = ['nombre', 'marca', 'categoria', 'precio', 'costo',
                      'precio_b2d', 'precio_volumen', 'cantidad_minima_volumen',
                      'pronto_a_vencer', 'stock', 'lugar_stock', 'lote',
                      'fecha_vencimiento', 'activo', 'destacado']
    list_filter    = ['categoria', 'activo', 'destacado', 'marca']
    search_fields  = ['nombre', 'marca', 'descripcion']
    list_editable  = ['precio', 'costo', 'precio_b2d', 'precio_volumen',
                      'cantidad_minima_volumen', 'pronto_a_vencer',
                      'stock', 'lugar_stock', 'lote', 'fecha_vencimiento',
                      'activo', 'destacado']
    fieldsets = (
        ('Información básica', {
            'fields': ('nombre', 'marca', 'categoria', 'descripcion', 'imagen', 'activo', 'destacado')
        }),
        ('Precios', {
            'fields': ('precio', 'costo', 'precio_b2d', 'precio_pack', 'unidades_pack'),
            'description': 'precio_b2d se calcula automáticamente (costo × 1.20) si se deja vacío.'
        }),
        ('Precio por volumen', {
            'fields': ('precio_volumen', 'cantidad_minima_volumen'),
            'description': 'Precio especial al comprar la cantidad mínima o más (mismo producto).'
        }),
        ('Pronto a vencer', {
            'fields': ('pronto_a_vencer',),
            'description': '⚠️ Al activar esto, el precio de venta y B2D cambia a costo × 1.19 automáticamente.'
        }),
        ('Inventario', {
            'fields': ('stock', 'lugar_stock', 'lote', 'fecha_vencimiento')
        }),
        ('Público objetivo', {
            'fields': ('edad_min', 'edad_max'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Clinica)
class ClinicaAdmin(admin.ModelAdmin):
    list_display  = ['nombre_clinica', 'region', 'ciudad', 'email',
                     'medio_contacto', 'verificada', 'fecha_inscripcion']
    list_filter   = ['region', 'verificada', 'medio_contacto']
    search_fields = ['nombre_clinica', 'rut', 'email']
    list_editable = ['verificada']
    fieldsets = (
        ('Datos de la clínica', {
            'fields': ('nombre_clinica', 'rut', 'direccion', 'ciudad', 'region',
                       'telefono', 'email', 'sitio_web', 'verificada')
        }),
        ('Contacto', {
            'fields': ('nombre_contacto', 'cargo_contacto', 'medio_contacto', 'dias_contacto')
        }),
        ('Preferencias de productos', {
            'fields': ('rotacion_estimada', 'productos_interes', 'producto_no_catalogo')
        }),
        ('Notas internas', {
            'fields': ('notas',),
            'classes': ('collapse',)
        }),
    )


@admin.register(ConsultaContacto)
class ConsultaContactoAdmin(admin.ModelAdmin):
    list_display  = ['nombre', 'email', 'es_clinica', 'tipo_consulta', 'leido', 'fecha']
    list_filter   = ['tipo_consulta', 'es_clinica', 'leido']
    list_editable = ['leido']
    search_fields = ['nombre', 'email', 'mensaje']


@admin.register(CarritoItem)
class CarritoItemAdmin(admin.ModelAdmin):
    list_display  = ['clinica', 'producto', 'cantidad', 'precio_unitario', 'agregado']
    list_filter   = ['clinica']

@admin.register(ProductoSugerido)
class ProductoSugeridoAdmin(admin.ModelAdmin):
    list_display  = ['nombre_producto', 'marca', 'clinica', 'cantidad_mensual', 'revisado', 'fecha']
    list_filter   = ['revisado']
    list_editable = ['revisado']
    search_fields = ['nombre_producto', 'marca', 'clinica__nombre_clinica']


@admin.register(VentaStock)
class VentaStockAdmin(admin.ModelAdmin):
    list_display  = ['clinica', 'producto', 'personal', 'cantidad', 'fecha']
    list_filter   = ['clinica']
    search_fields = ['clinica__nombre_clinica', 'producto__nombre']


@admin.register(AjusteInventario)
class AjusteInventarioAdmin(admin.ModelAdmin):
    list_display  = ['clinica', 'producto', 'cantidad', 'nota', 'fecha']
    search_fields = ['clinica__nombre_clinica', 'producto__nombre']