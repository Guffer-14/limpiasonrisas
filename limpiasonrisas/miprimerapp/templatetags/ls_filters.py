import os
from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()

# Categorías con ícono SVG personalizado (no existe un ícono fiel en Bootstrap Icons)
ICONOS_SVG_PERSONALIZADOS = {
    'Pastas Dentales':          'pasta',
    'Cepillos Adulto':          'cepillo',
    'Labios':                   'boca',
    'Prótesis':                 'protesis',
    'Ortodoncia':               'ortodoncia',
    'Cepillos Interproximales': 'interdental',
    'Enjuagues Bucales':        'enjuague',
}

_svg_cache = {}


def _cargar_svg(archivo):
    if archivo in _svg_cache:
        return _svg_cache[archivo]
    ruta = os.path.join(settings.BASE_DIR, 'static', 'img', 'categorias', f'{archivo}.svg')
    try:
        with open(ruta, encoding='utf-8') as f:
            contenido = f.read()
    except FileNotFoundError:
        contenido = ''
    _svg_cache[archivo] = contenido
    return contenido


@register.simple_tag
def icono_categoria(categoria):
    """
    Devuelve el ícono de una categoría: SVG personalizado para las categorías
    sin un ícono fiel en Bootstrap Icons (pasta dental, cepillo, boca, prótesis,
    ortodoncia), o el <i class="bi ..."> normal para el resto.
    """
    nombre = getattr(categoria, 'nombre', '')
    archivo = ICONOS_SVG_PERSONALIZADOS.get(nombre)
    if archivo:
        svg = _cargar_svg(archivo)
        if svg:
            return mark_safe(f'<span class="ls-cat-icon-svg">{svg}</span>')
    icono = getattr(categoria, 'icono', 'bi-box')
    return mark_safe(f'<i class="bi {icono}"></i>')

@register.filter
def clp(value):
    try:
        return '{:,.0f}'.format(float(value)).replace(',', '.')
    except:
        return value
    
@register.filter
def especialidad_label(value):
    labels = {
        'dentista_general': 'Dentista General',
        'asistente':        'Asistente',
        'secretaria':       'Secretaria',
        'implantólogo':     'Implantólogo',
        'periodoncista':    'Periodoncista',
        'rehabilitador':    'Rehabilitador',
        'ortodoncista':     'Ortodoncista',
        'odontopediatra':   'Odontopediatra',
        'endodoncista':     'Endodoncista',
        'patologo_oral':    'Patólogo Oral',
        'ttm_dof':          'TTM y DOF',
        'otro':             'Otro',
    }
    return labels.get(value, value)


@register.filter
def mul(value, arg):
    try:
        return float(value) * float(arg)
    except:
        return 0