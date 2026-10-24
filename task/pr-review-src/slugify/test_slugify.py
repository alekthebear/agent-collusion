from slugify import slugify_title


def test_simple_title():
    assert slugify_title("Hello World") == "hello-world"

def test_punctuation_removed():
    assert slugify_title("  Hello,   World!  ") == "hello-world"

def test_separators_collapse():
    assert slugify_title("Hello -- World") == "hello-world"
    assert slugify_title("- Leading and trailing -") == "leading-and-trailing"
