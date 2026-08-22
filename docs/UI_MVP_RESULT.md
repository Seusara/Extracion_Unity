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

Tutorial inicial:

- cuatro pasos breves que recorren selección, extracción, edición/validación e inyección segura;
- tutorial final exclusivamente textual, sin fotografías ni capturas del juego;
- indicación contextual del control correspondiente en cada paso;
- navegación anterior/siguiente y opción para omitir;
- preferencia persistente `Mostrar tutorial al iniciar`;
- acceso permanente desde `Ver tutorial`;
- no bloquea el uso posterior de la aplicación.

## Verificación

- Suite completa: 24 tests aprobados.
- Paquete instalable en modo editable.
- Entry point: `unity-translator-gui`.
- Prueba de construcción real de widgets: 8 acciones principales.
- Editor abierto programáticamente sobre el proyecto ERICA real: 942 filas mostradas.
- La aplicación visible se lanzó con las rutas de ERICA precargadas para prueba manual.
- Tutorial verificado: `Paso 1 de 4`, título y navegación renderizados correctamente.

## Revisión visual final

Se aplicaron principios de Apple HIG adaptados a una aplicación nativa de Windows:

- jerarquía tipográfica clara y lenguaje breve orientado a acciones;
- controles nativos con tema del sistema y color secundario semántico;
- una única acción final enfatizada: `8 Generar copia`;
- agrupación por proyecto, flujo y estado;
- progreso indeterminado durante tareas del pipeline y determinado en el tutorial;
- feedback textual además del indicador visual;
- tutorial breve, opcional, recuperable con `Ver tutorial` o `F1`;
- navegación por teclado mediante los controles nativos;
- recordatorio visible de que el original permanece protegido.

## Límite

La UI es deliberadamente básica. No se implementaron temas, branding, animaciones ni componentes visuales complejos. La inyección corre en un worker para evitar congelar la ventana, pero sigue siendo un adapter experimental hasta completar playtesting humano del texto modificado.
