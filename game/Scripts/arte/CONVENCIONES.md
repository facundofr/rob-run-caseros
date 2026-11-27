# Convenciones compartidas — arte de prueba de Barrio (Caseros)

Proyecto: Unreal Engine 5.8.4, Windows, RTX 5050 8 GB, Lumen. Juego multijugador en tercera persona ambientado en Caseros (conurbano bonaerense, época actual).
Estas reglas valen para los tres trabajos en paralelo (texturas, fachada/calle, ambiente). Respetarlas al pie de la letra para que encajen sin retrabajo.

## Reglas del proyecto que no se negocian
- Nada de marcas reales, logos ni carteles reales. Nada copiado de otros juegos (en particular ROB RUN). Identidad propia: Caseros real.
- Unidades: 1 uu = 1 cm. Z arriba. Personaje de 180 cm. Puerta 210 cm alto. Módulo de fachada 300 cm.
- Comentarios y logs en español.

## Referencias visuales
`/mnt/user-data/outputs/refs/*.jpg` (Street View de Caseros, 800x600). Mirarlas con la herramienta Read antes de decidir colores, proporciones y materiales.

## Carpetas de salida (en este contenedor)
- Texturas PNG: `/home/claude/barrio_art/textures/<Set>/T_<Set>_BC.png`, `_N.png`, `_ORM.png`
- Scripts Python de Unreal: `/home/claude/barrio_art/scripts/`
El agente principal copia todo a la PC y corre los scripts en el editor.
En la PC, las texturas quedan en `C:/Users/facufr/Desktop/rob-run-caseros/rob-run-caseros/game/ArtSource/Textures/<Set>/` (ruta que deben usar los scripts para importar).

## Texturas (sets fijos)
Sets: `Revoque`, `Ladrillo`, `Baldosa`, `Asfalto`, `Hormigon`, `Chapa`, `Madera`, `Tejas`, `MetalPintado`, `PiedraLaja`.
- 2048x2048, tileables sin costura.
- `_BC`: base color sRGB. Revoque y MetalPintado en gris claro casi neutro (se tiñen con el parámetro Tint).
- `_N`: normal en convención DirectX (la de Unreal: verde invertido, Y-).
- `_ORM`: R = oclusión, G = rugosidad, B = metálico. Lineal (no sRGB).
- Tamaño real que cubre cada textura (para el tiling): Revoque 200 cm, Ladrillo 120 cm, Baldosa 80 cm (4x4 baldosas de 20 cm), Asfalto 400 cm, Hormigon 150 cm, Chapa 100 cm (canaleta cada ~7,6 cm, vertical), Madera 120 cm (tablas verticales), Tejas 120 cm, MetalPintado 100 cm, PiedraLaja 150 cm.

## Contenido en Unreal
- Texturas: `/Game/Barrio/Art/Textures/<Set>/T_<Set>_BC|_N|_ORM`
- Material maestro: `/Game/Barrio/Art/Materials/M_Barrio_Surface`
  Parámetros: `BaseColorTex`, `NormalTex`, `ORMTex` (texture), `Tint` (vector, default blanco), `TileSizeCM` (scalar, tamaño real que cubre la textura), `NormalStrength` (1), `RoughnessMult` (1), `GrimeAmount` (0..1, suciedad y humedad en la base de muros, gradiente por altura de mundo), `GrimeHeightCM` (60), `MacroVariation` (0..1, variación de tono a gran escala para romper la repetición).
  Proyección: triplanar en coordenadas de mundo (WorldAlignedTexture / WorldAlignedNormal), así la geometría generada no depende de sus UVs.
- Instancias: `/Game/Barrio/Art/Materials/MI_<Nombre>`. Nombres FIJOS que usa la fachada:
  `MI_Revoque_Blanco`, `MI_Revoque_Gris`, `MI_Revoque_Rosa`, `MI_Revoque_VerdeAgua`, `MI_Revoque_Amarillo`,
  `MI_Ladrillo`, `MI_Baldosa`, `MI_Asfalto`, `MI_Hormigon`, `MI_Chapa_Gris`, `MI_Chapa_Verde`, `MI_Madera`,
  `MI_Tejas`, `MI_Metal_Negro`, `MI_Metal_Verde`, `MI_PiedraLaja`, `MI_Vidrio`, `MI_PosteMadera`, `MI_Cable`.
- Geometría de la fachada: `/Game/Barrio/Art/Facade/SM_<Nombre>`
- Mapa: `/Game/Barrio/Maps/L_Greybox` (ya existe, plantilla Basic: DirectionalLight, SkyAtmosphere, SkyLight, ExponentialHeightFog, VolumetricCloud, SM_SkySphere, más el barrio gris generado por código).
- Zona libre para la calle de prueba ("FacadeTest"): el bloque va en X de -3800 a -600, Y de 1500 a 5500, Z=0 (terreno "Afuera", plano, fuera del barrio gris). El frente de las casas mira a +X (hacia el barrio). El jugador aparece en (500, 500, 100).
- Los scripts deben ser idempotentes (si el asset existe, reemplazarlo o reutilizarlo sin romper) y loguear con `unreal.log("[ARTE] ...")`.

---------------------------------------------------------------------------------------------------
# v2 (26/11): del bloque de prueba al mapa jugable

El diseño del mapa está en `/home/claude/barrio_art/MAPA.md` (fuente de verdad del trazado, salidas, zonas y coordenadas).
La revisión de arte del pase v1 está resumida en el pedido de cada agente.

## Nuevas instancias de material (las crea setup_materials.py; la geometría las usa por nombre)
`MI_Corteza`, `MI_PosteHormigon`, `MI_Tierra`, `MI_Pasto`, `MI_Agua`, `MI_Hormigon_Bacheo`, `MI_Madera_Puerta`,
`MI_Follaje` (verde follaje, no metal), `MI_Plastico_Negro`, `MI_Neumatico`,
`MI_Auto_Blanco`, `MI_Auto_Gris`, `MI_Auto_Rojo`, `MI_Auto_Azul`, `MI_Auto_Negro`,
`MI_Pintura_Blanca`, `MI_Pintura_Amarilla` (sendas, líneas, cordón amarillo),
`MI_Comisaria_Azul`, `MI_Cartel_Blanco`, `MI_Cartel_Rojo`, `MI_Cartel_Verde`, `MI_Cartel_Azul`,
`MI_Vidrio_Local`, `MI_Emisivo_Calido` (cabeza de luminaria / ventanas encendidas), `MI_Emisivo_Baliza_Azul`, `MI_Emisivo_Baliza_Roja`,
`MI_Riel` (acero de vía), `MI_Durmiente`, `MI_Balasto` (piedra partida de vía), `MI_Alambrado`.
Se mantienen todas las MI de v1.

## Contrato entre geometría e iluminación
- Cada luminaria de calle que construya la geometría deja un actor `TargetPoint` en la cabeza de la lámpara,
  con label `LUM_<n>` y tag de actor `LUMINARIA`, rotado mirando hacia abajo, en la carpeta `Barrio/Luminarias`.
- La iluminación (preset noche) pone una SpotLight en cada uno de esos puntos y las apaga/borra en los presets de día.
- Las ventanas o carteles encendidos de noche usan `MI_Emisivo_Calido` (la iluminación no los toca).

## Carpetas de actores del mapa
`Barrio/Manzanas`, `Barrio/Calles`, `Barrio/Vias`, `Barrio/Afuera`, `Barrio/Props`, `Barrio/Autos`, `Barrio/Cables`, `Barrio/Luminarias`, `Barrio/Gameplay`, `Ambiente` (iluminación).

## Materiales v2 (setup_materials.py / gen_textures.py)
- Sets nuevos (mismas reglas: 2048, tileables, normal DirectX, ORM lineal): `Corteza` 120 cm (fresno), `Pasto` 200 cm (visto desde arriba),
  `Tierra` 200 cm, `Balasto` 120 cm, `Riel` 80 cm (el eje u = largo del riel), `Follaje` 150 cm (copas lejanas).
- `Ladrillo` ahora cubre 240 cm (36 hiladas x 10 ladrillos); `MI_Ladrillo` usa TileSizeCM 264.
- Normales importadas como TC_NORMALMAP (BC5); ORM como TC_MASKS.
- Parámetros nuevos de `M_Barrio_Surface`: `Saturation`, `HueVariation`, `AntiTile` (0 en texturas con patrón), `StreakAmount`, `MossAmount`,
  `ContactGrime` + `ContactRadiusCM` + switch estático `UseContactGrime` (Mesh Distance Fields), `GroundZ`, `PolishTop` (rieles),
  `RoughnessAdd`, `MetallicAdd`, `Specular`, `EmissiveColor` + `EmissiveStrength` (nits) + `EmissivePulseHz`/`EmissivePhase` (balizas).
  Todo opaco: el vidrio es oscuro y reflectivo, sin Opacity.
- Instancia extra opcional: `MI_Emisivo_Luminaria` (cabeza de luminaria LED, 150 nits); `MI_Emisivo_Calido` sigue sirviendo para ventanas y luminarias.

---------------------------------------------------------------------------------------------------
# v4 (26/11): carteles con texto, atmósfera de tarde, props (revisión del director 5/10)

## Orden de corrida
1. En el contenedor: `python3 gen_textures.py Carteles` (ya corrido) -> `textures/Carteles/` (atlas + `carteles_atlas.json`).
   Copiar la carpeta ENTERA (con el json) a `ArtSource/Textures/Carteles/`.
2. En UE: `setup_materials.py` (importa `/Game/Barrio/Art/Textures/Carteles/*`, crea `M_Barrio_Cartel`, `M_Barrio_Cartel_Mascara` y las MI).
3. `build_barrio.py` (las MI v4 se registran solas en `barrio_kit.MATS` al importar `barrio_props`). 4. `setup_lighting.py`.

## Texturas de texto (atlas, NO tileables, NO triplanar)
| Atlas | Tamaño | Contenido |
| --- | --- | --- |
| `T_Carteles_Calle_BC/_ORM` | 2048x2048 | 16 placas de calle 1024x256 (4:1), 2 columnas x 8 filas |
| `T_Carteles_Comercio_BC/_ORM` | 2048x4096 | 16 marquesinas 2048x256 (8:1), una por fila |
| `T_Carteles_Varios_BC(RGBA)/_ORM` | 2048x2048 | comisaría y estación (8:1), salidas y NO ESTACIONAR (4:1), bandera (2:1), afiches (1:1), 4 pintadas (1:1, con alfa) |
| `T_Carteles_N` | 256x256 | normal plana compartida |
ORM: R oclusión, G rugosidad, B metálico (saltaduras de pintura = acero). Desgaste horneado: sol (decolorado), chorreaduras, óxido en bordes y bulones.
`carteles_atlas.json` = MI -> atlas, `rect_px` [x, y, w, h], `uv` [u0, v0, su, sv], `aspecto`, `mascara`. setup_materials tiene la misma tabla de respaldo.

## Material de texto
`M_Barrio_Cartel` (opaco) y `M_Barrio_Cartel_Mascara` (masked, máscara = alfa del BC; solo pintadas). Usan **UV0 de la malla**:
`UV' = AtlasRect.rg + saturate(UV0) * AtlasRect.ba` (V hacia abajo, origen arriba-izquierda). Parámetros: `BaseColorTex`, `ORMTex`, `NormalTex`,
`AtlasRect` (vector), `Tint`, `Saturation`, `RoughnessMult`, `MetallicMult`, `NormalStrength`, `Specular`, `EmissiveStrength` (nits, 0 = apagado; el color emitido es el del cartel), `EmissiveColor`.
**La cara de texto de la malla tiene que tener UV0 0..1** (u a la derecha de quien lee, v hacia abajo). Usar los helpers de `barrio_props` (abajo); una caja del kit (box/cbox) NO sirve: sus UV no están controladas.

## MI nuevas (nombres exactos)
- Placas de calle (azul, letras blancas, sin escudo), aspecto 4:1: `MI_CartelCalle_<slug>` con slug en
  `ValentinGomez, Urquiza, AvSanMartin, Ferreyra, Alberdi, Nicaragua, Sabattini, Fischetti, MarianoMoreno, EstebanMerlo, Bonifacini, Puan, Rauch, MarcoPolo, Espana, Constitucion`.
  Slots de la malla compartida: `MI_CartelCalle_X` (default Valentín Gómez) y `MI_CartelCalle_Y` (default Nicaragua).
- Comercios inventados, aspecto 8:1: `MI_Comercio_<slug>`: `AlmacenDonTito, Kiosco24hs, VerduleriaLaEsquina, FerreteriaElTornillo, PizzeriaLoDeCacho, FarmaciaDelBarrio, CarniceriaLosHermanos, PanaderiaLaEspiga, PeluqueriaEstilo, RotiseriaDonaRosa, LibreriaElLapiz, GomeriaElRayo, LavaderoBurbujas, PolirrubroLosChicos, DespensaMary, BazarElSol`.
- `MI_Cartel_Comisaria` ("DESTACAMENTO CASEROS", 8:1; policía ficticia: no usar la denominación real de comisarías bonaerenses), `MI_Cartel_Estacion` ("CASEROS", 8:1, sin logos de operadora),
  `MI_Cartel_Salida` / `MI_Cartel_Salida_Der` / `MI_Cartel_Salida_Izq` (4:1, el mismo diseño en las tres salidas), `MI_Cartel_NoEstacionar` (4:1),
  `MI_Afiche_SeVende`, `MI_Afiche_Alquilo` (1:1), `MI_Pintada_1..4` (1:1, enmascaradas), `MI_Bandera_Celeste` (2:1, #75AADB con franja blanca y Sol simple).
- Superficie (triplanar, `M_Barrio_Surface`): `MI_Ladrillo_Torre`, `MI_Hormigon_Pilar`.
- Todas ya están en `barrio_kit.MATS` en tiempo de corrida (`barrio_props.registrar_materiales()`); si se agrega otra: `P.registrar_materiales(['MI_...'])`.

## API de barrio_props para la geometría
- `P.placa_texto(mb, mi, cx, cy, z0, ancho, alto=None, espesor=1.5, yaw=0.0, dos_caras=False)`: placa con texto.
  Marco antes de yaw: caja centrada en (cx, cy) (cx = centro del espesor), **cara de texto a +X** (convención de fachadas), ancho en Y, de z0 a z0+alto.
  `alto=None` usa el aspecto del atlas (`P.CARTELES_V4[mi]`): respetarlo para no estirar letras. Funciona dentro de variantes espejadas (`_m`): el texto no se invierte.
- `P.cartel_con_texto(mb, mi, cx, cy, z0, ancho, yaw=0, espesor=2, marco='MI_Metal_Negro', dos_caras=False)` -> alto. Para marquesinas: la banda de color actual (`_cartel`) puede quedar y se le apoya encima una placa 8:1 centrada (p. ej. 400 x 50 cm).
- `P.bandera_celeste(mb, mx, my, z_top, ancho=150, yaw=0)`: bandera doble faz colgada del mástil en (mx, my), hacia +X local.
- `P.pintada(mb, n, cx, cy, z0, ancho=120, yaw=0)`: tag 1..4 sobre una pared que mira a +X (cx = cara de la pared).
- `P.build_cartel_calle()` -> malla `CartelCalle` con slots `MI_CartelCalle_X` (placa a lo largo del eje local X, z 262) y `MI_CartelCalle_Y` (eje local Y, z 236), doble faz.
  **Nombre por instancia** (una sola malla): `put(c, cartel, label, s['pos'], s['yaw'], FP, swaps=P.swaps_cartel_calle_en(s['pos'], s['yaw']))`
  (elige por posición con `P.CALLES_NS` / `P.CALLES_EO`: N-S Fischetti / Valentín Gómez / Mariano Moreno / Av. San Martín; E-O Esteban Merlo / Justo José de Urquiza / Andrés Ferreyra / Sabattini (calle de la estación)),
  o a mano `swaps=P.swaps_cartel_calle('Nicaragua', 'Puan')`. Alternativa horneada: `P.build_cartel_calle('Nicaragua', 'Puan')` (una malla por combinación).
  HOY build_barrio pone los carteles sin swaps: todos dirían Valentín Gómez / Nicaragua hasta que se agregue el `swaps=`.
- `P.build_cartel_salida(variante='' | 'Der' | 'Izq')`: dos caños + placa SALIDA (texto a +X, doble faz), colisión de los caños. Una por salida (E1, E2, E3), del lado barrio mirando hacia la salida.
- `P.build_moto()`: moto 110 cc genérica (+X adelante, pie a -Y), slot de color `MI_Auto_Blanco` (swaps como autos). Instanciar con ~6° de roll hacia el pie (si queda al revés, invertir el signo). Colisión: una caja.
- `P.build_auto(t)` (misma firma): carrocería a tres vistas, pasaruedas, ópticas, paragolpes envolventes; una caja de colisión. Usa ~8 booleanos por auto (solo una vez por tipo: está cacheada).
- `P.build_arbol2(kind, seed, pelado, big)` (misma firma): vereda x1,5 (fresno/plátano 9,5-11 m, paraíso 7,5-8 m, la copa avanza 3-4,5 m sobre la calle), `big` (plaza/Afuera) x2,2 (11-15 m). Colisión: solo una caja de tronco hasta 4 m.

## Pendientes que NO son de este agente (archivos de geometría)
- Cables más finos y menos densos: `barrio_geo.build_cables_group` (radio por cable y cantidad de rulos `torus(..., 0.7, ...)`), catenarias de avenida (`tube(... 0.7/0.8 ...)`, l. ~495). Sugerido: radios 0.45-0.55 cm y 30 % menos tendidos por tramo.
- Reja del cantero central no "penitenciaria": `barrio_geo._reja_panel_template` (sugerido: 90-100 cm de alto, barrotes cada 15-18 cm, sin puntas, pasamanos redondo).
- Carteles de comercio, comisaría (`barrio_edificios`, cartel en blanco 10..10.6 x 338..438), estación (`cbox 'MI_Cartel_Azul'` l. ~1181), mástil de la plaza y tapiales con pintadas: reemplazar las cajas lisas por los helpers de arriba.

## Iluminación v4 (setup_lighting.py)
BRUMA_MULT 0.85. Preset `tarde`: sol 22° / azimut 302° (ONO, sombra de casa de 7 m = 17 m), SkyLight 1.45, nubes cobertura 0.05 (cúmulos sueltos, base 1,4 km, capa 1,6 km),
niebla 0.032 / caída 0.45 / inicio 45 m / opacidad máx 0.96 (100 m 16 %, 300 m 56 %, 500 m 77 %: tapa el borde de Afuera), tinte cálido (inscattering +150/115/70 y aporte del cielo x(1.06, 1.0, 0.9), resplandor hacia el sol desde 60 m),
perspectiva aérea x1.6, exposición EV100 [11.3, 13.1] bias +0.3, exposición local sombras 0.62 / altas 0.78, contraste 1.0, skylight leaking 0.12.
Con `CachedLightingPreExposure=10` la ventana queda en [11.26, 13.66] (seguro [-6, 14]). Los otros presets compensan su Mie por la bruma nueva y también tapan el borde.
