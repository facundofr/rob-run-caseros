# Arte: encargo y especificaciones

Para quien vaya a hacer el arte del juego: el diseñador del equipo y cualquier artista contratado. Define qué hay que hacer, en qué orden y con qué formato técnico, para que todo encaje en Unreal sin retrabajo.

## 1. Qué es el juego

Multijugador en tercera persona ambientado en **Caseros, partido de Tres de Febrero, Zona Oeste del conurbano bonaerense, época actual**. Los jugadores son vecinos, ladrones o policías en un barrio de casas bajas. Reglas completas: [DISENO_JUEGO.md](DISENO_JUEGO.md).

**Estilo:** realista con un poco de estilización, para que se lea bien de lejos y corra en PCs medias. Paleta de conurbano: revoque, ladrillo a la vista, rejas negras y verdes, persianas de chapa, veredas grises, cables, árboles de vereda.

**Reglas que no se negocian:**
- **Nada de marcas reales**: ni comercios, ni autos, ni bancos. Logos y carteles inventados.
- **La policía es ficticia**: uniforme, escudo y nombre propios. Nunca los de la Policía de la Provincia de Buenos Aires ni de la Federal.
- **Nada copiado de otros juegos.**
- Si se usa IA para generar algún asset, se avisa: Steam exige declararlo.

## 2. Quién hace qué

| Tipo de asset | Quién conviene | Por qué |
| --- | --- | --- |
| **Diseño del mapa** (trazado, recorridos, dónde va cada cosa) | El equipo, sobre el mapa gris | Es diseño de juego, no arte: se prueba jugando |
| **Kit modular del barrio** (fachadas, rejas, veredas) | El diseñador del equipo o un artista 3D de entornos | Es lo que más identidad da y no existe en las tiendas |
| **Props genéricos** (árboles, tachos, postes, autos estacionados) | Comprar en Fab | Es barato y ahorra meses |
| **Personajes** | MetaHuman (gratis, incluido en Unreal) más ropa a medida | Calidad alta sin modelar desde cero |
| **Animaciones** | Las del pack Third Person, más Mixamo (gratis) | Movimientos estándar ya resueltos |
| **Armas y moto** | Artista 3D freelance de *hard surface* | Son pocos objetos, muy visibles |
| **Interfaz** (login, HUD, íconos) | El diseñador del equipo | Ya están definidos los textos y la información de cada pantalla |

**Dónde buscar artistas:** ArtStation (portfolios), Workana y Fiverr (freelance), y comunidades de desarrolladores de videojuegos de Argentina. Pedir siempre portfolio con modelos **dentro de Unreal**.

**El contrato tiene que decir** que el juego puede usar los assets de forma comercial, sin límite de tiempo. Lo ideal es una cesión de derechos, o como mínimo una licencia exclusiva.

## 3. Lista de assets por prioridad

La prioridad sigue el plan del juego. La **P1** reemplaza el mapa gris del MVP.

### P1: El barrio jugable

| Asset | Detalle | Cantidad |
| --- | --- | --- |
| Fachadas modulares | Casa baja de 1 planta y de 2 plantas, en módulos de 3 m de ancho: pared lisa, ventana con reja, puerta, portón de garaje, esquina | 10 a 15 piezas, con 3 o 4 variantes de color y material cada una |
| Rejas y portones | Rejas de frente bajas y altas, portón corredizo, puerta de reja | 6 a 8 |
| **Puerta robable** | La puerta de entrada de cada casa: cerrada, forzada (abierta) y versión rica | 3 variantes. Reemplaza la caja azul del mapa gris |
| Vereda y cordón | Baldosa gris, cordón, rampa, árbol de vereda con cantero | 6 a 8 |
| Calle | Asfalto, bacheo, senda peatonal, alcantarilla | Materiales más 4 piezas |
| Medianeras y fondos | Paredes de ladrillo, tapiales | 4 a 6 |
| Iluminación urbana | Poste de luz, cables, luminaria | 3 o 4 |

### P2: Personajes y lugares clave

| Asset | Detalle |
| --- | --- |
| Vecino | 4 a 6 variantes de ropa común (MetaHuman + ropa) |
| Pasamontañas | Prenda que se agrega al personaje al pasar a ladrón |
| Policía | Uniforme ficticio, chaleco, gorra. Escudo inventado |
| Comisaría | Fachada y mostrador interior (hoy es un bloque azul) |
| Reducidor | Un lugar "Afuera": galpón, desarmadero o puesto (hoy es un bloque verde) |
| Celda | Interior de calabozo |
| Salidas del barrio | Paso a nivel con barreras y vías del tren, salida a una avenida |

### P3: Armas, vehículos y detalle

| Asset | Detalle |
| --- | --- |
| Pistola | Genérica, sin marca real. Con animaciones de disparo y recarga |
| Moto | Moto de baja cilindrada genérica (el primer vehículo previsto) |
| Patrullero | Auto genérico con ploteo de la policía ficticia |
| Comercios de barrio | Kiosco, almacén, verdulería: fachadas con carteles inventados |
| Props de vida | Autos estacionados, bicicletas, tachos, garitas de colectivo, carteles de calle ficticios |

## 4. Especificaciones técnicas (para todos los assets)

| Tema | Especificación |
| --- | --- |
| Unidades | **1 unidad = 1 cm.** Una puerta mide unos 210 cm de alto y un módulo de fachada 300 cm de ancho |
| Ejes | Z hacia arriba, X hacia adelante (Unreal). En Blender: exportar con escala 1 y "Apply Transform" |
| Pivote | En la base del objeto. En los módulos, en una esquina inferior, para encajar en una grilla de 50 cm |
| Formato | FBX para mallas y animaciones; texturas en PNG o TGA |
| Polígonos | Módulo de fachada: hasta 5.000 triángulos. Prop chico: hasta 2.000. Personaje: lo que entregue MetaHuman. Arma: hasta 15.000. Moto: hasta 40.000 |
| LODs | 3 niveles para todo lo que se repite (fachadas, props). Nanite opcional para fachadas |
| Texturas | PBR: Base Color, Normal, y un mapa combinado ORM (Oclusión en R, Rugosidad en G, Metálico en B). 2048 px para fachadas y armas, 1024 px para props, 4096 px solo para el personaje |
| Colisión | Colisión simple (cajas) en cada malla; nombrarla `UCX_<nombre>` en el FBX |
| Nombres | Prefijos de Unreal: `SM_` malla estática, `SK_` esqueletal, `M_` material, `MI_` instancia de material, `T_` textura (`T_Fachada01_BC`, `_N`, `_ORM`) |
| Entrega | Archivo fuente (.blend o .max) más los FBX y las texturas, en la carpeta `Content/Barrio/Art/<categoría>` |

**Antes de modelar todo el kit:** entregar **una** fachada completa dentro de Unreal, sobre el mapa gris. Si escala, materiales y rendimiento están bien, se sigue con el resto.

## 5. Cómo se prueba cada entrega

1. Se importa en el proyecto y se coloca en el mapa gris.
2. Se juega encima: el personaje (de 180 cm) tiene que entrar por las puertas, chocar bien con las paredes y verse bien con la cámara en tercera persona.
3. Se mide el rendimiento con 16 jugadores: el objetivo son 60 FPS en una PC media.

## 6. Referencias visuales

- **Google Street View de Caseros**: Av. San Martín, alrededores de la estación Caseros del tren San Martín, calles residenciales cercanas. Fotografiar o capturar fachadas, rejas, veredas y comercios típicos. Solo como referencia: nada de carteles ni marcas reales.
- Una carpeta compartida con 30 a 50 fotos de referencia, ordenadas por categoría (fachadas, rejas, veredas, comercios, vías), antes de empezar a modelar.
