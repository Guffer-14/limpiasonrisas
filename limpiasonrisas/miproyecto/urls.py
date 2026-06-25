from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from miprimerapp import views
from django.contrib.auth import views as auth_views

urlpatterns = [
    path('password-reset/',         views.password_reset,      name='password_reset'),
    path('accounts/reset/<uidb64>/<token>/',
         auth_views.PasswordResetConfirmView.as_view(
             template_name='registration/password_reset_confirm.html',
             success_url='/accounts/reset/done/'
         ),
         name='password_reset_confirm'),
    path('accounts/reset/done/',
         auth_views.PasswordResetCompleteView.as_view(
             template_name='registration/password_reset_complete.html'
         ),
         name='password_reset_complete'),
    
    #CRUD agregar recordar
    path('admin/',                  admin.site.urls),
    path('',                        views.index,               name='index'),
    path('catalogo/',               views.catalogo,            name='catalogo'),
    path('asesoria/',               views.asesoria_inicio,     name='asesoria_inicio'),
    path('catalogo/<int:pk>/',      views.detalle_producto,    name='detalle_producto'),
    path('contacto/',               views.contacto,            name='contacto'),
    path('inscripcion/',            views.inscripcion_clinica, name='inscripcion_clinica'),
    path('dashboard/',              views.dashboard_clinica,   name='dashboard_clinica'),
    path('pedidos-activos/',        views.pedidos_activos,     name='pedidos_activos'),
    path('mis-pedidos/',            views.mis_pedidos,         name='mis_pedidos'),
    path('finalizar-pedido/',       views.finalizar_pedido,    name='finalizar_pedido'),
    path('admin-panel/',            views.panel_admin,         name='panel_admin'),
    path('login/',                  views.login_view,          name='login'),
    path('logout/',                 views.logout_view,         name='logout'),
    path('registro/',               views.registro,            name='registro'),
    path('verificar-disponibilidad/', views.verificar_disponibilidad, name='verificar_disponibilidad'),
    
    # APIs
    path('api/precio/<int:pk>/',    views.api_precio_producto, name='api_precio_producto'),
    path('api/buscar-productos/',      views.api_buscar_productos,       name='api_buscar_productos'),
    path('mi-stock/',                  views.mi_stock,                   name='mi_stock'),
    path('mi-cuenta/',                 views.mi_cuenta,                  name='mi_cuenta'),
    path('mis-datos/',                 views.mis_datos,                  name='mis_datos'),
    path('api/registrar-venta/',       views.api_registrar_venta,        name='api_registrar_venta'),
    path('api/actualizar-minimo/',     views.api_actualizar_minimo,      name='api_actualizar_minimo'),
    path('api/agregar-carrito-stock/', views.api_agregar_carrito_stock,  name='api_agregar_carrito_stock'),
    path('api/ajuste-inventario/',     views.api_ajuste_inventario,      name='api_ajuste_inventario'),
    path('api/sugerir-producto/',      views.api_sugerir_producto,       name='api_sugerir_producto'),
    path('api/eliminar-venta/',        views.api_eliminar_venta,         name='api_eliminar_venta'),
    path('api/carrito-publico/agregar/',    views.api_carrito_publico_agregar,    name='api_carrito_publico_agregar'),
    path('api/carrito-publico/actualizar/', views.api_carrito_publico_actualizar, name='api_carrito_publico_actualizar'),
    path('api/carrito-publico/eliminar/',   views.api_carrito_publico_eliminar,   name='api_carrito_publico_eliminar'),
    path('api/volver-a-pedir/',            views.api_volver_a_pedir,             name='api_volver_a_pedir'),
    path('finalizar-pedido-publico/',      views.finalizar_pedido_publico,       name='finalizar_pedido_publico'),
    path('seleccionar-medio-pago/<int:solicitud_id>/', views.seleccionar_medio_pago, name='seleccionar_medio_pago'),
    path('confirmar-pago-publico/',        views.confirmar_pago_publico,         name='confirmar_pago_publico'),
    
    # ── PANEL ADM ─────────────────────────────────────────────────────────────────
    path('adm/', views.adm_dashboard, name='adm_dashboard'),
    path('adm/usuarios/', views.adm_lista_usuarios, name='adm_lista_usuarios'),
    path('adm/usuarios/crear/', views.adm_crear_usuario, name='adm_crear_usuario'),
    path('adm/usuarios/editar/<int:id>/', views.adm_editar_usuario, name='adm_editar_usuario'),
    path('adm/usuarios/eliminar/<int:id>/', views.adm_eliminar_usuario, name='adm_eliminar_usuario'),
    # Mensajes ADM
    path('adm/mensajes/',                    views.adm_lista_mensajes,   name='adm_lista_mensajes'),
    path('adm/mensajes/resolver/<int:id>/',  views.adm_resolver_mensaje, name='adm_resolver_mensaje'),
    path('adm/mensajes/tomar/<int:id>/',     views.adm_tomar_mensaje,    name='adm_tomar_mensaje'),
    # Categorías ADM
    path('adm/categorias/',                   views.adm_lista_categorias,   name='adm_lista_categorias'),
    path('adm/categorias/crear/',             views.adm_crear_categoria,    name='adm_crear_categoria'),
    path('adm/categorias/editar/<int:id>/',   views.adm_editar_categoria,   name='adm_editar_categoria'),
    path('adm/categorias/eliminar/<int:id>/', views.adm_eliminar_categoria, name='adm_eliminar_categoria'),
    # Productos ADM
    path('adm/productos/',                    views.adm_lista_productos,   name='adm_lista_productos'),
    path('adm/productos/crear/',              views.adm_crear_producto,    name='adm_crear_producto'),
    path('adm/productos/editar/<int:id>/',    views.adm_editar_producto,   name='adm_editar_producto'),
    path('adm/productos/eliminar/<int:id>/',  views.adm_eliminar_producto, name='adm_eliminar_producto'),
    # Precios ADM
    path('adm/productos/precios/',                views.adm_precios_productos,   name='adm_precios_productos'),
    path('adm/productos/precios/editar/<int:id>/', views.adm_editar_precio,       name='adm_editar_precio'),
     # Compras a proveedores ADM
    path('adm/compras/',           views.adm_lista_compras,  name='adm_lista_compras'),
    path('adm/compras/nueva/',     views.adm_nueva_compra,   name='adm_nueva_compra'),
    path('adm/compras/<int:id>/',  views.adm_detalle_compra, name='adm_detalle_compra'),
    path('adm/compras/<int:id>/editar/', views.adm_editar_compra, name='adm_editar_compra'),
    # Pedidos ADM
    path('adm/pedidos/',                       views.adm_lista_pedidos,  name='adm_lista_pedidos'),
    path('adm/pedidos/<str:tipo>/<int:id>/',   views.adm_detalle_pedido, name='adm_detalle_pedido'),
# ── PANEL GESTOR ──────────────────────────────────────────────────────────────
    path('gestor/',                              views.gestor_dashboard,         name='gestor_dashboard'),
    path('gestor/productos/',                    views.gestor_lista_productos,   name='gestor_lista_productos'),
    path('gestor/productos/crear/',              views.gestor_crear_producto,    name='gestor_crear_producto'),
    path('gestor/productos/editar/<int:id>/',    views.gestor_editar_producto,   name='gestor_editar_producto'),
    path('gestor/productos/eliminar/<int:id>/',  views.gestor_eliminar_producto, name='gestor_eliminar_producto'),
    path('gestor/categorias/',                   views.gestor_lista_categorias,  name='gestor_lista_categorias'),
    path('gestor/categorias/crear/',             views.gestor_crear_categoria,   name='gestor_crear_categoria'),
    path('gestor/categorias/editar/<int:id>/',   views.gestor_editar_categoria,  name='gestor_editar_categoria'),
    path('gestor/categorias/eliminar/<int:id>/', views.gestor_eliminar_categoria,name='gestor_eliminar_categoria'),
    path('gestor/mensajes/',                     views.gestor_mensajes,          name='gestor_mensajes'),

    
# Legado
    path('contactomodel/',          views.contacto_modelform,  name='contacto_modelform'),
   
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
