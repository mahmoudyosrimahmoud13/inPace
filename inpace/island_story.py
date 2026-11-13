"""The story of Tempo's island: an adventure in ten chapters and three interludes.

Two worlds tell the same story:
- "universal": a made-up sea that works anywhere (the default for English).
- "arab": the same adventure on the Mediterranean, from Abu Qir Bay to the Library of Alexandria
  (the default for Arabic). Anyone can pick either world in either language.

Chapters are written once per language with {placeholders}; each world fills in its own names and
places, and can add a line or two of local colour. Your real pace moves the story: chapters open as
your island grows, the big fight needs a few days in a row, a new chapter can't open in thick fog,
and the interludes happen when you really come back, keep a week's goal, or meet other learners.
"""
from __future__ import annotations

WORLDS = {
    "universal": {
        "en": {"bay": "Starling Bay", "grandma": "Grandma Pearl", "sea": "the Sea of Things to Learn",
               "fog": "the Fog of Someday", "Fog": "The Fog", "fog_short": "the Fog", "whisper": "Someday.", "tomorrow": "someday",
               "lighthouse": "the Lighthouse of Real", "library": "the Great Library at the End of the Sea",
               "shore": "the Far Shore", "grey": "Lira"},
        "ar": {"bay": "خليج الزرازير", "grandma": "الجدة لؤلؤة", "sea": "بحر المعرفة",
               "fog": "ضباب يومٍ ما", "Fog": "الضباب", "fog_short": "الضباب", "whisper": "يومًا ما.", "tomorrow": "يومًا ما",
               "lighthouse": "منارة الحقيقة", "library": "المكتبة الكبرى عند آخر البحر",
               "shore": "الشاطئ البعيد", "grey": "ليرا"},
    },
    "arab": {
        "en": {"bay": "Abu Qir Bay", "grandma": "Teta Lulua", "sea": "the Great Green Sea",
               "fog": "the Fog of Bokra", "Fog": "The Fog", "fog_short": "the Fog", "whisper": "Bokra.", "tomorrow": "bokra",
               "lighthouse": "the Pharos of Alexandria", "library": "the Great Library of Alexandria",
               "shore": "the shore of Alexandria", "grey": "Salma"},
        "ar": {"bay": "خليج أبي قير", "grandma": "تيتا لؤلؤة", "sea": "البحر الأخضر العظيم",
               "fog": "ضباب بكرة", "Fog": "الضباب", "fog_short": "الضباب", "whisper": "بكرة.", "tomorrow": "بكرة",
               "lighthouse": "فنار الإسكندرية", "library": "مكتبة الإسكندرية الكبرى",
               "shore": "شاطئ الإسكندرية", "grey": "سلمى"},
    },
}

# A line or two of local colour for the Arab world, added after a chapter's first paragraph.
COLOUR = {
    "arab": {
        "en": {
            "c1": "Fishing feluccas were already out on the water, and far to the west the lights of Alexandria were going out one by one as the sun came up.",
            "c6": "It was the old wonder itself, the lighthouse that once guided every ship into Alexandria, rebuilt out of light.",
            "c9": "Where the old library had burned long ago, a new one had grown, and this time it was made of something fire can't touch.",
            "fair_winds": "Somewhere on the corniche, someone was playing the oud.",
        },
        "ar": {
            "c1": "كانت فلوكات الصيادين قد خرجت إلى الماء، وفي الغرب كانت أضواء الإسكندرية تنطفئ واحدًا بعد الآخر مع شروق الشمس.",
            "c6": "كانت هي الأعجوبة القديمة نفسها، الفنار الذي كان يهدي كل سفينة إلى الإسكندرية، وقد عاد مبنيًا من الضوء.",
            "c9": "حيث احترقت المكتبة القديمة منذ زمن بعيد، نبتت مكتبة جديدة، وهذه المرة صُنعت من شيء لا تلمسه النار.",
            "fair_winds": "وفي مكان ما على الكورنيش، كان أحدهم يعزف على العود.",
        },
    },
}

# key, title (en, ar), what opens it, text (en, ar)
CHAPTERS = [
    ("c1", ("The Slowest Turtle", "أبطأ سلحفاة"), {"plants": 0},
     ("In {bay}, everyone knew Tempo: the slowest turtle in the water, and the only one who never stopped. "
      "The morning after he beat the hare in the famous race, something ancient rose from the deep. It was {grandma}, older than the oldest map.\n"
      "She pressed a seed into the moss on his shell. \"Carry it to {shore},\" she said. \"And hurry slowly. {Fog} is spreading across {sea}, "
      "and it swallows islands that stop growing.\"\n"
      "Then she was gone, and Tempo swam out to sea with a seed, a scarf, and you.",
      "في {bay} كان الجميع يعرف تمبو: أبطأ سلحفاة في الماء، والوحيدة التي لا تتوقف أبدًا. "
      "وفي الصباح التالي لفوزه على الأرنب في السباق الشهير، صعد من الأعماق شيء قديم جدًا. كانت {grandma}، أقدم من أقدم خريطة.\n"
      "غرست بذرة في الطحلب الذي على صدفته وقالت: \"احملها إلى {shore}، وأسرع ببطء. {Fog} ينتشر فوق {sea}، "
      "ويبتلع الجزر التي تتوقف عن النمو.\"\n"
      "ثم اختفت، وسبح تمبو نحو البحر ومعه بذرة، ووشاح، وأنت.")),
    ("c2", ("First Light", "أول ضوء"), {"plants": 1},
     ("While you worked, Tempo swam. When he looked back, the seed had opened into a living plant, and it glowed. Not much. Just enough.\n"
      "A tired sparrow named Kiko dropped onto its branch. \"That light,\" she gasped. \"I followed it through the grey.\"\n"
      "Tempo turned. Far off on the horizon, a wall of fog stood perfectly still, as if it were waiting.",
      "بينما كنت تعمل، كان تمبو يسبح. وحين نظر خلفه، كانت البذرة قد تفتحت نباتًا حيًا، وكان يضيء. ليس كثيرًا. بالقدر الكافي فقط.\n"
      "هبطت على غصنه عصفورة متعبة اسمها كيكو، وقالت لاهثة: \"هذا الضوء... تبعته عبر الرمادي.\"\n"
      "التفت تمبو. وبعيدًا عند الأفق، كان جدار من الضباب واقفًا بلا حركة، كأنه ينتظر.")),
    ("c3", ("The Hare's Wager", "رهان الأرنب"), {"plants": 3},
     ("A spray of water, a flash of fur: Arnoob the hare, riding a raft piled with half-finished things. A half-built kite. Three first chapters. A guitar with one string.\n"
      "\"Still crawling, Tempo?\" he laughed. \"I'll be at {shore} before your weeds grow leaves.\" And he raced off, straight toward the fog.\n"
      "{grandma}'s words came back to Tempo: it swallows islands that stop growing. He swam a little faster. Not much. Just steady.",
      "رذاذ ماء، ولمحة فراء: إنه أرنوب الأرنب، يركب طوفًا مكدسًا بأشياء لم تكتمل. طائرة ورقية نصف مبنية. ثلاثة فصول أولى. جيتار بوتر واحد.\n"
      "ضحك وقال: \"ما زلت تزحف يا تمبو؟ سأصل إلى {shore} قبل أن تخرج أعشابك أوراقها.\" ثم انطلق مسرعًا، مباشرة نحو الضباب.\n"
      "عادت كلمات {grandma} إلى تمبو: يبتلع الجزر التي تتوقف عن النمو. فسبح أسرع قليلًا. ليس كثيرًا. بثبات فقط.")),
    ("c4", ("Into the Grey", "داخل الرمادي"), {"plants": 5},
     ("The fog came quietly. Colours drained from the water, sounds went soft, and a voice everywhere at once whispered: \"{whisper} Rest now. There's always {tomorrow}.\"\n"
      "Tempo's flippers grew heavy. Then you came back to work, and every plant on his shell lit up. The fog hissed and pulled away.\n"
      "Now he understood. {Fog} feeds on stopped minutes, and real minutes are light. And somewhere ahead, in the thickest grey, someone was calling for help.",
      "جاء الضباب بهدوء. انسحبت الألوان من الماء، وخفتت الأصوات، وهمس صوت من كل مكان في وقت واحد: \"{whisper} استرح الآن. هناك دائمًا {tomorrow}.\"\n"
      "ثقلت زعانف تمبو. ثم عدت أنت إلى العمل، فأضاء كل نبات على صدفته، وفحّ الضباب وتراجع.\n"
      "الآن فهم. {Fog} يتغذى على الدقائق المتوقفة، أما الدقائق الحقيقية فهي ضوء. وفي مكان ما أمامه، في أكثف الرمادي، كان أحدهم يستغيث.")),
    ("c5", ("The Grey Island", "الجزيرة الرمادية"), {"plants": 10},
     ("The cry came from an island grey as ash. Its turtle, {grey}, lay still. \"My learner stopped,\" she said. \"One day became a week. A week became a season. The fog took my colours.\"\n"
      "Tempo drifted close, and the light from your plants touched one of hers. A single grey leaf turned green. {grey} stared at it. \"It's not dead,\" she whispered. \"It's only waiting.\"\n"
      "Tempo promised to come back for her. That night, his shell grew its first ring.",
      "جاء النداء من جزيرة رمادية كالرماد. كانت سلحفاتها، {grey}، ممددة بلا حركة. قالت: \"صاحبي توقف عن التعلم. صار اليوم أسبوعًا، وصار الأسبوع فصلًا كاملًا. أخذ الضباب ألواني.\"\n"
      "اقترب تمبو، فلمس ضوء نباتاتك واحدة من نباتاتها. تحولت ورقة رمادية واحدة إلى الأخضر. حدقت فيها {grey} وهمست: \"لم تمت. إنها تنتظر فقط.\"\n"
      "وعدها تمبو أن يعود من أجلها. وفي تلك الليلة، نمت لصدفته أول حلقة.")),
    ("c6", ("The Lighthouse", "المنارة"), {"plants": 15},
     ("Out of the grey rose {lighthouse}. At the top, an owl in round glasses studied every island that passed.\n"
      "\"Halt,\" said Boomy. \"The fog is full of islands that only look alive: paint, not plants. Only real islands pass the Gate.\" "
      "She looked at your island for a long time, plant by plant, minute by minute. \"Real,\" she said at last, and the great beam swung toward {shore}.\n"
      "\"One piece of advice,\" she called after him. \"Find someone who checks your island too. Everyone needs a keeper.\"",
      "ومن قلب الرمادي ارتفع {lighthouse}. وفي قمته بومة بنظارة مستديرة تتفحص كل جزيرة تمر.\n"
      "قالت بومي: \"قف. الضباب مليء بجزر تبدو حية فقط: طلاء لا نبات. لا يعبر البوابة إلا الحقيقي.\" "
      "ونظرت إلى جزيرتك طويلًا، نبتة نبتة، ودقيقة دقيقة. ثم قالت أخيرًا: \"حقيقية.\" فاستدار الشعاع العظيم نحو {shore}.\n"
      "ونادت خلفه: \"نصيحة واحدة: ابحث عمن يتابع جزيرتك أيضًا. كل واحد يحتاج حارسًا.\"")),
    ("c7", ("The Raft of Halves", "طوف الأنصاف"), {"plants": 20},
     ("Past the Gate they found what was left of Arnoob's raft: sinking, every half-finished thing on it gone grey. The hare clung to the last plank.\n"
      "\"Nothing I carried was finished,\" he said, \"so nothing I carried could shine.\" Tempo didn't say I told you so. He just let Arnoob climb onto the shell.\n"
      "\"Slow island,\" Arnoob muttered, holding on tight. \"Steady island,\" said Tempo. Above them, the fog began to gather into a shape. The shape had a face.",
      "وبعد البوابة وجدوا ما تبقى من طوف أرنوب: يغرق، وكل شيء نصف مكتمل عليه صار رماديًا. كان الأرنب متشبثًا بآخر لوح.\n"
      "قال: \"لم يكتمل شيء مما حملته، فلم يستطع شيء منه أن يضيء.\" لم يقل له تمبو \"ألم أقل لك؟\". تركه فقط يصعد على صدفته.\n"
      "تمتم أرنوب وهو يتشبث جيدًا: \"جزيرة بطيئة.\" فقال تمبو: \"جزيرة ثابتة.\" وفوقهما، بدأ الضباب يتجمع في هيئة ما. وكان للهيئة وجه.")),
    ("c8", ("The Heart of the Fog", "قلب الضباب"), {"plants": 30, "streak": 3},
     ("At the centre of the sea, the fog stood up, tall as a storm. \"Why fight me?\" it said gently. \"I'm only {tomorrow}. Everyone loves {tomorrow}.\" It reached for the island's light.\n"
      "But you had shown up again and again, day after day, and every one of those days had taken root. The plants blazed. The fog screamed and tore apart, and through the hole poured sunlight, and the first sight of {shore}.\n"
      "\"It isn't gone,\" said Boomy, landing on a branch. \"It never is. It waits for the day you stop. So don't.\"",
      "وفي قلب البحر، نهض الضباب عاليًا كالعاصفة. قال بلطف: \"لماذا تقاتلني؟ أنا مجرد {tomorrow}. والجميع يحب {tomorrow}.\" ومدّ يده نحو ضوء الجزيرة.\n"
      "لكنك حضرت مرة بعد مرة، يومًا بعد يوم، وكل يوم من تلك الأيام كان قد ضرب جذوره. اشتعلت النباتات. صرخ الضباب وتمزق، ومن الفجوة تدفق ضوء الشمس، وأول نظرة إلى {shore}.\n"
      "قالت بومي وهي تهبط على غصن: \"لم ينته. لا ينتهي أبدًا. إنه ينتظر اليوم الذي تتوقف فيه. فلا تتوقف.\"")),
    ("c9", ("The Far Shore", "الشاطئ البعيد"), {"plants": 40},
     ("{shore} wasn't a beach. It was {library}: towers and bridges and gardens rising out of the water, and every tower was an island. "
      "Thousands of them, lit from inside, each one carried here by a turtle who kept going.\n"
      "Among them Tempo saw a grey island, glowing faintly green at its edges. {grey}. Her learner had come back.\n"
      "\"You came for me,\" she said. \"I promised,\" said Tempo.",
      "لم يكن {shore} رمالًا. كان {library}: أبراجًا وجسورًا وحدائق تنهض من الماء، وكل برج منها جزيرة. "
      "آلاف الجزر، مضاءة من داخلها، حملت كلًّا منها إلى هنا سلحفاةٌ لم تتوقف.\n"
      "وبينها رأى تمبو جزيرة رمادية، تتوهج حوافها بأخضر خافت. إنها {grey}. لقد عاد صاحبها.\n"
      "قالت: \"جئت من أجلي.\" فقال تمبو: \"وعدتك.\"")),
    ("c10", ("The Library of Islands", "مكتبة الجزر"), {"plants": 50},
     ("In the great hall waited {grandma}. Her shell was the floor of the whole library. \"Every learner who kept going added a room,\" she said. \"Now it's your turn.\"\n"
      "Tempo's island settled into place: a new room, full of everything you grew. Then she held out a second seed, different from the first.\n"
      "\"The fog is gathering again, far out where new learners are starting. They'll need someone to show them the way.\" "
      "Tempo looked at you. \"Slow and steady,\" he said. \"Again?\"",
      "في القاعة الكبرى كانت تنتظر {grandma}. كانت صدفتها أرضية المكتبة كلها. قالت: \"كل متعلم لم يتوقف أضاف غرفة. والآن دورك.\"\n"
      "استقرت جزيرة تمبو في مكانها: غرفة جديدة مليئة بكل ما زرعته. ثم مدّت بذرة ثانية، مختلفة عن الأولى.\n"
      "\"الضباب يتجمع من جديد، بعيدًا حيث يبدأ متعلمون جدد. سيحتاجون من يدلهم على الطريق.\" "
      "نظر تمبو إليك وقال: \"ببطء وثبات. مرة أخرى؟\"")),
]

# Moments that happen because of how you really study.
INTERLUDES = {
    "fog_lifts": (("The Fog Lifts", "الضباب ينقشع"),
                  ("For days Tempo drifted in the grey, holding your sprout under his scarf to keep it safe. The friends slept. The voice whispered: {tomorrow}, {tomorrow}.\n"
                   "Then, a light. You. The fog peeled back like a curtain, and Tempo smiled as if no time had passed at all. \"There you are,\" he said. \"Shall we?\"",
                   "لأيام ظل تمبو طافيًا في الرمادي، يخبئ نبتتك تحت وشاحه ليحميها. نام الأصدقاء. وظل الصوت يهمس: {tomorrow}، {tomorrow}.\n"
                   "ثم ضوء. أنت. انقشع الضباب كستارة تُزاح، وابتسم تمبو كأن وقتًا لم يمر. قال: \"ها أنت ذا. هيا بنا؟\"")),
    "fair_winds": (("Fair Winds", "رياح طيبة"),
                   ("You kept your promise for a whole week, and the sea noticed. A warm wind painted a rainbow across the sky, and the current turned to carry Tempo forward.\n"
                    "Even Arnoob, watching from his raft, raised an eyebrow. \"Huh,\" he said. \"Not bad. For a turtle.\"",
                    "وفيت بوعدك أسبوعًا كاملًا، ولاحظ البحر ذلك. رسمت ريح دافئة قوس قزح في السماء، واستدار التيار ليحمل تمبو إلى الأمام.\n"
                    "حتى أرنوب، وهو يراقب من طوفه، رفع حاجبه وقال: \"هممم. ليس سيئًا. بالنسبة لسلحفاة.\"")),
    "meeting": (("Other Lights", "أضواء أخرى"),
                ("One evening a lantern appeared on the water: another turtle, another island, another learner's light. Then another.\n"
                 "\"We're not alone out here,\" said Kiko. Everyone you learn with has a turtle of their own, sailing the same sea. Out here, a friend's light is the best map there is.",
                 "في إحدى الأمسيات ظهر فانوس على الماء: سلحفاة أخرى، وجزيرة أخرى، وضوء متعلم آخر. ثم ظهر غيره.\n"
                 "قالت كيكو: \"لسنا وحدنا هنا.\" كل من تتعلم معه لديه سلحفاته الخاصة، تبحر في البحر نفسه. وهنا، ضوء الصديق هو أفضل خريطة.")),
}


def world_for(setting: str, lang: str) -> str:
    """Which world to tell: the one you chose, or the one that fits your language."""
    if setting in WORLDS:
        return setting
    return "arab" if lang == "ar" else "universal"


def _fill(text: str, world: str, lang: str) -> str:
    names = WORLDS[world][lang]
    for k, v in names.items():
        text = text.replace("{" + k + "}", v)
    return text


def chapter(key: str, world: str, lang: str) -> dict:
    lang = lang if lang in ("en", "ar") else "en"
    i = 0 if lang == "en" else 1
    if key in INTERLUDES:
        titles, texts = INTERLUDES[key]
        title, text = titles[i], texts[i]
    else:
        _, titles, _, texts = next(c for c in CHAPTERS if c[0] == key)
        title, text = titles[i], texts[i]
    paras = _fill(text, world, lang).split("\n")
    extra = COLOUR.get(world, {}).get(lang, {}).get(key)
    if extra:
        paras.insert(1, extra)
    return {"key": key, "title": title, "paras": paras, "interlude": key in INTERLUDES}


def opens(key: str, st: dict) -> bool:
    need = next(c[2] for c in CHAPTERS if c[0] == key)
    return all(st.get(k, 0) >= n for k, n in need.items())
