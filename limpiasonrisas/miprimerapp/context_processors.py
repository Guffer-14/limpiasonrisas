from .models import CarritoItem, CarritoItemPublico

def carrito_count(request):
    count = 0
    tiene_clinica = False

    if request.user.is_authenticated:
        try:
            clinica = request.user.clinica
            tiene_clinica = True
            count = clinica.carrito_items.count()
        except:
            tiene_clinica = False
            count = CarritoItemPublico.objects.filter(
                usuario=request.user
            ).count()

    return {
        'carrito_count': count,
        'tiene_clinica': tiene_clinica,
    }