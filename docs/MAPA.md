# Mapa: el barrio jugable

Actualizado: 27 de noviembre de 2026 (v5: fila sur, calle comercial y paso bajo nivel E4). Diseño del primer mapa real de Barrio, que reemplaza al barrio gris (`GreyboxNeighborhood`). Las reglas que el mapa tiene que servir están en [DISENO_JUEGO.md](DISENO_JUEGO.md); el arte y sus especificaciones, en [ARTE.md](ARTE.md).

## 1. Objetivos

1. **Cómodo para jugar:** se entiende dónde estás y hacia dónde ir sin minimapa, nada traba al personaje, las distancias se recorren sin aburrir.
2. **Bueno para PvP:** varias rutas entre cada robo y cada salida, coberturas cada pocos metros, ninguna calle es un pasillo de francotirador sin cortes.
3. **Bueno para PvE:** los policías bot navegan todo el barrio jugable (veredas, calles, plaza, pasillos) y tienen lugares claros donde patrullar.
4. **Lindo y creíble:** Caseros real y contemporáneo, legible de día y de noche.

## 2. Medidas (Caseros real)

| Elemento | Medida |
| --- | --- |
| Manzana (línea municipal a línea municipal) | 86,6 m |
| Calle (LM a LM) | 17,32 m: vereda 3,5 m + calzada 10,32 m + vereda 3,5 m |
| Avenida (LM a LM) | 26 m: vereda 4,5 m + calzada 17 m con cantero central con reja + vereda 4,5 m |
| Lote | 8,66 m de frente; 10 por lado de manzana, esquinas con ochava de 4 m |
| Cordón | 16 cm (el personaje sube escalones de hasta 45 cm) |
| Altura de casas | 1 planta 3,2-4 m, 2 plantas 6,5-7 m; torres de 25-45 m solo como hitos |

## 3. Trazado

Coordenadas en cm, X hacia el este, Y hacia el norte, Z = 0 en la calzada.

```
 Y
 ^      AFUERA NORTE: estación, andén (llegada), playón, reducidor
 |  =[E4 túnel]==[E1 paso a nivel]=======[E2 pasarela]=====  vías (alambrado)
 |  calle paralela a las vías                                  |   A
 |  [M0,1 baldío]   [M1,1 PLAZA]   [M2,1 torre + comercios]  | AV | F
 |  calle                                              [E3]  | E  | U
 |  [M0,0 chalets]  [M1,0 COMISARÍA] [M2,0 comercios]        | N  | E
 |  CALLE COMERCIAL (arcos, locales, edificios de 4-6 pisos)  | I  | R
 |  [M0,S]           [M1,S]          [M2,S]   (casas + edif.)  | DA | A
 |  calle Fondo                                                |    |
 |  tapial de galpones (cerrado)                               |    |
 +-------------------------------------------------------------------> X
   tapial del club (cerrado, oeste)
```

| Franja | X | Y |
| --- | --- | --- |
| Calle oeste (borde, cerrada por tapial del club en X<0) | 0 - 1.732 | toda |
| Columna de manzanas 0 / calle / 1 / calle / 2 | 1.732-10.392 / 10.392-12.124 / 12.124-20.784 / 20.784-22.516 / 22.516-31.176 | |
| Avenida (lado barrio LM 31.176, lado Afuera LM 33.776) | 31.176 - 33.776 | toda |
| Afuera Este (vereda de enfrente y locales) | 33.776 - 40.000 | 0 - 36.000 |
| Calle Fondo (borde, cerrada por los galpones en Y < -10.392) | | -10.392 - -8.660 |
| Fila de manzanas S (v5) | | -8.660 - 0 |
| Calle comercial (antes "calle sur") | | 0 - 1.732 |
| Fila de manzanas 0 / calle / 1 | | 1.732-10.392 / 10.392-12.124 / 12.124-20.784 |
| Calle paralela a las vías | | 20.784 - 22.516 |
| Vías (alambrado en 22.616 y 25.916, dos vías) | | 22.516 - 26.016 |
| Afuera Norte | 0 - 40.000 | 26.016 - 36.000 |

Barrio jugable: unos 310 x 330 m (v5, con la fila sur). Para 16 jugadores alcanza para que haya encuentros sin que estén todos juntos; se puede crecer agregando una columna de manzanas sin cambiar nada más.

## 4. Las salidas

Tres salidas con perfiles de riesgo distintos. Las tres son también la entrada al barrio desde Afuera.

| Salida | Dónde | Cómo se juega |
| --- | --- | --- |
| **E1 Paso a nivel** | Calle entre columnas 0 y 1 (X 10.392-12.124) cruzando las vías | Abierta y ancha: rápida pero muy vigilable. Barreras, casilla del guardabarrera |
| **E2 Pasarela peatonal** | Sobre las vías en X ~24.840, escaleras a ambos lados | Solo a pie. Alta y expuesta: da vista sobre la calle de las vías (vigía policial), pero el que sube queda a la vista |
| **E3 Cruce de la avenida** | Semáforo en Y ~11.258 (sigue la calle entre filas). El cantero central tiene reja salvo ahí | La más lejos del reducidor, pero con más cobertura (paradas de colectivo, autos, locales) |
| **E4 Paso bajo nivel** (v5) | Túnel peatonal bajo las vías en X ~4.900: se entra por un hueco del alambrado (X 3.920-4.180) desde la calle paralela, escalera paralela a las vías, túnel de 30 m pintado a franjas de colores, escalera de salida y patio ferroviario cerrado | Encerrado y corto: nadie lo ve desde lejos, pero adentro no hay dónde esconderse. Ideal para el que viene del oeste o de la fila sur |

La `ExitZone` de cada salida está **del lado de Afuera** (pasando las vías, o en la vereda de enfrente de la avenida), así no se sale por error. Las marca un piso verde, un tótem con flecha y un cartel SALIDA.

| ExitZone | Centro (X, Y) | Medio tamaño (X, Y) |
| --- | --- | --- |
| `ExitZone_E1_PasoNivel` | 11.258, 26.800 | 900 × 600 |
| `ExitZone_E2_Pasarela` | 24.840, 26.250 (al pie de la escalera norte) | 430 × 320 |
| `ExitZone_E3_Avenida` | 33.560, 11.258 (vereda de enfrente) | 215 × 680 |
| `ExitZone_E4_Tunel` | 4.050, 26.560 (patio ferroviario, al salir del túnel) | 520 × 420 |

## 5. Zonas y puntos fijos

| Punto | Dónde | Notas |
| --- | --- | --- |
| Llegada de jugadores (zona segura) | Andén de la estación (X 14.000-20.500, Y ~25.000-25.900, 40 cm de alto). `PlayerStart` en (19.250, 25.350) y (19.950, 25.350), mirando a la plaza y la torre. La zona segura cubre andén, estación y explanada (centro 17.250, 26.750) | Entre E1 y E2. La formación que los trajo queda detenida al oeste del andén |
| Reducidor | Galpón en Afuera Norte, `FenceStation` en (22.200, 30.000) | 60-110 m desde E1 y E2, ~280 m desde E3 |
| Comisaría (zona segura adentro, mostrador, aparición de policías) | Manzana 1,0, frente norte mirando a la plaza, X 15.000-18.500 | Central: llega a cualquier punto en menos de 150 m |
| Celda | Dentro del corazón de la manzana 1,0, detrás de la comisaría | Inaccesible desde la calle |
| Plaza | Manzana 1,1 entera | Centro del mapa: árboles, bancos, juegos, mástil, puesto de diarios |

## 6. Manzanas

El corazón de cada manzana (los fondos) **no es accesible**: las casas forman un frente continuo y los fondos se tapan con medianeras y techos. Así cada manzana es un bloque que corta la visión, y los atajos son pocos y elegidos.

| Manzana | Carácter | Robos | Atajo |
| --- | --- | --- | --- |
| 0,0 (SO) | Chalets con tejas, rejas altas, jardín | Casas ricas (botín alto, alarma más rápida) | Pasillo de PH norte-sur por el medio |
| 0,1 (NO) | Casas bajas viejas y de 2 plantas | Botín bajo y medio | **Terreno baldío** que cruza este-oeste |
| 1,0 (S) | Comisaría al norte; casas en los otros lados | Pocas (cerca de la policía) | Ninguno |
| 1,1 (centro) | **Plaza** | Kiosco de diarios | Toda la plaza se cruza |
| 2,0 (SE) | Casas al oeste y sur; **locales** sobre la avenida | Comercios: robo rápido, botín chico | Pasillo de PH este-oeste |
| 2,1 (NE) | **Torre de 12 pisos** en la esquina (hito) y locales sobre la avenida | Comercios | Pasillo norte-sur |
| 0,S / 1,S / 2,S (v5) | Casas bajas con edificios de departamentos (4 y 6 pisos, PB comercial) mezclados; el frente norte da a la **calle comercial** con locales y edificios | Muchos comercios: robo rápido, botín chico | Ninguno |

**Calle comercial** (estilo 3 de Febrero): entre la fila 0 y la fila S. Locales y edificios con PB comercial en los dos frentes de las manzanas S y en el frente sur de las 1,0 y 2,0; arcos de caño con guirnaldas de lamparitas que cruzan la calle cada ~28 m (encendidas de noche).

Esquinas: ochava con kiosco, almacén o verdulería en la mitad de las esquinas (robos rápidos). Pasillos: 1,5 a 2 m de ancho, entre tapiales de 2,5 m, con 2 o 3 puertas de PH robables.

Densidad de robos: unas 86 puertas robables (v5) en todo el barrio (no todas las casas), repartidas para que haya robos a menos de 40 m de cualquier punto. El resto de las casas tiene puertas cerradas con reja y candado, que se leen distinto.

## 7. Coberturas y líneas de visión

- Autos estacionados genéricos (sin marcas) en un lado de cada calle, uno cada uno o dos lotes, con huecos para cruzar.
- Árboles de vereda cada lote (v5: mayoría de plátanos podados y pelados como en invierno, mezclados con fresnos y paraísos con hoja; la plaza siempre verde), postes cada 30 m, canastos de basura, contenedores en las esquinas.
- Ninguna calle queda abierta más de 120 m sin cortes: en las calles largas este-oeste hay una obra con vallas y un volquete, un camión estacionado o un puesto.
- La avenida tiene paradas de colectivo y el cantero central como cobertura.
- Sin techos transitables en el MVP. La única altura jugable es la pasarela E2.

## 8. Orientación: hitos

Que se sepa dónde estás mirando cualquier pantalla, sin minimapa:

1. **Torre** de 12 pisos (esquina NE): se ve desde todo el barrio, marca el noreste y la avenida.
2. **Vías y catenaria** al norte: horizonte bajo y abierto.
3. **Plaza** en el centro: el verde y el mástil.
4. **Comisaría**: frente azul y balizas.
5. **Avenida** al este: más ancha, comercios con carteles inventados y colectivos.
6. **Carteles de calle** en cada esquina.

## 9. Comodidad

- Colisiones simples (cajas y cápsulas). Cables, bolsas, plantas chicas y detalles finos sin colisión.
- Rampas en los garajes y en las esquinas: el personaje nunca se traba con el cordón.
- Nada de paredes invisibles: los bordes del mapa son tapiales, vías con alambrado y edificios.
- Puertas robables legibles a 10 m: punto de robo con su color de estado y lámpara encendida de noche.
- Noche jugable: luminarias cada 25-30 m con charcos de luz que se solapan; nunca negro total.

## 10. PvE: navegación de los bots

- Un `NavMeshBoundsVolume` cubre el barrio, las salidas y Afuera.
- Veredas, calzadas, plaza, pasillos (mínimo 1,5 m) y baldío son navegables. Los fondos de manzana no.
- Puntos de patrulla sugeridos: esquinas de la plaza, las tres salidas y la avenida.

## 11. Presupuesto técnico

- 60 fps en la PC de desarrollo (RTX 5050) con 16 jugadores.
- Casas como un juego chico de variantes repetidas (Nanite), con colores y orden variados para que no se note la repetición.
- Cables por tramo de calle en una sola malla Nanite sin colisión.

## 12. Cómo se genera

Por script, sobre `/Game/Barrio/Maps/L_Greybox`: `game/Scripts/arte/build_barrio.py` arma todo y reubica los actores de juego (llegada, zonas seguras, salidas, comisaría, reducidor, celda, puntos de robo). Es reproducible: se puede regenerar con otra semilla o con más manzanas.
