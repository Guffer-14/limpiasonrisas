# LimpiaSONRISAS — Módulo de Administración de Productos

Entrega Módulo 7 — Acceso a Datos en Aplicaciones Python Django.
Bootcamp Full Stack Python, Sustantiva / AD Academy.

## 1. Motor de base de datos

**SQLite3** (motor por defecto de Django), configurado en `miproyecto/settings.py`:

```python
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}
```

El archivo de base de datos vive en `build/db.sqlite3`. El proyecto incluye
también, comentada en el mismo archivo, una configuración alternativa para
PostgreSQL pensada para un eventual entorno de producción.

## 2. Descripción del modelo de datos

El módulo de administración de productos gira en torno a dos modelos
principales, relacionados entre sí:

### `Categoria`

Agrupa los productos del catálogo (ej. "Cepillos Adulto", "Pasta dental",
"Higiene infantil").

| Campo | Tipo | Descripción |
|---|---|---|
| `nombre` | CharField | Nombre de la categoría |
| `icono` | CharField | Clase de ícono (Bootstrap Icons) para la UI |
| `descripcion` | TextField | Descripción opcional |
| `orden` | PositiveSmallIntegerField | Orden de despliegue en el catálogo |
| `activo` | BooleanField | Si la categoría está visible |

### `Producto`

Representa cada producto del catálogo de LimpiaSONRISAS.

| Campo | Tipo | Descripción |
|---|---|---|
| `categoria` | **ForeignKey → Categoria** (obligatorio, `on_delete=PROTECT`) | Relación uno a muchos: una categoría tiene muchos productos. Todo producto debe tener una categoría asignada; si se intenta eliminar una categoría que aún tiene productos, Django lo impide |
| `nombre` | CharField | Nombre del producto |
| `marca` | CharField | Marca comercial |
| `descripcion` | TextField | Descripción del producto |
| `imagen` | ImageField | Foto del producto |
| `precio` | PositiveIntegerField | Precio de venta al público |
| `costo` | PositiveIntegerField | Costo de adquisición |
| `precio_b2d` | PositiveIntegerField | Precio especial para clínicas (B2D = business to dental). Se calcula automáticamente como `costo × 1.20` si se deja vacío |
| `precio_volumen` / `cantidad_minima_volumen` | — | Precio especial por compra de volumen |
| `precio_pack` / `unidades_pack` | — | Precio y tamaño si se vende en pack |
| `pronto_a_vencer` | BooleanField | Si está cerca de su fecha de vencimiento (al activarse, recalcula precios automáticamente a `costo × 1.19`) |
| `stock` | PositiveIntegerField | Unidades disponibles |
| `lugar_stock`, `lote`, `fecha_vencimiento` | — | Trazabilidad de inventario |
| `edad_min`, `edad_max` | — | Público objetivo del producto |
| `activo`, `destacado` | BooleanField | Visibilidad y destaque en el catálogo |

**Relación clave:** `Producto.categoria` es una `ForeignKey` obligatoria
hacia `Categoria` (`on_delete=models.PROTECT`) — cada producto debe
pertenecer a exactamente una categoría, y una categoría puede tener muchos
productos. La obligatoriedad se valida en tres capas: a nivel de base de
datos (el campo no admite `NULL`, aplicado en la migración
`0024_alter_producto_categoria`), en el formulario (`required` en el
`<select>`), y en la vista (`adm_crear_producto` rechaza la creación si no
llega una categoría, con un mensaje de error claro).

**Regla de negocio sobre el precio:** los productos nuevos se crean sin
precio asignado todavía (precio en $0). Esto es intencional: en el flujo
real del negocio, el precio se define recién cuando ingresa stock real del
producto, a través del módulo de **compra a proveedor**
(`CompraProveedor` / `LoteCompra`), no al momento de dar de alta el
producto en el catálogo. El campo `precio` sí valida que sea mayor a 0 en
el formulario de **edición** y en la pantalla dedicada de **precios**
(`adm_precios_productos`), que es donde corresponde asignarlo según este
modelo de negocio.

**Extra destacable:** el formulario de edición de producto incluye además
un **historial de cambios de precio** (fecha, precio/costo anterior y
nuevo, motivo del cambio, usuario que lo hizo) — trazabilidad adicional no
exigida por la pauta, pero que refuerza el control sobre los datos del
catálogo.

## 3. Rutas principales del módulo de administración

Todas requieren sesión iniciada con rol **ADM** (administrador) o
superusuario — verificado con la función `es_adm()` en `views.py`.

| Ruta | Vista | Acción |
|---|---|---|
| `/adm/productos/` | `adm_lista_productos` | Listado de todos los productos, con filtros y búsqueda |
| `/adm/productos/crear/` | `adm_crear_producto` | Formulario de creación de un nuevo producto |
| `/adm/productos/editar/<id>/` | `adm_editar_producto` | Formulario de edición de un producto existente |
| `/adm/productos/eliminar/<id>/` | `adm_eliminar_producto` | Página de confirmación + eliminación del producto |
| `/adm/productos/precios/` | `adm_precios_productos` | Vista dedicada para asignar/editar precios masivamente |

Existe también un set paralelo de rutas bajo `/gestor/productos/...` para
el rol **Gestor** (con permisos más acotados), no documentado en detalle
aquí porque el módulo principal de administración es el de `/adm/`.

## 4. Pasos para ejecutar el proyecto

```bash
# 1. Ubicarse en la carpeta del proyecto
cd limpiasonrisas_actualizado_1/build

# 2. Crear y activar entorno virtual (si no existe)
python -m venv entornovirtual
source entornovirtual/Scripts/activate      # Git Bash en Windows

# 3. Instalar dependencias
pip install django

# 4. Aplicar migraciones
python manage.py migrate

# 5. (Opcional) Crear superusuario para acceder a /admin/
python manage.py createsuperuser

# 6. Levantar el servidor
python manage.py runserver
```

El proyecto queda disponible en `http://127.0.0.1:8000/`.

- Panel de administración de productos (rol ADM): `http://127.0.0.1:8000/adm/productos/`
- Django Admin nativo: `http://127.0.0.1:8000/admin/`

**Para acceder como ADM:** el usuario debe ser superusuario, o pertenecer
al grupo `ADM` (creado vía Django Admin, en *Auth > Groups*, asignando el
grupo al usuario correspondiente).

## 5. Uso del panel administrativo de Django

El modelo `Producto` está registrado en `admin.py` con configuración
extendida, no solo el registro básico:

```python
@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display  = ['nombre', 'marca', 'categoria', 'precio', 'costo', ...]
    list_filter    = ['categoria', 'activo', 'destacado', 'marca']
    search_fields  = ['nombre', 'marca', 'descripcion']
    list_editable  = ['precio', 'costo', ...]
    fieldsets = (
        ('Información básica', {...}),
        ('Precios', {...}),
        ('Precio por volumen', {...}),
        ('Pronto a vencer', {...}),
        ('Inventario', {...}),
        ('Público objetivo', {...}),
    )
```

Esto permite, desde `/admin/`: filtrar productos por categoría o estado,
buscar por nombre/marca/descripción, **editar precio y stock directo
desde la lista** (sin entrar al detalle, gracias a `list_editable`), y ver
los campos organizados por secciones lógicas (`fieldsets`) al entrar al
detalle de un producto.

*(Evidencia: ver capturas en la carpeta `/evidencias` — listado de
productos en Django Admin y formulario de edición.)*

## 6. Evidencias (capturas)

Se incluyen en la carpeta `evidencias/` de esta entrega:

1. `01_listado_productos.png` — Listado de productos en el panel `/adm/productos/`
2. `02_crear_producto.png` — Formulario de creación de producto
3. `03_editar_producto.png` — Formulario de edición de producto
4. `04_eliminar_producto.png` — Página de confirmación antes de eliminar
5. `05_django_admin_listado.png` — Listado de `Producto` desde `/admin/` (Django Admin nativo)
6. `06_django_admin_detalle.png` — Detalle/edición de un producto desde `/admin/`, mostrando los `fieldsets`

## 7. Notas para el profesor

- El proyecto incluye, además del módulo de productos pedido en esta
  pauta, un sistema más amplio de e-commerce (carritos, pedidos,
  consignación a clínicas, y una pasarela de pago simulada en un segundo
  proyecto Django aparte) desarrollado de forma incremental durante el
  curso. El alcance de esta entrega se centra específicamente en el CRUD
  de productos solicitado.
- Las rutas usadas (`/adm/productos/...`) son propias del proyecto, no las
  rutas de ejemplo (`/products/...`) sugeridas en la pauta — la pauta las
  indica como referenciales.
- Durante esta entrega se reforzó la relación `Producto → Categoria`,
  haciéndola obligatoria (antes admitía productos sin categoría). El
  cambio quedó registrado en la migración
  `0024_alter_producto_categoria.py`, aplicada sin pérdida de datos
  porque se verificó previamente que no existían productos sin categoría
  asignada.
