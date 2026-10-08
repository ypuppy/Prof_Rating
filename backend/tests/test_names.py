import pytest

from names import name_words, normalize_name


@pytest.mark.parametrize("raw, key", [
    ("Dr. Alex Lim", "alexlim"),
    ("alex lim", "alexlim"),
    ("  ALEX   LIM ", "alexlim"),
    ("Assoc Prof Moon-Young Song", "moonyoungsong"),
    ("Prof Dr  Lee", "lee"),                # stacked titles
    ("A/P Tan", "tan"),
    ("Mr.Tan", "tan"),                      # no space after the dot
    ("Drew Barry", "drewbarry"),            # "Dr" inside a real name is kept
    ("Émile Zola", "emilezola"),            # accents folded
    ("Nguyễn Văn An", "nguyenvanan"),
    ("Dr", "dr"),                           # only a title: keep it rather than ""
])
def test_normalize_name(raw, key):
    assert normalize_name(raw) == key


def test_name_words_keeps_word_boundaries():
    assert name_words("Dr. Moon-Young  Song") == "moon young song"
    assert name_words("Émile Zola") == "emile zola"
