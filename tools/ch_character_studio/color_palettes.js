(() => {
  const families = {
    skin:[['skin_porcelain','#F6D7C3'],['skin_fair','#F4C7A8'],['skin_peach','#EFB58F'],['skin_warm','#D99A72'],['skin_tan','#C8875F'],['skin_olive','#B97855'],['skin_brown','#925F42'],['skin_deep','#704631'],['skin_dark','#503226'],['skin_umber','#38231C']],
    hair:[['hair_black','#201B1A'],['hair_soft_black','#342A27'],['hair_dark_brown','#4A3025'],['hair_brown','#6B4630'],['hair_chestnut','#824A32'],['hair_auburn','#9A4D32'],['hair_copper','#B9673F'],['hair_golden','#C99442'],['hair_blonde','#DDBD69'],['hair_light_blonde','#EAD89A'],['hair_gray','#8D8D8A'],['hair_silver','#C7C9C8'],['hair_white','#EAECEA']],
    neutral:[['ink','#202629'],['charcoal','#343B3E'],['slate','#526069'],['steel','#73828A'],['silver','#A9B1B4'],['mist','#D4D8D7'],['ivory','#F0ECE0'],['paper','#F7F5EC'],['warm_gray','#8D847B'],['taupe','#6E6258']],
    vivid:[['red','#D83A36'],['scarlet','#E6523F'],['orange','#E67E32'],['amber','#E4A62F'],['yellow','#E7C93E'],['lime','#86B83E'],['green','#3D9B55'],['emerald','#218B68'],['teal','#258A8B'],['cyan','#3A9DB7'],['sky','#4E9BD8'],['blue','#3E70C9'],['indigo','#4F56B7'],['violet','#7D52B8'],['purple','#944AA1'],['magenta','#C2478D'],['pink','#DE6792']],
    pastel:[['pastel_red','#E7A09B'],['pastel_orange','#EAB68F'],['pastel_yellow','#E9D995'],['pastel_green','#A9C99B'],['pastel_mint','#9FCFC0'],['pastel_cyan','#A5CED8'],['pastel_blue','#A8BFE0'],['pastel_lilac','#C1ADD8'],['pastel_pink','#DDB0C4']],
    earth:[['sand','#CDB58B'],['ochre','#B88A45'],['clay','#AA674A'],['brick','#964D3E'],['rust','#8B4935'],['leather','#704A32'],['bark','#55402F'],['moss','#66724A'],['olive','#777A43'],['forest','#36553E']],
    deep:[['burgundy','#672F3B'],['wine','#7A3447'],['deep_orange','#88472D'],['deep_green','#28513B'],['petrol','#214D55'],['navy','#273E62'],['deep_blue','#2F416E'],['deep_violet','#4B3868'],['deep_purple','#56355D']],
    metal:[['iron','#4B5356'],['gunmetal','#384246'],['steel_light','#8E9A9E'],['aluminum','#B9C0BF'],['gold','#C79B3E'],['brass','#A77B32'],['copper','#A96545'],['bronze','#7A5839']],
    fantasy:[['neon_green','#65D94D'],['neon_cyan','#46D4D7'],['electric_blue','#4A7BFF'],['hot_pink','#F05AA6'],['bright_purple','#A85CE3'],['festival_yellow','#F4D94E'],['clown_red','#E3473D'],['clown_blue','#3F80D2']]
  };
  window.CH_CHARACTER_PALETTES = {
    contract:'CH_CHARACTER_PALETTE_V1',
    families:Object.fromEntries(Object.entries(families).map(([family,values]) => [family, values.map(([id,hex]) => ({id,hex}))])),
    all(){ return Object.values(this.families).flat(); }
  };
})();
