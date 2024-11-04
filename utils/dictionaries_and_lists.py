# All the variable in this module are to be used and imported by the scrapping scripts.


# Below list contains the column names for the dataframes.
columns_list = [
    'Country_Name',
    'Company_Name',
    'Product_Name',
    'Product_URL',
    'Image_URL',
    'Category',
    'Currency',
    'Price',
    'Description',
    'Product_Weight',
    'Metal_Type',
    'Metal_Colour',
    'Metal_Purity',
    'Metal_Weight',
    'Diamond_Colour',
    'Diamond_Clarity',
    'Diamond_Pieces',
    'Diamond_Weight',
    'Flag'
]


# Below dictionary contains the list of keywords and their corresponding categories.
jewelry_types = {
    "Watch Accessories": ["watch accessory", "watch-accessory", "watch accessories", "watch-accessories", "watch charm",
                          "watch-charm", "watchcharm", "watchband", "watch-band", "watch band", "watch pin", "watchpin",
                          "watch-pin"],
    "Tanmaniya": ['tanmaniya'],
    "Earring": ["earring", "hoop", "dangle", "climber", "stud", "huggie", "ear cuff", "ear-cuff", "earcuff", "ear clip",
                "earclip", "ear-clip"],
    "Necklace": ["necklace", "collier", "haram", "choker"],
    "Pendant": ["pendant", "charm", "cross", "letter", "medallion", "locket", "pendent"],
    "Nose Pin": ['nose pin', 'nosepin', "nose-pin", 'nose ring', 'nosering', "nose-ring", 'nose screw', 'nosescrew',
                 'nose-screw'],
    "Ring": ["ring", "band", "finger ring", "fingerring", 'finger-ring'],
    "Cufflink": ["cufflink"],
    "Bracelet": ["bracelet", "hand chain", "handchain", "hand-chain", "hand piece", "handpiece", "hand-piece", "kada",
                 "cuff"],
    "Watch": ['watch'],
    "Anklet": ['ankle bracelet', 'anklet', "ankle", "ankle-bracelet"],
    "Hair Pin": ["hair pin", "hair-pin", "hairpin", "tiara", "crown"],
    "Mang Tikka": ['mang tikka', 'mang-tikka', 'mangtikka', 'mang tika', 'mangtika', 'mang-tika'],
    "Mangalsutra": ['mangalsutra', 'mangal sutra', 'mangal-sutra'],
    "Bangle": ["bangle", "kada"],
    "Brooches & Pins": ['brooch', 'pin', 'collar pin', 'collar-pin'],
    "Chain": ['chain'],
}


# Below dictionary contains the list of keywords and their corresponding metal colour.
metal_colour = {
    "Three Tone": ["whiteroseyellow", "roseyellowwhite", "whiteyellowrose", "rosewhiteyellow",
                   "yellowrosewhite", "yellowwhiterose", "threetone", "three-tone", "3"],
    "Two Tone": ["whiterose", "whiteyellow", "rosewhite", "roseyellow", "yellowwhite", "yellowrose", "twotone", "two-tone", "2"],
    "Yellow": ["yellow", "chocolate", "beige"],
    "White": ["white"],
    "Rose": ["rose", "pink"],
    "Black": ["black", "burnished"]
}


# Below list contains the list of network errors to be checked while runtime.
network_errors = [
    'NS_ERROR_UNKNOWN_HOST',
    'NS_ERROR_ABORT',
    'NS_ERROR_CONNECTION_REFUSED',
    'ERR_INTERNET_DISCONNECTED',
    'NS_ERROR_CONNECTION_TIMEOUT',
    'ERR_NETWORK_CHANGED',
    'NS_ERROR_NET_TIMEOUT'
]


gold_purity = {
    22: ['917', '916', '22'],
    18: ['750', '18'],
    14: ['585', '583', '14'],
    12: ['500', '12'],
    10: ['417', '416'],
    9: ['375', '9'],
    8:['333', '8']
}