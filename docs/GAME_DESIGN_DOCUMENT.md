# Barrio — Documento de diseño (roles, reglas y loop)

Actualizado: 24 de noviembre de 2026. Fuente de verdad de las reglas del juego: el código se ajusta a este documento.

Barrio toma mecánicas del género *sandbox criminal* (roles que se eligen al entrar, robos, policías jugadores, arresto, coima) y las adapta a **su propia identidad**: Caseros, servidores de 16 jugadores, nombres y valores propios. No es una copia de otro juego. Las referencias de mercado están en [referencias/](referencias/) y se usan solo como inspiración.

## 1. Principio de diseño

**Riesgo opcional, visible y calculable.** Por defecto no se pierde nada. El riesgo empieza cuando el jugador elige ponerse el pasamontañas, y desde ahí todo lo que lleva encima se puede perder. La pregunta que el juego tiene que provocar todo el tiempo es: *"¿lo que llevo encima ya vale más de lo que me puedo permitir perder?"*.

## 2. Zonas del mapa

| Zona | Dónde | Reglas |
| --- | --- | --- |
| **Barrio** | Las manzanas de Caseros | Rigen los roles. Hay policía. Se puede robar |
| **Afuera** | Más allá de las salidas (vías del tren, avenida) | Sin policía ni roles. Acá están el reducidor y el punto de llegada |
| **Zona segura** | Punto de llegada, interior de la comisaría | No se puede hacer daño. Morir ahí no cuesta nada |

**Salidas del barrio:** 2 o 3 puntos fijos (por ejemplo, el paso a nivel de las vías y la salida a la avenida). Cruzarlas es la **única** forma de dejar de ser ladrón.

## 3. Roles

El rol es un **estado del personaje dentro del barrio**, no una clase permanente. Se elige al entrar desde Afuera.

### 3.1 Vecino (por defecto)

- **Puede:** recorrer el barrio sin riesgo, planear rutas, comprar herramientas, usar el banco.
- **No puede:** usar armas, robar.
- **Al morir:** no pierde nada propio. Si lleva botín robado (por ejemplo, yendo al reducidor después de escapar), el botín sí se pierde.
- **Ningún jugador puede hacerle daño sin consecuencia:** a un ladrón le sube el nivel de búsqueda, y un policía comete una falta grave.
- Para qué existe: aprender el mapa y la economía sin castigo. El riesgo es una decisión del jugador.

### 3.2 Ladrón

- **Cómo se vuelve ladrón:** se pone el **pasamontañas** dentro del barrio (tecla dedicada, 2 s de animación). Es una acción explícita y visible: los demás lo ven con pasamontañas y con la marca de ladrón.
- **Cómo deja de serlo:** solo **cruzando una salida del barrio**. Sacarse el pasamontañas no alcanza. También termina al morir, al ser arrestado, o al desconectarse (ver abajo).
- **Puede:** robar casas y comercios, usar armas, atacar y ser atacado por policías **y por otros ladrones**.
- **No puede:** usar el banco, unirse a la policía.
- **Al morir:** pierde **todo lo que lleva encima**: botín, armas, munición y herramientas.
- **Si se desconecta siendo ladrón:** el personaje queda 60 s en el mundo y después **muere**, con las mismas pérdidas. Evita el "me desconecto para salvarme".

### 3.3 Policía

- **Cómo se vuelve policía:** en el mostrador de la comisaría, siendo vecino y sin botín, si hay cupo. Es instantáneo.
- **Cupo:** **máximo 4 policías** por servidor. Con menos de 2 policías humanos, **policías bot** completan la presencia policial (ver 3.5).
- **Turno:** sus pertenencias personales quedan guardadas durante el turno y recibe **equipo del departamento**. Al terminar el turno (en la comisaría), cobra el salario y recupera sus cosas.
- **Puede:** patrullar, recibir avisos de alarma, ver la ubicación de quienes están en nivel 3 de búsqueda, arrestar, confiscar botín.
- **Solo puede dañar ladrones.** El servidor **rechaza** el daño de un policía a un vecino o a otro policía: no es un castigo posterior, directamente no ocurre.
- **Al morir:** pierde solo el equipo del departamento y **reaparece** en la comisaría con 10 s de protección.
- Riesgo bajo a propósito: equilibra que el ladrón arriesga todo.

### 3.4 Cuándo se puede cambiar de rol

| Desde | Hacia | Cómo | Condición |
| --- | --- | --- | --- |
| Vecino | Ladrón | Ponerse el pasamontañas | Dentro del barrio, fuera de zona segura |
| Vecino | Policía | Mostrador de la comisaría | Hay cupo, no lleva botín, no está detenido |
| Ladrón | Vecino | Cruzar una salida del barrio | Al volver a entrar, elige rol de nuevo |
| Policía | Vecino | Terminar el turno en la comisaría | Cobra el salario |
| Cualquiera | — | Cambiar de nuevo | Espera de 5 s entre cambios |

En un grupo de amigos (más adelante), **todos tienen el mismo rol** dentro del barrio.

### 3.5 Policías bot

Agregado propio de Barrio: con 16 jugadores no siempre va a haber 2 policías humanos conectados.

- Aparecen si hay menos de 2 policías humanos. Desaparecen cuando entra un humano.
- Responden alarmas, persiguen y arrestan. Son más lentos y predecibles que un humano: la amenaza principal tienen que seguir siendo los jugadores.

## 4. El robo

1. **Preparación (como vecino):** comprar herramientas (ganzúa), reconocer la ruta y la salida.
2. **Entrar:**
   - **Ganzúa en la puerta:** lento y silencioso. Baja mucho la chance de alarma.
   - **Romper una ventana:** rápido y ruidoso. Alarma casi segura.
   - **Cortar la luz** en el tablero de la cuadra: apaga las alarmas de esa cuadra por un tiempo (más adelante).
   - Agachado: más lento y más sigiloso (ya implementado).
3. **Alarma:** avisa a los policías cercanos con la ubicación, no con la identidad. Las casas ricas y los comercios avisan más rápido. Los **golpes grandes** (más adelante: el banco, la agencia de autos) disparan una alarma para todo el servidor.
4. **Botín:** va a la mochila, con capacidad limitada.
5. **Escapar:** llegar a una salida del barrio con el botín encima.
6. **Vender:** al **reducidor**, que está Afuera. El precio depende de la notoriedad (ver 6).

## 5. La captura

Máquina de estados en el servidor:

```
LIBRE ──(se rinde: tecla Q)──► RENDIDO ──(policía lo esposa: mantener E 2,5 s)──► ESPOSADO
  │                                                                                    │
  │ (muere)                                                    (lo llevan a la celda / pasan 90 s)
  ▼                                                                                    ▼
MUERTO: pierde todo                                       ARRESTADO: pierde el botín, conserva el equipo
```

| Opción del ladrón acorralado | Botín | Equipo |
| --- | --- | --- |
| Rendirse y ser arrestado | Lo confisca la policía | Lo conserva |
| Rendirse y ofrecer **coima** | Lo conserva si el policía acepta | Lo conserva |
| Seguir peleando y morir | Lo pierde | Lo pierde |

- **Rendido:** manos arriba, no puede moverse rápido ni disparar. Rendirse es la decisión inteligente si el botín es chico.
- **Esposado:** otro ladrón puede **liberarlo** (mantener E 5 s) mientras no llegue a la celda. Liberar a alguien suma notoriedad.
- **Coima:** el ladrón ofrece plata del **banco** (no de la mochila). El policía decide si acepta: es un dilema real entre jugadores, no un botón automático.
- **Celda:** el tiempo de condena depende del nivel de búsqueda (hoy: 60 s + 15 s por nivel).

## 6. Notoriedad y nivel de búsqueda

Son dos medidores distintos con propósitos opuestos:

| | Notoriedad | Nivel de búsqueda |
| --- | --- | --- |
| Qué mide | La racha de robos en una misma entrada al barrio | La violencia contra vecinos |
| Cómo sube | +1 por cada robo completado sin salir del barrio | +1 por cada vecino que mata; herir vecinos impide que baje |
| Cómo baja | Se pierde al salir del barrio, morir o ser arrestado | 1 nivel por minuto sin delitos violentos |
| Efecto | Cada robo vale +10 % por nivel (hasta +50 %): el valor queda en el botín y se cobra después en el reducidor | Nivel 3: **toda la ciudad ve tu ubicación** |
| Qué premia | El robo profesional | El robo sin víctimas |

**Ladrones solos o de a dos** arrancan con notoriedad más alta que los grupos, para que puedan competir.

**Cambio respecto del MVP 0:** hoy la alarma sube el nivel de búsqueda. Con estas reglas, lo que te vuelve arrestable es **ser ladrón** (el pasamontañas). La alarma solo marca dónde está pasando el robo, y el nivel de búsqueda queda para la violencia.

## 7. Recompensas de la policía

**Regla central: arrestar paga mucho más que matar.** La tabla de pagos define cómo se comporta un buen policía.

| Acción | Pago (valores iniciales propios, se ajustan en la alpha) |
| --- | --- |
| Arrestar a un ladrón | $1.500 + 10 % del botín confiscado |
| Abatir a un ladrón | $300 |
| Matar a un ladrón rendido o esposado | $0 y falta grave |
| Dañar a un vecino | No ocurre: el servidor lo bloquea |
| Ordenar rendición antes de disparar (tecla Q) | +20 % en el arresto siguiente, durante 20 s |
| Sirena del patrullero (cuando haya vehículos) | +20 % en las acciones de los siguientes 20 s y aviso a policías a 35 m |

- El salario se acumula durante el turno y **se cobra al terminarlo** en la comisaría. Hay un tope por turno.
- Si el policía se desconecta en pleno turno, cobra lo acumulado hasta ese momento.

## 8. Faltas e infracciones

- **Vecinos y policías** acumulan faltas: atropellar, dañar vecinos (policía), matar rendidos. Con 10 puntos van a la celda de la comisaría por un rato y no pueden cambiar de rol mientras están ahí. Baja 1 punto por minuto.
- Los **ladrones** no acumulan faltas: para ellos está el nivel de búsqueda.

## 9. Dinero y economía

| Dónde está el dinero | ¿Se puede perder? |
| --- | --- |
| **Banco** (cuenta del backend) | No |
| Botín y efectivo encima | Sí: al morir siendo ladrón, o confiscado en un arresto |

- El reducidor paga el botín, y la plata va al banco del personaje. Más adelante: el pago queda como efectivo en el mostrador y hay que agarrarlo, así que se puede asaltar a quien acaba de vender.
- Solo los vecinos usan el banco. La coima sale del banco.

## 10. Qué entra en cada etapa

| Mecánica | Etapa |
| --- | --- |
| Roles vecino, ladrón y policía, con pasamontañas y salidas del barrio | **MVP**, código escrito (etapa 6b) |
| La policía solo puede dañar ladrones; zonas seguras; protección al reaparecer | **MVP**, código escrito |
| Pérdida total al morir siendo ladrón; desconectarse siendo ladrón pierde el botín | **MVP**, código escrito |
| Reducidor Afuera, notoriedad | **MVP**, código escrito |
| Rendirse (Q), orden de rendición (Q policía), esposar (E 2,5 s), arresto | **MVP**, código escrito |
| Pago de la policía: arresto mucho mayor que abatir, salario al terminar el turno | **MVP**, código escrito |
| Nivel de búsqueda por violencia, con nivel 3 visible para todos | **MVP**, código escrito |
| Policías bot de relleno | **MVP completo** |
| Ganzúa vs. romper ventana | **MVP completo** |
| Liberar a un esposado; coima | Después del MVP |
| Faltas e infracciones (con vehículos) | Después del MVP |
| Cortar la luz de la cuadra, golpes grandes con alarma global | Después del MVP |
| Grupos, terrenos, lavado, negocios, ciclos de reinicio del servidor | A evaluar con jugadores reales |

## 11. Lo que Barrio no copia

- Nombres de personajes, lugares, objetos y marcas de otros juegos.
- Valores exactos de balance: los de este documento son propios y se ajustan en las pruebas.
- Escala de miles de jugadores: Barrio es de 16 por servidor.
- Estética: Caseros real y contemporáneo, con arte propio.
