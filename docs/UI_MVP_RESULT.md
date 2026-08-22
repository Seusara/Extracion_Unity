# UI MVP — resultado

Fecha: 2026-08-22.

## Alcance

Se agregó una interfaz mínima Tkinter que consume exclusivamente las funciones del core. No contiene lógica de extracción, validación o reinyección.

Flujo visible:

- seleccionar juego;
- analizar;
- seleccionar perfil;
- crear/seleccionar proyecto;
- extraer;
- exportar/importar CSV;
- validar;
- inyectar a un build separado;
- consultar logs y errores.

Editor interno:

- tabla `Original | Translation | Status`;
- búsqueda por ID, original o traducción;
- filtro por estado;
- edición manual;
- estado `intentionally_empty` explícito;
- persistencia atómica en Translation IR mediante el core.

## Verificación

- Suite completa: 21 tests aprobados.
- Paquete instalable en modo editable.
- Entry point: `unity-translator-gui`.
- Prueba de construcción real de widgets: 8 acciones principales.
- Editor abierto programáticamente sobre el proyecto ERICA real: 942 filas mostradas.
- La aplicación visible se lanzó con las rutas de ERICA precargadas para prueba manual.

## Límite

La UI es deliberadamente básica. No se implementaron temas, branding, animaciones ni componentes visuales complejos. La inyección corre en un worker para evitar congelar la ventana, pero sigue siendo un adapter experimental hasta completar playtesting humano del texto modificado.
