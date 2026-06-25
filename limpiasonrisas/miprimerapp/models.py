from django.db import models
import datetime
from django.contrib.auth.models import User
from django.conf import settings



# ── CATEGORÍAS DE PRODUCTOS ──────────────────────────────────────────────────
class Categoria(models.Model):
    nombre      = models.CharField(max_length=80)
    icono       = models.CharField(max_length=50, default='bi-box')
    descripcion = models.TextField(blank=True)
    orden       = models.PositiveSmallIntegerField(default=0)
    activo      = models.BooleanField(default=True)

    class Meta:
        verbose_name        = 'Categoría'
        verbose_name_plural = 'Categorías'
        ordering            = ['orden', 'nombre']

    def __str__(self):
        return self.nombre


# ── PRODUCTOS ────────────────────────────────────────────────────────────────
class Producto(models.Model):
    categoria     = models.ForeignKey(Categoria, on_delete=models.PROTECT,
                                      related_name='productos')
    nombre        = models.CharField(max_length=150)
    marca         = models.CharField(max_length=80, blank=True)
    descripcion   = models.TextField(blank=True)
    precio        = models.PositiveIntegerField(help_text='Precio público en CLP')
    costo         = models.PositiveIntegerField(default=0,
                                                help_text='Costo del producto (base para B2D)')
    precio_b2d    = models.PositiveIntegerField(null=True, blank=True,
                                                help_text='Precio canal dental (se calcula automáticamente si se deja vacío)')
    precio_pack   = models.PositiveIntegerField(null=True, blank=True)
    unidades_pack = models.PositiveSmallIntegerField(null=True, blank=True)
    lote              = models.CharField(max_length=50, blank=True, default='sin_lote')
    fecha_vencimiento = models.DateField(null=True, blank=True)
    imagen        = models.ImageField(upload_to='productos/', blank=True, null=True)
    # Precio por volumen
    precio_volumen          = models.PositiveIntegerField(null=True, blank=True,
                              help_text='Precio especial al comprar la cantidad mínima o más')
    cantidad_minima_volumen = models.PositiveSmallIntegerField(null=True, blank=True,
                              help_text='Cantidad mínima para activar el precio especial')
    # Pronto a vencer
    pronto_a_vencer = models.BooleanField(default=False,
                      help_text='Activa precio especial: costo × 1.19')
    stock         = models.PositiveIntegerField(default=0)
    lugar_stock   = models.CharField(max_length=80, blank=True)
    activo        = models.BooleanField(default=True)
    destacado     = models.BooleanField(default=False)
    edad_min      = models.PositiveSmallIntegerField(null=True, blank=True)
    edad_max      = models.PositiveSmallIntegerField(null=True, blank=True)
    creado        = models.DateTimeField(auto_now_add=True)
    actualizado   = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Producto'
        verbose_name_plural = 'Productos'
        ordering            = ['categoria', 'nombre']

    def __str__(self):
        return f"{self.nombre} – ${self.precio:,}"

    def get_precio_venta(self):
        """Precio público vigente (considera pronto a vencer)."""
        if self.pronto_a_vencer and self.costo:
            return round(self.costo * 1.19)
        return self.precio

    def get_precio_b2d(self):
        """Precio B2D vigente (considera pronto a vencer)."""
        if self.pronto_a_vencer and self.costo:
            return round(self.costo * 1.19)
        if self.precio_b2d:
            return self.precio_b2d
        margen = getattr(settings, 'MARGEN_B2D', 1.20)
        return round(self.costo * margen) if self.costo else self.precio

    def get_precio_volumen_b2d(self):
        """Precio B2D en volumen (aplica margen B2D sobre precio_volumen)."""
        if self.pronto_a_vencer and self.costo:
            return round(self.costo * 1.19)
        if self.precio_volumen:
            margen = getattr(settings, 'MARGEN_B2D', 1.20)
            costo  = self.costo or 0
            return round(costo * margen) if costo else self.precio_volumen
        return None

    def get_total_volumen(self):
        """Total a pagar comprando la cantidad mínima al precio volumen."""
        if self.precio_volumen and self.cantidad_minima_volumen:
            return self.precio_volumen * self.cantidad_minima_volumen
        return None

    def save(self, *args, **kwargs):
        if not self.precio_b2d and self.costo:
            margen = getattr(settings, 'MARGEN_B2D', 1.20)
            self.precio_b2d = round(self.costo * margen)
        super().save(*args, **kwargs)


# ── REGIONES ─────────────────────────────────────────────────────────────────
REGION_CHOICES = [
    ('RM',   'Región Metropolitana'),
    ('V',    'Valparaíso'),
    ('VI',   "O'Higgins"),
    ('VII',  'Maule'),
    ('VIII', 'Biobío'),
    ('IX',   'La Araucanía'),
    ('X',    'Los Lagos'),
    ('XIV',  'Los Ríos'),
    ('XV',   'Arica y Parinacota'),
    ('XVI',  'Ñuble'),
    ('I',    'Tarapacá'),
    ('II',   'Antofagasta'),
    ('III',  'Atacama'),
    ('IV',   'Coquimbo'),
]


# ── CLÍNICAS ──────────────────────────────────────────────────────────────────
class Clinica(models.Model):
    ROTACION_CHOICES = [
        ('baja',     'Baja – 1 a 5 unidades / semana'),
        ('media',    'Media – 6 a 20 unidades / semana'),
        ('alta',     'Alta – 21 a 50 unidades / semana'),
        ('muy_alta', 'Muy alta – más de 50 unidades / semana'),
    ]
    CONTACTO_CHOICES = [
        ('whatsapp', 'WhatsApp'),
        ('llamada',  'Llamada telefónica'),
        ('ambos',    'Cualquiera de los dos'),
    ]
    DIAS_CHOICES = [
        ('lunes_viernes', 'Lunes a Viernes'),
        ('lunes_sabado',  'Lunes a Sábado'),
        ('manana',        'Solo mañanas (9:00–13:00)'),
        ('tarde',         'Solo tardes (14:00–18:00)'),
        ('cualquier_dia', 'Cualquier día/horario'),
    ]
    usuario              = models.OneToOneField(User, on_delete=models.CASCADE,
                                                related_name='clinica', null=True, blank=True)
    nombre_clinica       = models.CharField(max_length=150)
    rut                  = models.CharField(max_length=12, unique=True)
    direccion            = models.CharField(max_length=200)
    ciudad               = models.CharField(max_length=80)
    region               = models.CharField(max_length=5, choices=REGION_CHOICES)
    telefono             = models.CharField(max_length=20)
    email                = models.EmailField()
    sitio_web            = models.URLField(blank=True)
    nombre_contacto      = models.CharField(max_length=100)
    cargo_contacto       = models.CharField(max_length=80, blank=True)
    medio_contacto       = models.CharField(max_length=10, choices=CONTACTO_CHOICES, default='whatsapp')
    dias_contacto        = models.CharField(max_length=20, choices=DIAS_CHOICES, blank=True)
    productos_interes    = models.ManyToManyField(Producto, blank=True,
                                                  related_name='clinicas_interesadas')
    producto_no_catalogo = models.TextField(blank=True)
    rotacion_estimada    = models.CharField(max_length=10, choices=ROTACION_CHOICES, default='media')
    verificada           = models.BooleanField(default=False)
    fecha_inscripcion    = models.DateTimeField(auto_now_add=True)
    notas                = models.TextField(blank=True)

    class Meta:
        verbose_name        = 'Clínica'
        verbose_name_plural = 'Clínicas'
        ordering            = ['region', 'nombre_clinica']

    def __str__(self):
        return f"{self.nombre_clinica} ({self.get_region_display()})"


# ── PEDIDOS ───────────────────────────────────────────────────────────────────
class Pedido(models.Model):
    ESTADO_CHOICES = [
        ('pendiente',      'Pendiente'),
        ('en_preparacion', 'En preparación'),
        ('enviado',        'Enviado'),
        ('entregado',      'Entregado'),
        ('devolucion',     'Devolución'),
        ('cancelado',      'Cancelado'),
    ]
    clinica             = models.ForeignKey(Clinica, on_delete=models.CASCADE,
                                            related_name='pedidos')
    estado              = models.CharField(max_length=20, choices=ESTADO_CHOICES,
                                           default='pendiente')
    fecha_creacion      = models.DateTimeField(auto_now_add=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    observaciones       = models.TextField(blank=True)
    total               = models.PositiveIntegerField(default=0)

    class Meta:
        verbose_name        = 'Pedido'
        verbose_name_plural = 'Pedidos'
        ordering            = ['-fecha_creacion']

    def __str__(self):
        return f"Pedido #{self.pk} – {self.clinica.nombre_clinica} ({self.get_estado_display()})"

    @property
    def total_con_iva(self):
        return round(self.total * 1.19)


# ── DETALLE DE PEDIDO ─────────────────────────────────────────────────────────
class DetallePedido(models.Model):
    pedido          = models.ForeignKey(Pedido, on_delete=models.CASCADE,
                                        related_name='detalles')
    producto        = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad        = models.PositiveSmallIntegerField()
    precio_unitario = models.PositiveIntegerField()
    observaciones   = models.TextField(blank=True)

    class Meta:
        verbose_name        = 'Detalle de pedido'
        verbose_name_plural = 'Detalles de pedido'

    @property
    def subtotal(self):
        return self.precio_unitario * self.cantidad

    def __str__(self):
        return f"{self.producto.nombre} x{self.cantidad}"



# ── HISTORIAL DE ESTADOS ──────────────────────────────────────────────────────
class HistorialEstado(models.Model):
    pedido     = models.ForeignKey(Pedido, on_delete=models.CASCADE,
                 related_name='historial', null=True, blank=True)
    solicitud  = models.ForeignKey('SolicitudPublico', on_delete=models.CASCADE,
                 related_name='historial', null=True, blank=True)
    estado     = models.CharField(max_length=20)
    fecha      = models.DateTimeField(auto_now_add=True)
    nota       = models.CharField(max_length=200, blank=True)
    cambiado_por = models.ForeignKey(User, on_delete=models.SET_NULL,
                   null=True, blank=True, related_name='cambios_estado_pedido')

    class Meta:
        verbose_name        = 'Historial de estado'
        verbose_name_plural = 'Historial de estados'
        ordering            = ['fecha']

    def __str__(self):
        if self.pedido_id:
            return f"Pedido #{self.pedido_id} → {self.estado}"
        return f"Solicitud #{self.solicitud_id} → {self.estado}"


# ── CARRITO ───────────────────────────────────────────────────────────────────
class CarritoItem(models.Model):
    clinica         = models.ForeignKey(Clinica, on_delete=models.CASCADE,
                                        related_name='carrito_items')
    producto        = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad        = models.PositiveSmallIntegerField(default=1)
    precio_unitario = models.PositiveIntegerField()
    observaciones   = models.TextField(blank=True)
    agregado        = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Ítem de carrito'
        verbose_name_plural = 'Ítems de carrito'
        unique_together     = ('clinica', 'producto')
        ordering            = ['agregado']

    @property
    def subtotal(self):
        return self.precio_unitario * self.cantidad

    def __str__(self):
        return f"{self.clinica.nombre_clinica} · {self.producto.nombre} x{self.cantidad}"


# ── CONTACTO ──────────────────────────────────────────────────────────────────
class ConsultaContacto(models.Model):
    TIPO_CHOICES = [
        ('info',         'Quiero más información'),
        ('inscripcion',  'Inscribir mi clínica'),
        ('pedido',       'Hacer un pedido'),
        ('soporte',      'Soporte técnico'),
        ('factura',      'Consulta de facturación'),
        ('reclamo',      'Reclamo'),
        ('felicitacion', 'Felicitaciones'),
        ('otro',         'Otro'),
    ]
    ESTADO_CASO_CHOICES = [
        ('pendiente',  'Pendiente'),
        ('en_proceso', 'En proceso'),
        ('resuelto',   'Resuelto'),
    ]
    nombre            = models.CharField(max_length=100)
    email             = models.EmailField()
    telefono          = models.CharField('Teléfono', max_length=20, blank=True)
    es_clinica        = models.BooleanField('Soy Clínica Dental', default=False)
    region            = models.CharField(max_length=5, choices=REGION_CHOICES, blank=True)
    tipo_consulta     = models.CharField(max_length=15, choices=TIPO_CHOICES, default='info')
    mensaje           = models.TextField()
    adjunto           = models.FileField(upload_to='adjuntos/', blank=True, null=True)
    leido             = models.BooleanField(default=False)
    fecha             = models.DateTimeField(auto_now_add=True)
    estado_caso       = models.CharField(max_length=15, choices=ESTADO_CASO_CHOICES,
                                         default='pendiente')
    tomado_por        = models.ForeignKey(User, on_delete=models.SET_NULL,
                                          null=True, blank=True,
                                          related_name='casos_tomados')
    fecha_tomado      = models.DateTimeField(null=True, blank=True)
    notas_seguimiento = models.TextField(blank=True)
    resuelto_por      = models.ForeignKey(User, on_delete=models.SET_NULL,
                                          null=True, blank=True,
                                          related_name='mensajes_resueltos')
    fecha_resolucion  = models.DateTimeField(null=True, blank=True)
    nota_resolucion   = models.TextField(blank=True)
    canal_respuesta   = models.CharField(max_length=15, choices=[
        ('email',      '📧 Email'),
        ('whatsapp',   '💬 WhatsApp'),
        ('llamada',    '📞 Llamada telefónica'),
        ('presencial', '🏢 Presencial'),
        ('otro',       '🌐 Otro'),
    ], default='email', blank=True)
    direccion         = models.CharField(max_length=200, blank=True)
    dias_respuesta    = models.CharField(max_length=200, blank=True)
    horario_respuesta = models.CharField(max_length=15, choices=[
        ('manana',     'Mañana (9:00–13:00)'),
        ('tarde',      'Tarde (14:00–18:00)'),
        ('cualquiera', 'Cualquier horario'),
    ], default='cualquiera', blank=True)
    caso_padre = models.ForeignKey('self', null=True, blank=True,
                                    on_delete=models.SET_NULL,
                                    related_name='consultas_relacionadas')
    caso_padre = models.ForeignKey('self', null=True, blank=True,
                                    on_delete=models.SET_NULL,
                                    related_name='consultas_relacionadas')

    class Meta:
        verbose_name        = 'Mensaje de contacto'
        verbose_name_plural = 'Mensajes de contacto'
        ordering            = ['-fecha']

    def __str__(self):
        return f"{self.nombre} – {self.get_tipo_consulta_display()} ({self.fecha.strftime('%d/%m/%Y')})"


# ── MI STOCK ──────────────────────────────────────────────────────────────────
class PersonalClinica(models.Model):
    ESPECIALIDAD_CHOICES = [
       ('dentista_general',  'Dentista General'),
       ('asistente',         'Asistente'),
       ('secretaria',        'Secretaria'),
       ('implantólogo',      'Implantólogo'),
       ('periodoncista',     'Periodoncista'),
       ('rehabilitador',     'Rehabilitador'),
       ('ortodoncista',      'Ortodoncista'),
       ('odontopediatra',    'Odontopediatra'),
       ('endodoncista',      'Endodoncista'),
       ('patologo_oral',     'Patólogo Oral'),
       ('ttm_dof',           'TTM y DOF'),
       ('otro',              'Otro'),
    ]
    clinica      = models.ForeignKey(Clinica, on_delete=models.CASCADE,
                                     related_name='personal')
    nombre       = models.CharField(max_length=100)
    especialidad = models.CharField(max_length=20, choices=ESPECIALIDAD_CHOICES,
                                    default='dentista_general')
    activo       = models.BooleanField(default=True)

    class Meta:
        verbose_name        = 'Personal de clínica'
        verbose_name_plural = 'Personal de clínicas'
        unique_together     = ('clinica', 'nombre')
        ordering            = ['nombre']

    def __str__(self):
        return f"{self.nombre} – {self.clinica.nombre_clinica}"


class StockMinimo(models.Model):
    clinica  = models.ForeignKey(Clinica, on_delete=models.CASCADE,
                                  related_name='stock_minimos')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    minimo   = models.PositiveSmallIntegerField(default=0)

    class Meta:
        verbose_name        = 'Stock mínimo'
        verbose_name_plural = 'Stock mínimos'
        unique_together     = ('clinica', 'producto')

    def __str__(self):
        return f"{self.clinica.nombre_clinica} – {self.producto.nombre} mín:{self.minimo}"


class VentaStock(models.Model):
    clinica  = models.ForeignKey(Clinica, on_delete=models.CASCADE,
                                  related_name='ventas_stock')
    producto = models.ForeignKey(Producto, on_delete=models.CASCADE)
    personal = models.ForeignKey(PersonalClinica, on_delete=models.SET_NULL,
                                  null=True, blank=True)
    cantidad = models.PositiveSmallIntegerField()
    fecha = models.DateField(default=datetime.date.today)

    class Meta:
        verbose_name        = 'Venta de stock'
        verbose_name_plural = 'Ventas de stock'
        ordering            = ['-fecha']

    def __str__(self):
        return f"{self.clinica.nombre_clinica} – {self.producto.nombre} x{self.cantidad}"


class AjusteInventario(models.Model):
    clinica   = models.ForeignKey(Clinica, on_delete=models.CASCADE,
                                   related_name='ajustes_inventario')
    producto  = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad  = models.IntegerField(default=0)
    nota      = models.CharField(max_length=200, blank=True)
    fecha     = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name        = 'Ajuste de inventario'
        verbose_name_plural = 'Ajustes de inventario'
        unique_together     = ('clinica', 'producto')
        ordering            = ['producto__nombre']

    def __str__(self):
        return f"{self.clinica.nombre_clinica} – {self.producto.nombre}: {self.cantidad} ud."


class ProductoSugerido(models.Model):
    clinica          = models.ForeignKey(Clinica, on_delete=models.CASCADE,
                                          related_name='productos_sugeridos')
    nombre_producto  = models.CharField(max_length=150)
    marca            = models.CharField(max_length=80, blank=True)
    uso              = models.TextField(blank=True)
    cantidad_mensual = models.PositiveSmallIntegerField(null=True, blank=True)
    revisado         = models.BooleanField(default=False)
    fecha            = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Producto sugerido'
        verbose_name_plural = 'Productos sugeridos'
        ordering            = ['-fecha']

    def __str__(self):
        return f"{self.nombre_producto} – sugerido por {self.clinica.nombre_clinica}"
    
    # ── PERFIL DE USUARIO PÚBLICO ─────────────────────────────────────────────────
class PerfilUsuario(models.Model):
    HORARIO_CHOICES = [
        ('manana',     'Mañana (9:00–13:00)'),
        ('tarde',      'Tarde (14:00–18:00)'),
        ('cualquiera', 'Cualquier horario'),
    ]
    DIAS_CHOICES = [
        ('lunes_viernes', 'Lunes a Viernes'),
        ('lunes_sabado',  'Lunes a Sábado'),
        ('cualquier_dia', 'Cualquier día'),
    ]
    usuario              = models.OneToOneField(User, on_delete=models.CASCADE,
                                                related_name='perfil')
    rut                  = models.CharField(max_length=12, blank=True)
    telefono             = models.CharField(max_length=20, blank=True)
    horario_preferido    = models.CharField(max_length=15, choices=HORARIO_CHOICES,
                                            default='cualquiera')
    dias_disponibles = models.CharField(max_length=100, blank=True, default='cualquier_dia')
    observaciones_entrega = models.TextField(blank=True,
                                             help_text='Ej: Tocar timbre, no llamar')

    class Meta:
        verbose_name        = 'Perfil de usuario'
        verbose_name_plural = 'Perfiles de usuario'

    def __str__(self):
        return f"Perfil de {self.usuario.get_full_name() or self.usuario.username}"


# ── DIRECCIONES DE DESPACHO ───────────────────────────────────────────────────
class DireccionDespacho(models.Model):
    REGION_CHOICES = [
        ('RM',   'Región Metropolitana'),
        ('V',    'Valparaíso'),
        ('VI',   "O'Higgins"),
        ('VII',  'Maule'),
        ('VIII', 'Biobío'),
        ('IX',   'La Araucanía'),
        ('X',    'Los Lagos'),
        ('XIV',  'Los Ríos'),
        ('XV',   'Arica y Parinacota'),
        ('XVI',  'Ñuble'),
        ('I',    'Tarapacá'),
        ('II',   'Antofagasta'),
        ('III',  'Atacama'),
        ('IV',   'Coquimbo'),
    ]
    usuario    = models.ForeignKey(User, on_delete=models.CASCADE,
                                   related_name='direcciones')
    alias      = models.CharField(max_length=50, default='Casa',
                                  help_text='Ej: Casa, Trabajo')
    direccion  = models.CharField(max_length=200)
    ciudad     = models.CharField(max_length=80)
    region     = models.CharField(max_length=5, choices=REGION_CHOICES)
    referencia = models.CharField(max_length=200, blank=True,
                                  help_text='Ej: Depto 302, casa azul')
    principal  = models.BooleanField(default=False)

    class Meta:
        verbose_name        = 'Dirección de despacho'
        verbose_name_plural = 'Direcciones de despacho'
        ordering            = ['-principal', 'alias']

    def __str__(self):
        return f"{self.alias} – {self.direccion}, {self.ciudad}"


# ── CARRITO PÚBLICO ───────────────────────────────────────────────────────────
class CarritoItemPublico(models.Model):
    usuario         = models.ForeignKey(User, on_delete=models.CASCADE,
                                        related_name='carrito_publico')
    producto        = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad        = models.PositiveSmallIntegerField(default=1)
    precio_unitario = models.PositiveIntegerField()
    agregado        = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Ítem carrito público'
        verbose_name_plural = 'Ítems carrito público'
        unique_together     = ('usuario', 'producto')
        ordering            = ['agregado']

    @property
    def subtotal(self):
        return self.precio_unitario * self.cantidad

    def __str__(self):
        return f"{self.usuario.username} · {self.producto.nombre} x{self.cantidad}"


# ── SOLICITUD PÚBLICO (pedido confirmado) ─────────────────────────────────────
class SolicitudPublico(models.Model):
    ESTADO_CHOICES = [
        ('pendiente',  'Pendiente'),
        ('en_proceso', 'En proceso'),
        ('enviado',    'Enviado'),
        ('entregado',  'Entregado'),
        ('devolucion', 'Devolución'),
        ('cancelado',  'Cancelado'),
    ]
    usuario          = models.ForeignKey(User, on_delete=models.CASCADE,
                                         related_name='solicitudes_publico')
    estado           = models.CharField(max_length=15, choices=ESTADO_CHOICES,
                                        default='pendiente')
    # ── Campos para el pago simulado ──
    PAGO_CHOICES = [
        ('pendiente', 'Pendiente'),
        ('aprobado',  'Aprobado'),
        ('rechazado', 'Rechazado'),
    ]
    pago_estado = models.CharField(max_length=10, choices=PAGO_CHOICES,
                                    default='pendiente')
    token_pago  = models.CharField(max_length=64, blank=True, null=True)
    direccion        = models.ForeignKey(DireccionDespacho, on_delete=models.SET_NULL,
                                         null=True, blank=True)
    horario          = models.CharField(max_length=15, blank=True)
    dias             = models.CharField(max_length=15, blank=True)
    observaciones    = models.TextField(blank=True)
    total            = models.PositiveIntegerField(default=0)
    fecha_creacion   = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Solicitud público'
        verbose_name_plural = 'Solicitudes público'
        ordering            = ['-fecha_creacion']

    @property
    def total_con_iva(self):
        return round(self.total * 1.19)

    def __str__(self):
        return f"Solicitud #{self.pk} – {self.usuario.username}"


# ── DETALLE SOLICITUD PÚBLICO ─────────────────────────────────────────────────
class DetalleSolicitudPublico(models.Model):
    solicitud       = models.ForeignKey(SolicitudPublico, on_delete=models.CASCADE,
                                        related_name='detalles')
    producto        = models.ForeignKey(Producto, on_delete=models.CASCADE)
    cantidad        = models.PositiveSmallIntegerField()
    precio_unitario = models.PositiveIntegerField()

    @property
    def subtotal(self):
        return self.precio_unitario * self.cantidad

    def __str__(self):
        return f"{self.producto.nombre} x{self.cantidad}"
    
    # ── HISTORIAL DE PRECIOS ──────────────────────────────────────────────────────
class HistorialPrecio(models.Model):
    producto        = models.ForeignKey(Producto, on_delete=models.CASCADE,
                                        related_name='historial_precios')
    precio_anterior = models.PositiveIntegerField()
    precio_nuevo    = models.PositiveIntegerField()
    costo_anterior  = models.PositiveIntegerField(default=0)
    costo_nuevo     = models.PositiveIntegerField(default=0)
    cambiado_por    = models.ForeignKey(User, on_delete=models.SET_NULL,
                                        null=True, blank=True)
    fecha           = models.DateTimeField(auto_now_add=True)
    motivo          = models.CharField(max_length=200, blank=True,
                                       help_text='Ej: Actualización proveedor')

    class Meta:
        verbose_name        = 'Historial de precio'
        verbose_name_plural = 'Historial de precios'
        ordering            = ['-fecha']

    def __str__(self):
        return f"{self.producto.nombre} — ${self.precio_anterior} → ${self.precio_nuevo}"
    
    # ── NOTAS DE SEGUIMIENTO ──────────────────────────────────────────────────────
class NotaSeguimiento(models.Model):
    CANAL_CHOICES = [
        ('email',      '📧 Email'),
        ('whatsapp',   '💬 WhatsApp'),
        ('llamada',    '📞 Llamada telefónica'),
        ('presencial', '🏢 Presencial'),
        ('otro',       '🌐 Otro'),
    ]
    mensaje            = models.ForeignKey(ConsultaContacto, on_delete=models.CASCADE,
                                           related_name='notas')
    autor              = models.ForeignKey(User, on_delete=models.SET_NULL,
                                           null=True, blank=True)
    canal              = models.CharField(max_length=15, choices=CANAL_CHOICES,
                                          default='email')
    nota               = models.TextField()
    consulta_vinculada = models.ForeignKey(ConsultaContacto, on_delete=models.SET_NULL,
                                           null=True, blank=True,
                                           related_name='notas_vinculadas')
    fecha              = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Nota de seguimiento'
        verbose_name_plural = 'Notas de seguimiento'
        ordering            = ['fecha']

    def __str__(self):
        return f"Nota de {self.autor} en caso #{self.mensaje_id}"
    
    # ── COMPRAS A PROVEEDORES ─────────────────────────────────────────────────────
class CompraProveedor(models.Model):
    TIPO_CHOICES = [
        ('compra',  'Compra con factura'),
        ('inicial', 'Stock inicial / ajuste'),
    ]
    tipo            = models.CharField(max_length=10, choices=TIPO_CHOICES, default='compra')
    proveedor       = models.CharField(max_length=150, blank=True)
    numero_factura  = models.CharField(max_length=80, blank=True)
    fecha_compra    = models.DateField()
    flete_total     = models.PositiveIntegerField(default=0,
                      help_text='Valor total del flete. Se reparte proporcionalmente entre los productos.')
    motivo          = models.TextField(blank=True,
                      help_text='Obligatorio para stock inicial o ajuste.')
    registrado_por  = models.ForeignKey(User, on_delete=models.SET_NULL,
                      null=True, blank=True)
    creado          = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Compra a proveedor'
        verbose_name_plural = 'Compras a proveedores'
        ordering            = ['-fecha_compra']

    def __str__(self):
        if self.numero_factura:
            return f"Factura {self.numero_factura} – {self.proveedor} ({self.fecha_compra})"
        return f"Stock inicial – {self.fecha_compra}"

    @property
    def total_unidades(self):
        return sum(l.cantidad for l in self.lotes.all())

    @property
    def flete_por_unidad(self):
        if self.total_unidades > 0:
            return round(self.flete_total / self.total_unidades)
        return 0

    @property
    def total_sin_iva(self):
        return sum(l.costo_total_sin_iva for l in self.lotes.all())

    @property
    def total_con_iva(self):
        return sum(l.costo_total_con_iva for l in self.lotes.all())


# ── LOTES POR PRODUCTO ────────────────────────────────────────────────────────
class LoteCompra(models.Model):
    compra            = models.ForeignKey(CompraProveedor, on_delete=models.CASCADE,
                        related_name='lotes')
    producto          = models.ForeignKey('Producto', on_delete=models.PROTECT,
                        related_name='lotes')
    numero_lote       = models.CharField(max_length=80, blank=True)
    fecha_vencimiento = models.DateField(null=True, blank=True)
    no_vence          = models.BooleanField(default=False,
                        help_text='Marcar si este producto no tiene fecha de vencimiento (ej. cepillos, dispositivos).')
    cantidad          = models.PositiveIntegerField()
    cantidad_disponible = models.PositiveIntegerField(default=0,
                          help_text='Unidades que quedan de este lote (se actualiza con cada venta).')
    costo_unitario    = models.PositiveIntegerField(default=0,
                        help_text='Costo por unidad SIN IVA ni flete.')
    actualizo_precio  = models.BooleanField(default=False,
                        help_text='True si al ingresar este lote se actualizó el precio de venta.')
    notas             = models.TextField(blank=True)

    class Meta:
        verbose_name        = 'Lote de compra'
        verbose_name_plural = 'Lotes de compra'

    def __str__(self):
        return f"{self.producto.nombre} – Lote {self.numero_lote or 'S/N'} ({self.cantidad} u.)"

    def save(self, *args, **kwargs):
        # Al crear el lote por primera vez, la cantidad disponible inicia igual a la cantidad comprada
        if not self.pk:
            self.cantidad_disponible = self.cantidad
        super().save(*args, **kwargs)

    @property
    def flete_unitario(self):
        return self.compra.flete_por_unidad

    @property
    def costo_unitario_sin_iva(self):
        return self.costo_unitario + self.flete_unitario

    @property
    def costo_unitario_con_iva(self):
        return round(self.costo_unitario_sin_iva * 1.19)

    @property
    def costo_total_sin_iva(self):
        return self.costo_unitario_sin_iva * self.cantidad

    @property
    def costo_total_con_iva(self):
        return self.costo_unitario_con_iva * self.cantidad

    @property
    def dias_para_vencer(self):
        if self.fecha_vencimiento:
            from django.utils import timezone
            delta = self.fecha_vencimiento - timezone.now().date()
            return delta.days
        return None

    @property
    def semaforo_vencimiento(self):
        dias = self.dias_para_vencer
        if dias is None:
            return 'sin_fecha'
        if dias <= 30:
            return 'rojo'
        if dias <= 90:
            return 'amarillo'
        return 'verde'

    @property
    def margen_publico(self):
        precio = self.producto.get_precio_venta()
        if precio and self.costo_unitario_con_iva:
            return round((precio - self.costo_unitario_con_iva) / precio * 100)
        return None

    @property
    def margen_dentista(self):
        precio_b2d = self.producto.get_precio_b2d()
        if precio_b2d and self.costo_unitario_con_iva:
            return round((precio_b2d - self.costo_unitario_con_iva) / precio_b2d * 100)
        return None


def descontar_stock_fifo(producto, cantidad_a_descontar):
    """
    Descuenta stock de los lotes de un producto, empezando por el que
    vence primero (FIFO). Devuelve una lista de tuplas (lote, cantidad_usada)
    para trazabilidad. También actualiza producto.stock automáticamente.
    """
    lotes_disponibles = LoteCompra.objects.filter(
        producto=producto,
        cantidad_disponible__gt=0
    ).order_by('fecha_vencimiento')

    detalle_uso = []
    restante = cantidad_a_descontar

    for lote in lotes_disponibles:
        if restante <= 0:
            break
        usar = min(lote.cantidad_disponible, restante)
        lote.cantidad_disponible -= usar
        lote.save()
        detalle_uso.append((lote, usar))
        restante -= usar

    # Actualizar el stock del producto restando lo que realmente se descontó de los lotes
    cantidad_descontada_real = cantidad_a_descontar - restante
    if cantidad_descontada_real > 0:
        producto.stock = max(0, producto.stock - cantidad_descontada_real)
        producto.save()

    return detalle_uso, restante

def verificar_stock(producto, cantidad_solicitada):
    """
    Verifica si hay stock suficiente para la cantidad solicitada.
    Retorna (ok: bool, disponible: int, mensaje: str)
    """
    disponible = producto.stock
    if cantidad_solicitada > disponible:
        if disponible == 0:
            mensaje = f'"{producto.nombre}" está sin stock por ahora.'
        else:
            mensaje = f'Solo quedan {disponible} unidades de "{producto.nombre}".'
        return False, disponible, mensaje
    return True, disponible, ""

# ── TRAZABILIDAD DE VENTAS POR LOTE ───────────────────────────────────────────
class DetalleLoteVenta(models.Model):
    """
    Registra de qué lote(s) salió cada producto vendido, para trazabilidad
    completa (saber el costo real y el lote exacto de cada venta).
    """
    lote              = models.ForeignKey(LoteCompra, on_delete=models.PROTECT,
                        related_name='ventas')
    cantidad          = models.PositiveIntegerField()
    detalle_pedido    = models.ForeignKey('DetallePedido', on_delete=models.CASCADE,
                        null=True, blank=True, related_name='lotes_usados')
    detalle_solicitud = models.ForeignKey('DetalleSolicitudPublico', on_delete=models.CASCADE,
                        null=True, blank=True, related_name='lotes_usados')
    fecha             = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name        = 'Detalle de lote en venta'
        verbose_name_plural = 'Detalles de lote en ventas'

    def __str__(self):
        return f"{self.cantidad} u. del lote {self.lote.numero_lote or 'S/N'}"