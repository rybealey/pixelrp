"""English names for the furni import-zipto-shop.py brings in.

Zipto's own names are a mix: most are fine, but whole sets came across in
Portuguese (Christmas Charm, Blue Classic), French (the wired tiles, buttons and
levers), Dutch (the baby furni), or as the raw classname (the Origins pirate
lodge). `name_for` takes Zipto's name and returns the one the shop shows.

Three layers, first match wins:
  NAMES      written by hand - from the furni's own picture where the
             classname said nothing (contact sheets of their icons)
  RULES      colour and number series (Yvess5_DallePress_Rouge ->
             'Red Pressure Plate'), where a pattern names a whole family
  tidy()     everything else: Zipto's name with set prefixes dropped and
             placeholder text ('origins_c24_tv_blue', 'Shtrdl Xmasowl')
             turned into words
"""
import re

# French, Portuguese and Dutch colour words and the short forms the wired sets
# use. 'ro' is not here: it is pink on crates, ring plates and glowballs but
# red on the glass gates, so those families say which.
COLOURS = {
    'bleu': 'Blue', 'bleue': 'Blue', 'bleuu': 'Blue', 'bluee': 'Blue', 'ble': 'Blue', 'bl': 'Blue',
    'blue': 'Blue',
    'cyan': 'Cyan', 'cya': 'Cyan', 'cian': 'Cyan',
    'jaune': 'Yellow', 'jaun': 'Yellow', 'jau': 'Yellow', 'ja': 'Yellow', 'jone': 'Yellow',
    'yellow': 'Yellow',
    'orange': 'Orange', 'orang': 'Orange', 'oran': 'Orange', 'ora': 'Orange', 'or': 'Orange',
    'rose': 'Pink', 'rosee': 'Pink', 'ros': 'Pink', 'rs': 'Pink', 'pink': 'Pink',
    'rouge': 'Red', 'roug': 'Red', 'rou': 'Red', 'rg': 'Red', 'red': 'Red', 'rood': 'Red',
    'redisa': 'Red',
    'vert': 'Green', 'verte': 'Green', 'vertt': 'Green', 'ver': 'Green', 've': 'Green',
    'green': 'Green',
    'violet': 'Purple', 'violette': 'Purple', 'vi': 'Purple', 'purple': 'Purple',
    'noir': 'Black', 'no': 'Black', 'black': 'Black',
    'blanc': 'White', 'blanche': 'White', 'bla': 'White', 'bc': 'White', 'white': 'White',
    'marron': 'Brown', 'maron': 'Brown', 'mar': 'Brown', 'brun': 'Brown',
    'bleuciel': 'Sky Blue', 'bleuc': 'Light Blue', 'bleuf': 'Dark Blue',
    'bluecyan': 'Blue and Cyan', 'grey': 'Grey', 'glaciale': 'Ice Blue',
    'mcolor': 'Multicolour', 'allcolor': 'Multicolour', 'mult': 'Multicolour',
    'be': 'Beige', 'cr': 'Cream',
}


def colour(word):
    return COLOURS[word.lower()]


NAMES = {
    # 2026- Elven Easter: Habblet's marble Love Adventure set, filed there by Zipto
    'Habblet_loveadv_18': 'Pink Bench',
    'Habblet_loveadv_22': 'Pink Armchair',
    # Blue Classic (Portuguese)
    'chase_classic_banquetaclassica': 'Classic Stool',
    'chase_classic_blocoazuldepedra': 'Blue Stone Block',
    'chase_classic_blocodecorado1': 'Decorated Block 1',
    'chase_classic_blocodecorado2': 'Decorated Block 2',
    'chase_classic_bonecaerika': 'Erika Doll',
    'chase_classic_bordaazul': 'Blue Border 1',
    'chase_classic_bordaazul2': 'Blue Border 2',
    'chase_classic_bordaazul3': 'Blue Border 3',
    'chase_classic_brincoscharlotte': 'Charlotte Earrings',
    'chase_classic_cadeiraclassica': 'Classic Chair',
    'chase_classic_caixaclassica': 'Classic Box',
    'chase_classic_caixinhaclassica': 'Small Classic Box',
    'chase_classic_casadebonecas': 'Dollhouse',
    'chase_classic_casadepassaros': 'Birdhouse',
    'Chase_classic_chaleiraclassica': 'Classic Kettle',
    'chase_classic_detalheazul3': 'Blue Trim 1',
    'chase_classic_detalheazul4': 'Blue Trim 2',
    'chase_classic_detalheclassico': 'Classic Trim 1',
    'chase_classic_detalheclassico2': 'Classic Trim 2',
    'chase_classic_espelhoclassico': 'Classic Mirror',
    'chase_classic_lamparina': 'Oil Lamp',
    'chase_classic_mesaazulclassica': 'Blue Classic Table',
    'chase_classic_molduraclassica': 'Classic Frame',
    'chase_classic_pilarclassico': 'Classic Pillar 1',
    'chase_classic_pilarclassico2': 'Classic Pillar 2',
    'chase_classic_pilarclassico3': 'Classic Pillar 3',
    'chase_classic_sombrinha': 'Parasol',
    'chase_classic_vasoazul': 'Blue Vase',
    'chase_classic_vestidoclassico': 'Classic Dress',
    'chase_classic_xicaraclassica': 'Classic Teacup',
    # Christmas Charm (Portuguese)
    'Wniverso_Arvore_enfeitada': 'Decorated Tree',
    'Wniverso_Barreira_de_Neve': 'Snow Barrier',
    'Wniverso_Biscoitinho': 'Little Cookie',
    'Wniverso_Bloco_Cristal_G': 'Large Crystal Block',
    'Wniverso_Boneco_de_neve_Magico': 'Magic Snowman',
    'Wniverso_Cabra_Mistica': 'Mystic Goat',
    'Wniverso_Cervo_Real': 'Royal Deer',
    'Wniverso_Conifera_Natalina': 'Christmas Conifer',
    'Wniverso_Cristais_da_Fonte': 'Fountain Crystals',
    'Wniverso_Cristal_Verdadeiro': 'True Crystal',
    'Wniverso_Danca_Da_Neve': 'Snow Dance',
    'Wniverso_Duend_de_natal': 'Christmas Elf',
    'Wniverso_enfeites_de_Cristais': 'Crystal Ornaments',
    'Wniverso_Estrela_de_Cristal': 'Crystal Star',
    'Wniverso_Iceberg': 'Iceberg',
    'Wniverso_Janela_casa_natalina': 'Christmas House Window 1',
    'Wniverso_Janela_casa_natalina2': 'Christmas House Window 2',
    'Wniverso_Janela_de_Cristal': 'Crystal Window',
    'Wniverso_Janelinha_Cristal': 'Small Crystal Window',
    'Wniverso_Lua_de_Cristal': 'Crystal Moon',
    'Wniverso_Mamute_Congelado': 'Frozen Mammoth',
    'Wniverso_Muralha_Cristal': 'Crystal Rampart',
    'Wniverso_Musa_natalina': 'Christmas Muse',
    'Wniverso_Parede_Coniferas': 'Conifer Wall',
    'Wniverso_Parede_Cristal_P': 'Small Crystal Wall',
    'Wniverso_Parede_pinheiro': 'Pine Wall',
    'Wniverso_Parede_rocha_nevada': 'Snowy Rock Wall',
    'Wniverso_Pequeno_Gnomo': 'Little Gnome',
    'Wniverso_Pilar_Cristal_G': 'Large Crystal Pillar',
    'Wniverso_Pilar_Cristal_P': 'Small Crystal Pillar',
    'Wniverso_Pinguim_congelado': 'Frozen Penguin',
    'Wniverso_Pinguins_Tematicos': 'Festive Penguins',
    'Wniverso_Piso_Flocos': 'Snowflake Floor',
    'Wniverso_piso_Gelido': 'Icy Floor',
    'Wniverso_piso_Grama_alta': 'Tall Grass Floor',
    'Wniverso_Piso_grama_congelada': 'Frozen Grass Floor',
    'Wniverso_Piso_Gramado_Baixo': 'Short Grass Floor',
    'Wniverso_Piso_Madeira_Natalina': 'Christmas Wood Floor',
    'Wniverso_Piso_neve_da_floresta': 'Forest Snow Floor',
    'Wniverso_Piso_Neve_da_praia': 'Beach Snow Floor',
    'Wniverso_Piso_Neve_Enfeitada': 'Decorated Snow Floor',
    'Wniverso_Piso_pedrinhas': 'Pebble Floor',
    'Wniverso_Piso_tapete_de_Grama': 'Grass Rug',
    'Wniverso_Piso_Xadre_Elevado': 'Raised Chequered Floor',
    'Wniverso_piso_Xadrez_Nevado': 'Snowy Chequered Floor',
    'Wniverso_Porta_Casa_Natalina': 'Christmas House Door 1',
    'Wniverso_Porta_casa_natalina02': 'Christmas House Door 2',
    'Wniverso_Portao_de_cristal': 'Crystal Gate',
    'Wniverso_Presente_decorado': 'Decorated Present',
    'Wniverso_Presente_especial': 'Special Present',
    'Wniverso_Presente_grande': 'Large Present',
    'Wniverso_Rochas_decoradas': 'Decorated Rocks',
    'Wniverso_Saco_de_presentes': 'Sack of Presents',
    'Wniverso_Saco_Vazio': 'Empty Sack',
    'Wniverso_sofa_Ursinho_natalino': 'Christmas Teddy Sofa',
    'Wniverso_Telhado_Casa_Natalina': 'Christmas House Roof',
    'Wniverso_Teto_Casa_Natalina02': 'Christmas House Ceiling',
    'Wniverso_Teto_Cristal_G': 'Large Crystal Ceiling',
    'Wniverso_Teto_Cristal_M': 'Medium Crystal Ceiling',
    'Wniverso_Teto_Cristal_P': 'Small Crystal Ceiling',
    'Wniverso_torre_de_CristalG': 'Large Crystal Tower',
    'Wniverso_Torre_de_CristalM': 'Medium Crystal Tower',
    'Wniverso_Torre_de_CristalP': 'Small Crystal Tower',
    'Wniverso_Trenor_da_Realeza': 'Royal Sleigh',
    'Wniverso_Trenor_Encantado': 'Enchanted Sleigh',
    'Wniverso_Ursinho_de_presente': 'Gift Teddy',
    'Wniverso_Urso_Polar': 'Polar Bear',
    # Feerique, Hanami, Ice Age, Icy Blue
    'theire_feerique_Marion': 'Teapot',
    'setmagie_feerique_Marion': 'Magic Set',
    'Glycine_feerique_Marion': 'Wisteria',
    'Habblet_FL25_65': 'Pagoda Roof',
    'Lamp_Phy': 'Hanging Lantern',
    'eradogelo_habblet_26': 'Buck',
    'eradogelo_habblet_27': 'Scratte',
    'eradogelo_habblet_18': 'Ice Age Plants',
    'eradogelo_habblet_19': 'Ice Age Mini Tree',
    'eradogelo_habblet_20': 'Ice Age Tree',
    'eradogelo_habblet_23': 'Ice Hole',
    'eradogelo_habblet_24': 'Ice Block',
    'eradogelo_habblet_25': 'Ice Age Pterodactyl',
    'eradogelo_habblet_30': 'Ice Age Plant',
    'Habblet_mossblue': 'Blue Moss',
    'hlive_r24_shtrdl_xmascat': 'Blue Cat',
    'hlive_r24_shtrdl_xmasdeer': 'Blue Deer',
    'hlive_r24_shtrdl_xmasfox': 'Blue Fox',
    'hlive_r24_shtrdl_xmasowl': 'Blue Owl',
    'Habblet_bluefloor': 'Blue Floor',
    'habblet_bluerock': 'Big Blue Rock',
    'habblet_bluerock2': 'Small Blue Rock',
    'Habblet_bluevine': 'Blue Vine',
    'habblet_bluewaterfall': 'Blue Waterfall',
    'Habblet_icetree': 'Ice Tree',
    # Mini Items, Regazza
    'cain_minimotocycle': 'Mini Motorcycle',
    'cain_minibike': 'Mini Bike',
    'Regazza_chaves_ferramentas': 'Spanners',
    'Regazza_Ferramentas_de_oficina': 'Workshop Tools',
    'Regazza_Motor_de_carro': 'Car Engine',
    'Regazza_Pnel_de_luxo': 'Luxury Tyre',
    'Regazza_Prensa_industrial': 'Wine Press',
    'Regazza_Trono_Regazza': "Wine Baron's Throne",
    'Regazza_Alarme_Alerta': 'Alarm',
    # Cokemusic: typos and the 'Cc' left from the classname
    'cc_lighthouse_aquarium': 'Lighthouse Aquarium',
    'cc_refrigerator': 'Refrigerator',
    'CocaCola_Pinball': 'Coca-Cola Pinball Machine',
    'cc_decompression_chamber': 'Decompression Chamber',
    'cc_zebra_couch': 'Zebra Sofa',
    'cc_tv': 'TV',
    'cc_batman_begins_poster': 'Batman Begins Poster',
    'cc_acoustic_foam': 'Acoustic Foam',
    'cc_psychedelic_carpet': 'Psychedelic Carpet',
    'cc_leopard_couch': 'Leopard Couch',
    'cc_doc_chair': 'Doc Chair',
    'cc_submarine': 'Submarine',
    'cc_victorian_table': 'Victorian Table',
    'cc_fireplace': 'Fireplace',
    'cc_cow_pattern_bean_bag_chair': 'Cow Pattern Beanbag',
    # Music Shop, Recycler, Trophies, Windows, AD
    'youtube_jukebox': 'YouTube Jukebox',
    'habbox_recycler_bedblue': 'Recycler Blue Bed',
    'habbox_recycler_chairblue': 'Recycler Blue Chair',
    'habbox_recycler_chairpink': 'Recycler Pink Chair',
    'habbox_recycler_cratechairdark': 'Recycler Dark Crate Chair',
    'habbox_recycler_cratechairligh': 'Recycler Light Crate Chair',
    'habbox_recycler_kintsugia': 'Recycler Kintsugi Vase 1',
    'habbox_recycler_kintsugib': 'Recycler Kintsugi Vase 2',
    'habbox_recycler_mantelbooks': 'Recycler Mantel Books',
    'habbox_recycler_mantelclock': 'Recycler Mantel Clock',
    'habbox_recycler_patchsofaoran': 'Recycler Orange Patchwork Sofa',
    'habbox_recycler_patchsofapink': 'Recycler Pink Patchwork Sofa',
    'habbox_recycler_resintableblue': 'Recycler Blue Resin Table',
    'habbox_recycler_resintableoran': 'Recycler Orange Resin Table',
    'habbox_recycler_rosedresser': 'Recycler Rose Dresser',
    'habbox_recycler_rugblue': 'Recycler Blue Rug',
    'habbox_recycler_rugred': 'Recycler Red Rug',
    'habbox_recycler_scrapbooka': 'Recycler Scrapbook 1',
    'habbox_recycler_scrapbookb': 'Recycler Scrapbook 2',
    'habbox_recycler_tabledark': 'Recycler Dark Table',
    'habbox_recycler_tablelight': 'Recycler Light Table',
    'origins_c25_prizetrophy_anniv': 'Origins Anniversary Trophy',
    'origins_c25_prizetrophy_star': 'Origins Star Trophy',
    'habbox_finley_fenetre_tokyo2': 'Tokyo Window',
    'ads_blu_roses': 'Blue Roses',
    # Modern Furniture
    'livefurni19_husky': 'Husky',
    'Hare_Animal': 'Hare',
    'Tortoise_Tortue': 'Tortoise',
    'BurroAfron': 'Donkey',
    'rip_sheep': 'RIP Sheep',
    'xmas_c15_sheep': 'Christmas Sheep',
    'vinilo_gorillaz': 'Gorillaz Vinyl',
    'vinilo_kiss': 'KISS Vinyl',
    'vinilo_pinkfloyd': 'Pink Floyd Vinyl',
    'vinilo_queen': 'Queen Vinyl',
    'vinilo_rollingstones': 'Rolling Stones Vinyl',
    'vinilo_tameimpala': 'Tame Impala Vinyl',
    'vinilo_vaporwave': 'Vaporwave Vinyl',
    'cstm_tokyo_glass_door': 'Tokyo Glass Door',
    'oriental_vloer01': 'Oriental Floor',
    'orientl_poster': 'Oriental Poster',
    'orien_bijzetfl': 'Oriental Side Table',
    'orien_placem': 'Oriental Placemat',
    'orien_sausje': 'Oriental Sauce',
    'orien_stoel_klein': 'Small Oriental Chair',
    'orien_tafel_gr': 'Large Oriental Table',
    'DIY_a028_LuckyLantern': 'Lucky Lantern',
    'habbox_autumn_bucket_hay': 'Bucket of Hay',
    'habcrush_c25_greenpicnicblank': 'Green Picnic Blanket',
    'country_sack': 'Country Sack',
    'Yvess5_Garage_Amplif': 'Garage Amplifier 1',
    'Yvess5_Garage_Amplif2': 'Garage Amplifier 2',
    'Yvess5_Garage_Batterie': 'Car Battery',
    'Yvess5_Garage_BoiteCarton': 'Cardboard Box',
    'Yvess5_Garage_Bonbone': 'Gas Bottle',
    'Yvess5_Garage_Clou': 'Nails',
    'Yvess5_Garage_Door1': 'Garage Door 1',
    'Yvess5_Garage_Door2': 'Garage Door 2',
    'Yvess5_Garage_Drapeau': 'Garage Flag',
    'Yvess5_Garage_Etagere': 'Garage Shelf',
    'Yvess5_Garage_Exhaust': 'Exhaust Pipe',
    'Yvess5_Garage_GrosCoffre': 'Large Tool Chest',
    'Yvess5_Garage_Huile1': 'Oil Can 1',
    'Yvess5_Garage_Huile2': 'Oil Can 2',
    'Yvess5_Garage_Interupteur': 'Garage Light Switch',
    'Yvess5_Garage_Stereo': 'Garage Stereo',
    'Nawloh_Poubelle_City': 'City Bin',
    'miroir_hollywood4': 'Hollywood Mirror 1',
    'miroir_hollywood_2': 'Hollywood Mirror 2',
    'estanteria_medica': 'Medical Shelf',
    'livefurni20_hospitalpillar': 'Hospital Pillar',
    'livefurni20_hospitalplate': 'Hospital Floor Plate',
    'w19_cleanwash': 'Green Washing Machine',
    'wasmachine': 'White Washing Machine',
    'estatualibertad': 'Statue of Liberty',
    'one_way_marion': 'One Way Sign',
    'traficllight_marion': 'Traffic Light',
    'space_lift_off': 'Rocket Lift-Off',
    'bday10_duckballoon': 'Birthday Duck Balloon',
    'prideflagaromantic': 'Aromantic Pride Flag',
    'prideflagasexual': 'Asexual Pride Flag',
    'prideflagbisexual': 'Bisexual Pride Flag',
    'prideflaggay': 'Gay Pride Flag',
    'prideflaginclusive': 'Inclusive Pride Flag',
    'prideflaglesbian': 'Lesbian Pride Flag',
    'prideflagnonbinary': 'Non-Binary Pride Flag',
    'prideflagpansexual': 'Pansexual Pride Flag',
    'prideflagrainbow': 'Rainbow Pride Flag',
    'prideflagtrans': 'Trans Pride Flag',
    'habbox_shone_botte_beige': 'Beige Rain Boots',
    'habbox_shone_botte_jaune': 'Yellow Rain Boots',
    'habbox_shone_botte_rose': 'Pink Rain Boots',
    'habbox_shone_botte_rouge': 'Red Rain Boots',
    'tokyo_c18_fla1': 'Horse Head',
    'Birthday_duck': 'Birthday Duck',
    # Seasonal
    'xmas14_lights3': 'Christmas Lights',
    'mansion_hw23_dragon': 'Mansion Dragon',
    'mansion_hw23_egg': 'Mansion Egg',
    'mansion_hw23_pillow': 'Mansion Pillow',
    'mansion_hw23_displaystand': 'Mansion Display Stand',
    'habbox_egypte_01': 'Dark Stone Table',
    'habbox_egypte_02': 'Egyptian Cabinet',
    'habbox_egypte_03': 'Pharaoh Bust',
    'habbox_egypte_04': 'All-Seeing Pyramid',
    'habbox_egypte_05': 'Bastet Mask',
    'habbox_egypte_06': 'Egyptian Chest',
    'habbox_egypte_07': 'Reed Boat',
    'habbox_egypte_08': 'Clay Pot',
    'habbox_egypte_09': 'Anubis Statue',
    'habbox_egypte_10': 'Egyptian Rug',
    'habbox_egypte_11': 'Eye of Horus Panel',
    'habbox_egypte_12': 'Large Sand Tile',
    'habbox_egypte_13': 'Sandstone Tile',
    'habbox_egypte_14': 'Egyptian Column',
    'habbox_egypte_15': 'Sandstone Block',
    'habbox_egypte_16': 'Small Egyptian Column',
    'habbox_egypte_17': 'Skull',
    'habbox_egypte_18': 'Dark Sand Tile',
    'habbox_egypte_19': 'Sandstone Bench',
    'habbox_egypte_20': 'Spike Trap',
    'habbox_egypte_21': 'Sandstone Stairs',
    'habbox_egypte_aguas': 'Nile Water',
    'habbox_egypte_chs': 'Sand Floor',
    'habbox_egypte_coins': 'Gold Coins',
    'habbox_egypte_pedregulhos': 'Boulder',
    'habbox_egypte_pegadaar': 'Sand Pile',
    # Habbo Origins
    'origins_c25_telebox_orange': 'Origins Orange Teleporter',
    'origins_c25_poster_blackknots': 'Origins Black Knots Poster',
    'origns_bb7': 'Orange Battle Ball Statue',
    'origins_bb3': 'Turquoise Battle Ball Statue',
    'origins_c25_funky_bubblejuice': 'Origins Bubble Juice',
    'origins_stocking1': 'Origins Black Stocking',
    'origins_stocking2': 'Origins Blue Stocking',
    'origins_stocking3': 'Origins Festive Stocking',
    'origins_stocking4': 'Origins Pink Stocking',
    'origins_stocking5': 'Origins Yellow Stocking',
    'origins_c25_duckgift': 'Origins Gift Duck',
    'origins_c25_dpolyfon_stand_z': 'Dark Polyfon Z Stand',
    'origins_c24_hween_duck1': 'Origins Halloween Duck 1',
    'origins_c24_hween_duck2': 'Origins Halloween Duck 2',
    'Seawood_gianteye': 'Giant Eye',
    'origins_c24_pirate_bed_one': 'Pirate Single Bed',
    'origins_c24_pirate_bed_two': 'Pirate Double Bed',
    'origins_c24_pirate_div': 'Pirate Divider',
    'origins_c24_pirate_div_crn': 'Pirate Divider Corner',
    'origins_c24_pirate_shelve': 'Pirate Shelf',
    'origins_c24_pirate_table_small': 'Small Pirate Table',
    'origins_c24_pirate_treasuremap': 'Treasure Map',
    'origins_c24_pirate_bartable': 'Pirate Bar Table',
    'origins_c24_pirate_bear': 'Pirate Bear Poster',
    'origins_c24_pirate_croco': 'Pirate Croc Poster',
    'origins_doormat': 'Origins Doormat',
    'origins_c25_doormat_bobba': 'Bobba Doormat',
    'origins_c25_heartsofa_black': 'Origins Black Heart Sofa',
    # Public furniture
    'room_lobby_roommatic': 'Lobby Room-o-matic',
    'room_lobby_watermatic': 'Lobby Water-o-matic',
    'rare_eend': 'Rare Duck',
    'rooftop7_crn': 'Rooftop Corner',
    'room_roof15_sofa1': 'Rooftop Sofa',
    'rumble_bob': 'Round Pouf',
    'sun_chairsunny': 'Sunny Sun Chair',
    'tab_chair_bnjwt': 'Lido Stool',
    'habbox_public_c19_1x1red': 'Red Oriental Tile',
    'habbox_public_c19_1x1yellow': 'Yellow Oriental Tile',
    'habbox_public_c19_petalpatch': 'Petal Patch',
    'habbox_public_c19_petalpsml': 'Small Petal Patch',
    'orientala19r_rflower': 'Oriental Red Flower',
    'orientala19r_wlily': 'Oriental Water Lily',
    'orientala19r_yflower': 'Oriental Yellow Flower',
    'wgardn_bench': 'Garden Bench',
    'wgard_bench_plain': 'Plain Garden Bench',
    'wgard_div_2': 'Garden Divider',
    'wgard_div_3_crnr2': 'Garden Divider Corner',
    'room_hbct_barchair': 'Club Bar Chair',
    'room_hbct_barside': 'Club Bar Side',
    'room_hbct_div': 'Club Divider',
    'room_hbct_hanglight': 'Club Hanging Light',
    'room_hbct_stairside': 'Club Stair Side',
    'room_hbct_wallbl1': 'Club Wall Left 1',
    'room_hbct_wallbl2': 'Club Wall Left 2',
    'room_hbct_wallbl3': 'Club Wall Left 3',
    'room_hbct_wallcrnr': 'Club Wall Corner',
    'room_hbct_walltl': 'Club Wall Top Left',
    'room_hbct_walltr1': 'Club Wall Top Right 1',
    'room_hbct_walltr2': 'Club Wall Top Right 2',
    'habcrush_c23_boutiqueplant': 'Boutique Plant',
    'habcrush_c23_wallvine': 'Wall Vine',
    'risesnowball': 'Snowball',
    'snowballm': 'Snowball Machine',
    'snowstorm_snowblock01': 'Snow Block',
    # NFT, Zipto Club
    'hcrush_c23_netcafeplant': 'Net Cafe Plant 1',
    'hcrush_c23_netcafeplant2': 'Net Cafe Plant 2',
    'hcrush_c23_netcafetable': 'Net Cafe Table',
    'hc15_club_display': 'HC Club Display',
    'newdic2': 'Club Dice',
    'shadow_VIP23_dice': 'Shadow VIP Dice',
    'lipe_r22_goldenhand': 'Golden Hand',
    'shadow_VIP23_gatecrn': 'Shadow VIP Gate Corner',
    'shadow_VIP23_sofathrone': 'Shadow VIP Sofa Throne',
    # Wired accessories that follow no series
    'crew_dark_color_tile_1x2': '1x2 Colour Tile',
    'Yvess5_Astronomie_Cabletourne': 'Spiral Platform',
    'habboxfr_c19_rainpressuretile': 'Rain Pressure Tile',
    'near_tiles_memorygame': 'Memory Game Tiles',
    'rainbowtile': 'Rainbow Tile 1',
    'rainbowtile2': 'Rainbow Tile 2',
    'Yvess5_RectangleDalle_MArc': 'Rainbow Rectangle Tile',
    'case_colore': 'Purple Outline Tile',
    'bgry_marble': 'Grey Marble Tile',
    'gala_marble': 'Pink Marble Tile',
    'mybobba_crew_dark_color_tile': 'Dark Colour Tile',
    'dalle_2x2': '2x2 Tile',
    'dalle_3x3': '3x3 Tile',
    'dalle_3x3_bronze': '3x3 Bronze Tile',
    'dalle_4x4': '4x4 Tile',
    'dalle_4x4_bronze': '4x4 Bronze Tile',
    'dalle_bonze_pastel': 'Bronze Pastel Tile',
    'dalle_bronze_couleur_vive': 'Bronze Bright Tile',
    'dalle_couleur_vive': 'Bright Colour Tile',
    'dalle_noir_blanche': 'Black and White Tile',
    'dalle_numero': 'Number Tile',
    'dalle_numero_noir': 'Black Number Tile',
    'Dalle_pastel_clair': 'Light Pastel Tile',
    'dalle_pastel_sombre': 'Dark Pastel Tile',
    'Dalle_x_o': 'Noughts and Crosses Tile',
    'crystaltileachromatic': 'Clear Crystal Tile',
    'Yvess5_fleche_blanc': 'White Arrow',
    'Yvess5_fleche_noir': 'Black Arrow',
    'Yvess5_fleche_PanoBlanc': 'White Arrow Sign',
    'Yvess5_fleche_PanoNoir': 'Black Arrow Sign',
    'Yvess5_fleche_poteau1': 'Arrow Signpost 1',
    'Yvess5_fleche_poteau2': 'Arrow Signpost 2',
    'yv_flech_1': 'Arrow',
    'ipixxel_arrow_floor': 'Arrow Floor Tile',
    'box_bd': 'Dark Blue Crate',
    'box_gd': 'Khaki Crate',
    'lb_box': 'White Crate',
    'ro_box': 'Pink Crate',
    'lb_maze': 'Grey Maze Wall',
    'wf_acidever': 'Acid Trap 1',
    'wf_acidevrb': 'Acid Trap 2',
    'wf_firegteb': 'Fire Trap',
    'wf_jetseaub': 'Water Jet',
    'leuchtball1': 'Yellow Glowball',
    'leuchtball2': 'Orange Glowball',
    'leuchtball3': 'Red Glowball',
    'leuchtball4': 'Pink Glowball',
    'leuchtball5': 'Blue Glowball',
    'leuchtball6': 'Green Glowball',
    'leuchtball7': 'Beige Glowball',
    'leuchtball9': 'Black Glowball',
    'ro_balwired': 'Pink Glowball 2',
    'rg_balwired': 'Red Glowball 2',
    'ro_porteverr': 'Red Glass Gate',
    'rs_porteverr': 'Pink Glass Gate',
    'wf_glassdoor_black': 'Black Glass Door',
    'lb_floor_switch1': 'Floor Switch',
    'natur_schalter': 'Nature Switch',
    'halloween_schalter': 'Halloween Switch',
    'wf_floor_switchs': 'Grey Floor Lever',
    'wf_floor_switchw': 'White Floor Lever',
    'hb_invisbl': 'Invisible Block',
    'alien_pinkpyramid': 'Pink Alien Pyramid',
    'hbox_switch_2_1_1': 'Light Switch',
    'hbox_switch_2_2_1': 'Dial Switch',
    'hbox_switch_2_3_1': 'Small Wall Button',
    'hbox_switch_2_4_1': 'Grey Lever Switch',
    'hbox_switch_2_4_2': 'Black Lever Switch',
    'hbox_switch_2_4_3': 'Brown Lever Switch',
    'hbox_switch_2_5_1': 'White Toggle Switch',
    'hbox_switch_2_5_2': 'Black Toggle Switch',
    'hbox_switch_2_5_3': 'Brown Toggle Switch',
    'hbox_switch_2_6_1': 'Green Wall Lever',
    'hbox_switch_4_1_1': 'Four Button Panel',
    'hbox_switch_4_2_1': 'Triple Light Switch',
    'ro_dallering': 'Pink Ring Plate 1',
    'ro_dallerngb': 'Pink Ring Plate 2',
    'lb_ringplate': 'Ring Plate',
    'da_rondbleuu': 'Teal Round Tile',
    'lb_rondorang': 'Orange Round Tile 2',
    'wiredextras_pfeilplatte1': 'Arrow Plate',
    'lb_arrowplate': 'Arrow Plate 2',
    'button_1rood': 'Red Push Button',
    'Christmas_counter': 'Emerald Counter',
    'wf_hub_count2': 'Golden Countdown Timer 2',
    # Baby accessories (named from their pictures)
    'baby_kinderwagen': 'White Pram',
    'baby_stewie': 'Stewie Doll',
    'baby_strik': 'Ribbon Bow',
    'bday_c18_laurens_teddy': 'Orange Teddy Bear',
    'cuadrodeverano': 'Sandcastle',
    'eend_05': 'Explorer Duck',
    'events_prijs_aapje1': 'Monkey Plush',
    'events_prijs_hellokitty': 'Hello Kitty Plush',
    'events_prijs_panda': 'Panda Plush',
    'events_prijs_pikachu': 'Pikachu Plush',
    'events_prijs_poliwag': 'Poliwag Plush',
    'flwrpwr_01': 'Red Flower Power',
    'flwrpwr_02': 'Blue Flower Power',
    'flwrpwr_03': 'Yellow Flower Power',
    'hamtaru_1': 'Hamtaro',
    'HMleeuw1': 'Lion Plush',
    'patofuente': 'Duck Fountain',
    'pixar_alien': 'Toy Story Alien',
    'pixar_bal': 'Pixar Ball',
    'pixel_clock_baby': 'Baby Clock',
    'sick_teddy': 'Sick Teddy',
    'solarium_flpwr': 'Flower Power Solarium',
    'spongebobslak': 'Gary the Snail',
    'SS_train_5': 'Toy Train',
    'teddy_briaa': 'Brown Teddy Bear',
    'teddy_deat': 'Grey Teddy Bear',
    'vbunn': 'Pink Bunny Plush',
    'xm0611_firewood': 'Firewood',
    'xmas13_toyblock5': 'Green Toy Block',
    'xmas13_toyblock6': 'Yellow Toy Block',
    '01_caterbody': 'Pink Caterpillar Body',
    '02_caterbody': 'Blue Caterpillar Body',
    '02_caterhead': 'Arrow Box',
    '05_drawer': 'Toy Drawer',
    # Trax
    'galaxy_beark_trax': 'Galaxy Trax Machine',
    'sfx_furni_bongo': 'Bongo Sound Block',
    'sfx_furni_fire': 'Fire Sound Block',
    'sfx_furni_toilet': 'Toilet Sound Block',
}

SANRIO = {'hellokitty': 'Hello Kitty', 'badtz': 'Badtz-Maru', 'chococat': 'Chococat',
          'keroppi': 'Keroppi', 'mymelody': 'My Melody', 'twinstar': 'Little Twin Stars'}
SANRIO_THING = {'catrug': 'Cat Rug', 'plushy': 'Plushie', 'drawer': 'Drawers'}
ON = {'b': 'White', 'bl': 'White', 'bla': 'White', 'blanc': 'White',
      'm': 'Brown', 'ma': 'Brown', 'mar': 'Brown', 'maron': 'Brown', 'brun': 'Brown'}


def _rules(c):
    """Names for the colour and number series. None when no rule applies."""
    m = re.match(r'Yvess5_DallePress_(Maron|Blanc|Clean)?_?([A-Za-z]+)$', c)
    if m:
        base, col = m.group(1), colour(m.group(2))
        if base == 'Clean':
            return 'Plain %s Pressure Plate' % col
        if base:
            return '%s Pressure Plate on %s' % (col, ON[base.lower()])
        return '%s Pressure Plate' % col
    m = re.match(r'HboxDalDiag_(Blanc|Brun)_([A-Za-z]+)$', c)
    if m:
        return '%s Diagonal Arrow Tile on %s' % (colour(m.group(2)), ON[m.group(1).lower()])
    m = re.match(r'Yvess5_Dalle_Poite_([MB])_([A-Za-z]+)$', c)
    if m:
        return '%s Pointed Tile on %s' % (colour(m.group(2)), ON[m.group(1).lower()])
    m = re.match(r'Yvess5_Dal_Num_(Bla|Mar)_([A-Za-z]+)$', c)
    if m:
        return '%s Number Tile on %s' % (colour(m.group(2)), ON[m.group(1).lower()])
    m = re.match(r'Yvess_(Bl|Ma)_([A-Za-z]+)_Dal_Star$', c)
    if m:
        return '%s Star Tile on %s' % (colour(m.group(2)), ON[m.group(1).lower()])
    m = re.match(r'(Habbox|Yvess5)_Dalle_Rue_([a-z]+)1$', c)
    if m:
        return '%s Path Tile%s' % (colour(m.group(2)), ' 2' if m.group(1) == 'Yvess5' else '')
    m = re.match(r'Yv_Comp_(Neg|Pos)_([A-Za-z]+)_([A-Za-z]+?)(_test)?$', c)
    if m:
        a, b = colour(m.group(2)), colour(m.group(3))
        cols = a if a == b else '%s and %s' % (a, b)
        return '%s %s Block' % (cols, 'Minus' if m.group(1) == 'Neg' else 'Plus')
    m = re.match(r'TOOL_GlassFloor_([A-Za-z]+?)(_s)?$', c)
    if m:
        return '%s %sGlass Floor' % (colour(m.group(1)), 'Small ' if m.group(2) else '')
    m = re.match(r'DalleMinimaliste([A-Z][a-z]+)_Zhynk$', c)
    if m:
        return '%s Minimal Glass Tile' % colour(m.group(1))
    m = re.match(r'crystaltile([a-z]+)$', c)
    if m:
        return '%s Crystal Tile' % colour(m.group(1))
    m = re.match(r'tile_([a-z]+)$', c)
    if m and m.group(1).lower() in COLOURS:
        return '%s Tile' % colour(m.group(1))
    m = re.match(r'numeric_colour_tile_(\d+)$', c)
    if m:
        return 'Number Colour Tile %s' % m.group(1)
    m = re.match(r'(bl|ja|or|rg|ve)_box$', c)
    if m:
        return '%s Crate' % colour(m.group(1))
    m = re.match(r'mu_([a-z]+)$', c)
    if m:
        return '%s Wall' % colour(m.group(1))
    m = re.match(r'(bl|ja|or|ve)_balwired$', c)
    if m:
        return '%s Glowball 2' % colour(m.group(1))
    m = re.match(r'wf_dragbal(\d)$', c)
    if m:
        return 'Dragon Ball (%s Star%s)' % (m.group(1), '' if m.group(1) == '1' else 's')
    m = re.match(r'(bl|ja|or|ve)_porteverr$', c)
    if m:
        return '%s Glass Gate' % colour(m.group(1))
    m = re.match(r'wf_glas+doo(\d)$', c)
    if m:
        return 'Glass Door %s' % m.group(1)
    m = re.match(r'wf_firegate_([a-z]+)$', c)
    if m:
        return '%s Fire Gate' % colour(m.group(1))
    m = re.match(r'leviernothen_([a-z]+)$', c)
    if m:
        return '%s Lever' % colour(m.group(1))
    m = re.match(r'hc_([a-z]+)_levier1$', c)
    if m:
        col = {'bleuu': 'Blue', 'orang': 'Orange', 'rosee': 'Pink'}.get(m.group(1)) or colour(m.group(1))
        return '%s HC Lever' % col
    m = re.match(r'rav_holo_switch(\d)$', c)
    if m:
        return 'Holo Switch %s' % m.group(1)
    m = re.match(r'Yvess5_LevierOnOff_+(\d+)$', c)
    if m:
        return 'On/Off Lever %s' % m.group(1)
    m = re.match(r'Bouton_([A-Z]{2})(\d)$', c)
    if m:
        return '%s Button %s' % (colour(m.group(1)), m.group(2))
    m = re.match(r'wibbotybo_buzzer([a-z]+?)(\d)?$', c)
    if m:
        return '%s Buzzer%s' % (colour(m.group(1)), ' %s' % m.group(2) if m.group(2) else '')
    m = re.match(r'ipixxel_arrowdown_([a-z]+)$', c)
    if m:
        return '%s Down Arrow' % colour(m.group(1))
    m = re.match(r'(bl|ja|or|rg|ve)_dallering$', c)
    if m:
        return '%s Ring Plate 1' % colour(m.group(1))
    m = re.match(r'(bl|ja|or|rg|ve)_dallerngb$', c)
    if m:
        return '%s Ring Plate 2' % colour(m.group(1))
    m = re.match(r'da_rond(bleu|blue|jaun|oran|rose|roug|vert)([a-z])$', c)
    if m:
        col = colour({'blue': 'bleu'}.get(m.group(1), m.group(1)))
        return '%s Round Tile%s' % (col, ' on Brown' if m.group(2) == 'b' else '')
    m = re.match(r'(bl|ja|or|ro|rg|ve)_dalleflech$', c, re.I)
    if m:
        col = 'Pink' if m.group(1).lower() == 'ro' else colour(m.group(1))
        return '%s Arrow Tile 2' % col
    m = re.match(r'(bleu1|bleu|jone|orange|rose|rouge|vert)_dallefleche$', c)
    if m:
        return '%s Arrow Tile%s' % (colour(m.group(1).rstrip('1')), ' 3' if m.group(1) == 'bleu1' else '')
    m = re.match(r'wf_(arrowplate|ringplate|switch|pressureplate)_(black|white)$', c)
    if m:
        thing = {'arrowplate': 'Arrow Plate', 'ringplate': 'Ring Plate', 'switch': 'Switch',
                 'pressureplate': 'Pressure Plate'}[m.group(1)]
        return '%s %s' % (colour(m.group(2)), thing)
    m = re.match(r'wf_touw(\d)$', c)
    if m:
        return 'Rope %s' % m.group(1)
    m = re.match(r'(hcity|shone)_(com|coiv)([a-z]+)$', c)
    if m:
        col = colour({'jaun': 'jaune', 'roug': 'rouge', 'bleu': 'bleu', 'vert': 'vert', 'ble': 'bleu',
                      'rou': 'rouge', 'jau': 'jaune', 'ver': 'vert'}[m.group(3)])
        return '%s %sCountdown Timer' % (col, 'Outline ' if m.group(2) == 'coiv' else '')
    m = re.match(r'sanrio_c2[12]_([a-z]+)_([a-z]+)$', c)
    if m:
        return '%s %s' % (SANRIO[m.group(1)], SANRIO_THING.get(m.group(2), m.group(2).capitalize()))
    m = re.match(r'monsterseyes_(?:c17_)?([a-z]+?)(\d)?$', c)
    if m:
        thing = {'bedgirl': "Girl's Bed", 'sofagirl': "Girl's Sofa", 'creamrolls': 'Cream Rolls',
                 'smalltable': 'Small Table', 'teaplant': 'Tea Plant', 'teaset': 'Tea Set',
                 'walldecor': 'Wall Decoration', 'clowndoor': 'Clown Door'}.get(m.group(1), m.group(1).capitalize())
        return 'Spooky %s%s' % (thing, ' %s' % m.group(2) if m.group(2) else '')
    m = re.match(r'origins_c24_pirate_duck_([a-z]+)$', c)
    if m:
        return '%s Pirate Duck' % colour(m.group(1))
    m = re.match(r'origins_c24_pirate_([a-z]+)$', c)
    if m:
        return 'Pirate %s' % m.group(1).capitalize()
    m = re.match(r'origins_c24_hween_([a-z]+)$', c)
    if m:
        return 'Origins Halloween %s' % m.group(1).capitalize()
    m = re.match(r'origins_c24_tv_([a-z]+)$', c)
    if m:
        return 'Origins %s TV' % colour(m.group(1))
    m = re.match(r'origins_c25_dpolyfon_(.+)$', c)
    if m:
        thing = {'tabl_smth': 'Smooth Table', 'sofachair': 'Armchair', 'bed_one': 'Single Bed',
                 'table_s': 'Small Table', 'table_m': 'Medium Table', 'table': 'Large Table'}.get(
            m.group(1), m.group(1).replace('_', ' ').title())
        return 'Dark Polyfon %s' % thing
    m = re.match(r'room_hbct_([a-z]+?)(\d)?$', c)
    if m:
        return 'Club %s%s' % (m.group(1).capitalize(), ' %s' % m.group(2) if m.group(2) else '')
    m = re.match(r'orientala19r_([a-z]+)$', c)
    if m:
        return 'Oriental %s' % m.group(1).capitalize()
    m = re.match(r'room_lobby_([a-z]+)$', c)
    if m:
        return 'Lobby %s' % m.group(1).capitalize()
    m = re.match(r'rylai_japan_([a-z]+?)(\d)?$', c)
    if m:
        thing = {'halfboard': 'Half Board', 'hangingchair': 'Hanging Chair', 'shinto': 'Shinto Shrine',
                 'bento': 'Bento Box'}.get(m.group(1), m.group(1).capitalize())
        food = m.group(1) in ('bento', 'dango', 'onigiri', 'ramen', 'shinto')
        return '%s%s%s' % ('' if food else 'Japanese ', thing, ' %s' % m.group(2) if m.group(2) else '')
    m = re.match(r'(\w+)_figure_(blue|green|red|yellow|black)$', c)
    if m:
        who = m.group(1).replace('_', ' ').title()
        return who if m.group(2) == 'black' else '%s %s' % (colour(m.group(2)), who)
    m = re.match(r'origins_bb(\d)$', c)
    if m:
        return None   # the tidy pass splits 'Battleball'
    return None


PREFIXES = re.compile(r'^(Habblet|Habbox|Yvess|Hcrush|Livefurni|Cc)\s+', re.I)


def tidy(name, classname):
    """Zipto's name, made presentable: placeholder text becomes words."""
    if not name or name == classname or '_' in name:
        name = re.sub(r'_(desc|name)$', '', name or classname)
        name = re.sub(r'^(origins|habbox|habblet)_(c\d\d_)?', '', name)
        name = re.sub(r'(?<=[a-z])(?=\d)', ' ', name.replace('_', ' '))
    name = name.replace('Battleball', 'Battle Ball').replace('Shadow Vip', 'Shadow VIP')
    name = re.sub(r'\bCoca-cola\b', 'Coca-Cola', name)
    name = re.sub(r'\bXmas\b', 'Christmas', name)
    name = PREFIXES.sub('', re.sub(r'\s+', ' ', name).strip())
    return ' '.join(w if (w.isupper() and len(w) > 1) or any(ch.isdigit() for ch in w) or "'" in w
                    else w[:1].upper() + w[1:] for w in name.split(' '))


def name_for(classname, zipto_name):
    if classname in NAMES:
        return NAMES[classname]
    by_rule = _rules(classname)
    if by_rule:
        return by_rule
    return tidy(zipto_name, classname)
