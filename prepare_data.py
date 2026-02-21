import pandas as pd
import re
import json
import os
from sklearn.model_selection import train_test_split

# Column Names
COL_H1 = 'الشطر الايمن' 
COL_H2 = 'الشطر الايسر'
COL_METER = 'البحر'
COL_RHYME  = 'القافية'
COL_DIWAN  = 'الديوان'
COL_POET   = 'الشاعر'
COL_ERA = 'العصر'


VALID_METERS = {
    'الطويل', 'الكامل', 'البسيط', 'الخفيف',
    'الوافر', 'الرجز', 'الرمل', 'المتقارب',
    'السريع', 'المنسرح', 'المجتث', 'المديد',
    'الهزج', 'المتدارك', 'المقتضب', 'المضارع',
}

def clean_arabic(text: str) -> str:
    """
    Normalize an Arabic text string for model training.

    Performs the following cleaning steps in order:
    1. Returns empty string for NaN/None values
    2. Removes diacritics (tashkeel/harakat): Unicode range U+0610-U+061A
       and U+064B-U+065F, including fatha, kasra, damma, sukun, shadda, etc.
    3. Removes tatweel: decorative horizontal stretch character that carries no 
       linguistic meaning
    4. Removes any non-Arabic characters: keeps only Arabic Unicode block
       (U+0600-U+06FF) and whitespace
    5. Collapses multiple consecutive whitespace characters into a single space
       and strips leading/trailing whitespace

    Args:
        text (str): Raw Arabic text, potentially containing diacritics,
                    tatweel, punctuation, or mixed-language characters.

    Returns:
        str: Cleaned Arabic text with diacritics, tatweel, and non-Arabic
             characters removed. Returns empty string if input is NaN/None.

    Example:
        clean_arabic("خَليلَيَّ لا تَستَعجِلا") = 'خليلي لا تستعجلا'
        clean_arabic("جميـــل") = 'جميل'
    """
    if pd.isna(text):
        return ""
    
    # Remove diacritics (tashkeel/harakat)
    text = re.sub(r'[\u0610-\u061A\u064B-\u065F\u0670]', '', text)

    # Remove tatweel (kashida)
    text = re.sub(r'\u0640', '', text)

    # Remove non-Arabic characters (keep only Arabic block and whitespace)
    text = re.sub(r'[^\u0600-\u06FF\s]', '', text)

    # Collapse multiple whitespace into single space and trim
    text = re.sub(r'\s+', ' ', text).strip()
    
    return text

def format_poem(poem_verses: pd.DataFrame) -> str:
    """
    Format a group of verses into a single training example string,
    following the special token scheme from Abboushi & Azzeh (2023).

    Each verse is formatted in RTL logical order as:
        [rhyme] H2 [meter] H1
    where H1 is the right hemistich and H2 is the left hemistich. Verses are 
    joined by newlines to form one complete poem training example.

    The meter and rhyme are read directly from each row's COL_METER and 
    COL_RHYME columns respectively.

    Args:
        poem_verses (pd.DataFrame): A DataFrame subset containing all verses
                                    belonging to a single poem, sharing the
                                    same poet, diwan, meter, and rhyme.
                                    Expected columns are COL_H1, COL_H2,
                                    COL_METER, and COL_RHYME. Rows should be
                                    pre-sorted by index to preserve original
                                    verse order.

    Returns:
        str: A newline-separated string of formatted verses representing
             one complete poem. 

    Example:
        format_poem(poem_verses) = 
        '[د] خليلي لا تستعجلا ان تزودا [الطويل] وان تجمعا شملي وتنتظرا غدا
         [د] فما لبث يوما بسابق مغنم [الطويل] ولا سرعتي يوما بسابقة الردى
         [د] وان تنظراني اليوم اقض لبانة [الطويل] وتستوجبا منا علي وتحمدا'

    """
    lines = []

    # Iterate through each verse in the poem group
    for _, row in poem_verses.iterrows():
        # Clean hemistichs and read meter/rhyme
        h1 = clean_arabic(row[COL_H1])
        h2 = clean_arabic(row[COL_H2])
        meter = str(row[COL_METER]).strip()
        rhyme = str(row[COL_RHYME]).strip()

        # RTL order: H1 [meter] H2 [rhyme]
        lines.append(f"[{rhyme}] {h1} [{meter}] {h2}")

    # Join all formatted verses with newlines to create the final poem string
    return "\n".join(lines)


if __name__ == "__main__":
    # 1. Load dataset
    DATA_PATH = "data/raw/APCD.csv"
    print("Loading dataset...")
    df = pd.read_csv(DATA_PATH, encoding="utf-8")
    print(f"Loaded : {len(df):,} verses, {df.shape[1]} columns")

    # 2. Filter out verses with invalid meter, missing values, or empty hemistichs
    df = df[df[COL_METER].isin(VALID_METERS)]
    df = df.dropna(subset=[COL_H1, COL_H2, COL_METER, COL_RHYME])
    df = df[(df[COL_H1].str.strip() != '') & (df[COL_H2].str.strip() != '')]
    print(f"After filter : {len(df):,} verses across {df[COL_METER].nunique()} meters")

    # 3. Group verses into poems based on shared poet, diwan, meter, rhyme, and era.
    print("Grouping verses into poems...")
    poems = []
    grouped = df.groupby([COL_POET, COL_DIWAN, COL_METER, COL_RHYME, COL_ERA], sort=False)

    for (poet, diwan, meter, rhyme, era), poem_verses in grouped:
        poem_verses = poem_verses.sort_index()   # preserve original verse order
        text = format_poem(poem_verses)
        if text.strip():
            poems.append({
                "poem":  text,
                "meter": meter,
                "rhyme": rhyme,
                "diwan": diwan,
                "poet":  poet,
                "era": era
            })

    print(f"Total poems : {len(poems):,}")

    # 4. Train / val split (97.5 / 2.5)
    train_poems, val_poems = train_test_split(
        poems, test_size=0.025, random_state=42, shuffle=True
    )
    print(f"Train : {len(train_poems):,}  |  Val : {len(val_poems):,}")

    # 5. Save JSONL
    os.makedirs("data/processed", exist_ok=True)

    for split, data in [("train", train_poems), ("val", val_poems)]:
        path = f"data/processed/{split}.jsonl"
        with open(path, "w", encoding="utf-8") as f:
            for poem in data:
                f.write(json.dumps(poem, ensure_ascii=False) + "\n")
        print(f"Saved {path}")

    print("\nDone!")