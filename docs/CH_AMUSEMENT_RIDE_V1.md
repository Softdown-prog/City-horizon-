# CH_AMUSEMENT_RIDE_V1

`CH_AMUSEMENT_RIDE_V1` is the canonical City Horizon contract for amusement rides that use the City Park ticket booth, a visitor queue, finite seats, a synchronized ride cycle and visible CHActor passengers.

The goal is to make park growth data-driven. Adding the 2nd, 20th or 50th ride must not require adding `if (definition.id == "...")` branches to the visitor runtime. A new ride becomes discoverable and operable by authoring its building JSON correctly.

## Required building contract

A managed amusement ride must:

- use `category: "city_park"`;
- set `requiresTicketBooth: true`;
- expose a valid `accessPoints` entry for the attraction footprint;
- restore citizen fun through `needsEffect.fun > 0`;
- define an `amusementRide` object using `CH_AMUSEMENT_RIDE_V1`;
- keep the definition filename equal to the building id (`<id>.json`), because the ride runtime resolves the immutable authored definition by id and caches it for the game session.

Example:

```json
{
  "id": "example_ride_01",
  "category": "city_park",
  "requiresTicketBooth": true,
  "needsEffect": {
    "fun": 70
  },
  "amusementRide": {
    "contract": "CH_AMUSEMENT_RIDE_V1",
    "capacity": 20,
    "queue": {
      "contract": "CH_AMUSEMENT_RIDE_QUEUE_V1",
      "enabled": true,
      "boardingPolicy": "fifo",
      "dispatchPolicy": "full_or_timeout",
      "boardingTimeoutMs": 2500
    },
    "cycle": {
      "durationMs": 3000
    },
    "passengers": {
      "seatCount": 20,
      "overlayContract": "CH_RIDE_PASSENGER_OVERLAY_V1",
      "actorSource": "ch_actor_green_01",
      "paletteMode": "stable_per_visitor",
      "seatAssignment": "queue_order_next_free_slot"
    }
  }
}
```

## Runtime rules

The citizen decision system does not know concrete ride ids. A ticketed attraction is considered when its normal building definition satisfies the visitor need (currently amusement rides restore `fun`). The linked ticket booth remains the public entrance and transaction point.

The managed ride lifecycle is:

1. CHActor chooses a reachable ticketed attraction that satisfies its current need.
2. CHActor walks to the front service anchor of the linked ticket booth.
3. The ticket booth charges the attraction price.
4. The visitor enters the ride FIFO queue while remaining logically at the booth service position.
5. A batch dispatches when capacity is reached or `boardingTimeoutMs` expires.
6. Riders receive deterministic seat indexes from queue order.
7. World CHActors are hidden while riding; the passenger overlay represents only the riders that actually boarded.
8. The ride runs for `cycle.durationMs`.
9. The complete batch is released together, fun is restored, and the CHActors reappear at the ticket-booth service point before returning to normal autonomous decisions.

The queue and cycle are per attraction instance. Two copies of the same ride therefore keep independent queues and independent batches.

## Queue contract

`CH_AMUSEMENT_RIDE_QUEUE_V1` currently accepts only:

- `enabled: true`
- `boardingPolicy: "fifo"`
- `dispatchPolicy: "full_or_timeout"`
- `boardingTimeoutMs > 0`

Capacity must be greater than zero. The runtime currently caps authored capacity/seat counts at 512 as a defensive content-validation limit.

## Passenger contract

`CH_RIDE_PASSENGER_OVERLAY_V1` requires:

- `seatCount >= capacity`;
- a non-empty `actorSource`;
- `paletteMode: "stable_per_visitor"` so a citizen keeps the same clothing colors while walking, queueing and riding;
- `seatAssignment: "queue_order_next_free_slot"`.

The visual overlay must use the runtime seat index rather than filling seats decoratively. This prevents a half-full ride from rendering as full and prevents a full ride from appearing empty.

## Ticket booth ownership

A managed ride must never be entered directly from the public path. The ticket booth is the only public access point for the visit transaction and queue handoff. Existing one-to-one booth/attraction linking remains authoritative for pricing and routing.

The attraction access point is still retained for footprint/placement semantics and for legacy ticketed attractions, but a `CH_AMUSEMENT_RIDE_V1` visitor is transferred from the booth queue to a seat instead of walking visibly through the attraction footprint.

## Adding a new amusement ride

Before a new ride is considered runtime-ready, verify the following in its authored data and assets:

1. City Park building definition and directional sprites exist.
2. `requiresTicketBooth` is enabled and booth linking works at the intended placement distance.
3. `needsEffect.fun` is authored so visitors can discover the ride without id-specific code.
4. `amusementRide.capacity` matches the intended gameplay capacity.
5. Queue timeout and cycle duration are authored in the JSON.
6. Passenger `seatCount` is at least the ride capacity.
7. CHActor passenger overlay positions exist for every usable seat and every supported ride direction/frame.
8. Passenger colors come from the actual visitor instance and remain stable during the cycle.
9. Runtime animation uses activity state so an empty/idle ride does not pretend to carry passengers.
10. Ticket purchase, queue order, batch dispatch, exit and need restoration are verified in-game.

## Legacy ticketed attractions

A ticketed attraction without `amusementRide.contract = "CH_AMUSEMENT_RIDE_V1"` keeps the legacy visit path. It is not silently assigned an invented capacity. Existing rides should be migrated deliberately once their real capacity, passenger layout and cycle timing are known.

## Architectural rule

Do not add concrete amusement-ride ids to `building_visit_runtime.h` or other visitor decision code. Differences between rides belong in authored data (capacity, timing, need effects, passenger layout/overlay and animation assets), not in ride-name conditionals.
