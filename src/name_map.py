"""
Nepali <-> English vocabulary maps: commodity names and units.

COMMODITY_NAME_MAP (Nepali -> English):
AMPIS publishes commodity names in Nepali only. Kalimati's API
(https://kalimatimarket.gov.np/api/daily-prices/en) publishes English names
for the same commodities, in Kalimati's own naming convention
(e.g. "Tomato Big(Nepali)"). The two systems don't share a machine-readable
key, so this dict is a manually curated bridge: built once from AMPIS's
full commodity list, cross-checked against Kalimati's English names.

Keep this updated as you discover unmapped names (the scraper logs any
Nepali name it can't find here, so check ``data/unmapped_commodities.txt``
after each run and add entries).

Format: {nepali_name: english_name}

UNIT_NAME_MAP (English -> bilingual) is defined further down — see its
own docstring for details.
"""

COMMODITY_NAME_MAP: dict[str, str] = {
    # तरकारी / Vegetables
    "गोलभेंडा ठुलो (नेपाली)": "Tomato Big (Nepali)",
    "गोलभेंडा ठुलो (भारतीय)": "Tomato Big (Indian)",
    "गोलभेंडा सानो (लोकल)": "Tomato Small (Local)",
    "गोलभेंडा सानो (टनेल)": "Tomato Small (Tunnel)",
    "गोलभेंडा सानो (भारतीय)": "Tomato Small (Indian)",
    "गोलभेंडा सानो (तराई)": "Tomato Small (Terai)",
    "रातो आलु (लाम्चो)": "Potato Red (Long)",
    "रातो आलु (गोलो)": "Potato Red (Round)",
    "आलु रातो (मुढे)": "Potato Red (Mude)",
    "आलु रातो (भारतीय)": "Potato Red (Indian)",
    "आलु सेतो": "Potato White",
    "प्याज सुकेको (भारतीय)": "Onion Dry (Indian)",
    "प्याज सुकेको (चाईनिज)": "Onion Dry (Chinese)",
    "प्याज सुकेको (नेपाली)": "Onion Dry (Nepali)",
    "गाँजर (लोकल)": "Carrot (Local)",
    "गाँजर (तराई)": "Carrot (Terai)",
    "गाँजर (नेपाली)": "Carrot (Nepali)",
    "बन्दा (लोकल)": "Cabbage (Local)",
    "बन्दा (तराई)": "Cabbage (Terai)",
    "बन्दा (नरिवल)": "Cabbage (Coconut)",
    "काउली (स्थानीय)": "Cauliflower (Local)",
    "काउली स्थानीय (ज्यापू)": "Cauliflower Local (Jyapu)",
    "काउली (तराई)": "Cauliflower (Terai)",
    "मूला रातो": "Radish Red",
    "मूला सेतो (लोकल)": "Radish White (Local)",
    "मूला सेतो (हाइब्रिड)": "Radish White (Hybrid)",
    "भन्टा लाम्चो": "Brinjal Long",
    "भन्टा डल्लो": "Brinjal Round",
    "बोडी (तने)": "Cow Pea (Long)",
    "मकै बोडी": "Maize Cow Pea",
    "बोडी (रातो)": "Cow Pea (Red)",
    "मटरकोशा": "Green Peas",
    "घिउ सिमी (लोकल)": "French Bean (Local)",
    "घिउ सिमी (हाइब्रिड)": "French Bean (Hybrid)",
    "घिउ सिमी (राजमा)": "French Bean (Rajma)",
    "टाटे सिमी": "Sword Bean",
    "भटमास": "Soyabean Green",
    "तितो करेला": "Bitter Gourd",
    "लौका": "Bottle Gourd",
    "परवर (लोकल)": "Pointed Gourd (Local)",
    "परवर (तराई)": "Pointed Gourd (Terai)",
    "चिचिण्डो": "Snake Gourd",
    "घिरौंला": "Smooth Gourd",
    "झिगूनी": "Sponge Gourd",
    "फर्सी पाकेको": "Pumpkin",
    "फर्सी हरियो (लाम्चो)": "Squash (Long)",
    "फर्सी हरियो (डल्लो)": "Squash (Round)",
    "सलगम": "Turnip",
    "भिण्डी": "Okra",
    "सखरखण्ड": "Sweet Potato",
    "बरेला": "Okra (Barela)",
    "पिंडालु": "Arum",
    "स्कूस": "Christophine",
    "रायो साग": "Broad Leaf Mustard",
    "पालुंगो साग": "Spinach Leaf",
    "चम्सुरको साग": "Cress Leaf",
    "तोरीको साग": "Mustard Leaf",
    "मेथीको साग": "Fenugreek Leaf",
    "प्याज हरियो": "Onion Green",
    "बकुला": "Broad Bean",
    "तरुल": "Yam",
    "च्याउ (कन्ये)": "Mushroom (Kanya)",
    "च्याउ (डल्ले)": "Mushroom (Button)",
    "राजा च्याउ": "King Oyster Mushroom",
    "सिताके च्याउ": "Shiitake Mushroom",
    "कुरीलो": "Asparagus",
    "न्यूरो": "Neuro (Fiddlehead Fern)",
    "ब्रोकाउली": "Broccoli",
    "चुकन्दर": "Sugarbeet",
    "सजिवन": "Drumstick",
    "कोइरालो": "Koiralo Leaf",
    "बन्दा रातो": "Red Cabbage",
    "जिरीको साग": "Jiri Leaf",
    "ग्याठ कोबी": "Knol Khol",
    "सेलरी": "Celery",
    "पार्सले": "Parsley",
    "सौफको साग": "Fennel Leaf",
    "पुदिना": "Mint",
    "गान्टे मूला": "Turnip (Gante)",
    "हरियो मकै": "Green Maize",
    "इमली": "Tamarind",
    "तामा": "Bamboo Shoot",
    "तोफु": "Tofu",
    "गुन्द्रुक": "Gundruk",
    "रुख टमाटर": "Tree Tomato",
    # फलफूल / Fruits
    "स्याउ (झोले)": "Apple (Jhole)",
    "स्याउ (फूजी)": "Apple (Fuji)",
    "स्याउ (मुस्ताङ्ग)": "Apple (Mustang)",
    "स्याउ (जुम्ला)": "Apple (Jumla)",
    "स्याउ (चकलेटी)": "Apple (Chakleti)",
    "केरा (नेपाली)": "Banana (Nepali)",
    "केरा (मालभोग)": "Banana (Malbhog)",
    "केरा (हरियो)": "Banana (Green)",
    "केरा (भारतीय)": "Banana (Indian)",
    "कागती": "Lime",
    "अनार": "Pomegranate",
    "आँप (मालदह)": "Mango (Maldah)",
    "आँप (दसहरी)": "Mango (Dushari)",
    "आँप (चौसा)": "Mango (Chausa)",
    "आँप (कलकत्ते)": "Mango (Kalkatte)",
    "आँप (बम्बे)": "Mango (Bombay)",
    "अंगुर (हरियो)": "Grapes (Green)",
    "अंगुर (कालो)": "Grapes (Black)",
    "सुन्तला (नेपाली)": "Mandarin (Nepali)",
    "सुन्तला (भारतीय)": "Mandarin (Indian)",
    "तर्बुजा (हरियो)": "Water Melon (Green)",
    "तर्बुजा (पाटे)": "Water Melon (Pate)",
    "मौसम": "Sweet Orange (Mausam)",
    "जुनार": "Junar (Sweet Orange)",
    "भुँईकटहर": "Ground Jackfruit",
    "काँक्रो (लोकल)": "Cucumber (Local)",
    "काँक्रो (हाइब्रिड)": "Cucumber (Hybrid)",
    "काँक्रो (स्थानीय क्रस)": "Cucumber (Local Cross)",
    "रुख कटहर": "Jack Fruit",
    "निबुवा": "Citron",
    "चाक्सी": "Chaksi",
    "नास्पाती (लोकल)": "Pear (Local)",
    "नास्पाती (चाईनिज)": "Pear (Chinese)",
    "मेवा (नेपाली)": "Papaya (Nepali)",
    "मेवा (भारतीय)": "Papaya (Indian)",
    "अम्बा": "Amba",
    "लप्सी": "Nepali Hog Plum (Lapsi)",
    "लिच्ची (लोकल)": "Litchi (Local)",
    "लिच्ची (भारतीय)": "Litchi (Indian)",
    "खर्बुजा": "Musk Melon",
    "उखु": "Sugarcane",
    "किनु": "Kinnow",
    "स्ट्रबेरी": "Strawberry",
    "किवि": "Kiwi",
    "शरीफा": "Custard Apple",
    "आभोकाडो": "Avocado",
    "अमला": "Indian Gooseberry (Amla)",
    "नरिवल (काँचो)": "Coconut (Tender)",
    "नरिवल (हरियो)": "Coconut (Green)",
    "ड्रागन फ्रुट (नेपाली)": "Dragon Fruit (Nepali)",
    "ड्रागन फ्रुट (भारतीय)": "Dragon Fruit (Indian)",
    "बयर (नेपाली)": "Jujube (Nepali)",
    "बयर (भारतीय)": "Jujube (Indian)",
    # मसला बाली / Spices
    "अदुवा": "Ginger",
    "सुकेको खुर्सानी": "Chilli Dry",
    "खुर्सानी हरियो (लाम्चो)": "Chilli Green (Long)",
    "खुर्सानी हरियो (बुलेट)": "Chilli Green (Bullet)",
    "खुर्सानी हरियो (माछे)": "Chilli Green (Machhe)",
    "खुर्सानी हरियो (अकबरे)": "Chilli Green (Akbare)",
    "भेडे खुर्सानी": "Capsicum",
    "हरियो लसुन": "Garlic Green",
    "हरियो धनिया": "Coriander Green",
    "सुकेको चाईनिज लसुन": "Garlic Dry (Chinese)",
    "सुकेको नेपाली लसुन": "Garlic Dry (Nepali)",
    "सुकेको लसुन (भारतीय)": "Garlic Dry (Indian)",
    "सुकेको छ्यापी": "Chyapi Dry",
    "हरियो छ्यापी": "Chyapi Green",
    "मरिच": "Black Pepper",
    "सुकमेल": "Cinnamon",
    "अलैँची": "Cardamom",
    "जिरा": "Cumin",
    # माछा / Fish
    "सुकेको माछा": "Fish Dry",
    "ताजा माछा (रहु)": "Fish Fresh (Rahu)",
    "ताजा माछा (बचुवा)": "Fish Fresh (Bachuwa)",
    "ताजा माछा (छडी)": "Fish Fresh (Chhadi)",
    # मासु / Meat
    "कुखुराको मासु (बोईलर)": "Chicken Meat (Broiler)",
    "कुखुराको मासु (लोकल)": "Chicken Meat (Local)",
    "खसीको मासु": "Goat Meat",
    "बंगुरको मासु": "Pork",
    # दुग्धजन्य / Dairy
    "गाईको दुध": "Cow Milk",
    "भैसीको दुध": "Buffalo Milk",
    "घ्यु": "Ghee",
    "पनीर": "Paneer (Cheese)",
    "छुर्पी": "Churpi",
    "मखन": "Butter",
}


# Unit translation map: Kalimati's English unit (lowercased, whitespace-
# collapsed) -> {"en": canonical English form, "ne": Nepali form}.
#
# Kalimati's own API already gives bilingual COMMODITY names, but unit
# strings come back English-only ("KG", "Doz", "1 Pc", etc. — observed
# casing/spelling is inconsistent across rows). Unlike commodity names,
# the unit vocabulary here is small and closed (weight/count/volume
# units), so a hand-maintained lookup is the right tool — not another
# scrape just for units.
#
# Lookup keys are normalized (lowercased, extra whitespace collapsed) so
# "KG", "Kg", "kg" etc. all hit the same entry. If Kalimati uses a unit
# string not listed here, it's left as English-only with a console
# warning rather than guessed at — see _translate_unit() in
# kalimati_fetcher.py.
UNIT_NAME_MAP: dict[str, dict[str, str]] = {
    # Weight
    "kg": {"en": "Kg", "ne": "के.जी."},
    "gram": {"en": "Gram", "ne": "ग्राम"},
    "gm": {"en": "Gram", "ne": "ग्राम"},
    "g": {"en": "Gram", "ne": "ग्राम"},
    "quintal": {"en": "Quintal", "ne": "क्विन्टल"},
    "ton": {"en": "Ton", "ne": "टन"},
    "tonne": {"en": "Ton", "ne": "टन"},
    # Volume
    "litre": {"en": "Litre", "ne": "लिटर"},
    "liter": {"en": "Litre", "ne": "लिटर"},
    "ltr": {"en": "Litre", "ne": "लिटर"},
    "l": {"en": "Litre", "ne": "लिटर"},
    "ml": {"en": "Millilitre", "ne": "मिलिलिटर"},
    # Count-based — these are the ones that showed up distinct from
    # plain weight units (e.g. Banana sold by dozen/piece, not weight).
    "doz": {"en": "Dozen", "ne": "दर्जन"},
    "dozen": {"en": "Dozen", "ne": "दर्जन"},
    "per dozen": {"en": "Dozen", "ne": "दर्जन"},
    "pc": {"en": "Piece", "ne": "थान"},
    "pcs": {"en": "Piece", "ne": "थान"},
    "piece": {"en": "Piece", "ne": "थान"},
    "1 pc": {"en": "Piece", "ne": "थान"},
    "no": {"en": "Piece", "ne": "थान"},  # "No." / "Number" used as a count unit
    "bundle": {"en": "Bundle", "ne": "मुठा"},
    "mutha": {"en": "Bundle", "ne": "मुठा"},
}
