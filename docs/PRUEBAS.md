# Pruebas

Listas para verificar cada etapa. Qué cierra cada etapa: [PLAN.md](PLAN.md). Cómo compilar y armar el mapa: [GUIA_DESARROLLO.md](GUIA_DESARROLLO.md). Reglas que se prueban: [DISENO_JUEGO.md](DISENO_JUEGO.md).

Si algo falla, anotar el punto de la lista, qué se ve y el error del **Output Log** (en el editor: Window → Output Log).

Las pruebas automáticas del backend son aparte: `cd backend && npm test`.

## Fase 1: un jugador

Botón **Play**, modo *Selected Viewport*.

- [ ] W A S D mueven y el mouse gira la cámara.
- [ ] Shift corre (abajo a la izquierda dice *Corriendo*, unos 21 km/h; caminando, unos 12 km/h).
- [ ] Espacio salta y C agacha.
- [ ] El personaje choca con casas, medianeras y cordones.
- [ ] Mirando una puerta azul de cerca aparece `[E] Para robar, ponete el pasamontañas (G)`. Desde más de 2,5 m no aparece nada.

## Fase 2: multijugador en el editor

Junto al botón Play, en **⋮**: **Number of Players: 3** y **Net Mode: Play As Client**. Esto levanta un servidor dedicado oculto y tres clientes.

- [ ] Los tres se ven moviéndose, corriendo y agachándose sin tirones.
- [ ] Abajo a la izquierda cada ventana dice *Cliente*.
- [ ] Con latencia simulada se sigue pudiendo jugar: en la consola (`º` o `~`) escribir `NetEmulation.PktLag 150` en un cliente y repetir las pruebas.

## Loop completo (3 jugadores, Play As Client)

Jugador A = ladrón, Jugador B = policía, Jugador C = vecino.

**Roles**
- [ ] Los tres aparecen como **VECINO**. Un vecino no puede disparar (el clic no hace nada).
- [ ] Dentro de la zona segura, G muestra "Acá no te podés poner el pasamontañas".
- [ ] B va a la comisaría y con E entra de servicio: reaparece en el Player Start `Police` y su panel dice **POLICÍA (de servicio)**.
- [ ] Un cuarto jugador no puede entrar de servicio si el cupo está lleno ("Cupo de policía completo").
- [ ] A, fuera de la zona segura, aprieta G: barra de 2 s y pasa a **LADRÓN**. Los demás ven "LADRÓN" sobre su cabeza.
- [ ] Un ladrón no puede entrar de servicio en la comisaría.

**Robo y alarma**
- [ ] A roba una casa: barra "Robando...". Si se aleja antes de terminar, se cancela.
- [ ] Al terminar, el panel muestra el botín y la notoriedad sube 1. El segundo robo seguido rinde más (+10 % por nivel).
- [ ] Si suena la alarma: la puerta se pone roja, A ve "¡Sonó la alarma!", B ve "ALARMA xx m" y C no ve nada.

**Daño**
- [ ] B le dispara a C (vecino): no le hace daño. B le dispara a A (ladrón): sí.
- [ ] Nadie recibe daño dentro de una zona segura.
- [ ] A mata a C: el nivel de búsqueda de A sube 1. Con 3 muertes, B y C ven a A marcado como "MÁS BUSCADO" desde cualquier distancia.

**Captura**
- [ ] B aprieta Q cerca de A: A ve "¡POLICÍA! ¡Rendite! (Q)".
- [ ] A aprieta Q: queda **RENDIDO**, camina lento y no puede disparar.
- [ ] B mira a A y aprieta E: barra "Esposando..." de 2,5 s. A va a la celda con la cuenta regresiva y pierde el botín, y el panel de B suma la ganancia (+20 % si dio la orden de rendición antes).
- [ ] Si B se aleja durante el esposado, falla ("Se te escapó").
- [ ] Un ladrón con poca vida (25 % o menos) también se puede esposar sin rendirse.
- [ ] B abate a A sin que se rinda: +$300. Si A estaba rendido: "no se paga".
- [ ] Al terminar la condena, A reaparece como **vecino**.

**Escape y venta**
- [ ] A, con botín, cruza una salida (caja amarilla): "Saliste del barrio: ya no sos ladrón". Su panel dice VECINO, con "Botín para vender".
- [ ] Con el pasamontañas puesto, el reducidor no le compra. Ya como vecino, vende: el botín pasa a Banco.
- [ ] A muere siendo ladrón: pierde todo el botín y reaparece como vecino.

**Turno policial**
- [ ] B termina el turno en la comisaría: cobra las ganancias acumuladas y vuelve a ser vecino.
- [ ] B muere de servicio: reaparece como policía en la comisaría, con 10 s sin recibir daño.

## En el VPS

Con el servidor de juego en el VPS ([DESPLIEGUE_VPS.md](DESPLIEGUE_VPS.md)): repetir el loop completo con jugadores conectados desde casas distintas.

## Cuentas y dinero

Requiere el backend y el servidor de juego en el VPS. Usar un cliente empaquetado en Development que abre el juego sin argumentos.

- [ ] Aparece la pantalla de login. Con usuario o contraseña incorrectos muestra "Usuario o contraseña incorrectos".
- [ ] "Crear cuenta" con una contraseña corta muestra el motivo ("al menos 10 caracteres").
- [ ] Al crear la cuenta, entra solo a `caseros.facundofr.com` y el panel muestra Banco: $0.
- [ ] Robar, escapar y vender: el banco sube. Salir del juego y volver a entrar con la misma cuenta: el dinero sigue ahí.
- [ ] Abrir un segundo cliente con la misma cuenta: el segundo es expulsado con "Esa cuenta ya está conectada".
- [ ] Conectarse a mano sin login (`open caseros.facundofr.com:7777` desde la consola): el servidor lo rechaza.

Para ver la pantalla de login en el editor: **Project Settings → Game → Barrio Online → Show Login In Editor**, y Play en modo **Standalone Game**.
