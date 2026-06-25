"""
Carga productos desde el Excel original de LimpioSonrisas.
Uso: python manage.py cargar_productos --excel ruta/productos.xlsx
"""
import re
import pandas as pd
from django.core.management.base import BaseCommand
from miprimerapp.models import Categoria, Producto


CATEGORIA_MAP = {
    'labios':         'Labios',
    'irrigad':        'Irrigadores',
    'bebe':           'Bebés e Infantil',
    'ortodoncia':     'Ortodoncia',
    'interdental':    'Cepillos Interproximales',
    'enjuague':       'Enjuagues Bucales',
    'protesis':       'Prótesis',
    'cepillo':        'Cepillos Adulto',
    'adulto':         'Cepillos Adulto',
    'pasta':          'Pastas Dentales',
    'portacepillo':   'Accesorios',
}

ICONOS = {
    'Labios':                   'bi-heart',
    'Irrigadores':              'bi-droplet',
    'Bebés e Infantil':         'bi-emoji-smile',
    'Ortodoncia':               'bi-braces',
    'Cepillos Interproximales': 'bi-distribute-horizontal',
    'Enjuagues Bucales':        'bi-cup-straw',
    'Prótesis':                 'bi-award',
    'Cepillos Adulto':          'bi-brush',
    'Pastas Dentales':          'bi-capsule',
    'Pastas Infantiles':        'bi-emoji-laughing',
    'Accesorios':               'bi-bag',
    'Otros':                    'bi-box',
}


def map_cat(cat_raw):
    cat = str(cat_raw).lower()
    if 'labios' in cat:          return 'Labios'
    if 'irrigad' in cat:         return 'Irrigadores'
    if 'bebe' in cat or ('infantil' in cat and 'pasta' not in cat):
        return 'Bebés e Infantil'
    if 'pasta' in cat and 'infantil' in cat: return 'Pastas Infantiles'
    if 'ortodoncia' in cat:      return 'Ortodoncia'
    if 'interdental' in cat:     return 'Cepillos Interproximales'
    if 'enjuague' in cat:        return 'Enjuagues Bucales'
    if 'protesis' in cat and 'ortodoncia' not in cat: return 'Prótesis'
    if 'pasta' in cat:           return 'Pastas Dentales'
    if 'cepillo' in cat or 'adulto' in cat: return 'Cepillos Adulto'
    if 'portacepillo' in cat:    return 'Accesorios'
    return 'Otros'


def base_name(name):
    return re.sub(
        r'\s*(PROMO\s*(X\d+)?|ESPECIAL|PROMOX\d+|REGALO)\s*$',
        '', str(name), flags=re.IGNORECASE
    ).strip()


def extract_qty(name):
    m = re.search(r'(?:PROMO\s*X|PROMOX)(\d+)', str(name), re.IGNORECASE)
    if m: return int(m.group(1))
    if re.search(r'PROMO|ESPECIAL', str(name), re.IGNORECASE): return 4
    return None


class Command(BaseCommand):
    help = 'Carga productos desde el Excel de LimpioSonrisas'

    def add_arguments(self, parser):
        parser.add_argument('--excel', type=str,
                            default='productos.xlsx',
                            help='Ruta al archivo Excel')
        parser.add_argument('--limpiar', action='store_true',
                            help='Elimina productos existentes antes de cargar')

    def handle(self, *args, **options):
        excel_path = options['excel']
        self.stdout.write(f'📂 Leyendo {excel_path}…')

        df = pd.read_excel(excel_path)

        if options['limpiar']:
            Producto.objects.all().delete()
            Categoria.objects.all().delete()
            self.stdout.write('🗑  Productos y categorías eliminados.')

        # Crear categorías
        cat_cache = {}
        for nombre_cat in ['Labios','Irrigadores','Bebés e Infantil','Ortodoncia',
                           'Cepillos Interproximales','Enjuagues Bucales','Prótesis',
                           'Cepillos Adulto','Pastas Dentales','Pastas Infantiles',
                           'Accesorios','Otros']:
            cat, _ = Categoria.objects.get_or_create(
                nombre=nombre_cat,
                defaults={'icono': ICONOS.get(nombre_cat, 'bi-box'), 'orden': 0}
            )
            cat_cache[nombre_cat] = cat

        # Build promo lookup: base_name -> (precio_volumen, cantidad_minima)
        promo_mask = df['nombre_producto'].str.contains('PROMO|ESPECIAL|REGALO', case=False, na=False)
        promo_lookup = {}
        for _, row in df[promo_mask].iterrows():
            bn  = base_name(row['nombre_producto'])
            qty = extract_qty(row['nombre_producto'])
            precio = int(row['precio_venta_producto'])
            if precio > 0 and bn not in promo_lookup:
                promo_lookup[bn] = (precio, qty)

        # Load base products only
        base_df = df[~promo_mask]
        creados = actualizados = 0

        for _, row in base_df.iterrows():
            nombre   = str(row['nombre_producto']).strip()
            cat_name = map_cat(row['categoria '])
            categoria = cat_cache[cat_name]
            precio   = int(row['precio_venta_producto'])
            costo    = round(float(row['costo_producto']), 2)

            # Determine marca from name
            marca = ''
            for m in ['VITIS','Curaprox','CURAPROX','elmex','ELMEX','PHB','Colgate',
                      'TePe','Interprox','Oral-B','Oxyfresh','Blistex','Vaseline',
                      'LIP ICE','Dentwell','Fresh Up','Mayer','Waterpik','USMILE',
                      'Halita','Xeros','Caristop','Vai Origenes']:
                if m.lower() in nombre.lower():
                    marca = m
                    break

            # Volume pricing
            vol = promo_lookup.get(nombre, (None, None))

            # Fecha vencimiento
            fv = None
            if pd.notna(row['fecha_vencimiento']):
                fv_str = str(row['fecha_vencimiento'])[:10]
                if fv_str != '2099-12-31':
                    fv = fv_str

            lote = str(row['lote']) if pd.notna(row['lote']) else 'sin_lote'

            prod, created = Producto.objects.update_or_create(
                nombre=nombre,
                defaults={
                    'categoria':               categoria,
                    'marca':                   marca,
                    'descripcion':             '',
                    'precio':                  precio,
                    'costo':                   int(costo),
                    'precio_volumen':          int(vol[0]) if vol[0] else None,
                    'cantidad_minima_volumen': vol[1],
                    'lote':                    lote,
                    'fecha_vencimiento':       fv,
                    'activo':                  True,
                    'destacado':               False,
                }
            )
            if created: creados += 1
            else: actualizados += 1

        self.stdout.write(self.style.SUCCESS(
            f'\n✅ ¡Listo! {creados} productos creados, {actualizados} actualizados.'
        ))
        self.stdout.write(f'   Categorías: {Categoria.objects.count()}')
        self.stdout.write(f'   Productos:  {Producto.objects.count()}')
