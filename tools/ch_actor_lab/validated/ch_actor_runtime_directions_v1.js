(() => {
  'use strict';

  // Runtime direction profile validated against the CH Actor / Faxineiro map proof.
  // This intentionally does NOT change pose, animation phases, camera or anchor.
  // +Z projects to screen SW, +X to SE, -X to NW and -Z to NE.
  const DIRECTIONS = Object.freeze([
    Object.freeze({logical:'S', screen:'SW', row:0, angleRad:0}),
    Object.freeze({logical:'E', screen:'SE', row:1, angleRad:Math.PI/2}),
    Object.freeze({logical:'W', screen:'NW', row:2, angleRad:-Math.PI/2}),
    Object.freeze({logical:'N', screen:'NE', row:3, angleRad:Math.PI})
  ]);

  function direction(logical) {
    return DIRECTIONS.find(d => d.logical === logical);
  }

  function setDirection(actor, logical) {
    const d = direction(logical);
    if (!d) throw Error(`Unknown CH Actor runtime direction ${logical}`);
    actor.root.rotation.y = d.angleRad;
    return d;
  }

  window.CH_ACTOR_RUNTIME_DIRECTIONS_V1 = Object.freeze({
    version: 'CH_ACTOR_RUNTIME_DIRECTIONS_V1',
    reference: 'CH Actor Faxineiro map-validated direction profile',
    directions: DIRECTIONS,
    direction,
    setDirection
  });
})();
