(() => {
  const TEMPLATES = [
    {
      id: "blank_actor",
      label: "Ator base limpo",
      placements: []
    },
    {
      id: "clown_classic",
      label: "Palhaço clássico",
      palette: {
        skin: "#f3ead7",
        hair: "#e3e4e2",
        eye: "#2f2b29",
        nose: "#df3b36",
        mouth: "#a7373d",
        collar: "#f4f2e3",
        primary: "#d43b2f",
        secondary: "#2b71c9",
        shoes: "#26313a",
        gloves: "#f7f5e9"
      },
      placements: [
        {shape:"hair_puff", x:24, y:13, color:"hair", scale:1.00},
        {shape:"face_oval", x:24, y:17, color:"skin", scale:1.00},
        {shape:"eye_pair", x:24, y:16, color:"eye", scale:1.00},
        {shape:"round_nose", x:24, y:19, color:"nose", scale:1.00},
        {shape:"smile", x:24, y:20, color:"mouth", scale:1.00},
        {shape:"ruff", x:24, y:25, color:"collar", scale:1.00},
        {shape:"torso", x:24, y:32, color:"primary", scale:1.00},
        {shape:"sleeve", x:17, y:32, color:"secondary", scale:1.00},
        {shape:"sleeve", x:31, y:32, color:"primary", scale:1.00},
        {shape:"glove", x:16, y:38, color:"gloves", scale:.85},
        {shape:"glove", x:32, y:38, color:"gloves", scale:.85},
        {shape:"trouser_leg", x:21, y:46, color:"secondary", scale:1.00},
        {shape:"trouser_leg", x:27, y:46, color:"primary", scale:1.00},
        {shape:"shoe", x:21, y:56, color:"shoes", scale:.90},
        {shape:"shoe", x:27, y:56, color:"shoes", scale:.90}
      ]
    },
    {
      id: "visitor_classic",
      label: "Visitante tycoon",
      palette: {
        skin: "#f6c29e",
        hair: "#5a3825",
        primary: "#15803d",
        secondary: "#1d4ed8",
        shoes: "#1f2937"
      },
      placements: [
        {shape:"hair_cap", x:24, y:14, color:"hair", scale:.90},
        {shape:"face_oval", x:24, y:17, color:"skin", scale:.95},
        {shape:"eye_pair", x:24, y:16, color:"shoes", scale:.80},
        {shape:"torso", x:24, y:32, color:"primary", scale:.95},
        {shape:"sleeve", x:18, y:32, color:"primary", scale:.90},
        {shape:"sleeve", x:30, y:32, color:"primary", scale:.90},
        {shape:"trouser_leg", x:21, y:46, color:"secondary", scale:.95},
        {shape:"trouser_leg", x:27, y:46, color:"secondary", scale:.95},
        {shape:"shoe", x:21, y:56, color:"shoes", scale:.85},
        {shape:"shoe", x:27, y:56, color:"shoes", scale:.85}
      ]
    }
  ];

  window.CH_CHARACTER_TEMPLATES = Object.freeze(TEMPLATES);
})();
