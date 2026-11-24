# Changelog

## [Sin publicar] MVP 0: robo, alarma y policía

Código escrito, pendiente de primera compilación y de las pruebas del README.

### Agregado
- Módulo `BarrioCombat`: vida replicada y pistola hitscan con validación en el servidor (cadencia, munición, punto de vista y dirección). Disparo con clic izquierdo y recarga con R.
- `ABarrioPlayerState`: rol, nivel de buscado (0 a 5), dinero, botín encima, cárcel y progreso de robo.
- `ABarrioPlayerController`: avisos de alarma solo para policías y mensajes en pantalla.
- `UBarrioGameEvents`: canal de eventos del servidor (alarma, daño, muerte, arresto, cambio de rol).
- `ABarrioGameMode` con las reglas: cupo de policías, nivel de buscado y su descenso, arresto, cárcel, recompensas, reaparición por rol.
- `ALootPoint`: puerta robable con 3 niveles de botín, robo con duración, modo sigilo agachado, alarma con demora, reposición a los 5 minutos. El barrio gris crea una en cada casa.
- `AFenceStation` (reducidor), `APoliceStation` (comisaría) y `AJailCell` (celda).
- El personaje se puede arrestar: un policía que mira de cerca a un sospechoso buscado ve "Arrestar".
- Muerte con ragdoll y reaparición a los 5 segundos.
- HUD: panel de rol, buscado, botín, dinero, vida y balas; barra de robo; cuenta de la cárcel; marcas de POLICÍA y BUSCADO sobre otros jugadores; alarmas para la policía.
- Target `BarrioServer` para servidor dedicado, mapas por defecto, `MaxPlayers=16` y guía de despliegue en el VPS (`infra/vps`).

### Cambiado
- `IInteractable::GetInteractionText` recibe a quien mira, porque el texto depende de su rol.
- La detección de interacción busca por tipo de objeto para incluir a otros personajes.

### Diferido respecto del informe
- Gameplay Ability System: el MVP 0 usa el daño simple del motor. GAS entra con armaduras y más armas.
- Bots policía, inventario por ranuras, vehículos y backend quedan para el MVP completo.
- Compensación de latencia en los disparos.

## [Sin publicar] Fase 1: prototipo

Código escrito, pendiente de primera compilación y de las pruebas del README.

### Agregado
- Proyecto de Unreal `Barrio` con 5 módulos de C++: `Barrio`, `BarrioCore`, `BarrioCharacters`, `BarrioWorld`, `BarrioUI`.
- Personaje en tercera persona: caminar, correr, saltar, agacharse. Cámara con brazo.
- Sprint predicho en red dentro del movimiento del personaje, validado por el servidor.
- Controles por defecto creados desde código (Enhanced Input), reemplazables por assets.
- Interfaz `IInteractable` e interacción autoritativa: el cliente pide, el servidor valida distancia y frecuencia, y ejecuta.
- `InteractableTestActor`: interruptor de prueba con estado replicado.
- `GreyboxNeighborhood`: generador de barrio en gris configurable (por defecto, 4 manzanas de 100 m con casas, veredas y medianeras).
- HUD mínimo: mira, aviso de interacción y línea de estado (rol de red, velocidad, estado).
- Git LFS con bloqueo para assets de Unreal.

### Cambiado respecto del informe de la Fase 0
- El GameMode pasa del módulo base a un módulo principal (`Barrio`) para que el módulo base no dependa de ningún otro sistema.
- Los módulos de sistemas futuros se crean al iniciar su fase, no vacíos de antemano.
